# Epson Smart Helpdesk - Backend & AI Engine

Sistem Helpdesk cerdas untuk PT Epson yang menggabungkan teknologi **RAG (Retrieval-Augmented Generation)** untuk menjawab pertanyaan teknis secara otomatis dan **Ticketing System** untuk eskalasi kendala ke teknisi manusia.

---

## 🚀 Tech Stack

### Backend (Core Infrastructure)

* **Framework:** FastAPI (Python 3.11+)
* **Database (Relational):** PostgreSQL (via Supabase)
* **ORM:** SQLModel (SQLAlchemy + Pydantic)
* **Migration:** Alembic
* **Deployment:** Docker & AWS EC2
* **Email Service:** Resend API

### AI Engine (RAG Pipeline)

* **Framework:** LlamaIndex
* **Vector Database:** pgvector (PostgreSQL extension)
* **LLM:** OpenAI (GPT-4 / GPT-3.5)
* **Embedding:** OpenAI `text-embedding-3-small`

---

## 📁 Project Structure

```text
epson-smart-helpdesk-be/
├── app/
│   ├── api/            # API Endpoints (V1)
│   ├── core/           # Configuration & Global Settings
│   ├── db/             # Database Connection & Session
│   ├── models/         # SQLModel Schemas (Database Tables)
│   ├── schemas/        # Pydantic Schemas (Request/Response Validation)
│   └── services/       # Business Logic (RAG & Ticketing)
├── migrations/         # Alembic Database Migrations
├── docker-compose.yml  # Local Orchestration
├── Dockerfile          # Production Containerization
├── alembic.ini         # Alembic Configuration
└── .env                # Environment Variables (Keep it Secret!)
```

---

## 🛠️ Setup & Installation

### 1. Clone Repository

```bash
git clone https://github.com/username/epson-smart-helpdesk-be.git
cd epson-smart-helpdesk-be
```

---

### 2. Environment Variables

Buat file `.env` di root folder dan isi konfigurasi berikut.

```env
PROJECT_NAME="Epson Smart Helpdesk"

DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[HOST].supabase.co:5432/postgres
SUPABASE_URL=https://[HOST].supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

OPENAI_API_KEY=sk-xxxx
RESEND_API_KEY=re_xxxx
```

---

### 3. Install Dependencies (Local)

#### Linux / Mac

```bash
python -m venv venv
source venv/bin/activate
```

#### Windows

```bash
python -m venv venv
.\venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

### 4. Database Migration

Pastikan ekstensi **vector** sudah aktif di PostgreSQL.

```bash
alembic upgrade head
```

---

## 🏃 Running the Application

### Development Mode

```bash
uvicorn app.main:app --reload
```

Akses dokumentasi API:

```
http://127.0.0.1:8000/docs
```

---

### Docker Mode (Production Prep)

Build image:

```bash
docker build -t epson-be .
```

Run container:

```bash
docker run -p 8000:8000 epson-be
```

---

## 🤝 Collaboration Workflow

### For Backend Developers

Fokus pada pengembangan backend service dan API layer.

Area utama:

* `app/api` → REST API endpoints
* `app/models` → database table schemas (SQLModel)
* `app/schemas` → request & response validation
* `app/services` → business logic (ticketing system, integrations)
* `app/db` → database session & connection management
* `app/core` → application configuration

Tanggung jawab:

* mengembangkan endpoint API
* mengelola database schema dan migration
* mengintegrasikan layanan eksternal (Resend, AWS, Supabase)
* memastikan keamanan dan performa API

Gunakan branch dengan prefix:

```
feat/be-
fix/be-
```

---

### For AI Engineers

Fokus pada pengembangan **RAG (Retrieval-Augmented Generation) pipeline**.

Area utama:

* `app/services/rag_service.py` → RAG query pipeline
* embedding generation
* vector search logic
* dataset processing

Tanggung jawab:

* implementasi RAG menggunakan **LlamaIndex**
* mengelola ingestion dataset ke vector database
* membuat embedding menggunakan OpenAI model
* mengoptimalkan retrieval dan context generation
* mengintegrasikan hasil retrieval dengan LLM

Catatan:

* Hindari mengubah skema dasar `DATABASE_URL`
* Gunakan migration baru jika diperlukan perubahan database

Gunakan branch dengan prefix:

```
feat/ai-
```

---

## 🔒 Security Group (AWS)

Pastikan instance **EC2** memiliki rule berikut.

### Inbound Rules

| Port | Description                      |
| ---- | -------------------------------- |
| 22   | SSH (Restricted to Developer IP) |
| 8000 | API Access                       |

### Outbound Rules

| Port | Description                 |
| ---- | --------------------------- |
| 5432 | PostgreSQL (Supabase)       |
| 443  | HTTPS (OpenAI & Resend API) |

---
📄 License

© 2026 Tim Suka Maju - Capstone Epson Smart Helpdesk
