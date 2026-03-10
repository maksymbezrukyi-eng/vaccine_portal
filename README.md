# 💉 Vaccine Portal — Житомирська область

Портал збору та аналізу щомісячних звітів про профілактичні щеплення.

## Що це

Веб-застосунок для ЦКПХ Житомирської області. Замінює ручний збір Excel-файлів від 104 ЗОЗ.

**Ключові функції:**
- 🔐 Авторизація (один пароль для ЦКПХ)
- 📂 Завантаження Excel-файлів ЗОЗ (формат Ф70) + автоматична валідація (20+ перевірок)
- 📊 Таблиця стану: хто здав / хто ні / статус помилок
- 📈 Дашборди: охоплення, рейтинг ЗОЗ, залишки вакцин, відмови
- 🏛️ Генерація зведеного файлу (Level 0) та Level 1 для МОЗ
- 💾 **Дані зберігаються між сесіями** (PostgreSQL / Supabase)

---

## Швидкий старт

### 1. Клонувати репозиторій

```bash
git clone https://github.com/YOUR_USERNAME/vaccine-portal.git
cd vaccine-portal
```

### 2. Встановити залежності

```bash
pip install -r requirements.txt
```

### 3. Налаштувати Supabase

1. Зареєструватись на [supabase.com](https://supabase.com) (безкоштовно)
2. Створити новий проект
3. Перейти в **Settings → Database → Connection string → URI**
4. Скопіювати URL підключення

### 4. Налаштувати secrets

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Відредагувати `.streamlit/secrets.toml`:
```toml
APP_PASSWORD = "ваш_надійний_пароль"
DATABASE_URL = "postgresql://postgres.xxx:password@..."
```

### 5. Запустити локально

```bash
streamlit run app.py
```

Застосунок відкриється на `http://localhost:8501`

---

## Деплой на Streamlit Cloud

1. Залити код на GitHub (`.streamlit/secrets.toml` — **не комітити!**)
2. Зайти на [share.streamlit.io](https://share.streamlit.io)
3. Підключити репозиторій, вказати `app.py` як головний файл
4. В **Advanced settings → Secrets** вставити вміст `secrets.toml`
5. Deploy!

---

## Перший запуск — ініціалізація ЗОЗ

Після першого входу:
1. Перейти на сторінку **📂 Завантаження**
2. В боковій панелі відкрити розділ **🏥 Управління списком ЗОЗ**
3. Завантажити файл `заклади_житомирськоі__області.xlsx`
4. Натиснути **Завантажити список ЗОЗ**

Таблиці БД створюються автоматично при першому запуску.

---

## Структура проекту

```
vaccine-portal/
├── app.py                    # Головна сторінка + авторизація
├── requirements.txt
├── .gitignore
├── .streamlit/
│   └── secrets.toml.example  # Шаблон (скопіюйте в secrets.toml)
├── core/
│   ├── __init__.py
│   ├── database.py           # SQLAlchemy моделі + підключення до Supabase
│   ├── parser.py             # Парсинг та валідація Excel Ф70
│   ├── service.py            # Бізнес-логіка: збереження, запити
│   └── level1.py             # Генерація Level 1 файлу
└── pages/
    ├── 1_📂_Завантаження.py  # Завантаження файлів ЗОЗ
    ├── 2_📊_Стан_подання.py  # Таблиця стану + деталі помилок
    ├── 3_📈_Дашборди.py      # Дашборди охоплення
    └── 4_🏛️_Звіти.py        # Генерація Level 0 та Level 1
```

---

## Структура БД

| Таблиця | Опис |
|---|---|
| `organizations` | Список ЗОЗ (104 Житомирська обл.) |
| `report_periods` | Звітні місяці |
| `report_files` | Завантажені файли + статус валідації |
| `vaccination_execution` | Дані виконання з Зведеного звіту |
| `stock_data` | Залишки вакцин |
| `refusals` | Відмови від щеплень |
| `birth_data` | Народжуваність / КДП / протипокази |
| `validation_issues` | Помилки та попередження |

---

## Пов'язані проекти

- **vaccine-merger** — попередня версія без БД: [vaccine-merger.streamlit.app](https://vaccine-merger.streamlit.app/)

---

*Розроблено спільно з ЦКПХ Житомирської області*
