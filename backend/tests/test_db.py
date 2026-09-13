import datetime as dt

import pytest

from app.db import DateAlreadyTaken, create_booking, ping, taken_dates

DAY = dt.date(2030, 1, 1)


async def test_create_booking_marks_date_taken(sessionmaker):
    async with sessionmaker() as session:
        await create_booking(session, tuesday=DAY, name="Jean Dupont", phone="0612345678")
    async with sessionmaker() as session:
        assert await taken_dates(session) == {DAY}


async def test_same_date_twice_raises(sessionmaker):
    async with sessionmaker() as session:
        await create_booking(session, tuesday=DAY, name="Jean", phone=None)
    async with sessionmaker() as session:
        with pytest.raises(DateAlreadyTaken):
            await create_booking(session, tuesday=DAY, name="Marie", phone=None)


async def test_ping(engine):
    await ping(engine)
