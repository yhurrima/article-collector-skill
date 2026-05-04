"""Uninstall the macOS launchd daily summary schedule and queue server."""
import subprocess

from scheduler import (
    LAUNCHD_LABEL,
    LAUNCHD_PLIST_PATH,
    LAUNCHD_QUEUE_LABEL,
    LAUNCHD_QUEUE_PLIST_PATH,
    scheduler_support_status,
)


def uninstall_macos_launchd(plist_path, label):
    if plist_path.exists():
        subprocess.run(["launchctl", "unload", str(plist_path)], check=False, capture_output=True, text=True)
        plist_path.unlink()
        return True
    return False


def main():
    status = scheduler_support_status()
    if status["kind"] != "launchd":
        print(f"当前系统没有可卸载的 macOS launchd 定时任务: {status.get('reason', 'not_macos')}")
        return 1

    # Uninstall queue server
    queue_removed = uninstall_macos_launchd(LAUNCHD_QUEUE_PLIST_PATH, LAUNCHD_QUEUE_LABEL)
    if queue_removed:
        print(f"已卸载队列服务: {LAUNCHD_QUEUE_LABEL}")

    # Uninstall daily summary scheduler
    summary_removed = uninstall_macos_launchd(LAUNCHD_PLIST_PATH, LAUNCHD_LABEL)
    if summary_removed:
        print(f"已卸载定时汇总任务: {LAUNCHD_LABEL}")

    if not queue_removed and not summary_removed:
        print("未找到已安装的 macOS launchd 定时任务")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
