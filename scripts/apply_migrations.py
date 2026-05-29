import asyncio, pathlib, asyncpg
from app.config import get_settings

async def main():
    url = get_settings().database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(url)
    for f in sorted(pathlib.Path("migrations").glob("*.sql")):
        print("applying", f.name)
        await conn.execute(f.read_text(encoding="utf-8"))
    await conn.close()
    print("migrations done")

if __name__ == "__main__":
    asyncio.run(main())
