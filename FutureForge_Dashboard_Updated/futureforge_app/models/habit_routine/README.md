# Habit & Routine Forecasting — model slot (no trained model yet)

Status: **no trained model installed.** The page runs a transparent rule-based indicator and labels it as such;
no confidence value is shown until a trained model exists.

To plug in a trained model, place these two files in this folder and restart the app:

- `model.joblib`  — a scikit-learn-style regressor whose `predict(DataFrame)` returns a 0-100 score
- `metadata.json` — `{"features": ['sleep_consistency', 'exercise_frequency', 'study_work_hours', 'screen_time', 'break_frequency', 'mood', 'routine_consistency'], "version": "...", "trained_on": "..."}`
  (the `features` list must match exactly, in this order, or the model is ignored)

Or train one from your own real data:

    python scripts/train_domain_model.py --domain habit_routine --csv your_data.csv --target your_target_column
