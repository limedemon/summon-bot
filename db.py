import time

import asyncpg

from config import DATABASE_URL

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS admins (
    user_id BIGINT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    exp BIGINT NOT NULL DEFAULT 0,
    first_seen BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS rarities (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    chance TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS summons (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cards (
    id SERIAL PRIMARY KEY,
    summon_id INTEGER NOT NULL REFERENCES summons(id) ON DELETE CASCADE,
    photo_file_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rarity_id INTEGER NOT NULL REFERENCES rarities(id),
    exp_reward BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_cards (
    user_id BIGINT NOT NULL,
    card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    obtained_at BIGINT NOT NULL,
    PRIMARY KEY (user_id, card_id)
);

CREATE TABLE IF NOT EXISTS cooldowns (
    user_id BIGINT NOT NULL,
    summon_id INTEGER NOT NULL REFERENCES summons(id) ON DELETE CASCADE,
    last_used BIGINT NOT NULL,
    PRIMARY KEY (user_id, summon_id)
);
"""

_pool: asyncpg.Pool | None = None


async def init_db():
    global _pool
    _pool = await asyncpg.create_pool(dsn=DATABASE_URL)
    async with _pool.acquire() as conn:
        await conn.execute(SCHEMA)


async def close_db():
    if _pool is not None:
        await _pool.close()


# ---------- meta / users / admins ----------

async def ensure_user(user_id: int) -> bool:
    """Registers the user if new. Returns True if this user just became the main admin."""
    became_main_admin = False
    async with _pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO users (user_id, exp, first_seen) VALUES ($1, 0, $2) "
                "ON CONFLICT (user_id) DO NOTHING",
                user_id, int(time.time()),
            )
            row = await conn.fetchrow("SELECT value FROM meta WHERE key = 'main_admin_id'")
            if row is None:
                await conn.execute(
                    "INSERT INTO meta (key, value) VALUES ('main_admin_id', $1)", str(user_id)
                )
                await conn.execute(
                    "INSERT INTO admins (user_id) VALUES ($1) ON CONFLICT DO NOTHING", user_id
                )
                became_main_admin = True
    return became_main_admin


async def get_main_admin_id() -> int | None:
    async with _pool.acquire() as conn:
        row = await conn.fetchrow("SELECT value FROM meta WHERE key = 'main_admin_id'")
        return int(row["value"]) if row else None


async def get_admin_ids() -> list[int]:
    async with _pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM admins")
        return [r["user_id"] for r in rows]


async def is_admin(user_id: int) -> bool:
    async with _pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM admins WHERE user_id = $1", user_id)
        return row is not None


async def add_admin(user_id: int):
    async with _pool.acquire() as conn:
        await conn.execute("INSERT INTO admins (user_id) VALUES ($1) ON CONFLICT DO NOTHING", user_id)


async def remove_admin(user_id: int):
    async with _pool.acquire() as conn:
        await conn.execute("DELETE FROM admins WHERE user_id = $1", user_id)


async def get_user(user_id: int) -> asyncpg.Record | None:
    async with _pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)


async def add_exp(user_id: int, amount: int):
    async with _pool.acquire() as conn:
        await conn.execute("UPDATE users SET exp = exp + $1 WHERE user_id = $2", amount, user_id)


# ---------- rarities ----------

async def list_rarities_sorted() -> list[asyncpg.Record]:
    async with _pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM rarities")
        return sorted(rows, key=lambda r: float(r["chance"]), reverse=True)


async def get_rarity(rarity_id: int) -> asyncpg.Record | None:
    async with _pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM rarities WHERE id = $1", rarity_id)


async def add_rarity(name: str, chance: str) -> int:
    async with _pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO rarities (name, chance) VALUES ($1, $2) RETURNING id", name, chance
        )


async def update_rarity_name(rarity_id: int, name: str):
    async with _pool.acquire() as conn:
        await conn.execute("UPDATE rarities SET name = $1 WHERE id = $2", name, rarity_id)


async def update_rarity_chance(rarity_id: int, chance: str):
    async with _pool.acquire() as conn:
        await conn.execute("UPDATE rarities SET chance = $1 WHERE id = $2", chance, rarity_id)


async def count_cards_with_rarity(rarity_id: int) -> int:
    async with _pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM cards WHERE rarity_id = $1", rarity_id)


async def delete_rarity(rarity_id: int):
    async with _pool.acquire() as conn:
        await conn.execute("DELETE FROM rarities WHERE id = $1", rarity_id)


# ---------- summons ----------

async def list_summons() -> list[asyncpg.Record]:
    async with _pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM summons ORDER BY name")


async def list_summons_with_cards() -> list[asyncpg.Record]:
    async with _pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT s.* FROM summons s
            WHERE EXISTS (SELECT 1 FROM cards c WHERE c.summon_id = s.id)
            ORDER BY s.name
            """
        )


async def get_summon(summon_id: int) -> asyncpg.Record | None:
    async with _pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM summons WHERE id = $1", summon_id)


async def add_summon(name: str) -> int:
    async with _pool.acquire() as conn:
        return await conn.fetchval("INSERT INTO summons (name) VALUES ($1) RETURNING id", name)


async def count_cards_in_summon(summon_id: int) -> int:
    async with _pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM cards WHERE summon_id = $1", summon_id)


async def delete_summon(summon_id: int):
    async with _pool.acquire() as conn:
        # cascades to cards, user_cards and cooldowns via foreign keys
        await conn.execute("DELETE FROM summons WHERE id = $1", summon_id)


# ---------- cards ----------

async def list_cards_in_summon(summon_id: int) -> list[asyncpg.Record]:
    async with _pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT c.*, r.name AS rarity_name, r.chance AS rarity_chance
            FROM cards c JOIN rarities r ON r.id = c.rarity_id
            WHERE c.summon_id = $1
            ORDER BY c.name
            """,
            summon_id,
        )


async def get_card(card_id: int) -> asyncpg.Record | None:
    async with _pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT c.*, r.name AS rarity_name, r.chance AS rarity_chance, s.name AS summon_name
            FROM cards c
            JOIN rarities r ON r.id = c.rarity_id
            JOIN summons s ON s.id = c.summon_id
            WHERE c.id = $1
            """,
            card_id,
        )


async def add_card(summon_id: int, photo_file_id: str, name: str, rarity_id: int, exp_reward: int) -> int:
    async with _pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO cards (summon_id, photo_file_id, name, rarity_id, exp_reward) "
            "VALUES ($1, $2, $3, $4, $5) RETURNING id",
            summon_id, photo_file_id, name, rarity_id, exp_reward,
        )


async def update_card_field(card_id: int, field: str, value):
    assert field in ("photo_file_id", "name", "rarity_id", "exp_reward")
    async with _pool.acquire() as conn:
        await conn.execute(f"UPDATE cards SET {field} = $1 WHERE id = $2", value, card_id)


async def delete_card(card_id: int):
    async with _pool.acquire() as conn:
        # cascades to user_cards via foreign key
        await conn.execute("DELETE FROM cards WHERE id = $1", card_id)


# ---------- user cards / collection ----------

async def owns_card(user_id: int, card_id: int) -> bool:
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM user_cards WHERE user_id = $1 AND card_id = $2", user_id, card_id
        )
        return row is not None


async def grant_card(user_id: int, card_id: int):
    async with _pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO user_cards (user_id, card_id, obtained_at) VALUES ($1, $2, $3) "
            "ON CONFLICT DO NOTHING",
            user_id, card_id, int(time.time()),
        )


async def get_collection(user_id: int) -> list[asyncpg.Record]:
    async with _pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT c.id, c.name, r.name AS rarity_name, r.chance AS rarity_chance,
                   s.name AS summon_name, uc.obtained_at
            FROM user_cards uc
            JOIN cards c ON c.id = uc.card_id
            JOIN rarities r ON r.id = c.rarity_id
            JOIN summons s ON s.id = c.summon_id
            WHERE uc.user_id = $1
            ORDER BY uc.obtained_at DESC
            """,
            user_id,
        )


# ---------- cooldowns ----------

async def get_cooldown(user_id: int, summon_id: int) -> int | None:
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT last_used FROM cooldowns WHERE user_id = $1 AND summon_id = $2",
            user_id, summon_id,
        )
        return row["last_used"] if row else None


async def set_cooldown(user_id: int, summon_id: int):
    async with _pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO cooldowns (user_id, summon_id, last_used) VALUES ($1, $2, $3)
            ON CONFLICT (user_id, summon_id) DO UPDATE SET last_used = EXCLUDED.last_used
            """,
            user_id, summon_id, int(time.time()),
        )
