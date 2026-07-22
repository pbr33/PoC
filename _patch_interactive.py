"""Patch: replace _plotly_arch_diagram with full interactive HTML clickable diagram."""
import re, pathlib

TARGET = pathlib.Path("modules/diagrams.py")
src = TARGET.read_text(encoding="utf-8")

OLD_START = "def _plotly_arch_diagram(ar: dict, se: dict) -> None:\n    \"\"\"Solution Architecture — high-quality SVG + KPI strip + tech pills.\"\"\""
OLD_END   = "\n\ndef _plotly_workflow"

start_idx = src.index(OLD_START)
end_idx   = src.index(OLD_END, start_idx)

NEW_FUNC = '''def _plotly_arch_diagram(ar: dict, se: dict) -> None:
    """Interactive Solution Architecture — clickable node cards, animated connections, slide-up detail panel."""
    import json as _jj

    comps  = safe_list(ar.get("components", []))
    flow   = safe_list(ar.get("data_flow", []))
    sec    = safe_list(ar.get("security", []))
    tech   = safe_list(se.get("technology_stack", []))
    proj   = safe_str(se.get("project_type", "Enterprise Solution"))

    TIER_DEF = [
        ("External",       "#06b6d4", "👤", ["client","user","browser","mobile","external","webhook","third-party"]),
        ("Presentation",   "#a78bfa", "🎨", ["ui ","frontend","web app","portal","dashboard","react","angular","spa","teams","copilot studio","power bi"]),
        ("API / Gateway",  "#0078d4", "⚡", ["api management","apim","front door","cdn","gateway","load bal","signalr"]),
        ("Application",    "#00b294", "⚙️",  ["app service","function","container","backend","logic app","service bus","event grid"]),
        ("AI & Cognitive", "#e040fb", "🤖", ["openai","gpt","ai search","cognitive","foundry","claude","ml","embedding","vector","rag"]),
        ("Data & Storage", "#22c55e", "🗄️", ["sql","cosmos","blob","storage","database","redis","cache","sharepoint","data lake"]),
        ("Security",       "#f97316", "🔒", ["key vault","entra","active dir","defender","firewall","mfa","identity","azure ad","policy"]),
        ("Monitoring",     "#facc15", "📊", ["monitor","insights","analytics","devops","logging","observ"]),
    ]

    comp_data = []
    for idx, raw in enumerate(comps):
        c      = safe_dict(raw)
        name   = safe_str(c.get("name", f"Component {idx+1}"))
        desc   = safe_str(c.get("description", ""))
        ctype  = safe_str(c.get("type", ""))
        conns  = safe_list(c.get("connections", []))
        ctechs = safe_list(c.get("technology", []))
        search = (name + " " + desc + " " + ctype).lower()
        tier_name = "Application"; tier_color = "#00b294"; tier_icon = "⚙️"
        for tname, tcol, ticon, kws in TIER_DEF:
            if any(kw in search for kw in kws):
                tier_name = tname; tier_color = tcol; tier_icon = ticon; break
        comp_data.append({
            "id": f"c{idx}", "name": name, "type": ctype or tier_name,
            "desc": desc, "tier": tier_name, "color": tier_color, "icon": tier_icon,
            "conns": [safe_str(x) for x in conns],
            "techs": [safe_str(x) for x in ctechs],
        })

    flow_steps = []
    for f in flow[:14]:
        fs = safe_str(f) if isinstance(f, str) else safe_str(safe_dict(f).get("step", safe_str(f)))
        flow_steps.append(fs[:85])

    cj  = _jj.dumps(comp_data,   ensure_ascii=False)
    tj  = _jj.dumps([{"name":t[0],"color":t[1],"icon":t[2]} for t in TIER_DEF], ensure_ascii=False)
    fj  = _jj.dumps(flow_steps,  ensure_ascii=False)
    sj  = _jj.dumps([safe_str(s) for s in sec[:10]], ensure_ascii=False)
    thj = _jj.dumps([safe_str(t) for t in tech[:15]], ensure_ascii=False)
    nc  = len(comp_data); nf = len(flow_steps); ns = len(sec); nt = len(tech)
    pe  = proj.replace('"', "&quot;")

    html = (
        "<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'><style>\n"
        "*{margin:0;padding:0;box-sizing:border-box}\n"
        ":root{--bg:#07101f;--sur:#0d1b2e;--sur2:#101e33;--brd:#1e3654;--txt:#e2e8f0;--mut:#64748b}\n"
        "body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--txt);min-height:820px;overflow-x:hidden}\n"
        ".hdr{background:#0a1628;border-bottom:1px solid var(--brd);padding:12px 18px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}\n"
        ".htitle{font-size:1rem;font-weight:800;color:#e2e8f0;display:flex;align-items:center;gap:8px}\n"
        ".hbadge{font-size:.6rem;background:#0f2a4a;border:1px solid #0078d4;border-radius:20px;padding:2px 10px;color:#60a5fa;font-weight:700}\n"
        ".stats{display:flex;gap:14px;margin-left:auto}\n"
        ".stat{font-size:.68rem;color:var(--mut);text-align:center}\n"
        ".stat b{display:block;font-size:.95rem;color:#e2e8f0;font-weight:800}\n"
        ".srch{background:var(--sur2);border:1px solid var(--brd);border-radius:8px;padding:5px 12px;display:flex;align-items:center;gap:6px}\n"
        ".srch input{background:none;border:none;outline:none;color:var(--txt);font-size:.78rem;width:140px}\n"
        ".canvas{overflow-x:auto;padding:14px 18px;min-height:420px}\n"
        ".tier-row{display:flex;gap:8px;min-width:max-content;align-items:flex-start}\n"
        ".tier-col{display:flex;flex-direction:column;min-width:150px;max-width:168px}\n"
        ".tier-hd{font-size:.58rem;font-weight:800;letter-spacing:1px;text-transform:uppercase;padding:5px 8px;text-align:center;border-radius:7px 7px 0 0;margin-bottom:5px}\n"
        ".cards{display:flex;flex-direction:column;gap:5px}\n"
        ".card{background:var(--sur);border:1px solid var(--brd);border-radius:9px;padding:9px;cursor:pointer;"
        "transition:all .2s;position:relative;overflow:hidden}\n"
        ".card::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--tc);transition:width .18s}\n"
        ".card:hover{transform:translateY(-2px);box-shadow:0 6px 28px rgba(0,0,0,.45),0 0 14px var(--glow)}\n"
        ".card:hover::before{width:5px}\n"
        ".card.active{border-color:var(--tc);box-shadow:0 0 22px var(--glow)}\n"
        ".card.dimmed{opacity:.28;pointer-events:none}\n"
        ".cico{font-size:1.22rem;margin-bottom:3px;display:block}\n"
        ".cnm{font-size:.74rem;font-weight:700;color:#e2e8f0;line-height:1.2;margin-bottom:2px}\n"
        ".cty{font-size:.57rem;color:var(--mut);text-transform:uppercase;letter-spacing:.3px}\n"
        ".cbadge{display:inline-block;font-size:.52rem;font-weight:700;padding:1px 6px;border-radius:10px;margin-top:4px}\n"
        ".arr{display:flex;align-items:center;padding-top:26px;opacity:.5;min-width:24px}\n"
        ".panel{position:fixed;bottom:0;left:0;right:0;background:linear-gradient(180deg,#0b1829,#071221);"
        "border-top:2px solid #1e3654;border-radius:14px 14px 0 0;"
        "transform:translateY(100%);transition:transform .32s cubic-bezier(.16,1,.3,1);z-index:999;max-height:54vh;overflow-y:auto}\n"
        ".panel.open{transform:translateY(0)}\n"
        ".drag{width:36px;height:4px;background:#1e3654;border-radius:2px;margin:9px auto 0}\n"
        ".ph{display:flex;align-items:center;gap:10px;padding:12px 18px 9px;border-bottom:1px solid #1e3654;"
        "position:sticky;top:0;background:#0b1829;z-index:1}\n"
        ".phico{font-size:1.85rem}.phnm{font-size:1rem;font-weight:800;color:#e2e8f0}\n"
        ".phsub{font-size:.63rem;color:#64748b;margin-top:1px}\n"
        ".phtr{font-size:.6rem;font-weight:700;padding:3px 10px;border-radius:12px;border:1px solid}\n"
        ".phcl{margin-left:auto;cursor:pointer;font-size:1.1rem;color:#64748b;padding:4px 8px;"
        "border-radius:6px;background:#101e33;border:1px solid #1e3654;transition:all .15s}\n"
        ".phcl:hover{color:#e2e8f0;border-color:#60a5fa}\n"
        ".pb{display:grid;grid-template-columns:2fr 1fr 1fr;gap:11px;padding:12px 18px 18px}\n"
        ".ps{background:var(--sur2);border:1px solid var(--brd);border-radius:9px;padding:11px}\n"
        ".plbl{font-size:.57rem;color:var(--mut);text-transform:uppercase;letter-spacing:1px;font-weight:700;margin-bottom:7px}\n"
        ".ptxt{font-size:.77rem;color:#cbd5e1;line-height:1.65}\n"
        ".trow{display:flex;flex-wrap:wrap;gap:4px}\n"
        ".tag{font-size:.62rem;padding:2px 8px;border-radius:10px;background:#0f2a4a;border:1px solid #1e4a80;color:#93c5fd}\n"
        ".ci{font-size:.72rem;color:#93c5fd;padding:2px 0;border-bottom:1px solid #1e3654;display:flex;align-items:center;gap:5px}\n"
        ".ci::before{content:'→';color:#0078d4}\n"
        ".fstrip{display:flex;gap:0;overflow-x:auto;padding:8px 18px;border-top:1px solid var(--brd);background:var(--sur);scrollbar-width:thin}\n"
        ".fstep{display:flex;align-items:center;flex-shrink:0}\n"
        ".fnode{font-size:.63rem;background:var(--bg);border:1px solid var(--brd);border-radius:6px;"
        "padding:4px 9px;color:#94a3b8;max-width:128px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n"
        ".farr{font-size:.85rem;color:#1e3654;padding:0 2px;flex-shrink:0}\n"
        ".lgnd{display:flex;flex-wrap:wrap;gap:6px;padding:7px 18px;border-top:1px solid var(--brd)}\n"
        ".li{display:flex;align-items:center;gap:4px;font-size:.6rem;color:var(--mut)}\n"
        ".ld{width:7px;height:7px;border-radius:2px}\n"
        "@keyframes fa{to{stroke-dashoffset:-20}}.fl{animation:fa 1s linear infinite}\n"
        "::-webkit-scrollbar{width:5px;height:5px}::-webkit-scrollbar-track{background:#07101f}"
        "::-webkit-scrollbar-thumb{background:#1e3654;border-radius:3px}\n"
        "</style></head><body>\n"
        f"<div class='hdr'>"
        f"<div class='htitle'>🏗️ Interactive Solution Architecture <span class='hbadge'>{pe}</span></div>"
        f"<div class='stats'>"
        f"<div class='stat'><b>{nc}</b>Services</div>"
        f"<div class='stat'><b>{nf}</b>Flow Steps</div>"
        f"<div class='stat'><b>{ns}</b>Security</div>"
        f"<div class='stat'><b>{nt}</b>Technologies</div>"
        f"</div>"
        "<div class='srch'>🔍 <input id='si' type='text' placeholder='Search…' oninput='filterCards(this.value)'></div>"
        "</div>\n"
        "<div class='canvas'><div class='tier-row' id='tr'></div></div>\n"
        "<div class='fstrip' id='fs'></div>\n"
        "<div class='lgnd' id='lg'></div>\n"
        "<div class='panel' id='pnl'><div class='drag'></div><div class='ph' id='ph'></div><div class='pb' id='pb'></div></div>\n"
        "<script>\n"
        f"const COMPS={cj};\n"
        f"const TIERS={tj};\n"
        f"const FLOWS={fj};\n"
        f"const SEC={sj};\n"
        f"const TECH={thj};\n"
        "let aid=null;\n"
        # legend
        "const lg=document.getElementById('lg');\n"
        "TIERS.forEach(t=>{\n"
        "  const n=COMPS.filter(c=>c.tier===t.name).length;\n"
        "  if(!n)return;\n"
        "  lg.innerHTML+=`<div class='li'><div class='ld' style='background:${t.color}'></div>${t.icon} ${t.name} (${n})</div>`;\n"
        "});\n"
        # flow strip
        "const fs=document.getElementById('fs');\n"
        "FLOWS.forEach((s,i)=>{\n"
        "  const d=document.createElement('div');\n"
        "  d.className='fstep';\n"
        "  d.innerHTML=(i>0?'<span class=\"farr\">→</span>':'')+`<div class='fnode' title='${s}'>${i+1}. ${s}</div>`;\n"
        "  fs.appendChild(d);\n"
        "});\n"
        # tier columns
        "const tr=document.getElementById('tr');\n"
        "const used=TIERS.filter(t=>COMPS.some(c=>c.tier===t.name));\n"
        "used.forEach((tier,ti)=>{\n"
        "  if(ti>0){\n"
        "    const a=document.createElement('div');\n"
        "    a.className='arr';\n"
        "    a.innerHTML=`<svg width='24' viewBox='0 0 24 60' fill='none'>"
        "<line x1='12' y1='0' x2='12' y2='44' stroke='${tier.color}' stroke-width='1.5' stroke-dasharray='4 3' class='fl'/>"
        "<polygon points='6,43 18,43 12,56' fill='${tier.color}' opacity='.7'/></svg>`;\n"
        "    tr.appendChild(a);\n"
        "  }\n"
        "  const tc=COMPS.filter(c=>c.tier===tier.name);\n"
        "  const col=document.createElement('div');\n"
        "  col.className='tier-col';\n"
        "  col.innerHTML=`<div class='tier-hd' style='background:${tier.color}20;color:${tier.color};border:1px solid ${tier.color}50'>${tier.icon} ${tier.name}</div><div class='cards' id='tc${ti}'></div>`;\n"
        "  tr.appendChild(col);\n"
        "  const cd=col.querySelector('.cards');\n"
        "  tc.forEach(comp=>{\n"
        "    const card=document.createElement('div');\n"
        "    card.className='card';\n"
        "    card.id='card-'+comp.id;\n"
        "    card.style.cssText=`--tc:${comp.color};--glow:${comp.color}44`;\n"
        "    card.dataset.nm=comp.name.toLowerCase();\n"
        "    card.innerHTML=`<span class='cico'>${comp.icon}</span><div class='cnm'>${comp.name}</div>"
        "<div class='cty'>${comp.type}</div>"
        "<span class='cbadge' style='background:${comp.color}22;color:${comp.color};border:1px solid ${comp.color}55'>${comp.tier}</span>`;\n"
        "    card.addEventListener('click',()=>openPanel(comp));\n"
        "    cd.appendChild(card);\n"
        "  });\n"
        "});\n"
        # openPanel
        "function openPanel(comp){\n"
        "  if(aid){const p=document.getElementById('card-'+aid);if(p)p.classList.remove('active');}\n"
        "  aid=comp.id;\n"
        "  const card=document.getElementById('card-'+comp.id);\n"
        "  if(card){card.classList.add('active');card.style.background=comp.color+'18';}\n"
        "  document.getElementById('ph').innerHTML=`"
        "<span class='phico'>${comp.icon}</span>"
        "<div><div class='phnm'>${comp.name}</div><div class='phsub'>${comp.type}</div></div>"
        "<span class='phtr' style='color:${comp.color};border-color:${comp.color};background:${comp.color}20'>${comp.tier}</span>"
        "<div class='phcl' onclick='closePanel()'>✕</div>`;\n"
        "  const connH=comp.conns.length>0\n"
        "    ?comp.conns.slice(0,6).map(x=>`<div class='ci'>${x}</div>`).join('')\n"
        "    :'<div style=\"color:#64748b;font-size:.75rem\">No connections documented</div>';\n"
        "  const techH=(comp.techs.length>0?comp.techs:[comp.tier,'Azure']).map(t=>`<span class='tag'>${t}</span>`).join('');\n"
        "  const secH=SEC.slice(0,5).map(s=>`<span class='tag'>${s}</span>`).join('')||'<span style=\"color:#64748b;font-size:.75rem\">—</span>';\n"
        "  const stackH=TECH.slice(0,8).map(t=>`<span class='tag'>${t}</span>`).join('');\n"
        "  document.getElementById('pb').innerHTML=`"
        "<div class='ps' style='grid-column:1/3'>"
        "<div class='plbl'>📋 Description</div>"
        "<div class='ptxt'>${comp.desc||'Core '+comp.tier+' component providing essential capabilities in the solution.'}</div>"
        "</div>"
        "<div class='ps' style='background:${comp.color}10;border-color:${comp.color}40'>"
        "<div class='plbl' style='color:${comp.color}'>⭐ Tier Role</div>"
        "<div class='ptxt'><strong style='color:${comp.color}'>${comp.tier}</strong> layer · ${comp.type||comp.name}"
        "<div class='trow' style='margin-top:8px'>${techH}</div></div>"
        "</div>"
        "<div class='ps' style='grid-column:1/2'>"
        "<div class='plbl'>🔗 Connections (${comp.conns.length})</div>"
        "<div class='ptxt'>${connH}</div>"
        "</div>"
        "<div class='ps' style='grid-column:2/4'>"
        "<div class='plbl'>🔒 Security Controls</div>"
        "<div class='trow'>${secH}</div>"
        "<div class='plbl' style='margin-top:10px'>🛠️ Full Tech Stack</div>"
        "<div class='trow'>${stackH}</div>"
        "</div>`;\n"
        "  document.getElementById('pnl').classList.add('open');\n"
        "}\n"
        "function closePanel(){\n"
        "  document.getElementById('pnl').classList.remove('open');\n"
        "  if(aid){const c=document.getElementById('card-'+aid);if(c){c.classList.remove('active');c.style.background='';};aid=null;}\n"
        "}\n"
        "function filterCards(q){\n"
        "  q=q.toLowerCase().trim();\n"
        "  document.querySelectorAll('.card').forEach(c=>{\n"
        "    c.classList.toggle('dimmed',q&&!c.dataset.nm.includes(q));\n"
        "  });\n"
        "}\n"
        "document.addEventListener('keydown',e=>{if(e.key==='Escape')closePanel();});\n"
        "</script></body></html>"
    )
    st.iframe(srcdoc=html, height=820, scrolling=True)'''

replacement = src[:start_idx] + NEW_FUNC + src[end_idx:]
TARGET.write_text(replacement, encoding="utf-8")
print(f"OK — replaced _plotly_arch_diagram ({end_idx-start_idx} chars → {len(NEW_FUNC)} chars)")
