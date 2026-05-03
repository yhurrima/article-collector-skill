"""Article Collector - 本地 API 服务"""
import json
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from extractor import process_url
from feishu_client import add_record, send_text
from config import (
    SERVER_HOST, SERVER_PORT,
    FEISHU_BASE_APP_TOKEN, FEISHU_ARTICLES_TABLE_ID,
    FEISHU_IM_CHAT_ID,
)

app = Flask(__name__)


@app.route("/save", methods=["POST"])
def save_article():
    """保存文章: URL → 抓取 → Claude 解析 → 写入飞书多维表格"""
    data = request.json
    url = data.get("url")
    if not url:
        return jsonify({"error": "url is required"}), 400

    try:
        # 1. 抓取 + 解析
        article = process_url(url)

        # 2. 写入飞书多维表格
        fields = {
            "标题": article.get("title", ""),
            "原文链接": article["url"],
            "作者": article.get("author", ""),
            "来源": article.get("source", ""),
            "发布日期": article.get("publish_date", ""),
            "分类": article.get("category", "其他"),
            "摘要": article.get("summary", ""),
            "关键词": ", ".join(article.get("tags", [])),
            "主要内容": "\n".join(article.get("main_points", [])),
            "保存日期": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }

        if FEISHU_BASE_APP_TOKEN and FEISHU_ARTICLES_TABLE_ID:
            add_record(FEISHU_BASE_APP_TOKEN, FEISHU_ARTICLES_TABLE_ID, fields)

        # 3. 可选: 推送确认消息到 IM
        if FEISHU_IM_CHAT_ID:
            msg = f"✅ 已收藏: {article.get('title', url)}\n📝 {article.get('summary', '')}"
            send_text(FEISHU_IM_CHAT_ID, msg)

        return jsonify({"ok": True, "article": article})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    print(f"🚀 Article Collector running on http://{SERVER_HOST}:{SERVER_PORT}")
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=True)
