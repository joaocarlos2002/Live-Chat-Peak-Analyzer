from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / ".data"


def ensure_data_dirs() -> None:
    for directory in (
        DATA_DIR / "videos",
        DATA_DIR / "raw" / "chats",
        DATA_DIR / "processed" / "chats",
        DATA_DIR / "metadata",
        DATA_DIR / "reports",
        DATA_DIR / "reports" / "clips",
    ):
        directory.mkdir(parents=True, exist_ok=True)


def clear_data() -> None:
    """Remove generated data while preserving the .data directory itself."""
    ensure_data_dirs()
    for path in DATA_DIR.iterdir():
        if path.name == "backend.log":
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    ensure_data_dirs()


def delete_live_data(live_id: str) -> bool:
    """Delete one live and only the files owned by that live."""
    metadata = load_metadata(live_id)
    if not metadata:
        return False

    metadata_path(live_id).unlink(missing_ok=True)
    (DATA_DIR / "raw" / "chats" / f"{live_id}.jsonl").unlink(missing_ok=True)
    video_root = (DATA_DIR / "videos").resolve()
    video_path = Path(metadata.get("video_path", "")).resolve()
    if video_path.is_file() and video_root in video_path.parents:
        video_path.unlink()
    report_dir = DATA_DIR / "reports" / live_id
    if report_dir.is_dir():
        shutil.rmtree(report_dir)
    return True
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_live_id(url: str) -> str:
    import hashlib

    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()[:16]


def safe_name(value: str, fallback: str = "unknown") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("._")
    return cleaned[:80] or fallback


def metadata_path(live_id: str) -> Path:
    return DATA_DIR / "metadata" / f"{live_id}.json"


def load_metadata(live_id: str) -> dict[str, Any] | None:
    path = metadata_path(live_id)
    if not path.exists():
        return None
    metadata = json.loads(path.read_text(encoding="utf-8"))
    video_path = metadata.get("video_path")
    if video_path and not Path(video_path).is_file():
        filename = Path(video_path).name
        candidates = list((DATA_DIR / "videos").rglob(filename))
        if candidates:
            metadata["video_path"] = str(candidates[0])
            save_metadata(metadata)
        else:
            metadata["video_available"] = False
    return metadata


def save_metadata(metadata: dict[str, Any]) -> None:
    ensure_data_dirs()
    target = metadata_path(metadata["id"])
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)


def list_metadata() -> list[dict[str, Any]]:
    ensure_data_dirs()
    items = []
    for path in (DATA_DIR / "metadata").glob("*.json"):
        try:
            items.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(items, key=lambda item: item.get("created_at", ""), reverse=True)


def create_live_metadata(url: str, platform: str, channel: str) -> dict[str, Any]:
    live_id = stable_live_id(url)
    return {
        "id": live_id,
        "url": url,
        "platform": platform,
        "channel": channel,
        "title": url,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "status": "queued",
        "video_available": False,
        "chat_available": False,
        "limitations": [],
        "message_count": 0,
        "unique_users": 0,
        "job_id": str(uuid.uuid4()),
    }
