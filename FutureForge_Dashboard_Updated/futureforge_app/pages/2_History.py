import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import db, scoring
from core.theme import inject_theme, render_top_nav

st.set_page_config(page_title="FutureForge | History", page_icon="📜", layout="wide")
inject_theme()
render_top_nav("History")
from core.domain_ui import maybe_render_domain_view
maybe_render_domain_view("history")  # non-Student active domain -> that domain's view, then stop

st.markdown('<div class="hero-title">📜 History</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Every saved daily report, searchable and filterable.</div>', unsafe_allow_html=True)

df = db.get_all_reports()

if df.empty:
    st.markdown(
        '<div class="glass-card">No reports yet. Complete your first prediction and save it to start '
        "building your personal performance history.</div>",
        unsafe_allow_html=True,
    )
    if st.button("Start Analysis →"):
        st.switch_page("pages/1_Prediction.py")
    st.stop()

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
st.markdown("### 🔎 Filters & Search")
f1, f2, f3, f4 = st.columns(4)

years = sorted(df["year"].unique().tolist(), reverse=True)
year_filter = f1.selectbox("Year", ["All"] + [str(y) for y in years])
months = ["All"] + sorted(df["month"].unique().tolist())
month_filter = f2.selectbox("Month", months)
preset_filter = f3.selectbox(
    "Quick Range", ["All Time", "Today", "Yesterday", "Last 7 Days", "Last 30 Days", "This Month"]
)
search_query = f4.text_input("Search", placeholder="e.g. stressed, high focus, Sep")

filtered = df.copy()

if year_filter != "All":
    filtered = filtered[filtered["year"] == int(year_filter)]
if month_filter != "All":
    filtered = filtered[filtered["month"] == month_filter]

today = datetime.now().date()
if preset_filter == "Today":
    filtered = filtered[filtered["date"].dt.date == today]
elif preset_filter == "Yesterday":
    filtered = filtered[filtered["date"].dt.date == (today - timedelta(days=1))]
elif preset_filter == "Last 7 Days":
    filtered = filtered[filtered["date"] >= datetime.now() - timedelta(days=7)]
elif preset_filter == "Last 30 Days":
    filtered = filtered[filtered["date"] >= datetime.now() - timedelta(days=30)]
elif preset_filter == "This Month":
    filtered = filtered[(filtered["date"].dt.month == today.month) & (filtered["date"].dt.year == today.year)]

if search_query:
    q = search_query.lower()
    mask = (
        filtered["prediction"].str.lower().str.contains(q, na=False)
        | filtered["mood"].str.lower().str.contains(q, na=False)
        | filtered["month"].str.lower().str.contains(q, na=False)
        | filtered["recommendations"].str.lower().str.contains(q, na=False)
    )
    filtered = filtered[mask]

custom_range = st.date_input("Custom Date Range (optional)", value=())
if isinstance(custom_range, tuple) and len(custom_range) == 2:
    start_d, end_d = custom_range
    filtered = filtered[(filtered["date"].dt.date >= start_d) & (filtered["date"].dt.date <= end_d)]

st.caption(f"Showing {len(filtered)} of {len(df)} saved reports")

st.markdown("---")

# ---------------------------------------------------------------------------
# Calendar heatmap
# ---------------------------------------------------------------------------
st.markdown("### 🗓️ Calendar View")
cal_df = filtered.copy()
if not cal_df.empty:
    cal_df["grade"] = cal_df.apply(lambda r: scoring.performance_grade(r["focus_score"], r["stress_score"]), axis=1)
    cal_df["grade_num"] = cal_df["grade"].map({"Needs Attention": 1, "Average": 2, "Good": 3, "Excellent": 4})
    cal_df["week"] = cal_df["date"].dt.isocalendar().week
    cal_df["weekday"] = cal_df["date"].dt.day_name()
    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    pivot = cal_df.pivot_table(index="week", columns="weekday", values="grade_num", aggfunc="mean")
    pivot = pivot.reindex(columns=weekday_order)

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=weekday_order,
            y=[f"Week {w}" for w in pivot.index],
            colorscale=[[0, "#f87171"], [0.33, "#fbbf24"], [0.66, "#60a5fa"], [1, "#34d399"]],
            zmin=1,
            zmax=4,
            showscale=False,
            hoverongaps=False,
        )
    )
    fig.update_layout(
        height=max(180, 60 * len(pivot.index)),
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#eef0ff"},
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("🔴 Needs Attention · 🟡 Average · 🔵 Good · 🟢 Excellent")
else:
    st.caption("No data in the selected range for the calendar view.")

st.markdown("---")

# ---------------------------------------------------------------------------
# List + detail view
# ---------------------------------------------------------------------------
st.markdown("### 📋 Saved Reports")

if filtered.empty:
    st.info("No reports match the current filters.")
else:
    for _, row in filtered.sort_values("date", ascending=False).iterrows():
        with st.expander(
            f"{row['date'].strftime('%A, %B %d, %Y')} — Focus {row['focus_score']:.0f} · "
            f"Stress {row['stress_score']:.0f} · {row['prediction']}"
        ):
            dcol1, dcol2 = st.columns(2)
            with dcol1:
                st.markdown("**Daily Performance**")
                st.write(f"Focus: {row['focus_score']:.0f}")
                st.write(f"Stress: {row['stress_score']:.0f}")
                st.write(f"Mood: {row['mood_score']:.1f}/10 ({row['mood']})")
                st.write(f"Sleep: {row['sleep_display']}")
                st.write(f"Productivity: {row['productivity_score']:.0f}%")
            with dcol2:
                st.markdown("**AI Prediction**")
                st.write(f"Prediction: {row['prediction']}")
                st.write(f"Confidence: {row['prediction_confidence']:.0f}%")
                st.markdown("**Why**")
                st.write(row["prediction_explanation"] or "—")
                st.markdown("**Recommendations**")
                for rec in str(row["recommendations"]).split(" | "):
                    if rec:
                        st.write(f"• {rec}")

            if st.button("🗑️ Delete this report", key=f"del_{row['id']}"):
                db.delete_report(int(row["id"]))
                st.rerun()

st.markdown("---")

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
st.markdown("### ⬇️ Export")
ecol1, ecol2 = st.columns(2)
csv_bytes = filtered.drop(columns=["feedback"], errors="ignore").to_csv(index=False).encode("utf-8")
ecol1.download_button("Export Filtered CSV", csv_bytes, "futureforge_history.csv", "text/csv", use_container_width=True)

try:
    from fpdf import FPDF

    def build_pdf(data: pd.DataFrame) -> bytes:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "FutureForge - History Report", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 8, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
        pdf.ln(4)
        for _, r in data.sort_values("date", ascending=False).iterrows():
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, r["date"].strftime("%Y-%m-%d (%A)"), ln=True)
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(
                0,
                5,
                f"Focus {r['focus_score']:.0f} | Stress {r['stress_score']:.0f} | Mood {r['mood_score']:.1f} | "
                f"Sleep {r['sleep_display']} | Productivity {r['productivity_score']:.0f}%\n"
                f"Prediction: {r['prediction']} (Confidence {r['prediction_confidence']:.0f}%)\n",
            )
            pdf.ln(1)
        return bytes(pdf.output(dest="S"))

    pdf_bytes = build_pdf(filtered)
    ecol2.download_button(
        "Export Filtered PDF", pdf_bytes, "futureforge_history.pdf", "application/pdf", use_container_width=True
    )
except Exception:
    ecol2.caption("PDF export unavailable in this environment.")
