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
         patch("app.services.audit_service.run_audit_ai", AsyncMock(return_value=rep)), \
         patch("app.services.audit_service.repo.insert_audit_report", AsyncMock()):
        out = await svc.run_audit("PROJ-X", "paint walls")
    assert out.audit_report.discrepancies == []
    assert out.project_id == "PROJ-X"
