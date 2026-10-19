#!/usr/bin/env python3
"""Apply the fork's behavioural patches to the working tree, for the CI build only.

Every patch is an assertion first and a rewrite second: when upstream changes the line a
patch anchors on, this fails loudly instead of shipping a build that silently kept the
upstream behaviour. Nothing is committed, so merging upstream stays conflict-free.

Patches:

* `AgreementConsentPanel.kt` - replaces the consent bar so the agreement needs one tap
  instead of a 30 second wait plus a scroll check plus an arithmetic answer.
* the consent countdown's initial value - dropped to 0 so the retired timer logic in
  `AgreementScreen` does not keep recomposing the screen for 30 seconds.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

PANEL_TARGET = "app/src/main/java/com/eltavine/duckdetector/startup/legal/AgreementConsentPanel.kt"
PANEL_SOURCE = "fork/patches/AgreementConsentPanel.kt"

COUNTDOWN_FROM = "var countdown by remember { mutableIntStateOf(30) }"
COUNTDOWN_TO = "var countdown by remember { mutableIntStateOf(0) }"


@dataclass(frozen=True)
class Result:
    name: str
    changed: bool
    detail: str


def replace_once(path: Path, old: str, new: str, dry_run: bool) -> Result:
    text = path.read_text(encoding="utf-8")
    if new in text and old not in text:
        return Result(path.name, True, "已是目标写法（补丁可重复应用）")
    occurrences = text.count(old)
    if occurrences == 0:
        return Result(path.name, False, f"锚点已不存在，上游可能改过写法：{old!r}")
    if occurrences > 1:
        return Result(path.name, False, f"锚点出现 {occurrences} 次，无法唯一定位：{old!r}")
    if not dry_run:
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return Result(path.name, True, "已改写（dry run）" if dry_run else "已改写")


def copy_patch(repo: Path, dry_run: bool) -> Result:
    source = repo / PANEL_SOURCE
    target = repo / PANEL_TARGET
    if not source.is_file():
        return Result(PANEL_TARGET, False, f"补丁文件缺失：{PANEL_SOURCE}")
    if not target.is_file():
        return Result(PANEL_TARGET, False, "上游对应文件不存在，路径或类名可能变过")
    same = source.read_bytes() == target.read_bytes()
    if same:
        return Result(PANEL_TARGET, True, "已是 fork 版（补丁可重复应用）")
    if dry_run:
        return Result(PANEL_TARGET, True, "将用 fork 版覆盖（dry run）")
    shutil.copyfile(source, target)
    return Result(PANEL_TARGET, True, "已用 fork 版覆盖")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", default=".", help="repository root")
    parser.add_argument("--check", action="store_true", help="report without writing")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    screen = repo / "app/src/main/java/com/eltavine/duckdetector/startup/legal/AgreementScreen.kt"
    if not screen.is_file():
        print("::error::找不到 AgreementScreen.kt —— 协议页被移动或改名了", file=sys.stderr)
        return 1

    results: list[Result] = [copy_patch(repo, args.check)]
    results.append(replace_once(screen, COUNTDOWN_FROM, COUNTDOWN_TO, args.check))

    failures = [r for r in results if not r.changed]
    for result in results:
        mark = "✅" if result.changed else "❌"
        print(f"{mark} {result.name}：{result.detail}")
    if failures:
        print("\n上游结构已变，必须回来同步 fork 补丁（不改则沿用上游行为）", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
