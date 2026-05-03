"""User preferences for article summary delivery."""
import json
import os
import re
from pathlib import Path


SETTINGS_DIR = Path(os.environ.get("ARTICLE_COLLECTOR_HOME", "~/.article-collector")).expanduser()
SETTINGS_PATH = SETTINGS_DIR / "config.json"

DEFAULT_SETTINGS = {
    "onboardingComplete": False,
    "timezone": "Asia/Shanghai",
    "deliverySchedule": "same_day",
    "deliveryTime": "21:00",
    "summaryLength": "brief",
    "processingMode": "api",
    "delivery": {
        "method": "feishu",
        "chatId": "",
    },
}

VALID_SUMMARY_LENGTHS = {"brief", "medium", "detailed"}
VALID_PROCESSING_MODES = {"api", "link_only"}
VALID_DELIVERY_SCHEDULES = {"same_day", "next_day", "manual"}
LEGACY_DELIVERY_SCHEDULES = {
    "same_day_21": ("same_day", "21:00"),
    "next_day_09": ("next_day", "09:00"),
}
TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def normalize_settings(saved=None):
    saved = saved or {}
    settings = DEFAULT_SETTINGS.copy()
    settings.update(saved)
    settings["delivery"] = {
        **DEFAULT_SETTINGS["delivery"],
        **saved.get("delivery", {}),
    }

    schedule = settings.get("deliverySchedule")
    if schedule in LEGACY_DELIVERY_SCHEDULES:
        settings["deliverySchedule"], legacy_time = LEGACY_DELIVERY_SCHEDULES[schedule]
        if not saved.get("deliveryTime"):
            settings["deliveryTime"] = legacy_time

    if settings.get("summaryLength") not in VALID_SUMMARY_LENGTHS:
        settings["summaryLength"] = DEFAULT_SETTINGS["summaryLength"]
    if settings.get("processingMode") not in VALID_PROCESSING_MODES:
        settings["processingMode"] = DEFAULT_SETTINGS["processingMode"]
    if settings.get("deliverySchedule") not in VALID_DELIVERY_SCHEDULES:
        settings["deliverySchedule"] = DEFAULT_SETTINGS["deliverySchedule"]
    if settings.get("deliverySchedule") != "manual" and not TIME_RE.match(str(settings.get("deliveryTime", ""))):
        settings["deliveryTime"] = DEFAULT_SETTINGS["deliveryTime"]

    return settings


def load_settings():
    if not SETTINGS_PATH.exists():
        return normalize_settings()

    with SETTINGS_PATH.open("r", encoding="utf-8") as f:
        saved = json.load(f)

    return normalize_settings(saved)


def save_settings(settings):
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with SETTINGS_PATH.open("w", encoding="utf-8") as f:
        json.dump(normalize_settings(settings), f, ensure_ascii=False, indent=2)
