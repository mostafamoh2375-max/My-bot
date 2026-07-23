import os
import sys
import json
import uuid
import time
import logging
import sqlite3
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive"

def run():
    app.run(host='0.0.0.0', port=8080)

t = Thread(target=run)
t.start()

import telebot
from telebot import types

# ── SQLite Database Setup ──────────────────────────────────────
DB_FILE = "bot_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS buttons (
            id TEXT PRIMARY KEY,
            name TEXT,
            content_type TEXT,
            content TEXT,
            parent_id TEXT,
            unlock_points INTEGER,
            unlock_desc TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT,
            points INTEGER,
            last_gift REAL,
            unlocked TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS banned (
            user_id INTEGER PRIMARY KEY
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            referred_id TEXT PRIMARY KEY,
            referrer_id TEXT
        )
    ''')
    
    conn.commit()
    
    # Default settings
    cursor.execute("SELECT value FROM settings WHERE key='gift_points'")
    if not cursor.fetchone():
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('gift_points', '2')")
    cursor.execute("SELECT value FROM settings WHERE key='gift_name'")
    if not cursor.fetchone():
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('gift_name', 'الهدية اليومية')")
    cursor.execute("SELECT value FROM settings WHERE key='gift_active'")
    if not cursor.fetchone():
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('gift_active', 'true')")
        
    cursor.execute("SELECT value FROM settings WHERE key='referral_points'")
    if not cursor.fetchone():
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('referral_points', '5')")
    cursor.execute("SELECT value FROM settings WHERE key='referral_active'")
    if not cursor.fetchone():
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('referral_active', 'true')")
    cursor.execute("SELECT value FROM settings WHERE key='referral_name'")
    if not cursor.fetchone():
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('referral_name', 'رابط الإحالة')")

    cursor.execute("SELECT value FROM settings WHERE key='sub_active'")
    if not cursor.fetchone():
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('sub_active', 'true')")
    cursor.execute("SELECT value FROM settings WHERE key='sub_channels'")
    if not cursor.fetchone():
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('sub_channels', ?)", (json.dumps(["@Salemly_1", "@shr_llh"]),))
        
    conn.commit()
    conn.close()

init_db()

def load_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name, content_type, content, parent_id, unlock_points, unlock_desc FROM buttons")
    rows = cursor.fetchall()
    buttons = []
    for r in rows:
        buttons.append({
            "id": r[0], "name": r[1], "content_type": r[2],
            "content": r[3], "parent_id": r[4], "unlock_points": r[5], "unlock_desc": r[6]
        })
        
    cursor.execute("SELECT user_id FROM users")
    users = [int(r[0]) if r[0].isdigit() else r[0] for r in cursor.fetchall()]
    
    cursor.execute("SELECT user_id FROM banned")
    banned_users = [int(r[0]) for r in cursor.fetchall()]
    
    cursor.execute("SELECT key, value FROM settings")
    settings_dict = {r[0]: r[1] for r in cursor.fetchall()}
    
    conn.close()
    
    gift_points = int(settings_dict.get("gift_points", 2))
    gift_name = settings_dict.get("gift_name", "الهدية اليومية")
    gift_active = settings_dict.get("gift_active", "true") == "true"
    
    referral_points = int(settings_dict.get("referral_points", 5))
    referral_name = settings_dict.get("referral_name", "رابط الإحالة")
    referral_active = settings_dict.get("referral_active", "true") == "true"
    
    sub_active = settings_dict.get("sub_active", "true") == "true"
    
    try:
        sub_channels = json.loads(settings_dict.get("sub_channels", '["@Salemly_1", "@shr_llh"]'))
    except:
        sub_channels = ["@Salemly_1", "@shr_llh"]
        
    return {
        "buttons": buttons, "users": users, "banned_users": banned_users,
        "gift_points": gift_points, "gift_name": gift_name, "gift_active": gift_active,
        "referral_points": referral_points, "referral_name": referral_name, "referral_active": referral_active,
        "sub_active": sub_active, "sub_channels": sub_channels
    }

def save_db(data):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM buttons")
    for b in data.get("buttons", []):
        cursor.execute(
            "INSERT OR REPLACE INTO buttons (id, name, content_type, content, parent_id, unlock_points, unlock_desc) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (b.get("id"), b.get("name"), b.get("content_type", "text"), b.get("content", ""), b.get("parent_id"), b.get("unlock_points", 0), b.get("unlock_desc", ""))
        )
        
    cursor.execute("DELETE FROM banned")
    for bu in data.get("banned_users", []):
        cursor.execute("INSERT OR IGNORE INTO banned (user_id) VALUES (?)", (bu,))
        
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('gift_points', ?)", (str(data.get("gift_points", 2)),))
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('gift_name', ?)", (str(data.get("gift_name", "الهدية اليومية")),))
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('gift_active', ?)", ("true" if data.get("gift_active", True) else "false",))
    
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('referral_points', ?)", (str(data.get("referral_points", 5)),))
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('referral_name', ?)", (str(data.get("referral_name", "رابط الإحالة")),))
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('referral_active', ?)", ("true" if data.get("referral_active", True) else "false",))
    
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('sub_active', ?)", ("true" if data.get("sub_active", True) else "false",))
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('sub_channels', ?)", (json.dumps(data.get("sub_channels", ["@Salemly_1", "@shr_llh"])),))
    
    conn.commit()
    conn.close()

def load_users():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, name, points, last_gift, unlocked FROM users")
    rows = cursor.fetchall()
    users_dict = {}
    for r in rows:
        uid = str(r[0])
        try:
            unlocked = json.loads(r[4]) if r[4] else []
        except:
            unlocked = []
        users_dict[uid] = {
            "name": r[1] or "",
            "points": r[2] if r[2] is not None else 0,
            "last_gift": r[3] if r[3] is not None else 0.0,
            "unlocked": unlocked
        }
    conn.close()
    return {"users": users_dict}

def save_users(data):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    for uid, udata in data.get("users", {}).items():
        cursor.execute(
            "INSERT OR REPLACE INTO users (user_id, name, points, last_gift, unlocked) VALUES (?, ?, ?, ?, ?)",
            (
                str(uid),
                udata.get("name", ""),
                udata.get("points", 0),
                udata.get("last_gift", 0.0),
                json.dumps(udata.get("unlocked", []))
            )
        )
    conn.commit()
    conn.close()

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or "7623300303:AAHA-f9LWLbKE4uP-1ZDn8E2IHkGzUm5vaM"

if not TOKEN:
    sys.stderr.write("ERROR: TELEGRAM_BOT_TOKEN environment variable is not set.\n")
    raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set")

ADMIN_ID = 8097008430

bot = telebot.TeleBot(TOKEN, threaded=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

def report_admin_error(exc: Exception, context: str = ""):
    try:
        logger.exception("Unhandled exception in %s: %s", context, exc)
    except Exception:
        pass
    try:
        bot.send_message(
            ADMIN_ID,
            f"⚠️ Error in bot ({context}):\n{type(exc).__name__}: {str(exc)[:300]}",
        )
    except Exception:
        logger.exception("Failed to send error message to ADMIN_ID")

 REQUIRED_CHANNELS = ["@Salemly_1", "@shr_llh"]

user_states = {}
user_data = {}

WAIT_BTN_NAME = "WAIT_BTN_NAME"
WAIT_BTN_CONTENT = "WAIT_BTN_CONTENT"
WAIT_BROADCAST = "WAIT_BROADCAST"
WAIT_BAN = "WAIT_BAN"
WAIT_UNBAN = "WAIT_UNBAN"
WAIT_GIFT_NAME = "WAIT_GIFT_NAME"
WAIT_REF_NAME = "WAIT_REF_NAME"
WAIT_LOCK_POINTS = "WAIT_LOCK_POINTS"
WAIT_LOCK_DESC = "WAIT_LOCK_DESC"

def set_state(uid, state, **data):
    user_states[uid] = state
    user_data[uid] = data

def clear_state(uid):
    user_states.pop(uid, None)
    user_data.pop(uid, None)

def get_state(uid):
    return user_states.get(uid)

def get_data(uid):
    return user_data.get(uid, {})

def register_user(user_id):
    db = load_db()
    if user_id not in db["users"]:
        db["users"].append(user_id)
        save_db(db)

def register_user_points(user_id, name=""):
    data = load_users()
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {"name": name, "points": 0, "unlocked": []}
        save_users(data)
    else:
        changed = False
        if name and data["users"][uid].get("name") != name:
            data["users"][uid]["name"] = name
            changed = True
        if "points" not in data["users"][uid]:
            data["users"][uid]["points"] = 0
            changed = True
        if "unlocked" not in data["users"][uid]:
            data["users"][uid]["unlocked"] = []
            changed = True
        if changed:
            save_users(data)

def check_subscription(user_id):
    db = load_db()
    if not db.get("sub_active", True):
        return []
    
    not_subscribed = []
    channels = db.get("sub_channels", REQUIRED_CHANNELS)
    for channel in channels:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status in ("left", "kicked"):
                not_subscribed.append(channel)
        except Exception as e:
            logger.exception("check_subscription failed for %s: %s", channel, e)
            not_subscribed.append(channel)
    return not_subscribed

GIFT_INTERVAL = 86400

def claim_daily_gift(user_id):
    users_data = load_users()
    db = load_db()
    
    uid = str(user_id)
    if uid not in users_data["users"]:
        return False, "⚠️ سجّل أولاً بإرسال /start"
        
    user = users_data["users"][uid]
    now = time.time()
    last = user.get("last_gift", 0)
    elapsed = now - last
    
    if elapsed < GIFT_INTERVAL:
        remaining = GIFT_INTERVAL - elapsed
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        return False, (
            f"⏳ لقد حصلت على هديتك اليومية بالفعل.\n"
            f"يمكنك المطالبة مجدداً بعد: {hours} ساعة و {minutes} دقيقة."
        )
        
    current_gift_points = db.get("gift_points", 2)
    user["points"] = user.get("points", 0) + current_gift_points
    user["last_gift"] = now
    save_users(users_data)
    
    gift_name = db.get("gift_name", "الهدية اليومية")
    return True, (
        f"🎁 تهانينا! حصلت على {current_gift_points} نقاط من ({gift_name})!\n"
        f"رصيدك الحالي: {user['points']} نقطة 🌟"
    )

def get_button(db, btn_id):
    for btn in db["buttons"]:
        if btn.get("id") == btn_id:
            return btn
    return None

def get_children(db, parent_id):
    return [b for b in db["buttons"] if b.get("parent_id") == parent_id]

def collect_descendants(db, btn_id):
    result = set()
    for child in get_children(db, btn_id):
        result.add(child["id"])
        result.update(collect_descendants(db, child["id"]))
    return result

def new_id():
    return str(uuid.uuid4())[:8]

def extract_content(message):
    ct = message.content_type
    if ct == "text":
        return "text", message.text.strip()
    elif ct == "photo":
        return "photo", message.photo[-1].file_id
    elif ct == "document":
        return "document", message.document.file_id
    elif ct == "video":
        return "video", message.video.file_id
    elif ct == "audio":
        return "audio", message.audio.file_id
    elif ct == "voice":
        return "voice", message.voice.file_id
    elif ct == "sticker":
        return "sticker", message.sticker.file_id
    else:
        return "text", ""

def send_content(cid, btn, back_markup):
    ct = btn.get("content_type", "text")
    content = btn.get("content", "")
    name = btn.get("name", "")

    if not content:
        bot.send_message(
            cid, f"ℹ️ {name}\n\n(لا يوجد محتوى بعد.)", reply_markup=back_markup
        )
        return

    try:
        if ct == "text":
            bot.send_message(cid, content, reply_markup=back_markup)
        elif ct == "photo":
            bot.send_photo(cid, content, reply_markup=back_markup)
        elif ct == "document":
            bot.send_document(cid, content, reply_markup=back_markup)
        elif ct == "video":
            bot.send_video(cid, content, reply_markup=back_markup)
        elif ct == "audio":
            bot.send_audio(cid, content, reply_markup=back_markup)
        elif ct == "voice":
            bot.send_voice(cid, content, reply_markup=back_markup)
        elif ct == "sticker":
            bot.send_sticker(cid, content)
            bot.send_message(cid, "↩️", reply_markup=back_markup)
        else:
            bot.send_message(cid, content, reply_markup=back_markup)
    except Exception as e:
        report_admin_error(e, "send_content")

def build_nav_markup(db, parent_id=None):
    children = get_children(db, parent_id)
    markup = types.InlineKeyboardMarkup()
    
    for i in range(0, len(children), 2):
        row_buttons = []
        for btn in children[i:i+2]:
            is_locked = int(btn.get("unlock_points", 0)) > 0
            lock_icon = " 🔒" if is_locked else ""
            row_buttons.append(
                types.InlineKeyboardButton(f"{btn['name']}{lock_icon}", callback_data=f"nav_{btn['id']}")
            )
        markup.row(*row_buttons)

    if parent_id is not None:
        parent = get_button(db, parent_id)
        back_to = parent.get("parent_id") if parent else None
        markup.add(
            types.InlineKeyboardButton(
                "🔙 رجوع", callback_data=f"nav_back_{back_to if back_to else 'root'}"
            )
        )
    else:
        db_data = load_db()
        gift_name = db_data.get("gift_name", "الهدية اليومية")
        ref_name = db_data.get("referral_name", "رابط الإحالة")
        
        markup.add(
            types.InlineKeyboardButton(f"🎁 {gift_name}", callback_data="gift_claim"),
            types.InlineKeyboardButton(f"🔗 {ref_name}", callback_data="ref_link_get")
        )
    return markup

def back_only_markup(btn):
    parent_id = btn.get("parent_id")
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "🔙 رجوع", callback_data=f"nav_back_{parent_id if parent_id else 'root'}"
        )
    )
    return markup

def build_admin_settings_markup(db, parent_id=None):
    children = get_children(db, parent_id)
    markup = types.InlineKeyboardMarkup()
    
    for i in range(0, len(children), 2):
        row_buttons = []
        for btn in children[i:i+2]:
            has_sub = len(get_children(db, btn["id"])) > 0
            icon = "📁" if has_sub else "📄"
            is_locked = int(btn.get("unlock_points", 0)) > 0
            lock_icon = " 🔒" if is_locked else ""
            row_buttons.append(
                types.InlineKeyboardButton(f"{icon} {btn['name']}{lock_icon}", callback_data=f"adm_set_click_{btn['id']}")
            )
        markup.row(*row_buttons)

    if parent_id is not None:
        parent = get_button(db, parent_id)
        back_to = parent.get("parent_id") if parent else None
        markup.add(
            types.InlineKeyboardButton("🔙 رجوع", callback_data=f"adm_set_back_{back_to if back_to else 'root'}")
        )
    else:
        markup.add(types.InlineKeyboardButton("🔙 رجوع لوحة التحكم", callback_data="adm_back_main"))
    return markup

@bot.message_handler(commands=["start"])
def start(message):
    clear_state(message.from_user.id)
    register_user(message.from_user.id)
    u = message.from_user
    uid_str = str(u.id)
    name = f"{u.first_name or ''} {u.last_name or ''}".strip() or u.username or ""
    register_user_points(u.id, name)

    # Referral system handling
    text_parts = message.text.split()
    if len(text_parts) > 1:
        ref_arg = text_parts[1]
        if ref_arg.isdigit() and int(ref_arg) != u.id:
            referrer_id_str = str(ref_arg)
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT referrer_id FROM referrals WHERE referred_id = ?", (uid_str,))
            existing_ref = cursor.fetchone()
            if not existing_ref:
                db = load_db()
                if db.get("referral_active", True):
                    cursor.execute("INSERT OR REPLACE INTO referrals (referred_id, referrer_id) VALUES (?, ?)", (uid_str, referrer_id_str))
                    conn.commit()
                    
                    ref_pts = db.get("referral_points", 5)
                    users_data = load_users()
                    if referrer_id_str in users_data["users"]:
                        users_data["users"][referrer_id_str]["points"] = users_data["users"][referrer_id_str].get("points", 0) + ref_pts
                        save_users(users_data)
                        
                        try:
                            bot.send_message(
                                int(referrer_id_str),
                                f"🎉 انضم مستخدم جديد عبر رابط إحالتك!\n"
                                f"تمت إضافة {ref_pts} نقاط إلى رصيدك 🌟"
                            )
                        except Exception:
                            pass
            conn.close()

    if u.id != ADMIN_ID:
        missing = check_subscription(u.id)
        if missing:
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "✅ تحقق من الاشتراك", callback_data="sub_check"
                )
            )
            bot.send_message(
                message.chat.id,
                "⚠️ يجب عليك الاشتراك في قنواتنا لاستخدام البوت.\n"
                "اشترك ثم أرسل /start أو اضغط الزر أدناه للتحقق.",
                reply_markup=markup,
            )
            return

    db = load_db()
    if get_children(db, None):
        bot.send_message(
            message.chat.id,
            "أهلاً بك في متجري! اختر من القائمة:",
            reply_markup=build_nav_markup(db, None),
        )
    else:
        bot.send_message(
            message.chat.id,
            "أهلاً بك! القائمة فارغة حالياً.\nتواصل مع الإدارة أو انتظر إضافة الخدمات.",
        )

def admin_menu_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⚙️ إعدادات الخدمات والأزرار", callback_data="adm_settings_list"))
    markup.add(
        types.InlineKeyboardButton("🎁 إعدادات الهدية اليومية", callback_data="adm_feat_gift"),
        types.InlineKeyboardButton("🔗 إعدادات نظام الإحالة", callback_data="adm_feat_ref")
    )
    markup.add(types.InlineKeyboardButton("🛡 إدارة الاشتراك الإجباري", callback_data="adm_feat_sub"))
    markup.add(types.InlineKeyboardButton("🔒 قفل الخدمات بنقاط", callback_data="adm_lock_menu"))
    markup.add(types.InlineKeyboardButton("➕ إضافة زر", callback_data="adm_add"), types.InlineKeyboardButton("🗑 حذف زر", callback_data="adm_delete"))
    markup.add(types.InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="adm_users"), types.InlineKeyboardButton("📣 إرسال إعلان", callback_data="adm_broadcast"))
    return markup

@bot.message_handler(commands=["admin"])
def admin(message):
    if message.from_user.id != ADMIN_ID:
        return
    clear_state(message.from_user.id)
    db = load_db()
    bot.send_message(
        message.chat.id,
        f"🔧 لوحة التحكم\nإجمالي الأزرار: {len(db['buttons'])}",
        reply_markup=admin_menu_markup(),
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_edit_") or call.data.startswith("change_"))
def handle_dynamic_admin_actions(call):
    data = call.data
    cid = call.message.chat.id
    uid = call.from_user.id
    
    if data.startswith("adm_edit_"):
        btn_id = data.replace("adm_edit_", "")
        db = load_db()
        btn = get_button(db, btn_id)
        
        if not btn:
            bot.answer_callback_query(call.id, "⚠️ هذا العنصر غير موجود أو تم حذفه.", show_alert=True)
            return
            
        btn_name = btn.get('name', 'بدون اسم')
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📝 تعديل الاسم", callback_data=f"change_{btn_id}_name"),
            types.InlineKeyboardButton("📄 تعديل المحتوى/الوصف", callback_data=f"change_{btn_id}_content")
        )
        markup.add(
            types.InlineKeyboardButton("💎 تعديل النقاط/الإعدادات", callback_data=f"change_{btn_id}_points"),
            types.InlineKeyboardButton("🗑️ حذف الخدمة/الزر", callback_data=f"delete_btn_{btn_id}")
        )
        markup.add(types.InlineKeyboardButton("🔙 عودة لقائمة إعدادات الخدمات", callback_data="adm_settings_list"))
        
        bot.edit_message_text(
            f"⚙️ **لوحة التحكم الخاصة بـ:** «{btn_name}»\n\n"
            f"من هنا يمكنك التحكم الكامل بالخدمة (تعديل، تغيير، حذف، أو تحرير كافة محتوياتها):",
            cid,
            call.message.message_id,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)

    elif data.startswith("change_"):
        parts = data.split("_")
        if len(parts) >= 3:
            btn_id = parts[1]
            key = parts[2]
            
            set_state(uid, "WAIT_DYNAMIC_BTN_EDIT", btn_id=btn_id, edit_key=key)
            
            db = load_db()
            btn = get_button(db, btn_id)
            btn_name = btn.get('name', 'الخدمة') if btn else 'الخدمة'
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data=f"adm_edit_{btn_id}"))
            
            key_translations = {
                "name": "الاسم الجديد",
                "content": "المحتوى أو الوصف الجديد",
                "points": "النقاط أو الإعدادات الجديدة"
            }
            readable_key = key_translations.get(key, key)
            
            bot.edit_message_text(
                f"✍️ أنت الآن تقوم بـ **تعديل ({readable_key})** للخدمة/الزر: «{btn_name}».\n\n"
                f"أرسل القيمة الجديدة الآن في رسالة وسيقوم البوت بتحديثها وحفظها فوراً:",
                cid,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    bot.answer_callback_query(call.id)  
    try:
        data = call.data
        uid = call.from_user.id
        cid = call.message.chat.id
        mid = call.message.message_id

        if data == "ref_link_get":
            db = load_db()
            if not db.get("referral_active", True):
                bot.send_message(cid, "⚠️ خدمة نظام الإحالة متوقفة مؤقتاً من قبل الإدارة.")
                return
            bot_username = bot.get_me().username
            ref_link = f"https://t.me/{bot_username}?start={uid}"
            ref_pts = db.get("referral_points", 5)
            
            users_db = load_users()
            u_data = users_db["users"].get(str(uid), {})
            user_points = u_data.get("points", 0)
            
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (str(uid),))
            ref_count = cursor.fetchone()[0]
            conn.close()
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="nav_back_root"))
            
            bot.send_message(
                cid,
                f"🔗 **نظام الإحالة وجلب النقاط المجانية**\n\n"
                f"شارك رابطك الخاص مع أصدقائك أو في المجموعات:\n"
                f"`{ref_link}`\n\n"
                f"📊 **إحصائياتك:**\n"
                f"• عدد الأشخاص الذين أحلتهم: {ref_count} شخص\n"
                f"• النقاط المكتسبة من الإحالات: ستحصل على **{ref_pts}** نقاط عن كل مستخدم جديد يسجل عبر رابطك!\n"
                f"• رصيدك الحالي: {user_points} نقطة 🌟",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            return

        if data == "adm_settings_list" or data == "admin_buttons_list":
            db = load_db()
            markup = build_admin_settings_markup(db, None)
            bot.edit_message_text(
                "⚙️ **إعدادات الخدمات والأزرار:**\n\n"
                "اختر القسم الرئيسي أو الزر الذي تريد إدارته وتعديله:",
                cid, mid, reply_markup=markup, parse_mode="Markdown"
            )
            return

        if data.startswith("adm_set_back_"):
            db = load_db()
            target = data[len("adm_set_back_"):]
            parent_id = None if target == "root" else target
            markup = build_admin_settings_markup(db, parent_id)
            title = "⚙️ **إعدادات الخدمات والأزرار:**\n\nاختر القسم أو الزر:" if parent_id is None else f"⚙️ إدارة قسم: «{(get_button(db, parent_id) or {}).get('name', '')}»"
            bot.edit_message_text(title, cid, mid, reply_markup=markup, parse_mode="Markdown")
            return

        if data.startswith("adm_set_click_"):
            btn_id = data[len("adm_set_click_"):]
            db = load_db()
            btn = get_button(db, btn_id)
            if not btn:
                bot.answer_callback_query(call.id, "⚠️ هذا العنصر غير موجود.", show_alert=True)
                return
            
            children = get_children(db, btn_id)
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("⚙️ تعديل اسم، محتوى أو إعدادات هذا الزر", callback_data=f"adm_edit_{btn_id}")
            )
            if children:
                markup.add(
                    types.InlineKeyboardButton(f"📂 استعراض الأزرار الفرعية بداخله ({len(children)})", callback_data=f"adm_set_subnav_{btn_id}")
                )
            markup.add(
                types.InlineKeyboardButton("🔙 رجوع للقائمة السابقة", callback_data=f"adm_set_back_{btn.get('parent_id') if btn.get('parent_id') else 'root'}")
            )
            
            bot.edit_message_text(
                f"🎛 **إدارة العنصر:** «{btn['name']}»\n\nاختر الإجراء المطلوب:",
                cid, mid, reply_markup=markup, parse_mode="Markdown"
            )
            return

        if data.startswith("adm_set_subnav_"):
            btn_id = data[len("adm_set_subnav_"):]
            db = load_db()
            markup = build_admin_settings_markup(db, btn_id)
            btn = get_button(db, btn_id)
            bot.edit_message_text(
                f"📂 الأزرار الفرعية داخل: «{btn['name'] if btn else ''}»\n\nاختر الزر الفرعي المطلوب إدارته:",
                cid, mid, reply_markup=markup, parse_mode="Markdown"
            )
            return

        if data == "adm_feat_gift":
            db = load_db()
            current_points = db.get("gift_points", 2)
            gift_name = db.get("gift_name", "الهدية اليومية")
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("✏️ تعديل عدد النقاط", callback_data="edit_gift_points_val"),
                types.InlineKeyboardButton("👁 معرفة النقاط الحالية", callback_data="show_gift_points")
            )
            markup.add(
                types.InlineKeyboardButton("📝 تغيير اسم الخدمة", callback_data="edit_gift_name"),
                types.InlineKeyboardButton("🔄 تفعيل/إيقاف الخدمة", callback_data="toggle_gift_status")
            )
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_back_main"))
            bot.edit_message_text(
                f"⚙️ إعدادات الهدية اليومية:\n\n• الاسم: {gift_name}\n• النقاط: {current_points}\n• الحالة: مفعلة ✅", 
                cid, mid, reply_markup=markup
            )
            return

        if data == "adm_feat_ref":
            db = load_db()
            ref_pts = db.get("referral_points", 5)
            ref_name = db.get("referral_name", "رابط الإحالة")
            ref_status = "مفعل ✅" if db.get("referral_active", True) else "معطل ❌"
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("✏️ تعديل نقاط الإحالة", callback_data="edit_ref_points_val"),
                types.InlineKeyboardButton("📝 تغيير اسم الزر", callback_data="edit_ref_name")
            )
            markup.add(
                types.InlineKeyboardButton("🔄 تفعيل/إيقاف الخدمة", callback_data="toggle_ref_status"),
                types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_back_main")
            )
            bot.edit_message_text(
                f"⚙️ **إعدادات نظام الإحالة المتقدمة:**\n\n"
                f"• اسم الزر: {ref_name}\n"
                f"• نقاط كل إحالة: {ref_pts} نقاط\n"
                f"• الحالة: {ref_status}\n\n"
                f"اختر ما تريد تعديله:",
                cid, mid, reply_markup=markup, parse_mode="Markdown"
            )
            return

        if data == "edit_ref_points_val":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="adm_feat_ref"))
            msg = bot.edit_message_text("✍️ أرسل الآن عدد النقاط الجديد لكل إحالة (برقم صحيح):", cid, mid, reply_markup=markup)
            bot.register_next_step_handler(msg, save_new_ref_points)
            return

        if data == "edit_ref_name":
            set_state(uid, WAIT_REF_NAME)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="adm_feat_ref"))
            try:
                bot.delete_message(cid, mid)
            except: pass
            bot.send_message(cid, "✍️ أرسل الآن اسم زر الإحالة الجديد في القائمة الرئيسية:", reply_markup=markup)
            return

        if data == "toggle_ref_status":
            db = load_db()
            current_status = db.get("referral_active", True)
            db["referral_active"] = not current_status
            save_db(db)
            status_text = "مفعل ✅" if db["referral_active"] else "معطل ❌"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_feat_ref"))
            bot.edit_message_text(f"🔄 تم تغيير حالة نظام الإحالة بنجاح!\nالحالة الآن: {status_text}", cid, mid, reply_markup=markup)
            return

        if data == "show_gift_points":
            db = load_db()
            pts = db.get("gift_points", 2)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_feat_gift"))
            bot.edit_message_text(f"🎁 عدد النقاط الحالي في الهدية اليومية هو: **{pts}** نقطة.", cid, mid, reply_markup=markup, parse_mode="Markdown")
            return

        if data == "edit_gift_points_val":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="adm_feat_gift"))
            msg = bot.edit_message_text("✍️ أرسل عدد النقاط الجديد:", cid, mid, reply_markup=markup)
            bot.register_next_step_handler(msg, save_new_gift_points)
            return
            
        if data == "edit_gift_name":
            set_state(uid, WAIT_GIFT_NAME)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="adm_feat_gift"))
            try:
                bot.delete_message(cid, mid)
            except: pass
            bot.send_message(cid, "✍️ أرسل اسم الهدية اليومية الجديد:", reply_markup=markup)
            return

        if data == "toggle_gift_status":
            db = load_db()
            current_status = db.get("gift_active", True)
            db["gift_active"] = not current_status
            save_db(db)
            status_text = "مفعلة ✅" if db["gift_active"] else "معطلة ❌"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_feat_gift"))
            bot.edit_message_text(f"🔄 الحالة الحالية للهدية: {status_text}", cid, mid, reply_markup=markup)
            return

        if data == "toggle_sub_status":
            db = load_db()
            current_status = db.get("sub_active", True)
            db["sub_active"] = not current_status
            save_db(db)
            status_text = "مفعل ✅" if db["sub_active"] else "معطل ❌"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_feat_sub"))
            bot.edit_message_text(f"🔄 الحالة الحالية: {status_text}", cid, mid, reply_markup=markup)
            return

        if data == "list_sub_channels":
            db = load_db()
            channels = db.get("sub_channels", REQUIRED_CHANNELS)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_feat_sub"))
            ch_list = "\n".join([f"• {ch}" for ch in channels]) if channels else "لا توجد قنوات"
            bot.edit_message_text(f"📋 القنوات:\n\n{ch_list}", cid, mid, reply_markup=markup)
            return

        if data == "adm_feat_sub":
            db = load_db()
            sub_st = "مفعل ✅" if db.get("sub_active", True) else "معطل ❌"
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("📋 عرض القنوات", callback_data="list_sub_channels"),
                types.InlineKeyboardButton("➕ إضافة قناة", callback_data="add_sub_channel")
            )
            markup.add(
                types.InlineKeyboardButton("🗑 إزالة قناة", callback_data="remove_sub_channel"),
                types.InlineKeyboardButton("🔄 تفعيل/إيقاف", callback_data="toggle_sub_status")
            )
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_back_main"))
            bot.edit_message_text(f"🛡 إدارة الاشتراك الإجباري:\n• الحالة: {sub_st}", cid, mid, reply_markup=markup)
            return

        if data == "adm_back_main":
            bot.edit_message_text("👋 أهلاً بك في لوحة التحكم:", call.message.chat.id, call.message.message_id, reply_markup=admin_menu_markup())
            return

        if data.startswith("pay_"):
            btn_id = data[len("pay_"):]
            db = load_db()
            btn = get_button(db, btn_id)
            if not btn:
                bot.answer_callback_query(call.id, "⚠️ الزر غير موجود.", show_alert=True)
                return
                
            unlock_pts = int(btn.get("unlock_points", 0))
            users_db = load_users()
            uid_str = str(uid)
            user = users_db["users"].get(uid_str)
            
            if not user or user.get("points", 0) < unlock_pts:
                bot.answer_callback_query(call.id, f"❌ رصيد نقاطك غير كافٍ! تحتاج {unlock_pts} نقطة.", show_alert=True)
                return
                
            user["points"] -= unlock_pts
            if "unlocked" not in user:
                user["unlocked"] = []
            user["unlocked"].append(btn_id)
            save_users(users_db)
            
            bot.answer_callback_query(call.id, "✅ تم الدفع وفتح الخدمة بنجاح!", show_alert=True)
            try:
                bot.delete_message(cid, mid)
            except: pass
            send_content(cid, btn, back_only_markup(btn))
            return

        if data.startswith("nav_"):
            db = load_db()
            if uid in db.get("banned_users", []):
                bot.send_message(cid, "⛔ أنت محظور من استخدام هذا البوت.")
                return

            if data.startswith("nav_back_"):
                target = data[len("nav_back_") :]
                parent_id = None if target == "root" else target
                text = "أهلاً بك في متجري! اختر من القائمة:" if parent_id is None else ((get_button(db, parent_id) or {}).get("name", "اختر:"))
                nav_markup = build_nav_markup(db, parent_id)
                if call.message.content_type != "text":
                    try:
                        bot.delete_message(cid, mid)
                    except: pass
                    bot.send_message(cid, text, reply_markup=nav_markup)
                else:
                    bot.edit_message_text(text, cid, mid, reply_markup=nav_markup)
                return

            btn_id = data[len("nav_") :]
            btn = get_button(db, btn_id)
            if not btn:
                bot.send_message(cid, "⚠️ هذا الزر لم يعد موجوداً.")
                return

            if get_children(db, btn_id):
                bot.edit_message_text(btn["name"], cid, mid, reply_markup=build_nav_markup(db, btn_id))
            else:
                unlock_pts = int(btn.get("unlock_points", 0))
                if uid == ADMIN_ID:
                    send_content(cid, btn, back_only_markup(btn))
                elif unlock_pts > 0:
                    users_db = load_users()
                    uid_str = str(uid)
                    user_data_db = users_db["users"].get(uid_str, {})
                    user_unlocked = user_data_db.get("unlocked", [])
                    
                    if btn_id in user_unlocked:
                        send_content(cid, btn, back_only_markup(btn))
                    else:
                        desc = btn.get("unlock_desc", "هذا المحتوى حصري ومقفول.")
                        markup = types.InlineKeyboardMarkup()
                        markup.add(types.InlineKeyboardButton(f"🔓 فتح الخدمة بـ {unlock_pts} نقطة", callback_data=f"pay_{btn_id}"))
                        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=f"nav_back_{btn.get('parent_id', 'root')}"))
                        payment_text = f"🔒 **خدمة مدفوعة**\n\n{desc}\n\n⚠️ **تكلفة الفتح:** {unlock_pts} نقطة."
                        
                        if call.message.content_type != "text":
                            try: bot.delete_message(cid, mid)
                            except: pass
                            bot.send_message(cid, payment_text, reply_markup=markup, parse_mode="Markdown")
                        else:
                            bot.edit_message_text(payment_text, cid, mid, reply_markup=markup, parse_mode="Markdown")
                else:
                    send_content(cid, btn, back_only_markup(btn))
            return

        if data == "gift_claim":
            db = load_db()
            if not db.get("gift_active", True):
                bot.send_message(cid, "⚠️ الهدية اليومية متوقفة مؤقتاً.")
                return
            success, msg = claim_daily_gift(uid)
            bot.send_message(cid, msg)
            return

        if data == "sub_check":
            db = load_db()
            if not db.get("sub_active", True) or not REQUIRED_CHANNELS:
                bot.send_message(cid, "✅ لا توجد قنوات مطلوبة حالياً.")
                return
            missing = check_subscription(uid)
            if missing:
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="sub_check"))
                bot.send_message(cid, "❌ لم تشترك في جميع القنوات بعد.", reply_markup=markup)
            else:
                if get_children(db, None):
                    bot.send_message(cid, "✅ تم التحقق!", reply_markup=build_nav_markup(db, None))
                else:
                    bot.send_message(cid, "✅ تم التحقق!")
            return

        if uid != ADMIN_ID:
            return

        if data == "adm_add":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📌 زر رئيسي", callback_data="adm_add_main"))
            markup.add(types.InlineKeyboardButton("🔗 زر فرعي", callback_data="adm_add_sub"))
            bot.send_message(cid, "نوع الزر الجديد:", reply_markup=markup)

        elif data == "adm_add_main":
            set_state(uid, WAIT_BTN_NAME, parent_id=None)
            bot.send_message(cid, "📝 أرسل اسم الزر الرئيسي:\n/cancel للإلغاء")

        elif data == "adm_add_sub":
            db = load_db()
            root_buttons = [b for b in db["buttons"] if b.get("parent_id") is None]
            if not root_buttons:
                bot.send_message(cid, "⚠️ لا توجد أقسام رئيسية.")
                return
            markup = types.InlineKeyboardMarkup()
            for btn in root_buttons:
                markup.add(types.InlineKeyboardButton(f"📁 {btn['name']}", callback_data=f"adm_sub_root_{btn['id']}"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_back_main"))
            bot.edit_message_text("اختر القسم الرئيسي:", cid, mid, reply_markup=markup)

        elif data.startswith("adm_sub_root_"):
            root_id = data[len("adm_sub_root_"):]
            db = load_db()
            root_btn = get_button(db, root_id)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(f"➕ إضافة داخل «{root_btn['name']}»", callback_data=f"adm_parent_{root_id}"))
            children = get_children(db, root_id)
            for child in children:
                markup.add(types.InlineKeyboardButton(f"📄 بداخل: {child['name']}", callback_data=f"adm_parent_{child['id']}"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_add_sub"))
            bot.edit_message_text("حدد مكان إضافة الزر:", cid, mid, reply_markup=markup)

        elif data.startswith("adm_parent_"):
            parent_id = data[len("adm_parent_") :]
            db = load_db()
            parent = get_button(db, parent_id)
            set_state(uid, WAIT_BTN_NAME, parent_id=parent_id)
            bot.edit_message_text(f"أرسل **اسم الزر الجديد** تحت «{parent['name']}»:", cid, mid, parse_mode="Markdown")

        elif data == "adm_lock_menu":
            db = load_db()
            leaves = [b for b in db["buttons"] if not get_children(db, b["id"]) and b.get("parent_id") is not None]
            if not leaves:
                bot.send_message(cid, "⚠️ لا توجد خدمات لقفلها.")
                return
            markup = types.InlineKeyboardMarkup()
            for btn in leaves:
                is_locked = int(btn.get("unlock_points", 0)) > 0
                lock_icon = " 🔒" if is_locked else " 🔓"
                markup.add(types.InlineKeyboardButton(f"{btn['name']}{lock_icon}", callback_data=f"lockbtn_{btn['id']}"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_back_main"))
            bot.edit_message_text("اختر الخدمة لتعيين القفل بالنقاط:", cid, mid, reply_markup=markup)

        elif data.startswith("lockbtn_"):
            btn_id = data[len("lockbtn_") :]
            db = load_db()
            btn = get_button(db, btn_id)
            set_state(uid, WAIT_LOCK_POINTS, btn_id=btn_id)
            bot.send_message(cid, f"أرسل عدد النقاط المطلوبة لفتح «{btn['name']}» (0 للإلغاء):")

        elif data == "adm_delete":
            db = load_db()
            markup = types.InlineKeyboardMarkup()
            for btn in db["buttons"]:
                markup.add(types.InlineKeyboardButton(f"🗑 {btn['name']}", callback_data=f"del_{btn['id']}"))
            bot.send_message(cid, "اختر الزر للحذف:", reply_markup=markup)

        elif data.startswith("del_") or data.startswith("delete_btn_"):
            btn_id = data.replace("del_", "").replace("delete_btn_", "")
            db = load_db()
            descendants = collect_descendants(db, btn_id)
            db["buttons"] = [b for b in db["buttons"] if b["id"] not in descendants and b["id"] != btn_id]
            save_db(db)
            bot.send_message(cid, "✅ تم الحذف بنجاح.")

        elif data == "adm_users":
            db = load_db()
            users = db.get("users", [])
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("👁 عرض المستخدمين", callback_data="usr_view"))
            markup.add(types.InlineKeyboardButton("🚫 حظر مستخدم", callback_data="usr_ban"))
            markup.add(types.InlineKeyboardButton("✅ رفع الحظر", callback_data="usr_unban"))
            bot.send_message(cid, f"👥 إجمالي المستخدمين: {len(users)}", reply_markup=markup)

        elif data == "usr_view":
            db = load_db()
            users = db.get("users", [])
            bot.send_message(cid, f"👥 المستخدمون:\n" + "\n".join([str(u) for u in users[:50]]))

        elif data == "usr_ban":
            set_state(uid, WAIT_BAN)
            bot.send_message(cid, "أرسل ID المستخدم لحظره:")

        elif data == "usr_unban":
            set_state(uid, WAIT_UNBAN)
            bot.send_message(cid, "أرسل ID المستخدم لرفع حظره:")

        elif data == "adm_broadcast":
            db = load_db()
            set_state(uid, WAIT_BROADCAST)
            bot.send_message(cid, f"📣 أرسل رسالة البث لـ {len(db['users'])} مستخدم:")

    except Exception as e:
        report_admin_error(e, "callback")

@bot.message_handler(
    content_types=["text", "photo", "document", "video", "audio", "voice", "sticker"],
    func=lambda m: not (m.content_type == "text" and m.text and m.text.startswith("/")),
)
def handle_state(message):
    uid = message.from_user.id
    cid = message.chat.id
    state = get_state(uid)

    if state is None:
        return

    if message.content_type == "text" and message.text.strip().startswith("/cancel"):
        clear_state(uid)
        bot.send_message(cid, "❌ تم الإلغاء.")
        return

    if state == WAIT_BTN_NAME:
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ أرسل الاسم كنص.")
            return
        btn_name = message.text.strip()
        parent_id = get_data(uid).get("parent_id")
        set_state(uid, WAIT_BTN_CONTENT, parent_id=parent_id, btn_name=btn_name)
        bot.send_message(cid, f"الآن أرسل محتوى الزر «{btn_name}»:")

    elif state == WAIT_BTN_CONTENT:
        d = get_data(uid)
        parent_id = d.get("parent_id")
        btn_name = d.get("btn_name", "زر")
        ct, content = extract_content(message)
        
        db = load_db()
        db["buttons"].append({
            "id": new_id(), "name": btn_name, "content_type": ct,
            "content": content, "parent_id": parent_id, "unlock_points": 0, "unlock_desc": ""
        })
        save_db(db)
        clear_state(uid)
        bot.send_message(cid, f"✅ تم حفظ الزر «{btn_name}» بنجاح!")

    elif state == WAIT_LOCK_POINTS:
        try:
            pts = int(message.text.strip())
            btn_id = get_data(uid).get("btn_id")
            if pts <= 0:
                db = load_db()
                btn = get_button(db, btn_id)
                btn["unlock_points"] = 0
                btn["unlock_desc"] = ""
                save_db(db)
                clear_state(uid)
                bot.send_message(cid, "✅ تم إلغاء القفل وأصبح مجانياً.")
            else:
                set_state(uid, WAIT_LOCK_DESC, btn_id=btn_id, points=pts)
                bot.send_message(cid, "✍️ أرسل رسالة الوصف التي ستظهر للمستخدم قبل الدفع:")
        except ValueError:
            bot.send_message(cid, "❌ أرسل رقماً صحيحاً.")

    elif state == WAIT_LOCK_DESC:
        desc = message.text.strip()
        d = get_data(uid)
        btn_id = d.get("btn_id")
        pts = d.get("points")
        db = load_db()
        btn = get_button(db, btn_id)
        if btn:
            btn["unlock_points"] = pts
            btn["unlock_desc"] = desc
            save_db(db)
        clear_state(uid)
        bot.send_message(cid, f"✅ تم القفل بنجاح (السعر: {pts} نقطة).")

    elif state == WAIT_GIFT_NAME:
        new_name = message.text.strip()
        db = load_db()
        db["gift_name"] = new_name
        save_db(db)
        clear_state(uid)
        bot.send_message(cid, f"✅ تم تغيير اسم الهدية إلى: {new_name}")

    elif state == WAIT_REF_NAME:
        new_name = message.text.strip()
        db = load_db()
        db["referral_name"] = new_name
        save_db(db)
        clear_state(uid)
        bot.send_message(cid, f"✅ تم تغيير اسم زر الإحالة إلى: {new_name}")

    elif state == "WAIT_DYNAMIC_BTN_EDIT":
        state_data = get_data(uid)
        btn_id = state_data.get("btn_id")
        edit_key = state_data.get("edit_key")
        new_value = message.text.strip()
        db = load_db()
        btn = get_button(db, btn_id)
        if btn:
            btn[edit_key] = new_value
            save_db(db)
        clear_state(uid)
        bot.send_message(cid, "✅ تم التعديل بنجاح.")

    elif state == WAIT_BAN:
        try:
            target_id = int(message.text.strip())
            db = load_db()
            if target_id not in db.get("banned_users", []):
                db.setdefault("banned_users", []).append(target_id)
                save_db(db)
                bot.send_message(cid, f"✅ تم الحظر.")
        except ValueError:
            pass
        clear_state(uid)

    elif state == WAIT_UNBAN:
        try:
            target_id = int(message.text.strip())
            db = load_db()
            if target_id in db.get("banned_users", []):
                db["banned_users"].remove(target_id)
                save_db(db)
                bot.send_message(cid, f"✅ تم رفع الحظر.")
        except ValueError:
            pass
        clear_state(uid)

    elif state == WAIT_BROADCAST:
        db = load_db()
        sent = 0
        for target_uid in db.get("users", []):
            if target_uid == ADMIN_ID: continue
            try:
                bot.copy_message(target_uid, cid, message.message_id)
                sent += 1
            except: pass
        clear_state(uid)
        bot.send_message(cid, f"📣 تم البث بنجاح لـ {sent} مستخدم.")

def save_new_gift_points(message):
    try:
        new_pts = int(message.text.strip())
        db = load_db()
        db["gift_points"] = new_pts
        save_db(db)
        bot.send_message(message.chat.id, f"✅ تم التحديث إلى {new_pts} نقطة.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ خطأ في الرقم.")

def save_new_ref_points(message):
    try:
        new_pts = int(message.text.strip())
        db = load_db()
        db["referral_points"] = new_pts
        save_db(db)
        bot.send_message(message.chat.id, f"✅ تم تحديث نقاط الإحالة إلى: {new_pts} نقطة لكل شخص.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ خطأ: يرجى إرسال رقم صحيح.")

logger.info("Bot is starting (polling with SQLite & Referrals)...")
while True:
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        logger.exception("Polling crashed")
        time.sleep(5)
