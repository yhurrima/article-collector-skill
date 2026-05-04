#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.article-collector.queue"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

echo "Article Collector setup"
echo "======================="

echo ""
echo "Installing Python dependencies..."
pip3 install -r "$SCRIPT_DIR/requirements.txt"

echo ""
if command -v lark-cli >/dev/null 2>&1; then
    echo "lark-cli is installed."
else
    echo "lark-cli is required for Feishu Base, Docs, and IM operations."
    echo "Install it first, then rerun setup."
    exit 1
fi

echo ""
if [ ! -f "$SCRIPT_DIR/backend/.env" ]; then
    cp "$SCRIPT_DIR/backend/.env.example" "$SCRIPT_DIR/backend/.env"
    echo "Created backend/.env from backend/.env.example."
else
    echo "backend/.env already exists; leaving it unchanged."
fi

# --- launchd auto-start setup ---
echo ""
read -p "Enable queue server auto-start on login? (Y/n) " -n 1 -r REPLY
echo ""
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    mkdir -p "$HOME/Library/LaunchAgents"
    mkdir -p "$HOME/.article-collector"

    cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${SCRIPT_DIR}/run.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${HOME}/.article-collector/queue-server.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/.article-collector/queue-server.log</string>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
</dict>
</plist>
PLIST

    # Unload if already loaded, then load fresh
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    launchctl load "$PLIST_PATH"
    echo "launchd service installed and started: $PLIST_PATH"
    echo "Queue server will auto-start on login."
    echo "Logs: ~/.article-collector/queue-server.log"
else
    echo "Skipped auto-start setup. Start manually with: ./run.sh"
fi

echo ""
echo "Next steps:"
echo "1. Edit backend/.env and fill in your own API and Feishu values."
echo "2. Required model config: BASE_URL/AUTH_TOKEN/AI_MODEL, mapped to AI_* or ANTHROPIC_* variables."
echo "3. Required Feishu config: FEISHU_BASE_APP_TOKEN, FEISHU_ARTICLES_TABLE_ID."
echo "4. IM push: set FEISHU_IM_USER_ID (private) or FEISHU_IM_CHAT_ID (group) in .env."
echo "5. Load chrome-extension/ in Chrome via Developer Mode -> Load unpacked."

echo ""
echo "Setup complete."
