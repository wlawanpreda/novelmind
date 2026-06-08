# 📞 ANSRE Gateway — ตัวอย่างเรียกจาก client ต่างๆ (CONCEPT)

> ดูสถาปัตยกรรมที่ [../SERVICE_ARCHITECTURE.md](../SERVICE_ARCHITECTURE.md) · gateway: [gateway.py](gateway.py) · SDK: [ansre_client.py](ansre_client.py)
> สมมติ gateway รันที่ `http://pj-mac-mini.tail9bbbd4.ts.net:9000` token = `secret`

---

## 1. curl (เครื่องไหนก็เรียกได้)

```bash
GW=http://pj-mac-mini.tail9bbbd4.ts.net:9000
H='-H Content-Type:application/json -H X-ANSRE-Token:secret'

# LLM (sync) — ได้ข้อความกลับทันที
curl -s $GW/v1/llm/generate $H \
  -d '{"prompt":"วิเคราะห์จุดขายนิยายย้อนเวลา 1 บรรทัด","role":"analyzer"}'
# -> {"text":"..."}

# Image (async) — ได้ job_id
JOB=$(curl -s $GW/v1/image/generate $H \
  -d '{"prompt":"a serene thai temple at dawn, cinematic","aspect_ratio":"1:1"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['job_id'])")

# เช็คสถานะจนเสร็จ
curl -s $GW/v1/jobs/$JOB -H X-ANSRE-Token:secret      # {"status":"running"} ... "done"

# ดึงรูป
curl -s $GW/v1/image/result/$JOB -H X-ANSRE-Token:secret -o cover.png
```

---

## 2. Python (ใช้ SDK — 3 บรรทัด)

```python
from ansre_client import Ansre
cli = Ansre("http://pj-mac-mini.tail9bbbd4.ts.net:9000", token="secret")

text = cli.llm("ตั้งชื่อไทยให้นิยายสืบสวน 5 ชื่อ", role="analyzer")
cli.image("a serene thai temple at dawn, cinematic", "/tmp/cover.jpg")   # รอ+เซฟให้เลย
```

---

## 3. JavaScript / Node (fetch)

```js
const GW = "http://pj-mac-mini.tail9bbbd4.ts.net:9000";
const H = { "Content-Type": "application/json", "X-ANSRE-Token": "secret" };

// LLM
const r = await fetch(`${GW}/v1/llm/generate`, {
  method: "POST", headers: H,
  body: JSON.stringify({ prompt: "เขียนประโยคเปิดนิยาย", role: "writer" }),
});
console.log((await r.json()).text);

// Image: enqueue -> poll -> ดึงรูป
const { job_id } = await (await fetch(`${GW}/v1/image/generate`, {
  method: "POST", headers: H,
  body: JSON.stringify({ prompt: "a misty thai mountain temple, cinematic" }),
})).json();

let st;
do { await new Promise(s => setTimeout(s, 2000));
     st = await (await fetch(`${GW}/v1/jobs/${job_id}`, { headers: H })).json();
} while (st.status === "queued" || st.status === "running");

const img = await (await fetch(`${GW}/v1/image/result/${job_id}`, { headers: H })).arrayBuffer();
require("fs").writeFileSync("cover.png", Buffer.from(img));
```

---

## 4. ANSRE pipeline (หลังย้าย — เทียบกับของเดิม)

```python
# เดิม: import provider ตรง (เครื่อง client ต้องมีคีย์ + โค้ด provider)
from image_provider import generate_image
generate_image(prompt, "cover.jpg", aspect_ratio="1:1")

# ใหม่: เรียก gateway (client ไม่ต้องรู้คีย์/คิว/โมเดล — แค่ token)
from ansre_client import Ansre
Ansre(GW, token=TOKEN).image(prompt, "cover.jpg")
```

> ย้ายทีละไฟล์ได้ — ใส่ fallback: ถ้า gateway ต่อไม่ได้ค่อย import provider เดิม จนกว่าจะมั่นใจ

---

## 5. n8n / automation อื่น
ใช้ HTTP Request node ยิง `/v1/image/generate` → เก็บ `job_id` → loop `/v1/jobs/{id}` จน `done`
→ `/v1/image/result/{id}` หรือใส่ `callback_url` (Phase 4) ให้ gateway ยิงกลับเมื่อเสร็จ
