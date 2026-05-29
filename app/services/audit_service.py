from fastapi import HTTPException
from app.db.engine import SessionLocal
from app.db import repositories as repo
from app.core.reasoning import run_audit as run_audit_ai
from app.models.schemas import AuditResponse


async def run_audit(project_id: str, scope_text: str,
                    language: str = "English") -> AuditResponse:
    async with SessionLocal() as s:
        if not await repo.project_has_indices(s, project_id):   # EX-02
            raise HTTPException(status_code=422,
                detail="Vui lòng tải lên và xử lý hình ảnh dự án trước khi thực hiện kiểm định báo giá.")
        descs = await repo.get_descriptions(s, project_id)
        context_block = "\n".join(f"- ({url}) {desc}" for url, desc in descs)
        report = await run_audit_ai(context_block, scope_text, language)
        await repo.insert_audit_report(s, project_id, scope_text, report.model_dump())
    return AuditResponse(project_id=project_id, audit_report=report)
