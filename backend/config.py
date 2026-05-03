import os

# 自动加载 .env 文件（如果存在）
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# AI 配置 - 支持多种引擎
# AI_PROVIDER: anthropic / openai / local
AI_PROVIDER = os.environ.get("AI_PROVIDER", "anthropic")
AI_API_KEY = os.environ.get("AI_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
AI_BASE_URL = os.environ.get("AI_BASE_URL") or os.environ.get("ANTHROPIC_BASE_URL", "")
AI_MODEL = os.environ.get("AI_MODEL", "mimo-v2.5")

# Feishu Base (多维表格)
FEISHU_BASE_APP_TOKEN = os.environ.get("FEISHU_BASE_APP_TOKEN", "")
FEISHU_ARTICLES_TABLE_ID = os.environ.get("FEISHU_ARTICLES_TABLE_ID", "")
FEISHU_WEEKLY_TABLE_ID = os.environ.get("FEISHU_WEEKLY_TABLE_ID", "")

# Server
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5678

# IM 推送目标 (群聊 ID 或用户 ID)
FEISHU_IM_CHAT_ID = os.environ.get("FEISHU_IM_CHAT_ID", "")
