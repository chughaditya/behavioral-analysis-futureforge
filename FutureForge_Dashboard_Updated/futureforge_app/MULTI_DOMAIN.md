# FutureForge — multi-domain extension

Run (same as before):

    pip install -r requirements.txt
    streamlit run app.py

First launch migrates `backend/data/futureforge.db` additively (no rows deleted). **The first account you create
inherits the existing single-user history** (reports, focus sessions, test results); later accounts start empty.

Layout
- `core/auth.py` (accounts, scrypt hashing, sessions, lockout) · `core/auth_ui.py` (login/signup UI, page guard, logout)
- `core/predictions_db.py` (per-user prediction store + unified history) · `core/domain_ui.py` (sidebar + generic domain page)
- `services/*_predictor.py` (one per domain, common `DomainPredictor` interface in `services/base.py`) · `services/registry.py`
- `models/<domain>/` model slots (README each) · `scripts/train_domain_model.py` trains a real model from your CSV
- `pages/10-17_*` domain pages · `pages/18_Prediction_History.py` · `pages/19_Profile.py`

Tests (no Streamlit needed for the first; the second uses the bundled stub):

    python tests/test_backend.py
    PYTHONPATH=tests/stubs python tests/test_pages_smoke.py

Smart Recommendation (Focus Lab)
- `core/recommender.py` maps a forecast score (75 / 55 bands) + the user's inputs to a Focus Lab test and a focus plan
  (session / break / blocks). Student uses the trained hybrid model; other domains use their DomainPredictor
  (ML if models/<domain>/ has a trained model, otherwise the labelled rule-based indicator).
- `core/recommender_ui.py` renders the panel at the top of Focus Lab. Every domain page and this panel predict only when you click Run (no live update); "Use plan" preloads Focus Mode duration.
- Test: `python tests/test_recommender.py`

Focus Lab Recommendations (risk -> test loop)
- Flow: prediction -> `services/focus_lab/recommendation_engine.py` detects the risk area -> card under the prediction
  ("Recommended Action", or "looks stable") -> [Go to Focus Lab →] opens the recommended test automatically
  (Focus Lab > "Self-Assessments & Recommendations") -> scored -> saved -> observations/actions + progress table.
- `services/focus_lab/`: `tests_bank.py` (22 tests, 5-6 questions, 4-point scale), `scoring.py` (score %, category
  80/60/40), `test_engine.py`, `recommendation_engine.py` (rule table per domain; student uses the trained model's scores).
- `core/focus_lab_db.py`: tables `focus_lab_recommendations` + `focus_lab_results` in the SAME SQLite DB, created lazily,
  every query scoped to the logged-in user. `core/focus_lab_ui.py`: risk card + assessment UI.
- Self-assessments only; not a medical or psychological assessment.
- Tests: `python tests/test_focus_lab.py`
