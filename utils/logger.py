from loguru import logger
import os


def setup_logging(log_level="INFO"):
    """Set up Loguru logging for the bot."""
    if not os.path.exists("logs"):
        os.makedirs("logs")

    log_file = "logs/bot.log"

    # Remove the default logger to avoid duplicate logs.
    logger.remove()

    # Add file and console handlers.
    logger.add(log_file, format="{time} - {level} - {message}", level=log_level)
    logger.add(
        lambda msg: print(msg, end=""),
        format="{time} - {level} - {message}",
        level=log_level,
    )

    return logger
