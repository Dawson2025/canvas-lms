#!/usr/bin/env python3
"""Generate a presentation-ready HTML report from the live demo database.

Runs the same queries the demo walks through and renders them as a single
self-contained HTML file (no external assets) suitable for projecting in class.
"""
import html
import subprocess
import sys

DB = "cse290r_ai_demo"


def q(sql, tuples_only=True, expanded=False):
    args = ["psql", "-d", DB, "-A", "-F", "\x1f"]
    if tuples_only:
        args.append("-t")
    if expanded:
        args.append("-x")
    args += ["-c", sql]
    out = subprocess.run(args, capture_output=True, text=True, check=True).stdout
    return out


def rows(sql):
    """Return list-of-lists from a unit-separated psql result."""
    out = q(sql)
    result = []
    for line in out.splitlines():
        if not line.strip():
            continue
        result.append(line.split("\x1f"))
    return result


def esc(s):
    return html.escape(s if s is not None else "")


def table(headers, data, aligns=None):
    th = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = []
    for r in data:
        tds = "".join(f"<td>{esc(c)}</td>" for c in r)
        body.append(f"<tr>{tds}</tr>")
    return f"<table><thead><tr>{th}</tr></thead><tbody>{''.join(body)}</tbody></table>"


# --- gather live data ---
manifest = rows("SELECT course_id, course_name, course_code, module_count, "
                "assignment_count, page_count, announcement_count, file_count "
                "FROM ai_course_manifest;")[0]

raw_html = q("SELECT description FROM assignments WHERE id = 16835669;").strip()
clean_md = q("SELECT description_clean FROM ai_course_assignments WHERE id = 16835669;").strip()

secret_raw = rows("SELECT id, title, workflow_state FROM assignments WHERE id = 99999;")
secret_view = rows("SELECT id, title FROM ai_course_assignments WHERE id = 99999;")

unified = rows("SELECT content_type, left(title,46), left(coalesce(content_clean,''),60) "
               "FROM ai_course_content ORDER BY content_type, content_id;")

modules = rows("SELECT module_name, item_position, content_type, coalesce(item_title,'') "
               "FROM ai_course_modules WHERE module_name='Brownfield - Week 3' "
               "ORDER BY item_position;")


def run_tests(path):
    out = subprocess.run(["psql", "-d", DB, "-t", "-f", path],
                         capture_output=True, text=True).stdout
    res = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("PASS:") or line.startswith("FAIL:"):
            res.append(line)
    return res


import os
here = os.path.dirname(os.path.abspath(__file__))
core = run_tests(os.path.join(here, "test_ai_views.sql"))
edge = run_tests(os.path.join(here, "test_edge_cases.sql"))
all_tests = core + edge
n_pass = sum(1 for t in all_tests if t.startswith("PASS:"))
n_fail = sum(1 for t in all_tests if t.startswith("FAIL:"))


def test_html(items):
    li = []
    for t in items:
        ok = t.startswith("PASS:")
        cls = "pass" if ok else "fail"
        mark = "✓" if ok else "✗"
        text = t.split(":", 1)[1].strip()
        li.append(f'<li class="{cls}"><span class="mark">{mark}</span> {esc(text)}</li>')
    return f'<ul class="tests">{"".join(li)}</ul>'


manifest_kv = [
    ("Course", f"{manifest[2]} — {manifest[1]} (id {manifest[0]})"),
    ("Modules", manifest[3]), ("Assignments", manifest[4]),
    ("Pages", manifest[5]), ("Announcements", manifest[6]), ("Files", manifest[7]),
]
manifest_rows = "".join(
    f'<tr><th>{esc(k)}</th><td>{esc(str(v))}</td></tr>' for k, v in manifest_kv)

ferpa_ok = len(secret_view) == 0
ferpa_banner = ('<div class="banner good">✓ FERPA-safe: the unpublished row is INVISIBLE '
                'through the AI view</div>' if ferpa_ok else
                '<div class="banner bad">✗ LEAK: unpublished content visible</div>')

HTML = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Canvas AI Content Access — Demo</title>
<style>
  :root {{ --bg:#0f1419; --panel:#1a2230; --ink:#e6edf3; --muted:#9bb0c3;
           --accent:#4fc3f7; --good:#3fb950; --bad:#f85149; --line:#2a3646; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
          font:16px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; }}
  header {{ padding:28px 40px; background:linear-gradient(135deg,#16202e,#0f1419);
            border-bottom:1px solid var(--line); }}
  h1 {{ margin:0 0 4px; font-size:28px; }}
  .sub {{ color:var(--muted); font-size:15px; }}
  main {{ max-width:1080px; margin:0 auto; padding:32px 40px 80px; }}
  section {{ margin:0 0 36px; }}
  h2 {{ font-size:20px; border-left:4px solid var(--accent); padding-left:12px; margin:0 0 14px; }}
  .lead {{ color:var(--muted); margin:0 0 14px; }}
  .panel {{ background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:18px 20px; }}
  table {{ border-collapse:collapse; width:100%; font-size:14px; }}
  th,td {{ border:1px solid var(--line); padding:7px 10px; text-align:left; vertical-align:top; }}
  th {{ background:#202b3b; color:var(--muted); font-weight:600; }}
  .ba {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
  pre {{ background:#0b0f14; border:1px solid var(--line); border-radius:8px; padding:14px;
         overflow:auto; font:13px/1.5 ui-monospace,Menlo,Consolas,monospace; margin:0;
         white-space:pre-wrap; max-height:340px; }}
  .tag {{ font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.06em; margin-bottom:6px; }}
  .raw .tag {{ color:#e3a008; }}
  .clean .tag {{ color:var(--good); }}
  .banner {{ border-radius:8px; padding:10px 14px; font-weight:600; margin-top:12px; }}
  .banner.good {{ background:rgba(63,185,80,.14); color:var(--good); border:1px solid var(--good); }}
  .banner.bad {{ background:rgba(248,81,73,.14); color:var(--bad); border:1px solid var(--bad); }}
  ul.tests {{ list-style:none; padding:0; margin:0; columns:2; column-gap:28px; }}
  ul.tests li {{ break-inside:avoid; padding:3px 0; font-size:13.5px; }}
  .tests .mark {{ font-weight:700; }}
  .tests .pass .mark {{ color:var(--good); }}
  .tests .fail .mark {{ color:var(--bad); }}
  .scorebar {{ display:inline-block; background:var(--good); color:#04210d; font-weight:800;
               border-radius:999px; padding:6px 18px; font-size:18px; margin-bottom:14px; }}
  .scorebar.bad {{ background:var(--bad); color:#2a0606; }}
  footer {{ color:var(--muted); font-size:13px; border-top:1px solid var(--line);
            padding:18px 40px; text-align:center; }}
</style></head>
<body>
<header>
  <h1>Canvas AI Content Access</h1>
  <div class="sub">Brownfield feature · CSE 290R · PostgreSQL views that serve Canvas course
  content to AI agents as clean, FERPA-safe markdown — no Rails app required</div>
</header>
<main>

<section>
  <h2>1 · Course manifest</h2>
  <p class="lead">One compact row an agent loads into its system prompt — counts of every content type.</p>
  <div class="panel"><table>{manifest_rows}</table></div>
</section>

<section>
  <h2>2 · Before / After — raw Canvas HTML → agent-ready markdown</h2>
  <p class="lead">The same field (<code>Lab 3.2</code> description), as stored vs. as the view returns it.
  The <code>strip_html_tags()</code> SQL function does the conversion in the database.</p>
  <div class="ba">
    <div class="panel raw"><div class="tag">Raw · assignments.description</div><pre>{esc(raw_html)}</pre></div>
    <div class="panel clean"><div class="tag">Clean · ai_course_assignments.description_clean</div><pre>{esc(clean_md)}</pre></div>
  </div>
</section>

<section>
  <h2>3 · FERPA safety — enforced in the database</h2>
  <p class="lead">An <strong>unpublished</strong> "SECRET DRAFT EXAM" row exists in the table.
  The view filters to published/active content only, so an agent literally cannot see it.</p>
  <div class="ba">
    <div class="panel raw"><div class="tag">Raw table — row exists</div>
      {table(["id","title","workflow_state"], secret_raw)}</div>
    <div class="panel clean"><div class="tag">Through AI view — empty</div>
      {table(["id","title"], secret_view) if secret_view else '<pre>(0 rows)</pre>'}</div>
  </div>
  {ferpa_banner}
</section>

<section>
  <h2>4 · Unified content search</h2>
  <p class="lead"><code>ai_course_content</code> UNIONs assignments, pages, and announcements into one surface.</p>
  <div class="panel">{table(["type","title","clean preview"], unified)}</div>
</section>

<section>
  <h2>5 · Module structure, items resolved</h2>
  <p class="lead">Module + its content_tag items, joined in the view — no agent-side SQL needed.</p>
  <div class="panel">{table(["module","pos","content_type","item"], modules)}</div>
</section>

<section>
  <h2>6 · Tests — AAA pattern, run live</h2>
  <div class="scorebar{'' if n_fail==0 else ' bad'}">{n_pass} passed · {n_fail} failed</div>
  <div class="panel">
    <div class="tag">Core view tests ({len(core)})</div>{test_html(core)}
    <div class="tag" style="margin-top:14px">Edge-case tests ({len(edge)})</div>{test_html(edge)}
  </div>
</section>

</main>
<footer>8 views + 1 SQL function · ~516 lines of SQL · deploys on the fork as a read-only Rails migration ·
generated live from PostgreSQL database <code>{DB}</code></footer>
</body></html>
"""

out_path = os.path.join(here, "demo_report.html")
with open(out_path, "w") as f:
    f.write(HTML)
print(out_path)
print(f"tests: {n_pass} pass / {n_fail} fail")
if n_fail:
    sys.exit(1)
