# Student model (existing — do not move)

Student Productivity uses the ALREADY-TRAINED hybrid pipeline (StandardScaler + K-Means + LSTM/statistical
fallback + Random Forest). Its artifacts stay where they always were:

    backend/data/artifacts/{scaler,kmeans,random_forest}.joblib

Inputs: study_hours, sleep_hours, screen_time, mood. Nothing here is retrained or renamed.
