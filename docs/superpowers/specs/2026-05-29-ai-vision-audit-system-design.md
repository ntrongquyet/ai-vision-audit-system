# AI Vision Audit System — Design Spec

- **Project**: AI Vision Audit System (FastAPI + Postgres/pgvector → Supabase, tích hợp Bubble.io)
- **Client**: Richard Waite (Construction, Painting & Washing Contracts)
- **Author**: SPORTAIV Team
- **Date**: 2026-05-29
- **Nguồn**: BRD, FRS, SRS trong `docs/` + sample-data (dự án Mosgiel)

> Ngôn ngữ tài liệu: tiếng Việt, giữ thuật ngữ kỹ thuật ở tiếng Anh.

---

## 1. Mục tiêu & phạm vi

### 1.1. Vấn đề nghiệp vụ
Doanh nghiệp đấu thầu thi công sơn & vệ sinh công nghiệp. Mỗi dự án có 20–40 ảnh khảo sát hiện trường + một văn bản Scope of Works (SoW). Việc đối chiếu ảnh ↔ SoW đang làm thủ công (30–45 phút/hồ sơ), dẫn đến **bỏ sót hạng mục** (thất thoát doanh thu) và **ngôn từ mơ hồ** (tranh chấp chi phí).

### 1.2. Mục tiêu (đo lường được)
- Giảm tỷ lệ bỏ sót hạng mục chi phí cao xuống **< 2%**.
- Giảm thời gian kiểm định **30–45 phút → < 2 phút**.
- Chuẩn hóa dữ liệu vào kho tập trung có **semantic index** (Supabase).
- Chi phí biến đổi (token) **< $0.5–$1.0 / dự án (~30 ảnh)** — BR-04.

### 1.3. In-scope
- Kiến trúc **"Process Once, Query Anywhere"**: mỗi ảnh chỉ được AI quét/phân tích **một lần** để tạo Visual Index, tránh lặp chi phí API.
- **AI Audit Engine**: phát hiện discrepancies, ambiguity alerts, safety/equipment recommendations.
- **Semantic Search & Chat** trên album ảnh đã index.
- Tích hợp hệ sinh thái Supabase (Tables, Storage, pgvector) — ở môi trường dev dùng Postgres + pgvector trong Docker, migrate lên Supabase cloud sau.
- **Demo UI** local để test end-to-end không cần Bubble (bổ sung ngoài BRD để phục vụ nghiệm thu).

### 1.4. Out-of-scope
- Frontend production mới (Bubble.io đảm nhiệm).
- AI tự tính lại số tiền báo giá (chỉ cảnh báo, không định giá).
- Xử lý ghi chép tay (đã chuyển sang nhập liệu cấu trúc).

---

## 2. Quyết định kiến trúc (Architecture Decisions)

| # | Quyết định | Lý do |
|---|---|---|
| AD-1 | **AI qua 9router** (OpenAI-compatible), 1 `AsyncOpenAI` client, model theo role lấy từ env (`VISION_MODEL`, `REASONING_MODEL`, `EMBEDDING_MODEL`, `EMBEDDING_DIM`) | Người dùng tự cost-tune & chọn model sau; không khoá cứng vendor |
| AD-2 | **Async = FastAPI `BackgroundTasks` + bảng `project_index_jobs` + endpoint `/status`** (Phương án A). Đây là lựa chọn cho giai đoạn hiện tại; **về sau sẽ nâng cấp lên Redis + task queue** (arq/Celery/RQ) để cải thiện performance & độ bền job. | Trung thành SRS, không thêm infra ở MVP; vẫn cấp tiến độ cho UI/Bubble. Service layer thiết kế tách rời để swap sang queue sau mà không đổi API contract |
| AD-3 | **DB access = SQLAlchemy async + asyncpg + pgvector** qua `DATABASE_URL` (thay `supabase-py`) | Chạy **giống hệt** local Docker Postgres và Supabase cloud (đều là Postgres) |
| AD-4 | **Structured output**: `response_format` JSON + validate Pydantic + 1 "repair retry" | An toàn với mọi backend phía sau 9router, không phụ thuộc tính năng riêng |
| AD-5 | **Migrations = file `.sql` thuần** trong `migrations/` | Chạy local script được, đồng thời dán/đẩy thẳng lên Supabase |
| AD-6 | **Image storage**: dev dùng endpoint `/uploads` + StaticFiles; prod Bubble upload lên Supabase Storage rồi truyền URL | Indexing chỉ cần `image_urls`; tách biệt dev/prod sạch sẽ |

---

## 3. Technology stack
- Python **3.11+**, **FastAPI** (Uvicorn ASGI).
- **SQLAlchemy 2.x async + asyncpg + pgvector**.
- **openai** SDK (async) trỏ 9router; **tenacity** (retry); **loguru** (logging); **pydantic-settings** (config).
- **Postgres 16 + pgvector** (Docker), tương thích Supabase cloud.
- Test: **pytest, pytest-asyncio**, testcontainers (hoặc compose) cho Postgres.

---

## 4. Cấu trúc thư mục

```
ai-vision-audit-system/
├── app/
│   ├── main.py                 # FastAPI app, mount routers + static UI, cấu hình timeout
│   ├── config.py               # pydantic-settings đọc .env
│   ├── security.py             # X-API-KEY dependency/middleware
│   ├── api/
│   │   ├── routes_index.py      # POST /index
│   │   ├── routes_status.py     # GET /{project_id}/status
│   │   ├── routes_audit.py      # POST /audit
│   │   ├── routes_chat.py       # POST /chat
│   │   └── routes_uploads.py    # POST /uploads (dev)
│   ├── services/
│   │   ├── indexing_service.py
│   │   ├── audit_service.py
│   │   ├── chat_service.py
│   │   └── job_service.py
│   ├── core/
│   │   ├── ai_client.py         # AsyncOpenAI → 9router
│   │   ├── vision.py            # ảnh → {tags, detailed_description}
│   │   ├── embeddings.py        # text → vector
│   │   ├── reasoning.py         # SoW audit → AuditReportSchema
│   │   ├── prompts.py           # system prompts + industry rules
│   │   └── resilience.py        # tenacity wrappers + asyncio.Semaphore(5)
│   ├── db/
│   │   ├── engine.py            # async engine/session từ DATABASE_URL
│   │   ├── models.py            # ORM models (3 bảng)
│   │   └── repositories.py      # CRUD + RPC match
│   ├── models/schemas.py        # Pydantic request/response + AuditReportSchema
│   └── static/                  # Demo UI (HTML/CSS/JS thuần)
├── migrations/
│   ├── 001_init.sql             # extension vector + 3 bảng + index
│   └── 002_match_function.sql   # RPC match_visual_indices
├── scripts/run_mosgiel_stress_test.py
├── tests/
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── pyproject.toml
└── README.md
```

---

## 5. Database schema

### 5.1. `project_visual_indices` (đúng SRS)
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE project_visual_indices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(255) NOT NULL,
    image_url TEXT NOT NULL,
    tags TEXT[] NOT NULL,
    detailed_description TEXT NOT NULL,
    embedding_vector vector(1536),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX project_visual_indices_vector_idx
    ON project_visual_indices USING hnsw (embedding_vector vector_cosine_ops);
CREATE INDEX project_visual_indices_project_id_idx
    ON project_visual_indices (project_id);
```
> `vector(1536)` mặc định khớp `EMBEDDING_DIM=1536`. Nếu đổi model embedding khác chiều, phải đổi đồng bộ migration + env.

### 5.2. `project_audit_reports` (đúng SRS)
```sql
CREATE TABLE project_audit_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(255) NOT NULL,
    scope_text TEXT NOT NULL,
    report_json JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX project_audit_reports_project_id_idx ON project_audit_reports (project_id);
```

### 5.3. `project_index_jobs` (mới — phương án A)
```sql
CREATE TABLE project_index_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending|processing|completed|partial|failed
    total_images INT NOT NULL DEFAULT 0,
    processed_images INT NOT NULL DEFAULT 0,
    succeeded_images INT NOT NULL DEFAULT 0,
    failed_images INT NOT NULL DEFAULT 0,
    error_log JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX project_index_jobs_project_id_idx ON project_index_jobs (project_id);
```

### 5.4. RPC `match_visual_indices`
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

---

## 6. API Contract

Tất cả request (trừ `/health` + static UI) **bắt buộc** header `X-API-KEY` = `APP_API_KEY`; sai/thiếu → `401`.

### 6.1. `POST /api/v1/projects/index`
Request: `{ "project_id": str, "image_urls": [str, ...] }`
- `image_urls` rỗng → `400`.
- Tạo `project_index_jobs` (pending), kích `BackgroundTasks`, trả **`202`**:
```json
{ "status": "success", "message": "Bulk image indexing initiated in background.",
  "project_id": "PROJ-3132", "job_id": "...", "total_images": 30 }
```

### 6.2. `GET /api/v1/projects/{project_id}/status`
Trả job mới nhất: `{ project_id, job_id, status, total_images, processed_images, succeeded_images, failed_images, updated_at }` → `200`.

### 6.3. `POST /api/v1/projects/audit`
Request: `{ "project_id": str, "scope_text": str }`
- Project chưa có visual index → **`422`** (EX-02): *"Vui lòng tải lên và xử lý hình ảnh dự án trước khi thực hiện kiểm định báo giá."*
- Thành công → **`200`**:
```json
{ "project_id": "...", "status": "completed", "audit_report": {
    "discrepancies": [ { "issue_title","evidence_description","suggested_action","related_image_url" } ],
    "ambiguity_alerts": [ { "original_text","risk_analysis","recommended_phrasing" } ],
    "safety_equipment_recommendations": [ { "equipment_name","reason" } ] } }
```
Lưu vào `project_audit_reports` trước khi trả.

### 6.4. `POST /api/v1/projects/chat`
Request: `{ "project_id": str, "user_question": str }`
Response `200`: `{ "answer_text": str, "reference_image_urls": [str, ...] }`.

### 6.5. `POST /api/v1/uploads` (chỉ dev)
multipart files → lưu `uploads/` → trả `{ "image_urls": [ "<UPLOAD_PUBLIC_BASE_URL>/..." ] }`.

### 6.6. `GET /health` → `200 {"status":"ok"}`.

---

## 7. Pydantic models (output enforcement — đúng SRS §4.1)
```python
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
    discrepancies: list[DiscrepancyItem]
    ambiguity_alerts: list[AmbiguityAlertItem]
    safety_equipment_recommendations: list[SafetyEquipmentItem]

class VisionTagResult(BaseModel):
    tags: list[str]
    detailed_description: str
```

---

## 8. Luồng nghiệp vụ

### 8.1. Visual Indexing (FR-1)
1. Validate payload (rỗng → 400). Tạo job `pending`, trả `202` ngay (FR-1.2).
2. BackgroundTask: chia `image_urls` thành batch 5; `asyncio.gather` dưới `asyncio.Semaphore(5)`.
3. Mỗi ảnh: `vision()` → `{tags, detailed_description}` → `embeddings()` → vector → bulk insert `project_visual_indices`.
4. **Cô lập lỗi từng ảnh** (try/except): ảnh fail → ghi `error_log`, tăng `failed_images`, tiếp tục ảnh khác (NFR §5.2).
5. Kết job: tất cả OK → `completed`; có fail nhưng có thành công → `partial`; fail toàn bộ → `failed`. Cập nhật counters + `updated_at`.

### 8.2. Scope Audit (FR-2)
1. Kiểm tra project có visual index chưa → chưa thì `422`.
2. Query toàn bộ `detailed_description` của project → gộp thành `<context>`.
3. Gọi `reasoning()` với system prompt chuyên gia + `<context>` + `<scope_text>` → ép `AuditReportSchema`.
4. Lưu `project_audit_reports`, trả `200`.

### 8.3. Semantic Chat (FR-3)
1. `embeddings(user_question)` → query vector.
2. RPC `match_visual_indices` (Top-3, ngưỡng 0.7).
3. Gửi câu hỏi + mô tả 3 ảnh vào LLM → `answer_text`; trả kèm `reference_image_urls`.

---

## 9. AI orchestration & industry intelligence (BR-03)
- **Vision prompt**: vai "field survey assistant"; nhận diện chất liệu (timber/weatherboard/brick/concrete/corrugated iron), tình trạng (peeling paint, rust, mould/mildew, cracks), bối cảnh độ cao/địa hình; ép `VisionTagResult`.
- **Reasoning prompt**: vai "international painting/cleaning tender consultant". Industry rules nạp vào prompt:
  - Nhà xây **trước 1970** → cảnh báo kiểm tra **lead paint**.
  - Chọn **PSI** rửa áp lực theo chất liệu (gỗ mềm ≠ bê tông).
  - Bề mặt **> 5m** hoặc địa hình xấu → cảnh báo scaffolding / cherry picker / boom lift.
  - Rỉ sét kim loại (mái tôn, máng nước) → đề xuất rust treatment/anti-corrosive primer.
- Map output trực tiếp vào `AuditReportSchema`; lỗi parse → 1 repair retry, vẫn lỗi → trả lỗi thân thiện + log.

---

## 10. Exception handling & NFR
- **EX-01 / NFR §5.2**: mọi call AI bọc `@retry(stop_after_attempt(3), wait_exponential(min=4,max=10))`; HTTP 429/overload → retry; quá 3 lần → log loguru, cô lập, không sập request; lỗi audit/chat tổng thể → `503` + *"Hệ thống đang bận xử lý dữ liệu lớn, vui lòng thử lại sau 1 phút."*
- **EX-02**: audit khi chưa index → `422` (mục 6.3).
- **EX-03**: Uvicorn/Gunicorn timeout ≥ **90s** cho audit.
- **NFR §5.1**: `asyncio.Semaphore(5)` — tối đa 5 ảnh gọi AI song song.
- **NFR §5.3 / BR-05/06**: `X-API-KEY` middleware; không lộ lỗi kỹ thuật thô; toàn bộ dữ liệu nằm trong DB/Storage của khách (Supabase).

---

## 11. Demo UI (local)
SPA tĩnh do FastAPI serve tại `/`:
1. Nhập/chọn `project_id`.
2. Upload ảnh (`/uploads`) → nhận URL.
3. "Index images" → `/index` → poll `/status` hiển thị tiến độ + ảnh fail.
4. Dán SoW → "Run AI Audit" → render 3 nhóm (discrepancies / ambiguity / safety) kèm ảnh bằng chứng.
5. Ô Chat → `/chat`, hiển thị answer + ảnh tham chiếu.
Tất cả request đính `X-API-KEY` (nhập 1 lần, lưu localStorage).

---

## 12. Testing & Acceptance (gắn BRD Success Criteria)
- **Unit**: Pydantic schema, prompt builder, batch/semaphore, retry (mock AI client).
- **Integration**: Postgres+pgvector (testcontainers/compose), test 4 endpoint với AI mock; verify insert/RPC/JSONB.
- **Stress-test Mosgiel** (`scripts/run_mosgiel_stress_test.py`): index ~30 ảnh thật trong sample-data, chạy audit với SoW cố tình bỏ sót (rust mái, mould → pressure-wash PSI, tường cao → scaffolding) → assert phát hiện **≥ 90%** lỗi cài cắm (BRD success criteria).
- **Cost test**: log token usage/audit → assert < ngân sách (BR-04).
- **Acceptance**: backend ghi đúng vào các bảng + bảng vector; AI đạt ≥90% trên Mosgiel; Demo UI chạy end-to-end.

---

## 13. Deployment & vận hành
- `docker-compose.yml`: `db` (`pgvector/pgvector:pg16`) + `api` (Uvicorn, timeout ≥90s) + `adminer` (xem DB); volume `uploads/`.
- `.env.example` đầy đủ biến (mục 3 phần trình bày).
- Lên cloud: chạy `migrations/*.sql` trên Supabase; đổi `DATABASE_URL` sang Supabase Postgres; ảnh thật do Bubble upload lên Supabase Storage.
- **README** kèm **Bubble integration guide**: 4 endpoint, header `X-API-KEY`, ví dụ payload, lưu ý timeout 90s + poll `/status`.

---

## 14. Milestones
1. **M1 – Foundation**: scaffold, config, docker-compose, migrations, `X-API-KEY`, `/health`.
2. **M2 – Indexing**: ai_client + vision + embeddings + job table + `/index` + `/status` + per-image isolation.
3. **M3 – Audit**: reasoning + industry-rule prompts + `/audit` + lưu report + 422.
4. **M4 – Chat**: RPC vector search + `/chat`.
5. **M5 – Demo UI** + `/uploads`.
6. **M6 – Tests + Mosgiel stress-test + cost report**.
7. **M7 – Docs + Bubble/Supabase deploy guide**.

---

## 15. Rủi ro & giả định
- **Model trên 9router phải hỗ trợ vision (multimodal) + embeddings**; nếu model embedding ≠ 1536 chiều phải đồng bộ schema/env (AD-1, §5.1).
- **HNSW index** cần pgvector ≥ 0.5 (image `pgvector/pgvector:pg16` đáp ứng).
- Ảnh hiện trường nhiều nhiễu (đồ đạc, người) → vision prompt phải tập trung bề mặt công trình, bỏ qua vật thể không liên quan.
- Chi phí token phụ thuộc kích thước context (30 mô tả ảnh); cần theo dõi để giữ < BR-04.

---

## 16. Future enhancements (ngoài MVP)
- **Durable task queue**: thay `BackgroundTasks` bằng **Redis + arq/Celery/RQ** để job sống sót khi restart, hỗ trợ nhiều worker, retry/visibility tốt hơn, scale khi số ảnh/dự án tăng (AD-2). Service layer (`indexing_service`, `job_service`) được thiết kế tách rời để swap sang queue **mà không đổi API contract** (`/index` vẫn trả `202`, UI vẫn poll `/status`).
- Khả năng mở rộng tiếp: caching mô tả ảnh, batch embedding, rate-limit theo project, list/delete project endpoints, webhook báo Bubble khi job xong (thay vì poll).
