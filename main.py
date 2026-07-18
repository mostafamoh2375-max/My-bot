import os
import sys
import json
import uuid
import time
import logging

import telebot
from telebot import types

# Files for JSON storage
DB_FILE = "buttons.json"
USERS_FILE = "users.json"

# Bot token (required)
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

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

# Startup diagnostics: validate token and detect existing webhook (best-effort).
try:
    # Verify token is valid and get bot identity
    me = bot.get_me()
    if isinstance(me, dict):
        first_name = me.get("first_name")
        username = me.get("username")
        bot_id = me.get("id")
    else:
        first_name = getattr(me, "first_name", None)
        username = getattr(me, "username", None)
        bot_id = getattr(me, "id", None)
    logger.info("Bot identity verified: %s (@%s, id=%s)", first_name, username, bot_id)
    # Also print to stdout so hosting platforms show the identity prominently
    print(f"Bot running as: @{username or 'unknown'} (id: {bot_id})", flush=True)
except Exception as e:
    logger.exception("Failed to validate TELEGRAM_BOT_TOKEN with getMe(): %s", e)
    raise

try:
    url = None
    if hasattr(bot, "get_webhook_info"):
        info = bot.get_webhook_info()
        if isinstance(info, dict):
            url = info.get("url") or (info.get("result", {}) or {}).get("url")
        else:
            url = getattr(info, "url", None)
    if url:
        logger.warning(
            "Telegram webhook is set for this token: %s. Polling (getUpdates) may not receive updates while webhook is active.",
            url,
        )
except Exception:
    logger.debug("Could not retrieve webhook info at startup; continuing to polling.")


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


def load_required_channels():
    """
    Load the required channels list from buttons.json (via load_db()) and return it as a list
    of channel identifiers (strings). Accepts either:
      - a JSON array under the "required_channels" key, e.g. ["@chan1", "@chan2"]
      - or a comma-separated string, e.g. "@chan1,@chan2"
      - or numeric IDs (will be converted to strings)
    Falls back to the in-file REQUIRED_CHANNELS constant if the key is missing (preserves
    backwards compatibility). Returns an empty list if nothing is configured or on error.
    """
    try:
        db = load_db()
        channels = db.get("required_channels", None)

        # If the key is missing in buttons.json, keep backward compatibility and use the in-file constant.
        if channels is None:
            try:
                return [str(c).strip() for c in REQUIRED_CHANNELS if str(c).strip()]
            except Exception:
                return []

        # If it's already a list, normalize entries to non-empty stripped strings
        if isinstance(channels, list):
            result = []
            for c in channels:
                if c is None:
                    continue
                s = str(c).strip()
                if s:
                    result.append(s)
            return result

        # If it's a single string, allow comma-separated values
        if isinstance(channels, str):
            return [c.strip() for c in channels.split(",") if c.strip()]

    except Exception as e:
        # Don't raise — log and return empty (no checks)
        logger.exception("Failed to load required channels from %s: %s", DB_FILE, e)

    return []


def check_subscription(user_id):
    """Return list of channel IDs the user has NOT joined.
    Empty list means all checks passed (or no required channels configured).

    The required channels are loaded dynamically from buttons.json via load_required_channels().
    Any verification error will treat the channel as "not subscribed" to be safe.
    """
    not_subscribed = []
    required_channels = load_required_channels()

    # If no required channels configured, treat as all checks passed.
    if not required_channels:
        return []

    for channel in required_channels:
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

# (rest of file unchanged)


# ---- start bot (append at end of file) ----
def _run_polling_loop():
    """Run the bot polling loop forever, restarting on exceptions."""
    while True:
        try:
            logger.info("Starting Telegram polling...")
            # Try to use infinity_polling (recommended in newer pyTelegramBotAPI).
            if hasattr(bot, "infinity_polling"):
                # use reasonable timeouts to avoid hanging forever
                bot.infinity_polling(timeout=60, long_polling_timeout=60)
            else:
                # Fallback to classic polling; none_stop=True keeps it running
                bot.polling(none_stop=True, timeout=60)
        except Exception as exc:
            # Log and notify admin, then sleep briefly before restart to avoid tight loop.
            logger.exception("Polling crashed, will restart after delay: %s", exc)
            try:
                report_admin_error(exc, "polling")
            except Exception:
                logger.exception("Failed to report error to admin")
            time.sleep(5)


if __name__ == "__main__":
    _run_polling_loop()
