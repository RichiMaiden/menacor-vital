from flask import Flask, request, jsonify
from flask_cors import CORS
import os, sqlite3
from datetime import datetime


APP_DB = os.environ.get("MENACOR_SERVER_DB", os.path.join(os.path.expanduser("~"), ".menacor_vital_server", "server.db"))
SCHEMA = """
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
"""


os.makedirs(os.path.dirname(APP_DB), exist_ok=True)
with sqlite3.connect(APP_DB) as con:
    con.executescript(SCHEMA)


app = Flask(__name__)
CORS(app)


def db():
    con = sqlite3.connect(APP_DB)
    con.row_factory = sqlite3.Row
    return con


@app.get("/health")
def health():
    return {"ok": True, "ts": datetime.utcnow().isoformat() + "Z"}


@app.post("/api/users")
def api_users_create():
    data = request.get_json(silent=True) or {}
    req = ["username", "password", "birthdate"]
    if any(not data.get(k) for k in req):
        return jsonify({"error": "Faltan campos"}), 400
    with db() as con:
        cur = con.cursor()
        try:
            cur.execute(
                """
                INSERT INTO users (username, password, full_name, birthdate, email)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    data.get("username",""), data.get("password",""),
                    data.get("full_name"), data.get("birthdate"), data.get("email")
                )
            )
            uid = cur.lastrowid
            con.commit()
        except sqlite3.IntegrityError:
            cur.execute("SELECT id FROM users WHERE username=?", (data.get("username"),))
            row = cur.fetchone()
            uid = row["id"] if row else None
    return jsonify({"status": "ok", "user_id": uid}), 201

@app.post("/api/vitals")
def api_vitals_create():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    with db() as con:
        cur = con.cursor()
        if not user_id:
            uext = data.get("user_external")
            if not uext:
                return jsonify({"error": "user_id o user_external requeridos"}), 400
            cur.execute("SELECT id FROM users WHERE username=?", (uext,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Usuario no encontrado en servidor"}), 404
            user_id = row["id"]
        cur.execute(
            """
            INSERT INTO vitals (user_id, date, pressure_systolic, pressure_diastolic, glucose, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                data.get("date"),
                data.get("pressure_systolic"),
                data.get("pressure_diastolic"),
                data.get("glucose"),
                data.get("notes"),
            )
        )
        vid = cur.lastrowid
        con.commit()
    return jsonify({"status": "ok", "vital_id": vid}), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)