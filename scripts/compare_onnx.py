import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from sentence_transformers import SentenceTransformer
from tests.onnx_scorer_test import ONNXSemanticScorer


PAIRS = [
    (
        "Software Engineer Python Backend",
        "Software Engineering Intern",
    ),
    (
        "Frontend React Developer",
        "Frontend Developer Intern",
    ),
    (
        "Data Analyst SQL Pandas",
        "Data Analyst Intern",
    ),
    (
        "Machine Learning PyTorch",
        "ML Intern",
    ),
    (
        "Embedded C C++ Systems",
        "Embedded Intern",
    ),
]


def cosine_score(a, b):
    return float(np.dot(a, b)) * 100.0


print("Loading PyTorch model...")
pytorch = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2"
)

print("Loading ONNX model...")
onnx = ONNXSemanticScorer()

print("\n=== SCORE COMPARISON ===\n")

for domain, job in PAIRS:

    pytorch_vectors = pytorch.encode(
        [domain, job],
        normalize_embeddings=True,
    )

    onnx_vectors = onnx.encode(
        [domain, job]
    )

    pytorch_score = cosine_score(
        pytorch_vectors[0],
        pytorch_vectors[1],
    )

    onnx_score = cosine_score(
        onnx_vectors[0],
        onnx_vectors[1],
    )

    difference = abs(
        pytorch_score - onnx_score
    )

    print(f"Domain : {domain}")
    print(f"Job    : {job}")
    print(f"PyTorch: {pytorch_score:.4f}")
    print(f"ONNX   : {onnx_score:.4f}")
    print(f"Diff   : {difference:.4f}")
    print("-" * 60)