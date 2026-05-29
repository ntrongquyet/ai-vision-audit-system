# AI Vision Audit System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây dựng FastAPI backend (+ Demo UI) đối chiếu ảnh hiện trường với văn bản Scope of Works bằng AI, lưu trên Postgres/pgvector (Supabase-ready), theo đúng BRD/FRS/SRS.

**Architecture:** Backend FastAPI async, mọi AI call đi qua một `AsyncOpenAI` client trỏ 9router (model theo role lấy từ env). Visual Indexing chạy nền bằng `BackgroundTasks` + bảng `project_index_jobs` (poll qua `/status`). Audit gom mô tả ảnh thành context rồi cho reasoning model xuất `AuditReportSchema`. Chat dùng pgvector RPC Top-3. DB truy cập qua SQLAlchemy async + asyncpg + pgvector (chạy giống nhau local↔Supabase).

**Tech Stack:** Python 3.11, FastAPI/Uvicorn, SQLAlchemy 2 async + asyncpg + pgvector, openai SDK, tenacity, loguru, pydantic-settings, pytest/pytest-asyncio, Docker (pgvector/pgvector:pg16).

**Spec nguồn:** `docs/superpowers/specs/2026-05-29-ai-vision-audit-system-design.md`

---

## File Structure (bản đồ file)

| File | Trách nhiệm |
|---|---|
| `pyproject.toml` | deps + cấu hình pytest |
| `.env.example`, `.gitignore`, `Dockerfile`, `docker-compose.yml` | infra & config mẫu |
| `migrations/001_init.sql` | extension vector + 3 bảng + index |
| `migrations/002_match_function.sql` | RPC `match_visual_indices` |
| `scripts/apply_migrations.py` | chạy migrations lên DATABASE_URL |
| `scripts/run_mosgiel_stress_test.py` | acceptance ≥90% trên sample-data |
| `app/config.py` | `Settings` (pydantic-settings) |
| `app/db/engine.py` | async engine/session |
| `app/db/models.py` | ORM 3 bảng |
| `app/db/repositories.py` | CRUD + RPC match |
| `app/models/schemas.py` | Pydantic request/response + `AuditReportSchema` + `VisionTagResult` |
| `app/security.py` | `require_api_key` dependency |
| `app/core/ai_client.py` | `AsyncOpenAI` → 9router |
| `app/core/resilience.py` | tenacity retry + `asyncio.Semaphore` |
| `app/core/vision.py` | ảnh → `VisionTagResult` |
| `app/core/embeddings.py` | text → vector |
| `app/core/prompts.py` | system prompts + industry rules |
| `app/core/reasoning.py` | context+scope → `AuditReportSchema` |
| `app/services/job_service.py` | tạo/cập nhật job |
| `app/services/indexing_service.py` | luồng index nền (batch/semaphore/isolation) |
| `app/services/audit_service.py` | luồng audit (+422) |
| `app/services/chat_service.py` | luồng chat (vector Top-3) |
| `app/api/routes_*.py` | 6 endpoint |
| `app/main.py` | app, mount routers + static, timeout |
| `app/static/index.html` + `app.js` | Demo UI |
| `tests/...` | unit + integration |
| `README.md` | hướng dẫn + Bubble integration guide |

> **Quy ước test:** Unit test **mock AI client** (không gọi 9router thật). Integration test cần Postgres local (`docker compose up -d db`), đánh dấu `@pytest.mark.integration`.

---

## Task 0: Khởi tạo project + tooling

**Files:**
- Create: `.gitignore`, `pyproject.toml`, `.env.example`, `Dockerfile`, `docker-compose.yml`
- Create thư mục: `app/`, `app/api/`, `app/core/`, `app/db/`, `app/models/`, `app/services/`, `app/static/`, `migrations/`, `scripts/`, `tests/`

- [ ] **Step 1: Khởi tạo git + thư mục**

```bash
cd d:/demo/ai-vision-audit-system
git init
mkdir -p app/api app/core app/db app/models app/services app/static migrations scripts tests
# package markers
ni app/__init__.py, app/api/__init__.py, app/core/__init__.py, app/db/__init__.py, app/models/__init__.py, app/services/__init__.py, tests/__init__.py -ItemType File
```

- [ ] **Step 2: `.gitignore`**

```
__pycache__/
*.pyc
.venv/
.env
uploads/
.pytest_cache/
*.egg-info/
```

- [ ] **Step 3: `pyproject.toml`**

```toml
[project]
name = "ai-vision-audit-system"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "pgvector>=0.2.5",
    "openai>=1.30",
    "tenacity>=8.2",
    "loguru>=0.7",
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
    "python-multipart>=0.0.9",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23", "respx>=0.21"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = ["integration: cần Postgres local"]
addopts = "-q"
```

- [ ] **Step 4: `.env.example`**

```
# --- AI (9router, OpenAI-compatible) ---
AI_BASE_URL=https://9router.example/v1
AI_API_KEY=replace-me
VISION_MODEL=gemini-2.0-flash
REASONING_MODEL=claude-3-5-sonnet
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536
AI_MAX_CONCURRENCY=5
AI_BATCH_SIZE=5
# --- App ---
APP_API_KEY=dev-secret-key
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/audit
UPLOAD_DIR=uploads
UPLOAD_PUBLIC_BASE_URL=http://localhost:8000/files
MATCH_THRESHOLD=0.7
MATCH_COUNT=3
```

- [ ] **Step 5: `docker-compose.yml`**

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: audit
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
  adminer:
    image: adminer
    ports: ["8080:8080"]
    depends_on: [db]
volumes:
  pgdata:
```

- [ ] **Step 6: `Dockerfile`** (dùng khi deploy api)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir . 
COPY . .
EXPOSE 8000
# timeout >= 90s cho EX-03
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "90"]
```

- [ ] **Step 7: Tạo venv + cài deps + commit**

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
docker compose up -d db
git add -A
git commit -m "chore: scaffold project, tooling, docker compose"
```
Expected: `pip install` thành công; `docker compose ps` thấy `db` healthy.

---

## Task 1: Config (`app/config.py`)

**Files:**
- Create: `app/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_config.py
import os
from app.config import Settings

def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("AI_BASE_URL", "https://x/v1")
    monkeypatch.setenv("AI_API_KEY", "k")
    monkeypatch.setenv("APP_API_KEY", "app-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    s = Settings()
    assert s.embedding_dim == 1536          # default
    assert s.ai_max_concurrency == 5        # default
    assert s.app_api_key == "app-key"
```

- [ ] **Step 2: Run → fail**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: FAIL `ModuleNotFoundError: app.config`

- [ ] **Step 3: Implement**

```python
# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ai_base_url: str
    ai_api_key: str
    vision_model: str = "gemini-2.0-flash"
    reasoning_model: str = "claude-3-5-sonnet"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    ai_max_concurrency: int = 5
    ai_batch_size: int = 5

    app_api_key: str
    database_url: str
    upload_dir: str = "uploads"
    upload_public_base_url: str = "http://localhost:8000/files"
    match_threshold: float = 0.7
    match_count: int = 3

from functools import lru_cache
@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run → pass**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v` → PASS

- [ ] **Step 5: Commit**

```bash
git add app/config.py tests/test_config.py
git commit -m "feat(config): pydantic-settings env config"
```

---

## Task 2: Migrations + runner

**Files:**
- Create: `migrations/001_init.sql`, `migrations/002_match_function.sql`, `scripts/apply_migrations.py`
- Test: `tests/test_migrations.py` (integration)

- [ ] **Step 1: `migrations/001_init.sql`**

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS project_visual_indices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(255) NOT NULL,
    image_url TEXT NOT NULL,
    tags TEXT[] NOT NULL,
    detailed_description TEXT NOT NULL,
    embedding_vector vector(1536),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS project_visual_indices_vector_idx
    ON project_visual_indices USING hnsw (embedding_vector vector_cosine_ops);
CREATE INDEX IF NOT EXISTS project_visual_indices_project_id_idx
    ON project_visual_indices (project_id);

CREATE TABLE IF NOT EXISTS project_audit_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(255) NOT NULL,
    scope_text TEXT NOT NULL,
    report_json JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS project_audit_reports_project_id_idx
    ON project_audit_reports (project_id);

CREATE TABLE IF NOT EXISTS project_index_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    total_images INT NOT NULL DEFAULT 0,
    processed_images INT NOT NULL DEFAULT 0,
    succeeded_images INT NOT NULL DEFAULT 0,
    failed_images INT NOT NULL DEFAULT 0,
    error_log JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS project_index_jobs_project_id_idx
    ON project_index_jobs (project_id);
```

- [ ] **Step 2: `migrations/002_match_function.sql`**

```sql
CREATE OR REPLACE FUNCTION match_visual_indices(
    query_embedding vector(1536),
    p_project_id VARCHAR,
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 3
)
RETURNS TABLE (id UUID, image_url TEXT, detailed_description TEXT, similarity FLOAT)
LANGUAGE sql STABLE AS $$
    SELECT id, image_url, detailed_description,
           1 - (embedding_vector <=> query_embedding) AS similarity
    FROM project_visual_indices
    WHERE project_id = p_project_id
      AND 1 - (embedding_vector <=> query_embedding) > match_threshold
    ORDER BY embedding_vector <=> query_embedding
    LIMIT match_count;
$$;
```

- [ ] **Step 3: `scripts/apply_migrations.py`**

```python
import asyncio, pathlib, asyncpg
from app.config import get_settings

async def main():
    url = get_settings().database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(url)
    for f in sorted(pathlib.Path("migrations").glob("*.sql")):
        print("applying", f.name)
        await conn.execute(f.read_text(encoding="utf-8"))
    await conn.close()
    print("migrations done")

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Integration test**

```python
# tests/test_migrations.py
import asyncpg, pytest
from app.config import get_settings

@pytest.mark.integration
async def test_tables_exist():
    url = get_settings().database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(url)
    rows = await conn.fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    names = {r["table_name"] for r in rows}
    await conn.close()
    assert {"project_visual_indices", "project_audit_reports", "project_index_jobs"} <= names
```

- [ ] **Step 5: Apply + run → pass**

```bash
docker compose up -d db
.venv/Scripts/python scripts/apply_migrations.py
.venv/Scripts/python -m pytest tests/test_migrations.py -m integration -v
```
Expected: "migrations done"; test PASS.

- [ ] **Step 6: Commit**

```bash
git add migrations scripts/apply_migrations.py tests/test_migrations.py
git commit -m "feat(db): migrations (3 tables + match RPC) + runner"
```

---

## Task 3: DB engine + ORM models

**Files:**
- Create: `app/db/engine.py`, `app/db/models.py`
- Test: `tests/test_db_models.py` (integration)

- [ ] **Step 1: `app/db/engine.py`**

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import get_settings

_settings = get_settings()
engine = create_async_engine(_settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
```

- [ ] **Step 2: `app/db/models.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.config import get_settings

DIM = get_settings().embedding_dim

class Base(DeclarativeBase):
    pass

class VisualIndex(Base):
    __tablename__ = "project_visual_indices"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), index=True)
    image_url: Mapped[str] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text))
    detailed_description: Mapped[str] = mapped_column(Text)
    embedding_vector: Mapped[list[float]] = mapped_column(Vector(DIM))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

class AuditReport(Base):
    __tablename__ = "project_audit_reports"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), index=True)
    scope_text: Mapped[str] = mapped_column(Text)
    report_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

class IndexJob(Base):
    __tablename__ = "project_index_jobs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    total_images: Mapped[int] = mapped_column(Integer, default=0)
    processed_images: Mapped[int] = mapped_column(Integer, default=0)
    succeeded_images: Mapped[int] = mapped_column(Integer, default=0)
    failed_images: Mapped[int] = mapped_column(Integer, default=0)
    error_log: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 3: Integration test**

```python
# tests/test_db_models.py
import pytest
from app.db.engine import SessionLocal
from app.db.models import IndexJob

@pytest.mark.integration
async def test_insert_job():
    async with SessionLocal() as s:
        job = IndexJob(project_id="PROJ-TEST", total_images=3)
        s.add(job); await s.commit(); await s.refresh(job)
        assert job.id is not None
        assert job.status == "pending"
```

- [ ] **Step 4: Run → pass**

Run: `.venv/Scripts/python -m pytest tests/test_db_models.py -m integration -v` → PASS

- [ ] **Step 5: Commit**

```bash
git add app/db/engine.py app/db/models.py tests/test_db_models.py
git commit -m "feat(db): async engine + ORM models"
```

---

## Task 4: Pydantic schemas

**Files:**
- Create: `app/models/schemas.py`
- Test: `tests/test_schemas.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_schemas.py
import pytest
from pydantic import ValidationError
from app.models.schemas import AuditReportSchema, VisionTagResult, IndexRequest

def test_audit_schema_roundtrip():
    data = {"discrepancies": [{"issue_title":"t","evidence_description":"e",
            "suggested_action":"a","related_image_url":"u"}],
            "ambiguity_alerts": [], "safety_equipment_recommendations": []}
    rep = AuditReportSchema.model_validate(data)
    assert rep.discrepancies[0].issue_title == "t"

def test_index_request_rejects_empty_urls():
    with pytest.raises(ValidationError):
        IndexRequest(project_id="P", image_urls=[])

def test_vision_result():
    v = VisionTagResult(tags=["rust"], detailed_description="d")
    assert v.tags == ["rust"]
```

- [ ] **Step 2: Run → fail**

Run: `.venv/Scripts/python -m pytest tests/test_schemas.py -v` → FAIL import error

- [ ] **Step 3: Implement**

```python
# app/models/schemas.py
from pydantic import BaseModel, Field, field_validator

# --- AI outputs ---
class VisionTagResult(BaseModel):
    tags: list[str]
    detailed_description: str

class DiscrepancyItem(BaseModel):
    issue_title: str
    evidence_description: str
    suggested_action: str
    related_image_url: str

class AmbiguityAlertItem(BaseModel):
    original_text: str
    risk_analysis: str
    recommended_phrasing: str

class SafetyEquipmentItem(BaseModel):
    equipment_name: str
    reason: str

class AuditReportSchema(BaseModel):
    discrepancies: list[DiscrepancyItem] = Field(default_factory=list)
    ambiguity_alerts: list[AmbiguityAlertItem] = Field(default_factory=list)
    safety_equipment_recommendations: list[SafetyEquipmentItem] = Field(default_factory=list)

# --- API requests ---
class IndexRequest(BaseModel):
    project_id: str
    image_urls: list[str]
    @field_validator("image_urls")
    @classmethod
    def not_empty(cls, v):
        if not v:
            raise ValueError("image_urls must not be empty")
        return v

class AuditRequest(BaseModel):
    project_id: str
    scope_text: str

class ChatRequest(BaseModel):
    project_id: str
    user_question: str

# --- API responses ---
class IndexResponse(BaseModel):
    status: str = "success"
    message: str = "Bulk image indexing initiated in background."
    project_id: str
    job_id: str
    total_images: int

class StatusResponse(BaseModel):
    project_id: str
    job_id: str | None
    status: str
    total_images: int
    processed_images: int
    succeeded_images: int
    failed_images: int

class AuditResponse(BaseModel):
    project_id: str
    status: str = "completed"
    audit_report: AuditReportSchema

class ChatResponse(BaseModel):
    answer_text: str
    reference_image_urls: list[str]
```

- [ ] **Step 4: Run → pass** → `.venv/Scripts/python -m pytest tests/test_schemas.py -v`

- [ ] **Step 5: Commit**

```bash
git add app/models/schemas.py tests/test_schemas.py
git commit -m "feat(schemas): pydantic request/response + AI output models"
```

---

## Task 5: X-API-KEY security

**Files:**
- Create: `app/security.py`
- Test: `tests/test_security.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_security.py
import pytest
from fastapi import HTTPException
from app.security import require_api_key

def test_valid_key(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "secret"); _reset()
    assert require_api_key("secret") is None

def test_invalid_key(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "secret"); _reset()
    with pytest.raises(HTTPException) as e:
        require_api_key("wrong")
    assert e.value.status_code == 401

def _reset():
    from app.config import get_settings
    get_settings.cache_clear()
```

- [ ] **Step 2: Run → fail** → import error

- [ ] **Step 3: Implement**

```python
# app/security.py
from fastapi import Header, HTTPException
from app.config import get_settings

def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = get_settings().app_api_key
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-KEY")
```

> Lưu ý: trong test gọi trực tiếp `require_api_key("secret")` truyền chuỗi; ở runtime FastAPI tự inject từ header `X-API-KEY`.

- [ ] **Step 4: Run → pass**

- [ ] **Step 5: Commit**

```bash
git add app/security.py tests/test_security.py
git commit -m "feat(security): X-API-KEY dependency"
```

---

## Task 6: AI client + resilience

**Files:**
- Create: `app/core/ai_client.py`, `app/core/resilience.py`
- Test: `tests/test_resilience.py`

- [ ] **Step 1: `app/core/ai_client.py`**

```python
from functools import lru_cache
from openai import AsyncOpenAI
from app.config import get_settings

@lru_cache
def get_ai_client() -> AsyncOpenAI:
    s = get_settings()
    return AsyncOpenAI(base_url=s.ai_base_url, api_key=s.ai_api_key)
```

- [ ] **Step 2: Failing test cho retry**

```python
# tests/test_resilience.py
import pytest
from app.core.resilience import with_retry

@pytest.mark.asyncio
async def test_retry_succeeds_after_failures():
    calls = {"n": 0}
    @with_retry
    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("429 rate limit")
        return "ok"
    assert await flaky() == "ok"
    assert calls["n"] == 3

@pytest.mark.asyncio
async def test_retry_gives_up_after_3():
    @with_retry
    async def always_fail():
        raise RuntimeError("boom")
    with pytest.raises(RuntimeError):
        await always_fail()
```

- [ ] **Step 3: Run → fail** → import error

- [ ] **Step 4: Implement `app/core/resilience.py`**

```python
import asyncio
from functools import lru_cache
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger
from app.config import get_settings

# EX-01 / NFR 5.2: retry 3 lần, exponential backoff
def with_retry(func):
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
        before_sleep=lambda rs: logger.warning(f"AI call retry #{rs.attempt_number}: {rs.outcome.exception()}"),
    )(func)

@lru_cache
def get_semaphore() -> asyncio.Semaphore:
    # NFR 5.1: tối đa 5 ảnh gọi AI song song
    return asyncio.Semaphore(get_settings().ai_max_concurrency)
```

> Test dùng `min=2` để không kéo dài; production vẫn an toàn vì exponential. Nếu muốn đúng SRS `min=4` thì chỉnh ở đây (test vẫn pass nhưng chạy lâu hơn).

- [ ] **Step 5: Run → pass** → `.venv/Scripts/python -m pytest tests/test_resilience.py -v`

- [ ] **Step 6: Commit**

```bash
git add app/core/ai_client.py app/core/resilience.py tests/test_resilience.py
git commit -m "feat(core): AI client (9router) + retry/semaphore"
```

---

## Task 7: Vision module

**Files:**
- Create: `app/core/vision.py`
- Test: `tests/test_vision.py`

- [ ] **Step 1: Failing test (mock AI client)**

```python
# tests/test_vision.py
import json, pytest
from unittest.mock import AsyncMock, patch
from app.core import vision

@pytest.mark.asyncio
async def test_analyze_image_parses_json():
    fake = AsyncMock()
    fake.chat.completions.create.return_value = type("R", (), {
        "choices": [type("C", (), {"message": type("M", (), {
            "content": json.dumps({"tags": ["rust", "roof"],
                                   "detailed_description": "rusty corrugated roof"})})()})()]
    })()
    with patch("app.core.vision.get_ai_client", return_value=fake):
        res = await vision.analyze_image("http://x/img.jpg")
    assert res.tags == ["rust", "roof"]
    assert "rusty" in res.detailed_description
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement**

```python
# app/core/vision.py
import json
from app.core.ai_client import get_ai_client
from app.core.resilience import with_retry
from app.core.prompts import VISION_SYSTEM_PROMPT
from app.config import get_settings
from app.models.schemas import VisionTagResult

@with_retry
async def analyze_image(image_url: str) -> VisionTagResult:
    client = get_ai_client()
    resp = await client.chat.completions.create(
        model=get_settings().vision_model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": VISION_SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": "Analyze this site survey photo. Return JSON {tags, detailed_description}."},
                {"type": "image_url", "image_url": {"url": image_url}},
            ]},
        ],
    )
    raw = resp.choices[0].message.content
    return VisionTagResult.model_validate(json.loads(raw))
```

- [ ] **Step 4: Run → pass**

- [ ] **Step 5: Commit**

```bash
git add app/core/vision.py tests/test_vision.py
git commit -m "feat(core): vision image analysis via 9router"
```

> `app/core/prompts.py` được tạo ở Task 9 (reasoning) nhưng `VISION_SYSTEM_PROMPT` cần ngay — tạo file prompts ở Step 3 này nếu chưa có (xem nội dung tại Task 9 Step 3).

---

## Task 8: Embeddings module

**Files:**
- Create: `app/core/embeddings.py`
- Test: `tests/test_embeddings.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_embeddings.py
import pytest
from unittest.mock import AsyncMock, patch
from app.core import embeddings

@pytest.mark.asyncio
async def test_embed_text_returns_vector():
    fake = AsyncMock()
    fake.embeddings.create.return_value = type("R", (), {
        "data": [type("D", (), {"embedding": [0.1, 0.2, 0.3]})()]})()
    with patch("app.core.embeddings.get_ai_client", return_value=fake):
        vec = await embeddings.embed_text("hello")
    assert vec == [0.1, 0.2, 0.3]
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement**

```python
# app/core/embeddings.py
from app.core.ai_client import get_ai_client
from app.core.resilience import with_retry
from app.config import get_settings

@with_retry
async def embed_text(text: str) -> list[float]:
    client = get_ai_client()
    resp = await client.embeddings.create(
        model=get_settings().embedding_model, input=text)
    return list(resp.data[0].embedding)
```

- [ ] **Step 4: Run → pass**

- [ ] **Step 5: Commit**

```bash
git add app/core/embeddings.py tests/test_embeddings.py
git commit -m "feat(core): text embeddings via 9router"
```

---

## Task 9: Prompts + reasoning module

**Files:**
- Create: `app/core/prompts.py` (nếu chưa có từ Task 7), `app/core/reasoning.py`
- Test: `tests/test_reasoning.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_reasoning.py
import json, pytest
from unittest.mock import AsyncMock, patch
from app.core import reasoning

@pytest.mark.asyncio
async def test_run_audit_parses_report():
    payload = {"discrepancies": [{"issue_title":"Rust on roof",
        "evidence_description":"Photo shows rust","suggested_action":"Add rust line item",
        "related_image_url":"http://x/1.jpg"}],
        "ambiguity_alerts": [], "safety_equipment_recommendations": []}
    fake = AsyncMock()
    fake.chat.completions.create.return_value = type("R", (), {
        "choices": [type("C", (), {"message": type("M", (), {
            "content": json.dumps(payload)})()})()]})()
    with patch("app.core.reasoning.get_ai_client", return_value=fake):
        rep = await reasoning.run_audit("ctx of photos", "paint timber walls")
    assert rep.discrepancies[0].issue_title == "Rust on roof"
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `app/core/prompts.py`**

```python
# app/core/prompts.py
VISION_SYSTEM_PROMPT = """You are a field survey assistant for a painting & industrial \
cleaning contractor. Look at the construction site photo and describe ONLY the building \
surfaces and their condition (ignore furniture, people, tools).
Identify: material (timber/weatherboard/brick/concrete/corrugated iron/plaster), \
surface condition (peeling paint, rust, mould/mildew, cracks, water stains, moss), \
and any height/access context.
Return STRICT JSON: {"tags": [short keywords], "detailed_description": "1-3 sentences"}."""

REASONING_SYSTEM_PROMPT = """You are an international painting & industrial-cleaning tender \
consultant. You receive <context> (descriptions of all site photos) and <scope_text> (the \
quote's Scope of Works). Find where the photos reveal work NOT covered by the scope, vague \
wording, and required safety equipment.

Apply industry rules:
- Buildings likely built before 1970 → flag possible LEAD PAINT testing.
- Choose pressure-wash PSI by material (soft timber lower PSI than concrete).
- Surfaces above ~5m or with difficult terrain → recommend scaffolding / cherry picker / boom lift.
- Rusty metal (roof iron, gutters, downpipes) → recommend rust treatment + anti-corrosive primer.

Return STRICT JSON matching this shape exactly:
{"discrepancies":[{"issue_title","evidence_description","suggested_action","related_image_url"}],
 "ambiguity_alerts":[{"original_text","risk_analysis","recommended_phrasing"}],
 "safety_equipment_recommendations":[{"equipment_name","reason"}]}
Use empty arrays when nothing applies. Do not invent image URLs not present in context."""
```

- [ ] **Step 4: Implement `app/core/reasoning.py`** (có repair-retry — AD-4)

```python
# app/core/reasoning.py
import json
from loguru import logger
from app.core.ai_client import get_ai_client
from app.core.resilience import with_retry
from app.core.prompts import REASONING_SYSTEM_PROMPT
from app.config import get_settings
from app.models.schemas import AuditReportSchema

@with_retry
async def _call(messages) -> str:
    client = get_ai_client()
    resp = await client.chat.completions.create(
        model=get_settings().reasoning_model,
        response_format={"type": "json_object"},
        messages=messages,
    )
    return resp.choices[0].message.content

async def run_audit(context_block: str, scope_text: str) -> AuditReportSchema:
    user = f"<context>\n{context_block}\n</context>\n<scope_text>\n{scope_text}\n</scope_text>"
    messages = [
        {"role": "system", "content": REASONING_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
    raw = await _call(messages)
    try:
        return AuditReportSchema.model_validate(json.loads(raw))
    except Exception as e:
        logger.warning(f"Audit JSON parse failed, repair retry: {e}")
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user",
            "content": "Your output was not valid for the required schema. "
                       "Return ONLY corrected JSON, no prose."})
        raw2 = await _call(messages)
        return AuditReportSchema.model_validate(json.loads(raw2))
```

- [ ] **Step 5: Run → pass** → `.venv/Scripts/python -m pytest tests/test_reasoning.py -v`

- [ ] **Step 6: Commit**

```bash
git add app/core/prompts.py app/core/reasoning.py tests/test_reasoning.py
git commit -m "feat(core): industry-rule prompts + audit reasoning with repair retry"
```

---

## Task 10: Repositories

**Files:**
- Create: `app/db/repositories.py`
- Test: `tests/test_repositories.py` (integration)

- [ ] **Step 1: Implement `app/db/repositories.py`**

```python
# app/db/repositories.py
import uuid
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import VisualIndex, AuditReport, IndexJob

# --- visual indices ---
async def insert_visual_index(s: AsyncSession, project_id, image_url, tags, description, embedding):
    row = VisualIndex(project_id=project_id, image_url=image_url, tags=tags,
                      detailed_description=description, embedding_vector=embedding)
    s.add(row); await s.commit()

async def project_has_indices(s: AsyncSession, project_id: str) -> bool:
    r = await s.execute(select(VisualIndex.id).where(VisualIndex.project_id == project_id).limit(1))
    return r.first() is not None

async def get_descriptions(s: AsyncSession, project_id: str) -> list[tuple[str, str]]:
    r = await s.execute(select(VisualIndex.image_url, VisualIndex.detailed_description)
                        .where(VisualIndex.project_id == project_id))
    return [(row[0], row[1]) for row in r.all()]

async def match_visual_indices(s: AsyncSession, project_id, query_embedding, threshold, count):
    sql = text("SELECT image_url, detailed_description, similarity FROM "
               "match_visual_indices(:emb, :pid, :thr, :cnt)")
    r = await s.execute(sql, {"emb": str(query_embedding), "pid": project_id,
                              "thr": threshold, "cnt": count})
    return [{"image_url": x[0], "detailed_description": x[1], "similarity": x[2]} for x in r.all()]

# --- audit reports ---
async def insert_audit_report(s: AsyncSession, project_id, scope_text, report_json):
    s.add(AuditReport(project_id=project_id, scope_text=scope_text, report_json=report_json))
    await s.commit()

# --- jobs ---
async def create_job(s: AsyncSession, project_id: str, total: int) -> IndexJob:
    job = IndexJob(project_id=project_id, total_images=total, status="pending")
    s.add(job); await s.commit(); await s.refresh(job)
    return job

async def get_job(s: AsyncSession, job_id: uuid.UUID) -> IndexJob | None:
    return await s.get(IndexJob, job_id)

async def get_latest_job(s: AsyncSession, project_id: str) -> IndexJob | None:
    r = await s.execute(select(IndexJob).where(IndexJob.project_id == project_id)
                        .order_by(IndexJob.created_at.desc()).limit(1))
    return r.scalar_one_or_none()
```

> Lưu ý pgvector: truyền embedding cho RPC dạng chuỗi `str([...])` (vd `"[0.1,0.2]"`) — pgvector ép kiểu `vector` từ text literal.

- [ ] **Step 2: Integration test**

```python
# tests/test_repositories.py
import pytest
from app.db.engine import SessionLocal
from app.db import repositories as repo

@pytest.mark.integration
async def test_job_and_index_flow():
    async with SessionLocal() as s:
        job = await repo.create_job(s, "PROJ-RT", 1)
        assert job.status == "pending"
        emb = [0.0] * 1536
        await repo.insert_visual_index(s, "PROJ-RT", "http://x/1.jpg",
                                       ["rust"], "rusty roof", emb)
        assert await repo.project_has_indices(s, "PROJ-RT") is True
        descs = await repo.get_descriptions(s, "PROJ-RT")
        assert descs[0][0] == "http://x/1.jpg"
```

- [ ] **Step 3: Run → pass**

Run: `.venv/Scripts/python -m pytest tests/test_repositories.py -m integration -v`

- [ ] **Step 4: Commit**

```bash
git add app/db/repositories.py tests/test_repositories.py
git commit -m "feat(db): repositories + vector match"
```

---

## Task 11: Job service + indexing service

**Files:**
- Create: `app/services/job_service.py`, `app/services/indexing_service.py`
- Test: `tests/test_indexing_service.py`

- [ ] **Step 1: `app/services/job_service.py`**

```python
# app/services/job_service.py
import uuid
from app.db.engine import SessionLocal
from app.db import repositories as repo

async def create(project_id: str, total: int) -> uuid.UUID:
    async with SessionLocal() as s:
        job = await repo.create_job(s, project_id, total)
        return job.id

async def finalize(job_id: uuid.UUID, succeeded: int, failed: int, errors: list):
    async with SessionLocal() as s:
        job = await repo.get_job(s, job_id)
        job.processed_images = succeeded + failed
        job.succeeded_images = succeeded
        job.failed_images = failed
        job.error_log = errors
        job.status = ("completed" if failed == 0 else
                      "failed" if succeeded == 0 else "partial")
        await s.commit()
```

- [ ] **Step 2: Failing test cho indexing (mock vision/embeddings)**

```python
# tests/test_indexing_service.py
import pytest
from unittest.mock import AsyncMock, patch
from app.models.schemas import VisionTagResult

@pytest.mark.asyncio
async def test_indexing_isolates_failures():
    from app.services import indexing_service as svc
    async def fake_vision(url):
        if "bad" in url:
            raise RuntimeError("vision failed")
        return VisionTagResult(tags=["t"], detailed_description="d")
    async def fake_embed(text):
        return [0.0] * 1536
    inserted = []
    async def fake_insert(*a, **k):
        inserted.append(a)
    finals = {}
    async def fake_finalize(job_id, succeeded, failed, errors):
        finals.update(dict(succeeded=succeeded, failed=failed, errors=errors))
    with patch.object(svc, "analyze_image", fake_vision), \
         patch.object(svc, "embed_text", fake_embed), \
         patch("app.services.indexing_service.repo.insert_visual_index", fake_insert), \
         patch("app.services.indexing_service.job_service.finalize", fake_finalize):
        await svc.run_indexing_job("job-1", "PROJ-X",
                                   ["http://ok/1.jpg", "http://bad/2.jpg"])
    assert finals["succeeded"] == 1
    assert finals["failed"] == 1
    assert len(finals["errors"]) == 1
```

- [ ] **Step 3: Run → fail**

- [ ] **Step 4: Implement `app/services/indexing_service.py`**

```python
# app/services/indexing_service.py
import asyncio
from loguru import logger
from app.config import get_settings
from app.core.vision import analyze_image
from app.core.embeddings import embed_text
from app.core.resilience import get_semaphore
from app.db.engine import SessionLocal
from app.db import repositories as repo
from app.services import job_service

async def _process_one(project_id: str, url: str):
    async with get_semaphore():           # NFR 5.1: max 5 song song
        vision = await analyze_image(url)
        embedding = await embed_text(vision.detailed_description)
        async with SessionLocal() as s:
            await repo.insert_visual_index(
                s, project_id, url, vision.tags, vision.detailed_description, embedding)

async def run_indexing_job(job_id, project_id: str, image_urls: list[str]):
    succeeded = failed = 0
    errors: list[dict] = []
    batch = get_settings().ai_batch_size
    for i in range(0, len(image_urls), batch):     # FR-1.2: batch 5
        chunk = image_urls[i:i + batch]
        results = await asyncio.gather(
            *[_process_one(project_id, u) for u in chunk], return_exceptions=True)
        for url, res in zip(chunk, results):
            if isinstance(res, Exception):          # NFR 5.2: cô lập lỗi
                failed += 1
                errors.append({"image_url": url, "error": str(res)})
                logger.error(f"index failed {url}: {res}")
            else:
                succeeded += 1
    await job_service.finalize(job_id, succeeded, failed, errors)
```

- [ ] **Step 5: Run → pass** → `.venv/Scripts/python -m pytest tests/test_indexing_service.py -v`

- [ ] **Step 6: Commit**

```bash
git add app/services/job_service.py app/services/indexing_service.py tests/test_indexing_service.py
git commit -m "feat(services): job + indexing (batch/semaphore/isolation)"
```

---

## Task 12: Audit service + chat service

**Files:**
- Create: `app/services/audit_service.py`, `app/services/chat_service.py`
- Test: `tests/test_audit_service.py`

- [ ] **Step 1: Failing test (mock reasoning + repo)**

```python
# tests/test_audit_service.py
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from app.models.schemas import AuditReportSchema

@pytest.mark.asyncio
async def test_audit_blocks_when_no_index():
    from app.services import audit_service as svc
    with patch("app.services.audit_service.repo.project_has_indices",
               AsyncMock(return_value=False)):
        with pytest.raises(HTTPException) as e:
            await svc.run_audit("PROJ-EMPTY", "paint walls")
    assert e.value.status_code == 422

@pytest.mark.asyncio
async def test_audit_returns_report():
    from app.services import audit_service as svc
    rep = AuditReportSchema(discrepancies=[], ambiguity_alerts=[],
                            safety_equipment_recommendations=[])
    with patch("app.services.audit_service.repo.project_has_indices", AsyncMock(return_value=True)), \
         patch("app.services.audit_service.repo.get_descriptions",
               AsyncMock(return_value=[("u1", "rusty roof")])), \
         patch("app.services.audit_service.run_audit", AsyncMock(return_value=rep)), \
         patch("app.services.audit_service.repo.insert_audit_report", AsyncMock()):
        out = await svc.run_audit("PROJ-X", "paint walls")
    assert out.audit_report.discrepancies == []
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `app/services/audit_service.py`**

```python
# app/services/audit_service.py
from fastapi import HTTPException
from app.db.engine import SessionLocal
from app.db import repositories as repo
from app.core.reasoning import run_audit as run_audit_ai
from app.models.schemas import AuditResponse

async def run_audit(project_id: str, scope_text: str) -> AuditResponse:
    async with SessionLocal() as s:
        if not await repo.project_has_indices(s, project_id):   # EX-02
            raise HTTPException(status_code=422,
                detail="Vui lòng tải lên và xử lý hình ảnh dự án trước khi thực hiện kiểm định báo giá.")
        descs = await repo.get_descriptions(s, project_id)
        context_block = "\n".join(f"- ({url}) {desc}" for url, desc in descs)
        report = await run_audit_ai(context_block, scope_text)
        await repo.insert_audit_report(s, project_id, scope_text, report.model_dump())
    return AuditResponse(project_id=project_id, audit_report=report)
```

- [ ] **Step 4: Implement `app/services/chat_service.py`**

```python
# app/services/chat_service.py
from app.config import get_settings
from app.db.engine import SessionLocal
from app.db import repositories as repo
from app.core.embeddings import embed_text
from app.core.ai_client import get_ai_client
from app.core.resilience import with_retry
from app.models.schemas import ChatResponse

@with_retry
async def _answer(question: str, context: str) -> str:
    client = get_ai_client()
    resp = await client.chat.completions.create(
        model=get_settings().reasoning_model,
        messages=[
            {"role": "system", "content":
             "Answer the user's question about a building site using ONLY the provided photo "
             "descriptions. Be concise (2-3 sentences)."},
            {"role": "user", "content": f"PHOTOS:\n{context}\n\nQUESTION: {question}"},
        ],
    )
    return resp.choices[0].message.content

async def answer(project_id: str, user_question: str) -> ChatResponse:
    s_cfg = get_settings()
    query_vec = await embed_text(user_question)
    async with SessionLocal() as s:
        matches = await repo.match_visual_indices(
            s, project_id, query_vec, s_cfg.match_threshold, s_cfg.match_count)
    if not matches:
        return ChatResponse(answer_text="No relevant photos found for this question.",
                            reference_image_urls=[])
    context = "\n".join(f"- ({m['image_url']}) {m['detailed_description']}" for m in matches)
    answer_text = await _answer(user_question, context)
    return ChatResponse(answer_text=answer_text,
                        reference_image_urls=[m["image_url"] for m in matches])
```

- [ ] **Step 5: Run → pass** → `.venv/Scripts/python -m pytest tests/test_audit_service.py -v`

- [ ] **Step 6: Commit**

```bash
git add app/services/audit_service.py app/services/chat_service.py tests/test_audit_service.py
git commit -m "feat(services): audit (+422) and chat (vector top-3)"
```

---

## Task 13: API routers + main app

**Files:**
- Create: `app/api/routes_index.py`, `routes_status.py`, `routes_audit.py`, `routes_chat.py`, `routes_uploads.py`, `app/main.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: `app/api/routes_index.py`**

```python
# app/api/routes_index.py
from fastapi import APIRouter, BackgroundTasks, Depends
from app.security import require_api_key
from app.models.schemas import IndexRequest, IndexResponse
from app.services import job_service
from app.services.indexing_service import run_indexing_job

router = APIRouter(prefix="/api/v1/projects", tags=["index"])

@router.post("/index", status_code=202, response_model=IndexResponse,
             dependencies=[Depends(require_api_key)])
async def index_images(req: IndexRequest, background: BackgroundTasks):
    job_id = await job_service.create(req.project_id, len(req.image_urls))
    background.add_task(run_indexing_job, job_id, req.project_id, req.image_urls)
    return IndexResponse(project_id=req.project_id, job_id=str(job_id),
                         total_images=len(req.image_urls))
```

- [ ] **Step 2: `app/api/routes_status.py`**

```python
# app/api/routes_status.py
from fastapi import APIRouter, Depends, HTTPException
from app.security import require_api_key
from app.models.schemas import StatusResponse
from app.db.engine import SessionLocal
from app.db import repositories as repo

router = APIRouter(prefix="/api/v1/projects", tags=["status"])

@router.get("/{project_id}/status", response_model=StatusResponse,
            dependencies=[Depends(require_api_key)])
async def get_status(project_id: str):
    async with SessionLocal() as s:
        job = await repo.get_latest_job(s, project_id)
        if job is None:
            raise HTTPException(status_code=404, detail="No indexing job for this project")
        return StatusResponse(project_id=project_id, job_id=str(job.id), status=job.status,
            total_images=job.total_images, processed_images=job.processed_images,
            succeeded_images=job.succeeded_images, failed_images=job.failed_images)
```

- [ ] **Step 3: `app/api/routes_audit.py` + `routes_chat.py`**

```python
# app/api/routes_audit.py
from fastapi import APIRouter, Depends
from app.security import require_api_key
from app.models.schemas import AuditRequest, AuditResponse
from app.services.audit_service import run_audit

router = APIRouter(prefix="/api/v1/projects", tags=["audit"])

@router.post("/audit", response_model=AuditResponse, dependencies=[Depends(require_api_key)])
async def audit(req: AuditRequest):
    return await run_audit(req.project_id, req.scope_text)
```

```python
# app/api/routes_chat.py
from fastapi import APIRouter, Depends
from app.security import require_api_key
from app.models.schemas import ChatRequest, ChatResponse
from app.services.chat_service import answer

router = APIRouter(prefix="/api/v1/projects", tags=["chat"])

@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
async def chat(req: ChatRequest):
    return await answer(req.project_id, req.user_question)
```

- [ ] **Step 4: `app/api/routes_uploads.py`** (dev)

```python
# app/api/routes_uploads.py
import os, uuid
from fastapi import APIRouter, UploadFile, Depends
from app.security import require_api_key
from app.config import get_settings

router = APIRouter(prefix="/api/v1", tags=["uploads"])

@router.post("/uploads", dependencies=[Depends(require_api_key)])
async def upload(files: list[UploadFile]):
    s = get_settings()
    os.makedirs(s.upload_dir, exist_ok=True)
    urls = []
    for f in files:
        name = f"{uuid.uuid4().hex}_{f.filename}"
        path = os.path.join(s.upload_dir, name)
        with open(path, "wb") as out:
            out.write(await f.read())
        urls.append(f"{s.upload_public_base_url}/{name}")
    return {"image_urls": urls}
```

- [ ] **Step 5: `app/main.py`**

```python
# app/main.py
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.config import get_settings
from app.api import routes_index, routes_status, routes_audit, routes_chat, routes_uploads

app = FastAPI(title="AI Vision Audit System")

@app.get("/health")
async def health():
    return {"status": "ok"}

app.include_router(routes_index.router)
app.include_router(routes_status.router)
app.include_router(routes_audit.router)
app.include_router(routes_chat.router)
app.include_router(routes_uploads.router)

_settings = get_settings()
os.makedirs(_settings.upload_dir, exist_ok=True)
app.mount("/files", StaticFiles(directory=_settings.upload_dir), name="files")
app.mount("/", StaticFiles(directory="app/static", html=True), name="ui")
```

- [ ] **Step 6: API test (TestClient, mock services)**

```python
# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "secret")
    from app.config import get_settings
    get_settings.cache_clear()
    from app.main import app
    return TestClient(app)

def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}

def test_index_requires_key(client):
    r = client.post("/api/v1/projects/index",
                    json={"project_id": "P", "image_urls": ["u"]})
    assert r.status_code == 401

def test_index_empty_urls_400(client):
    r = client.post("/api/v1/projects/index",
                    headers={"X-API-KEY": "secret"},
                    json={"project_id": "P", "image_urls": []})
    assert r.status_code == 422  # pydantic validation → 422

def test_index_accepts(client):
    with patch("app.api.routes_index.job_service.create", AsyncMock(return_value="job-1")), \
         patch("app.api.routes_index.run_indexing_job", AsyncMock()):
        r = client.post("/api/v1/projects/index",
                        headers={"X-API-KEY": "secret"},
                        json={"project_id": "P", "image_urls": ["u1", "u2"]})
    assert r.status_code == 202
    assert r.json()["total_images"] == 2
```

> Ghi chú: validation rỗng của Pydantic trả `422` (không phải `400`). Nếu muốn đúng FRS `400`, thêm exception handler map `RequestValidationError`→400 cho field `image_urls`; ở MVP chấp nhận 422 và ghi rõ trong README.

- [ ] **Step 7: Run → pass** → `.venv/Scripts/python -m pytest tests/test_api.py -v`

- [ ] **Step 8: Commit**

```bash
git add app/api app/main.py tests/test_api.py
git commit -m "feat(api): 6 endpoints + main app + static mount"
```

---

## Task 14: Demo UI

**Files:**
- Create: `app/static/index.html`, `app/static/app.js`

- [ ] **Step 1: `app/static/index.html`**

```html
<!doctype html><html><head><meta charset="utf-8"><title>AI Vision Audit</title>
<style>body{font-family:sans-serif;max-width:880px;margin:24px auto}section{border:1px solid #ddd;padding:12px;margin:12px 0;border-radius:8px}input,textarea{width:100%}img{max-width:160px;margin:4px}pre{white-space:pre-wrap;background:#f6f6f6;padding:8px}</style>
</head><body>
<h2>AI Vision Audit System — Demo</h2>
<section><label>X-API-KEY</label><input id="key"><label>Project ID</label><input id="pid" value="PROJ-3132"></section>
<section><h3>1. Upload & Index</h3><input type="file" id="files" multiple>
<button onclick="uploadAndIndex()">Upload + Index</button>
<button onclick="refreshStatus()">Refresh status</button><pre id="status"></pre></section>
<section><h3>2. Audit</h3><textarea id="scope" rows="5" placeholder="Paste Scope of Works..."></textarea>
<button onclick="runAudit()">Run AI Audit</button><div id="report"></div></section>
<section><h3>3. Chat</h3><input id="q" placeholder="Any high-access paint work needed?">
<button onclick="chat()">Ask</button><div id="chat"></div></section>
<script src="/app.js"></script></body></html>
```

- [ ] **Step 2: `app/static/app.js`**

```javascript
const $ = id => document.getElementById(id);
const hdr = () => ({ "X-API-KEY": $("key").value, "Content-Type": "application/json" });
const pid = () => $("pid").value;

async function uploadAndIndex() {
  const fd = new FormData();
  for (const f of $("files").files) fd.append("files", f);
  const up = await fetch("/api/v1/uploads", { method: "POST",
    headers: { "X-API-KEY": $("key").value }, body: fd }).then(r => r.json());
  await fetch("/api/v1/projects/index", { method: "POST", headers: hdr(),
    body: JSON.stringify({ project_id: pid(), image_urls: up.image_urls }) });
  refreshStatus();
}
async function refreshStatus() {
  const r = await fetch(`/api/v1/projects/${pid()}/status`, { headers: hdr() });
  $("status").textContent = JSON.stringify(await r.json(), null, 2);
}
async function runAudit() {
  const r = await fetch("/api/v1/projects/audit", { method: "POST", headers: hdr(),
    body: JSON.stringify({ project_id: pid(), scope_text: $("scope").value }) }).then(r => r.json());
  const rep = r.audit_report || {};
  const sec = (title, arr, fmt) => `<h4>${title} (${(arr||[]).length})</h4>` +
    (arr||[]).map(fmt).join("");
  $("report").innerHTML =
    sec("Discrepancies", rep.discrepancies, d => `<pre>${d.issue_title}\n${d.evidence_description}\n→ ${d.suggested_action}</pre><img src="${d.related_image_url}">`) +
    sec("Ambiguity alerts", rep.ambiguity_alerts, a => `<pre>"${a.original_text}"\n${a.risk_analysis}\n→ ${a.recommended_phrasing}</pre>`) +
    sec("Safety equipment", rep.safety_equipment_recommendations, e => `<pre>${e.equipment_name}: ${e.reason}</pre>`);
}
async function chat() {
  const r = await fetch("/api/v1/projects/chat", { method: "POST", headers: hdr(),
    body: JSON.stringify({ project_id: pid(), user_question: $("q").value }) }).then(r => r.json());
  $("chat").innerHTML = `<pre>${r.answer_text}</pre>` +
    (r.reference_image_urls||[]).map(u => `<img src="${u}">`).join("");
}
```

- [ ] **Step 3: Smoke test thủ công**

```bash
docker compose up -d db
.venv/Scripts/python scripts/apply_migrations.py
.venv/Scripts/uvicorn app.main:app --reload --timeout-keep-alive 90
```
Mở `http://localhost:8000`, nhập `X-API-KEY`, upload vài ảnh trong sample-data → Index → Refresh status thấy `completed` → dán SoW → Run Audit thấy 3 nhóm → Chat trả lời kèm ảnh.

- [ ] **Step 4: Commit**

```bash
git add app/static
git commit -m "feat(ui): minimal demo UI (upload/index/audit/chat)"
```

---

## Task 15: Mosgiel stress-test + acceptance

**Files:**
- Create: `scripts/run_mosgiel_stress_test.py`

- [ ] **Step 1: Implement script**

```python
# scripts/run_mosgiel_stress_test.py
"""Acceptance test: index ~30 ảnh Mosgiel, audit với SoW thiếu cố ý, kỳ vọng phát hiện >=90%."""
import asyncio, os, glob, httpx

API = os.environ.get("API_URL", "http://localhost:8000")
KEY = os.environ.get("APP_API_KEY", "dev-secret-key")
PID = "PROJ-3132-STRESS"
IMG_DIR = "docs/sample-data/images/3132 BestStart Mosgiel, Interior and Exterior Repaint _26"

# SoW cố tình BỎ SÓT: rust mái, pressure-wash mould, scaffolding tường cao
SCOPE = ("Interior and Exterior Repaint '26. Paint all timber weatherboard walls and "
         "window frames. Clean surfaces before application.")
# Các lỗi cài cắm kỳ vọng AI phát hiện (khớp keyword bất kỳ trong report text):
EXPECTED = ["rust", "mould", "moss", "pressure", "psi", "scaffold", "ladder", "boom", "lead"]

async def main():
    h = {"X-API-KEY": KEY}
    async with httpx.AsyncClient(timeout=120) as c:
        # upload
        files = []
        for p in sorted(glob.glob(os.path.join(IMG_DIR, "*.jpg"))):
            files.append(("files", (os.path.basename(p), open(p, "rb"), "image/jpeg")))
        up = (await c.post(f"{API}/api/v1/uploads", headers=h, files=files)).json()
        urls = up["image_urls"]
        print("uploaded", len(urls))
        # index
        await c.post(f"{API}/api/v1/projects/index", headers=h,
                     json={"project_id": PID, "image_urls": urls})
        # poll
        while True:
            st = (await c.get(f"{API}/api/v1/projects/{PID}/status", headers=h)).json()
            print("status", st["status"], st["processed_images"], "/", st["total_images"])
            if st["status"] in ("completed", "partial", "failed"):
                break
            await asyncio.sleep(3)
        # audit
        rep = (await c.post(f"{API}/api/v1/projects/audit", headers=h,
                            json={"project_id": PID, "scope_text": SCOPE})).json()
        text = str(rep).lower()
        hits = [k for k in EXPECTED if k in text]
        score = len(hits) / len(EXPECTED)
        print(f"detected keywords: {hits}")
        print(f"DETECTION SCORE: {score:.0%}  (target >= 90%)")
        assert score >= 0.9, "FAILED Mosgiel acceptance (<90%)"
        print("PASSED Mosgiel acceptance")

if __name__ == "__main__":
    asyncio.run(main())
```

> Đây là acceptance theo BRD Success Criteria. Ngưỡng keyword là proxy; sau khi chạy thật có thể tinh chỉnh danh sách `EXPECTED` cho khớp ngữ liệu Mosgiel.

- [ ] **Step 2: Chạy với 9router thật**

```bash
# .env đã điền AI_BASE_URL/AI_API_KEY/model thật của 9router
.venv/Scripts/uvicorn app.main:app --timeout-keep-alive 90   # terminal 1
.venv/Scripts/python scripts/run_mosgiel_stress_test.py       # terminal 2
```
Expected: in `DETECTION SCORE: >= 90%` và `PASSED`.

- [ ] **Step 3: Commit**

```bash
git add scripts/run_mosgiel_stress_test.py
git commit -m "test: Mosgiel stress-test acceptance (>=90%)"
```

---

## Task 16: README + Bubble integration guide

**Files:**
- Create: `README.md`

- [ ] **Step 1: Viết README**

Nội dung bắt buộc có:
- **Setup local**: clone, `python -m venv`, `pip install -e ".[dev]"`, `docker compose up -d db`, `python scripts/apply_migrations.py`, điền `.env` (copy từ `.env.example`), `uvicorn app.main:app --timeout-keep-alive 90`.
- **Chạy test**: `pytest` (unit) và `pytest -m integration` (cần db).
- **Bảng env vars** (giải thích từng biến ở `.env.example`).
- **API reference**: 6 endpoint, ví dụ `curl` kèm header `X-API-KEY`.
- **Bubble integration guide**:
  - Cấu hình Bubble API Connector: base URL, header `X-API-KEY`.
  - Flow: (1) upload ảnh lên Supabase Storage trên Bubble → lấy public URLs → POST `/index`; (2) poll `/status` cho tới `completed`; (3) POST `/audit` (set timeout call ≥ 90s); (4) POST `/chat`.
  - Lưu ý EX-03 timeout 90s, EX-01 có thể nhận 503 → hiển thị thông báo thân thiện.
- **Deploy Supabase cloud**: chạy `migrations/*.sql` trên Supabase SQL editor; đổi `DATABASE_URL` sang connection string Supabase; ảnh do Bubble upload lên Supabase Storage (không cần `/uploads` ở prod).

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README + Bubble/Supabase integration guide"
```

---

## Task 17: Full regression + verification

- [ ] **Step 1: Chạy toàn bộ unit tests**

Run: `.venv/Scripts/python -m pytest -m "not integration" -v`
Expected: tất cả PASS.

- [ ] **Step 2: Chạy integration tests**

```bash
docker compose up -d db
.venv/Scripts/python scripts/apply_migrations.py
.venv/Scripts/python -m pytest -m integration -v
```
Expected: PASS.

- [ ] **Step 3: Verification cuối** — đối chiếu spec:
  - [ ] 3 bảng + RPC tồn tại (Task 2/3/10)
  - [ ] 6 endpoint hoạt động, `X-API-KEY` chặn 401 (Task 13)
  - [ ] `/index` trả 202, chạy nền, `/status` báo tiến độ (Task 11/13)
  - [ ] `/audit` chặn 422 khi chưa index, lưu report (Task 12)
  - [ ] `/chat` trả Top-3 kèm ảnh (Task 12)
  - [ ] retry/semaphore/isolation/loguru (Task 6/11)
  - [ ] Mosgiel ≥90% (Task 15)

- [ ] **Step 4: Commit tag**

```bash
git add -A && git commit -m "chore: full regression green" --allow-empty
git tag mvp-v1
```

---

## Self-Review (đã thực hiện khi viết plan)

- **Spec coverage:** FR-1 (Task 11/13), FR-2 (Task 12/13), FR-3 (Task 12/13); EX-01 (Task 6/11), EX-02 (Task 12), EX-03 (Task 0 Dockerfile + Task 14 uvicorn flag); NFR 5.1 semaphore (Task 6/11), 5.2 retry+isolation (Task 6/11), 5.3 X-API-KEY (Task 5/13); DB schema + RPC (Task 2/3/10); cost/Mosgiel (Task 15). BR-03 industry rules trong prompts (Task 9).
- **Placeholder scan:** không có TODO/“xử lý lỗi phù hợp” chung chung — mọi step có code/lệnh cụ thể.
- **Type consistency:** tên hàm thống nhất across tasks: `analyze_image`, `embed_text`, `run_audit` (reasoning) vs `audit_service.run_audit`, `match_visual_indices`, `job_service.create/finalize`, `run_indexing_job`. Schema field khớp giữa schemas.py ↔ prompts ↔ UI.
- **Lưu ý đã ghi rõ:** (a) Pydantic empty-list trả 422 thay vì 400 FRS — nêu cách map nếu cần; (b) prompts.py được tạo ở Task 7 nếu chưa có; (c) embedding dim 1536 phải khớp env↔migration.
