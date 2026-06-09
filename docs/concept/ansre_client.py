"""
ANSRE Client SDK — CONCEPT (ตัวอย่างให้ client เรียก gateway ง่ายๆ)
==================================================================
client ภาษา Python ตัวบางๆ — ไม่ต้องรู้เรื่อง provider/คีย์/คิว เลย
แค่ชี้ base_url ของ gateway แล้วเรียก:

    from ansre_client import Ansre
    cli = Ansre("http://pj-mac-mini.tail9bbbd4.ts.net:9000", token="secret")

    # LLM (sync)
    txt = cli.llm("วิเคราะห์จุดขายนิยายย้อนเวลา 1 บรรทัด", role="analyzer")

    # Image — รอจนเสร็จ แล้วเซฟไฟล์ให้เลย
    cli.image("a serene thai temple at dawn, cinematic", "/tmp/cover.jpg")

    # Image — async: ได้ job_id ไปทำอย่างอื่นก่อน
    job = cli.image("...", wait=False)
    ... cli.wait(job["job_id"], save_to="/tmp/cover.jpg")

ใช้ stdlib ล้วน (urllib) — ก๊อปไฟล์เดียวไปใช้ที่ client ไหนก็ได้ ไม่ต้องลง dep
"""
from __future__ import annotations

import json
import time
import urllib.request
import urllib.error


class Ansre:
    def __init__(self, base_url: str, token: str = "", timeout: int = 60):
        self.base = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    # ---- internal ----
    def _req(self, method: str, path: str, body: dict | None = None, timeout=None, raw=False):
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["X-ANSRE-Token"] = self.token
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
            return r.read() if raw else json.loads(r.read().decode())

    # ---- LLM (sync) ----
    def llm(self, prompt: str, role: str = "default", system: str | None = None,
            is_json: bool = False) -> str:
        r = self._req("POST", "/v1/llm/generate",
                      {"prompt": prompt, "role": role, "system": system, "is_json": is_json})
        return r["text"]

    # ---- Image (async job) ----
    def image(self, prompt: str, save_to: str | None = None, aspect_ratio: str = "1:1",
              backend: str | None = None, wait: bool = True, poll_timeout: int = 600):
        """
        wait=True  : บล็อกจนเรนเดอร์เสร็จ, ถ้าใส่ save_to จะเซฟไฟล์ให้ คืน path
        wait=False : คืน {job_id, status} ทันที (ไปเช็คเองด้วย .status()/.wait())
        """
        job = self._req("POST", "/v1/image/generate",
                        {"prompt": prompt, "aspect_ratio": aspect_ratio, "backend": backend})
        if not wait:
            return job
        return self.wait(job["job_id"], save_to=save_to, poll_timeout=poll_timeout)

    def status(self, job_id: str) -> dict:
        return self._req("GET", f"/v1/jobs/{job_id}")

    def wait(self, job_id: str, save_to: str | None = None, poll_timeout: int = 600,
             interval: float = 2.0):
        deadline = time.monotonic() + poll_timeout
        while time.monotonic() < deadline:
            st = self.status(job_id)
            if st["status"] == "done":
                if save_to:
                    img = self._req("GET", f"/v1/image/result/{job_id}", raw=True, timeout=120)
                    with open(save_to, "wb") as f:
                        f.write(img)
                    return save_to
                return st
            if st["status"] == "error":
                raise RuntimeError(f"image job failed: {st.get('error')}")
            time.sleep(interval)
        raise TimeoutError(f"job {job_id} ไม่เสร็จใน {poll_timeout}s")

    def health(self) -> dict:
        return self._req("GET", "/healthz")


if __name__ == "__main__":
    import sys
    cli = Ansre(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9000")
    print("health:", cli.health())
    print("llm:", cli.llm("พูดสวัสดีสั้นๆ", role="analyzer"))
    print("image ->", cli.image("a misty thai mountain temple, cinematic", "/tmp/ansre_demo.png"))
