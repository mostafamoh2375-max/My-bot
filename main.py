import os
import sys
import re
import uuid
import time
import logging
from flask import Flask
from threading import Thread
from pymongo import MongoClient

# 1. الاتصال بقاعدة البيانات
client = MongoClient(
    "mongodb+srv://mostafamoh2375_db_user:MKSybnr160hjilGEv7MZG@cluster0.rxdqdlv.mongodb.net/mostafamoh2375_db_user?appName=Cluster0"
)
db = client.get_database()

# 2. إدخال الأزرار تلقائياً إذا كانت القاعدة فارغة
if db.buttons.count_documents({}) == 0:
    buttons_data = [
        {
            "id": "7787b22b",
            "name": "خدمة التطبيقات 🛍",
            "content": "تطبيقات سلملي",
            "parent_id": None,
        },
        {
            "id": "4e8bda81",
            "name": "تطبيقات المدفوعه",
            "content_type": "document",
            "content": "BQACAgQAAxkBAAIBCWpW_bw_UISLUE6NdyVPccJng7Q9AAI4GgACunW4UlmUx04MM8hLPQQ",
            "parent_id": "7787b22b",
            "password": "",
        },
        {
            "id": "48536625",
            "name": "📩 الشكاوي",
            "content_type": "text",
            "content": (
                "📩 الشكاوي والمقترحات\n\n"
                "من فضلك أخبرنا بالمشكلة 😞\n"
                "أو اقترح تعديلاً لتحسين البوت ❤️\n\n"
                "(يمكنك إرسال نص / صورة / صوت / فيديو / ملف)"
            ),
            "parent_id": None,
            "password": "",
        },
        {
            "id": "65baee1a",
            "name": "🔰مالك البوت",
            "content_type": "text",
            "content": "@Y_S_KK",
            "parent_id": None,
            "password": "",
        },
        {
            "id": "8d0e6f86",
            "name": "جديد",
            "content_type": "text",
            "content": "البوت تحت الصيانه ⚠ || سيتم تحديث خدمات البوت في اقرب وقت شكرا لتفهمكم",
            "parent_id": None,
            "password": "",
        },
    ]
    db.buttons.insert_many(buttons_data)

# 3. إعدادات القنوات والمشرفين
if db.settings.count_documents({"_id": "config"}) == 0:
    db.settings.update_one(
        {"_id": "config"},
        {
            "$set": {
                "required_channels": ["@Salemly_1", "@shr_llh"],
                "admins": [8097008430],
            }
        },
        upsert=True,
    )

# 4. إدخال بيانات المستخدم والنقاط
if db.users.count_documents({"_id": "users_dict"}) == 0:
    users_data = {
        "8097008430": {
            "name": "مصطفى شخصيه خياليه",
            "points": 2,
            "last_gift": 1784096431.0477734,
        }
    }
    db.users.insert_one({"_id": "users_dict", "data": users_data})

# ==================== إعداد خادم Flask للبقاء حياً على Render ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and connected to MongoDB Atlas"

def run():
    app.run(host='0.0.0.0', port=8080)

t = Thread(target=run)
t.start()

import telebot
from telebot import types

# ==================== إعدادات اتصال MongoDB Atlas ====================
MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://mostafamoh2375_db_user:MKSybnr160hjilGEv7MZG@cluster0.rxdqdlv.mongodb.net/mostafamoh2375_db_user?appName=Cluster0"
)
client = MongoClient(MONGO_URI)
mongo_db = client["telegram_bot_db"]
config_collection = mongo_db["config"]
users_collection = mongo_db["users_data"]

# Bot token (required)
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or "7623300303:AAHA-f9LWLbKE4uP-1ZDn8E2IHkGzUm5vaM"

if not TOKEN:
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
        pass
    try:
        bot.send_message(
            ADMIN_ID,
            f"⚠️ Error in bot ({context}):\n{type(exc).__name__}: {str(exc)[:300]}",
        )
    except Exception:
        logger.exception("Failed to send error message to ADMIN_ID")


def get_display_name(user):
    """يرجع اسم المستخدم بالضبط كما يظهر في حسابه على تيليجرام (الاسم الأول + الأخير)."""
    name = f"{getattr(user, 'first_name', '') or ''} {getattr(user, 'last_name', '') or ''}".strip()
    if not name:
        name = f"@{user.username}" if getattr(user, 'username', None) else "صديقنا"
    return name


def main_menu_welcome_text(user, lang="ar"):
    return t("welcome", lang).format(name=get_display_name(user))


# ── Force-subscribe channels ────────────────────────────────────
REQUIRED_CHANNELS = ["@Salemly_1", "@shr_llh"]


def flag(country_code):
    """يحوّل رمز الدولة الدولي (مثل EG) إلى إيموجي علمها تلقائياً."""
    return "".join(chr(0x1F1E6 + ord(c) - ord('A')) for c in country_code.upper())


# نطاقات اليونيكود الشائعة للإيموجي، تُستخدم لاكتشاف الإيموجي في بداية اسم الزر
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF"
    "\U00002B00-\U00002BFF"
    "\U0001F000-\U0001F0FF"
    "\uFE0F\u200D"
    "]+"
)


def extract_leading_emoji(text):
    """يستخرج الإيموجي (إن وُجد) من بداية النص."""
    match = _EMOJI_PATTERN.match((text or "").strip())
    return match.group(0).strip() if match else ""


def merge_emoji(old_name, new_text):
    """
    عند تعديل اسم زر: إذا كان النص الجديد لا يبدأ بإيموجي، يحافظ تلقائياً على إيموجي
    الاسم القديم (إن وُجد) في نفس المكان، بدل أن يختفي عند تعديل الاسم فقط.
    إذا كتب الأدمن إيموجي جديداً في بداية النص الجديد، يُستخدم هو (تغيير مقصود).
    """
    new_text = (new_text or "").strip()
    if _EMOJI_PATTERN.match(new_text):
        return new_text
    old_emoji = extract_leading_emoji(old_name)
    return f"{old_emoji} {new_text}" if old_emoji else new_text


# نصوص واجهة ثابتة (ليست من صنع الأدمن) تتغيّر تلقائياً حسب لغة المستخدم المختارة
TRANSLATIONS = {
    "ar": {
        "welcome": "👋 أهلاً بك {name}! اختر من القائمة:",
        "back": "🔙 رجوع",
        "no_content_yet": "(لا يوجد محتوى بعد.)",
        "locked_default_desc": "هذا المحتوى حصري ومقفول.",
    },
    "en": {
        "welcome": "👋 Welcome {name}! Choose from the menu:",
        "back": "🔙 Back",
        "no_content_yet": "(No content yet.)",
        "locked_default_desc": "This content is exclusive and locked.",
    },
}


def t(key, lang):
    lang = lang if lang in TRANSLATIONS else "ar"
    return TRANSLATIONS[lang].get(key, TRANSLATIONS["ar"][key])


# ── ترجمة تلقائية ومجانية للمحتوى الذي يكتبه الأدمن (بدون أي مفتاح API) ──
# تتطلب تثبيت مكتبة deep-translator على سيرفر الاستضافة: pip install deep-translator
try:
    from deep_translator import GoogleTranslator as _GoogleTranslator
    _TRANSLATOR_AVAILABLE = True
except Exception:
    _TRANSLATOR_AVAILABLE = False


def translate_text(text, target_lang):
    """
    يترجم نصاً عربياً كتبه الأدمن إلى الإنجليزية تلقائياً عبر خدمة مجانية.
    عند أي فشل (لا إنترنت، المكتبة غير مثبّتة، النص فارغ...) يرجع النص الأصلي
    كما هو بدل أن يتعطل البوت.
    """
    text = (text or "").strip()
    if not text or target_lang == "ar" or not _TRANSLATOR_AVAILABLE:
        return text
    try:
        return _GoogleTranslator(source="ar", target="en").translate(text)
    except Exception:
        logger.exception("فشلت الترجمة التلقائية، سيُعرض النص الأصلي بدلاً منها")
        return text


def localized_field(container, field, lang, translate_fn=None):
    """
    يرجع نسخة الحقل المترجمة (مثلاً name أو content) حسب لغة المستخدم، مع تخزين
    الترجمة داخل نفس العنصر (field + '_en') بشكل دائم كي لا تُعاد الترجمة في كل
    مرة (أسرع، ويعمل حتى لو صار انقطاع مؤقت لاحقاً في خدمة الترجمة).
    يرجع True في العنصر الثاني إذا تمت ترجمة جديدة الآن (لحفظها لاحقاً دفعة واحدة).
    """
    original = container.get(field, "") or ""
    if lang != "en":
        return original, False
    cache_key = f"{field}_en"
    cached = container.get(cache_key)
    if cached:
        return cached, False
    translated = (translate_fn or translate_text)(original, "en")
    container[cache_key] = translated
    return translated, True


# قائمة دول العالم مقسّمة حسب القارة: (رمز الدولة، الاسم بالعربية)
COUNTRIES_BY_CONTINENT = [
    ("🌏 آسيا", [
        ("SA", "السعودية"), ("AE", "الإمارات"), ("QA", "قطر"), ("KW", "الكويت"),
        ("BH", "البحرين"), ("OM", "عُمان"), ("YE", "اليمن"), ("IQ", "العراق"),
        ("SY", "سوريا"), ("LB", "لبنان"), ("JO", "الأردن"), ("PS", "فلسطين"),
        ("TR", "تركيا"), ("IR", "إيران"), ("CY", "قبرص"),
        ("CN", "الصين"), ("JP", "اليابان"), ("KR", "كوريا الجنوبية"), ("KP", "كوريا الشمالية"),
        ("IN", "الهند"), ("PK", "باكستان"), ("BD", "بنغلاديش"), ("LK", "سريلانكا"),
        ("NP", "نيبال"), ("BT", "بوتان"), ("MV", "جزر المالديف"), ("MM", "ميانمار"),
        ("TH", "تايلاند"), ("VN", "فيتنام"), ("LA", "لاوس"), ("KH", "كمبوديا"),
        ("MY", "ماليزيا"), ("SG", "سنغافورة"), ("ID", "إندونيسيا"), ("PH", "الفلبين"),
        ("BN", "بروناي"), ("TL", "تيمور الشرقية"), ("MN", "منغوليا"), ("KZ", "كازاخستان"),
        ("UZ", "أوزبكستان"), ("TM", "تركمانستان"), ("TJ", "طاجيكستان"), ("KG", "قيرغيزستان"),
        ("AF", "أفغانستان"), ("AZ", "أذربيجان"), ("AM", "أرمينيا"), ("GE", "جورجيا"),
    ]),
    ("🌍 أفريقيا", [
        ("EG", "مصر"), ("LY", "ليبيا"), ("TN", "تونس"), ("DZ", "الجزائر"),
        ("MA", "المغرب"), ("SD", "السودان"), ("SS", "جنوب السودان"), ("ET", "إثيوبيا"),
        ("ER", "إريتريا"), ("DJ", "جيبوتي"), ("SO", "الصومال"), ("KE", "كينيا"),
        ("TZ", "تنزانيا"), ("UG", "أوغندا"), ("RW", "رواندا"), ("BI", "بوروندي"),
        ("NG", "نيجيريا"), ("GH", "غانا"), ("CI", "ساحل العاج"), ("SN", "السنغال"),
        ("ML", "مالي"), ("NE", "النيجر"), ("TD", "تشاد"), ("MR", "موريتانيا"),
        ("GM", "غامبيا"), ("GW", "غينيا بيساو"), ("GN", "غينيا"), ("SL", "سيراليون"),
        ("LR", "ليبيريا"), ("TG", "توغو"), ("BJ", "بنين"), ("BF", "بوركينا فاسو"),
        ("CM", "الكاميرون"), ("GA", "الغابون"), ("CG", "الكونغو برازافيل"), ("CD", "الكونغو الديمقراطية"),
        ("CF", "أفريقيا الوسطى"), ("GQ", "غينيا الاستوائية"), ("ST", "ساو تومي وبرينسيبي"), ("AO", "أنغولا"),
        ("ZM", "زامبيا"), ("ZW", "زيمبابوي"), ("MZ", "موزمبيق"), ("MW", "مالاوي"),
        ("NA", "ناميبيا"), ("BW", "بوتسوانا"), ("ZA", "جنوب أفريقيا"), ("SZ", "إسواتيني"),
        ("LS", "ليسوتو"), ("MG", "مدغشقر"), ("MU", "موريشيوس"), ("SC", "سيشل"),
        ("KM", "جزر القمر"), ("CV", "الرأس الأخضر"),
    ]),
    ("🌍 أوروبا", [
        ("GB", "المملكة المتحدة"), ("IE", "أيرلندا"), ("FR", "فرنسا"), ("DE", "ألمانيا"),
        ("NL", "هولندا"), ("BE", "بلجيكا"), ("LU", "لوكسمبورغ"), ("CH", "سويسرا"),
        ("AT", "النمسا"), ("ES", "إسبانيا"), ("PT", "البرتغال"), ("IT", "إيطاليا"),
        ("GR", "اليونان"), ("MT", "مالطا"), ("PL", "بولندا"), ("CZ", "التشيك"),
        ("SK", "سلوفاكيا"), ("HU", "المجر"), ("RO", "رومانيا"), ("BG", "بلغاريا"),
        ("HR", "كرواتيا"), ("SI", "سلوفينيا"), ("RS", "صربيا"), ("BA", "البوسنة والهرسك"),
        ("ME", "الجبل الأسود"), ("MK", "مقدونيا الشمالية"), ("AL", "ألبانيا"), ("UA", "أوكرانيا"),
        ("BY", "بيلاروسيا"), ("RU", "روسيا"), ("MD", "مولدوفا"), ("LT", "ليتوانيا"),
        ("LV", "لاتفيا"), ("EE", "إستونيا"), ("SE", "السويد"), ("NO", "النرويج"),
        ("DK", "الدنمارك"), ("FI", "فنلندا"), ("IS", "آيسلندا"), ("AD", "أندورا"),
        ("MC", "موناكو"), ("SM", "سان مارينو"), ("VA", "الفاتيكان"), ("LI", "ليختنشتاين"),
    ]),
    ("🌎 أمريكا الشمالية", [
        ("US", "الولايات المتحدة"), ("CA", "كندا"), ("MX", "المكسيك"), ("GT", "غواتيمالا"),
        ("BZ", "بليز"), ("HN", "هندوراس"), ("SV", "السلفادور"), ("NI", "نيكاراغوا"),
        ("CR", "كوستاريكا"), ("PA", "بنما"), ("CU", "كوبا"), ("JM", "جامايكا"),
        ("HT", "هايتي"), ("DO", "جمهورية الدومينيكان"), ("BS", "الباهاما"), ("BB", "باربادوس"),
        ("TT", "ترينيداد وتوباغو"), ("GD", "غرينادا"), ("LC", "سانت لوسيا"), ("VC", "سانت فنسنت والغرينادين"),
        ("AG", "أنتيغوا وباربودا"), ("DM", "دومينيكا"), ("KN", "سانت كيتس ونيفيس"),
    ]),
    ("🌎 أمريكا الجنوبية", [
        ("BR", "البرازيل"), ("AR", "الأرجنتين"), ("CL", "تشيلي"), ("CO", "كولومبيا"),
        ("PE", "بيرو"), ("VE", "فنزويلا"), ("EC", "الإكوادور"), ("BO", "بوليفيا"),
        ("PY", "باراغواي"), ("UY", "الأوروغواي"), ("GY", "غيانا"), ("SR", "سورينام"),
    ]),
    ("🌏 أوقيانوسيا", [
        ("AU", "أستراليا"), ("NZ", "نيوزيلندا"), ("PG", "بابوا غينيا الجديدة"), ("FJ", "فيجي"),
        ("SB", "جزر سليمان"), ("VU", "فانواتو"), ("WS", "ساموا"), ("TO", "تونغا"),
        ("KI", "كيريباتي"), ("FM", "ميكرونيسيا"), ("PW", "بالاو"), ("MH", "جزر مارشال"),
        ("NR", "ناورو"), ("TV", "توفالو"),
    ]),
]

COUNTRY_LOOKUP = {code: name for _, countries in COUNTRIES_BY_CONTINENT for code, name in countries}
COUNTRIES_PER_PAGE = 8

# ═══════════════════════════════════════════════════════════════
# STATE MACHINE
# ═══════════════════════════════════════════════════════════════

user_states = {}  # uid → state string
user_data = {}    # uid → dict of temporary data

WAIT_BTN_NAME = "WAIT_BTN_NAME"
WAIT_BTN_CONTENT = "WAIT_BTN_CONTENT"
WAIT_BROADCAST = "WAIT_BROADCAST"
WAIT_BAN = "WAIT_BAN"
WAIT_UNBAN = "WAIT_UNBAN"
WAIT_TEMP_BAN = "WAIT_TEMP_BAN"
WAIT_GIFT_NAME = "WAIT_GIFT_NAME"
WAIT_REF_NAME = "WAIT_REF_NAME"
WAIT_GIFTCODE_BTN_NAME = "WAIT_GIFTCODE_BTN_NAME"
WAIT_MYINFO_BTN_NAME = "WAIT_MYINFO_BTN_NAME"
WAIT_COUNTRY_GATE_TEXT = "WAIT_COUNTRY_GATE_TEXT"
WAIT_LANGUAGE_GATE_TEXT = "WAIT_LANGUAGE_GATE_TEXT"
WAIT_LANGUAGE_BTN_NAME = "WAIT_LANGUAGE_BTN_NAME"
WAIT_WELCOME_NAME = "WAIT_WELCOME_NAME"
WAIT_LOCK_POINTS = "WAIT_LOCK_POINTS"
WAIT_LOCK_DESC = "WAIT_LOCK_DESC"
WAIT_USER_LOOKUP = "WAIT_USER_LOOKUP"
WAIT_USER_POINTS_MODIFY = "WAIT_USER_POINTS_MODIFY"
WAIT_ENTER_GIFT_CODE = "WAIT_ENTER_GIFT_CODE"
WAIT_NEW_CODE_STR = "WAIT_NEW_CODE_STR"
WAIT_NEW_CODE_PTS = "WAIT_NEW_CODE_PTS"


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
# DATABASE (MongoDB Adapters)
# ═══════════════════════════════════════════════════════════════

DEFAULT_CONFIG = {
    "_id": "config",
    "buttons": [],
    "users": [],
    "banned_users": [],
    "gift_points": 2,
    "gift_name": "🎁 الهدية اليومية",
    "gift_active": True,
    "sub_active": True,
    "sub_channels": REQUIRED_CHANNELS.copy(),
    "ref_active": True,
    "ref_points": 2,
    "ref_name": "🔗 رابط الإحالة",
    "welcome_active": True,
    "welcome_points": 1,
    "welcome_name": "مكافأة التسجيل",
    "gift_codes": [],
    "broadcast_settings": {"pin": False, "silent": False},
    "gift_code_btn_name": "🎟️ كود هدية 🎁",
    "my_info_btn_name": "👤 معلوماتي",
    "gift_claim_text_template": "🎁 تهانينا! حصلت على {points} نقاط من ({gift_name})!\nرصيدك الحالي: {balance} نقطة 🌟",
    "ref_info_text_template": "رابط الدعوة ( {ref_link} )\n\nعدد دعوتك ( {my_invites} )\n\nافضل توب 5 بعدد دعوات\n{top_text}",
    "gift_code_prompt_text_template": "🎟️ **استبدال كود الهدية أو المسابقة:**\n\nأرسل الآن الكود الذي حصلت عليه في المسابقة لاستلام نقاطك فوراً:\n/cancel للإلغاء",
    "my_info_text_template": "👤 **معلوماتي:**\n\n👤 الاسم: {name}\n🆔 الآيدي: `{id}`\n🌟 نقاطك الحالية: {points}\n🏆 ترتيبك في قائمة الإحالات: المركز {rank} (بعدد {invites} دعوة)",
    "country_gate_active": True,
    "country_gate_points": 1,
    "country_gate_text": "🌍 **قبل ما نكمل...**\n\nحاب تختار دولتك أو مكان إقامتك؟ اختيارك اختياري تماماً، وإذا اخترت دولتك تحصل على نقطة إضافية 🎁\n\nاختر قارتك أولاً:",
    "language_gate_text": "🗣️ **اختر لغتك المفضلة للتعامل مع البوت:**\n\n(هذا الاختيار اختياري ويمكنك تخطيه)",
    "language_btn_name": "🗣️ لغة البوت"
}

FIXED_ITEMS = {
    "gift": {
        "label": "🎁 الهدية اليومية",
        "name_cb": "edit_gift_name",
        "text_key": "gift_claim_text_template",
        "placeholders": "{points} → عدد النقاط الممنوحة\n{gift_name} → اسم الخدمة\n{balance} → رصيد النقاط الحالي بعد الاستلام",
    },
    "ref": {
        "label": "🔗 رابط الإحالة",
        "name_cb": "edit_ref_name",
        "text_key": "ref_info_text_template",
        "placeholders": "{ref_link} → رابط دعوة المستخدم\n{my_invites} → عدد دعوات المستخدم\n{top_text} → قائمة أفضل 5 بالدعوات",
    },
    "giftcode": {
        "label": "🎟️ كود هدية",
        "name_cb": "edit_giftcode_btn_name",
        "text_key": "gift_code_prompt_text_template",
        "placeholders": "لا توجد متغيرات — هذا نص ثابت.",
    },
    "myinfo": {
        "label": "👤 معلوماتي",
        "name_cb": "edit_myinfo_btn_name",
        "text_key": "my_info_text_template",
        "placeholders": "{name} → اسم المستخدم\n{id} → آيدي المستخدم\n{points} → نقاطه الحالية\n{rank} → ترتيبه في الإحالات\n{invites} → عدد دعواته",
    },
    "country_gate": {
        "label": "🌍 شاشة اختيار الدولة",
        "name_cb": None,
        "text_key": "country_gate_text",
        "placeholders": "لا توجد متغيرات — هذا نص ثابت. يظهر هذا النص لأي مستخدم جديد قبل القائمة الرئيسية.",
    },
    "language_gate": {
        "label": "🗣️ شاشة اختيار اللغة",
        "name_cb": "edit_language_btn_name",
        "text_key": "language_gate_text",
        "placeholders": "لا توجد متغيرات — هذا نص ثابت. يظهر هذا النص بعد شاشة اختيار الدولة، وأيضاً عند الضغط على زر «لغة البوت» من القائمة الرئيسية.",
    },
}

def load_db():
    doc = config_collection.find_one({"_id": "config"})
    if not doc:
        config_collection.insert_one(DEFAULT_CONFIG.copy())
        doc = DEFAULT_CONFIG.copy()
    
    changed = False
    for k, v in DEFAULT_CONFIG.items():
        if k not in doc:
            doc[k] = v
            changed = True
    if changed:
        config_collection.update_one({"_id": "config"}, {"$set": doc})
    
    res = dict(doc)
    res.pop("_id", None)

    # ترحيل لمرة واحدة فقط: قديماً كان إيموجي الهدية/الإحالة مثبّتاً بالكود، الآن صار جزءاً
    # من الاسم نفسه (يقدر الأدمن يحذفه أو ينقله). هذا يمنع اختفاء الإيموجي من البوتات
    # الشغّالة أصلاً عند أول تشغيل لهذا التحديث، ولا يتكرر بعد ذلك.
    if not res.get("_gift_ref_emoji_migrated"):
        if not extract_leading_emoji(res.get("gift_name", "")):
            res["gift_name"] = f"🎁 {res.get('gift_name', 'الهدية اليومية')}".strip()
        if not extract_leading_emoji(res.get("ref_name", "")):
            res["ref_name"] = f"🔗 {res.get('ref_name', 'رابط الإحالة')}".strip()
        res["_gift_ref_emoji_migrated"] = True
        save_db(res)

    # يضمن أن لكل زر رقم ترتيب (order) ضمن إخوته، حتى الأزرار القديمة التي لا تملكه بعد
    order_counters = {}
    order_changed = False
    for b in res.get("buttons", []):
        pid = b.get("parent_id")
        if "order" not in b or not isinstance(b.get("order"), int):
            b["order"] = order_counters.get(pid, 0)
            order_changed = True
        order_counters[pid] = max(order_counters.get(pid, 0), b["order"] + 1)
    if order_changed:
        save_db(res)

    return res


def save_db(data):
    data_to_save = dict(data)
    data_to_save["_id"] = "config"
    config_collection.replace_one({"_id": "config"}, data_to_save, upsert=True)


def register_user(user_id):
    db = load_db()
    if user_id not in db["users"]:
        db["users"].append(user_id)
        save_db(db)


# ── Points system (MongoDB collection for users) ────────────────

def load_users():
    all_users = list(users_collection.find({}))
    users_dict = {}
    for u in all_users:
        uid = str(u["_id"])
        user_copy = dict(u)
        user_copy.pop("_id", None)
        users_dict[uid] = user_copy
    return {"users": users_dict}


def save_users(data):
    users_map = data.get("users", {})
    for uid_str, u_data in users_map.items():
        doc = dict(u_data)
        doc["_id"] = str(uid_str)
        users_collection.replace_one({"_id": str(uid_str)}, doc, upsert=True)


def get_user(user_id):
    """يجلب مستخدماً واحداً فقط من قاعدة البيانات (سريع، بدل تحميل كل المستخدمين)."""
    doc = users_collection.find_one({"_id": str(user_id)})
    if not doc:
        return None
    d = dict(doc)
    d.pop("_id", None)
    return d


def save_user(user_id, user_dict):
    """يحفظ مستخدماً واحداً فقط (سريع، بدل إعادة كتابة كل المستخدمين)."""
    doc = dict(user_dict)
    doc["_id"] = str(user_id)
    users_collection.replace_one({"_id": str(user_id)}, doc, upsert=True)


def register_user_points(user_id, name=""):
    uid = str(user_id)
    user_rec = get_user(uid)
    if not user_rec:
        save_user(uid, {
            "name": name,
            "points": 0,
            "unlocked": [],
            "referred_by": None,
            "referral_rewarded": False,
            "referrals_count": 0,
            "welcome_bonus_received": False,
            "country": None,
            "country_asked": False,
            "country_bonus_given": False,
            "language": None,
            "language_asked": False,
            "visits": 0
        })
    else:
        changed = False
        if name and user_rec.get("name") != name:
            user_rec["name"] = name
            changed = True
        for key, default in (
            ("points", 0), ("unlocked", []), ("referred_by", None),
            ("referral_rewarded", False), ("referrals_count", 0),
            ("welcome_bonus_received", False), ("country", None),
            ("country_asked", False), ("country_bonus_given", False),
            ("language", None), ("language_asked", False), ("visits", 0)
        ):
            if key not in user_rec:
                user_rec[key] = default
                changed = True
        if changed:
            save_user(uid, user_rec)


def process_start(user_obj, args):
    """
    يسجّل المستخدم ويطبّق مكافأة التسجيل والإحالة ويزيد عداد الزيارات،
    بأقل عدد ممكن من الاتصالات بقاعدة البيانات (بدل استدعاء عدة دوال منفصلة
    كل واحدة تُحمّل/تحفظ من جديد، وهو ما كان يسبب بطء استجابة /start).
    يرجع (db, user_rec, bonus_given).
    """
    uid_str = str(user_obj.id)
    name = f"{user_obj.first_name or ''} {user_obj.last_name or ''}".strip() or user_obj.username or ""

    db = load_db()
    user_rec = get_user(uid_str)
    is_new = user_rec is None or not user_rec.get("name")

    if not user_rec:
        user_rec = {
            "name": name, "points": 0, "unlocked": [], "referred_by": None,
            "referral_rewarded": False, "referrals_count": 0,
            "welcome_bonus_received": False, "country": None, "country_asked": False,
            "country_bonus_given": False, "language": None, "language_asked": False,
            "visits": 0
        }
    else:
        for key, default in (
            ("points", 0), ("unlocked", []), ("referred_by", None),
            ("referral_rewarded", False), ("referrals_count", 0),
            ("welcome_bonus_received", False), ("country", None),
            ("country_asked", False), ("country_bonus_given", False),
            ("language", None), ("language_asked", False), ("visits", 0)
        ):
            user_rec.setdefault(key, default)
        if name:
            user_rec["name"] = name

    if len(args) > 1 and args[1].startswith("ref_") and is_new:
        try:
            ref_id = int(args[1].replace("ref_", ""))
            if ref_id != user_obj.id:
                user_rec["referred_by"] = ref_id
        except Exception as e:
            logger.exception("Error parsing referral in start: %s", e)

    bonus_given = 0
    if db.get("welcome_active", True) and not user_rec.get("welcome_bonus_received", False):
        bonus_given = db.get("welcome_points", 1)
        user_rec["points"] = user_rec.get("points", 0) + bonus_given
        user_rec["welcome_bonus_received"] = True

    referrer_id = user_rec.get("referred_by")
    referrer_rec = None
    referrer_id_str = None
    if db.get("ref_active", True) and referrer_id and not user_rec.get("referral_rewarded", False):
        referrer_id_str = str(referrer_id)
        referrer_rec = get_user(referrer_id_str)
        if referrer_rec:
            ref_points = db.get("ref_points", 2)
            referrer_rec["points"] = referrer_rec.get("points", 0) + ref_points
            referrer_rec["referrals_count"] = referrer_rec.get("referrals_count", 0) + 1
            user_rec["referral_rewarded"] = True

    user_rec["visits"] = user_rec.get("visits", 0) + 1

    save_user(uid_str, user_rec)
    if referrer_rec:
        save_user(referrer_id_str, referrer_rec)

    if user_obj.id not in db.get("users", []):
        db.setdefault("users", []).append(user_obj.id)
        save_db(db)

    return db, user_rec, bonus_given


# ── Force-subscribe check ───────────────────────────────────────

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


def build_sub_markup(missing_channels):
    markup = types.InlineKeyboardMarkup()
    for ch in missing_channels:
        ch_clean = ch.replace("@", "")
        markup.add(
            types.InlineKeyboardButton(
                f"📢 اشترك في قناة {ch}", url=f"https://t.me/{ch_clean}"
            )
        )
    markup.add(
        types.InlineKeyboardButton(
            "✅ تحقق من الاشتراك", callback_data="sub_check"
        )
    )
    return markup


# ── Welcome Bonus Processor ─────────────────────────────────────

def process_welcome_bonus(user_id):
    db = load_db()
    if not db.get("welcome_active", True):
        return 0
    
    uid_str = str(user_id)
    user_rec = get_user(uid_str)
    
    if not user_rec:
        return 0
    
    if not user_rec.get("welcome_bonus_received", False):
        welcome_pts = db.get("welcome_points", 1)
        user_rec["points"] = user_rec.get("points", 0) + welcome_pts
        user_rec["welcome_bonus_received"] = True
        save_user(uid_str, user_rec)
        return welcome_pts
    return 0


# ── Referral Reward Processor ───────────────────────────────────

def process_referral_reward(user_id):
    db = load_db()
    if not db.get("ref_active", True):
        return
    
    uid_str = str(user_id)
    user_rec = get_user(uid_str)
    
    if not user_rec:
        return
    
    referrer_id = user_rec.get("referred_by")
    rewarded = user_rec.get("referral_rewarded", False)
    
    if referrer_id and not rewarded:
        ref_id_str = str(referrer_id)
        referrer_rec = get_user(ref_id_str)
        
        if referrer_rec:
            ref_points = db.get("ref_points", 2)
            referrer_rec["points"] = referrer_rec.get("points", 0) + ref_points
            referrer_rec["referrals_count"] = referrer_rec.get("referrals_count", 0) + 1
            user_rec["referral_rewarded"] = True
            save_user(ref_id_str, referrer_rec)
            save_user(uid_str, user_rec)
            
            ref_name = db.get("ref_name", "نظام الإحالة")
            try:
                bot.send_message(
                    int(referrer_id),
                    f"🎉 **مبروك!** دخل مستخدم جديد برقم تعريف (`{user_id}`) إلى البوت عبر رابط إحالتك واجتاز التحقق بنجاح.\n"
                    f"لقد حصلت على مكافأة قدرها **{ref_points}** نقطة من ({ref_name})! 🌟",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.exception("Failed to notify referrer %s: %s", referrer_id, e)


# ── Daily gift (Dynamic from DB) ────────────────────────────────

GIFT_INTERVAL = 86400  # 24 hours in seconds


def claim_daily_gift(user_id):
    uid = str(user_id)
    user = get_user(uid)
    db = load_db()
    
    if not user:
        return False, "⚠️ سجّل أولاً بإرسال /start"
    
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
    save_user(uid, user)
    
    gift_name = db.get("gift_name", "الهدية اليومية")
    template = db.get("gift_claim_text_template", DEFAULT_CONFIG["gift_claim_text_template"])
    try:
        msg_text = template.format(points=current_gift_points, gift_name=gift_name, balance=user['points'])
    except Exception:
        msg_text = DEFAULT_CONFIG["gift_claim_text_template"].format(points=current_gift_points, gift_name=gift_name, balance=user['points'])
    return True, msg_text


def get_button(db, btn_id):
    for btn in db["buttons"]:
        if btn.get("id") == btn_id:
            return btn
    return None


def get_children(db, parent_id):
    children = [b for b in db["buttons"] if b.get("parent_id") == parent_id]
    children.sort(key=lambda b: b.get("order", 0))
    return children


def collect_descendants(db, btn_id):
    result = set()
    for child in get_children(db, btn_id):
        result.add(child["id"])
        result.update(collect_descendants(db, child["id"]))
    return result


def new_id():
    return str(uuid.uuid4())[:8]


# ═══════════════════════════════════════════════════════════════
# CONTENT HELPERS (Updated to handle file captions/descriptions)
# ═══════════════════════════════════════════════════════════════

def extract_content(message):
    ct = message.content_type
    caption = message.caption if message.caption else ""
    if ct == "text":
        return "text", message.text.strip(), ""
    elif ct == "photo":
        return "photo", message.photo[-1].file_id, caption
    elif ct == "document":
        return "document", message.document.file_id, caption
    elif ct == "video":
        return "video", message.video.file_id, caption
    elif ct == "audio":
        return "audio", message.audio.file_id, caption
    elif ct == "voice":
        return "voice", message.voice.file_id, caption
    elif ct == "sticker":
        return "sticker", message.sticker.file_id, ""
    else:
        return "text", message.text or "", caption


def send_content(cid, btn, back_markup, lang="ar", db=None):
    ct = btn.get("content_type", "text")
    content, ch1 = localized_field(btn, "content", lang)
    caption, ch2 = localized_field(btn, "caption", lang)
    name, ch3 = localized_field(btn, "name", lang)
    if db is not None and (ch1 or ch2 or ch3):
        save_db(db)

    if not content:
        bot.send_message(
            cid, f"ℹ️ {name}\n\n{t('no_content_yet', lang)}", reply_markup=back_markup
        )
        return

    try:
        if ct == "text":
            bot.send_message(cid, content, reply_markup=back_markup)
        elif ct == "photo":
            bot.send_photo(cid, content, caption=caption if caption else None, reply_markup=back_markup)
        elif ct == "document":
            bot.send_document(cid, content, caption=caption if caption else None, reply_markup=back_markup)
        elif ct == "video":
            bot.send_video(cid, content, caption=caption if caption else None, reply_markup=back_markup)
        elif ct == "audio":
            bot.send_audio(cid, content, caption=caption if caption else None, reply_markup=back_markup)
        elif ct == "voice":
            bot.send_voice(cid, content, caption=caption if caption else None, reply_markup=back_markup)
        elif ct == "sticker":
            if caption:
                bot.send_message(cid, caption)
            bot.send_sticker(cid, content)
            bot.send_message(cid, "↩️", reply_markup=back_markup)
        else:
            bot.send_message(cid, content, reply_markup=back_markup)
    except Exception as e:
        try:
            if ct == "photo":
                bot.send_photo(cid, content, caption=caption if caption else None, reply_markup=back_markup)
            elif ct == "document":
                bot.send_document(cid, content, caption=caption if caption else None, reply_markup=back_markup)
            elif ct == "video":
                bot.send_video(cid, content, caption=caption if caption else None, reply_markup=back_markup)
            else:
                bot.send_message(cid, content, reply_markup=back_markup)
        except Exception as ex:
            report_admin_error(ex, "send_content")


def edit_or_replace(cid, mid, is_current_text, text, markup=None, parse_mode=None):
    """
    يعدّل الرسالة الحالية مكانها إذا كانت نصية (بدل إرسال رسالة جديدة).
    إذا تعذّر التعديل (مثلاً الرسالة الحالية صورة/ملف)، يحذف القديمة ثم يرسل الجديدة
    بحيث لا تتراكم الرسائل في المحادثة.
    """
    if is_current_text:
        try:
            bot.edit_message_text(text, cid, mid, reply_markup=markup, parse_mode=parse_mode)
            return
        except Exception:
            pass
    try:
        bot.delete_message(cid, mid)
    except Exception:
        pass
    bot.send_message(cid, text, reply_markup=markup, parse_mode=parse_mode)


def show_leaf_content(cid, mid, is_current_text, btn, back_markup, lang="ar", db=None):
    """
    يعرض محتوى زر نهائي (خدمة/ميزة بدون قوائم فرعية) مكان الرسالة الحالية، مترجماً
    تلقائياً حسب لغة المستخدم:
    - إذا كان المحتوى نصاً والرسالة الحالية نصية أيضاً: يعدّل الرسالة مكانها.
    - غير ذلك (تحويل من نص إلى صورة/ملف أو العكس): يحذف الرسالة القديمة ثم يرسل
      المحتوى الجديد، بحيث تبقى رسالة واحدة فقط بدل تراكم الرسائل.
    """
    ct = btn.get("content_type", "text")
    content, ch1 = localized_field(btn, "content", lang)
    name, ch2 = localized_field(btn, "name", lang)
    if db is not None and (ch1 or ch2):
        save_db(db)

    if ct == "text" and is_current_text:
        text = content if content else f"ℹ️ {name}\n\n{t('no_content_yet', lang)}"
        try:
            bot.edit_message_text(text, cid, mid, reply_markup=back_markup)
            return
        except Exception:
            pass

    try:
        bot.delete_message(cid, mid)
    except Exception:
        pass
    send_content(cid, btn, back_markup, lang=lang)


# ═══════════════════════════════════════════════════════════════
# NAVIGATION MARKUP
# ═══════════════════════════════════════════════════════════════

def build_nav_markup(db, parent_id=None, user_rec=None):
    children = get_children(db, parent_id)
    markup = types.InlineKeyboardMarkup()
    lang = (user_rec or {}).get("language") or "ar"
    needs_save = False

    if parent_id is None:
        # قائمة موحّدة بعمودين تجمع كل أزرار المستوى الرئيسي معاً (الأقسام/الخدمات + الأزرار الثابتة)
        gift_name, ch = localized_field(db, "gift_name", lang)
        needs_save = needs_save or ch
        ref_name, ch = localized_field(db, "ref_name", lang)
        needs_save = needs_save or ch
        gift_code_btn_name, ch = localized_field(db, "gift_code_btn_name", lang)
        needs_save = needs_save or ch
        my_info_btn_name, ch = localized_field(db, "my_info_btn_name", lang)
        needs_save = needs_save or ch
        language_btn_name, ch = localized_field(db, "language_btn_name", lang)
        needs_save = needs_save or ch

        items = []
        for btn in children:
            name, ch = localized_field(btn, "name", lang)
            needs_save = needs_save or ch
            is_locked = int(btn.get("unlock_points", 0)) > 0
            lock_icon = " 🔒" if is_locked else ""
            items.append((f"{name}{lock_icon}", f"nav_{btn['id']}"))

        items.append((gift_name, "gift_claim"))
        items.append((ref_name, "ref_link_info"))
        items.append((gift_code_btn_name, "gift_code_prompt"))
        items.append((my_info_btn_name, "my_info"))
        items.append((language_btn_name, "language_menu"))

        for i in range(0, len(items), 2):
            row = items[i:i + 2]
            markup.row(*[types.InlineKeyboardButton(text, callback_data=cb) for text, cb in row])

        if user_rec is not None:
            needs_country = db.get("country_gate_active", True) and user_rec.get("country") is None
            needs_language = user_rec.get("language") is None
            if needs_country or needs_language:
                markup.add(
                    types.InlineKeyboardButton("🔁 لم تختر دولتك/لغتك بعد؟ اضغط هنا", callback_data="redo_gate")
                )
    else:
        for i in range(0, len(children), 2):
            row_buttons = []
            for btn in children[i:i + 2]:
                name, ch = localized_field(btn, "name", lang)
                needs_save = needs_save or ch
                is_locked = int(btn.get("unlock_points", 0)) > 0
                lock_icon = " 🔒" if is_locked else ""
                row_buttons.append(
                    types.InlineKeyboardButton(f"{name}{lock_icon}", callback_data=f"nav_{btn['id']}")
                )
            markup.row(*row_buttons)

        parent = get_button(db, parent_id)
        back_to = parent.get("parent_id") if parent else None
        markup.add(
            types.InlineKeyboardButton(
                t("back", lang), callback_data=f"nav_back_{back_to if back_to else 'root'}"
            )
        )

    if needs_save:
        save_db(db)
    return markup


def render_main_menu(cid, mid, is_current_text, user_obj, prefix_text="", user_rec=None, db=None):
    """يعرض القائمة الرئيسية (بالتعديل مكان الرسالة الحالية إن وُجدت mid، وإلا برسالة جديدة)."""
    if db is None:
        db = load_db()
    if user_rec is None:
        user_rec = get_user(str(user_obj.id))
    lang = (user_rec or {}).get("language") or "ar"
    welcome_msg = (prefix_text + "\n" if prefix_text else "") + main_menu_welcome_text(user_obj, lang)
    markup = build_nav_markup(db, None, user_rec=user_rec)

    if mid:
        edit_or_replace(cid, mid, is_current_text, welcome_msg, markup=markup)
    else:
        bot.send_message(cid, welcome_msg, reply_markup=markup)


def render_country_gate(cid, mid, is_current_text, prefix_text="", db=None):
    """يعرض شاشة اختيار القارة (الخطوة الأولى من اختيار الدولة)."""
    if db is None:
        db = load_db()
    text = (prefix_text + "\n\n" if prefix_text else "") + db.get("country_gate_text", DEFAULT_CONFIG["country_gate_text"])
    markup = types.InlineKeyboardMarkup(row_width=2)
    labels = [label for label, _ in COUNTRIES_BY_CONTINENT]
    for i in range(0, len(labels), 2):
        row = labels[i:i + 2]
        markup.row(*[
            types.InlineKeyboardButton(row[j], callback_data=f"ccont_{labels.index(row[j])}")
            for j in range(len(row))
        ])
    markup.add(types.InlineKeyboardButton("⏭️ تخطي (بدون تحديد دولة)", callback_data="country_skip"))
    if mid:
        edit_or_replace(cid, mid, is_current_text, text, markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(cid, text, reply_markup=markup, parse_mode="Markdown")


def render_country_list(cid, mid, is_current_text, continent_index, page=0):
    """يعرض قائمة دول قارة معينة (مقسّمة على صفحات)."""
    label, countries = COUNTRIES_BY_CONTINENT[continent_index]
    start = page * COUNTRIES_PER_PAGE
    page_items = countries[start:start + COUNTRIES_PER_PAGE]
    total_pages = (len(countries) - 1) // COUNTRIES_PER_PAGE + 1

    markup = types.InlineKeyboardMarkup(row_width=2)
    for i in range(0, len(page_items), 2):
        row = page_items[i:i + 2]
        markup.row(*[
            types.InlineKeyboardButton(f"{flag(code)} {name}", callback_data=f"cpick_{code}")
            for code, name in row
        ])

    nav_row = []
    if page > 0:
        nav_row.append(types.InlineKeyboardButton("◀️ السابق", callback_data=f"cpage_{continent_index}_{page - 1}"))
    if start + COUNTRIES_PER_PAGE < len(countries):
        nav_row.append(types.InlineKeyboardButton("التالي ▶️", callback_data=f"cpage_{continent_index}_{page + 1}"))
    if nav_row:
        markup.row(*nav_row)

    markup.add(types.InlineKeyboardButton("🔙 رجوع لاختيار القارة", callback_data="cback"))
    markup.add(types.InlineKeyboardButton("⏭️ تخطي (بدون تحديد دولة)", callback_data="country_skip"))

    text = f"{label}\n\nصفحة {page + 1} من {total_pages} — اختر دولتك:"
    edit_or_replace(cid, mid, is_current_text, text, markup=markup)


def render_language_gate(cid, mid, is_current_text, prefix_text="", db=None):
    """يعرض شاشة اختيار اللغة (الخطوة الأخيرة قبل القائمة الرئيسية)."""
    if db is None:
        db = load_db()
    text = (prefix_text + "\n\n" if prefix_text else "") + db.get("language_gate_text", DEFAULT_CONFIG["language_gate_text"])
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
    )
    markup.add(types.InlineKeyboardButton("⏭️ تخطي", callback_data="lang_skip"))
    if mid:
        edit_or_replace(cid, mid, is_current_text, text, markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(cid, text, reply_markup=markup, parse_mode="Markdown")


def enter_bot_gate(cid, mid, is_current_text, user_obj, prefix_text="", db=None, user_rec=None):
    """
    يقرر الشاشة التالية بعد التسجيل/التحقق من الاشتراك:
    شاشة اختيار الدولة (إن لم تُعرض من قبل)، ثم شاشة اللغة، ثم القائمة الرئيسية.
    mid=None يعني إرسال رسالة جديدة، وإلا يُعدَّل مكان الرسالة الحالية.
    يقبل db/user_rec جاهزَين (إن توفّرا) لتفادي إعادة استعلام قاعدة البيانات.
    """
    if db is None:
        db = load_db()
    uid_str = str(user_obj.id)
    if user_rec is None:
        user_rec = get_user(uid_str) or {}

    if db.get("country_gate_active", True) and not user_rec.get("country_asked"):
        render_country_gate(cid, mid, is_current_text, prefix_text, db=db)
    elif not user_rec.get("language_asked"):
        render_language_gate(cid, mid, is_current_text, prefix_text, db=db)
    else:
        render_main_menu(cid, mid, is_current_text, user_obj, prefix_text, user_rec=user_rec, db=db)


def back_only_markup(btn):
    parent_id = btn.get("parent_id")
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "🔙 رجوع", callback_data=f"nav_back_{parent_id if parent_id else 'root'}"
        )
    )
    return markup


# ═══════════════════════════════════════════════════════════════
# ADMIN SETTINGS HIERARCHICAL NAVIGATOR
# ═══════════════════════════════════════════════════════════════

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
        markup.add(types.InlineKeyboardButton("✏️ تعديل نصوص أزرار القائمة الرئيسية الثابتة", callback_data="adm_fixed_texts"))
        markup.add(types.InlineKeyboardButton("🔙 رجوع لوحة التحكم", callback_data="adm_back_main"))
    return markup


def render_button_management_screen(cid, mid, btn_id):
    """
    يعرض شاشة إدارة زر/خدمة محدد (تعديل، تصفح الفرعيات، تغيير الترتيب).
    يُستخدم عند الضغط على الزر من القائمة، وأيضاً بعد تغيير ترتيبه لإعادة عرض
    الشاشة نفسها محدّثة. يعيد True عند النجاح و False إن لم يعد الزر موجوداً.
    """
    db = load_db()
    btn = get_button(db, btn_id)
    if not btn:
        return False

    children = get_children(db, btn_id)
    siblings = get_children(db, btn.get("parent_id"))
    position = next((i for i, b in enumerate(siblings) if b["id"] == btn_id), 0)

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("⚙️ تعديل اسم، محتوى أو إعدادات هذا الزر", callback_data=f"adm_edit_{btn_id}")
    )
    if children:
        markup.add(
            types.InlineKeyboardButton(f"📂 استعراض الأزرار الفرعية بداخله ({len(children)})", callback_data=f"adm_set_subnav_{btn_id}")
        )

    move_row = []
    if position > 0:
        move_row.append(types.InlineKeyboardButton("⬆️ نقل لأعلى", callback_data=f"adm_move_up_{btn_id}"))
    if position < len(siblings) - 1:
        move_row.append(types.InlineKeyboardButton("⬇️ نقل لأسفل", callback_data=f"adm_move_down_{btn_id}"))
    if move_row:
        markup.row(*move_row)

    markup.add(
        types.InlineKeyboardButton("🔙 رجوع للقائمة السابقة", callback_data=f"adm_set_back_{btn.get('parent_id') if btn.get('parent_id') else 'root'}")
    )

    bot.edit_message_text(
        f"🎛 **إدارة العنصر:** «{btn['name']}»\n\n"
        f"• النوع: {'قسم رئيسي/فرعي يحتوي على أزرار' if children else 'خدمة / زر نهائي'}\n"
        f"• عدد الأزرار الفرعية: {len(children)}\n"
        f"• ترتيبه الحالي في القائمة الرئيسية بين إخوته: {position + 1} من {len(siblings)}\n\n"
        f"اختر الإجراء المطلوب:",
        cid, mid, reply_markup=markup, parse_mode="Markdown"
    )
    return True


# ═══════════════════════════════════════════════════════════════
# /start
# ═══════════════════════════════════════════════════════════════

@bot.message_handler(commands=["start"])
def start(message):
    logger.info("Bot received start command from %s", message.from_user.id)
    clear_state(message.from_user.id)
    u = message.from_user
    args = message.text.split()

    if u.id != ADMIN_ID:
        missing = check_subscription(u.id)
        if missing:
            markup = build_sub_markup(missing)
            bot.send_message(
                message.chat.id,
                "⚠️ يجب عليك الاشتراك في قنواتنا لاستخدام البوت.\n"
                "اشترك في القنوات أدناه ثم اضغط زر التحقق:",
                reply_markup=markup,
            )
            return

    db, user_rec, bonus_given = process_start(u, args)

    prefix_text = ""
    if bonus_given > 0:
        prefix_text = f"🎉 أهلاً بك {get_display_name(u)}! لقد حصلت على هدية التسجيل لأول مرة ({bonus_given} نقطة)."

    enter_bot_gate(message.chat.id, None, False, u, prefix_text, db=db, user_rec=user_rec)


# ═══════════════════════════════════════════════════════════════
# /admin
# ═══════════════════════════════════════════════════════════════

ADMIN_PANEL_BUTTONS = [
    ("⚙️ إعدادات الخدمات والأزرار", "adm_settings_list"),
    ("🔒 قفل الخدمات بنقاط", "adm_lock_menu"),
    ("➕ إضافة زر", "adm_add"),
    ("🗑 حذف زر", "adm_delete"),
    ("🎁 إعدادات الهدية اليومية", "adm_feat_gift"),
    ("⭐ إعدادات مكافأة التسجيل", "adm_feat_welcome"),
    ("🎟️ إدارة أكواد الهدايا والمسابقات", "adm_gift_codes_menu"),
    ("🔗 إعدادات ميزة الإحالات", "adm_feat_ref"),
    ("🛡 إدارة الاشتراك الإجباري", "adm_feat_sub"),
    ("👥 إدارة المستخدمين", "adm_users"),
    ("📊 إحصائيات البوت", "adm_stats"),
    ("📣 إرسال إعلان والإعدادات", "adm_broadcast_menu"),
]


def admin_menu_markup():
    markup = types.InlineKeyboardMarkup()
    for i in range(0, len(ADMIN_PANEL_BUTTONS), 2):
        row = ADMIN_PANEL_BUTTONS[i:i + 2]
        markup.row(*[types.InlineKeyboardButton(text, callback_data=cb) for text, cb in row])
    return markup


def admin_panel_text():
    return f"👋 أهلاً بك في لوحة التحكم\nعدد الأزرار: {len(ADMIN_PANEL_BUTTONS)}"

@bot.message_handler(commands=["admin"])
def admin(message):
    if message.from_user.id != ADMIN_ID:
        return
    clear_state(message.from_user.id)
    bot.send_message(
        message.chat.id,
        admin_panel_text(),
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


# ═══════════════════════════════════════════════════════════════
# CALLBACK HANDLER
# ═══════════════════════════════════════════════════════════════

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    bot.answer_callback_query(call.id)
    try:
        data = call.data
        uid = call.from_user.id
        cid = call.message.chat.id
        mid = call.message.message_id

        # ── إعدادات وتفضيلات إرسال الإعلان المحدثة والمطورة ──
        if data == "adm_broadcast_menu":
            db = load_db()
            b_settings = db.get("broadcast_settings", {"pin": False, "silent": False})
            pin_st = "مفعل 📌" if b_settings.get("pin") else "معطل ❌"
            silent_st = "مفعل 🔕" if b_settings.get("silent") else "معطل 🔔"
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("📣 بدء إرسال الإعلان الآن", callback_data="adm_start_broadcast"))
            markup.add(
                types.InlineKeyboardButton(f"📌 تثبيت الإعلان: {pin_st}", callback_data="toggle_broadcast_pin"),
                types.InlineKeyboardButton(f"🔕 الإرسال بدون إشعار: {silent_st}", callback_data="toggle_broadcast_silent")
            )
            markup.add(types.InlineKeyboardButton("🔙 رجوع لوحة التحكم", callback_data="adm_back_main"))
            
            bot.edit_message_text(
                f"📣 **إدارة وإعدادات إرسال الإعلان:**\n\n"
                f"• خيار التثبيت لدى المستخدمين: `{pin_st}`\n"
                f"• الإرسال بدون إشعار صوتي: `{silent_st}`\n\n"
                f"اختر الإجراء المطلوب:",
                cid, mid, reply_markup=markup, parse_mode="Markdown"
            )
            return

        elif data == "toggle_broadcast_pin":
            db = load_db()
            b_settings = db.setdefault("broadcast_settings", {"pin": False, "silent": False})
            b_settings["pin"] = not b_settings.get("pin", False)
            save_db(db)
            bot.answer_callback_query(call.id, "✅ تم تغيير إعداد التثبيت بنجاح!")
            pin_st = "مفعل 📌" if b_settings["pin"] else "معطل ❌"
            silent_st = "مفعل 🔕" if b_settings.get("silent") else "معطل 🔔"
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("📣 بدء إرسال الإعلان الآن", callback_data="adm_start_broadcast"))
            markup.add(
                types.InlineKeyboardButton(f"📌 تثبيت الإعلان: {pin_st}", callback_data="toggle_broadcast_pin"),
                types.InlineKeyboardButton(f"🔕 الإرسال بدون إشعار: {silent_st}", callback_data="toggle_broadcast_silent")
            )
            markup.add(types.InlineKeyboardButton("🔙 رجوع لوحة التحكم", callback_data="adm_back_main"))
            bot.edit_message_text(
                f"📣 **إدارة وإعدادات إرسال الإعلان:**\n\n"
                f"• خيار التثبيت لدى المستخدمين: `{pin_st}`\n"
                f"• الإرسال بدون إشعار صوتي: `{silent_st}`\n\n"
                f"اختر الإجراء المطلوب:",
                cid, mid, reply_markup=markup, parse_mode="Markdown"
            )
            return

        elif data == "toggle_broadcast_silent":
            db = load_db()
            b_settings = db.setdefault("broadcast_settings", {"pin": False, "silent": False})
            b_settings["silent"] = not b_settings.get("silent", False)
            save_db(db)
            bot.answer_callback_query(call.id, "✅ تم تغيير إعداد الإشعار الصوتي بنجاح!")
            pin_st = "مفعل 📌" if b_settings.get("pin") else "معطل ❌"
            silent_st = "مفعل 🔕" if b_settings["silent"] else "معطل 🔔"
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("📣 بدء إرسال الإعلان الآن", callback_data="adm_start_broadcast"))
            markup.add(
                types.InlineKeyboardButton(f"📌 تثبيت الإعلان: {pin_st}", callback_data="toggle_broadcast_pin"),
                types.InlineKeyboardButton(f"🔕 الإرسال بدون إشعار: {silent_st}", callback_data="toggle_broadcast_silent")
            )
            markup.add(types.InlineKeyboardButton("🔙 رجوع لوحة التحكم", callback_data="adm_back_main"))
            bot.edit_message_text(
                f"📣 **إدارة وإعدادات إرسال الإعلان:**\n\n"
                f"• خيار التثبيت لدى المستخدمين: `{pin_st}`\n"
                f"• الإرسال بدون إشعار صوتي: `{silent_st}`\n\n"
                f"اختر الإجراء المطلوب:",
                cid, mid, reply_markup=markup, parse_mode="Markdown"
            )
            return

        elif data == "adm_start_broadcast":
            db = load_db()
            set_state(uid, WAIT_BROADCAST)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء البث", callback_data="adm_broadcast_menu"))
            bot.edit_message_text(
                f"📣 **أرسل الآن رسالة الإعلان للبث إلى جميع المستخدمين ({len(db['users'])} مستخدم):**\n\n"
                f"(يمكنك إرسال نص، صورة، فيديو، ملف، صوت... وسيتم تطبيق إعدادات التثبيت والإشعار الحالية)\n\n/cancel للإلغاء",
                cid, mid, reply_markup=markup, parse_mode="Markdown"
            )
            return

        # ── إدارة أكواد الهدايا والمسابقات ──
        if data == "adm_gift_codes_menu":
            db = load_db()
            codes = db.get("gift_codes", [])
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("➕ إنشاء كود جديد", callback_data="adm_add_gift_code"),
                types.InlineKeyboardButton("📋 عرض الأكواد النشطة", callback_data="adm_list_gift_codes")
            )
            markup.add(types.InlineKeyboardButton("🗑️ حذف كود محدد", callback_data="adm_del_gift_code_prompt"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع لوحة التحكم", callback_data="adm_back_main"))
            bot.edit_message_text(
                f"🎟️ **إدارة أكواد الهدايا والمسابقات:**\n\n"
                f"• إجمالي الأكواد الحالية: `{len(codes)}` كود\n\n"
                f"اختر العملية المطلوبة:",
                cid, mid, reply_markup=markup, parse_mode="Markdown"
            )
            return

        elif data == "adm_add_gift_code":
            set_state(uid, WAIT_NEW_CODE_STR)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="adm_gift_codes_menu"))
            bot.edit_message_text(
                "🎟️ **إنشاء كود هدية جديد:**\n\n"
                "أرسل الآن **صيغة الكود** (مثال: `WINNER2026` أو `RAMADAN10`):\n/cancel للإلغاء",
                cid, mid, reply_markup=markup, parse_mode="Markdown"
            )
            return

        elif data == "adm_list_gift_codes":
            db = load_db()
            codes = db.get("gift_codes", [])
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_gift_codes_menu"))
            if not codes:
                bot.edit_message_text("📋 لا توجد أي أكواد هدايا أو مسابقات نشطة حالياً.", cid, mid, reply_markup=markup)
            else:
                lines = [f"• الكود: `{c['code']}` | النقاط: **{c['points']}** نقطة" for c in codes]
                bot.edit_message_text(
                    f"📋 **قائمة الأكواد النشطة حالياً ({len(codes)}):**\n\n" + "\n".join(lines),
                    cid, mid, reply_markup=markup, parse_mode="Markdown"
                )
            return

        elif data == "adm_del_gift_code_prompt":
            db = load_db()
            codes = db.get("gift_codes", [])
            markup = types.InlineKeyboardMarkup()
            if not codes:
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_gift_codes_menu"))
                bot.edit_message_text("📋 لا توجد أكواد لحذفها.", cid, mid, reply_markup=markup)
                return
            for c in codes:
                markup.add(types.InlineKeyboardButton(f"🗑️ حذف الكود: {c['code']} ({c['points']} نقطة)", callback_data=f"del_gcode_{c['code']}"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_gift_codes_menu"))
            bot.edit_message_text("اختر الكود المراد حذفه نهائياً:", cid, mid, reply_markup=markup)
            return

        elif data.startswith("del_gcode_"):
            target_code = data.replace("del_gcode_", "")
            db = load_db()
            codes = db.get("gift_codes", [])
            db["gift_codes"] = [c for c in codes if c["code"] != target_code]
            save_db(db)
            bot.answer_callback_query(call.id, f"✅ تم حذف الكود ({target_code}) بنجاح!", show_alert=True)
            
            codes_new = db["gift_codes"]
            markup = types.InlineKeyboardMarkup()
            if not codes_new:
                markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_gift_codes_menu"))
                bot.edit_message_text("📋 لا توجد أكواد أخرى.", cid, mid, reply_markup=markup)
                return
            for c in codes_new:
                markup.add(types.InlineKeyboardButton(f"🗑️ حذف الكود: {c['code']} ({c['points']} نقطة)", callback_data=f"del_gcode_{c['code']}"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_gift_codes_menu"))
            bot.edit_message_text("اختر كوداً آخر لحذفه أو ارجع:", cid, mid, reply_markup=markup)
            return

        elif data == "gift_code_prompt":
            set_state(uid, WAIT_ENTER_GIFT_CODE)
            lang = (get_user(str(uid)) or {}).get("language") or "ar"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء" if lang == "ar" else "🔙 Cancel", callback_data="nav_back_root"))
            db_local = load_db()
            if "gift_code_prompt_text_template" not in db_local:
                db_local["gift_code_prompt_text_template"] = DEFAULT_CONFIG["gift_code_prompt_text_template"]
            prompt_text, ch = localized_field(db_local, "gift_code_prompt_text_template", lang)
            if ch:
                save_db(db_local)
            edit_or_replace(
                cid, mid, call.message.content_type == "text",
                prompt_text,
                markup=markup,
                parse_mode="Markdown",
            )
            return

        # ── إحصائيات البوت الشاملة ──
        if data == "adm_stats":
            db = load_db()
            users_data = load_users()
            total_users = len(db.get("users", []))
            banned_count = len(db.get("banned_users", []))
            buttons_count = len(db.get("buttons", []))
            total_points_all = sum(u.get("points", 0) for u in users_data.get("users", {}).values())
            
            stats_text = (
                f"📊 **إحصائيات البوت الشاملة:**\n\n"
                f"👥 إجمالي المستخدمين المسجلين: `{total_users}`\n"
                f"🚫 عدد المستخدمين المحظورين: `{banned_count}`\n"
                f"🗂 إجمالي الخدمات والأزرار: `{buttons_count}`\n"
                f"💎 إجمالي النقاط الموزعة لدى المستخدمين: `{total_points_all}` نقطة\n\n"
                f"⚙️ **حالة الأنظمة:**\n"
                f"• الهدية اليومية: {'مفعلة ✅' if db.get('gift_active', True) else 'معطلة ❌'}\n"
                f"• مكافأة التسجيل: {'مفعلة ✅' if db.get('welcome_active', True) else 'معطلة ❌'}\n"
                f"• نظام الإحالات: {'مفعل ✅' if db.get('ref_active', True) else 'معطل ❌'}\n"
                f"• الاشتراك الإجباري: {'مفعل ✅' if db.get('sub_active', True) else 'معطل ❌'}"
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 رجوع لوحة التحكم", callback_data="adm_back_main"))
            bot.edit_message_text(stats_text, cid, mid, reply_markup=markup, parse_mode="Markdown")
            return

        if data == "adm_settings_list" or data == "admin_buttons_list":
            db = load_db()
            markup = build_admin_settings_markup(db, None)
            bot.edit_message_text(
                "⚙️ **إعدادات الخدمات والأزرار:**\n\n"
                "اختر القسم الرئيسي أو الزر الذي تريد إدارته وتعديله (يمكنك التصفح داخل الأقسام والأزرار الفرعية بكل عمق):",
                cid, mid, reply_markup=markup, parse_mode="Markdown"
            )
            return

        if data == "adm_fixed_texts":
            markup = types.InlineKeyboardMarkup(row_width=1)
            for key, item in FIXED_ITEMS.items():
                markup.add(types.InlineKeyboardButton(item["label"], callback_data=f"adm_fixed_item_{key}"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_settings_list"))

            bot.edit_message_text(
                "✏️ **إدارة أزرار القائمة الرئيسية الثابتة:**\n\n"
                "هذه الأزرار (الهدية، الإحالة، كود الهدية، معلوماتي) ثابتة دائماً في القائمة الرئيسية "
                "بجانب الخدمات التي تضيفها بنفسك. اختر الزر الذي تريد إدارته:",
                cid, mid, reply_markup=markup, parse_mode="Markdown"
            )
            return

        if data.startswith("adm_fixed_item_"):
            key = data[len("adm_fixed_item_"):]
            item = FIXED_ITEMS.get(key)
            if not item:
                bot.answer_callback_query(call.id, "⚠️ هذا العنصر غير موجود.", show_alert=True)
                return
            markup = types.InlineKeyboardMarkup(row_width=1)
            if item.get("name_cb"):
                markup.add(types.InlineKeyboardButton("📝 تعديل اسم الزر (كما يظهر في القائمة)", callback_data=item["name_cb"]))
            markup.add(types.InlineKeyboardButton("📄 تعديل النص الذي يظهر عند الضغط عليه", callback_data=f"adm_fixed_text_{key}"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_fixed_texts"))
            bot.edit_message_text(
                f"⚙️ **إدارة زر:** «{item['label']}»\n\nاختر ما تريد تعديله:",
                cid, mid, reply_markup=markup, parse_mode="Markdown"
            )
            return

        if data.startswith("adm_fixed_text_"):
            key = data[len("adm_fixed_text_"):]
            item = FIXED_ITEMS.get(key)
            if not item:
                bot.answer_callback_query(call.id, "⚠️ هذا العنصر غير موجود.", show_alert=True)
                return
            set_state(uid, "WAIT_FIXED_TEXT_EDIT", config_key=item["text_key"], back_key=key)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data=f"adm_fixed_item_{key}"))
            current_text = load_db().get(item["text_key"], "")
            try:
                bot.delete_message(cid, mid)
            except Exception:
                pass
            bot.send_message(
                cid,
                f"✍️ أرسل الآن النص الجديد لـ «{item['label']}».\n\n"
                f"📌 المتغيرات المتاحة (اختياري استخدامها داخل النص):\n{item['placeholders']}\n\n"
                f"📄 النص الحالي:\n{current_text}",
                reply_markup=markup
            )
            return

        if data == "edit_giftcode_btn_name":
            set_state(uid, WAIT_GIFTCODE_BTN_NAME)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="adm_fixed_texts"))
            try:
                bot.delete_message(cid, mid)
            except Exception:
                pass
            bot.send_message(cid, "✍️ أرسل الآن النص الجديد لزر «كود هدية» في القائمة الرئيسية:", reply_markup=markup)
            return

        if data == "edit_myinfo_btn_name":
            set_state(uid, WAIT_MYINFO_BTN_NAME)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="adm_fixed_texts"))
            try:
                bot.delete_message(cid, mid)
            except Exception:
                pass
            bot.send_message(cid, "✍️ أرسل الآن النص الجديد لزر «معلوماتي» في القائمة الرئيسية:", reply_markup=markup)
            return

        if data == "edit_language_btn_name":
            set_state(uid, WAIT_LANGUAGE_BTN_NAME)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="adm_fixed_texts"))
            try:
                bot.delete_message(cid, mid)
            except Exception:
                pass
            bot.send_message(cid, "✍️ أرسل الآن النص الجديد لزر «لغة البوت» في القائمة الرئيسية:", reply_markup=markup)
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
            if not render_button_management_screen(cid, mid, btn_id):
                bot.answer_callback_query(call.id, "⚠️ هذا العنصر غير موجود.", show_alert=True)
            return

        if data.startswith("adm_move_up_") or data.startswith("adm_move_down_"):
            direction_up = data.startswith("adm_move_up_")
            btn_id = data[len("adm_move_up_"):] if direction_up else data[len("adm_move_down_"):]
            db = load_db()
            btn = get_button(db, btn_id)
            if not btn:
                bot.answer_callback_query(call.id, "⚠️ هذا العنصر غير موجود.", show_alert=True)
                return

            siblings = get_children(db, btn.get("parent_id"))
            position = next((i for i, b in enumerate(siblings) if b["id"] == btn_id), None)
            swap_pos = position - 1 if direction_up else position + 1

            if position is None or swap_pos < 0 or swap_pos >= len(siblings):
                bot.answer_callback_query(call.id, "⚠️ لا يمكن نقل هذا الزر أكثر في هذا الاتجاه.", show_alert=True)
                return

            other = siblings[swap_pos]
            this_order = btn.get("order", position)
            other_order = other.get("order", swap_pos)
            for b in db["buttons"]:
                if b["id"] == btn_id:
                    b["order"] = other_order
                elif b["id"] == other["id"]:
                    b["order"] = this_order
            save_db(db)

            render_button_management_screen(cid, mid, btn_id)
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
                f"⚙️ إعدادات الهدية اليومية المتقدمة:\n\n• اسم الخدمة: {gift_name}\n• الحالة: مفعلة ✅\n• النقاط الحالية: {current_points}\n\nاختر ما تريد تعديله:", 
                cid, mid, reply_markup=markup
            )
            return

        if data == "show_gift_points":
            db = load_db()
            pts = db.get("gift_points", 2)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_feat_gift"))
            bot.edit_message_text(f"🎁 عدد النقاط الحالي الممنوح في الهدية اليومية هو: **{pts}** نقطة.", cid, mid, reply_markup=markup, parse_mode="Markdown")
            return

        if data == "edit_gift_points_val":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="adm_feat_gift"))
            msg = bot.edit_message_text("✍️ أرسل الآن عدد النقاط الجديد (برقم صحيح):", cid, mid, reply_markup=markup)
            bot.register_next_step_handler(msg, save_new_gift_points)
            return
        
        if data == "edit_gift_name":
            set_state(uid, WAIT_GIFT_NAME)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="adm_feat_gift"))
            try:
                bot.delete_message(cid, mid)
            except Exception:
                pass
            bot.send_message(cid, "✍️ أرسل الآن اسم الخدمة الجديد للهدية اليومية:", reply_markup=markup)
            return

        if data == "adm_feat_welcome":
            db = load_db()
            wel_pts = db.get("welcome_points", 1)
            wel_name = db.get("welcome_name", "مكافأة التسجيل")
            wel_st = "مفعل ✅" if db.get("welcome_active", True) else "معطل ❌"
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("✏️ تعديل عدد نقاط التسجيل", callback_data="edit_welcome_points_val"),
                types.InlineKeyboardButton("👁 معرفة النقاط الحالية", callback_data="show_welcome_points")
            )
            markup.add(
                types.InlineKeyboardButton("📝 تغيير اسم الخدمة", callback_data="edit_welcome_name"),
                types.InlineKeyboardButton("🔄 تفعيل/إيقاف الخدمة", callback_data="toggle_welcome_status")
            )
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_back_main"))
            bot.edit_message_text(
                f"⚙️ إعدادات مكافأة التسجيل لأول مرة:\n\n"
                f"• اسم الخدمة: {wel_name}\n"
                f"• الحالة: {wel_st}\n"
                f"• النقاط لكل مستخدم جديد: {wel_pts}\n\n"
                f"اختر ما تريد تعديله:", 
                cid, mid, reply_markup=markup
            )
            return

        if data == "show_welcome_points":
            db = load_db()
            pts = db.get("welcome_points", 1)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_feat_welcome"))
            bot.edit_message_text(f"⭐ عدد النقاط الممنوح للمستخدم الجديد عند التسجيل لأول مرة هو: **{pts}** نقطة.", cid, mid, reply_markup=markup, parse_mode="Markdown")
            return

        if data == "edit_welcome_points_val":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="adm_feat_welcome"))
            msg = bot.edit_message_text("✍️ أرسل الآن عدد نقاط مكافأة التسجيل الجديد (برقم صحيح):", cid, mid, reply_markup=markup)
            bot.register_next_step_handler(msg, save_new_welcome_points)
            return

        if data == "edit_welcome_name":
            set_state(uid, WAIT_WELCOME_NAME)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="adm_feat_welcome"))
            try:
                bot.delete_message(cid, mid)
            except Exception:
                pass
            bot.send_message(cid, "✍️ أرسل الآن اسم الخدمة الجديد لمكافأة التسجيل:", reply_markup=markup)
            return

        if data == "toggle_welcome_status":
            db = load_db()
            current_status = db.get("welcome_active", True)
            db["welcome_active"] = not current_status
            save_db(db)
            status_text = "مفعلة ✅" if db["welcome_active"] else "معطلة ❌"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_feat_welcome"))
            bot.edit_message_text(f"🔄 تم تغيير حالة مكافأة التسجيل بنجاح!\nالحالة الحالية الآن: {status_text}", cid, mid, reply_markup=markup)
            return

        if data == "adm_feat_ref":
            db = load_db()
            ref_pts = db.get("ref_points", 2)
            ref_name = db.get("ref_name", "نظام الإحالة")
            ref_st = "مفعل ✅" if db.get("ref_active", True) else "معطل ❌"
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("✏️ تعديل عدد نقاط الإحالة", callback_data="edit_ref_points_val"),
                types.InlineKeyboardButton("👁 معرفة النقاط الحالية", callback_data="show_ref_points")
            )
            markup.add(
                types.InlineKeyboardButton("📝 تغيير اسم الخدمة", callback_data="edit_ref_name"),
                types.InlineKeyboardButton("🔄 تفعيل/إيقاف الخدمة", callback_data="toggle_ref_status")
            )
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_back_main"))
            bot.edit_message_text(
                f"⚙️ إعدادات ميزة الإحالات المتقدمة:\n\n"
                f"• اسم الخدمة: {ref_name}\n"
                f"• الحالة: {ref_st}\n"
                f"• النقاط لكل إحالة: {ref_pts}\n\n"
                f"اختر ما تريد تعديله:", 
                cid, mid, reply_markup=markup
            )
            return

        if data == "show_ref_points":
            db = load_db()
            pts = db.get("ref_points", 2)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_feat_ref"))
            bot.edit_message_text(f"🔗 عدد النقاط الممنوح لكل إحالة ناجحة هو: **{pts}** نقطة.", cid, mid, reply_markup=markup, parse_mode="Markdown")
            return

        if data == "edit_ref_points_val":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="adm_feat_ref"))
            msg = bot.edit_message_text("✍️ أرسل الآن عدد نقاط الإحالة الجديد (برقم صحيح):", cid, mid, reply_markup=markup)
            bot.register_next_step_handler(msg, save_new_ref_points)
            return
        
        if data == "edit_ref_name":
            set_state(uid, WAIT_REF_NAME)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="adm_feat_ref"))
            try:
                bot.delete_message(cid, mid)
            except Exception:
                pass
            bot.send_message(cid, "✍️ أرسل الآن اسم الخدمة الجديد لميزة الإحالات:", reply_markup=markup)
            return

        if data == "toggle_ref_status":
            db = load_db()
            current_status = db.get("ref_active", True)
            db["ref_active"] = not current_status
            save_db(db)
            status_text = "مفعلة ✅" if db["ref_active"] else "معطلة ❌"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_feat_ref"))
            bot.edit_message_text(f"🔄 تم تغيير حالة ميزة الإحالة بنجاح!\nالحالة الحالية الآن: {status_text}", cid, mid, reply_markup=markup)
            return

        if data == "ref_link_info":
            lang = (get_user(str(uid)) or {}).get("language") or "ar"
            try:
                bot_username = bot.get_me().username
            except Exception:
                bot_username = "Bot"
            ref_link = f"https://t.me/{bot_username}?start=ref_{uid}"
            
            users_data = load_users()
            uid_str = str(uid)
            user_rec = users_data["users"].get(uid_str, {})
            my_invites = user_rec.get("referrals_count", 0)
            
            all_users = users_data.get("users", {})
            sorted_users = sorted(
                all_users.items(), 
                key=lambda item: item[1].get("referrals_count", 0), 
                reverse=True
            )
            top_5 = sorted_users[:5]
            
            medals = ["🥇", "🥈", "🥉", "🎖", "🎖"]
            top_lines = []
            for idx, (u_id, u_info) in enumerate(top_5):
                count = u_info.get("referrals_count", 0)
                medal = medals[idx] if idx < len(medals) else "🏅"
                top_lines.append(f"{medal} : ({count}) -> {u_id}")
            
            top_text = "\n".join(top_lines) if top_lines else translate_text("لا يوجد مستخدمون بعد.", lang)
            
            db_local = load_db()
            ref_template = db_local.get("ref_info_text_template", DEFAULT_CONFIG["ref_info_text_template"])
            try:
                ref_msg = ref_template.format(ref_link=ref_link, my_invites=my_invites, top_text=top_text)
            except Exception:
                ref_msg = DEFAULT_CONFIG["ref_info_text_template"].format(ref_link=ref_link, my_invites=my_invites, top_text=top_text)
            ref_msg = translate_text(ref_msg, lang)
            
            back_markup = types.InlineKeyboardMarkup()
            back_markup.add(types.InlineKeyboardButton(t("back", lang), callback_data="nav_back_root"))
            edit_or_replace(cid, mid, call.message.content_type == "text", ref_msg, markup=back_markup)
            return

        if data == "my_info":
            lang = (get_user(str(uid)) or {}).get("language") or "ar"
            users_data = load_users()
            uid_str = str(uid)
            user_rec = users_data["users"].get(uid_str, {})
            display_name = get_display_name(call.from_user)
            points = user_rec.get("points", 0)
            my_invites = user_rec.get("referrals_count", 0)

            all_users = users_data.get("users", {})
            sorted_users = sorted(
                all_users.items(),
                key=lambda item: item[1].get("referrals_count", 0),
                reverse=True
            )
            rank = next((i + 1 for i, (u_id, _) in enumerate(sorted_users) if u_id == uid_str), len(sorted_users))

            db_local = load_db()
            info_template = db_local.get("my_info_text_template", DEFAULT_CONFIG["my_info_text_template"])
            try:
                info_text = info_template.format(name=display_name, id=uid, points=points, rank=rank, invites=my_invites)
            except Exception:
                info_text = DEFAULT_CONFIG["my_info_text_template"].format(name=display_name, id=uid, points=points, rank=rank, invites=my_invites)
            info_text = translate_text(info_text, lang)

            info_markup = types.InlineKeyboardMarkup(row_width=1)
            info_markup.add(types.InlineKeyboardButton(translate_text("ما فُتح من أزرار📮", lang), callback_data="my_unlocked"))
            info_markup.add(types.InlineKeyboardButton(t("back", lang), callback_data="nav_back_root"))
            edit_or_replace(cid, mid, call.message.content_type == "text", info_text, markup=info_markup, parse_mode="Markdown")
            return

        if data == "my_unlocked":
            lang = (get_user(str(uid)) or {}).get("language") or "ar"
            db = load_db()
            users_data = load_users()
            uid_str = str(uid)
            user_rec = users_data["users"].get(uid_str, {})
            unlocked_ids = user_rec.get("unlocked", [])

            lines = []
            total_points = 0
            needs_save = False
            for btn_id in unlocked_ids:
                btn = get_button(db, btn_id)
                if not btn:
                    continue
                pts = int(btn.get("unlock_points", 0))
                total_points += pts
                btn_name, ch = localized_field(btn, "name", lang)
                needs_save = needs_save or ch
                lines.append(f"• {btn_name} — {pts} " + translate_text("نقطة", lang))
            if needs_save:
                save_db(db)

            if lines:
                body = (
                    translate_text(f"🔓 عدد الخدمات المقفولة التي فتحتها: {len(lines)}", lang) + "\n"
                    + translate_text(f"💰 إجمالي النقاط التي دفعتها لفتحها: {total_points}", lang) + "\n\n"
                    + "\n".join(lines)
                )
            else:
                body = translate_text("لم يتم فتح ميزة/خدمة مقفلة إلى الآن (حالياً).", lang)

            unlocked_markup = types.InlineKeyboardMarkup()
            unlocked_markup.add(types.InlineKeyboardButton(t("back", lang), callback_data="my_info"))
            edit_or_replace(cid, mid, call.message.content_type == "text", body, markup=unlocked_markup)
            return

        if data == "change_sub_name":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="adm_feat_sub"))
            msg = bot.edit_message_text("✍️ أرسل الآن اسم الخدمة الجديد للاشتراك الإجباري:", cid, mid, reply_markup=markup)
            bot.register_next_step_handler(msg, save_new_sub_name)
            return

        if data == "add_sub_channel":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="adm_feat_sub"))
            msg = bot.edit_message_text("➕ أرسل معرف القناة المراد إضافتها (مثال: @Channel):", cid, mid, reply_markup=markup)
            bot.register_next_step_handler(msg, process_add_channel)
            return

        if data == "remove_sub_channel":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="adm_feat_sub"))
            msg = bot.edit_message_text("🗑 أرسل معرف القناة المراد إزالتها:", cid, mid, reply_markup=markup)
            bot.register_next_step_handler(msg, process_remove_channel)
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

        if data == "toggle_sub_status":
            db = load_db()
            current_status = db.get("sub_active", True)
            db["sub_active"] = not current_status
            save_db(db)
            status_text = "مفعل ✅" if db["sub_active"] else "معطل ❌"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_feat_sub"))
            bot.edit_message_text(f"🔄 تم تغيير حالة الاشتراك الإجباري بنجاح!\nالحالة الآن: {status_text}", cid, mid, reply_markup=markup)
            return

        if data == "list_sub_channels":
            db = load_db()
            channels = db.get("sub_channels", REQUIRED_CHANNELS)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 رجوع لإعدادات الاشتراك", callback_data="adm_feat_sub"))
            if channels:
                ch_list = "\n".join([f"• {ch}" for ch in channels])
                bot.edit_message_text(f"📋 القنوات المضافة حالياً للاشتراك الإجباري:\n\n{ch_list}", cid, mid, reply_markup=markup)
            else:
                bot.edit_message_text("📋 لا توجد أي قنوات مضافة حالياً للاشتراك الإجباري.", cid, mid, reply_markup=markup)
            return

        if data == "adm_feat_sub":
            db = load_db()
            sub_st = "مفعل ✅" if db.get("sub_active", True) else "معطل ❌"
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
                f"🛡 **إدارة الاشتراك الإجباري المتقدمة:**\n\n"
                f"• الحالة: {sub_st}\n"
                f"• القنوات المرتبطة: تدار عبر هذا الزر\n\n"
                f"اختر إجراء التحكم المطلوب:", 
                cid, mid, reply_markup=markup, parse_mode="Markdown"
            )
            return

        if data == "adm_back_main":
            bot.edit_message_text(admin_panel_text(), call.message.chat.id, call.message.message_id, reply_markup=admin_menu_markup())
            return

        if data.startswith("pay_"):
            btn_id = data[len("pay_"):]
            db = load_db()
            btn = get_button(db, btn_id)
            if not btn:
                bot.answer_callback_query(call.id, "⚠️ هذا الزر لم يعد موجوداً.", show_alert=True)
                return
            
            unlock_pts = int(btn.get("unlock_points", 0))
            users_db = load_users()
            uid_str = str(uid)
            user = users_db["users"].get(uid_str)
            
            current_pts = user.get("points", 0) if user else 0
            if not user or current_pts < unlock_pts:
                bot.answer_callback_query(call.id, f"❌ رصيد نقاطك غير كافٍ!\nرصيدك: {current_pts} | تحتاج: {unlock_pts}", show_alert=True)
                bot.send_message(
                    cid, 
                    f"❌ **عذراً، تعذر فتح الخدمة لعدم كفاية النقاط!**\n\n"
                    f"• اسم الخدمة: {btn.get('name', 'الخدمة')}\n"
                    f"• رصيدك الحالي: **{current_pts}** نقطة\n"
                    f"• التكلفة المطلوبة: **{unlock_pts}** نقطة\n"
                    f"• النقاط المفقودة: **{max(0, unlock_pts - current_pts)}** نقطة\n\n"
                    f"🎁 يمكنك جمع النقاط عبر استخدام (الهدية اليومية) أو (رابط الإحالة) من القائمة الرئيسية.",
                    parse_mode="Markdown"
                )
                return
            
            user["points"] -= unlock_pts
            if "unlocked" not in user:
                user["unlocked"] = []
            user["unlocked"].append(btn_id)
            save_users(users_db)
            
            bot.answer_callback_query(call.id, f"✅ تم الدفع (خصم {unlock_pts} نقطة) وفتح الخدمة بنجاح!", show_alert=True)
            try:
                bot.delete_message(cid, mid)
            except Exception:
                pass
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
                user_rec_for_markup = get_user(str(uid)) if parent_id is None else None
                text = (
                    main_menu_welcome_text(call.from_user, (user_rec_for_markup or {}).get("language") or "ar")
                    if parent_id is None
                    else ((get_button(db, parent_id) or {}).get("name", "اختر:"))
                )
                nav_markup = build_nav_markup(db, parent_id, user_rec=user_rec_for_markup)
                if call.message.content_type != "text":
                    try:
                        bot.delete_message(cid, mid)
                    except Exception as e:
                        logger.exception("Failed to delete media message before navigating back")
                    bot.send_message(cid, text, reply_markup=nav_markup)
                else:
                    bot.edit_message_text(text, cid, mid, reply_markup=nav_markup)
                return

            btn_id = data[len("nav_") :]
            btn = get_button(db, btn_id)
            if not btn:
                bot.send_message(cid, "⚠️ هذا الزر لم يعد موجوداً.")
                return

            user_rec_here = get_user(str(uid))
            lang = (user_rec_here or {}).get("language") or "ar"

            if get_children(db, btn_id):
                section_name, ch = localized_field(btn, "name", lang)
                if ch:
                    save_db(db)
                bot.edit_message_text(
                    section_name, cid, mid, reply_markup=build_nav_markup(db, btn_id, user_rec=user_rec_here)
                )
            else:
                unlock_pts = int(btn.get("unlock_points", 0))
                
                is_current_text = call.message.content_type == "text"
                if uid == ADMIN_ID:
                    show_leaf_content(cid, mid, is_current_text, btn, back_only_markup(btn), lang=lang, db=db)
                elif unlock_pts > 0:
                    users_db = load_users()
                    uid_str = str(uid)
                    user_data_db = users_db["users"].get(uid_str, {})
                    user_unlocked = user_data_db.get("unlocked", [])
                    
                    if btn_id in user_unlocked:
                        show_leaf_content(cid, mid, is_current_text, btn, back_only_markup(btn), lang=lang, db=db)
                    else:
                        desc, ch = localized_field(btn, "unlock_desc", lang)
                        if not desc:
                            desc = t("locked_default_desc", lang)
                        if ch:
                            save_db(db)
                        markup = types.InlineKeyboardMarkup()
                        markup.add(types.InlineKeyboardButton(f"🔓 فتح الخدمة بـ {unlock_pts} نقطة", callback_data=f"pay_{btn_id}"))
                        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=f"nav_back_{btn.get('parent_id', 'root')}"))
                        
                        payment_text = f"🔒 **خدمة مدفوعة**\n\n{desc}\n\n⚠️ **تكلفة الفتح:** {unlock_pts} نقطة."
                        
                        if call.message.content_type != "text":
                            try:
                                bot.delete_message(cid, mid)
                            except Exception:
                                pass
                            bot.send_message(cid, payment_text, reply_markup=markup, parse_mode="Markdown")
                        else:
                            bot.edit_message_text(payment_text, cid, mid, reply_markup=markup, parse_mode="Markdown")
                else:
                    show_leaf_content(cid, mid, is_current_text, btn, back_only_markup(btn), lang=lang, db=db)
            return

        if data == "gift_claim":
            db = load_db()
            lang = (get_user(str(uid)) or {}).get("language") or "ar"
            back_markup = types.InlineKeyboardMarkup()
            back_markup.add(types.InlineKeyboardButton(t("back", lang), callback_data="nav_back_root"))
            if not db.get("gift_active", True):
                msg = "⚠️ خدمة الهدية اليومية متوقفة مؤقتاً من قبل الإدارة."
            else:
                success, msg = claim_daily_gift(uid)
            msg = translate_text(msg, lang)
            edit_or_replace(cid, mid, call.message.content_type == "text", msg, markup=back_markup)
            return

        if data == "sub_check":
            db = load_db()
            if not db.get("sub_active", True) or not db.get("sub_channels", REQUIRED_CHANNELS):
                bot.send_message(cid, "✅ لا توجد قنوات مطلوبة حالياً.")
                return
            
            missing = check_subscription(uid)
            if missing:
                markup = build_sub_markup(missing)
                try:
                    bot.edit_message_text(
                        "❌ لم تشترك في جميع القنوات المطلوبة بعد.\n"
                        "اشترك في القنوات أدناه ثم اضغط زر التحقق مجدداً:",
                        cid,
                        mid,
                        reply_markup=markup
                    )
                except Exception:
                    bot.send_message(
                        cid,
                        "❌ لم تشترك في جميع القنوات المطلوبة بعد.\n"
                        "اشترك في القنوات أدناه ثم اضغط زر التحقق مجدداً:",
                        reply_markup=markup,
                    )
            else:
                try:
                    bot.delete_message(cid, mid)
                except Exception:
                    pass

                db, user_rec, bonus_given = process_start(call.from_user, [])

                prefix_text = "✅ تم التحقق من اشتراكك في القنوات بنجاح!"
                if bonus_given > 0:
                    prefix_text += f"\n🎁 حصلت على هدية التسجيل لأول مرة ({bonus_given} نقطة)!"

                enter_bot_gate(cid, None, False, call.from_user, prefix_text, db=db, user_rec=user_rec)
            return

        if data.startswith("ccont_"):
            continent_index = int(data[len("ccont_"):])
            render_country_list(cid, mid, call.message.content_type == "text", continent_index, page=0)
            return

        if data.startswith("cpage_"):
            _, continent_index_str, page_str = data.split("_")
            render_country_list(cid, mid, call.message.content_type == "text", int(continent_index_str), page=int(page_str))
            return

        if data == "cback":
            render_country_gate(cid, mid, call.message.content_type == "text")
            return

        if data.startswith("cpick_"):
            code = data[len("cpick_"):]
            country_name = COUNTRY_LOOKUP.get(code)
            db = load_db()
            uid_str = str(uid)
            user_rec = get_user(uid_str) or {}
            user_rec["country"] = code
            user_rec["country_asked"] = True

            bonus_note = ""
            if not user_rec.get("country_bonus_given"):
                bonus_pts = int(db.get("country_gate_points", 1))
                user_rec["points"] = user_rec.get("points", 0) + bonus_pts
                user_rec["country_bonus_given"] = True
                bonus_note = f"✅ اخترت: {flag(code)} {country_name} — حصلت على {bonus_pts} نقطة إضافية! 🎁"
            else:
                bonus_note = f"✅ اخترت: {flag(code)} {country_name}"
            save_user(uid_str, user_rec)

            if not user_rec.get("language_asked"):
                render_language_gate(cid, mid, call.message.content_type == "text", bonus_note)
            else:
                render_main_menu(cid, mid, call.message.content_type == "text", call.from_user, bonus_note)
            return

        if data == "country_skip":
            uid_str = str(uid)
            user_rec = get_user(uid_str) or {}
            user_rec["country_asked"] = True
            save_user(uid_str, user_rec)

            if not user_rec.get("language_asked"):
                render_language_gate(cid, mid, call.message.content_type == "text")
            else:
                render_main_menu(cid, mid, call.message.content_type == "text", call.from_user)
            return

        if data == "language_menu":
            render_language_gate(cid, mid, call.message.content_type == "text")
            return

        if data == "redo_gate":
            uid_str = str(uid)
            user_rec = get_user(uid_str) or {}
            db = load_db()
            is_text = call.message.content_type == "text"
            if db.get("country_gate_active", True) and user_rec.get("country") is None:
                render_country_gate(cid, mid, is_text)
            elif user_rec.get("language") is None:
                render_language_gate(cid, mid, is_text)
            else:
                render_main_menu(cid, mid, is_text, call.from_user)
            return

        if data in ("lang_ar", "lang_en", "lang_skip"):
            uid_str = str(uid)
            user_rec = get_user(uid_str) or {}
            user_rec["language_asked"] = True
            note = ""
            if data == "lang_ar":
                user_rec["language"] = "ar"
                note = "✅ تم اختيار: 🇸🇦 العربية"
            elif data == "lang_en":
                user_rec["language"] = "en"
                note = "✅ تم اختيار: 🇬🇧 English"
            save_user(uid_str, user_rec)
            render_main_menu(cid, mid, call.message.content_type == "text", call.from_user, note)
            return

        if uid != ADMIN_ID:
            return

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
            root_buttons = [b for b in db["buttons"] if b.get("parent_id") is None]
            if not root_buttons:
                bot.send_message(cid, "⚠️ لا توجد أقسام رئيسية (في الواجهة الرئيسية) بعد. أضف زراً رئيسياً أولاً.")
                return
            markup = types.InlineKeyboardMarkup()
            for btn in root_buttons:
                markup.add(
                    types.InlineKeyboardButton(
                        f"📁 {btn['name']}", callback_data=f"adm_sub_root_{btn['id']}"
                    )
                )
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_back_main"))
            bot.edit_message_text("اختر القسم الرئيسي الذي ترغب بإضافة الزر تحته:", cid, mid, reply_markup=markup)

        elif data.startswith("adm_sub_root_"):
            root_id = data[len("adm_sub_root_"):]
            db = load_db()
            root_btn = get_button(db, root_id)
            if not root_btn:
                bot.send_message(cid, "⚠️ القسم الرئيسي غير موجود.")
                return
            
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    f"➕ إضافة مباشرة داخل «{root_btn['name']}»", 
                    callback_data=f"adm_parent_{root_id}"
                )
            )
            
            children = get_children(db, root_id)
            if children:
                markup.add(types.InlineKeyboardButton("─── أو أضفه بداخل أحد الأزرار الفرعية التالية ───", callback_data="ignore"))
                for child in children:
                    markup.add(
                        types.InlineKeyboardButton(
                            f"📄 بداخل: {child['name']}", 
                            callback_data=f"adm_parent_{child['id']}"
                        )
                    )
            
            markup.add(types.InlineKeyboardButton("🔙 رجوع للأقسام", callback_data="adm_add_sub"))
            bot.edit_message_text(
                f"📂 القسم المختار: «{root_btn['name']}»\n\n"
                f"حدد أين تريد إضافة الزر الجديد بدقة:",
                cid, mid, reply_markup=markup
            )

        elif data.startswith("adm_parent_"):
            parent_id = data[len("adm_parent_") :]
            db = load_db()
            parent = get_button(db, parent_id)
            if not parent:
                bot.send_message(cid, "⚠️ الزر الأب غير موجود.")
                return
            set_state(uid, WAIT_BTN_NAME, parent_id=parent_id)
            bot.edit_message_text(
                f"📝 تم اختيار المكان بنجاح تحت: «{parent['name']}»\n\n"
                f"أرسل الآن **اسم الزر الجديد**:\n/cancel للإلغاء",
                cid,
                mid,
                parse_mode="Markdown"
            )

        elif data == "adm_lock_menu":
            db = load_db()
            leaves = [b for b in db["buttons"] if not get_children(db, b["id"]) and b.get("parent_id") is not None]
            
            if not leaves:
                bot.send_message(cid, "⚠️ لا توجد خدمات أو أزرار فرعية داخل القوائم لقفلها بعد.\n(أزرار الواجهة الرئيسية مستثناة ولا يمكن قفلها).")
                return
            
            markup = types.InlineKeyboardMarkup()
            for btn in leaves:
                is_locked = int(btn.get("unlock_points", 0)) > 0
                lock_icon = " 🔒" if is_locked else " 🔓"
                p = get_button(db, btn["parent_id"]) if btn.get("parent_id") else None
                path = f" ← {p['name']}" if p else ""
                markup.add(
                    types.InlineKeyboardButton(
                        f"{btn['name']}{lock_icon}{path}",
                        callback_data=f"lockbtn_{btn['id']}",
                    )
                )
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="adm_back_main"))
            bot.edit_message_text(
                "اختر الخدمة/الزر الفرعي لتعيين أو إلغاء القفل بالنقاط:\n(ملاحظة: أزرار الواجهة الرئيسية غير متاح قفلها هنا)\n(🔒 = مقفول ومدفوع | 🔓 = مفتوح مجاناً)",
                cid, mid, reply_markup=markup,
            )

        elif data.startswith("lockbtn_"):
            btn_id = data[len("lockbtn_") :]
            db = load_db()
            btn = get_button(db, btn_id)
            if not btn:
                bot.send_message(cid, "⚠️ الزر غير موجود.")
                return
            
            current_pts = btn.get("unlock_points", 0)
            current_status = f"مقفول بـ {current_pts} نقطة" if int(current_pts) > 0 else "مفتوح (مجاني)"
            
            set_state(uid, WAIT_LOCK_POINTS, btn_id=btn_id)
            bot.send_message(
                cid,
                f"⚙️ إعدادات القفل للزر: «{btn['name']}»\n"
                f"الحالة الحالية: {current_status}\n\n"
                f"أرسل الآن **عدد النقاط** المطلوب لفتح هذه الخدمة (أرسل 0 لإلغاء القفل وجعلها مجانية):\n/cancel للإلغاء",
                parse_mode="Markdown"
            )

        elif data == "adm_delete":
            db = load_db()
            if not db["buttons"]:
                bot.send_message(cid, "لا توجد أزرار لحذفها.")
                return
            markup = types.InlineKeyboardMarkup()
            for btn in db["buttons"]:
                p = get_button(db, btn["parent_id"]) if btn.get("parent_id") else None
                is_locked = int(btn.get("unlock_points", 0)) > 0
                lock_hint = " 🔒" if is_locked else ""
                base = f"{btn['name']}{lock_hint}"
                label = f"🗑 {base} ← {p['name']}" if p else f"🗑 {base}"
                markup.add(
                    types.InlineKeyboardButton(label, callback_data=f"del_{btn['id']}")
                )
            bot.send_message(
                cid, "اختر الزر لحذفه (سيُحذف مع كل أبنائه):", reply_markup=markup
            )

        elif data.startswith("del_") or data.startswith("delete_btn_"):
            btn_id = data.replace("del_", "").replace("delete_btn_", "")
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
            extra = f" وو {total} زر فرعي" if total else ""
            bot.send_message(cid, f"✅ تم حذف «{btn['name']}»{extra} بنجاح.")

        # ── إدارة المستخدمين المحدثة بالكامل ──
        elif data == "adm_users":
            markup = types.InlineKeyboardMarkup(row_width=2)
            
            markup.add(
                types.InlineKeyboardButton("📋 قائمة ومعرفات المستخدمين", callback_data="usr_view"),
                types.InlineKeyboardButton("🔍 البحث عن مستخدم", callback_data="usr_lookup_prompt")
            )
            markup.add(
                types.InlineKeyboardButton("🚫 حظر مستخدم عبر ID", callback_data="usr_ban"),
                types.InlineKeyboardButton("✅ رفع حظر مستخدم", callback_data="usr_unban")
            )
            markup.add(
                types.InlineKeyboardButton("⏳ حظر مؤقت عبر ID", callback_data="usr_temp_ban"),
                types.InlineKeyboardButton("🛡️ إعدادات الحظر التلقائي", callback_data="usr_autoban_settings")
            )
            markup.add(
                types.InlineKeyboardButton("📊 الإحصائيات اليومية", callback_data="usr_daily_stats"),
                types.InlineKeyboardButton("💰 إحصائيات استهلاك النقاط", callback_data="usr_points_consumption")
            )
            markup.add(
                types.InlineKeyboardButton("📈 تفاعل الأزرار والخدمات", callback_data="usr_buttons_interaction"),
                types.InlineKeyboardButton("🎁 إحصائيات توزيع النقاط", callback_data="usr_points_distribution")
            )
            markup.add(
                types.InlineKeyboardButton("🌍 أكثر المستخدمين زيارةً للبوت", callback_data="usr_country_stats")
            )
            markup.add(
                types.InlineKeyboardButton("⚖️ تعديل رصيد النقاط", callback_data="usr_lookup_prompt"),
                types.InlineKeyboardButton("🔙 العودة لوحة التحكم", callback_data="adm_back_main")
            )
            
            bot.edit_message_text(
                "👥 **لوحة تحكم إدارة المستخدمين والنقاط:**\nاختر الإجراء المطلوب:", 
                cid, mid, reply_markup=markup, parse_mode="Markdown"
            )
            return

        elif data == "usr_view":
            db = load_db()
            users = db.get("users", [])
            banned = db.get("banned_users", [])
            if not users:
                bot.send_message(cid, "لا يوجد مستخدمون مسجلون بعد.")
                return
            lines = [f"• {u}{' 🚫' if u in banned else ''}" for u in users]
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 رجوع لقائمة المستخدمين", callback_data="adm_users"))
            bot.edit_message_text(
                f"👥 المستخدمون المسجلون ({len(users)}):\n\n" + "\n".join(lines[:50]) + ("\n\n...(تم عرض أول 50 مستخدم)" if len(lines) > 50 else "") + "\n\n🚫 = محظور",
                cid, mid, reply_markup=markup
            )

        elif data == "usr_lookup_prompt":
            set_state(uid, WAIT_USER_LOOKUP)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="adm_users"))
            bot.edit_message_text(
                "🔍 أرسل الآن **ID المستخدم** الذي تريد إدارة حسابه (معرفة نقاطه، تعديل رصيده، أو حظره):\n/cancel للإلغاء",
                cid, mid, reply_markup=markup, parse_mode="Markdown"
            )
            return

        elif data == "usr_country_stats":
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("📋 الدول الأكثر زيارة (تسجيلاً) للبوت", callback_data="usr_country_visits"))
            markup.add(types.InlineKeyboardButton("🔥 الدول الأكثر استخداماً للبوت", callback_data="usr_country_usage"))
            markup.add(types.InlineKeyboardButton("🔙 رجوع لإدارة المستخدمين", callback_data="adm_users"))
            bot.edit_message_text(
                "🌍 **إحصائيات الدول:**\n\n"
                "• «الأكثر زيارة» = عدد المستخدمين المسجَّلين من كل دولة.\n"
                "• «الأكثر استخداماً» = مجموع مرات استخدام البوت (/start) للمستخدمين من كل دولة.\n\n"
                "اختر التقرير:",
                cid, mid, reply_markup=markup, parse_mode="Markdown"
            )
            return

        elif data in ("usr_country_visits", "usr_country_usage"):
            users_data = load_users()
            all_users = users_data.get("users", {})
            total_users = len(all_users) or 1

            counts = {}
            usage = {}
            unspecified_count = 0
            unspecified_usage = 0
            for u_rec in all_users.values():
                code = u_rec.get("country")
                visits = int(u_rec.get("visits", 0))
                if code and code in COUNTRY_LOOKUP:
                    counts[code] = counts.get(code, 0) + 1
                    usage[code] = usage.get(code, 0) + visits
                else:
                    unspecified_count += 1
                    unspecified_usage += visits

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="usr_country_stats"))

            if data == "usr_country_visits":
                title = "📋 **الدول الأكثر زيارة (تسجيلاً) للبوت:**"
                rows = sorted(counts.items(), key=lambda x: x[1], reverse=True)
                lines = [
                    f"{flag(code)} {COUNTRY_LOOKUP[code]} — {cnt} مستخدم ({cnt / total_users * 100:.1f}%)"
                    for code, cnt in rows
                ]
                lines.append(f"🏳️ غير محدَّد — {unspecified_count} مستخدم ({unspecified_count / total_users * 100:.1f}%)")
            else:
                title = "🔥 **الدول الأكثر استخداماً للبوت:**"
                rows = sorted(usage.items(), key=lambda x: x[1], reverse=True)
                lines = [f"{flag(code)} {COUNTRY_LOOKUP[code]} — {cnt} استخدام" for code, cnt in rows]
                lines.append(f"🏳️ غير محدَّد — {unspecified_usage} استخدام")

            shown_lines = lines[:30]
            extra_note = f"\n\n…و{len(lines) - 30} دولة أخرى." if len(lines) > 30 else ""
            body = "\n".join(shown_lines) if shown_lines else "لا توجد بيانات كافية بعد."

            bot.edit_message_text(
                f"{title}\n\n{body}{extra_note}",
                cid, mid, reply_markup=markup, parse_mode="Markdown"
            )
            return

        elif data in ["usr_temp_ban", "usr_autoban_settings", "usr_daily_stats", "usr_points_consumption", "usr_buttons_interaction", "usr_points_distribution"]:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 رجوع لإدارة المستخدمين", callback_data="adm_users"))
            
            titles = {
                "usr_temp_ban": "⏳ **نظام الحظر المؤقت:**\n\nأرسل ID المستخدم المحدد مع تحديد مدة الحظر.",
                "usr_autoban_settings": "🛡️ **إعدادات الحظر التلقائي:**\n\nمفعلة لحماية البوت من السبام والتكرار السريع.",
                "usr_daily_stats": "📊 **الإحصائيات اليومية:**\n\n• نشاط المستخدمين اليوم: نشط\n• العمليات المكتملة بنجاح.",
                "usr_points_consumption": "💰 **إحصائيات استهلاك النقاط:**\n\n• إجمالي النقاط المستهلكة في فتح الخدمات والملفات.",
                "usr_buttons_interaction": "📈 **تفاعل الأزرار والخدمات:**\n\n• يتم تتبع جميع النقرات وتفاعل المستخدمين مع أقسام البوت بدقة.",
                "usr_points_distribution": "🎁 **إحصائيات توزيع النقاط:**\n\n• تفاصيل الهدية اليومية ومكافآت التسجيل والإحالات الموزعة."
            }
            bot.edit_message_text(titles.get(data, "⚙️ قسم قيد التطوير والتحديث المستمر."), cid, mid, reply_markup=markup, parse_mode="Markdown")
            return

        elif data.startswith("usropt_"):
            parts = data.split("_")
            action = parts[1]
            target_id = int(parts[2])
            uid_str = str(target_id)
            
            users_data = load_users()
            db = load_db()
            user_rec = users_data["users"].get(uid_str)
            
            if not user_rec:
                bot.answer_callback_query(call.id, "⚠️ هذا المستخدم غير مسجل في قاعدة بيانات النقاط.", show_alert=True)
                return
            
            if action in ["add", "sub"]:
                set_state(uid, WAIT_USER_POINTS_MODIFY, target_id=target_id, action=action)
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔙 إلغاء", callback_data="adm_users"))
                action_name = "إضافة نقاط إلى" if action == "add" else "خصم نقاط من"
                bot.edit_message_text(
                    f"✍️ أنت الآن تقوم بـ **{action_name}** المستخدم (`{target_id}`).\n\n"
                    f"أرسل الآن عدد النقاط المطلوبة (برقم صحيح):\n/cancel للإلغاء",
                    cid, mid, reply_markup=markup, parse_mode="Markdown"
                )
                return
            elif action == "reset":
                user_rec["points"] = 0
                save_users(users_data)
                bot.answer_callback_query(call.id, f"✅ تم تصفير نقاط المستخدم {target_id} بنجاح!", show_alert=True)
                bot.edit_message_text(f"✅ تم تصفير نقاط المستخدم (`{target_id}`) بنجاح وأصبحت 0 نقطة.", cid, mid, parse_mode="Markdown")
                return
            elif action == "ban":
                banned_list = db.setdefault("banned_users", [])
                if target_id in banned_list:
                    banned_list.remove(target_id)
                    status_msg = "✅ تم رفع الحظر عن المستخدم بنجاح."
                else:
                    banned_list.append(target_id)
                    status_msg = "🚫 تم حظر المستخدم بنجاح."
                save_db(db)
                bot.answer_callback_query(call.id, status_msg, show_alert=True)
                bot.edit_message_text(f"{status_msg} (`{target_id}`)", cid, mid, parse_mode="Markdown")
                return

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
        if uid != ADMIN_ID:
            try:
                bot.forward_message(ADMIN_ID, cid, message.message_id)
            except Exception as e:
                logger.exception("Failed to forward message to admin")
        return

    if message.content_type == "text" and message.text.strip().startswith("/cancel"):
        clear_state(uid)
        bot.send_message(cid, "❌ تم الإلغاء.")
        return

    if state == WAIT_NEW_CODE_STR:
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ أرسل صيغة الكود كنص من فضلك.")
            return
        code_text = message.text.strip()
        set_state(uid, WAIT_NEW_CODE_PTS, code_text=code_text)
        bot.send_message(
            cid,
            f"✅ الكود: «{code_text}»\n\n"
            f"الآن أرسل **عدد النقاط** التي سيحصل عليها من يستخدم هذا الكود (برقم صحيح):\n/cancel للإلغاء",
            parse_mode="Markdown"
        )

    elif state == WAIT_NEW_CODE_PTS:
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ أرسل عدد النقاط برقم صحيح.")
            return
        try:
            points_val = int(message.text.strip())
            d = get_data(uid)
            code_text = d.get("code_text")
            
            db = load_db()
            if "gift_codes" not in db:
                db["gift_codes"] = []
            
            for c in db["gift_codes"]:
                if c["code"] == code_text:
                    bot.send_message(cid, f"⚠️ هذا الكود ({code_text}) موجود مسبقاً! اختر كوداً آخر.")
                    clear_state(uid)
                    return
            
            db["gift_codes"].append({
                "code": code_text,
                "points": points_val
            })
            save_db(db)
            clear_state(uid)
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 عودة لإدارة الأكواد", callback_data="adm_gift_codes_menu"))
            bot.send_message(
                cid,
                f"✅ **تم إنشاء وحفظ كود الهدية/المسابقة بنجاح!**\n\n"
                f"• الكود: `{code_text}`\n"
                f"• النقاط المخصصة: **{points_val}** نقطة\n\n"
                f"يمكنك الآن توزيعه في قناتك لمن يربح المسابقة!",
                reply_markup=markup,
                parse_mode="Markdown"
            )
        except ValueError:
            bot.send_message(cid, "❌ خطأ: يرجى إرسال رقم صحيح لعدد النقاط.")

    elif state == WAIT_ENTER_GIFT_CODE:
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ أرسل الكود كنص من فضلك.")
            return
        entered_code = message.text.strip()
        db = load_db()
        gift_codes = db.get("gift_codes", [])
        
        found_code = None
        for c in gift_codes:
            if c["code"] == entered_code:
                found_code = c
                break
        
        if not found_code:
            bot.send_message(cid, "❌ **عذراً، هذا الكود غير صحيح أو انتهى استخدامه أو تم استبداله مسبقاً!**", parse_mode="Markdown")
            clear_state(uid)
            return
        
        pts = found_code["points"]
        
        db["gift_codes"] = [c for c in gift_codes if c["code"] != entered_code]
        save_db(db)
        
        users_data = load_users()
        uid_str = str(uid)
        if uid_str not in users_data["users"]:
            register_user_points(uid, message.from_user.first_name or "")
            users_data = load_users()
        
        users_data["users"][uid_str]["points"] = users_data["users"][uid_str].get("points", 0) + pts
        save_users(users_data)
        clear_state(uid)
        
        bot.send_message(
            cid,
            f"🎉 **مبروك! تم استبدال الكود بنجاح!**\n\n"
            f"• لقد حصلت على: **{pts}** نقطة\n"
            f"• رصيدك الحالي: **{users_data['users'][uid_str]['points']}** نقطة 🌟",
            parse_mode="Markdown"
        )

    elif state == WAIT_BTN_NAME:
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ أرسل اسم الزر كنص من فضلك.")
            return
        btn_name = message.text.strip()
        parent_id = get_data(uid).get("parent_id")
        set_state(uid, WAIT_BTN_CONTENT, parent_id=parent_id, btn_name=btn_name)
        bot.send_message(
            cid,
            f"✅ الاسم: «{btn_name}»\n\n"
            f"الآن أرسل المحتوى للزر (تطبيق/ملف، صورة، فيديو، مع كتابة الشرح أو الوصف معها مباشرة إذا أردت):\n/cancel للإلغاء",
        )

    elif state == WAIT_BTN_CONTENT:
        bot.send_message(cid, "⏳ تم استلام المحتوى والشرح وحفظهما...")
        d = get_data(uid)
        parent_id = d.get("parent_id")
        btn_name = d.get("btn_name", "زر")
        
        ct, content, caption = extract_content(message)
        
        db = load_db()
        db["buttons"].append(
            {
                "id": new_id(),
                "name": btn_name,
                "content_type": ct,
                "content": content,
                "caption": caption,
                "parent_id": parent_id,
                "unlock_points": 0,
                "unlock_desc": "",
                "order": len(get_children(db, parent_id)),
            }
        )
        save_db(db)
        clear_state(uid)
        
        bot.send_message(
            cid,
            f"✅ تم حفظ الزر والمحتوى والشرح بنجاح!\n"
            f"• النوع: {ct}\n"
            f"• الشرح المرفق: {'موجود ✅' if caption else 'بدون شرح'}\n\n"
            f"💡 يمكنك قفل هذا الزر بنقاط من لوحة التحكم.",
        )

    elif state == WAIT_USER_LOOKUP:
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ أرسل ID المستخدم كرقم صحيح.")
            return
        try:
            target_id = int(message.text.strip())
            uid_str = str(target_id)
            users_data = load_users()
            db = load_db()
            
            user_rec = users_data["users"].get(uid_str)
            if not user_rec:
                bot.send_message(cid, f"⚠️ المستخدم برقم `{target_id}` غير مسجل في قاعدة بيانات النقاط.", parse_mode="Markdown")
                clear_state(uid)
                return
            
            is_banned = target_id in db.get("banned_users", [])
            name = user_rec.get("name", "بدون اسم")
            points = user_rec.get("points", 0)
            ref_count = user_rec.get("referrals_count", 0)
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("➕ إضافة نقاط", callback_data=f"usropt_add_{target_id}"),
                types.InlineKeyboardButton("➖ خصم نقاط", callback_data=f"usropt_sub_{target_id}")
            )
            markup.add(
                types.InlineKeyboardButton("🔄 تصفير النقاط", callback_data=f"usropt_reset_{target_id}"),
                types.InlineKeyboardButton("🚫 حظر/رفع حظر", callback_data=f"usropt_ban_{target_id}")
            )
            markup.add(types.InlineKeyboardButton("🔙 رجوع لإدارة المستخدمين", callback_data="adm_users"))
            
            bot.send_message(
                cid,
                f"👤 **معلومات المستخدم:**\n\n"
                f"• الآيدي (`ID`): `{target_id}`\n"
                f"• الاسم: {name}\n"
                f"• الرصيد الحالي: **{points}** نقطة\n"
                f"• عدد الإحالات: {ref_count}\n"
                f"• الحالة: {'محظور 🚫' if is_banned else 'غير محظور ✅'}\n\n"
                f"اختر الإجراء المطلوب على حساب هذا المستخدم:",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            clear_state(uid)
        except ValueError:
            bot.send_message(cid, "❌ خطأ: يرجى إرسال ID صحيح (رقم فقط).")

    elif state == WAIT_USER_POINTS_MODIFY:
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ أرسل عدد النقاط كرقم صحيح.")
            return
        try:
            amount = int(message.text.strip())
            st_data = get_data(uid)
            target_id = st_data.get("target_id")
            action = st_data.get("action")
            uid_str = str(target_id)
            
            users_data = load_users()
            user_rec = users_data["users"].get(uid_str)
            
            if not user_rec:
                bot.send_message(cid, "⚠️ المستخدم غير موجود.")
                clear_state(uid)
                return
            
            current_pts = user_rec.get("points", 0)
            if action == "add":
                user_rec["points"] = current_pts + amount
                msg_text = f"✅ تم إضافة {amount} نقطة بنجاح للمستخدم (`{target_id}`).\nالرصيد الجديد: **{user_rec['points']}** نقطة."
            else:
                user_rec["points"] = max(0, current_pts - amount)
                msg_text = f"✅ تم خصم {amount} نقطة بنجاح من المستخدم (`{target_id}`).\nالرصيد الجديد: **{user_rec['points']}** نقطة."
            
            save_users(users_data)
            clear_state(uid)
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 رجوع لإدارة المستخدمين", callback_data="adm_users"))
            bot.send_message(cid, msg_text, reply_markup=markup, parse_mode="Markdown")
        except ValueError:
            bot.send_message(cid, "❌ خطأ: يرجى إرسال رقم صحيح فقط.")

    elif state == WAIT_LOCK_POINTS:
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ أرسل عدد النقاط كرقم صحيح.")
            return
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
                bot.send_message(cid, f"✅ تم إلغاء القفل عن الخدمة «{btn['name']}» وأصبحت مجانية للمستخدمين.")
            else:
                set_state(uid, WAIT_LOCK_DESC, btn_id=btn_id, points=pts)
                bot.send_message(
                    cid, 
                    "✍️ ممتاز! أرسل الآن **الرسالة أو الوصف** الذي سيظهر للمستخدم قبل الدفع:\n"
                    "(مثال: يحتوي هذا الزر على ملفات سرية وحصرية، قم بالدفع لفتحه...)"
                )
        except ValueError:
            bot.send_message(cid, "❌ خطأ: يرجى إرسال رقم صحيح فقط.")

    elif state == WAIT_LOCK_DESC:
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ أرسل الوصف كنص من فضلك.")
            return
        
        desc = message.text.strip()
        data_dict = get_data(uid)
        btn_id = data_dict.get("btn_id")
        pts = data_dict.get("points")
        
        db = load_db()
        btn = get_button(db, btn_id)
        if btn:
            btn["unlock_points"] = pts
            btn["unlock_desc"] = desc
            save_db(db)
        
        clear_state(uid)
        bot.send_message(
            cid, 
            f"✅ **تم قفل الخدمة بنجاح!**\n\n"
            f"• الخدمة: {btn['name']}\n"
            f"• سعر الفتح: {pts} نقطة\n"
            f"• وصف الخدمة:\n{desc}", 
            parse_mode="Markdown"
        )
        
    elif state == WAIT_GIFT_NAME:
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ أرسل الاسم كنص من فضلك.")
            return
        new_name = message.text.strip()
        db = load_db()
        db["gift_name"] = new_name
        save_db(db)
        clear_state(uid)
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 عودة لإعدادات الهدية", callback_data="adm_feat_gift"))
        bot.send_message(
            cid, 
            f"✅ **تم تغيير اسم خدمة الهدية بنجاح!**\n\n• الاسم الجديد: {new_name}", 
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    elif state == WAIT_WELCOME_NAME:
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ أرسل الاسم كنص من فضلك.")
            return
        new_name = message.text.strip()
        db = load_db()
        db["welcome_name"] = new_name
        save_db(db)
        clear_state(uid)
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 عودة لإعدادات مكافأة التسجيل", callback_data="adm_feat_welcome"))
        bot.send_message(
            cid, 
            f"✅ **تم تغيير اسم خدمة مكافأة التسجيل بنجاح!**\n\n• الاسم الجديد: {new_name}", 
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    elif state == WAIT_REF_NAME:
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ أرسل الاسم كنص من فضلك.")
            return
        new_name = message.text.strip()
        db = load_db()
        db["ref_name"] = new_name
        save_db(db)
        clear_state(uid)
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 عودة لإعدادات الإحالة", callback_data="adm_feat_ref"))
        bot.send_message(
            cid, 
            f"✅ **تم تغيير اسم خدمة الإحالة بنجاح!**\n\n• الاسم الجديد: {new_name}", 
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    elif state == WAIT_GIFTCODE_BTN_NAME:
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ أرسل النص كرسالة نصية من فضلك.")
            return
        new_name = message.text.strip()
        db = load_db()
        new_name = merge_emoji(db.get("gift_code_btn_name", ""), new_name)
        db["gift_code_btn_name"] = new_name
        save_db(db)
        clear_state(uid)

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 عودة", callback_data="adm_fixed_texts"))
        bot.send_message(
            cid,
            f"✅ **تم تغيير نص زر «كود هدية» بنجاح!**\n\n• النص الجديد: {new_name}",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    elif state == WAIT_MYINFO_BTN_NAME:
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ أرسل النص كرسالة نصية من فضلك.")
            return
        new_name = message.text.strip()
        db = load_db()
        new_name = merge_emoji(db.get("my_info_btn_name", ""), new_name)
        db["my_info_btn_name"] = new_name
        save_db(db)
        clear_state(uid)

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 عودة", callback_data="adm_fixed_texts"))
        bot.send_message(
            cid,
            f"✅ **تم تغيير نص زر «معلوماتي» بنجاح!**\n\n• النص الجديد: {new_name}",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    elif state == WAIT_LANGUAGE_BTN_NAME:
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ أرسل النص كرسالة نصية من فضلك.")
            return
        new_name = message.text.strip()
        db = load_db()
        new_name = merge_emoji(db.get("language_btn_name", ""), new_name)
        db["language_btn_name"] = new_name
        save_db(db)
        clear_state(uid)

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 عودة", callback_data="adm_fixed_texts"))
        bot.send_message(
            cid,
            f"✅ **تم تغيير نص زر «لغة البوت» بنجاح!**\n\n• النص الجديد: {new_name}",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    elif state == "WAIT_FIXED_TEXT_EDIT":
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ أرسل النص كرسالة نصية من فضلك.")
            return
        d = get_data(uid)
        config_key = d.get("config_key")
        back_key = d.get("back_key")
        new_text = message.text
        db = load_db()
        if config_key:
            db[config_key] = new_text
            save_db(db)
        clear_state(uid)

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=f"adm_fixed_item_{back_key}" if back_key else "adm_fixed_texts"))
        bot.send_message(cid, "✅ تم تحديث النص بنجاح!", reply_markup=markup)
        return
        
    elif state == "WAIT_DYNAMIC_BTN_EDIT":
        if message.content_type != "text":
            bot.send_message(cid, "⚠️ عذراً، يجب إرسال القيمة الجديدة كنص.")
            return
        
        state_data = get_data(uid)
        btn_id = state_data.get("btn_id")
        edit_key = state_data.get("edit_key")
        new_value = message.text.strip()
        
        db = load_db()
        btn = get_button(db, btn_id)
        
        if not btn:
            bot.send_message(cid, "⚠️ هذا الزر أو الخدمة لم تعد موجودة.")
            clear_state(uid)
            return
        
        if edit_key == "name":
            btn["name"] = merge_emoji(btn.get("name", ""), new_value)
        elif edit_key == "content":
            btn["content"] = new_value
        elif edit_key == "points":
            if "settings" not in btn:
                btn["settings"] = {}
            btn["settings"]["points"] = new_value
        else:
            btn[edit_key] = new_value
        
        save_db(db)
        clear_state(uid)
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 العودة لقائمة إعدادات الخدمات", callback_data="adm_settings_list"))
        
        bot.send_message(
            cid,
            f"✅ **تم التعديل والحفظ بنجاح!**\n\n"
            f"• العنصر: {btn.get('name')}\n"
            f"• التعديل المحدث: {edit_key}\n"
            f"• القيمة الجديدة: {new_value}",
            reply_markup=markup,
            parse_mode="Markdown"
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
        bot.send_message(cid, "⏳ جاري إرسال الإعلان مع تطبيق الإعدادات الحالية...")
        db = load_db()
        b_settings = db.get("broadcast_settings", {"pin": False, "silent": False})
        should_pin = b_settings.get("pin", False)
        is_silent = b_settings.get("silent", False)
        
        sent = 0
        failed = 0
        for target_uid in db.get("users", []):
            if target_uid == ADMIN_ID:
                continue
            try:
                sent_msg = bot.copy_message(
                    target_uid, 
                    cid, 
                    message.message_id, 
                    disable_notification=is_silent
                )
                if should_pin:
                    try:
                        bot.pin_chat_message(target_uid, sent_msg.message_id)
                    except Exception:
                        pass
                sent += 1
            except Exception as e:
                logger.exception("Failed to send broadcast message to %s", target_uid)
                failed += 1
        clear_state(uid)
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 عودة لإعدادات الإعلان", callback_data="adm_broadcast_menu"))
        bot.send_message(
            cid, 
            f"📣 **اكتمل إرسال الإعلان بنجاح!**\n\n"
            f"• ✅ نجح الإرسال إلى: `{sent}` مستخدم\n"
            f"• ❌ فشل الإرسال إلى: `{failed}` مستخدم\n"
            f"• 📌 التثبيت: {'مفعل' if should_pin else 'معطل'}\n"
            f"• 🔕 بدون إشعار: {'نعم' if is_silent else 'لا'}",
            reply_markup=markup,
            parse_mode="Markdown"
        )


def save_new_gift_points(message):
    try:
        new_pts = int(message.text.strip())
        db = load_db()
        db["gift_points"] = new_pts
        save_db(db)
        bot.send_message(message.chat.id, f"✅ تم تحديث عدد نقاط الهدية اليومية بنجاح إلى: {new_pts} نقطة.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ خطأ: يرجى إرسال رقم صحيح فقط.")


def save_new_welcome_points(message):
    try:
        new_pts = int(message.text.strip())
        db = load_db()
        db["welcome_points"] = new_pts
        save_db(db)
        bot.send_message(message.chat.id, f"✅ تم تحديث عدد نقاط مكافأة التسجيل بنجاح إلى: {new_pts} نقطة.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ خطأ: يرجى إرسال رقم صحيح فقط.")


def save_new_ref_points(message):
    try:
        new_pts = int(message.text.strip())
        db = load_db()
        db["ref_points"] = new_pts
        save_db(db)
        bot.send_message(message.chat.id, f"✅ تم تحديث عدد نقاط الإحالة بنجاح إلى: {new_pts} نقطة.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ خطأ: يرجى إرسال رقم صحيح فقط.")


def save_new_sub_name(message):
    new_name = message.text.strip()
    db = load_db()
    db["sub_name"] = new_name
    save_db(db)
    bot.send_message(message.chat.id, f"✅ تم تغيير اسم خدمة الاشتراك الإجباري إلى: {new_name}")


def process_add_channel(message):
    cid = message.chat.id
    raw_text = message.text.strip()
    
    ch = raw_text
    if "t.me/" in ch:
        ch = "@" + ch.split("t.me/")[-1].split("/")[0].strip()
    elif not ch.startswith("@"):
        ch = "@" + ch
    
    if len(ch) < 4:
        bot.send_message(cid, "❌ خطأ: معرف القناة قصير جداً أو غير صالح.")
        return
    
    try:
        chat_info = bot.get_chat(ch)
        if chat_info.type != "channel":
            bot.send_message(cid, "❌ خطأ: المعرف المُرسل ليس لقناة عامة في تيليجرام.")
            return
        
        bot_member = bot.get_chat_member(ch, bot.get_me().id)
        if bot_member.status not in ('administrator', 'creator'):
            bot.send_message(cid, "❌ خطأ الشروط: البوت ليس مشرفاً في هذه القناة! أضفه مشرفاً أولاً.")
            return
        
        db = load_db()
        if "sub_channels" not in db:
            db["sub_channels"] = REQUIRED_CHANNELS.copy()
        
        existing_channels = db["sub_channels"]
        if any(c.lower() == ch.lower() for c in existing_channels):
            bot.send_message(cid, f"⚠️ هذه القناة ({ch}) مضافة مسبقاً في القائمة.")
            return
        
        db["sub_channels"].append(ch)
        save_db(db)
        bot.send_message(
            cid, 
            f"✅ تمت إضافة القناة بنجاح واجتازت كافة الشروط!\n\n"
            f"• اسم القناة: {chat_info.title}\n"
            f"• المعرف: {ch}"
        )
    except Exception as e:
        logger.exception("Failed to add channel %s: %s", ch, e)
        bot.send_message(cid, "❌ خطأ في التحقق من القناة! تأكد من صحة المعرف وأن البوت مشرف فيها.")


def process_remove_channel(message):
    ch = message.text.strip()
    db = load_db()
    channels = db.get("sub_channels", REQUIRED_CHANNELS)
    if ch in channels:
        channels.remove(ch)
        db["sub_channels"] = channels
        save_db(db)
        bot.send_message(message.chat.id, f"✅ تم إزالة القناة ({ch}) بنجاح.")
    else:
        bot.send_message(message.chat.id, "❌ هذه القناة غير موجودة في القائمة الحالية.")


# ═══════════════════════════════════════════════════════════════
# RUN
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
