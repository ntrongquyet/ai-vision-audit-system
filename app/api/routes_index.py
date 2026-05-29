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
