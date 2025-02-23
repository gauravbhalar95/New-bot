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

def log_info(logger, message):
    """Logs an info level message."""
    logger.info(message)

def log_warning(logger, message):
    """Logs a warning level message."""
    logger.warning(message)

def log_error(logger, message):
    """Logs an error level message."""
    logger.error(message)

def log_debug(logger, message):
    """Logs a debug level message."""
    logger.debug(message)

def log_critical(logger, message):
    """Logs a critical level message."""
    logger.critical(message)

