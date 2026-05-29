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
