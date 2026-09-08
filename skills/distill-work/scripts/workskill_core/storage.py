"""SQLite is authoritative; Markdown files are rebuildable views."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile


class WorkSkillError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise WorkSkillError(message)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def slug(value):
    require(isinstance(value, str) and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value)
            and len(value) <= 64, "Use a lowercase identifier of at most 64 letters, digits and hyphens.")
    return value


def text(value, field, maximum=12000):
    require(isinstance(value, str) and 0 < len(value.strip()) <= maximum, f"{field} must be nonempty text (max {maximum}).")
    require("\x00" not in value, f"{field} contains a NUL byte.")
    return value.strip()


def inside(path, roots):
    return any(path == root or root in path.parents for root in roots)


def safe_path(root, *parts):
    path = root.joinpath(*parts)
    require(inside(path.resolve(), [root.resolve()]), "Path escapes the vault.")
    for item in [path, *path.parents]:
        if item == root.parent:
            break
        require(not item.is_symlink(), "Symlinks are not allowed inside the vault.")
    return path


def atomic_write(path, content, immutable=False):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(not path.is_symlink(), "Refusing to replace a symlink.")
    if immutable and path.exists():
        require(path.read_text(encoding="utf-8") == content, "Immutable evidence was modified; restore it before continuing.")
        return
    fd, temp = tempfile.mkstemp(prefix=".workskill-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class Store:
    @staticmethod
    def initialize(root, owner, sources, projects):
        require(not root.is_symlink(), "Vault must not be a symlink.")
        root = root.expanduser().resolve()
        require(not root.exists(), "Vault already exists; use a new private directory.")
        source_paths = [Path(p).expanduser().resolve() for p in sources]
        project_paths = [Path(p).expanduser().resolve() for p in projects]
        require(source_paths and project_paths, "Explicit source and project allowlists are required.")
        for p in source_paths + project_paths:
            require(p.is_dir() and p != Path(p.anchor), "Allowlist entries must be existing, specific directories.")
        config = {"schema": 1, "owner": text(owner, "owner", 100), "created": now(),
                  "sources": [str(p) for p in source_paths], "projects": [str(p) for p in project_paths]}
        root.mkdir(parents=True, mode=0o700)
        root.chmod(0o700)
        atomic_write(root / "config.json", encode(config) + "\n")
        atomic_write(root / ".gitignore", "*\n!.gitignore\n")
        for name in ("raw", "wiki/patterns", "candidates", "skills", "evaluations"):
            (root / name).mkdir(parents=True, exist_ok=True, mode=0o700)
        return {"vault": str(root), "owner": config["owner"]}

    def __init__(self, root):
        require(not root.is_symlink(), "Vault must not be a symlink.")
        self.root = root.expanduser().resolve()
        config_path = safe_path(self.root, "config.json")
        require(config_path.is_file(), "Vault not initialized; run init with explicit source and project paths.")
        self.config = json.loads(config_path.read_text(encoding="utf-8"))
        require(self.config.get("schema") == 1, "Unsupported vault schema.")
        db = safe_path(self.root, "workskill.sqlite3")
        for suffix in ("-wal", "-shm", "-journal"):
            safe_path(self.root, "workskill.sqlite3" + suffix)
        self.db = sqlite3.connect(db, timeout=15)
        db.chmod(0o600)
        for table in ("evidence", "patterns", "proposals", "evaluations", "processed", "imports", "active"):
            self.db.execute(f"CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS revisions (id TEXT, revision INTEGER, body TEXT NOT NULL, PRIMARY KEY(id, revision))")
        self.db.execute("CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, kind TEXT, body TEXT, created TEXT)")
        self.db.commit()
        self.db.execute("BEGIN IMMEDIATE")

    def get(self, table, key, required=True):
        row = self.db.execute(f"SELECT body FROM {table} WHERE id = ?", (key,)).fetchone()
        require(row is not None or not required, f"Unknown {table} identifier: {key}")
        return json.loads(row[0]) if row else None

    def all(self, table):
        return [json.loads(row[0]) for row in self.db.execute(f"SELECT body FROM {table} ORDER BY id")]

    def put(self, table, key, value):
        self.db.execute(f"INSERT INTO {table} VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET body=excluded.body", (key, encode(value)))

    def event(self, kind, body):
        self.db.execute("INSERT INTO events(kind, body, created) VALUES (?, ?, ?)", (kind, encode(body), now()))

    def write(self, relative, content, immutable=False):
        atomic_write(safe_path(self.root, relative), content, immutable)

    def finish(self, success):
        try:
            self.db.commit() if success else self.db.rollback()
        finally:
            self.db.close()
