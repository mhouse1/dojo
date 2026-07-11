from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any


def build_static_report_html(title: str, marker: str, reports: list[dict[str, Any]], generated_at: str | None = None) -> str:
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    counts = {"passed": 0, "failed": 0, "skipped": 0, "xfailed": 0, "xpassed": 0, "error": 0}
    for report in reports:
        outcome = str(report.get("outcome", "unknown")).lower()
        if outcome in counts:
            counts[outcome] += 1
        else:
            counts["error"] += 1

    rows = []
    for report in reports:
        nodeid = escape(str(report.get("nodeid", "unknown")))
        outcome = escape(str(report.get("outcome", "unknown")).upper())
        duration = report.get("duration", 0.0)
        duration_text = f"{duration:.3f}s" if isinstance(duration, (int, float)) else str(duration)
        steps = report.get("steps", []) or []
        step_items = "".join(f"<li>{escape(str(step))}</li>" for step in steps)
        if not step_items:
            step_items = "<li>No narration recorded.</li>"
        details = escape(str(report.get("details", ""))).replace("\n", "<br>")
        rows.append(
            f"<tr class=\"{escape(str(report.get('outcome', 'unknown')).lower())}\">"
            f"<td>{nodeid}</td><td>{outcome}</td><td>{duration_text}</td>"
            f"<td><details><summary>View steps</summary><ol>{step_items}</ol></details></td>"
            f"<td>{details or '&nbsp;'}</td></tr>"
        )

    if not rows:
        rows.append("<tr><td colspan=\"5\">No test results were collected.</td></tr>")

    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>{escape(title)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; color: #222; }}
    h1 {{ margin-bottom: 0.25rem; }}
    .summary {{ margin-bottom: 1rem; padding: 0.75rem 1rem; background: #f5f5f5; border: 1px solid #ddd; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 0.5rem; text-align: left; vertical-align: top; }}
    th {{ background: #f0f0f0; }}
    .passed {{ background: #eef8ee; }}
    .failed {{ background: #fdeeee; }}
    .skipped {{ background: #fff8e8; }}
    .xfailed, .xpassed {{ background: #f3f0ff; }}
    .error {{ background: #fdeeee; }}
    code {{ background: #f7f7f7; padding: 0.1rem 0.3rem; }}
  </style>
</head>
<body>
  <h1>{escape(title)}</h1>
  <p>Generated: {escape(generated_at)}</p>
  <div class=\"summary\">
    <strong>Marker expression:</strong> {escape(marker or '(none - all collected tests)')}<br>
    <strong>Summary:</strong> {counts['passed']} passed, {counts['failed']} failed, {counts['skipped']} skipped, {counts['xfailed']} xfailed, {counts['xpassed']} xpassed, {counts['error']} errors.
  </div>
  <table>
    <thead>
      <tr><th>Test</th><th>Status</th><th>Duration</th><th>Narration</th><th>Details</th></tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</body>
</html>
"""


def write_static_report(session: Any, reports: list[dict[str, Any]], title: str) -> None:
    html_path = session.config.getoption("htmlpath")
    if not html_path:
        return
    output_path = Path(html_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    static_path = output_path.with_name(f"{output_path.stem}-static{output_path.suffix}")
    static_path.write_text(
        build_static_report_html(
            title=title,
            marker=session.config.getoption("-m") or "(none - all collected tests)",
            reports=reports,
        ),
        encoding="utf-8",
    )
