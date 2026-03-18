#!/bin/bash
set -a
source /opt/neurotrade-zeus/.env
set +a
cd /opt/neurotrade-zeus
exec python3 bot.py
