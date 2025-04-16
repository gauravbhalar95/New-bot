#!/bin/bash
set -e

# Run update script
/app/update.sh

# Start the webhook server
python webhook.py &
WEBHOOK_PID=$!

# Wait for webhook server to be ready
while ! nc -z localhost 8080; do
  sleep 0.1
done

# Start the bot
python bot.py &
BOT_PID=$!

# Handle shutdown gracefully
trap 'kill $WEBHOOK_PID $BOT_PID; exit 0' SIGTERM

# Keep container running and monitor child processes
wait