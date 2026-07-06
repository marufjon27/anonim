# keyboards.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Admin menyusi
admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="👥 Ro'yxatni ko'rish")],
        [KeyboardButton(text="📢 Reklama tarqatish")],
        [KeyboardButton(text="➕ Admin Qo'shish"), KeyboardButton(text="➖ Admin O'chirish")],
        [KeyboardButton(text="🏠 Oddiy rejim")]
    ],
    resize_keyboard=True
)

# Foydalanuvchi menyusi
main_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🔗 Mening Havolam")]],
    resize_keyboard=True
)

# Uzluksiz javob tugmasi
def get_reply_button(chat_id, target_role):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Xabarga javob yozish", callback_data=f"rep_{chat_id}_{target_role}")]
    ])

# Admin ko'prik tugmalari
def get_admin_bridge_buttons(chat_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👤 Anonim nomidan (Egasiga)", callback_data=f"abr_{chat_id}_anon"),
            InlineKeyboardButton(text="🏠 Ega nomidan (Anonimga)", callback_data=f"abr_{chat_id}_owner")
        ]
    ])
# keyboards.py ichiga qo'shing yoki almashtiring:
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Muloqot tugmasiga "Suhbatni to'xtatish" tugmasini qo'shamiz
def get_reply_button(chat_id: int, role: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="↩️ Javob berish", callback_data=f"rep_{chat_id}_{role}"),
            InlineKeyboardButton(text="🚫 Suhbatni yakunlash", callback_data=f"end_{chat_id}")
        ]
    ])

# Admin ko'prik loglari uchun tugmalar
def get_admin_bridge_buttons(chat_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🕵️‍♂️ Anonim nomidan", callback_data=f"abr_{chat_id}_anon"),
            InlineKeyboardButton(text="👤 Egasi nomidan", callback_data=f"abr_{chat_id}_owner")
        ]
    ])

# Admin panel tugmalariga "Tozalash tizimi"ni qo'shamiz
# Agar sizda ReplyKeyboardMarkup bo'lsa, undagi tugmalar qatoriga "🧹 Bazani tozalash" matnini qo'shib qo'ying.