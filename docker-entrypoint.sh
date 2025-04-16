#!/bin/bash
set -e

# Add debugging
echo "[$(date)] Starting services..."

# Run update script
echo "[$(date)] Running update script..."
/app/update.sh

# Start the webhook server
echo "[$(date)] Starting webhook server..."
python webhook.py &
WEBHOOK_PID=$!

# More detailed health check
echo "[$(date)] Waiting for webhook server to be ready..."
max_retries=30
count=0
until curl -s http://localhost:8080/health >/dev/null 2>&1; do
    count=$((count + 1))
    if [ $count -ge $max_retries ]; then
        echo "[$(date)] Webhook server failed to start after $max_retries attempts"
        exit 1
    fi
    echo "[$(date)] Attempt $count: Waiting for webhook server..."
    sleep 2
done
echo "[$(date)] Webhook server is ready"

# Start the bot with logging
echo "[$(date)] Starting Telegram bot..."
python bot.py &
BOT_PID=$!
echo "[$(date)] Bot started with PID $BOT_PID"

# Handle shutdown gracefully
trap 'echo "[$(date)] Received SIGTERM, shutting down..."; kill $WEBHOOK_PID $BOT_PID; exit 0' SIGTERM

echo "[$(date)] All services started successfully"

# Monitor both processes
while kill -0 $WEBHOOK_PID $BOT_PID 2>/dev/null; do
    sleep 1
done

# If we get here, one of the processes died
echo "[$(date)] One of the processes died unexpectedly"
exit 1