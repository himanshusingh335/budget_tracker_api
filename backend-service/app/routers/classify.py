import threading
from pathlib import Path

import joblib
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

router = APIRouter(prefix="/classify", tags=["Classify"])

_MODELS_DIR = Path(__file__).parent.parent.parent / "models"
_lock = threading.Lock()
_cache: dict = {}


def _load_models():
    if _cache:
        return _cache["st"], _cache["clf"], _cache["encoder"]
    with _lock:
        if _cache:
            return _cache["st"], _cache["clf"], _cache["encoder"]
        try:
            st = SentenceTransformer("all-MiniLM-L6-v2")
            clf = joblib.load(_MODELS_DIR / "classifier.joblib")
            encoder = joblib.load(_MODELS_DIR / "label_encoder.joblib")
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Model load failed: {exc}") from exc
        _cache.update(st=st, clf=clf, encoder=encoder)
    return _cache["st"], _cache["clf"], _cache["encoder"]


class ClassifyRequest(BaseModel):
    description: str


class ClassifyResponse(BaseModel):
    category: str
    confidence: float


@router.post("", response_model=ClassifyResponse, operation_id="classify_description")
def classify(payload: ClassifyRequest):
    """Predict the budget category for a transaction description.

    Uses a trained LinearSVC with sentence-transformer embeddings to map free-text
    descriptions to one of: Auto, Entertainment, Food, Home, Medical, Personal Items,
    Travel, Utilities, Other.
    """
    if not payload.description.strip():
        raise HTTPException(status_code=400, detail="description must not be empty")
    st, clf, encoder = _load_models()
    embedding = st.encode([payload.description], normalize_embeddings=True, show_progress_bar=False)
    scores = clf.decision_function(embedding)
    pred_idx = int(np.argmax(scores, axis=1)[0])
    category = str(encoder.inverse_transform([pred_idx])[0])
    confidence = round(float(scores[0][pred_idx]), 4)
    return ClassifyResponse(category=category, confidence=confidence)
