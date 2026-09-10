import secrets
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

bp = Blueprint("web", __name__)


def db():
    return current_app.extensions["db"]


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("web.login"))
        return view(*args, **kwargs)
    return wrapped


def csrf_token():
    return session.setdefault("csrf_token", secrets.token_urlsafe(32))


def require_csrf():
    expected = session.get("csrf_token")
    submitted = request.form.get("csrf_token")
    if not expected or not submitted or not secrets.compare_digest(expected, submitted):
        abort(400)


@bp.app_context_processor
def csrf_context():
    return {"csrf_token": csrf_token}


@bp.get("/health")
def health():
    try:
        with db().transaction() as connection:
            db().execute(connection, "SELECT 1")
    except Exception:
        return {"status": "unavailable"}, 503
    return {"status": "ok"}, 200


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        require_csrf()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if "@" not in email or len(password) < 12:
            flash("Adresse e-mail invalide ou mot de passe trop court (12 caracteres minimum).")
        else:
            try:
                with db().transaction() as connection:
                    db().execute(connection, "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)", (email, generate_password_hash(password), now()))
                flash("Compte cree. Connectez-vous.")
                return redirect(url_for("web.login"))
            except Exception:
                flash("Cette adresse e-mail est deja utilisee.")
    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        require_csrf()
        with db().transaction() as connection:
            row = db().execute(connection, "SELECT id, password_hash FROM users WHERE email = ?", (request.form.get("email", "").strip().lower(),)).fetchone()
        if row and check_password_hash(row["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"] = row["id"]
            csrf_token()
            return redirect(url_for("web.dashboard"))
        flash("Identifiants invalides.")
    return render_template("login.html")


@bp.post("/logout")
@login_required
def logout():
    require_csrf()
    session.clear()
    return redirect(url_for("web.login"))


@bp.get("/")
@login_required
def dashboard():
    with db().transaction() as connection:
        exercises = db().execute(connection, "SELECT e.id, c.code, e.number, e.title FROM exercises e JOIN courses c ON c.id = e.course_id ORDER BY c.code, e.number").fetchall()
        rows = db().execute(connection, "SELECT s.exercise_id, s.status, s.score, s.submitted_at, s.graded_at FROM submissions s WHERE s.user_id = ? ORDER BY s.submitted_at DESC, s.id DESC", (session["user_id"],)).fetchall()
        best_rows = db().execute(connection, "SELECT exercise_id, score, graded_at FROM best_submissions WHERE user_id = ?", (session["user_id"],)).fetchall()
        languages = db().execute(connection, "SELECT exercise_id, language FROM exercise_languages ORDER BY language").fetchall()
    latest = {}
    for row in rows:
        latest.setdefault(row["exercise_id"], row)
    language_map = {}
    for row in languages:
        language_map.setdefault(row["exercise_id"], []).append(row["language"])
    best = {row["exercise_id"]: row for row in best_rows}
    return render_template("dashboard.html", exercises=exercises, latest=latest, best=best, language_map=language_map)


@bp.post("/submit")
@login_required
def submit():
    require_csrf()
    try:
        exercise_id = int(request.form.get("exercise_id", ""))
    except ValueError:
        abort(400)
    language = request.form.get("language", "")
    source = request.files.get("source")
    allowed_extensions = {"c": ".c", "python": ".py"}
    if not source or language not in allowed_extensions or not source.filename.lower().endswith(allowed_extensions[language]):
        flash("Le fichier ne correspond pas au langage selectionne.")
        return redirect(url_for("web.dashboard"))
    payload = source.read(current_app.config["UPLOAD_MAX_BYTES"] + 1)
    if not payload or len(payload) > current_app.config["UPLOAD_MAX_BYTES"]:
        flash("Fichier vide ou trop volumineux.")
        return redirect(url_for("web.dashboard"))

    filename = secure_filename(source.filename)
    with db().transaction() as connection:
        allowed = db().execute(connection, "SELECT 1 FROM exercise_languages WHERE exercise_id = ? AND language = ?", (exercise_id, language)).fetchone()
        if not allowed:
            abort(400)
        created_at = now()
        cursor = db().execute(connection, "INSERT INTO submissions (user_id, exercise_id, language, original_filename, source_code, status, submitted_at) VALUES (?, ?, ?, ?, ?, 'queued', ?)", (session["user_id"], exercise_id, language, filename, payload.decode("utf-8", errors="replace"), created_at))
        submission_id = cursor.lastrowid
        db().execute(connection, "INSERT INTO jobs (submission_id, status, attempts, available_at) VALUES (?, 'queued', 0, ?)", (submission_id, created_at))
    flash("Soumission placee en attente de correction.")
    return redirect(url_for("web.dashboard"))
