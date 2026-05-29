import pytest
from pydantic import ValidationError
from app.models.schemas import AuditReportSchema, VisionTagResult, IndexRequest


def test_audit_schema_roundtrip():
    data = {"discrepancies": [{"issue_title": "t", "evidence_description": "e",
            "suggested_action": "a", "related_image_url": "u"}],
            "ambiguity_alerts": [], "safety_equipment_recommendations": []}
    rep = AuditReportSchema.model_validate(data)
    assert rep.discrepancies[0].issue_title == "t"


def test_index_request_rejects_empty_urls():
    with pytest.raises(ValidationError):
        IndexRequest(project_id="P", image_urls=[])


def test_vision_result():
    v = VisionTagResult(tags=["rust"], detailed_description="d")
    assert v.tags == ["rust"]
