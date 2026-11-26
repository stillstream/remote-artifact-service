from dataclasses import dataclass
from pathlib import Path
import json

@dataclass(frozen=True)
class RootConfig:
    id: str
    label: str
    path: Path
    show_hidden: bool = False

@dataclass(frozen=True)
class AppConfig:
    host: str
    port: int
    roots: tuple[RootConfig, ...]


def load_config(path: str | Path) -> AppConfig:
    data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    roots, seen = [], set()
    for item in data.get("roots", []):
        root_id = str(item["id"])
        if not root_id or root_id in seen or "/" in root_id:
            raise ValueError(f"invalid or duplicate root id: {root_id!r}")
        seen.add(root_id)
        root = Path(item["path"]).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise ValueError(f"root is not a directory: {root}")
        roots.append(RootConfig(root_id, str(item.get("label", root_id)), root, bool(item.get("show_hidden", False))))
    if not roots:
        raise ValueError("at least one readable root must be configured")
    host = str(data.get("host", "127.0.0.1"))
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("v0.1 only supports loopback bind addresses")
    port = int(data.get("port", 18765))
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    return AppConfig(host, port, tuple(roots))
