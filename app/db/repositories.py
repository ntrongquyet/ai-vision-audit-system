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
