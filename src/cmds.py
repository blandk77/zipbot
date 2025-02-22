from functools import partial
from telethon.events import NewMessage, StopPropagation
from telethon.tl.custom import Message
import os
import time #Imported time
import asyncio #Imported asyncio
from datetime import datetime, timedelta, timezone #Imported datetime

MessageEvent = NewMessage.Event | Message

def register_commands(bot, tasks, stop_download, zip_names, STORAGE, DAILY_LIMIT_GB, IS_PREMIUM, user_collection, PREMIUM_DAYS, PAID_PLANS, UPI_DETAILS, ADMIN_USER_ID, FILES_CHANNEL, check_daily_limit, get_running_loop, rmtree, download_files, add_to_zip, logging, is_premium_user, add_premium_user, get_daily_usage, set_daily_usage, get_entity): #Added functions and get_entity and bot
    @bot.on(NewMessage(pattern='/start'))
    async def start_command_handler(event: MessageEvent):
        await event.respond(
            '<blockquote><b>Hᴇʟʟᴏ ᴛʜᴇʀᴇ! \n\nIᴍ ᴀ ᴀᴅᴠᴀɴᴄᴇ ғɪʟᴇs ᴢɪᴘ ʙᴏᴛ! I ᴄᴀɴ ᴢɪᴘ ғɪʟᴇs ᴛɪʟʟ 2ɢʙ ᴀɴᴅ Iᴍ ғʀᴇᴇ ᴛᴏ ᴜsᴇ 🤩. Iᴍ ᴀ ʙᴏᴛ ʙʏ</b> <a href="https://t.me/The_TGguy">𝑇𝑒𝑙𝑒𝑔𝑟𝑎𝑚 𝐺𝑢𝑦</a>!!\n\n<i>==&gt;</i> <a href="https://t.me/The_TGguy">𝑈𝑝𝑑𝑎𝑡𝑒𝑠 𝐶ℎ𝑎𝑛𝑛𝑒𝑙</a> \n\n<i>==&gt;</i> <a href="https://t.me/Tg_Guy_Support">𝑆𝑢𝑝𝑝𝑜𝑟𝑡 𝑔𝑟𝑜𝑢𝑝</a></blockquote>',
            parse_mode='html',
            link_preview=False
        )
        raise StopPropagation


    @bot.on(NewMessage(pattern='/help'))
    async def help_command_handler(event: MessageEvent):
        await event.respond(
            '<blockquote>Hᴏᴡ ᴛᴏ ᴜsᴇ ᴍᴇ??</blockquote>\n'

'Usᴇ /zip ᴡɪᴛʜ ᴀ ɴᴇᴡ ғɪʟᴇ ɴᴀᴍᴇ ᴡɪᴛʜᴏᴜᴛ ᴇxᴛᴇɴsɪᴏɴ \n'
'\n<blockquote>/zip TG</blockquote> \n'
'Tʜɪs ᴡɪʟʟ ᴍᴀᴋᴇ ᴛʜᴇ ғɪʟᴇ ɴᴀᴍᴇ ᴀs "TG" ᴀɴᴅ ᴛʜᴇɴ sᴇɴᴅ ᴀʟʟ ᴛʜᴇ ғɪʟᴇs ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴢɪᴘ (ʙᴏᴛ ᴄᴜʀʀᴇɴᴛʟʏ sᴜᴘᴘᴏʀᴛs 2ɢʙ ᴏɴʟʏ). Sᴇɴᴅ /done ᴀғᴛᴇʀ sᴇɴᴅɪɴɢ ᴀʟʟ ᴛʜᴇ ғɪʟᴇs. Tʜᴇ ғɪʟᴇs ᴡɪʟʟ sᴛᴀʀᴛ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ ᴀɴᴅ ᴜᴘʟᴏᴀᴅ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ.'

'\n\n<b>Available commands</b>:\n'
'<blockquote expandable><i>/start</i> - <code>Starts the bot and shows a welcome message</code>.\n'
'<i>/help</i> - <code>Shows this help message</code>.\n'
'<i>/zip</i><i> &lt;filename&gt;</i> - <code>Notifies the bot that you are going to send files to be zipped. Filename must be specified</code>\n'
'<i>/done</i> -  <code>Zips the files you sent after using /zip</code>.\n'
'<i>/cancel</i> - <code>Cancels the current zipping task and removes the files from the queue.</code>\n'
'<i>/stop</i> - <code>Stops the downloading process but does not remove files from queue</code>\n'
'<i>/myplan</i> - <code>Shows your current plan</code>.\n'
'<i>/buy</i> - <code>Shows available premium plans.</code>\n </blockquote>',
            parse_mode='html'
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
                await event.respond(f'÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷\n\n~ Pʟᴀɴ: 𝑷𝒓𝒆𝒎𝒊𝒖𝒎 ★ \n~ Pʟᴀɴ Vᴀʟɪᴅɪᴛʏ: {PREMIUM_DAYS}  𝒅𝒂𝒚𝒔 \n~ Pʟᴀɴ ᴇxᴘɪʀʏ ᴅᴀᴛᴇ:  {expiry_date.strftime("%Y-%m-%d %H:%M:%S")}\n~ Lɪᴍɪᴛ: 𝑵𝒐𝒏𝒆\n\n÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷', parse_mode='html')
            except Exception as e:
                logging.error(f"Error displaying premium plan: {e}")
                await event.respond("Error fetching your premium plan details.", parse_mode='html')
        else:
            await event.respond(f'÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷\n\n~ Pʟᴀɴ: 𝑭𝒓𝒆𝒆 °=° \n~ Pʟᴀɴ Vᴀʟɪᴅɪᴛʏ: 𝑳𝒊𝒇𝒆𝒍𝒐𝒏𝒈 \n~ Pʟᴀɴ ᴇxᴘɪʀʏ ᴅᴀᴛᴇ: 𝑵𝒐𝒏𝒆 \n~ Lɪᴍɪᴛ: {DAILY_LIMIT_GB} GB/Per day \n\n÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷÷\n\n𝚃𝚘 𝚙𝚞𝚛𝚌𝚑𝚊𝚜𝚎 𝚊 𝚙𝚕𝚊𝚗, 𝚜𝚎𝚎 /buy', parse_mode='html')
        raise StopPropagation


    @bot.on(NewMessage(pattern='/buy'))
    async def buy_command_handler(event: MessageEvent):
        if IS_PREMIUM:
            await event.respond(f'{PAID_PLANS}\n<i>Payment Details</i>: <code>{UPI_DETAILS}</code>.\n<i>A bot by @The_TGguy!</i>', parse_mode='html', link_preview=False)
        else:
            await event.respond('I am currently free to use without any limit 🤩\nJoin @The_TGguy.', parse_mode='html')
        raise StopPropagation


    @bot.on(NewMessage(pattern='/addpremium (?P<user_id>\d+)'))
    async def add_premium_command_handler(event: MessageEvent):
        sender_id = event.sender_id
        if sender_id == ADMIN_USER_ID:
            user_id = int(event.pattern_match['user_id'])
            try:
                user = await get_entity(user_id) #Here
                username = user.username or user.first_name
            except Exception:
                username = str(user_id)  # If can't fetch user, just use ID string
            if await add_premium_user(user_id):
                await event.respond(f'{username} got premium enabled for {PREMIUM_DAYS} days.', parse_mode='html')
            else:
                await event.respond('Failed to add premium user (database error).', parse_mode='html')
            return #Early return to avoid error in non-admin.
        await event.respond('You are not authorized to use this command.', parse_mode='html')
        raise StopPropagation



    @bot.on(NewMessage(pattern='/zip (?P<name>\w+)'))
    async def start_task_handler(event: MessageEvent):
        sender_id = event.sender_id
        tasks[sender_id] = []
        stop_download[sender_id] = False
        zip_names[sender_id] = event.pattern_match['name']

        await event.respond('OK, send me some files. Use /done when finished.', parse_mode='html')
        print(f"start_task_handler: tasks = {tasks}") #Added for debugging
        raise StopPropagation


    @bot.on(NewMessage(
        func=lambda e: e.sender_id in tasks and e.file is not None))
    async def add_file_handler(event: MessageEvent):
        sender_id = event.sender_id
        file_size = event.file.size

        if not await check_daily_limit(sender_id, file_size):
            await event.respond(f"Sorry, you have exceeded your daily limit of {DAILY_LIMIT_GB} GB. Use /buy to upgrade to premium.", reply_to=event.id, parse_mode='html')
            return

        tasks[event.sender_id].append(event.id)
        print(f"add_file_handler: tasks = {tasks}") #Added for debugging
        raise StopPropagation



    @bot.on(NewMessage(pattern='/done'))
    async def zip_handler(event: MessageEvent):
        sender_id = event.sender_id
        if sender_id not in tasks:
            await event.respond('You must use /zip first.', parse_mode='html')
        elif not tasks[sender_id]:
            await event.respond('You must send me some files first.', parse_mode='html')
        elif sender_id not in zip_names:
            await event.respond('Filename not specified. Use /zip <filename> first.', parse_mode='html')
        else:
            messages = await bot.get_messages(
                sender_id, ids=tasks[sender_id])
            zip_size = sum([m.file.size for m in messages if m.file])

            if zip_size > 1024 * 1024 * 2000:
                await event.respond('Total filesize must not exceed 2.0 GB.', parse_mode='html')
            else:
                root = STORAGE / f'{sender_id}/'
                os.makedirs(root, exist_ok=True)
                zip_name = root / (zip_names[sender_id] + '.zip')
                zip_name_str = str(zip_name)

                total_files = len(messages)
                files_downloaded = 0
                start_time = time.time()

                progress_message = await event.respond("Starting download...", parse_mode='html')
                progress_message_id = progress_message.id


                async def download_and_add_file(message, file_number, zip_size, event, progress_message_id, start_time): # Changed total_size to zip_size
                    try:
                        if stop_download[sender_id]:
                            await bot.send_message(event.chat_id, "Download stopped by user.", parse_mode='html')
                            return False

                        file_path = await download_files(message, root, bot, event, progress_message_id, total_files, file_number, start_time, zip_size) # Changed total_size to zip_size

                        if file_path:
                            await get_running_loop().run_in_executor(
                                None, partial(add_to_zip, zip_name_str, file_path))
                            nonlocal files_downloaded
                            files_downloaded += 1
                            return True
                        else:
                            await bot.send_message(event.chat_id, "Failed to download file", parse_mode='html')
                            return False
                    except Exception as e:
                        await bot.send_message(event.chat_id, f"Error processing file: {e}", parse_mode='html')
                        return False


                download_tasks = [download_and_add_file(message, i + 1, zip_size, event, progress_message_id, start_time) for i, message in enumerate(messages)] # Changed total_size to zip_size

                results = await asyncio.gather(*download_tasks)

                end_time = time.time()
                total_time = end_time - start_time

                if all(results):
                    #send the zip file
                        await bot.send_file(event.chat_id, zip_name_str, caption="Done!")
                        # Log to files channel
                        if FILES_CHANNEL:
                            try:
                                await bot.send_file(FILES_CHANNEL, zip_name_str, caption=f"User {sender_id} zipped file {zip_names[sender_id]}.zip")
                            except Exception as e:
                                logging.error(f"Failed to send zipped file to files channel: {e}")
                    except Exception as e:
                        await event.respond(f"Error sending zipped file: {e}", parse_mode='html')
                else:
                    await bot.send_message(event.chat_id, "Zipping process incomplete due to errors or user stop.", parse_mode='html')

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
            await event.respond('Zipping task cancelled and files removed from queue. Use /zip for a new one.', parse_mode='html')
        except KeyError:
            await event.respond('No active zipping task to cancel.', parse_mode='html')

        raise StopPropagation

    @bot.on(NewMessage(pattern='/stop'))
    async def stop_handler(event: MessageEvent):
        sender_id = event.sender_id
        if sender_id in stop_download:
            stop_download[sender_id] = True
            await event.respond("Stopping the download process...", parse_mode='html')
        else:
            await event.respond("No active download to stop. Please use /zip first.", parse_mode='html')
        raise StopPropagation
