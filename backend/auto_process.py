"""
自动处理单篇文章：抓取 → 提取 → 写飞书 → 发 IM
供 queue_server.py 收到 URL 后自动调用，也可独立运行。
"""
import sys, json, re, subprocess, requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlparse
from user_settings import load_settings
from config import (
    FEISHU_BASE_APP_TOKEN, FEISHU_ARTICLES_TABLE_ID, FEISHU_IM_CHAT_ID,
    AI_API_KEY, FEISHU_IM_USER_ID,
)


def _run_lark(*args):
    cmd = ["lark-cli"] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        print(f"lark-cli error: {r.stderr}", file=sys.stderr)
    return r.stdout


def fetch(url):
    """抓取网页，返回 (title, text, meta_dict)"""
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

    # Reddit 用 old.reddit.com
    if "reddit.com" in url:
        url = url.replace("www.reddit.com", "old.reddit.com")

    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # 提取 meta 信息
    meta = {}
    for tag in soup.find_all("meta"):
        name = tag.get("name", "") or tag.get("property", "")
        content = tag.get("content", "")
        if name and content:
            meta[name.lower()] = content

    # 清理噪音
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
        tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    # Reddit 标题处理
    if " : " in title:
        title = title.split(" : ")[0].strip()

    text = soup.get_text(separator="\n", strip=True)
    if len(text) > 12000:
        text = text[:12000]

    return title, text, meta


def guess_source(url, meta):
    """从 URL 和 meta 推断来源"""
    domain = urlparse(url).netloc.lower()
    if "reddit.com" in domain:
        # 提取 subreddit
        m = re.search(r"/r/(\w+)", url)
        return f"Reddit r/{m.group(1)}" if m else "Reddit"
    if "mp.weixin.qq.com" in domain:
        return "微信公众号"
    source_map = {
        "qbitai.com": "量子位",
        "chinadaily.com": "中国网",
        "technews.tw": "科技新报",
        "36kr.com": "36氪",
        "macrumors.com": "MacRumors",
        "arstechnica.com": "Ars Technica",
        "theverge.com": "The Verge",
    }
    for key, val in source_map.items():
        if key in domain:
            return val
    # fallback: 用 og:site_name 或域名
    return meta.get("og:site_name", domain.replace("www.", "").split(".")[0].title())


def guess_category(text):
    """简单关键词分类"""
    t = text.lower()
    if any(k in t for k in ["ai", "llm", "gpt", "claude", "模型", "agent", "机器学习", "深度学习"]):
        return "AI"
    if any(k in t for k in ["融资", "营收", "财报", "上市", "估值"]):
        return "商业"
    if any(k in t for k in ["设计", "ui", "ux", "交互", "原型"]):
        return "设计"
    if any(k in t for k in ["产品", "功能", "用户", "需求"]):
        return "产品"
    return "技术"


def extract_basic(title, text, url, meta):
    """无 AI 时的基础提取"""
    # 作者
    author = meta.get("author", "")
    if not author:
        # Reddit: 从页面找
        m = re.search(r"submitted\s+\S+\s+by\s+(\w+)", text)
        if m:
            author = m.group(1)

    # 发布日期
    pub_date = ""
    for key in ["article:published_time", "date", "publishdate"]:
        if key in meta:
            pub_date = meta[key][:10]
            break
    if not pub_date:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", text[:500])
        if m:
            pub_date = m.group(1)

    # 摘要：取前 80 字
    # 找正文开头（跳过导航等）
    lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 20]
    body_lines = []
    for l in lines:
        if any(skip in l.lower() for skip in ["jump to", "log in", "sign up", "cookie", "subscribe"]):
            continue
        body_lines.append(l)
        if len(body_lines) >= 5:
            break

    body_text = " ".join(body_lines)
    summary = body_text[:75].rsplit("，", 1)[0] if len(body_text) > 75 else body_text
    if len(summary) > 30:
        summary = summary[:28] + "..."

    # 主要内容：取前 5 个较长的句子
    sentences = re.split(r'[。！？\n]', body_text)
    sentences = [s.strip() for s in sentences if 15 < len(s.strip()) < 80]
    main_points = sentences[:5]
    if not main_points:
        main_points = [body_text[:80]]

    # 关键词
    category = guess_category(text)
    tags = [category]
    if "github.com" in url.lower():
        tags.append("开源")

    return {
        "title": title,
        "author": author,
        "source": guess_source(url, meta),
        "publish_date": pub_date,
        "category": category,
        "summary": summary,
        "main_points": main_points,
        "tags": tags[:3],
    }


def write_to_feishu(info, url):
    """写入飞书多维表格"""
    today = datetime.now().strftime("%Y-%m-%d")
    short_content = "\n".join(f"{i+1}. {p}" for i, p in enumerate(info.get("main_points", [])))
    fields = {
        "标题": info["title"],
        "原文链接": url,
        "作者": info.get("author", ""),
        "来源": info.get("source", ""),
        "发布日期": info.get("publish_date", ""),
        "分类": info.get("category", "其他"),
        "摘要": info.get("summary", ""),
        "关键词": ", ".join(info.get("tags", [])),
        "主要内容": short_content,
        "处理状态": "完成",
        "保存日期": today,
    }
    payload = json.dumps({
        "fields": list(fields.keys()),
        "rows": [list(fields.values())]
    }, ensure_ascii=False)

    result = _run_lark("base", "+record-batch-create",
                        "--base-token", FEISHU_BASE_APP_TOKEN,
                        "--table-id", FEISHU_ARTICLES_TABLE_ID,
                        "--json", payload)
    return "ok" in result


def write_failed_to_feishu(url, error_message):
    """保存处理失败的链接，供每日汇总前重试。"""
    today = datetime.now().strftime("%Y-%m-%d")
    fields = {
        "标题": url,
        "原文链接": url,
        "摘要": "",
        "主要内容": "",
        "处理状态": "处理失败",
        "保存日期": today,
    }
    payload = json.dumps({
        "fields": list(fields.keys()),
        "rows": [list(fields.values())]
    }, ensure_ascii=False)

    result = _run_lark("base", "+record-batch-create",
                        "--base-token", FEISHU_BASE_APP_TOKEN,
                        "--table-id", FEISHU_ARTICLES_TABLE_ID,
                        "--json", payload)
    return "ok" in result


def write_link_only_to_feishu(url):
    """只保存链接，不抓取正文、不调用模型 API。"""
    today = datetime.now().strftime("%Y-%m-%d")
    fields = {
        "标题": url,
        "原文链接": url,
        "摘要": "",
        "主要内容": "",
        "处理状态": "待处理",
        "保存日期": today,
    }
    payload = json.dumps({
        "fields": list(fields.keys()),
        "rows": [list(fields.values())]
    }, ensure_ascii=False)

    result = _run_lark("base", "+record-batch-create",
                        "--base-token", FEISHU_BASE_APP_TOKEN,
                        "--table-id", FEISHU_ARTICLES_TABLE_ID,
                        "--json", payload)
    return "ok" in result


def send_im(info, url):
    """机器人发送确认消息"""
    title = info["title"]
    source = info.get("source", "")
    category = info.get("category", "")
    summary = info.get("summary", "")

    msg = f"""**已收藏**

**{title}**
来源: {source} | 分类: {category}

{summary}

[查看原文]({url})"""

    # 优先私信推送，其次群聊
    if FEISHU_IM_USER_ID:
        _run_lark("im", "+messages-send",
                  "--as", "bot",
                  "--user-id", FEISHU_IM_USER_ID,
                  "--markdown", msg)
    elif FEISHU_IM_CHAT_ID:
        _run_lark("im", "+messages-send",
                  "--as", "bot",
                  "--chat-id", FEISHU_IM_CHAT_ID,
                  "--markdown", msg)


def try_ai_extract(title, text, url):
    """用 AI 提取；失败时抛错，禁止用规则拼接伪装成功。"""
    from config import AI_API_KEY
    if not AI_API_KEY:
        raise RuntimeError("AI_API_KEY/ANTHROPIC_AUTH_TOKEN is not configured")
    from extractor import extract_with_ai
    summary_length = load_settings().get("summaryLength", "brief")
    return extract_with_ai({"title": title, "text": text, "url": url}, summary_length=summary_length)


def process(url):
    """完整处理流程"""
    print(f"Processing: {url}")
    settings = load_settings()
    if settings.get("processingMode") == "link_only" or not AI_API_KEY:
        ok = write_link_only_to_feishu(url)
        print(f"Feishu link-only: {'ok' if ok else 'failed'}")
        # link_only 模式也要发 IM 确认
        send_im({"title": url, "source": "", "category": "", "summary": "链接已保存，待后续处理"}, url)
        return {
            "title": url,
            "url": url,
            "processing_status": "待处理",
        }

    try:
        title, text, meta = fetch(url)

        # 必须使用 AI API 提取；失败则保存失败状态，等待后续重试。
        info = try_ai_extract(title, text, url)
        info.setdefault("title", title)
        info.setdefault("source", guess_source(url, meta))

        # 写飞书
        ok = write_to_feishu(info, url)
        print(f"Feishu: {'ok' if ok else 'failed'}")

        # 发 IM
        send_im(info, url)
        print(f"IM: sent")

        return info
    except Exception as e:
        write_failed_to_feishu(url, str(e))
        print(f"Feishu: saved failed link ({e})", file=sys.stderr)
        return {
            "title": url,
            "url": url,
            "processing_status": "处理失败",
            "error": str(e),
        }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        process(sys.argv[1])
    else:
        print("Usage: python auto_process.py <url>")
