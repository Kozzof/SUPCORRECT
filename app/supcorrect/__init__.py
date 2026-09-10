from pathlib import Path
import os

from flask import Flask
from dotenv import load_dotenv

from .db import Database


def environment_flag(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)
    database_url = os.environ.get("DATABASE_URL", "sqlite:///instance/supcorrect.db")
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "development-only-change-me"),
        DATABASE_URL=database_url,
        UPLOAD_MAX_BYTES=int(os.environ.get("UPLOAD_MAX_BYTES", "65536")),
        GRADER_WORKDIR=os.environ.get("GRADER_WORKDIR", str(Path(app.instance_path) / "work")),
        JOB_MAX_ATTEMPTS=int(os.environ.get("JOB_MAX_ATTEMPTS", "3")),
        JOB_LOCK_TIMEOUT_SECONDS=int(os.environ.get("JOB_LOCK_TIMEOUT_SECONDS", "300")),
        SESSION_COOKIE_SECURE=environment_flag("FLASK_SESSION_COOKIE_SECURE", database_url.startswith("mysql")),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        REFERENCE_DIR=os.environ.get(
            "GRADER_REFERENCE_DIR",
            str(Path(__file__).resolve().parents[2] / "tests" / "reference"),
        ),
    )
    if test_config:
        app.config.update(test_config)
        if "SESSION_COOKIE_SECURE" not in test_config and "FLASK_SESSION_COOKIE_SECURE" not in os.environ:
            app.config["SESSION_COOKIE_SECURE"] = app.config["DATABASE_URL"].startswith("mysql")

    app.extensions["db"] = Database(app.config["DATABASE_URL"])
    if not app.extensions["db"].mysql:
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    from .routes import bp

    app.register_blueprint(bp)
    return app
