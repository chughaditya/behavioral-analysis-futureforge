"""Apple-Health-style circular progress "activity rings" as inline SVG.

Pure SVG (no JS/chart lib) so it renders instantly and matches the
pixel-crisp look of Apple Health rings in both light and dark themes.
"""

from __future__ import annotations

import streamlit as st


def _ring_svg(pct: float, color: str, size: int, stroke: int) -> str:
    pct = max(0.0, min(100.0, pct))
    r = (size - stroke) / 2
    c = size / 2
    circumference = 2 * 3.14159265 * r
    offset = circumference * (1 - pct / 100)
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" style="transform:rotate(-90deg);">
      <circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="rgba(128,128,140,0.18)" stroke-width="{stroke}"/>
      <circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="{color}" stroke-width="{stroke}"
              stroke-linecap="round" stroke-dasharray="{circumference:.2f}"
              stroke-dashoffset="{offset:.2f}"
              style="transition: stroke-dashoffset 0.8s cubic-bezier(.4,0,.2,1);"/>
    </svg>
    """


def activity_ring_card(label: str, value_display: str, pct: float, color: str, icon: str = "") -> str:
    """One Apple-Health-style ring card: ring + big number + label."""
    size, stroke = 84, 9
    svg = _ring_svg(pct, color, size, stroke)
    return f"""
    <div class="ring-card">
      <div class="ring-wrap">{svg}
        <div class="ring-center">{icon}</div>
      </div>
      <div class="ring-value">{value_display}</div>
      <div class="ring-label">{label}</div>
    </div>
    """


def render_ring_row(rings: list[dict]) -> None:
    """Render a row of activity rings using Streamlit columns instead of one raw HTML string."""
    cols = st.columns(len(rings))
    for col, ring in zip(cols, rings):
        with col:
            st.markdown(
                f"""
                <div class="ring-card">
                  <div class="ring-wrap">
                    {_ring_svg(ring["pct"], ring["color"], 84, 9)}
                    <div class="ring-center">{ring.get("icon", "")}</div>
                  </div>
                  <div class="ring-value">{ring['value_display']}</div>
                  <div class="ring-label">{ring['label']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def ring_row(rings: list[dict]) -> str:
    """Backward-compatible HTML string helper kept for older call sites."""
    cards = "".join(
        activity_ring_card(r["label"], r["value_display"], r["pct"], r["color"], r.get("icon", "")) for r in rings
    )
    return f'<div class="ring-row">{cards}</div>'
