"""Train the transaction category classifier and publish it to backend-service/models/.

Pipeline: embed transaction descriptions with a sentence-transformer, compare a
handful of scikit-learn classifiers via cross-validation, evaluate the best one
on a held-out test set, then refit it on all data before saving.

Input data comes from db_backup/csv_exports/budget_tracker.csv — run
db_backup/restore_latest_backup.py first to pull the latest snapshot.
"""
import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC, SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.metrics import classification_report

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = REPO_ROOT / "db_backup" / "csv_exports" / "budget_tracker.csv"
MODELS_DIR = REPO_ROOT / "backend-service" / "models"

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CV_FOLDS = 3
TEST_SIZE = 0.2
RANDOM_STATE = 42


def load_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        sys.exit(
            f"{DATA_PATH} not found. Run db_backup/restore_latest_backup.py first "
            "to pull the latest data snapshot and regenerate csv_exports/."
        )
    df = pd.read_csv(DATA_PATH)
    df["Description"] = df["Description"].str.strip()
    df["Category"] = df["Category"].str.strip()
    df = df.dropna(subset=["Description", "Category"])
    print(f"Total transactions: {len(df)}")
    print("\nCategory distribution:")
    print(df["Category"].value_counts().to_string())
    return df


def embed(descriptions: list[str]) -> np.ndarray:
    # normalize_embeddings=True applies L2 normalization, which improves all
    # downstream classifiers on dense vector spaces.
    embedder = SentenceTransformer(EMBEDDING_MODEL)
    return embedder.encode(
        descriptions, batch_size=64, show_progress_bar=True, normalize_embeddings=True
    )


def split_train_test(X: np.ndarray, y: np.ndarray, num_classes: int):
    # Classes with fewer than 2 samples can't be stratified, so those samples
    # are forced into the training set only (they'd otherwise crash train_test_split).
    class_counts = np.bincount(y, minlength=num_classes)
    rare_class_ids = np.where(class_counts < 2)[0]

    rare_mask = np.isin(y, rare_class_ids)
    X_rare, y_rare = X[rare_mask], y[rare_mask]
    X_rest, y_rest = X[~rare_mask], y[~rare_mask]

    X_train_rest, X_test, y_train_rest, y_test = train_test_split(
        X_rest, y_rest, test_size=TEST_SIZE, stratify=y_rest, random_state=RANDOM_STATE
    )

    X_train = np.vstack([X_train_rest, X_rare]) if len(X_rare) else X_train_rest
    y_train = np.concatenate([y_train_rest, y_rare]) if len(y_rare) else y_train_rest
    return X_train, X_test, y_train, y_test


def build_candidates() -> dict:
    return {
        "Logistic Regression": LogisticRegression(
            C=1.0, class_weight="balanced", max_iter=1000, solver="lbfgs"
        ),
        "LinearSVC": LinearSVC(C=1.0, class_weight="balanced", max_iter=5000),
        "RBF SVM": SVC(
            kernel="rbf", C=10.0, gamma="scale",
            class_weight="balanced", probability=True
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=300, class_weight="balanced_subsample", random_state=RANDOM_STATE
        ),
    }


def select_best_model(candidates: dict, X_train: np.ndarray, y_train: np.ndarray) -> str:
    # Cross-validation runs on the training set only, for model selection.
    # Primary metric: macro F1 (weights all classes equally, not inflated by
    # the Food majority). Rare-class (e.g. Medical, Miscellaneous) CV scores
    # are unreliable due to sample size, but macro F1 still surfaces that.
    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    cv_results = {}

    print(f"\nCross-validation ({CV_FOLDS}-fold) on train set — macro F1\n")
    for name, model in candidates.items():
        scores = cross_val_score(model, X_train, y_train, cv=cv, scoring="f1_macro", n_jobs=-1)
        cv_results[name] = scores.mean()
        print(f"  {name:<22} {scores.mean():.4f} ± {scores.std():.4f}")

    best_name = max(cv_results, key=cv_results.get)
    print(f"\nBest model: {best_name} ({cv_results[best_name]:.4f})")
    return best_name


def evaluate(model, X_test: np.ndarray, y_test: np.ndarray, encoder: LabelEncoder, best_name: str):
    y_pred = model.predict(X_test)
    # Only include classes actually present in the test set.
    present_ids = sorted(set(y_test))
    target_names = [encoder.classes_[i] for i in present_ids]

    print(f"\nTest set evaluation — {best_name}\n")
    print(classification_report(
        y_test, y_pred, labels=present_ids, target_names=target_names, zero_division=0,
    ))


def main():
    df = load_data()

    encoder = LabelEncoder()
    y = encoder.fit_transform(df["Category"])
    descriptions = df["Description"].tolist()

    print("\nLabel encoding:")
    for i, cls in enumerate(encoder.classes_):
        print(f"  {i}: {cls} ({(y == i).sum()} samples)")

    X = embed(descriptions)

    X_train, X_test, y_train, y_test = split_train_test(X, y, len(encoder.classes_))
    print(f"\nTrain: {len(X_train)} samples | Test: {len(X_test)} samples")

    candidates = build_candidates()
    best_name = select_best_model(candidates, X_train, y_train)

    best_model = candidates[best_name]
    best_model.fit(X_train, y_train)
    evaluate(best_model, X_test, y_test, encoder, best_name)

    # Refit the selected model on 100% of the data before saving —
    # maximizes coverage for production use now that model selection is done.
    final_model = candidates[best_name]
    final_model.fit(X, y)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(final_model, MODELS_DIR / "classifier.joblib")
    joblib.dump(encoder, MODELS_DIR / "label_encoder.joblib")
    print(f"\nSaved: {best_name} → {MODELS_DIR / 'classifier.joblib'}")
    print(f"Saved: label_encoder → {MODELS_DIR / 'label_encoder.joblib'}")


if __name__ == "__main__":
    main()
