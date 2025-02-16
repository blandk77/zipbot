import asyncio
import time
from pathlib import Path
from zipfile import ZipFile
import logging

# Configure logging
logging.basicConfig(
    format='[%(levelname)s/%(asctime)s] %(name)s: %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
    ]
)


async def download_files(message, root, bot, event, progress_message_id, total_files, file_number, start_time, total_size):
    try:
        file_path = root / message.file.name if message.file.name else root / str(message.id)
        file_path_str = str(file_path)
        logging.info(f"Downloading file {file_number}/{total_files}: {file_path_str}")

        start_dl_time = time.time()
        downloaded_bytes = 0 # To track amount of downloaded bytes across callbacks
        last_update_time = time.time() # Track when the last update was sent


        async def callback(downloaded, total):
            nonlocal start_dl_time, downloaded_bytes, last_update_time
            downloaded_bytes = downloaded

            current_time = time.time()

            # Update progress message only every 5 seconds
            if current_time - last_update_time >= 5:
                time_elapsed = current_time - start_time
                speed = downloaded / time_elapsed if time_elapsed > 0 else 0
                speed_mbps = speed / (1024 * 1024)

                percentage = (downloaded / total) * 100
                percentage = min(percentage, 100)  # Cap to 100
                completed_blocks = int(percentage // 10)
                remaining_blocks = 10 - completed_blocks
                progress_bar = '█' * completed_blocks + '░' * remaining_blocks

                # Time elapsed calculations
                time_elapsed_str = format_time(time_elapsed)

                # ETA calculation
                if speed > 0:
                    time_remaining = (total_size - downloaded) / speed
                    eta_str = format_time(time_remaining)
                else:
                    eta_str = "Unknown"  # If speed is zero.

                progress_message = (
                    "✨ Process Status ⚙️\n\n"
                    f"  [{progress_bar}] {percentage:.0f}%\n\n"
                    f"  📂 Total Files: {total_files}\n"
                    f"  ✅ Completed: {file_number - 1}\n" #file_number is the file that is currently downloading
                    f"  📶 Network Speed: {speed_mbps:.2f} MB/s\n"
                    f"  ⏱️ Time Elapsed: {time_elapsed_str}\n"
                    f"  ⏰ ETA: {eta_str}"
                )

                try:
                    logging.info(f"Editing message {progress_message_id} with progress: {downloaded}/{total}")
                    await bot.edit_message(event.chat_id, progress_message_id, progress_message)
                    logging.info(f"Message {progress_message_id} edited successfully.")
                except Exception as e:
                    logging.exception(f"Error editing message: {e}")

                last_update_time = current_time # Update the time of the last update

        logging.info(f"Calling bot.download_media with file: {file_path_str}")
        await bot.download_media(message, file=file_path_str, progress_callback=callback)
        logging.info(f"Finished downloading file: {file_path_str}")

        # Delete the progress message after finishing download
        try:
            await bot.delete_messages(event.chat_id, progress_message_id)
            logging.info(f"Deleted progress message {progress_message_id}")
        except Exception as e:
            logging.exception(f"Error deleting progress message: {e}")

        return file_path
    except Exception as e:
        logging.exception(f"Error in download_files: {e}")
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


def format_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"
