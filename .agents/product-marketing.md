# Product Marketing Context

**Document version:** v1
**Last updated:** 2026-09-08
**Basis:** Current public implementation. Audience and conversion goals below are working assumptions, not customer research.

## Product overview

WorkSkill turns methods expressed in authorized Codex work records into a personal wiki and reusable skill candidates. The hosting Codex agent performs semantic distillation; the dependency-free Python CLI stores evidence, checks proposals and evaluations, and renders reports. Independent adaptation of WikiSkill; MIT licensed.

## Audience and problem

Primary audience: people who repeatedly develop, debug, or analyze data with Codex and want to preserve their own methods across tasks. Their useful instructions are scattered through session records and difficult to inspect or reuse. Company size, willingness to pay, and customer adoption have not been established.

## Positioning and differentiation

- Preserve methods with exact source evidence, conditions, counterexamples, and version history.
- Distinguish human methods from AI-reported outcomes.
- Propose skills and gate activation with caller-supplied paired evaluation evidence.
- Keep rejected proposals available for later learning.
- Let visitors inspect the full data flow using a synthetic local demo before granting access to real records.

## Alternatives and related projects

Manual notes and repeated prompts are workflow alternatives; no comparative performance study is available. Reflect Workday summarizes what happened; Personal Workbench routes registered capabilities; WorkSkill preserves how a task was done. The projects are independent and have no automatic data synchronization.

## Objections and boundaries

- Is it fully offline? The Python engine is offline; evidence read by Codex reaches the configured model service.
- Does it prove a skill improves performance? It validates submitted evaluation evidence and gates activation; it does not independently authenticate scores.
- Does the demo show measured improvement? No. All demo records and scores are synthetic.
- Does installation start continuous learning? No. Full recurring distillation requires a host automation task.
- Is it an employee scoring product? No. Evidence frequency is not proficiency or performance.

## Voice and evidence

Concrete, restrained, bilingual Chinese/English. Lead with an inspectable output, then explain the mechanism. Do not invent testimonials, adoption counts, time savings, benchmark gains, or enterprise security guarantees. There are no verified customer quotes yet.

Proof sources: `scripts/demo.py`, `tests/test_distribution.py`, `tests/test_workskill.py`, `skills/distill-work/references/evaluation.md`, and the synthetic report screenshot. Preserve the WikiSkill attribution.

## Goal

Primary README action: run the synthetic demo and open the report. Secondary action: install the skill and authorize a specific source/project. Feedback should describe the task, expected output, and synthetic reproduction. GitHub visits and clones are discovery indicators, not measurements of successful installation; no installation telemetry is present.

## Changelog

- v1 (2026-09-08) — Capture implementation-backed positioning, demo-first onboarding, and claims boundaries for repository copy.
