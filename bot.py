from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from datetime import datetime, time as dtime
import random

# 🔐 Replace with your NEW token from BotFather
TOKEN = "8279749975:AAHIe5YfA5RAPpQNbitbf9t1puHcY7u4NRk"

# A small list of random encouragement quotes
QUOTES = [
    "Water very nice right 🔥",
    "Coffee not counted btw ☕️",
    "Good job hongyi!",
    "study impt but water impt also!",
]

# We store user settings and scheduled jobs
SETTINGS = {}
JOBS = {}


# -------------------------
# Helper: parse AM/PM times
# -------------------------
def parse_times(input_text):
    """
    Takes a string like:
      '9:00 AM, 2:30 PM, 10 PM'
    and returns a list of datetime.time objects.
    """
    times = []
    invalid = []

    parts = [p.strip() for p in input_text.split(",") if p.strip()]

    for p in parts:
        parsed = None
        # Try formats: "9:00 PM" and "9 PM"
        for fmt in ["%I:%M %p", "%I %p"]:
            try:
                parsed = datetime.strptime(p, fmt).time()
                break
            except ValueError:
                continue
        if parsed is None:
            invalid.append(p)
        else:
            times.append(parsed)

    return times, invalid


# -------------------------
# /start – setup flow
# -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome! Let's set up your hydration reminder.\n\n"
        "1️⃣ Send me your friend's name."
    )
    context.user_data["step"] = "name"


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("step")

    # Step 1 — ask for name
    if step == "name":
        context.user_data["name"] = update.message.text
        context.user_data["step"] = "message"
        await update.message.reply_text("Great! What message should I send him?")

    # Step 2 — ask for message content
    elif step == "message":
        context.user_data["msg"] = update.message.text
        context.user_data["step"] = "times"
        await update.message.reply_text(
            "Nice! What times should I remind him each day?\n"
            "Example: 9:00 AM, 2:30 PM, 10 PM"
        )

    # Step 3 — ask for reminder times (AM/PM)
    elif step == "times":
        raw = update.message.text
        times, invalid = parse_times(raw)

        if invalid or not times:
            msg = "I couldn't understand these time(s): " + ", ".join(invalid) if invalid else "I couldn't understand any of the times."
            await update.message.reply_text(
                msg
                + "\n\nPlease try again in this format, e.g.:\n"
                  "`9:00 AM, 2:30 PM, 10 PM`",
                parse_mode="Markdown",
            )
            return

        uid = update.effective_user.id

        SETTINGS[uid] = {
            "name": context.user_data["name"],
            "msg": context.user_data["msg"],
            "times": times,  # list of datetime.time
        }

        context.user_data["step"] = None

        # Show the parsed times back to you
        pretty_times = ", ".join(t.strftime("%I:%M %p") for t in times)

        await update.message.reply_text(
            f"All set! I'll remind {SETTINGS[uid]['name']} at:\n"
            f"{pretty_times}\n\nUse /go to start sending reminders."
        )


# -------------------------
# Job callback – send reminder
# -------------------------
async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    uid = job.data["uid"]

    settings = SETTINGS.get(uid)
    if not settings:
        return

    name = settings["name"]
    msg = settings["msg"]

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("I drank 💧", callback_data=f"drank:{uid}")]
    ])

    await context.bot.send_message(
        chat_id=job.chat_id,
        text=f"{name}, {msg}",
        reply_markup=keyboard,
    )


# -------------------------
# /go – schedule daily reminders
# -------------------------
async def go(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if uid not in SETTINGS:
        await update.message.reply_text("Please run /start first.")
        return

    # Cancel old jobs (if any)
    if uid in JOBS:
        for job in JOBS[uid]:
            job.schedule_removal()

    jobs = []
    chat_id = update.effective_chat.id
    times = SETTINGS[uid]["times"]

    for t in times:
        job = context.application.job_queue.run_daily(
            callback=send_reminder,
            time=t,
            chat_id=chat_id,
            data={"uid": uid},
            name=f"hydration_{uid}_{t.strftime('%H%M')}",
        )
        jobs.append(job)

    JOBS[uid] = jobs

    pretty_times = ", ".join(t.strftime("%I:%M %p") for t in times)
    await update.message.reply_text(
        f"Hydration reminders scheduled daily at:\n{pretty_times} 🚰"
    )


# -------------------------
# Button callback: user drank
# -------------------------
async def drank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = int(query.data.split(":")[1])

    await query.answer()
    await query.edit_message_text(
        random.choice(QUOTES)
    )


# -------------------------
# Quote management commands
# -------------------------
async def addquote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)

    if not text:
        await update.message.reply_text("Usage: /addquote your quote here")
        return

    QUOTES.append(text)
    await update.message.reply_text(f"Added quote:\n\n{text}")


async def listquotes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not QUOTES:
        await update.message.reply_text("No quotes yet! Add some using /addquote")
        return

    msg = "Here are your quotes:\n\n"
    for i, q in enumerate(QUOTES, start=1):
        msg += f"{i}. {q}\n"

    await update.message.reply_text(msg)


async def removequote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /removequote number")
        return

    try:
        idx = int(context.args[0]) - 1
        deleted = QUOTES.pop(idx)
        await update.message.reply_text(f"Removed quote:\n\n{deleted}")
    except Exception:
        await update.message.reply_text("Invalid number.")


# -------------------------
# main()
# -------------------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("go", go))
    app.add_handler(CallbackQueryHandler(drank, pattern="^drank"))
    app.add_handler(
        # handle all normal text while setting up
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )
    app.add_handler(CommandHandler("addquote", addquote))
    app.add_handler(CommandHandler("listquotes", listquotes))
    app.add_handler(CommandHandler("removequote", removequote))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
