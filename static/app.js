const $ = (selector) => document.querySelector(selector);

function render(lives) {
  const totalMessages = lives.reduce((sum, live) => sum + (live.message_count || 0), 0);
  const channels = new Set(lives.map((live) => live.channel)).size;
  $("#stats").innerHTML = [
    ["Lives processadas", lives.length],
    ["Mensagens analisadas", totalMessages],
    ["Canais", channels],
  ].map(([label, value]) => `<div class="stat"><span class="muted">${label}</span><strong>${value}</strong></div>`).join("");
  $("#lives").innerHTML = lives.length ? lives.map((live) => `
    <article class="live">
      <a class="live-cover" href="${escapeHtml(live.url)}" target="_blank" rel="noreferrer">
        ${live.thumbnail ? `<img src="${escapeHtml(live.thumbnail)}" alt="Thumbnail de ${escapeHtml(live.title)}">` : `<span class="cover-fallback">${escapeHtml((live.platform || "LIVE").slice(0, 1).toUpperCase())}</span>`}
      </a>
      <div class="live-info"><a class="live-title link" title="${escapeHtml(live.title)}" href="/live/${encodeURIComponent(live.id)}">${escapeHtml(live.title)}</a><span class="muted">${escapeHtml(platformLabel(live.platform))} · ${escapeHtml(live.channel)}</span>${live.limitations?.length ? `<span class="warning" title="${escapeHtml(live.limitations[0])}">${escapeHtml(live.limitations[0])}</span>` : ""}</div>
      ${live.video_available ? `<a class="watch" href="/media/${encodeURIComponent(live.id)}" target="_blank">Abrir vídeo</a>` : ""}
      ${isProcessing(live) ? `
        <div class="progress-area">
          <div class="progress-label"><span>${escapeHtml(statusLabel(live))}</span><strong>${live.progress || 0}%</strong></div>
          <div class="progress-track"><div class="progress-value" style="width:${live.progress || 0}%"></div></div>
        </div>` : `<span class="pill">${escapeHtml(statusLabel(live))}</span>`}
    </article>`).join("") : '<div class="empty">Nenhuma live cadastrada ainda.</div>';
}

function isProcessing(live) {
  return ["queued", "running", "cancelling"].includes(live.jobStatus || live.status);
}

function statusLabel(live) {
  return ({ queued: "Na fila", running: "Baixando gravação", cancelling: "Cancelando" }[live.jobStatus || live.status] || live.status);
}

function platformLabel(platform) {
  return ({ youtube: "YouTube", twitch: "Twitch", kick: "Kick" }[platform] || platform);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));
}

async function load() {
  const response = await fetch("/api/lives");
  const lives = await response.json();
  const enriched = await Promise.all(lives.map(async (live) => {
    if (!live.job_id) return live;
    const jobResponse = await fetch(`/api/jobs/${live.job_id}`);
    if (!jobResponse.ok) return live;
    const job = await jobResponse.json();
    return { ...live, progress: job.progress, jobStatus: job.status };
  }));
  render(enriched);
  if (enriched.some(isProcessing)) {
    window.setTimeout(load, 700);
  }
}

$("#live-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("#message").textContent = "Validando e preparando o processamento...";
  const response = await fetch("/api/lives", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: $("#url").value }),
  });
  const result = await response.json();
  $("#message").textContent = response.ok ? (result.message || "Live cadastrada. Verifique as limitações informadas no processamento.") : result.error;
  if (response.ok) { $("#url").value = ""; load(); }
});

$("#refresh").addEventListener("click", load);
$("#clear-all").addEventListener("click", async () => {
  if (!window.confirm("Isso apagará todas as lives, vídeos, chats e relatórios da pasta .data. Continuar?")) return;
  const response = await fetch("/api/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirm: true }),
  });
  const result = await response.json();
  $("#message").textContent = response.ok ? result.message : (result.error || "Não foi possível apagar os dados.");
  if (response.ok) load();
});
load();
