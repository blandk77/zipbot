from asyncio import get_running_loop
from shutil import rmtree
from pathlib import Path
import logging
import os
import asyncio
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.events import NewMessage
from telethon.tl.custom import Message

import pymongo
from utils import download_files, add_to_zip  # Imported functions
from cmds import register_commands #Imported Register commands

load_dotenv()

API_ID = int(os.environ['API_ID'])
API_HASH = os.environ['API_HASH']
BOT_TOKEN = os.environ['BOT_TOKEN']
CONC_MAX = int(os.environ.get('CONC_MAX', 3))
LOGS_CHANNEL = int(os.environ.get('LOGS_CHANNEL', 0))  # Added logs channel
FILES_CHANNEL = int(os.environ.get('FILES_CHANNEL', 0)) # Added files channel
STORAGE = Path('./files/')
os.makedirs(STORAGE, exist_ok=True)
MONGO_URL = os.environ['MONGO_URL']  # Make MONGO_URL required
ADMIN_USER_ID = int(os.environ.get('ADMIN_USER_ID', 0))
PREMIUM_DAYS = int(os.environ.get('PREMIUM_DAYS', 28))
DAILY_LIMIT_GB = int(os.environ.get('DAILY_LIMIT_GB', 6))
PAID_PLANS = os.environ.get('PAID_PLANS', "Premium Plan: Unlimited Download for 28 Days. Price: [Enter price] INR")
UPI_DETAILS = os.environ.get('UPI_DETAILS', "your_upi_id@examplebank")
DB_NAME = os.environ.get("DB_NAME", "telegram_zip_bot")
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "user_data")  # Single collection name
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


if __name__ == '__main__':
    register_commands(bot, tasks, stop_download, zip_names, STORAGE, DAILY_LIMIT_GB, IS_PREMIUM, user_collection, PREMIUM_DAYS, PAID_PLANS, UPI_DETAILS, ADMIN_USER_ID, FILES_CHANNEL, check_daily_limit, get_running_loop, rmtree, download_files, add_to_zip, logging, is_premium_user, add_premium_user, get_daily_usage, set_daily_usage, bot.get_entity) #Added functions and get_entity and bot
    loop = asyncio.get_event_loop()
    loop.run_until_complete(send_start_message())
    bot.run_until_disconnected()
