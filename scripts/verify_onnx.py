import os
import psutil
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sentence_transformers import SentenceTransformer
from tests.onnx_scorer_test import ONNXSemanticScorer


def print_memory(tag: str):
    process = psutil.Process(os.getpid())
    memory_mb = process.memory_info().rss / (1024 * 1024)
    print(f"[{tag}] Process RSS: {memory_mb:.2f} MB")


print_memory("Baseline Start")


print("\nLoading PyTorch model...")
st_model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2"
)

print_memory("After PyTorch Load")


print("\nLoading ONNX model...")
onnx_scorer = ONNXSemanticScorer()

print_memory("After ONNX Load")


pairs = [
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


print("\n--- Drift Analysis ---")


for domain_profile, job_text in pairs:

    st_vecs = st_model.encode(
        [domain_profile, job_text]
    )

    st_score = (
        float(np.dot(st_vecs[0], st_vecs[1]))
        * 100.0
    )

    onnx_vecs = onnx_scorer.encode(
        [domain_profile, job_text]
    )

    onnx_score = (
        float(np.dot(onnx_vecs[0], onnx_vecs[1]))
        * 100.0
    )

    diff = abs(st_score - onnx_score)

    print(
        f"Domain: {domain_profile[:30]:<30} | "
        f"PyTorch: {st_score:6.2f} | "
        f"ONNX: {onnx_score:6.2f} | "
        f"Diff: {diff:5.2f}"
    )


print_memory("Final")