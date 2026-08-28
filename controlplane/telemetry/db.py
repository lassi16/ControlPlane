"""
Database Layer — Dual-mode persistence
- Local / no Docker: SQLite (aiosqlite) — zero config, file-based
- Docker / production: PostgreSQL (asyncpg) — full ACID, scalable

Switches automatically based on DATABASE_URL in .env:
  - Not set → SQLite at controlplane/data/events.db
  - postgresql+asyncpg:// → PostgreSQL
"""
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

logger = logging.getLogger("controlplane.db")

# ── Detect which backend to use ──────────────────────────────────────────────
_RAW_DB_URL = os.getenv("DATABASE_URL", "")
USE_POSTGRES = _RAW_DB_URL.startswith("postgresql")

# SQLite file location (local mode)
_DB_DIR  = Path(__file__).parent.parent / "data"
_DB_PATH = _DB_DIR / "events.db"

_pg_pool = None  # asyncpg connection pool (Postgres mode only)


# ── Startup init ──────────────────────────────────────────────────────────────

async def init_db():
    """Create tables if they don't exist. Called once on app startup."""
    if USE_POSTGRES:
        await _init_postgres()
    else:
        await _init_sqlite()


async def _init_sqlite():
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(_DB_PATH)) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id              TEXT PRIMARY KEY,
                timestamp       REAL NOT NULL,
                application_id  TEXT,
                model_id        TEXT,
                policy_action   TEXT,
                impact          TEXT,
                data            TEXT NOT NULL
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_ts     ON events(timestamp DESC)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_app    ON events(application_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_action ON events(policy_action)")
        await db.commit()
    logger.info(f"SQLite ready — {_DB_PATH}")


async def _init_postgres():
    try:
        pool = await _pg_get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id              TEXT PRIMARY KEY,
                    timestamp       DOUBLE PRECISION NOT NULL,
                    application_id  TEXT,
                    model_id        TEXT,
                    policy_action   TEXT,
                    impact          TEXT,
                    data            JSONB NOT NULL
                )
            """)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON events(timestamp DESC)")
        logger.info("PostgreSQL ready")
    except Exception as e:
        logger.warning(f"PostgreSQL unavailable ({e}), falling back to SQLite")
        await _init_sqlite()


async def _pg_get_pool():
    global _pg_pool
    if _pg_pool is None:
        import asyncpg
        url = _RAW_DB_URL.replace("postgresql+asyncpg://", "postgresql://")
        _pg_pool = await asyncpg.create_pool(url, min_size=2, max_size=10)
    return _pg_pool


# ── Public API ────────────────────────────────────────────────────────────────

async def db_store_event(event: Dict[str, Any]) -> str:
    """Persist a new event. Returns its ID."""
    if USE_POSTGRES:
        return await _pg_store(event)
    return await _sqlite_store(event)


async def db_update_event(event_id: str, updates: Dict[str, Any]) -> bool:
    """Merge updates into an existing event."""
    if USE_POSTGRES:
        return await _pg_update(event_id, updates)
    return await _sqlite_update(event_id, updates)


async def db_get_event(event_id: str) -> Optional[Dict]:
    if USE_POSTGRES:
        return await _pg_get(event_id)
    return await _sqlite_get(event_id)


async def db_get_events(
    limit: int = 50,
    offset: int = 0,
    application_id: Optional[str] = None,
    policy_action: Optional[str] = None,
) -> List[Dict]:
    if USE_POSTGRES:
        return await _pg_list(limit, offset, application_id, policy_action)
    return await _sqlite_list(limit, offset, application_id, policy_action)


async def db_count_events() -> int:
    if USE_POSTGRES:
        return await _pg_count()
    return await _sqlite_count()


# ── SQLite implementations ────────────────────────────────────────────────────

async def _sqlite_store(event: Dict) -> str:
    async with aiosqlite.connect(str(_DB_PATH)) as db:
        await db.execute(
            "INSERT OR IGNORE INTO events"
            "(id, timestamp, application_id, model_id, policy_action, impact, data)"
            " VALUES (?,?,?,?,?,?,?)",
            (
                event["id"],
                event.get("timestamp", time.time()),
                event.get("application_id"),
                event.get("model_id"),
                event.get("policy_action"),
                event.get("impact"),
                json.dumps(event),
            ),
        )
        await db.commit()
    return event["id"]


async def _sqlite_update(event_id: str, updates: Dict) -> bool:
    async with aiosqlite.connect(str(_DB_PATH)) as db:
        async with db.execute("SELECT data FROM events WHERE id=?", (event_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            return False
        existing = json.loads(row[0])
        existing.update(updates)
        await db.execute(
            "UPDATE events SET data=?, policy_action=?, impact=? WHERE id=?",
            (
                json.dumps(existing),
                existing.get("policy_action"),
                existing.get("impact"),
                event_id,
            ),
        )
        await db.commit()
    return True


async def _sqlite_get(event_id: str) -> Optional[Dict]:
    async with aiosqlite.connect(str(_DB_PATH)) as db:
        async with db.execute("SELECT data FROM events WHERE id=?", (event_id,)) as cur:
            row = await cur.fetchone()
    return json.loads(row[0]) if row else None


async def _sqlite_list(limit, offset, application_id, policy_action) -> List[Dict]:
    clauses, params = ["1=1"], []
    if application_id:
        clauses.append("application_id=?")
        params.append(application_id)
    if policy_action:
        clauses.append("policy_action=?")
        params.append(policy_action)
    params += [limit, offset]
    sql = (
        f"SELECT data FROM events WHERE {' AND '.join(clauses)}"
        " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    )
    async with aiosqlite.connect(str(_DB_PATH)) as db:
        async with db.execute(sql, params) as cur:
            rows = await cur.fetchall()
    return [json.loads(r[0]) for r in rows]


async def _sqlite_count() -> int:
    async with aiosqlite.connect(str(_DB_PATH)) as db:
        async with db.execute("SELECT COUNT(*) FROM events") as cur:
            row = await cur.fetchone()
    return row[0] if row else 0


# ── PostgreSQL implementations ────────────────────────────────────────────────

async def _pg_store(event: Dict) -> str:
    pool = await _pg_get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO events(id,timestamp,application_id,model_id,policy_action,impact,data)"
            " VALUES($1,$2,$3,$4,$5,$6,$7) ON CONFLICT(id) DO NOTHING",
            event["id"], event.get("timestamp", time.time()),
            event.get("application_id"), event.get("model_id"),
            event.get("policy_action"), event.get("impact"),
            json.dumps(event),
        )
    return event["id"]


async def _pg_update(event_id: str, updates: Dict) -> bool:
    pool = await _pg_get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT data FROM events WHERE id=$1", event_id)
        if not row:
            return False
        existing = json.loads(row["data"])
        existing.update(updates)
        await conn.execute(
            "UPDATE events SET data=$1, policy_action=$2, impact=$3 WHERE id=$4",
            json.dumps(existing), existing.get("policy_action"),
            existing.get("impact"), event_id,
        )
    return True


async def _pg_get(event_id: str) -> Optional[Dict]:
    pool = await _pg_get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT data FROM events WHERE id=$1", event_id)
    return json.loads(row["data"]) if row else None


async def _pg_list(limit, offset, application_id, policy_action) -> List[Dict]:
    pool = await _pg_get_pool()
    clauses, params, i = ["1=1"], [], 1
    if application_id:
        clauses.append(f"application_id=${i}"); params.append(application_id); i += 1
    if policy_action:
        clauses.append(f"policy_action=${i}"); params.append(policy_action); i += 1
    params += [limit, offset]
    sql = (
        f"SELECT data FROM events WHERE {' AND '.join(clauses)}"
        f" ORDER BY timestamp DESC LIMIT ${i} OFFSET ${i+1}"
    )
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)
    return [json.loads(r["data"]) for r in rows]


async def _pg_count() -> int:
    pool = await _pg_get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM events")
