import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

DEFAULT_SESSIONS_FILE = Path(__file__).parent / "sessions.yaml"

TUESDAY = 1


class SessionsFileError(ValueError):
    """Le fichier du programme est invalide : l'application ne doit pas démarrer."""


@dataclass(frozen=True)
class Meeting:
    date: dt.date
    theme: str


class _Entry(BaseModel):
    date: dt.date
    theme: str


class _File(BaseModel):
    sessions: list[_Entry]


def load_sessions(path: Path) -> list[Meeting]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        parsed = _File.model_validate(raw)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise SessionsFileError(f"{path} illisible : {exc}") from exc

    seen: set[dt.date] = set()
    meetings: list[Meeting] = []
    for entry in parsed.sessions:
        if entry.date.weekday() != TUESDAY:
            raise SessionsFileError(f"{entry.date.isoformat()} n'est pas un mardi")
        if entry.date in seen:
            raise SessionsFileError(f"{entry.date.isoformat()} : date en doublon")
        theme = entry.theme.strip()
        if not theme:
            raise SessionsFileError(f"{entry.date.isoformat()} : thème vide")
        seen.add(entry.date)
        meetings.append(Meeting(date=entry.date, theme=theme))
    return sorted(meetings, key=lambda m: m.date)
