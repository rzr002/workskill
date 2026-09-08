#!/usr/bin/env python3
"""Exercise the complete pipeline with fictional records and explicitly synthetic scores."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "skills/distill-work/scripts/workskill.py"


def demo(output):
    if output.exists():
        raise ValueError("Demo output already exists; choose a fresh directory.")
    output.mkdir(parents=True)
    project, source, vault = (output / name for name in ("project", "sessions", "vault"))
    project.mkdir()
    source.mkdir()

    def run(*args):
        result = subprocess.run([sys.executable, str(CLI), "--vault", str(vault), *map(str, args)], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def save(name, data):
        path = output / name
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    run("init", "--owner", "演示员工 · 陈禾（虚构）", "--source", source, "--project", project)
    messages = [
        ("demo-one", "合并销售数据前先确认主键唯一性；合并后核对行数和金额总计，不能只看程序是否报错。", "主键唯一，合并前后总计一致，测试通过。"),
        ("demo-two", "这次也要先检查重复主键，再比较合并前后的总金额。如果业务要求过滤记录，需要单独核对过滤掉的金额。", "检查了重复键；对过滤数据单独核对，结果一致。"),
        ("demo-three", "排查接口故障时，先给出最小复现，再比较预期与实际响应；记录证据后再修改代码。", "用最小请求复现错误，定位到字段映射。"),
        ("demo-four", "请修复导出。", "我通过显式指定 UTF-8 编码修复导出，回归测试通过。"),
    ]
    for sid, human, agent in messages:
        records = [{"type": "session_meta", "payload": {"id": sid, "cwd": str(project)}}]
        records += [{"type": "event_msg", "payload": {"type": kind, "message": value}} for kind, value in (("user_message", human), ("agent_message", agent))]
        (source / f"{sid}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    run("ingest")
    evidence = run("inbox")["evidence"]

    def ref(fragment, support="human_method"):
        item = next(e for e in evidence if fragment in e["text"])
        return {"id": item["id"], "quote": item["text"], "supports": support}

    patterns = [
        {"id": "join-reconciliation", "title": "用业务总量验证数据合并", "capability": "数据核对 / DATA RECONCILIATION",
         "claim": "员工在两次工作任务中主动要求主键检查与总量核对。", "when": "合并带金额或数量字段的数据表时",
         "procedure": ["记录输入行数、主键重复情况及金额总计。", "按声明的连接关系合并，核对输出行数。", "比较前后总额；有意过滤的数据单独核对。"],
         "avoid": ["预期的一对多关系需要单独定义核对规则。"], "evidence": [ref("合并销售数据前"), ref("这次也要先检查")]},
        {"id": "minimal-reproduction", "title": "从最小复现开始排查接口", "capability": "问题诊断 / DEBUGGING",
         "claim": "员工明确要求用可复现的输入与响应差异推动诊断。", "when": "排查接口响应与预期不一致时",
         "procedure": ["构造能稳定复现问题的最小请求。", "记录预期响应与实际响应。", "根据差异定位根因，并保留回归用例。"],
         "avoid": ["单次观察，尚未证明在其他项目中可复用。"], "evidence": [ref("排查接口故障时")]},
        {"id": "explicit-encoding", "title": "导出时显式声明文本编码", "capability": "AI 执行经验 / AGENT WORKFLOW",
         "claim": "此方法来自 AI 的执行总结，尚无员工提出该方法的证据。", "when": "处理编码不一致的文本导出时",
         "procedure": ["确认消费方要求的字符编码。", "显式指定编码，并验证往返读取。"], "avoid": ["不能据此认定员工已掌握编码诊断。"],
         "evidence": [ref("我通过显式指定", "agent_outcome")]},
    ]
    for pattern in patterns:
        run("learn", "--file", save(pattern["id"] + ".json", pattern))
    proposal = run("propose", "--skill", "reconcile-joins", "--pattern", "join-reconciliation")
    trace = output / "synthetic-evaluation.txt"
    trace.write_text("SYNTHETIC DEMO ONLY. These scores demonstrate the gate; they are not measured model performance.\nCase A baseline=0 candidate=1; Case B baseline=1 candidate=1.\n", encoding="utf-8")

    def evaluate(p, scores):
        report = {"proposal": p["id"], "candidate_sha256": p["sha256"], "evaluator": "SYNTHETIC DEMO — not a live model",
                  "environment": "fictional paired tasks", "artifact": str(trace), "cases": [
                      {"id": f"demo-holdout-{i}", "session": f"demo-unseen-{i}", "baseline": b, "candidate": c,
                       "rationale": "Synthetic outcome for deterministic gate demonstration only."}
                      for i, (b, c) in enumerate(zip((0, 1), scores))]}
        return run("evaluate", "--file", save("report-" + p["id"] + ".json", report))

    evaluate(proposal, (1, 1))
    run("promote", proposal["id"])
    patterns[0]["procedure"].append("检查空主键，并记录它们对连接结果的影响。")
    run("learn", "--file", save("updated-pattern.json", patterns[0]))
    second = run("propose", "--skill", "reconcile-joins", "--pattern", "join-reconciliation")
    trace.write_text("SYNTHETIC DEMO ONLY. Candidate regresses: A baseline=0 candidate=0; B baseline=1 candidate=0.\n", encoding="utf-8")
    evaluate(second, (0, 0))
    run("ack", *[e["id"] for e in evidence], "--reason", "Reviewed in fictional demonstration.")
    html = run("report")
    return {"vault": str(vault), "report": html["path"], "accepted": 1, "rejected": 1,
            "notice": "All employee records and evaluation scores are synthetic."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(demo(args.output.expanduser().resolve()), ensure_ascii=False))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(str(error) + (getattr(error, "stderr", "") or ""), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
