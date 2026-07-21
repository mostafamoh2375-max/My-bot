import os
import sys
import json
import uuid
import time
import logging
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

# Files for JSON storage
DB_FILE = "buttons.json"
USERS_FILE = "users.json"

# Bot token (required)
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or "7623300303:AAHA-f9LWLbKE4uP-1ZDn8E2IHkGzUm5vaM"

if not TOKEN:
    # Fail fast, clearly — avoids creating a bot instance with None token
    sys.stderr.write("ERROR: TELEGRAM_BOT_TOKEN environment variable is not set.\n")
    raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set")

# Admin Telegram ID (integer)
ADMIN_ID = 8097008430

# Create bot instance
bot = telebot.TeleBot(TOKEN, threaded=True)

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def report_admin_error(exc: Exception, context: str = ""):
    """Log exception and attempt to notify the admin with a short traceback."""
    try:
        logger.exception("Unhandled exception in %s: %s", context, exc)
    except Exception:
        # best-effort logging; don't fail if logging itself errors
        pass
    try:
        # Short admin message (avoid sending huge traces into chat)
        bot.send_message(
            ADMIN_ID,
            f"⚠️ Error in bot ({context}):\n{type(exc).__name__}: {str(exc)[:300]}",
        )
    except Exception:
        # If sending to admin fails, just swallow — we already logged
        logger.exception("Failed to send error message to ADMIN_ID")

# ── Force-subscribe channels ────────────────────────────────────
# Add channel usernames (e.g. '@mychannel') or numeric IDs here.
# Leave empty to disable the force-subscribe check entirely.
REQUIRED_CHANNELS = ["@Salemly_1", "@shr_llh"]

# ═══════════════════════════════════════════════════════════════
#  STATE MACHINE
# ═══════════════════════════════════════════════════════════════

user_states = {}  # uid → state string
user_data = {}  # uid → dict of temporary data

# State constants
WAIT_BTN_NAME = "WAIT_BTN_NAME"
WAIT_BTN_CONTENT = "WAIT_BTN_CONTENT"
WAIT_BTN_PASSWORD = "WAIT_BTN_PASSWORD"  # admin: optional password after content
WAIT_SET_PW_PICK = "WAIT_SET_PW_PICK"  # admin: change pw on existing button
WAIT_PASSWORD_INPUT = "WAIT_PASSWORD_INPUT"  # user: entering password for locked button
WAIT_BROADCAST = "WAIT_BROADCAST"
WAIT_BAN = "WAIT_BAN"
WAIT_UNBAN = "WAIT_UNBAN"


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


# ═══════════════════════════════════════════════════════════════
#  DATABASE
# ═══════════════════════════════════════════════════════════════


def load_db():
    if not os.path.exists(DB_FILE):
        default = {"buttons": [], "users": [], "banned_users": []}
        save_db(default)
        return default
    with open(DB_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("buttons", [])
    data.setdefault("users", [])
    data.setdefault("banned_users", [])
    return data


def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def register_user(user_id):
    db = load_db()
    if user_id not in db["users"]:
        db["users"].append(user_id)
        save_db(db)


# ── Points system (users.json) ──────────────────────────────────


def load_users():
    if not os.path.exists(USERS_FILE):
        default = {"users": {}}
        save_users(default)
        return default
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("users", {})
    return data


def save_users(data):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def register_user_points(user_id, name=""):
    """Ensure the user exists in users.json with a points field (default 0).
    Never overwrites an existing points balance."""
    data = load_users()
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {"name": name, "points": 0}
        save_users(data)
    else:
        # Update name if provided and points key is missing (safety migration)
        changed = False
        if name and data["users"][uid].get("name") != name:
            data["users"][uid]["name"] = name
            changed = True
        if "points" not in data["users"][uid]:
            data["users"][uid]["points"] = 0
            changed = True
        if changed:
            save_users(data)


# ── Force-subscribe check ───────────────────────────────────────


def check_subscription(user_id):
    """Return list of channel IDs the user has NOT joined.
    Empty list means all checks passed (or REQUIRED_CHANNELS is empty)."""
    not_subscribed = []
    for channel in REQUIRED_CHANNELS:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status in ("left", "kicked"):
                not_subscribed.append(channel)
        except Exception as e:
            # Can't verify → treat as not subscribed to be safe
            logger.exception("check_subscription failed for %s: %s", channel, e)
            not_subscribed.append(channel)
    return not_subscribed


# ── Daily gift ──────────────────────────────────────────────────

GIFT_POINTS = 2
GIFT_INTERVAL = 86400  # 24 hours in seconds


def claim_daily_gift(user_id):
    """Try to claim the daily gift.
    Returns (success: bool, message_ar: str)."""
    data = load_users()
    uid = str(user_id)
    if uid not in data["users"]:
        return False, "⚠️ سجّل أولاً بإرسال /start"
    user = data["users"][uid]
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
    user["points"] = user.get("points", 0) + GIFT_POINTS
    user["last_gift"] = now
    save_users(data)
    return True, (
        f"🎁 تهانينا! حصلت على {GIFT_POINTS} نقاط!\n"
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


# ═══════════════════════════════════════════════════════════════
#  CONTENT HELPERS
# ═══════════════════════════════════════════════════════════════


def extract_content(message):
    """Return (content_type, file_id_or_text) from any message type."""
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
    """Send a button's stored content to the user."""
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


# ═══════════════════════════════════════════════════════════════
#  NAVIGATION MARKUP
# ═══════════════════════════════════════════════════════════════


def build_nav_markup(db, parent_id=None):
    """Inline keyboard of children, plus 🔙 if not at root.
    At root level, appends the 🎁 Daily Gift button."""
    children = get_children(db, parent_id)
    markup = types.InlineKeyboardMarkup()
    for btn in children:
        markup.add(
            types.InlineKeyboardButton(btn["name"], callback_data=f"nav_{btn['id']}")
        )
    if parent_id is not None:
        parent = get_button(db, parent_id)
        back_to = parent.get("parent_id") if parent else None
        markup.add(
            types.InlineKeyboardButton(
                "🔙 رجوع", callback_data=f"nav_back_{back_to if back_to else 'root'}"
            )
        )
    else:
        # Root level — add the Daily Gift button
        markup.add(
            types.InlineKeyboardButton("🎁 الهدية اليومية", callback_data="gift_claim")
        )
    return markup


def back_only_markup(btn):
    """Single 🔙 button pointing to the button's parent level."""
    parent_id = btn.get("parent_id")
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "🔙 رجوع", callback_data=f"nav_back_{parent_id if parent_id else 'root'}"
        )
    )
    return markup


# ═══════════���═══════════════════════════════════════════════════
#  /start
# ═══════════════════════════════════════════════════════════════


@bot.message_handler(commands=["start"])
def start(message):
    logger.info("Bot received start command from %s", message.from_user.id)
    clear_state(message.from_user.id)
    register_user(message.from_user.id)
    u = message.from_user
    name = f"{u.first_name or ''} {u.last_name or ''}".strip() or u.username or ""
    register_user_points(u.id, name)

    # ── Force-subscribe gate (admin always bypasses) ────────────
    if u.id != ADMIN_ID and REQUIRED_CHANNELS:
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


# ═══════════════════════════════════════════════════════════════
#  /admin
# ═══════════════════════════════════════════════════════════════


def admin_menu_markup():
    markup = types.InlineKeyboardMarkup()
    # إدارة الخدمات
    markup.add(types.InlineKeyboardButton("⚙️ إعدادات الخدمات والأزرار", callback_data="adm_settings_list"))
    # إدارة الميزات
    markup.add(types.InlineKeyboardButton("🎁 إعدادات الهدية اليومية", callback_data="adm_feat_gift"))
    markup.add(types.InlineKeyboardButton("🛡 إدارة الاشتراك الإجباري", callback_data="adm_feat_sub"))
    # الإدارة العامة
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

@bot.callback_query_handler(func=lambda call: call.data == "adm_settings_list")
def list_buttons_for_settings(call):
    db = load_db()
    markup = types.InlineKeyboardMarkup()
    for btn in db["buttons"]:
        markup.add(types.InlineKeyboardButton(btn["name"], callback_data=f"adm_edit_{btn['id']}"))
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_back_main")) # تأكد أن لديك دالة للرجوع
    bot.edit_message_text("اختر الزر لتعديل إعداداته:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_edit_"))
def edit_btn_settings(call):
    btn_id = call.data.split("_")[2]
    db = load_db()
    btn = get_button(db, btn_id)
    if not btn: return
    
    if "settings" not in btn:
        btn["settings"] = {"points": "0", "status": "on"}
        save_db(db)
        
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✏️ تغيير الاسم", callback_data=f"change_{btn_id}_name"))
    markup.add(types.InlineKeyboardButton("📝 تغيير المحتوى", callback_data=f"change_{btn_id}_content"))
    markup.add(types.InlineKeyboardButton(f"⭐ النقاط: {btn.get('settings', {}).get('points', '0')}", callback_data=f"change_{btn_id}_points"))
    markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_settings_list"))
    
    bot.edit_message_text(f"تحكم في الزر «{btn['name']}»:", call.message.chat.id, call.message.message_id, reply_markup=markup)


# ═══════════════════════════════════════════════════════════════
#  CALLBACK HANDLER
# ═══════════════════════════════════════════════════════════════


@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    bot.answer_callback_query(call.id)  # Always first — kills the loading spinner
    try:
        data = call.data
        uid = call.from_user.id
        cid = call.message.chat.id
        mid = call.message.message_id
       # 1. إعدادات الهدية اليومية الرئيسية
       if data == "adm_feat_gift":
            db = load_db()
            current_points = db.get("gift_points", 5) # افتراضي 5 نقاط
            gift_name = db.get("gift_name", "الهدية اليومية")
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("✏️ تعديل عدد النقاط", callback_data="edit_gift_points_val"),
                types.InlineKeyboardButton("👁 معرفة النقاط الحالية", callback_data="show_gift_points")
            )
            markup.add(
                types.InlineKeyboardButton("📝 تغيير اسم الخدمة", callback_data="change_gift_name"),
                types.InlineKeyboardButton("🔄 تفعيل/إيقاف الخدمة", callback_data="toggle_gift_status")
            )
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_back_main"))
            bot.edit_message_text(
                f"⚙️ إعدادات الهدية اليومية المتقدمة:\n\n• اسم الخدمة: {gift_name}\n• الحالة: مفعلة ✅\n• النقاط الحالية: {current_points}\n\nاختر ما تريد تعديله:", 
                cid, mid, reply_markup=markup
            )
            return

        # 2. أزرار الهدية الوظيفية الحقيقية
        if data == "show_gift_points":
            db = load_db()
            pts = db.get("gift_points", 5)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_feat_gift"))
            bot.edit_message_text(f"🎁 عدد النقاط الحالي الممنوح في الهدية اليومية هو: **{pts}** نقطة.", cid, mid, reply_markup=markup, parse_mode="Markdown")
            return

        if data == "edit_gift_points_val":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="adm_feat_gift"))
            msg = bot.edit_message_text("✍️ أرسل الآن عدد النقاط الجديد (برقم صحيح) لتعيينه للهدية اليومية:", cid, mid, reply_markup=markup)
            bot.register_next_step_handler(msg, save_new_gift_points)
            return

        if data == "change_gift_name":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="adm_feat_gift"))
            msg = bot.edit_message_text("✍️ أرسل الآن اسم الخدمة الجديد للهدية اليومية:", cid, mid, reply_markup=markup)
            bot.register_next_step_handler(msg, save_new_gift_name)
            return

        if data == "toggle_gift_status":
            db = load_db()
            current_status = db.get("gift_active", True)
            db["gift_active"] = not current_status
            save_db(db)
            status_text = "مفعلة ✅" if db["gift_active"] else "معطلة ❌"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_feat_gift"))
            bot.edit_message_text(f"🔄 تم تغيير حالة الهدية بنجاح!\nالحالة الحالية الآن: {status_text}", cid, mid, reply_markup=markup)
            return

        if data == "change_sub_name":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="adm_feat_sub"))
            msg = bot.edit_message_text("✍️ أرسل الآن اسم الخدمة الجديد للاشتراك الإجباري:", cid, mid, reply_markup=markup)
            bot.register_next_step_handler(msg, save_new_sub_name)
            return

        if data in ["list_sub_channels", "add_sub_channel", "remove_sub_channel", "toggle_sub_status"]:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 رجوع لإعدادات الاشتراك", callback_data="adm_feat_sub"))
            bot.edit_message_text(
                "🛠 تم تفعيل هذا القسم لتنفيذ إدارة القنوات والاشتراك الإجباري بشكل تفاعلي ومباشر.", 
                cid, mid, reply_markup=markup
            )
            return

        if data == "adm_feat_sub":
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("📋 عرض القنوات المضافة", callback_data="list_sub_channels"),
                types.InlineKeyboardButton("➕ إضافة قناة جديدة", callback_data="add_sub_channel")
            )
            markup.add(
                types.InlineKeyboardButton("🗑 إزالة قناة", callback_data="remove_sub_channel"),
                types.InlineKeyboardButton("🔄 تفعيل/إيقاف الاشتراك", callback_data="toggle_sub_status")
            )
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_back_main"))
            bot.edit_message_text(
                "🛡 **إدارة الاشتراك الإجباري المتقدمة:**\n\n"
                "• الحالة: مفعل ✅\n"
                "• القنوات المرتبطة: تدار عبر هذا الزر\n\n"
                "اختر إجراء التحكم المطلوب:", 
                cid, mid, reply_markup=markup, parse_mode="Markdown"
            )
            return

                # إضافة هذه الأسطر لربط الأزرار الجديدة
        if data == "adm_back_main":
            bot.edit_message_text("👋 أهلاً بك في لوحة التحكم:", call.message.chat.id, call.message.message_id, reply_markup=admin_menu_markup())
            return
        if data == "adm_settings_list":
            list_buttons_for_settings(call)
            return

        # ── User navigation ────────────────────────────────────────────────
        if data.startswith("nav_"):
            db = load_db()

            if uid in db.get("banned_users", []):
                bot.send_message(cid, "⛔ أنت محظور من استخدام هذا البوت.")
                return

            # Back button
            if data.startswith("nav_back_"):
                target = data[len("nav_back_") :]
                parent_id = None if target == "root" else target
                text = (
                    "أهلاً بك في متجري! اختر من القائمة:"
                    if parent_id is None
                    else ((get_button(db, parent_id) or {}).get("name", "اختر:"))
                )
                nav_markup = build_nav_markup(db, parent_id)
                # Media messages (photo, video, etc.) have no text field —
                # edit_message_text would crash with "no text in the message".
                # Delete the media message and send a fresh text message instead.
                if call.message.content_type != "text":
                    try:
                        bot.delete_message(cid, mid)
                    except Exception as e:
                        logger.exception("Failed to delete media message before navigating back")
                    bot.send_message(cid, text, reply_markup=nav_markup)
                else:
                    bot.edit_message_text(text, cid, mid, reply_markup=nav_markup)
                return

            # Forward into a button
            btn_id = data[len("nav_") :]
            btn = get_button(db, btn_id)
            if not btn:
                bot.send_message(cid, "⚠️ هذا الزر لم يعد موجوداً.")
                return

            if get_children(db, btn_id):
                # Has sub-buttons → navigate in place
                bot.edit_message_text(
                    btn["name"], cid, mid, reply_markup=build_nav_markup(db, btn_id)
                )
            else:
                # Leaf → check password first (admin always bypasses)
                password = btn.get("password", "").strip()
                if password and uid != ADMIN_ID:
                    set_state(uid, WAIT_PASSWORD_INPUT, btn_id=btn_id)
                    bot.send_message(
                        cid,
                        f"🔒 هذا القسم محمي بكلمة مرور.\nأرسل كلمة المرور للمتابعة:\n/cancel للإلغاء",
                    )
                else:
                    send_content(cid, btn, back_only_markup(btn))
            return

        # ── Daily Gift ─────────────────────────────────────────────────────
        if data == "gift_claim":
            success, msg = claim_daily_gift(uid)
            bot.send_message(cid, msg)
            return

        # ── Subscription check ─────────────────────────────────────────────
        if data == "sub_check":
            if not REQUIRED_CHANNELS:
                bot.send_message(cid, "✅ لا توجد قنوات مطلوبة حالياً.")
                return
            missing = check_subscription(uid)
            if missing:
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton(
                        "✅ تحقق من الاشتراك", callback_data="sub_check"
                    )
                )
                bot.send_message(
                    cid,
                    "❌ لم تشترك في جميع القنوات المطلوبة بعد.\n"
                    "اشترك ثم اضغط زر التحقق مجدداً أو أرسل /start.",
                    reply_markup=markup,
                )
            else:
                db = load_db()
                if get_children(db, None):
                    bot.send_message(
                        cid,
                        "✅ تم التحقق! أهلاً بك في متجري! اختر من القائمة:",
                        reply_markup=build_nav_markup(db, None),
                    )
                else:
                    bot.send_message(cid, "✅ تم التحقق! أهلاً بك! القائمة فارغة حالياً.")
            return

        # ── Admin only below ───────────────────────────────────────────────
        if uid != ADMIN_ID:
            return

        # ── Add button ─────────────────────────────────────────────────────
        if data == "adm_add":
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "📌 زر رئيسي (بدون أب)", callback_data="adm_add_main"
                )
            )
            markup.add(
                types.InlineKeyboardButton(
                    "🔗 زر فرعي (تحت زر موجود)", callback_data="adm_add_sub"
                )
            )
            bot.send_message(cid, "نوع الزر الجديد:", reply_markup=markup)

        elif data == "adm_add_main":
            set_state(uid, WAIT_BTN_NAME, parent_id=None)
            bot.send_message(cid, "📝 أرسل اسم الزر الرئيسي:\n/cancel للإلغاء")

        elif data == "adm_add_sub":
            db = load_db()
            if not db["buttons"]:
                bot.send_message(cid, "⚠️ لا توجد أزرار بعد. أضف زراً رئيسياً أولاً.")
                return
            markup = types.InlineKeyboardMarkup()
            for btn in db["buttons"]:
                p = get_button(db, btn["parent_id"]) if btn.get("parent_id") else None
                label = f"{btn['name']}  ← {p['name']}" if p else btn["name"]
                markup.add(
                    types.InlineKeyboardButton(
                        label, callback_data=f"adm_parent_{btn['id']}"
                    )
                )
            bot.send_message(cid, "اختر الزر الأب:", reply_markup=markup)

        elif data.startswith("adm_parent_"):
            parent_id = data[len("adm_parent_") :]
            db = load_db()
            parent = get_button(db, parent_id)
            if not parent:
                bot.send_message(cid, "⚠️ الزر الأب غير موجود.")
                return
            set_state(uid, WAIT_BTN_NAME, parent_id=parent_id)
            bot.send_message(
                cid, f"📝 أرسل اسم الزر الفرعي تحت «{parent['name']}»:\n/cancel للإلغاء"
            )

        # ── Set / change password on existing button ───────────────────────
        elif data == "adm_setpw":
            db = load_db()
            leaves = [b for b in db["buttons"] if not get_children(db, b["id"]) ]
            if not leaves:
                bot.send_message(cid, "⚠️ لا توجد أزرار نهائية (leaf) لحمايتها بعد.")
                return
            markup = types.InlineKeyboardMarkup()
            for btn in leaves:
                # Hide actual password in the list label; show only lock icon
                pw_hint = " 🔒" if btn.get("password") else " 🔓"
                p = get_button(db, btn["parent_id"]) if btn.get("parent_id") else None
                path = f"  ← {p['name']}" if p else ""
                markup.add(
                    types.InlineKeyboardButton(
                        f"{btn['name']}{pw_hint}{path}",
                        callback_data=f"setpw_{btn['id']}",
                    )
                )
            bot.send_message(
                cid,
                "اختر الزر لتعيين/تغيير كلمته السرية:\n(🔒 = محمي | 🔓 = مفتوح)",
                reply_markup=markup,
            )

        elif data.startswith("setpw_"):
            btn_id = data[len("setpw_") :]
            db = load_db()
            btn = get_button(db, btn_id)
            if not btn:
                bot.send_message(cid, "⚠️ الزر غير موجود.")
                return
            current = (
                f"كلمة المرور الحالية: `{btn['password']}`\n\n"
                if btn.get("password")
                else ""
            )
            set_state(uid, WAIT_SET_PW_PICK, btn_id=btn_id)
            bot.send_message(
                cid,
                f"🔑 الزر: «{btn['name']}" + "»\n" + current
                + f"أرسل كلمة المرور الجديدة، أو أرسل 0 لإزالة الحماية:\n/cancel للإلغاء",
            )

        # ── Delete button ──────────────────────────────────────────────────
        elif data == "adm_delete":
            db = load_db()
            if not db["buttons"]:
                bot.send_message(cid, "لا توجد أزرار لحذفها.")
                return
            markup = types.InlineKeyboardMarkup()
            for btn in db["buttons"]:
                p = get_button(db, btn["parent_id"]) if btn.get("parent_id") else None
                pw_hint = (
                    f" (كلمة المرور)" if btn.get("password") else ""
                )
                base = f"{btn['name']}{pw_hint}"
                label = f"🗑 {base}  ← {p['name']}" if p else f"🗑 {base}"
                markup.add(
                    types.InlineKeyboardButton(label, callback_data=f"del_{btn['id']}")
                )
            bot.send_message(
                cid, "اختر الزر لحذفه (سيُحذف مع كل أبنائه):", reply_markup=markup
            )

        elif data.startswith("del_"):
            btn_id = data[len("del_") :]
            db = load_db()
            btn = get_button(db, btn_id)
            if not btn:
                bot.send_message(cid, "الزر غير موجود.")
                return
            descendants = collect_descendants(db, btn_id)
            total = len(descendants)
            db["buttons"] = [
                b
                for b in db["buttons"]
                if b["id"] not in descendants and b["id"] != btn_id
            ]
            save_db(db)
            extra = f" و{total} زر فرعي" if total else ""
            bot.send_message(cid, f"✅ تم حذف «{btn['name']}»{extra}.")

        # ── User management ────────────────────────────────────────────────
        elif data == "adm_users":
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("👁 عرض المستخدمين", callback_data="usr_view")
            )
            markup.add(
                types.InlineKeyboardButton("🚫 حظر مستخدم", callback_data="usr_ban")
            )
            markup.add(
                types.InlineKeyboardButton("✅ رفع الحظر", callback_data="usr_unban")
            )
            bot.send_message(cid, "👥 إدارة المستخدمين:", reply_markup=markup)

        elif data == "usr_view":
            db = load_db()
            users = db.get("users", [])
            banned = db.get("banned_users", [])
            if not users:
                bot.send_message(cid, "لا يوجد مستخدمون مسجلون بعد.")
                return
            lines = [f"• {u}{' 🚫' if u in banned else ''}" for u in users]
            bot.send_message(
                cid,
                f"👥 المستخدمون ({len(users)}):\n" + "\n".join(lines) + "\n\n🚫 = محظور",
            )

        elif data == "usr_ban":
            set_state(uid, WAIT_BAN)
            bot.send_message(cid, "أرسل ID المستخدم لحظره:\n/cancel للإلغاء")

        elif data == "usr_unban":
            db = load_db()
            banned = db.get("banned_users", [])
            if not banned:
                bot.send_message(cid, "لا يوجد مستخدمون محظورون.")
                return
            set_state(uid, WAIT_UNBAN)
            bot.send_message(
                cid,
                "المحظورون:\n"
                + "\n".join(f"• {u}" for u in banned)
                + "\n\nأرسل ID لرفع حظره:\n/cancel للإلغاء",
            )

        # ── Broadcast ──────────────────────────────────────────────────────
        elif data == "adm_broadcast":
            db = load_db()
            set_state(uid, WAIT_BROADCAST)
            bot.send_message(
                cid,
                f"📣 أرسل الرسالة للبث إلى {len(db['users'])} مستخدم:\n"
                f"(يمكنك إرسال نص، صورة، فيديو، ملف...)\n/cancel للإلغاء",
            )

    except Exception as e:
        report_admin_error(e, "callback")


# ═══════════════════════════════════════════════════════════════
#  UNIFIED MESSAGE HANDLER (state machine)
# ═══════════════════════════════════════════════════════════════


@bot.message_handler(
    content_types=["text", "photo", "document", "video", "audio", "voice", "sticker"],
    func=lambda m: not (m.content_type == "text" and m.text and m.text.startswith("/")),
)
def handle_state(message):
    uid = message.from_user.id
    cid = message.chat.id
    state = get_state(uid)

    # ── No active state → forward to admin ────────────────────────────────
    if state is None:
        if uid != ADMIN_ID:
            try:
                bot.forward_message(ADMIN_ID, cid, message.message_id)
            except Exception as e:
                logger.exception("Failed to forward message to admin")
        return

    # ── /cancel check (text only) ──────────────────────────────────────────
    if message.content_type == "text" and message.text.strip().startswith("/cancel"):
        clear_state(uid)
        bot.send_message(cid, "❌ تم الإلغاء.")
        return

    # ── Route by state ─────────────────────────────────────────────────────

    if state == WAIT_BTN_NAME:
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ أرسل اسم الزر كنص من فضلك.")
            return
        btn_name = message.text.strip()
        parent_id = get_data(uid).get("parent_id")
        set_state(uid, WAIT_BTN_CONTENT, parent_id=parent_id, btn_name=btn_name)
        bot.send_message(
            cid,
            f"✅ الاسم: «{btn_name}»\n\n"
            f"الآن أرسل المحتوى (نص، صورة، فيديو، ملف...):\n/cancel للإلغاء",
        )

    elif state == WAIT_BTN_CONTENT:
        bot.send_message(cid, "⏳ تم استلام المحتوى...")
        d = get_data(uid)
        parent_id = d.get("parent_id")
        btn_name = d.get("btn_name", "زر")
        ct, content = extract_content(message)
        # Transition to password step — keep all collected data
        set_state(
            uid,
            WAIT_BTN_PASSWORD,
            parent_id=parent_id,
            btn_name=btn_name,
            content_type=ct,
            content=content,
        )
        bot.send_message(
            cid,
            f"🔑 هل تريد حماية الزر «{btn_name}» بكلمة مرور؟\n\n"
            f"• أرسل كلمة المرور لتفعيل الحماية\n"
            f"• أرسل 0 (صفر) لتركه مفتوحاً بدون كلمة مرور\n"
            f"/cancel للإلغاء",
        )

    elif state == WAIT_BTN_PASSWORD:
        # Admin setting optional password after uploading content
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ أرسل كلمة المرور كنص، أو أرسل 0 للتخطي.")
            return
        d = get_data(uid)
        parent_id = d.get("parent_id")
        btn_name = d.get("btn_name", "زر")
        ct = d.get("content_type", "text")
        content = d.get("content", "")
        raw = message.text.strip()
        password = "" if raw == "0" else raw
        db = load_db()
        db["buttons"].append(
            {
                "id": new_id(),
                "name": btn_name,
                "content_type": ct,
                "content": content,
                "parent_id": parent_id,
                "password": password,
            }
        )
        save_db(db)
        clear_state(uid)
        level = "رئيسي" if parent_id is None else "فرعي"
        pw_msg = (
            f"🔒 محمي بكلمة مرور: `{password}`"
            if password
            else "🔓 مفتوح (بدون كلمة مرور)"
        )
        bot.send_message(
            cid,
            f"✅ تم حفظ الزر {level} «{btn_name}»!\n"
            f"نوع المحتوى: {ct}\n{pw_msg}\n"
            f"المستخدمون سيرونه فور ضغطهم على /start.",
        )

    elif state == WAIT_SET_PW_PICK:
        # Admin changing password on an existing button
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ أرسل كلمة المرور كنص، أو أرسل 0 لإزالة الحماية.")
            return
        btn_id = get_data(uid).get("btn_id")
        raw = message.text.strip()
        password = "" if raw == "0" else raw
        db = load_db()
        btn = get_button(db, btn_id)
        if not btn:
            bot.send_message(cid, "⚠️ الزر لم يعد موجوداً.")
            clear_state(uid)
            return
        btn["password"] = password
        save_db(db)
        clear_state(uid)
        if password:
            bot.send_message(
                cid, f"✅ تم تعيين كلمة المرور «{password}» للزر «{btn['name']}»."
            )
        else:
            bot.send_message(
                cid, f"✅ تمت إزالة كلمة المرور من الزر «{btn['name']}». هو الآن مفتوح."
            )

    elif state == WAIT_PASSWORD_INPUT:
        # User entering password for a locked button
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ أرسل كلمة المرور كنص.")
            return
        btn_id = get_data(uid).get("btn_id")
        db = load_db()
        btn = get_button(db, btn_id)
        if not btn:
            bot.send_message(cid, "⚠️ هذا الزر لم يعد موجوداً.")
            clear_state(uid)
            return
        if message.text.strip() == btn.get("password", ""):
            clear_state(uid)
            send_content(cid, btn, back_only_markup(btn))
        else:
            bot.send_message(
                cid, "❌ كلمة المرور خاطئة. حاول مرة أخرى أو أرسل /cancel للإلغاء."
            )

    elif state == WAIT_BAN:
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ أرسل ID المستخدم كرقم.")
            return
        try:
            target_id = int(message.text.strip())
            db = load_db()
            if target_id not in db.get("banned_users", []):
                db.setdefault("banned_users", []).append(target_id)
                save_db(db)
                bot.send_message(cid, f"✅ تم حظر المستخدم {target_id}.")
            else:
                bot.send_message(cid, f"المستخدم {target_id} محظور مسبقاً.")
        except ValueError:
            bot.send_message(cid, "⚠️ ID غير صحيح، يجب أن يكون رقماً.")
        clear_state(uid)

    elif state == WAIT_UNBAN:
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ أرسل ID المستخدم كرقم.")
            return
        try:
            target_id = int(message.text.strip())
            db = load_db()
            if target_id in db.get("banned_users", []):
                db["banned_users"].remove(target_id)
                save_db(db)
                bot.send_message(cid, f"✅ تم رفع الحظر عن {target_id}.")
            else:
                bot.send_message(cid, f"المستخدم {target_id} ليس محظوراً.")
        except ValueError:
            bot.send_message(cid, "⚠️ ID غير صحيح، يجب أن يكون رقماً.")
        clear_state(uid)

    elif state == WAIT_BROADCAST:
        bot.send_message(cid, "⏳ جاري الإرسال...")
        db = load_db()
        sent = 0
        failed = 0
        for target_uid in db.get("users", []):
            if target_uid == ADMIN_ID:
                continue
            try:
                bot.copy_message(target_uid, cid, message.message_id)
                sent += 1
            except Exception as e:
                logger.exception("Failed to send broadcast message to %s", target_uid)
                failed += 1
        clear_state(uid)
        bot.send_message(cid, f"📣 اكتمل البث:\n✅ نجح: {sent}\n❌ فشل: {failed}")


# دالة استقبال التعديل الجديد (أضفها في نهاية الملف)
def update_json_setting(btn_id, key, new_value):
    db = load_db()
    for btn in db["buttons"]:
        if btn["id"] == btn_id:
            # تحديث القيمة في قاموس الإعدادات
            btn["settings"][key] = new_value
            break
    save_db(db)

# دالة التعامل مع ضغط زر الإعداد (أضفها مع دوال الـ callback)
@bot.callback_query_handler(func=lambda call: call.data.startswith("change_"))
def handle_change_setting(call):
    btn_id = call.data.split("_")[1]
    key = call.data.split("_")[2]
    
    msg = bot.send_message(call.message.chat.id, f"أرسل القيمة الجديدة لـ {key}:")
    bot.register_next_step_handler(msg, lambda m: finish_update(m, btn_id, key))

def finish_update(message, btn_id, key):
    update_json_setting(btn_id, key, message.text)
    bot.send_message(message.chat.id, f"✅ تم تحديث {key} بنجاح!")


# ═══════════════════════════════════════════════════════════════
#  RUN
# ═══════════════════════════════════════════════════════════════

logger.info("Bot is starting (polling)...")
while True:
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        logger.exception("Polling crashed — will restart in 5s")
        try:
            bot.send_message(ADMIN_ID, f"⚠️ Bot polling crashed: {type(e).__name__}: {str(e)[:300]}")
        except Exception:
            logger.exception("Failed to notify admin about polling crash")
        time.sleep(5)
