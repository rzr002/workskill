# WorkSkill

Turn the methods in your work into a personal, evidence-backed wiki and reusable skills. WorkSkill is an independent adaptation of [WikiSkill](https://arxiv.org/abs/2608.27454) for employee-owned work knowledge, packaged as a portable Codex skill with a plugin manifest.

[中文说明](README.md) · [Record schemas](skills/distill-work/references/records.md) · [Evaluation](skills/distill-work/references/evaluation.md) · [Continuous use](skills/distill-work/references/continuous.md)

![Local capability report using fictional employee data](docs/images/demo-report.png)

## Install

```bash
git clone https://github.com/rzr002/workskill.git
cd workskill
python3 scripts/install_skill.py
```

Requires Python 3.10+, with no runtime dependencies. Open a new Codex task after installation and ask:

> Use $distill-work to extract my work methods from authorized Codex session exports at /absolute/sessions, restricted to /absolute/project. Use employee alias example-user. Update my wiki, show an evidence report, and propose reusable skills.

The installer copies the self-contained skill into `~/.codex/skills/distill-work` and refuses to overwrite an existing installation. `--dest` selects a different skills parent directory; `--dry-run` previews installation. The plugin manifest is provided for plugin distribution systems; this repository does not configure a marketplace.

## Run a fictional demonstration

```bash
python3 scripts/demo.py --output /tmp/workskill-demo
```

Open the reported `report.html` path. All employee records and evaluation scores in this demo are synthetic. It demonstrates one accepted and one rejected skill proposal, not measured model improvement.

## What it does

- Incrementally imports allowlisted Codex JSONL visible user/assistant messages, redacts common secrets and email addresses, and deduplicates evidence.
- Separates human-authored methods, AI-reported outcomes, and contradictory evidence. Multiple observations are evidence frequency, not a proficiency score.
- Keeps a persistent wiki with exact quotes, revisions, employee confirmation, retirement, and failed-proposal history.
- Compiles standard `SKILL.md` files with private provenance and immutable proposal hashes.
- Gates caller-supplied paired evaluations: distinct held-out sessions, current baseline and pattern revisions, higher average score, and no per-case regression.
- Activates accepted candidates, restores previously activated versions, and exports only the active skill instructions.
- Produces a self-contained offline HTML report with source evidence and skill history.

The hosting Codex agent does semantic distillation. The bundled Python CLI does no model calls and does not independently establish that submitted evaluation scores are true. Pending candidates remain pending when actual evaluation is unavailable.

## Continuous updates

Ask Codex to use this skill on a recurring schedule. Where a host automation tool is available, the skill configures a recurring distillation task in the requested scope. Installation alone starts no background process.

`workskill --vault /private/vault watch --interval 60` only imports new evidence. Full semantic updates require the recurring hosting-agent task. See [continuous operation](skills/distill-work/references/continuous.md).

## Data and limitations

One private vault per person, default `~/.local/share/workskill`. SQLite is authoritative; Markdown views can be rebuilt with `render`. The importer records redacted visible-message snapshots, not full unredacted traces or hidden reasoning. Source exports remain unchanged. Narrowing future import scope preserves historical records.

The CLI is offline, but evidence read by the hosting model is processed by the user's configured model service. Redaction is heuristic and cannot guarantee removal of business secrets. Exported instructions still need review before sharing. This is not a multi-tenant enterprise platform, an employee rating system, or a reproduction of WikiSkill's benchmark gains.

## Develop

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_package.py
```

Optional CLI packaging: `python3 -m pip install .`, then `workskill --help`. Tests use fictional evidence in temporary directories. [Architecture](docs/architecture.md) · [MIT License](LICENSE).
