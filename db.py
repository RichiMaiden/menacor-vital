import os
import sqlite3
import datetime
import csv
import io

DEFAULT_HOME_DB = os.path.join(os.path.expanduser("~"), ".menacor_vital_offline", "app.db")
FALLBACK_DB = os.path.join(os.getcwd(), "app.db")

def _choose_db_path() -> str:
    path = DEFAULT_HOME_DB
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with sqlite3.connect(path) as _:
            pass
        return path
    except Exception:
        return FALLBACK_DB

DB_PATH = _choose_db_path()

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,
  full_name TEXT,
  birthdate TEXT NOT NULL,
  email TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS vitals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  date TEXT NOT NULL,
  pressure_systolic INTEGER,
  pressure_diastolic INTEGER,
  glucose REAL,
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS sync_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entity TEXT NOT NULL,
  entity_id INTEGER NOT NULL,
  action TEXT NOT NULL,
  payload TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now')),
  processed INTEGER DEFAULT 0
);
"""

def ensure_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.executescript(SCHEMA_SQL)

def validate_birthdate(date_str: str) -> bool:
    try:
        datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except Exception:
        return False

def parse_pressure(value: str):
    if not value:
        return None, None
    parts = value.replace(" ", "").split("/")
    try:
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
        elif len(parts) == 1 and parts[0].isdigit():
            return int(parts[0]), None
    except ValueError:
        pass
    return None, None

def register_user(username: str, password: str, full_name: str, birthdate: str, email: str) -> int:
    if not username or not password or not birthdate:
        raise ValueError("Usuario/contraseña/fecha son obligatorios")
    if not validate_birthdate(birthdate):
        raise ValueError("Fecha inválida. Usa AAAA-MM-DD")
    try:
        with sqlite3.connect(DB_PATH) as con:
            cur = con.cursor()
            cur.execute(
                "INSERT INTO users (username, password, full_name, birthdate, email) VALUES (?, ?, ?, ?, ?)",
                (username.strip(), password.strip(), (full_name or None), birthdate.strip(), (email or None)),
            )
            uid = cur.lastrowid
            con.commit()
            return uid
    except sqlite3.IntegrityError as e:
        raise ValueError("El nombre de usuario ya existe. Elegí otro.") from e

def login_user(username: str, password: str):
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username.strip(), password.strip()))
        row = cur.fetchone()
        return dict(row) if row else None

def add_vital(user_id: int, date: str, pressure: str, glucose: str, notes: str) -> int:
    s, d = parse_pressure(pressure)
    try:
        g = float(glucose) if glucose else None
    except ValueError:
        g = None
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(
            "INSERT INTO vitals (user_id, date, pressure_systolic, pressure_diastolic, glucose, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, date, s, d, g, notes or None),
        )
        vid = cur.lastrowid
        con.commit()
        return vid

def list_vitals(user_id: int):
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("SELECT * FROM vitals WHERE user_id=? ORDER BY date DESC, id DESC", (user_id,))
        return [dict(r) for r in cur.fetchall()]

def export_csv(user_id: int) -> io.BytesIO:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Fecha", "Sistólica", "Diastólica", "Glucosa", "Notas"])
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("SELECT * FROM vitals WHERE user_id=? ORDER BY date DESC", (user_id,))
        for r in cur.fetchall():
            w.writerow([
                r["date"],
                r["pressure_systolic"] if r["pressure_systolic"] is not None else "",
                r["pressure_diastolic"] if r["pressure_diastolic"] is not None else "",
                r["glucose"] if r["glucose"] is not None else "",
                r["notes"] or "",
            ])
    return io.BytesIO(out.getvalue().encode("utf-8"))

# --- Sync ---
import json
BACKEND_BASE_URL = os.environ.get("MENACOR_BACKEND_URL", "http://127.0.0.1:5000")

def enqueue(entity: str, entity_id: int, action: str, payload: dict):
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            "INSERT INTO sync_queue (entity, entity_id, action, payload) VALUES (?, ?, ?, ?)",
            (entity, entity_id, action, json.dumps(payload)),
        )
        con.commit()

def sync_if_possible() -> int:
    try:
        import requests
    except Exception:
        return 0

    try:
        r = requests.get(BACKEND_BASE_URL + "/health", timeout=2)
        if r.status_code != 200:
            return 0
    except Exception:
        return 0

    processed = 0
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("SELECT * FROM sync_queue WHERE processed=0 ORDER BY id ASC")
        for row in cur.fetchall():
            payload = json.loads(row["payload"])
            try:
                if row["entity"] == "user" and row["action"] == "create":
                    resp = requests.post(BACKEND_BASE_URL + "/api/users", json=payload, timeout=5)
                    if resp.status_code in (200, 201):
                        cur.execute("UPDATE sync_queue SET processed=1 WHERE id=?", (row["id"],))
                        processed += 1
                elif row["entity"] == "vital" and row["action"] == "create":
                    resp = requests.post(BACKEND_BASE_URL + "/api/vitals", json=payload, timeout=5)
                    if resp.status_code in (200, 201):
                        cur.execute("UPDATE sync_queue SET processed=1 WHERE id=?", (row["id"],))
                        processed += 1
                con.commit()
            except Exception:
                pass
    return processed
