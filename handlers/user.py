import logging
from aiogram import Router, Bot, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from handlers.base import check_user_subscriptions
import config

logger = logging.getLogger(__name__)
user_router = Router()

def get_sub_keyboard(not_subscribed: list) -> InlineKeyboardMarkup:
    keyboard = []
    for chan in not_subscribed:
        keyboard.append([InlineKeyboardButton(text=f"🔗 {chan['name']}", url=chan['invite_link'])])
    
    keyboard.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@user_router.message(CommandStart())
async def start_cmd(message: types.Message, bot: Bot):
    user_id = message.from_user.id
    username = message.from_user.username
    fullname = message.from_user.full_name
    
    # Foydalanuvchini bazaga qo'shish
    await db.add_user(user_id, username, fullname)
    
    # Obunani tekshirish
    not_subscribed = await check_user_subscriptions(bot, user_id)
    
    if not_subscribed:
        markup = get_sub_keyboard(not_subscribed)
        await message.answer(
            "⚠️ Siz hali barcha kanallarga obuna bo'lmadingiz. Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:",
            reply_markup=markup
        )
    else:
        await message.answer("🎬 Kino kodini yuboring:")

@user_router.callback_query(F.data == "check_sub")
async def check_sub_callback(call: types.CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    not_subscribed = await check_user_subscriptions(bot, user_id)
    
    if not_subscribed:
        await call.answer("⚠️ Siz hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)
        # Tugmalarni yangilash (faqat qolgan kanallarni ko'rsatish)
        markup = get_sub_keyboard(not_subscribed)
        try:
            await call.message.edit_reply_markup(reply_markup=markup)
        except Exception:
            pass  # Agar tugmalar o'zgarmagan bo'lsa xato bermasligi uchun
    else:
        await call.answer("✅ Rahmat! Obuna tasdiqlandi.", show_alert=True)
        await call.message.delete()
        await call.message.answer("🎬 Kino kodini yuboring:")

@user_router.message(F.text & ~F.text.startswith('/'))
async def movie_search_handler(message: types.Message, bot: Bot):
    user_id = message.from_user.id
    code = message.text.strip()
    
    # Obunani tekshirish
    not_subscribed = await check_user_subscriptions(bot, user_id)
    if not_subscribed:
        markup = get_sub_keyboard(not_subscribed)
        await message.answer(
            "⚠️ Siz hali barcha kanallarga obuna bo'lmadingiz. Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:",
            reply_markup=markup
        )
        return
        
    # Kinoni qidirish
    movie = await db.get_movie(code)
    
    if not movie:
        await message.answer("😔 Kechirasiz, bunday kodli kino topilmadi. Iltimos, kodni to'g'ri kiritganingizni tekshiring.")
        return
        
    # Ko'rishlar sonini oshirish
    await db.increment_movie_views(code)
    
    # Kinoni yuborish
    try:
        # 1-usul: MOVIE_CHANNEL_ID va channel_message_id orqali ko'chirib o'tkazish (copy_message)
        if config.MOVIE_CHANNEL_ID and movie['channel_message_id']:
            try:
                await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=config.MOVIE_CHANNEL_ID,
                    message_id=movie['channel_message_id'],
                    caption=movie['caption'] or None
                )
                return
            except Exception as e:
                logger.warning(f"Kanal xabarini nusxalashda xatolik (kod: {code}): {e}. Fayl ID orqali yuborishga o'tiladi.")
        
        # 2-usul: File ID orqali to'g'ridan-to'g'ri yuborish (fallback)
        file_id = movie['file_id']
        file_type = movie['file_type']
        caption = movie['caption'] or ""
        
        if file_type == 'video':
            await bot.send_video(chat_id=user_id, video=file_id, caption=caption)
        elif file_type == 'document':
            await bot.send_document(chat_id=user_id, document=file_id, caption=caption)
        elif file_type == 'photo':
            await bot.send_photo(chat_id=user_id, photo=file_id, caption=caption)
        elif file_type == 'audio':
            await bot.send_audio(chat_id=user_id, audio=file_id, caption=caption)
        else:
            # Agar faqat matnli bo'lsa
            await bot.send_message(chat_id=user_id, text=caption)
            
    except Exception as e:
        logger.error(f"Kinoni yuborishda xatolik yuz berdi (kod: {code}): {e}")
        await message.answer("⚠️ Kechirasiz, kinoni yuborishda texnik xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko'ring.")
