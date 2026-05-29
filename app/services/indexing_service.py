import asyncio

from loguru import logger

from app.config import get_settings
from app.core.vision import analyze_image
from app.core.embeddings import embed_text
from app.core.resilience import get_semaphore
from app.db.engine import SessionLocal
from app.db import repositories as repo
from app.services import job_service


async def _process_one(project_id: str, url: str):
    async with get_semaphore():           # NFR 5.1: max 5 song song
        vision = await analyze_image(url)
        embedding = await embed_text(vision.detailed_description)
        async with SessionLocal() as s:
            await repo.insert_visual_index(
                s, project_id, url, vision.tags, vision.detailed_description, embedding)


async def run_indexing_job(job_id, project_id: str, image_urls: list[str]):
    succeeded = failed = 0
    errors: list[dict] = []
    batch = get_settings().ai_batch_size
    await job_service.mark_processing(job_id)
    for i in range(0, len(image_urls), batch):     # FR-1.2: batch 5
        chunk = image_urls[i:i + batch]
        results = await asyncio.gather(
            *[_process_one(project_id, u) for u in chunk], return_exceptions=True)
        for url, res in zip(chunk, results):
            if isinstance(res, Exception):          # NFR 5.2: cô lập lỗi
                failed += 1
                errors.append({"image_url": url, "error": str(res)})
                logger.error(f"index failed {url}: {res}")
            else:
                succeeded += 1
        # persist incremental progress so the UI progress bar tracks reality
        await job_service.update_progress(job_id, succeeded, failed)
    await job_service.finalize(job_id, succeeded, failed, errors)
