import os
from dotenv import load_dotenv

# .env faylini yuklash (mahalliy testlar uchun)
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///database.db")

# Admin ID larini tekshirish va massivga o'tkazish
admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = []
if admin_ids_raw:
    for admin_id in admin_ids_raw.split(","):
        admin_id = admin_id.strip()
        if admin_id.isdigit() or (admin_id.startswith("-") and admin_id[1:].isdigit()):
            ADMIN_IDS.append(int(admin_id))

# Kinolar saqlanadigan kanal ID si
movie_channel_id_raw = os.getenv("MOVIE_CHANNEL_ID", "")
MOVIE_CHANNEL_ID = None
if movie_channel_id_raw:
    movie_channel_id_raw = movie_channel_id_raw.strip()
    if movie_channel_id_raw.isdigit() or (movie_channel_id_raw.startswith("-") and movie_channel_id_raw[1:].isdigit()):
        MOVIE_CHANNEL_ID = int(movie_channel_id_raw)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
