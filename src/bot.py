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

load_dotenv()

API_ID = int(os.environ['API_ID'])
API_HASH = os.environ['API_HASH']
BOT_TOKEN = os.environ['BOT_TOKEN']
CONC_MAX = int(os.environ.get('CONC_MAX', 3))
LOGS_CHANNEL = int(os.environ.get('LOGS_CHANNEL', 0))  # Added logs channel
STORAGE = Path('./files/')
os.makedirs(STORAGE, exist_ok=True)
MONGO_URL = os.environ.get('MONGO_URL')
ADMIN_USER_ID = int(os.environ.get('ADMIN_USER_ID', 0))
PREMIUM_DAYS = int(os.environ.get('PREMIUM_DAYS', 28))
DAILY_LIMIT_GB = int(os.environ.get('DAILY_LIMIT_GB', 6))
PAID_PLANS = os.environ.get('PAID_PLANS', "Premium Plan: Unlimited Download for 28 Days. Price: [Enter price] INR")
UPI_DETAILS = os.environ.get('UPI_DETAILS', "your_upi_id@examplebank")
DB_NAME = os.environ.get("DB_NAME", "telegram_zip_bot")
PREMIUM_USERS_COLLECTION_NAME = os.environ.get("PREMIUM_USERS_COLLECTION_NAME", "premium_users")
USAGE_COLLECTION_NAME = os.environ.get("USAGE_COLLECTION_NAME", "usage")

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

# Initialize MongoDB client
mongo_client = pymongo.MongoClient(MONGO_URL) if MONGO_URL else None
db = mongo_client[DB_NAME] if mongo_client else None # Specify the database name
premium_users_collection = db[PREMIUM_USERS_COLLECTION_NAME] if db else None #Specify the collection name
usage_collection = db[USAGE_COLLECTION_NAME] if db else None # Collection for usage data


bot = TelegramClient(
    'quick-zip-bot', api_id=API_ID, api_hash=API_HASH
).start(bot_token=BOT_TOKEN)


async def send_start_message():
    if LOGS_CHANNEL:
        try:
            await bot.send_message(LOGS_CHANNEL, "Bot started/restarted!")
        except Exception as e:
            logging.error(f"Failed to send start message to logs channel: {e}")

# MongoDB Functions
async def is_premium_user(user_id: int) -> bool:
    """Checks if a user is a premium user."""
    if not premium_users_collection:
        return False
    user = premium_users_collection.find_one({'user_id': user_id})
    if user and user.get('expiry_date') and user['expiry_date'] > datetime.utcnow():
        return True
    return False


async def add_premium_user(user_id: int):
    """Adds a user to the premium users collection."""
    if not premium_users_collection:
        return False
    expiry_date = datetime.utcnow() + timedelta(days=PREMIUM_DAYS)
    premium_users_collection.update_one(
        {'user_id': user_id},
        {'$set': {'expiry_date': expiry_date}},
        upsert=True
    )
    return True

async def get_daily_usage(user_id: int) -> int:
    """Gets a user's current daily usage in bytes"""
    if not usage_collection:
        return 0

    today = datetime.utcnow().date()
    start_of_day = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
    end_of_day = start_of_day + timedelta(days=1)

    usage_data = usage_collection.find_one({
        'user_id': user_id,
        'date': {'$gte': start_of_day, '$lt': end_of_day}
    })

    return usage_data.get('usage', 0) if usage_data else 0


async def set_daily_usage(user_id: int, usage: int):
    """Sets a user's current daily usage in bytes"""
    if not usage_collection:
        return

    today = datetime.utcnow().date()
    start_of_day = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
    end_of_day = start_of_day + timedelta(days=1)

    usage_collection.update_one(
        {
            'user_id': user_id,
            'date': {'$gte': start_of_day, '$lt': end_of_day}
        },
        {'$set': {'usage': usage, 'user_id': user_id, 'date': start_of_day}},
        upsert=True
    )


async def check_daily_limit(user_id: int, file_size: int) -> bool:
    """Checks if a user has exceeded their daily limit."""
    if await is_premium_user(user_id):
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
        '/addpremium <user_id> - Adds premium to a user (Admin only).\n\n'
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
        user = premium_users_collection.find_one({'user_id': sender_id})
        expiry_date = user['expiry_date'].replace(tzinfo=timezone.utc).astimezone(tz=None)
        await event.respond(f'You are a premium user. Your subscription expires on {expiry_date.strftime("%Y-%m-%d %H:%M:%S")}')
    else:
        await event.respond(f'You are a free user. Your daily limit is {DAILY_LIMIT_GB} GB.')
    raise StopPropagation


@bot.on(NewMessage(pattern='/buy'))
async def buy_command_handler(event: MessageEvent):
    await event.respond(f'{PAID_PLANS}\nPayment Details (UPI): {UPI_DETAILS}')
    raise StopPropagation


@bot.on(NewMessage(pattern='/addpremium (?P<user_id>\d+)'))
async def add_premium_command_handler(event: MessageEvent):
    sender_id = event.sender_id
    if sender_id == ADMIN_USER_ID:
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
    raise StopPropagation


async def download_files(message: Message, root: Path, bot: TelegramClient, event: MessageEvent, progress_message_id: int, total_files: int, file_number: int, start_time: float, total_size: int):
    """Downloads a file and returns its path."""
    try:
        filename = message.file.name or f'file_{file_number}'
        file_path = root / filename
        file_path_str = str(file_path)
        downloaded_bytes = 0
        previous_percentage = 0

        async def callback(current: int):
            nonlocal downloaded_bytes, previous_percentage
            downloaded_bytes = current
            percentage = min(int((downloaded_bytes / message.file.size) * 100), 100)  # Ensure percentage doesn't exceed 100

            if percentage > previous_percentage:
                elapsed_time = time.time() - start_time
                downloaded_size_mb = downloaded_bytes / (1024 * 1024)
                total_size_mb = total_size / (1024 * 1024)
                speed_mbps = downloaded_size_mb / elapsed_time if elapsed_time > 0 else 0

                remaining_bytes = message.file.size - downloaded_bytes
                estimated_remaining_time = remaining_bytes / (downloaded_bytes / elapsed_time) if downloaded_bytes > 0 else 0

                status_message = (
                    f"Downloading file {file_number}/{total_files}: {filename}\n"
                    f"{percentage}% completed\n"
                    f"Downloaded: {downloaded_size_mb:.2f} MB / {total_size_mb:.2f} MB\n"
                    f"Speed: {speed_mbps:.2f} MB/s\n"
                    f"Estimated time remaining: {estimated_remaining_time:.2f} seconds"
                )

                try:
                    await bot.edit_message(event.chat_id, progress_message_id, status_message)
                except Exception as e:
                    logging.warning(f"Failed to edit message: {e}")

                previous_percentage = percentage

        await bot.download_media(message, file=file_path_str, progress_callback=callback)
        return file_path_str
    except Exception as e:
        logging.error(f"Error downloading file: {e}")
        return None


def add_to_zip(zip_name: str, file_path: str):
    """Adds a file to a zip archive."""
    try:
        with zipfile.ZipFile(zip_name, 'a', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(file_path, os.path.basename(file_path))
    except Exception as e:
        logging.error(f"Error adding file to zip: {e}")



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

            async def download_and_add_file(message, file_number, total_size):
                nonlocal files_downloaded
                try:
                    if stop_download[sender_id]:
                        await bot.send_message(event.chat_id, "Download stopped by user.")
                        return False

                    file_path = await download_files(message, root, bot, event, progress_message_id, total_files, file_number, start_time, total_size)

                    if file_path:
                        await get_running_loop().run_in_executor(
                            None, partial(add_to_zip, zip_name_str, file_path))
                        files_downloaded += 1

                        return True
                    else:
                        await bot.send_message(event.chat_id, f"Failed to download file {file_number}/{total_files}")
                        return False
                except Exception as e:
                     await bot.send_message(event.chat_id, f"Error processing file {file_number}/{total_files}: {e}")
                     return False

            total_size = sum(message.file.size for message in messages if message.file)

            download_tasks = [download_and_add_file(message, i + 1, total_size) for i, message in enumerate(messages)]

            results = await asyncio.gather(*download_tasks)

            end_time = time.time()
            total_time = end_time - start_time

            if all(results):
                await bot.edit_message(event.chat_id, progress_message_id, f"All files downloaded and zipped in {total_time:.2f} seconds.")
                 # Send the zipped file
                try:
                    await bot.send_file(event.chat_id, zip_name_str, caption="Done!")
                except Exception as e:
                    await event.respond(f"Error sending zipped file: {e}")
            else:
                 await bot.edit_message(event.chat_id, progress_message_id, "Zipping process incomplete due to errors or user stop.")

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
