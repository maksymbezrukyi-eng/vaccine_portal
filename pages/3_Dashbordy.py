"""
Сторінка 3: Дашборди — охоплення, рейтинг, залишки, відмови
"""
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Дашборди", page_icon="📈", layout="wide")
import plotly.graph_objects as go

if not st.session_state.get("authenticated"):
    st.error("⛔ Будь ласка, увійдіть через головну сторінку.")
    st.stop()

from core import (
    get_or_create_period,
    get_coverage_data, get_facility_coverage,
    get_stock_summary, get_refusal_summary,
    get_period_status, get_session, Organization,
)

st.title("📈 Дашборди")
st.divider()

# ─── Сайдбар ──────────────────────────────────────────────────────────
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

# ─── Завантаження даних ────────────────────────────────────────────────
session = get_session()
total_orgs = session.query(Organization).filter_by(is_active=True).count()
session.close()

status = get_period_status(period_id, total_orgs)
coverage = get_coverage_data(period_id)
facility_cov = get_facility_coverage(period_id)
stocks = get_stock_summary(period_id)
refusals = get_refusal_summary(period_id)

if status["submitted"] == 0:
    st.warning(f"ℹ️ За {period_label} ще немає завантажених файлів.")
    st.stop()

st.subheader(f"📅 {period_label} · Подано: {status['submitted']}/{status['total']} ЗОЗ")

# ─── Вкладки дашбордів ────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "💉 Охоплення", "🏆 Рейтинг ЗОЗ", "🏥 Залишки вакцин", "❌ Відмови та протипокази"
])

# ═══════════════════════════════════════════════════════════════════════
# ВКЛ 1: ОХОПЛЕННЯ
# ═══════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("💉 Охоплення щепленнями по регіону")

    if not coverage:
        st.info("Немає даних охоплення за цей місяць.")
    else:
        # Фільтруємо рядки з планом > 0
        df_cov = pd.DataFrame([c for c in coverage if c["planned"] > 0])

        if df_cov.empty:
            st.info("Немає даних з плановими показниками.")
        else:
            # Ключові показники
            KEY_VACCINES = [
                "КДП3 до 1 р", "КДП4 18 міс", "Поліо3", "Поліо4",
                "Гепатит В3", "КПК1", "КПК2", "Hib3",
            ]

            # Компактна назва
            df_cov["label"] = df_cov.apply(
                lambda r: f"{r['vaccine']} ({r['age_group']})" if r["age_group"] else r["vaccine"],
                axis=1
            )

            # Фільтрація для відображення
            max_show = st.slider("Показати вакцин:", 5, min(50, len(df_cov)), 20)
            df_show = df_cov.sort_values("pct").tail(max_show)

            colors_list = [
                "#2ECC71" if p >= 95 else "#F39C12" if p >= 85 else "#E74C3C"
                for p in df_show["pct"]
            ]
            fig = go.Figure(go.Bar(
                x=df_show["pct"],
                y=df_show["label"],
                orientation="h",
                marker_color=colors_list,
                text=[f"{p}%" for p in df_show["pct"]],
                textposition="outside",
                customdata=df_show[["planned", "executed"]].values,
                hovertemplate="<b>%{y}</b><br>%{x}%<br>План: %{customdata[0]:.0f}  Виконано: %{customdata[1]:.0f}<extra></extra>",
            ))
            fig.add_vline(x=95, line_dash="dash", line_color="green", annotation_text="95%")
            fig.add_vline(x=85, line_dash="dash", line_color="orange", annotation_text="85%")
            fig.update_layout(
                xaxis=dict(range=[0, 130]),
                xaxis_title="% виконання",
                height=max(400, len(df_show) * 30),
                margin=dict(l=10, r=90, t=20, b=40),
                plot_bgcolor="white",
            )
            st.plotly_chart(fig, use_container_width=True)

            lc1, lc2, lc3 = st.columns(3)
            lc1.success("🟢 ≥ 95% — виконано")
            lc2.warning("🟡 85–95% — потребує уваги")
            lc3.error("🔴 < 85% — критично")

            # Таблиця
            with st.expander("📋 Таблиця охоплення"):
                df_table = df_cov[["label", "planned", "executed", "pct"]].copy()
                df_table.columns = ["Вакцина / Вік", "План", "Виконано", "%"]
                df_table = df_table.sort_values("%", ascending=False)
                st.dataframe(df_table, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════
# ВКЛ 2: РЕЙТИНГ ЗОЗ
# ═══════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("🏆 Рейтинг закладів за % охоплення")

    if not facility_cov:
        st.info("Немає даних для рейтингу.")
    else:
        df_r = pd.DataFrame(facility_cov).sort_values("avg_pct", ascending=False).reset_index(drop=True)
        df_r.index += 1

        colors_r = [
            "#2ECC71" if p >= 95 else "#F39C12" if p >= 85 else "#E74C3C"
            for p in df_r["avg_pct"]
        ]
        fig_r = go.Figure(go.Bar(
            x=df_r["avg_pct"],
            y=df_r["org_name"],
            orientation="h",
            marker_color=colors_r,
            text=[f"{p}%" for p in df_r["avg_pct"]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Середній %: %{x}<extra></extra>",
        ))
        fig_r.add_vline(x=95, line_dash="dash", line_color="green")
        fig_r.add_vline(x=85, line_dash="dash", line_color="orange")
        fig_r.update_layout(
            xaxis=dict(range=[0, 120]),
            yaxis=dict(autorange="reversed"),
            height=max(400, len(df_r) * 40),
            margin=dict(l=10, r=90, t=20, b=40),
            plot_bgcolor="white",
        )
        st.plotly_chart(fig_r, use_container_width=True)

        df_r["Місце"] = range(1, len(df_r) + 1)
        df_r["Статус"] = df_r["avg_pct"].apply(
            lambda x: "🟢 OK" if x >= 95 else ("🟡 Увага" if x >= 85 else "🔴 Критично")
        )
        st.dataframe(
            df_r[["Місце", "org_name", "avg_pct", "Статус"]].rename(
                columns={"org_name": "Заклад", "avg_pct": "Середній %"}
            ),
            use_container_width=True, hide_index=True,
        )


# ═══════════════════════════════════════════════════════════════════════
# ВКЛ 3: ЗАЛИШКИ ВАКЦИН
# ═══════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("🏥 Залишки вакцин (сума по регіону)")

    if not stocks:
        st.info("Немає даних залишків за цей місяць.")
    else:
        thr = st.number_input(
            "⚙️ Поріг критичного залишку (доз):", min_value=0, max_value=10000, value=50, step=10
        )
        df_s = pd.DataFrame([s for s in stocks if s["stock_end"] > 0 or s["used"] > 0])
        df_s = df_s.sort_values("stock_end", ascending=True)

        if not df_s.empty:
            cs = ["#E74C3C" if v <= thr else "#3498DB" for v in df_s["stock_end"]]
            fig_s = go.Figure(go.Bar(
                x=df_s["stock_end"],
                y=df_s["vaccine"],
                orientation="h",
                marker_color=cs,
                text=df_s["stock_end"].astype(int),
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>Залишок: %{x} доз<extra></extra>",
            ))
            fig_s.add_vline(
                x=thr, line_dash="dash", line_color="red",
                annotation_text=f"Критично ({thr})", annotation_position="top right",
            )
            fig_s.update_layout(
                height=max(400, len(df_s) * 30),
                margin=dict(l=10, r=90, t=20, b=40),
                plot_bgcolor="white",
            )
            st.plotly_chart(fig_s, use_container_width=True)

            crit = df_s[df_s["stock_end"] <= thr]
            if not crit.empty:
                st.error(f"🚨 Критично мало ({thr} доз і менше):")
                st.dataframe(
                    crit.rename(columns={"vaccine": "Вакцина", "stock_end": "Залишок (доз)", "used": "Витрачено (доз)"}),
                    use_container_width=True, hide_index=True,
                )


# ═══════════════════════════════════════════════════════════════════════
# ВКЛ 4: ВІДМОВИ ТА ПРОТИПОКАЗИ
# ═══════════════════════════════════════════════════════════════════════
with tab4:
    st.subheader("❌ Відмови та протипокази від щеплень")

    cr, cc = st.columns(2)

    with cr:
        st.markdown("**Відмови від щеплень**")
        if refusals:
            df_ref = pd.DataFrame([r for r in refusals if r["count"] > 0])
            if not df_ref.empty:
                fig_ref = px.bar(
                    df_ref, x="count", y="disease", orientation="h",
                    color="count",
                    color_continuous_scale=["#FFF3CD", "#E74C3C"],
                    text="count",
                )
                fig_ref.update_traces(textposition="outside")
                fig_ref.update_layout(
                    height=300, showlegend=False,
                    plot_bgcolor="white",
                    margin=dict(l=10, r=60, t=10, b=20),
                )
                fig_ref.update_coloraxes(showscale=False)
                st.plotly_chart(fig_ref, use_container_width=True)
                st.dataframe(
                    df_ref.rename(columns={"disease": "Нозологія", "count": "Відмов"})
                    .sort_values("Відмов", ascending=False),
                    use_container_width=True, hide_index=True,
                )
            else:
                st.info("Відмов не зареєстровано.")
        else:
            st.info("Відмов не зареєстровано.")

    with cc:
        st.markdown("**Медичні протипокази**")
        # Підтягуємо з BirthData
        from core.database import BirthData, ReportFile as RF
        session = get_session()
        try:
            bd_rows = (
                session.query(BirthData)
                .join(RF, BirthData.file_id == RF.id)
                .filter(RF.period_id == period_id)
                .all()
            )
            temp_total = sum(b.temp_ci for b in bd_rows)
            perm_total = sum(b.perm_ci for b in bd_rows)
        finally:
            session.close()

        if temp_total + perm_total > 0:
            fig_p = px.pie(
                values=[temp_total, perm_total],
                names=["Тимчасові", "Постійні"],
                color_discrete_sequence=["#F39C12", "#E74C3C"],
                hole=0.4,
            )
            fig_p.update_traces(textposition="inside", textinfo="percent+label+value")
            fig_p.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_p, use_container_width=True)

            p1, p2, p3 = st.columns(3)
            p1.metric("Тимчасові", int(temp_total))
            p2.metric("Постійні", int(perm_total))
            p3.metric("Всього", int(temp_total + perm_total))
        else:
            st.info("Протипоказів не зареєстровано.")
