"""Evidence validation, pattern consolidation, skill compilation and evaluation gating."""
import difflib
import json
import math
from pathlib import Path
import uuid

from .ingest import redact
from .storage import atomic_write, digest, encode, now, require, safe_path, slug, text


def text_list(value, field, nonempty=False):
    require(isinstance(value, list) and len(value) <= 40 and (value or not nonempty), f"{field} must be a list of at most 40 text items.")
    return [text(item, field, 3000) for item in value]


def inbox(store, limit=40):
    require(1 <= limit <= 200, "limit must be between 1 and 200.")
    rows = store.db.execute("SELECT e.body FROM evidence e LEFT JOIN processed p ON e.id=p.id WHERE p.id IS NULL ORDER BY e.rowid LIMIT ?", (limit,))
    return {"evidence": [json.loads(row[0]) for row in rows], "limit": limit}


def acknowledge(store, ids, reason):
    reason = text(reason, "reason", 1000)
    for key in ids:
        store.get("evidence", key)
        store.put("processed", key, {"id": key, "reason": reason, "at": now()})
    store.event("acknowledge", {"ids": ids, "reason": reason})
    return {"acknowledged": len(ids)}


def attribution(store, refs):
    human = [store.get("evidence", ref["id"]) for ref in refs if ref["supports"] == "human_method"]
    sessions = {item["session"] for item in human}
    # Repeated copies of a single instruction are not independent methods.
    distinct = {item["text"] for item in human}
    return "human_repeated" if len(sessions) >= 2 and len(distinct) >= 2 else "human_observed" if human else "agent_only"


def learn(store, data):
    require(isinstance(data, dict), "Pattern must be a JSON object.")
    key = slug(data.get("id"))
    old = store.get("patterns", key, False)
    pattern = {field: text(data.get(field), field, 4000) for field in ("title", "capability", "claim", "when")}
    pattern.update(id=key, procedure=text_list(data.get("procedure"), "procedure", True),
                   avoid=text_list(data.get("avoid", []), "avoid"))
    require(redact(encode(pattern)) == encode(pattern), "Pattern contains a likely secret or email; generalize it before saving.")
    refs = data.get("evidence")
    require(isinstance(refs, list) and 0 < len(refs) <= 100, "Supply 1–100 source evidence references.")
    merged = {(r["id"], r["supports"], r["quote"]): r for r in old["evidence"]} if old else {}
    for ref in refs:
        require(isinstance(ref, dict), "Each evidence reference must be an object.")
        evidence = store.get("evidence", text(ref.get("id"), "evidence.id", 64))
        quote = text(ref.get("quote"), "evidence.quote", 4000)
        require(quote in evidence["text"], "Evidence quote does not occur in the imported text.")
        support = ref.get("supports")
        require(support in ("human_method", "agent_outcome", "counterexample"), "Invalid evidence support type.")
        require(support != "human_method" or evidence["role"] == "user", "Human methods must cite user-authored evidence.")
        merged[(evidence["id"], support, quote)] = {"id": evidence["id"], "quote": quote, "supports": support}
    pattern["evidence"] = list(merged.values())
    pattern["status"] = "disputed" if any(r["supports"] == "counterexample" for r in merged.values()) else "active"
    if old and old["status"] == "retired":
        pattern["status"] = "retired"
    pattern["attribution"] = attribution(store, pattern["evidence"])
    # Repeated scheduled runs with identical findings do not manufacture revisions.
    if old and all(pattern[k] == old.get(k) for k in pattern):
        return old
    pattern.update(revision=old["revision"] + 1 if old else 1, updated=now(),
                   confirmed=False, confirmation=None)
    store.put("patterns", key, pattern)
    store.db.execute("INSERT INTO revisions VALUES (?, ?, ?)", (key, pattern["revision"], encode(pattern)))
    store.event("learn", {"pattern": key, "revision": pattern["revision"]})
    return pattern


def confirm(store, key, note):
    pattern = store.get("patterns", slug(key))
    require(pattern["attribution"] != "agent_only", "An agent-only pattern cannot become an employee claim by confirmation alone; add a quoted employee explanation.")
    require(pattern["status"] == "active", "Disputed or retired patterns cannot be confirmed.")
    pattern.update(confirmed=True, confirmation=text(note, "confirmation", 2000), updated=now(), revision=pattern["revision"] + 1)
    store.put("patterns", key, pattern)
    store.db.execute("INSERT INTO revisions VALUES (?, ?, ?)", (key, pattern["revision"], encode(pattern)))
    store.event("confirm", {"pattern": key, "note": note})
    return pattern


def retire(store, key, reason):
    pattern = store.get("patterns", slug(key))
    pattern.update(status="retired", retired_reason=text(reason, "reason", 2000), updated=now(), revision=pattern["revision"] + 1)
    store.put("patterns", key, pattern)
    store.db.execute("INSERT INTO revisions VALUES (?, ?, ?)", (key, pattern["revision"], encode(pattern)))
    store.event("retire", {"pattern": key, "reason": reason})
    return pattern


def compile_skill(name, patterns):
    description = "Use when " + "; ".join(p["when"] for p in patterns)
    # JSON-quoted strings are valid YAML scalars and cannot inject frontmatter fields.
    result = ["---", f"name: {name}", "description: " + json.dumps(description[:900], ensure_ascii=False), "---", "", f"# {name}", ""]
    for p in patterns:
        result.extend([f"## {p['title']}", "", p["when"], ""])
        result.extend(f"{i}. {step}" for i, step in enumerate(p["procedure"], 1))
        if p["avoid"]:
            result.extend(["", "Applicability limits:", ""] + [f"- {limit}" for limit in p["avoid"]])
        result.append("")
    return "\n".join(result)


def propose(store, name, keys):
    name = slug(name)
    require(1 <= len(set(keys)) <= 8, "Compile 1–8 distinct, related patterns at a time.")
    patterns = [store.get("patterns", slug(key)) for key in dict.fromkeys(keys)]
    require(all(p["status"] == "active" for p in patterns), "Disputed or retired patterns cannot be compiled.")
    content = compile_skill(name, patterns)
    active = store.get("active", name, False)
    base = store.get("proposals", active["proposal"]) if active else None
    require(not base or base["sha256"] != digest(content), "Candidate is identical to the active skill.")
    revisions = {p["id"]: p["revision"] for p in patterns}
    for previous in store.all("proposals"):
        if previous["skill"] == name and previous["sha256"] == digest(content) and previous["patterns"] == revisions and previous["base"] == (base["id"] if base else None):
            return previous
    key = uuid.uuid4().hex
    refs = [r for p in patterns for r in p["evidence"]]
    proposal = {"id": key, "skill": name, "sha256": digest(content), "content": content,
                "patterns": revisions, "training_sessions": sorted({store.get("evidence", r["id"])["session"] for r in refs}),
                "base": base["id"] if base else None, "created": now(), "decision": "pending"}
    proposal["diff"] = "".join(difflib.unified_diff((base["content"] if base else "").splitlines(True), content.splitlines(True), fromfile="active/SKILL.md", tofile="candidate/SKILL.md"))
    store.write(f"candidates/{key}/SKILL.md", content, immutable=True)
    store.write(f"candidates/{key}/PURPOSE.md", purpose(proposal), immutable=True)
    store.write(f"candidates/{key}/proposal.json", encode(proposal) + "\n", immutable=True)
    store.put("proposals", key, proposal)
    store.event("propose", {"id": key, "skill": name, "patterns": revisions})
    return proposal


def purpose(proposal):
    return "# Private provenance\n\n" + "\n".join(f"- {key}, revision {version}" for key, version in proposal["patterns"].items()) + f"\n\nProposal: {proposal['id']}\nSHA-256: {proposal['sha256']}\n"


def check_candidate(store, proposal):
    content = safe_path(store.root, "candidates", proposal["id"], "SKILL.md").read_text(encoding="utf-8")
    require(digest(content) == proposal["sha256"], "Candidate bytes changed after proposal creation.")
    for key, revision in proposal["patterns"].items():
        pattern = store.get("patterns", key)
        require(pattern["revision"] == revision and pattern["status"] == "active", "Pattern changed or was retired; create a fresh proposal.")
    active = store.get("active", proposal["skill"], False)
    current = active["proposal"] if active else None
    require(current == proposal["base"], "Active baseline changed; create and evaluate a fresh proposal.")


def evaluate(store, report):
    require(isinstance(report, dict), "Evaluation must be a JSON object.")
    proposal = store.get("proposals", text(report.get("proposal"), "proposal", 64))
    require(proposal["decision"] == "pending", "This proposal already has a decision; new evidence requires a new proposal.")
    check_candidate(store, proposal)
    require(report.get("candidate_sha256") == proposal["sha256"], "Evaluation hash does not match this candidate.")
    for field in ("evaluator", "environment"):
        text(report.get(field), field, 1000)
    artifact = Path(text(report.get("artifact"), "artifact", 4000)).expanduser()
    require(artifact.is_file() and artifact.stat().st_size <= 8 * 1024 * 1024, "Supply an existing evaluator trace artifact of at most 8 MiB.")
    trace = artifact.read_text(encoding="utf-8")
    require(trace.strip(), "Evaluator artifact is empty.")
    cases = report.get("cases")
    require(isinstance(cases, list) and 2 <= len(cases) <= 200, "Supply 2–200 paired held-out cases.")
    ids, sessions = set(), set()
    for case in cases:
        require(isinstance(case, dict), "Case must be an object.")
        key = text(case.get("id"), "case.id", 200)
        session = text(case.get("session"), "case.session", 200)
        text(case.get("rationale"), "case.rationale", 4000)
        require(key not in ids and session not in sessions, "Held-out case ids and session ids must be distinct.")
        # Accept normalized imported ids or original Codex ids, checking both representations.
        require(session not in proposal["training_sessions"] and digest(session)[:24] not in proposal["training_sessions"], "Holdout overlaps pattern training evidence.")
        ids.add(key)
        sessions.add(session)
        for field in ("baseline", "candidate"):
            score = case.get(field)
            require(type(score) in (int, float) and math.isfinite(score) and 0 <= score <= 1, "Scores must be finite numbers in [0, 1].")
    baseline = sum(c["baseline"] for c in cases) / len(cases)
    candidate = sum(c["candidate"] for c in cases) / len(cases)
    regressions = [c["id"] for c in cases if c["candidate"] < c["baseline"]]
    decision = "accepted" if candidate > baseline and not regressions else "rejected"
    record = json.loads(redact(encode(report)))
    record.update(id=proposal["id"], decision=decision, baseline_mean=baseline, candidate_mean=candidate,
                  regressions=regressions, artifact_sha256=digest(trace), evaluated=now(),
                  score_provenance="caller-supplied paired evaluation; not independently verified by WorkSkill")
    store.write(f"evaluations/{proposal['id']}.txt", redact(trace), immutable=True)
    store.write(f"evaluations/{proposal['id']}.json", encode(record) + "\n", immutable=True)
    store.put("evaluations", proposal["id"], record)
    proposal["decision"] = decision
    store.put("proposals", proposal["id"], proposal)
    store.event("evaluate", {"proposal": proposal["id"], "decision": decision, "baseline": baseline, "candidate": candidate})
    return record


def promote(store, key):
    proposal = store.get("proposals", key)
    require(proposal["decision"] == "accepted", "Only an accepted evaluation can be promoted.")
    current = store.get("active", proposal["skill"], False)
    if current and current["proposal"] == key:
        return current
    check_candidate(store, proposal)
    store.put("active", proposal["skill"], {"skill": proposal["skill"], "proposal": key, "promoted": now()})
    store.event("promote", {"skill": proposal["skill"], "proposal": key, "previous": proposal["base"]})
    return {"skill": proposal["skill"], "proposal": key, "path": str(store.root / "skills" / proposal["skill"])}


def rollback(store, name, key):
    name = slug(name)
    proposal = store.get("proposals", key)
    require(proposal["skill"] == name and proposal["decision"] == "accepted", "Rollback target must be an accepted version of this skill.")
    current = store.get("active", name)
    # Only a previously activated ancestor is a rollback, not a bypass for a stale candidate.
    activated = {json.loads(r[0]).get("proposal") for r in store.db.execute("SELECT body FROM events WHERE kind='promote'")}
    require(key in activated, "Rollback target has never been promoted.")
    store.put("active", name, {"skill": name, "proposal": key, "promoted": now()})
    store.event("rollback", {"skill": name, "proposal": key, "previous": current["proposal"]})
    return {"skill": name, "proposal": key, "wiki_preserved": True}


def profile(store):
    return {"owner": store.config["owner"], "patterns": store.all("patterns"),
            "notice": "Evidence of methods expressed in work; not a proficiency score or employment assessment."}


def status(store):
    return {"owner": store.config["owner"], "vault": str(store.root),
            **{field: store.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for field, table in
               (("evidence", "evidence"), ("patterns", "patterns"), ("proposals", "proposals"), ("active_skills", "active"))},
            "pending_evidence": store.db.execute("SELECT COUNT(*) FROM evidence WHERE id NOT IN (SELECT id FROM processed)").fetchone()[0]}


def export_skill(store, name, destination):
    name = slug(name)
    active = store.get("active", name)
    proposal = store.get("proposals", active["proposal"])
    require(all(store.get("patterns", key)["status"] == "active" for key in proposal["patterns"]),
            "This skill depends on disputed or retired knowledge; review and compile a new version before exporting.")
    destination = Path(destination).expanduser()
    require(not destination.is_symlink(), "Export destination must not be a symlink.")
    target = destination / name
    require(not target.exists() and not target.is_symlink(), "Export target already exists; choose a new destination.")
    target.mkdir(parents=True, mode=0o700)
    atomic_write(target / "SKILL.md", proposal["content"])
    return {"path": str(target.resolve()), "files": ["SKILL.md"], "review_before_sharing": True}


def scope(store, sources, projects):
    for key, values in (("sources", sources), ("projects", projects)):
        paths = [Path(p).expanduser().resolve() for p in values]
        require(paths and all(p.is_dir() and p != Path(p.anchor) for p in paths), "Allowlist entries must be existing, specific directories.")
        store.config[key] = [str(p) for p in paths]
    store.write("config.json", encode(store.config) + "\n")
    store.db.execute("DELETE FROM imports")
    store.event("scope", {"sources": store.config["sources"], "projects": store.config["projects"]})
    return {"sources": store.config["sources"], "projects": store.config["projects"], "existing_evidence_preserved": True}


def render(store):
    patterns = store.all("patterns")
    index = ["# WorkSkill knowledge wiki", "", "Private derived view. Use the CLI to change records.", ""]
    for p in patterns:
        index.append(f"- [{p['title']}](patterns/{p['id']}.md) — {p['attribution']}, {p['status']}, revision {p['revision']}")
        page = [f"# {p['title']}", "", f"Capability: {p['capability']}", f"Attribution: {p['attribution']}",
                f"Status: {p['status']}", f"Revision: {p['revision']}", f"Employee confirmed: {p['confirmed']}", "", p["claim"], "", p["when"], ""]
        page += [f"{i}. {step}" for i, step in enumerate(p["procedure"], 1)]
        page += ["", "## Limits", ""] + [f"- {s}" for s in p["avoid"]]
        page += ["", "## Evidence", ""]
        for ref in p["evidence"]:
            evidence = store.get("evidence", ref["id"])
            page += [f"- [{ref['id'][:12]}](../../raw/{ref['id']}.json) · {ref['supports']} · session {evidence['session']}", "", "    " + ref["quote"].replace("\n", "\n    "), ""]
        store.write(f"wiki/patterns/{p['id']}.md", "\n".join(page) + "\n")
    store.write("wiki/index.md", "\n".join(index) + "\n")
    history = ["# Evolution history", ""]
    for kind, body, created in store.db.execute("SELECT kind, body, created FROM events ORDER BY seq"):
        history.append(f"- {created} · {kind} · {body}")
    store.write("wiki/logs.md", "\n".join(history) + "\n")
    impact = ["# Skill impact", "", "Failed proposals remain evidence for later iterations.", ""]
    for p in store.all("proposals"):
        impact += [f"## {p['skill']} · {p['id']}", "", f"Decision: {p['decision']}", "", "```diff", p["diff"], "```", ""]
    store.write("wiki/skill-impact.md", "\n".join(impact) + "\n")
    for active in store.all("active"):
        p = store.get("proposals", active["proposal"])
        store.write(f"skills/{p['skill']}/SKILL.md", p["content"])
        store.write(f"skills/{p['skill']}/PURPOSE.md", purpose(p))
    return {"rendered_patterns": len(patterns)}
