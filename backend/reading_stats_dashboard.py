"""Create or reuse the Feishu Base reading statistics dashboard."""
import argparse
import json

from config import FEISHU_BASE_APP_TOKEN, FEISHU_ARTICLES_TABLE_ID
from feishu_client import _run_cli


DASHBOARD_NAME = "阅读统计"
REQUIRED_BLOCKS = (
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
        "name": "每日收藏趋势",
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
        return data.get("dashboard_id") or data.get("id")
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
    return f"https://my.feishu.cn/base/{base_token}?dashboard={dashboard_id}"


def build_reading_stats_blocks(table_name):
    blocks = []
    for block in REQUIRED_BLOCKS:
        group_by = {
            "field_name": block["group_field"],
            "mode": "integrated",
        }
        if block["sort"]:
            group_by["sort"] = block["sort"]
        blocks.append(
            {
                "name": block["name"],
                "type": block["type"],
                "data_config": {
                    "table_name": table_name,
                    "count_all": True,
                    "group_by": [group_by],
                },
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


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="创建或打开阅读统计仪表盘")
    return parser.parse_args(argv)


def main(argv=None):
    parse_args(argv)
    result = ensure_reading_stats_dashboard()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
