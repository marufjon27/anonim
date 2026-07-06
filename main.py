import asyncio
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext

from config import BOT_TOKEN, SUPER_ADMIN_ID
from database import db
from states import BotStates
import keyboards as kb

# Bot va Dispatcher obyektlarini yaratamiz
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def check_admin(user_id):
    return user_id == SUPER_ADMIN_ID or user_id in db.get_admins()


# --- REKLAMANI FONDA TARQATISH (BOT QOTMASLIGI UCHUN ALOHIDA TASK) ---
async def send_broadcast_task(message: Message, users: list, admin_id: int):
    send_count = 0
    fail_count = 0

    for u in users:
        try:
            # Telegram FloodWait sanksiyasiga tushmaslik va bot qotmasligi uchun copy_message
            await message.bot.copy_message(
                chat_id=u[0],
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            send_count += 1
            await asyncio.sleep(0.05)  # Har bir xabar orasida kichik uzilish (sekundiga ~20 ta xabar)
        except Exception:
            fail_count += 1

    # Reklama yakunlangach adminni ogohlantirish
    try:
        await message.bot.send_message(
            admin_id,
            f"📢 **Reklama yakunlandi!**\n\n"
            f"✅ Muvaffaqiyatli yetkazildi: {send_count} ta\n"
            f"❌ Botni bloklaganlar: {fail_count} ta",
            parse_mode="Markdown"
        )
    except Exception:
        pass


# --- START KOMANDASI ---
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    username = f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas"

    user = db.get_user(user_id)
    bot_user = await bot.get_me()

    if not user:
        token = db.add_user(user_id, full_name, username)
        alert = f"🆕 **Yangi foydalanuvchi:** {full_name}\n🆔 ID: `{user_id}`"
        try:
            await bot.send_message(SUPER_ADMIN_ID, alert, parse_mode="Markdown")
        except Exception:
            pass
    else:
        token = user[1]

    target_token = command.args if command.args else None

    if target_token:
        owner = db.get_user_by_token(target_token)
        if not owner:
            await message.answer("❌ Havola xato.", reply_markup=kb.main_menu)
            return
        if owner[0] == user_id:
            await message.answer("⚠️ O'zingizga yoza olmaysiz.", reply_markup=kb.main_menu)
            return

        await state.update_data(owner_id=owner[0])
        await message.answer(f"👤 **{owner[2]}** ga anonim xabar yozyapsiz. Matnni yuboring:")
        await state.set_state(BotStates.write_anon_msg)
    else:
        await message.answer(
            f"👋 Salom, {full_name}!\n\n🔗 Shaxsiy anonim havolangiz:\n"
            f"https://t.me/{bot_user.username}?start={token}",
            reply_markup=kb.main_menu
        )


# --- ILK ANONIM XABAR ---
@dp.message(BotStates.write_anon_msg, F.text)
async def send_anonymous_text(message: Message, state: FSMContext):
    data = await state.get_data()
    owner_id = data.get("owner_id")
    sender_id = message.from_user.id

    chat_id = db.get_or_create_chat(owner_id, sender_id)
    db.save_message(chat_id, sender_id, message.text)

    owner_info = db.get_user(owner_id)
    owner_name = owner_info[2] if owner_info else "Noma'lum"

    await bot.send_message(
        owner_id,
        f"📥 **Yangi anonim xabar oldingiz!**\n\n💬 {message.text}",
        reply_markup=kb.get_reply_button(chat_id, "anon"),
        parse_mode="Markdown"
    )

    admin_log = (
        f"🕵️‍♂️ 📑 **[KUZATUV # {chat_id}]**\n\n"
        f"👤 **Kimdan (Anonim):** ID: `{sender_id}`\n"
        f"➡️ **Kimga (Havola Egasi):** {owner_name} | ID: `{owner_id}`\n\n"
        f"💬 **Xabar matni:** {message.text}"
    )
    try:
        await bot.send_message(SUPER_ADMIN_ID, admin_log, reply_markup=kb.get_admin_bridge_buttons(chat_id),
                               parse_mode="Markdown")
    except Exception:
        pass

    await message.answer("✅ Xabaringiz anonim tarzda yuborildi!", reply_markup=kb.main_menu)
    await state.clear()


# --- FOYDALANUVCHILAR UCHUN UZLUKSIZ INLINE JAVOB ---
@dp.callback_query(F.data.startswith("rep_"))
async def handle_reply_callback(call: CallbackQuery, state: FSMContext):
    _, chat_id, target_role = call.data.split("_")
    chat_id = int(chat_id)

    await state.update_data(chat_id=chat_id, target_role=target_role)
    await call.message.answer("✍ *Javobingizni yozing:*", parse_mode="Markdown")
    await state.set_state(BotStates.reply_msg)
    await call.answer()


@dp.message(BotStates.reply_msg, F.text)
async def process_continuous_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data.get("chat_id")
    target_role = data.get("target_role")

    chat = db.get_chat_by_id(chat_id)
    if not chat: 
        await message.answer("❌ Suhbat topilmadi.")
        return

    receiver_id, sender_id = chat

    if target_role == "anon":
        destination = sender_id
        prefix = "↩️ **Havola egasidan javob keldi:**"
        next_role = "owner"
    else:
        destination = receiver_id
        prefix = "📥 **Anonim suhbatdoshingizdan yangi xabar:**"
        next_role = "anon"

    db.save_message(chat_id, message.from_user.id, message.text)

    try:
        await bot.send_message(
            destination,
            f"{prefix}\n\n💬 {message.text}",
            reply_markup=kb.get_reply_button(chat_id, next_role),
            parse_mode="Markdown"
        )
        await message.answer("✅ Xabaringiz yetkazildi.", reply_markup=kb.main_menu)
    except Exception:
        await message.answer("❌ Xabarni yetkazishda xatolik yuz berdi.")

    # --- ADMIN LOG (MUKAMMAL SHPION KUZATUVI) ---
    admin_log = (
        f"🕵️‍♂️ 📑 **[KUZATUV # {chat_id}]**\n\n"
        f"👤 **Yozuvchi (ID):** `{message.from_user.id}`\n"
        f"➡️ **Qabul qiluvchi (ID):** `{destination}`\n\n"
        f"💬 **Xabar matni:** {message.text}"
    )
    try:
        await bot.send_message(SUPER_ADMIN_ID, admin_log, reply_markup=kb.get_admin_bridge_buttons(chat_id),
                               parse_mode="Markdown")
    except Exception:
        pass
    await state.clear()


# --- ADMIN: KO'PRIK (SHPION) BO'LIB ORAGA QO'SHILISH ---
@dp.callback_query(F.data.startswith("abr_"))
async def handle_admin_bridge(call: CallbackQuery, state: FSMContext):
    if not check_admin(call.from_user.id): return
    _, chat_id, pretend_role = call.data.split("_")
    chat_id = int(chat_id)

    await state.update_data(bridge_chat_id=chat_id, pretend_role=pretend_role)

    if pretend_role == "anon":
        await call.message.answer(f"✍️ **Suhbat #{chat_id}: Anonim nomidan Havola Egasiga** xabar yozing:")
    else:
        await call.message.answer(f"✍️ **Suhbat #{chat_id}: Havola Egasi nomidan Anonimga** xabar yozing:")

    await state.set_state(BotStates.admin_bridge_reply)
    await call.answer()


@dp.message(BotStates.admin_bridge_reply, F.text)
async def process_admin_bridge_reply(message: Message, state: FSMContext):
    if not check_admin(message.from_user.id): return
    data = await state.get_data()
    chat_id = data.get("bridge_chat_id")
    pretend_role = data.get("pretend_role")

    chat = db.get_chat_by_id(chat_id)
    if not chat:
        await message.answer("❌ Ushbu suhbat faol emas.")
        return

    receiver_id, sender_id = chat

    if pretend_role == "anon":
        destination = receiver_id
        prefix = "📥 **Anonim suhbatdoshingizdan yangi xabar:**"
        next_role = "anon"
        db.save_message(chat_id, sender_id, f"[ADMIN AS ANON]: {message.text}")
    else:
        destination = sender_id
        prefix = "↩️ **Havola egasidan javob keldi:**"
        next_role = "owner"
        db.save_message(chat_id, receiver_id, f"[ADMIN AS OWNER]: {message.text}")

    try:
        await bot.send_message(
            destination,
            f"{prefix}\n\n💬 {message.text}",
            reply_markup=kb.get_reply_button(chat_id, next_role),
            parse_mode="Markdown"
        )
        await message.answer(f"🚀 Xabar muvaffaqiyatli tarzda '{pretend_role}' nomidan yetkazildi!",
                             reply_markup=kb.admin_menu)
    except Exception:
        await message.answer("❌ Xabarni yuborishda xatolik yuz berdi.")

    # Admin o'zi yozgan aralashuv logi
    admin_log = (
        f"🕵️‍♂️ ⚠️ **[ADMIN ARALASHUVI # {chat_id}]**\n\n"
        f"👨‍💻 **Admin ID:** `{message.from_user.id}`\n"
        f"🎭 **Kimning nomidan yozdi:** {pretend_role.upper()}\n"
        f"💬 **Yuborilgan matn:** {message.text}"
    )
    try:
        await bot.send_message(SUPER_ADMIN_ID, admin_log, reply_markup=kb.get_admin_bridge_buttons(chat_id), parse_mode="Markdown")
    except Exception:
        pass

    await state.clear()


# --- FOYDALANUCHI MENYUSI: MENING HAVOLAM ---
@dp.message(F.text == "🔗 Mening Havolam")
async def show_my_link(message: Message):
    user = db.get_user(message.from_user.id)
    bot_user = await bot.get_me()
    if user:
        await message.answer(f"🔗 **Sizning shaxsiy havolangiz:**\n\nhttps://t.me/{bot_user.username}?start={user[1]}",
                             reply_markup=kb.main_menu)


# --- COMMAND ADMIN PANEL OCHISH ---
@dp.message(Command("admin"))
async def open_admin(message: Message):
    if check_admin(message.from_user.id):
        await message.answer("👨‍💻 Admin panel ochildi:", reply_markup=kb.admin_menu)


# --- ADMIN PANEL TUGMALARI BOSHQARUVI ---
@dp.message(F.text == "🏠 Oddiy rejim")
async def close_admin(message: Message):
    if check_admin(message.from_user.id):
        await message.answer("Oddiy rejimga qaytdingiz.", reply_markup=kb.main_menu)


@dp.message(F.text == "📊 Statistika")
async def view_stats(message: Message):
    if check_admin(message.from_user.id):
        await message.answer(f"📊 **Jami ro'yxatdan o'tgan foydalanuvchilar:** {len(db.get_all_users())} ta",
                             reply_markup=kb.admin_menu)


@dp.message(F.text == "👥 Ro'yxatni ko'rish")
async def view_users(message: Message):
    if not check_admin(message.from_user.id): return
    text = "👥 **Foydalanuvchilar Ro'yxati:**\n\n"
    for u in db.get_all_users():
        text += f"👤 {u[2]} | ID: `{u[0]}`\n"
    await message.answer(text[:4000], parse_mode="Markdown", reply_markup=kb.admin_menu)


@dp.message(F.text == "➕ Admin Qo'shish")
async def add_admin_state(message: Message, state: FSMContext):
    if check_admin(message.from_user.id):
        await message.answer("➕ Yangi admin Telegram ID-sini kiriting:")
        await state.set_state(BotStates.add_admin)


@dp.message(BotStates.add_admin, F.text)
async def add_admin_finish(message: Message, state: FSMContext):
    try:
        db.add_admin(int(message.text))
        await message.answer("✅ Yangi admin muvaffaqiyatli qo'shildi.", reply_markup=kb.admin_menu)
    except Exception:
        await message.answer("❌ Xatolik! ID raqam bo'lishi kerak.", reply_markup=kb.admin_menu)
    await state.clear()


@dp.message(F.text == "➖ Admin O'chirish")
async def del_admin_state(message: Message, state: FSMContext):
    if check_admin(message.from_user.id):
        await message.answer("➖ O'chiriladigan admin Telegram ID-sini kiriting:")
        await state.set_state(BotStates.del_admin)


@dp.message(BotStates.del_admin, F.text)
async def del_admin_finish(message: Message, state: FSMContext):
    try:
        del_id = int(message.text)
        if del_id == SUPER_ADMIN_ID:
            await message.answer("🛑 Asosiy tizm adminini o'chirib bo'lmaydi!", reply_markup=kb.admin_menu)
        else:
            db.del_admin(del_id)
            await message.answer("✅ Admin muvaffaqiyatli o'chirildi.", reply_markup=kb.admin_menu)
    except Exception:
        await message.answer("❌ Xatolik!", reply_markup=kb.admin_menu)
    await state.clear()


# --- REKLAMA XIZMATI BO'LIMI (FONLI TIZIMDA) ---
@dp.message(F.text == "📢 Reklama tarqatish")
async def start_broadcast(message: Message, state: FSMContext):
    if check_admin(message.from_user.id):
        await message.answer(
            "📢 **Barcha foydalanuvchilarga yuboriladigan reklama matnini (yoki rasmini) kiriting:**\n\n_Eslatma: Har qanday formatdagi xabar (matn, rasm, video) hammaga boradi._",
            parse_mode="Markdown")
        await state.set_state(BotStates.admin_broadcast)


@dp.message(BotStates.admin_broadcast)
async def send_broadcast(message: Message, state: FSMContext):
    if not check_admin(message.from_user.id): return

    users = db.get_all_users()
    await message.answer(
        "🚀 **Reklama tarqatish orqa fonda boshlandi!**\n"
        "Bot mutlaqo qotib qolmaydi, foydalanuvchilar suhbatni bemalol davom ettirishi mumkin.\n"
        "Tugagach sizga hisobot yuboriladi.",
        reply_markup=kb.admin_menu
    )
    await state.clear()

    # Asosiy oqim qotmasligi uchun reklamani fonda (task) ishga tushirish
    asyncio.create_task(send_broadcast_task(message, users, message.from_user.id))


# --- NUSXALASH TUGMASI CALLBACK ---
@dp.callback_query(F.data == "copy_link")
async def process_copy_link(call: CallbackQuery):
    user = db.get_user(call.from_user.id)
    bot_user = await bot.get_me()
    token = user[1] if user else "xato"
    share_link = f"https://t.me/{bot_user.username}?start={token}"

    await call.message.answer(
        f"📋 **Sizning shaxsiy havolangiz:**\n\n`{share_link}`\n\n"
        f"👆 _Havola ustiga bir marta bossangiz avtomatik nusxalanadi._",
        parse_mode="Markdown"
    )
    await call.answer("Havola nusxalash uchun yuborildi!")


# 🛑 NOTANISH/TASODIFIY XABARLARNI USHLASH (ENG OXIRIDA) 🛑
@dp.message(F.text, ~F.text.startswith("/"))
async def handle_unknown_messages(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        return

    user = db.get_user(message.from_user.id)
    bot_user = await bot.get_me()
    token = user[1] if user else "xato"
    share_link = f"https://t.me/{bot_user.username}?start={token}"

    explain_text = (
        "⚠️ **Kechirasiz, xabaringiz hech kimga yetkazilmadi.**\n\n"
        "💡 Kimdir sizga anonim xabar yuborishi uchun avval o'z havolangizni do'stlaringizga tarqatishingiz kerak.\n\n"
        "👇 Quyidagi tugmalar orqali shaxsiy havolangizni oling va ulashing:"
    )

    share_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚀 Do'stlarga ulashish",
                                 switch_inline_query=f"\n\n🤖 Menga anonim xabar yuborish uchun ushbu havolaga bosing:\n👉 {share_link}"),
        ],
        [
            InlineKeyboardButton(text="📋 Havolani nusxalash", callback_data="copy_link")
        ]
    ])

    await message.answer(explain_text, reply_markup=share_keyboard, parse_mode="Markdown")


# --- RENDER UCHUN TEKIN PORT OCHISH (WEB SERVER) ---
async def handle(request):
    return web.Response(text="Bot is running!")


async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000)) 
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server started on port {port}")


# --- ASOSIY ISHGA TUSHIRISH FUNKSIYASI (FAQAT BITTA BO'LISHI SHART) ---
async def main():
    # 1. Fonda veb-serverni ishga tushiramiz (Render o'chib qolmasligi uchun)
    asyncio.create_task(start_web_server()) 
    
    # 2. Telegram dagi eski kelib to'planib qolgan xabarlarni tozalab tashlaymiz
    await bot.delete_webhook(drop_pending_updates=True)
    
    # 3. Botni polling rejimida yoqamiz
    print("Bot is starting polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
