"""A self-contained, offline HTML report. All work-derived strings are escaped."""
from html import escape

from .engine import status
from .storage import now

LABELS = {"human_observed": "员工方法 · 单次观察", "human_repeated": "员工方法 · 跨任务复现",
          "agent_only": "AI 执行经验", "active": "有效", "disputed": "存在反例", "retired": "已停用",
          "accepted": "验证通过", "rejected": "验证未通过", "pending": "等待验证"}

CSS = """
:root{--paper:#f4f2e9;--ink:#24382e;--muted:#6d786d;--line:#d4d9c9;--green:#356744;--accent:#de8d49}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.65 'Avenir Next','PingFang SC','Noto Sans CJK SC',sans-serif}
a{color:var(--green);text-underline-offset:4px}a:focus-visible,summary:focus-visible{outline:3px solid var(--accent);outline-offset:5px}
header{padding:26px 5vw;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:20px}
.wordmark{font-size:21px;font-weight:700;letter-spacing:-1px}.mark{display:inline-grid;place-items:center;background:var(--ink);color:var(--paper);width:31px;height:31px;margin-right:9px;font-family:Georgia,serif}
.eyebrow,.mono{font:11px/1.6 'SFMono-Regular',Consolas,monospace;letter-spacing:1.8px;text-transform:uppercase}.eyebrow{color:var(--muted)}nav{display:flex;gap:24px;font-size:12px}nav a{text-decoration:none}
main{max-width:1320px;margin:auto;padding:48px 5vw 70px}.hero{display:grid;grid-template-columns:1.6fr 1fr;gap:48px;align-items:end;margin-bottom:48px}h1{font:clamp(38px,5vw,68px)/1.17 Georgia,'Songti SC',serif;letter-spacing:-2px;margin:17px 0 22px;font-weight:400}h1 em{color:var(--green);font-style:normal}.intro{max-width:590px;color:var(--muted);font-size:15px}
.aside{border-left:2px solid var(--accent);padding-left:22px;margin:0 0 20px;color:var(--muted);font-size:13px}.aside strong{color:var(--ink);display:block;margin-bottom:9px}.stats{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin-bottom:46px}.stat{padding:22px 24px;border-right:1px solid var(--line)}.stat:first-child{padding-left:0}.stat:last-child{border:0}.number{font:42px/1.3 Georgia,serif}.stat label{display:block;font-size:12px;color:var(--muted);margin-top:6px}
.section-title{display:flex;align-items:baseline;justify-content:space-between;gap:20px;margin:36px 0 18px}h2{font-size:21px;font-weight:500;margin:0}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.card{border:1px solid var(--line);padding:25px;background:#fcfbf6;min-width:0}.card-top{display:flex;justify-content:space-between;gap:10px;align-items:start}.badge{font-size:10px;white-space:nowrap;border:1px solid #b4c4ae;padding:3px 7px;color:var(--green)}.badge.warn{color:#87522d;border-color:#d6b08a}.card h3{font:24px/1.3 Georgia,'Songti SC',serif;margin:17px 0 10px}.card p{font-size:13px;color:var(--muted)}.meta{display:flex;gap:15px;font-size:11px;color:var(--muted);margin:15px 0}.card ol{padding-left:20px;font-size:13px}.card li{padding:4px 0}.card footer{border-top:1px solid var(--line);padding-top:14px;margin-top:22px;display:flex;gap:20px;align-items:center;font-size:11px}.card footer a{margin-left:auto}details{margin-top:18px}summary{cursor:pointer;font-size:12px;color:var(--green)}blockquote{border-left:2px solid var(--line);padding-left:13px;margin:14px 0;font-size:12px;overflow-wrap:anywhere}
.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px}th{text-align:left;color:var(--muted);font-size:11px;font-weight:400}td,th{padding:15px 10px;border-bottom:1px solid var(--line)}td:first-child,th:first-child{padding-left:0}td small{display:block;font-size:10px;color:var(--muted)}.empty{padding:32px;border:1px dashed var(--line);color:var(--muted)}.footnote{margin-top:45px;padding-top:20px;border-top:1px solid var(--line);font-size:11px;color:var(--muted);display:flex;justify-content:space-between;gap:30px}code{font-size:11px;overflow-wrap:anywhere}
@media(max-width:720px){header{align-items:start}nav{gap:12px}.hero{grid-template-columns:1fr;gap:14px}.hero h1{letter-spacing:-1px}.stats{grid-template-columns:repeat(2,1fr)}.stat{padding:16px!important}.grid{grid-template-columns:1fr}main{padding-top:32px}.section-title,.footnote{flex-direction:column;gap:8px}.badge{white-space:normal}.aside{margin-bottom:0}}
@media print{header nav{display:none}main{padding:20px}.hero{margin-bottom:20px}.card{break-inside:avoid}body{background:white}details[open]{display:block}}
"""


def report(store):
    info = status(store)
    cards = []
    for p in sorted(store.all("patterns"), key=lambda p: (p["attribution"] == "agent_only", p["id"])):
        refs = p["evidence"]
        sessions = {store.get("evidence", r["id"])["session"] for r in refs}
        evidence_html = "".join(f'<blockquote>{escape(r["quote"])}<br><a href="raw/{r["id"]}.json">{escape(r["supports"])} · {r["id"][:10]}</a></blockquote>' for r in refs)
        procedure = "".join(f"<li>{escape(step)}</li>" for step in p["procedure"])
        limits = " / ".join(p["avoid"])
        warn = " warn" if p["status"] != "active" or p["attribution"] == "agent_only" else ""
        cards.append(f'''<article class="card"><div class="card-top"><span class="eyebrow">{escape(p['capability'])}</span><span class="badge{warn}">{LABELS[p['attribution']]}</span></div>
<h3>{escape(p['title'])}</h3><p>{escape(p['claim'])}</p><div class="meta"><span>{len(sessions)} 个任务</span><span>{len(refs)} 条证据</span><span>REV {p['revision']:02d}</span></div>
<ol>{procedure}</ol><p>适用边界：{escape(limits) or '尚未补充'}</p><details><summary>展开原始证据与归属</summary>{evidence_html}</details>
<footer><span>{LABELS[p['status']]}</span><span>{'AI 经验，不作员工归属' if p['attribution'] == 'agent_only' else '员工已确认' if p['confirmed'] else '待员工确认'}</span><a href="wiki/patterns/{p['id']}.md">查看 Wiki ↗</a></footer></article>''')
    proposals = store.all("proposals")
    active_ids = {p["proposal"] for p in store.all("active")}
    rows = []
    for p in sorted(proposals, key=lambda p: (p["created"], p["id"]), reverse=True):
        ev = store.get("evaluations", p["id"], False)
        score = f"{ev['baseline_mean']:.0%} → {ev['candidate_mean']:.0%}" if ev else "—"
        evaluator = escape(ev["evaluator"]) if ev else "尚无评估记录"
        rows.append(f'<tr><td>{escape(p["skill"])}<small>{p["id"][:12]}</small></td><td>{LABELS[p["decision"]]}</td><td>{score}<small>{evaluator}</small></td><td>{"使用中" if p["id"] in active_ids else "保留历史"}</td><td><a href="candidates/{p["id"]}/SKILL.md">查看版本 ↗</a></td></tr>')
    stats = "".join(f'<div class="stat"><span class="number">{info[key]:02d}</span><label>{label}</label></div>' for key, label in (("evidence", "工作证据"), ("patterns", "知识模式"), ("active_skills", "已启用 Skills"), ("pending_evidence", "待蒸馏记录")))
    document = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>WorkSkill · 个人能力档案</title><style>{CSS}</style></head><body>
<header><div class="wordmark"><span class="mark">w</span>workskill</div><nav><a href="#patterns">知识档案</a><a href="#evolution">技能演化</a><span class="eyebrow">LOCAL / PRIVATE</span></nav></header>
<main><section class="hero"><div><div class="eyebrow">THE WORK YOU DO. THE CRAFT YOU KEEP.</div><h1>让工作的经验，<br>成为<em>自己的能力。</em></h1><p class="intro">从真实工作中发现方法，为每一条经验保留证据，让经过验证的技能持续积累。</p></div><div class="aside"><strong>{escape(info['owner'])} / 个人工作档案</strong>区分员工表达的方法与 AI 的执行经验。观察记录可追溯，能力归属由员工确认。<br><br>更新于 {escape(now())}</div></section>
<section class="stats" aria-label="档案统计">{stats}</section>
<section id="patterns"><div class="section-title"><h2>经验正在形成的方法</h2><span class="eyebrow">EVIDENCE → KNOWLEDGE → SKILL</span></div><div class="grid">{''.join(cards) or '<p class="empty">还没有知识模式。导入已授权的工作记录后，让 $distill-work 开始蒸馏。</p>'}</div></section>
<section id="evolution"><div class="section-title"><h2>每一次技能演化，都留下依据</h2><a href="wiki/skill-impact.md">查看完整修改历史 ↗</a></div><div class="table-wrap"><table><thead><tr><th>SKILL / VERSION</th><th>验证结果</th><th>配对评估</th><th>当前状态</th><th>内容</th></tr></thead><tbody>{''.join(rows) or '<tr><td colspan="5">尚无候选 Skill。先积累有证据支持的方法。</td></tr>'}</tbody></table></div></section>
<footer class="footnote"><span>基于 WikiSkill 思路独立开发 · 工作方法观察，不作为员工绩效评分。<br>评估分数由调用方提供，WorkSkill 校验门槛与版本关联，不独立证明能力提升。</span><span>WorkSkill 0.1.0<br>此报告包含私人工作知识，请在分享前审阅。</span></footer></main></body></html>'''
    store.write("report.html", document)
    return {"path": str(store.root / "report.html"), "patterns": len(cards), "private": True}
