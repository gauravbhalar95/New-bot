from loguru import logger
import os

def setup_logging(log_level="INFO"):
    """Sets up Loguru logging configuration."""
    # Create 'logs' directory if it doesn't exist
    if not os.path.exists("logs"):
        os.makedirs("logs")

    log_file = "logs/bot.log"

    # Remove default logger to avoid duplicate logs
    logger.remove()

    # Add file and console handlers
    logger.add(log_file, format="{time} - {level} - {message}", level=log_level)
    logger.add(lambda msg: print(msg, end=""), format="{time} - {level} - {message}", level=log_level)

    return logger

# Example usage
logger = setup_logging()
logger.info("Bot logging initialized successfully!")
logger.warning("This is a warning message")
logger.error("This is an error message")