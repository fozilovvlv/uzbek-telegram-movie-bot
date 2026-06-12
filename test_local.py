import sys
import os
import unittest
import asyncio

# Hozirgi katalogni yuklash ro'yxatiga qo'shamiz
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

class TestBotCode(unittest.TestCase):
    def test_imports(self):
        """Tizimdagi barcha modullar to'g'ri import bo'lishini va sintaksisda xatolar yo'qligini tekshirish"""
        try:
            import config
            import database
            import handlers
            from handlers.user import user_router
            from handlers.admin import admin_router
            self.assertIsNotNone(user_router)
            self.assertIsNotNone(admin_router)
            print("[OK] Barcha modullar muvaffaqiyatli import qilindi.")
        except Exception as e:
            self.fail(f"[ERROR] Import qilishda xatolik yuz berdi: {e}")

    def test_database_sqlite(self):
        """SQLite ma'lumotlar bazasi in-memory rejimida ishlashini tekshirish"""
        async def run_db_test():
            from database import Database
            # In-memory SQLite bazasi (xotirada vaqtincha ochiladi, diskka yozilmaydi)
            db_test = Database("sqlite:///:memory:")
            await db_test.connect()
            
            # Foydalanuvchi yozish va o'qish testi
            await db_test.add_user(12345, "test_user", "Test Fullname")
            user = await db_test.get_user(12345)
            self.assertIsNotNone(user)
            self.assertEqual(user['username'], "test_user")
            
            # Homiy kanal yozish va o'qish testi
            await db_test.add_sponsor(-1001234567, "Test Sponsor", "https://t.me/test_link")
            sponsors = await db_test.get_sponsors()
            self.assertEqual(len(sponsors), 1)
            self.assertEqual(sponsors[0]['name'], "Test Sponsor")
            
            # Kino yozish va o'qish testi
            await db_test.add_movie("555", "file_abc", "video", "Kino 555", 999)
            movie = await db_test.get_movie("555")
            self.assertIsNotNone(movie)
            self.assertEqual(movie['file_id'], "file_abc")
            
            # Ko'rishlar sonini oshirish testi
            await db_test.increment_movie_views("555")
            movie_updated = await db_test.get_movie("555")
            self.assertEqual(movie_updated['views'], 1)
            
            # Baza ulanishini yopish
            await db_test.close()
            print("[OK] SQLite ma'lumotlar bazasi testlari muvaffaqiyatli o'tdi.")

        asyncio.run(run_db_test())

if __name__ == '__main__':
    unittest.main()
