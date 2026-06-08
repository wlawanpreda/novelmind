// ANSRE Dashboard frontend logic
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const api = (p, opt) => fetch(p, opt).then(r => r.json()).catch(e => { toast("เชื่อมต่อ server ไม่ได้", "bad"); throw e; });
const VIEW_META = {
  overview: ["ภาพรวม", "สถานะระบบและการผลิตคอนเทนต์"],
  ideas: ["ไอเดีย", "คลังไอเดีย — คิด ให้คะแนน แล้ว promote ไปเขียน"],
  novels: ["นิยาย", "คลังนิยายที่หามาและดัดแปลง"],
  studio: ["Studio", "สร้าง prompt ภาพ/วิดีโอ, script เสียง, ลูปเกลาบท"],
  outputs: ["ผลผลิต", "ปก หนังสือเสียง และวิดีโอ teaser"],
  usage: ["ค่าใช้จ่าย", "ติดตามการใช้ token และต้นทุน"],
  config: ["LLM Routing", "งานไหนวิ่งไป Gemini หรือ Mac mini"],
  health: ["สุขภาพระบบ", "ตรวจว่าทุกอย่างพร้อมใช้งาน"],
};

// ---- navigation ----
$$(".nav a").forEach(a => a.onclick = () => {
  $$(".nav a").forEach(x => x.classList.remove("active"));
  a.classList.add("active");
  const v = a.dataset.view;
  $$(".view").forEach(x => x.classList.remove("active"));
  $("#view-" + v).classList.add("active");
  const [t, s] = VIEW_META[v]; $("#viewTitle").textContent = t; $("#viewSub").textContent = s;
  loadView(v);
});

// ---- toasts ----
function toast(msg, kind = "") {
  const el = document.createElement("div");
  el.className = "toast " + kind; el.textContent = msg;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

// ---- overview ----
const STAT_DEFS = [
  ["scouted", "🔍 รอวิเคราะห์", "pool"], ["analyzed", "🧠 รอเขียน", "pool"],
  ["chapters", "📖 บทนิยาย", "outputs"], ["audio", "🎧 หนังสือเสียง", "outputs"],
  ["teasers", "🎬 teaser", "outputs"], ["publish_queue", "📤 คิวเผยแพร่", "outputs"],
];
const STAGES = [
  ["scout", "🔍 Scout", "scouted", "pool"], ["analyze", "🧠 Analyze", "analyzed", "pool"],
  ["write", "✍️ Write", "processed", "pool"], ["cover", "🖼️ Cover", "covers", "outputs"],
  ["audio", "🎧 Audio", "audio", "outputs"], ["teaser", "🎬 Teaser", "teasers", "outputs"],
  ["publish", "📤 Publish", "publish_queue", "outputs"],
];

async function loadOverview() {
  const s = await api("/api/status");
  $("#statCards").innerHTML = STAT_DEFS.map(([k, lbl, grp]) =>
    `<div class="card stat"><div class="k">${lbl}</div><div class="v">${s[grp][k] ?? 0}</div></div>`).join("")
    + `<div class="card stat flat"><div class="k">💰 ค่า LLM วันนี้</div><div class="v">$${s.spend_today.toFixed(4)}</div></div>`;
  $("#flow").innerHTML = STAGES.map((st, i) => {
    const cnt = s[st[3]][st[2]] ?? 0;
    return `<div class="step"><span class="run" onclick="runStage('${st[0]}')">▶ run</span>
      <div class="n">${st[1]}</div><div class="c">${cnt}</div></div>`
      + (i < STAGES.length - 1 ? '<div class="arrow">→</div>' : '');
  }).join("");
  $("#quickActions").innerHTML = STAGES.map(st =>
    `<button class="btn" onclick="runStage('${st[0]}')">${st[1]}</button>`).join("");
  updateWorker(s.worker_running);
  $("#clock").textContent = "อัปเดต " + s.time;
}

function updateWorker(on) {
  const p = $("#workerPill");
  p.classList.toggle("on", !!on);
  $("#workerTxt").textContent = "worker: " + (on ? "ทำงาน" : "หยุด");
}

// ---- ideas ----
const SRC_ICON = { manual: "✍️", brainstorm: "🤖", trend: "🔥", fusion: "🧬", merge: "🧬" };
let IDEAS = [], SEL = new Set();

async function loadIdeas() {
  const { ideas } = await api("/api/ideas");
  IDEAS = ideas || [];
  SEL = new Set([...SEL].filter(id => IDEAS.some(i => i.id === id)));
  renderIdeas();
}

function ideaCard(i) {
  const sel = SEL.has(i.id) ? " selected" : "";
  const score = i.score ? `<div class="score">${esc(i.score)}<small style="color:var(--muted);font-size:11px">/10</small></div>` : "<div></div>";
  const act = i.status === "Scored"
    ? `<button class="btn sm" onclick="event.stopPropagation();ideaLoop('${esc(i.id)}')">🔄</button>
       <button class="btn sm" onclick="event.stopPropagation();promoteIdea('${esc(i.id)}')">→ เขียน</button>`
    : `<div class="tag ${i.status === "Promoted" ? "Processed" : "Analyzed"}">${esc(i.status)}</div>`;
  return `<div class="nv-row idea-card${sel}" draggable="true" data-id="${esc(i.id)}"
       ondragstart="dragIdea(event)" ondragover="event.preventDefault()" ondrop="dropIdea(event)">
      <input type="checkbox" class="idea-chk" ${sel ? "checked" : ""} onclick="event.stopPropagation();toggleSel('${esc(i.id)}')">
      <div><div class="ti">${SRC_ICON[i.source] || "💡"} ${esc(i.title)}
        ${i.group ? `<span class="grp">🗂️ ${esc(i.group)}</span>` : ""}</div>
        <div class="meta">${esc(i.logline || i.genre || "ยังไม่ได้ให้คะแนน")}</div></div>
      ${score}
      <span class="head-actions" style="gap:6px">${act}
        <button class="btn sm ghost" onclick="event.stopPropagation();delIdea('${esc(i.id)}')" title="ลบ">🗑️</button></span>
    </div>`;
}

function renderIdeas() {
  const q = ($("#ideaSearch")?.value || "").toLowerCase();
  const groupBy = $("#ideaGroupBy")?.value || "none";
  const sortBy = $("#ideaSort")?.value || "score";
  let list = IDEAS.filter(i => !q || (i.title + i.logline + i.genre).toLowerCase().includes(q));
  list.sort(sortBy === "title" ? (a, b) => a.title.localeCompare(b.title)
    : (a, b) => (parseFloat(b.score) || 0) - (parseFloat(a.score) || 0));
  const el = $("#ideaList");
  if (!list.length) { el.innerHTML = `<div class="empty">ยังไม่มีไอเดีย — พิมพ์ด้านบน หรือกด “ให้ AI คิดไอเดีย”</div>`; updateBulk(); return; }
  if (groupBy === "none") {
    el.innerHTML = list.map(ideaCard).join("");
  } else {
    const groups = {};
    list.forEach(i => { const k = i[groupBy] || "(ไม่ระบุ)"; (groups[k] = groups[k] || []).push(i); });
    el.innerHTML = Object.entries(groups).map(([k, items]) =>
      `<div class="grp-head">${esc(k)} <span>${items.length}</span></div>` + items.map(ideaCard).join("")).join("");
  }
  updateBulk();
}

// selection
function toggleSel(id) { SEL.has(id) ? SEL.delete(id) : SEL.add(id); renderIdeas(); }
function clearSel() { SEL.clear(); renderIdeas(); }
function updateBulk() {
  $("#bulkCount").textContent = SEL.size;
  $("#ideaBulk").style.display = SEL.size ? "flex" : "none";
}
// drag-to-merge
let DRAG_ID = null;
function dragIdea(e) { DRAG_ID = e.currentTarget.dataset.id; e.dataTransfer.effectAllowed = "move"; }
function dropIdea(e) {
  e.preventDefault();
  const target = e.currentTarget.dataset.id;
  if (DRAG_ID && target && DRAG_ID !== target) mergeIdeas([DRAG_ID, target]);
  DRAG_ID = null;
}
// bulk actions
async function mergeIdeas(ids) {
  const r = await api("/api/idea/merge", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids }) });
  if (r.error) return toast(r.error, "bad");
  toast("กำลังผสมไอเดีย 🧬"); openDrawer(r.task, "merge ideas"); clearSel();
}
function bulkMerge() { if (SEL.size < 2) return toast("เลือกอย่างน้อย 2 อัน", "bad"); mergeIdeas([...SEL]); }
async function bulkDelete() {
  if (!confirm(`ลบ ${SEL.size} ไอเดีย?`)) return;
  for (const id of SEL) await api("/api/idea/action", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "delete", id }) });
  toast("ลบแล้ว", "good"); clearSel(); loadIdeas();
}
async function bulkGroup() {
  const g = prompt("ชื่อกลุ่ม:"); if (!g) return;
  for (const id of SEL) await api("/api/idea/action", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "group", id, group: g }) });
  toast("จัดกลุ่มแล้ว 🗂️", "good"); clearSel(); loadIdeas();
}
async function delIdea(id) {
  if (!confirm("ลบไอเดียนี้?")) return;
  await api("/api/idea/action", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "delete", id }) });
  toast("ลบแล้ว", "good"); loadIdeas();
}
async function addIdea() {
  const t = $("#ideaInput").value.trim();
  if (!t) return;
  const r = await api("/api/idea/add", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: t }) });
  if (r.ok) { $("#ideaInput").value = ""; toast("เก็บไอเดียแล้ว 💡", "good"); loadIdeas(); }
}
async function ideaLoop(id) {
  const r = await api("/api/studio", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "idea-loop", id, rounds: 3 }) });
  if (r.error) return toast("error: " + r.error, "bad");
  toast("เริ่ม AI loop เกลาไอเดีย 🔄");
  openDrawer(r.task, "idea loop");
}
async function promoteIdea(id) {
  const r = await api("/api/idea/promote", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id }) });
  if (r.ok) { toast("ส่งเข้าคิวเขียนแล้ว ✍️", "good"); loadIdeas(); refreshAll(); }
}

// ---- studio ----
async function loadProjects() {
  const { projects } = await api("/api/projects");
  const sel = $("#studioProject");
  sel.innerHTML = projects.length
    ? projects.map(p => `<option value="${esc(p)}">${esc(p.length > 50 ? p.slice(0, 50) + "…" : p)}</option>`).join("")
    : `<option value="">(ยังไม่มีเรื่อง — เขียนนิยายก่อน)</option>`;
}
const loadStudio = loadProjects;

async function studio(action) {
  const title = $("#studioProject").value;
  if (!title) return toast("เลือกเรื่องก่อน", "bad");
  const body = { action, title, rounds: 2 };
  const r = await api("/api/studio", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (r.error) return toast("error: " + r.error, "bad");
  toast("เริ่ม: " + action);
  openDrawer(r.task, "studio: " + action);
  // หลังเสร็จ ลองโหลดผลให้ดู
  const kind = { visual: "visual", video: "video", audio: "audio", bible: "bible" }[action];
  if (kind) setTimeout(() => viewStudio(kind), 1500);
}

async function viewStudio(kind) {
  const title = $("#studioProject").value;
  if (!title) return;
  const r = await api(`/api/studio/output?kind=${encodeURIComponent(kind)}&title=${encodeURIComponent(title)}`);
  $("#studioOut").textContent = (r.content && r.content.trim()) ? r.content : `(ยังไม่มีผล ${kind} — กดปุ่มสร้างด้านบน)`;
}

// ---- novels ----
async function loadNovels() {
  const [{ novels }, trend] = await Promise.all([api("/api/novels"), api("/api/trends")]);
  const fmtViews = v => v >= 1e6 ? (v / 1e6).toFixed(1) + "M" : v >= 1e3 ? (v / 1e3).toFixed(0) + "K" : v;
  $("#novelList").innerHTML = `
    <div class="head-actions" style="margin-bottom:14px">
      <button class="btn" onclick="runStage('scout')">🔍 Scout เรื่องใหม่</button>
      <button class="btn" onclick="runStage('analyze')">🧠 วิเคราะห์</button>
      <button class="btn" onclick="runStage('trends')">📈 สรุปเทรนด์</button>
    </div>` + (trend.content ? `<details class="card" style="margin-bottom:14px"><summary style="cursor:pointer;font-weight:700">📈 Trend Report (คลิกดู)</summary><pre class="studio-out" style="margin-top:12px">${esc(trend.content)}</pre></details>` : "")
    + (novels.length ? novels.map(n => `
    <div class="nv-row">
      <div><div class="ti">${n.rank ? `<span class="rankbadge">#${n.rank}</span> ` : ""}${esc(n.title)}</div>
        <div class="meta">${esc(n.source)} · ${esc(n.genre || "—")}${n.rating ? ` · ⭐${esc(n.rating)}` : ""}${n.views ? ` · 👁 ${fmtViews(n.views)}` : ""}</div></div>
      ${n.popularity ? `<div class="score">${n.popularity}<small style="color:var(--muted);font-size:11px">/100</small></div>` : "<div></div>"}
      <div class="tag ${n.status}">${esc(n.status)}</div>
    </div>`).join("") : `<div class="empty">ยังไม่มีนิยาย — กด “🔍 Scout เรื่องใหม่”</div>`);
}

// ---- outputs ----
async function loadOutputs() {
  const o = await api("/api/outputs");
  $("#galCovers").innerHTML = o.covers.length ? o.covers.map(c =>
    `<div class="item"><img loading="lazy" src="${c.url}"><div class="cap">${esc(c.name)}</div></div>`).join("")
    : emptyGal("ยังไม่มีปก");
  $("#galAudio").innerHTML = o.audio.length ? o.audio.map(a =>
    `<div class="item" style="padding:12px"><div class="cap" style="padding:0 0 8px">${esc(a.name)}</div><audio controls preload="none" src="${a.url}"></audio></div>`).join("")
    : emptyGal("ยังไม่มีหนังสือเสียง");
  $("#galTeasers").innerHTML = o.teasers.length ? o.teasers.map(t =>
    `<div class="item"><video controls preload="metadata" src="${t.url}"></video><div class="cap">${esc(t.name)}</div></div>`).join("")
    : emptyGal("ยังไม่มี teaser");
}
const emptyGal = m => `<div class="empty">${m}</div>`;

// ---- usage ----
async function loadUsage() {
  const u = await api("/api/usage");
  const total = u.by_date.reduce((a, [, v]) => a + v, 0);
  $("#usageCards").innerHTML = `
    <div class="card stat"><div class="k">💰 วันนี้</div><div class="v">$${u.today.toFixed(4)}</div></div>
    <div class="card stat flat"><div class="k">📅 รวม 14 วัน</div><div class="v">$${total.toFixed(3)}</div></div>
    <div class="card stat flat"><div class="k">🟢 เรียก local (ฟรี)</div><div class="v">${u.by_backend.local || 0}</div></div>
    <div class="card stat flat"><div class="k">🟣 เรียก gemini</div><div class="v">${u.by_backend.gemini || 0}</div></div>`;
  const max = Math.max(0.0001, ...u.by_date.map(([, v]) => v));
  $("#usageChart").innerHTML = u.by_date.length ? u.by_date.map(([d, v]) =>
    `<div class="bar" style="height:${Math.max(3, v / max * 100)}%" title="${d}: $${v}">
       <span>$${v.toFixed(3)}</span><small>${d.slice(5)}</small></div>`).join("")
    : `<div class="empty">ยังไม่มีข้อมูลการใช้งาน</div>`;
  $("#backendBreak").innerHTML = Object.entries(u.by_backend).map(([b, n]) =>
    `<div class="route"><b>${b}</b><span class="be ${b}">${n} ครั้ง</span></div>`).join("") || `<div class="empty">—</div>`;
}

// ---- config ----
async function loadConfig() {
  const c = await api("/api/config");
  $("#configCards").innerHTML = `
    <div class="card stat flat"><div class="k">🔀 Backend</div><div class="v" style="font-size:22px">${c.backend}</div></div>
    <div class="card stat flat"><div class="k">✍️ Writing mode</div><div class="v" style="font-size:22px">${c.writing_mode}</div></div>
    <div class="card stat flat"><div class="k">🖥️ Local model</div><div class="v" style="font-size:16px">${esc(c.local_model || "—")}</div></div>
    <div class="card stat flat"><div class="k">🧱 เพดาน/วัน</div><div class="v" style="font-size:20px">$${c.daily_cap}</div></div>`;
  $("#routingChips").innerHTML = c.routing.map(r =>
    `<div class="route"><b>${r.role}</b><span class="be ${r.backend}">${r.backend}</span></div>`).join("");
  // เติมค่าปัจจุบันลงในฟอร์มตั้งค่า
  if ($("#set-backend")) { $("#set-backend").value = c.backend; $("#set-mode").value = c.writing_mode; $("#set-cap").value = c.daily_cap; }
}

async function saveSettings() {
  const body = {
    LLM_BACKEND: $("#set-backend").value,
    WRITING_MODE: $("#set-mode").value,
    ANSRE_DAILY_USD_CAP: $("#set-cap").value || "0",
  };
  const r = await api("/api/env", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (r.ok) { toast("บันทึกแล้ว: " + r.updated.join(", "), "good"); loadConfig(); }
  else toast("บันทึกไม่สำเร็จ", "bad");
}

// ---- health ----
async function loadHealth() {
  const d = await api("/api/doctor");
  $("#healthChecks").innerHTML = d.checks.map(c => `
    <div class="check ${c.level}">
      <div class="badge">${c.ok ? "✓" : (c.level === "warn" ? "!" : "✕")}</div>
      <div><div class="t">${esc(c.label)}</div><div class="d">${esc(c.detail)}</div></div>
    </div>`).join("");
}

// ---- actions ----
async function runPipeline() {
  $("#runBtn").disabled = true;
  const { task } = await api("/api/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  toast("เริ่มเดิน pipeline แล้ว");
  openDrawer(task, "เดิน Pipeline");
  $("#runBtn").disabled = false;
}
async function runStage(stage) {
  const { task, error } = await api("/api/stage", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ stage })
  });
  if (error) return toast("error: " + error, "bad");
  toast("เริ่ม: " + stage);
  openDrawer(task, stage);
}
async function worker(action) {
  const r = await api("/api/worker", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action })
  });
  updateWorker(r.running);
  toast(action === "start" ? "เปิด worker แล้ว — จะรันเองทุก 20 นาที" : "ปิด worker แล้ว", "good");
}

// ---- log drawer ----
let pollTimer = null;
function openDrawer(task, title) {
  if (!task) return;
  $("#drawer").classList.add("open");
  $("#drawerTitle").textContent = title;
  $("#drawerLog").textContent = "กำลังเริ่ม…";
  clearInterval(pollTimer);
  const poll = async () => {
    const t = await api("/api/task/" + task);
    $("#drawerLog").textContent = t.output || "(no output)";
    $("#drawerLog").scrollTop = $("#drawerLog").scrollHeight;
    const st = $("#drawerStatus"); st.className = "st " + t.status;
    st.innerHTML = t.status === "running" ? '<span class="spinner"></span> running' : t.status;
    if (t.status !== "running") {
      clearInterval(pollTimer);
      toast(t.status === "done" ? "เสร็จแล้ว: " + title : "ผิดพลาด: " + title, t.status === "done" ? "good" : "bad");
      refreshAll();
    }
  };
  poll(); pollTimer = setInterval(poll, 1500);
}
function closeDrawer() { $("#drawer").classList.remove("open"); clearInterval(pollTimer); }

// ---- util ----
function esc(s) { return String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

function loadView(v) {
  ({ overview: loadOverview, ideas: loadIdeas, novels: loadNovels, studio: loadStudio,
     outputs: loadOutputs, usage: loadUsage, config: loadConfig, health: loadHealth }[v] || (() => {}))();
}
function refreshAll() {
  const active = $(".nav a.active").dataset.view;
  loadOverview(); loadView(active);
}
// boot
loadOverview();
setInterval(loadOverview, 8000);
