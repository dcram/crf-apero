import datetime as dt
from pathlib import Path

import pytest

from app.sessions import DEFAULT_SESSIONS_FILE, Meeting, SessionsFileError, load_sessions

FIXTURE = Path(__file__).parent / "fixtures" / "sessions.yaml"


def write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "sessions.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_loads_and_sorts_by_date():
    meetings = load_sessions(FIXTURE)
    assert meetings == [
        Meeting(date=dt.date(2020, 1, 7), theme="Thème passé"),
        Meeting(date=dt.date(2030, 1, 1), theme="Thème A"),
        Meeting(date=dt.date(2030, 1, 15), theme="Thème B"),
    ]


def test_accepts_quoted_dates(tmp_path):
    path = write(tmp_path, 'sessions:\n  - date: "2030-01-01"\n    theme: "A"\n')
    assert load_sessions(path) == [Meeting(date=dt.date(2030, 1, 1), theme="A")]


def test_rejects_non_tuesday(tmp_path):
    path = write(tmp_path, "sessions:\n  - date: 2030-01-02\n    theme: A\n")
    with pytest.raises(SessionsFileError, match="2030-01-02.*mardi"):
        load_sessions(path)


def test_rejects_duplicate_dates(tmp_path):
    path = write(
        tmp_path,
        "sessions:\n  - date: 2030-01-01\n    theme: A\n  - date: 2030-01-01\n    theme: B\n",
    )
    with pytest.raises(SessionsFileError, match="doublon"):
        load_sessions(path)


def test_rejects_empty_theme(tmp_path):
    path = write(tmp_path, 'sessions:\n  - date: 2030-01-01\n    theme: "  "\n')
    with pytest.raises(SessionsFileError, match="thème"):
        load_sessions(path)


def test_rejects_invalid_date(tmp_path):
    path = write(tmp_path, "sessions:\n  - date: pas-une-date\n    theme: A\n")
    with pytest.raises(SessionsFileError):
        load_sessions(path)


def test_rejects_missing_sessions_key(tmp_path):
    path = write(tmp_path, "autre: 1\n")
    with pytest.raises(SessionsFileError):
        load_sessions(path)


def test_shipped_program_is_valid():
    assert len(load_sessions(DEFAULT_SESSIONS_FILE)) > 0
