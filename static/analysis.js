const id = decodeURIComponent(location.pathname.split("/").pop());
const $ = (selector) => document.querySelector(selector);
let live;
let markers = [];
function esc(value) { return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[c])); }
function duration(seconds) { const value = Math.max(0, Math.round(Number(seconds) || 0)); return `${String(Math.floor(value / 3600)).padStart(2, "0")}:${String(Math.floor(value % 3600 / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`; }
function render(data) {
  live = data; const analysis = data.analysis;
  $("#title").textContent = data.title; $("#subtitle").textContent = `${data.uploader || data.channel} · ${data.platform}`;
  if (data.video_available) {
    const player = $("#player");
    player.style.display = "block";
    player.src = `/media/${encodeURIComponent(data.id)}`;
    player.load();
    $("#video-empty").style.display = "none";
    $("#video-note").textContent = "O gráfico usa o tempo relativo ao primeiro timestamp do chat.";
  } else {
    $("#player").style.display = "none";
    $("#video-empty").style.display = "grid";
    $("#video-note").textContent = "O vídeo desta live ainda não está disponível localmente.";
  }
  const timelinePeaks = $("#timeline-peaks");
  if (timelinePeaks) timelinePeaks.innerHTML = analysis.peaks.slice(0, 5).map((peak, index) => `<button class="chat-peak-marker peak-${index + 1}" style="left:${peak.offset_seconds / Math.max(analysis.timeline.at(-1)?.offset_seconds + analysis.window_seconds || 1, 1) * 100}%" data-offset="${peak.offset_seconds}" title="P${index + 1} · ${peak.count} mensagens">${index + 1}</button>`).join("");
  if (!analysis.timeline.length) { $("#chart").innerHTML = `<div class="analysis-empty"><div class="empty-icon">⌁</div><strong>O chat ainda não tem mensagens</strong><small>${esc((data.limitations || ["O replay do chat precisa ser coletado separadamente."])[0])}</small></div>`; $("#peaks").innerHTML = '<div class="analysis-empty compact"><strong>Nenhum pico disponível</strong><small>Os maiores momentos aparecerão quando o replay do chat for coletado.</small></div>'; $("#chart-note").textContent = "Aguardando chat"; return; }
  $("#chart-note").textContent = `${analysis.total_messages.toLocaleString("pt-BR")} mensagens`;
  drawChart(analysis);
  $("#peaks").innerHTML = analysis.peaks.slice(0, 5).map((peak) => `<button class="peak" data-offset="${peak.offset_seconds}"><b>P${peak.rank}</b><span><strong>${duration(peak.offset_seconds)}</strong><small>${duration(peak.offset_seconds + analysis.window_seconds)}</small></span><strong>${peak.count.toLocaleString("pt-BR")} mensagens</strong><em>${peak.relative_intensity}x da média</em></button>`).join("");
  document.querySelectorAll(".peak").forEach((button) => button.addEventListener("click", () => seek(Number(button.dataset.offset))));
  document.querySelectorAll(".chat-peak-marker").forEach((button) => button.addEventListener("click", (event) => { event.stopPropagation(); seek(Number(button.dataset.offset)); }));
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
function setClipValue(selector) {
  const player = $("#player");
  if (player && Number.isFinite(player.currentTime)) {
    $(selector).value = player.currentTime.toFixed(1);
    updateVideoTimeline();
  }
}
function videoDuration() {
  const player = $("#player");
  return player && Number.isFinite(player.duration) ? player.duration : 0;
}
function renderEditorTexture() {
  const filmstrip = $("#video-filmstrip");
  const waveform = $("#audio-waveform");
  if (filmstrip && !filmstrip.children.length) {
    filmstrip.innerHTML = Array.from({ length: 32 }, (_, index) => `<span style="--i:${index}"></span>`).join("");
  }
  if (waveform && !waveform.children.length) {
    const bars = Array.from({ length: 180 }, (_, index) => {
      const value = 16 + Math.abs(Math.sin(index * 1.7) * 24) + ((index * 13) % 17);
      return `<i style="height:${Math.min(94, value)}%"></i>`;
    }).join("");
    waveform.innerHTML = bars;
  }
}
async function renderVideoThumbnails() {
  const filmstrip = $("#video-filmstrip");
  const player = $("#player");
  if (!filmstrip || !player || !player.currentSrc || !videoDuration()) return;
  const canvas = document.createElement("canvas");
  canvas.width = 180;
  canvas.height = 58;
  const context = canvas.getContext("2d");
  const source = document.createElement("video");
  source.src = player.currentSrc;
  source.muted = true;
  source.preload = "auto";
  await new Promise((resolve) => {
    source.addEventListener("loadedmetadata", resolve, { once: true });
    source.addEventListener("error", resolve, { once: true });
  });
  if (!source.duration || !context) return;
  const frames = 32;
  const images = [];
  for (let index = 0; index < frames; index += 1) {
    source.currentTime = source.duration * index / frames;
    await new Promise((resolve) => source.addEventListener("seeked", resolve, { once: true }));
    context.drawImage(source, 0, 0, canvas.width, canvas.height);
    images.push(canvas.toDataURL("image/jpeg", .55));
  }
  filmstrip.innerHTML = images.map((image) => `<span style="background-image:url('${image}')"></span>`).join("");
}
function renderRuler() {
  const ruler = $("#timeline-ruler");
  const total = videoDuration();
  if (!ruler || !total) return;
  const count = Math.min(12, Math.max(4, Math.ceil(total / 600)));
  ruler.innerHTML = Array.from({ length: count + 1 }, (_, index) => {
    const time = total * index / count;
    return `<span style="left:${index / count * 100}%"><i></i>${duration(time)}</span>`;
  }).join("");
}
function seekFromTimeline(event) {
  const timeline = $("#video-timeline");
  const durationValue = videoDuration();
  if (!timeline || !durationValue) return;
  const rect = timeline.getBoundingClientRect();
  const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
  seek(ratio * durationValue);
}
function renderMarkers() {
  const durationValue = videoDuration();
  const markerLayer = $("#timeline-markers");
  const list = $("#marker-list");
  if (!markerLayer || !list || !durationValue) return;
  markerLayer.innerHTML = markers.map((marker, index) => `<button class="video-marker" style="left:${marker.time / durationValue * 100}%" data-index="${index}" title="Marcação ${index + 1}: ${duration(marker.time)}"><span>${index + 1}</span></button>`).join("");
  list.innerHTML = markers.length ? markers.map((marker, index) => `<button class="marker-item" data-index="${index}"><b>M${index + 1}</b><span>${duration(marker.time)}</span><small>${index === 0 ? "início" : index === 1 ? "fim" : "marcação"}</small></button>`).join("") : '<span class="muted">Nenhuma marcação criada.</span>';
  markerLayer.querySelectorAll(".video-marker").forEach((element) => element.addEventListener("click", (event) => {
    event.stopPropagation();
    seek(markers[Number(element.dataset.index)].time);
  }));
  list.querySelectorAll(".marker-item").forEach((element) => element.addEventListener("click", () => seek(markers[Number(element.dataset.index)].time)));
}
function updateVideoTimeline() {
  const player = $("#player");
  const durationValue = videoDuration();
  if (!player || !durationValue) return;
  $("#timeline-progress").style.width = `${player.currentTime / durationValue * 100}%`;
  $("#timeline-playhead").style.left = `${player.currentTime / durationValue * 100}%`;
  $("#current-time").textContent = `${duration(player.currentTime)} / ${duration(durationValue)}`;
  const start = Number($("#clip-start").value) || 0;
  const end = Number($("#clip-end").value) || 0;
  const safeStart = Math.max(0, Math.min(start, durationValue));
  const safeEnd = Math.max(safeStart, Math.min(end, durationValue));
  $("#timeline-selection").style.left = `${safeStart / durationValue * 100}%`;
  $("#timeline-selection").style.width = `${Math.max(0, (safeEnd - safeStart) / durationValue * 100)}%`;
  $("#start-readout").textContent = duration(safeStart);
  $("#end-readout").textContent = duration(safeEnd);
  $("#selection-readout").textContent = duration(Math.max(0, safeEnd - safeStart));
  $("#clip-duration").textContent = `Duração: ${duration(Math.max(0, safeEnd - safeStart))}`;
  $("#toggle-play").textContent = player.paused ? "▶" : "Ⅱ";
}
function bindTrimHandle(selector, field, isStart) {
  const handle = $(selector);
  if (!handle) return;
  handle.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    handle.setPointerCapture(event.pointerId);
    event.stopPropagation();
    const move = (moveEvent) => {
      const timeline = $("#video-timeline");
      const durationValue = videoDuration();
      const rect = timeline.getBoundingClientRect();
      const seconds = Math.max(0, Math.min(durationValue, ((moveEvent.clientX - rect.left) / rect.width) * durationValue));
      const other = Number($(isStart ? "#clip-end" : "#clip-start").value) || 0;
      const value = isStart ? Math.min(seconds, Math.max(0, other - 0.1)) : Math.max(seconds, other + 0.1);
      $(field).value = value.toFixed(1);
      updateVideoTimeline();
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", (upEvent) => {
      upEvent.stopPropagation();
      handle.removeEventListener("pointermove", move);
    }, { once: true });
    handle.addEventListener("click", (clickEvent) => clickEvent.stopPropagation(), { once: true });
  });
}
function setupClip() {
  const player = $("#player");
  if (!player) return;
  player.addEventListener("loadedmetadata", () => {
    $("#clip-duration").textContent = `Duração: ${duration(player.duration)}`;
    $("#clip-end").value = Math.min(60, player.duration).toFixed(1);
    $("#clip-end").max = player.duration;
    renderRuler();
    renderEditorTexture();
    renderVideoThumbnails().catch(() => {});
  });
  player.addEventListener("error", () => {
    const code = player.error?.code;
    $("#video-note").textContent = code === 4
      ? "O navegador não conseguiu decodificar este arquivo de vídeo."
      : "Não foi possível carregar o vídeo local.";
    $("#video-empty").textContent = "Erro ao carregar o vídeo";
    $("#video-empty").style.display = "grid";
    renderMarkers();
    updateVideoTimeline();
  });
  player.addEventListener("timeupdate", updateVideoTimeline);
  player.addEventListener("play", updateVideoTimeline);
  player.addEventListener("pause", updateVideoTimeline);
  $("#toggle-play").addEventListener("click", () => player.paused ? player.play() : player.pause());
  $("#skip-back").addEventListener("click", () => seek(Math.max(0, player.currentTime - 5)));
  $("#skip-forward").addEventListener("click", () => seek(Math.min(videoDuration(), player.currentTime + 5)));
  $("#timeline-zoom").addEventListener("input", (event) => {
    const zoom = Number(event.target.value) || 1;
    $("#video-timeline").style.width = `${zoom * 100}%`;
    $("#timeline-ruler").style.width = `${zoom * 100}%`;
  });
  $("#video-timeline").addEventListener("click", seekFromTimeline);
  $("#add-marker").addEventListener("click", () => {
    const time = Number(player.currentTime.toFixed(1));
    if (markers.some((marker) => Math.abs(marker.time - time) < 0.2)) return;
    markers.push({ time });
    markers.sort((a, b) => a.time - b.time);
    if (markers.length === 1) $("#clip-start").value = time.toFixed(1);
    if (markers.length === 2) $("#clip-end").value = time.toFixed(1);
    renderMarkers();
    updateVideoTimeline();
  });
  $("#clear-markers").addEventListener("click", () => {
    markers = [];
    renderMarkers();
    updateVideoTimeline();
  });
  ["#clip-start", "#clip-end"].forEach((selector) => $(selector).addEventListener("input", updateVideoTimeline));
  bindTrimHandle("#start-handle", "#clip-start", true);
  bindTrimHandle("#end-handle", "#clip-end", false);
  $("#set-start").addEventListener("click", () => setClipValue("#clip-start"));
  $("#set-end").addEventListener("click", () => setClipValue("#clip-end"));
  $("#create-clip").addEventListener("click", async () => {
    const button = $("#create-clip");
    const start = Number($("#clip-start").value);
    const end = Number($("#clip-end").value);
    if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end <= start) {
      $("#clip-message").textContent = "Informe um início e um fim válidos.";
      return;
    }
    button.disabled = true;
    button.textContent = "Gerando trecho...";
    $("#clip-message").textContent = "O FFmpeg está recortando o vídeo...";
    try {
      const response = await fetch(`/api/lives/${encodeURIComponent(id)}/clip`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ start, end }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Não foi possível criar o trecho.");
      $("#clip-message").innerHTML = `${esc(result.message)} <a href="${result.download_url}" download>Baixar novamente</a>`;
      const link = document.createElement("a");
      link.href = result.download_url;
      link.download = result.filename;
      link.click();
    } catch (error) {
      $("#clip-message").textContent = error.message;
    } finally {
      button.disabled = false;
      button.textContent = "Criar e baixar trecho";
    }
  });
}
async function load() {
  try {
    const response = await fetch(`/api/lives/${encodeURIComponent(id)}?window=${$("#window").value}`);
    if (!response.ok) throw new Error(`Não foi possível carregar a análise (${response.status}).`);
    render(await response.json());
  } catch (error) {
    $("#title").textContent = "Não foi possível carregar a análise";
    $("#subtitle").textContent = error.message;
    $("#chart").innerHTML = `<div class="analysis-empty"><strong>Erro ao carregar os dados</strong><small>${esc(error.message)}</small></div>`;
  }
}
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
window.addEventListener("DOMContentLoaded", () => {
  $("#window").addEventListener("change", load);
  setupClip();
  load();
});
