"""Create or reuse the Feishu Base reading statistics dashboard."""
import argparse
import json
from datetime import datetime, timedelta

from config import FEISHU_BASE_APP_TOKEN, FEISHU_ARTICLES_TABLE_ID, FEISHU_IM_CHAT_ID
from feishu_client import _run_cli, list_records, send_markdown


DASHBOARD_NAME = "阅读统计"
REQUIRED_BLOCKS = (
    {
        "name": "收藏文章总数",
        "type": "statistics",
        "group_field": None,
        "sort": None,
    },
    {
        "name": "分类分布",
        "type": "pie",
        "group_field": "分类",
        "sort": None,
    },
    {
        "name": "来源分布",
        "type": "column",
        "group_field": "来源",
        "sort": {"type": "value", "order": "desc"},
    },
    {
        "name": "每日收藏文章量",
        "type": "line",
        "group_field": "保存日期",
        "sort": {"type": "group", "order": "asc"},
    },
)


def _items(payload):
    if "items" in payload:
        return payload.get("items") or []
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict):
        return data.get("items") or data.get("data") or []
    return []


def _extract_dashboard_id(payload):
    if payload.get("dashboard_id"):
        return payload["dashboard_id"]
    data = payload.get("data")
    if isinstance(data, dict):
        if data.get("dashboard_id"):
            return data["dashboard_id"]
        dashboard = data.get("dashboard")
        if isinstance(dashboard, dict) and dashboard.get("dashboard_id"):
            return dashboard["dashboard_id"]
        return data.get("id")
    return ""


def _extract_table_name(payload):
    table = payload.get("table")
    if isinstance(table, dict) and table.get("name"):
        return table["name"]
    data = payload.get("data")
    if isinstance(data, dict):
        table = data.get("table")
        if isinstance(table, dict) and table.get("name"):
            return table["name"]
        if data.get("name"):
            return data["name"]
    raise RuntimeError("无法读取文章收藏表名称，不能创建阅读统计仪表盘")


def dashboard_url(base_token, dashboard_id):
    return f"https://my.feishu.cn/base/{base_token}?dashboard={dashboard_id}&table={dashboard_id}"


def build_reading_stats_blocks(table_name):
    blocks = []
    for block in REQUIRED_BLOCKS:
        data_config = {
            "table_name": table_name,
            "count_all": True,
        }
        if block["group_field"]:
            group_by = {
                "field_name": block["group_field"],
                "mode": "integrated",
            }
            if block["sort"]:
                group_by["sort"] = block["sort"]
            data_config["group_by"] = [group_by]
        blocks.append(
            {
                "name": block["name"],
                "type": block["type"],
                "data_config": data_config,
            }
        )
    return blocks


def require_feishu_config():
    missing = []
    if not FEISHU_BASE_APP_TOKEN:
        missing.append("FEISHU_BASE_APP_TOKEN")
    if not FEISHU_ARTICLES_TABLE_ID:
        missing.append("FEISHU_ARTICLES_TABLE_ID")
    if missing:
        raise RuntimeError(f"缺少配置: {', '.join(missing)}")


def get_articles_table_name():
    payload = _run_cli(
        "base", "+table-get",
        "--base-token", FEISHU_BASE_APP_TOKEN,
        "--table-id", FEISHU_ARTICLES_TABLE_ID,
    )
    return _extract_table_name(payload)


def find_dashboard():
    payload = _run_cli(
        "base", "+dashboard-list",
        "--base-token", FEISHU_BASE_APP_TOKEN,
    )
    for item in _items(payload):
        if item.get("name") == DASHBOARD_NAME:
            return item
    return None


def create_dashboard():
    payload = _run_cli(
        "base", "+dashboard-create",
        "--base-token", FEISHU_BASE_APP_TOKEN,
        "--name", DASHBOARD_NAME,
    )
    dashboard_id = _extract_dashboard_id(payload)
    if not dashboard_id:
        raise RuntimeError("创建阅读统计仪表盘失败: 返回中没有 dashboard_id")
    return {"dashboard_id": dashboard_id, "name": DASHBOARD_NAME}


def list_dashboard_blocks(dashboard_id):
    payload = _run_cli(
        "base", "+dashboard-block-list",
        "--base-token", FEISHU_BASE_APP_TOKEN,
        "--dashboard-id", dashboard_id,
        "--page-size", "100",
    )
    return _items(payload)


def create_dashboard_block(dashboard_id, block):
    return _run_cli(
        "base", "+dashboard-block-create",
        "--base-token", FEISHU_BASE_APP_TOKEN,
        "--dashboard-id", dashboard_id,
        "--name", block["name"],
        "--type", block["type"],
        "--data-config", json.dumps(block["data_config"], ensure_ascii=False),
    )


def arrange_dashboard(dashboard_id):
    return _run_cli(
        "base", "+dashboard-arrange",
        "--base-token", FEISHU_BASE_APP_TOKEN,
        "--dashboard-id", dashboard_id,
    )


def ensure_reading_stats_dashboard():
    require_feishu_config()
    table_name = get_articles_table_name()
    dashboard = find_dashboard()
    created = False
    if dashboard:
        dashboard_id = dashboard.get("dashboard_id") or dashboard.get("id")
    else:
        dashboard = create_dashboard()
        dashboard_id = dashboard["dashboard_id"]
        created = True

    existing_block_names = {block.get("name") for block in list_dashboard_blocks(dashboard_id)}
    created_blocks = []
    for block in build_reading_stats_blocks(table_name):
        if block["name"] in existing_block_names:
            continue
        create_dashboard_block(dashboard_id, block)
        created_blocks.append(block["name"])

    if created_blocks:
        arrange_dashboard(dashboard_id)

    return {
        "name": DASHBOARD_NAME,
        "dashboard_id": dashboard_id,
        "dashboard_url": dashboard_url(FEISHU_BASE_APP_TOKEN, dashboard_id),
        "created": created,
        "created_blocks": created_blocks,
        "time_filter_field": "保存日期",
    }


def get_articles_in_range(start_date, end_date):
    """读取多维表格全部记录，按保存日期筛选在 [start_date, end_date] 范围内的文章。"""
    result = list_records(FEISHU_BASE_APP_TOKEN, FEISHU_ARTICLES_TABLE_ID, limit=200)
    items = result.get("data", {}).get("data", [])
    fields_list = result.get("data", {}).get("fields", [])
    record_ids = result.get("data", {}).get("record_id_list", [])
    articles = []
    for index, row in enumerate(items):
        record = dict(zip(fields_list, row))
        if index < len(record_ids):
            record["record_id"] = record_ids[index]
        save_date = record.get("保存日期", "")
        if save_date and start_date <= save_date <= end_date:
            articles.append(record)
    return articles


def compute_range_stats(articles):
    """从筛选后的文章中计算摘要统计。"""
    categories = {}
    sources = {}
    daily = {}

    for art in articles:
        cat = art.get("分类", "其他")
        if isinstance(cat, list):
            cat = cat[0] if cat else "其他"
        categories[cat] = categories.get(cat, 0) + 1

        source = art.get("来源", "未知")
        if isinstance(source, list):
            source = source[0] if source else "未知"
        sources[source] = sources.get(source, 0) + 1

        save_date = art.get("保存日期", "")
        if save_date:
            daily[save_date] = daily.get(save_date, 0) + 1

    top_sources = dict(sorted(sources.items(), key=lambda x: -x[1])[:5])
    daily_sorted = dict(sorted(daily.items()))

    return {
        "total": len(articles),
        "categories": categories,
        "top_sources": top_sources,
        "daily": daily_sorted,
    }


def build_stats_im_markdown(stats, start_date, end_date, dashboard_url):
    """构建 IM 消息 Markdown。"""
    lines = [
        f"**📊 阅读统计 ({start_date} ~ {end_date})**",
        "",
        f"共收藏 **{stats['total']}** 篇文章",
    ]

    if stats["categories"]:
        lines.append("")
        lines.append("**📂 分类分布**")
        cat_parts = []
        for cat, count in sorted(stats["categories"].items(), key=lambda x: -x[1]):
            cat_parts.append(f"{cat}: {count}篇")
        lines.append(" | ".join(cat_parts))

    if stats["top_sources"]:
        lines.append("")
        lines.append("**🔗 来源 Top 5**")
        for i, (source, count) in enumerate(stats["top_sources"].items(), 1):
            lines.append(f"{i}. {source} ({count}篇)")

    if dashboard_url:
        lines.append("")
        lines.append(f"👉 [查看完整仪表盘]({dashboard_url})")

    return "\n".join(lines)


def send_stats_im(start_date, end_date):
    """主流程：创建/复用仪表盘 → 读取文章 → 计算统计 → IM 推送。"""
    result = ensure_reading_stats_dashboard()
    dashboard_url = result.get("dashboard_url", "")

    articles = get_articles_in_range(start_date, end_date)
    if not articles:
        print(f"{start_date} ~ {end_date} 没有收藏的文章")
        return result

    stats = compute_range_stats(articles)
    print(f"统计: {stats['total']} 篇文章")

    if FEISHU_IM_CHAT_ID:
        markdown = build_stats_im_markdown(stats, start_date, end_date, dashboard_url)
        send_markdown(FEISHU_IM_CHAT_ID, markdown)
        print("IM 推送完成")

    result["stats"] = stats
    return result


def default_date_range():
    """返回默认时间范围：最近 30 天。"""
    today = datetime.now()
    start = today - timedelta(days=30)
    return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="创建或打开阅读统计仪表盘")
    parser.add_argument("--start-date", help="统计起始日期，格式 YYYY-MM-DD（默认 30 天前）")
    parser.add_argument("--end-date", help="统计结束日期，格式 YYYY-MM-DD（默认今天）")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    start_date = args.start_date
    end_date = args.end_date
    if not start_date or not end_date:
        default_start, default_end = default_date_range()
        if not start_date:
            start_date = default_start
        if not end_date:
            end_date = default_end
    result = send_stats_im(start_date, end_date)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
