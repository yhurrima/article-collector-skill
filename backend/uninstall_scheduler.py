"""Uninstall the macOS launchd daily summary schedule."""
import subprocess

from scheduler import LAUNCHD_LABEL, LAUNCHD_PLIST_PATH, scheduler_support_status


def uninstall_macos_launchd(plist_path=LAUNCHD_PLIST_PATH):
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

    removed = uninstall_macos_launchd()
    if removed:
        print(f"已卸载 macOS launchd 定时任务: {LAUNCHD_LABEL}")
    else:
        print("未找到已安装的 macOS launchd 定时任务")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
