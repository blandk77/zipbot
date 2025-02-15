import asyncio
import time
from pathlib import Path
from zipfile import ZipFile

async def download_files(message, root, bot, event, progress_message_id, total_files, file_number, start_time, total_size):
    try:
        file_path = root / message.file.name if message.file.name else root / str(message.id)
        file_path_str = str(file_path)
        start_dl_time = time.time()
        async def callback(downloaded, total):
            nonlocal start_dl_time
            current_time = time.time()
            time_taken = current_time - start_dl_time
            speed = downloaded / time_taken if time_taken > 0 else 0
            speed_mbps = speed / (1024 × 1024)
            remaining_files = total_files - file_number

            minutes = int((current_time - start_time) // 60)
            seconds = int((current_time - start_time) % 60)


            progress_message = (
                "========Status========\n"
                "Downloading File: {}/{}/{}\n"
                "Time Taken: {}m {}s\n"
                "Speed: {:.2f} MB/s\n"
                "To stop the process, use /stop"
            ).format(file_number, total_files,remaining_files, minutes, seconds, speed_mbps)
            try:
                await bot.edit_message(event.chat_id, progress_message_id, progress_message, parse_mode='html')
            except Exception as e:
                print(f"Error editing message: {e}")
                return

        await bot.download_media(message, file=file_path_str, progress_callback=callback)
        return file_path
    except Exception as e:
        print(f"Error downloading file: {e}")
        return None


def add_to_zip(zip_file_path, file_path):
    try:
        file_path = Path(file_path)
        zip_file_path = Path(zip_file_path)

        flag = 'a' if zip_file_path.is_file() else 'x'
        with ZipFile(zip_file_path, flag) as zfile:
            zfile.write(file_path, file_path.name)
    except Exception as e:
        print(f"Error adding to zip: {e}")
