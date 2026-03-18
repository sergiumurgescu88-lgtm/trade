#!/bin/bash
set -a
source /opt/neurotrade-omega/.env
set +a
cd /opt/neurotrade-omega
exec python3 bot.py
