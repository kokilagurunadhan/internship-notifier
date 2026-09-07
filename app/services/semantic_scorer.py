# ============================================================
# SEMANTIC AI RELEVANCE SCORER
# ============================================================

import logging
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer


logger = logging.getLogger(__name__)


# ============================================================
# LOAD QINT8 ONNX MODEL ONCE
# ============================================================

logger.info("Loading semantic AI model")

BASE_DIR = Path(__file__).resolve().parents[2]

MODEL_PATH = (
    BASE_DIR
    / "model_onnx"
    / "model_quantized_qint8.onnx"
)

TOKENIZER_PATH = (
    BASE_DIR
    / "model_onnx"
    / "tokenizer.json"
)


if not MODEL_PATH.exists():
    raise RuntimeError(
        f"Semantic AI model not found: {MODEL_PATH}"
    )

if not TOKENIZER_PATH.exists():
    raise RuntimeError(
        f"Semantic AI tokenizer not found: {TOKENIZER_PATH}"
    )


# ------------------------------------------------------------
# ONNX Runtime configuration
# ------------------------------------------------------------

session_options = ort.SessionOptions()

session_options.intra_op_num_threads = 1
session_options.inter_op_num_threads = 1
session_options.execution_mode = (
    ort.ExecutionMode.ORT_SEQUENTIAL
)


semantic_session = ort.InferenceSession(
    str(MODEL_PATH),
    sess_options=session_options,
    providers=["CPUExecutionProvider"],
)


tokenizer = Tokenizer.from_file(
    str(TOKENIZER_PATH)
)

tokenizer.enable_padding(
    pad_token="[PAD]",
    pad_id=0
)

tokenizer.enable_truncation(
    max_length=128
)


logger.info(
    "Semantic AI model ready: QInt8 ONNX Runtime"
)


# ============================================================
# DOMAIN PROFILES
# ============================================================

DOMAIN_PROFILES = {

    "frontend": """
    Frontend web development.
    User interface development.
    React, Angular, Vue, JavaScript,
    TypeScript, HTML, CSS, Tailwind,
    web applications and UI engineering.
    """,

    "backend": """
    Backend software development.
    Server-side application development.
    APIs, databases and backend services.
    Python, Java, Node.js, Django,
    Flask, FastAPI, Spring and REST APIs.
    """,

    "full stack": """
    Full stack web application development.
    Frontend and backend development.
    React, JavaScript, Python, Node.js,
    APIs, databases and web applications.
    """,

    "data": """
    Data analysis and data engineering.
    Data analytics, SQL, Python,
    Pandas, NumPy, Power BI, Tableau,
    databases and business intelligence.
    """,

    "machine learning": """
    Machine learning and artificial intelligence.
    Deep learning, neural networks,
    NLP, computer vision, LLMs,
    TensorFlow, PyTorch and AI systems.
    """,

    "software": """
    General software engineering and software development.
    Programming, application development,
    software systems, Python, Java,
    C++, C# and software engineering.
    """,

    "embedded": """
    Embedded systems and firmware development.
    Microcontrollers, microprocessors,
    embedded software, firmware,
    ARM, STM32, Arduino, ESP32 and RTOS.
    """,

    "testing": """
    Software testing and quality assurance.
    QA engineering, test automation,
    Selenium, Cypress, Playwright,
    pytest and software quality.
    """,

    "hr": """
    Human resources, recruitment and talent acquisition.
    Hiring, recruiting, employee operations,
    talent management and people operations.
    """,

    "design": """
    UI UX and product design.
    User interface design,
    user experience design,
    Figma, product design and visual design.
    """
}


# ============================================================
# NORMALIZE DOMAIN
# ============================================================

def normalize_domain(domain):

    if not domain:
        return ""

    return domain.strip().lower()


# ============================================================
# DOMAIN PROFILE
# ============================================================

def get_domain_profile(domain):

    domain = normalize_domain(domain)

    if not domain:
        return ""

    if domain in DOMAIN_PROFILES:

        return DOMAIN_PROFILES[domain]

    return f"""
    Internship role related to:
    {domain}
    """


# ============================================================
# ONNX EMBEDDING
# ============================================================

def _encode_texts(texts):
    """
    Generate sentence embeddings using the
    QInt8 ONNX version of all-MiniLM-L6-v2.

    Processing is equivalent to the original
    SentenceTransformer mean-pooling + L2
    normalization behavior.
    """

    encodings = tokenizer.encode_batch(
        texts
    )

    inputs = {
        "input_ids": np.array(
            [encoding.ids for encoding in encodings],
            dtype=np.int64
        ),

        "attention_mask": np.array(
            [
                encoding.attention_mask
                for encoding in encodings
            ],
            dtype=np.int64
        ),

        "token_type_ids": np.array(
            [
                encoding.type_ids
                for encoding in encodings
            ],
            dtype=np.int64
        ),
    }

    outputs = semantic_session.run(
        None,
        inputs
    )

    token_embeddings = outputs[0]

    # --------------------------------------------------------
    # Mean pooling using attention mask
    # --------------------------------------------------------

    input_mask_expanded = np.expand_dims(
        inputs["attention_mask"],
        axis=-1
    ).astype(np.float32)

    sum_embeddings = np.sum(
        token_embeddings
        * input_mask_expanded,
        axis=1
    )

    sum_mask = np.clip(
        input_mask_expanded.sum(axis=1),
        a_min=1e-9,
        a_max=None
    )

    embeddings = (
        sum_embeddings
        / sum_mask
    )

    # --------------------------------------------------------
    # L2 normalization
    # --------------------------------------------------------

    norms = np.linalg.norm(
        embeddings,
        axis=1,
        keepdims=True
    )

    embeddings = (
        embeddings
        / np.maximum(norms, 1e-12)
    )

    return embeddings


# ============================================================
# SEMANTIC TITLE SCORE
# ============================================================

def calculate_semantic_score(
    job_title,
    user_domain,
    job_description=""
):
    """
    Semantic AI primarily evaluates the JOB TITLE.

    Keyword logic is responsible for detailed
    description matching.

    job_description is intentionally NOT used
    for semantic scoring.

    Uses the QInt8 ONNX version of
    all-MiniLM-L6-v2.
    """

    if not user_domain:
        return 50.0

    job_title = (
        job_title or ""
    ).strip()

    if not job_title:
        return 0.0

    domain_profile = get_domain_profile(
        user_domain
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Semantic AI sees the ROLE/TITLE only.
    # --------------------------------------------------------

    job_text = f"""
    Internship role title:
    {job_title}
    """

    embeddings = _encode_texts(
        [
            domain_profile,
            job_text
        ]
    )

    # Both embeddings are already L2 normalized,
    # therefore their dot product equals cosine similarity.
    similarity = float(
        np.dot(
            embeddings[0],
            embeddings[1]
        )
    )

    score = float(
        similarity * 100
    )

    return round(
        max(
            0.0,
            min(score, 100.0)
        ),
        2
    )