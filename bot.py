import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "shop.db"
PRODUCTS_PATH = BASE_DIR / "products.json"
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "your_support_username")
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/your_channel")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


@dataclass
class Product:
    id: str
    title: str
    description: str
    price_xtr: int
    delivery_type: str
    delivery_value: str
    button_text: str = "Купить"
    image_url: Optional[str] = None


DEFAULT_PRODUCTS = [
    {
        "id": "guide_1",
        "title": "PDF-гайд: 50 идей цифровых товаров",
        "description": "Полезный PDF для запуска продаж в Telegram.",
        "price_xtr": 150,
        "delivery_type": "text",
        "delivery_value": "Спасибо за покупку! Замените этот текст на ссылку, код доступа или инструкцию.",
        "button_text": "Купить за 150 ⭐",
        "image_url": "https://placehold.co/1200x800/png?text=Digital+Guide",
    },
    {
        "id": "channel_vip",
        "title": "Доступ в VIP-канал на 30 дней",
        "description": "Бот отправит ссылку на закрытый канал после оплаты.",
        "price_xtr": 300,
        "delivery_type": "text",
        "delivery_value": "Вставьте сюда одноразовую или постоянную ссылку на закрытый канал: https://t.me/+your_invite_link",
        "button_text": "Открыть VIP за 300 ⭐",
        "image_url": "https://placehold.co/1200x800/png?text=VIP+Channel",
    },
]


def ensure_products_file() -> None:
    if not PRODUCTS_PATH.exists():
        with PRODUCTS_PATH.open("w", encoding="utf-8") as f:
            json.dump(DEFAULT_PRODUCTS, f, ensure_ascii=False, indent=2)


def load_products() -> Dict[str, Product]:
    ensure_products_file()
    with PRODUCTS_PATH.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    products = {}
    for item in raw:
        products[item["id"]] = Product(**item)
    return products


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                product_id TEXT NOT NULL,
                telegram_payment_charge_id TEXT UNIQUE NOT NULL,
                total_amount INTEGER NOT NULL,
                currency TEXT NOT NULL,
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def purchase_exists(charge_id: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT 1 FROM purchases WHERE telegram_payment_charge_id = ?",
            (charge_id,),
        ).fetchone()
        return row is not None


def save_purchase(
    user_id: int,
    username: str,
    product_id: str,
    charge_id: str,
    total_amount: int,
    currency: str,
) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO purchases
            (user_id, username, product_id, telegram_payment_charge_id, total_amount, currency)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, username, product_id, charge_id, total_amount, currency),
        )
        conn.commit()


def product_card(product: Product) -> str:
    return (
        f"<b>{product.title}</b>\n"
        f"{product.description}\n\n"
        f"Цена: <b>{product.price_xtr} ⭐</b>"
    )


def catalog_keyboard(products: Dict[str, Product]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(p.button_text or f"Купить {p.title}", callback_data=f"buy:{p.id}")]
        for p in products.values()
    ]
    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    products = context.bot_data["products"]
    text = (
        "<b>Магазин цифровых товаров</b>\n\n"
        "Выберите товар ниже. Оплата цифровых товаров в Telegram проходит в Stars (⭐).\n\n"
        f"Канал витрины: {CHANNEL_URL}"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=catalog_keyboard(products))


async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


async def pay_support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Поддержка по оплатам и доставке:\n"
        f"@{SUPPORT_USERNAME}\n\n"
        "Напишите номер заказа, ваш @username и название товара."
    )
    if update.message:
        await update.message.reply_text(text)


async def terms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Условия:\n"
        "1. Это цифровые товары.\n"
        "2. Доставка происходит автоматически после оплаты.\n"
        "3. По спорным ситуациям используйте /paysupport.\n"
        "4. Возвраты обрабатываются продавцом вручную."
    )
    if update.message:
        await update.message.reply_text(text)


async def on_buy_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, product_id = query.data.split(":", 1)
    products = context.bot_data["products"]
    product = products.get(product_id)

    if not product:
        await query.message.reply_text("Товар не найден.")
        return

    prices = [LabeledPrice(label=product.title, amount=product.price_xtr)]

    await context.bot.send_invoice(
        chat_id=query.from_user.id,
        title=product.title,
        description=product.description,
        payload=f"product:{product.id}",
        currency="XTR",
        prices=prices,
        provider_token="",
        photo_url=product.image_url,
        start_parameter=f"buy-{product.id}",
    )


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.pre_checkout_query
    payload = query.invoice_payload

    if not payload.startswith("product:"):
        await query.answer(ok=False, error_message="Неверный товар.")
        return

    product_id = payload.split(":", 1)[1]
    products = context.bot_data["products"]

    if product_id not in products:
        await query.answer(ok=False, error_message="Этот товар недоступен.")
        return

    await query.answer(ok=True)


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    payment = msg.successful_payment
    payload = payment.invoice_payload
    product_id = payload.split(":", 1)[1]
    products = context.bot_data["products"]
    product = products.get(product_id)

    if not product:
        await msg.reply_text("Оплата прошла, но товар не найден. Напишите в /paysupport")
        return

    charge_id = payment.telegram_payment_charge_id
    if purchase_exists(charge_id):
        return

    save_purchase(
        user_id=msg.from_user.id,
        username=msg.from_user.username or "",
        product_id=product.id,
        charge_id=charge_id,
        total_amount=payment.total_amount,
        currency=payment.currency,
    )

    await deliver_product(msg, product)
    await notify_admin(context, msg.from_user.id, msg.from_user.username or "", product)


async def deliver_product(message, product: Product) -> None:
    await message.reply_text(
        f"Оплата получена ✅\n\nВаш товар: {product.title}",
    )

    if product.delivery_type == "text":
        await message.reply_text(product.delivery_value, disable_web_page_preview=True)
    elif product.delivery_type == "document_file_id":
        await message.reply_document(document=product.delivery_value, caption=f"Ваш товар: {product.title}")
    elif product.delivery_type == "photo_file_id":
        await message.reply_photo(photo=product.delivery_value, caption=f"Ваш товар: {product.title}")
    else:
        await message.reply_text(
            "Товар оплачен, но способ доставки не настроен. Напишите в /paysupport"
        )


async def notify_admin(context: ContextTypes.DEFAULT_TYPE, user_id: int, username: str, product: Product) -> None:
    if not ADMIN_CHAT_ID:
        return

    text = (
        "Новая продажа 💸\n"
        f"Пользователь: {username or 'без username'} (ID: {user_id})\n"
        f"Товар: {product.title}\n"
        f"Цена: {product.price_xtr} ⭐"
    )
    try:
        await context.bot.send_message(chat_id=int(ADMIN_CHAT_ID), text=text)
    except Exception as exc:
        logger.warning("Не удалось отправить уведомление админу: %s", exc)


async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message and update.message.text:
        await update.message.reply_text(
            "Используйте /start, /catalog, /paysupport или кнопки магазина."
        )


def main() -> None:
    load_dotenv()
    global BOT_TOKEN, SUPPORT_USERNAME, CHANNEL_URL, ADMIN_CHAT_ID
    BOT_TOKEN = os.getenv("BOT_TOKEN", BOT_TOKEN)
    SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", SUPPORT_USERNAME)
    CHANNEL_URL = os.getenv("CHANNEL_URL", CHANNEL_URL)
    ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", ADMIN_CHAT_ID)

    if not BOT_TOKEN:
        raise RuntimeError("Не найден BOT_TOKEN. Скопируйте .env.example в .env и укажите токен.")

    init_db()
    products = load_products()

    application = Application.builder().token(BOT_TOKEN).build()
    application.bot_data["products"] = products

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("catalog", catalog))
    application.add_handler(CommandHandler("paysupport", pay_support))
    application.add_handler(CommandHandler("terms", terms))
    application.add_handler(CallbackQueryHandler(on_buy_click, pattern=r"^buy:"))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown))

    logger.info("Bot started")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
