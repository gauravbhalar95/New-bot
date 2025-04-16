#!/bin/bash
set -e

echo "[$(date)] Starting services..."

# Run update script
echo "[$(date)] Running update script..."
/app/update.sh

# Start the webhook server
echo "[$(date)] Starting webhook server..."
python webhook.py &
WEBHOOK_PID=$!

# Wait for webhook server to be ready
echo "[$(date)] Waiting for webhook server to start..."
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

# Start the bot with debug logging
echo "[$(date)] Starting Telegram bot..."
PYTHONUNBUFFERED=1 python bot.py &
BOT_PID=$!
echo "[$(date)] Bot started with PID $BOT_PID"

# Function to cleanup processes
cleanup() {
    echo "[$(date)] Received shutdown signal, cleaning up..."
    kill -TERM $WEBHOOK_PID $BOT_PID 2>/dev/null
    wait $WEBHOOK_PID $BOT_PID
    echo "[$(date)] Cleanup complete"
    exit 0
}

# Setup trap for cleanup
trap cleanup SIGTERM SIGINT

# Monitor both processes
while kill -0 $WEBHOOK_PID $BOT_PID 2>/dev/null; do
    sleep 1
done

# If we get here, one of the processes died unexpectedly
echo "[$(date)] One of the processes died unexpectedly"
exit 1