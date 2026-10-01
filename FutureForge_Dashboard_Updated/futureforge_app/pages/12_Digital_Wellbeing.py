import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.theme import inject_theme, render_top_nav
from core.domain_ui import render_domain_page

st.set_page_config(page_title="FutureForge | Digital Well-being", page_icon="📱", layout="wide")
inject_theme()
render_top_nav("digital_wellbeing")
render_domain_page("digital_wellbeing")
