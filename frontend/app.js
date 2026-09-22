const $ = (id) => document.getElementById(id);
let jobId = null;
let timer = null;

const drop = $("drop"), fileInput = $("file"), go = $("go");

drop.addEventListener("click", () => fileInput.click());
drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("on"); });
drop.addEventListener("dragleave", () => drop.classList.remove("on"));
drop.addEventListener("drop", (e) => {
  e.preventDefault(); drop.classList.remove("on");
  if (e.dataTransfer.files.length) upload(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", () => fileInput.files.length && upload(fileInput.files[0]));

async function upload(file) {
  drop.querySelector("b").textContent = "Subiendo " + file.name + "…";
  const fd = new FormData();
  fd.append("file", file);
  try {
    const r = await fetch("/api/upload", { method: "POST", body: fd });
    if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
    const data = await r.json();
    jobId = data.job_id;
    drop.querySelector("b").textContent = "✓ " + file.name;
    go.disabled = false;
  } catch (err) {
    drop.querySelector("b").textContent = "✗ Error al subir";
    setStep("Error: " + err.message, true);
  }
}

go.addEventListener("click", async () => {
  if (!jobId) return;
  go.disabled = true;
  $("links").innerHTML = "";
  setStep("Enviando a procesar…");
  const body = {
    target: $("target").value.trim() || "es",
    whisper_model: $("whisper").value || null,
    translate_model: $("tmodel").value.trim() || null,
    remove_burned: $("burned").value,
    strip_soft: $("strip").checked,
    force: $("force").checked,
  };
  const r = await fetch("/api/process/" + jobId, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) { setStep("Error: " + (await r.json()).detail, true); go.disabled = false; return; }
  poll();
});

function poll() {
  clearInterval(timer);
  timer = setInterval(async () => {
    const r = await fetch("/api/jobs/" + jobId);
    const job = await r.json();
    $("bar").style.width = Math.round((job.progress || 0) * 100) + "%";
    setStep(job.step || job.status);
    if (job.status === "done" || job.status === "error") {
      clearInterval(timer);
      go.disabled = false;
      render(job);
    }
  }, 1200);
}

function setStep(text, isError) {
  const el = $("step");
  el.textContent = text || "";
  el.style.color = isError ? "var(--err)" : "var(--muted)";
}

function render(job) {
  const card = $("reportCard");
  card.style.display = "block";
  const pill = $("status");
  pill.className = "pill " + (job.status === "done" ? "ok" : "err");
  pill.textContent = job.status === "done" ? "completado" : "error";
  $("report").textContent = JSON.stringify(job.report || { error: job.error }, null, 2);

  const links = $("links");
  links.innerHTML = "";
  if (job.status === "done" && job.report) {
    if (job.report.final) links.innerHTML += `<a href="/api/download/${jobId}/final">⬇ Vídeo con subtítulo</a>`;
    if (job.report.srt) links.innerHTML += `<a href="/api/download/${jobId}/srt">⬇ .srt castellano</a>`;
    const bi = job.report.burned_in || {};
    if (bi.method) setStep((job.report.message || "") + " · detección: " + bi.method + " (" + Math.round((bi.confidence || 0) * 100) + "%)");
  }
}
