#!/bin/bash
set -e

echo "Article Collector setup"
echo "======================="

echo ""
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

echo ""
if command -v lark-cli >/dev/null 2>&1; then
    echo "lark-cli is installed."
else
    echo "lark-cli is required for Feishu Base, Docs, and IM operations."
    echo "Install it first, then rerun setup."
    exit 1
fi

echo ""
if [ ! -f backend/.env ]; then
    cp backend/.env.example backend/.env
    echo "Created backend/.env from backend/.env.example."
else
    echo "backend/.env already exists; leaving it unchanged."
fi

echo ""
echo "Next steps:"
echo "1. Edit backend/.env and fill in your own API and Feishu values."
echo "2. Required model config: BASE_URL/AUTH_TOKEN/AI_MODEL, mapped to AI_* or ANTHROPIC_* variables."
echo "3. Required Feishu config: FEISHU_BASE_APP_TOKEN, FEISHU_ARTICLES_TABLE_ID, FEISHU_IM_CHAT_ID."
echo "4. Start the queue server with: ./run.sh"
echo "5. Load chrome-extension/ in Chrome via Developer Mode -> Load unpacked."

echo ""
echo "Setup complete."
