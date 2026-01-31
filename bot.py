def main():
    # Start background tasks
    auto_refresh_cookies()
    cleanup_files()

    # Initialize workers
    initialize_workers()

    # Run the bot
    bot.infinity_polling()
