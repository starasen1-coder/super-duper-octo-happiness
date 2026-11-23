"""Strict configuration loading for the research worker."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json


@dataclass(frozen=True)
class SourceConfig:
    name: str
    source_type: str
    enabled: bool = True


def load_sources(path: str | Path) -> list[SourceConfig]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("source configuration must be a JSON array")
    result = []
    seen = set()
    for entry in data:
        if not isinstance(entry, dict):
            raise ValueError("each source entry must be an object")
        name = entry.get("name")
        source_type = entry.get("source_type")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("source name is required")
        if not isinstance(source_type, str) or not source_type.strip():
            raise ValueError("source_type is required")
        if name in seen:
            raise ValueError(f"duplicate source: {name}")
        seen.add(name)
        result.append(SourceConfig(name=name, source_type=source_type, enabled=entry.get("enabled", True) is True))
    return result
