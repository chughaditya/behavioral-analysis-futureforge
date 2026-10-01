#!/usr/bin/env python3
"""
Quick Prediction Script (LITE VERSION - No TensorFlow)
Simplified version using only Scikit-learn
"""

from hybrid_pipeline_lite import HybridPredictor

print("=" * 70)
print("🚀 FutureForge LITE - Quick Prediction Test")
print("=" * 70)
print()

# Initialize predictor
print("📥 Loading model...")
try:
    predictor = HybridPredictor(
        dataset_path="backend/data/dummy_behavior_data.csv",
        artifact_dir="backend/data/artifacts"
    )
    print("✅ Model loaded successfully!\n")
except Exception as e:
    print(f"❌ Error loading model: {e}")
    print("Make sure you've run: python train_lite.py\n")
    exit(1)

# Make prediction
print("🔮 Making prediction with sample data...")
print()

sample_data = {
    "study_hours": 6.5,
    "sleep_hours": 7.8,
    "screen_time": 3.2,
    "mood": "focused"
}

print(f"Input Data:")
print(f"  Study Hours: {sample_data['study_hours']}")
print(f"  Sleep Hours: {sample_data['sleep_hours']}")
print(f"  Screen Time: {sample_data['screen_time']}")
print(f"  Mood: {sample_data['mood']}")
print()

try:
    prediction = predictor.predict(sample_data)
    
    print("✅ PREDICTION RESULTS:")
    print("=" * 70)
    print(f"📊 Future Score: {prediction['future_score']}/100")
    print(f"⚠️  Risk Level: {prediction['risk'].upper()}")
    print(f"🎯 Confidence: {prediction['confidence']}%")
    print(f"📈 Cluster: {prediction['cluster']}")
    print()
    
    print("💡 TOP INSIGHTS:")
    print("-" * 70)
    for i, insight in enumerate(prediction['feedback'], 1):
        print(f"\n{i}. {insight['title']}")
        print(f"   Priority: {insight['priority']}")
        print(f"   Action: {insight['action']}")
        print(f"   Outcome: {insight['outcome']}")
    
    print()
    print("=" * 70)
    print("✅ SUCCESS! Model is working perfectly! 🎉")
    print("=" * 70)
    
except Exception as e:
    print(f"❌ Error making prediction: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
