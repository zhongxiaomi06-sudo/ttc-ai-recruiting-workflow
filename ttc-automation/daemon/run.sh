#!/bin/bash
# Start the TTC local daemon
set -e
cd "$(dirname "$0")"
python3 -m venv venv 2>/dev/null || true
source venv/bin/activate
pip install -q -r requirements.txt
python ttc_daemon.py
