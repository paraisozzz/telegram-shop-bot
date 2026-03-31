import asyncio
import logging
import os
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Update
from telegram.ext import (
    Application,
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
BOT_USERNAME = os.getenv("BOT_USERNAME", "Zarabotok49_bot").replace("@", "")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "lotus762001").replace("@", "")
SHOP_TITLE = os.getenv("SHOP_TITLE", "Заработок на нейросетях")
START_TEXT = os.getenv(
    "START_TEXT",
    "Добро пожаловать в магазин по заработку на нейросетях!\n"
    "Здесь вы можете купить гайды, промпты и инструменты, которые помогут начать зарабатывать с помощью ИИ уже сегодня.",
)
SHOP_TEXT = os.getenv(
    "SHOP_TEXT",
    "Выберите товар ниже и откройте карточку, чтобы оплатить в Stars или в рублях.",
)
ABOUT_TEXT = os.getenv(
    "ABOUT_TEXT",
    "В этом боте собраны цифровые продукты по заработку на нейросетях.\n"
    "После оплаты в Stars или в рублях бот автоматически отправит ваш товар.",
)

YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "1314251")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
DB_PATH = Path(os.getenv("DB_PATH", "bot_data.sqlite3"))
PAYMENT_POLL_INTERVAL = int(os.getenv("PAYMENT_POLL_INTERVAL", "20"))


PRODUCTS: Dict[str, Product] = {
    "p1": Product(
        code="p1",
        title="1000 ПРОМПТОВ ДЛЯ ЗАРАБОТКА С CHATGPT",
        description="Готовые промпты для заработка на текстах, контенте, маркетинге, переводах, идеях и онлайн-услугах.",
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
        description="Пошаговая инструкция по созданию AI-видео и заработку на коротких видео и контенте.",
        price_stars=279,
        price_rub=390,
        delivery_text="Спасибо за покупку!\n\nВаш цифровой продукт готов к скачиванию:\nhttps://clck.ru/3SnZgq\n\nСохраните файл себе на устройство.\nЕсли возникнут вопросы, напишите в поддержку: @lotus762001",
    ),
    "bundle": Product(
        code="bundle",
        title="ВСЕ 4 ТОВАРА ВМЕСТЕ",
        description="Все 4 цифровых продукта одним платежом.",
        price_stars=1156,
        price_rub=1605,
        delivery_text="Спасибо за покупку!\n\nВаш комплект готов к скачиванию:\n\n1) https://clck.ru/3SnYDx\n2) https://clck.ru/3SnYqW\n3) https://clck.ru/3SnZUN\n4) https://clck.ru/3SnZgq\n\nСохраните материалы себе на устройство.\nЕсли возникнут вопросы, напишите в поддержку: @lotus762001",
    ),
}


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
                amount INTEGER NOT NULL,
                payment_id TEXT NOT NULL UNIQUE,
                payment_method TEXT NOT NULL,
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_rub_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                username TEXT,
                product_code TEXT NOT NULL,
                product_title TEXT NOT NULL,
                amount_rub INTEGER NOT NULL,
                confirmation_url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                delivered_at TIMESTAMP
            )
            """
        )
        conn.commit()


def save_purchase(user_id: int, username: str | None, product: Product, amount: int, payment_id: str, payment_method: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO purchases
            (user_id, username, product_code, product_title, amount, payment_id, payment_method)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, username or "", product.code, product.title, amount, payment_id, payment_method),
        )
        conn.commit()


def add_pending_rub_payment(payment_id: str, user_id: int, username: str | None, product: Product, confirmation_url: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO pending_rub_payments
            (payment_id, user_id, username, product_code, product_title, amount_rub, confirmation_url, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (payment_id, user_id, username or "", product.code, product.title, product.price_rub, confirmation_url),
        )
        conn.commit()


def get_pending_rub_payments() -> list[tuple[str, int, str, str]]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT payment_id, user_id, username, product_code
            FROM pending_rub_payments
            WHERE status = 'pending'
            ORDER BY id ASC
            """
        ).fetchall()
    return rows


def mark_rub_payment_delivered(payment_id: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE pending_rub_payments
            SET status = 'delivered', delivered_at = CURRENT_TIMESTAMP
            WHERE payment_id = ?
            """,
            (payment_id,),
        )
        conn.commit()


def get_user_purchases(user_id: int) -> list[tuple[str, str]]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT product_code, product_title
            FROM purchases
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()
    return rows


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
    for product in PRODUCTS.values():
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{product.title} — ⭐ {product.price_stars} / {product.price_rub} ₽",
                    callback_data=f"product:{product.code}",
                )
            ]
        )
    rows.append([InlineKeyboardButton("⬅️ В главное меню", callback_data="menu:main")])
    return InlineKeyboardMarkup(rows)


def product_keyboard(product_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⭐ Купить за Stars", callback_data=f"buy_stars:{product_code}")],
            [InlineKeyboardButton("💳 Оплатить в рублях", callback_data=f"buy_rub:{product_code}")],
            [InlineKeyboardButton("🛍 Назад в магазин", callback_data="menu:shop")],
            [InlineKeyboardButton("⬅️ Главное меню", callback_data="menu:main")],
        ]
    )


def after_purchase_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔥 Смотреть другие товары", callback_data="menu:shop")],
            [InlineKeyboardButton("📦 Мои покупки", callback_data="menu:orders")],
            [InlineKeyboardButton("💬 Поддержка", callback_data="menu:support")],
        ]
    )


def support_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🛍 Магазин", callback_data="menu:shop")],
            [InlineKeyboardButton("⬅️ Главное меню", callback_data="menu:main")],
        ]
    )


def start_message() -> str:
    return f"{SHOP_TITLE}\n\n{START_TEXT}\n\nВыберите раздел ниже."


def shop_message() -> str:
    lines = [f"🛍 {SHOP_TITLE}", "", SHOP_TEXT, ""]
    for idx, product in enumerate(PRODUCTS.values(), start=1):
        lines.append(f"{idx}. {product.title}")
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
        "После успешной оплаты бот автоматически отправит товар."
    )


def about_message() -> str:
    return f"ℹ️ О продуктах\n\n{ABOUT_TEXT}"


def support_message() -> str:
    return (
        "💬 Поддержка\n\n"
        f"Если возникли вопросы по оплате или доступу к материалам, напишите: @{SUPPORT_USERNAME}\n\n"
        "В сообщении укажите:\n"
        "— дату покупки\n"
        "— название товара\n"
        "— ваш username"
    )


def purchases_message(user_id: int) -> str:
    purchases = get_user_purchases(user_id)
    if not purchases:
        return "📦 У вас пока нет покупок.\n\nОткройте магазин и выберите первый продукт."

    seen = set()
    lines = ["📦 Ваши покупки", ""]
    for product_code, product_title in purchases:
        if product_code in seen:
            continue
        seen.add(product_code)
        lines.append(f"— {product_title}")
    lines.append("")
    lines.append("Все купленные товары вы можете открыть повторно через поддержку.")
    return "\n".join(lines)


async def create_yookassa_payment(product: Product, user_id: int, username: str | None) -> tuple[str, str]:
    if not YOOKASSA_SECRET_KEY:
        raise RuntimeError("Не задан YOOKASSA_SECRET_KEY в Render Environment.")

    payload = {
        "amount": {"value": f"{product.price_rub:.2f}", "currency": "RUB"},
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": f"https://t.me/{BOT_USERNAME}",
        },
        "description": product.title,
        "metadata": {
            "telegram_user_id": str(user_id),
            "telegram_username": username or "",
            "product_code": product.code,
        },
    }

    headers = {"Idempotence-Key": str(uuid.uuid4())}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.yookassa.ru/v3/payments",
            json=payload,
            headers=headers,
            auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY),
        )
        response.raise_for_status()
        data = response.json()

    payment_id = data["id"]
    confirmation_url = data["confirmation"]["confirmation_url"]
    return payment_id, confirmation_url


async def get_yookassa_payment_status(payment_id: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"https://api.yookassa.ru/v3/payments/{payment_id}",
            auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY),
        )
        response.raise_for_status()
        data = response.json()
    return data["status"]


async def payment_watcher(application: Application) -> None:
    while True:
        try:
            pending = get_pending_rub_payments()
            for payment_id, user_id, username, product_code in pending:
                product = PRODUCTS.get(product_code)
                if not product:
                    continue
                status = await get_yookassa_payment_status(payment_id)
                if status == "succeeded":
                    save_purchase(
                        user_id=user_id,
                        username=username,
                        product=product,
                        amount=product.price_rub,
                        payment_id=payment_id,
                        payment_method="yookassa",
                    )
                    mark_rub_payment_delivered(payment_id)
                    await application.bot.send_message(chat_id=user_id, text=product.delivery_text)
                    await application.bot.send_message(
                        chat_id=user_id,
                        text="✨ Оплата в рублях прошла успешно.\n\nТовар уже отправлен выше.",
                        reply_markup=after_purchase_keyboard(),
                    )
        except Exception as exc:
            logger.exception("Payment watcher error: %s", exc)

        await asyncio.sleep(PAYMENT_POLL_INTERVAL)


async def post_init(application: Application) -> None:
    application.bot_data["payment_watcher_task"] = asyncio.create_task(payment_watcher(application))


async def post_shutdown(application: Application) -> None:
    task = application.bot_data.get("payment_watcher_task")
    if task:
        task.cancel()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    if context.args:
        arg = context.args[0]
        if arg.startswith("product_"):
            code = arg.replace("product_", "")
            product = PRODUCTS.get(code)
            if product:
                await update.message.reply_text(
                    product_message(product),
                    reply_markup=product_keyboard(product.code),
                )
                return

    await update.message.reply_text(start_message(), reply_markup=main_menu_keyboard())


async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(shop_message(), reply_markup=shop_keyboard())


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(about_message(), reply_markup=support_keyboard())


async def support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(support_message(), reply_markup=support_keyboard())


async def myorders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message and update.effective_user:
        await update.message.reply_text(
            purchases_message(update.effective_user.id),
            reply_markup=support_keyboard(),
        )


async def show_menu(query, menu_key: str, user_id: int | None = None) -> None:
    if menu_key == "main":
        text = start_message()
        markup = main_menu_keyboard()
    elif menu_key == "shop":
        text = shop_message()
        markup = shop_keyboard()
    elif menu_key == "about":
        text = about_message()
        markup = support_keyboard()
    elif menu_key == "support":
        text = support_message()
        markup = support_keyboard()
    elif menu_key == "orders":
        text = purchases_message(user_id) if user_id else "Не удалось определить пользователя."
        markup = support_keyboard()
    else:
        text = "Раздел не найден."
        markup = main_menu_keyboard()

    await query.answer()
    await query.message.edit_text(text, reply_markup=markup)


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    _, menu_key = query.data.split(":", 1)
    user_id = update.effective_user.id if update.effective_user else None
    await show_menu(query, menu_key, user_id=user_id)


async def product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    _, product_code = query.data.split(":", 1)
    product = PRODUCTS.get(product_code)
    await query.answer()
    if not product:
        await query.message.edit_text("Товар не найден.", reply_markup=shop_keyboard())
        return

    await query.message.edit_text(product_message(product), reply_markup=product_keyboard(product.code))


async def buy_stars(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message:
        return

    _, product_code = query.data.split(":", 1)
    product = PRODUCTS.get(product_code)
    await query.answer()

    if not product:
        await query.message.reply_text("Товар не найден. Откройте магазин и попробуйте снова.")
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
    user = update.effective_user
    if not query or not user:
        return

    _, product_code = query.data.split(":", 1)
    product = PRODUCTS.get(product_code)
    await query.answer()

    if not product:
        await query.message.reply_text("Товар не найден. Откройте магазин и попробуйте снова.")
        return

    try:
        payment_id, confirmation_url = await create_yookassa_payment(product, user.id, user.username)
        add_pending_rub_payment(payment_id, user.id, user.username, product, confirmation_url)
    except Exception as exc:
        logger.exception("Failed to create Yookassa payment: %s", exc)
        await query.message.reply_text(
            "Не удалось создать оплату в рублях. Попробуйте позже или выберите оплату через Stars.",
            reply_markup=product_keyboard(product.code),
        )
        return

    text = (
        f"💳 Оплата в рублях для товара:\n{product.title}\n\n"
        f"Сумма: {product.price_rub} ₽\n\n"
        "Нажмите кнопку ниже, чтобы перейти к оплате.\n"
        "После успешной оплаты бот автоматически отправит товар."
    )
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Перейти к оплате", url=confirmation_url)],
            [InlineKeyboardButton("⬅️ Назад к товару", callback_data=f"product:{product.code}")],
        ]
    )
    await query.message.reply_text(text, reply_markup=keyboard)


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
    user = update.effective_user
    if not message or not message.successful_payment or not user:
        return

    payment = message.successful_payment
    product = PRODUCTS.get(payment.invoice_payload)
    if not product:
        await message.reply_text(f"Оплата прошла, но товар не найден. Напишите в поддержку: @{SUPPORT_USERNAME}")
        return

    save_purchase(
        user_id=user.id,
        username=user.username,
        product=product,
        amount=payment.total_amount,
        payment_id=payment.telegram_payment_charge_id,
        payment_method="stars",
    )
    await message.reply_text(product.delivery_text)
    await message.reply_text(
        "✨ Оплата через Stars прошла успешно.\n\nНиже можете посмотреть другие материалы:",
        reply_markup=after_purchase_keyboard(),
    )


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "Неизвестная команда. Используйте /start, чтобы открыть главное меню.",
            reply_markup=main_menu_keyboard(),
        )


def validate_config() -> None:
    if not BOT_TOKEN:
        raise ValueError("Не задан BOT_TOKEN.")
    if not YOOKASSA_SECRET_KEY:
        raise ValueError("Не задан YOOKASSA_SECRET_KEY в Render Environment.")


def main() -> None:
    validate_config()
    init_db()
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("shop", shop))
    application.add_handler(CommandHandler("about", about))
    application.add_handler(CommandHandler("support", support))
    application.add_handler(CommandHandler("myorders", myorders))

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
