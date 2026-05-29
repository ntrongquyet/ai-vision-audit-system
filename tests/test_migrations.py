import asyncpg, pytest
from app.config import get_settings

@pytest.mark.integration
async def test_tables_exist():
    url = get_settings().database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(url)
    rows = await conn.fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    names = {r["table_name"] for r in rows}
    await conn.close()
    assert {"project_visual_indices", "project_audit_reports", "project_index_jobs"} <= names
