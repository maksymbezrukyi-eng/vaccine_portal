"""
database.py — SQLAlchemy моделі + підключення до Supabase (PostgreSQL)
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

import streamlit as st
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey,
    Integer, LargeBinary, Numeric, String, Text, UniqueConstraint,
    create_engine, text,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker


# ─── Підключення ─────────────────────────────────────────────────────

def get_db_url() -> str:
    """Повертає рядок підключення з st.secrets або змінних середовища."""
    try:
        return st.secrets["DATABASE_URL"]
    except Exception:
        url = os.getenv("DATABASE_URL", "")
        if not url:
            raise RuntimeError(
                "DATABASE_URL не знайдено. "
                "Додайте його до .streamlit/secrets.toml або змінних середовища."
            )
        return url


@st.cache_resource
def get_engine():
    url = get_db_url()
    # Supabase повертає postgres://, SQLAlchemy потребує postgresql://
    if url.startswith("postgres://") and not url.startswith("postgresql://"):
        url = "postgresql://" + url[len("postgres://"):]
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)


def get_session() -> Session:
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


# ─── Базовий клас ─────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ─── Моделі ───────────────────────────────────────────────────────────

class Organization(Base):
    """Список ЗОЗ (104 + можливо більше в майбутньому)."""
    __tablename__ = "organizations"

    id         = Column(Integer, primary_key=True)
    seq_number = Column(Integer, nullable=True)          # порядковий номер зі списку
    name       = Column(String(500), nullable=False)
    edrpou     = Column(String(20), nullable=True)       # може бути невідомий на початку
    region     = Column(String(100), default="Житомирська")
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    report_files = relationship("ReportFile", back_populates="organization")


class ReportPeriod(Base):
    """Звітний місяць."""
    __tablename__ = "report_periods"
    __table_args__ = (UniqueConstraint("year", "month", name="uq_period"),)

    id         = Column(Integer, primary_key=True)
    year       = Column(Integer, nullable=False)
    month      = Column(Integer, nullable=False)   # 1-12
    created_at = Column(DateTime, default=datetime.utcnow)

    report_files = relationship("ReportFile", back_populates="period")

    @property
    def label(self) -> str:
        MONTHS = {1:"Січень",2:"Лютий",3:"Березень",4:"Квітень",5:"Травень",
                  6:"Червень",7:"Липень",8:"Серпень",9:"Вересень",
                  10:"Жовтень",11:"Листопад",12:"Грудень"}
        return f"{MONTHS[self.month]} {self.year}"


class ReportFile(Base):
    """Завантажений Excel-файл ЗОЗ."""
    __tablename__ = "report_files"
    __table_args__ = (
        UniqueConstraint("org_id", "period_id", name="uq_org_period"),
    )

    id            = Column(Integer, primary_key=True)
    org_id        = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    period_id     = Column(Integer, ForeignKey("report_periods.id"), nullable=False)
    filename      = Column(String(255))
    file_bytes    = Column(LargeBinary)              # оригінальний .xlsx
    uploaded_at   = Column(DateTime, default=datetime.utcnow)
    status        = Column(String(20), default="pending")  # ok / warning / error
    error_count   = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)

    organization    = relationship("Organization", back_populates="report_files")
    period          = relationship("ReportPeriod", back_populates="report_files")
    execution_rows  = relationship("VaccinationExecution", back_populates="file",
                                   cascade="all, delete-orphan")
    stock_rows      = relationship("StockData", back_populates="file",
                                   cascade="all, delete-orphan")
    refusal_rows    = relationship("Refusal", back_populates="file",
                                   cascade="all, delete-orphan")
    issues          = relationship("ValidationIssue", back_populates="file",
                                   cascade="all, delete-orphan")
    birth_data      = relationship("BirthData", back_populates="file",
                                   cascade="all, delete-orphan", uselist=False)


class VaccinationExecution(Base):
    """Дані виконання з аркушу 'Зведений звіт' (col C=план, D=місяць, E=ytd)."""
    __tablename__ = "vaccination_execution"

    id              = Column(Integer, primary_key=True)
    file_id         = Column(Integer, ForeignKey("report_files.id"), nullable=False)
    sheet_row       = Column(Integer)                # рядок у Зведеному звіті (11-119)
    vaccine         = Column(String(200))
    age_group       = Column(String(100))
    planned         = Column(Numeric(10, 2))
    executed_month  = Column(Numeric(10, 2))
    ytd             = Column(Numeric(10, 2))
    pct             = Column(Numeric(8, 2))

    file = relationship("ReportFile", back_populates="execution_rows")


class StockData(Base):
    """Залишки вакцин (аркуш 'Залишки', рядки 11-37)."""
    __tablename__ = "stock_data"

    id            = Column(Integer, primary_key=True)
    file_id       = Column(Integer, ForeignKey("report_files.id"), nullable=False)
    vaccine       = Column(String(200))
    stock_start   = Column(Numeric(10, 2), default=0)
    received      = Column(Numeric(10, 2), default=0)
    stock_end     = Column(Numeric(10, 2), default=0)
    executed      = Column(Numeric(10, 2), default=0)
    used          = Column(Numeric(10, 2), default=0)
    local_budget  = Column(Numeric(10, 2), default=0)
    other_sources = Column(Numeric(10, 2), default=0)

    file = relationship("ReportFile", back_populates="stock_rows")


class Refusal(Base):
    """Відмови від щеплень (Виконання рядки 8-13, col T)."""
    __tablename__ = "refusals"

    id      = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("report_files.id"), nullable=False)
    disease = Column(String(200))
    count   = Column(Integer, default=0)

    file = relationship("ReportFile", back_populates="refusal_rows")


class BirthData(Base):
    """Дані народжуваності / КДП (Виконання рядок 8, cols J-M)."""
    __tablename__ = "birth_data"

    id           = Column(Integer, primary_key=True)
    file_id      = Column(Integer, ForeignKey("report_files.id"), nullable=False, unique=True)
    born_month   = Column(Integer, default=0)   # J8 — народилось у пологовому
    hepb_1day    = Column(Integer, default=0)   # K8 — підлягали ГепВ у 1 добу
    born_7months = Column(Integer, default=0)   # L8 — народилось за 7 місяців
    kdp3_timely  = Column(Integer, default=0)   # M8 — отримали КДП3 своєчасно
    temp_ci      = Column(Integer, default=0)   # протипокази тимчасові
    perm_ci      = Column(Integer, default=0)   # протипокази постійні

    file = relationship("ReportFile", back_populates="birth_data")


class ValidationIssue(Base):
    """Помилки та попередження після валідації файлу."""
    __tablename__ = "validation_issues"

    id       = Column(Integer, primary_key=True)
    file_id  = Column(Integer, ForeignKey("report_files.id"), nullable=False)
    severity = Column(String(10))   # 'error' / 'warning'
    message  = Column(Text)

    file = relationship("ReportFile", back_populates="issues")


# ─── Ініціалізація БД ────────────────────────────────────────────────

def init_db():
    """Створює таблиці якщо вони не існують."""
    engine = get_engine()
    Base.metadata.create_all(engine)


def seed_organizations(orgs: list[dict]):
    """
    Заповнює таблицю organizations із списку ЗОЗ.
    orgs = [{"seq_number": 1, "name": "...", "region": "Житомирська"}, ...]
    Пропускає вже існуючі (за name).
    """
    session = get_session()
    try:
        existing = {o.name for o in session.query(Organization).all()}
        new_orgs = [
            Organization(
                seq_number=o.get("seq_number"),
                name=o["name"].strip(),
                region=o.get("region", "Житомирська"),
            )
            for o in orgs
            if o["name"].strip() not in existing
        ]
        if new_orgs:
            session.add_all(new_orgs)
            session.commit()
        return len(new_orgs)
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_or_create_period(year: int, month: int) -> ReportPeriod:
    session = get_session()
    try:
        p = session.query(ReportPeriod).filter_by(year=year, month=month).first()
        if not p:
            p = ReportPeriod(year=year, month=month)
            session.add(p)
            session.commit()
            session.refresh(p)
        return p
    finally:
        session.close()
