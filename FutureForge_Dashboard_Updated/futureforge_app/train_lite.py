from pathlib import Path
from hybrid_pipeline_lite import HybridPredictor

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[0]
    
    print("=" * 70)
    print("🚀 FutureForge LITE - Hybrid ML Model Training")
    print("=" * 70)
    print()
    
    predictor = HybridPredictor(
        dataset_path=str(root / "backend" / "data" / "dummy_behavior_data.csv"),
        artifact_dir=str(root / "backend" / "data" / "artifacts"),
    )
    
    print()
    print("=" * 70)
    print("✅ Hybrid model artifacts generated successfully!")
    print("=" * 70)
    print()
    print("Now you can make predictions!")
    print("Run: python quick_predict_lite.py")
