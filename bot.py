import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

# Настройки
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PORT = int(os.environ.get("PORT", 10000))

# Загрузка базы знаний
def load_knowledge():
    knowledge_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge.txt")
    try:
        with open(knowledge_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "База знаний пуста."

KNOWLEDGE = load_knowledge()

# Настройка Gemini
client = OpenAI(
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    api_key=GEMINI_API_KEY,
)

SYSTEM_PROMPT = f"""Ты — помощник, который отвечает на вопросы СТРОГО на основе базы знаний ниже.

Правила:
- Отвечай только на основе информации из базы знаний
- Если в базе знаний нет ответа — так и скажи: "В моей базе знаний нет информации по этому вопросу"
- Отвечай кратко, по делу, как будто пишешь в личных сообщениях
- Пиши на русском языке

БАЗА ЗНАНИЙ:
{KNOWLEDGE}
"""

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def run_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    server.serve_forever()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Отправь мне вопрос, и я отвечу на основе базы знаний."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    logger.info(f"Вопрос: {user_message}")

    try:
        response = client.chat.completions.create(
            model="gemini-2.0-flash",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )
        if response.choices and response.choices[0].message.content:
            answer = response.choices[0].message.content
        else:
            answer = "Пустой ответ. Попробуй ещё раз."
    except Exception as e:
        logger.error(f"Ошибка API: {type(e).__name__}: {e}")
        answer = f"Ошибка: {type(e).__name__}: {e}"

    await update.message.reply_text(answer)


def main():
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    logger.info(f"Health server запущен на порту {PORT}")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Бот запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
