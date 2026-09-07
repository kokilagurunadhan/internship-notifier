import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

import app.services.relevance_engine as relevance_engine
from app.services.semantic_scorer import get_domain_profile
from tests.onnx_scorer_test import ONNXSemanticScorer


# ============================================================
# QINT8 ONNX SEMANTIC SCORER
# ============================================================

onnx_scorer = ONNXSemanticScorer()


def calculate_onnx_semantic_score(
    job_title,
    user_domain,
    job_description="",
):
    if not user_domain:
        return 50.0

    job_title = (job_title or "").strip()

    if not job_title:
        return 0.0

    domain_profile = get_domain_profile(user_domain)

    job_text = f"""
    Internship role title:
    {job_title}
    """

    embeddings = onnx_scorer.encode(
        [domain_profile, job_text]
    )

    similarity = float(
        np.dot(
            embeddings[0],
            embeddings[1],
        )
    )

    score = similarity * 100

    return round(
        max(0.0, min(score, 100.0)),
        2,
    )


# ============================================================
# BOUNDARY TEST CASES
# ============================================================

TEST_CASES = [
    ("Python Intern", "software"),
    ("Python Developer Intern", "software"),
    ("Software Developer Intern", "software"),
    ("Backend Developer Intern", "backend"),
    ("Frontend Developer Intern", "frontend"),
    ("Data Analyst Intern", "data"),
    ("Machine Learning Intern", "machine learning"),
    ("Embedded Intern", "embedded"),
    ("Testing Intern", "testing"),
    ("Developer Intern", "software"),
    ("Technology Intern", "software"),
    ("Engineering Intern", "embedded"),
    ("Data Intern", "data"),
    ("Analyst Intern", "data"),
    ("Programming Intern", "software"),
    ("Technical Intern", "software"),
    ("Software Intern", "software"),
    ("Web Developer Intern", "software"),
    ("Application Developer Intern", "software"),
    ("Computer Science Intern", "software"),
]


# ============================================================
# RUN TEST
# ============================================================

def run_test():

    print()
    print("=" * 100)
    print("PRODUCTION RELEVANCE 50-POINT BOUNDARY TEST")
    print("=" * 100)
    print()

    print("Locked rule:")
    print("Final relevance >= 50  -> NOTIFICATION")
    print("Final relevance <  50  -> REJECT")
    print()

    original_semantic_score = (
        relevance_engine.calculate_semantic_score
    )

    results = []

    try:

        for title, domain in TEST_CASES:

            # ------------------------------------------------
            # Production PyTorch
            # ------------------------------------------------

            pytorch_result = (
                relevance_engine.calculate_relevance_score(
                    job_title=title,
                    job_description="",
                    user_domain=domain,
                )
            )

            # ------------------------------------------------
            # QInt8
            # ------------------------------------------------

            relevance_engine.calculate_semantic_score = (
                calculate_onnx_semantic_score
            )

            onnx_result = (
                relevance_engine.calculate_relevance_score(
                    job_title=title,
                    job_description="",
                    user_domain=domain,
                )
            )

            relevance_engine.calculate_semantic_score = (
                original_semantic_score
            )

            pytorch_final = float(
                pytorch_result["final_score"]
            )

            onnx_final = float(
                onnx_result["final_score"]
            )

            difference = abs(
                pytorch_final - onnx_final
            )

            pytorch_decision = (
                "PASS"
                if pytorch_final >= 50
                else "REJECT"
            )

            onnx_decision = (
                "PASS"
                if onnx_final >= 50
                else "REJECT"
            )

            decision_match = (
                pytorch_decision == onnx_decision
            )

            results.append(
                (
                    title,
                    pytorch_final,
                    onnx_final,
                    difference,
                    decision_match,
                )
            )

            print(f"Job       : {title}")
            print(f"Domain    : {domain}")
            print(
                f"PyTorch   : "
                f"{pytorch_final:.2f} "
                f"[{pytorch_decision}]"
            )
            print(
                f"QInt8     : "
                f"{onnx_final:.2f} "
                f"[{onnx_decision}]"
            )
            print(
                f"Difference: "
                f"{difference:.2f}"
            )

            if not decision_match:
                print(
                    "❌ DECISION FLIP — CRITICAL"
                )
            elif (
                abs(pytorch_final - 50) <= 5
                or abs(onnx_final - 50) <= 5
            ):
                print(
                    "🎯 NEAR 50-POINT BOUNDARY"
                )
            else:
                print(
                    "✅ SAME DECISION"
                )

            print("-" * 100)

    finally:

        relevance_engine.calculate_semantic_score = (
            original_semantic_score
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    decision_flips = [
        result
        for result in results
        if not result[4]
    ]

    boundary_cases = [
        result
        for result in results
        if (
            abs(result[1] - 50) <= 5
            or abs(result[2] - 50) <= 5
        )
    ]

    print()
    print("=" * 100)
    print("BOUNDARY TEST SUMMARY")
    print("=" * 100)

    print(
        f"Total cases          : {len(results)}"
    )

    print(
        f"Near-boundary cases  : "
        f"{len(boundary_cases)}"
    )

    print(
        f"Decision flips       : "
        f"{len(decision_flips)}"
    )

    print()

    if decision_flips:

        print(
            "❌ BOUNDARY TEST FAILED"
        )

        print()
        print(
            "QInt8 changed the production "
            ">=50 decision for:"
        )

        for result in decision_flips:

            print(
                f"- {result[0]}"
            )

            print(
                f"  PyTorch: "
                f"{result[1]:.2f}"
            )

            print(
                f"  QInt8:   "
                f"{result[2]:.2f}"
            )

    else:

        print(
            "✅ BOUNDARY TEST PASSED"
        )

        print()
        print(
            "QInt8 preserved the production "
            "50-point decision boundary."
        )

    print()
    print("=" * 100)


if __name__ == "__main__":
    run_test()