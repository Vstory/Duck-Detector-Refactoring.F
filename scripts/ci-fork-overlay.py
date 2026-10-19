#!/usr/bin/env python3
"""Lay the fork's own source files over the working tree, for the CI build only.

Nothing is committed, so syncing upstream stays conflict-free. Build settings (application id,
version, signing) are NOT here -- they come from fork/build/fork.init.gradle plus environment
variables, which leaves upstream's build files untouched.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

LEGAL = "app/src/main/java/com/eltavine/duckdetector/startup/legal"
PANEL_SOURCE = "fork/build/AgreementConsentPanel.kt"
PANEL_TARGET = f"{LEGAL}/AgreementConsentPanel.kt"

# The consent bar is replaced by a one-tap version, but the screen still runs the 30 second
# timer and recomposes for it. Zeroing the start value retires it; the anchor is asserted so a
# renamed variable upstream fails loudly instead of silently keeping the timer.
COUNTDOWN_FROM = "var countdown by remember { mutableIntStateOf(30) }"
COUNTDOWN_TO = "var countdown by remember { mutableIntStateOf(0) }"
SCREEN = f"{LEGAL}/AgreementScreen.kt"


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

    if args.check:
        print(f"✅ {PANEL_TARGET}：将用 fork 版覆盖（dry run）")
        print(f"✅ {SCREEN}：倒计时归零（dry run）")
        return 0

    shutil.copyfile(source, target)
    replace_once(screen, COUNTDOWN_FROM, COUNTDOWN_TO)
    print(f"✅ 已覆盖 {PANEL_TARGET}")
    print(f"✅ 已归零 {SCREEN} 的倒计时")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
