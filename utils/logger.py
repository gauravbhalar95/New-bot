import logging
import os

def setup_logging():
    # Create 'logs' directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Configure the logging settings
    logging.basicConfig(
        level=logging.INFO,  # Set the logging level to INFO
        format="%(asctime)s - %(levelname)s - %(message)s",  # Define the log message format
        handlers=[
            logging.FileHandler("logs/bot.log"),  # Log messages to a file
            logging.StreamHandler()  # Log messages to the console
        ]
    )

    # Create and return a logger instance
    logger = logging.getLogger(__name__)
    return logger


# Example usage
if __name__ == "__main__":
    logger = setup_logging()
    logger.info("Logging setup complete.")
    logger.warning("This is a warning.")
    logger.error("This is an error message.")