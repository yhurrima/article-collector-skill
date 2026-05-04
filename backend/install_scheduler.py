"""Install the configured daily summary schedule on supported platforms."""
import os
import subprocess
import sys
from pathlib import Path

from scheduler import (
    LAUNCHD_LABEL,
    LAUNCHD_PLIST_PATH,
    LAUNCHD_QUEUE_LABEL,
    LAUNCHD_QUEUE_PLIST_PATH,
    build_launchd_plist,
    build_scheduled_summary_job,
    build_queue_server_plist,
    is_macos_protected_path,
    scheduler_support_status,
)
from user_settings import load_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def install_macos_launchd(job, plist_path=LAUNCHD_PLIST_PATH):
    project_root = Path(job["command"][1]).parents[1]
    if is_macos_protected_path(project_root):
        raise RuntimeError(
            "项目位于 macOS 受保护目录，launchd 可能无法读取脚本。"
            "请将项目移动到 ~/Projects/article-collector 或 ~/.article-collector/app 后再安装。"
        )
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_text(build_launchd_plist(job, environment_path=os.environ.get("PATH", "")), encoding="utf-8")
    subprocess.run(["launchctl", "unload", str(plist_path)], check=False, capture_output=True, text=True)
    subprocess.run(["launchctl", "load", str(plist_path)], check=True)
    return plist_path


def install_macos_queue_server(plist_path=LAUNCHD_QUEUE_PLIST_PATH):
    """Install the queue server as a launchd service (always-on)."""
    if is_macos_protected_path(PROJECT_ROOT):
        raise RuntimeError(
            "项目位于 macOS 受保护目录，launchd 可能无法读取脚本。"
            "请将项目移动到 ~/Projects/article-collector 或 ~/.article-collector/app 后再安装。"
        )
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_text(build_queue_server_plist(PROJECT_ROOT, python_executable=sys.executable, environment_path=os.environ.get("PATH", "")), encoding="utf-8")
    subprocess.run(["launchctl", "unload", str(plist_path)], check=False, capture_output=True, text=True)
    subprocess.run(["launchctl", "load", str(plist_path)], check=True)
    return plist_path


def main():
    status = scheduler_support_status()
    if not status["supported"]:
        print(f"当前系统暂不支持自动安装定时任务: {status['reason']}")
        print("Windows 暂不支持系统定时任务；可手动运行 daily_summary.py --today/--yesterday。")
        return 1

    # Always install queue server on macOS (for browser extension)
    if status["kind"] == "launchd":
        queue_plist = install_macos_queue_server()
        print(f"已安装队列服务: {LAUNCHD_QUEUE_LABEL}")
        print(f"plist: {queue_plist}")

    # Install daily summary scheduler if configured
    settings = load_settings()
    job = build_scheduled_summary_job(settings, PROJECT_ROOT, python_executable=sys.executable)
    if not job["enabled"]:
        print(f"不安装定时汇总任务: {job['reason']}")
        return 0

    if status["kind"] == "launchd":
        plist_path = install_macos_launchd(job)
        print(f"已安装定时汇总任务: {LAUNCHD_LABEL}")
        print(f"plist: {plist_path}")
        return 0

    print("当前平台未实现安装器")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
