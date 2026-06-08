"""
ANSRE Client — SDK บางๆ เรียก ANSRE Gateway (stdlib ล้วน, ก๊อปไฟล์เดียวไปใช้ได้)
================================================================================
    from ansre_client import Ansre
    cli = Ansre("http://pj-mac-mini.tail9bbbd4.ts.net:9000", token="secret")

    txt = cli.llm("วิเคราะห์จุดขาย 1 บรรทัด", role="analyzer")        # sync
    cli.image("a serene thai temple at dawn", "/tmp/cover.jpg")        # รอ+เซฟให้
    job = cli.image("...", wait=False)                                # async

ตั้ง default ผ่าน env ได้: ANSRE_GATEWAY_URL, ANSRE_GATEWAY_TOKEN
"""
from __future__ import annotations

import os
import json
import time
import urllib.request


class Ansre:
    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: int = 120):
        self.base = (base_url or os.environ.get("ANSRE_GATEWAY_URL", "http://localhost:9000")).rstrip("/")
        self.token = token if token is not None else os.environ.get("ANSRE_GATEWAY_TOKEN", "")
        self.timeout = timeout

    def _req(self, method, path, body=None, timeout=None, raw=False):
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["X-ANSRE-Token"] = self.token
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
            return r.read() if raw else json.loads(r.read().decode())

    # LLM (sync)
    def llm(self, prompt, role="default", system=None, is_json=False) -> str:
        return self._req("POST", "/v1/llm/generate",
                         {"prompt": prompt, "role": role, "system": system,
                          "is_json": is_json})["text"]

    # Image (async job)
    def image(self, prompt, save_to=None, aspect_ratio="1:1", backend=None,
              wait=True, poll_timeout=600):
        job = self._req("POST", "/v1/image/generate",
                        {"prompt": prompt, "aspect_ratio": aspect_ratio, "backend": backend})
        if not wait:
            return job
        return self.wait(job["job_id"], save_to=save_to, poll_timeout=poll_timeout)

    def status(self, job_id) -> dict:
        return self._req("GET", f"/v1/jobs/{job_id}")

    def wait(self, job_id, save_to=None, poll_timeout=600, interval=2.0):
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
    cli = Ansre(sys.argv[1] if len(sys.argv) > 1 else None)
    print("health:", json.dumps(cli.health(), ensure_ascii=False))
    print("llm   :", cli.llm("พูดสวัสดีสั้นๆ", role="analyzer"))
