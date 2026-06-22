"""
Run this script once after installing or upgrading Streamlit
to replace Streamlit branding with ECI in the static index.html.

Usage:
    python patch_streamlit_branding.py
"""
import os, re, shutil, sys

try:
    import streamlit
except ImportError:
    sys.exit("Streamlit not found — install it first.")

INDEX = os.path.join(os.path.dirname(streamlit.__file__), "static", "index.html")
BAK   = INDEX + ".eci_bak"

with open(INDEX, "r", encoding="utf-8") as f:
    html = f.read()

if "eci-init-cover" in html:
    print("ECI patch already applied. Nothing to do.")
    sys.exit(0)

# Backup original
if not os.path.exists(BAK):
    shutil.copy2(INDEX, BAK)
    print(f"Backup: {BAK}")

# 1. Page title
html = re.sub(r"<title>[^<]*</title>", "<title>ECI Presale Intelligence</title>", html)

# 2. Favicon -> ECI teal "E" SVG
ECI_FAVICON = (
    "data:image/svg+xml,"
    "<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 32 32%22>"
    "<rect width=%2232%22 height=%2232%22 rx=%226%22 fill=%22%230a0e1a%22/>"
    "<text x=%2216%22 y=%2222%22 font-family=%22sans-serif%22 font-weight=%22800%22"
    " font-size=%2217%22 fill=%22%2300d4aa%22 text-anchor=%22middle%22>E</text></svg>"
)
html = re.sub(r'href="[^"]*favicon[^"]*"', f'href="{ECI_FAVICON}"', html)

# 3. ECI loading overlay — visible immediately, removed when React renders #root
ECI_COVER = """\
    <div id="eci-init-cover" style="position:fixed;inset:0;z-index:2147483647;background:#0a0e1a;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:sans-serif;">
      <div style="font-size:2.6rem;font-weight:800;color:#00d4aa;letter-spacing:.06em">ECI</div>
      <div style="font-size:.9rem;color:#94a3b8;margin-top:6px;letter-spacing:.22em;text-transform:uppercase">Presale Intelligence</div>
      <div style="margin-top:28px;width:180px;height:3px;background:#1e2a3a;border-radius:2px;overflow:hidden">
        <div id="eci-bar" style="height:100%;width:0%;background:linear-gradient(90deg,#00d4aa,#7b61ff)"></div>
      </div>
    </div>
    <style>
      @keyframes eci-pulse{0%,100%{opacity:.6}50%{opacity:1}}
      #eci-init-cover div:first-child{animation:eci-pulse 2s ease-in-out infinite}
    </style>
    <script>
      (function(){
        var bar=document.getElementById("eci-bar");
        var pct=0;
        var iv=setInterval(function(){pct=Math.min(pct+(100-pct)*0.04+0.3,92);bar.style.width=pct+"%";},80);
        var obs=new MutationObserver(function(){
          var root=document.getElementById("root");
          if(root&&root.children.length>0){
            clearInterval(iv);bar.style.width="100%";
            var cover=document.getElementById("eci-init-cover");
            if(cover){cover.style.transition="opacity 0.4s ease";cover.style.opacity="0";setTimeout(function(){cover.remove();},450);}
            obs.disconnect();
          }
        });
        obs.observe(document.body,{childList:true,subtree:true});
      })();
    </script>
"""
html = html.replace("    <noscript>", ECI_COVER + "    <noscript>")

with open(INDEX, "w", encoding="utf-8") as f:
    f.write(html)

print("ECI patch applied successfully.")
print(f"  Title  : ECI Presale Intelligence")
print(f"  Favicon: ECI teal SVG")
print(f"  Cover  : ECI loading overlay injected into body")
