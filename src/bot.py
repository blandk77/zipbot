
from functools import partial
from asyncio import get_running_loop
from shutil import rmtree
from pathlib import Path
import logging
import os
import time
import asyncio
import zipfile
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.events import NewMessage, StopPropagation
from telethon.tl.custom import Message

import pymongo
from utils import download_files, add_to_zip #Imported functions

load_dotenv()

API_ID = int(os.environ['API_ID'])
API_HASH = os.environ['API_HASH']
BOT_TOKEN = os.environ['BOT_TOKEN']
CONC_MAX = int(os.environ.get('CONC_MAX', 3))
LOGS_CHANNEL = int(os.environ.get('LOGS_CHANNEL', 0))  # Added logs channel
STORAGE = Path('./files/')
os.makedirs(STORAGE, exist_ok=True)
MONGO_URL = os.environ['MONGO_URL']  # Make MONGO_URL required
OWNER_ID = int(os.environ.get('OWNER_ID', 0)) # Renamed ADMIN_USER_ID to OWNER_ID and used get() with default
PREMIUM_DAYS = int(os.environ.get('PREMIUM_DAYS', 28))
DAILY_LIMIT_GB = int(os.environ.get('DAILY_LIMIT_GB', 6))
PAID_PLANS = os.environ.get('PAID_PLANS', "Premium Plan: Unlimited Download for 28 Days. Price: [Enter price] INR")
UPI_DETAILS = os.environ.get('UPI_DETAILS', "your_upi_id@examplebank")
DB_NAME = os.environ.get("DB_NAME", "telegram_zip_bot")
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "user_data") # Single collection name
IS_PREMIUM = os.environ.get('IS_PREMIUM', 'False').lower() == 'true'  # Boolean premium mode

MessageEvent = NewMessage.Event | Message

logging.basicConfig(
    format='[%(levelname)s/%(asctime)s] %(name)s: %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
    ]
)

tasks: dict[int, list[int]] = {}
stop_download: dict[int, bool] = {}
zip_names: dict[int, str] = {}
download_semaphore = asyncio.Semaphore(CONC_MAX)  # Semaphore for download concurrency

# Initialize Telegram client
bot = TelegramClient('zipper', API_ID, API_HASH).start(bot_token=BOT_TOKEN)


# Initialize MongoDB client
try:
    mongo_client = pymongo.MongoClient(MONGO_URL)
    db = mongo_client[DB_NAME]  # Use the specified database name
    user_collection = db[COLLECTION_NAME]  # Single collection for all data
    logging.info("Connected to MongoDB")
except Exception as e:
    logging.error(f"Failed to connect to MongoDB: {e}")
    mongo_client = None
    db = None
    user_collection = None


async def send_start_message():
    if LOGS_CHANNEL:
        try:
            await bot.send_message(LOGS_CHANNEL, "Bot started/restarted!")
        except Exception as e:
            logging.error(f"Failed to send start message to logs channel: {e}")

# MongoDB Functions
async def is_premium_user(user_id: int) -> bool:
    """Checks if a user is a premium user."""
    if not IS_PREMIUM or user_collection is None:  # Check IS_PREMIUM flag
        return False
    try:
        user = user_collection.find_one({'user_id': user_id, 'is_premium': True})
        if user and user.get('expiry_date') and user['expiry_date'] > datetime.utcnow():
            return True
        return False
    except Exception as e:
        logging.error(f"Error checking premium user: {e}")
        return False


async def add_premium_user(user_id: int):
    """Adds a user to the premium users collection."""
    if not IS_PREMIUM or user_collection is None:  # Check IS_PREMIUM flag
        return False
    try:
        expiry_date = datetime.utcnow() + timedelta(days=PREMIUM_DAYS)
        user_collection.update_one(
            {'user_id': user_id},
            {'$set': {'expiry_date': expiry_date, 'is_premium': True}},  # Add is_premium flag
            upsert=True
        )
        return True
    except Exception as e:
        logging.error(f"Error adding premium user: {e}")
        return False

async def get_daily_usage(user_id: int) -> int:
    """Gets a user's current daily usage in bytes"""
    if not IS_PREMIUM or user_collection is None:
        return 0

    try:
        today = datetime.utcnow().date()
        start_of_day = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
        end_of_day = start_of_day + timedelta(days=1)

        usage_data = user_collection.find_one({
            'user_id': user_id,
            'date': {'$gte': start_of_day, '$lt': end_of_day}
        })

        return usage_data.get('usage', 0) if usage_data else 0
    except Exception as e:
        logging.error(f"Error getting daily usage: {e}")
        return 0


async def set_daily_usage(user_id: int, usage: int):
    """Sets a user's current daily usage in bytes"""
    if not IS_PREMIUM or user_collection is None:
        return

    try:
        today = datetime.utcnow().date()
        start_of_day = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
        end_of_day = start_of_day + timedelta(days=1)

        user_collection.update_one(
            {
                'user_id': user_id,
                'date': {'$gte': start_of_day, '$lt': end_of_day}
            },
            {'$set': {'usage': usage, 'user_id': user_id, 'date': start_of_day}},
            upsert=True
        )
    except Exception as e:
        logging.error(f"Error setting daily usage: {e}")


async def check_daily_limit(user_id: int, file_size: int) -> bool:
    """Checks if a user has exceeded their daily limit."""
    if IS_PREMIUM and await is_premium_user(user_id):
        return True

    daily_limit_bytes = DAILY_LIMIT_GB * 1024 * 1024 * 1024  # GB to bytes
    current_usage = await get_daily_usage(user_id)

    if current_usage + file_size <= daily_limit_bytes:
        await set_daily_usage(user_id, current_usage + file_size)
        return True
    else:
        return False


@bot.on(NewMessage(pattern='/start'))
async def start_command_handler(event: MessageEvent):
    await event.respond(
        'Hello! I am a bot that can help you zip files from Telegram.\n'
        'Use /help to see available commands.'
    )
    raise StopPropagation


@bot.on(NewMessage(pattern='/help'))
async def help_command_handler(event: MessageEvent):
    await event.respond(
        'Available commands:\n'
        '/start - Starts the bot and shows a welcome message.\n'
        '/help - Shows this help message.\n'
        '/zip <filename> - Notifies the bot that you are going to send files to be zipped. Filename must be specified\n'
        '/done -  Zips the files you sent after using /zip.\n'
        '/cancel - Cancels the current zipping task and removes the files from the queue.\n'
        '/stop - Stops the downloading process but does not remove files from queue\n'
        '/myplan - Shows your current plan.\n'
        '/buy - Shows available premium plans.\n'
        '/addpremium <user_id> - Adds premium to a user (Admin only).\n'
        '/broadcast <message> - Broadcast a message to all users (Owner only).\n\n'
        'Example usage:\n'
        '1. /zip my_archive\n'
        '2. Send the files you want to zip.\n'
        '3. /done\n\n'
        'The bot will then create a file named `my_archive.zip` containing all the files you sent.'
    )
    raise StopPropagation

@bot.on(NewMessage(pattern='/myplan'))
async def myplan_command_handler(event: MessageEvent):
    sender_id = event.sender_id
    is_premium = await is_premium_user(sender_id)
    if is_premium:
        try:
            user = user_collection.find_one({'user_id': sender_id})
            expiry_date = user['expiry_date'].replace(tzinfo=timezone.utc).astimezone(tz=None)
            await event.respond(f'You are a premium user. Your subscription expires on {expiry_date.strftime("%Y-%m-%d %H:%M:%S")}')
        except Exception as e:
            logging.error(f"Error displaying premium plan: {e}")
            await event.respond("Error fetching your premium plan details.")
    else:
        await event.respond(f'You are a free user. Your daily limit is {DAILY_LIMIT_GB} GB.')
    raise StopPropagation


@bot.on(NewMessage(pattern='/buy'))
async def buy_command_handler(event: MessageEvent):
    if IS_PREMIUM:
        await event.respond(f'{PAID_PLANS}\nPayment Details (UPI): {UPI_DETAILS}')
    else:
        await event.respond('Premium plans are currently disabled.')
    raise StopPropagation


@bot.on(NewMessage(pattern='/addpremium (?P<user_id>\d+)'))
async def add_premium_command_handler(event: MessageEvent):
    sender_id = event.sender_id
    if sender_id == OWNER_ID: # Changed from ADMIN_USER_ID to OWNER_ID
        user_id = int(event.pattern_match['user_id'])
        try:
            user = await bot.get_entity(user_id)
            username = user.username or user.first_name
        except Exception:
            username = str(user_id)  # If can't fetch user, just use ID string
        if await add_premium_user(user_id):
            await event.respond(f'{username} got premium enabled for {PREMIUM_DAYS} days.')
        else:
            await event.respond('Failed to add premium user (database error).')
        return #Early return to avoid error in non-admin.
    await event.respond('You are not authorized to use this command.')
    raise StopPropagation

@bot.on(NewMessage(pattern='/broadcast (?P<message>.*)'))
async def broadcast_command_handler(event: MessageEvent):
     sender_id = event.sender_id
     if sender_id == OWNER_ID:
        broadcast_message = event.pattern_match['message']
        all_users = user_collection.find({}) # Fetch all users from the database
        successful_broadcasts = 0
        failed_broadcasts = 0

        async for user in all_users:
            user_id = user["user_id"]
            try:
                await bot.send_message(user_id, broadcast_message)
                successful_broadcasts += 1
                await asyncio.sleep(0.1)  # Avoid hitting flood limits
            except Exception as e:
                logging.warning(f"Failed to send broadcast to user {user_id}: {e}")
                failed_broadcasts += 1

        await event.respond(
            f"Broadcast completed.\nSuccessful: {successful_broadcasts}\nFailed: {failed_broadcasts}"
        )
     else:
        await event.respond('You are not authorized to use this command.')
     raise StopPropagation


@bot.on(NewMessage(pattern='/zip (?P<name>\w+)'))
async def start_task_handler(event: MessageEvent):
    sender_id = event.sender_id
    tasks[sender_id] = []
    stop_download[sender_id] = False
    zip_names[sender_id] = event.pattern_match['name']

    await event.respond('OK, send me some files. Use /done when finished.')
    print(f"start_task_handler: tasks = {tasks}") #Added for debugging
    raise StopPropagation


@bot.on(NewMessage(
    func=lambda e: e.sender_id in tasks and e.file is not None))
async def add_file_handler(event: MessageEvent):
    sender_id = event.sender_id
    file_size = event.file.size

    if not await check_daily_limit(sender_id, file_size):
        await event.respond(f"Sorry, you have exceeded your daily limit of {DAILY_LIMIT_GB} GB. Use /buy to upgrade to premium.", reply_to=event.id)
        return

    tasks[event.sender_id].append(event.id)
    print(f"add_file_handler: tasks = {tasks}") #Added for debugging
    raise StopPropagation



@bot.on(NewMessage(pattern='/done'))
async def zip_handler(event: MessageEvent):
    sender_id = event.sender_id
    if sender_id not in tasks:
        await event.respond('You must use /zip first.')
    elif not tasks[sender_id]:
        await event.respond('You must send me some files first.')
    elif sender_id not in zip_names:
        await event.respond('Filename not specified. Use /zip <filename> first.')
    else:
        messages = await bot.get_messages(
            sender_id, ids=tasks[sender_id])
        zip_size = sum([m.file.size for m in messages if m.file])

        if zip_size > 1024 * 1024 * 2000:
            await event.respond('Total filesize must not exceed 2.0 GB.')
        else:
            root = STORAGE / f'{sender_id}/'
            os.makedirs(root, exist_ok=True)
            zip_name = root / (zip_names[sender_id] + '.zip')
            zip_name_str = str(zip_name)

            total_files = len(messages)
            files_downloaded = 0
            start_time = time.time()

            progress_message = await event.respond("Starting download...")
            progress_message_id = progress_message.id


            async def download_and_add_file(message, file_number, zip_size, event, progress_message_id, start_time): # Changed total_size to zip_size
                try:
                    if stop_download[sender_id]:
                        await bot.send_message(event.chat_id, "Download stopped by user.")
                        return False

                    file_path = await download_files(message, root, bot, event, progress_message_id, total_files, file_number, start_time, zip_size) # Changed total_size to zip_size

                    if file_path:
                        await get_running_loop().run_in_executor(
                            None, partial(add_to_zip, zip_name_str, file_path))
                        nonlocal files_downloaded
                        files_downloaded += 1
                        return True
                    else:
                        await bot.send_message(event.chat_id, "Failed to download file")
                        return False
                except Exception as e:
                    await bot.send_message(event.chat_id, f"Error processing file: {e}")
                    return False


            download_tasks = [download_and_add_file(message, i + 1, zip_size, event, progress_message_id, start_time) for i, message in enumerate(messages)] # Changed total_size to zip_size

            results = await asyncio.gather(*download_tasks)

            end_time = time.time()
            total_time = end_time - start_time

            if all(results):
                await bot.send_message(event.chat_id, f"All files downloaded and zipped in {total_time:.2f} seconds.")
                 # Send the zipped file
                try:
                    await bot.send_file(event.chat_id, zip_name_str, caption="Done!")
                except Exception as e:
                    await event.respond(f"Error sending zipped file: {e}")
            else:
                 await bot.send_message(event.chat_id, "Zipping process incomplete due to errors or user stop.")

            try:
                await get_running_loop().run_in_executor(
                    None, rmtree, str(root))
            except Exception as e:
                logging.error(f"Error deleting directory: {e}")

        tasks.pop(sender_id)
        stop_download.pop(sender_id)
        zip_names.pop(sender_id)

    raise StopPropagation


@bot.on(NewMessage(pattern='/cancel'))
async def cancel_handler(event: MessageEvent):
    sender_id = event.sender_id
    try:
        tasks.pop(sender_id)
        stop_download.pop(sender_id)
        zip_names.pop(sender_id)
        await event.respond('Zipping task cancelled and files removed from queue. Use /zip for a new one.')
    except KeyError:
        await event.respond('No active zipping task to cancel.')

    raise StopPropagation

@bot.on(NewMessage(pattern='/stop'))
async def stop_handler(event: MessageEvent):
    sender_id = event.sender_id
    if sender_id in stop_download:
        stop_download[sender_id] = True
        await event.respond("Stopping the download process...")
    else:
        await event.respond("No active download to stop. Please use /zip first.")
    raise StopPropagation


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(send_start_message())
    bot.run_until_disconnected()
