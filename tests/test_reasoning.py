import json, pytest
from unittest.mock import AsyncMock, patch
from app.core import reasoning

@pytest.mark.asyncio
async def test_run_audit_parses_report():
    payload = {"discrepancies": [{"issue_title":"Rust on roof",
        "evidence_description":"Photo shows rust","suggested_action":"Add rust line item",
        "related_image_urls":["http://x/1.jpg","http://x/2.jpg"]}],
        "ambiguity_alerts": [], "safety_equipment_recommendations": []}
    fake = AsyncMock()
    fake.chat.completions.create.return_value = type("R", (), {
        "choices": [type("C", (), {"message": type("M", (), {
            "content": json.dumps(payload)})()})()]})()
    with patch("app.core.reasoning.get_ai_client", return_value=fake):
        rep = await reasoning.run_audit("ctx of photos", "paint timber walls")
    assert rep.discrepancies[0].issue_title == "Rust on roof"

@pytest.mark.asyncio
async def test_run_audit_repair_retry_on_bad_json():
    good = {"discrepancies": [], "ambiguity_alerts": [], "safety_equipment_recommendations": []}
    fake = AsyncMock()
    # first call returns invalid JSON, second returns valid
    bad_msg = type("M", (), {"content": "not json at all"})()
    good_msg = type("M", (), {"content": json.dumps(good)})()
    fake.chat.completions.create.side_effect = [
        type("R", (), {"choices": [type("C", (), {"message": bad_msg})()]})(),
        type("R", (), {"choices": [type("C", (), {"message": good_msg})()]})(),
    ]
    with patch("app.core.reasoning.get_ai_client", return_value=fake):
        rep = await reasoning.run_audit("ctx", "scope")
    assert rep.discrepancies == []
    assert fake.chat.completions.create.call_count == 2

@pytest.mark.asyncio
async def test_run_audit_passes_language_into_prompt():
    good = {"discrepancies": [], "ambiguity_alerts": [], "safety_equipment_recommendations": []}
    fake = AsyncMock()
    fake.chat.completions.create.return_value = type("R", (), {
        "choices": [type("C", (), {"message": type("M", (), {
            "content": json.dumps(good)})()})()]})()
    with patch("app.core.reasoning.get_ai_client", return_value=fake):
        await reasoning.run_audit("ctx", "scope", language="Vietnamese")
    sent = fake.chat.completions.create.call_args.kwargs["messages"]
    assert any("Vietnamese" in m["content"] for m in sent)
