import contextlib
import sqlite3
from pathlib import Path
from urllib.parse import urlparse


class Database:
    """Small DB adapter: SQLite for local work, MariaDB through PyMySQL in production."""

    def __init__(self, url):
        self.url = url
        self.mysql = url.startswith("mysql")

    def connect(self):
        if not self.mysql:
            location = self.url.removeprefix("sqlite:///")
            Path(location).parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(location)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            return connection

        import pymysql

        parsed = urlparse(self.url)
        return pymysql.connect(
            host=parsed.hostname,
            port=parsed.port or 3306,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path.lstrip("/"),
            autocommit=False,
            cursorclass=pymysql.cursors.DictCursor,
        )

    def placeholder(self, sql):
        return sql.replace("?", "%s") if self.mysql else sql

    @contextlib.contextmanager
    def transaction(self, immediate=False):
        connection = self.connect()
        try:
            if immediate and not self.mysql:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def execute(self, connection, sql, values=()):
        cursor = connection.cursor()
        cursor.execute(self.placeholder(sql), values)
        return cursor

    def script(self, connection, sql):
        if self.mysql:
            for statement in sql.split(";"):
                if statement.strip():
                    self.execute(connection, statement)
        else:
            connection.executescript(sql)
