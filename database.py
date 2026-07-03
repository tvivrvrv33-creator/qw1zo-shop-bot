import os
import asyncpg

_pool: asyncpg.Pool | None = None


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            raise RuntimeError("DATABASE_URL is not set")
        _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
    return _pool


async def init_db():
    pool = await _get_pool()
    async with pool.acquire() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                stars_balance INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                type TEXT NOT NULL,
                amount TEXT,
                price TEXT,
                extra TEXT,
                receipt_file_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS action_log (
                id SERIAL PRIMARY KEY,
                admin_id BIGINT,
                action TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS giveaway_entries (
                id SERIAL PRIMARY KEY,
                round INTEGER NOT NULL,
                user_id BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(round, user_id)
            )
        """)
        defaults = [
            ("payment_card", "0000 0000 0000 0000"),
            ("sell_rate", "0.40"),
            ("buy_rate", "0.84"),
            ("premium_1m", "120"),
            ("premium_3m", "320"),
            ("premium_6m", "600"),
            ("premium_12m", "1100"),
            ("promo_text",
             "🔥 <b>Пакет 50 ⭐ = 40 грн</b> — найкраща ціна!\n"
             "⭐ 26 ⭐ за 40 грн — ціна як 50 ⭐ у конкурентів\n\n"
             "👑 <b>Premium на 12 місяців</b> — найвигідніший тариф\n\n"
             "📢 Стежте за оновленнями: @qw1zo"),
            ("giveaway_active", "0"),
            ("giveaway_prize", "0"),
            ("giveaway_entry_cost", "0"),
            ("giveaway_round", "1"),
            ("sell_stars_destination", "@qw1zo"),
            ("premium_sticker_id", ""),
        ]
        for key, val in defaults:
            await db.execute(
                "INSERT INTO settings (key, value) VALUES ($1, $2) "
                "ON CONFLICT (key) DO NOTHING",
                key, val
            )


async def get_setting(key: str) -> str:
    pool = await _get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT value FROM settings WHERE key=$1", key)
        return row["value"] if row else ""


async def set_setting(key: str, value: str):
    pool = await _get_pool()
    async with pool.acquire() as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES ($1, $2) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            key, value
        )


async def ensure_user(user_id: int, username: str, first_name: str):
    pool = await _get_pool()
    async with pool.acquire() as db:
        await db.execute(
            "INSERT INTO users (user_id, username, first_name) VALUES ($1, $2, $3) "
            "ON CONFLICT (user_id) DO NOTHING",
            user_id, username, first_name
        )
        await db.execute(
            "UPDATE users SET username=$1, first_name=$2 WHERE user_id=$3",
            username, first_name, user_id
        )


async def get_user(user_id: int) -> dict | None:
    pool = await _get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
        return dict(row) if row else None


async def is_banned(user_id: int) -> bool:
    user = await get_user(user_id)
    return bool(user and user["is_banned"])


async def add_stars_balance(user_id: int, amount: int):
    pool = await _get_pool()
    async with pool.acquire() as db:
        await db.execute(
            "UPDATE users SET stars_balance = stars_balance + $1 WHERE user_id=$2",
            amount, user_id
        )


async def deduct_stars_balance(user_id: int, amount: int) -> bool:
    pool = await _get_pool()
    async with pool.acquire() as db:
        async with db.transaction():
            row = await db.fetchrow(
                "SELECT stars_balance FROM users WHERE user_id=$1 FOR UPDATE", user_id
            )
            if not row or row["stars_balance"] < amount:
                return False
            await db.execute(
                "UPDATE users SET stars_balance = stars_balance - $1 WHERE user_id=$2",
                amount, user_id
            )
            return True


async def create_order(user_id: int, type_: str, amount: str, price: str,
                       extra: str = "", receipt_file_id: str = "") -> int:
    pool = await _get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow(
            "INSERT INTO orders (user_id, type, amount, price, extra, receipt_file_id) "
            "VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
            user_id, type_, amount, price, extra, receipt_file_id
        )
        return row["id"]


async def get_order(order_id: int) -> dict | None:
    pool = await _get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT * FROM orders WHERE id=$1", order_id)
        return dict(row) if row else None


async def update_order_status(order_id: int, status: str):
    pool = await _get_pool()
    async with pool.acquire() as db:
        await db.execute("UPDATE orders SET status=$1 WHERE id=$2", status, order_id)


async def get_pending_orders() -> list[dict]:
    pool = await _get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch(
            "SELECT * FROM orders WHERE status='pending' ORDER BY created_at DESC"
        )
        return [dict(r) for r in rows]


async def get_all_users() -> list[dict]:
    pool = await _get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch("SELECT * FROM users ORDER BY created_at DESC")
        return [dict(r) for r in rows]


async def set_ban(user_id: int, banned: bool):
    pool = await _get_pool()
    async with pool.acquire() as db:
        await db.execute(
            "UPDATE users SET is_banned=$1 WHERE user_id=$2",
            1 if banned else 0, user_id
        )


async def get_stats() -> dict:
    pool = await _get_pool()
    async with pool.acquire() as db:
        total_users = await db.fetchval("SELECT COUNT(*) FROM users")
        pending = await db.fetchval("SELECT COUNT(*) FROM orders WHERE status='pending'")
        confirmed = await db.fetchval("SELECT COUNT(*) FROM orders WHERE status='confirmed'")
        rejected = await db.fetchval("SELECT COUNT(*) FROM orders WHERE status='rejected'")
    return {
        "total_users": total_users,
        "pending": pending,
        "confirmed": confirmed,
        "rejected": rejected,
    }


async def get_buy_stars_by_user(limit: int = 15) -> list[dict]:
    pool = await _get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch(
            """
            SELECT o.user_id AS user_id,
                   u.username AS username,
                   COUNT(*) AS orders_count,
                   SUM(CAST(o.amount AS INTEGER)) AS total_stars,
                   SUM(CAST(o.price AS REAL)) AS total_spent
            FROM orders o
            LEFT JOIN users u ON u.user_id = o.user_id
            WHERE o.type = 'buy_stars' AND o.status = 'confirmed'
            GROUP BY o.user_id
            ORDER BY total_stars DESC
            LIMIT $1
            """,
            limit,
        )
        return [dict(r) for r in rows]


async def get_giveaway() -> dict:
    active = await get_setting("giveaway_active")
    prize = await get_setting("giveaway_prize")
    entry_cost = await get_setting("giveaway_entry_cost")
    round_ = await get_setting("giveaway_round")
    return {
        "active": active == "1",
        "prize": prize or "0",
        "entry_cost": entry_cost or "0",
        "round": int(round_) if round_ and round_.isdigit() else 1,
    }


async def start_giveaway(prize: str, entry_cost: str):
    current_round = await get_setting("giveaway_round")
    next_round = (int(current_round) if current_round and current_round.isdigit() else 0) + 1
    await set_setting("giveaway_prize", prize)
    await set_setting("giveaway_entry_cost", entry_cost)
    await set_setting("giveaway_active", "1")
    await set_setting("giveaway_round", str(next_round))


async def stop_giveaway():
    await set_setting("giveaway_active", "0")


async def has_entered_giveaway(round_: int, user_id: int) -> bool:
    pool = await _get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow(
            "SELECT 1 FROM giveaway_entries WHERE round=$1 AND user_id=$2",
            round_, user_id
        )
        return row is not None


async def add_giveaway_entry(round_: int, user_id: int) -> bool:
    pool = await _get_pool()
    async with pool.acquire() as db:
        try:
            await db.execute(
                "INSERT INTO giveaway_entries (round, user_id) VALUES ($1, $2)",
                round_, user_id
            )
            return True
        except Exception:
            return False


async def count_giveaway_entries(round_: int) -> int:
    pool = await _get_pool()
    async with pool.acquire() as db:
        return await db.fetchval(
            "SELECT COUNT(*) FROM giveaway_entries WHERE round=$1", round_
        )


async def get_giveaway_entrants(round_: int) -> list[int]:
    pool = await _get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch(
            "SELECT user_id FROM giveaway_entries WHERE round=$1", round_
        )
        return [r["user_id"] for r in rows]


async def add_log(admin_id: int, action: str, details: str = ""):
    pool = await _get_pool()
    async with pool.acquire() as db:
        await db.execute(
            "INSERT INTO action_log (admin_id, action, details) VALUES ($1, $2, $3)",
            admin_id, action, details
        )


async def get_logs(limit: int = 30) -> list[dict]:
    pool = await _get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch(
            "SELECT * FROM action_log ORDER BY created_at DESC LIMIT $1", limit
        )
        return [dict(r) for r in rows]
