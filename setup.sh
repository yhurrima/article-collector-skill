#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.article-collector.queue"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

echo "Article Collector setup"
echo "======================="

echo ""
echo "Installing Python dependencies..."
# Python 3.12+ (PEP 668) 不允许直接 pip install，用 --user 或 --break-system-packages
if pip3 install -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null; then
    :
elif pip3 install --user -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null; then
    :
elif pip3 install --break-system-packages -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null; then
    :
else
    echo "Warning: pip install failed. Dependencies may need manual installation."
    echo "Try: pip3 install --user -r requirements.txt"
fi

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

    # 检测工具实际路径，构建 launchd 需要的 PATH
    PYTHON_BIN="$(command -v python3 2>/dev/null || echo /usr/bin/python3)"
    LARK_BIN="$(command -v lark-cli 2>/dev/null || echo /usr/local/bin/lark-cli)"
    PYTHON_DIR="$(dirname "$PYTHON_BIN")"
    LARK_DIR="$(dirname "$LARK_BIN")"

    # 去重并构建 PATH
    LAUNCH_PATH="$PYTHON_DIR:$LARK_DIR:/usr/bin:/bin"
    # 补充常见 Homebrew 路径（如果不在已有路径中）
    for d in /opt/homebrew/bin /usr/local/bin; do
        case ":$LAUNCH_PATH:" in
            *":$d:"*) ;;  # 已存在
            *) LAUNCH_PATH="$d:$LAUNCH_PATH" ;;
        esac
    done

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
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>${LAUNCH_PATH}</string>
    </dict>
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

    echo "Detected paths:"
    echo "  python3: $PYTHON_BIN"
    echo "  lark-cli: $LARK_BIN"
    echo "  launchd PATH: $LAUNCH_PATH"

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
