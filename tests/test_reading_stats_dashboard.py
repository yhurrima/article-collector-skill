import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


class ReadingStatsDashboardTests(unittest.TestCase):
    def test_skill_instructions_include_reading_stats_trigger(self):
        skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("我想看我的阅读统计", skill_text)
        self.assertIn("阅读统计", skill_text)
        self.assertIn("分类饼图", skill_text)
        self.assertIn("来源柱状图", skill_text)
        self.assertIn("每天收藏文章数量折线图", skill_text)

    def test_builds_expected_dashboard_blocks(self):
        from reading_stats_dashboard import build_reading_stats_blocks

        blocks = build_reading_stats_blocks("文章收藏表")

        self.assertEqual(
            [block["name"] for block in blocks],
            ["分类分布", "来源分布", "每日收藏趋势"],
        )
        self.assertEqual([block["type"] for block in blocks], ["pie", "column", "line"])

        category_config = blocks[0]["data_config"]
        self.assertEqual(category_config["table_name"], "文章收藏表")
        self.assertTrue(category_config["count_all"])
        self.assertEqual(category_config["group_by"][0]["field_name"], "分类")

        source_config = blocks[1]["data_config"]
        self.assertTrue(source_config["count_all"])
        self.assertEqual(source_config["group_by"][0]["field_name"], "来源")
        self.assertEqual(source_config["group_by"][0]["sort"], {"type": "value", "order": "desc"})

        daily_config = blocks[2]["data_config"]
        self.assertTrue(daily_config["count_all"])
        self.assertEqual(daily_config["group_by"][0]["field_name"], "保存日期")
        self.assertEqual(daily_config["group_by"][0]["sort"], {"type": "group", "order": "asc"})

    def test_missing_feishu_config_raises_clear_error(self):
        from reading_stats_dashboard import ensure_reading_stats_dashboard

        with patch("reading_stats_dashboard.FEISHU_BASE_APP_TOKEN", ""), \
             patch("reading_stats_dashboard.FEISHU_ARTICLES_TABLE_ID", "tbl_xxx"):
            with self.assertRaisesRegex(RuntimeError, "FEISHU_BASE_APP_TOKEN"):
                ensure_reading_stats_dashboard()

    def test_reuses_existing_dashboard_and_does_not_create_duplicate_blocks(self):
        from reading_stats_dashboard import ensure_reading_stats_dashboard

        calls = []

        def fake_run_cli(*args):
            calls.append(args)
            command = args[1]
            if command == "+table-get":
                return {"table": {"name": "文章收藏表"}}
            if command == "+dashboard-list":
                return {"items": [{"dashboard_id": "blk_existing", "name": "阅读统计"}]}
            if command == "+dashboard-block-list":
                return {
                    "items": [
                        {"block_id": "cht_1", "name": "分类分布", "type": "pie"},
                        {"block_id": "cht_2", "name": "来源分布", "type": "column"},
                        {"block_id": "cht_3", "name": "每日收藏趋势", "type": "line"},
                    ]
                }
            raise AssertionError(f"unexpected command: {args}")

        with patch("reading_stats_dashboard.FEISHU_BASE_APP_TOKEN", "bas_xxx"), \
             patch("reading_stats_dashboard.FEISHU_ARTICLES_TABLE_ID", "tbl_xxx"), \
             patch("reading_stats_dashboard._run_cli", side_effect=fake_run_cli):
            result = ensure_reading_stats_dashboard()

        self.assertEqual(result["dashboard_id"], "blk_existing")
        self.assertFalse(result["created"])
        self.assertEqual(result["created_blocks"], [])
        self.assertIn("blk_existing", result["dashboard_url"])
        self.assertNotIn("+dashboard-create", [call[1] for call in calls])
        self.assertNotIn("+dashboard-block-create", [call[1] for call in calls])


if __name__ == "__main__":
    unittest.main()
