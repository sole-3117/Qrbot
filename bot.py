import json
from io import BytesIO
import qrcode
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Admin ID
ADMIN_ID = 6887251996 # Bu yerga sizning Telegram ID'ingiz

# Foydalanuvchilarni yuklash
try:
    with open("users.json", "r", encoding="utf-8") as f:
        users = json.load(f)
except:
    users = {}

# Til tanlash menyusi
lang_keyboard = ReplyKeyboardMarkup([["UZ", "RU", "EN"]], resize_keyboard=True)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    # Agar yangi foydalanuvchi bo'lsa adminga xabar
    if user_id not in users:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"Yangi foydalanuvchi: {update.message.from_user.full_name} ({user_id})"
        )
        users[user_id] = {"lang": None, "blocked": False}
        save_users()
    await update.message.reply_text("Tilni tanlang / Choose language / Выберите язык:", reply_markup=lang_keyboard)

# Tilni tanlash
async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    lang = update.message.text.lower()
    if lang in ["uz", "ru", "en"]:
        users[user_id]["lang"] = lang
        save_users()
        msg = {
            "uz": "Endi matn yuboring, men QR kod qilaman!",
            "ru": "Теперь отправьте текст, я создам QR код!",
            "en": "Now send the text, I will generate a QR code!"
        }
        await update.message.reply_text(msg[lang])

# QR yaratish
async def qr_yarat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if users.get(user_id, {}).get("blocked", False):
        return  # Agar foydalanuvchi bloklangan bo'lsa ishlamaydi
    lang = users.get(user_id, {}).get("lang", "uz")
    matn = update.message.text

    # QR matnini dasturchi info bilan birlashtirish
    info = {
        "uz": "\n\nDasturchi: @adashovsolejonoffical",
        "ru": "\n\nРазработчик: @adashovsolejonoffical",
        "en": "\n\nDeveloper: @adashovsolejonoffical"
    }
    matn += info[lang]

    # QR yaratish
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(matn)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = BytesIO()
    bio.name = "qr_code.png"
    img.save(bio, "PNG")
    bio.seek(0)
    await update.message.reply_photo(bio, caption="QR kod tayyor ✅")

# Admin komandasi: xabar yuborish
async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return
    text = update.message.text.replace("/broadcast ", "")
    count = 0
    for uid, data in users.items():
        if not data.get("blocked", False):
            try:
                await context.bot.send_message(chat_id=int(uid), text=text)
                count += 1
            except:
                pass
    await update.message.reply_text(f"Xabar {count} foydalanuvchiga yuborildi.")

# Admin komandasi: statistika
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return
    total = len(users)
    blocked = len([u for u in users.values() if u.get("blocked", False)])
    active = total - blocked
    await update.message.reply_text(
        f"📊 Statistika:\nUmumiy: {total}\nFaol: {active}\nBloklangan: {blocked}"
    )

# Foydalanuvchilarni saqlash
def save_users():
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)

# Main
async def main():
    TOKEN = "8504094462:AAGFn1wk-fA5ueBXzaqQhR3dx14JSfJ4Lfk"
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^(UZ|RU|EN)$"), set_language))
    app.add_handler(CommandHandler("broadcast", admin_broadcast))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, qr_yarat))

    print("Bot ishga tushdi...")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())