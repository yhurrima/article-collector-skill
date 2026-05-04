"""Pure helpers for building scheduled summary jobs."""
import plistlib
import platform
from pathlib import Path

from user_settings import normalize_settings


LAUNCHD_LABEL = "com.article-collector.daily-summary"
LAUNCHD_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"
LAUNCHD_QUEUE_LABEL = "com.article-collector.queue-server"
LAUNCHD_QUEUE_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_QUEUE_LABEL}.plist"
MACOS_PROTECTED_DIRS = {"Desktop", "Documents", "Downloads"}


def parse_delivery_time(value):
    hour_text, minute_text = str(value).split(":", 1)
    return int(hour_text), int(minute_text)


def build_scheduled_summary_job(settings, project_root, is_persistent_platform=False, python_executable="python3"):
    """Return the daily summary job implied by settings without installing it."""
    normalized = normalize_settings(settings)
    schedule = normalized["deliverySchedule"]
    processing_mode = normalized["processingMode"]

    if schedule == "manual":
        return {
            "enabled": False,
            "reason": "manual",
        }

    if processing_mode == "link_only" and not is_persistent_platform:
        return {
            "enabled": False,
            "reason": "no_api_non_persistent",
        }

    if schedule == "same_day":
        report_arg = "--today"
    elif schedule == "next_day":
        report_arg = "--yesterday"
    else:
        return {
            "enabled": False,
            "reason": "unsupported_schedule",
        }

    hour, minute = parse_delivery_time(normalized["deliveryTime"])
    script = Path(project_root) / "backend" / "daily_summary.py"
    return {
        "enabled": True,
        "schedule": schedule,
        "hour": hour,
        "minute": minute,
        "command": [python_executable, str(script), report_arg],
    }


def build_launchd_plist(job, label=LAUNCHD_LABEL, environment_path=None):
    """Build a launchd plist for an enabled scheduled summary job."""
    if not job.get("enabled"):
        raise ValueError(f"Cannot build plist for disabled job: {job.get('reason', 'unknown')}")

    plist = {
        "Label": label,
        "ProgramArguments": job["command"],
        "StartCalendarInterval": {
            "Hour": job["hour"],
            "Minute": job["minute"],
        },
        "WorkingDirectory": str(Path(job["command"][1]).parents[1]),
        "StandardOutPath": "/tmp/article-collector-daily-summary.out.log",
        "StandardErrorPath": "/tmp/article-collector-daily-summary.err.log",
    }
    if environment_path:
        plist["EnvironmentVariables"] = {
            "PATH": environment_path,
        }
    return plistlib.dumps(plist, sort_keys=False).decode("utf-8")


def current_os():
    return platform.system()


def scheduler_support_status(system_name=None):
    system = system_name or current_os()
    if system == "Darwin":
        return {
            "supported": True,
            "kind": "launchd",
        }
    if system == "Windows":
        return {
            "supported": False,
            "kind": "windows",
            "reason": "windows_not_supported",
        }
    if system == "Linux":
        return {
            "supported": False,
            "kind": "linux",
            "reason": "linux_not_implemented",
        }
    return {
        "supported": False,
        "kind": "unknown",
        "reason": "unsupported_os",
    }


def is_macos_protected_path(path):
    """Return True if launchd may hit TCC restrictions for this project path."""
    resolved_parts = Path(path).expanduser().parts
    if len(resolved_parts) < 4:
        return False
    return (
        resolved_parts[1] == "Users"
        and resolved_parts[3] in MACOS_PROTECTED_DIRS
    )


def build_queue_server_plist(project_root, python_executable="python3", environment_path=None):
    """Build a launchd plist for the queue server (always-on HTTP listener)."""
    script = Path(project_root) / "backend" / "queue_server.py"
    plist = {
        "Label": LAUNCHD_QUEUE_LABEL,
        "ProgramArguments": [python_executable, str(script)],
        "RunAtLoad": True,
        "KeepAlive": True,
        "WorkingDirectory": str(project_root),
        "StandardOutPath": "/tmp/article-collector-queue-server.out.log",
        "StandardErrorPath": "/tmp/article-collector-queue-server.err.log",
    }
    if environment_path:
        plist["EnvironmentVariables"] = {
            "PATH": environment_path,
        }
    return plistlib.dumps(plist, sort_keys=False).decode("utf-8")
