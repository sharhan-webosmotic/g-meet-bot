#!/bin/bash

# Start Xvfb
Xvfb :99 -screen 0 1920x1080x24 &

# Wait for Xvfb to start
sleep 2

# Set display and run the bot
export DISPLAY=:99
python3 gmeet.py