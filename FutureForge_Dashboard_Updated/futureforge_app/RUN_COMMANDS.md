# FutureForge - Run Commands Guide

## 🚀 Complete Setup & Execution Commands

---

## 1️⃣ INSTALLATION & SETUP

### Step 1: Extract the zip file
```bash
unzip FutureForge_ML_Model.zip
cd FutureForge_ML_Model
```

### Step 2: Create virtual environment (Optional but recommended)
```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install dependencies
```bash
# Basic installation
pip install -r requirements.txt

# OR install individual packages
pip install tensorflow scikit-learn pandas numpy joblib

# For GPU support (NVIDIA only)
pip install tensorflow[and-cuda]
```

### Step 4: Verify installation
```bash
python -c "import tensorflow; import sklearn; print('✅ All packages installed!')"
```

---

## 2️⃣ TRAINING THE MODEL

### Train model (generates artifacts)
```bash
python train.py
```

**Output:**
```
Hybrid model artifacts generated successfully.
```

**Files generated:**
```
backend/data/artifacts/
├── scaler.joblib
├── kmeans.joblib
├── random_forest.joblib
└── lstm_model.keras
```

---

## 3️⃣ MAKE PREDICTIONS

### Method 1: Simple Python Script (Recommended for beginners)

Create a file `predict.py`:
```bash
cat > predict.py << 'EOF'
from hybrid_pipeline import HybridPredictor

predictor = HybridPredictor(
    dataset_path="backend/data/dummy_behavior_data.csv",
    artifact_dir="backend/data/artifacts"
)

# Make prediction
result = predictor.predict({
    "study_hours": 6.5,
    "sleep_hours": 7.8,
    "screen_time": 3.2,
    "mood": "focused"
})

# Print results
print(f"✅ Prediction Results:")
print(f"   Score: {result['future_score']}")
print(f"   Risk: {result['risk']}")
print(f"   Confidence: {result['confidence']}%")
print(f"\n💡 Top Insight: {result['feedback'][0]['title']}")
EOF

python predict.py
```

### Method 2: Interactive Python Shell
```bash
python
```

Then inside Python:
```python
from hybrid_pipeline import HybridPredictor

predictor = HybridPredictor(
    dataset_path="backend/data/dummy_behavior_data.csv",
    artifact_dir="backend/data/artifacts"
)

result = predictor.predict({
    "study_hours": 6.5,
    "sleep_hours": 7.8,
    "screen_time": 3.2,
    "mood": "focused"
})

print(f"Score: {result['future_score']}")
print(f"Risk: {result['risk']}")
print(f"Confidence: {result['confidence']}%")

# View all insights
for insight in result['feedback']:
    print(f"\n{insight['title']}")
    print(f"Action: {insight['action']}")

exit()
```

### Method 3: Run Examples (Most detailed)
```bash
python example_usage.py
```

**This will show:**
- Basic single prediction
- 4 batch predictions (High performer, Struggling user, Stressed, Balanced)
- Detailed analysis
- Performance metrics
- Export to JSON

---

## 4️⃣ BATCH PREDICTIONS

Create a file `batch_predict.py`:
```bash
cat > batch_predict.py << 'EOF'
from hybrid_pipeline import HybridPredictor
import json

predictor = HybridPredictor(
    dataset_path="backend/data/dummy_behavior_data.csv",
    artifact_dir="backend/data/artifacts"
)

# Multiple test cases
test_cases = [
    {"name": "User 1 - High Performer", "data": {"study_hours": 8.0, "sleep_hours": 8.0, "screen_time": 2.0, "mood": "focused"}},
    {"name": "User 2 - Struggling", "data": {"study_hours": 3.0, "sleep_hours": 5.5, "screen_time": 6.0, "mood": "tired"}},
    {"name": "User 3 - Stressed", "data": {"study_hours": 7.5, "sleep_hours": 6.0, "screen_time": 5.5, "mood": "stressed"}},
    {"name": "User 4 - Balanced", "data": {"study_hours": 5.5, "sleep_hours": 7.5, "screen_time": 3.5, "mood": "balanced"}},
]

results = []

print("📊 BATCH PREDICTIONS")
print("=" * 70)

for test in test_cases:
    pred = predictor.predict(test["data"])
    results.append({
        "name": test["name"],
        "score": pred["future_score"],
        "risk": pred["risk"],
        "confidence": pred["confidence"]
    })
    
    print(f"{test['name']}")
    print(f"  Score: {pred['future_score']}/100")
    print(f"  Risk: {pred['risk']}")
    print(f"  Confidence: {pred['confidence']}%\n")

# Save to JSON
with open("predictions.json", "w") as f:
    json.dump(results, f, indent=2)
    
print("✅ Results saved to predictions.json")
EOF

python batch_predict.py
```

---

## 5️⃣ API SETUP (FastAPI)

Create a file `api.py`:
```bash
cat > api.py << 'EOF'
from fastapi import FastAPI
from pydantic import BaseModel
from hybrid_pipeline import HybridPredictor

app = FastAPI(title="FutureForge API")

predictor = HybridPredictor(
    dataset_path="backend/data/dummy_behavior_data.csv",
    artifact_dir="backend/data/artifacts"
)

class PredictionRequest(BaseModel):
    study_hours: float
    sleep_hours: float
    screen_time: float
    mood: str

@app.post("/predict")
async def predict(request: PredictionRequest):
    return predictor.predict({
        "study_hours": request.study_hours,
        "sleep_hours": request.sleep_hours,
        "screen_time": request.screen_time,
        "mood": request.mood
    })

@app.get("/health")
async def health():
    return {"status": "Model is running ✅"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
EOF
```

Install FastAPI:
```bash
pip install fastapi uvicorn
```

Run the API:
```bash
python api.py
```

**Output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Test the API:
```bash
# Test health
curl http://localhost:8000/health

# Make prediction
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "study_hours": 6.5,
    "sleep_hours": 7.8,
    "screen_time": 3.2,
    "mood": "focused"
  }'

# View API docs
# Open in browser: http://localhost:8000/docs
```

---

## 6️⃣ DATA ANALYSIS

Create a file `analyze_data.py`:
```bash
cat > analyze_data.py << 'EOF'
import pandas as pd

# Load and analyze dataset
df = pd.read_csv("backend/data/dummy_behavior_data.csv")

print("📊 DATASET ANALYSIS")
print("=" * 70)
print(f"Total records: {len(df)}")
print(f"\nColumns: {df.columns.tolist()}")
print(f"\nData types:\n{df.dtypes}")
print(f"\nStatistics:\n{df.describe()}")
print(f"\nMissing values:\n{df.isnull().sum()}")
print(f"\nMood distribution:\n{df['mood'].value_counts()}")
EOF

python analyze_data.py
```

---

## 7️⃣ TESTING & VALIDATION

Run unit tests:
```bash
# If pytest is installed
pip install pytest

# Create test_model.py
cat > test_model.py << 'EOF'
from hybrid_pipeline import HybridPredictor

predictor = HybridPredictor(
    dataset_path="backend/data/dummy_behavior_data.csv",
    artifact_dir="backend/data/artifacts"
)

# Test 1: Valid input
result = predictor.predict({
    "study_hours": 5.0,
    "sleep_hours": 7.0,
    "screen_time": 3.0,
    "mood": "focused"
})

assert 0 <= result['future_score'] <= 100, "Score out of range"
assert result['risk'] in ['low', 'medium', 'high'], "Invalid risk level"
assert 0 <= result['confidence'] <= 100, "Confidence out of range"
assert len(result['feedback']) > 0, "No insights generated"

print("✅ All tests passed!")
EOF

python test_model.py
```

---

## 8️⃣ PERFORMANCE BENCHMARKING

Create a file `benchmark.py`:
```bash
cat > benchmark.py << 'EOF'
import time
from hybrid_pipeline import HybridPredictor

predictor = HybridPredictor(
    dataset_path="backend/data/dummy_behavior_data.csv",
    artifact_dir="backend/data/artifacts"
)

test_input = {
    "study_hours": 6.5,
    "sleep_hours": 7.8,
    "screen_time": 3.2,
    "mood": "focused"
}

# Warm up
predictor.predict(test_input)

# Benchmark 100 predictions
print("🚀 PERFORMANCE BENCHMARK")
print("=" * 70)

times = []
for i in range(100):
    start = time.time()
    predictor.predict(test_input)
    end = time.time()
    times.append((end - start) * 1000)  # Convert to ms

import statistics

print(f"Total predictions: 100")
print(f"Average latency: {statistics.mean(times):.2f}ms")
print(f"Min latency: {min(times):.2f}ms")
print(f"Max latency: {max(times):.2f}ms")
print(f"Std deviation: {statistics.stdev(times):.2f}ms")
print(f"Throughput: {1000 / statistics.mean(times):.1f} predictions/second")
EOF

python benchmark.py
```

---

## 9️⃣ COMPLETE WORKFLOW

Run everything in sequence:
```bash
#!/bin/bash

echo "🚀 FutureForge Complete Workflow"
echo "=================================="

# Step 1: Install
echo "📦 Installing dependencies..."
pip install -r requirements.txt
echo "✅ Dependencies installed\n"

# Step 2: Train
echo "🧠 Training models..."
python train.py
echo "✅ Models trained\n"

# Step 3: Test
echo "🧪 Running tests..."
python test_model.py
echo "✅ Tests passed\n"

# Step 4: Benchmark
echo "⚡ Running benchmark..."
python benchmark.py
echo "✅ Benchmark complete\n"

# Step 5: Examples
echo "📚 Running examples..."
python example_usage.py
echo "✅ Examples complete\n"

echo "🎉 ALL DONE!"
```

Save as `run_all.sh`:
```bash
chmod +x run_all.sh
./run_all.sh
```

---

## 🔟 QUICK COMMAND REFERENCE

```bash
# Install dependencies
pip install -r requirements.txt

# Train model
python train.py

# Run examples (RECOMMENDED FOR FIRST RUN)
python example_usage.py

# Single prediction
python predict.py

# Batch predictions
python batch_predict.py

# Start API server
python api.py

# Analyze data
python analyze_data.py

# Run tests
python test_model.py

# Benchmark performance
python benchmark.py
```

---

## 📋 STEP-BY-STEP FOR BEGINNERS

### Complete Setup (Copy & Paste)

```bash
# 1. Extract
unzip FutureForge_ML_Model.zip
cd FutureForge_ML_Model

# 2. Create virtual environment (Optional)
python -m venv venv
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate  # Windows

# 3. Install
pip install -r requirements.txt

# 4. Train
python train.py

# 5. Test
python example_usage.py

# 6. Make prediction
python predict.py

# 7. Start API (Optional)
pip install fastapi uvicorn
python api.py
```

---

## 🎯 MOST IMPORTANT COMMANDS

**For First Time:**
```bash
pip install -r requirements.txt
python train.py
python example_usage.py
```

**For Production:**
```bash
pip install -r requirements.txt
python api.py
# Then send POST requests to http://localhost:8000/predict
```

**For Quick Test:**
```bash
python predict.py
```

---

**Ready? Start with:** `python example_usage.py` 🚀
