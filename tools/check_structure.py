from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ALLOWED_TOP_LEVEL_ZIPS = {
    "MVP_FlowForm_Vitality_MasterSuite_V2_POLISHED_UNIFIEDROOT_R6_STABLE_BOOT.zip",
}

ALLOWED_RUN_SCRIPTS = {
    "00_setup_all.bat",
    "00_setup.bat",
    "01_run_all.bat",
    "_run.bat",
    "_open_browser.bat",
    "_run_tests.bat",
    "run_server.py",
    "boot_port.py",
    "_BAT/1_setup.bat",
    "_BAT/2_run.bat",
    "_BAT/3_open_browser.bat",
    "_BAT/6_run_tests.bat",
    "tools/run_full_tests.py",
    "tools/check_structure.py",
}

BOOT_STACK_GROUPS = {
    "root_boot": {"00_setup.bat", "_run.bat", "_open_browser.bat", "_run_tests.bat", "run_server.py", "boot_port.py"},
    "legacy_bat_wrappers": {"_BAT/1_setup.bat", "_BAT/2_run.bat", "_BAT/3_open_browser.bat", "_BAT/6_run_tests.bat"},
}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def find_nested_or_unapproved_zips() -> list[str]:
    violations: list[str] = []
    for path in ROOT.rglob("*.zip"):
        rp = rel(path)
        if "/" in rp:
            violations.append(f"Nested ZIP not allowed: {rp}")
            continue
        if path.name not in ALLOWED_TOP_LEVEL_ZIPS:
            violations.append(f"Unapproved top-level ZIP: {rp}")
    return violations


def find_duplicate_or_unapproved_run_scripts() -> list[str]:
    run_like: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rp = rel(path)
        low = rp.lower()
        if low.startswith(".git/") or low.startswith(".venv/"):
            continue
        if low.startswith("tests/") or "/tests/" in low:
            continue
        if low.endswith(".bat") or low.endswith(".py"):
            if any(token in low for token in ("run", "boot", "setup")):
                run_like.append(path)

    violations: list[str] = []
    for path in sorted(run_like):
        rp = rel(path)
        if rp not in ALLOWED_RUN_SCRIPTS:
            violations.append(f"Unapproved run/boot/test script: {rp}")

    return violations


def find_duplicate_boot_stacks() -> list[str]:
    # A "boot stack" is counted when both setup+run entrypoints exist within a folder.
    stack_candidates: list[tuple[str, str]] = []

    for folder in {p.parent for p in ROOT.rglob("*.bat")}:
        rel_folder = rel(folder) if folder != ROOT else "."
        bat_names = {p.name.lower() for p in folder.glob("*.bat")}
        has_setup = any("setup" in name for name in bat_names)
        has_run = any("run" in name for name in bat_names)
        if has_setup and has_run:
            stack_candidates.append((rel_folder, ", ".join(sorted(bat_names))))

    # Known stacks are the root and _BAT folder.
    allowed_stack_folders = {".", "_BAT"}
    violations: list[str] = []

    for folder, names in sorted(stack_candidates):
        if folder not in allowed_stack_folders:
            violations.append(f"Duplicate boot stack folder detected: {folder} ({names})")

    # Ensure allowed stack definitions are still intact.
    existing = {rel(p) for p in ROOT.rglob("*") if p.is_file()}
    for stack_name, required in BOOT_STACK_GROUPS.items():
        missing = sorted(required - existing)
        if missing:
            violations.append(f"Required boot stack files missing for {stack_name}: {', '.join(missing)}")

    return violations


def main() -> int:
    checks = [
        find_nested_or_unapproved_zips,
        find_duplicate_or_unapproved_run_scripts,
        find_duplicate_boot_stacks,
    ]

    violations: list[str] = []
    for check in checks:
        violations.extend(check())

    if violations:
        print("[check_structure] FAIL")
        for item in violations:
            print(f" - {item}")
        return 1

    print("[check_structure] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
