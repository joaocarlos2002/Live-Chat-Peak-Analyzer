import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const api = async (path, options) => {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Não foi possível concluir a operação.");
  return data;
};

function Layout({ children }) {
  return <main className="app"><header><a className="brand" href="/">LIVE<span>DROP</span></a><span className="local"><i /> servidor local</span></header>{children}</main>;
}

function Home() {
  const [url, setUrl] = useState("");
  const [lives, setLives] = useState([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    const items = await api("/api/lives");
    const enriched = await Promise.all(items.map(async (item) => {
      if (!item.job_id) return item;
      try {
        const job = await api(`/api/jobs/${encodeURIComponent(item.job_id)}`);
        return { ...item, progress: job.progress || 0, jobStatus: job.status, jobError: job.error };
      } catch {
        return item;
      }
    }));
    setLives(enriched);
    if (enriched.some((item) => ["queued", "running", "cancelling"].includes(item.jobStatus || item.status))) setTimeout(load, 900);
  }
  useEffect(() => { load().catch((error) => setMessage(error.message)); }, []);

  async function submit(event) {
    event.preventDefault();
    setLoading(true); setMessage("Preparando download...");
    try {
      await api("/api/lives", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }) });
      setUrl(""); setMessage("Download iniciado. Você pode acompanhar o progresso abaixo."); await load();
    } catch (error) { setMessage(error.message); } finally { setLoading(false); }
  }
  async function clear() {
    if (!confirm("Apagar vídeos, chats e relatórios locais?")) return;
    try { await api("/api/reset", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirm: true }) }); setLives([]); setMessage("Dados apagados."); }
    catch (error) { setMessage(error.message); }
  }
  async function removeLive(live) {
    if (!confirm(`Apagar "${live.title || live.url}" e todos os arquivos desta live?`)) return;
    try { await api(`/api/lives/${encodeURIComponent(live.id)}`, { method: "DELETE" }); setMessage("Live apagada."); await load(); }
    catch (error) { setMessage(error.message); }
  }
  return <Layout>
    <section className="intro"><div><p className="eyebrow">BAIXADOR DE LIVES</p><h1>Baixe a gravação.<br /><em>Encontre os picos.</em></h1><p className="muted">Cole o link de uma live pública e deixe o yt-dlp fazer o trabalho.</p></div><div className="orb">↓</div></section>
    <section className="panel form-panel"><form onSubmit={submit}><input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://youtube.com/watch?v=..." required /><button disabled={loading}>{loading ? "Iniciando..." : "Baixar live"}</button></form>{message && <p className="feedback">{message}</p>}<small>O vídeo é salvo localmente em <code>.data/videos</code>.</small></section>
    <section className="section-heading"><div><p className="eyebrow">BIBLIOTECA</p><h2>Suas lives</h2></div><button className="quiet" onClick={() => load()}>Atualizar</button><button className="quiet danger" onClick={clear}>Apagar tudo</button></section>
    <div className="library">{lives.length ? lives.map((live) => <LiveCard key={live.id} live={live} onDelete={removeLive} />) : <div className="empty">Nenhuma live baixada ainda.</div>}</div>
  </Layout>;
}

function LiveCard({ live, onDelete }) {
  const active = ["queued", "running", "cancelling"].includes(live.jobStatus || live.status);
  const progress = Math.max(0, Math.min(100, Number(live.progress) || 0));
  const status = live.video_available ? "Vídeo disponível" : active ? (live.jobStatus === "queued" ? "Na fila" : `Baixando · ${progress}%`) : "Download com aviso";
  return <article className="live-card">{live.thumbnail ? <img src={live.thumbnail} alt="" /> : <div className="thumb">▶</div>}<div className="live-content"><span className="tag">{live.platform}</span><h3>{live.title || live.url}</h3><p className="muted">{live.channel} · {(live.message_count || 0).toLocaleString("pt-BR")} mensagens</p>{(active || live.video_available) && <div className="progress-wrap"><div className="progress-label"><span>{active ? "Progresso do download" : "Download concluído"}</span><strong>{active ? `${progress}%` : "100%"}</strong></div><div className="progress"><span style={{ width: `${active ? progress : 100}%` }} /></div></div>}<span className={`state ${live.video_available ? "ok" : active ? "working" : "warning"}`}>{status}</span>{live.jobError && <small className="error-detail">{live.jobError}</small>}</div><div className="card-actions">{live.video_available && <a className="watch" href={`/live/${encodeURIComponent(live.id)}`}>Abrir análise →</a>}{!live.video_available && !active && <a className="watch" href={`/live/${encodeURIComponent(live.id)}`}>Tentar novamente →</a>}<button className="delete-button" onClick={() => onDelete(live)} aria-label={`Apagar ${live.title || "live"}`} title="Apagar esta live">🗑</button></div></article>;
}

function Analysis() {
  const id = decodeURIComponent(location.pathname.split("/").pop());
  const [live, setLive] = useState(null);
  const [message, setMessage] = useState("");
  const [clip, setClip] = useState({ start: 0, end: 60 });
  const [windowSize, setWindowSize] = useState(10);
  async function load() {
    const data = await api(`/api/lives/${encodeURIComponent(id)}?window=${windowSize}`);
    setLive(data);
    if (["queued", "running"].includes(data.status)) setTimeout(load, 900);
  }
  useEffect(() => { load().catch((error) => setMessage(error.message)); }, [windowSize]);
  async function retry(path) { try { setMessage("Operação iniciada..."); await api(`/api/lives/${id}/${path}`, { method: "POST" }); await load(); } catch (error) { setMessage(error.message); } }
  async function createClip() {
    try { const result = await api(`/api/lives/${id}/clip`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(clip) }); window.location.href = result.download_url; }
    catch (error) { setMessage(error.message); }
  }
  if (!live) return <Layout><div className="empty">Carregando live...</div></Layout>;
  const analysis = live.analysis || { timeline: [], peaks: [], total_messages: 0 };
  const max = Math.max(...analysis.timeline.map((point) => point.count), 1);
  function seek(offset) { const player = document.querySelector(".player"); if (player) player.currentTime = offset; }
  return <Layout><a className="back" href="/">← biblioteca</a><section className="analysis-head"><div><p className="eyebrow">{live.platform} / {live.channel}</p><h1>{live.title}</h1><p className="muted">{live.video_available ? "Vídeo pronto para assistir e recortar." : "O vídeo ainda não está disponível."}</p>{live.tags?.length > 0 && <div className="video-tags" aria-label="Tags do vídeo">{live.tags.map((tag) => <span key={tag}>#{tag}</span>)}</div>}</div><div className="head-actions">{!live.video_available && <button onClick={() => retry("retry-video")}>↓ baixar vídeo</button>}<button className="quiet" onClick={() => retry("retry-chat")}>↻ coletar chat</button></div></section>
    {live.video_available ? <video className="player" controls src={`/media/${encodeURIComponent(id)}`} /> : <div className="video-missing">O download ainda não terminou.<br /><button onClick={() => retry("retry-video")}>Tentar download novamente</button></div>}
    {message && <p className="feedback">{message}</p>}<section className="panel chart-panel"><div className="section-heading"><div><p className="eyebrow">ATIVIDADE DO CHAT</p><h2>{analysis.total_messages.toLocaleString("pt-BR")} mensagens</h2></div><select value={windowSize} onChange={(event) => setWindowSize(event.target.value)}><option value="5">5 segundos</option><option value="10">10 segundos</option><option value="30">30 segundos</option><option value="60">1 minuto</option></select></div><div className="bars">{analysis.timeline.map((point) => <button key={point.offset_seconds} title={`${point.count} mensagens`} onClick={() => seek(point.offset_seconds)} style={{ height: `${Math.max(3, point.count / max * 100)}%` }} />)}</div>{!analysis.timeline.length && <div className="empty">Nenhum replay de chat disponível.</div>}</section>
    <section className="panel clip-panel"><div><p className="eyebrow">RECORTE</p><h2>Baixar um trecho</h2></div><label>início<input type="number" min="0" step="0.1" value={clip.start} onChange={(event) => setClip({ ...clip, start: event.target.value })} /></label><label>fim<input type="number" min="0" step="0.1" value={clip.end} onChange={(event) => setClip({ ...clip, end: event.target.value })} /></label><button onClick={createClip} disabled={!live.video_available}>Criar MP4</button></section>
  </Layout>;
}

createRoot(document.getElementById("root")).render(<StrictMode>{location.pathname.startsWith("/live/") ? <Analysis /> : <Home />}</StrictMode>);
