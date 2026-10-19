#!/usr/bin/env python3
"""Lay the fork's own build and source files over the working tree, for the CI build only.

Nothing is committed, so syncing upstream stays conflict-free. The fork owns its own
app/build.gradle.kts (package id + version); signing comes from the ANDROID_KEYSTORE_* env vars
the upstream build-logic already reads, so no upstream build file is touched.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

LEGAL = "app/src/main/java/com/eltavine/duckdetector/startup/legal"
APP_GRADLE = "app/build.gradle.kts"
APP_GRADLE_SOURCE = "fork/ci/app/build.gradle.kts"
PANEL_SOURCE = "fork/ci/AgreementConsentPanel.kt"
PANEL_TARGET = f"{LEGAL}/AgreementConsentPanel.kt"

# The consent bar is replaced by a one-tap version, but the screen still runs the 30 second
# timer and recomposes for it. Zeroing the start value retires it; the anchor is asserted so a
# renamed variable upstream fails loudly instead of silently keeping the timer.
COUNTDOWN_FROM = "var countdown by remember { mutableIntStateOf(30) }"
COUNTDOWN_TO = "var countdown by remember { mutableIntStateOf(0) }"
SCREEN = f"{LEGAL}/AgreementScreen.kt"

MANIFEST = "app/src/main/AndroidManifest.xml"
# native 启动壳默认按 <包名>.MainActivity 拼类名（preload_entry.cpp），包名加了 .fork 就拼不到
#   真实类；上游为此留了 meta-data 入口，指回不改名的真实类即可
LAUNCH_META_FROM = """            <meta-data
                android:name="android.app.lib_name"
                android:value="duckdetector" />"""
LAUNCH_META_TO = LAUNCH_META_FROM + """
            <meta-data
                android:name="com.eltavine.duckdetector.launch_activity"
                android:value="com.eltavine.duckdetector.MainActivity" />"""

APP_NAME_GLOB = "core/ui/src/main/res/values*/mainscreen_strings.xml"
APP_NAME_FROM = ">Duck Detector<"
APP_NAME_TO = ">Duck Detector.F<"


def replace_once(path: Path, old: str, new: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        return False
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", default=".")
    parser.add_argument("--check", action="store_true", help="report without writing")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    source = repo / PANEL_SOURCE
    target = repo / PANEL_TARGET
    screen = repo / SCREEN
    if not source.exists():
        print(f"::error::缺少 {PANEL_SOURCE}", file=sys.stderr)
        return 1
    if not screen.exists():
        print(f"::error::缺少 {SCREEN}", file=sys.stderr)
        return 1

    timer_ok = COUNTDOWN_FROM in screen.read_text(encoding="utf-8")
    if not timer_ok:
        print(f"::error::{SCREEN} 里找不到倒计时锚点 —— 上游改了写法，需回来同步", file=sys.stderr)
        return 1

    gradle_source = repo / APP_GRADLE_SOURCE
    if not gradle_source.exists():
        print(f"::error::缺少 {APP_GRADLE_SOURCE}", file=sys.stderr)
        return 1

    if args.check:
        print(f"✅ {PANEL_TARGET}：将用 fork 版覆盖（dry run）")
        print(f"✅ {APP_GRADLE}：将用 fork 版覆盖（dry run）")
        print(f"✅ {MANIFEST}：加 launch_activity meta-data（dry run）")
        print(f"✅ 应用名 → Duck Detector.F（dry run）")
        print(f"✅ {SCREEN}：倒计时归零（dry run）")
        return 0

    manifest = repo / MANIFEST
    if "com.eltavine.duckdetector.launch_activity" not in manifest.read_text(encoding="utf-8"):
        replace_once(manifest, LAUNCH_META_FROM, LAUNCH_META_TO)

    renamed = 0
    for strings in repo.glob(APP_NAME_GLOB):
        text = strings.read_text(encoding="utf-8")
        if APP_NAME_FROM in text:
            strings.write_text(text.replace(APP_NAME_FROM, APP_NAME_TO), encoding="utf-8")
            renamed += 1

    shutil.copyfile(source, target)
    shutil.copyfile(gradle_source, repo / APP_GRADLE)
    replace_once(screen, COUNTDOWN_FROM, COUNTDOWN_TO)
    print(f"✅ 已覆盖 {PANEL_TARGET}")
    print(f"✅ 已覆盖 {APP_GRADLE}")
    print(f"✅ 已为 NativeActivity 配上 launch_activity meta-data")
    print(f"✅ 应用名改为 Duck Detector.F（{renamed} 个语言文件）")
    print(f"✅ 已归零 {SCREEN} 的倒计时")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
