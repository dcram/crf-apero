import datetime as dt

from app.frdate import format_date_fr


def test_formats_tuesday():
    assert format_date_fr(dt.date(2026, 10, 6)) == "mardi 6 octobre 2026"


def test_formats_first_of_month_and_accents():
    assert format_date_fr(dt.date(2027, 2, 2)) == "mardi 2 février 2027"
    assert format_date_fr(dt.date(2026, 12, 1)) == "mardi 1er décembre 2026"
