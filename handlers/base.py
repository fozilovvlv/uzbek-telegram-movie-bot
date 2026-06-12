import logging
from aiogram import Bot
from database import db

logger = logging.getLogger(__name__)

async def check_user_subscriptions(bot: Bot, user_id: int) -> list:
    """
    Foydalanuvchining homiy kanallarga obunasini tekshiradi.
    Obuna bo'lmagan kanallar ro'yxatini qaytaradi.
    """
    sponsors = await db.get_sponsors()
    not_subscribed = []
    
    for sponsor in sponsors:
        try:
            member = await bot.get_chat_member(chat_id=sponsor['channel_id'], user_id=user_id)
            # Obuna holatlari
            if member.status not in ['creator', 'administrator', 'member']:
                not_subscribed.append(sponsor)
        except Exception as e:
            # Agar bot kanaldan haydalgan yoki kanal topilmasa ham obuna bo'lmagan deb hisoblaymiz
            logger.warning(f"Kanal obunasini tekshirishda xatolik (ID: {sponsor['channel_id']}): {e}")
            not_subscribed.append(sponsor)
            
    return not_subscribed
