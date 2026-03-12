import sqlite3
from datetime import datetime

from config import DB_PATH


class Database:
    def __init__(self, path: str = DB_PATH):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        cur = self.conn.cursor()

        # Пользователи
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                name TEXT,
                phone TEXT
            )
            """
        )

        # Рабочие дни
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS work_days (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE NOT NULL, -- YYYY-MM-DD
                is_closed INTEGER DEFAULT 0
            )
            """
        )

        # Временные слоты
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS time_slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day_id INTEGER NOT NULL,
                time TEXT NOT NULL, -- HH:MM
                is_available INTEGER DEFAULT 1,
                FOREIGN KEY (day_id) REFERENCES work_days(id) ON DELETE CASCADE
            )
            """
        )

        # Записи
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                slot_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                appointment_datetime TEXT NOT NULL, -- ISO
                status TEXT DEFAULT 'active', -- active/cancelled
                reminder_job_id TEXT,
                reminder_time TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (slot_id) REFERENCES time_slots(id)
            )
            """
        )

        self.conn.commit()

    # ---------- Пользователи ----------

    def get_or_create_user(self, telegram_id: int, username: str | None = None):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = cur.fetchone()
        if row:
            return row

        cur.execute(
            "INSERT INTO users (telegram_id, username) VALUES (?, ?)",
            (telegram_id, username),
        )
        self.conn.commit()
        cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        return cur.fetchone()

    def update_user_contact(self, telegram_id: int, name: str, phone: str):
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE users SET name = ?, phone = ? WHERE telegram_id = ?",
            (name, phone, telegram_id),
        )
        self.conn.commit()

    def get_user_by_telegram_id(self, telegram_id: int):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        return cur.fetchone()

    # ---------- Дни и слоты ----------

    def get_or_create_day(self, date_str: str):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM work_days WHERE date = ?", (date_str,))
        row = cur.fetchone()
        if row:
            return row

        cur.execute(
            "INSERT INTO work_days (date, is_closed) VALUES (?, 0)",
            (date_str,),
        )
        self.conn.commit()
        cur.execute("SELECT * FROM work_days WHERE date = ?", (date_str,))
        return cur.fetchone()

    def add_day(self, date_str: str):
        return self.get_or_create_day(date_str)

    def close_day(self, date_str: str):
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE work_days SET is_closed = 1 WHERE date = ?",
            (date_str,),
        )
        cur.execute(
            """
            UPDATE time_slots
            SET is_available = 0
            WHERE day_id = (SELECT id FROM work_days WHERE date = ?)
            """,
            (date_str,),
        )
        self.conn.commit()

    def add_time_slot(self, date_str: str, time_str: str):
        day = self.get_or_create_day(date_str)
        day_id = day["id"]
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT * FROM time_slots
            WHERE day_id = ? AND time = ?
            """,
            (day_id, time_str),
        )
        if cur.fetchone():
            return
        cur.execute(
            "INSERT INTO time_slots (day_id, time, is_available) VALUES (?, ?, 1)",
            (day_id, time_str),
        )
        self.conn.commit()

    def delete_time_slot(self, slot_id: int):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM time_slots WHERE id = ?", (slot_id,))
        self.conn.commit()

    def get_day_slots(self, date_str: str, only_available: bool = False):
        cur = self.conn.cursor()
        q = """
            SELECT ts.*, wd.date, wd.is_closed
            FROM time_slots ts
            JOIN work_days wd ON wd.id = ts.day_id
            WHERE wd.date = ?
        """
        params = [date_str]
        if only_available:
            q += " AND ts.is_available = 1"
        q += " ORDER BY time"
        cur.execute(q, params)
        return cur.fetchall()

    def get_available_days_in_range(self, start_date: str, end_date: str):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT wd.date
            FROM work_days wd
            JOIN time_slots ts ON ts.day_id = wd.id
            WHERE wd.date BETWEEN ? AND ?
              AND wd.is_closed = 0
              AND ts.is_available = 1
            ORDER BY wd.date
            """,
            (start_date, end_date),
        )
        return [r["date"] for r in cur.fetchall()]

    def get_slot_by_id(self, slot_id: int):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT ts.*, wd.date
            FROM time_slots ts
            JOIN work_days wd ON wd.id = ts.day_id
            WHERE ts.id = ?
            """,
            (slot_id,),
        )
        return cur.fetchone()

    def set_slot_available(self, slot_id: int, available: bool):
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE time_slots SET is_available = ? WHERE id = ?",
            (1 if available else 0, slot_id),
        )
        self.conn.commit()

    # ---------- Записи ----------

    def user_has_active_booking(self, telegram_id: int) -> bool:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT b.*
            FROM bookings b
            JOIN users u ON u.id = b.user_id
            WHERE u.telegram_id = ? AND b.status = 'active'
            """,
            (telegram_id,),
        )
        return cur.fetchone() is not None

    def get_user_active_booking(self, telegram_id: int):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT b.*, ts.time, wd.date
            FROM bookings b
            JOIN users u ON u.id = b.user_id
            JOIN time_slots ts ON ts.id = b.slot_id
            JOIN work_days wd ON wd.id = ts.day_id
            WHERE u.telegram_id = ? AND b.status = 'active'
            """,
            (telegram_id,),
        )
        return cur.fetchone()

    def create_booking(
        self,
        telegram_id: int,
        username: str | None,
        name: str,
        phone: str,
        slot_id: int,
        appointment_dt: datetime,
    ):
        user = self.get_or_create_user(telegram_id, username)
        # обновим контакт
        self.update_user_contact(telegram_id, name, phone)

        if self.user_has_active_booking(telegram_id):
            return None

        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO bookings (
                user_id, slot_id, name, phone,
                appointment_datetime, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, 'active', ?)
            """,
            (
                user["id"],
                slot_id,
                name,
                phone,
                appointment_dt.isoformat(),
                datetime.utcnow().isoformat(),
            ),
        )
        booking_id = cur.lastrowid

        # слот больше не доступен
        self.set_slot_available(slot_id, False)

        self.conn.commit()
        return booking_id

    def cancel_booking(self, booking_id: int):
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE bookings SET status = 'cancelled' WHERE id = ?",
            (booking_id,),
        )
        self.conn.commit()

    def get_booking_by_id(self, booking_id: int):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
        return cur.fetchone()

    def attach_reminder(
        self, booking_id: int, job_id: str, reminder_time_iso: str
    ):
        cur = self.conn.cursor()
        cur.execute(
            """
            UPDATE bookings
            SET reminder_job_id = ?, reminder_time = ?
            WHERE id = ?
            """,
            (job_id, reminder_time_iso, booking_id),
        )
        self.conn.commit()

    def clear_reminder(self, booking_id: int):
        cur = self.conn.cursor()
        cur.execute(
            """
            UPDATE bookings
            SET reminder_job_id = NULL, reminder_time = NULL
            WHERE id = ?
            """,
            (booking_id,),
        )
        self.conn.commit()

    def get_future_bookings_with_reminders(self, now_iso: str):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT b.*, u.telegram_id, ts.time, wd.date
            FROM bookings b
            JOIN users u ON u.id = b.user_id
            JOIN time_slots ts ON ts.id = b.slot_id
            JOIN work_days wd ON wd.id = ts.day_id
            WHERE b.status = 'active'
              AND b.reminder_job_id IS NOT NULL
              AND b.reminder_time > ?
            """,
            (now_iso,),
        )
        return cur.fetchall()

    def get_bookings_for_date(self, date_str: str):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT b.*, u.telegram_id, u.name as user_name, ts.time, wd.date
            FROM bookings b
            JOIN users u ON u.id = b.user_id
            JOIN time_slots ts ON ts.id = b.slot_id
            JOIN work_days wd ON wd.id = ts.day_id
            WHERE wd.date = ?
              AND b.status = 'active'
            ORDER BY ts.time
            """,
            (date_str,),
        )
        return cur.fetchall()