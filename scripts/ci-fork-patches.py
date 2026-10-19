#!/usr/bin/env python3
"""Apply the fork's patches to the working tree, for the CI build only.

Every patch is an assertion first and a rewrite second: when upstream changes the line a
patch anchors on, this fails loudly instead of shipping a build that silently kept the
upstream behaviour. Nothing is committed, so merging upstream stays conflict-free.

Patches:

* `AgreementConsentPanel.kt` - replaces the consent bar so the agreement needs one tap
  instead of a 30 second wait plus a scroll check plus an arithmetic answer.
* the consent countdown's initial value - dropped to 0 so the retired timer logic in
  `AgreementScreen` does not keep recomposing the screen for 30 seconds.
* the application id - suffixed with `.F` so this build installs alongside the upstream one.
  The namespace stays untouched: it is what `.MainActivity` and the R class resolve against.
* the version name and code - read from `CI_VERSION_NAME` / `CI_VERSION_CODE`, so CI ships its
  own monotonic version instead of upstream's date-and-commit naming. Locally the variables
  are absent and upstream's sources stay in charge.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

PANEL_TARGET = "app/src/main/java/com/eltavine/duckdetector/startup/legal/AgreementConsentPanel.kt"
PANEL_SOURCE = "fork/patches/AgreementConsentPanel.kt"
APP_GRADLE = "app/build.gradle.kts"
VERSION_FILE = "build-logic/src/main/kotlin/com/eltavine/duckdetector/buildlogic/DuckDetectorAndroidApplicationConventionPlugin.kt"

PACKAGE_FROM = 'applicationId = "com.eltavine.duckdetector"'
PACKAGE_TO = 'applicationId = "com.eltavine.duckdetector.fork"'

COUNTDOWN_FROM = "var countdown by remember { mutableIntStateOf(30) }"
COUNTDOWN_TO = "var countdown by remember { mutableIntStateOf(0) }"

VERSION_CODE_FROM = "this.versionCode = versionCode.get()"
VERSION_CODE_TO = 'this.versionCode = System.getenv("CI_VERSION_CODE")?.toIntOrNull() ?: versionCode.get()'
VERSION_NAME_FROM = "this.versionName = versionName.get()"
VERSION_NAME_TO = 'this.versionName = System.getenv("CI_VERSION_NAME") ?: versionName.get()'

# AGP 9 不再保证 ciRelease 产出 v3 块（实测 --print-certs 里 v3 为 false），显式打开，
#   让 CI 的 v2+v3 断言有意义
SIGNING_V3_FROM = """                        keyPassword = releaseKeyPassword.orNull
                    }"""
SIGNING_V3_TO = """                        keyPassword = releaseKeyPassword.orNull
                        enableV3Signing = true
                    }"""


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
    targets = {
        "screen": screen,
        "app": repo / APP_GRADLE,
        "version": repo / VERSION_FILE,
    }
    for label, path in targets.items():
        if not path.is_file():
            print(f"::error::找不到 {path.relative_to(repo)} —— 上游移动或改名了", file=sys.stderr)
            return 1

    dry = args.check
    results: list[Result] = [copy_patch(repo, dry)]
    results.append(replace_once(targets["screen"], COUNTDOWN_FROM, COUNTDOWN_TO, dry))
    results.append(replace_once(targets["app"], PACKAGE_FROM, PACKAGE_TO, dry))
    results.append(replace_once(targets["version"], VERSION_CODE_FROM, VERSION_CODE_TO, dry))
    results.append(replace_once(targets["version"], VERSION_NAME_FROM, VERSION_NAME_TO, dry))
    results.append(replace_once(targets["version"], SIGNING_V3_FROM, SIGNING_V3_TO, dry))

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
