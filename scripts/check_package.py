#!/usr/bin/env python3
"""Dependency-free packaging preflight; complements official Codex validators."""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def check():
    manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "workskill"
    assert re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"])
    assert manifest["skills"] == "./skills/"
    assert manifest["author"]["name"] and manifest["interface"]["displayName"]
    assert manifest["interface"]["category"] == "Productivity"
    skill = ROOT / "skills/distill-work"
    body = (skill / "SKILL.md").read_text(encoding="utf-8")
    assert body.startswith("---\n") and "\nname: distill-work\n" in body
    frontmatter = body.split("---", 2)[1]
    description = next(line.removeprefix("description: ") for line in frontmatter.splitlines() if line.startswith("description: "))
    assert 20 < len(json.loads(description)) < 1024
    metadata = (skill / "agents/openai.yaml").read_text(encoding="utf-8")
    assert "$distill-work" in metadata
    assert (skill / "scripts/workskill.py").is_file()
    assert (skill / "scripts/workskill_core/cli.py").is_file()
    checked = 0
    for directory in (skill, ROOT / "docs"):
        for path in directory.rglob("*.md"):
            content = path.read_text(encoding="utf-8")
            assert "[TODO:" not in content, f"Unfinished scaffold: {path}"
            for link in re.findall(r"\]\(([^)]+)\)", content):
                if "://" in link or link.startswith("#"):
                    continue
                target = (path.parent / link.split("#")[0]).resolve()
                assert target.is_relative_to(ROOT), f"Link outside package: {path}: {link}"
                assert target.exists(), f"Missing reference: {path}: {link}"
                checked += 1
    version_file = skill / "scripts/workskill_core/__init__.py"
    assert f'__version__ = "{manifest["version"]}"' in version_file.read_text(encoding="utf-8")
    print(f"Package checks passed; {checked} local references resolve; version {manifest['version']}.")


if __name__ == "__main__":
    try:
        check()
    except (AssertionError, OSError, ValueError, KeyError, StopIteration) as error:
        print(f"Package check failed: {error}", file=sys.stderr)
        sys.exit(1)
