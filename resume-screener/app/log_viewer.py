from pathlib import Path

LOG_FILE = Path(__file__).parent.parent / "logs" / "app.log"

LOG_UI_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Resume Screener — Logs</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0d1117; color: #c9d1d9; font-family: 'Courier New', monospace; font-size: 13px; }}
    header {{ background: #161b22; padding: 14px 24px; border-bottom: 1px solid #30363d;
              display: flex; align-items: center; justify-content: space-between; }}
    header h1 {{ font-size: 16px; color: #58a6ff; letter-spacing: 1px; }}
    #controls {{ display: flex; gap: 12px; align-items: center; padding: 10px 24px;
                 background: #161b22; border-bottom: 1px solid #30363d; flex-wrap: wrap; }}
    #filter {{ background: #0d1117; border: 1px solid #30363d; color: #c9d1d9;
               padding: 5px 10px; border-radius: 6px; width: 220px; font-size: 13px; }}
    .btn {{ background: #21262d; border: 1px solid #30363d; color: #c9d1d9;
            padding: 5px 14px; border-radius: 6px; cursor: pointer; font-size: 12px; }}
    .btn:hover {{ background: #30363d; }}
    .btn.active {{ background: #388bfd; border-color: #388bfd; color: #fff; }}
    #status {{ font-size: 11px; color: #8b949e; margin-left: auto; }}
    #log-container {{ padding: 16px 24px; overflow-y: auto; height: calc(100vh - 110px); }}
    .log-line {{ padding: 2px 0; border-bottom: 1px solid #161b22; white-space: pre-wrap; word-break: break-all; }}
    .log-line.ERROR, .log-line.CRITICAL {{ color: #ff7b72; }}
    .log-line.WARNING {{ color: #d29922; }}
    .log-line.SUCCESS {{ color: #3fb950; }}
    .log-line.INFO {{ color: #c9d1d9; }}
    .log-line.DEBUG {{ color: #8b949e; }}
    .highlight {{ background: #2d333b; border-left: 3px solid #388bfd; padding-left: 6px; }}
    #empty {{ color: #8b949e; text-align: center; margin-top: 40px; font-size: 14px; }}
  </style>
</head>
<body>
  <header>
    <h1>&#128203; Resume Screener — Live Logs</h1>
    <span id="status">Loading...</span>
  </header>
  <div id="controls">
    <input id="filter" type="text" placeholder="Search logs..." oninput="renderLogs()"/>
    <button class="btn active" onclick="setLevel('ALL', this)">ALL</button>
    <button class="btn" onclick="setLevel('INFO', this)">INFO</button>
    <button class="btn" onclick="setLevel('WARNING', this)">WARNING</button>
    <button class="btn" onclick="setLevel('ERROR', this)">ERROR</button>
    <button class="btn" onclick="clearDisplay()">Clear Display</button>
    <button class="btn" onclick="toggleAutoScroll(this)">Auto-scroll: ON</button>
  </div>
  <div id="log-container"><div id="empty">No logs yet.</div></div>

  <script>
    let allLines = [];
    let activeLevel = 'ALL';
    let autoScroll = true;

    function setLevel(level, btn) {{
      activeLevel = level;
      document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderLogs();
    }}

    function toggleAutoScroll(btn) {{
      autoScroll = !autoScroll;
      btn.textContent = 'Auto-scroll: ' + (autoScroll ? 'ON' : 'OFF');
    }}

    function clearDisplay() {{
      allLines = [];
      renderLogs();
    }}

    function levelOf(line) {{
      if (line.includes(' | ERROR | ') || line.includes(' | CRITICAL | ')) return 'ERROR';
      if (line.includes(' | WARNING | ')) return 'WARNING';
      if (line.includes(' | SUCCESS | ')) return 'SUCCESS';
      if (line.includes(' | DEBUG | ')) return 'DEBUG';
      return 'INFO';
    }}

    function renderLogs() {{
      const container = document.getElementById('log-container');
      const query = document.getElementById('filter').value.toLowerCase();
      const filtered = allLines.filter(l => {{
        if (activeLevel !== 'ALL' && levelOf(l) !== activeLevel) return false;
        if (query && !l.toLowerCase().includes(query)) return false;
        return true;
      }});

      if (filtered.length === 0) {{
        container.innerHTML = '<div id="empty">No matching logs.</div>';
        return;
      }}

      container.innerHTML = filtered.map(l => {{
        const lvl = levelOf(l);
        const hl = query && l.toLowerCase().includes(query) ? ' highlight' : '';
        const escaped = l.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
        return `<div class="log-line ${{lvl}}${{hl}}">${{escaped}}</div>`;
      }}).join('');

      if (autoScroll) container.scrollTop = container.scrollHeight;
    }}

    async function fetchLogs() {{
      try {{
        const res = await fetch('/logs/raw');
        if (!res.ok) throw new Error(res.status);
        const text = await res.text();
        const lines = text.split('\\n').filter(l => l.trim());
        allLines = lines;
        document.getElementById('status').textContent = `${{lines.length}} lines — ${{new Date().toLocaleTimeString()}}`;
        renderLogs();
      }} catch(e) {{
        document.getElementById('status').textContent = 'Error fetching logs: ' + e.message;
      }}
    }}

    fetchLogs();
    setInterval(fetchLogs, 3000);
  </script>
</body>
</html>
"""


def get_log_content() -> str:
    if not LOG_FILE.exists():
        return ""
    return LOG_FILE.read_text(encoding="utf-8", errors="replace")
