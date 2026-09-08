# Evaluate a candidate without manufacturing evidence

The gate validates a submitted paired evaluation, not a model's behavior by itself. An evaluator can be a domain-specific test runner or a person reviewing actual task outputs. The hosting agent must run or inspect that evaluation and preserve its trace before calling `evaluate`.

## Paired protocol

1. Read the proposal JSON and its `base`. If null, evaluate without a skill as baseline. Otherwise use the exact baseline proposal content. The currently active version cannot change between evaluation and promotion.
2. Choose at least two held-out task sessions absent from the pattern evidence. Use the actual session identifiers, never rename training sessions to bypass overlap checks. Synthetic new tasks use their own unique identifiers and must be described as synthetic.
3. Fix the model/version or human evaluator, tools, environment, input, and scoring rubric. Compare baseline and candidate on the same cases. An isolated temporary directory is appropriate for outputs. The user must already have authorized any actual external side effects the tasks require.
4. Record scores from observed results, normalized to [0,1]. Preserve inputs, outputs, rubric, model/evaluator identity, and reasoning in a trace file. Do not record secrets. Prefer deterministic outcome checks when available. Label subjective human/model judgments accurately.
5. Submit the report. Acceptance requires strictly better mean performance and no individual-case regression. If validation is unavailable, keep `pending`; a well-written skill is not evidence of improved outcomes.

## Input (`evaluate --file evaluation.json`)

```json
{
  "proposal": "ACTUAL_PROPOSAL_ID",
  "candidate_sha256": "ACTUAL_PROPOSAL_SHA256",
  "evaluator": "Example: named test harness and version",
  "environment": "Example: model/version; OS/tool versions; rubric version",
  "artifact": "/absolute/private/path/to/paired-evaluation-trace.txt",
  "cases": [
    {
      "id": "holdout-case-1",
      "session": "ACTUAL_HELDOUT_SESSION_1",
      "baseline": 0,
      "candidate": 1,
      "rationale": "Replace these illustrative numbers with observed outcomes and scoring reasons."
    },
    {
      "id": "holdout-case-2",
      "session": "ACTUAL_HELDOUT_SESSION_2",
      "baseline": 1,
      "candidate": 1,
      "rationale": "Both runs satisfied the same predeclared assertions."
    }
  ]
}
```

This is a schema illustration, not an evaluation to submit unchanged. `scripts/demo.py` in the source repository uses explicitly fictional scores solely to demonstrate deterministic state transitions.

## What the gate enforces

- Exact candidate content hash and current pattern revisions.
- The baseline pointer has not changed since proposal creation.
- 2–200 distinct case ids and session ids; no overlap with training references. Original Codex ids and normalized importer ids are checked.
- Finite numeric scores in [0,1]; nonempty evaluator/environment/rationales.
- An existing, nonempty UTF-8 trace file of at most 8 MiB. A redacted copy and original-content hash are retained.
- One immutable accept/reject decision per proposal. Strict aggregate improvement without any per-case regression.

The gate cannot independently prove that supplied scores are true, that holdout task semantics differ from training, or that the evaluator is unbiased. Describe these limitations when reporting efficacy. Two cases are a minimum operational gate, not statistical evidence of broad skill superiority. The tests shipped with WorkSkill validate software behavior, not model capability gains.

After acceptance, `promote` rechecks the pattern revisions and baseline before switching the active pointer. `rollback` requires a previously activated version and never resets wiki history. A pattern with later contradictory evidence can prevent exporting its existing skill. Already copied skills outside the vault are not automatically revoked.
