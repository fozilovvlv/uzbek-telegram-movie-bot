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
    is_adm = (user_id in config.ADMIN_IDS) or (await db.is_assistant_admin(user_id))
    if is_adm:
        not_subscribed = []
    else:
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
    is_adm = (user_id in config.ADMIN_IDS) or (await db.is_assistant_admin(user_id))
    if is_adm:
        not_subscribed = []
    else:
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
    is_adm = (user_id in config.ADMIN_IDS) or (await db.is_assistant_admin(user_id))
    if is_adm:
        not_subscribed = []
    else:
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

# --- Yopiq kanallarga qo'shilish so'rovlarini (Join Requests) qayd etish ---
@user_router.chat_join_request()
async def on_chat_join_request(request: types.ChatJoinRequest):
    chat = request.chat
    user_id = request.from_user.id
    
    # Kanal homiy kanallar ro'yxatida borligini tekshiramiz
    sponsors = await db.get_sponsors()
    sponsor = next((s for s in sponsors if s['channel_id'] == chat.id), None)
    if not sponsor:
        return
        
    # Bazaga qo'shilish so'rovi yuborilganligini yozib qo'yamiz
    await db.add_join_request(chat.id, user_id, "pending")
    logger.info(f"Foydalanuvchi {user_id} '{chat.title}' kanaliga qo'shilish so'rovini yubordi.")

# --- Kanal a'zoligi holati o'zgarganda (masalan, tark etganda) ogohlantirish ---
@user_router.chat_member()
async def on_chat_member_update(update: types.ChatMemberUpdated, bot: Bot):
    chat = update.chat
    if chat.type != "channel":
        return
        
    user_id = update.new_chat_member.user.id
    old_status = update.old_chat_member.status
    new_status = update.new_chat_member.status
    
    # Kanal homiy kanallar ro'yxatida borligini tekshiramiz
    sponsors = await db.get_sponsors()
    sponsor = next((s for s in sponsors if s['channel_id'] == chat.id), None)
    if not sponsor:
        return
        
    # Agar foydalanuvchi rasman a'zo bo'lsa (admin tasdiqlagan yoki ommaviy kanalga kirgan)
    if new_status in ['member', 'administrator', 'creator']:
        await db.remove_join_request(chat.id, user_id)
        
    # Agar foydalanuvchi kanalni tark etgan bo'lsa (left, kicked)
    was_member = old_status in ['member', 'administrator', 'creator']
    is_no_longer_member = new_status in ['left', 'kicked']
    
    if was_member and is_no_longer_member:
        # Bazadagi so'rovlarni ham tozalaymiz
        await db.remove_join_request(chat.id, user_id)
        
        # Foydalanuvchiga ogohlantirish xabarini yuboramiz
        try:
            await bot.send_message(
                chat_id=user_id,
                text=f"⚠️ Siz '{sponsor['name']}' kanalini tark etdingiz!\n\n"
                     f"Qayta obuna bo'lmasangiz bot xizmatlaridan foydalana olmaysiz:\n"
                     f"👉 {sponsor['invite_link']}"
            )
            logger.info(f"Foydalanuvchi {user_id} '{sponsor['name']}' kanalini tark etgani uchun ogohlantirildi.")
        except Exception as e:
            logger.warning(f"Foydalanuvchi {user_id} ga ogohlantirish yuborishda xatolik: {e}")

