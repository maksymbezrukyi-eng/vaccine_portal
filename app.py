"""
app.py — головний файл vaccine-portal
Портал збору та аналізу звітів про вакцинацію (Житомирська область)
"""
import streamlit as st

# ─── Налаштування сторінки ────────────────────────────────────────────
st.set_page_config(
    page_title="Vaccine Portal — Житомирська область",
    page_icon="💉",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Авторизація ─────────────────────────────────────────────────────
def check_auth() -> bool:
    """Перевіряє пароль. Повертає True якщо авторизовано."""
    try:
        correct_password = st.secrets["APP_PASSWORD"]
    except Exception:
        st.error("❌ APP_PASSWORD не налаштовано у .streamlit/secrets.toml")
        st.code("""
# .streamlit/secrets.toml
APP_PASSWORD = "your_password_here"
DATABASE_URL = "postgresql://..."
        """)
        st.stop()
        return False

    if st.session_state.get("authenticated"):
        return True

    st.title("💉 Vaccine Portal")
    st.subheader("Система збору звітів про вакцинацію — Житомирська область")
    st.divider()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        password = st.text_input("🔐 Введіть пароль доступу:", type="password",
                                  placeholder="Пароль...")
        if st.button("Увійти", type="primary", use_container_width=True):
            if password == correct_password:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("❌ Невірний пароль")
    return False


if not check_auth():
    st.stop()

# ─── Ініціалізація БД (один раз) ─────────────────────────────────────
if not st.session_state.get("db_initialized"):
    try:
        from core import init_db
        init_db()
        st.session_state["db_initialized"] = True
    except Exception as e:
        st.error(f"❌ Помилка підключення до БД: {e}")
        st.info("Перевірте DATABASE_URL у .streamlit/secrets.toml")
        st.stop()

# ─── Головна сторінка ────────────────────────────────────────────────
st.title("💉 Vaccine Portal")
st.markdown("**Система збору та аналізу звітів про профілактичні щеплення**")
st.caption("Житомирська область · ЦКПХ")
st.divider()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("""
    ### 📂 Завантаження
    Завантажте Excel-файли ЗОЗ.  
    Система автоматично перевірить і збереже дані.
    """)
    if st.button("Перейти →", key="go_upload", use_container_width=True):
        st.switch_page("pages/1_📂_Завантаження.py")

with col2:
    st.markdown("""
    ### 📊 Стан подання
    Хто здав звіт, хто ні.  
    Статус по кожному ЗОЗ.
    """)
    if st.button("Перейти →", key="go_status", use_container_width=True):
        st.switch_page("pages/2_📊_Стан_подання.py")

with col3:
    st.markdown("""
    ### 📈 Дашборди
    Охоплення, рейтинг ЗОЗ,  
    залишки вакцин, відмови.
    """)
    if st.button("Перейти →", key="go_dash", use_container_width=True):
        st.switch_page("pages/3_📈_Дашборди.py")

with col4:
    st.markdown("""
    ### 🏛️ Звіти
    Зведений файл (Level 0)  
    та Level 1 для МОЗ.
    """)
    if st.button("Перейти →", key="go_reports", use_container_width=True):
        st.switch_page("pages/4_🏛️_Звіти.py")

st.divider()

# Швидка статистика
try:
    from core import get_session, ReportPeriod, ReportFile, Organization
    session = get_session()
    try:
        total_orgs = session.query(Organization).filter_by(is_active=True).count()
        total_periods = session.query(ReportPeriod).count()
        total_files = session.query(ReportFile).count()
        ok_files = session.query(ReportFile).filter_by(status="ok").count()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🏥 ЗОЗ у системі", total_orgs)
        m2.metric("📅 Звітних місяців", total_periods)
        m3.metric("📁 Файлів завантажено", total_files)
        m4.metric("🟢 Файлів без помилок", ok_files)
    finally:
        session.close()
except Exception as e:
    st.info("📊 Статистика буде доступна після підключення до БД.")

# Кнопка виходу в сайдбарі
with st.sidebar:
    st.markdown("---")
    if st.button("🚪 Вийти", use_container_width=True):
        st.session_state.clear()
        st.rerun()
