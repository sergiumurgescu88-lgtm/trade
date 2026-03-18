#!/bin/bash
set -a
source /opt/neurotrade-v3/.env
set +a
cd /opt/neurotrade-v3
exec python3 bot.py
