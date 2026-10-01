#!/usr/bin/env python3
"""
Train a REAL model for one of the new domains from YOUR data and install it in models/<domain>/.

  python scripts/train_domain_model.py --domain employee --csv my_employee_data.csv --target productivity_score

The CSV needs one column per input feature of the domain (exact names — run with --show-schema to list them)
plus the numeric target column (0-100). Nothing is fabricated: with no CSV there is no model, and the app keeps
using the labelled rule-based indicator for that domain.
"""
import argparse, json, sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

from services.registry import BY_KEY, get_predictor


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", required=True, choices=[k for k in BY_KEY if k != "student"])
    ap.add_argument("--csv")
    ap.add_argument("--target", default="target")
    ap.add_argument("--show-schema", action="store_true")
    a = ap.parse_args()

    pred = get_predictor(a.domain)
    cols = [f.name for f in pred.input_features]
    if a.show_schema or not a.csv:
        print(f"{a.domain} input features (in order): {cols}")
        return
    df = pd.read_csv(a.csv)
    missing = [c for c in cols + [a.target] if c not in df.columns]
    if missing:
        sys.exit(f"CSV is missing columns: {missing}")
    if len(df) < 100:
        sys.exit(f"Only {len(df)} rows — need at least 100 real observations for a meaningful model.")
    X, y = df[cols], df[a.target].clip(0, 100)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestRegressor(n_estimators=300, random_state=42, n_jobs=1).fit(Xtr, ytr)
    p = model.predict(Xte)
    meta = {"features": cols, "version": datetime.now().strftime("%Y%m%d-%H%M"), "trained_on": Path(a.csv).name,
            "n_rows": int(len(df)), "metrics": {"mae": round(float(mean_absolute_error(yte, p)), 3),
                                                  "r2": round(float(r2_score(yte, p)), 3)}}
    out = pred.model_dir
    out.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, out / "model.joblib")
    (out / "metadata.json").write_text(json.dumps(meta, indent=2))
    print("Installed", out, meta["metrics"])


if __name__ == "__main__":
    main()
