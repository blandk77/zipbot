
from functools import partial
from asyncio import get_running_loop
from shutil import rmtree
from pathlib import Path
import logging
import os
import time
import asyncio

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.events import NewMessage, StopPropagation
from telethon.tl.custom import Message

# Import for web server
from aiohttp import web

load_dotenv()

API_ID = int(os.environ['API_ID'])
API_HASH = os.environ['API_HASH']
BOT_TOKEN = os.environ['BOT_TOKEN']
CONC_MAX = int(os.environ.get('CONC_MAX', 3))
LOGS_CHANNEL = int(os.environ.get('LOGS_CHANNEL', 0))
WEB_PORT = int(os.environ.get('PORT', 8080))  # Koyeb provides PORT
WEB_ROUTE = os.environ.get('WEB_ROUTE', '/')  # Route for web endpoint
STORAGE = Path('./files/')
os.makedirs(STORAGE, exist_ok=True)

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

bot = TelegramClient(
    'quick-zip-bot', api_id=API_ID, api_hash=API_HASH
).start(bot_token=BOT_TOKEN)

# --- Web Server ---
async def handle_web_request(request):
    """Handles web requests; returns a simple status message."""
    return web.Response(text="Telegram Bot is running!")

async def start_web_server():
    """Starts the aiohttp web server."""
    app = web.Application()
    app.add_routes([web.get(WEB_ROUTE, handle_web_request)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', WEB_PORT)  # Listen on all interfaces
    await site.start()
    logging.info(f"Web server started on port {WEB_PORT} at route {WEB_ROUTE}")

# --- Telegram Bot ---
async def send_start_message():
    if LOGS_CHANNEL:
        try:
            await bot.send_message(LOGS_CHANNEL, "Bot started/restarted!")
        except Exception as e:
            logging.error(f"Failed to send start message to logs channel: {e}")

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
        '/stop - Stops the downloading process but does not remove files from queue\n\n'
        'Example usage:\n'
        '1. /zip my_archive\n'
        '2. Send the files you want to zip.\n'
        '3. /done\n\n'
        'The bot will then create a file named `my_archive.zip` containing all the files you sent.'
    )
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
    tasks[event.sender_id].append(event.id)
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

async def main():
    """Main function to start both the bot and the web server."""
    await asyncio.gather(send_start_message(), start_web_server(), bot.run_until_disconnected())

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
