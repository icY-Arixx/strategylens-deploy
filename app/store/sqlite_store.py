"""Short-lived connections; atomic snapshot read and compare-and-swap writes."""
import sqlite3
import hashlib
from contextlib import contextmanager
from pathlib import Path

from app.domain.models import DataSnapshot, Execution, ScreeningRun, Strategy, now


class RevisionConflict(Exception):
    pass


class SQLiteStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS strategies (
                    strategy_id TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS executions (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_id TEXT UNIQUE NOT NULL,
                    strategy_id TEXT NOT NULL REFERENCES strategies(strategy_id),
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS execution_strategy
                    ON executions(strategy_id, sequence DESC);
                CREATE TABLE IF NOT EXISTS data_snapshots (
                    snapshot_id TEXT PRIMARY KEY, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS screening_runs (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT UNIQUE NOT NULL,
                    strategy_id TEXT NOT NULL REFERENCES strategies(strategy_id),
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS run_strategy ON screening_runs(strategy_id, sequence DESC);
            """)
        self._migrate_legacy()

    def _migrate_legacy(self):
        # Canonicalize Phase 1 aliases before CAS writes. Preserve financial values and IDs.
        with self.connection() as conn:
            if conn.execute("PRAGMA user_version").fetchone()[0] >= 2:
                return
            old_rows = conn.execute("SELECT strategy_id, payload FROM strategies").fetchall()
            old_runs = conn.execute("SELECT execution_id, payload FROM executions").fetchall()
            strategies = [(sid, Strategy.model_validate_json(payload)) for sid, payload in old_rows]
            executions = [(eid, Execution.model_validate_json(payload)) for eid, payload in old_runs]
            if old_rows or old_runs:
                backups = self.path.parent / "backups"
                backups.mkdir(exist_ok=True)
                backup_path = backups / f"{self.path.stem}-before-v2-{now():%Y%m%dT%H%M%S%f}.sqlite3"
                backup = sqlite3.connect(str(backup_path))
                try:
                    conn.backup(backup)
                finally:
                    backup.close()
            legacy_ids = {e.strategy_id for _, e in executions if e.snapshot_id is None}
            for sid, strategy in strategies:
                if sid in legacy_ids and strategy.status == "executed":
                    strategy = strategy.model_copy(update={"status":"stale", "updated_at":now()})
                conn.execute("UPDATE strategies SET payload=? WHERE strategy_id=?", (strategy.model_dump_json(), sid))
            for eid, execution in executions:
                conn.execute("UPDATE executions SET payload=? WHERE execution_id=?", (execution.model_dump_json(), eid))
            conn.execute("PRAGMA user_version = 2")

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(str(self.path), timeout=10)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def create(self, strategy: Strategy):
        with self.connection() as conn:
            conn.execute("INSERT INTO strategies VALUES (?, ?, ?)",
                         (strategy.strategy_id, strategy.revision, strategy.model_dump_json()))

    def read(self, strategy_id: str) -> tuple[Strategy, Execution | None]:
        strategy, execution, _ = self.read_state(strategy_id)
        return strategy, execution

    def read_state(self, strategy_id: str):
        with self.connection() as conn:
            conn.execute("BEGIN")
            row = conn.execute("SELECT payload FROM strategies WHERE strategy_id = ?", (strategy_id,)).fetchone()
            if row is None:
                raise KeyError(strategy_id)
            run = conn.execute("SELECT payload FROM executions WHERE strategy_id = ? ORDER BY sequence DESC LIMIT 1",
                               (strategy_id,)).fetchone()
            latest = conn.execute("SELECT payload FROM screening_runs WHERE strategy_id=? ORDER BY sequence DESC LIMIT 1",
                                  (strategy_id,)).fetchone()
            return (Strategy.model_validate_json(row[0]), Execution.model_validate_json(run[0]) if run else None,
                    ScreeningRun.model_validate_json(latest[0]) if latest else None)

    @staticmethod
    def snapshot_hash(snapshot):
        return hashlib.sha256(snapshot.model_dump_json(exclude={"content_hash"}).encode("utf-8")).hexdigest()

    def save_snapshot(self, snapshot: DataSnapshot):
        sealed = snapshot.model_copy(update={"content_hash": self.snapshot_hash(snapshot)})
        with self.connection() as conn:
            conn.execute("INSERT INTO data_snapshots VALUES (?, ?)", (sealed.snapshot_id, sealed.model_dump_json()))
        return sealed

    def read_snapshot(self, snapshot_id: str):
        with self.connection() as conn:
            row = conn.execute("SELECT payload FROM data_snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
        if row is None:
            raise KeyError(snapshot_id)
        snapshot = DataSnapshot.model_validate_json(row[0])
        if snapshot.content_hash != self.snapshot_hash(snapshot):
            raise ValueError("快照完整性校验失败")
        return snapshot

    def save_run(self, run: ScreeningRun):
        with self.connection() as conn:
            conn.execute("""INSERT INTO screening_runs (run_id,strategy_id,payload) VALUES (?,?,?)
                         ON CONFLICT(run_id) DO UPDATE SET payload=excluded.payload""",
                         (run.run_id, run.strategy_id, run.model_dump_json()))

    def read_execution(self, execution_id: str):
        with self.connection() as conn:
            row = conn.execute("SELECT payload FROM executions WHERE execution_id=?", (execution_id,)).fetchone()
        if row is None:
            raise KeyError(execution_id)
        return Execution.model_validate_json(row[0])

    def save(self, original: Strategy, updated: Strategy, execution: Execution | None = None):
        # Compare the entire old snapshot, including status. An execution changes status
        # without changing the condition revision; revision alone would miss that race.
        with self.connection() as conn:
            cursor = conn.execute(
                "UPDATE strategies SET revision = ?, payload = ? WHERE strategy_id = ? AND payload = ?",
                (updated.revision, updated.model_dump_json(), original.strategy_id, original.model_dump_json()))
            if cursor.rowcount != 1:
                raise RevisionConflict("策略已被其他请求更新，请刷新后重试")
            if execution:
                conn.execute("INSERT INTO executions (execution_id, strategy_id, payload) VALUES (?, ?, ?)",
                             (execution.execution_id, execution.strategy_id, execution.model_dump_json()))
                if execution.run:
                    conn.execute("UPDATE screening_runs SET payload=? WHERE run_id=?",
                                 (execution.run.model_dump_json(), execution.run.run_id))
