# database.py
import sqlite3
import secrets


class Database:
    def __init__(self, db_name="link_chat.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # Foydalanuvchilar jadvali (phone olib tashlandi)
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            token TEXT UNIQUE,
            full_name TEXT,
            username TEXT
        )""")

        # Adminlar jadvali
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            admin_id INTEGER PRIMARY KEY
        )""")

        # Suhbat xonalari jadvali
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id INTEGER PRIMARY KEY AUTOINCREMENT,
            receiver_id INTEGER,
            sender_id INTEGER
        )""")

        # Xabarlar tarixi
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            sender_id INTEGER,
            text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        self.conn.commit()

    def get_user(self, user_id):
        self.cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return self.cursor.fetchone()

    def get_user_by_token(self, token):
        self.cursor.execute("SELECT * FROM users WHERE token = ?", (token,))
        return self.cursor.fetchone()

    def add_user(self, user_id, full_name, username):
        token = secrets.token_urlsafe(8)
        self.cursor.execute(
            "INSERT OR IGNORE INTO users (id, token, full_name, username) VALUES (?, ?, ?, ?)",
            (user_id, token, full_name, username)
        )
        self.conn.commit()
        return token

    def get_all_users(self):
        self.cursor.execute("SELECT id, full_name, username FROM users")
        return self.cursor.fetchall()

    def add_admin(self, admin_id):
        self.cursor.execute("INSERT OR IGNORE INTO admins (admin_id) VALUES (?)", (admin_id,))
        self.conn.commit()

    def del_admin(self, admin_id):
        self.cursor.execute("DELETE FROM admins WHERE admin_id = ?", (admin_id,))
        self.conn.commit()

    def get_admins(self):
        self.cursor.execute("SELECT admin_id FROM admins")
        return [row[0] for row in self.cursor.fetchall()]

    def get_or_create_chat(self, receiver_id, sender_id):
        self.cursor.execute("SELECT chat_id FROM chats WHERE receiver_id = ? AND sender_id = ?",
                            (receiver_id, sender_id))
        res = self.cursor.fetchone()
        if res:
            return res[0]
        else:
            self.cursor.execute("INSERT INTO chats (receiver_id, sender_id) VALUES (?, ?)", (receiver_id, sender_id))
            self.conn.commit()
            return self.cursor.lastrowid

    def get_chat_by_id(self, chat_id):
        self.cursor.execute("SELECT receiver_id, sender_id FROM chats WHERE chat_id = ?", (chat_id,))
        return self.cursor.fetchone()

    def save_message(self, chat_id, sender_id, text):
        self.cursor.execute("INSERT INTO messages (chat_id, sender_id, text) VALUES (?, ?, ?)",
                            (chat_id, sender_id, text))
        self.conn.commit()


db = Database()
# database.py ichiga qo'shing:

def get_chat_status(self, chat_id):
    """Suhbat faol yoki yopilganligini tekshirish"""
    conn = self.connect()
    cursor = conn.cursor()
    # Agar bazangizda chats jadvalida 'status' maydoni bo'lsa, shuni tekshiramiz.
    # Agar yo'q bo'lsa, jadvalga status maydonini qo'shish kerak (DEFAULT 'active')
    try:
        cursor.execute("SELECT status FROM chats WHERE id = ?", (chat_id,))
        res = cursor.fetchone()
        return res[0] if res else "closed"
    except:
        # Agar maydon bo'lmasa xato bermasligi uchun jadvalni yangilab qo'yamiz:
        try:
            cursor.execute("ALTER TABLE chats ADD COLUMN status TEXT DEFAULT 'active'")
            conn.commit()
            return "active"
        except:
            return "active"

def close_chat(self, chat_id):
    """Suhbatni yopish (boshqa xabar borishini to'xtatish)"""
    conn = self.connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE chats SET status = 'closed' WHERE id = ?", (chat_id,))
    conn.commit()

def delete_user(self, user_id):
    """Botni bloklagan foydalanuvchini bazadan o'chirish"""
    conn = self.connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    conn.commit()