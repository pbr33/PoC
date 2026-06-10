# ═══════════════════════════════════════════════════════════════════════
#  ECI BRANDING CONSTANTS + CSS
# ═══════════════════════════════════════════════════════════════════════
import streamlit as st

ECI_BLUE = (27, 58, 92)
ECI_LIGHT_BLUE = (214, 228, 240)
ECI_ACCENT = (0, 180, 216)
ECI_GREEN = (0, 212, 170)
ECI_DARK = (10, 14, 26)
ECI_TEXT = (30, 30, 30)
ECI_GRAY = (100, 100, 100)

ECI_LOGO_BLUE_B64 = "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"
ECI_LOGO_WHITE_B64 = "iVBORw0KGgoAAAANSUhEUgAAAMgAAABGCAYAAACJ4ts2AAADvElEQVR4nO3dza9dUxzG8e+vJV6Cq5WQklTrPbgxaMplYkAHN4RBhaRNaiANgw6uob/A8EqIaBoTikGplBAJIpKiBgYGqqFRAy+9BqUvIlfVY7COSZP2rLvvXj13rfN8kjP77bWfs09+Z5/9ctYGMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzM7NGxKgDnAuSVgD3AXcCk8C1wFXAxcD5wAngGPAbsB/4Bvgc+CIi/hlFZqucpJdU1t5F5lsuaaOkDyWd7JjhqKRdkqYlLethe8ws5j3ZuXfWD71Wkh4i7QXeBO4Hzus41GXAI8D7wEFJq/pJaLVoqkEkTUh6HdgD3Nzz8GuBiZ7HtCWu6zfrkiNpNemb/rZRZ7F2NNEgkq4GPgXWjDiKNab6BpF0IWnPsSZzkSPA28A7wAHgMDAPXDF43QFMkc563dJzXBsXS+WsjaQXM89InZL0gtIp39yxpyTtkDQ/GOOMDbNUtof1q+qDdEnrgacySk8Bj0fEtoj4PXf8iNgXEVtJe5I3gH+7JbVa1f4T61nyLnY+GRE7u64kIg4Bm7oub/Wqdg8iaZJ0nDDMexHxcuk81qZqGwTYklEjYKZwDmtYzQ3ycEbNRxFxsHgSa1aVDSLpSuDGjNLXSmextlXZIMC6zLp9RVNY80o3yGzmNYrTHRgy7nUZ6z4GfNfDe7AxVuse5JqMml8iQsWTWNNqbZBLM2qOFk9hzau1QS7IqDlePIU1r9YGmc+ouaR4CmtertQGOSmj5nLRIax9pRvk6ehm2G3mP2esexXwW9IZpUNKp7ABuSfoBuReoCJjLrcAAAAASUVORK5CYII="


def inject_css():
    st.markdown("""<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600;700&family=DM+Sans:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');
    :root{--bg0:#0a0e1a;--bg1:#111827;--bg2:#151c2e;--bd:#1e2a4a;--t1:#e2e8f0;--t2:#94a3b8;--t3:#64748b;--c1:#00d4aa;--c2:#00b4d8;--c3:#7b61ff;--c4:#ff6b6b;--c5:#ffd166;--c6:#06d6a0;--gc:rgba(0,212,170,.15);--gp:rgba(123,97,255,.15)}
    .stApp{background:var(--bg0)!important}
    .main .block-container{padding-top:1rem;max-width:100%}
    section[data-testid="stSidebar"]{background:linear-gradient(180deg,#0d1321,#111827)!important;border-right:1px solid var(--bd)}
    .logo-box{display:flex;align-items:center;gap:12px}
    .logo-icon{font-size:2.2rem;background:linear-gradient(135deg,var(--c1),var(--c3));-webkit-background-clip:text;-webkit-text-fill-color:transparent;filter:drop-shadow(0 0 12px var(--gc))}
    .logo-txt{font-family:'Space Grotesk',sans-serif;font-size:1.8rem;font-weight:700;background:linear-gradient(135deg,var(--c1),var(--c2));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
    .logo-sub{font-family:'DM Sans',sans-serif;font-size:.7rem;color:var(--t2);letter-spacing:2px;text-transform:uppercase}
    .tagline{text-align:center;font-family:'DM Sans',sans-serif;color:var(--t2);font-size:.85rem;padding-top:.8rem}
    .dt{text-align:right;font-family:'JetBrains Mono',monospace;color:var(--t3);font-size:.8rem;padding-top:1rem}
    .stitle{font-family:'Space Grotesk',sans-serif;font-size:1.3rem;font-weight:600;color:var(--t1);margin-bottom:1rem;padding-bottom:.5rem;border-bottom:1px solid var(--bd)}
    .csec{font-family:'DM Sans',sans-serif;font-size:.9rem;font-weight:600;color:var(--c1);margin:.8rem 0 .4rem;letter-spacing:.5px}
    .cstat{background:var(--bg2);border-radius:8px;padding:12px;border:1px solid var(--bd)}
    .srow{display:flex;align-items:center;gap:8px;padding:4px 0;font-family:'DM Sans',sans-serif;font-size:.82rem;color:var(--t2)}
    .sdot{width:8px;height:8px;border-radius:50%;display:inline-block}
    .sdot.on{background:var(--c6);box-shadow:0 0 6px var(--c6)}.sdot.off{background:var(--t3)}
    .shdr{font-family:'Space Grotesk',sans-serif;font-size:1.3rem;font-weight:600;color:var(--t1);margin:1.5rem 0 1rem;display:flex;align-items:center;gap:10px}
    .shdr-i{font-size:1.4rem}
    .phdr{font-family:'Space Grotesk',sans-serif;font-size:1.1rem;font-weight:600;color:var(--c1);text-align:center;padding:12px;background:linear-gradient(135deg,var(--gc),var(--gp));border-radius:8px;margin-bottom:1rem;border:1px solid var(--bd)}
    .crd{background:var(--bg2);border:1px solid var(--bd);border-radius:12px;padding:1.2rem;margin-bottom:.8rem;transition:border-color .3s}
    .crd:hover{border-color:var(--c1)}
    .crd-t{font-family:'Space Grotesk',sans-serif;font-size:1.05rem;font-weight:600;color:var(--t1);margin-bottom:.3rem}
    .crd-d{font-family:'DM Sans',sans-serif;font-size:.82rem;color:var(--t2);margin-bottom:.8rem}
    .kpi{background:var(--bg2);border:1px solid var(--bd);border-radius:12px;padding:1.2rem;text-align:center;transition:all .3s}
    .kpi:hover{border-color:var(--c1);box-shadow:0 0 20px var(--gc);transform:translateY(-2px)}
    .kpi-i{font-size:1.8rem;margin-bottom:.4rem}
    .kpi-v{font-family:'JetBrains Mono',monospace;font-size:1.5rem;font-weight:700;color:var(--c1)}
    .kpi-t{font-family:'DM Sans',sans-serif;font-size:.85rem;font-weight:600;color:var(--t1);margin-top:.2rem}
    .kpi-s{font-family:'DM Sans',sans-serif;font-size:.72rem;color:var(--t3)}
    .alog{display:flex;align-items:center;gap:12px;padding:6px 12px;background:var(--bg2);border-radius:6px;margin-bottom:4px;border-left:3px solid var(--c1)}
    .abadge{font-family:'JetBrains Mono',monospace;font-size:.78rem;font-weight:600;color:var(--c2);min-width:160px}
    .aok{color:var(--c6);font-size:.8rem;font-weight:500;min-width:90px}
    .adet{font-family:'DM Sans',sans-serif;color:var(--t2);font-size:.8rem}
    .rch{font-family:'Space Grotesk',sans-serif;font-size:.95rem;font-weight:600;padding:8px 12px;border-radius:8px;margin-bottom:.8rem}
    .rch.fn{background:rgba(0,212,170,.1);color:var(--c1);border:1px solid rgba(0,212,170,.2)}
    .rch.nf{background:rgba(0,180,216,.1);color:var(--c2);border:1px solid rgba(0,180,216,.2)}
    .rch.ig{background:rgba(123,97,255,.1);color:var(--c3);border:1px solid rgba(123,97,255,.2)}
    .ri{background:var(--bg2);border:1px solid var(--bd);border-radius:8px;padding:10px 12px;margin-bottom:6px;font-family:'DM Sans',sans-serif;font-size:.82rem;color:var(--t2)}
    .ri strong{color:var(--t1);font-size:.85rem}
    .ri-c{font-family:'JetBrains Mono',monospace;font-size:.7rem;color:var(--c5);margin-top:2px}
    .ttag{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
    .tt{font-family:'JetBrains Mono',monospace;font-size:.72rem;background:var(--bg2);border:1px solid var(--c3);color:var(--c3);padding:3px 10px;border-radius:12px}
    .rsb{background:var(--bg2);padding:16px 20px;border-radius:10px;display:flex;align-items:center;gap:16px;margin-bottom:1rem}
    .rsv{font-family:'JetBrains Mono',monospace;font-size:2rem;font-weight:700;color:var(--t1)}
    .rsl{font-family:'DM Sans',sans-serif;font-size:1rem;color:var(--t2)}
    .rc{background:var(--bg2);border:1px solid var(--bd);border-radius:8px;padding:14px;margin-bottom:8px}
    .rch2{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
    .rch2 strong{color:var(--t1);font-family:'DM Sans',sans-serif}
    .rsev{font-family:'JetBrains Mono',monospace;font-size:.78rem;font-weight:600}
    .rc p{color:var(--t2);font-size:.82rem;margin:4px 0}
    .rmit{font-size:.8rem;color:var(--c6)}
    .ac{background:var(--bg2);border:1px solid var(--bd);border-radius:10px;padding:14px;margin-bottom:10px;transition:all .3s}
    .ac:hover{border-color:var(--c3);box-shadow:0 0 16px var(--gp)}
    .acn{font-family:'Space Grotesk',sans-serif;font-size:.95rem;font-weight:600;color:var(--t1)}
    .act{font-family:'JetBrains Mono',monospace;font-size:.7rem;color:var(--c3);margin-bottom:6px}
    .acs{font-family:'DM Sans',sans-serif;font-size:.8rem;color:var(--t2);padding-left:16px}
    .acs li{margin-bottom:2px}
    .dfv{font-family:'JetBrains Mono',monospace;font-size:.85rem;color:var(--c1);background:var(--bg2);padding:12px 16px;border-radius:8px;border:1px solid var(--bd);text-align:center;letter-spacing:.5px}
    .ls{background:var(--bg2);border:1px solid var(--bd);border-radius:10px;padding:16px 12px;text-align:center;min-height:160px}
    .ln{display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:50%;font-family:'JetBrains Mono',monospace;font-size:1rem;font-weight:700;color:#fff;margin-bottom:8px}
    .lt{font-family:'Space Grotesk',sans-serif;font-size:.88rem;font-weight:600;color:var(--t1);margin-bottom:6px}
    .ld{font-family:'DM Sans',sans-serif;font-size:.72rem;color:var(--t2);line-height:1.4}
    .mc{background:var(--bg2);border:1px solid var(--bd);border-radius:10px;padding:16px;text-align:center;min-height:120px}
    .mi{font-size:1.6rem;margin-bottom:6px}
    .mt{font-family:'Space Grotesk',sans-serif;font-size:.85rem;font-weight:600;color:var(--t1);margin-bottom:4px}
    .md2{font-family:'DM Sans',sans-serif;font-size:.72rem;color:var(--t2);line-height:1.3}
    button[data-testid="stBaseButton-primary"]{background:linear-gradient(135deg,var(--c1),var(--c2))!important;color:#0a0e1a!important;font-family:'DM Sans',sans-serif!important;font-weight:600!important;border:none!important;border-radius:8px!important}
    button[data-testid="stBaseButton-primary"]:hover{box-shadow:0 0 20px var(--gc)!important}
    button[data-testid="stBaseButton-secondary"]{background:var(--bg2)!important;color:var(--t1)!important;border:1px solid var(--bd)!important;border-radius:8px!important}
    .stTabs [data-baseweb="tab-list"]{gap:4px;background:var(--bg1);padding:4px;border-radius:10px}
    .stTabs [data-baseweb="tab"]{background:transparent;color:var(--t2);border-radius:8px;padding:8px 16px;font-family:'DM Sans',sans-serif;font-size:.85rem}
    .stTabs [data-baseweb="tab"][aria-selected="true"]{background:var(--bg2)!important;color:var(--c1)!important}
    .stTabs [data-baseweb="tab-highlight"]{display:none}
    [data-testid="stFileUploader"]{background:var(--bg2);border:1px dashed var(--bd);border-radius:10px;padding:1rem}
    [data-testid="stMetric"]{background:var(--bg2);border:1px solid var(--bd);border-radius:10px;padding:12px 16px}
    [data-testid="stMetricValue"]{font-family:'JetBrains Mono',monospace!important;color:var(--c1)!important}
    #MainMenu{visibility:hidden}footer{visibility:hidden}
    header[data-testid="stHeader"]{background:rgba(10,14,26,.95);backdrop-filter:blur(10px)}
    ::-webkit-scrollbar{width:6px}::-webkit-scrollbar-track{background:var(--bg0)}::-webkit-scrollbar-thumb{background:var(--bd);border-radius:3px}
    .stMarkdown p,.stMarkdown li,.stMarkdown span:not(.tt),.stMarkdown label{color:var(--t1)!important}
    .stMarkdown strong,.stMarkdown b{color:#ffffff!important}
    .stMarkdown em,.stMarkdown i{color:var(--t2)!important}
    .stMarkdown h1,.stMarkdown h2,.stMarkdown h3,.stMarkdown h4,.stMarkdown h5{color:var(--t1)!important}
    .stMarkdown a{color:var(--c2)!important}
    .stMarkdown code{color:var(--c5)!important;background:var(--bg2)!important}
    [data-testid="stExpander"] summary p,[data-testid="stExpander"] summary span{color:var(--t1)!important}
    [data-testid="stExpander"] details summary{color:var(--t1)!important}
    [data-testid="stProgressBar"]>div{background:linear-gradient(90deg,var(--c1),var(--c3),var(--c1))!important;background-size:200% 100%!important;animation:pb-shimmer 2s linear infinite;box-shadow:0 0 10px var(--c1)!important;transition:width .3s ease}
    @keyframes pb-shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
    .kpi-glow{background:linear-gradient(var(--bg2),var(--bg2)) padding-box,linear-gradient(135deg,var(--c1) 0%,var(--c3) 50%,var(--c1) 100%) border-box;border:1.5px solid transparent!important;background-size:200%;animation:kpi-border 4s linear infinite}
    @keyframes kpi-border{0%{background-position:0% 50%}100%{background-position:200% 50%}}
    .toast{position:fixed;bottom:24px;right:24px;z-index:9999;background:var(--bg2);border-radius:10px;padding:13px 20px;font-family:'DM Sans',sans-serif;font-size:.88rem;color:var(--t1);box-shadow:0 4px 32px rgba(0,0,0,.5);max-width:360px;animation:toast-anim 5s ease forwards;pointer-events:none}
    .toast.success{border-left:3px solid var(--c6)}.toast.error{border-left:3px solid var(--c4)}.toast.info{border-left:3px solid var(--c2)}.toast.warn{border-left:3px solid var(--c5)}
    @keyframes toast-anim{0%{opacity:0;transform:translateX(80px)}8%{opacity:1;transform:translateX(0)}80%{opacity:1}100%{opacity:0;transform:translateX(80px)}}
    .skeleton{background:linear-gradient(90deg,var(--bg2) 25%,rgba(255,255,255,.04) 50%,var(--bg2) 75%);background-size:200% 100%;animation:sk-anim 1.5s infinite;border-radius:10px}
    @keyframes sk-anim{0%{background-position:200% 0}100%{background-position:-200% 0}}
    .sk-kpi{height:110px}.sk-row{height:18px;margin-bottom:8px}.sk-row.w80{width:80%}.sk-row.w60{width:60%}.sk-row.w40{width:40%}
    .pipe-stepper{display:flex;align-items:center;overflow-x:auto;padding:14px 0;margin-bottom:10px;scrollbar-width:none}.pipe-stepper::-webkit-scrollbar{display:none}
    .ps-step{display:flex;align-items:center;gap:5px;white-space:nowrap}
    .ps-dot{width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-family:'JetBrains Mono',monospace;font-size:.7rem;font-weight:700;flex-shrink:0;transition:all .4s}
    .ps-dot.done{background:var(--c6);color:#0a0e1a}.ps-dot.active{background:var(--c1);color:#0a0e1a;box-shadow:0 0 12px var(--c1);animation:ps-pulse 1s ease-in-out infinite}.ps-dot.pend{background:var(--bg2);border:1px solid var(--bd);color:var(--t3)}
    @keyframes ps-pulse{0%,100%{box-shadow:0 0 10px var(--c1)}50%{box-shadow:0 0 22px var(--c1),0 0 40px var(--gc)}}
    .ps-lbl{font-family:'DM Sans',sans-serif;font-size:.72rem;color:var(--t3);transition:color .4s}.ps-lbl.done{color:var(--c6)}.ps-lbl.active{color:var(--t1);font-weight:600}
    .ps-conn{width:18px;height:2px;flex-shrink:0;transition:background .4s}.ps-conn.done{background:var(--c6)}.ps-conn.pend{background:var(--bd)}
    .stApp::before{content:'';position:fixed;top:0;left:0;right:0;bottom:0;background:radial-gradient(ellipse 60% 50% at 15% 40%,rgba(0,212,170,.04) 0%,transparent 60%),radial-gradient(ellipse 60% 50% at 85% 60%,rgba(123,97,255,.04) 0%,transparent 60%);animation:ambient-shift 10s ease-in-out infinite alternate;pointer-events:none;z-index:0}
    @keyframes ambient-shift{0%{opacity:.6}100%{opacity:1}}
    .kpi-v{animation:kpi-appear .5s ease both}
    @keyframes kpi-appear{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
    @keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
    @keyframes bounce-arr{0%,100%{transform:translateY(0);opacity:.5}50%{transform:translateY(-7px);opacity:1}}
    @keyframes blink-dot{0%,80%,100%{opacity:.25;transform:scale(.85)}40%{opacity:1;transform:scale(1)}}
    @keyframes fade-in-up{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
    .home-stats{display:flex;align-items:center;justify-content:center;gap:2.5rem;flex-wrap:wrap;padding:1.1rem 2rem;background:linear-gradient(135deg,var(--gc),var(--gp));border:1px solid var(--bd);border-radius:12px;margin-bottom:1.4rem;animation:fade-in-up .5s ease}
    .hs-item{text-align:center}
    .hs-n{font-family:'JetBrains Mono',monospace;font-size:1.7rem;font-weight:700;color:var(--c1);display:block}
    .hs-l{font-family:'DM Sans',sans-serif;font-size:.72rem;color:var(--t3);text-transform:uppercase;letter-spacing:.6px}
    .hs-sep{width:1px;height:36px;background:var(--bd)}
    .empty-state{text-align:center;padding:2.5rem 1rem;animation:fade-in-up .5s ease}
    .es-icon{font-size:3.8rem;display:inline-block;animation:float 3s ease-in-out infinite;line-height:1}
    .es-arr{font-size:1.8rem;display:inline-block;animation:bounce-arr 1.4s ease-in-out infinite;margin-top:-.4rem}
    .es-title{font-family:'Space Grotesk',sans-serif;font-size:1.1rem;font-weight:600;color:var(--t1);margin:.8rem 0 .3rem}
    .es-sub{font-family:'DM Sans',sans-serif;font-size:.84rem;color:var(--t2);line-height:1.5;max-width:360px;margin:0 auto}
    .typing-dots{display:flex;justify-content:center;gap:6px;margin:.6rem 0}
    .typing-dots span{width:8px;height:8px;border-radius:50%;background:var(--c1);animation:blink-dot 1.4s infinite}
    .typing-dots span:nth-child(2){animation-delay:.2s}
    .typing-dots span:nth-child(3){animation-delay:.4s}
    #cmdpal-overlay{display:none;position:fixed;inset:0;background:rgba(10,14,26,.88);backdrop-filter:blur(10px);z-index:2147483647;align-items:flex-start;justify-content:center;padding-top:13vh}
    #cmdpal-overlay.open{display:flex}
    #cmdpal-box{background:#111827;border:1px solid #1e2a4a;border-radius:14px;width:560px;max-width:92vw;overflow:hidden;box-shadow:0 24px 80px rgba(0,0,0,.7);font-family:'DM Sans',sans-serif}
    #cmdpal-input{width:100%;background:transparent;border:none;border-bottom:1px solid #1e2a4a;padding:16px 20px;font-size:1rem;color:#e2e8f0;outline:none;font-family:'DM Sans',sans-serif}
    #cmdpal-input::placeholder{color:#64748b}
    #cmdpal-list{max-height:320px;overflow-y:auto;padding:6px 0}
    #cmdpal-list::-webkit-scrollbar{width:4px}#cmdpal-list::-webkit-scrollbar-thumb{background:#1e2a4a;border-radius:2px}
    .cmd-group{font-size:.7rem;color:#64748b;text-transform:uppercase;letter-spacing:.8px;padding:8px 20px 4px;font-family:'JetBrains Mono',monospace}
    .cmd-item{display:flex;align-items:center;gap:12px;padding:9px 20px;cursor:pointer;transition:background .15s;color:#94a3b8;font-size:.9rem}
    .cmd-item:hover,.cmd-item.active{background:rgba(0,212,170,.08);color:#e2e8f0}
    .cmd-item-icon{font-size:1rem;width:22px;text-align:center;flex-shrink:0}
    .cmd-item-label{flex:1}
    .cmd-item-hint{font-size:.72rem;color:#64748b;font-family:'JetBrains Mono',monospace}
    #cmdpal-footer{padding:8px 20px;border-top:1px solid #1e2a4a;display:flex;gap:16px;font-size:.72rem;color:#64748b;font-family:'JetBrains Mono',monospace}
    </style>""", unsafe_allow_html=True)
