import datetime as dt

from sqlalchemy import Date, DateTime, Integer, Text, UniqueConstraint, delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (UniqueConstraint("tuesday", name="uq_bookings_tuesday"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tuesday: Mapped[dt.date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AdminCode(Base):
    __tablename__ = "admin_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DateAlreadyTaken(Exception):
    """Un autre paroissien a déjà réservé ce mardi."""


def make_engine(url: str) -> AsyncEngine:
    return create_async_engine(url, pool_pre_ping=True, hide_parameters=True)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def taken_dates(session: AsyncSession) -> set[dt.date]:
    return set(await session.scalars(select(Booking.tuesday)))


async def create_booking(
    session: AsyncSession, *, tuesday: dt.date, name: str, phone: str | None
) -> None:
    session.add(Booking(tuesday=tuesday, name=name, phone=phone))
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise DateAlreadyTaken(tuesday) from exc


async def ping(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def replace_code(
    session: AsyncSession,
    *,
    email: str,
    code_hash: str,
    expires_at: dt.datetime,
    now: dt.datetime,
) -> None:
    """Un seul code valable par adresse : le précédent est effacé, les expirés aussi."""
    await session.execute(delete(AdminCode).where(AdminCode.email == email))
    await session.execute(delete(AdminCode).where(AdminCode.expires_at <= now))
    session.add(AdminCode(email=email, code_hash=code_hash, expires_at=expires_at))
    await session.commit()


async def fetch_code(session: AsyncSession, email: str) -> AdminCode | None:
    return await session.scalar(select(AdminCode).where(AdminCode.email == email))


async def register_failed_attempt(
    session: AsyncSession, code: AdminCode, *, max_attempts: int
) -> None:
    code.attempts += 1
    if code.attempts >= max_attempts:
        await session.delete(code)
    await session.commit()


async def consume_code(session: AsyncSession, code: AdminCode) -> None:
    await session.delete(code)
    await session.commit()
