#!/bin/bash
set -e

cd "$(dirname "$0")/backend"

# 加载 .env
if [ -f .env ]; then
    set -a
    . ./.env
    set +a
fi

echo "启动 Article Collector queue server on http://127.0.0.1:5679/queue"
python3 queue_server.py
