import sys
import unittest
from unittest.mock import patch
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import requests


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from daily_summary import (
    build_doc_markdown,
    complete_incomplete_articles,
    get_pending_articles,
    get_today_articles,
    mark_pending_article_failed,
    resolve_report_date,
    retry_failed_articles,
    update_pending_article_completed,
)
from auto_process import process, write_failed_to_feishu, write_link_only_to_feishu, write_to_feishu
from extractor import build_extract_prompt, clean_article_text_from_html, normalize_extracted_article
from scheduler import (
    build_launchd_plist,
    build_scheduled_summary_job,
    is_macos_protected_path,
    scheduler_support_status,
)
from user_settings import normalize_settings


class DailySummaryMarkdownTest(unittest.TestCase):
    def article(self):
        return {
            "标题": "SAP: How enterprise AI governance secures profit margins",
            "摘要": "企业AI治理通过确定性控制确保利润边缘。",
            "主要内容": (
                "1. 企业AI治理将AI代理转变为主动数字行动者。\n"
                "2. Agentic AI系统要求建立生命周期管理。\n"
                "3. 数据基础至关重要。"
            ),
            "来源": "AI News",
            "原文链接": "https://example.com/article",
            "分类": "AI",
        }

    def test_main_points_with_existing_numbers_are_not_numbered_twice(self):
        markdown = build_doc_markdown(
            [self.article()],
            "2026-05-02",
        )

        self.assertIn("1. 企业AI治理将AI代理转变为主动数字行动者。", markdown)
        self.assertIn("2. Agentic AI系统要求建立生命周期管理。", markdown)
        self.assertIn("3. 数据基础至关重要。", markdown)
        self.assertNotIn("1. 1. 企业AI治理", markdown)
        self.assertNotIn("2. 2. Agentic AI", markdown)

    def test_summary_length_does_not_change_daily_summary_field(self):
        articles = [self.article()]

        brief = build_doc_markdown(articles, "2026-05-02", summary_length="brief")
        medium = build_doc_markdown(articles, "2026-05-02", summary_length="medium")
        detailed = build_doc_markdown(articles, "2026-05-02", summary_length="detailed")

        self.assertEqual(brief, medium)
        self.assertEqual(brief, detailed)

    def test_failed_article_shows_link_only_failure_message(self):
        article = {
            "标题": "失败文章",
            "原文链接": "https://example.com/failed",
            "来源": "Example",
            "分类": "AI",
            "保存日期": "2026-05-03",
            "处理状态": "处理失败",
        }

        markdown = build_doc_markdown([article], "2026-05-03", summary_length="detailed")

        self.assertIn("仅保存链接，正文处理失败", markdown)
        self.assertIn("[查看原文](https://example.com/failed)", markdown)
        self.assertNotIn("**主要内容**:", markdown)

    def test_failed_article_with_select_status_list_shows_failure_message(self):
        article = {
            "标题": "失败文章",
            "原文链接": "https://example.com/failed",
            "来源": "Example",
            "分类": ["AI"],
            "保存日期": "2026-05-03",
            "处理状态": ["处理失败"],
            "主要内容": None,
        }

        markdown = build_doc_markdown([article], "2026-05-03")

        self.assertIn("仅保存链接，正文处理失败", markdown)
        self.assertNotIn("1. None", markdown)
        self.assertNotIn("**主要内容**:", markdown)

    def test_write_to_feishu_marks_successful_article_complete(self):
        captured = {}

        def fake_run_lark(*args):
            captured["args"] = args
            return '{"ok": true}'

        info = {
            "title": "测试文章",
            "author": "",
            "source": "Example",
            "publish_date": "2026-05-03",
            "category": "AI",
            "summary": "测试摘要",
            "tags": ["AI"],
            "main_points": ["简短内容"],
        }

        with patch("auto_process._run_lark", fake_run_lark):
            self.assertTrue(write_to_feishu(info, "https://example.com"))

        payload = captured["args"][captured["args"].index("--json") + 1]
        self.assertIn("处理状态", payload)
        self.assertIn("完成", payload)
        self.assertIn("主要内容", payload)
        self.assertNotIn("主要内容-简短", payload)
        self.assertNotIn("主要内容-中等", payload)
        self.assertNotIn("主要内容-详细", payload)

    def test_write_failed_to_feishu_saves_link_with_failed_status(self):
        captured = {}

        def fake_run_lark(*args):
            captured["args"] = args
            return '{"ok": true}'

        with patch("auto_process._run_lark", fake_run_lark):
            self.assertTrue(write_failed_to_feishu("https://example.com/failed", "抓取失败"))

        payload = captured["args"][captured["args"].index("--json") + 1]
        self.assertIn("https://example.com/failed", payload)
        self.assertIn("处理状态", payload)
        self.assertIn("处理失败", payload)
        self.assertNotIn("主要内容-简短", payload)
        self.assertNotIn("主要内容-中等", payload)
        self.assertNotIn("主要内容-详细", payload)

    def test_write_link_only_to_feishu_saves_pending_link(self):
        captured = {}

        def fake_run_lark(*args):
            captured["args"] = args
            return '{"ok": true}'

        with patch("auto_process._run_lark", fake_run_lark):
            self.assertTrue(write_link_only_to_feishu("https://example.com/pending"))

        payload = captured["args"][captured["args"].index("--json") + 1]
        self.assertIn("https://example.com/pending", payload)
        self.assertIn("处理状态", payload)
        self.assertIn("待处理", payload)
        self.assertIn("主要内容", payload)
        self.assertNotIn("处理失败", payload)

    def test_process_does_not_fallback_to_basic_extract_when_ai_fails(self):
        with patch("auto_process.load_settings", return_value={"processingMode": "api", "summaryLength": "brief"}), \
             patch("auto_process.fetch", return_value=("标题", "正文内容", {})), \
             patch("auto_process.try_ai_extract", side_effect=RuntimeError("API failed")), \
             patch("auto_process.write_failed_to_feishu", return_value=True) as write_failed, \
             patch("auto_process.write_to_feishu") as write_success:
            result = process("https://example.com/article")

        self.assertEqual(result["processing_status"], "处理失败")
        self.assertIn("API failed", result["error"])
        write_failed.assert_called_once()
        write_success.assert_not_called()

    def test_process_link_only_mode_saves_pending_without_fetch_or_ai(self):
        settings = {"processingMode": "link_only"}
        with patch("auto_process.load_settings", return_value=settings), \
             patch("auto_process.fetch") as fetch_article, \
             patch("auto_process.try_ai_extract") as try_ai, \
             patch("auto_process.write_link_only_to_feishu", return_value=True) as write_link:
            result = process("https://example.com/link-only")

        self.assertEqual(result["processing_status"], "待处理")
        fetch_article.assert_not_called()
        try_ai.assert_not_called()
        write_link.assert_called_once_with("https://example.com/link-only")

    def test_process_without_api_key_saves_pending_without_marking_failed(self):
        settings = {"processingMode": "api"}
        with patch("auto_process.load_settings", return_value=settings), \
             patch("auto_process.AI_API_KEY", ""), \
             patch("auto_process.fetch") as fetch_article, \
             patch("auto_process.try_ai_extract") as try_ai, \
             patch("auto_process.write_failed_to_feishu") as write_failed, \
             patch("auto_process.write_link_only_to_feishu", return_value=True) as write_link:
            result = process("https://example.com/no-api")

        self.assertEqual(result["processing_status"], "待处理")
        fetch_article.assert_not_called()
        try_ai.assert_not_called()
        write_failed.assert_not_called()
        write_link.assert_called_once_with("https://example.com/no-api")

    def test_get_today_articles_keeps_record_id_for_updates(self):
        fake_records = {
            "data": {
                "data": [["测试文章", "2026-05-03"]],
                "fields": ["标题", "保存日期"],
                "record_id_list": ["rec123"],
            }
        }

        with patch("daily_summary.list_records", return_value=fake_records):
            articles = get_today_articles("2026-05-03")

        self.assertEqual(articles[0]["record_id"], "rec123")

    def test_resolve_report_date_supports_explicit_today_and_yesterday(self):
        now = datetime(2026, 5, 3, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

        self.assertEqual(resolve_report_date(date_str="2026-05-01", now=now), "2026-05-01")
        self.assertEqual(resolve_report_date(mode="today", now=now, timezone_name="Asia/Shanghai"), "2026-05-03")
        self.assertEqual(resolve_report_date(mode="yesterday", now=now, timezone_name="Asia/Shanghai"), "2026-05-02")

    def test_user_settings_supports_dynamic_delivery_time_and_legacy_schedule(self):
        dynamic = normalize_settings({
            "deliverySchedule": "next_day",
            "deliveryTime": "10:00",
        })
        legacy = normalize_settings({
            "deliverySchedule": "next_day_09",
        })

        self.assertEqual(dynamic["deliverySchedule"], "next_day")
        self.assertEqual(dynamic["deliveryTime"], "10:00")
        self.assertEqual(legacy["deliverySchedule"], "next_day")
        self.assertEqual(legacy["deliveryTime"], "09:00")

    def test_scheduler_builds_dynamic_same_day_and_next_day_jobs(self):
        root = Path("/tmp/article-collector")

        same_day = build_scheduled_summary_job({
            "deliverySchedule": "same_day",
            "deliveryTime": "22:30",
            "processingMode": "api",
        }, root)
        next_day = build_scheduled_summary_job({
            "deliverySchedule": "next_day",
            "deliveryTime": "10:00",
            "processingMode": "api",
        }, root)

        self.assertTrue(same_day["enabled"])
        self.assertEqual(same_day["hour"], 22)
        self.assertEqual(same_day["minute"], 30)
        self.assertEqual(same_day["command"], ["python3", "/tmp/article-collector/backend/daily_summary.py", "--today"])
        self.assertTrue(next_day["enabled"])
        self.assertEqual(next_day["hour"], 10)
        self.assertEqual(next_day["minute"], 0)
        self.assertEqual(next_day["command"], ["python3", "/tmp/article-collector/backend/daily_summary.py", "--yesterday"])

    def test_scheduler_disables_manual_and_no_api_non_persistent_jobs(self):
        root = Path("/tmp/article-collector")

        manual = build_scheduled_summary_job({
            "deliverySchedule": "manual",
            "processingMode": "api",
        }, root)
        no_api_local = build_scheduled_summary_job({
            "deliverySchedule": "next_day",
            "deliveryTime": "10:00",
            "processingMode": "link_only",
        }, root, is_persistent_platform=False)
        no_api_persistent = build_scheduled_summary_job({
            "deliverySchedule": "next_day",
            "deliveryTime": "10:00",
            "processingMode": "link_only",
        }, root, is_persistent_platform=True)

        self.assertFalse(manual["enabled"])
        self.assertEqual(manual["reason"], "manual")
        self.assertFalse(no_api_local["enabled"])
        self.assertEqual(no_api_local["reason"], "no_api_non_persistent")
        self.assertTrue(no_api_persistent["enabled"])

    def test_scheduler_builds_macos_launchd_plist(self):
        job = build_scheduled_summary_job({
            "deliverySchedule": "next_day",
            "deliveryTime": "10:05",
            "processingMode": "api",
        }, Path("/tmp/article-collector"))

        plist = build_launchd_plist(job, environment_path="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin")

        self.assertIn("<key>Label</key>", plist)
        self.assertIn("com.article-collector.daily-summary", plist)
        self.assertIn("<key>Hour</key>", plist)
        self.assertIn("<integer>10</integer>", plist)
        self.assertIn("<key>Minute</key>", plist)
        self.assertIn("<integer>5</integer>", plist)
        self.assertIn("<string>/tmp/article-collector/backend/daily_summary.py</string>", plist)
        self.assertIn("<string>--yesterday</string>", plist)
        self.assertIn("<key>EnvironmentVariables</key>", plist)
        self.assertIn("<string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>", plist)

    def test_scheduler_supports_macos_and_rejects_windows(self):
        mac = scheduler_support_status("Darwin")
        windows = scheduler_support_status("Windows")

        self.assertTrue(mac["supported"])
        self.assertEqual(mac["kind"], "launchd")
        self.assertFalse(windows["supported"])
        self.assertEqual(windows["reason"], "windows_not_supported")

    def test_scheduler_detects_macos_protected_project_paths(self):
        self.assertTrue(is_macos_protected_path(Path("/Users/test/Desktop/project")))
        self.assertTrue(is_macos_protected_path(Path("/Users/test/Documents/project")))
        self.assertTrue(is_macos_protected_path(Path("/Users/test/Downloads/project")))
        self.assertFalse(is_macos_protected_path(Path("/Users/test/Projects/project")))

    def test_retry_failed_articles_updates_record_when_retry_succeeds(self):
        articles = [
            {
                "record_id": "rec123",
                "标题": "失败文章",
                "原文链接": "https://example.com/failed",
                "处理状态": "处理失败",
            }
        ]
        extracted = {
            "title": "已恢复文章",
            "author": "",
            "source": "Example",
            "publish_date": "2026-05-03",
            "category": "AI",
            "summary": "恢复摘要",
            "tags": ["AI"],
            "main_points": ["简短内容"],
        }

        with patch("daily_summary.process_url", return_value=extracted), \
             patch("daily_summary.update_record_fields") as update_record:
            retried = retry_failed_articles(articles)

        self.assertEqual(retried[0]["处理状态"], "完成")
        update_record.assert_called_once()
        patch_fields = update_record.call_args.args[1]
        self.assertEqual(patch_fields["处理状态"], "完成")
        self.assertEqual(patch_fields["主要内容"], "1. 简短内容")
        self.assertNotIn("主要内容-中等", patch_fields)

    def test_complete_incomplete_articles_processes_pending_before_summary(self):
        articles = [
            {
                "record_id": "rec_pending",
                "标题": "待处理文章",
                "原文链接": "https://example.com/pending",
                "处理状态": "待处理",
            },
            {
                "record_id": "rec_done",
                "标题": "完成文章",
                "原文链接": "https://example.com/done",
                "处理状态": "完成",
            },
        ]
        extracted = {
            "title": "已处理文章",
            "author": "",
            "source": "Example",
            "publish_date": "2026-05-03",
            "category": "AI",
            "summary": "处理后摘要",
            "tags": ["AI"],
            "main_points": ["处理后要点"],
        }

        with patch("daily_summary.process_url", return_value=extracted), \
             patch("daily_summary.update_record_fields") as update_record:
            completed = complete_incomplete_articles(articles)

        self.assertEqual(completed[0]["处理状态"], "完成")
        self.assertEqual(completed[0]["摘要"], "处理后摘要")
        self.assertEqual(completed[1]["处理状态"], "完成")
        update_record.assert_called_once()
        self.assertEqual(update_record.call_args.args[0], "rec_pending")

    def test_complete_incomplete_articles_marks_pending_failed_when_api_fails(self):
        articles = [
            {
                "record_id": "rec_pending",
                "标题": "待处理文章",
                "原文链接": "https://example.com/pending",
                "处理状态": "待处理",
            }
        ]

        with patch("daily_summary.process_url", side_effect=RuntimeError("API failed")), \
             patch("daily_summary.update_record_fields") as update_record:
            completed = complete_incomplete_articles(articles)

        self.assertEqual(completed[0]["处理状态"], "处理失败")
        self.assertIn("API failed", completed[0]["摘要"])
        update_record.assert_called_once()
        fields = update_record.call_args.args[1]
        self.assertEqual(fields["处理状态"], "处理失败")

    def test_get_pending_articles_filters_today_pending_records(self):
        fake_records = {
            "data": {
                "data": [
                    ["今天待处理", "https://example.com/pending", "2026-05-03", ["待处理"]],
                    ["今天完成", "https://example.com/done", "2026-05-03", ["完成"]],
                    ["昨天待处理", "https://example.com/old", "2026-05-02", ["待处理"]],
                ],
                "fields": ["标题", "原文链接", "保存日期", "处理状态"],
                "record_id_list": ["rec_pending", "rec_done", "rec_old"],
            }
        }

        with patch("daily_summary.list_records", return_value=fake_records):
            pending = get_pending_articles("2026-05-03")

        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["record_id"], "rec_pending")
        self.assertEqual(pending[0]["原文链接"], "https://example.com/pending")

    def test_update_pending_article_completed_writes_summary_and_status(self):
        article = {
            "title": "标题",
            "author": "作者",
            "source": "来源",
            "publish_date": "2026-05-03",
            "category": "AI",
            "summary": "摘要",
            "tags": ["AI", "测试"],
            "main_points": ["要点一", "要点二"],
        }

        with patch("daily_summary.update_record_fields") as update_record:
            update_pending_article_completed("rec123", article, "https://example.com/a")

        update_record.assert_called_once()
        fields = update_record.call_args.args[1]
        self.assertEqual(fields["标题"], "标题")
        self.assertEqual(fields["原文链接"], "https://example.com/a")
        self.assertEqual(fields["摘要"], "摘要")
        self.assertEqual(fields["关键词"], "AI, 测试")
        self.assertEqual(fields["主要内容"], "1. 要点一\n2. 要点二")
        self.assertEqual(fields["处理状态"], "完成")

    def test_update_record_fields_uses_record_upsert_not_batch_update(self):
        import daily_summary

        captured = {}

        def fake_run_cli(*args):
            captured["args"] = args
            return {"ok": True}

        with patch("daily_summary._run_cli", fake_run_cli):
            daily_summary.update_record_fields("rec123", {"处理状态": "完成"})

        args = captured["args"]
        self.assertIn("+record-upsert", args)
        self.assertNotIn("+record-batch-update", args)
        self.assertIn("--record-id", args)
        self.assertEqual(args[args.index("--record-id") + 1], "rec123")

    def test_mark_pending_article_failed_sets_failed_status(self):
        with patch("daily_summary.update_record_fields") as update_record:
            mark_pending_article_failed("rec123", "抓取失败")

        update_record.assert_called_once()
        fields = update_record.call_args.args[1]
        self.assertEqual(fields["处理状态"], "处理失败")
        self.assertIn("抓取失败", fields["摘要"])

    def test_extract_prompt_uses_selected_summary_length(self):
        brief_prompt = build_extract_prompt("标题", "https://example.com", "正文", "brief")
        medium_prompt = build_extract_prompt("标题", "https://example.com", "正文", "medium")
        detailed_prompt = build_extract_prompt("标题", "https://example.com", "正文", "detailed")

        self.assertIn("简短篇幅", brief_prompt)
        self.assertIn("中等篇幅", medium_prompt)
        self.assertIn("详细篇幅", detailed_prompt)
        self.assertIn("比简短篇幅更完整", medium_prompt)
        self.assertIn("每条 60-100 字", medium_prompt)
        self.assertIn("建议 4-6 条", detailed_prompt)
        self.assertIn("每条 300-400 字", detailed_prompt)
        self.assertIn("自动回退为中等篇幅要求", detailed_prompt)
        self.assertIn("可追溯的原始资料细节", detailed_prompt)
        self.assertIn("只总结文章主体内容", detailed_prompt)
        self.assertNotIn("main_content_medium", detailed_prompt)

    def test_normalize_extracted_article_keeps_main_points_only(self):
        article = normalize_extracted_article({
            "summary": "一句话摘要",
            "main_points": ["要点一", "要点二"],
        })

        self.assertEqual(article["main_points"], ["要点一", "要点二"])
        self.assertNotIn("main_content_short", article)

    def test_clean_article_text_prefers_body_and_removes_page_noise(self):
        html = """
        <html>
          <head><title>测试标题</title></head>
          <body>
            <nav>Subscribe on Apple Podcasts</nav>
            <main>
              <article>
                <h1>测试标题</h1>
                <p>这是文章主体第一段，讨论OpenAI诉讼的关键争议。</p>
                <p>这是文章主体第二段，包含人物、事件和因果关系。</p>
                <section class="author-bio">作者简介：某某是TechCrunch制作人。</section>
                <aside>相关阅读：另一个AI故事</aside>
                <div class="newsletter">订阅我们的newsletter</div>
              </article>
            </main>
            <footer>Copyright TechCrunch</footer>
          </body>
        </html>
        """

        result = clean_article_text_from_html(html)

        self.assertEqual(result["title"], "测试标题")
        self.assertIn("文章主体第一段", result["text"])
        self.assertIn("文章主体第二段", result["text"])
        self.assertNotIn("作者简介", result["text"])
        self.assertNotIn("相关阅读", result["text"])
        self.assertNotIn("newsletter", result["text"])
        self.assertNotIn("Copyright", result["text"])

    def test_fetch_article_retries_without_proxy_when_default_fetch_fails(self):
        from extractor import fetch_article

        html = """
        <html>
          <head><title>代理重试测试</title></head>
          <body><article><p>无代理重试后抓取到的正文。</p></article></body>
        </html>
        """

        class FakeResponse:
            text = html

            def raise_for_status(self):
                return None

        sessions = []

        class FakeSession:
            def __init__(self):
                self.trust_env = True
                sessions.append(self)

            def get(self, *args, **kwargs):
                return FakeResponse()

        with patch("extractor.requests.get", side_effect=requests.RequestException("proxy failed")) as default_get, \
             patch("extractor.requests.Session", FakeSession):
            article = fetch_article("https://example.com/proxy")

        default_get.assert_called_once()
        self.assertEqual(len(sessions), 1)
        self.assertFalse(sessions[0].trust_env)
        self.assertEqual(article["title"], "代理重试测试")
        self.assertIn("无代理重试后抓取到的正文", article["text"])

    def test_skill_instructions_include_onboarding_prompts(self):
        skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("首次使用", skill_text)
        self.assertIn("前置依赖", skill_text)
        self.assertIn("lark-cli", skill_text)
        self.assertIn("机器人应用", skill_text)
        self.assertIn("直接帮用户创建一个飞书多维表格", skill_text)
        self.assertIn("以后你收藏的文章都可以在这里查看", skill_text)
        self.assertIn("<飞书多维表格链接>", skill_text)
        self.assertIn("发送报告时间", skill_text)
        self.assertIn("当天晚上 9 点", skill_text)
        self.assertIn("第二天早上 9 点", skill_text)
        self.assertIn("发送我今天的阅读汇总", skill_text)
        self.assertIn("阅读汇总篇幅", skill_text)
        self.assertIn("API 配置", skill_text)
        self.assertIn("你有可用的模型API做文章总结吗", skill_text)
        self.assertIn("我有API，稍后提供base url/auth token/ai model", skill_text)
        self.assertIn("没有 api，用我正在使用的agent的原生能力", skill_text)
        self.assertIn("只保存链接模式", skill_text)
        self.assertIn("待处理", skill_text)
        self.assertIn("处理今天收藏的文章", skill_text)
        self.assertIn("写回飞书表格", skill_text)
        self.assertIn("处理状态", skill_text)
        self.assertIn("更新为“完成”", skill_text)
        self.assertIn("更新为“处理失败”", skill_text)
        self.assertIn("BASE_URL", skill_text)
        self.assertIn("AUTH_TOKEN", skill_text)
        self.assertIn("AI_MODEL", skill_text)
        self.assertIn("不限定 Anthropic 命名", skill_text)
        self.assertIn("浏览器插件", skill_text)
        self.assertIn("使用体验更好", skill_text)
        self.assertIn("强烈推荐", skill_text)
        self.assertIn("是否要安装浏览器插件", skill_text)
        self.assertIn("开发者模式", skill_text)
        self.assertIn("加载未打包的程序", skill_text)
        self.assertIn("chrome-extension", skill_text)
        self.assertIn("收藏这篇文章，这是文章链接", skill_text)
        self.assertIn("简短", skill_text)
        self.assertIn("中等", skill_text)
        self.assertIn("详细", skill_text)
        self.assertIn("所有设置之后都可以通过对话随时修改", skill_text)
        self.assertIn("显示我当前的设置", skill_text)


if __name__ == "__main__":
    unittest.main()
