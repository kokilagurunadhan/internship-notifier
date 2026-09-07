import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
import psutil
import numpy as np

from tests.onnx_scorer_test import ONNXSemanticScorer


def memory_mb():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)


print(f"[Start] RSS: {memory_mb():.2f} MB")

print("\nLoading ONNX INT8 model...")

scorer = ONNXSemanticScorer()

print(f"[After ONNX Load] RSS: {memory_mb():.2f} MB")

print("\nRunning inference...")

texts = [
    "Software Engineer Python Backend",
    "Software Engineering Intern",
    "Data Analyst SQL Pandas",
    "Data Analyst Intern",
    "Machine Learning PyTorch",
    "ML Intern",
]

embeddings = scorer.encode(texts)

print(f"Embedding shape: {embeddings.shape}")
print(f"Embedding dtype: {embeddings.dtype}")

print(f"[After Inference] RSS: {memory_mb():.2f} MB")

print("\nONNX-ONLY MEMORY TEST COMPLETE")