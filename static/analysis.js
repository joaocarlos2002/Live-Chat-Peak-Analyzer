const id = decodeURIComponent(location.pathname.split("/").pop());
const $ = (selector) => document.querySelector(selector);
let live;
function esc(value) { return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[c])); }
function duration(seconds) { const value = Math.max(0, Math.round(Number(seconds) || 0)); return `${String(Math.floor(value / 3600)).padStart(2, "0")}:${String(Math.floor(value % 3600 / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`; }
function render(data) {
  live = data; const analysis = data.analysis;
  $("#title").textContent = data.title; $("#subtitle").textContent = `${data.uploader || data.channel} · ${data.platform}`;
  if (data.video_available) { $("#player").src = `/media/${encodeURIComponent(data.id)}`; $("#video-empty").style.display = "none"; $("#video-note").textContent = "O gráfico usa o tempo relativo ao primeiro timestamp do chat."; } else { $("#player").style.display = "none"; $("#video-empty").style.display = "grid"; $("#video-note").textContent = "O vídeo desta live ainda não está disponível localmente."; }
  if (!analysis.timeline.length) { $("#chart").innerHTML = `<div class="analysis-empty"><div class="empty-icon">⌁</div><strong>O chat ainda não tem mensagens</strong><small>${esc((data.limitations || ["O replay do chat precisa ser coletado separadamente."])[0])}</small></div>`; $("#peaks").innerHTML = '<div class="analysis-empty compact"><strong>Nenhum pico disponível</strong><small>Os maiores momentos aparecerão quando o replay do chat for coletado.</small></div>'; $("#chart-note").textContent = "Aguardando chat"; return; }
  $("#chart-note").textContent = `${analysis.total_messages.toLocaleString("pt-BR")} mensagens`;
  drawChart(analysis);
  $("#peaks").innerHTML = analysis.peaks.slice(0, 5).map((peak) => `<button class="peak" data-offset="${peak.offset_seconds}"><b>P${peak.rank}</b><span><strong>${duration(peak.offset_seconds)}</strong><small>${duration(peak.offset_seconds + analysis.window_seconds)}</small></span><strong>${peak.count.toLocaleString("pt-BR")} mensagens</strong><em>${peak.relative_intensity}x da média</em></button>`).join("");
  document.querySelectorAll(".peak").forEach((button) => button.addEventListener("click", () => seek(Number(button.dataset.offset))));
}
function drawChart(analysis) {
  const values = analysis.timeline.map((point) => point.count);
  const max = Math.max(...values, 1);
  const width = 900;
  const height = 280;
  const chartBottom = height - 35;
  const topOffsets = new Set(analysis.peaks.slice(0, 5).map((peak) => peak.offset_seconds));
  const step = width / Math.max(values.length, 1);
  const bars = analysis.timeline.map((point, index) => {
    const x = index * step;
    const barHeight = (point.count / max) * (chartBottom - 25);
    const isPeak = topOffsets.has(point.offset_seconds);
    const label = isPeak ? `<text class="peak-label" x="${x + step / 2}" y="${Math.max(16, chartBottom - barHeight - 9)}">${point.count}</text>` : "";
    return `<rect class="${isPeak ? "timeline-bar peak-bar" : "timeline-bar"}" x="${x + 1}" y="${chartBottom - barHeight}" width="${Math.max(step - 2, 2)}" height="${Math.max(barHeight, 1)}" data-offset="${point.offset_seconds}"><title>${duration(point.offset_seconds)} · ${point.count} mensagens</title></rect>${label}`;
  }).join("");
  const peakMarkers = analysis.peaks.slice(0, 5).map((peak, index) => {
    const position = (peak.offset_seconds / Math.max(analysis.timeline.at(-1).offset_seconds || analysis.window_seconds, analysis.window_seconds)) * width;
    return `<line class="peak-marker" x1="${position}" x2="${position}" y1="5" y2="${chartBottom}" /><text class="peak-rank" x="${Math.min(position + 4, width - 20)}" y="16">P${index + 1}</text>`;
  }).join("");
  $("#chart").innerHTML = `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="Timeline de fluxo de mensagens">${peakMarkers}${bars}</svg><div class="chart-axis"><span>00:00:00</span><span>${duration(analysis.timeline.at(-1).offset_seconds + analysis.window_seconds)}</span></div><div class="chart-legend"><span><i class="legend-normal"></i>Fluxo normal</span><span><i class="legend-peak"></i>Maior fluxo</span><span>Os 5 maiores picos estão marcados como P1–P5</span></div>`;
  document.querySelectorAll("#chart .timeline-bar").forEach((point) => point.addEventListener("click", () => seek(Number(point.dataset.offset))));
}
function seek(offset) { const player = $("#player"); if (player) { player.currentTime = offset; player.play().catch(() => {}); } }
async function load() { const response = await fetch(`/api/lives/${encodeURIComponent(id)}?window=${$("#window").value}`); if (!response.ok) { $("#title").textContent = "Live não encontrada"; return; } render(await response.json()); }
$("#retry-chat").addEventListener("click", async () => {
  const button = $("#retry-chat");
  button.disabled = true;
  button.textContent = "Coletando chat...";
  const response = await fetch(`/api/lives/${encodeURIComponent(id)}/retry-chat`, { method: "POST" });
  const result = await response.json();
  if (!response.ok) {
    button.disabled = false;
    button.textContent = "↻ Tentar coletar chat";
    window.alert(result.error || "Não foi possível iniciar a coleta.");
    return;
  }
  const poll = async () => {
    const jobResponse = await fetch(`/api/jobs/${encodeURIComponent(result.job_id)}`);
    const job = await jobResponse.json();
    if (["queued", "running"].includes(job.status)) {
      button.textContent = `Coletando chat... ${job.progress || 0}%`;
      window.setTimeout(poll, 700);
      return;
    }
    button.disabled = false;
    button.textContent = "↻ Tentar coletar chat";
    await load();
    if (job.logs?.length && job.status !== "completed") window.alert(job.logs[0]);
  };
  poll();
});
$("#window").addEventListener("change", load); load();
