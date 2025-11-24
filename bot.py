import os
import json
from datetime import datetime, timezone, timedelta
from io import BytesIO

import qrcode
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ====== CONFIG ======
TOKEN = os.environ.get("BOT_TOKEN")  # Render / env var orqali bering
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))  # Soni sifatida admin id
USERS_FILE = "users.json"
ONLINE_SECONDS = 300  # "Online" deb hisoblash uchun oxirgi faollik (sekundlarda)
# ====================

# Tilga mos "Dasturchi" matni
DEVELOPER_TEXT = {
    "uz": "\n\nDasturchi: @adashovsolejonoffical",
    "ru": "\n\nРазработчик: @adashovsolejonoffical",
    "en": "\n\nDeveloper: @adashovsolejonoffical",
}

# Tillarni tugma bilan ko'rsatish
LANG_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton("🇺🇿 UZ"), KeyboardButton("🇷🇺 RU"), KeyboardButton("🇬🇧 EN")]],
    resize_keyboard=True,
)

# ====== Users management ======
def load_users():
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

users = load_users()

def ensure_user(user_id: str, fullname: str = None):
    if user_id not in users:
        users[user_id] = {
            "lang": "uz",  # default
            "blocked": False,
            "last_active": None,
        }
        save_users(users)
        # notify admin
        if ADMIN_ID:
            try:
                app_bot = application.bot
                app_bot.send_message(chat_id=ADMIN_ID, text=f"🆕 Yangi foydalanuvchi: {fullname} ({user_id})")
            except Exception:
                pass

def update_last_active(user_id: str):
    users.setdefault(user_id, {"lang": "uz", "blocked": False, "last_active": None})
    # store ISO timestamp in UTC
    users[user_id]["last_active"] = datetime.now(timezone.utc).isoformat()
    save_users(users)

# ====== Helper: language normalization ======
def norm_lang(text: str):
    t = text.strip().lower()
    if t.startswith("uz") or "uz" in t or "🇺🇿" in text:
        return "uz"
    if t.startswith("ru") or "ru" in t or "🇷🇺" in text:
        return "ru"
    if t.startswith("en") or "en" in t or "🇬🇧" in text:
        return "en"
    return None

# ====== Handlers ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    fullname = user.full_name
    ensure_user(user_id, fullname)
    update_last_active(user_id)
    await update.message.reply_text(
        "Assalomu alaykum!\nTilni tanlang / Выберите язык / Choose a language:",
        reply_markup=LANG_KEYBOARD,
    )

# Commands to set language directly
async def cmd_set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    text = update.message.text
    # allow commands: /uz /ru /en or plain text buttons
    chosen = norm_lang(text.replace("/", ""))
    if not chosen:
        # maybe user pressed a button like "🇺🇿 UZ"
        chosen = norm_lang(text)
    if not chosen:
        await update.message.reply_text("Tilni tanlash mumkin: UZ / RU / EN")
        return
    users.setdefault(user_id, {"lang": "uz", "blocked": False, "last_active": None})
    users[user_id]["lang"] = chosen
    save_users(users)
    update_last_active(user_id)
    msgs = {
        "uz": "Til o'rnatildi: Oʻzbekcha. Endi matn yoki media yuboring — men QR yarataman.",
        "ru": "Язык установлен: Русский. Отправьте текст или медиа — я создам QR-код.",
        "en": "Language set: English. Send text or media — I will generate a QR code.",
    }
    await update.message.reply_text(msgs[chosen])

# Core: create QR from text (or from caption of media)
def build_qr_image(full_text: str):
    qr = qrcode.QRCode(version=None, box_size=10, border=4)
    qr.add_data(full_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = BytesIO()
    bio.name = "qr.png"
    img.save(bio, "PNG")
    bio.seek(0)
    return bio

async def make_qr_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    ensure_user(user_id, user.full_name)
    update_last_active(user_id)

    # If blocked, ignore
    if users.get(user_id, {}).get("blocked", False):
        return

    # Determine input: text or caption (for photo/video)
    text = None
    if update.message.text and not update.message.text.startswith("/"):
        text = update.message.text.strip()
    elif update.message.caption:
        text = update.message.caption.strip()

    # If user sent photo/video but no caption - we cannot make QR of media file itself sensibly.
    if not text:
        # If message has photo/video but no caption, suggest to send caption or text
        if update.message.photo or update.message.video:
            await update.message.reply_text(
                "Iltimos, QR yaratish uchun matn yoki media caption yuboring.\n"
                "Eslatma: rasm/video o'zi fayl bo‘lib, fayl ichidan matn olinmaydi — caption yuboring."
            )
            return
        else:
            await update.message.reply_text("Matn yuboring (link, sms yoki boshqa):")
            return

    # Get user's language (default uz)
    lang = users.get(user_id, {}).get("lang", "uz")
    developer_line = DEVELOPER_TEXT.get(lang, DEVELOPER_TEXT["uz"])

    full_text = text + developer_line

    try:
        bio = build_qr_image(full_text)
        await update.message.reply_photo(photo=bio, caption={
            "uz": "🔹 Sizning QR kodingiz tayyor!",
            "ru": "🔹 Ваш QR-код готов!",
            "en": "🔹 Your QR code is ready!"
        }[lang])
    except Exception as e:
        await update.message.reply_text(f"Xatolik yuz berdi: {e}")

# ========== ADMIN COMMANDS ==========
def is_admin(user_id: int):
    return ADMIN_ID and user_id == ADMIN_ID

# /send <user_id> <message...>
async def admin_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Foydalanish: /send <user_id> <matn>")
        return
    target = args[0]
    text = " ".join(args[1:])
    try:
        await context.bot.send_message(chat_id=int(target), text=text)
        await update.message.reply_text("Xabar yuborildi.")
    except Exception as e:
        await update.message.reply_text(f"Xato: {e}")

# /broadcast <message...>
async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Foydalanish: /broadcast <matn>")
        return
    ok = 0
    fail = 0
    for uid, udata in list(users.items()):
        if udata.get("blocked"):
            continue
        try:
            await context.bot.send_message(chat_id=int(uid), text=text)
            ok += 1
        except Exception:
            fail += 1
    await update.message.reply_text(f"Yuborildi: {ok}, Xato: {fail}")

# /block <user_id>
async def admin_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Foydalanish: /block <user_id>")
        return
    uid = context.args[0]
    users.setdefault(uid, {"lang": "uz", "blocked": False, "last_active": None})
    users[uid]["blocked"] = True
    save_users(users)
    await update.message.reply_text(f"{uid} bloklandi.")

# /unblock <user_id>
async def admin_unblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Foydalanish: /unblock <user_id>")
        return
    uid = context.args[0]
    users.setdefault(uid, {"lang": "uz", "blocked": False, "last_active": None})
    users[uid]["blocked"] = False
    save_users(users)
    await update.message.reply_text(f"{uid} blokdan olindi.")

# /stats
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    total = len(users)
    blocked = len([1 for u in users.values() if u.get("blocked")])
    # online: last_active within ONLINE_SECONDS
    now = datetime.now(timezone.utc)
    online = 0
    today_count = 0
    for u in users.values():
        ts = u.get("last_active")
        if ts:
            try:
                t = datetime.fromisoformat(ts)
            except Exception:
                continue
            if (now - t).total_seconds() <= ONLINE_SECONDS:
                online += 1
            # daily active (same UTC date)
            if t.date() == now.date():
                today_count += 1
    await update.message.reply_text(
        f"📊 Statistika (faqat admin uchun):\n"
        f"Umumiy foydalanuvchilar: {total}\n"
        f"Bloklanganlar: {blocked}\n"
        f"Hozir onlayn (oxirgi {ONLINE_SECONDS}s): {online}\n"
        f"Bugungi faol foydalanuvchilar: {today_count}"
    )

# ========== MAIN APP ==========
def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    # language commands
    app.add_handler(CommandHandler("uz", cmd_set_lang))
    app.add_handler(CommandHandler("ru", cmd_set_lang))
    app.add_handler(CommandHandler("en", cmd_set_lang))
    # admin
    app.add_handler(CommandHandler("send", admin_send))
    app.add_handler(CommandHandler("broadcast", admin_broadcast))
    app.add_handler(CommandHandler("block", admin_block))
    app.add_handler(CommandHandler("unblock", admin_unblock))
    app.add_handler(CommandHandler("stats", admin_stats))
    # messages (text, media captions)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, make_qr_handler))
    app.add_handler(MessageHandler(filters.PHOTO, make_qr_handler))
    app.add_handler(MessageHandler(filters.VIDEO, make_qr_handler))

async def main():
    global application
    application = ApplicationBuilder().token(TOKEN).build()
    register_handlers(application)
    print("Bot ishga tushdi...")
    await application.run_polling()

if __name__ == "__main__":
    import asyncio
    # minimal checks
    if not TOKEN or ADMIN_ID == 0:
        print("Iltimos: BOT_TOKEN va ADMIN_ID muhit o'zgaruvchilarini o'rnating.")
    else:
        asyncio.run(main())