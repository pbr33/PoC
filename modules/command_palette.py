# ═══════════════════════════════════════════════════════════════════════
#  COMMAND PALETTE (Ctrl+K)
# ═══════════════════════════════════════════════════════════════════════
import streamlit as st


def inject_command_palette():
    """Inject a Ctrl+K command palette into the Streamlit parent document."""
    commands_js = """[
      {g:"Navigate", icon:"⚡", label:"Business Estimation", hint:"Main tab"},
      {g:"Navigate", icon:"🗂️", label:"Run Library", hint:"Main tab"},
      {g:"Navigate", icon:"⚙️", label:"Admin & Training", hint:"Main tab"},
      {g:"Results",  icon:"📋", label:"Requirements",   hint:"Results tab"},
      {g:"Results",  icon:"⏱️", label:"Time",           hint:"Results tab"},
      {g:"Results",  icon:"💰", label:"Infra Cost",     hint:"Results tab"},
      {g:"Results",  icon:"⚠️", label:"Risk",           hint:"Results tab"},
      {g:"Results",  icon:"🏗️", label:"Architecture",   hint:"Results tab"},
      {g:"Results",  icon:"📐", label:"Diagrams",       hint:"Results tab"},
      {g:"Results",  icon:"📄", label:"Proposal",       hint:"Results tab"},
      {g:"Results",  icon:"📌", label:"Scope",          hint:"Results tab"},
      {g:"Results",  icon:"👥", label:"Team & Roles",   hint:"Results tab"},
      {g:"Results",  icon:"🎮", label:"3D View",        hint:"Results tab"},
      {g:"Results",  icon:"🎬", label:"Narrator",       hint:"Results tab"},
      {g:"Results",  icon:"💬", label:"Chat",           hint:"Results tab"},
      {g:"Results",  icon:"📚", label:"History",        hint:"Results tab"},
      {g:"Admin",    icon:"📊", label:"Dashboard",      hint:"Admin tab"},
      {g:"Admin",    icon:"🔧", label:"Config",         hint:"Admin tab"}
    ]"""

    st.components.v1.html(f"""<!DOCTYPE html><html><body style="margin:0">
<script>
(function(, ){{
  var p = window.parent;
  var pd = p.document;

  if (!pd.getElementById('cmdpal-style')) {{
    var s = pd.createElement('style');
    s.id = 'cmdpal-style';
    s.textContent = [
      '#cmdpal-overlay{{display:none;position:fixed;inset:0;background:rgba(10,14,26,.88);backdrop-filter:blur(10px);z-index:2147483647;align-items:flex-start;justify-content:center;padding-top:13vh}}',
      '#cmdpal-overlay.open{{display:flex}}',
      '#cmdpal-box{{background:#111827;border:1px solid #1e2a4a;border-radius:14px;width:560px;max-width:92vw;overflow:hidden;box-shadow:0 24px 80px rgba(0,0,0,.7);font-family:DM Sans,sans-serif}}',
      '#cmdpal-input{{width:100%;box-sizing:border-box;background:transparent;border:none;border-bottom:1px solid #1e2a4a;padding:16px 20px;font-size:1rem;color:#e2e8f0;outline:none;font-family:DM Sans,sans-serif}}',
      '#cmdpal-input::placeholder{{color:#64748b}}',
      '#cmdpal-list{{max-height:320px;overflow-y:auto;padding:6px 0;scrollbar-width:thin}}',
      '.cmd-group{{font-size:.68rem;color:#64748b;text-transform:uppercase;letter-spacing:.8px;padding:8px 20px 3px;font-family:JetBrains Mono,monospace}}',
      '.cmd-item{{display:flex;align-items:center;gap:10px;padding:9px 20px;cursor:pointer;transition:background .12s;color:#94a3b8;font-size:.88rem}}',
      '.cmd-item:hover,.cmd-item.cmd-active{{background:rgba(0,212,170,.09);color:#e2e8f0}}',
      '.cmd-icon{{font-size:.95rem;width:22px;text-align:center;flex-shrink:0}}',
      '.cmd-lbl{{flex:1}}',
      '.cmd-hint{{font-size:.68rem;color:#64748b;font-family:JetBrains Mono,monospace}}',
      '#cmdpal-footer{{padding:7px 20px;border-top:1px solid #1e2a4a;display:flex;gap:16px;font-size:.7rem;color:#64748b;font-family:JetBrains Mono,monospace}}'
    ].join('');
    pd.head.appendChild(s);
  }}

  if (!pd.getElementById('cmdpal-overlay')) {{
    var div = pd.createElement('div');
    div.id = 'cmdpal-overlay';
    div.innerHTML = '<div id="cmdpal-box">' +
      '<input id="cmdpal-input" placeholder="Search commands… (e.g. Requirements, Chat, 3D View)" autocomplete="off"/>' +
      '<div id="cmdpal-list"></div>' +
      '<div id="cmdpal-footer"><span>↑↓ navigate</span><span>↵ select</span><span>esc close</span></div>' +
      '</div>';
    pd.body.appendChild(div);
  }}

  var CMDS = {commands_js};
  var overlay = pd.getElementById('cmdpal-overlay');
  var input   = pd.getElementById('cmdpal-input');
  var list    = pd.getElementById('cmdpal-list');
  var activeIdx = 0;

  function navigate(label) {{
    var tabs = pd.querySelectorAll('[data-baseweb="tab"]');
    for (var i = 0; i < tabs.length; i++) {{
      if (tabs[i].textContent.trim().includes(label.replace(/[⚡🗂️⚙️📋⏱️💰⚠️🏗️📐📄📌👥🎮🎬💬📚📊🔧]/g,'').trim())) {{
        tabs[i].click(); break;
      }}
    }}
    close();
  }}

  function renderList(q) {{
    var filtered = CMDS.filter(function(c) {{
      return !q || c.label.toLowerCase().includes(q.toLowerCase()) || c.g.toLowerCase().includes(q.toLowerCase());
    }});
    activeIdx = 0;
    var html = '', lastGroup = '';
    filtered.forEach(function(c, i) {{
      if (c.g !== lastGroup) {{ html += '<div class="cmd-group">' + c.g + '</div>'; lastGroup = c.g; }}
      html += '<div class="cmd-item' + (i===0?' cmd-active':'') + '" data-label="' + c.label + '">' +
        '<span class="cmd-icon">' + c.icon + '</span><span class="cmd-lbl">' + c.label + '</span>' +
        '<span class="cmd-hint">' + c.hint + '</span></div>';
    }});
    list.innerHTML = html || '<div style="padding:20px;color:#64748b;text-align:center;font-size:.85rem">No results</div>';
    list.querySelectorAll('.cmd-item').forEach(function(el) {{
      el.addEventListener('click', function() {{ navigate(el.dataset.label); }});
    }});
  }}

  function updateActive(delta) {{
    var items = list.querySelectorAll('.cmd-item');
    if (!items.length) return;
    items[activeIdx].classList.remove('cmd-active');
    activeIdx = (activeIdx + delta + items.length) % items.length;
    items[activeIdx].classList.add('cmd-active');
    items[activeIdx].scrollIntoView({{block:'nearest'}});
  }}

  function open() {{ overlay.classList.add('open'); input.value=''; renderList(''); setTimeout(function(){{input.focus();}},50); }}
  function close() {{ overlay.classList.remove('open'); }}

  if (!p._cmdpalReady) {{
    p._cmdpalReady = true;
    pd.addEventListener('keydown', function(e) {{
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {{ e.preventDefault(); overlay.classList.contains('open') ? close() : open(); }}
      if (!overlay.classList.contains('open')) return;
      if (e.key === 'Escape') {{ close(); }}
      if (e.key === 'ArrowDown') {{ e.preventDefault(); updateActive(1); }}
      if (e.key === 'ArrowUp')   {{ e.preventDefault(); updateActive(-1); }}
      if (e.key === 'Enter') {{ var items = list.querySelectorAll('.cmd-item'); if (items[activeIdx]) navigate(items[activeIdx].dataset.label); }}
    }});
    overlay.addEventListener('click', function(e) {{ if (e.target === overlay) close(); }});
  }}
  input.addEventListener('input', function() {{ renderList(input.value); activeIdx=0; }});
}})();
</script>
</body></html>""", height=0)
