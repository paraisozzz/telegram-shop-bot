import asyncio
import json
import logging
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict
from urllib.parse import urlparse

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Product:
    code: str
    title: str
    description: str
    price_stars: int
    price_rub: int
    delivery_text: str


BOT_TOKEN = os.getenv("BOT_TOKEN", "")
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
PORT = int(os.getenv("PORT", "10000"))
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "lotus762001").replace("@", "")
SHOP_TITLE = os.getenv("SHOP_TITLE", "Заработок на нейросетях")
SHOP_TEXT = os.getenv("SHOP_TEXT", "Выберите товар и удобный способ оплаты.")
DB_PATH = Path(os.getenv("DB_PATH", "bot_data.sqlite3"))

PRODUCTS: Dict[str, Product] = {
    "p1": Product(
        code="p1",
        title="1000 ПРОМПТОВ ДЛЯ ЗАРАБОТКА С CHATGPT",
        description="Готовые запросы для заработка на текстах, контенте, маркетинге, переводах, идеях и онлайн-услугах.",
        price_stars=299,
        price_rub=410,
        delivery_text="Спасибо за покупку!\n\nВаш цифровой продукт готов к скачиванию:\nhttps://clck.ru/3SnYDx\n\nСохраните файл себе на устройство.\nЕсли возникнут вопросы, напишите в поддержку: @lotus762001",
    ),
    "p2": Product(
        code="p2",
        title="50 СПОСОБОВ ЗАРАБОТАТЬ НА НЕЙРОСЕТЯХ В 2026 ГОДУ",
        description="Сборник актуальных идей и пошаговых схем заработка с помощью искусственного интеллекта.",
        price_stars=289,
        price_rub=400,
        delivery_text="Спасибо за покупку!\n\nВаш цифровой продукт готов к скачиванию:\nhttps://clck.ru/3SnYqW\n\nСохраните файл себе на устройство.\nЕсли возникнут вопросы, напишите в поддержку: @lotus762001",
    ),
    "p3": Product(
        code="p3",
        title="365 ИДЕЙ КОНТЕНТА ДЛЯ TELEGRAM / TIKTOK / REELS",
        description="Готовый план постов и видео на каждый день для роста подписчиков и заработка на контенте.",
        price_stars=289,
        price_rub=405,
        delivery_text="Спасибо за покупку!\n\nВаш цифровой продукт готов к скачиванию:\nhttps://clck.ru/3SnZUN\n\nСохраните файл себе на устройство.\nЕсли возникнут вопросы, напишите в поддержку: @lotus762001",
    ),
    "p4": Product(
        code="p4",
        title="КАК ДЕЛАТЬ AI-ВИДЕО И ЗАРАБАТЫВАТЬ НА НИХ",
        description="Пошаговая инструкция по созданию AI-видео и заработку на коротких видео, контенте и цифровых продуктах.",
        price_stars=279,
        price_rub=390,
        delivery_text="Спасибо за покупку!\n\nВаш цифровой продукт готов к скачиванию:\nhttps://clck.ru/3SnZgq\n\nСохраните файл себе на устройство.\nЕсли возникнут вопросы, напишите в поддержку: @lotus762001",
    ),
    "bundle": Product(
        code="bundle",
        title="ВСЕ 4 ТОВАРА ВМЕСТЕ",
        description="Все 4 продукта одним пакетом: промпты, способы заработка, идеи контента и AI-видео.",
        price_stars=1156,
        price_rub=1605,
        delivery_text="Спасибо за покупку!\n\nВаш комплект готов к скачиванию:\n\n1) https://clck.ru/3SnYDx\n2) https://clck.ru/3SnYqW\n3) https://clck.ru/3SnZUN\n4) https://clck.ru/3SnZgq\n\nСохраните файлы себе на устройство.\nЕсли возникнут вопросы, напишите в поддержку: @lotus762001",
    ),
}

APP_LOOP: asyncio.AbstractEventLoop | None = None
APPLICATION: Application | None = None


def validate_config() -> None:
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not YOOKASSA_SHOP_ID:
        missing.append("YOOKASSA_SHOP_ID")
    if not YOOKASSA_SECRET_KEY:
        missing.append("YOOKASSA_SECRET_KEY")
    if not PUBLIC_BASE_URL:
        missing.append("PUBLIC_BASE_URL")
    if missing:
        raise ValueError(f"Не заданы переменные окружения: {', '.join(missing)}")


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                product_code TEXT NOT NULL,
                product_title TEXT NOT NULL,
                source TEXT NOT NULL,
                amount TEXT NOT NULL,
                payment_id TEXT NOT NULL UNIQUE,
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def purchase_exists(payment_id: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT 1 FROM purchases WHERE payment_id = ? LIMIT 1",
            (payment_id,),
        ).fetchone()
    return row is not None


def save_purchase(user_id: int, username: str | None, product: Product, amount: str, payment_id: str, source: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO purchases
            (user_id, username, product_code, product_title, source, amount, payment_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, username or "", product.code, product.title, source, amount, payment_id),
        )
        conn.commit()


def get_user_purchases(user_id: int) -> list[str]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT product_title
            FROM purchases
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()
    return [row[0] for row in rows]


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🛍 Магазин", callback_data="menu:shop")],
            [InlineKeyboardButton("📦 Мои покупки", callback_data="menu:orders")],
            [InlineKeyboardButton("ℹ️ О продуктах", callback_data="menu:about")],
            [InlineKeyboardButton("💬 Поддержка", callback_data="menu:support")],
        ]
    )


def shop_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for code in ["p1", "p2", "p3", "p4", "bundle"]:
        product = PRODUCTS[code]
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{product.title} — ⭐ {product.price_stars} / {product.price_rub} ₽",
                    callback_data=f"product:{code}",
                )
            ]
        )
    rows.append([InlineKeyboardButton("⬅️ В главное меню", callback_data="menu:main")])
    return InlineKeyboardMarkup(rows)


def product_keyboard(product: Product) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"⭐ Купить за {product.price_stars}", callback_data=f"buy_stars:{product.code}")],
            [InlineKeyboardButton(f"💳 Оплатить {product.price_rub} ₽", callback_data=f"buy_rub:{product.code}")],
            [InlineKeyboardButton("🛍 Назад в магазин", callback_data="menu:shop")],
            [InlineKeyboardButton("⬅️ Главное меню", callback_data="menu:main")],
        ]
    )


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Главное меню", callback_data="menu:main")]])


def start_message() -> str:
    return (
        f"{SHOP_TITLE}\n\n"
        "Добро пожаловать в магазин по заработку на нейросетях.\n"
        "Здесь можно купить продукты за Telegram Stars или оплатить в рублях с автоматической выдачей.\n\n"
        "Выберите раздел ниже."
    )


def shop_message() -> str:
    lines = [f"🛍 {SHOP_TITLE}", "", SHOP_TEXT, ""]
    for i, code in enumerate(["p1", "p2", "p3", "p4", "bundle"], start=1):
        product = PRODUCTS[code]
        lines.append(f"{i}. {product.title}")
        lines.append(f"Цена: ⭐ {product.price_stars} или {product.price_rub} ₽")
        lines.append("")
    lines.append("Нажмите на товар, чтобы открыть описание и выбрать способ оплаты.")
    return "\n".join(lines)


def product_message(product: Product) -> str:
    return (
        f"{product.title}\n\n"
        f"{product.description}\n\n"
        f"Цена в Telegram: ⭐ {product.price_stars}\n"
        f"Цена в рублях: {product.price_rub} ₽\n\n"
        "После успешной оплаты товар отправляется автоматически."
    )


def about_message() -> str:
    return (
        "ℹ️ О продуктах\n\n"
        "В этом боте собраны цифровые продукты по заработку на нейросетях:\n"
        "— промпты ChatGPT\n"
        "— идеи контента\n"
        "— способы заработка\n"
        "— AI-видео\n\n"
        "Доступны 2 способа оплаты:\n"
        "⭐ Telegram Stars\n"
        "💳 Рубли через ЮKassa"
    )


def support_message() -> str:
    return (
        "💬 Поддержка\n\n"
        f"Если возникли вопросы по оплате или доступу к материалам, напишите: @{SUPPORT_USERNAME}\n\n"
        "В сообщении укажите:\n"
        "— дату покупки\n"
        "— название товара\n"
        "— ваш username"
    )


def orders_message(user_id: int) -> str:
    purchases = get_user_purchases(user_id)
    if not purchases:
        return "📦 У вас пока нет покупок.\n\nОткройте магазин и выберите первый продукт."
    lines = ["📦 Ваши покупки", ""]
    for title in purchases:
        lines.append(f"— {title}")
    return "\n".join(lines)


async def send_delivery(user_id: int, product: Product) -> None:
    if APPLICATION is None:
        return
    await APPLICATION.bot.send_message(chat_id=user_id, text=product.delivery_text)
    await APPLICATION.bot.send_message(
        chat_id=user_id,
        text="✨ Оплата прошла успешно.\n\nЕсли хотите, можете выбрать другие товары:",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🛍 Открыть магазин", callback_data="menu:shop")],
                [InlineKeyboardButton("💬 Поддержка", url=f"https://t.me/{SUPPORT_USERNAME}")],
            ]
        ),
    )


async def create_yookassa_payment(user_id: int, username: str | None, product: Product) -> str:
    payload = {
        "amount": {
            "value": f"{Decimal(product.price_rub):.2f}",
            "currency": "RUB",
        },
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": "https://t.me/Zarabotok49_bot",
        },
        "description": product.title,
        "metadata": {
            "product_code": product.code,
            "telegram_user_id": str(user_id),
            "telegram_username": username or "",
        },
    }
    headers = {
        "Idempotence-Key": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.yookassa.ru/v3/payments",
            auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY),
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
    return data["confirmation"]["confirmation_url"]


class WebhookHandler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, payload: dict) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_json(200, {"ok": True, "service": "telegram-shop-bot"})
        else:
            self._send_json(404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/yookassa/webhook":
            self._send_json(404, {"ok": False, "error": "not_found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "invalid_json"})
            return

        try:
            event = payload.get("event")
            obj = payload.get("object", {})
            status = obj.get("status")
            payment_id = obj.get("id")
            metadata = obj.get("metadata", {}) or {}
            product_code = metadata.get("product_code")
            user_id_raw = metadata.get("telegram_user_id")

            if event != "payment.succeeded" or status != "succeeded":
                self._send_json(200, {"ok": True, "ignored": True})
                return

            if not payment_id or not product_code or not user_id_raw:
                self._send_json(400, {"ok": False, "error": "missing_metadata"})
                return

            if purchase_exists(payment_id):
                self._send_json(200, {"ok": True, "duplicate": True})
                return

            product = PRODUCTS.get(product_code)
            if not product:
                self._send_json(400, {"ok": False, "error": "unknown_product"})
                return

            user_id = int(user_id_raw)
            username = metadata.get("telegram_username", "")
            amount = str(obj.get("amount", {}).get("value", product.price_rub))

            save_purchase(
                user_id=user_id,
                username=username,
                product=product,
                amount=amount,
                payment_id=payment_id,
                source="yookassa",
            )

            if APP_LOOP is not None:
                asyncio.run_coroutine_threadsafe(send_delivery(user_id, product), APP_LOOP)

            self._send_json(200, {"ok": True})
        except Exception as exc:
            logger.exception("Webhook error: %s", exc)
            self._send_json(500, {"ok": False, "error": "server_error"})


def start_web_server() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), WebhookHandler)
    logger.info("Webhook server started on port %s", PORT)
    server.serve_forever()


async def post_init(application: Application) -> None:
    global APP_LOOP, APPLICATION
    APP_LOOP = asyncio.get_running_loop()
    APPLICATION = application


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    arg = context.args[0] if context.args else ""
    if arg.startswith("product_"):
        code = arg.replace("product_", "", 1)
        product = PRODUCTS.get(code)
        if product and update.message:
            await update.message.reply_text(product_message(product), reply_markup=product_keyboard(product))
            return

    if arg.startswith("payrub_"):
        code = arg.replace("payrub_", "", 1)
        product = PRODUCTS.get(code)
        if product and update.effective_user and update.message:
            try:
                payment_url = await create_yookassa_payment(
                    user_id=update.effective_user.id,
                    username=update.effective_user.username,
                    product=product,
                )
                await update.message.reply_text(
                    f"{product.title}\n\nОплата в рублях: {product.price_rub} ₽\n\nПосле успешной оплаты товар придёт автоматически.",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [InlineKeyboardButton("💳 Перейти к оплате", url=payment_url)],
                            [InlineKeyboardButton("⬅️ В главное меню", callback_data="menu:main")],
                        ]
                    ),
                )
                return
            except Exception as exc:
                logger.exception("YooKassa create payment error: %s", exc)
                await update.message.reply_text("Не удалось создать платёж. Попробуйте ещё раз позже.", reply_markup=back_keyboard())
                return

    if update.message:
        await update.message.reply_text(start_message(), reply_markup=main_menu_keyboard())


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    _, key = query.data.split(":", 1)

    if key == "main":
        await query.message.edit_text(start_message(), reply_markup=main_menu_keyboard())
    elif key == "shop":
        await query.message.edit_text(shop_message(), reply_markup=shop_keyboard())
    elif key == "about":
        await query.message.edit_text(about_message(), reply_markup=back_keyboard())
    elif key == "support":
        await query.message.edit_text(support_message(), reply_markup=back_keyboard())
    elif key == "orders":
        user_id = update.effective_user.id if update.effective_user else 0
        await query.message.edit_text(orders_message(user_id), reply_markup=back_keyboard())


async def product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    _, code = query.data.split(":", 1)
    product = PRODUCTS.get(code)
    if not product:
        await query.message.edit_text("Товар не найден.", reply_markup=shop_keyboard())
        return
    await query.message.edit_text(product_message(product), reply_markup=product_keyboard(product))


async def buy_stars(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message:
        return
    await query.answer()
    _, code = query.data.split(":", 1)
    product = PRODUCTS.get(code)
    if not product:
        await query.message.reply_text("Товар не найден.")
        return

    prices = [LabeledPrice(label=product.title, amount=product.price_stars)]
    await context.bot.send_invoice(
        chat_id=query.message.chat_id,
        title=product.title,
        description=product.description,
        payload=product.code,
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter=product.code,
    )


async def buy_rub(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user:
        return
    await query.answer()
    _, code = query.data.split(":", 1)
    product = PRODUCTS.get(code)
    if not product:
        await query.message.reply_text("Товар не найден.")
        return

    try:
        payment_url = await create_yookassa_payment(
            user_id=update.effective_user.id,
            username=update.effective_user.username,
            product=product,
        )
    except Exception as exc:
        logger.exception("YooKassa create payment error: %s", exc)
        await query.message.reply_text("Не удалось создать платёж. Попробуйте ещё раз позже.")
        return

    await query.message.reply_text(
        f"{product.title}\n\nОплата в рублях: {product.price_rub} ₽\n\nПосле успешной оплаты товар придёт автоматически.",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("💳 Перейти к оплате", url=payment_url)],
                [InlineKeyboardButton("🛍 Открыть магазин", callback_data="menu:shop")],
            ]
        ),
    )


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.pre_checkout_query
    if not query:
        return
    if query.invoice_payload not in PRODUCTS:
        await query.answer(ok=False, error_message="Товар не найден. Попробуйте снова.")
        return
    await query.answer(ok=True)


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.successful_payment or not update.effective_user:
        return

    payment = message.successful_payment
    product = PRODUCTS.get(payment.invoice_payload)
    if not product:
        await message.reply_text("Оплата прошла, но товар не найден. Напишите в поддержку.")
        return

    payment_id = payment.telegram_payment_charge_id
    if not purchase_exists(payment_id):
        save_purchase(
            user_id=update.effective_user.id,
            username=update.effective_user.username,
            product=product,
            amount=str(payment.total_amount),
            payment_id=payment_id,
            source="stars",
        )

    await send_delivery(update.effective_user.id, product)


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text("Используйте /start для открытия главного меню.", reply_markup=main_menu_keyboard())


def main() -> None:
    validate_config()
    init_db()

    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()

    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu:"))
    application.add_handler(CallbackQueryHandler(product_callback, pattern=r"^product:"))
    application.add_handler(CallbackQueryHandler(buy_stars, pattern=r"^buy_stars:"))
    application.add_handler(CallbackQueryHandler(buy_rub, pattern=r"^buy_rub:"))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))

    logger.info("Bot started")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
