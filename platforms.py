from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class PlatformInfo:
    key: str
    name: str
    domains: tuple[str, ...]
    video_download: bool
    chat_replay: bool
    authentication: bool
    limitations: tuple[str, ...]


PLATFORMS = (
    PlatformInfo(
        "twitch",
        "Twitch",
        ("twitch.tv", "www.twitch.tv"),
        False,
        False,
        True,
        ("A coleta de replay do chat depende de autenticação e disponibilidade da plataforma.",),
    ),
    PlatformInfo(
        "youtube",
        "YouTube",
        ("youtube.com", "www.youtube.com", "youtu.be"),
        False,
        False,
        False,
        ("O download e o replay do chat exigem integração autorizada específica.",),
    ),
    PlatformInfo(
        "kick",
        "Kick",
        ("kick.com", "www.kick.com"),
        False,
        False,
        True,
        ("Não há coletor oficial incluído nesta versão.",),
    ),
)


def detect_platform(url: str) -> PlatformInfo | None:
    hostname = (urlparse(url).hostname or "").lower()
    for platform in PLATFORMS:
        if hostname in platform.domains or any(hostname.endswith("." + domain) for domain in platform.domains):
            return platform
    return None


def extract_channel(url: str, platform: PlatformInfo | None) -> str:
    path = [part for part in urlparse(url).path.split("/") if part]
    if platform and platform.key == "youtube":
        return "youtube"
    return path[0] if path else "unknown"


def platform_catalog() -> list[dict]:
    return [asdict(platform) for platform in PLATFORMS]

