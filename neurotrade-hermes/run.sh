#!/bin/bash
set -a
source /opt/neurotrade-hermes/.env
set +a
exec python3 /opt/neurotrade-hermes/bot.py
