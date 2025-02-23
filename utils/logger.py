import logging
import os

def setup_logging(log_level=logging.INFO):
    """Sets up the logging configuration."""
    # Create 'logs' directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    logger = logging.getLogger("bot_logger")  # Use a unique name

    if not logger.hasHandlers():  # Prevent duplicate handlers
        logger.setLevel(log_level)  # Set log level from parameter

        file_handler = logging.FileHandler("logs/bot.log")
        stream_handler = logging.StreamHandler()

        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)
        stream_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)

    return logger

