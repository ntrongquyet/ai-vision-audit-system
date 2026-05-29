import uuid

from app.db.engine import SessionLocal
from app.db import repositories as repo


async def create(project_id: str, total: int) -> uuid.UUID:
    async with SessionLocal() as s:
        job = await repo.create_job(s, project_id, total)
        return job.id


async def mark_processing(job_id: uuid.UUID):
    async with SessionLocal() as s:
        job = await repo.get_job(s, job_id)
        job.status = "processing"
        await s.commit()


async def update_progress(job_id: uuid.UUID, succeeded: int, failed: int):
    """Persist incremental progress so GET /status reflects real-time indexing."""
    async with SessionLocal() as s:
        job = await repo.get_job(s, job_id)
        job.status = "processing"
        job.succeeded_images = succeeded
        job.failed_images = failed
        job.processed_images = succeeded + failed
        await s.commit()


async def finalize(job_id: uuid.UUID, succeeded: int, failed: int, errors: list):
    async with SessionLocal() as s:
        job = await repo.get_job(s, job_id)
        job.processed_images = succeeded + failed
        job.succeeded_images = succeeded
        job.failed_images = failed
        job.error_log = errors
        job.status = (
            "completed" if failed == 0
            else "failed" if succeeded == 0
            else "partial"
        )
        await s.commit()
