import datetime as dt

_WEEKDAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
_MONTHS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def format_date_fr(d: dt.date) -> str:
    """Date longue en français, sans dépendre de la locale système."""
    day = "1er" if d.day == 1 else str(d.day)
    return f"{_WEEKDAYS[d.weekday()]} {day} {_MONTHS[d.month - 1]} {d.year}"
