"""
MMM Samarqand — HR bot (Telegram) + AI Tahlil va Kengaytirilgan Anketa
----------------------------------------------------------------------
"""

import csv
import io
import logging
import sqlite3
import os
from datetime import datetime
import openai

from telegram import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# ======================= SOZLAMALAR =======================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = 394044965

# OpenAI API kalitingizni shu yerga yozasiz (AI tahlil ishlashi uchun shart)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_PATH = "arizalar.db"
# ============================================================

# OpenAI mijozini sozlash
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Suhbat bosqichlari (FSM)
(
    NAME,
    BIRTH_DATE,
    PHONE,
    PHOTO,
    VIDEO_NOTE,
    DURATION,
    LAST_WORKPLACE,
    REFERENCE,
    PREV_SALARY,
    EXPECTED_SALARY,
    SITUATIONAL,
    CONFIRM,
) = range(12)


def init_db() -> None:
    """Ariza saqlanadigan jadvalni yaratadi (agar mavjud bo'lmasa)."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS arizalar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            full_name TEXT,
            birth_date TEXT,
            phone TEXT,
            duration TEXT,
            last_workplace TEXT,
            reference TEXT,
            prev_salary TEXT,
            expected_salary TEXT,
            situational TEXT,
            ai_analysis TEXT,
            created_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def save_application(data: dict) -> int:
    """Arizani bazaga yozadi va uning id raqamini qaytaradi."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        """
        INSERT INTO arizalar
            (user_id, full_name, birth_date, phone, duration, last_workplace, reference, prev_salary, expected_salary, situational, ai_analysis, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["user_id"],
            data["full_name"],
            data["birth_date"],
            data["phone"],
            data["duration"],
            data["last_workplace"],
            data["reference"],
            data["prev_salary"],
            data["expected_salary"],
            data["situational"],
            data.get("ai_analysis", ""),
            datetime.now().strftime("%Y-%m-%d %H:%M"),
        ),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


# ------------------------- Suhbat oqimi -------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Assalomu alaykum! Samarqand Sweets jamoasining bo'sh ish o'rinlari uchun nomzodlarni saralash botiga xush kelibsiz.\n\n"
        "Jamoamizga qo'shilish uchun bir nechta savolga javob bering.\n"
        "Istalgan vaqtda /bekor_qilish buyrug'i orqali to'xtatishingiz mumkin.\n\n"
        "To'liq F.I.Sh. (Familiya, Ism, Sharifingiz)ni yozib yuboring:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["full_name"] = update.message.text.strip()
    await update.message.reply_text("Tug'ilgan kuningiz va yoshingiz nechada? (Masalan: 15.08.2003)")
    return BIRTH_DATE


async def get_birth_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["birth_date"] = update.message.text.strip()
    
    contact_button = KeyboardButton("📱 Telefon raqamni ulashish", request_contact=True)
    keyboard = ReplyKeyboardMarkup([[contact_button]], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "Biz bilan bog'lanishimiz uchun telefon raqamingizni yuboring (pastdagi tugmani bosing):",
        reply_markup=keyboard,
    )
    return PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text.strip()
    context.user_data["phone"] = phone

    await update.message.reply_text(
        "Iltimos, o'zingizning oxirgi tushgan aniq rasmingizni (selfi yoki shaxsiy foto) yuboring:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return PHOTO


async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.photo:
        await update.message.reply_text("Iltimos, shaxsiy rasmingizni rasm ko'rinishida yuboring!")
        return PHOTO
    
    context.user_data["photo"] = update.message.photo[-1].file_id
    await update.message.reply_text(
        "Endi esa botga **dumaloq video formatida** (video-kruglyash) 30 soniyadan 1 minutgacha xabar yuboring: "
        "O'zingiz haqingizda qisqacha, tajribangiz va nima uchun aynan bizning kompaniyada ishlamoqchiligingizni gapirib bering."
    )
    return VIDEO_NOTE


async def get_video_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.video_note:
        await update.message.reply_text("Iltimos, aynan **dumaloq video** (video-kruglyash) formatida xabar yuboring!")
        return VIDEO_NOTE

    context.user_data["video_note"] = update.message.video_note.file_id
    await update.message.reply_text(
        "Bizning jamoamizda kamida qancha muddat davomida uzluksiz ishlashni rejalashtiryapsiz? "
        "(Masalan: 1 yil, 3 yil va hokazo)"
    )
    return DURATION


async def get_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["duration"] = update.message.text.strip()
    await update.message.reply_text("Oxirgi bo'lib qaysi korxona yoki tashkilotda ishlagansiz va lavozimingiz qanday edi?")
    return LAST_WORKPLACE


async def get_last_workplace(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["last_workplace"] = update.message.text.strip()
    await update.message.reply_text(
        "Siz haqingizda xarakteristika/fikr olishimiz uchun oxirgi ish joyingizdagi rahbar "
        "yoki mas'ul shaxsning F.I.Sh. va telefon raqamini yozib qoldiring:"
    )
    return REFERENCE


async def get_reference(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["reference"] = update.message.text.strip()
    await update.message.reply_text("Oxirgi ish joyingizda taxminan qancha oylik/daromad olib ishlagansiz?")
    return PREV_SALARY


async def get_prev_salary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["prev_salary"] = update.message.text.strip()
    await update.message.reply_text("Bizning jamoamizda qancha oylik evaziga to'laqonli ishlashni xohlardingiz?")
    return EXPECTED_SALARY


async def get_expected_salary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["expected_salary"] = update.message.text.strip()
    await update.message.reply_text(
        "🧠 **Oxirgi savol (Situatsion vaziyat):**\n\n"
        "Tasavvur qiling: Ish kuni qizg'in pallada, tayyor mahsulotni jo'natish vaqti keldi, lekin kutilmaganda xatolik chiqdi yoki nuqson sezildi. "
        "Sizning birinchi harakatingiz qanday bo'ladi va bu vaziyatda mas'uliyatni qanday olasiz?"
    )
    return SITUATIONAL


async def get_situational(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["situational"] = update.message.text.strip()
    d = context.user_data

    await update.message.reply_text(
        "Rahmat! Barcha ma'lumotlar qabul qilindi. AI (Sun'iy intellekt) orqali tahlil qilinmoqda, ozgina kuting..."
    )

    # OpenAI orqali tahlil qilish
    ai_prompt = f"""
    Sen Samarqand Sweets (qandolat mahsulotlari ishlab chiqarish) korxonasining bosh HR menejerisan. 
    Bizga uzoq muddatli, mas'uliyatli va barqaror xodim kerak. Quyidagi nomzod ma'lumotlarini tahlil qilib, professional xulosa yozib ber:
    
    - F.I.Sh: {d.get('full_name')}
    - Tug'ilgan sana/Yosh: {d.get('birth_date')}
    - Tel: {d.get('phone')}
    - Rejalashtirilgan ishlash muddati: {d.get('duration')}
    - Oxirgi ish joyi va lavozimi: {d.get('last_workplace')}
    - Tavsiyanoma uchun aloqa: {d.get('reference')}
    - Oldingi oyligi: {d.get('prev_salary')}
    - Talab qilinayotgan oylik: {d.get('expected_salary')}
    - Situatsion savolga javobi: {d.get('situational')}
    
    Vazifang:
    1. Nomzodni 10 ballik tizimda bahola.
    2. Uning kuchli va xavfli/zaif tomonlarini ko'rsat.
    3. Suhbatga chaqirish tavsiya etiladimi yoki yo'q, aniq qaror yoz (Tavsiya etiladi / Rad etiladi).
    """

    ai_analysis = "AI tahlili amalga oshmadi."
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": ai_prompt}],
            temperature=0.7,
        )
        ai_analysis = response.choices[0].message.content
    except Exception as e:
        ai_analysis = f"AI xatolik yuz berdi: {str(e)}"

    d["ai_analysis"] = ai_analysis
    d["user_id"] = update.effective_user.id
    
    # Bazaga saqlash
    app_id = save_application(d)

    await update.message.reply_text(
        "Arizangiz muvaffaqiyatli topshirildi! HR bo'limi uni ko'rib chiqib, siz bilan tez orada bog'lanadi.",
        reply_markup=ReplyKeyboardRemove(),
    )

    # Adminga xabar yuborish
    if ADMIN_CHAT_ID:
        admin_text = (
            f"🆕 **Yangi ariza (#{app_id})**\n\n"
            f"👤 **F.I.Sh:** {d['full_name']}\n"
            f"📅 **Tug'ilgan sana:** {d['birth_date']}\n"
            f"📱 **Telefon:** {d['phone']}\n"
            f"⏳ **Muddat:** {d['duration']}\n"
            f"🏢 **Oxirgi ish:** {d['last_workplace']}\n"
            f"📞 **Tavsiyanoma tel:** {d['reference']}\n"
            f"💰 **Oldingi oylik:** {d['prev_salary']} | **Kutilayotgan:** {d['expected_salary']}\n\n"
            f"🧠 **Situatsion javob:** {d['situational']}\n\n"
            f"🤖 **AI Tahlili va Xulosasi:**\n{ai_analysis}"
        )
        try:
            # Rasm va dumaloq videoni adminga yuborish
            await context.bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=d['photo'], caption=admin_text, parse_mode="Markdown")
            await context.bot.send_video_note(chat_id=ADMIN_CHAT_ID, video_note=d['video_note'])
        except Exception as e:
            logger.error(f"Adminga media yuborishda xatolik: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Ariza bekor qilindi. Qaytadan boshlash uchun /start yozing.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# ------------------------- Admin buyruqlari -------------------------

async def applications_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, full_name, phone, expected_salary, created_at "
        "FROM arizalar ORDER BY id DESC LIMIT 10"
    ).fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Hozircha arizalar yo'q.")
        return

    lines = ["📋 Oxirgi arizalar:\n"]
    for r in rows:
        lines.append(f"#{r[0]} — {r[1]} | Tel: {r[2]} | So'ralgan oylik: {r[3]} | Vaqti: {r[4]}")
    await update.message.reply_text("\n".join(lines))


async def export_csv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.id != ADMIN_CHAT_ID:
        return

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT * FROM arizalar ORDER BY id DESC").fetchall()
    columns = [d[0] for d in conn.execute("SELECT * FROM arizalar").description]
    conn.close()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    writer.writerows(rows)
    buffer.seek(0)

    data = io.BytesIO(buffer.getvalue().encode("utf-8-sig"))
    data.name = f"arizalar_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    await update.message.reply_document(document=data)


# ------------------------- Ishga tushirish -------------------------

def main() -> None:
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            BIRTH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birth_date)],
            PHONE: [MessageHandler(filters.CONTACT | filters.TEXT & ~filters.COMMAND, get_phone)],
            PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
            VIDEO_NOTE: [MessageHandler(filters.VIDEO_NOTE, get_video_note)],
            DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_duration)],
            LAST_WORKPLACE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_last_workplace)],
            REFERENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_reference)],
            PREV_SALARY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_prev_salary)],
            EXPECTED_SALARY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_expected_salary)],
            SITUATIONAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_situational)],
        },
        fallbacks=[CommandHandler("bekor_qilish", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("arizalar", applications_list))
    application.add_handler(CommandHandler("export", export_csv))

    logger.info("Bot ishga tushdi...")
    application.run_polling()


if __name__ == "__main__":
    main()
