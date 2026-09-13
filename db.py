import time
from contextlib import asynccontextmanager

import aiosqlite

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    exp INTEGER NOT NULL DEFAULT 0,
    first_seen INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS rarities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    chance TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS summons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summon_id INTEGER NOT NULL REFERENCES summons(id) ON DELETE CASCADE,
    photo_file_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rarity_id INTEGER NOT NULL REFERENCES rarities(id),
    exp_reward INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS user_cards (
    user_id INTEGER NOT NULL,
    card_id INTEGER NOT NULL,
    obtained_at INTEGER NOT NULL,
    PRIMARY KEY (user_id, card_id)
);

CREATE TABLE IF NOT EXISTS cooldowns (
    user_id INTEGER NOT NULL,
    summon_id INTEGER NOT NULL,
    last_used INTEGER NOT NULL,
    PRIMARY KEY (user_id, summon_id)
);
"""


@asynccontextmanager
async def get_conn():
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        await conn.close()


async def init_db():
    async with get_conn() as conn:
        await conn.executescript(SCHEMA)
        await conn.commit()


# ---------- meta / users / admins ----------

async def ensure_user(user_id: int) -> bool:
    """Registers the user if new. Returns True if this user just became the main admin."""
    became_main_admin = False
    async with get_conn() as conn:
        cur = await conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        exists = await cur.fetchone()
        if not exists:
            await conn.execute(
                "INSERT INTO users (user_id, exp, first_seen) VALUES (?, 0, ?)",
                (user_id, int(time.time())),
            )
        cur = await conn.execute("SELECT value FROM meta WHERE key = 'main_admin_id'")
        row = await cur.fetchone()
        if row is None:
            await conn.execute(
                "INSERT INTO meta (key, value) VALUES ('main_admin_id', ?)", (str(user_id),)
            )
            await conn.execute(
                "INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,)
            )
            became_main_admin = True
        await conn.commit()
    return became_main_admin


async def get_main_admin_id() -> int | None:
    async with get_conn() as conn:
        cur = await conn.execute("SELECT value FROM meta WHERE key = 'main_admin_id'")
        row = await cur.fetchone()
        return int(row["value"]) if row else None


async def get_admin_ids() -> list[int]:
    async with get_conn() as conn:
        cur = await conn.execute("SELECT user_id FROM admins")
        rows = await cur.fetchall()
        return [r["user_id"] for r in rows]


async def is_admin(user_id: int) -> bool:
    async with get_conn() as conn:
        cur = await conn.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
        return (await cur.fetchone()) is not None


async def add_admin(user_id: int):
    async with get_conn() as conn:
        await conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
        await conn.commit()


async def remove_admin(user_id: int):
    async with get_conn() as conn:
        await conn.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        await conn.commit()


async def get_user(user_id: int) -> aiosqlite.Row | None:
    async with get_conn() as conn:
        cur = await conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return await cur.fetchone()


async def add_exp(user_id: int, amount: int):
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE users SET exp = exp + ? WHERE user_id = ?", (amount, user_id)
        )
        await conn.commit()


# ---------- rarities ----------

async def list_rarities_sorted() -> list[aiosqlite.Row]:
    async with get_conn() as conn:
        cur = await conn.execute("SELECT * FROM rarities")
        rows = await cur.fetchall()
        return sorted(rows, key=lambda r: float(r["chance"]), reverse=True)


async def get_rarity(rarity_id: int) -> aiosqlite.Row | None:
    async with get_conn() as conn:
        cur = await conn.execute("SELECT * FROM rarities WHERE id = ?", (rarity_id,))
        return await cur.fetchone()


async def add_rarity(name: str, chance: str) -> int:
    async with get_conn() as conn:
        cur = await conn.execute(
            "INSERT INTO rarities (name, chance) VALUES (?, ?)", (name, chance)
        )
        await conn.commit()
        return cur.lastrowid


async def update_rarity_name(rarity_id: int, name: str):
    async with get_conn() as conn:
        await conn.execute("UPDATE rarities SET name = ? WHERE id = ?", (name, rarity_id))
        await conn.commit()


async def update_rarity_chance(rarity_id: int, chance: str):
    async with get_conn() as conn:
        await conn.execute("UPDATE rarities SET chance = ? WHERE id = ?", (chance, rarity_id))
        await conn.commit()


async def count_cards_with_rarity(rarity_id: int) -> int:
    async with get_conn() as conn:
        cur = await conn.execute("SELECT COUNT(*) c FROM cards WHERE rarity_id = ?", (rarity_id,))
        row = await cur.fetchone()
        return row["c"]


async def delete_rarity(rarity_id: int):
    async with get_conn() as conn:
        await conn.execute("DELETE FROM rarities WHERE id = ?", (rarity_id,))
        await conn.commit()


# ---------- summons ----------

async def list_summons() -> list[aiosqlite.Row]:
    async with get_conn() as conn:
        cur = await conn.execute("SELECT * FROM summons ORDER BY name")
        return await cur.fetchall()


async def list_summons_with_cards() -> list[aiosqlite.Row]:
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            SELECT s.* FROM summons s
            WHERE EXISTS (SELECT 1 FROM cards c WHERE c.summon_id = s.id)
            ORDER BY s.name
            """
        )
        return await cur.fetchall()


async def get_summon(summon_id: int) -> aiosqlite.Row | None:
    async with get_conn() as conn:
        cur = await conn.execute("SELECT * FROM summons WHERE id = ?", (summon_id,))
        return await cur.fetchone()


async def add_summon(name: str) -> int:
    async with get_conn() as conn:
        cur = await conn.execute("INSERT INTO summons (name) VALUES (?)", (name,))
        await conn.commit()
        return cur.lastrowid


async def count_cards_in_summon(summon_id: int) -> int:
    async with get_conn() as conn:
        cur = await conn.execute("SELECT COUNT(*) c FROM cards WHERE summon_id = ?", (summon_id,))
        row = await cur.fetchone()
        return row["c"]


async def delete_summon(summon_id: int):
    async with get_conn() as conn:
        await conn.execute(
            "DELETE FROM user_cards WHERE card_id IN (SELECT id FROM cards WHERE summon_id = ?)",
            (summon_id,),
        )
        await conn.execute("DELETE FROM cooldowns WHERE summon_id = ?", (summon_id,))
        await conn.execute("DELETE FROM cards WHERE summon_id = ?", (summon_id,))
        await conn.execute("DELETE FROM summons WHERE id = ?", (summon_id,))
        await conn.commit()


# ---------- cards ----------

async def list_cards_in_summon(summon_id: int) -> list[aiosqlite.Row]:
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            SELECT c.*, r.name AS rarity_name, r.chance AS rarity_chance
            FROM cards c JOIN rarities r ON r.id = c.rarity_id
            WHERE c.summon_id = ?
            ORDER BY c.name
            """,
            (summon_id,),
        )
        return await cur.fetchall()


async def get_card(card_id: int) -> aiosqlite.Row | None:
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            SELECT c.*, r.name AS rarity_name, r.chance AS rarity_chance, s.name AS summon_name
            FROM cards c
            JOIN rarities r ON r.id = c.rarity_id
            JOIN summons s ON s.id = c.summon_id
            WHERE c.id = ?
            """,
            (card_id,),
        )
        return await cur.fetchone()


async def add_card(summon_id: int, photo_file_id: str, name: str, rarity_id: int, exp_reward: int) -> int:
    async with get_conn() as conn:
        cur = await conn.execute(
            "INSERT INTO cards (summon_id, photo_file_id, name, rarity_id, exp_reward) VALUES (?, ?, ?, ?, ?)",
            (summon_id, photo_file_id, name, rarity_id, exp_reward),
        )
        await conn.commit()
        return cur.lastrowid


async def update_card_field(card_id: int, field: str, value):
    assert field in ("photo_file_id", "name", "rarity_id", "exp_reward")
    async with get_conn() as conn:
        await conn.execute(f"UPDATE cards SET {field} = ? WHERE id = ?", (value, card_id))
        await conn.commit()


async def delete_card(card_id: int):
    async with get_conn() as conn:
        await conn.execute("DELETE FROM user_cards WHERE card_id = ?", (card_id,))
        await conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        await conn.commit()


# ---------- user cards / collection ----------

async def owns_card(user_id: int, card_id: int) -> bool:
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT 1 FROM user_cards WHERE user_id = ? AND card_id = ?", (user_id, card_id)
        )
        return (await cur.fetchone()) is not None


async def grant_card(user_id: int, card_id: int):
    async with get_conn() as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO user_cards (user_id, card_id, obtained_at) VALUES (?, ?, ?)",
            (user_id, card_id, int(time.time())),
        )
        await conn.commit()


async def get_collection(user_id: int) -> list[aiosqlite.Row]:
    async with get_conn() as conn:
        cur = await conn.execute(
            """
            SELECT c.id, c.name, r.name AS rarity_name, r.chance AS rarity_chance,
                   s.name AS summon_name, uc.obtained_at
            FROM user_cards uc
            JOIN cards c ON c.id = uc.card_id
            JOIN rarities r ON r.id = c.rarity_id
            JOIN summons s ON s.id = c.summon_id
            WHERE uc.user_id = ?
            ORDER BY uc.obtained_at DESC
            """,
            (user_id,),
        )
        return await cur.fetchall()


# ---------- cooldowns ----------

async def get_cooldown(user_id: int, summon_id: int) -> int | None:
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT last_used FROM cooldowns WHERE user_id = ? AND summon_id = ?",
            (user_id, summon_id),
        )
        row = await cur.fetchone()
        return row["last_used"] if row else None


async def set_cooldown(user_id: int, summon_id: int):
    async with get_conn() as conn:
        await conn.execute(
            """
            INSERT INTO cooldowns (user_id, summon_id, last_used) VALUES (?, ?, ?)
            ON CONFLICT(user_id, summon_id) DO UPDATE SET last_used = excluded.last_used
            """,
            (user_id, summon_id, int(time.time())),
        )
        await conn.commit()
