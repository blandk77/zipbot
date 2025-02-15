from functools import partial
from asyncio import get_running_loop
from shutil import rmtree
from pathlib import Path
import logging
import os

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.events import NewMessage, StopPropagation
from telethon.tl.custom import Message

from utils import download_files, add_to_zip

load_dotenv()

API_ID = os.environ['API_ID']
API_HASH = os.environ['API_HASH']
BOT_TOKEN = os.environ['BOT_TOKEN']
CONC_MAX = int(os.environ.get('CONC_MAX', 3))
STORAGE = Path('./files/')

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
        '/zip <filename> - Zips the files you sent after using /add.  Replace <filename> with the desired zip file name (without the .zip extension).\n\n'
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
    Stores the ID of messages sended with files by this user.
    """
    tasks[event.sender_id].append(event.id)

    raise StopPropagation


@bot.on(NewMessage(pattern='/zip (?P<name>\w+)'))
async def zip_handler(event: MessageEvent):
    """
    Zips the media of messages corresponding to the IDs saved for this user in
    tasks. The zip filename must be provided in the command.
    """
    if event.sender_id not in tasks:
        await event.respond('You must use /add first.')
    elif not tasks[event.sender_id]:
        await event.respond('You must send me some files first.')
    else:
        messages = await bot.get_messages(
            event.sender_id, ids=tasks[event.sender_id])
        zip_size = sum([m.file.size for m in messages])

        if zip_size > 1024 * 1024 * 2000:   # zip_size > 1.95 GB approximately
            await event.respond('Total filesize don\'t must exceed 2.0 GB.')
        else:
            root = STORAGE / f'{event.sender_id}/'
            zip_name = root / (event.pattern_match['name'] + '.zip')

            async for file in download_files(messages, CONC_MAX, root):
                await get_running_loop().run_in_executor(
                    None, partial(add_to_zip, zip_name, file))
            
            await event.respond('Done!', file=zip_name)

            await get_running_loop().run_in_executor(
                None, rmtree, STORAGE / str(event.sender_id))

        tasks.pop(event.sender_id)

    raise StopPropagation


@bot.on(NewMessage(pattern='/cancel'))
async def cancel_handler(event: MessageEvent):
    """
    Cleans the list of tasks for the user.
    """
    try:
        tasks.pop(event.sender_id)
    except KeyError:
        pass

    await event.respond('Canceled zip. For a new one, use /add.')

    raise StopPropagation


if __name__ == '__main__':
    bot.run_until_disconnected()
