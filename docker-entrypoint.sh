#!/bin/bash
set -e

# Run update script
/app/update.sh

# Start the webhook server
python webhook.py &
WEBHOOK_PID=$!

# Wait for webhook server to be ready (using curl instead of nc)
echo "Waiting for webhook server to start..."
until curl -s http://localhost:8080/health >/dev/null 2>&1; do
    sleep 1
done
echo "Webhook server is ready"

# Start the bot
python bot.py &
BOT_PID=$!

# Handle shutdown gracefully
trap 'kill $WEBHOOK_PID $BOT_PID; exit 0' SIGTERM

# Keep container running and monitor child processes
wait