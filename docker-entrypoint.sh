#!/bin/bash
set -e

echo "[$(date)] Starting services..."

# Run update script if it exists
if [ -f "/app/update.sh" ]; then
    echo "[$(date)] Running update script..."
    /app/update.sh
fi

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

# Monitor the webhook process
while kill -0 $WEBHOOK_PID 2>/dev/null; do
    sleep 1
done

# If we get here, the webhook process died unexpectedly
echo "[$(date)] Webhook process died unexpectedly"
exit 1