import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer
from typing import List


class ONNXSemanticScorer:

    def __init__(
        self,
        model_path: str = "model_onnx/model_quantized_qint8.onnx",
        tokenizer_path: str = "model_onnx/tokenizer.json",
    ):
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

        self.session = ort.InferenceSession(
            model_path,
            sess_options=opts,
            providers=["CPUExecutionProvider"],
        )

        self.tokenizer = Tokenizer.from_file(tokenizer_path)

        self.tokenizer.enable_padding(
            pad_token="[PAD]",
            pad_id=0,
        )

        self.tokenizer.enable_truncation(
            max_length=128,
        )

    def encode(self, texts: List[str]) -> np.ndarray:

        encodings = self.tokenizer.encode_batch(texts)

        inputs = {
            "input_ids": np.array(
                [e.ids for e in encodings],
                dtype=np.int64,
            ),
            "attention_mask": np.array(
                [e.attention_mask for e in encodings],
                dtype=np.int64,
            ),
            "token_type_ids": np.array(
                [e.type_ids for e in encodings],
                dtype=np.int64,
            ),
        }

        outputs = self.session.run(None, inputs)

        token_embeddings = outputs[0]

        input_mask_expanded = np.expand_dims(
            inputs["attention_mask"],
            axis=-1,
        ).astype(np.float32)

        sum_embeddings = np.sum(
            token_embeddings * input_mask_expanded,
            axis=1,
        )

        sum_mask = np.clip(
            input_mask_expanded.sum(axis=1),
            a_min=1e-9,
            a_max=None,
        )

        embeddings = sum_embeddings / sum_mask

        norms = np.linalg.norm(
            embeddings,
            axis=1,
            keepdims=True,
        )

        return embeddings / np.maximum(norms, 1e-12)