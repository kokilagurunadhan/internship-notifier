# 🚀 Internship Notifier

An automated internship discovery and notification system that searches for relevant internship opportunities, filters and ranks them using AI-based semantic relevance scoring, prevents duplicate notifications, and delivers grouped email alerts.

The system is designed as a production-style asynchronous application with automated scheduling, PostgreSQL persistence, notification idempotency, retry handling, and retention management.

---

## 🎯 What Problem Does It Solve?

Finding internships manually across multiple companies and job platforms is repetitive and time-consuming.

Internship Notifier automates this process:

```text
User Subscription
       ↓
12-Hour Scheduler
       ↓
Grouped SerpAPI Search
       ↓
Parse / Normalize
       ↓
Strict Internship Filter
       ↓
AI Relevance Scoring
       ↓
Database URL Uniqueness
       ↓
7-Day User Notification Check
       ↓
Create PENDING Notification
       ↓
Group Notifications by Email
       ↓
Idempotency Check
       ↓
Send Email Digest
       ↓
SENT / Retry / FAILED
       ↓
45-Day Retention Cleanup
```

---

# ✨ Key Features

### 🔎 Automated Internship Discovery

* Searches internship opportunities automatically.
* Uses SerpAPI for search discovery.
* Searches are grouped to reduce unnecessary API requests.
* Supports company and domain/role-based subscriptions.

### 🎯 Strict Internship Filtering

The system verifies that discovered jobs are actually internships before they enter the relevance pipeline.

### 🤖 AI-Based Relevance Scoring

The project uses `all-MiniLM-L6-v2` for semantic similarity scoring.

The production inference pipeline uses:

* ONNX Runtime
* Dynamically quantized INT8 model
* Tokenizers
* Mean pooling
* L2 normalization
* Cosine similarity

The minimum relevance threshold is:

```text
50
```

Only opportunities meeting the required relevance threshold proceed to notification creation.

### ⏰ Automated 12-Hour Scheduler

The internship discovery process runs automatically every:

```text
12 hours
```

The scheduler is configured with:

* UTC timezone
* Maximum one concurrent scheduler instance
* Coalescing of missed executions
* Per-subscription-group failure isolation

### 🛡️ Duplicate Protection

The system uses multiple layers of duplicate protection.

#### Global internship uniqueness

Internships are identified using canonicalized URLs.

This prevents tracking parameters and URL variations from creating duplicate global internship records.

#### User notification duplicate protection

A user is prevented from receiving the same internship repeatedly within the configured 7-day notification window.

### 📧 Reliable Email Notification System

Notifications are created before email delivery.

The system supports:

* PENDING state
* PROCESSING state
* SENT state
* FAILED state
* Retry handling
* Exponential/backoff-style retry scheduling
* Maximum retry attempts
* Persistent idempotency keys
* Concurrent email send limits
* Zombie PROCESSING recovery
* Maximum 15 internships per email

### 🔐 Notification Idempotency

Every notification has a persistent idempotency key.

The same key is reused during retries to prevent accidental duplicate email delivery.

### 🔄 Email Retry Handling

Failed email attempts remain retryable.

The production configuration supports:

```text
Maximum attempts: 5
Base retry delay: 5 minutes
```

After the maximum retry count is reached, the notification is marked permanently as:

```text
FAILED
```

### 🧹 45-Day Retention

Internships that have not been seen for more than 45 days are removed from the database.

The cleanup uses `last_seen_at` so that actively rediscovered internships are retained even if they were originally created more than 45 days ago.

Related notifications are removed through the database relationship.

---

# 🧠 AI / Semantic Relevance Pipeline

The relevance engine combines keyword-based and semantic signals to determine whether an internship matches a user's requested domain.

The production semantic scorer uses:

```text
all-MiniLM-L6-v2
        ↓
ONNX Runtime
        ↓
QInt8 Dynamic Quantization
        ↓
Tokenization
        ↓
Mean Pooling
        ↓
L2 Normalization
        ↓
Cosine Similarity
```

The production ONNX model was validated against the original PyTorch implementation.

The optimized inference path significantly reduces runtime dependency and memory requirements, making it more suitable for constrained deployment environments.

---

# 🏗️ System Architecture

```text
                    ┌───────────────────┐
                    │      User         │
                    │ Email + Company   │
                    │ Domain / Role     │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │   Subscription    │
                    │     PostgreSQL    │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │  12-Hour Scheduler│
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │      SerpAPI      │
                    │  Grouped Search   │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │ Parse / Normalize │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │ Strict Internship │
                    │      Filter       │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │ Relevance Engine  │
                    │   Score >= 50     │
                    └─────────┬─────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
                 LOW SCORE           RELEVANT
                    │                   │
                    ▼                   ▼
                  STOP             URL Check
                                        │
                              ┌─────────┴─────────┐
                              │                   │
                           NEW URL           EXISTING URL
                              │                   │
                              ▼                   ▼
                       Global Internship      Reuse
                           Record             Existing
                              │                   │
                              └─────────┬─────────┘
                                        │
                                        ▼
                              7-Day User Duplicate
                                      Check
                                        │
                                        ▼
                              Create PENDING
                                 Notification
                                        │
                                        ▼
                              Group by Email
                                        │
                                        ▼
                                  Idempotency
                                        │
                                        ▼
                                Email Dispatcher
                                        │
                              ┌─────────┴─────────┐
                              │                   │
                              ▼                   ▼
                            SENT              RETRY
                                                  │
                                                  ▼
                                               FAILED
```

---

# 🗄️ Database

The application uses:

* PostgreSQL
* SQLAlchemy
* asyncpg
* Alembic
* pgvector extension

Main entities include:

```text
Subscription
     │
     └──────────────┐
                    │
                    ▼
               Notification
                    │
                    ▼
                Internship
```

### Subscription uniqueness

A subscription is uniquely identified by:

```text
user_email + company + domain
```

This allows the same user to track multiple companies and domains while preventing the exact same subscription from being duplicated.

Example:

```text
user@example.com + Amazon + software
user@example.com + Google + software
user@example.com + Microsoft + software
user@example.com + Amazon + data
```

All can coexist.

---

# 📬 Notification Lifecycle

```text
PENDING
   │
   ▼
PROCESSING
   │
   ├──────────────► SENT
   │
   └──────────────► RETRY
                       │
                       ▼
                   PROCESSING
                       │
                       └────► FAILED
```

The system uses atomic notification claiming to prevent multiple workers from processing the same notification simultaneously.

Database row locking with:

```text
SELECT ... FOR UPDATE SKIP LOCKED
```

is used during notification claiming.

---

# 🛡️ Concurrency Safety

The notification system was tested under concurrent execution.

Multiple workers attempted to create the same notification simultaneously.

Expected result:

```text
10 concurrent workers
        ↓
1 notification created
        ↓
9 duplicate attempts blocked
```

The database uniqueness constraint prevents duplicate notification records.

---

# 🧪 Testing

The project has a comprehensive automated test suite.

Current regression result:

```text
193 passed
```

The production hardening tests cover areas including:

* URL canonicalization
* Duplicate internship detection
* 7-day notification protection
* Notification idempotency
* Concurrent notification creation
* Email retry handling
* Maximum retry failure
* 45-day retention cleanup
* Scheduler configuration
* ONNX relevance scoring
* Relevance threshold boundaries
* API behavior
* Database behavior

A real production E2E cycle was also verified.

The production test confirmed:

```text
SerpAPI search
      ↓
Internship discovered
      ↓
Filtering
      ↓
Relevance scoring
      ↓
Notification created
      ↓
Email sent
      ↓
Notification = SENT
```

A second production cycle correctly reused the existing internship and blocked the duplicate notification within the 7-day window.

---

# 🌐 Deployment

The application is deployed as a FastAPI web service with PostgreSQL.

Production components:

```text
FastAPI
   │
   ├── PostgreSQL
   │
   ├── SerpAPI
   │
   ├── Resend
   │
   ├── APScheduler
   │
   └── ONNX Runtime
```

Production health endpoint:

```text
GET /healthz
```

Expected response:

```json
{
  "status": "healthy",
  "database": "connected"
}
```

---

# 🛠️ Technology Stack

| Category                | Technology                 |
| ----------------------- | -------------------------- |
| Backend                 | FastAPI                    |
| Language                | Python                     |
| Database                | PostgreSQL                 |
| ORM                     | SQLAlchemy                 |
| Database Driver         | asyncpg                    |
| Migrations              | Alembic                    |
| Search                  | SerpAPI                    |
| AI Model                | all-MiniLM-L6-v2           |
| AI Runtime              | ONNX Runtime               |
| Model Optimization      | QInt8 Dynamic Quantization |
| Tokenization            | Hugging Face Tokenizers    |
| Scheduler               | APScheduler                |
| Email                   | Resend                     |
| Vector Database Support | pgvector                   |
| Frontend                | HTML, CSS, JavaScript      |
| Deployment              | Render                     |
| Testing                 | Pytest                     |
| Version Control         | Git / GitHub               |

---

# 📁 Project Structure

```text
internship-notifier/
│
├── app/
│   ├── api/
│   │   ├── internships.py
│   │   └── subscriptions.py
│   │
│   ├── database/
│   │   └── database.py
│   │
│   ├── models/
│   │   ├── internship.py
│   │   ├── notification.py
│   │   └── subscription.py
│   │
│   ├── schemas/
│   │
│   └── services/
│       ├── internship_search.py
│       ├── internship_service.py
│       ├── notification_dispatcher.py
│       ├── pipeline_processor.py
│       ├── scheduler.py
│       └── semantic_scorer.py
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   ├── script.js
│   ├── internships.html
│   ├── internships.css
│   └── internships.js
│
├── model_onnx/
│   ├── config.json
│   ├── model_quantized_qint8.onnx
│   ├── tokenizer.json
│   ├── tokenizer_config.json
│   ├── special_tokens_map.json
│   └── vocab.txt
│
├── scripts/
│   ├── export_onnx.py
│   ├── compare_onnx.py
│   └── verification scripts
│
├── tests/
│
├── alembic/
│
├── main.py
├── requirements.txt
├── .env.example
└── README.md
```

---

# 🚀 Local Setup

## 1. Clone the repository

```bash
git clone https://github.com/kokilagurunadhan/internship-notifier.git
cd internship-notifier
```

## 2. Create a virtual environment

Windows:

```powershell
python -m venv venv
venv\Scripts\activate
```

Linux/macOS:

```bash
python -m venv venv
source venv/bin/activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Configure environment variables

Create:

```text
.env
```

using:

```text
.env.example
```

Required configuration includes:

```text
DATABASE_URL=
SERPAPI_API_KEY=
RESEND_API_KEY=
FROM_EMAIL=
SCHEDULER_ENABLED=
CORS_ORIGINS=
```

Never commit `.env` or real API credentials.

## 5. Run database migrations

```bash
alembic upgrade head
```

## 6. Start the application

```bash
uvicorn main:app --reload
```

The application will be available locally through the FastAPI server.

---

# 📡 API Endpoints

### Health

```http
GET /healthz
```

### Dashboard

```http
GET /dashboard
```

### Internships

```http
GET /internships
```

### Companies

```http
GET /companies
```

### Subscriptions

```http
POST /subscriptions
```

Additional subscription operations support:

* listing subscriptions
* pausing
* resuming
* deleting

### Internship Search

```http
GET /search-internships
```

---

# 🔐 Environment & Security

Secrets are supplied through environment variables.

The repository does not require real credentials to run from source.

Important production secrets include:

```text
DATABASE_URL
SERPAPI_API_KEY
RESEND_API_KEY
FROM_EMAIL
```

The scheduler is controlled using:

```text
SCHEDULER_ENABLED=true
```

---

# 📊 Production Reliability

The application includes several production-oriented safeguards:

* Async database access
* Database uniqueness constraints
* Canonical URL normalization
* Batched database queries
* Search request limits
* API retry handling
* Search failure isolation
* Subscription-group failure isolation
* Notification idempotency
* Concurrent notification protection
* Email retry handling
* Zombie notification recovery
* Maximum email concurrency
* 45-day database retention
* Health monitoring
* Environment-based configuration
* CORS configuration
* Automated regression testing

---

# 🎓 What This Project Demonstrates

This project demonstrates practical experience with:

* Backend API development
* Asynchronous Python
* REST API design
* PostgreSQL database design
* SQLAlchemy ORM
* Database transactions
* Database constraints and indexes
* Background scheduling
* External API integration
* AI/semantic similarity
* ONNX model optimization
* Notification systems
* Idempotent processing
* Retry mechanisms
* Concurrency control
* Production debugging
* Automated testing
* Deployment
* Git/GitHub workflows

---

# 🔮 Future Improvements

Potential future improvements include:

* More internship/job data sources
* Advanced personalization
* Improved ranking models
* User authentication
* Analytics dashboards
* More sophisticated search strategies
* Distributed background processing when scale requires it

These are intentionally kept outside the current production architecture.

---

# 👨‍💻 Author

**Kokila Gurunadhan**

Electronics & Communication Engineering student building production-oriented software and AI-assisted systems.

---

## 📌 Project Status

**Production-ready student project**

Current verification:

```text
Automated regression tests: 193 passed
Production database: Connected
Production email delivery: Verified
Scheduler: 12-hour interval
AI relevance scoring: ONNX Runtime + QInt8
Duplicate protection: Verified
Notification idempotency: Verified
Email retry handling: Verified
45-day retention: Verified
```
