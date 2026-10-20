"""Sentence embeddings for /classify, using all-MiniLM-L6-v2 run through onnxruntime.

This replaces sentence-transformers + torch with the model's published int8
ONNX export. It gives the same 384-dim mean-pooled, L2-normalized vectors
for a fraction of the memory. classifier-training/ imports this module too,
so training and serving always embed text the same way.

Run `python -m app.embedder` to download the model files into
models/minilm/. The Docker build does this so the image works offline.
"""
import urllib.request
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

MODEL_DIR = Path(__file__).parent.parent / "models" / "minilm"

# Pinned Hub revision so every build gets byte-identical weights.
_HF_BASE = (
    "https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/"
    "1110a243fdf4706b3f48f1d95db1a4f5529b4d41/"
)
_FILES = {
    "model.onnx": "onnx/model_qint8_arm64.onnx",
    "tokenizer.json": "tokenizer.json",
}
_MAX_SEQ_LENGTH = 256  # matches sentence-transformers' setting for this model


def download(model_dir: Path = MODEL_DIR) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    for local_name, remote_path in _FILES.items():
        dest = model_dir / local_name
        if not dest.exists():
            urllib.request.urlretrieve(_HF_BASE + remote_path, dest)


class Embedder:
    def __init__(self, model_dir: Path = MODEL_DIR):
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        # The arena allocator keeps peak buffers reserved forever; inputs here are
        # a handful of tokens, so freeing per call costs nothing and saves RAM.
        opts.enable_cpu_mem_arena = False
        self._session = ort.InferenceSession(
            str(model_dir / "model.onnx"), opts, providers=["CPUExecutionProvider"]
        )
        self._tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self._tokenizer.enable_truncation(_MAX_SEQ_LENGTH)
        self._tokenizer.enable_padding()

    def encode(self, texts: list[str], batch_size: int = 64) -> np.ndarray:
        return np.vstack([self._encode_batch(texts[i:i + batch_size]) for i in range(0, len(texts), batch_size)])

    def _encode_batch(self, texts: list[str]) -> np.ndarray:
        encodings = self._tokenizer.encode_batch(texts)
        input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
        token_embeddings = self._session.run(None, {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": np.zeros_like(input_ids),
        })[0]
        # Mean pooling over real (non-padding) tokens, then L2 normalize.
        mask = attention_mask[..., None].astype(np.float32)
        pooled = (token_embeddings * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
        return pooled / np.linalg.norm(pooled, axis=1, keepdims=True)


if __name__ == "__main__":
    download()
    print(f"Model files ready in {MODEL_DIR}")
