from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from analyzer import analyze, read_messages
from platforms import detect_platform, extract_channel, platform_catalog
from storage import DATA_DIR, clear_data, create_live_metadata, delete_live_data, ensure_data_dirs, list_metadata, load_metadata, now_iso, save_metadata


PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC = PROJECT_ROOT / "frontend" / "dist"
JOBS: dict[str, dict] = {}
LOCK = threading.Lock()


def configure_logging() -> logging.Logger:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("live-drop")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        DATA_DIR / "backend.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False
    return logger


LOGGER = configure_logging()


def command_for_log(command: list[str]) -> str:
    """Return a command without exposing cookie file paths or cookie values."""
    hidden_next = {"--cookies", "--cookies-from-browser"}
    rendered = []
    skip_next = False
    for item in command:
        if skip_next:
            rendered.append("<redacted>")
            skip_next = False
        elif item in hidden_next:
            rendered.append(item)
            skip_next = True
        else:
            rendered.append(item)
    return " ".join(rendered)


def json_response(handler: BaseHTTPRequestHandler, payload: object, status: int = 200) -> None:
    LOGGER.debug("Resposta HTTP %s %s status=%s", handler.command, handler.path, status)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def downloader_command() -> list[str] | None:
    executable = shutil.which("yt-dlp")
    if executable:
        LOGGER.info("yt-dlp encontrado no PATH: %s", executable)
        return [executable]
    probe = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--version"],
        capture_output=True,
        text=True,
    )
    if probe.returncode == 0:
        LOGGER.info("yt-dlp encontrado como módulo Python")
        return [sys.executable, "-m", "yt_dlp"]
    LOGGER.error("yt-dlp não encontrado. stderr=%s", probe.stderr.strip()[-500:])
    return None


def youtube_cookie_variants(url: str) -> list[list[str]]:
    if "youtube.com" not in url and "youtu.be" not in url:
        return [[]]
    local_app_data = Path.home() / "AppData" / "Local"
    roaming = Path.home() / "AppData" / "Roaming"
    browsers = [
        ("edge", local_app_data / "Microsoft" / "Edge" / "User Data"),
        ("chrome", local_app_data / "Google" / "Chrome" / "User Data"),
        ("firefox", roaming / "Mozilla" / "Firefox" / "Profiles"),
    ]
    cookie_files = [
        Path.home() / "Downloads" / "cookies.txt",
    ]
    return [[]] + [
        ["--cookies", str(cookie_file)]
        for cookie_file in cookie_files
        if cookie_file.is_file()
    ] + [
        ["--cookies-from-browser", browser]
        for browser, profile_root in browsers
        if profile_root.exists()
    ]


def run_ytdlp_download(command: list[str], url: str, options: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    variants = youtube_cookie_variants(url)
    results = []
    LOGGER.info("Iniciando yt-dlp url=%s tentativas=%d timeout=%ss", url, len(variants), timeout)
    for index, cookies in enumerate(variants, start=1):
        full_command = [*command, *cookies, *options, url]
        LOGGER.debug("yt-dlp tentativa %d/%d comando=%s", index, len(variants), command_for_log(full_command))
        try:
            cookie_result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            LOGGER.exception("yt-dlp excedeu timeout na tentativa %d url=%s", index, url)
            raise
        results.append((cookie_result, cookies))
        LOGGER.info(
            "yt-dlp terminou tentativa=%d retorno=%d stdout=%s stderr=%s",
            index,
            cookie_result.returncode,
            cookie_result.stdout.strip()[-500:],
            cookie_result.stderr.strip()[-1000:],
        )
        if cookie_result.returncode == 0:
            LOGGER.info("Download yt-dlp concluído url=%s", url)
            return cookie_result
        combined = f"{cookie_result.stdout}\n{cookie_result.stderr}".lower()
        if (
            "sign in to confirm" not in combined
            and "not a bot" not in combined
            and "the page needs to be reloaded" not in combined
        ):
            return cookie_result
    cookie_file_attempts = [
        attempt for attempt, variant in results
        if "--cookies" in variant
    ]
    result = cookie_file_attempts[0] if cookie_file_attempts else results[-1][0]
    LOGGER.error("Todas as tentativas yt-dlp falharam url=%s erro=%s", url, download_error(result))
    return result


def download_error(result: subprocess.CompletedProcess[str]) -> str:
    output = (result.stderr or result.stdout or "yt-dlp não conseguiu acessar a gravação.").strip()
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if any("could not copy chrome cookie database" in line.lower() for line in lines):
        return (
            "O navegador ainda está mantendo o banco de cookies bloqueado. "
            "Feche completamente o Edge/Chrome ou use o arquivo "
            "www.youtube.com_cookies.txt exportado do navegador."
        )
    if any("sign in to confirm" in line.lower() or "not a bot" in line.lower() for line in lines):
        return (
            "O yt-dlp não conseguiu validar a sessão do YouTube. O arquivo de cookies foi "
            "tentado, mas pode estar expirado, incompleto ou ter sido exportado antes do login. "
            "Exporte novamente os cookies enquanto a gravação estiver aberta e tente o trecho."
        )
    for line in reversed(lines):
        if line.startswith(("ERROR:", "WARNING:")):
            return line
    return output[-1000:]


def update_job(job_id: str, progress: int, status: str | None = None, **values: object) -> None:
    with LOCK:
        job = JOBS.setdefault(job_id, {"id": job_id})
        job["progress"] = progress
        if status:
            job["status"] = status
        job.update(values)


def read_platform_metadata(url: str, command: list[str] | None) -> dict:
    if command:
        metadata_command = [*command, "--dump-single-json", "--skip-download", "--no-playlist", url]
        LOGGER.info("Buscando metadados url=%s comando=%s", url, command_for_log(metadata_command))
        result = subprocess.run(
            metadata_command,
            capture_output=True,
            text=True,
            timeout=120,
        )
        LOGGER.debug("Metadados retorno=%d stderr=%s", result.returncode, result.stderr.strip()[-1000:])
        if result.returncode == 0:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                LOGGER.exception("yt-dlp retornou JSON inválido ao buscar metadados url=%s", url)
    if "youtube.com" in url or "youtu.be" in url:
        LOGGER.info("Tentando fallback oEmbed url=%s", url)
        request = Request(f"https://www.youtube.com/oembed?url={url}&format=json", headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    return {}


def collect_youtube_chat(live: dict, command: list[str], has_node: bool) -> tuple[int, str]:
    chat_dir = DATA_DIR / "raw" / "chats"
    chat_dir.mkdir(parents=True, exist_ok=True)
    temporary_dir = DATA_DIR / "raw" / ".chat-download"
    temporary_dir.mkdir(parents=True, exist_ok=True)
    base = temporary_dir / live["id"]
    chat_command = [
        *command,
        "--no-playlist",
        "--skip-download",
        "--write-subs",
        "--sub-langs", "live_chat",
        "--sub-format", "json",
        "--output", str(base),
        live["url"],
    ]
    if has_node:
        chat_command.extend(["--js-runtimes", "node"])
    LOGGER.info("Iniciando coleta de chat live_id=%s node=%s comando=%s", live["id"], has_node, command_for_log(chat_command))
    try:
        result = subprocess.run(chat_command, capture_output=True, text=True, timeout=3600)
    except subprocess.TimeoutExpired:
        LOGGER.exception("Coleta de chat excedeu timeout live_id=%s", live["id"])
        raise
    LOGGER.info(
        "Coleta de chat terminou live_id=%s retorno=%d stdout=%s stderr=%s",
        live["id"], result.returncode, result.stdout.strip()[-500:], result.stderr.strip()[-1000:],
    )
    subtitle_files = [
        *temporary_dir.glob(f"{live['id']}*.live_chat.json"),
        *temporary_dir.glob(f"{live['id']}*.live_chat.json3"),
    ]
    if result.returncode != 0 or not subtitle_files:
        detail = (result.stderr or result.stdout or "O replay do chat não foi disponibilizado pela plataforma.")[-1000:].strip()
        LOGGER.error("Falha na coleta de chat live_id=%s detalhe=%s", live["id"], detail)
        return 0, detail

    try:
        source = subtitle_files[0]
        raw_events = []
        with source.open(encoding="utf-8") as chat_file:
            for line in chat_file:
                if not line.strip():
                    continue
                try:
                    raw_events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        if len(raw_events) == 1 and isinstance(raw_events[0], dict):
            payload = raw_events[0]
            raw_events = payload.get("events", []) if "events" in payload else [payload]

        messages = []
        for event in raw_events:
            actions = event.get("replayChatItemAction", {}).get("actions", [])
            for action in actions:
                item = action.get("addChatItemAction", {}).get("item", {})
                renderer = next(
                    (
                        value for key, value in item.items()
                        if key in {"liveChatTextMessageRenderer", "liveChatPaidMessageRenderer"}
                        and isinstance(value, dict)
                    ),
                    None,
                )
                if not renderer or "message" not in renderer:
                    continue
                runs = renderer.get("message", {}).get("runs", [])
                text = "".join(run.get("text", "") for run in runs if isinstance(run, dict)).strip()
                timestamp = renderer.get("timestampUsec")
                if not text or not timestamp:
                    continue
                messages.append({
                    "absolute_timestamp": int(timestamp) / 1_000_000,
                    "message": text,
                    "user_id": renderer.get("authorExternalChannelId"),
                    "username": renderer.get("authorName", {}).get("simpleText"),
                })

        if not messages:
            LOGGER.warning("Replay de chat sem mensagens reconhecíveis live_id=%s", live["id"])
            return 0, "O arquivo de replay foi baixado, mas não continha mensagens de texto reconhecíveis."
        first_timestamp = messages[0]["absolute_timestamp"]
        target = chat_dir / f"{live['id']}.jsonl"
        with target.open("w", encoding="utf-8") as output:
            for message in messages:
                output.write(json.dumps({
                    "timestamp": round(message["absolute_timestamp"] - first_timestamp, 3),
                    "message": message["message"],
                    "user_id": message["user_id"],
                    "username": message["username"],
                }, ensure_ascii=False) + "\n")
        LOGGER.info("Chat processado live_id=%s mensagens=%d arquivo=%s", live["id"], len(messages), target)
        return len(messages), ""
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        LOGGER.exception("Falha ao interpretar replay de chat live_id=%s", live["id"])
        return 0, f"Não foi possível interpretar o replay do chat: {error}"


def retry_chat(live: dict) -> None:
    job_id = live["job_id"]
    LOGGER.info("Retry de chat iniciado live_id=%s job_id=%s", live["id"], job_id)
    update_job(job_id, 5, "running", live_id=live["id"], logs=["Tentando coletar o replay do chat..."])
    try:
        command = downloader_command()
        if not command:
            raise RuntimeError("yt-dlp não está instalado. Instale com: python -m pip install -U yt-dlp")
        if live["platform"] != "youtube":
            raise RuntimeError("A coleta automática de replay ainda está disponível somente para YouTube.")
        count, error = collect_youtube_chat(live, command, shutil.which("node") is not None)
        live["chat_available"] = count > 0
        live["message_count"] = count
        live["updated_at"] = now_iso()
        if count:
            live["limitations"] = [item for item in live.get("limitations", []) if not item.startswith("Chat:")]
            live["status"] = "completed"
            status = "completed"
            logs = [f"{count} mensagens coletadas."]
        else:
            message = f"Chat: {error or 'nenhuma mensagem foi encontrada.'}"
            live["limitations"] = [message]
            live["status"] = "completed_with_warnings"
            status = "completed_with_warnings"
            logs = [message]
        save_metadata(live)
        update_job(job_id, 100, status, logs=logs)
        LOGGER.info("Retry de chat finalizado live_id=%s status=%s mensagens=%d", live["id"], status, count)
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        LOGGER.exception("Retry de chat falhou live_id=%s job_id=%s", live["id"], job_id)
        live["chat_available"] = False
        live["updated_at"] = now_iso()
        live["limitations"] = [f"Chat: {error}"]
        save_metadata(live)
        update_job(job_id, 100, "failed", logs=live["limitations"], error=str(error))


def create_clip(live: dict, start: float, end: float) -> Path:
    LOGGER.info("Criando recorte live_id=%s inicio=%.3f fim=%.3f", live["id"], start, end)
    if shutil.which("ffmpeg") is None:
        LOGGER.error("FFmpeg não encontrado ao criar recorte live_id=%s", live["id"])
        raise RuntimeError("FFmpeg não está instalado ou não está disponível no PATH.")
    video = Path(live.get("video_path", "")).resolve()
    video_root = (DATA_DIR / "videos").resolve()
    duration = end - start
    clip_dir = DATA_DIR / "reports" / live["id"] / "clips"
    clip_dir.mkdir(parents=True, exist_ok=True)
    target = clip_dir / f"{live['id']}-{int(start)}-{int(end)}.mp4"
    if video_root not in video.parents or not video.is_file():
        command = downloader_command()
        if not command:
            raise RuntimeError("yt-dlp não está instalado. Instale com: python -m pip install -U yt-dlp")
        section = f"*{start:.3f}-{end:.3f}"
        download_options = [
            "--no-playlist", "--download-sections", section,
            "--force-keyframes-at-cuts", "--merge-output-format", "mp4",
            "--output", str(target),
        ]
        if shutil.which("node"):
            download_options.extend(["--js-runtimes", "node"])
        result = run_ytdlp_download(command, live["url"], download_options, 3600)
        if result.returncode != 0 or not target.exists() or target.stat().st_size == 0:
            detail = download_error(result)
            LOGGER.error("Falha ao baixar recorte live_id=%s detalhe=%s", live["id"], detail)
            raise RuntimeError(detail)
        LOGGER.info("Recorte baixado live_id=%s arquivo=%s tamanho=%d", live["id"], target, target.stat().st_size)
        return target
    command = [
        "ffmpeg", "-y", "-ss", str(start), "-i", str(video),
        "-t", str(duration), "-map", "0", "-c", "copy",
        "-avoid_negative_ts", "make_zero", str(target),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=1800)
    LOGGER.debug("FFmpeg copy retorno=%d stderr=%s", result.returncode, result.stderr.strip()[-1000:])
    if result.returncode != 0 or not target.exists() or target.stat().st_size == 0:
        fallback = [
            "ffmpeg", "-y", "-ss", str(start), "-i", str(video),
            "-t", str(duration), "-c:v", "libx264", "-c:a", "aac",
            "-movflags", "+faststart", str(target),
        ]
        result = subprocess.run(fallback, capture_output=True, text=True, timeout=1800)
        LOGGER.debug("FFmpeg fallback retorno=%d stderr=%s", result.returncode, result.stderr.strip()[-1000:])
    if result.returncode != 0 or not target.exists() or target.stat().st_size == 0:
        detail = (result.stderr or result.stdout or "FFmpeg não gerou o arquivo.")[-800:].strip()
        LOGGER.error("Falha ao gerar recorte local live_id=%s detalhe=%s", live["id"], detail)
        raise RuntimeError(detail)
    LOGGER.info("Recorte local criado live_id=%s arquivo=%s tamanho=%d", live["id"], target, target.stat().st_size)
    return target


def process_live(live: dict) -> None:
    job_id = live["job_id"]
    LOGGER.info("Processamento iniciado live_id=%s job_id=%s url=%s", live["id"], job_id, live["url"])
    try:
        update_job(job_id, 5, "running", live_id=live["id"], logs=[])
        time.sleep(0.05)
        with LOCK:
            if JOBS[job_id].get("cancel_requested"):
                live["status"] = "cancelled"
                live["updated_at"] = now_iso()
                JOBS[job_id].update({"status": "cancelled", "progress": 100})
                save_metadata(live)
                return
        platform = detect_platform(live["url"])
        downloader = downloader_command()
        LOGGER.info("Plataforma detectada live_id=%s plataforma=%s", live["id"], platform.key if platform else None)
        update_job(job_id, 15, "running")
        try:
            metadata = read_platform_metadata(live["url"], downloader)
            live["title"] = metadata.get("title") or metadata.get("author_name") or live["url"]
            live["thumbnail"] = metadata.get("thumbnail") or metadata.get("thumbnail_url")
            live["uploader"] = metadata.get("uploader") or metadata.get("author_name")
            live["duration_seconds"] = metadata.get("duration")
            live["tags"] = list(dict.fromkeys(
                tag.strip() for tag in (metadata.get("tags") or [])
                if isinstance(tag, str) and tag.strip()
            ))
            LOGGER.info("Metadados carregados live_id=%s tags=%d", live["id"], len(live["tags"]))
            save_metadata(live)
        except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as error:
            LOGGER.exception("Falha ao buscar metadados live_id=%s", live["id"])
            update_job(job_id, 20, "running", logs=[f"Metadados: {error}"])
        if not downloader:
            live["status"] = "completed_with_warnings"
            live["limitations"] = list(platform.limitations) if platform else ["Plataforma não suportada."]
            live["limitations"].append("yt-dlp não está instalado. Instale com: python -m pip install -U yt-dlp")
        else:
            has_node = shutil.which("node") is not None
            if live["platform"] == "youtube":
                update_job(job_id, 25, "running", logs=["Coletando replay do chat..."])
                chat_count, chat_error = collect_youtube_chat(live, downloader, has_node)
                live["chat_available"] = chat_count > 0
                live["message_count"] = chat_count
                if chat_count:
                    live["limitations"] = []
                elif chat_error:
                    live["limitations"] = [f"Chat: {chat_error}"]
            video_dir = DATA_DIR / "videos" / live["platform"] / live["channel"]
            video_dir.mkdir(parents=True, exist_ok=True)
            output = video_dir / f'{live["id"]}.%(ext)s'
            has_ffmpeg = shutil.which("ffmpeg") is not None
            download_options = [
                "--no-playlist",
                "--format", "bestvideo*+bestaudio/best" if has_ffmpeg else "best",
                "--output", str(output),
            ]
            if has_node:
                download_options.extend(["--js-runtimes", "node"])
            if has_ffmpeg:
                download_options.extend(["--merge-output-format", "mp4"])
            update_job(job_id, 35, "running")
            result = run_ytdlp_download(downloader, live["url"], download_options, 3600)
            if result.returncode != 0:
                live["status"] = "completed_with_warnings"
                error_detail = download_error(result)
                live["limitations"] = [f"Não foi possível baixar a gravação: {error_detail}"]
                update_job(job_id, 100, live["status"], logs=live["limitations"])
                LOGGER.error("Download de vídeo falhou live_id=%s detalhe=%s", live["id"], error_detail)
            else:
                video_files = list(video_dir.glob(f'{live["id"]}.*'))
                live["video_available"] = any(path.suffix.lower() in {".mp4", ".webm", ".mkv"} for path in video_files)
                live["status"] = "completed" if live["video_available"] else "completed_with_warnings"
                live["limitations"] = [] if live["video_available"] else ["O downloader terminou sem produzir um arquivo de vídeo."]
                live["video_path"] = str(next((path for path in video_files if path.suffix.lower() in {".mp4", ".webm", ".mkv"}), ""))
                update_job(job_id, 95, "running")
                LOGGER.info(
                    "Download de vídeo finalizado live_id=%s disponível=%s arquivos=%s",
                    live["id"], live["video_available"], [str(path) for path in video_files],
                )
        if not live.get("chat_available"):
            live["limitations"].append("O replay do chat não foi coletado; a plataforma pode exigir autenticação ou não disponibilizá-lo.")
        live["updated_at"] = now_iso()
        update_job(job_id, 100, live["status"], logs=live["limitations"])
        save_metadata(live)
        LOGGER.info("Processamento finalizado live_id=%s status=%s", live["id"], live["status"])
    except Exception as error:
        LOGGER.exception("Processamento inesperadamente falhou live_id=%s job_id=%s", live["id"], job_id)
        live["status"] = "failed"
        save_metadata(live)
        with LOCK:
            JOBS[job_id] = {"id": job_id, "live_id": live["id"], "status": "failed", "progress": 100, "error": str(error)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format_string: str, *args: object) -> None:
        LOGGER.info("HTTP %s - %s", self.address_string(), format_string % args)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        LOGGER.info("GET %s", self.path)
        if path == "":
            self._serve_static("index.html")
        elif path.startswith("/live/"):
            self._serve_static("index.html")
        elif path.startswith("/static/"):
            self._serve_static(path.removeprefix("/static/"))
        elif path.startswith("/assets/"):
            self._serve_static(path.removeprefix("/"))
        elif path == "/api/platforms":
            json_response(self, platform_catalog())
        elif path == "/api/lives":
            json_response(self, list_metadata())
        elif path == "/api/channels":
            self._channels()
        elif path.startswith("/api/channels/"):
            self._channel_get(path.removeprefix("/api/channels/"))
        elif path.startswith("/api/lives/") and path.endswith("/export"):
            self._export(path.removeprefix("/api/lives/").removesuffix("/export"))
        elif path.startswith("/api/lives/"):
            self._live_get(path.removeprefix("/api/lives/"), parse_qs(parsed.query))
        elif path.startswith("/media/"):
            self._serve_video(path.removeprefix("/media/"))
        elif path.startswith("/clips/"):
            self._serve_clip(path.removeprefix("/clips/"))
        elif path.startswith("/api/jobs/"):
            with LOCK:
                job = JOBS.get(path.removeprefix("/api/jobs/"))
            json_response(self, job or {"error": "Tarefa não encontrada."}, HTTPStatus.OK if job else HTTPStatus.NOT_FOUND)
        elif path == "/api/health":
            json_response(self, {"status": "ok"})
        else:
            LOGGER.warning("GET rota não encontrada path=%s", path)
            json_response(self, {"error": "Rota não encontrada."}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = self.path.rstrip("/")
        LOGGER.info("POST %s", path)
        if path == "/api/reset":
            try:
                payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            except (ValueError, json.JSONDecodeError):
                LOGGER.warning("Payload inválido em POST /api/reset")
                payload = {}
            if payload.get("confirm") is not True:
                json_response(self, {"error": "A limpeza exige confirmação explícita."}, HTTPStatus.BAD_REQUEST)
                return
            clear_data()
            with LOCK:
                JOBS.clear()
            json_response(self, {"message": "Todos os dados enviados foram apagados."})
            LOGGER.warning("Dados locais apagados por solicitação HTTP")
            return
        if path.startswith("/api/jobs/") and path.endswith("/cancel"):
            job_id = path.removeprefix("/api/jobs/").removesuffix("/cancel")
            with LOCK:
                job = JOBS.get(job_id)
                if not job:
                    LOGGER.warning("Cancelamento de job inexistente job_id=%s", job_id)
                    json_response(self, {"error": "Tarefa não encontrada."}, HTTPStatus.NOT_FOUND)
                    return
                job["cancel_requested"] = True
                job["status"] = "cancelling"
            json_response(self, job)
            return
        if path.startswith("/api/lives/") and path.endswith("/retry-chat"):
            live_id = path.removeprefix("/api/lives/").removesuffix("/retry-chat")
            live = load_metadata(live_id)
            if not live:
                LOGGER.warning("Retry de chat para live inexistente live_id=%s", live_id)
                json_response(self, {"error": "Live não encontrada."}, HTTPStatus.NOT_FOUND)
                return
            with LOCK:
                running = JOBS.get(live["job_id"], {}).get("status") in {"queued", "running", "cancelling"}
            if running:
                LOGGER.warning("Retry de chat recusado porque job está em execução live_id=%s", live_id)
                json_response(self, {"error": "Já existe uma tentativa de coleta em andamento."}, HTTPStatus.CONFLICT)
                return
            live["status"] = "queued"
            save_metadata(live)
            threading.Thread(target=retry_chat, args=(live,), daemon=True).start()
            json_response(self, {"message": "Nova tentativa de coleta do chat iniciada.", "job_id": live["job_id"]}, HTTPStatus.ACCEPTED)
            return
        if path.startswith("/api/lives/") and path.endswith("/retry-video"):
            live_id = path.removeprefix("/api/lives/").removesuffix("/retry-video")
            live = load_metadata(live_id)
            if not live:
                LOGGER.warning("Retry de vídeo para live inexistente live_id=%s", live_id)
                json_response(self, {"error": "Live não encontrada."}, HTTPStatus.NOT_FOUND)
                return
            with LOCK:
                running = JOBS.get(live["job_id"], {}).get("status") in {"queued", "running", "cancelling"}
            if running:
                LOGGER.warning("Retry de vídeo recusado porque job está em execução live_id=%s", live_id)
                json_response(self, {"error": "Já existe um processamento em andamento."}, HTTPStatus.CONFLICT)
                return
            live["status"] = "queued"
            save_metadata(live)
            threading.Thread(target=process_live, args=(live,), daemon=True).start()
            json_response(self, {"message": "Nova tentativa de baixar o vídeo iniciada.", "job_id": live["job_id"]}, HTTPStatus.ACCEPTED)
            return
        if path.startswith("/api/lives/") and path.endswith("/clip"):
            live_id = path.removeprefix("/api/lives/").removesuffix("/clip")
            live = load_metadata(live_id)
            if not live:
                LOGGER.warning("Criação de clip para live inexistente live_id=%s", live_id)
                json_response(self, {"error": "Live não encontrada."}, HTTPStatus.NOT_FOUND)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                start = float(payload.get("start"))
                end = float(payload.get("end"))
                if start < 0 or end <= start:
                    raise ValueError("O fim deve ser maior que o início.")
                if live.get("duration_seconds") and end > float(live["duration_seconds"]):
                    raise ValueError("O fim do recorte ultrapassa a duração do vídeo.")
                clip = create_clip(live, start, end)
                json_response(self, {
                    "message": "Trecho criado com sucesso.",
                    "filename": clip.name,
                    "download_url": f"/clips/{live_id}/{clip.name}",
                }, HTTPStatus.CREATED)
            except (ValueError, TypeError, json.JSONDecodeError, OSError, RuntimeError) as error:
                LOGGER.exception("Falha ao criar clip live_id=%s", live_id)
                json_response(self, {"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        if path != "/api/lives":
            json_response(self, {"error": "Rota não encontrada."}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            url = str(payload.get("url", "")).strip()
            platform = detect_platform(url)
            if not url or not url.startswith(("http://", "https://")):
                raise ValueError("Informe a URL pública da gravação. O campo não aceita um arquivo de vídeo local.")
            if not platform:
                raise ValueError("A plataforma desta URL não é suportada.")
            live = create_live_metadata(url, platform.key, extract_channel(url, platform))
            existing = load_metadata(live["id"])
            if existing:
                LOGGER.info("Live já cadastrada live_id=%s status=%s", existing["id"], existing.get("status"))
                if (not existing.get("video_available") or not existing.get("chat_available")) and existing.get("status") not in {"queued", "running"}:
                    existing["status"] = "queued"
                    save_metadata(existing)
                    threading.Thread(target=process_live, args=(existing,), daemon=True).start()
                    json_response(self, {**existing, "message": "A live já existia, mas será reprocessada para tentar obter o vídeo e o replay do chat."}, HTTPStatus.ACCEPTED)
                else:
                    json_response(self, {**existing, "message": "Essa live já está cadastrada ou sendo processada."}, HTTPStatus.OK)
                return
            ensure_data_dirs()
            save_metadata(live)
            threading.Thread(target=process_live, args=(live,), daemon=True).start()
            LOGGER.info("Live cadastrada live_id=%s plataforma=%s", live["id"], live["platform"])
            json_response(self, {**live, "message": "URL cadastrada. O replay foi identificado, mas o vídeo e o chat só serão coletados quando houver um adaptador autorizado para a plataforma."}, HTTPStatus.ACCEPTED)
        except (ValueError, json.JSONDecodeError) as error:
            LOGGER.exception("Falha ao cadastrar live")
            json_response(self, {"error": str(error)}, HTTPStatus.BAD_REQUEST)

    def do_DELETE(self) -> None:
        path = self.path.rstrip("/")
        LOGGER.info("DELETE %s", path)
        if not path.startswith("/api/lives/"):
            json_response(self, {"error": "Rota não encontrada."}, HTTPStatus.NOT_FOUND)
            return
        live_id = path.removeprefix("/api/lives/")
        if "/" in live_id or not live_id:
            json_response(self, {"error": "Live inválida."}, HTTPStatus.BAD_REQUEST)
            return
        with LOCK:
            job = next((job for job in JOBS.values() if job.get("live_id") == live_id), None)
            if job and job.get("status") in {"queued", "running", "cancelling"}:
                LOGGER.warning("Exclusão recusada: job em execução live_id=%s", live_id)
                json_response(self, {"error": "Aguarde o download terminar antes de apagar esta live."}, HTTPStatus.CONFLICT)
                return
        if not delete_live_data(live_id):
            LOGGER.warning("Exclusão solicitada para live inexistente live_id=%s", live_id)
            json_response(self, {"error": "Live não encontrada."}, HTTPStatus.NOT_FOUND)
            return
        with LOCK:
            JOBS.pop(job["id"], None) if job else None
        LOGGER.info("Live excluída live_id=%s", live_id)
        json_response(self, {"message": "Live apagada com sucesso."})

    def _live_get(self, live_id: str, query: dict[str, list[str]]) -> None:
        live = load_metadata(live_id)
        if not live:
            json_response(self, {"error": "Live não encontrada."}, HTTPStatus.NOT_FOUND)
            return
        chat_path = DATA_DIR / "raw" / "chats" / f"{live_id}.jsonl"
        window = int(query.get("window", ["10"])[0])
        result = analyze(read_messages(chat_path), window)
        live["analysis"] = result
        json_response(self, live)

    def _channels(self) -> None:
        grouped = {}
        for live in list_metadata():
            channel = live.get("channel", "unknown")
            item = grouped.setdefault(channel, {"channel": channel, "platforms": set(), "lives": 0, "messages": 0})
            item["platforms"].add(live.get("platform", "unknown"))
            item["lives"] += 1
            item["messages"] += live.get("message_count", 0)
        result = [{**item, "platforms": sorted(item["platforms"])} for item in grouped.values()]
        json_response(self, sorted(result, key=lambda item: item["channel"]))

    def _channel_get(self, channel: str) -> None:
        lives = [live for live in list_metadata() if live.get("channel") == channel]
        if not lives:
            json_response(self, {"error": "Canal não encontrado."}, HTTPStatus.NOT_FOUND)
            return
        json_response(self, {"channel": channel, "lives": lives})

    def _export(self, live_id: str) -> None:
        live = load_metadata(live_id)
        if not live:
            json_response(self, {"error": "Live não encontrada."}, HTTPStatus.NOT_FOUND)
            return
        chat_path = DATA_DIR / "raw" / "chats" / f"{live_id}.jsonl"
        live["analysis"] = analyze(read_messages(chat_path), 10)
        body = json.dumps(live, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{live_id}-report.json"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_video(self, live_id: str) -> None:
        LOGGER.info("Solicitação de vídeo live_id=%s", live_id)
        live = load_metadata(live_id)
        if not live or not live.get("video_path"):
            LOGGER.warning("Vídeo não encontrado no metadata live_id=%s", live_id)
            json_response(self, {"error": "Vídeo não encontrado."}, HTTPStatus.NOT_FOUND)
            return
        video = Path(live["video_path"]).resolve()
        video_root = (DATA_DIR / "videos").resolve()
        if video_root not in video.parents or not video.is_file():
            LOGGER.error("Caminho de vídeo inválido ou inexistente live_id=%s caminho=%s", live_id, video)
            json_response(self, {"error": "Vídeo não encontrado."}, HTTPStatus.NOT_FOUND)
            return
        size = video.stat().st_size
        start = 0
        end = size - 1
        range_header = self.headers.get("Range")
        if range_header and range_header.startswith("bytes="):
            requested = range_header.removeprefix("bytes=").split("-", 1)
            try:
                start = int(requested[0] or 0)
                end = int(requested[1]) if len(requested) > 1 and requested[1] else end
                if start < 0 or start >= size or end < start:
                    raise ValueError
                end = min(end, size - 1)
            except ValueError:
                self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                return
        length = end - start + 1
        self.send_response(206 if range_header else 200)
        self.send_header("Content-Type", "video/mp4" if video.suffix.lower() == ".mp4" else "video/webm")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if range_header:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        try:
            with video.open("rb") as source:
                source.seek(start)
                remaining = length
                while remaining:
                    chunk = source.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # O player pode cancelar uma requisição ao trocar de posição ou formato.
            return

    def _serve_clip(self, resource: str) -> None:
        LOGGER.info("Solicitação de clip resource=%s", resource)
        parts = resource.split("/", 1)
        if len(parts) != 2:
            json_response(self, {"error": "Trecho inválido."}, HTTPStatus.NOT_FOUND)
            return
        live_id, filename = parts
        if Path(filename).name != filename or not filename.endswith(".mp4"):
            json_response(self, {"error": "Trecho inválido."}, HTTPStatus.NOT_FOUND)
            return
        clip = (DATA_DIR / "reports" / live_id / "clips" / filename).resolve()
        clip_root = (DATA_DIR / "reports" / live_id / "clips").resolve()
        if clip_root not in clip.parents or not clip.is_file():
            json_response(self, {"error": "Trecho não encontrado."}, HTTPStatus.NOT_FOUND)
            return
        body_size = clip.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(body_size))
        self.end_headers()
        try:
            with clip.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return

    def _serve_static(self, name: str) -> None:
        target = (STATIC / name).resolve()
        if STATIC.resolve() not in target.parents or not target.is_file():
            json_response(self, {"error": "Arquivo não encontrado."}, HTTPStatus.NOT_FOUND)
            return
        content_type = "text/html; charset=utf-8" if target.suffix == ".html" else "text/css; charset=utf-8" if target.suffix == ".css" else "application/javascript; charset=utf-8"
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    if "--clear-data" in sys.argv:
        clear_data()
        print("Dados da pasta .data apagados.")
        sys.argv.remove("--clear-data")
    ensure_data_dirs()
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    print("Live Chat Peak Analyzer: http://127.0.0.1:8000")
    server.serve_forever()
