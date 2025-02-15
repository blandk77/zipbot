import asyncio
import time
from pathlib import Path
from zipfile import ZipFile

async def download_files(message, root, bot, event, progress_message_id, total_files, file_number):
    """
    Downloads a single file with progress reporting.

    Args:
        message: The Telegram message containing the file.
        root: The directory to save the file.
        bot: The TelegramClient instance.
        event: The NewMessage event.
        progress_message_id: The ID of the message to update with progress.
        total_files: The total number of files to download.
        file_number: The current file number being downloaded.

    Returns:
        The path to the downloaded file, or None on error.
    """
    try:
        file_path = root / message.file.name if message.file.name else root / str(message.id)
        file_path_str = str(file_path) # Convert to string
        start_time = time.time()

        async def callback(downloaded, total):
            nonlocal start_time
            current_time = time.time()
            time_taken = current_time - start_time
            speed = downloaded / time_taken if time_taken > 0 else 0
            speed_mbps = speed / (1024 * 1024)

            progress_message = (
                f"Downloading file {file_number}/{total_files}...\n"
                f"Downloaded: {downloaded / (1024 * 1024):.2f} MB / {total / (1024 * 1024):.2f} MB\n"
                f"Time taken: {time_taken:.2f} seconds\n"
                f"Speed: {speed_mbps:.2f} MB/s"
            )
            try:
                await bot.edit_message(event.chat_id, progress_message_id, progress_message)
            except Exception as e:
                print(f"Error editing message: {e}")  # Log to console for debugging
                return  # Stop downloading if the update fails.

        await bot.download_media(message, file=file_path_str, progress_callback=callback)
        return file_path
    except Exception as e:
        print(f"Error downloading file: {e}")
        return None


def add_to_zip(zip_file_path, file_path):
    """
    Appends a file to a zip file.

    Args:
        zip_file_path: The path to the zip file.
        file_path: The path to the file that must be added.
    """
    try:
        file_path = Path(file_path)  # Ensure it's a Path object
        zip_file_path = Path(zip_file_path)

        flag = 'a' if zip_file_path.is_file() else 'x'
        with ZipFile(zip_file_path, flag) as zfile:
            zfile.write(file_path, file_path.name) # Add the file to the zip archive
    except Exception as e:
        print(f"Error adding to zip: {e}")
