import json
import logging
import os
from dataclasses import dataclass
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
        "description": "Руководство «1000 промптов для заработка с ChatGPT» — это готовые запросы, которые помогут зарабатывать на текстах, контенте, маркетинге, переводах, идеях и онлайн-услугах с помощью нейросетей даже без опыта",
        "price_stars": 200,
        "delivery_text": "Спасибо за покупку!\nВаш цифровой продукт готов к скачиванию:\nСсылка: https://clck.ru/3SnYDx\nСохраните файл себе на устройство\nЕсли возникнут вопросы, напишите в поддержку: @lotus762001",
    },
    {
        "code": "product_2",
        "title": "50 СПОСОБОВ ЗАРАБОТАТЬ НА НЕЙРОСЕТЯХ В 2026 ГОДУ",
        "description": "«50 способов заработать на нейросетях в 2026 году» — сборник актуальных идей и пошаговых схем заработка с помощью искусственного интеллекта.",
        "price_stars": 210,
        "delivery_text": "Спасибо за покупку!\nВаш цифровой продукт готов к скачиванию:\nСсылка: https://clck.ru/3SnYqW\nСохраните файл себе на устройство\nЕсли возникнут вопросы, напишите в поддержку: @lotus762001",
    },
    {
        "code": "product_3",
        "title": "365 ИДЕЙ КОНТЕНТА ДЛЯ TELEGRAM / TIKTOK / REELS",
        "description": "«365 идей контента для Telegram, TikTok и Reels» — это готовый план постов и видео на каждый день, который поможет регулярно публиковать контент, набирать подписчиков и зарабатывать",
        "price_stars": 190,
        "delivery_text": "Спасибо за покупку!\nВаш цифровой продукт готов к скачиванию:\nСсылка: https://clck.ru/3SnZUN\nСохраните файл себе на устройство\nЕсли возникнут вопросы, напишите в поддержку: @lotus762001",
    },
    {
        "code": "product_4",
        "title": "КАК ДЕЛАТЬ AI-ВИДЕО И ЗАРАБАТЫВАТЬ НА НИХ",
        "description": "Руководство «Как делать AI-видео и зарабатывать на них» — это пошаговая инструкция по созданию видео с помощью нейросетей и способам заработка на коротких видео и контенте",
        "price_stars": 208,
        "delivery_text": "Спасибо за покупку!\nВаш цифровой продукт готов к скачиванию:\nСсылка: https://clck.ru/3SnZgq\nСохраните файл себе на устройство\nЕсли возникнут вопросы, напишите в поддержку: @lotus762001",
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
    "Выберите цифровой продукт ниже и оплатите его звездами Telegram.",
)
PRODUCTS_JSON = os.getenv("PRODUCTS_JSON", json.dumps(DEFAULT_PRODUCTS, ensure_ascii=False))


def load_products() -> Dict[str, Product]:
    try:
        raw_products: List[dict] = json.loads(PRODUCTS_JSON)
    except json.JSONDecodeError as exc:
        raise ValueError("Переменная PRODUCTS_JSON содержит некорректный JSON.") from exc

    products: Dict[str, Product] = {}
    for index, item in enumerate(raw_products, start=1):
        code = item.get("code") or f"product_{index}"
        title = str(item["title"])
        description = str(item["description"])
        price_stars = int(item["price_stars"])
        delivery_text = str(item["delivery_text"])
        products[code] = Product(
            code=code,
            title=title,
            description=description,
            price_stars=price_stars,
            delivery_text=delivery_text,
        )
    if not products:
        raise ValueError("Список товаров пуст. Добавьте хотя бы один товар в PRODUCTS_JSON.")
    return products


PRODUCTS = load_products()


def build_shop_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for product in PRODUCTS.values():
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"Купить — ⭐ {product.price_stars}",
                    callback_data=f"buy:{product.code}",
                )
            ]
        )
    rows.append([InlineKeyboardButton("Поддержка", callback_data="support")])
    return InlineKeyboardMarkup(rows)



def shop_message() -> str:
    lines = [SHOP_TITLE, "", SHOP_TEXT, ""]
    for product in PRODUCTS.values():
        lines.append(f"{product.title}")
        lines.append(f"⭐ {product.price_stars}")
        lines.append(product.description)
        lines.append("")
    lines.append("После оплаты бот автоматически отправит вам продукт.")
    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = f"{SHOP_TITLE}\n\n{START_TEXT}"
    if update.message:
        await update.message.reply_text(text, reply_markup=build_shop_keyboard())


async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(shop_message(), reply_markup=build_shop_keyboard())


async def support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = (
        "По вопросам оплаты и доступа к материалам напишите в поддержку: "
        f"@{SUPPORT_USERNAME}"
    )
    if update.message:
        await update.message.reply_text(message)
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(message)


async def paysupport(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "По вопросам оплаты и возврата напишите в поддержку: "
            f"@{SUPPORT_USERNAME}\n\n"
            "В сообщении укажите дату покупки, название товара и ваш username."
        )


async def buy_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return

    await query.answer()
    _, product_code = query.data.split(":", 1)
    product = PRODUCTS.get(product_code)
    if not product:
        await query.message.reply_text("Товар не найден. Откройте /shop и попробуйте снова.")
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
    if not message or not message.successful_payment:
        return

    payment = message.successful_payment
    product = PRODUCTS.get(payment.invoice_payload)

    logger.info(
        "Successful payment | user_id=%s | username=%s | product=%s | amount=%s | payment_id=%s",
        update.effective_user.id if update.effective_user else None,
        update.effective_user.username if update.effective_user else None,
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

    await message.reply_text(product.delivery_text)
    await message.reply_text("Посмотреть остальные материалы: /shop")


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text("Неизвестная команда. Используйте /start или /shop.")


def validate_config() -> None:
    if not BOT_TOKEN:
        raise ValueError("Не задан BOT_TOKEN. Добавьте его в переменные окружения Render.")


def main() -> None:
    validate_config()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("shop", shop))
    application.add_handler(CommandHandler("support", support))
    application.add_handler(CommandHandler("paysupport", paysupport))
    application.add_handler(CallbackQueryHandler(buy_product, pattern=r"^buy:"))
    application.add_handler(CallbackQueryHandler(support, pattern=r"^support$"))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))

    logger.info("Bot started")
    application.run_polling(allowed_updates=Update.ALL_TYPES, close_loop=False)


if __name__ == "__main__":
    main()
