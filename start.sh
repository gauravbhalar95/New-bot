#!/bin/bash
python bot.py &
python run.py &
python keep_alive.py &
python config.py &
wait