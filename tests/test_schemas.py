from app.models.schemas import AuditReportSchema, VisionTagResult, IndexRequest


def test_audit_schema_roundtrip():
    data = {"discrepancies": [{"issue_title": "t", "evidence_description": "e",
            "suggested_action": "a", "related_image_urls": ["u1", "u2"]}],
            "ambiguity_alerts": [], "safety_equipment_recommendations": []}
    rep = AuditReportSchema.model_validate(data)
    assert rep.discrepancies[0].issue_title == "t"
    assert rep.discrepancies[0].related_image_urls == ["u1", "u2"]


def test_vision_result():
    v = VisionTagResult(tags=["rust"], detailed_description="d")
    assert v.tags == ["rust"]
