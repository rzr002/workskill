# WorkSkill

**Turn the work methods in your Codex sessions into a personal wiki and reusable skills.**

For people who use Codex to build software, diagnose problems, or work with data and want to reuse what worked. WorkSkill extracts methods from authorized records, keeps their source evidence and limits, and proposes skills for evaluation before activation.

**[Run the synthetic demo](#demo)** · [Install in Codex](#install) · [中文说明](README.md) · [Record schemas](skills/distill-work/references/records.md)

Python **3.10+** · No third-party runtime dependencies · [MIT](LICENSE) · Version **0.1.0**

- **A personal wiki with source evidence:** inspect the records, conditions, and counterexamples behind each method.
- **Reviewable skill candidates:** track revisions and failed proposals; activate only after the paired evaluation gate passes.
- **A local HTML report:** browse methods, evidence, and skill history in one place.

![Local capability report using fictional employee data](docs/images/demo-report.png)

<a id="demo"></a>
## Try it with synthetic records

Requires only Python and Git. The demo reads no real work records, installs no skill, and makes no model calls.

```bash
git clone https://github.com/rzr002/workskill.git
cd workskill
python3 scripts/demo.py --output /tmp/workskill-demo
```

Open the `report` path printed by the command. It shows four fictional work records, three patterns, and one accepted and one rejected skill proposal. Choose a fresh output directory when rerunning.

All employee records and evaluation scores are synthetic. This demonstrates the data flow and evaluation gate, not measured model improvement. To use your own records, continue with installation.

<a id="install"></a>
## Install in Codex

From the cloned `workskill` directory:

```bash
python3 scripts/install_skill.py
```

Requires Python 3.10+, with no runtime dependencies. Open a new Codex task after installation and ask:

> Use $distill-work to extract my work methods from authorized Codex session exports at /absolute/sessions, restricted to /absolute/project. Use employee alias example-user. Update my wiki, show an evidence report, and propose reusable skills.

The installer copies the self-contained skill into `~/.codex/skills/distill-work` and refuses to overwrite an existing installation. `--dest` selects a different skills parent directory; `--dry-run` previews installation. The plugin manifest is provided for plugin distribution systems; this repository does not configure a marketplace.

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

## Related projects and feedback

- [Reflect Workday](https://github.com/rzr002/reflect-workday): recall what happened during a day or week.
- [Personal Workbench](https://github.com/rzr002/personal-workbench): organize and route existing personal and team skills.

Each project works independently; there is no automatic personal-data synchronization between them. [Report a problem or suggest an improvement](https://github.com/rzr002/workskill/issues) with your use case, expected outcome, and a synthetic reproduction.

WorkSkill is an independent adaptation of [WikiSkill](https://arxiv.org/abs/2608.27454), with no Google affiliation or claim to reproduce the paper's benchmark results.
