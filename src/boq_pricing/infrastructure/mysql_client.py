from __future__ import annotations

import csv
import os
import subprocess
import tempfile
from pathlib import Path


class MySqlCliClient:
    """Small MySQL client backed by mysql.exe.

    This keeps the project runnable in locked-down environments where Python
    database drivers are not installed yet. The repository boundary remains
    isolated so a connector-based implementation can replace it later.
    """

    def __init__(
        self,
        user: str,
        password: str | None = None,
        database: str | None = None,
        host: str = "127.0.0.1",
        port: int = 3306,
        mysql_bin: str = "mysql",
    ) -> None:
        self.user = user
        self.password = password if password is not None else os.getenv("BOQ_MYSQL_PASSWORD", "")
        self.database = database
        self.host = host
        self.port = port
        self.mysql_bin = mysql_bin

    def execute(self, sql: str, database: str | None = None) -> str:
        with self._defaults_file() as defaults_file:
            command = [
                self.mysql_bin,
                f"--defaults-extra-file={defaults_file}",
                "--batch",
                "--raw",
                "--skip-column-names",
            ]
            selected_database = database if database is not None else self.database
            if selected_database:
                command.extend(["--database", selected_database])
            command.extend(["--execute", sql])
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                encoding="utf-8",
            )
            return completed.stdout

    def query_rows(self, sql: str) -> list[dict[str, str]]:
        with self._defaults_file() as defaults_file:
            command = [
                self.mysql_bin,
                f"--defaults-extra-file={defaults_file}",
                "--batch",
                "--raw",
            ]
            if self.database:
                command.extend(["--database", self.database])
            command.extend(["--execute", sql])
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                encoding="utf-8",
            )
        if not completed.stdout.strip():
            return []
        reader = csv.DictReader(completed.stdout.splitlines(), delimiter="\t")
        return [dict(row) for row in reader]

    def _defaults_file(self):
        temp = tempfile.NamedTemporaryFile("w", suffix=".cnf", delete=False, encoding="utf-8")
        path = Path(temp.name)
        temp.write("[client]\n")
        temp.write(f"user={self.user}\n")
        temp.write(f"password={self.password}\n")
        temp.write(f"host={self.host}\n")
        temp.write(f"port={self.port}\n")
        temp.write("default-character-set=utf8mb4\n")
        temp.close()

        class DefaultsFileContext:
            def __enter__(self_nonlocal):
                return str(path)

            def __exit__(self_nonlocal, exc_type, exc, traceback):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass

        return DefaultsFileContext()


def sql_quote(value: object) -> str:
    if value is None:
        return "NULL"
    text = str(value)
    escaped = text.replace("\\", "\\\\").replace("'", "''")
    return f"'{escaped}'"

