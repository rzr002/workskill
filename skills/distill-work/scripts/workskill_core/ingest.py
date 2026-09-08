"""Import public-facing Codex messages from explicitly allowlisted local exports."""
import json
from pathlib import Path
import re

from .storage import digest, encode, inside, require, now, safe_path

MAX_FILE = 32 * 1024 * 1024
MAX_LINE = 1024 * 1024
MAX_TEXT = 24000


def redact(value):
    value = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----", "[REDACTED_PRIVATE_KEY]", value)
    value = re.sub(r"\b(?:gh[pousr]_[A-Za-z0-9_]{16,}|github_pat_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]{16,}|AKIA[A-Z0-9]{16})\b", "[REDACTED_TOKEN]", value)
    value = re.sub(r"(?i)(\b(?:api[_-]?key|password|secret|token|authorization)\b[\"']?\s*[:=]\s*)(?:Bearer\s+)?(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)", r"\1[REDACTED_SECRET]", value)
    value = re.sub(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]", value)
    return value


def message(row):
    payload = row.get("payload", {})
    if not isinstance(payload, dict):
        return None
    if row.get("type") == "response_item" and payload.get("type") == "message":
        role = payload.get("role")
        if role not in ("user", "assistant") or payload.get("channel") in ("analysis", "justify", "confidence"):
            return None
        content = payload.get("content", [])
        if not isinstance(content, list):
            return None
        parts = [p["text"] for p in content if isinstance(p, dict) and isinstance(p.get("text"), str)]
        value = "\n".join(parts)
    elif row.get("type") == "event_msg" and payload.get("type") in ("user_message", "agent_message"):
        role = "user" if payload["type"] == "user_message" else "assistant"
        value = payload.get("message", "")
    else:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    if role == "user" and value.lstrip().startswith(("<environment_context>", "<permissions", "# AGENTS.md", "<system_reminder>")):
        return None
    return role, value


def ingest(store, selected=None):
    roots = [Path(p).resolve() for p in store.config["sources"]]
    projects = [Path(p).resolve() for p in store.config["projects"]]
    if selected:
        candidate = Path(selected).expanduser()
        require(candidate.is_file() and not candidate.is_symlink() and inside(candidate.resolve(), roots), "File is outside the authorized source directories or is a symlink.")
        paths = [candidate]
    else:
        paths = sorted({p for root in roots for p in root.rglob("*.jsonl") if p.is_file()})
    imported, skipped, warnings = 0, 0, []
    for path in paths:
        if path.is_symlink() or not inside(path.resolve(), roots):
            skipped += 1
            continue
        stat = path.stat()
        if stat.st_size > MAX_FILE:
            warnings.append({"file": str(path), "reason": "file exceeds 32 MiB; export a smaller selection"})
            continue
        source_key = digest(str(path.resolve()))
        fingerprint = {"mtime_ns": stat.st_mtime_ns, "size": stat.st_size}
        if store.get("imports", source_key, False) == fingerprint:
            continue
        rows, incomplete = [], False
        with path.open("rb") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.endswith(b"\n"):
                    incomplete = True
                    break
                if len(line) > MAX_LINE:
                    warnings.append({"file": str(path), "line": line_number, "reason": "line exceeds 1 MiB"})
                    continue
                try:
                    row = json.loads(line)
                    if isinstance(row, dict):
                        rows.append((line_number, row))
                except (ValueError, UnicodeDecodeError):
                    warnings.append({"file": str(path), "line": line_number, "reason": "malformed JSON"})
        if not rows or rows[0][1].get("type") != "session_meta":
            warnings.append({"file": str(path), "reason": "missing Codex session_meta header"})
            continue
        meta = rows[0][1].get("payload", {})
        if not isinstance(meta, dict) or not isinstance(meta.get("id"), str) or not isinstance(meta.get("cwd"), str):
            warnings.append({"file": str(path), "reason": "invalid session id or cwd"})
            continue
        session = digest(meta["id"])[:24]
        cwd = Path(meta["cwd"]).expanduser().resolve()
        # Codex may emit the same visible message in both event_msg and response_item.
        response_messages = {message(r) for _, r in rows if r.get("type") == "response_item" and message(r)}
        for line_number, row in rows[1:]:
            if row.get("type") == "turn_context":
                payload = row.get("payload", {})
                if isinstance(payload, dict) and isinstance(payload.get("cwd"), str):
                    cwd = Path(payload["cwd"]).expanduser().resolve()
            if not inside(cwd, projects):
                continue
            item = message(row)
            if not item or (row.get("type") == "event_msg" and item in response_messages):
                continue
            role, value = item
            cleaned = redact(value)
            truncated = len(cleaned) > MAX_TEXT
            cleaned = cleaned[:MAX_TEXT]
            # Source identity + line + original text hash remain stable across append/re-import.
            key = digest(encode([session, line_number, role, digest(value)]))
            if store.get("evidence", key, False):
                continue
            record = {"id": key, "session": session, "source": str(path.resolve()), "line": line_number,
                      "project": str(cwd), "role": role, "text": cleaned, "truncated": truncated,
                      "timestamp": row.get("timestamp"), "imported": now()}
            snapshot = safe_path(store.root, "raw", key + ".json")
            if snapshot.exists():
                prior = json.loads(snapshot.read_text(encoding="utf-8"))
                require(isinstance(prior, dict) and all(prior.get(k) == v for k, v in record.items() if k != "imported"),
                        "Uncommitted raw snapshot differs from source evidence; inspect it before continuing.")
                record["imported"] = prior["imported"]
            store.write(f"raw/{key}.json", encode(record) + "\n", immutable=True)
            store.put("evidence", key, record)
            imported += 1
        if not incomplete:
            store.put("imports", source_key, fingerprint)
    if imported:
        store.event("ingest", {"imported": imported})
    return {"imported": imported, "skipped_files": skipped, "warnings": warnings}
