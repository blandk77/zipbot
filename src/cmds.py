import asyncio
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from functools import partial
from pyrogram import Client, filters
from pyrogram.types import Message

# Define a type alias for message events
MessageEvent = Message

def register_commands(bot: Client, tasks, stop_download, zip_names, STORAGE, DAILY_LIMIT_GB, IS_PREMIUM,
                      user_collection, PREMIUM_DAYS, PAID_PLANS, UPI_DETAILS, ADMIN_USER_ID,
                      FILES_CHANNEL, check_daily_limit, get_running_loop, rmtree,
                      download_files, add_to_zip, logging, is_premium_user, add_premium_user,
                      get_daily_usage, set_daily_usage):

    @bot.on_message(filters.command("start"))
    async def start_command_handler(client: Client, message: MessageEvent):
        await message.reply_text(
            "Hello! I am a bot that can help you zip files from Telegram.\n"
            "Use /help to see available commands."
        )

    @bot.on_message(filters.command("help"))
    async def help_command_handler(client: Client, message: MessageEvent):
        await message.reply_text(
            "Available commands:\n"
            "/start - Starts the bot and shows a welcome message.\n"
            "/help - Shows this help message.\n"
            "/zip <filename> - Notifies the bot that you are going to send files to be zipped. Filename must be specified\n"
            "/done -  Zips the files you sent after using /zip.\n"
            "/cancel - Cancels the current zipping task and removes the files from the queue.\n"
            "/stop - Stops the downloading process but does not remove files from queue\n"
            "/myplan - Shows your current plan.\n"
            "/buy - Shows available premium plans.\n"
            "/addpremium <user_id> - Adds premium to a user (Admin only).\n\n"
            "Example usage:\n"
            "1. /zip my_archive\n"
            "2. Send the files you want to zip.\n"
            "3. /done\n\n"
            "The bot will then create a file named `my_archive.zip` containing all the files you sent."
        )

    @bot.on_message(filters.command("myplan"))
    async def myplan_command_handler(client: Client, message: MessageEvent):
        sender_id = message.from_user.id
        is_premium = await is_premium_user(sender_id)
        if is_premium:
            try:
                user = user_collection.find_one({'user_id': sender_id})
                expiry_date = user['expiry_date'].replace(tzinfo=timezone.utc).astimezone(tz=None)
                await message.reply_text(f'You are a premium user. Your subscription expires on {expiry_date.strftime("%Y-%m-%d %H:%M:%S")}')
            except Exception as e:
                logging.error(f"Error displaying premium plan: {e}")
                await message.reply_text("Error fetching your premium plan details.")
        else:
            await message.reply_text(f'You are a free user. Your daily limit is {DAILY_LIMIT_GB} GB.')

    @bot.on_message(filters.command("buy"))
    async def buy_command_handler(client: Client, message: MessageEvent):
        if IS_PREMIUM:
            await message.reply_text(f'{PAID_PLANS}\nPayment Details (UPI): {UPI_DETAILS}')
        else:
            await message.reply_text('Premium plans are currently disabled.')

    @bot.on_message(filters.command("addpremium") & filters.user(ADMIN_USER_ID))
    async def add_premium_command_handler(client: Client, message: MessageEvent):
        if len(message.command) < 2:
            await message.reply_text("Usage: /addpremium <user_id>")
            return

        try:
            user_id = int(message.command[1])
            user = await client.get_users(user_id)
            username = user.username or user.first_name
        except Exception:
            await message.reply_text("Invalid user ID.")
            return

        if await add_premium_user(user_id):
            await message.reply_text(f'{username} got premium enabled for {PREMIUM_DAYS} days.')
        else:
            await message.reply_text('Failed to add premium user (database error).')

    @bot.on_message(filters.command("zip"))
    async def start_task_handler(client: Client, message: MessageEvent):
        if len(message.command) < 2:
            await message.reply_text("Usage: /zip <filename>")
            return

        sender_id = message.from_user.id
        tasks[sender_id] = []
        stop_download[sender_id] = False
        zip_names[sender_id] = message.command[1]

        await message.reply_text('OK, send me some files. Use /done when finished.')

    @bot.on_message(filters.private & filters.media & filters.create(lambda _, __, m: m.from_user.id in tasks))
    async def add_file_handler(client: Client, message: MessageEvent):
        sender_id = message.from_user.id
        file_size = message.media.document.size if message.media.document else message.media.photo.size

        if not await check_daily_limit(sender_id, file_size):
            await message.reply_text(f"Sorry, you have exceeded your daily limit of {DAILY_LIMIT_GB} GB. Use /buy to upgrade to premium.")
            return

        tasks[sender_id].append(message.id)

    @bot.on_message(filters.command("done"))
    async def zip_handler(client: Client, message: MessageEvent):
        sender_id = message.from_user.id
        if sender_id not in tasks:
            await message.reply_text('You must use /zip first.')
            return
        elif not tasks[sender_id]:
            await message.reply_text('You must send me some files first.')
            return
        elif sender_id not in zip_names:
            await message.reply_text('Filename not specified. Use /zip <filename> first.')
            return

        message_ids = tasks[sender_id]
        messages = []
        for msg_id in message_ids:
            try:
                msg = await client.get_messages(message.chat.id, message_ids=msg_id)
                if msg:
                    messages.append(msg)
            except Exception as e:
                logging.error(f"Error retrieving message: {e}")
                await message.reply_text(f"Error retrieving one of the files, skipping. Check logs.")
                continue

        zip_size = sum(
            [msg.media.document.size if msg.media.document else msg.media.photo.size for msg in messages if
             msg.media])

        if zip_size > 2048 * 1024 * 1024:  # 2GB Limit
            await message.reply_text('Total filesize must not exceed 2.0 GB.')
            return

        root = STORAGE / f'{sender_id}/'
        os.makedirs(root, exist_ok=True)
        zip_name = root / (zip_names[sender_id] + '.zip')
        zip_name_str = str(zip_name)

        total_files = len(messages)
        files_downloaded = 0
        start_time = time.time()

        progress_message = await message.reply_text("Starting download...")
        progress_message_id = progress_message.id

        async def download_and_add_file(message, file_number, zip_size, progress_message, start_time):
            try:
                if stop_download[sender_id]:
                    await message.reply_text("Download stopped by user.")
                    return False

                file_path = await download_files(message, root, client, progress_message, total_files, file_number, start_time, zip_size)

                if file_path:
                    await get_running_loop().run_in_executor(
                        None, partial(add_to_zip, zip_name_str, file_path))
                    nonlocal files_downloaded
                    files_downloaded += 1
                    return True
                else:
                    await message.reply_text("Failed to download file")
                    return False
            except Exception as e:
                await message.reply_text(f"Error processing file: {e}")
                return False

        download_tasks = [download_and_add_file(message, i + 1, zip_size, progress_message, start_time) for i, message in
                          enumerate(messages)]
        results = await asyncio.gather(*download_tasks)

        end_time = time.time()
        total_time = end_time - start_time

        if all(results):
            await message.reply_text(f"All files downloaded and zipped in {total_time:.2f} seconds.")
            try:
                await client.send_document(message.chat.id, zip_name_str, caption="Done!")
                if FILES_CHANNEL:
                    try:
                        await client.send_document(FILES_CHANNEL, zip_name_str,
                                                  caption=f"User {sender_id} zipped file {zip_names[sender_id]}.zip")
                    except Exception as e:
                        logging.error(f"Failed to send zipped file to files channel: {e}")

            except Exception as e:
                await message.reply_text(f"Error sending zipped file: {e}")

        else:
            await message.reply_text("Zipping process incomplete due to errors or user stop.")

        try:
            await get_running_loop().run_in_executor(None, rmtree, str(root))
        except Exception as e:
            logging.error(f"Error deleting directory: {e}")

        tasks.pop(sender_id)
        stop_download.pop(sender_id)
        zip_names.pop(sender_id)

    @bot.on_message(filters.command("cancel"))
    async def cancel_handler(client: Client, message: MessageEvent):
        sender_id = message.from_user.id
        try:
            tasks.pop(sender_id)
            stop_download.pop(sender_id)
            zip_names.pop(sender_id)
            await message.reply_text('Zipping task cancelled and files removed from queue. Use /zip for a new one.')
        except KeyError:
            await message.reply_text('No active zipping task to cancel.')

    @bot.on_message(filters.command("stop"))
    async def stop_handler(client: Client, message: MessageEvent):
        sender_id = message.from_user.id
        if sender_id in stop_download:
            stop_download[sender_id] = True
            await message.reply_text("Stopping the download process...")
        else:
            await message.reply_text("No active download to stop. Please use /zip first.")
