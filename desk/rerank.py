"""Cross-encoder reranker: BAAI/bge-reranker-v2-m3 (Apache-2.0), int8 ONNX export from
onnx-community/bge-reranker-v2-m3-ONNX, run with onnxruntime on CPU. Files cached in .cache/ (git-ignored)."""
import os

import numpy as np

from .embed import CACHE

REPO = "onnx-community/bge-reranker-v2-m3-ONNX"
BASE_MODEL = "BAAI/bge-reranker-v2-m3"
ONNX_FILE = "onnx/model_int8.onnx"
MAX_LEN = 256  # 512 costs ~3.5x more CPU time per letter


class Reranker:
    def __init__(self):
        import onnxruntime as ort
        from huggingface_hub import snapshot_download
        from tokenizers import Tokenizer
        d = snapshot_download(REPO, cache_dir=str(CACHE), allow_patterns=[ONNX_FILE, "tokenizer.json", "config.json"])
        self.tok = Tokenizer.from_file(os.path.join(d, "tokenizer.json"))
        self.tok.enable_truncation(MAX_LEN, strategy="longest_first")
        self.tok.enable_padding(pad_id=self.tok.token_to_id("<pad>"), pad_token="<pad>")
        so = ort.SessionOptions()
        so.intra_op_num_threads = os.cpu_count()
        self.sess = ort.InferenceSession(os.path.join(d, ONNX_FILE), so, providers=["CPUExecutionProvider"])
        self.inputs = {i.name for i in self.sess.get_inputs()}

    def scores(self, query, passages, batch=8):
        out = []
        for i in range(0, len(passages), batch):
            enc = self.tok.encode_batch([(query, p) for p in passages[i:i + batch]])
            feed = {"input_ids": np.array([e.ids for e in enc], dtype=np.int64),
                    "attention_mask": np.array([e.attention_mask for e in enc], dtype=np.int64)}
            if "token_type_ids" in self.inputs:
                feed["token_type_ids"] = np.zeros_like(feed["input_ids"])
            logits = self.sess.run(None, feed)[0].reshape(-1)
            out.extend((1 / (1 + np.exp(-logits))).tolist())
        return out


_INSTANCE = None


def get():
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = Reranker()
    return _INSTANCE


def warm_up() -> float:
    """Load model + ORT session and run one tiny pair, so the first letter doesn't pay for it. Returns seconds."""
    import time
    t0 = time.perf_counter()
    get().scores("warm up", ["warm up"])
    return round(time.perf_counter() - t0, 2)
