import pytest
from unittest.mock import AsyncMock, patch
from app.models.schemas import VisionTagResult


@pytest.mark.asyncio
async def test_indexing_isolates_failures():
    from app.services import indexing_service as svc

    async def fake_vision(url):
        if "bad" in url:
            raise RuntimeError("vision failed")
        return VisionTagResult(tags=["t"], detailed_description="d")

    async def fake_embed(text):
        return [0.0] * 1536

    inserted = []

    async def fake_insert(*a, **k):
        inserted.append(a)

    finals = {}

    async def fake_finalize(job_id, succeeded, failed, errors):
        finals.update(dict(succeeded=succeeded, failed=failed, errors=errors))

    progress = []

    async def fake_update_progress(job_id, succeeded, failed):
        progress.append((succeeded, failed))

    with patch.object(svc, "analyze_image", fake_vision), \
         patch.object(svc, "embed_text", fake_embed), \
         patch("app.services.indexing_service.repo.insert_visual_index", fake_insert), \
         patch("app.services.indexing_service.job_service.mark_processing", AsyncMock()), \
         patch("app.services.indexing_service.job_service.update_progress", fake_update_progress), \
         patch("app.services.indexing_service.job_service.finalize", fake_finalize):
        await svc.run_indexing_job("job-1", "PROJ-X",
                                   ["http://ok/1.jpg", "http://bad/2.jpg"])
    assert finals["succeeded"] == 1
    assert finals["failed"] == 1
    assert len(finals["errors"]) == 1
    # progress was reported incrementally (at least once, ending at final tally)
    assert progress and progress[-1] == (1, 1)
