import os
import json
from datetime import datetime, timezone, timedelta
from io import BytesIO
import qrcode

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ===== CONFIG =====
TOKEN = "8504094462:AAGFn1wk-fA5ueBXzaqQhR3dx14JSfJ4Lfk"  # O'z TOKENingizni shu yerga yozing
ADMIN_ID = 6887251996  # O'z Telegram ID raqamingiz
USERS_FILE = "users.json"
ONLINE_SECONDS = 300  # onlayn deb hisoblash vaqti

# Tilga mos "Dasturchi" matni
DEVELOPER_TEXT = {
    "uz": "\n\nDasturchi: @adashovsolejonoffical",
    "ru": "\n\nРазработчик: @adashovsolejonoffical",
    "en": "\n\nDeveloper: @adashovsolejonoffical",
}

# Tillar tugmalari
LANG_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton("🇺🇿 UZ"), KeyboardButton("🇷🇺 RU"), KeyboardButton("🇬🇧 EN")]],
    resize_keyboard=True
)

# ===== Users management =====
def load_users():
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

users = load_users()

def ensure_user(user_id: str, fullname: str = None):
    if user_id not in users:
        users[user_id] = {"lang": "uz", "blocked": False, "last_active": None}
        save_users(users)
        # notify admin
        try:
            application.bot.send_message(chat_id=ADMIN_ID, text=f"🆕 Yangi foydalanuvchi: {fullname} ({user_id})")
        except:
            pass

def update_last_active(user_id: str):
    users.setdefault(user_id, {"lang": "uz", "blocked": False, "last_active": None})
    users[user_id]["last_active"] = datetime.now(timezone.utc).isoformat()
    save_users(users)

# ===== Helper =====
def norm_lang(text: str):
    t = text.lower()
    if "uz" in t or "🇺🇿" in t: return "uz"
    if "ru" in t or "🇷🇺" in t: return "ru"
    if "en" in t or "🇬🇧" in t: return "en"
    return None

# ===== Handlers =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(str(user.id), user.full_name)
    update_last_active(str(user.id))
    await update.message.reply_text(
        "Salom! Tilni tanlang / Выберите язык / Choose a language:",
        reply_markup=LANG_KEYBOARD
    )

async def cmd_set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text
    chosen = norm_lang(text.replace("/", ""))
    if not chosen: chosen = norm_lang(text)
    if not chosen:
        await update.message.reply_text("Tilni tanlang: UZ / RU / EN")
        return
    users.setdefault(user_id, {"lang": "uz", "blocked": False, "last_active": None})
    users[user_id]["lang"] = chosen
    save_users(users)
    update_last_active(user_id)
    msgs = {
        "uz": "Til o'rnatildi: Oʻzbekcha. Endi matn yoki media yuboring — men QR yarataman.",
        "ru": "Язык установлен: Русский. Отправьте текст или медиа — я создам QR-код.",
        "en": "Language set: English. Send text or media — I will generate a QR code."
    }
    await update.message.reply_text(msgs[chosen])

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
    user_id = str(update.effective_user.id)
    ensure_user(user_id, update.effective_user.full_name)
    update_last_active(user_id)
    if users.get(user_id, {}).get("blocked", False): return

    text = update.message.text or update.message.caption
    if not text:
        await update.message.reply_text(
            "Matn yoki media caption yuboring, QR uchun matn kerak."
        )
        return

    lang = users.get(user_id, {}).get("lang", "uz")
    full_text = text + DEVELOPER_TEXT.get(lang, DEVELOPER_TEXT["uz"])
    try:
        bio = build_qr_image(full_text)
        await update.message.reply_photo(photo=bio, caption={
            "uz": "🔹 Sizning QR kodingiz tayyor!",
            "ru": "🔹 Ваш QR-код готов!",
            "en": "🔹 Your QR code is ready!"
        }[lang])
    except Exception as e:
        await update.message.reply_text(f"Xatolik yuz berdi: {e}")

# ===== Admin =====
def is_admin(user_id: int): return user_id == ADMIN_ID

async def admin_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if len(context.args) < 2:
        await update.message.reply_text("/send <user_id> <matn>")
        return
    uid = context.args[0]; text = " ".join(context.args[1:])
    try: await context.bot.send_message(chat_id=int(uid), text=text); await update.message.reply_text("Xabar yuborildi.")
    except Exception as e: await update.message.reply_text(f"Xato: {e}")

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    text = " ".join(context.args); ok = fail = 0
    for uid, u in list(users.items()):
        if u.get("blocked"): continue
        try: await context.bot.send_message(chat_id=int(uid), text=text); ok += 1
        except: fail += 1
    await update.message.reply_text(f"Yuborildi: {ok}, Xato: {fail}")

async def admin_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not context.args: await update.message.reply_text("/block <user_id>"); return
    uid = context.args[0]; users.setdefault(uid, {"lang": "uz", "blocked": False, "last_active": None}); users[uid]["blocked"] = True; save_users(users)
    await update.message.reply_text(f"{uid} bloklandi.")

async def admin_unblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not context.args: await update.message.reply_text("/unblock <user_id>"); return
    uid = context.args[0]; users.setdefault(uid, {"lang": "uz", "blocked": False, "last_active": None}); users[uid]["blocked"] = False; save_users(users)
    await update.message.reply_text(f"{uid} blokdan olindi.")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    now = datetime.now(timezone.utc); total = len(users); blocked = len([1 for u in users.values() if u.get("blocked")])
    online = today = 0
    for u in users.values():
        ts = u.get("last_active")
        if ts:
            try: t = datetime.fromisoformat(ts)
            except: continue
            if (now - t).total_seconds() <= ONLINE_SECONDS: online += 1
            if t.date() == now.date(): today += 1
    await update.message.reply_text(
        f"📊 Statistika (faqat admin uchun):\n"
        f"Umumiy foydalanuvchilar: {total}\n"
        f"Bloklanganlar: {blocked}\n"
        f"Hozir onlayn: {online}\n"
        f"Bugungi faol foydalanuvchilar: {today}"
    )

# ===== Main =====
def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("uz", cmd_set_lang))
    app.add_handler(CommandHandler("ru", cmd_set_lang))
    app.add_handler(CommandHandler("en", cmd_set_lang))
    app.add_handler(CommandHandler("send", admin_send))
    app.add_handler(CommandHandler("broadcast", admin_broadcast))
    app.add_handler(CommandHandler("block", admin_block))
    app.add_handler(CommandHandler("unblock", admin_unblock))
    app.add_handler(CommandHandler("stats", admin_stats))
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
    asyncio.run(main())
