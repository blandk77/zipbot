import asyncio
import time
from pathlib import Path
from zipfile import ZipFile

from pyrofork import Client
from pyrofork.types import Message

async def download_files(message: Message, root: Path, client: Client, progress_message, total_files, file_number, start_time, total_size):
    try:
        # Determine file name
        if message.media.document and message.media.document.file_name:
            file_name = message.media.document.file_name
        elif message.media.photo:
            file_name = f"photo_{message.id}.jpg"  # Or a more appropriate extension
        else:
            file_name = str(message.id)  # Fallback to message ID

        file_path = root / file_name
        file_path_str = str(file_path)
        start_dl_time = time.time()

        async def callback(current, total):
            nonlocal start_dl_time
            current_time = time.time()
            time_taken = current_time - start_dl_time
            speed = current / time_taken if time_taken > 0 else 0
            speed_mbps = speed / (1024 * 1024)
            remaining_files = total_files - file_number

            minutes = int((current_time - start_time) // 60)
            seconds = int((current_time - start_time) % 60)

            progress_message_text = (
                "========Status========\n"
                "Downloading File: {}/{}/{}\n"
                "Time Taken: {}m {}s\n"
                "Speed: {:.2f} MB/s\n"
                "To stop the process, use /stop"
            ).format(file_number, total_files, remaining_files, minutes, seconds, speed_mbps)

            try:
                await progress_message.edit_text(progress_message_text)
            except Exception as e:
                print(f"Error editing message: {e}")
                return

        # Download the file
        await client.download_media(message, file=file_path_str, progress=callback)
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
