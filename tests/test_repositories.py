import pytest
from app.db.engine import SessionLocal
from app.db import repositories as repo

@pytest.mark.integration
async def test_job_and_index_flow():
    async with SessionLocal() as s:
        job = await repo.create_job(s, "PROJ-RT", 1)
        assert job.status == "pending"
        emb = [0.0] * 1536
        await repo.insert_visual_index(s, "PROJ-RT", "http://x/1.jpg",
                                       ["rust"], "rusty roof", emb)
        assert await repo.project_has_indices(s, "PROJ-RT") is True
        descs = await repo.get_descriptions(s, "PROJ-RT")
        assert descs[0][0] == "http://x/1.jpg"


@pytest.mark.integration
async def test_match_visual_indices_rpc():
    async with SessionLocal() as s:
        # insert a row whose embedding is a unit vector on dim 0
        emb = [0.0] * 1536
        emb[0] = 1.0
        await repo.insert_visual_index(s, "PROJ-MATCH", "http://x/match.jpg",
                                       ["wall"], "mossy concrete wall", emb)
        # query with the same direction → similarity ~1.0, above threshold 0.7
        results = await repo.match_visual_indices(s, "PROJ-MATCH", emb, 0.7, 3)
        assert len(results) >= 1
        assert results[0]["image_url"] == "http://x/match.jpg"
        assert results[0]["similarity"] > 0.7
