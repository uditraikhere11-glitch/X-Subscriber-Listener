from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class XPost:
    post_id: str
    handle: str
    url: str
    created_at: str
    observed_at: str
    text: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)
