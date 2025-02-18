web: gunicorn -b 0.0.0.0:$PORT webhook:app
worker1: python bot.py
worker2: python auto_fix.py
worker3: python handler_loader.py
release: ./install_ffmpeg.sh