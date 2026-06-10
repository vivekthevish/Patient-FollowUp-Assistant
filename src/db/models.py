"""SQLAlchemy models for the follow-up assistant."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.config import DATABASE_URL


def _sqlite_engine_kwargs(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


class Base(DeclarativeBase):
    pass


engine = create_engine(DATABASE_URL, future=True, **_sqlite_engine_kwargs(DATABASE_URL))


class Patient(Base):
    __tablename__ = "patients"

    patient_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    patient_name: Mapped[str] = mapped_column(String(100), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[str] = mapped_column(String(10), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    diagnosis: Mapped[str] = mapped_column(String(200), nullable=False)
    follow_up_date: Mapped[date] = mapped_column(Date, nullable=False)
    doctor_notes: Mapped[str] = mapped_column(Text, nullable=False)
    attending_doctor: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="Moderate")
    patient_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    followup_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Reminder(Base):
    __tablename__ = "reminders"

    reminder_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    reminder_text: Mapped[str] = mapped_column(Text, nullable=False)
    rag_context_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    reminder_sent_dates: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    email_status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_sent")
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Escalation(Base):
    __tablename__ = "escalations"
    __table_args__ = (UniqueConstraint("patient_id", name="uq_escalations_patient_id"),)

    escalation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    patient_name: Mapped[str] = mapped_column(String(100), nullable=False)
    diagnosis: Mapped[str] = mapped_column(String(200), nullable=False)
    follow_up_date: Mapped[date] = mapped_column(Date, nullable=False)
    doctor_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_report: Mapped[str] = mapped_column(Text, nullable=False)
    escalation_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
