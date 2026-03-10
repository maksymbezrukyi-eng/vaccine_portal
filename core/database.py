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


def get_db_url() -> str:
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
    if url.startswith("postgres://") and not url.startswith("postgresql://"):
        url = "postgresql://" + url[len("postgres://"):]
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)


def get_session() -> Session:
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"

    id         = Column(Integer, primary_key=True)
    seq_number = Column(Integer, nullable=True)
    name       = Column(String(500), nullable=False)
    edrpou     = Column(String(20), nullable=True)
    region     = Column(String(100), default="Житомирська")
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    report_files = relationship("ReportFile", back_populates="organization")


class ReportPeriod(Base):
    __tablename__ = "report_periods"
    __table_args__ = (UniqueConstraint("year", "month", name="uq_period"),)

    id         = Column(Integer, primary_key=True)
    year       = Column(Integer, nullable=False)
    month      = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    report_files = relationship("ReportFile", back_populates="period")

    @property
    def label(self) -> str:
        MONTHS =
