import logging
import re
from aiogram import Router, Bot, F, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import db
import config

logger = logging.getLogger(__name__)
admin_router = Router()

# FSM holatlari
class AdminStates(StatesGroup):
    # Kanal qo'shish
    waiting_for_channel_name = State()
    waiting_for_channel_link = State()
    waiting_for_channel_id_fallback = State()
    
    # Kino qo'shish
    waiting_for_movie_code = State()
    waiting_for_movie_file = State()
    
    # Kino o'chirish
    waiting_for_delete_movie_code = State()
    
    # Reklama tarqatish
    waiting_for_broadcast_msg = State()
    
    # Yordamchi admin qo'shish
    waiting_for_coadmin_id = State()
    
    # Asosiy admin qo'shish
    waiting_for_main_admin_id = State()

# Asosiy adminlikni tekshirish (Env + DB)
async def is_main_admin(user_id: int) -> bool:
    if user_id in config.ADMIN_IDS:
        return True
    return await db.is_main_admin_db(user_id)

# Admin ekanligini tekshirish uchun yordamchi funksiya (asosiy yoki yordamchi)
async def check_admin(user_id: int) -> bool:
    return (await is_main_admin(user_id)) or (await db.is_assistant_admin(user_id))

async def get_admin_keyboard(user_id: int) -> InlineKeyboardMarkup:
    is_main = await is_main_admin(user_id)
    if is_main:
        keyboard = [
            [
                InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="admin_add_channel"),
                InlineKeyboardButton(text="➖ Kanal o'chirish", callback_data="admin_remove_channel")
            ],
            [
                InlineKeyboardButton(text="📋 Kanallar ro'yxati", callback_data="admin_list_channels"),
                InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")
            ],
            [
                InlineKeyboardButton(text="➕ Kino qo'shish", callback_data="admin_add_movie"),
                InlineKeyboardButton(text="➖ Kino o'chirish", callback_data="admin_remove_movie")
            ],
            [
                InlineKeyboardButton(text="➕ Yordamchi admin", callback_data="admin_add_coadmin"),
                InlineKeyboardButton(text="➖ Yordamchi admin", callback_data="admin_remove_coadmin")
            ],
            [
                InlineKeyboardButton(text="➕ Asosiy admin", callback_data="admin_add_main"),
                InlineKeyboardButton(text="➖ Asosiy admin", callback_data="admin_remove_main")
            ],
            [
                InlineKeyboardButton(text="📢 Xabar yuborish", callback_data="admin_broadcast")
            ]
        ]
    else:
        # Faqat kino qo'shish tugmasi bo'lgan cheklangan menyu (yordamchi admin uchun)
        keyboard = [
            [
                InlineKeyboardButton(text="➕ Kino qo'shish", callback_data="admin_add_movie"),
                InlineKeyboardButton(text="❌ Chiqish", callback_data="admin_cancel")
            ]
        ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel")]
    ])

# Xabar admin ekanligini tekshiruvchi yordamchi (asosiy yoki yordamchi)
async def is_sender_admin(message: types.Message) -> bool:
    if not await check_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz.")
        return False
    return True

# Callback so'rov admin ekanligini tekshiruvchi yordamchi (asosiy yoki yordamchi)
async def is_callback_admin(call: types.CallbackQuery) -> bool:
    if not await check_admin(call.from_user.id):
        await call.answer("❌ Siz admin emassiz.", show_alert=True)
        return False
    return True

# Faqat asosiy adminligini tekshiruvchi yordamchilar
async def is_sender_main_admin(message: types.Message) -> bool:
    if not await is_main_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz.")
        return False
    return True

async def is_callback_main_admin(call: types.CallbackQuery) -> bool:
    if not await is_main_admin(call.from_user.id):
        await call.answer("❌ Siz admin emassiz.", show_alert=True)
        return False
    return True

@admin_router.message(Command("admin"))
async def admin_panel(message: types.Message):
    if not await is_sender_admin(message):
        return
    markup = await get_admin_keyboard(message.from_user.id)
    await message.answer("🛠 Admin paneliga xush kelibsiz. Kerakli bo'limni tanlang:", reply_markup=markup)

# Cancel callback (Bekor qilish)
@admin_router.callback_query(F.data == "admin_cancel")
async def cancel_handler(call: types.CallbackQuery, state: FSMContext):
    if not await is_callback_admin(call):
        return
    await state.clear()
    markup = await get_admin_keyboard(call.from_user.id)
    await call.message.edit_text("❌ Amal bekor qilindi.", reply_markup=markup)

# --- KANAL QO'SHISH FLOW (FSM) ---

@admin_router.callback_query(F.data == "admin_add_channel")
async def start_add_channel(call: types.CallbackQuery, state: FSMContext):
    if not await is_callback_main_admin(call):
        return
    await state.set_state(AdminStates.waiting_for_channel_name)
    await call.message.edit_text("📝 Kanal nomini yuboring.", reply_markup=get_cancel_keyboard())

@admin_router.message(AdminStates.waiting_for_channel_name)
async def process_channel_name(message: types.Message, state: FSMContext):
    if not await is_sender_main_admin(message):
        return
    
    channel_name = message.text.strip()
    await state.update_data(channel_name=channel_name)
    
    await state.set_state(AdminStates.waiting_for_channel_link)
    await message.answer(
        "🔗 Endi kanal havolasini yuboring.\n\n"
        "Misol:\n"
        "https://t.me/kanal_nomi\n"
        "yoki private invite link.",
        reply_markup=get_cancel_keyboard()
    )

def parse_public_username(link: str) -> str:
    link = link.strip()
    if link.startswith("@"):
        return link
    match = re.match(r'(?:https?://)?(?:t\.me|telegram\.me)/([a-zA-Z0-9_]{5,})/?$', link)
    if match:
        return f"@{match.group(1)}"
    return None

@admin_router.message(AdminStates.waiting_for_channel_link)
async def process_channel_link(message: types.Message, state: FSMContext, bot: Bot):
    if not await is_sender_main_admin(message):
        return
        
    link = message.text.strip() if message.text else ""
    
    # Agar xabar boshqa kanaldan forward qilingan bo'lsa, ID sini olishimiz mumkin
    forward_channel_id = None
    if message.forward_from_chat and message.forward_from_chat.type == "channel":
        forward_channel_id = message.forward_from_chat.id
        
    data = await state.get_data()
    channel_name = data.get("channel_name")
    
    # Kanal ID sini aniqlashga urinib ko'ramiz
    channel_id = None
    
    # 1. Agar xabar forward qilingan bo'lsa
    if forward_channel_id:
        channel_id = forward_channel_id
        
    # 2. Agar havola ommaviy username bo'lsa
    if not channel_id:
        pub_username = parse_public_username(link)
        if pub_username:
            try:
                chat = await bot.get_chat(pub_username)
                channel_id = chat.id
            except Exception as e:
                logger.warning(f"Public chatni get_chat orqali olishda xatolik: {e}")
                
    # 3. Agar shaxsiy havola (private invite link) bo'lsa va bot_channels'da moslik bo'lsa
    if not channel_id and ("+" in link or "joinchat" in link):
        # bot_channels bazasidan nomi yoki username'i bo'yicha qidiramiz
        bot_channels = await db.get_bot_channels()
        # Nomi mos keladiganini qidirish
        for chan in bot_channels:
            if channel_name.lower() in chan['title'].lower() or chan['title'].lower() in channel_name.lower():
                channel_id = chan['channel_id']
                break
        # Agar hali ham topilmasa, yagona private kanal bo'lsa shuni olamiz
        if not channel_id:
            private_chans = [c for c in bot_channels if not c['username']]
            if len(private_chans) == 1:
                channel_id = private_chans[0]['channel_id']
                
    # Agar aniqlab bo'lmasa, admin'dan ID ni yoki forward xabarni so'raymiz
    if not channel_id:
        await state.update_data(channel_link=link)
        await state.set_state(AdminStates.waiting_for_channel_id_fallback)
        await message.answer(
            "⚠️ Kanal ID sini avtomatik aniqlab bo'lmadi (bu shaxsiy kanal bo'lishi mumkin).\n\n"
            "Iltimos, kanal ID sini kiriting (masalan, `-100123456789`) yoki shu kanaldan birorta xabarni menga yuboring (forward qiling):",
            reply_markup=get_cancel_keyboard()
        )
        return
        
    # Kanalga bot adminligini tekshiramiz
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=bot.id)
        if member.status not in ['administrator', 'creator']:
            await message.answer(
                f"❌ Bot '{channel_name}' kanalida admin emas! Iltimos, avval botni kanalga administrator qilib qo'shing va qayta urinib ko'ring.",
                reply_markup=get_cancel_keyboard()
            )
            return
    except Exception as e:
        await message.answer(
            f"❌ Kanal topilmadi yoki bot u yerda admin emas. Xatolik: {e}\n"
            f"Iltimos, bot kanalda admin ekanligiga ishonch hosil qiling.",
            reply_markup=get_cancel_keyboard()
        )
        return
        
    # Bazaga saqlash
    await db.add_sponsor(channel_id, channel_name, link)
    await state.clear()
    markup = await get_admin_keyboard(message.from_user.id)
    await message.answer("✅ Kanal muvaffaqiyatli qo'shildi.", reply_markup=markup)

# Fallback holati (Kanal ID sini aniqlash uchun)
@admin_router.message(AdminStates.waiting_for_channel_id_fallback)
async def process_channel_id_fallback(message: types.Message, state: FSMContext, bot: Bot):
    if not await is_sender_main_admin(message):
        return
        
    channel_id = None
    
    # 1. Agar xabar forward qilingan bo'lsa
    if message.forward_from_chat and message.forward_from_chat.type == "channel":
        channel_id = message.forward_from_chat.id
    # 2. Agar matn ko'rinishida ID yozilgan bo'lsa
    elif message.text:
        text = message.text.strip()
        if text.startswith("-") and text[1:].isdigit():
            channel_id = int(text)
        elif text.isdigit():
            channel_id = int(text)
            
    if not channel_id:
        await message.answer(
            "❌ Noto'g'ri format. Iltimos, kanal ID sini kiriting (masalan, `-100123456789`) yoki shu kanaldan xabarni forward qiling:",
            reply_markup=get_cancel_keyboard()
        )
        return
        
    data = await state.get_data()
    channel_name = data.get("channel_name")
    channel_link = data.get("channel_link")
    
    # Adminlikni tekshirish
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=bot.id)
        if member.status not in ['administrator', 'creator']:
            await message.answer(
                "❌ Bot ushbu kanalda admin emas! Iltimos, avval botni kanalda admin qilib tayinlang va qayta urinib ko'ring.",
                reply_markup=get_cancel_keyboard()
            )
            return
    except Exception as e:
        await message.answer(
            f"❌ Kanalga ulanish imkoni bo'lmadi. Xatolik: {e}\n"
            f"Iltimos, bot kanalda admin ekanligini tekshiring.",
            reply_markup=get_cancel_keyboard()
        )
        return
        
    # Bazaga saqlash
    await db.add_sponsor(channel_id, channel_name, channel_link)
    await state.clear()
    markup = await get_admin_keyboard(message.from_user.id)
    await message.answer("✅ Kanal muvaffaqiyatli qo'shildi.", reply_markup=markup)

# --- KANALLAR RO'YXATI ---

@admin_router.callback_query(F.data == "admin_list_channels")
async def list_channels_callback(call: types.CallbackQuery):
    if not await is_callback_main_admin(call):
        return
        
    sponsors = await db.get_sponsors()
    if not sponsors:
        markup = await get_admin_keyboard(call.from_user.id)
        await call.message.edit_text("📋 Kanallar ro'yxati bo'sh.", reply_markup=markup)
        return
        
    text = "📋 Kanallar ro'yxati:\n\n"
    for idx, chan in enumerate(sponsors, 1):
        text += f"• {chan['name']} — {chan['invite_link']}\n"
        
    markup = await get_admin_keyboard(call.from_user.id)
    await call.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

# --- KANAL O'CHIRISH FLOW ---

@admin_router.callback_query(F.data == "admin_remove_channel")
async def show_channels_for_removal(call: types.CallbackQuery):
    if not await is_callback_main_admin(call):
        return
        
    sponsors = await db.get_sponsors()
    if not sponsors:
        markup = await get_admin_keyboard(call.from_user.id)
        await call.message.edit_text("❌ O'chirish uchun kanallar mavjud emas.", reply_markup=markup)
        return
        
    keyboard = []
    for chan in sponsors:
        keyboard.append([InlineKeyboardButton(text=f"❌ {chan['name']}", callback_data=f"admin_del_conf:{chan['channel_id']}")])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_cancel")])
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await call.message.edit_text("➖ O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=markup)

@admin_router.callback_query(F.data.startswith("admin_del_conf:"))
async def confirm_channel_removal(call: types.CallbackQuery):
    if not await is_callback_main_admin(call):
        return
        
    channel_id = int(call.data.split(":")[1])
    # Homiy ma'lumotlarini olish
    sponsors = await db.get_sponsors()
    channel = next((c for c in sponsors if c['channel_id'] == channel_id), None)
    
    if not channel:
        await call.answer("❌ Kanal topilmadi.", show_alert=True)
        return
        
    keyboard = [
        [
            InlineKeyboardButton(text="✅ Ha", callback_data=f"admin_del_yes:{channel_id}"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data="admin_remove_channel")
        ]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await call.message.edit_text(f"Rostdan ham ushbu kanalni o'chirmoqchimisiz?\n\n🔹 {channel['name']}", reply_markup=markup)

@admin_router.callback_query(F.data.startswith("admin_del_yes:"))
async def execute_channel_removal(call: types.CallbackQuery):
    if not await is_callback_main_admin(call):
        return
        
    channel_id = int(call.data.split(":")[1])
    await db.remove_sponsor(channel_id)
    await call.answer("✅ Kanal muvaffaqiyatli o'chirildi.", show_alert=True)
    
    # Kanallar ro'yxatiga qaytish
    sponsors = await db.get_sponsors()
    if not sponsors:
        markup = await get_admin_keyboard(call.from_user.id)
        await call.message.edit_text("✅ Kanal o'chirildi. Kanallar ro'yxati bo'sh.", reply_markup=markup)
    else:
        await show_channels_for_removal(call)

# --- STATISTIKA ---

@admin_router.callback_query(F.data == "admin_stats")
async def show_statistics(call: types.CallbackQuery):
    if not await is_callback_main_admin(call):
        return
        
    users_count = await db.get_users_count()
    movies_count = await db.get_movies_count()
    
    # Ko'p ko'rilgan 5 ta kino
    top_movies = await db.fetch("SELECT code, views FROM movies ORDER BY views DESC LIMIT 5")
    
    text = (
        "📊 Bot Statistikasi:\n\n"
        f"👥 Foydalanuvchilar: {users_count} ta\n"
        f"🎬 Kinolar soni: {movies_count} ta\n\n"
    )
    
    if top_movies:
        text += "🔥 Top 5 ta kino:\n"
        for idx, movie in enumerate(top_movies, 1):
            text += f"{idx}. Kod: {movie['code']} — {movie['views']} marta ko'rilgan\n"
            
    keyboard = [[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_cancel")]]
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

# --- KINO QO'SHISH FLOW (FSM) ---

@admin_router.callback_query(F.data == "admin_add_movie")
async def start_add_movie(call: types.CallbackQuery, state: FSMContext):
    if not await is_callback_admin(call):
        return
    await state.set_state(AdminStates.waiting_for_movie_code)
    await call.message.edit_text("🎬 Kino kodini yuboring (masalan, 120):", reply_markup=get_cancel_keyboard())

@admin_router.message(AdminStates.waiting_for_movie_code)
async def process_movie_code(message: types.Message, state: FSMContext):
    if not await is_sender_admin(message):
        return
        
    code = message.text.strip()
    
    # Kod mavjudligini tekshirish
    existing_movie = await db.get_movie(code)
    if existing_movie:
        await message.answer(
            "⚠️ Tizimda ushbu kod bilan kino allaqachon mavjud. Iltimos, boshqa kod yuboring:",
            reply_markup=get_cancel_keyboard()
        )
        return
        
    await state.update_data(movie_code=code)
    await state.set_state(AdminStates.waiting_for_movie_file)
    await message.answer(
        "🎬 Endi kinoni yuboring (video, fayl, rasm, matn yoki boshqa xabar ko'rinishida):",
        reply_markup=get_cancel_keyboard()
    )

@admin_router.message(AdminStates.waiting_for_movie_file)
async def process_movie_file(message: types.Message, state: FSMContext, bot: Bot):
    if not await is_sender_admin(message):
        return
        
    data = await state.get_data()
    code = data.get("movie_code")
    
    file_id = None
    file_type = "text"
    caption = message.caption or message.text or ""
    
    if message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    elif message.audio:
        file_id = message.audio.file_id
        file_type = "audio"
        
    channel_message_id = None
    
    # Agar MOVIE_CHANNEL_ID sozlangan bo'lsa, kinoni kanalga ko'chirib o'tkazamiz
    if config.MOVIE_CHANNEL_ID:
        try:
            sent_msg = await bot.copy_message(
                chat_id=config.MOVIE_CHANNEL_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            channel_message_id = sent_msg.message_id
        except Exception as e:
            logger.error(f"Kinoni saqlash kanaliga yuklashda xatolik: {e}. Faqat fayl ID si bazaga yoziladi.")
            
    # Bazaga yozish
    await db.add_movie(
        code=code,
        file_id=file_id,
        file_type=file_type,
        caption=caption,
        channel_message_id=channel_message_id
    )
    
    await state.clear()
    markup = await get_admin_keyboard(message.from_user.id)
    await message.answer("✅ Kino qo'shildi!", reply_markup=markup)

# --- KINO O'CHIRISH FLOW (FSM) ---

@admin_router.callback_query(F.data == "admin_remove_movie")
async def start_remove_movie(call: types.CallbackQuery, state: FSMContext):
    if not await is_callback_main_admin(call):
        return
    await state.set_state(AdminStates.waiting_for_delete_movie_code)
    await call.message.edit_text("O'chirmoqchi bo'lgan kino kodini kiriting:", reply_markup=get_cancel_keyboard())

@admin_router.message(AdminStates.waiting_for_delete_movie_code)
async def process_remove_movie(message: types.Message, state: FSMContext):
    if not await is_sender_main_admin(message):
        return
        
    code = message.text.strip()
    movie = await db.get_movie(code)
    
    if not movie:
        await message.answer(
            "❌ Bunday kodli kino topilmadi. Qayta urinib ko'ring:",
            reply_markup=get_cancel_keyboard()
        )
        return
        
    await db.remove_movie(code)
    await state.clear()
    markup = await get_admin_keyboard(message.from_user.id)
    await message.answer(f"✅ Kod: {code} bo'lgan kino muvaffaqiyatli o'chirildi.", reply_markup=markup)

# --- REKLAMA / XABAR YUBORISH (BROADCAST) ---

@admin_router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(call: types.CallbackQuery, state: FSMContext):
    if not await is_callback_main_admin(call):
        return
    await state.set_state(AdminStates.waiting_for_broadcast_msg)
    await call.message.edit_text(
        "📢 Barcha foydalanuvchilarga yuboriladigan xabarni (rasm, video, matn va h.k.) yuboring:",
        reply_markup=get_cancel_keyboard()
    )

@admin_router.message(AdminStates.waiting_for_broadcast_msg)
async def process_broadcast(message: types.Message, state: FSMContext, bot: Bot):
    if not await is_sender_main_admin(message):
        return
        
    # Xabarni bekor qilish holati emasligini tekshiramiz
    user_ids = await db.get_all_users_ids()
    if not user_ids:
        await state.clear()
        markup = await get_admin_keyboard(message.from_user.id)
        await message.answer("❌ Botda foydalanuvchilar mavjud emas.", reply_markup=markup)
        return
        
    progress_msg = await message.answer(f"⏳ Reklama yuborilmoqda: 0/{len(user_ids)}...")
    await state.clear()
    
    success = 0
    failed = 0
    
    for idx, user_id in enumerate(user_ids):
        try:
            # Xabarni nusxalash (copy_message) orqali yuborish
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            success += 1
        except Exception:
            failed += 1
            
        # Har 30 ta xabarda progressni yangilash
        if (idx + 1) % 30 == 0:
            try:
                await progress_msg.edit_text(f"⏳ Reklama yuborilmoqda: {idx + 1}/{len(user_ids)}...")
            except Exception:
                pass
                
    await progress_msg.delete()
    await message.answer(
        f"✅ Xabar muvaffaqiyatli yuborildi!\n\n"
        f"🟢 Yetkazildi: {success} ta\n"
        f"🔴 Yetkazilmadi: {failed} ta",
        reply_markup=await get_admin_keyboard(message.from_user.id)
    )

@admin_router.my_chat_member()
async def my_chat_member_handler(update: types.ChatMemberUpdated):
    chat = update.chat
    if chat.type == "channel":
        status = update.new_chat_member.status
        if status in ['administrator', 'creator']:
            # Bot admin bo'ldi - bazaga saqlaymiz
            await db.save_bot_channel(chat.id, chat.title, chat.username)
            logger.info(f"Bot '{chat.title}' kanaliga admin qilib qo'shildi (ID: {chat.id})")
        else:
            # Bot adminlikdan olindi yoki kanaldan chiqarildi
            await db.remove_bot_channel(chat.id)
            logger.info(f"Bot '{chat.title}' kanalidan olib tashlandi (ID: {chat.id})")



# --- YORDAMCHI ADMINLARNI BOSHQARISH (CO-ADMINS) ---

@admin_router.callback_query(F.data == "admin_add_coadmin")
async def start_add_coadmin(call: types.CallbackQuery, state: FSMContext):
    if not await is_callback_main_admin(call):
        return
    await state.set_state(AdminStates.waiting_for_coadmin_id)
    await call.message.edit_text(
        "📝 Yangi yordamchi adminning Telegram ID raqamini yuboring (faqat raqamlar, masalan: 12345678):",
        reply_markup=get_cancel_keyboard()
    )

@admin_router.message(AdminStates.waiting_for_coadmin_id)
async def process_coadmin_id(message: types.Message, state: FSMContext):
    if not await is_sender_main_admin(message):
        return
        
    text = message.text.strip()
    if not text.isdigit():
        await message.answer(
            "❌ Telegram ID faqat raqamlardan iborat bo'lishi kerak. Iltimos, to'g'ri ID kiriting:",
            reply_markup=get_cancel_keyboard()
        )
        return
        
    coadmin_id = int(text)
    
    # Asosiy adminlikni tekshirish
    if coadmin_id in config.ADMIN_IDS:
        await message.answer(
            "⚠️ Tizimda ushbu foydalanuvchi allaqachon asosiy admin hisoblanadi. Boshqa ID yuboring:",
            reply_markup=get_cancel_keyboard()
        )
        return
        
    # Allaqachon yordamchi admin ekanligini tekshirish
    if await db.is_assistant_admin(coadmin_id):
        await message.answer(
            "⚠️ Ushbu foydalanuvchi allaqachon yordamchi admin sifatida qo'shilgan. Boshqa ID yuboring:",
            reply_markup=get_cancel_keyboard()
        )
        return
        
    # Bazaga yozish
    await db.add_assistant_admin(coadmin_id, message.from_user.id)
    await state.clear()
    
    markup = await get_admin_keyboard(message.from_user.id)
    await message.answer(f"✅ Yordamchi admin muvaffaqiyatli qo'shildi! (ID: {coadmin_id})", reply_markup=markup)

@admin_router.callback_query(F.data == "admin_remove_coadmin")
async def show_coadmins_for_removal(call: types.CallbackQuery):
    if not await is_callback_main_admin(call):
        return
        
    coadmins = await db.get_assistant_admins()
    if not coadmins:
        markup = await get_admin_keyboard(call.from_user.id)
        await call.message.edit_text("❌ Yordamchi adminlar ro'yxati bo'sh.", reply_markup=markup)
        return
        
    keyboard = []
    for admin in coadmins:
        keyboard.append([InlineKeyboardButton(text=f"❌ ID: {admin['user_id']}", callback_data=f"admin_del_coadmin_conf:{admin['user_id']}")])
        
    keyboard.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_cancel")])
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await call.message.edit_text("➖ O'chirmoqchi bo'lgan yordamchi adminni tanlang:", reply_markup=markup)

@admin_router.callback_query(F.data.startswith("admin_del_coadmin_conf:"))
async def confirm_coadmin_removal(call: types.CallbackQuery):
    if not await is_callback_main_admin(call):
        return
        
    coadmin_id = int(call.data.split(":")[1])
    
    keyboard = [
        [
            InlineKeyboardButton(text="✅ Ha", callback_data=f"admin_del_coadmin_yes:{coadmin_id}"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data="admin_remove_coadmin")
        ]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await call.message.edit_text(f"Rostdan ham ushbu yordamchi adminni o'chirmoqchimisiz?\n\n🔹 ID: {coadmin_id}", reply_markup=markup)

@admin_router.callback_query(F.data.startswith("admin_del_coadmin_yes:"))
async def execute_coadmin_removal(call: types.CallbackQuery):
    if not await is_callback_main_admin(call):
        return
        
    coadmin_id = int(call.data.split(":")[1])
    await db.remove_assistant_admin(coadmin_id)
    await call.answer("✅ Yordamchi admin muvaffaqiyatli o'chirildi.", show_alert=True)
    
    await show_coadmins_for_removal(call)


# --- ASOSIY ADMINLARNI BOSHQARISH (MAIN ADMINS) ---

@admin_router.callback_query(F.data == "admin_add_main")
async def start_add_main_admin(call: types.CallbackQuery, state: FSMContext):
    if not await is_callback_main_admin(call):
        return
    await state.set_state(AdminStates.waiting_for_main_admin_id)
    await call.message.edit_text(
        "📝 Yangi asosiy adminning Telegram ID raqamini yuboring (faqat raqamlar, masalan: 12345678):",
        reply_markup=get_cancel_keyboard()
    )

@admin_router.message(AdminStates.waiting_for_main_admin_id)
async def process_main_admin_id(message: types.Message, state: FSMContext):
    if not await is_sender_main_admin(message):
        return
        
    text = message.text.strip()
    if not text.isdigit():
        await message.answer(
            "❌ Telegram ID faqat raqamlardan iborat bo'lishi kerak. Iltimos, to'g'ri ID kiriting:",
            reply_markup=get_cancel_keyboard()
        )
        return
        
    new_admin_id = int(text)
    
    # Allaqachon asosiy admin ekanligini tekshirish
    if await is_main_admin(new_admin_id):
        await message.answer(
            "⚠️ Ushbu foydalanuvchi allaqachon asosiy admin hisoblanadi. Boshqa ID yuboring:",
            reply_markup=get_cancel_keyboard()
        )
        return
        
    # Bazaga yozish
    await db.add_main_admin(new_admin_id, message.from_user.id)
    # Agar u avval yordamchi admin bo'lsa, uni yordamchilikdan o'chiramiz
    if await db.is_assistant_admin(new_admin_id):
        await db.remove_assistant_admin(new_admin_id)
        
    await state.clear()
    
    markup = await get_admin_keyboard(message.from_user.id)
    await message.answer(f"✅ Yangi asosiy admin muvaffaqiyatli qo'shildi! (ID: {new_admin_id})", reply_markup=markup)

@admin_router.callback_query(F.data == "admin_remove_main")
async def show_main_admins_for_removal(call: types.CallbackQuery):
    if not await is_callback_main_admin(call):
        return
        
    # Env faylidagi adminlar asosiy (system) adminlardir, ularni o'chirib bo'lmaydi (xavfsizlik uchun)
    db_admins = await db.get_main_admins_db()
    
    # Faqat bazadan qo'shilganlarini o'chira olamiz (Env-dagilarni emas)
    removeable_admins = [a for a in db_admins if a['user_id'] not in config.ADMIN_IDS]
    
    if not removeable_admins:
        markup = await get_admin_keyboard(call.from_user.id)
        await call.message.edit_text(
            "❌ O'chirish mumkin bo'lgan asosiy adminlar topilmadi.\n"
            "(Tizim/Env-dan qo'shilgan adminlarni faqat env fayli orqali o'chirish mumkin).",
            reply_markup=markup
        )
        return
        
    keyboard = []
    for admin in removeable_admins:
        keyboard.append([InlineKeyboardButton(text=f"❌ ID: {admin['user_id']}", callback_data=f"admin_del_main_conf:{admin['user_id']}")])
        
    keyboard.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_cancel")])
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await call.message.edit_text("➖ O'chirmoqchi bo'lgan asosiy adminni tanlang:", reply_markup=markup)

@admin_router.callback_query(F.data.startswith("admin_del_main_conf:"))
async def confirm_main_removal(call: types.CallbackQuery):
    if not await is_callback_main_admin(call):
        return
        
    admin_id = int(call.data.split(":")[1])
    
    keyboard = [
        [
            InlineKeyboardButton(text="✅ Ha", callback_data=f"admin_del_main_yes:{admin_id}"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data="admin_remove_main")
        ]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await call.message.edit_text(f"Rostdan ham ushbu asosiy adminni o'chirmoqchimisiz?\n\n🔹 ID: {admin_id}", reply_markup=markup)

@admin_router.callback_query(F.data.startswith("admin_del_main_yes:"))
async def execute_main_removal(call: types.CallbackQuery):
    if not await is_callback_main_admin(call):
        return
        
    admin_id = int(call.data.split(":")[1])
    await db.remove_main_admin(admin_id)
    await call.answer("✅ Asosiy admin muvaffaqiyatli o'chirildi.", show_alert=True)
    
    await show_main_admins_for_removal(call)
