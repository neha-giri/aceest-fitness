"""ACEest Fitness & Performance - Flask API.

Web version of the original Tkinter application (see legacy_versions/, latest: 3.2.4).
Features: login, client management, AI-style program generator, membership check,
weekly progress, workouts, body metrics and client report.
"""
import os
import random
import sqlite3
from datetime import datetime

from flask import Flask, current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

DEFAULT_DB = os.environ.get("ACEST_DB", "aceest_fitness.db")

PROGRAM_TEMPLATES = {
    "Fat Loss": ["Full Body HIIT", "Circuit Training", "Cardio + Weights"],
    "Muscle Gain": ["Push/Pull/Legs", "Upper/Lower Split", "Full Body Strength"],
    "Beginner": ["Full Body 3x/week", "Light Strength + Mobility"],
}
CALORIE_FACTORS = {"Fat Loss": 22, "Muscle Gain": 35, "Beginner": 26}
WORKOUT_TYPES = ["Strength", "Hypertrophy", "Cardio", "Mobility"]
MEMBERSHIP_STATUSES = ["Active", "Inactive", "Expired"]
UPDATABLE_FIELDS = {
    "age": int, "height": float, "weight": float, "program": str,
    "calories": int, "target_weight": float, "target_adherence": int,
    "membership_status": str, "membership_end": str,
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY, password TEXT, role TEXT);
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, age INTEGER,
    height REAL, weight REAL, program TEXT, calories INTEGER,
    target_weight REAL, target_adherence INTEGER,
    membership_status TEXT, membership_end TEXT);
CREATE TABLE IF NOT EXISTS progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT, client_name TEXT, week TEXT,
    adherence INTEGER);
CREATE TABLE IF NOT EXISTS workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, client_name TEXT, date TEXT,
    workout_type TEXT, duration_min INTEGER, notes TEXT);
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT, client_name TEXT, date TEXT,
    weight REAL, waist REAL, bodyfat REAL);
"""


def init_db(path):
    """Create tables and the default admin user (same as original init_db)."""
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    if not conn.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
        conn.execute("INSERT INTO users VALUES (?, ?, ?)",
                     ("admin", generate_password_hash("admin"), "Admin"))
    conn.commit()
    conn.close()


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def error(message, code=400):
    return jsonify({"error": message}), code


def valid_date(value):
    try:
        datetime.strptime(str(value), "%Y-%m-%d")
        return True
    except ValueError:
        return False


def find_client(name):
    return get_db().execute("SELECT * FROM clients WHERE name=?", (name,)).fetchone()


def calculate_calories(weight, program_type):
    """Estimated daily calories = weight (kg) * calorie factor of program type."""
    if program_type not in CALORIE_FACTORS:
        raise ValueError("Unknown program type")
    if weight <= 0:
        raise ValueError("Weight must be positive")
    return int(weight * CALORIE_FACTORS[program_type])


def parse_fields(data):
    """Cast numeric/text fields; raises ValueError/TypeError on bad input."""
    return {key: cast(data[key]) for key, cast in UPDATABLE_FIELDS.items()
            if data.get(key) is not None}


def create_app(test_config=None):
    app = Flask(__name__)
    app.config["DATABASE"] = DEFAULT_DB
    if test_config:
        app.config.update(test_config)
    init_db(app.config["DATABASE"])

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    # ---------- GENERAL ----------
    @app.route("/")
    def home():
        return jsonify({"service": "ACEest Fitness & Performance", "status": "running"})

    @app.route("/health")
    def health():
        return jsonify({"status": "healthy"})

    # ---------- LOGIN ----------
    @app.route("/login", methods=["POST"])
    def login():
        data = request.get_json(silent=True) or {}
        row = get_db().execute("SELECT password, role FROM users WHERE username=?",
                               (str(data.get("username", "")).strip(),)).fetchone()
        if row and check_password_hash(row["password"], str(data.get("password", ""))):
            return jsonify({"message": "Login successful", "role": row["role"]})
        return error("Invalid credentials", 401)

    # ---------- PROGRAMS ----------
    @app.route("/programs")
    def programs():
        return jsonify(PROGRAM_TEMPLATES)

    @app.route("/calories", methods=["POST"])
    def calories():
        data = request.get_json(silent=True) or {}
        try:
            value = calculate_calories(float(data.get("weight", 0)),
                                       str(data.get("program_type", "")))
        except (ValueError, TypeError) as exc:
            return error(str(exc))
        return jsonify({"calories": value})

    # ---------- CLIENTS ----------
    @app.route("/clients", methods=["GET"])
    def list_clients():
        rows = get_db().execute("SELECT name FROM clients ORDER BY name").fetchall()
        return jsonify([r["name"] for r in rows])

    @app.route("/clients", methods=["POST"])
    def add_client():
        data = request.get_json(silent=True) or {}
        name = str(data.get("name", "")).strip()
        if not name:
            return error("Client name is required")
        try:
            fields = parse_fields(data)
        except (ValueError, TypeError):
            return error("Invalid numeric value")
        status = fields.get("membership_status", "Active")
        if status not in MEMBERSHIP_STATUSES:
            return error("Invalid membership status")
        end = fields.get("membership_end")
        if end and not valid_date(end):
            return error("membership_end must be YYYY-MM-DD")
        if find_client(name):
            return error("Client already exists", 409)
        fields["membership_status"] = status
        fields["name"] = name
        cols = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        db = get_db()
        db.execute(f"INSERT INTO clients ({cols}) VALUES ({marks})", list(fields.values()))
        db.commit()
        return jsonify(dict(find_client(name))), 201

    @app.route("/clients/<name>", methods=["GET"])
    def get_client(name):
        client = find_client(name)
        if not client:
            return error("Client not found", 404)
        return jsonify(dict(client))

    @app.route("/clients/<name>", methods=["PUT"])
    def update_client(name):
        if not find_client(name):
            return error("Client not found", 404)
        data = request.get_json(silent=True) or {}
        try:
            fields = parse_fields(data)
        except (ValueError, TypeError):
            return error("Invalid numeric value")
        if not fields:
            return error("No valid fields to update")
        if fields.get("membership_status", "Active") not in MEMBERSHIP_STATUSES:
            return error("Invalid membership status")
        if fields.get("membership_end") and not valid_date(fields["membership_end"]):
            return error("membership_end must be YYYY-MM-DD")
        sets = ", ".join(f"{k}=?" for k in fields)
        db = get_db()
        db.execute(f"UPDATE clients SET {sets} WHERE name=?", [*fields.values(), name])
        db.commit()
        return jsonify(dict(find_client(name)))

    @app.route("/clients/<name>", methods=["DELETE"])
    def delete_client(name):
        if not find_client(name):
            return error("Client not found", 404)
        db = get_db()
        for table in ("progress", "workouts", "metrics"):
            db.execute(f"DELETE FROM {table} WHERE client_name=?", (name,))
        db.execute("DELETE FROM clients WHERE name=?", (name,))
        db.commit()
        return jsonify({"message": "Client deleted"})

    # ---------- AI-STYLE PROGRAM GENERATOR ----------
    @app.route("/clients/<name>/generate-program", methods=["POST"])
    def generate_program(name):
        if not find_client(name):
            return error("Client not found", 404)
        data = request.get_json(silent=True) or {}
        program_type = data.get("program_type") or random.choice(list(PROGRAM_TEMPLATES))
        if program_type not in PROGRAM_TEMPLATES:
            return error("Unknown program type")
        detail = random.choice(PROGRAM_TEMPLATES[program_type])
        db = get_db()
        db.execute("UPDATE clients SET program=? WHERE name=?", (detail, name))
        db.commit()
        return jsonify({"client": name, "program_type": program_type, "program": detail})

    # ---------- MEMBERSHIP ----------
    @app.route("/clients/<name>/membership")
    def membership(name):
        client = find_client(name)
        if not client:
            return error("Client not found", 404)
        return jsonify({"membership": client["membership_status"],
                        "renewal_date": client["membership_end"] or "N/A"})

    # ---------- PROGRESS (weekly adherence) ----------
    @app.route("/clients/<name>/progress", methods=["GET", "POST"])
    def progress(name):
        if not find_client(name):
            return error("Client not found", 404)
        db = get_db()
        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            week = str(data.get("week", "")).strip()
            try:
                adherence = int(data.get("adherence"))
            except (ValueError, TypeError):
                return error("adherence must be a number")
            if not week or not 0 <= adherence <= 100:
                return error("week is required and adherence must be 0-100")
            db.execute("INSERT INTO progress (client_name, week, adherence) VALUES (?,?,?)",
                       (name, week, adherence))
            db.commit()
            return jsonify({"week": week, "adherence": adherence}), 201
        rows = db.execute("SELECT week, adherence FROM progress WHERE client_name=? "
                          "ORDER BY id", (name,)).fetchall()
        return jsonify([dict(r) for r in rows])

    # ---------- WORKOUTS ----------
    @app.route("/clients/<name>/workouts", methods=["GET", "POST"])
    def workouts(name):
        if not find_client(name):
            return error("Client not found", 404)
        db = get_db()
        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            day = data.get("date") or datetime.now().strftime("%Y-%m-%d")
            wtype = data.get("workout_type")
            try:
                duration = int(data.get("duration_min", 60))
            except (ValueError, TypeError):
                return error("duration_min must be a number")
            if not valid_date(day):
                return error("date must be YYYY-MM-DD")
            if wtype not in WORKOUT_TYPES:
                return error("workout_type must be one of " + ", ".join(WORKOUT_TYPES))
            if duration <= 0:
                return error("duration_min must be positive")
            db.execute("INSERT INTO workouts (client_name, date, workout_type, duration_min, "
                       "notes) VALUES (?,?,?,?,?)",
                       (name, day, wtype, duration, data.get("notes", "")))
            db.commit()
            return jsonify({"date": day, "workout_type": wtype,
                            "duration_min": duration}), 201
        rows = db.execute("SELECT date, workout_type, duration_min, notes FROM workouts "
                          "WHERE client_name=? ORDER BY date DESC", (name,)).fetchall()
        return jsonify([dict(r) for r in rows])

    # ---------- BODY METRICS ----------
    @app.route("/clients/<name>/metrics", methods=["GET", "POST"])
    def metrics(name):
        if not find_client(name):
            return error("Client not found", 404)
        db = get_db()
        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            day = data.get("date") or datetime.now().strftime("%Y-%m-%d")
            try:
                weight = float(data.get("weight"))
                waist = float(data.get("waist", 0))
                bodyfat = float(data.get("bodyfat", 0))
            except (ValueError, TypeError):
                return error("weight, waist and bodyfat must be numbers")
            if not valid_date(day):
                return error("date must be YYYY-MM-DD")
            db.execute("INSERT INTO metrics (client_name, date, weight, waist, bodyfat) "
                       "VALUES (?,?,?,?,?)", (name, day, weight, waist, bodyfat))
            db.commit()
            return jsonify({"date": day, "weight": weight}), 201
        rows = db.execute("SELECT date, weight, waist, bodyfat FROM metrics "
                          "WHERE client_name=? ORDER BY date", (name,)).fetchall()
        return jsonify([dict(r) for r in rows])

    # ---------- REPORT (replaces PDF report) ----------
    @app.route("/clients/<name>/report")
    def report(name):
        client = find_client(name)
        if not client:
            return error("Client not found", 404)
        db = get_db()
        avg = db.execute("SELECT AVG(adherence) FROM progress WHERE client_name=?",
                         (name,)).fetchone()[0]
        count = db.execute("SELECT COUNT(*) FROM workouts WHERE client_name=?",
                           (name,)).fetchone()[0]
        return jsonify({"client": dict(client),
                        "average_adherence": round(avg, 1) if avg is not None else None,
                        "total_workouts": count})

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000)
