# Record schemas and CLI

All commands emit JSON on stdout and actionable errors on stderr (exit 2). Use `--vault` before the command. Python 3.10+; SQLite and standard library only. Limits keep incoming batches bounded: 32 MiB/session file, 1 MiB/line, 24,000 characters/message, 40 inbox records by default (max 200). Truncated messages carry `truncated: true`; do not infer missing context. A trailing JSONL fragment waits until its newline is written.

## Evidence

`inbox` returns `{evidence: [...]}`. Each record has:

```json
{
  "id": "64-character-sha256",
  "session": "24-character-normalized-session-id",
  "source": "/private/export/session.jsonl",
  "line": 12,
  "project": "/authorized/project",
  "role": "user",
  "text": "Before merging, check duplicate keys and record total revenue.",
  "truncated": false,
  "timestamp": "2026-09-01T09:00:00Z",
  "imported": "2026-09-02T09:00:00+00:00"
}
```

The source path is local provenance. The public repository must never contain a real record. `raw/<id>.json` is an immutable **redacted visible-message snapshot**, not a full verbatim Codex trace. The original session file remains untouched. A repeated import returns zero new evidence. Identical session copies with the same line content deduplicate; distinct authored statements remain separate. System/developer messages, tools, reasoning, images, and encrypted reasoning are not imported in v0.1.

## Pattern input (`learn --file pattern.json`)

```json
{
  "id": "join-reconciliation",
  "title": "Verify data joins with aggregate checks",
  "capability": "Data reconciliation",
  "claim": "The employee explicitly requests reconciliation of joins.",
  "when": "Joining tables with additive amount columns",
  "procedure": [
    "Record input row counts, duplicate keys, and aggregate totals.",
    "Join using the declared key cardinality.",
    "Reconcile output totals, accounting for intentionally filtered rows."
  ],
  "avoid": ["One-to-many joins require an explicit expected multiplicity."],
  "evidence": [
    {"id": "REAL_IMPORTED_ID", "quote": "EXACT_SUBSTRING_OF_IMPORTED_TEXT", "supports": "human_method"}
  ]
}
```

Identifiers use lowercase ASCII letters, digits and hyphens (max 64). A pattern needs nonempty title, capability, claim, when, procedure, and at least one valid reference. `avoid` is optional. Procedure and avoid lists allow at most 40 items. A quote must be an exact substring of the imported, redacted text. `human_method` must point to a user role. Attribution, revision, status, and confirmation are computed by the CLI; input fields cannot override them.

Updating an existing id merges evidence and saves a new revision. Existing evidence cannot be silently removed. An unchanged note is a no-op. New revisions clear employee confirmation. Counterexamples make a pattern disputed. Retirement is durable; new evidence cannot silently reactivate a retired method. Resolve a broad disputed claim by creating a context-bounded successor and retiring the old one with a reason referencing that successor.

## Commands

| Command | Effect |
| --- | --- |
| `init --owner ALIAS --source DIR --project DIR` | Create a private vault with explicit scope. Repeat source/project flags. |
| `scope --source DIR --project DIR` | Replace future-import scope, retain historical evidence. |
| `ingest [--file FILE]` | Import changed, allowlisted Codex session exports. |
| `inbox --limit 40` | Return unprocessed evidence in import order. |
| `ack ID ... --reason TEXT` | Mark only reviewed records processed, preserving snapshots. |
| `learn --file FILE` | Validate and merge a pattern. |
| `confirm PATTERN --note TEXT` | Record explicit employee confirmation of an active human method. |
| `retire PATTERN --reason TEXT` | Stop compiling an obsolete pattern, retain history. |
| `propose --skill NAME --pattern ID ...` | Compile 1–8 related active patterns into a versioned candidate. |
| `evaluate --file FILE` | Validate a paired outcome report and record accept/reject. |
| `promote PROPOSAL` | Activate a current accepted candidate in the vault. |
| `rollback SKILL --to PROPOSAL` | Restore a previously activated version; preserve wiki. |
| `export SKILL --to DIR` | Copy active SKILL.md only, refusing existing targets. |
| `profile` / `status` | Read method evidence or pipeline counts. |
| `report` | Generate a private, offline HTML report. |
| `render` | Rebuild wiki and active-skill views from SQLite. |
| `watch --interval 60` / `watch --once` | Incremental import loop / one import pass. |

The database serializes writers. Markdown views are derived files: direct Markdown edits are replaced by `render`. Candidate content must remain identical to its hash; create a new pattern revision/proposal to change it. Internal vault symlinks are rejected. Back up the whole private vault when no command is running.
