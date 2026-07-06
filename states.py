# states.py
from aiogram.fsm.state import State, StatesGroup

class BotStates(StatesGroup):
    get_phone = State()
    write_anon_msg = State()
    reply_msg = State()
    ask_msg = State()
    add_admin = State()
    del_admin = State()
    admin_bridge_reply = State()
    admin_broadcast = State()