import os

# Run auto-fix script before starting the bot
os.system("python auto_fix.py")

# Start the bot using Gunicorn
print("🚀 Starting the bot with Gunicorn...")
os.system("gunicorn --bind 0.0.0.0:8080 bot:app --workers 2 --timeout 120")