"""Shared theme CSS + cached resources for every FutureForge page."""

import streamlit as st

from hybrid_pipeline import HybridPredictor
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATASET_PATH = BASE_DIR / "backend" / "data" / "dummy_behavior_data.csv"
ARTIFACT_DIR = BASE_DIR / "backend" / "data" / "artifacts"


@st.cache_resource(show_spinner="Loading AI engine…")
def load_predictor() -> HybridPredictor:
    return HybridPredictor(dataset_path=str(DATASET_PATH), artifact_dir=str(ARTIFACT_DIR))


DARK_VARS = """
    --bg-grad: radial-gradient(circle at 15% 8%, #1a1033 0%, #0b0b17 42%, #000000 100%);
    --text-main: #f5f5f7;
    --text-sub: #98989f;
    --card-bg: #1c1c1e;
    --card-bg-soft: rgba(255,255,255,0.05);
    --card-border: rgba(255,255,255,0.08);
    --sidebar-bg: rgba(18,18,20,0.92);
    --shadow: 0 1px 0 rgba(255,255,255,0.04) inset, 0 10px 30px rgba(0,0,0,0.45);
    --ring-track: rgba(255,255,255,0.08);
    --divider: rgba(255,255,255,0.08);
"""

LIGHT_VARS = """
    --bg-grad: radial-gradient(circle at 15% 8%, #f4f2ff 0%, #f2f2f7 45%, #ffffff 100%);
    --text-main: #1d1d1f;
    --text-sub: #6e6e73;
    --card-bg: #ffffff;
    --card-bg-soft: rgba(0,0,0,0.02);
    --card-border: rgba(0,0,0,0.06);
    --sidebar-bg: rgba(255,255,255,0.92);
    --shadow: 0 1px 2px rgba(0,0,0,0.04), 0 8px 24px rgba(0,0,0,0.06);
    --ring-track: rgba(0,0,0,0.07);
    --divider: rgba(0,0,0,0.07);
"""


def inject_theme() -> None:
    if "theme" not in st.session_state:
        st.session_state.theme = "dark"

    variables = DARK_VARS if st.session_state.theme == "dark" else LIGHT_VARS

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=Pacifico&display=swap');

        :root {{ {variables} }}

        html, body, [class*="css"] {{
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter', sans-serif;
        }}

        .stApp {{
            background: var(--bg-grad);
            color: var(--text-main);
        }}
        section[data-testid="stSidebar"] {{
            display: none !important;
            width: 0 !important;
            min-width: 0 !important;
        }}
        header[data-testid="stHeader"] {{
            display: none !important;
        }}
        section[data-testid="stSidebar"] + div {{
            width: 100% !important;
        }}
        div[data-testid="stAppViewContainer"] > .main .block-container {{
            padding-top: 0.4rem !important;
            padding-left: 1.5rem !important;
            padding-right: 1.5rem !important;
            max-width: 100% !important;
        }}
        .top-nav-shell {{
            position: sticky;
            top: 0;
            z-index: 1000;
            width: 100%;
            padding: 0.7rem 1.1rem 0.75rem;
            margin: 0 -1.5rem 1.1rem;
            background: rgba(9, 11, 18, 0.9);
            backdrop-filter: blur(18px);
            border-bottom: 1px solid var(--divider);
            box-shadow: 0 8px 26px rgba(0,0,0,0.12);
        }}
        .top-nav-inner {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.7rem;
            max-width: 100%;
            margin: 0 auto;
        }}
        .brand-shell {{
            display: inline-flex;
            align-items: center;
            gap: 0.55rem;
            min-width: max-content;
            padding-left: 0.15rem;
            margin-right: 0.2rem;
        }}
        .brand-mark {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 30px;
            height: 30px;
            border-radius: 10px;
            background: linear-gradient(135deg, #8b5cf6, #3b82f6);
            color: #fff;
            font-weight: 800;
            font-size: 0.82rem;
            box-shadow: 0 8px 18px rgba(124,58,237,0.35);
        }}
        .brand-text {{
            font-family: 'Pacifico', cursive;
            font-size: 1.6rem;
            letter-spacing: 0.04em;
            line-height: 1;
            color: var(--text-main);
            white-space: nowrap;
        }}
        .top-nav-menu {{
            display: flex;
            align-items: center;
            justify-content: center;
            flex-wrap: nowrap;
            gap: 0.5rem;
            width: 100%;
            overflow-x: auto;
            scrollbar-width: none;
            padding: 0.15rem 0.1rem;
        }}
        .top-nav-menu::-webkit-scrollbar {{ display: none; }}
        .top-nav-item {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.42rem 0.72rem;
            border-radius: 999px;
            color: var(--text-sub);
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.01em;
            text-decoration: none;
            white-space: nowrap;
            min-width: max-content;
            transition: all 0.18s ease;
        }}
        .top-nav-item:hover {{
            background: rgba(255,255,255,0.04);
            color: var(--text-main);
            text-decoration: none;
        }}
        .top-nav-item.active {{
            background: rgba(168, 85, 247, 0.18);
            color: #f5ecff;
            border: 1px solid rgba(192, 132, 252, 0.28);
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.06);
        }}
        .top-nav-right {{
            display: flex;
            align-items: center;
            gap: 0.6rem;
            margin-left: auto;
        }}
        .profile-shell {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.42rem 0.8rem;
            border-radius: 999px;
            background: rgba(255,255,255,0.03);
            border: 1px solid var(--card-border);
            min-width: 150px;
            max-width: 220px;
        }}
        .profile-avatar {{
            width: 22px;
            height: 22px;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 0.7rem;
            font-weight: 700;
            background: linear-gradient(135deg, #a78bfa, #60a5fa);
            color: white;
        }}
        .top-nav input {{
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            color: var(--text-main) !important;
            font-size: 0.82rem !important;
            padding: 0.15rem 0 !important;
            min-height: 20px !important;
        }}
        .top-nav input::placeholder {{ color: var(--text-sub) !important; }}
        .top-nav label {{ display: none !important; }}
        @media (max-width: 960px) {{
            .top-nav-shell {{ padding-left: 0.9rem; padding-right: 0.9rem; }}
            .brand-text {{ font-size: 1.35rem; }}
            .top-nav-item {{ padding: 0.45rem 0.7rem; font-size: 0.76rem; }}
            .profile-shell {{ min-width: 120px; }}
        }}
        @media (max-width: 760px) {{
            .top-nav-inner {{ flex-wrap: wrap; }}
            .top-nav-menu {{ justify-content: flex-start; width: 100%; overflow-x: auto; white-space: nowrap; }}
            .top-nav-right {{ width: 100%; justify-content: flex-end; }}
        }}
        h1, h2, h3, h4 {{ font-family: 'Space Grotesk', sans-serif !important; color: var(--text-main); letter-spacing: -0.01em; }}
        p, span, label, div {{ color: var(--text-main); }}
        * {{ scroll-behavior: smooth; }}
        ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        ::-webkit-scrollbar-thumb {{ background: var(--card-border); border-radius: 8px; }}

        /* ---------------------------------------------------------------
           Apple-Health-style Activity Rings
        --------------------------------------------------------------- */
        .ring-row {{ display:flex; gap: 22px; flex-wrap: wrap; margin: 10px 0 6px 0; }}
        .ring-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 20px;
            box-shadow: var(--shadow);
            padding: 16px 14px;
            display: flex; flex-direction: column; align-items: center;
            min-width: 118px; flex: 1;
            transition: transform 0.18s ease;
        }}
        .ring-card:hover {{ transform: translateY(-2px); }}
        .ring-wrap {{ position: relative; width: 84px; height: 84px; }}
        .ring-center {{
            position: absolute; inset: 0; display:flex; align-items:center; justify-content:center;
            font-size: 1.5rem; transform: none;
        }}
        .ring-value {{ font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:1.15rem; margin-top:8px; }}
        .ring-label {{ font-size:0.72rem; color: var(--text-sub); text-transform:uppercase; letter-spacing:0.8px; margin-top:2px; }}

        /* ---------------------------------------------------------------
           Focus Lab test grids (Attention Grid / Memory Sequence)
        --------------------------------------------------------------- */
        .grid-cell-idle {{
            background: var(--card-bg-soft); border: 1px solid var(--card-border); border-radius: 14px;
            transition: all 0.12s ease;
        }}
        .grid-cell-active {{
            background: linear-gradient(145deg, #34d399, #10b981);
            border: 1px solid #34d399; border-radius: 14px;
            box-shadow: 0 0 22px rgba(52,211,153,0.55);
        }}
        .grid-cell-memory {{
            background: linear-gradient(145deg, #a78bfa, #7c3aed);
            border: 1px solid #a78bfa; border-radius: 14px;
            box-shadow: 0 0 22px rgba(139,92,246,0.55);
        }}
        .grid-cell-wrong {{
            background: linear-gradient(145deg, #f87171, #dc2626);
            border: 1px solid #f87171; border-radius: 14px;
            box-shadow: 0 0 22px rgba(248,113,113,0.5);
        }}

        /* ---------------------------------------------------------------
           AI Coach chat
        --------------------------------------------------------------- */
        .coach-mode-badge {{
            display:inline-block; padding: 3px 12px; border-radius: 999px; font-size: 0.7rem;
            font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 10px;
        }}
        .coach-mode-generative {{ background: rgba(52,211,153,0.15); color:#34d399; border:1px solid rgba(52,211,153,0.35); }}
        .coach-mode-local {{ background: rgba(96,165,250,0.15); color:#60a5fa; border:1px solid rgba(96,165,250,0.35); }}

        .hero-title {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 2.3rem;
            font-weight: 700;
            background: linear-gradient(90deg, #a78bfa, #60a5fa, #34d399);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.1rem;
        }}
        .hero-sub {{ color: var(--text-sub); font-size: 0.92rem; margin-bottom: 1.3rem; }}

        .glass-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 20px;
            padding: 20px 22px;
            box-shadow: var(--shadow);
            margin-bottom: 16px;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }}
        .metric-label {{ font-size: 0.78rem; color: var(--text-sub); text-transform: uppercase; letter-spacing: 1px; }}
        .metric-value {{ font-family: 'Space Grotesk', sans-serif; font-size: 2rem; font-weight: 700; color: var(--text-main); }}
        .metric-delta-up {{ color: #34d399; font-size: 0.85rem; font-weight: 600; }}
        .metric-delta-down {{ color: #f87171; font-size: 0.85rem; font-weight: 600; }}

        .badge {{ display:inline-block; padding:4px 14px; border-radius:999px; font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:0.5px; }}
        .badge-low {{ background: rgba(52,211,153,0.18); color:#34d399; border:1px solid rgba(52,211,153,0.4);}}
        .badge-medium {{ background: rgba(251,191,36,0.18); color:#fbbf24; border:1px solid rgba(251,191,36,0.4);}}
        .badge-high {{ background: rgba(248,113,113,0.18); color:#f87171; border:1px solid rgba(248,113,113,0.4);}}
        .badge-moderate {{ background: rgba(251,191,36,0.18); color:#fbbf24; border:1px solid rgba(251,191,36,0.4);}}

        .priority-High {{ color:#f87171; font-weight:700; }}
        .priority-Medium {{ color:#fbbf24; font-weight:700; }}
        .priority-Low {{ color:#34d399; font-weight:700; }}

        .insight-card {{
            background: var(--card-bg);
            border-left: 3px solid #8b5cf6;
            border-radius: 12px;
            padding: 14px 16px;
            margin-bottom: 12px;
        }}
        .insight-title {{ font-family:'Space Grotesk', sans-serif; font-size:1.02rem; font-weight:600; color: var(--text-main); }}
        .insight-meta {{ font-size:0.73rem; color: var(--text-sub); margin-bottom:6px; }}
        .insight-row {{ font-size:0.86rem; color: var(--text-main); margin-bottom:3px; line-height:1.4; }}

        .achievement-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 16px;
            text-align: center;
            opacity: 1;
        }}
        .achievement-locked {{ opacity: 0.35; filter: grayscale(1); }}
        .achievement-icon {{ font-size: 2rem; }}

        .streak-pill {{
            display:inline-block; background: linear-gradient(90deg, rgba(251,146,60,0.18), rgba(248,113,113,0.12));
            border:1px solid rgba(251,146,60,0.4); border-radius: 999px; padding: 8px 18px;
            font-weight:700; margin-right: 10px; margin-bottom: 8px;
        }}

        div[data-testid="stMetric"] {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 12px 16px;
            box-shadow: var(--shadow);
        }}

        .stButton>button {{
            background: linear-gradient(90deg, #7c3aed, #4f46e5);
            color: white !important;
            border: none;
            border-radius: 980px;
            padding: 0.55rem 1.3rem;
            font-weight: 600;
            box-shadow: 0 4px 16px rgba(124,58,237,0.35);
            transition: transform 0.12s ease, box-shadow 0.12s ease;
        }}
        .stButton>button:hover {{ background: linear-gradient(90deg, #8b5cf6, #6366f1); transform: translateY(-1px); }}
        .stButton>button:active {{ transform: translateY(0px) scale(0.98); }}
        .stButton>button p {{ color: white !important; }}

        hr {{ border-color: var(--divider) !important; }}
        div[data-testid="stTabs"] button[role="tab"] {{ font-weight: 600; }}

        /* ---------------------------------------------------------------
           Mobile responsiveness — custom breakpoint pass
           (Streamlit auto-stacks st.columns() below ~640px on its own;
           everything below fine-tunes spacing, touch targets and type
           scale on top of that, phone-first.)
        --------------------------------------------------------------- */

        /* Touch targets: every interactive control gets a real 44px+ hit area,
           on ALL viewports (helps trackpad/touch-hybrid laptops too). */
        .stButton>button {{ min-height: 44px; }}
        div[data-testid="stTextInput"] input,
        div[data-testid="stNumberInput"] input,
        div[data-baseweb="select"] > div,
        div[data-testid="stFileUploader"] section {{ min-height: 44px; }}
        div[data-baseweb="radio"] label,
        div[data-baseweb="checkbox"] label {{ min-height: 44px; display:flex; align-items:center; }}
        div[data-testid="stSlider"] [role="slider"] {{ width: 20px !important; height: 20px !important; }}

        /* Tablet & below (~900px): tighten the main content gutters */
        @media (max-width: 900px) {{
            div.block-container {{ padding-left: 1rem; padding-right: 1rem; padding-top: 1.2rem; }}
            .ring-row {{ gap: 12px; }}
            .ring-card {{ min-width: 100px; padding: 12px 10px; }}
        }}

        /* Phones (~640px): Streamlit stacks st.columns() here already —
           we tune type scale, card padding and grid density to match. */
        @media (max-width: 640px) {{
            .hero-title {{ font-size: 1.65rem; margin-bottom: 0.15rem; }}
            .hero-sub {{ font-size: 0.82rem; margin-bottom: 1rem; }}
            .glass-card {{ padding: 14px 16px; border-radius: 16px; }}
            .insight-card {{ padding: 12px 14px; }}
            .ring-row {{ gap: 10px; justify-content: center; }}
            .ring-card {{ min-width: 84px; flex: 0 1 27%; padding: 10px 8px; }}
            .ring-wrap {{ width: 62px; height: 62px; }}
            .ring-center {{ font-size: 1.1rem; }}
            .ring-value {{ font-size: 0.95rem; margin-top: 5px; }}
            .ring-label {{ font-size: 0.62rem; }}
            .metric-value {{ font-size: 1.5rem; }}
            .stButton>button {{ width: 100%; padding: 0.7rem 1rem; font-size: 0.92rem; }}
            div[data-testid="stMetric"] {{ padding: 8px 10px; }}
            div[data-testid="stMetricValue"] {{ font-size: 1.3rem; }}
            .streak-pill {{ padding: 7px 14px; font-size: 0.85rem; }}
            div[data-testid="stTabs"] button[role="tab"] {{ font-size: 0.82rem; padding: 8px 10px; }}
            /* Attention Grid / Memory Sequence cell buttons: bigger tap targets,
               tighter gutters between columns so a 4x4 grid still fits comfortably. */
            div[data-testid="column"] {{ padding: 0 3px !important; }}
            div[data-testid="stHorizontalBlock"] .stButton>button {{
                min-height: 52px; font-size: 1.1rem; padding: 0.4rem;
            }}
        }}

        /* Small phones (~420px): squeeze one notch further */
        @media (max-width: 420px) {{
            .hero-title {{ font-size: 1.4rem; }}
            div.block-container {{ padding-left: 0.6rem; padding-right: 0.6rem; }}
            .ring-card {{ flex: 0 1 42%; }}
            div[data-testid="stHorizontalBlock"] .stButton>button {{ min-height: 46px; font-size: 1rem; }}
        }}

        footer {{visibility:hidden;}}
        #MainMenu {{visibility:hidden;}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_top_nav(current_page: str) -> str:
    # Auth guard: every page calls this before touching data. Unauthenticated => login screen + st.stop().
    from core import auth_ui
    from core.domain_ui import render_domain_sidebar, set_active_domain, active_domain, student_only_notice
    from services.registry import BY_KEY

    user = auth_ui.require_login()
    if "user_name" not in st.session_state:
        st.session_state.user_name = user["name"]
    # Remember which forecasting domain the user is working in; History / Analytics / Prediction follow it.
    if current_page in BY_KEY:
        set_active_domain(current_page)
    elif current_page == "Prediction":
        set_active_domain("student")
    active = active_domain()

    nav_map = [
        ("app", "app.py", "Home"),
        ("Prediction", BY_KEY[active].page, "Prediction"),
        ("History", "pages/2_History.py", "History"),
        ("Analytics", "pages/3_Analytics.py", "Analytics"),
        ("Focus Lab", "pages/4_Focus_Lab.py", "Focus Lab"),
        ("Stress Relief", "pages/5_Stress_Relief.py", "Stress Relief"),
        ("Achievements", "pages/6_Achievements.py", "Achievements"),
        ("AI Coach", "pages/8_AI_Coach.py", "AI Coach"),
        ("Weekly Log", "pages/9_Weekly_Log.py", "Weekly Log"),
        ("Settings", "pages/7_Settings.py", "Settings"),
    ]

    left, center, right = st.columns([1.5, 8.4, 1.5], gap="small")

    with left:
        st.markdown(
            '<div class="brand-shell"><span class="brand-mark">F</span><span class="brand-text">FutureForge</span></div>',
            unsafe_allow_html=True,
        )

    with center:
        st.markdown('<div style="width: 1.5rem;"></div>', unsafe_allow_html=True)
        nav_cols = st.columns([1.2, 1.35, 1.2, 1.3, 1.7, 1.8, 1.5, 1.3, 1.45, 1.15], gap="small")
        for i, (key, target, label) in enumerate(nav_map):
            with nav_cols[i]:
                if current_page == key:
                    st.markdown(f'<div class="top-nav-item active">{label}</div>', unsafe_allow_html=True)
                else:
                    st.page_link(target, label=label, help=f"Open {label}")

    with right:
        first = user["name"].split()[0] if user["name"].split() else user["name"]
        chip = st.popover if hasattr(st, "popover") else st.expander
        with chip(f"👤 {first}", use_container_width=True) if hasattr(st, "popover") else chip(f"👤 {first}"):
            st.markdown(f"**Hello, {first} 👋**  \n{user['name']}  \n{user['email']}  \n🟢 Online")
            st.page_link("pages/19_Profile.py", label="👤 Profile & account")
            if st.button("🚪 Log out", key="logout_btn", use_container_width=True):
                auth_ui.logout()
                st.rerun()

    render_domain_sidebar(active)
    if current_page in ("Achievements", "Weekly Log"):
        student_only_notice()

    return st.session_state.user_name


def sidebar_ai_status() -> None:
    pass
