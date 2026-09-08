#!/usr/bin/env python3
"""Install the portable skill without changing user configuration or existing skills."""
import argparse
import json
from pathlib import Path
import shutil
import sys


def main():
    parser = argparse.ArgumentParser(description="Install WorkSkill's self-contained Codex skill")
    parser.add_argument("--dest", type=Path, default=Path.home() / ".codex/skills", help="Skills parent directory")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1] / "skills/distill-work"
    target = args.dest.expanduser() / "distill-work"
    if target.exists() or target.is_symlink():
        print(f"Refusing to overwrite existing skill: {target}. Move the old version aside after reviewing local changes.", file=sys.stderr)
        return 2
    if not args.dry_run:
        shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    print(json.dumps({"path": str(target.resolve()), "dry_run": args.dry_run, "next": "Open a new Codex task and use $distill-work."}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
