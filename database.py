import os
import re
import logging
from datetime import datetime
import config

logger = logging.getLogger(__name__)

# Baza kutubxonalarini shartli yuklash (agar o'rnatilmagan bo'lsa xato qilmasligi uchun)
try:
    import aiosqlite
except ImportError:
    aiosqlite = None

try:
    import asyncpg
except ImportError:
    asyncpg = None

class Database:
    def __init__(self, db_url: str):
        self.db_url = db_url
        # Baza turini aniqlash
        if db_url.startswith("postgres://") or db_url.startswith("postgresql://"):
            self.db_type = "postgres"
            # Railway kabi platformalarda postgresql:// formatini to'g'irlash
            if db_url.startswith("postgres://"):
                self.db_url = db_url.replace("postgres://", "postgresql://", 1)
        else:
            self.db_type = "sqlite"
            # SQLite fayl nomini aniqlash (sqlite:///database.db -> database.db)
            self.sqlite_file = db_url.replace("sqlite:///", "").replace("sqlite://", "")
            if not self.sqlite_file:
                self.sqlite_file = "database.db"
        
        self.postgres_pool = None
        self.sqlite_conn = None

    async def connect(self):
        if self.db_type == "postgres":
            if not asyncpg:
                raise ImportError("PostgreSQL ishlatish uchun 'asyncpg' kutubxonasi o'rnatilgan bo'lishi kerak!")
            try:
                self.postgres_pool = await asyncpg.create_pool(self.db_url)
                logger.info("PostgreSQL-ga ulanish muvaffaqiyatli o'rnatildi.")
            except Exception as e:
                logger.error(f"PostgreSQL-ga ulanishda xatolik: {e}")
                raise e
        else:
            if not aiosqlite:
                raise ImportError("SQLite ishlatish uchun 'aiosqlite' kutubxonasi o'rnatilgan bo'lishi kerak!")
            try:
                self.sqlite_conn = await aiosqlite.connect(self.sqlite_file)
                # Olingan natijalarni dictionary/row ko'rinishida olish uchun row_factory o'rnatamiz
                self.sqlite_conn.row_factory = aiosqlite.Row
                logger.info(f"SQLite-ga ulanish muvaffaqiyatli o'rnatildi: {self.sqlite_file}")
            except Exception as e:
                logger.error(f"SQLite-ga ulanishda xatolik: {e}")
                raise e
        
        await self.create_tables()

    async def close(self):
        if self.db_type == "postgres" and self.postgres_pool:
            await self.postgres_pool.close()
        elif self.db_type == "sqlite" and self.sqlite_conn:
            await self.sqlite_conn.close()

    def _translate_query(self, query: str) -> str:
        """PostgreSQL ($1, $2) formatidagi so'rovlarni SQLite (?) formatiga o'tkazadi"""
        if self.db_type == "sqlite":
            return re.sub(r'\$\d+', '?', query)
        return query

    async def execute(self, query: str, *args):
        translated_query = self._translate_query(query)
        if self.db_type == "postgres":
            async with self.postgres_pool.acquire() as conn:
                return await conn.execute(translated_query, *args)
        else:
            async with self.sqlite_conn.execute(translated_query, args) as cursor:
                await self.sqlite_conn.commit()
                return cursor.rowcount

    async def fetch(self, query: str, *args):
        translated_query = self._translate_query(query)
        if self.db_type == "postgres":
            async with self.postgres_pool.acquire() as conn:
                records = await conn.fetch(translated_query, *args)
                return [dict(r) for r in records]
        else:
            async with self.sqlite_conn.execute(translated_query, args) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def fetchrow(self, query: str, *args):
        translated_query = self._translate_query(query)
        if self.db_type == "postgres":
            async with self.postgres_pool.acquire() as conn:
                record = await conn.fetchrow(translated_query, *args)
                return dict(record) if record else None
        else:
            async with self.sqlite_conn.execute(translated_query, args) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def create_tables(self):
        # Users jadvali
        if self.db_type == "postgres":
            await self.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    fullname VARCHAR(255),
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self.execute("""
                CREATE TABLE IF NOT EXISTS sponsors (
                    id SERIAL PRIMARY KEY,
                    channel_id BIGINT UNIQUE,
                    name VARCHAR(255),
                    invite_link TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self.execute("""
                CREATE TABLE IF NOT EXISTS movies (
                    id SERIAL PRIMARY KEY,
                    code VARCHAR(100) UNIQUE,
                    file_id TEXT,
                    file_type VARCHAR(50),
                    caption TEXT,
                    channel_message_id BIGINT,
                    views INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self.execute("""
                CREATE TABLE IF NOT EXISTS bot_channels (
                    channel_id BIGINT PRIMARY KEY,
                    title VARCHAR(255),
                    username VARCHAR(255),
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self.execute("""
                CREATE TABLE IF NOT EXISTS join_requests (
                    channel_id BIGINT,
                    user_id BIGINT,
                    status VARCHAR(50),
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (channel_id, user_id)
                )
            """)
        else:
            await self.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    fullname TEXT,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self.execute("""
                CREATE TABLE IF NOT EXISTS sponsors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER UNIQUE,
                    name TEXT,
                    invite_link TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self.execute("""
                CREATE TABLE IF NOT EXISTS movies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE,
                    file_id TEXT,
                    file_type TEXT,
                    caption TEXT,
                    channel_message_id INTEGER,
                    views INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self.execute("""
                CREATE TABLE IF NOT EXISTS bot_channels (
                    channel_id INTEGER PRIMARY KEY,
                    title TEXT,
                    username TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self.execute("""
                CREATE TABLE IF NOT EXISTS join_requests (
                    channel_id INTEGER,
                    user_id INTEGER,
                    status TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (channel_id, user_id)
                )
            """)

    # --- Foydalanuvchilar bilan ishlash ---
    async def add_user(self, user_id: int, username: str, fullname: str):
        query = """
            INSERT INTO users (id, username, fullname, joined_at)
            VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO UPDATE 
            SET username = EXCLUDED.username, fullname = EXCLUDED.fullname
        """
        await self.execute(query, user_id, username, fullname)

    async def get_user(self, user_id: int):
        return await self.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

    async def get_users_count(self) -> int:
        res = await self.fetchrow("SELECT COUNT(*) as cnt FROM users")
        return res['cnt'] if res else 0

    async def get_all_users_ids(self):
        rows = await self.fetch("SELECT id FROM users")
        return [r['id'] for r in rows]

    # --- Homiylar (Kanallar) bilan ishlash ---
    async def add_sponsor(self, channel_id: int, name: str, invite_link: str):
        query = """
            INSERT INTO sponsors (channel_id, name, invite_link, created_at)
            VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
            ON CONFLICT (channel_id) DO UPDATE 
            SET name = EXCLUDED.name, invite_link = EXCLUDED.invite_link
        """
        await self.execute(query, channel_id, name, invite_link)

    async def remove_sponsor(self, channel_id: int):
        await self.execute("DELETE FROM sponsors WHERE channel_id = $1", channel_id)

    async def get_sponsors(self):
        return await self.fetch("SELECT * FROM sponsors ORDER BY id ASC")

    # --- Kinolar bilan ishlash ---
    async def add_movie(self, code: str, file_id: str = None, file_type: str = None, caption: str = None, channel_message_id: int = None):
        query = """
            INSERT INTO movies (code, file_id, file_type, caption, channel_message_id, views, created_at)
            VALUES ($1, $2, $3, $4, $5, 0, CURRENT_TIMESTAMP)
            ON CONFLICT (code) DO UPDATE 
            SET file_id = EXCLUDED.file_id, 
                file_type = EXCLUDED.file_type, 
                caption = EXCLUDED.caption, 
                channel_message_id = EXCLUDED.channel_message_id
        """
        await self.execute(query, code, file_id, file_type, caption, channel_message_id)

    async def remove_movie(self, code: str):
        await self.execute("DELETE FROM movies WHERE code = $1", code)

    async def get_movie(self, code: str):
        return await self.fetchrow("SELECT * FROM movies WHERE code = $1", code)

    async def get_movies_count(self) -> int:
        res = await self.fetchrow("SELECT COUNT(*) as cnt FROM movies")
        return res['cnt'] if res else 0

    async def increment_movie_views(self, code: str):
        await self.execute("UPDATE movies SET views = views + 1 WHERE code = $1", code)

    # --- Bot a'zo bo'lgan kanallarni vaqtincha saqlash (ID aniqlash uchun) ---
    async def save_bot_channel(self, channel_id: int, title: str, username: str = None):
        query = """
            INSERT INTO bot_channels (channel_id, title, username, updated_at)
            VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
            ON CONFLICT (channel_id) DO UPDATE 
            SET title = EXCLUDED.title, username = EXCLUDED.username, updated_at = CURRENT_TIMESTAMP
        """
        await self.execute(query, channel_id, title, username)

    async def remove_bot_channel(self, channel_id: int):
        await self.execute("DELETE FROM bot_channels WHERE channel_id = $1", channel_id)

    async def get_bot_channels(self):
        return await self.fetch("SELECT * FROM bot_channels")

    # --- Qo'shilish so'rovlari (Join Requests) ---
    async def add_join_request(self, channel_id: int, user_id: int, status: str):
        query = """
            INSERT INTO join_requests (channel_id, user_id, status, updated_at)
            VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
            ON CONFLICT (channel_id, user_id) DO UPDATE 
            SET status = EXCLUDED.status, updated_at = CURRENT_TIMESTAMP
        """
        await self.execute(query, channel_id, user_id, status)

    async def get_join_request(self, channel_id: int, user_id: int):
        return await self.fetchrow("SELECT * FROM join_requests WHERE channel_id = $1 AND user_id = $2", channel_id, user_id)

    async def remove_join_request(self, channel_id: int, user_id: int):
        await self.execute("DELETE FROM join_requests WHERE channel_id = $1 AND user_id = $2", channel_id, user_id)

# Global ma'lumotlar bazasi obyekti
db = Database(config.DATABASE_URL)
