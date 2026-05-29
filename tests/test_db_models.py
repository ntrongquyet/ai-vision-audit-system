import pytest
from app.db.engine import SessionLocal
from app.db.models import IndexJob


@pytest.mark.integration
async def test_insert_job():
    async with SessionLocal() as s:
        job = IndexJob(project_id="PROJ-TEST", total_images=3)
        s.add(job)
        await s.commit()
        await s.refresh(job)
        assert job.id is not None
        assert job.status == "pending"
