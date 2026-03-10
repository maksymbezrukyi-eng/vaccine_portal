"""
Сторінка 2: Стан подання звітів
"""
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Стан подання", page_icon="📊", layout="wide")

if not st.session_state.get("authenticated"):
    st.error("⛔ Будь ласка, увійдіть через головну сторінку.")
    st.stop()

from core import (
    get_session, get_or_create_period,
    Organization, ReportFile, ValidationIssue,
)

st.title("📊 Стан подання звітів")
st.divider()

# ─── Сайдбар ─────────────────────────────────────────────────────────
with st.sidebar:
    st.header("📅 Звітний місяць")
    MONTHS = {1:"Січень",2:"Лютий",3:"Березень",4:"Квітень",5:"Травень",
              6:"Червень",7:"Липень",8:"Серпень",9:"Вересень",
              10:"Жовтень",11:"Листопад",12:"Грудень"}
    report_year  = st.selectbox("Рік:", range(2024, 2032), index=2)
    report_month = st.selectbox("Місяць:", list(MONTHS.keys()),
                                format_func=lambda x: MONTHS[x], index=0)
    period_label = f"{MONTHS[report_month]} {report_year}"
    st.divider()
    if st.button("🚪 Вийти", use_container_width=True):
        st.session_state.clear()
        st.rerun()

period = get_or_create_period(report_year, report_month)
period_id = period.id

# ─── Дані ─────────────────────────────────────────────────────────────
session = get_session()
try:
    all_orgs = session.query(Organization).filter_by(is_active=True).order_by(Organization.seq_number, Organization.name).all()
    total = len(all_orgs)

    # Файли за цей місяць
    files_map: dict[int, ReportFile] = {}
    for rf in session.query(ReportFile).filter_by(period_id=period_id).all():
        files_map[rf.org_id] = rf

    submitted  = len(files_map)
    missing    = total - submitted
    ok_count   = sum(1 for f in files_map.values() if f.status == "ok")
    warn_count = sum(1 for f in files_map.values() if f.status == "warning")
    err_count  = sum(1 for f in files_map.values() if f.status == "error")
    pct        = round(submitted / total * 100) if total > 0 else 0

finally:
    session.close()

# ─── Метрики ──────────────────────────────────────────────────────────
st.subheader(f"📅 {period_label}")
m1,m2,m3,m4,m5 = st.columns(5)
m1.metric("🏥 Всього ЗОЗ",      total)
m2.metric("📥 Подали звіт",      submitted)
m3.metric("⏳ Не подали",        missing, delta=f"-{missing}" if missing else None, delta_color="inverse")
m4.metric("🟢 Без помилок",      ok_count)
m5.metric("🔴 З помилками",      err_count)

st.progress(pct / 100, text=f"Подано {submitted} з {total} закладів ({pct}%)")

if missing == 0 and total > 0:
    st.success("🎉 Усі заклади подали звіти!")
elif missing > 0:
    st.warning(f"⚠️ Ще не подали звіт: **{missing}** заклад(ів)")

st.divider()

# ─── Фільтри ──────────────────────────────────────────────────────────
col_f1, col_f2 = st.columns(2)
with col_f1:
    filter_status = st.multiselect(
        "Фільтр за статусом:",
        ["🟢 OK", "🟡 Попередження", "🔴 Помилки", "⏳ Не подали"],
        default=["🟢 OK", "🟡 Попередження", "🔴 Помилки", "⏳ Не подали"],
    )
with col_f2:
    search_name = st.text_input("🔍 Пошук по назві:", placeholder="Введіть частину назви...")

# ─── Таблиця ──────────────────────────────────────────────────────────
STATUS_MAP = {"ok":"🟢 OK", "warning":"🟡 Попередження", "error":"🔴 Помилки"}

session = get_session()
try:
    # Заново читаємо з сесією щоб мати повні об'єкти
    all_orgs = session.query(Organization).filter_by(is_active=True)\
        .order_by(Organization.seq_number, Organization.name).all()
    files_map2: dict[int, ReportFile] = {}
    for rf in session.query(ReportFile).filter_by(period_id=period_id).all():
        files_map2[rf.org_id] = rf

    rows = []
    for org in all_orgs:
        rf = files_map2.get(org.id)
        if rf:
            status_str = STATUS_MAP.get(rf.status, "—")
            row = {
                "#": org.seq_number or "",
                "Заклад": org.name,
                "ЄДРПОУ": org.edrpou or "—",
                "Статус": status_str,
                "Помилки": rf.error_count,
                "Попередж.": rf.warning_count,
                "Файл": rf.filename or "—",
                "Дата подачі": rf.uploaded_at.strftime("%d.%m.%Y %H:%M") if rf.uploaded_at else "—",
            }
        else:
            status_str = "⏳ Не подали"
            row = {
                "#": org.seq_number or "",
                "Заклад": org.name,
                "ЄДРПОУ": org.edrpou or "—",
                "Статус": status_str,
                "Помилки": 0,
                "Попередж.": 0,
                "Файл": "—",
                "Дата подачі": "—",
            }
        rows.append(row)

finally:
    session.close()

df = pd.DataFrame(rows)

# Застосовуємо фільтри
if filter_status:
    df = df[df["Статус"].isin(filter_status)]
if search_name:
    df = df[df["Заклад"].str.contains(search_name, case=False, na=False)]

st.markdown(f"Показано **{len(df)}** записів")
st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "#": st.column_config.NumberColumn(width="small"),
        "Помилки": st.column_config.NumberColumn(width="small"),
        "Попередж.": st.column_config.NumberColumn(width="small"),
        "Статус": st.column_config.TextColumn(width="medium"),
    }
)

# ─── Деталі помилок ──────────────────────────────────────────────────
st.divider()
st.subheader("🔍 Деталі помилок по файлах")

session = get_session()
try:
    problem_files = (
        session.query(ReportFile, Organization)
        .join(Organization, ReportFile.org_id == Organization.id)
        .filter(ReportFile.period_id == period_id)
        .filter(ReportFile.error_count > 0)
        .order_by(Organization.name)
        .all()
    )

    if not problem_files:
        st.success("✅ Файлів з критичними помилками немає!")
    else:
        for rf, org in problem_files:
            issues = session.query(ValidationIssue).filter_by(file_id=rf.id).all()
            errors = [i.message for i in issues if i.severity == "error"]
            warnings = [i.message for i in issues if i.severity == "warning"]

            with st.expander(f"🔴  {org.name}  |  ЄДРПОУ: {org.edrpou or '—'}"):
                if errors:
                    st.error("**Критичні помилки:**")
                    for e in errors:
                        st.write(f"• {e}")
                if warnings:
                    st.warning("**Попередження:**")
                    for w in warnings:
                        st.write(f"• {w}")
finally:
    session.close()

# Попередження (окремо)
st.subheader("🟡 Файли з попередженнями")
session = get_session()
try:
    warn_files = (
        session.query(ReportFile, Organization)
        .join(Organization, ReportFile.org_id == Organization.id)
        .filter(ReportFile.period_id == period_id)
        .filter(ReportFile.error_count == 0)
        .filter(ReportFile.warning_count > 0)
        .order_by(Organization.name)
        .all()
    )
    if not warn_files:
        st.info("ℹ️ Файлів лише з попередженнями (без критичних помилок) немає.")
    else:
        for rf, org in warn_files:
            issues = session.query(ValidationIssue).filter_by(
                file_id=rf.id, severity="warning"
            ).all()
            with st.expander(f"🟡  {org.name}"):
                for i in issues:
                    st.write(f"• {i.message}")
finally:
    session.close()
