import logging
import os

def setup_logging():
    # Create 'logs' directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    logger = logging.getLogger(__name__)

    # Prevent adding duplicate handlers
    if not logger.hasHandlers():
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler("logs/bot.log"),
                logging.StreamHandler()
            ]
        )

    return logger