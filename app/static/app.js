const $ = id => document.getElementById(id);
const hdr = () => ({ "X-API-KEY": $("key").value, "Content-Type": "application/json" });
const pid = () => $("pid").value;

async function uploadAndIndex() {
  const fd = new FormData();
  for (const f of $("files").files) fd.append("files", f);
  const up = await fetch("/api/v1/uploads", { method: "POST",
    headers: { "X-API-KEY": $("key").value }, body: fd }).then(r => r.json());
  await fetch("/api/v1/projects/index", { method: "POST", headers: hdr(),
    body: JSON.stringify({ project_id: pid(), image_urls: up.image_urls }) });
  refreshStatus();
}
async function refreshStatus() {
  const r = await fetch(`/api/v1/projects/${pid()}/status`, { headers: hdr() });
  $("status").textContent = JSON.stringify(await r.json(), null, 2);
}
async function runAudit() {
  const r = await fetch("/api/v1/projects/audit", { method: "POST", headers: hdr(),
    body: JSON.stringify({ project_id: pid(), scope_text: $("scope").value }) }).then(r => r.json());
  const rep = r.audit_report || {};
  const sec = (title, arr, fmt) => `<h4>${title} (${(arr||[]).length})</h4>` +
    (arr||[]).map(fmt).join("");
  $("report").innerHTML =
    sec("Discrepancies", rep.discrepancies, d => `<pre>${d.issue_title}\n${d.evidence_description}\n→ ${d.suggested_action}</pre><img src="${d.related_image_url}">`) +
    sec("Ambiguity alerts", rep.ambiguity_alerts, a => `<pre>"${a.original_text}"\n${a.risk_analysis}\n→ ${a.recommended_phrasing}</pre>`) +
    sec("Safety equipment", rep.safety_equipment_recommendations, e => `<pre>${e.equipment_name}: ${e.reason}</pre>`);
}
async function chat() {
  const r = await fetch("/api/v1/projects/chat", { method: "POST", headers: hdr(),
    body: JSON.stringify({ project_id: pid(), user_question: $("q").value }) }).then(r => r.json());
  $("chat").innerHTML = `<pre>${r.answer_text}</pre>` +
    (r.reference_image_urls||[]).map(u => `<img src="${u}">`).join("");
}
