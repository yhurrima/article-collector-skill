"""每日汇总: 读取今天的文章 → 生成飞书文档 → IM 推送"""
import argparse
import json
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from feishu_client import list_records, create_doc, send_markdown, _run_cli
from extractor import process_url
from config import (
    FEISHU_BASE_APP_TOKEN, FEISHU_ARTICLES_TABLE_ID,
    FEISHU_IM_CHAT_ID,
)
from user_settings import load_settings


LIST_MARKER_RE = re.compile(r"^\s*(?:\d+[\.)]|[a-zA-Z][\.)]|[-*+])\s+")


def local_now(timezone_name="Asia/Shanghai"):
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")
    return datetime.now(tz)


def resolve_report_date(mode="today", date_str=None, now=None, timezone_name="Asia/Shanghai"):
    if date_str:
        return date_str

    current = now or local_now(timezone_name)
    if current.tzinfo is None:
        try:
            current = current.replace(tzinfo=ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError:
            current = current.replace(tzinfo=ZoneInfo("UTC"))
    elif timezone_name:
        try:
            current = current.astimezone(ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError:
            current = current.astimezone(ZoneInfo("UTC"))

    if mode == "yesterday":
        current = current - timedelta(days=1)
    return current.strftime("%Y-%m-%d")


def normalize_main_points(main_points):
    """Return clean point text without stored list markers."""
    if main_points is None:
        return []
    points = []
    for point in str(main_points).split("\n"):
        point = LIST_MARKER_RE.sub("", point).strip()
        if point:
            points.append(point)
    return points


def normalize_select_value(value):
    if isinstance(value, list):
        return value[0] if value else ""
    return value


def format_points(points):
    return "\n".join(f"{i+1}. {point}" for i, point in enumerate(points or []))


def fields_from_extracted_article(article, url):
    main_content = format_points(article.get("main_points", []))
    return {
        "标题": article.get("title", ""),
        "原文链接": article.get("url", url),
        "作者": article.get("author", ""),
        "来源": article.get("source", ""),
        "发布日期": article.get("publish_date", ""),
        "分类": article.get("category", "其他"),
        "摘要": article.get("summary", ""),
        "关键词": ", ".join(article.get("tags", [])),
        "主要内容": main_content,
        "处理状态": "完成",
    }


def update_record_fields(record_id, fields):
    payload = json.dumps(fields, ensure_ascii=False)
    return _run_cli(
        "base", "+record-upsert",
        "--base-token", FEISHU_BASE_APP_TOKEN,
        "--table-id", FEISHU_ARTICLES_TABLE_ID,
        "--record-id", record_id,
        "--json", payload,
    )


def failed_fields(error_message):
    return {
        "摘要": f"处理失败：{error_message}",
        "主要内容": "",
        "处理状态": "处理失败",
    }


def complete_incomplete_articles(articles):
    completed = []
    for article in articles:
        if normalize_select_value(article.get("处理状态")) == "完成":
            completed.append(article)
            continue

        record_id = article.get("record_id")
        url = article.get("原文链接", "")
        if not record_id or not url:
            completed.append(article)
            continue

        try:
            extracted = process_url(url)
            fields = fields_from_extracted_article(extracted, url)
            update_record_fields(record_id, fields)
            updated = {**article, **fields}
            completed.append(updated)
        except Exception as exc:
            fields = failed_fields(str(exc))
            update_record_fields(record_id, fields)
            completed.append({**article, **fields})
    return completed


def retry_failed_articles(articles):
    return complete_incomplete_articles(articles)


def article_detail_lines(article, summary_length):
    if normalize_select_value(article.get("处理状态")) == "处理失败":
        return ["仅保存链接，正文处理失败。\n"]

    summary = article.get("摘要", "")
    main_content = article.get("主要内容", "")
    main_points = normalize_main_points(main_content)
    lines = []

    if summary:
        lines.append(f"**摘要**: {summary}\n")

    if main_points:
        lines.append("**主要内容**:")
        for i, point in enumerate(main_points, 1):
            lines.append(f"{i}. {point}")
        lines.append("")
    return lines


def get_today_articles(date_str=None):
    """从多维表格读取今天的文章"""
    today = date_str or resolve_report_date()
    result = list_records(FEISHU_BASE_APP_TOKEN, FEISHU_ARTICLES_TABLE_ID, limit=200)
    items = result.get("data", {}).get("data", [])
    fields_list = result.get("data", {}).get("fields", [])
    record_ids = result.get("data", {}).get("record_id_list", [])
    today_articles = []
    for index, row in enumerate(items):
        record = dict(zip(fields_list, row))
        if index < len(record_ids):
            record["record_id"] = record_ids[index]
        saved_date = record.get("保存日期", "")
        if isinstance(saved_date, str):
            saved_date = saved_date[:10]
        if str(saved_date) == today:
            today_articles.append(record)
    return today_articles


def get_pending_articles(date_str=None):
    """Return today's records that need Agent processing in link-only mode."""
    return [
        article for article in get_today_articles(date_str)
        if normalize_select_value(article.get("处理状态")) == "待处理"
    ]


def update_pending_article_completed(record_id, article, url):
    """Write Agent-produced summary fields back to a pending Feishu record."""
    return update_record_fields(record_id, fields_from_extracted_article(article, url))


def mark_pending_article_failed(record_id, error_message):
    """Mark a pending Feishu record as failed after Agent processing fails."""
    return update_record_fields(record_id, failed_fields(error_message))


def build_doc_markdown(articles, date_str, summary_length="brief"):
    """生成飞书文档"""
    raw_cats = [a.get("分类", "其他") for a in articles]
    categories = list(set(c[0] if isinstance(c, list) else (c or "其他") for c in raw_cats))
    cat_str = "、".join(categories)

    overviews = [a.get("摘要", "") for a in articles if a.get("摘要")]

    lines = [
        f"# {date_str} 阅读汇总\n",
        f"## 今日概览\n",
        f"今天你关注了 **{cat_str}** 领域的文章，共 **{len(articles)}** 篇。重点内容有：\n",
    ]
    for i, point in enumerate(overviews, 1):
        lines.append(f"{i}. {point}")

    lines.append(f"\n## 文章详情\n")
    for i, a in enumerate(articles, 1):
        title = a.get("标题", "无标题")
        url = a.get("原文链接", "")
        source = a.get("来源", "")

        lines.append(f"### {i}. {title}\n")
        lines.extend(article_detail_lines(a, summary_length))

        meta = []
        if source:
            meta.append(f"来源: {source}")
        if url:
            meta.append(f"[查看原文]({url})")
        if meta:
            lines.append(" | ".join(meta))
        lines.append("")

    lines.append(f"\n---\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    return "\n".join(lines)


def build_im_markdown(articles, date_str, doc_url=""):
    """生成 IM 推送的 Markdown 格式"""
    raw_cats = [a.get("分类", "其他") for a in articles]
    categories = list(set(c[0] if isinstance(c, list) else (c or "其他") for c in raw_cats))
    cat_str = "、".join(categories)

    overviews = [a.get("摘要", "") for a in articles if a.get("摘要")]

    # 构建 markdown 格式的消息
    lines = [
        f"**📰 {date_str} 阅读汇总**",
        f"",
        f"今天你关注了 **{cat_str}** 领域，共收藏 **{len(articles)}** 篇文章",
        f"",
        f"**💡 重点内容**",
    ]
    for i, point in enumerate(overviews, 1):
        lines.append(f"{i}. {point}")

    lines.append(f"")
    lines.append(f"**📂 今日文章**")
    for i, a in enumerate(articles, 1):
        title = a.get("标题", "无标题")
        source = a.get("来源", "")
        url = a.get("原文链接", "")
        if url:
            lines.append(f"{i}. [{title}]({url})  ({source})")
        else:
            lines.append(f"{i}. {title}  ({source})")

    if doc_url:
        lines.append(f"")
        lines.append(f"👉 [查看完整汇总]({doc_url})")

    return "\n".join(lines)


def run(date_str=None):
    """执行每日汇总"""
    report_date = date_str or resolve_report_date()
    print(f"开始生成 {report_date} 每日汇总...")

    articles = get_today_articles(report_date)
    if not articles:
        print(f"{report_date} 没有收藏的文章")
        if FEISHU_IM_CHAT_ID:
            send_markdown(FEISHU_IM_CHAT_ID, f"**📰 {report_date} 阅读汇总**\n\n昨天没有收藏文章。")
            print("IM 推送完成（无文章提醒）")
        return
    articles = complete_incomplete_articles(articles)

    print(f"找到 {len(articles)} 篇文章")
    settings = load_settings()
    summary_length = settings.get("summaryLength", "brief")

    doc_url = ""
    if FEISHU_BASE_APP_TOKEN:
        markdown = build_doc_markdown(articles, report_date, summary_length=summary_length)
        title = f"{report_date} 阅读汇总"
        doc = create_doc(title, markdown)
        doc_url = doc.get("data", {}).get("doc_url", "")
        print(f"汇总文档: {doc_url}")

    if FEISHU_IM_CHAT_ID:
        im_md = build_im_markdown(articles, report_date, doc_url)
        send_markdown(FEISHU_IM_CHAT_ID, im_md)
        print("IM 推送完成")

    print("每日汇总完成")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="生成指定日期的阅读汇总")
    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument("--date", dest="date_str", help="指定汇总日期，格式 YYYY-MM-DD")
    date_group.add_argument("--today", action="store_const", const="today", dest="mode", help="生成今天的阅读汇总")
    date_group.add_argument("--yesterday", action="store_const", const="yesterday", dest="mode", help="生成昨天的阅读汇总")
    parser.set_defaults(mode="today")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    settings = load_settings()
    report_date = resolve_report_date(
        mode=args.mode,
        date_str=args.date_str,
        timezone_name=settings.get("timezone", "Asia/Shanghai"),
    )
    run(report_date)


if __name__ == "__main__":
    main()
