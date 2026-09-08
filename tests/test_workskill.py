"""Behavior tests use synthetic work only; never inspect a developer's sessions."""
import json
import os
from pathlib import Path
import subprocess
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "skills/distill-work/scripts/workskill.py"


class WorkSkillTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.vault = self.base / "private-vault"
        self.sources = self.base / "sessions"
        self.project = self.base / "project"
        self.sources.mkdir()
        self.project.mkdir()

    def run_cli(self, *args, ok=True):
        result = subprocess.run(
            [sys.executable, str(CLI), "--vault", str(self.vault), *map(str, args)],
            capture_output=True, text=True,
        )
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("Traceback", result.stderr)
        return result.stderr

    def init(self):
        return self.run_cli("init", "--owner", "demo-owner", "--source", self.sources,
                            "--project", self.project)

    def write_json(self, name, value):
        path = self.base / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def session(self, name="one", messages=None, cwd=None):
        rows = [{"type": "session_meta", "payload": {"id": name, "cwd": str(cwd or self.project)}}]
        for role, text in messages or [("user", "Compare totals before and after every join."),
                                      ("assistant", "Checked row counts and totals; tests passed.")]:
            rows.append({"type": "response_item", "timestamp": "2026-09-01T09:00:00Z",
                         "payload": {"type": "message", "role": role, "channel": "final",
                                     "content": [{"type": "input_text", "text": text}]}})
        path = self.sources / (name + ".jsonl")
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        return path

    def learned(self):
        self.init()
        self.session()
        self.run_cli("ingest")
        ev = self.run_cli("inbox")["evidence"]
        user = next(e for e in ev if e["role"] == "user")
        note = {"id": "join-checks", "title": "Reconcile joins", "capability": "Data reconciliation",
                "claim": "Uses aggregate checks to detect incorrect joins.",
                "when": "When joining financial tables", "procedure": ["Record input totals.",
                "Join on declared keys.", "Compare row counts and aggregate totals."],
                "avoid": ["Do not apply equal-total assumptions to intentionally filtered data."],
                "evidence": [{"id": user["id"], "quote": user["text"], "supports": "human_method"}]}
        self.run_cli("learn", "--file", self.write_json("note.json", note))
        return note, user

    def proposed(self):
        note, user = self.learned()
        proposal = self.run_cli("propose", "--skill", "reconcile-joins", "--pattern", note["id"])
        return proposal, note, user

    def report(self, proposal, candidate=(1, 1), baseline=(0, 1)):
        artifact = self.base / "evaluation.txt"
        artifact.write_text("Synthetic evaluator trace: two held-out tasks.\n", encoding="utf-8")
        return {"proposal": proposal["id"], "candidate_sha256": proposal["sha256"],
                "evaluator": "synthetic-test-evaluator", "environment": "synthetic-python-tests",
                "artifact": str(artifact), "cases": [
                    {"id": f"heldout-{i}", "session": f"unseen-{i}", "baseline": b,
                     "candidate": c, "rationale": "Synthetic paired outcome."}
                    for i, (b, c) in enumerate(zip(baseline, candidate))]}

    def evaluate(self, proposal, report=None):
        return self.run_cli("evaluate", "--file", self.write_json("report.json", report or self.report(proposal)))

    def test_init_is_private_and_refuses_reinitialization(self):
        self.init()
        if os.name != "nt":
            self.assertEqual(os.stat(self.vault).st_mode & 0o777, 0o700)
        self.run_cli("init", "--owner", "other", "--source", self.sources,
                     "--project", self.project, ok=False)
        self.assertEqual(self.run_cli("status")["owner"], "demo-owner")

    def test_import_is_idempotent_and_redacts_before_persistence(self):
        self.init()
        self.session(messages=[("user", "token=ghp_" + "x" * 36 + " contact demo@example.com"),
                               ("assistant", "Done.")])
        self.assertEqual(self.run_cli("ingest")["imported"], 2)
        self.assertEqual(self.run_cli("ingest")["imported"], 0)
        data = self.run_cli("inbox")["evidence"]
        self.assertEqual(len(data), 2)
        for p in (self.vault / "raw").glob("*.json"):
            self.assertNotIn("ghp_", p.read_text())
            self.assertNotIn("demo@example.com", p.read_text())

    def test_append_imports_only_new_evidence_and_tolerates_partial_last_line(self):
        self.init()
        path = self.session()
        self.run_cli("ingest")
        with path.open("a") as f:
            f.write(json.dumps({"type": "event_msg", "payload": {"type": "user_message", "message": "New correction."}}) + "\n")
            f.write('{"unfinished":')
        result = self.run_cli("ingest")
        self.assertEqual(result["imported"], 1)
        self.assertEqual(len(self.run_cli("inbox")["evidence"]), 3)

    def test_project_and_source_boundaries(self):
        self.init()
        self.session("other", cwd=self.base / "project-private")
        self.assertEqual(self.run_cli("ingest")["imported"], 0)
        outside = self.base / "outside.jsonl"
        outside.write_text(self.session().read_text())
        self.run_cli("ingest", "--file", outside, ok=False)
        if os.name != "nt":
            (self.sources / "linked.jsonl").symlink_to(outside)
        self.assertEqual(self.run_cli("ingest")["imported"], 2)

    def test_analysis_and_system_context_are_not_imported(self):
        self.init()
        path = self.session(messages=[("system", "SYSTEM SECRET"), ("user", "Useful correction.")])
        with path.open("a") as f:
            f.write(json.dumps({"type": "response_item", "payload": {"type": "message", "role": "assistant", "channel": "analysis", "content": [{"text": "PRIVATE REASONING"}]}}) + "\n")
        self.run_cli("ingest")
        text = json.dumps(self.run_cli("inbox"))
        self.assertNotIn("SYSTEM SECRET", text)
        self.assertNotIn("PRIVATE REASONING", text)

    def test_workspace_switch_filters_later_events(self):
        self.init()
        path = self.session()
        with path.open("a") as f:
            f.write(json.dumps({"type": "turn_context", "payload": {"cwd": str(self.base / "private")}}) + "\n")
            f.write(json.dumps({"type": "event_msg", "payload": {"type": "user_message", "message": "PRIVATE TASK"}}) + "\n")
        self.run_cli("ingest")
        self.assertEqual(len(self.run_cli("inbox")["evidence"]), 2)

    def test_learning_requires_real_quotes_and_human_attribution(self):
        note, user = self.learned()
        profile = self.run_cli("profile")
        self.assertEqual(profile["patterns"][0]["attribution"], "human_observed")
        note["evidence"][0]["quote"] = "invented proof"
        self.run_cli("learn", "--file", self.write_json("bad.json", note), ok=False)
        agent = next(e for e in self.run_cli("inbox")["evidence"] if e["role"] == "assistant")
        note["evidence"] = [{"id": agent["id"], "quote": agent["text"], "supports": "human_method"}]
        self.run_cli("learn", "--file", self.write_json("bad.json", note), ok=False)

    def test_agent_outcomes_do_not_claim_employee_ability(self):
        note, _ = self.learned()
        agent = next(e for e in self.run_cli("inbox")["evidence"] if e["role"] == "assistant")
        note["id"] = "agent-pattern"
        note["evidence"] = [{"id": agent["id"], "quote": agent["text"], "supports": "agent_outcome"}]
        self.run_cli("learn", "--file", self.write_json("agent.json", note))
        p = next(p for p in self.run_cli("profile")["patterns"] if p["id"] == note["id"])
        self.assertEqual(p["attribution"], "agent_only")

    def test_pattern_updates_preserve_evidence_and_revisions(self):
        note, _ = self.learned()
        self.session("two", [("user", "After joining, verify the grand total and check duplicate keys.")])
        self.run_cli("ingest")
        user = next(e for e in self.run_cli("inbox")["evidence"] if "duplicate" in e["text"])
        note["evidence"] = [{"id": user["id"], "quote": user["text"], "supports": "human_method"}]
        self.run_cli("learn", "--file", self.write_json("update.json", note))
        pattern = self.run_cli("profile")["patterns"][0]
        self.assertEqual(pattern["attribution"], "human_repeated")
        self.assertEqual(len(pattern["evidence"]), 2)
        self.assertEqual(pattern["revision"], 2)
        self.assertTrue((self.vault / "wiki/patterns/join-checks.md").exists())

    def test_counterevidence_blocks_compilation(self):
        note, user = self.learned()
        note["evidence"] = [{"id": user["id"], "quote": user["text"], "supports": "counterexample"}]
        self.run_cli("learn", "--file", self.write_json("conflict.json", note))
        self.assertEqual(self.run_cli("profile")["patterns"][0]["status"], "disputed")
        self.run_cli("propose", "--skill", "reconcile-joins", "--pattern", note["id"], ok=False)

    def test_rejection_preserves_active_skill_and_wiki(self):
        proposal, note, _ = self.proposed()
        self.assertEqual(self.evaluate(proposal)["decision"], "accepted")
        self.run_cli("promote", proposal["id"])
        active = self.vault / "skills/reconcile-joins/SKILL.md"
        before = active.read_text()
        note["procedure"].append("Inspect null keys.")
        self.run_cli("learn", "--file", self.write_json("update.json", note))
        second = self.run_cli("propose", "--skill", "reconcile-joins", "--pattern", note["id"])
        self.assertEqual(self.evaluate(second, self.report(second, candidate=(0, 1)))["decision"], "rejected")
        self.run_cli("promote", second["id"], ok=False)
        self.assertEqual(active.read_text(), before)
        self.assertIn("rejected", (self.vault / "wiki/skill-impact.md").read_text())
        self.assertIn("Inspect null keys.", (self.vault / "wiki/patterns/join-checks.md").read_text())

    def test_gate_refuses_leaked_holdouts_and_nonfinite_scores(self):
        proposal, _, user = self.proposed()
        report = self.report(proposal)
        report["cases"][0]["session"] = user["session"]
        self.run_cli("evaluate", "--file", self.write_json("leaked.json", report), ok=False)
        report = self.report(proposal)
        report["cases"][0]["candidate"] = float("nan")
        self.run_cli("evaluate", "--file", self.write_json("nan.json", report), ok=False)
        self.run_cli("promote", proposal["id"], ok=False)

    def test_gate_binds_candidate_bytes_and_rejects_stale_pattern(self):
        proposal, note, _ = self.proposed()
        candidate = self.vault / "candidates" / proposal["id"] / "SKILL.md"
        candidate.write_text(candidate.read_text() + "\nTampered.\n")
        self.run_cli("evaluate", "--file", self.write_json("report.json", self.report(proposal)), ok=False)

    def test_changed_pattern_invalidates_previously_accepted_proposal(self):
        proposal, note, _ = self.proposed()
        self.evaluate(proposal)
        note["procedure"].append("New method.")
        self.run_cli("learn", "--file", self.write_json("update.json", note))
        self.run_cli("promote", proposal["id"], ok=False)

    def test_export_contains_only_validated_skill_without_private_provenance(self):
        proposal, _, _ = self.proposed()
        self.evaluate(proposal)
        self.run_cli("promote", proposal["id"])
        destination = self.base / "export"
        self.run_cli("export", "reconcile-joins", "--to", destination)
        files = list(destination.rglob("*"))
        self.assertEqual([p.name for p in files if p.is_file()], ["SKILL.md"])
        text = (destination / "reconcile-joins/SKILL.md").read_text()
        self.assertNotIn(str(self.sources), text)
        self.assertNotIn("demo-owner", text)
        self.run_cli("export", "reconcile-joins", "--to", destination, ok=False)

    def test_path_traversal_and_empty_inbox_limits_rejected(self):
        note, _ = self.learned()
        self.run_cli("propose", "--skill", "../../escape", "--pattern", note["id"], ok=False)
        self.run_cli("inbox", "--limit", "-1", ok=False)

    def test_watch_once_imports_without_automatic_promotion(self):
        self.init()
        self.session()
        self.assertEqual(self.run_cli("watch", "--once")["imported"], 2)
        self.assertEqual(self.run_cli("status")["active_skills"], 0)

    def test_confirmation_and_retirement_preserve_history(self):
        note, _ = self.learned()
        self.assertTrue(self.run_cli("confirm", note["id"], "--note", "Employee explicitly confirmed this method.")["confirmed"])
        self.run_cli("retire", note["id"], "--reason", "Workflow has changed.")
        self.assertEqual(self.run_cli("profile")["patterns"][0]["status"], "retired")
        self.run_cli("confirm", note["id"], "--note", "Still applies", ok=False)

    def test_ack_removes_only_selected_inbox_items(self):
        _, user = self.learned()
        self.run_cli("ack", user["id"], "--reason", "Recorded as pattern.")
        self.assertEqual(self.run_cli("status")["pending_evidence"], 1)
        self.assertEqual(self.run_cli("status")["evidence"], 2)

    def test_rollback_keeps_new_learning(self):
        first, note, _ = self.proposed()
        self.evaluate(first)
        self.run_cli("promote", first["id"])
        note["procedure"].append("Inspect null keys.")
        self.run_cli("learn", "--file", self.write_json("update.json", note))
        second = self.run_cli("propose", "--skill", "reconcile-joins", "--pattern", note["id"])
        self.evaluate(second)
        self.run_cli("promote", second["id"])
        self.run_cli("rollback", "reconcile-joins", "--to", first["id"])
        self.assertNotIn("Inspect null keys.", (self.vault / "skills/reconcile-joins/SKILL.md").read_text())
        self.assertIn("Inspect null keys.", (self.vault / "wiki/patterns/join-checks.md").read_text())

    def test_pending_export_and_export_after_retirement_are_blocked(self):
        proposal, note, _ = self.proposed()
        self.run_cli("export", "reconcile-joins", "--to", self.base / "export", ok=False)
        self.evaluate(proposal)
        self.run_cli("promote", proposal["id"])
        self.run_cli("retire", note["id"], "--reason", "No longer applies.")
        self.run_cli("export", "reconcile-joins", "--to", self.base / "export", ok=False)

    @unittest.skipIf(os.name == "nt", "Windows symlinks need a developer-mode permission outside this test's scope")
    def test_vault_symlink_cannot_overwrite_outside_file(self):
        self.learned()
        outside = self.base / "important.md"
        outside.write_text("Keep this file.")
        index = self.vault / "wiki/index.md"
        index.unlink()
        index.symlink_to(outside)
        self.run_cli("render", ok=False)
        self.assertEqual(outside.read_text(), "Keep this file.")

    def test_gate_acceptance_requires_improvement_without_case_regression(self):
        proposal, _, _ = self.proposed()
        report = self.report(proposal, baseline=(0, 0.5), candidate=(1, 0.4))
        self.assertEqual(self.evaluate(proposal, report)["decision"], "rejected")

    def test_duplicate_event_and_response_message_count_once(self):
        self.init()
        path = self.session()
        with path.open("a") as f:
            f.write(json.dumps({"type": "event_msg", "payload": {"type": "user_message", "message": "Compare totals before and after every join."}}) + "\n")
        self.assertEqual(self.run_cli("ingest")["imported"], 2)

    def test_invalid_case_types_fail_cleanly(self):
        proposal, _, _ = self.proposed()
        report = self.report(proposal)
        report["cases"][0] = "invalid"
        self.run_cli("evaluate", "--file", self.write_json("invalid.json", report), ok=False)

    def test_scope_can_be_narrowed_without_erasing_old_evidence(self):
        self.init()
        self.session()
        self.run_cli("ingest")
        other = self.base / "other-project"
        other.mkdir()
        self.run_cli("scope", "--project", other, "--source", self.sources)
        self.session("new", [("user", "A later instruction outside current scope.")])
        self.assertEqual(self.run_cli("ingest")["imported"], 0)
        self.assertEqual(self.run_cli("status")["evidence"], 2)

    def test_local_report_renders_chinese_and_escapes_html(self):
        note, _ = self.learned()
        note["title"] = "连接核对 <script>alert(1)</script>"
        self.run_cli("learn", "--file", self.write_json("title.json", note))
        result = self.run_cli("report")
        html = Path(result["path"]).read_text()
        self.assertIn("连接核对", html)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_import_recovers_raw_snapshot_written_before_database_commit(self):
        self.init()
        self.session()
        self.run_cli("ingest")
        snapshots = list((self.vault / "raw").glob("*.json"))
        for path in snapshots:
            data = json.loads(path.read_text())
            data["imported"] = "2020-01-01T00:00:00+00:00"
            path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n")
        connection = sqlite3.connect(self.vault / "workskill.sqlite3")
        with connection:
            connection.execute("DELETE FROM evidence")
            connection.execute("DELETE FROM imports")
        connection.close()
        self.assertEqual(self.run_cli("ingest")["imported"], 2)
        self.assertEqual({e["imported"] for e in self.run_cli("inbox")["evidence"]}, {"2020-01-01T00:00:00+00:00"})

    def test_secret_redaction_does_not_truncate_private_key_before_masking(self):
        self.init()
        value = "-----BEGIN PRIVATE KEY-----\n" + ("private-material" * 3000) + "\n-----END PRIVATE KEY-----"
        self.session(messages=[("user", value)])
        self.run_cli("ingest")
        self.assertNotIn("private-material", self.run_cli("inbox")["evidence"][0]["text"])

    def test_unicode_owner_works_with_ascii_process_output_encoding(self):
        result = subprocess.run([sys.executable, str(CLI), "--vault", str(self.vault), "init",
                                 "--owner", "员工陈禾", "--source", str(self.sources), "--project", str(self.project)],
                                capture_output=True, text=True, env={**os.environ, "PYTHONIOENCODING": "ascii"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["owner"], "员工陈禾")


if __name__ == "__main__":
    unittest.main()
