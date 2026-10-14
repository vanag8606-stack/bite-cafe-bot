import logging
import os
from html import escape
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.error import TelegramError
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

TOKEN = os.getenv("BITE_CAFE_TOKEN")
ADMIN_ID = os.getenv("BITE_CAFE_ADMIN_ID")

MENU = {
    1: ("Класичний бургер", "burger", 149, "🍔"),
    2: ("Подвійний смаш", "burger", 199, "🍔"),
    3: ("BBQ Бекон", "burger", 209, "🍔"),
    4: ("Кріспі чікен", "burger", 169, "🍗"),
    5: ("Спайсі бургер", "burger", 189, "🌶️"),
    6: ("Пепероні", "pizza", 229, "🍕"),
    7: ("Маргарита", "pizza", 199, "🍕"),
    8: ("Чотири сири", "pizza", 249, "🧀"),
    9: ("BBQ Chicken", "pizza", 259, "🍕"),
    10: ("Картопля фрі", "snack", 69, "🍟"),
    11: ("Сирні кульки", "snack", 99, "🧀"),
    12: ("Курячі нагетси", "snack", 109, "🍗"),
    13: ("Крильця BBQ", "snack", 149, "🍗"),
    14: ("Комбо Bite", "meal", 269, "🍔"),
    15: ("Рол із куркою", "meal", 159, "🌯"),
    16: ("Цезар-рол", "meal", 169, "🌯"),
    17: ("Кола", "drink", 45, "🥤"),
    18: ("Домашній лимонад", "drink", 69, "🍋"),
    19: ("Айс-лате", "drink", 79, "🧋"),
    20: ("Мілкшейк", "drink", 89, "🥤"),
    21: ("Пончик", "dessert", 59, "🍩"),
    22: ("Чізкейк", "dessert", 99, "🍰"),
    23: ("Брауні", "dessert", 79, "🍫"),
    24: ("Морозиво", "dessert", 75, "🍦"),
}
CATEGORIES = {
    "burger": "🍔 Бургери", "pizza": "🍕 Піца", "snack": "🍟 Закуски",
    "meal": "🌯 Комбо й роли", "drink": "🥤 Напої", "dessert": "🍰 Десерти"
}

def total(cart):
    return sum(MENU[i][2] * q for i, q in cart.items())

def home_keyboard():
    keys = list(CATEGORIES.items())
    rows = []
    for n in range(0, len(keys), 2):
        row = [InlineKeyboardButton(keys[n][1], callback_data=f"cat_{keys[n][0]}")]
        if n + 1 < len(keys):
            row.append(InlineKeyboardButton(keys[n+1][1], callback_data=f"cat_{keys[n+1][0]}"))
        rows.append(row)
    rows += [[InlineKeyboardButton("📋 Усе меню", callback_data="all_menu")],
             [InlineKeyboardButton("🛒 Мій кошик", callback_data="cart")]]
    return InlineKeyboardMarkup(rows)

def product_keyboard(category=None):
    rows = []
    for i, (name, cat, price, emoji) in MENU.items():
        if category is None or category == cat:
            rows.append([InlineKeyboardButton(f"{emoji} {name} · {price} ₴", callback_data=f"add_{i}")])
    rows += [[InlineKeyboardButton("🛒 Кошик", callback_data="cart")],
             [InlineKeyboardButton("↩ До категорій", callback_data="home")]]
    return InlineKeyboardMarkup(rows)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cart = context.user_data.setdefault("cart", {})
    context.user_data.pop("step", None)
    # The website passes cart_<base36 item id><base36 quantity>... as a Telegram start payload.
    if context.args and context.args[0].startswith("cart_"):
        encoded = context.args[0][5:]
        new_cart = {}
        valid = bool(encoded) and len(encoded) % 2 == 0
        if valid:
            try:
                for p in range(0, len(encoded), 2):
                    item_id, qty = int(encoded[p], 36), int(encoded[p+1], 36)
                    if item_id not in MENU or not 1 <= qty <= 35:
                        valid = False
                        break
                    new_cart[item_id] = qty
            except ValueError:
                valid = False
        if valid and new_cart:
            cart.clear()
            cart.update(new_cart)
            lines = [f"{MENU[i][3]} {escape(MENU[i][0])} × {q} — {MENU[i][2]*q} ₴" for i, q in cart.items()]
            await update.effective_message.reply_text(
                "🛒 <b>Твоє замовлення з сайту Bite Cafe</b>\n\n" +
                "\n".join(lines) + f"\n\n<b>Разом: {total(cart)} ₴</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Далі", callback_data="checkout")],
                    [InlineKeyboardButton("🗑 Очистити кошик", callback_data="clear_cart")],
                    [InlineKeyboardButton("🍽 Додати ще страви", callback_data="home")],
                ])
            )
            return
        await update.effective_message.reply_text("Не вдалося прочитати кошик із сайту. Спробуй ще раз.", reply_markup=home_keyboard())
        return
    await update.effective_message.reply_text(
        "👋 <b>Вітаємо в Bite Cafe!</b>\n\nОбирай страви в меню або переходь із кошиком із сайту.",
        parse_mode="HTML", reply_markup=home_keyboard()
    )

async def show_cart(update, context):
    cart = context.user_data.setdefault("cart", {})
    if not cart:
        await update.callback_query.edit_message_text("🛒 Кошик порожній.", reply_markup=home_keyboard())
        return
    lines = [f"{MENU[i][3]} {escape(MENU[i][0])} × {q} — {MENU[i][2]*q} ₴" for i, q in cart.items()]
    await update.callback_query.edit_message_text(
        "🛒 <b>Твій кошик</b>\n\n" + "\n".join(lines) + f"\n\n<b>Разом: {total(cart)} ₴</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Оформити замовлення", callback_data="checkout")],
            [InlineKeyboardButton("🗑 Очистити кошик", callback_data="clear_cart")],
            [InlineKeyboardButton("🍽 Продовжити вибір", callback_data="home")],
        ])
    )

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data or ""

    if data.startswith(("order_ok_", "order_no_")):
        if not ADMIN_ID or str(q.from_user.id) != str(ADMIN_ID):
            await q.answer("Тільки адміністратор може обробляти замовлення.", show_alert=True)
            return
        try:
            oid = int(data.rsplit("_", 1)[1])
        except ValueError:
            return
        orders = context.application.bot_data.setdefault("pending_orders", {})
        order = orders.pop(oid, None)
        if not order:
            await q.edit_message_reply_markup(reply_markup=None)
            await q.message.reply_text("Замовлення вже оброблено або бот перезапускався.")
            return
        accepted = data.startswith("order_ok_")
        try:
            await context.bot.send_message(
                chat_id=order["customer_id"],
                text=("✅ Твоє замовлення Bite Cafe підтверджено! Очікуй доставку."
                      if accepted else "❌ На жаль, кафе відхилило твоє замовлення. Зв’яжись із кафе для уточнення.")
            )
        except TelegramError:
            await q.message.reply_text("Не вдалося повідомити клієнта — можливо, він заблокував бота.")
        status = "✅ ПІДТВЕРДЖЕНО" if accepted else "❌ ВІДХИЛЕНО"
        await q.edit_message_text((q.message.text or "Замовлення") + f"\n\n<b>Статус: {status}</b>", parse_mode="HTML")
        return

    cart = context.user_data.setdefault("cart", {})
    if data == "home":
        await q.edit_message_text("🍔 <b>Меню Bite Cafe</b>\n\nОбери категорію або переглянь усі страви.", parse_mode="HTML", reply_markup=home_keyboard())
    elif data == "all_menu":
        await q.edit_message_text("📋 <b>Усе меню</b>\n\nОбери страву:", parse_mode="HTML", reply_markup=product_keyboard())
    elif data.startswith("cat_"):
        cat = data[4:]
        if cat in CATEGORIES:
            await q.edit_message_text(f"<b>{escape(CATEGORIES[cat])}</b>\n\nОбери страву:", parse_mode="HTML", reply_markup=product_keyboard(cat))
    elif data.startswith("add_"):
        try:
            i = int(data[4:])
        except ValueError:
            i = -1
        if i in MENU:
            cart[i] = cart.get(i, 0) + 1
            await q.message.reply_text(
                f"✅ Додано {MENU[i][3]} <b>{escape(MENU[i][0])}</b>. Разом у кошику: {total(cart)} ₴",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Кошик", callback_data="cart")],
                                                   [InlineKeyboardButton("🍽 Продовжити", callback_data="home")]])
            )
    elif data == "cart":
        await show_cart(update, context)
    elif data == "clear_cart":
        cart.clear()
        await q.edit_message_text("Кошик очищено.", reply_markup=home_keyboard())
    elif data == "checkout":
        if not cart:
            await q.edit_message_text("Кошик порожній.", reply_markup=home_keyboard())
            return
        context.user_data["step"] = "name"
        await q.message.reply_text("Як тебе звати? Напиши ім’я для замовлення.")
    elif data in ("pay_cash", "pay_transfer"):
        await send_order(update, context, "Готівкою при отриманні" if data == "pay_cash" else "Переказом")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("step")
    if not step:
        await update.message.reply_text("Щоб почати, натисни /start.")
        return
    value = (update.message.text or "").strip()
    if step == "name":
        if len(value) < 2:
            await update.message.reply_text("Напиши ім’я трохи повніше.")
            return
        context.user_data["customer_name"] = value[:100]
        context.user_data["step"] = "phone"
        await update.message.reply_text("Напиши номер телефону або натисни кнопку нижче.",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("📱 Поділитися номером", request_contact=True)]],
                                             resize_keyboard=True, one_time_keyboard=True))
    elif step == "phone":
        if len(value) < 5:
            await update.message.reply_text("Вкажи коректний номер телефону.")
            return
        context.user_data["customer_phone"] = value[:50]
        context.user_data["step"] = "address"
        await update.message.reply_text("📍 Напиши адресу доставки.", reply_markup=ReplyKeyboardRemove())
    elif step == "address":
        if len(value) < 5:
            await update.message.reply_text("Напиши адресу трохи докладніше.")
            return
        context.user_data["customer_address"] = value[:300]
        context.user_data["step"] = "payment"
        await update.message.reply_text("Як будеш оплачувати?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💵 Готівкою при отриманні", callback_data="pay_cash")],
                [InlineKeyboardButton("💳 Переказом", callback_data="pay_transfer")],
            ]))

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step") == "phone" and update.message.contact:
        context.user_data["customer_phone"] = update.message.contact.phone_number[:50]
        context.user_data["step"] = "address"
        await update.message.reply_text("📍 Напиши адресу доставки.", reply_markup=ReplyKeyboardRemove())
    else:
        await handle_text(update, context)

async def send_order(update: Update, context: ContextTypes.DEFAULT_TYPE, payment: str):
    cart = context.user_data.setdefault("cart", {})
    if not cart:
        await update.callback_query.message.reply_text("Кошик порожній. Натисни /start.")
        return
    if not ADMIN_ID:
        await update.callback_query.message.reply_text("⚠️ Не налаштовано BITE_CAFE_ADMIN_ID. Власник має додати свій Telegram ID.")
        return
    user = update.effective_user
    lines = [f"• {MENU[i][0]} × {qty} — {MENU[i][2]*qty} ₴" for i, qty in cart.items()]
    text = (
        "🆕 <b>НОВЕ ЗАМОВЛЕННЯ · BITE CAFE</b>\n\n"
        f"<b>Ім’я:</b> {escape(context.user_data.get('customer_name', '—'))}\n"
        f"<b>Телефон:</b> {escape(context.user_data.get('customer_phone', '—'))}\n"
        f"<b>Telegram:</b> @{escape(user.username or 'не вказано')} (ID {user.id})\n"
        f"<b>Адреса:</b> {escape(context.user_data.get('customer_address', '—'))}\n"
        f"<b>Оплата:</b> {escape(payment)}\n\n" + "\n".join(escape(line) for line in lines)
        + f"\n\n<b>РАЗОМ: {total(cart)} ₴</b>"
    )
    orders = context.application.bot_data.setdefault("pending_orders", {})
    oid = context.application.bot_data.get("order_counter", 0) + 1
    context.application.bot_data["order_counter"] = oid
    orders[oid] = {"customer_id": user.id}
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Підтвердити", callback_data=f"order_ok_{oid}"),
        InlineKeyboardButton("❌ Відхилити", callback_data=f"order_no_{oid}"),
    ]])
    try:
        await context.bot.send_message(chat_id=int(ADMIN_ID), text=text, parse_mode="HTML", reply_markup=keyboard)
    except (ValueError, TelegramError):
        orders.pop(oid, None)
        logging.exception("Could not send order to admin")
        await update.callback_query.message.reply_text("⚠️ Не вдалося надіслати замовлення. Перевір ADMIN ID.")
        return
    await update.callback_query.message.reply_text("✅ Замовлення надіслано кафе! Очікуй підтвердження.")
    cart.clear()
    for key in ("step", "customer_name", "customer_phone", "customer_address"):
        context.user_data.pop(key, None)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("step", None)
    await update.effective_message.reply_text("Оформлення скасовано. Натисни /start, щоб почати знову.", reply_markup=ReplyKeyboardRemove())

async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(f"Твій Telegram ID: {update.effective_user.id}")

def main():
    if not TOKEN:
        raise RuntimeError('Не задано BITE_CAFE_TOKEN. У PowerShell введи: $env:BITE_CAFE_TOKEN="ТВІЙ_ТОКЕН"')
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("id", my_id))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("Bite Cafe bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
