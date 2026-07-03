import asyncio
import aiosqlite
from config import DB_PATH

_backup_task: asyncio.Task | None = None


def _schedule_backup():
    global _backup_task
    import github_backup

    async def _delayed():
        await asyncio.sleep(5)
        await github_backup.backup_to_github(DB_PATH)

    if _backup_task is None or _backup_task.done():
        try:
            _backup_task = asyncio.create_task(_delayed())
        except RuntimeError:
            pass


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                stars_balance INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                action TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS giveaway_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
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
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, val)
            )
        await db.commit()


async def get_setting(key: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else ""


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        await db.commit()
    _schedule_backup()


async def ensure_user(user_id: int, username: str, first_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
            (user_id, username, first_name)
        )
        await db.execute(
            "UPDATE users SET username=?, first_name=? WHERE user_id=?",
            (username, first_name, user_id)
        )
        await db.commit()


async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def is_banned(user_id: int) -> bool:
    user = await get_user(user_id)
    return bool(user and user["is_banned"])


async def add_stars_balance(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET stars_balance = stars_balance + ? WHERE user_id=?",
            (amount, user_id)
        )
        await db.commit()
    _schedule_backup()


async def deduct_stars_balance(user_id: int, amount: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT stars_balance FROM users WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            if not row or row[0] < amount:
                return False
        await db.execute(
            "UPDATE users SET stars_balance = stars_balance - ? WHERE user_id=?",
            (amount, user_id)
        )
        await db.commit()
        _schedule_backup()
        return True


async def create_order(user_id: int, type_: str, amount: str, price: str,
                       extra: str = "", receipt_file_id: str = "") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO orders (user_id, type, amount, price, extra, receipt_file_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, type_, amount, price, extra, receipt_file_id)
        )
        await db.commit()
        _schedule_backup()
        return cur.lastrowid


async def get_order(order_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM orders WHERE id=?", (order_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def update_order_status(order_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET status=? WHERE id=?", (status, order_id)
        )
        await db.commit()
    _schedule_backup()


async def get_pending_orders() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM orders WHERE status='pending' ORDER BY created_at DESC"
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_all_users() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users ORDER BY created_at DESC") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def set_ban(user_id: int, banned: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_banned=? WHERE user_id=?",
            (1 if banned else 0, user_id)
        )
        await db.commit()
    _schedule_backup()


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            total_users = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM orders WHERE status='pending'") as cur:
            pending = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM orders WHERE status='confirmed'") as cur:
            confirmed = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM orders WHERE status='rejected'") as cur:
            rejected = (await cur.fetchone())[0]
    return {
        "total_users": total_users,
        "pending": pending,
        "confirmed": confirmed,
        "rejected": rejected,
    }


async def get_buy_stars_by_user(limit: int = 15) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
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
            LIMIT ?
            """,
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
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
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM giveaway_entries WHERE round=? AND user_id=?",
            (round_, user_id)
        ) as cur:
            row = await cur.fetchone()
            return row is not None


async def add_giveaway_entry(round_: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO giveaway_entries (round, user_id) VALUES (?, ?)",
                (round_, user_id)
            )
            await db.commit()
            _schedule_backup()
            return True
        except Exception:
            return False


async def count_giveaway_entries(round_: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM giveaway_entries WHERE round=?", (round_,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def get_giveaway_entrants(round_: int) -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id FROM giveaway_entries WHERE round=?", (round_,)
        ) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def add_log(admin_id: int, action: str, details: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO action_log (admin_id, action, details) VALUES (?, ?, ?)",
            (admin_id, action, details)
        )
        await db.commit()


async def get_logs(limit: int = 30) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM action_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
