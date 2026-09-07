import numpy as np

import app.services.relevance_engine as relevance_engine
from app.services.semantic_scorer import get_domain_profile
from tests.onnx_scorer_test import ONNXSemanticScorer

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# ============================================================
# QINT8 ONNX SEMANTIC SCORER
# ============================================================

onnx_scorer = ONNXSemanticScorer()


def calculate_onnx_semantic_score(
    job_title,
    user_domain,
    job_description="",
):
    """
    Same semantic-scoring logic as production,
    but using the QInt8 ONNX model.
    """

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
# TEST CASES
# ============================================================

TEST_CASES = [
    {
        "title": "Software Engineering Intern",
        "description": "Python backend development and software engineering",
        "domain": "software",
    },
    {
        "title": "Python Backend Developer Intern",
        "description": "Build APIs using Python and backend technologies",
        "domain": "backend",
    },
    {
        "title": "Frontend React Developer Intern",
        "description": "React JavaScript HTML CSS frontend development",
        "domain": "frontend",
    },
    {
        "title": "Data Analyst Intern",
        "description": "SQL Python Pandas data analysis and visualization",
        "domain": "data",
    },
    {
        "title": "Machine Learning Intern",
        "description": "Python machine learning model development",
        "domain": "machine learning",
    },
    {
        "title": "Embedded Systems Intern",
        "description": "C C++ microcontroller firmware embedded systems",
        "domain": "embedded",
    },
    {
        "title": "Software Testing Intern",
        "description": "Manual testing automation testing test cases",
        "domain": "testing",
    },
    {
        "title": "UI UX Design Intern",
        "description": "User interface user experience Figma design",
        "domain": "design",
    },
    {
        "title": "Human Resources Intern",
        "description": "Recruitment employee engagement HR operations",
        "domain": "hr",
    },

    # Borderline / weaker relevance cases
    {
        "title": "Technology Intern",
        "description": "",
        "domain": "software",
    },
    {
        "title": "Business Analyst Intern",
        "description": "Business requirements and reporting",
        "domain": "software",
    },
    {
        "title": "Python Intern",
        "description": "Python programming",
        "domain": "software",
    },
    {
        "title": "Engineering Intern",
        "description": "Technical engineering projects",
        "domain": "embedded",
    },
    {
        "title": "Data Intern",
        "description": "Working with data",
        "domain": "data",
    },
    {
        "title": "Developer Intern",
        "description": "Application development",
        "domain": "software",
    },
]


# ============================================================
# RUN TEST
# ============================================================

def run_test():

    print()
    print("=" * 90)
    print("PRODUCTION RELEVANCE THRESHOLD TEST")
    print("=" * 90)
    print()

    print("Formula:")
    print("Final Score = Keyword Score × 0.60 + Semantic Score × 0.40")
    print("Notification threshold = 50")
    print()

    original_semantic_score = (
        relevance_engine.calculate_semantic_score
    )

    results = []

    try:

        for case in TEST_CASES:

            title = case["title"]
            description = case["description"]
            domain = case["domain"]

            # ------------------------------------------------
            # PyTorch / CURRENT PRODUCTION MODEL
            # ------------------------------------------------

            pytorch_result = (
                relevance_engine.calculate_relevance_score(
                    job_title=title,
                    job_description=description,
                    user_domain=domain,
                )
            )

            # ------------------------------------------------
            # Replace ONLY semantic function with QInt8
            # ------------------------------------------------

            relevance_engine.calculate_semantic_score = (
                calculate_onnx_semantic_score
            )

            onnx_result = (
                relevance_engine.calculate_relevance_score(
                    job_title=title,
                    job_description=description,
                    user_domain=domain,
                )
            )

            # Restore production semantic function
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
                {
                    "title": title,
                    "pytorch": pytorch_final,
                    "onnx": onnx_final,
                    "difference": difference,
                    "decision_match": decision_match,
                }
            )

            print(f"Job      : {title}")
            print(f"Domain   : {domain}")
            print(
                f"Keyword  : "
                f"{pytorch_result['keyword_score']:.2f}"
            )
            print(
                f"Semantic : "
                f"{pytorch_result['semantic_score']:.2f}"
                f"  → PyTorch"
            )
            print(
                f"Final    : "
                f"{pytorch_final:.2f}"
                f"  [{pytorch_decision}]"
            )
            print(
                f"QInt8    : "
                f"{onnx_final:.2f}"
                f"  [{onnx_decision}]"
            )
            print(
                f"Difference: "
                f"{difference:.2f}"
            )

            if not decision_match:
                print(
                    "❌ DECISION FLIP!"
                )
            elif difference <= 2:
                print(
                    "✅ CLOSE"
                )
            else:
                print(
                    "⚠️ SCORE DRIFT"
                )

            print("-" * 90)

    finally:
        relevance_engine.calculate_semantic_score = (
            original_semantic_score
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 90)
    print("SUMMARY")
    print("=" * 90)

    decision_flips = [
        r for r in results
        if not r["decision_match"]
    ]

    score_drift = [
        r for r in results
        if r["difference"] > 2
    ]

    print(
        f"Total cases       : {len(results)}"
    )
    print(
        f"Decision flips    : {len(decision_flips)}"
    )
    print(
        f"Score drift >2    : {len(score_drift)}"
    )

    print()

    if decision_flips:

        print("❌ PRODUCTION THRESHOLD TEST FAILED")
        print()
        print("Cases where 50-point decision changed:")

        for result in decision_flips:
            print(
                f"- {result['title']}"
            )
            print(
                f"  PyTorch = "
                f"{result['pytorch']:.2f}"
            )
            print(
                f"  QInt8   = "
                f"{result['onnx']:.2f}"
            )

        print()
        print(
            "QInt8 must NOT replace PyTorch yet."
        )

    else:

        print(
            "✅ NO PRODUCTION DECISION FLIPS"
        )
        print()
        print(
            "QInt8 preserved the >=50 relevance "
            "threshold decisions for all tested cases."
        )

    print()
    print("=" * 90)


if __name__ == "__main__":
    run_test()