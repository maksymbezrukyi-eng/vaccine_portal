"""
Сторінка 1: Завантаження файлів ЗОЗ
"""
import io
import streamlit as st
import pandas as pd
from datetime import datetime

# Перевірка авторизації
if not st.session_state.get("authenticated"):
    st.error("⛔ Будь ласка, увійдіть через головну сторінку.")
    st.stop()

from core import (
    get_session, parse_file, save_report_file,
    find_org_by_name, find_org_by_edrpou,
    get_or_create_period, Organization, ReportFile,
    seed_organizations, init_db,
)

st.title("📂 Завантаження файлів ЗОЗ")
st.markdown("Завантажте Excel-файли від закладів охорони здоров'я.")
st.divider()

# ─── Ліва панель: налаштування ───────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Параметри")

    MONTHS = {1:"Січень",2:"Лютий",3:"Березень",4:"Квітень",5:"Травень",
              6:"Червень",7:"Липень",8:"Серпень",9:"Вересень",
              10:"Жовтень",11:"Листопад",12:"Грудень"}

    report_year  = st.selectbox("Рік:", range(2024, 2032), index=2)
    report_month = st.selectbox("Місяць:", list(MONTHS.keys()),
                                format_func=lambda x: MONTHS[x], index=0)
    period_label = f"{MONTHS[report_month]} {report_year}"

    st.divider()

    # Ініціалізація ЗОЗ зі списку
    with st.expander("🏥 Управління списком ЗОЗ"):
        uploaded_list = st.file_uploader(
            "Оновити список ЗОЗ (Excel):",
            type=["xlsx"], key="org_list_uploader",
            help="Файл: заклади_житомирськоі__області.xlsx"
        )
        if uploaded_list and st.button("Завантажити список ЗОЗ"):
            try:
                df = pd.read_excel(uploaded_list, header=0)
                df.columns = ["seq", "name"]
                orgs = [
                    {"seq_number": int(row["seq"]), "name": str(row["name"]).strip(),
                     "region": "Житомирська"}
                    for _, row in df.iterrows()
                    if pd.notna(row["name"])
                ]
                # Додаємо першу строку яка є заголовком файлу але першим записом
                added = seed_organizations(orgs)
                st.success(f"✅ Додано {added} нових ЗОЗ")
            except Exception as e:
                st.error(f"❌ Помилка: {e}")

    st.divider()
    if st.button("🚪 Вийти", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ─── Основний контент ────────────────────────────────────────────────
st.subheader(f"📅 Звітний місяць: **{period_label}**")

# Отримуємо список всіх ЗОЗ для відображення прогресу
session = get_session()
try:
    total_orgs = session.query(Organization).filter_by(is_active=True).count()
    # Отримуємо або створюємо звітний період
    period = get_or_create_period(report_year, report_month)
    period_id = period.id
    # Кількість вже завантажених файлів за цей місяць
    existing_files = session.query(ReportFile).filter_by(period_id=period_id).count()
finally:
    session.close()

# Метрики прогресу
if total_orgs > 0:
    pct = round(existing_files / total_orgs * 100)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🏥 Всього ЗОЗ", total_orgs)
    m2.metric("📥 Вже здали", existing_files)
    m3.metric("⏳ Не здали", max(0, total_orgs - existing_files))
    m4.metric("✅ Виконання", f"{pct}%")
    st.progress(pct / 100, text=f"Подано {existing_files} з {total_orgs} закладів ({pct}%)")
    st.divider()

# ─── Завантаження файлів ─────────────────────────────────────────────
st.subheader("📎 Оберіть файли для завантаження")
st.info("💡 Утримуйте **Ctrl** (або **Cmd** на Mac) для вибору кількох файлів одночасно.")

uploaded_files = st.file_uploader(
    "Файли Excel (.xlsx):",
    type=["xlsx"],
    accept_multiple_files=True,
    key="file_uploader",
)

if uploaded_files:
    st.markdown(f"Вибрано **{len(uploaded_files)}** файл(ів). Натисніть «Завантажити та перевірити».")

    if st.button("▶️ Завантажити та перевірити", type="primary", use_container_width=True):

        progress_bar = st.progress(0, text="Обробка файлів...")
        results_data = []
        errors_list  = []
        session = get_session()

        try:
            for i, uf in enumerate(uploaded_files):
                fname = uf.name
                fbytes = uf.read()

                # Парсинг та валідація
                parse_res = parse_file(fbytes, fname)

                # Пошук організації в БД
                org = None
                if parse_res.edrpou and parse_res.edrpou != "—":
                    org = find_org_by_edrpou(session, parse_res.edrpou)
                if not org and parse_res.name and parse_res.name != "—":
                    org = find_org_by_name(session, parse_res.name)

                matched_org = org.name if org else "⚠️ Не знайдено в реєстрі"
                matched_id  = org.id if org else None

                # Якщо ЗОЗ не знайдено — додаємо як новий
                if not org and parse_res.name != "—":
                    try:
                        new_org = Organization(
                            name=parse_res.name,
                            edrpou=parse_res.edrpou if parse_res.edrpou != "—" else None,
                            region="Житомирська",
                        )
                        session.add(new_org)
                        session.flush()
                        matched_id = new_org.id
                        matched_org = f"🆕 {parse_res.name} (додано)"
                    except Exception:
                        session.rollback()

                # Якщо знайдено і ЄДрпоу тепер відомий — оновлюємо
                if org and org.edrpou is None and parse_res.edrpou not in ("—", None):
                    org.edrpou = parse_res.edrpou
                    session.flush()

                # Зберігаємо в БД
                save_ok = False
                if matched_id:
                    try:
                        rf = save_report_file(
                            session=session,
                            org_id=matched_id,
                            period_id=period_id,
                            filename=fname,
                            file_bytes=fbytes,
                            parse_result=parse_res,
                        )
                        save_ok = True
                    except Exception as e:
                        errors_list.append(f"{fname}: {e}")

                results_data.append({
                    "Файл": fname,
                    "Заклад (з файлу)": parse_res.name,
                    "ЄДРПОУ": parse_res.edrpou,
                    "Статус": parse_res.status_emoji,
                    "Помилки": len(parse_res.errors),
                    "Попередж.": len(parse_res.warnings),
                    "Збережено": "✅" if save_ok else "❌",
                    "Реєстр": matched_org,
                })

                progress_bar.progress(
                    (i + 1) / len(uploaded_files),
                    text=f"Оброблено {i+1}/{len(uploaded_files)}: {fname}"
                )

            session.commit()

        except Exception as e:
            session.rollback()
            st.error(f"❌ Критична помилка: {e}")
        finally:
            session.close()

        # Результати
        progress_bar.empty()
        st.success(f"✅ Оброблено {len(results_data)} файл(ів)!")

        df_res = pd.DataFrame(results_data)
        st.dataframe(df_res, use_container_width=True, hide_index=True)

        if errors_list:
            with st.expander("⚠️ Помилки збереження"):
                for e in errors_list:
                    st.write(f"• {e}")

        # Детальний розбір проблемних файлів
        problem_files = [r for r in results_data if r["Помилки"] > 0 or r["Попередж."] > 0]
        if problem_files:
            st.divider()
            st.subheader("🔍 Файли з помилками або попередженнями")
            st.caption("Ці файли збережено в БД, але потребують уваги ЦКПХ.")

            # Повторно парсимо для деталей (з тимчасового сховища)
            for uf in uploaded_files:
                uf.seek(0)
                fbytes = uf.read()
                pr = parse_file(fbytes, uf.name)
                if pr.errors or pr.warnings:
                    with st.expander(f"{pr.status_emoji}  {uf.name}  |  {pr.name}"):
                        if pr.errors:
                            st.error("**Критичні помилки:**")
                            for e in pr.errors:
                                st.write(f"• {e}")
                        if pr.warnings:
                            st.warning("**Попередження:**")
                            for w in pr.warnings:
                                st.write(f"• {w}")

# ─── Поточний стан за вибраний місяць ────────────────────────────────
st.divider()
st.subheader(f"📋 Завантажені файли за {period_label}")

session = get_session()
try:
    files = (
        session.query(ReportFile, Organization)
        .join(Organization, ReportFile.org_id == Organization.id)
        .filter(ReportFile.period_id == period_id)
        .order_by(Organization.name)
        .all()
    )
    if files:
        rows = []
        for rf, org in files:
            rows.append({
                "Заклад": org.name,
                "ЄДРПОУ": org.edrpou or "—",
                "Файл": rf.filename or "—",
                "Статус": {"ok": "🟢 OK", "warning": "🟡 Попередж.", "error": "🔴 Помилки"}.get(rf.status, "—"),
                "Помилки": rf.error_count,
                "Попередж.": rf.warning_count,
                "Завантажено": rf.uploaded_at.strftime("%d.%m %H:%M") if rf.uploaded_at else "—",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(f"ℹ️ Файлів за {period_label} ще немає.")
finally:
    session.close()
