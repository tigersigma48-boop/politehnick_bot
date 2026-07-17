import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.effective_chat.id != ADMIN_CHAT_ID:
        await update.message.reply_text(
            "⛔️ Цей бот приватний."
        )
        return

    await update.message.reply_text(
        "✅ Бот працює.\n"
        "Команда /testpost опублікує тест у канал."
    )


async def id_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await update.message.reply_text(
        f"Твій chat_id: {update.effective_chat.id}"
    )


async def testpost_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.effective_chat.id != ADMIN_CHAT_ID:
        await update.message.reply_text(
            "⛔️ Цей бот приватний."
        )
        return

    try:
        sent_message = await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text="✅ Тестовий пост від бота «Політехнік».",
        )

        await update.message.reply_text(
            f"✅ Пост опубліковано.\n"
            f"message_id: {sent_message.message_id}"
        )

    except Exception as error:
        await update.message.reply_text(
            f"❌ Не вдалося опублікувати:\n{error}"
        )


def main() -> None:
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не знайдено.")
        return

    if not ADMIN_CHAT_ID:
        print("❌ ADMIN_CHAT_ID не знайдено.")
        return

    if not CHANNEL_ID:
        print("❌ CHANNEL_ID не знайдено.")
        return

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "id",
            id_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "testpost",
            testpost_command,
        )
    )

    print("✅ Бот запущений.")

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()