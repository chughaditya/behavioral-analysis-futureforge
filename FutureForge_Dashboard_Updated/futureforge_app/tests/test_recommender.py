"""Recommender tests: python tests/test_recommender.py  (no Streamlit needed)"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from core import recommender as R
from hybrid_pipeline import HybridPredictor

BASE = Path(__file__).resolve().parent.parent / "backend" / "data"
fails = 0


def check(name, cond):
    global fails
    print(("ok   " if cond else "FAIL ") + name)
    fails += 0 if cond else 1


# --- pure logic
hi = R.recommend(88, {"sleep_hours": 8, "screen_time": 2, "mood": "focused"}, source="ml_model")
mid = R.recommend(65, {"sleep_hours": 7, "screen_time": 3, "mood": "balanced"})
lo = R.recommend(40, {"sleep_hours": 7, "screen_time": 3, "mood": "balanced"})
check("high band -> Memory Sequence, 50-min blocks", hi.test == "Memory Sequence" and hi.session_minutes == 50)
check("medium band -> Attention Grid, 25-min blocks", mid.test == "Attention Grid" and mid.session_minutes == 25)
check("low band -> Reaction Time, short blocks", lo.test == "Reaction Time" and lo.session_minutes == 15)
check("boundaries 75/55", R.band_for(75) == "high" and R.band_for(74.9) == "medium" and R.band_for(55) == "medium" and R.band_for(54.9) == "low")
sl = R.recommend(90, {"sleep_hours": 4.5, "screen_time": 2, "mood": "focused"})
check("low sleep overrides to Reaction Time + caps block at 20", sl.test == "Reaction Time" and sl.session_minutes <= 20)
sc = R.recommend(90, {"sleep_hours": 8, "screen_time": 9, "mood": "focused"})
check("high screen -> Attention Grid", sc.test == "Attention Grid")
tdf = pd.DataFrame([{"test_type": "Memory Sequence", "created_at": datetime.now().isoformat(timespec="seconds")}])
rp = R.recommend(88, {"sleep_hours": 8, "screen_time": 2, "mood": "focused"}, tests_df=tdf)
check("recent test not repeated", rp.test != "Memory Sequence")
check("ranking has all 4 Focus Lab tests, best first", [t for t,_ in hi.ranking][0]==hi.test and set(t for t,_ in hi.ranking)==set(R.TESTS))
check("source/confidence passed through", hi.source == "ml_model" and mid.source == "rule_based")

# --- real trained student model
hp = HybridPredictor(dataset_path=str(BASE / "dummy_behavior_data.csv"), artifact_dir=str(BASE / "artifacts"))
good = R.from_student(hp, {"study_hours": 6, "sleep_hours": 8, "screen_time": 2, "mood": "focused"})
bad = R.from_student(hp, {"study_hours": 1, "sleep_hours": 4, "screen_time": 10, "mood": "stressed"})
print("   student good:", good.score, good.band, good.test, "| bad:", bad.score, bad.band, bad.test)
check("student uses ml_model", good.source == "ml_model" and bad.source == "ml_model")
check("student good score > bad score", good.score > bad.score)
check("student bad input -> light plan", bad.test == "Reaction Time" and bad.session_minutes <= 20)

# --- every non-student domain works with its defaults
from services.registry import DOMAINS, get_predictor
for d in DOMAINS:
    if d.predictor_cls is None:
        continue
    vals = {f.name: f.default for f in get_predictor(d.key).input_features}
    r = R.from_domain(d.key, vals)
    check(f"{d.key}: recommendation built ({r.score:.0f}, {r.band}, {r.test}, {r.source})", r.test in R.TESTS and r.source in ("rule_based", "ml_model"))

print("\nALL PASSED" if not fails else f"\n{fails} FAILED")
sys.exit(1 if fails else 0)
