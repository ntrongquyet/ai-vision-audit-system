from fastapi import APIRouter, Depends
from app.security import require_api_key
from app.models.schemas import AuditRequest, AuditResponse
from app.services.audit_service import run_audit

router = APIRouter(prefix="/api/v1/projects", tags=["audit"])


@router.post("/audit", response_model=AuditResponse, dependencies=[Depends(require_api_key)])
async def audit(req: AuditRequest):
    return await run_audit(req.project_id, req.scope_text)
