import json
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    PreCheckoutQuery
)
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN", "YOUR_PROVIDER_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))

storage = MemoryStorage()
bot = Bot(BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=storage)

DATA_FILE = "data.json"


# ===== СОСТОЯНИЯ FSM =====
class AdminStates(StatesGroup):
    waiting_for_photo = State()


# ===== СТРУКТУРА ДАННЫХ =====
DEFAULT_DATA = {
    "welcome_text": "🔥 <b>Крутой материал!</b>\n\nОписание вашего продукта здесь.\nЧто получит покупатель после оплаты.",
    "welcome_photo": "",
    "sale_text": "💎 <b>Забери свой материал!</b>\n\nЗдесь описание того что вы покупаете.\nЦенность продукта.",
    "sale_photo": "",
    "sale_button_text": "Забрать материал",
    "price": 449,
    "currency": "RUB",
    "product_title": "Доступ к материалу",
    "product_description": "После оплаты вы получите ссылку на материал",
    "paid_text": "✅ <b>Оплата прошла успешно!</b>\n\nВот ваш материал:\n{link}",
    "paid_link": "https://google.com"
}


# ===== ЗАГРУЗКА / СОХРАНЕНИЕ =====
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
            for key, value in DEFAULT_DATA.items():
                if key not in saved:
                    saved[key] = value
            return saved
    except:
        save_data(DEFAULT_DATA)
        return DEFAULT_DATA.copy()


def save_data(d):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


data = load_data()


# ===== ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ОТПРАВКИ СООБЩЕНИЯ =====
# Отправляет сообщение: если есть фото — с фото, если нет — текстом
async def send_message_with_or_without_photo(chat_id, text, photo, keyboard):
    if photo:
        await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=text,
            reply_markup=keyboard
        )
    else:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard
        )


# ===========================
# ===== ПОЛЬЗОВАТЕЛЬ ========
# ===========================

# Сообщение 1 — Приветствие
@dp.message_handler(commands=['start'], state="*")
async def start(message: types.Message, state: FSMContext):
    await state.finish()

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("✅ Забрать", callback_data="show_sale"))

    await send_message_with_or_without_photo(
        chat_id=message.chat.id,
        text=data["welcome_text"],
        photo=data.get("welcome_photo", ""),
        keyboard=kb
    )


# Сообщение 2 — Выдача (после нажатия "✅ Забрать")
@dp.callback_query_handler(lambda c: c.data == "show_sale", state="*")
async def show_sale(callback: types.CallbackQuery):
    await callback.answer()

    button_text = f"💳 {data['sale_button_text']} {data['price']}₽"
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(button_text, callback_data="buy"))

    await send_message_with_or_without_photo(
        chat_id=callback.message.chat.id,
        text=data["sale_text"],
        photo=data.get("sale_photo", ""),
        keyboard=kb
    )


# Инвойс оплаты
@dp.callback_query_handler(lambda c: c.data == "buy", state="*")
async def buy(callback: types.CallbackQuery):
    await callback.answer()
    prices = [LabeledPrice(label=data["product_title"], amount=data["price"] * 100)]
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=data["product_title"],
        description=data["product_description"],
        payload="paid_content",
        provider_token=PROVIDER_TOKEN,
        currency=data["currency"],
        prices=prices,
    )


@dp.pre_checkout_query_handler(state="*")
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@dp.message_handler(content_types=types.ContentType.SUCCESSFUL_PAYMENT, state="*")
async def successful_payment(message: types.Message):
    paid_text = data["paid_text"].format(link=data["paid_link"])
    await message.answer(paid_text)


# ===========================
# ===== АДМИН ПАНЕЛЬ ========
# ===========================

def is_admin(message: types.Message):
    return message.from_user.id == ADMIN_ID


@dp.message_handler(lambda msg: is_admin(msg) and msg.text == "/admin", state="*")
async def admin_panel(message: types.Message, state: FSMContext):
    await state.finish()
    text = (
        "⚙️ <b>Панель администратора</b>\n\n"
        "📝 <b>ПРИВЕТСТВИЕ (сообщение 1):</b>\n"
        "/setwelcome [текст] — изменить текст\n"
        "/setphoto — прикрепить фото (спросит куда)\n"
        "/clearphoto — убрать фото\n\n"
        "💎 <b>ВЫДАЧА (сообщение 2):</b>\n"
        "/setsale [текст] — изменить текст\n"
        "/setphoto — прикрепить фото (спросит куда)\n"
        "/clearphoto — убрать фото\n"
        "/setbutton [текст] — текст кнопки без цены\n\n"
        "💳 <b>ОПЛАТА:</b>\n"
        "/setprice [число] — цена в рублях\n"
        "/settitle [текст] — название товара\n"
        "/setdesc [текст] — описание\n\n"
        "🔗 <b>ПОСЛЕ ОПЛАТЫ:</b>\n"
        "/setlink [ссылка] — ссылка на материал\n"
        "/setpaidtext [текст] — сообщение ({link} = ссылка)\n\n"
        "👁 <b>ПРОСМОТР:</b>\n"
        "/preview — как видит пользователь\n"
        "/status — все настройки\n\n"
        "❌ /cancel — отмена"
    )
    await message.answer(text)


@dp.message_handler(lambda msg: is_admin(msg) and msg.text == "/status", state="*")
async def show_status(message: types.Message, state: FSMContext):
    await state.finish()
    text = (
        "📊 <b>Текущие настройки:</b>\n\n"
        f"1️⃣ <b>Приветствие:</b>\n{data['welcome_text'][:200]}\n"
        f"🖼 Фото: {'✅ Есть' if data.get('welcome_photo') else '❌ Нет'}\n\n"
        f"2️⃣ <b>Выдача:</b>\n{data['sale_text'][:200]}\n"
        f"🖼 Фото: {'✅ Есть' if data.get('sale_photo') else '❌ Нет'}\n"
        f"🔘 Кнопка: 💳 {data['sale_button_text']} {data['price']}₽\n\n"
        f"💰 <b>Цена:</b> {data['price']}₽\n"
        f"📦 <b>Название:</b> {data['product_title']}\n"
        f"🔗 <b>Ссылка:</b> {data['paid_link']}"
    )
    await message.answer(text)


# Превью — показывает ОБА сообщения как видит пользователь
@dp.message_handler(lambda msg: is_admin(msg) and msg.text == "/preview", state="*")
async def preview(message: types.Message, state: FSMContext):
    await state.finish()

    # --- Сообщение 1 ---
    await message.answer("👁 <b>Сообщение 1 — Приветствие:</b>")
    kb1 = InlineKeyboardMarkup()
    kb1.add(InlineKeyboardButton("✅ Забрать", callback_data="show_sale"))

    await send_message_with_or_without_photo(
        chat_id=message.chat.id,
        text=data["welcome_text"],
        photo=data.get("welcome_photo", ""),
        keyboard=kb1
    )

    # --- Сообщение 2 ---
    await message.answer("👁 <b>Сообщение 2 — Выдача:</b>")
    kb2 = InlineKeyboardMarkup()
    kb2.add(InlineKeyboardButton(f"💳 {data['sale_button_text']} {data['price']}₽", callback_data="buy"))

    await send_message_with_or_without_photo(
        chat_id=message.chat.id,
        text=data["sale_text"],
        photo=data.get("sale_photo", ""),
        keyboard=kb2
    )


# ===== ИЗМЕНЕНИЕ ТЕКСТОВ =====

@dp.message_handler(lambda msg: is_admin(msg) and msg.text and msg.text.startswith("/setwelcome "), state="*")
async def set_welcome_text(message: types.Message, state: FSMContext):
    await state.finish()
    new_text = message.text.replace("/setwelcome ", "", 1)
    data["welcome_text"] = new_text
    save_data(data)
    await message.answer(f"✅ Текст <b>приветствия</b> обновлён!\n\n{new_text}")


@dp.message_handler(lambda msg: is_admin(msg) and msg.text and msg.text.startswith("/setsale "), state="*")
async def set_sale_text(message: types.Message, state: FSMContext):
    await state.finish()
    new_text = message.text.replace("/setsale ", "", 1)
    data["sale_text"] = new_text
    save_data(data)
    await message.answer(f"✅ Текст <b>выдачи</b> обновлён!\n\n{new_text}")


@dp.message_handler(lambda msg: is_admin(msg) and msg.text and msg.text.startswith("/setbutton "), state="*")
async def set_button_text(message: types.Message, state: FSMContext):
    await state.finish()
    new_text = message.text.replace("/setbutton ", "", 1)
    data["sale_button_text"] = new_text
    save_data(data)
    await message.answer(f"✅ Кнопка: 💳 {new_text} {data['price']}₽")


@dp.message_handler(lambda msg: is_admin(msg) and msg.text and msg.text.startswith("/setprice "), state="*")
async def set_price(message: types.Message, state: FSMContext):
    await state.finish()
    try:
        price = int(message.text.replace("/setprice ", "", 1))
        data["price"] = price
        save_data(data)
        await message.answer(f"✅ Цена: <b>{price}₽</b>")
    except ValueError:
        await message.answer("❌ Укажите число. Пример: /setprice 490")


@dp.message_handler(lambda msg: is_admin(msg) and msg.text and msg.text.startswith("/settitle "), state="*")
async def set_title(message: types.Message, state: FSMContext):
    await state.finish()
    new_title = message.text.replace("/settitle ", "", 1)
    data["product_title"] = new_title
    save_data(data)
    await message.answer(f"✅ Название: <b>{new_title}</b>")


@dp.message_handler(lambda msg: is_admin(msg) and msg.text and msg.text.startswith("/setdesc "), state="*")
async def set_desc(message: types.Message, state: FSMContext):
    await state.finish()
    new_desc = message.text.replace("/setdesc ", "", 1)
    data["product_description"] = new_desc
    save_data(data)
    await message.answer(f"✅ Описание: <b>{new_desc}</b>")


@dp.message_handler(lambda msg: is_admin(msg) and msg.text and msg.text.startswith("/setlink "), state="*")
async def set_link(message: types.Message, state: FSMContext):
    await state.finish()
    new_link = message.text.replace("/setlink ", "", 1)
    data["paid_link"] = new_link
    save_data(data)
    await message.answer(f"✅ Ссылка: {new_link}")


@dp.message_handler(lambda msg: is_admin(msg) and msg.text and msg.text.startswith("/setpaidtext "), state="*")
async def set_paid_text(message: types.Message, state: FSMContext):
    await state.finish()
    new_text = message.text.replace("/setpaidtext ", "", 1)
    data["paid_text"] = new_text
    save_data(data)
    preview_text = new_text.format(link=data["paid_link"])
    await message.answer(f"✅ Сообщение после оплаты:\n\n{preview_text}")


# ===========================
# ===== ФОТО — FSM FLOW =====
# ===========================

# Шаг 1: /setphoto — просим отправить фото
@dp.message_handler(lambda msg: is_admin(msg) and msg.text == "/setphoto", state="*")
async def cmd_setphoto(message: types.Message, state: FSMContext):
    await state.finish()
    await AdminStates.waiting_for_photo.set()
    await message.answer(
        "📸 Отправьте фото.\n\n"
        "Для отмены: /cancel"
    )


# Шаг 2: Получили фото — спрашиваем куда
@dp.message_handler(
    lambda msg: is_admin(msg),
    content_types=types.ContentType.PHOTO,
    state=AdminStates.waiting_for_photo
)
async def receive_photo(message: types.Message, state: FSMContext):
    # Берём самое качественное фото (последнее в массиве)
    file_id = message.photo[-1].file_id
    print(f"[DEBUG] Получено фото file_id: {file_id}")

    # Сохраняем file_id в памяти FSM
    await state.update_data(pending_photo=file_id)

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("1️⃣ Приветствие (сообщение 1)", callback_data="photo_to_welcome"),
        InlineKeyboardButton("2️⃣ Выдача (сообщение 2)", callback_data="photo_to_sale"),
    )
    await message.answer(
        "✅ Фото получено!\n\n"
        "К какому сообщению прикрепить?",
        reply_markup=kb
    )


# Шаг 3а: Прикрепляем к приветствию (сообщение 1)
@dp.callback_query_handler(lambda c: c.data == "photo_to_welcome", state=AdminStates.waiting_for_photo)
async def attach_to_welcome(callback: types.CallbackQuery, state: FSMContext):
    fsm_data = await state.get_data()
    file_id = fsm_data.get("pending_photo")

    print(f"[DEBUG] Сохраняем фото в welcome_photo: {file_id}")
    data["welcome_photo"] = file_id
    save_data(data)
    await state.finish()

    await callback.message.edit_text(
        "✅ Фото прикреплено к <b>Приветствию (сообщение 1)</b>!\n\n"
        "Напишите /preview чтобы проверить."
    )
    await callback.answer("Сохранено!")


# Шаг 3б: Прикрепляем к выдаче (сообщение 2)
@dp.callback_query_handler(lambda c: c.data == "photo_to_sale", state=AdminStates.waiting_for_photo)
async def attach_to_sale(callback: types.CallbackQuery, state: FSMContext):
    fsm_data = await state.get_data()
    file_id = fsm_data.get("pending_photo")

    print(f"[DEBUG] Сохраняем фото в sale_photo: {file_id}")
    data["sale_photo"] = file_id
    save_data(data)
    await state.finish()

    await callback.message.edit_text(
        "✅ Фото прикреплено к <b>Выдаче (сообщение 2)</b>!\n\n"
        "Напишите /preview чтобы проверить."
    )
    await callback.answer("Сохранено!")


# Если фото прислали вне режима /setphoto — подсказка
@dp.message_handler(
    lambda msg: is_admin(msg),
    content_types=types.ContentType.PHOTO,
    state="*"
)
async def photo_without_state(message: types.Message):
    await message.answer(
        "📸 Получил фото!\n\n"
        "Чтобы прикрепить к сообщению — напишите /setphoto\n"
        "и затем отправьте фото ещё раз."
    )


# Убрать фото
@dp.message_handler(lambda msg: is_admin(msg) and msg.text == "/clearphoto", state="*")
async def clear_photo_menu(message: types.Message, state: FSMContext):
    await state.finish()
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("1️⃣ Убрать из Приветствия", callback_data="clear_welcome_photo"),
        InlineKeyboardButton("2️⃣ Убрать из Выдачи", callback_data="clear_sale_photo"),
    )
    await message.answer("Из какого сообщения убрать фото?", reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data == "clear_welcome_photo", state="*")
async def clear_welcome_photo(callback: types.CallbackQuery):
    data["welcome_photo"] = ""
    save_data(data)
    await callback.message.edit_text("✅ Фото удалено из <b>Приветствия</b>.")
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data == "clear_sale_photo", state="*")
async def clear_sale_photo(callback: types.CallbackQuery):
    data["sale_photo"] = ""
    save_data(data)
    await callback.message.edit_text("✅ Фото удалено из <b>Выдачи</b>.")
    await callback.answer()


# Отмена
@dp.message_handler(lambda msg: is_admin(msg) and msg.text == "/cancel", state="*")
async def cancel(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("❌ Отменено. Напишите /admin для меню.")


# ===========================
# ======= ЗАПУСК ============
# ===========================

if __name__ == "__main__":
    print("🤖 Бот запускается...")
    print(f"✅ Admin ID: {ADMIN_ID}")
    print(f"✅ Цена: {data['price']}₽")
    print(f"✅ Фото приветствия: {data.get('welcome_photo', 'нет')}")
    print(f"✅ Фото выдачи: {data.get('sale_photo', 'нет')}")
    print("🚀 Polling started!")
    executor.start_polling(dp, skip_updates=True)
