"""
service.py — бізнес-логіка: збереження файлів, завантаження даних для дашбордів
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from .database import (
    BirthData, Organization, ReportFile, ReportPeriod,
    Refusal, StockData, ValidationIssue, VaccinationExecution,
    get_session,
)
from .parser import ParseResult


# ─── Збереження завантаженого файлу ──────────────────────────────────

def save_report_file(
    session: Session,
    org_id: int,
    period_id: int,
    filename: str,
    file_bytes: bytes,
    parse_result: ParseResult,
) -> ReportFile:
    """
    Зберігає або оновлює запис файлу + всі пов'язані дані в БД.
    Якщо запис для (org_id, period_id) вже існує — видаляє старий і записує новий.
    """
    # Видалити старий запис якщо є (дозволяємо перезавантаження)
    existing = session.query(ReportFile).filter_by(
        org_id=org_id, period_id=period_id
    ).first()
    if existing:
        session.delete(existing)
        session.flush()

    rf = ReportFile(
        org_id=org_id,
        period_id=period_id,
        filename=filename,
        file_bytes=file_bytes,
        status=parse_result.status,
        error_count=len(parse_result.errors),
        warning_count=len(parse_result.warnings),
    )
    session.add(rf)
    session.flush()  # отримуємо rf.id

    # Дані виконання
    for row in parse_result.execution_rows:
        session.add(VaccinationExecution(
            file_id=rf.id,
            sheet_row=row["sheet_row"],
            vaccine=row["vaccine"],
            age_group=row["age_group"],
            planned=row["planned"],
            executed_month=row["executed_month"],
            ytd=row["ytd"],
            pct=row["pct"],
        ))

    # Залишки
    for row in parse_result.stock_rows:
        session.add(StockData(
            file_id=rf.id,
            vaccine=row["vaccine"],
            stock_start=row["stock_start"],
            received=row["received"],
            stock_end=row["stock_end"],
            executed=row["executed"],
            used=row["used"],
            local_budget=row["local_budget"],
            other_sources=row["other_sources"],
        ))

    # Відмови
    for row in parse_result.refusal_rows:
        session.add(Refusal(
            file_id=rf.id,
            disease=row["disease"],
            count=row["count"],
        ))

    # Народжуваність
    bd = parse_result.birth_data
    if bd:
        session.add(BirthData(
            file_id=rf.id,
            born_month=bd.get("born_month", 0),
            hepb_1day=bd.get("hepb_1day", 0),
            born_7months=bd.get("born_7months", 0),
            kdp3_timely=bd.get("kdp3_timely", 0),
            temp_ci=bd.get("temp_ci", 0),
            perm_ci=bd.get("perm_ci", 0),
        ))

    # Помилки та попередження
    for msg in parse_result.errors:
        session.add(ValidationIssue(file_id=rf.id, severity="error", message=msg))
    for msg in parse_result.warnings:
        session.add(ValidationIssue(file_id=rf.id, severity="warning", message=msg))

    session.commit()
    session.refresh(rf)
    return rf


# ─── Пошук організації за назвою (нечітке співпадіння) ───────────────

def find_org_by_name(session: Session, name: str) -> Optional[Organization]:
    """Шукає організацію за точним або нечітким співпадінням назви."""
    name = name.strip()
    # Точне
    org = session.query(Organization).filter(Organization.name == name).first()
    if org:
        return org
    # Нечітке: перші 30 символів
    prefix = name[:30]
    candidates = session.query(Organization).filter(
        Organization.name.ilike(f"{prefix}%")
    ).all()
    if len(candidates) == 1:
        return candidates[0]
    # Повний пошук по підрядку
    candidates = session.query(Organization).filter(
        Organization.name.ilike(f"%{name[:20]}%")
    ).all()
    if len(candidates) == 1:
        return candidates[0]
    return None


def find_org_by_edrpou(session: Session, edrpou: str) -> Optional[Organization]:
    return session.query(Organization).filter(Organization.edrpou == edrpou).first()


# ─── Дані для дашбордів ───────────────────────────────────────────────

def get_coverage_data(period_id: int) -> list[dict]:
    """
    Повертає агреговані дані охоплення по всіх ЗОЗ для вибраного місяця.
    [{vaccine, age_group, planned_total, executed_total, pct, org_count}, ...]
    """
    session = get_session()
    try:
        from sqlalchemy import func
        rows = (
            session.query(
                VaccinationExecution.vaccine,
                VaccinationExecution.age_group,
                func.sum(VaccinationExecution.planned).label("planned_total"),
                func.sum(VaccinationExecution.executed_month).label("executed_total"),
                func.count(VaccinationExecution.file_id).label("org_count"),
            )
            .join(ReportFile)
            .filter(ReportFile.period_id == period_id)
            .filter(ReportFile.status.in_(["ok", "warning"]))
            .group_by(VaccinationExecution.vaccine, VaccinationExecution.age_group)
            .all()
        )
        result = []
        for r in rows:
            plan = float(r.planned_total or 0)
            exec_ = float(r.executed_total or 0)
            pct = round(exec_ / plan * 100, 1) if plan > 0 else 0.0
            result.append({
                "vaccine": r.vaccine,
                "age_group": r.age_group,
                "planned": plan,
                "executed": exec_,
                "pct": pct,
                "org_count": r.org_count,
            })
        return result
    finally:
        session.close()


def get_facility_coverage(period_id: int) -> list[dict]:
    """
    Охоплення по кожному ЗОЗ (середній %).
    [{org_id, org_name, avg_pct, file_status}, ...]
    """
    session = get_session()
    try:
        from sqlalchemy import func
        rows = (
            session.query(
                Organization.id,
                Organization.name,
                ReportFile.status,
                func.avg(VaccinationExecution.pct).label("avg_pct"),
            )
            .join(ReportFile, ReportFile.org_id == Organization.id)
            .join(VaccinationExecution, VaccinationExecution.file_id == ReportFile.id)
            .filter(ReportFile.period_id == period_id)
            .filter(VaccinationExecution.planned > 0)
            .group_by(Organization.id, Organization.name, ReportFile.status)
            .all()
        )
        return [
            {"org_id": r.id, "org_name": r.name,
             "avg_pct": round(float(r.avg_pct or 0), 1),
             "file_status": r.status}
            for r in rows
        ]
    finally:
        session.close()


def get_stock_summary(period_id: int) -> list[dict]:
    """Залишки вакцин по регіону (сума по всіх ЗОЗ)."""
    session = get_session()
    try:
        from sqlalchemy import func
        rows = (
            session.query(
                StockData.vaccine,
                func.sum(StockData.stock_end).label("stock_end_total"),
                func.sum(StockData.used).label("used_total"),
            )
            .join(ReportFile)
            .filter(ReportFile.period_id == period_id)
            .filter(ReportFile.status.in_(["ok", "warning"]))
            .group_by(StockData.vaccine)
            .all()
        )
        return [
            {"vaccine": r.vaccine,
             "stock_end": float(r.stock_end_total or 0),
             "used": float(r.used_total or 0)}
            for r in rows
        ]
    finally:
        session.close()


def get_refusal_summary(period_id: int) -> list[dict]:
    """Відмови від щеплень по регіону."""
    session = get_session()
    try:
        from sqlalchemy import func
        rows = (
            session.query(
                Refusal.disease,
                func.sum(Refusal.count).label("total"),
            )
            .join(ReportFile)
            .filter(ReportFile.period_id == period_id)
            .filter(ReportFile.status.in_(["ok", "warning"]))
            .group_by(Refusal.disease)
            .all()
        )
        return [{"disease": r.disease, "count": int(r.total or 0)} for r in rows]
    finally:
        session.close()


def get_period_status(period_id: int, total_orgs: int) -> dict:
    """Загальний статус подання звітів за період."""
    session = get_session()
    try:
        files = session.query(ReportFile).filter_by(period_id=period_id).all()
        submitted = len(files)
        ok_count = sum(1 for f in files if f.status == "ok")
        warn_count = sum(1 for f in files if f.status == "warning")
        err_count = sum(1 for f in files if f.status == "error")
        return {
            "total": total_orgs,
            "submitted": submitted,
            "missing": max(0, total_orgs - submitted),
            "ok": ok_count,
            "warning": warn_count,
            "error": err_count,
            "pct": round(submitted / total_orgs * 100) if total_orgs > 0 else 0,
        }
    finally:
        session.close()


def get_all_files_for_period(period_id: int) -> list[ReportFile]:
    """Всі файли для вибраного місяця з організаціями."""
    session = get_session()
    try:
        files = (
            session.query(ReportFile)
            .filter_by(period_id=period_id)
            .all()
        )
        # Відв'язуємо від сесії щоб можна було використовувати поза нею
        for f in files:
            _ = f.organization  # eager load
        return files
    finally:
        session.close()
