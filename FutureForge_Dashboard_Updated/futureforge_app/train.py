from pathlib import Path

from ml.hybrid_pipeline import HybridPredictor


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    predictor = HybridPredictor(
        dataset_path=str(root / "backend" / "data" / "dummy_behavior_data.csv"),
        artifact_dir=str(root / "backend" / "data" / "artifacts"),
    )
    predictor.train()
    print("Hybrid model artifacts generated successfully.")
