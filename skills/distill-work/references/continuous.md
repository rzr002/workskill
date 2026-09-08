# Continuous operation

There are two separate running components:

- **Import watcher:** `watch` polls authorized session directories and adds new visible-message evidence. This runs locally and calls no model. Stop with Ctrl-C. `watch --once` is suitable for a scheduler. It cannot create semantic patterns on its own.
- **Distillation cycle:** a hosting Codex task loads `$distill-work`, reviews the inbox, updates the wiki, creates candidates, and evaluates when a valid evaluator and tasks are available. This uses the model configured in that Codex task.

A complete continuously updated product needs recurring distillation cycles. Do not imply that installing the skill or running the importer alone provides them.

## Codex app automation

When the user requests daily/hourly/ongoing updates, discover the app's automation tool and use its current schema. Prefer a heartbeat attached to the task unless the user requests a standalone job. Inspect existing matching automations before creating duplicates. The prompt must include the absolute skill path and private vault path and preserve the established import scope.

Use cohesive natural language, for example:

> Use $distill-work at /absolute/path/to/skills/distill-work/SKILL.md to maintain my personal work knowledge at /absolute/private/vault. Keep the existing owner and source/project allowlists. Import new work evidence and process at most 40 inbox records per run. Consolidate substantive employee-authored methods with exact evidence and preserve AI-only outcomes separately. Keep contradicted patterns disputed. Inspect prior rejected proposals before compiling a new candidate. Use real paired held-out evaluations when available; otherwise leave candidates pending. Promote only accepted current candidates within this vault. Do not export, install, or share generated skills unless separately requested. Refresh the private report when something changes. Stay quiet if there is no meaningful change; notify me about newly supported methods, validation outcomes, failures, or a required decision.

Use a schedule supplied by the user or a sensible local-time default for a general daily request. Report the actual configured schedule only after the tool confirms it. If scheduling is unavailable, provide a saved prompt and explain that it still needs a host scheduler. Don't secretly start a daemon or install a system cron job.

## Operation over longer periods

Process bounded batches so each cycle fits the hosting model's context. Acknowledge only reviewed evidence. Merge semantically duplicate patterns and retire obsolete ones with reasons; do not erase raw evidence or rejected proposal history. Use the wiki index to select relevant pattern pages instead of loading the whole vault. Refresh employee confirmation when a material revision changes the method.

The current importer stats all configured JSONL files but reparses only changed files. This is appropriate for personal vaults; a large enterprise deployment would need indexed event intake, authenticated actor identity, retention administration, and tenant isolation. Separate vaults are local organization, not a multi-tenant access-control system.

Source/project allowlists constrain future importing. Narrowing them preserves historical records by design. The vault directory contains the complete local state and has a deny-all `.gitignore`; users control backups and deletion. Do not upload it as part of distributing WorkSkill's source code.
