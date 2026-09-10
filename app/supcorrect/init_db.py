from pathlib import Path

from . import create_app


def main():
    app = create_app()
    schema_name = "schema_mariadb.sql" if app.extensions["db"].mysql else "schema_sqlite.sql"
    schema = Path(__file__).resolve().parents[2] / "infra" / "database" / schema_name
    with app.extensions["db"].transaction() as connection:
        app.extensions["db"].script(connection, schema.read_text(encoding="utf-8"))
        db = app.extensions["db"]
        insert_ignore = "INSERT IGNORE" if db.mysql else "INSERT OR IGNORE"
        db.execute(connection, f"{insert_ignore} INTO courses (id, code, label) VALUES (1, ?, ?)", ("INIT", "Initiation programmation"))
        db.execute(connection, f"{insert_ignore} INTO exercises (id, course_id, number, title) VALUES (1, 1, 1, ?)", ("Somme de deux entiers",))
        db.execute(connection, f"{insert_ignore} INTO exercises (id, course_id, number, title) VALUES (2, 1, 2, ?)", ("Maximum de trois entiers",))
        for exercise_id in (1, 2):
            for language in ("c", "python"):
                db.execute(connection, f"{insert_ignore} INTO exercise_languages (exercise_id, language) VALUES (?, ?)", (exercise_id, language))


if __name__ == "__main__":
    main()
