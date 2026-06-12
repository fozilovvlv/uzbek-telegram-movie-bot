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
        is_member = False
        try:
            member = await bot.get_chat_member(chat_id=sponsor['channel_id'], user_id=user_id)
            # Obuna holatlari
            if member.status in ['creator', 'administrator', 'member']:
                is_member = True
        except Exception as e:
            logger.warning(f"Kanal obunasini tekshirishda xatolik (ID: {sponsor['channel_id']}): {e}")
            
        if not is_member:
            # Agar Telegram bo'yicha obuna bo'lmagan bo'lsa, yopiq kanalga qo'shilish so'rovi yuborganligini tekshiramiz
            req = await db.get_join_request(sponsor['channel_id'], user_id)
            if req and req['status'] == 'pending':
                # So'rov yuborilgan (pending holatida) bo'lsa, obuna bo'lgan deb hisoblaymiz
                continue
            not_subscribed.append(sponsor)
            
    return not_subscribed
