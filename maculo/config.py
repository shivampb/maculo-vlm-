"""Runtime settings, read from environment variables (and an optional .env file).

Every setting has a MACULO_ prefix, e.g. MACULO_PORT=9000.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # python-dotenv is optional
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parent.parent


def _env(name: str, default: str) -> str:
    return os.environ.get(f"MACULO_{name}", default)


def _bool(name: str, default: bool) -> bool:
    return _env(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _list(name: str, default: str) -> list[str]:
    return [v.strip() for v in _env(name, default).split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    # Server
    host: str = field(default_factory=lambda: _env("HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(_env("PORT", "8000")))
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "info"))
    enable_docs: bool = field(default_factory=lambda: _bool("ENABLE_DOCS", True))
    cors_origins: list[str] = field(default_factory=lambda: _list("CORS_ORIGINS", ""))
    trust_proxy: bool = field(default_factory=lambda: _bool("TRUST_PROXY", False))

    # Models
    clip_id: str = field(
        default_factory=lambda: _env("CLIP_ID", "hf-hub:Xieji-Li/MAGEN-O-MAKE")
    )
    sam_dir: Path = field(
        default_factory=lambda: Path(_env("SAM_DIR", str(ROOT / "models" / "sam")))
    )
    device: str = field(default_factory=lambda: _env("DEVICE", "auto"))

    # Limits
    max_upload_mb: float = field(
        default_factory=lambda: float(_env("MAX_UPLOAD_MB", "15"))
    )
    max_image_side: int = field(
        default_factory=lambda: int(_env("MAX_IMAGE_SIDE", "1024"))
    )
    max_labels: int = field(default_factory=lambda: int(_env("MAX_LABELS", "120")))
    max_label_chars: int = 80
    max_points: int = 24
    session_ttl_s: int = field(
        default_factory=lambda: int(_env("SESSION_TTL_S", "900"))
    )
    session_capacity: int = field(
        default_factory=lambda: int(_env("SESSION_CAPACITY", "32"))
    )
    uploads_per_minute: int = field(
        default_factory=lambda: int(_env("UPLOADS_PER_MINUTE", "30"))
    )

    # Result interpretation
    low_confidence: float = 0.50
    low_margin: float = 0.10

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)

    def resolve_device(self) -> str:
        if self.device != "auto":
            return self.device
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"


def get_settings() -> Settings:
    return Settings()
