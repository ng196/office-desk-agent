"""Embeddings: intfloat/multilingual-e5-small (MIT) run with fastembed (ONNX, CPU).

e5 needs "query: " / "passage: " prefixes (tests.md 12.4). Model files are cached
in .cache/ inside the repo (git-ignored); copy that folder to the offline office box.
"""
import os
from pathlib import Path

MODEL = "intfloat/multilingual-e5-small"
DIM = 384
CACHE = Path(os.environ.get("DESK_CACHE", Path(__file__).resolve().parent.parent / ".cache"))

QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "


class Embedder:
    def __init__(self):
        from fastembed import TextEmbedding
        from fastembed.common.model_description import ModelSource, PoolingType
        known = {m["model"] for m in TextEmbedding.list_supported_models()}
        if MODEL not in known:
            TextEmbedding.add_custom_model(
                model=MODEL, pooling=PoolingType.MEAN, normalization=True,
                sources=ModelSource(hf=MODEL), dim=DIM, model_file="onnx/model.onnx")
        self.model = TextEmbedding(MODEL, cache_dir=str(CACHE), threads=os.cpu_count())
        self.calls = []  # every string sent to the model (for the prefix unit test)

    def _run(self, texts):
        self.calls.extend(texts)
        return [v.tolist() for v in self.model.embed(texts, batch_size=32)]

    def passages(self, texts):
        return self._run([PASSAGE_PREFIX + t for t in texts])

    def query(self, text):
        return self._run([QUERY_PREFIX + text])[0]
