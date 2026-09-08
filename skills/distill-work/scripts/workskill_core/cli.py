"""Machine-readable CLI. No network requests and no model credentials required."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
import time

from . import __version__, engine
from .ingest import ingest
from .storage import Store, WorkSkillError, require


def parser():
    p = argparse.ArgumentParser(description="WorkSkill — distill work evidence into a personal wiki and validated skills")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--vault", type=Path, default=Path.home() / ".local/share/workskill")
    commands = p.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create a private vault with explicit import scope")
    init.add_argument("--owner", required=True)
    init.add_argument("--source", action="append", required=True)
    init.add_argument("--project", action="append", required=True)
    scope = commands.add_parser("scope", help="Replace future-import allowlists without deleting existing evidence")
    scope.add_argument("--source", action="append", required=True)
    scope.add_argument("--project", action="append", required=True)
    imp = commands.add_parser("ingest", help="Incrementally import allowlisted Codex JSONL sessions")
    imp.add_argument("--file")
    incoming = commands.add_parser("inbox", help="Read a bounded batch of unprocessed evidence")
    incoming.add_argument("--limit", type=int, default=40)
    ack = commands.add_parser("ack", help="Mark reviewed evidence processed without deleting it")
    ack.add_argument("ids", nargs="+")
    ack.add_argument("--reason", required=True)
    for name in ("learn", "evaluate"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--file", type=Path, required=True)
    confirm = commands.add_parser("confirm", help="Record explicit employee confirmation")
    confirm.add_argument("pattern")
    confirm.add_argument("--note", required=True)
    retire = commands.add_parser("retire", help="Retire outdated patterns while retaining history")
    retire.add_argument("pattern")
    retire.add_argument("--reason", required=True)
    propose = commands.add_parser("propose", help="Compile candidate SKILL.md from current wiki patterns")
    propose.add_argument("--skill", required=True)
    propose.add_argument("--pattern", action="append", required=True)
    promote = commands.add_parser("promote", help="Activate an accepted candidate in the vault")
    promote.add_argument("proposal")
    rollback = commands.add_parser("rollback", help="Restore an earlier activated skill version; retain wiki")
    rollback.add_argument("skill")
    rollback.add_argument("--to", required=True)
    export = commands.add_parser("export", help="Export only active SKILL.md, without private provenance")
    export.add_argument("skill")
    export.add_argument("--to", required=True)
    for name in ("status", "profile", "render", "report"):
        commands.add_parser(name)
    watch = commands.add_parser("watch", help="Poll for new evidence; semantic distillation runs in the hosting agent")
    watch.add_argument("--once", action="store_true")
    watch.add_argument("--interval", type=float, default=60)
    return p


def dispatch(store, args):
    c = args.command
    if c == "ingest":
        return ingest(store, args.file)
    if c == "scope":
        return engine.scope(store, args.source, args.project)
    if c == "report":
        from .report import report
        return report(store)
    if c == "watch":
        require(1 <= args.interval <= 86400, "Watch interval must be between 1 and 86400 seconds.")
        return ingest(store)
    if c == "inbox":
        return engine.inbox(store, args.limit)
    if c == "ack":
        return engine.acknowledge(store, args.ids, args.reason)
    if c in ("learn", "evaluate"):
        require(args.file.stat().st_size <= 1024 * 1024, "Input JSON exceeds 1 MiB.")
        data = json.loads(args.file.read_text(encoding="utf-8"))
        return getattr(engine, c)(store, data)
    if c == "confirm":
        return engine.confirm(store, args.pattern, args.note)
    if c == "retire":
        return engine.retire(store, args.pattern, args.reason)
    if c == "propose":
        return engine.propose(store, args.skill, args.pattern)
    if c == "promote":
        return engine.promote(store, args.proposal)
    if c == "rollback":
        return engine.rollback(store, args.skill, args.to)
    if c == "export":
        return engine.export_skill(store, args.skill, args.to)
    return getattr(engine, c)(store)


def main():
    args = parser().parse_args()
    try:
        if args.command == "init":
            result = Store.initialize(args.vault, args.owner, args.source, args.project)
            store = Store(args.vault)
            try:
                engine.render(store)
                store.finish(True)
            except Exception:
                store.finish(False)
                raise
            print(json.dumps(result, sort_keys=True, allow_nan=False))
            return
        while True:
            store = Store(args.vault)
            try:
                result = dispatch(store, args)
                if args.command not in ("status", "profile", "inbox", "render"):
                    engine.render(store)
                store.finish(True)
            except Exception:
                store.finish(False)
                raise
            print(json.dumps(result, sort_keys=True, allow_nan=False), flush=True)
            if args.command != "watch" or args.once:
                break
            time.sleep(args.interval)
    except (WorkSkillError, OSError, ValueError, sqlite3.Error) as error:
        print(f"workskill: {error}", file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
