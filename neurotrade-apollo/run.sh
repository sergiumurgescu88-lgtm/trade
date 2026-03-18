#!/bin/bash
set -a
source /opt/neurotrade-apollo/.env
set +a
cd /opt/neurotrade-apollo
exec python3 bot.py
