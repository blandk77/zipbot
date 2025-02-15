from functools import partial
from asyncio import get_running_loop
from shutil import rmtree
from pathlib import Path
import logging
import os
import time  # Import the time module
import asyncio

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.events import NewMessage, StopPropagation
from telethon.tl.custom import Message

from utils import download_files, add_to_zip  # Assuming these are correctly defined in utils.py

load_dotenv()

API_ID = int(os.environ['API_ID'])  # Ensure API_ID is an integer
API_HASH = os.environ['API_HASH']
BOT_TOKEN = os.environ['BOT_TOKEN']
CONC_MAX = int(os.environ.get('CONC_MAX', 3))
STORAGE = Path('./files/')
os.makedirs(STORAGE, exist_ok=True) # Ensure storage directory exists

MessageEvent = NewMessage.Event | Message

logging.basicConfig(
    format='[%(levelname)s/%(asctime)s] %(name)s: %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
    ]
)

# dict to keep track of tasks for every user
tasks: dict[int, list[int]] = {}

bot = TelegramClient(
    'quick-zip-bot', api_id=API_ID, api_hash=API_HASH
).start(bot_token=BOT_TOKEN)


@bot.on(NewMessage(pattern='/start'))
async def start_command_handler(event: MessageEvent):
    """
    Handles the /start command.
    """
    await event.respond(
        'Hello! I am a bot that can help you zip files from Telegram.\n'
        'Use /help to see available commands.'
    )
    raise StopPropagation


@bot.on(NewMessage(pattern='/help'))
async def help_command_handler(event: MessageEvent):
    """
    Handles the /help command.
    """
    await event.respond(
        'Available commands:\n'
        '/start - Starts the bot and shows a welcome message.\n'
        '/help - Shows this help message.\n'
        '/add - Notifies the bot that you are going to send files to be zipped.\n'
        '/zip <filename> - Zips the files you sent after using /add.  Replace <filename> with the desired zip file name (without the .zip extension).\n'
        '/cancel - Cancels the current zipping task and clears the file list.\n\n'
        'Example usage:\n'
        '1. /add\n'
        '2. Send the files you want to zip.\n'
        '3. /zip my_archive\n\n'
        'The bot will then create a file named `my_archive.zip` containing all the files you sent.'
    )
    raise StopPropagation


@bot.on(NewMessage(pattern='/add'))
async def start_task_handler(event: MessageEvent):
    """
    Notifies the bot that the user is going to send the media.
    """
    tasks[event.sender_id] = []

    await event.respond('OK, send me some files.')

    raise StopPropagation


@bot.on(NewMessage(
    func=lambda e: e.sender_id in tasks and e.file is not None))
async def add_file_handler(event: MessageEvent):
    """
    Stores the ID of messages sent with files by this user.
    """
    tasks[event.sender_id].append(event.id)

    raise StopPropagation


@bot.on(NewMessage(pattern='/zip (?P<name>\w+)'))
async def zip_handler(event: MessageEvent):
    """
    Zips the media of messages corresponding to the IDs saved for this user in
    tasks. The zip filename must be provided in the command.
    """
    sender_id = event.sender_id  # Store sender_id in a variable
    if sender_id not in tasks:
        await event.respond('You must use /add first.')
    elif not tasks[sender_id]:
        await event.respond('You must send me some files first.')
    else:
        messages = await bot.get_messages(
            sender_id, ids=tasks[sender_id])
        zip_size = sum([m.file.size for m in messages if m.file])  # Only sum sizes of messages with files

        if zip_size > 1024 * 1024 * 2000:   # zip_size > 1.95 GB approximately
            await event.respond('Total filesize must not exceed 2.0 GB.')
        else:
            root = STORAGE / f'{sender_id}/'
            os.makedirs(root, exist_ok=True)
            zip_name = root / (event.pattern_match['name'] + '.zip')
            zip_name_str = str(zip_name)  # Convert to string for compatibility

            total_files = len(messages)
            files_downloaded = 0
            start_time = time.time()

            progress_message = await event.respond("Starting download...")
            progress_message_id = progress_message.id

            async def download_and_add_file(message, file_number):
                nonlocal files_downloaded  # Allows modification of the outer scope variable
                try:
                    file_path = await download_files(message, root, bot, event, progress_message_id, total_files, file_number) #changed arguments

                    if file_path:
                        await get_running_loop().run_in_executor(
                            None, partial(add_to_zip, zip_name_str, file_path))  # Pass string path
                        files_downloaded += 1
                        await bot.edit_message(
                            event.chat_id, progress_message_id,
                            f"Downloaded and added file {file_number}/{total_files}."
                        )
                    else:
                        await bot.send_message(event.chat_id, f"Failed to download file {file_number}/{total_files}")
                except Exception as e:
                     await bot.send_message(event.chat_id, f"Error processing file {file_number}/{total_files}: {e}")

            download_tasks = [download_and_add_file(message, i + 1) for i, message in enumerate(messages)]

            await asyncio.gather(*download_tasks) # Run downloads concurrently.
            end_time = time.time()
            total_time = end_time - start_time
            await bot.edit_message(event.chat_id, progress_message_id, f"All files downloaded and zipped in {total_time:.2f} seconds.")


            try:
                await bot.send_file(event.chat_id, zip_name_str, caption="Done!") # Use send_file instead of respond
            except Exception as e:
                await event.respond(f"Error sending zipped file: {e}")
            finally:
                try:
                    await get_running_loop().run_in_executor(
                        None, rmtree, str(root))  # rmtree expects a string path in linux based systems.
                except Exception as e:
                    logging.error(f"Error deleting directory: {e}")


        tasks.pop(sender_id)

    raise StopPropagation


@bot.on(NewMessage(pattern='/cancel'))
async def cancel_handler(event: MessageEvent):
    """
    Cleans the list of tasks for the user.
    """
    try:
        tasks.pop(event.sender_id)
        await event.respond('Canceled zip. For a new one, use /add.')
    except KeyError:
        await event.respond('No active zipping task to cancel.')

    raise StopPropagation


if __name__ == '__main__':
    bot.run_until_disconnected()
