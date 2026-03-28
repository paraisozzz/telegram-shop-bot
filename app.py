import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

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
    delivery_text: str


DEFAULT_PRODUCTS = [
    {
        "code": "product_1",
        "title": "1000 ПРОМПТОВ ДЛЯ ЗАРАБОТКА С CHATGPT",
        "description": "Руководство «1000 промптов для заработка с ChatGPT» — это готовые запросы, которые помогут зарабатывать на текстах, контенте, маркетинге, переводах, идеях и онлайн-услугах с помощью нейросетей даже без опыта.",
        "price_stars": 200,
        "delivery_text": "Спасибо за покупку!\n\nВаш цифровой продукт готов к скачиванию:\nhttps://clck.ru/3SnYDx\n\nСохраните файл себе на устройство.\nЕсли возникнут вопросы, напишите в поддержку: @lotus762001",
    },
    {
        "code": "product_2",
        "title": "50 СПОСОБОВ ЗАРАБОТАТЬ НА НЕЙРОСЕТЯХ В 2026 ГОДУ",
        "description": "«50 способов заработать на нейросетях в 2026 году» — сборник актуальных идей и пошаговых схем заработка с помощью искусственного интеллекта.",
        "price_stars": 210,
        "delivery_text": "Спасибо за покупку!\n\nВаш цифровой продукт готов к скачиванию:\nhttps://clck.ru/3SnYqW\n\nСохраните файл себе на устройство.\nЕсли возникнут вопросы, напишите в поддержку: @lotus762001",
    },
    {
        "code": "product_3",
        "title": "365 ИДЕЙ КОНТЕНТА ДЛЯ TELEGRAM / TIKTOK / REELS",
        "description": "«365 идей контента для Telegram, TikTok и Reels» — это готовый план постов и видео на каждый день, который поможет регулярно публиковать контент, набирать подписчиков и зарабатывать.",
        "price_stars": 190,
        "delivery_text": "Спасибо за покупку!\n\nВаш цифровой продукт готов к скачиванию:\nhttps://clck.ru/3SnZUN\n\nСохраните файл себе на устройство.\nЕсли возникнут вопросы, напишите в поддержку: @lotus762001",
    },
    {
        "code": "product_4",
        "title": "КАК ДЕЛАТЬ AI-ВИДЕО И ЗАРАБАТЫВАТЬ НА НИХ",
        "description": "Руководство «Как делать AI-видео и зарабатывать на них» — это пошаговая инструкция по созданию видео с помощью нейросетей и способам заработка на коротких видео и контенте.",
        "price_stars": 208,
        "delivery_text": "Спасибо за покупку!\n\nВаш цифровой продукт готов к скачиванию:\nhttps://clck.ru/3SnZgq\n\nСохраните файл себе на устройство.\nЕсли возникнут вопросы, напишите в поддержку: @lotus762001",
    },
]

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "lotus762001").replace("@", "")
SHOP_TITLE = os.getenv("SHOP_TITLE", "Заработок на нейросетях")
START_TEXT = os.getenv(
    "START_TEXT",
    "Добро пожаловать в магазин по заработку на нейросетях!\n"
    "Здесь вы можете купить гайды, промпты и инструменты, которые помогут начать зарабатывать с помощью ИИ уже сегодня.",
)
SHOP_TEXT = os.getenv(
    "SHOP_TEXT",
    "Выберите раздел ниже и откройте нужный продукт.",
)
ABOUT_TEXT = os.getenv(
    "ABOUT_TEXT",
    "В этом боте собраны цифровые продукты по заработку на нейросетях:\n"
    "— промпты ChatGPT\n"
    "— идеи контента\n"
    "— способы заработка\n"
    "— AI-видео\n\n"
    "После оплаты звездами Telegram бот автоматически отправит ваш материал.",
)
PRODUCTS_JSON = os.getenv("PRODUCTS_JSON", json.dumps(DEFAULT_PRODUCTS, ensure_ascii=False))
DB_PATH = Path(os.getenv("DB_PATH", "bot_data.sqlite3"))


def load_products() -> Dict[str, Product]:
    try:
        raw_products: List[dict] = json.loads(PRODUCTS_JSON)
    except json.JSONDecodeError as exc:
        raise ValueError("Переменная PRODUCTS_JSON содержит некорректный JSON.") from exc

    products: Dict[str, Product] = {}
    for index, item in enumerate(raw_products, start=1):
        code = str(item.get("code") or f"product_{index}")
        products[code] = Product(
            code=code,
            title=str(item["title"]),
            description=str(item["description"]),
            price_stars=int(item["price_stars"]),
            delivery_text=str(item["delivery_text"]),
        )

    if not products:
        raise ValueError("Список товаров пуст. Добавьте хотя бы один товар в PRODUCTS_JSON.")
    return products


PRODUCTS = load_products()


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
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def save_purchase(user_id: int, username: str | None, product: Product, amount: int, payment_id: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO purchases
            (user_id, username, product_code, product_title, amount, payment_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, username or "", product.code, product.title, amount, payment_id),
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
                    text=f"{product.title} — ⭐ {product.price_stars}",
                    callback_data=f"product:{product.code}",
                )
            ]
        )
    rows.append([InlineKeyboardButton("⬅️ В главное меню", callback_data="menu:main")])
    return InlineKeyboardMarkup(rows)


def product_keyboard(product_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💳 Купить", callback_data=f"buy:{product_code}")],
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
    return (
        f"{SHOP_TITLE}\n\n"
        f"{START_TEXT}\n\n"
        "Выберите раздел ниже."
    )


def shop_message() -> str:
    lines = [f"🛍 {SHOP_TITLE}", "", SHOP_TEXT, ""]
    for idx, product in enumerate(PRODUCTS.values(), start=1):
        lines.append(f"{idx}. {product.title}")
        lines.append(f"Цена: ⭐ {product.price_stars}")
        lines.append("")
    lines.append("Нажмите на товар, чтобы открыть подробное описание.")
    return "\n".join(lines)


def product_message(product: Product) -> str:
    return (
        f"{product.title}\n\n"
        f"{product.description}\n\n"
        f"Цена: ⭐ {product.price_stars}\n\n"
        "После оплаты бот автоматически отправит вам материал."
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
        return (
            "📦 У вас пока нет покупок.\n\n"
            "Откройте магазин и выберите первый продукт."
        )

    seen = set()
    lines = ["📦 Ваши покупки", ""]
    for product_code, product_title in purchases:
        if product_code in seen:
            continue
        seen.add(product_code)
        lines.append(f"— {product_title}")
    lines.append("")
    lines.append("Чтобы открыть товары снова, выберите их в магазине или напишите в поддержку.")
    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
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


async def paysupport(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        if user_id is None:
            text = "Не удалось определить пользователя."
        else:
            text = purchases_message(user_id)
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

    await query.message.edit_text(
        product_message(product),
        reply_markup=product_keyboard(product.code),
    )


async def buy_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message:
        return

    await query.answer()
    _, product_code = query.data.split(":", 1)
    product = PRODUCTS.get(product_code)
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

    logger.info(
        "Successful payment | user_id=%s | username=%s | product=%s | amount=%s | payment_id=%s",
        update.effective_user.id,
        update.effective_user.username,
        payment.invoice_payload,
        payment.total_amount,
        payment.telegram_payment_charge_id,
    )

    if not product:
        await message.reply_text(
            "Оплата прошла успешно, но продукт не найден. Напишите в поддержку: "
            f"@{SUPPORT_USERNAME}"
        )
        return

    save_purchase(
        user_id=update.effective_user.id,
        username=update.effective_user.username,
        product=product,
        amount=payment.total_amount,
        payment_id=payment.telegram_payment_charge_id,
    )

    await message.reply_text(product.delivery_text)
    await message.reply_text(
        "✨ Оплата прошла успешно.\n\n"
        "Я сохранил покупку в разделе «Мои покупки».\n"
        "Ниже можете посмотреть другие материалы:",
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
        raise ValueError("Не задан BOT_TOKEN. Добавьте его в переменные окружения Render.")


def main() -> None:
    validate_config()
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("shop", shop))
    application.add_handler(CommandHandler("about", about))
    application.add_handler(CommandHandler("support", support))
    application.add_handler(CommandHandler("paysupport", paysupport))
    application.add_handler(CommandHandler("myorders", myorders))

    application.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu:"))
    application.add_handler(CallbackQueryHandler(product_callback, pattern=r"^product:"))
    application.add_handler(CallbackQueryHandler(buy_product, pattern=r"^buy:"))

    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))

    logger.info("Bot started")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
