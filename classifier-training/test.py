"""Locally sanity-check the trained classifier against a few example descriptions.

Mirrors backend-service/app/routers/classify.py's loading and prediction logic
exactly, so results here reflect what production actually serves.

Usage:
    python test.py                          # run built-in example descriptions
    python test.py "swiggy order" "flight to goa"   # test specific descriptions
"""
import sys
from pathlib import Path

import joblib
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = REPO_ROOT / "backend-service" / "models"

sys.path.insert(0, str(REPO_ROOT / "backend-service"))
from app.embedder import Embedder, download  # noqa: E402

EXAMPLE_DESCRIPTIONS = [
    "Buy medicine",
    "eat dosa",
    "Rent payment",
    "Movie ticket",
    "Travel to office and back",
    "buy borosil tiffin from hometown",
    "buy bread and butter from instamart",
    "Hotel stay Bangalore",
    "Fill petrol"
]


def predict(descriptions: list[str]):
    download()
    embedder = Embedder()
    clf = joblib.load(MODELS_DIR / "classifier.joblib")
    encoder = joblib.load(MODELS_DIR / "label_encoder.joblib")

    embeddings = embedder.encode(descriptions)
    scores = clf.decision_function(embeddings)
    pred_idx = np.argmax(scores, axis=1)
    categories = encoder.inverse_transform(pred_idx)
    confidences = scores[np.arange(len(descriptions)), pred_idx]

    return list(zip(descriptions, categories, confidences))


def main():
    descriptions = sys.argv[1:] or EXAMPLE_DESCRIPTIONS
    for description, category, confidence in predict(descriptions):
        print(f"{description!r:<45} -> {category:<15} (confidence {confidence:.4f})")


if __name__ == "__main__":
    main()
