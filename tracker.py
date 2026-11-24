import sqlite3
import calendar
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash

DB_FILE = "subscriptions.db"


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                cycle TEXT NOT NULL,
                next_date TEXT NOT NULL,
                is_trial INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)


def create_user(username, password):
    clean_user = username.strip().lower()
    if not clean_user or len(password) < 4:
        return False, "Username required and password must be at least 4 characters."

    pw_hash = generate_password_hash(password)
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (clean_user, pw_hash),
            )
        return True, "Account created!"
    except sqlite3.IntegrityError:
        return False, "That username is already taken."


def verify_user(username, password):
    clean_user = username.strip().lower()
    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (clean_user,)
        ).fetchone()

    if user and check_password_hash(user["password_hash"], password):
        return dict(user)
    return None


def add_months(source_date, months):
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    day = min(source_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def roll_forward_date(next_date_str, cycle, is_trial=False):
    if is_trial:
        return next_date_str

    today = datetime.now().date()
    due_date = datetime.strptime(next_date_str, "%Y-%m-%d").date()
    months_to_add = 12 if cycle == "yearly" else 1

    while due_date < today:
        due_date = add_months(due_date, months_to_add)

    return due_date.strftime("%Y-%m-%d")


def load_subscriptions(user_id):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM subscriptions WHERE user_id = ?", (user_id,)
        ).fetchall()

        subs = []
        for row in rows:
            sub = dict(row)
            sub["is_trial"] = bool(sub["is_trial"])
            updated_date = roll_forward_date(
                sub["next_date"], sub["cycle"], sub["is_trial"]
            )
            if updated_date != sub["next_date"]:
                sub["next_date"] = updated_date
                conn.execute(
                    "UPDATE subscriptions SET next_date = ? WHERE id = ?",
                    (updated_date, sub["id"]),
                )
            subs.append(sub)
    return subs


def add_subscription(user_id, name, price, cycle, next_date, is_trial=False):
    clean_name = name.strip()
    clean_price = max(0.0, float(price))
    if not clean_name:
        return

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO subscriptions (user_id, name, price, cycle, next_date, is_trial)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, clean_name, clean_price, cycle.lower(), next_date, int(bool(is_trial))),
        )


def update_subscription(user_id, sub_id, name, price, cycle, next_date, is_trial=False):
    clean_name = name.strip()
    clean_price = max(0.0, float(price))
    if not clean_name:
        return

    with get_db() as conn:
        conn.execute(
            """
            UPDATE subscriptions
            SET name = ?, price = ?, cycle = ?, next_date = ?, is_trial = ?
            WHERE id = ? AND user_id = ?
            """,
            (clean_name, clean_price, cycle.lower(), next_date, int(bool(is_trial)), sub_id, user_id),
        )


def delete_subscription(user_id, sub_id):
    with get_db() as conn:
        conn.execute(
            "DELETE FROM subscriptions WHERE id = ? AND user_id = ?",
            (sub_id, user_id),
        )


def calculate_monthly_total(subscriptions):
    total = 0.0
    for sub in subscriptions:
        if sub.get("is_trial", False):
            continue
        if sub["cycle"] == "yearly":
            total += sub["price"] / 12
        else:
            total += sub["price"]
    return round(total, 2)


def get_days_until_due(next_date_str):
    today = datetime.now().date()
    due_date = datetime.strptime(next_date_str, "%Y-%m-%d").date()
    return (due_date - today).days