"""Acceptance test: index ~30 ảnh Mosgiel, audit với SoW thiếu cố ý, kỳ vọng phát hiện >=90%."""
import asyncio, os, glob, httpx

API = os.environ.get("API_URL", "http://localhost:8000")
KEY = os.environ.get("APP_API_KEY", "dev-secret-key")
PID = "PROJ-3132-STRESS"
IMG_DIR = "docs/sample-data/images/3132 BestStart Mosgiel, Interior and Exterior Repaint _26"

# SoW cố tình BỎ SÓT: rust mái, pressure-wash mould, scaffolding tường cao
SCOPE = ("Interior and Exterior Repaint '26. Paint all timber weatherboard walls and "
         "window frames. Clean surfaces before application.")
# Các lỗi cài cắm kỳ vọng AI phát hiện (khớp keyword bất kỳ trong report text):
EXPECTED = ["rust", "mould", "moss", "pressure", "psi", "scaffold", "ladder", "boom", "lead"]

async def main():
    h = {"X-API-KEY": KEY}
    async with httpx.AsyncClient(timeout=120) as c:
        # upload
        files = []
        for p in sorted(glob.glob(os.path.join(IMG_DIR, "*.jpg"))):
            files.append(("files", (os.path.basename(p), open(p, "rb"), "image/jpeg")))
        up = (await c.post(f"{API}/api/v1/uploads", headers=h, files=files)).json()
        urls = up["image_urls"]
        print("uploaded", len(urls))
        # index
        await c.post(f"{API}/api/v1/projects/index", headers=h,
                     json={"project_id": PID, "image_urls": urls})
        # poll
        while True:
            st = (await c.get(f"{API}/api/v1/projects/{PID}/status", headers=h)).json()
            print("status", st["status"], st["processed_images"], "/", st["total_images"])
            if st["status"] in ("completed", "partial", "failed"):
                break
            await asyncio.sleep(3)
        # audit
        rep = (await c.post(f"{API}/api/v1/projects/audit", headers=h,
                            json={"project_id": PID, "scope_text": SCOPE})).json()
        text = str(rep).lower()
        hits = [k for k in EXPECTED if k in text]
        score = len(hits) / len(EXPECTED)
        print(f"detected keywords: {hits}")
        print(f"DETECTION SCORE: {score:.0%}  (target >= 90%)")
        assert score >= 0.9, "FAILED Mosgiel acceptance (<90%)"
        print("PASSED Mosgiel acceptance")

if __name__ == "__main__":
    asyncio.run(main())
