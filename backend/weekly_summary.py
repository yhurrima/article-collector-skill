"""每周统计: 汇总本周阅读数据 → 写入多维表格 → IM 推送周报"""
import json
from datetime import datetime, timezone, timedelta
from feishu_client import list_records, batch_add_records, send_text
from config import (
    FEISHU_BASE_APP_TOKEN, FEISHU_ARTICLES_TABLE_ID, FEISHU_WEEKLY_TABLE_ID,
    FEISHU_IM_CHAT_ID,
)


def get_week_articles():
    """获取本周的文章"""
    today = datetime.now(timezone.utc)
    week_start = today - timedelta(days=today.weekday())
    start_str = week_start.strftime("%Y-%m-%d")

    result = list_records(FEISHU_BASE_APP_TOKEN, FEISHU_ARTICLES_TABLE_ID, limit=200)
    items = result.get("data", {}).get("items", [])
    return [item for item in items if item.get("fields", {}).get("保存日期", "") >= start_str]


def compute_stats(articles):
    """计算统计数据"""
    categories = {}
    total_score = 0
    sources = {}
    tags_count = {}

    for art in articles:
        fields = art.get("fields", {})
        cat = fields.get("分类", "其他")
        categories[cat] = categories.get(cat, 0) + 1

        score = fields.get("评分", 3)
        total_score += score

        source = fields.get("来源", "未知")
        sources[source] = sources.get(source, 0) + 1

        for tag in fields.get("关键词", "").split(","):
            tag = tag.strip()
            if tag:
                tags_count[tag] = tags_count.get(tag, 0) + 1

    return {
        "total": len(articles),
        "avg_score": round(total_score / max(len(articles), 1), 1),
        "categories": categories,
        "sources": sources,
        "top_tags": dict(sorted(tags_count.items(), key=lambda x: -x[1])[:10]),
    }


def save_weekly_stats(stats, week_label):
    """将周统计数据写入多维表格"""
    if not FEISHU_WEEKLY_TABLE_ID:
        return

    fields = {
        "周次": week_label,
        "总阅读量": stats["total"],
        "平均评分": stats["avg_score"],
        "分类分布": json.dumps(stats["categories"], ensure_ascii=False),
        "高频标签": json.dumps(stats["top_tags"], ensure_ascii=False),
        "主要来源": json.dumps(stats["sources"], ensure_ascii=False),
    }
    batch_add_records(FEISHU_BASE_APP_TOKEN, FEISHU_WEEKLY_TABLE_ID, [fields])


def send_weekly_digest(stats, chat_id, week_label):
    """推送周报到 IM"""
    lines = [
        f"📊 {week_label} 阅读周报",
        f"共收藏 {stats['total']} 篇 | 平均评分 {stats['avg_score']}/5",
        "",
        "📂 分类分布:"
    ]

    for cat, count in sorted(stats["categories"].items(), key=lambda x: -x[1]):
        bar = "█" * count + "░" * max(0, 5 - count)
        lines.append(f"  {cat}: {bar} {count}篇")

    if stats["top_tags"]:
        lines.append("\n🏷️ 高频标签:")
        tags_str = " · ".join(list(stats["top_tags"].keys())[:8])
        lines.append(f"  {tags_str}")

    send_text(chat_id, "\n".join(lines))


def run():
    """执行每周统计"""
    today = datetime.now(timezone.utc)
    week_start = today - timedelta(days=today.weekday())
    week_label = f"{week_start.strftime('%m/%d')}-{today.strftime('%m/%d')}"

    print(f"📊 开始生成 {week_label} 周报...")

    articles = get_week_articles()
    if not articles:
        print("本周没有收藏的文章")
        return

    stats = compute_stats(articles)
    print(f"本周共 {stats['total']} 篇文章")

    # 写入多维表格
    save_weekly_stats(stats, week_label)
    print("✅ 周统计数据已写入多维表格")

    # 推送 IM
    if FEISHU_IM_CHAT_ID:
        send_weekly_digest(stats, FEISHU_IM_CHAT_ID, week_label)
        print("✅ 周报已推送到 IM")


if __name__ == "__main__":
    run()
