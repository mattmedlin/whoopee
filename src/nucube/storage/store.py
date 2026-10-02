import json
import sqlite3
from pathlib import Path


class Store:
    """Normalized durable records; a whole job transition is one SQLite transaction."""

    def __init__(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(root / "state.sqlite3", check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, key TEXT UNIQUE,
                fingerprint TEXT NOT NULL, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS tasks (
                job_id TEXT, id TEXT, body TEXT NOT NULL, PRIMARY KEY (job_id,id));
            CREATE TABLE IF NOT EXISTS attempts (
                job_id TEXT, task_id TEXT, number INTEGER, body TEXT NOT NULL,
                PRIMARY KEY (job_id,task_id,number));
        """)

    def save(self, job: dict) -> None:
        head = {k: v for k, v in job.items() if k != "tasks"}
        with self.db:
            self.db.execute(
                "INSERT INTO jobs VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE "
                "SET body=excluded.body",
                (job["id"], job["key"], job["fingerprint"], json.dumps(head)),
            )
            for task in job["tasks"]:
                body = {k: v for k, v in task.items() if k != "attempts"}
                self.db.execute(
                    "INSERT OR REPLACE INTO tasks VALUES (?,?,?)",
                    (job["id"], task["id"], json.dumps(body)),
                )
                for attempt in task["attempts"]:
                    self.db.execute(
                        "INSERT OR REPLACE INTO attempts VALUES (?,?,?,?)",
                        (job["id"], task["id"], attempt["number"], json.dumps(attempt)),
                    )

    def get(self, job_id: str) -> dict | None:
        row = self.db.execute("SELECT body FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            return None
        job = json.loads(row[0])
        job["tasks"] = []
        for row in self.db.execute("SELECT body FROM tasks WHERE job_id=? ORDER BY id", (job_id,)):
            task = json.loads(row[0])
            task["attempts"] = [
                json.loads(r[0])
                for r in self.db.execute(
                    "SELECT body FROM attempts WHERE job_id=? AND task_id=? ORDER BY number",
                    (job_id, task["id"]),
                )
            ]
            job["tasks"].append(task)
        return job

    def ids(self) -> list[str]:
        return [r[0] for r in self.db.execute("SELECT id FROM jobs ORDER BY rowid")]

    def by_key(self, key: str) -> dict | None:
        row = self.db.execute("SELECT id FROM jobs WHERE key=?", (key,)).fetchone()
        return self.get(row[0]) if row else None
