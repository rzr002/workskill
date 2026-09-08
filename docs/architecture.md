# WorkSkill 0.1 architecture

WorkSkill ships one portable skill and a deterministic Python data engine. The hosting agent is the semantic analyst; this design reuses the user's Codex installation and model configuration. Installing the skill requires no API keys or daemon. A recurring hosting task provides ongoing analysis; the CLI watcher provides only import.

## Knowledge flow

1. Explicitly scoped Codex exports produce redacted, immutable visible-message snapshots.
2. The hosting agent proposes structured methods with exact source quotes. The engine validates roles and quotes, merges evidence, computes attribution, and preserves revisions.
3. Related active patterns compile into a candidate Skill and a source-mapping PURPOSE file. Candidate bytes and baseline versions are bound by hashes and ids.
4. A real external evaluator or an authorized human supplies paired held-out outcomes. The engine validates the report and gates acceptance. It is not an evaluator itself.
5. Promotion rechecks current patterns, candidate bytes, and baseline identity, then switches the active pointer. Rejection changes no active pointer. Rollback only targets a previously promoted version; wiki history remains.

## Employee-method attribution

The importer knows the role of a message, not an authenticated human identity. Each vault therefore requires an explicitly selected personal owner and scope. A substantive user statement can support a human method; a task request alone cannot. A host agent is responsible for this semantic distinction. AI outcomes are useful experience but do not imply the employee performed the method independently.

Attribution is frequency-based (`human_observed`, `human_repeated`, `agent_only`), with explicit employee confirmation recorded separately. There is no numeric competence score. A counterexample disputes a pattern and blocks new compilation. Retirement preserves records and stops reuse for new exports. Already exported skills cannot be revoked automatically.

## Durability and operations

SQLite serializes command writers with an immediate transaction and a bounded busy timeout. Tables hold evidence, patterns, revisions, proposals, evaluations, active pointers, acknowledgments, file fingerprints, and an event journal. Raw snapshots are content-addressed. Files are written using private temporary files followed by atomic replacement. A vault uses owner-only POSIX permissions; Windows additionally relies on the user's directory ACLs.

SQLite is authoritative. Markdown views are rebuilt from it. Filesystem views and SQL commit are not one cross-resource atomic transaction: an interrupted command may leave orphan candidate/evaluation files or stale views. Restoring database-backed views with `render` repairs views; an orphan candidate cannot be promoted because no committed proposal exists. Evidence can be re-imported idempotently. Back up a quiescent entire vault; do not back up only Markdown.

The importer reparses only files whose size or nanosecond modification time changed. It waits for complete JSONL lines, rejects oversized files, filters session and per-turn working directories, avoids symlink escapes, and supports Codex's `event_msg` and `response_item` message encodings. Copied fork histories and duplicated exports may still require semantic deduplication; different session ids alone do not prove independent human learning.

## Adaptation of WikiSkill

The conceptual source is [Tang et al., WikiSkill (2026)](https://arxiv.org/abs/2608.27454). WorkSkill retains the separation of evidence, persistent knowledge, and procedural skills; it also retains rejected proposal history. It adds human/agent attribution and an employee-controlled local interface.

This implementation stores redacted visible messages instead of full trajectories. It compiles host-authored pattern procedures without running its own optimization models. It uses caller-submitted evaluations and a stricter no-per-case-regression gate. The software tests establish deterministic workflow behavior only. No original paper code or performance claims are included.

## Known limits

- No independently authenticated employee identity, multi-tenant access controls, SSO, or team administration.
- No automatic scoring harness for arbitrary work. Reports can be dishonest or biased; the gate cannot establish their truth.
- Heuristic redaction misses some secrets and commercial context. The hosting model sees any records it reads.
- No hidden reasoning, tool outputs, attachments, or other app connectors in the v0.1 importer.
- No autonomous semantic daemon. Ongoing distillation requires the hosting platform's scheduler.
- No automatic deletion/retention policy or compaction of historical evidence; the user controls the local vault.
- Long-lived skill libraries require relevant retrieval by the host. A full production enterprise deployment needs further evaluation and operational work.
