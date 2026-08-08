import asyncio
import logging
import random
import aiosqlite
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
    LabeledPrice,
    PreCheckoutQuery
)

# -------------------------------------------------------------------
# КОНФИГУРАЦИЯ БОТА И МИНИ-ПРИЛОЖЕНИЯ EDGE GIFT
# -------------------------------------------------------------------
BOT_TOKEN = "8703953789:AAHDQfshxYkC_tNC7WL0-z9YeOoafpFxwtk"  # 👈 Вставьте ваш токен от BotFather
WEBAPP_URL = "http://localhost:8080"    # 👈 Ваша ссылка на WebApp (или ngrok/VPS ссылка)

ADMIN_IDS = [6629617970] # 👈 Укажите ваш Telegram ID
DB_NAME = "edge_gift_webapp.db"
STARS_RATE = 10  # 1 Star = 10 🪙

logging.basicConfig(level=logging.INFO)

# -------------------------------------------------------------------
# КЕЙСЫ И НАГРАДЫ EDGE GIFT WEB APP
# -------------------------------------------------------------------
CASES = {
    "starter": {
        "name": "🎁 Starter Box",
        "price": 100,
        "items": [
            {"name": "🌟 Telegram Star (x10)", "price": 15, "icon": "🌟", "rarity": "⚪ Обычный"},
            {"name": "🎁 Delicious Cake", "price": 50, "icon": "🎁", "rarity": "🔵 Редкий"},
            {"name": "🎁 Red Star Gift", "price": 140, "icon": "🎁", "rarity": "🟣 Эпический"},
            {"name": "🎁 Plush Bear", "price": 750, "icon": "🧸", "rarity": "🔴 Эксклюзив"},
            {"name": "🖼 Santa Hat NFT (#1204)", "price": 4200, "icon": "🖼", "rarity": "🟡 Fragment NFT"},
        ]
    },
    "stars": {
        "name": "⭐ Stars Box",
        "price": 500,
        "items": [
            {"name": "🎁 Heart Gift", "price": 120, "icon": "💖", "rarity": "🔵 Редкий"},
            {"name": "🎁 Party Sparkler", "price": 380, "icon": "🎉", "rarity": "🟣 Эпический"},
            {"name": "📱 Номер +888 0102", "price": 1200, "icon": "📱", "rarity": "🔴 Fragment NFT"},
            {"name": "🖼 Pepe NFT (#888)", "price": 4500, "icon": "🖼", "rarity": "🟡 Легендарный"},
            {"name": "🖼 Spotted Dog (#420)", "price": 14000, "icon": "🐶", "rarity": "💎 Мифический"},
        ]
    },
    "vip": {
        "name": "💎 High Roller NFT",
        "price": 2500,
        "items": [
            {"name": "🎁 Precious Peach", "price": 850, "icon": "🍑", "rarity": "🟣 Эпический"},
            {"name": "📱 Номер +888 7777", "price": 3200, "icon": "📱", "rarity": "🔴 Fragment NFT"},
            {"name": "🖼 Astral Skull (#66)", "price": 15000, "icon": "💀", "rarity": "🟡 Легендарный"},
            {"name": "🏷 @crypto Fragment", "price": 45000, "icon": "🏷", "rarity": "💎 Мифический"},
            {"name": "🏷 @durov Fragment", "price": 150000, "icon": "👑", "rarity": "👑 Durov NFT"},
        ]
    }
}

# -------------------------------------------------------------------
# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
# -------------------------------------------------------------------
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance REAL DEFAULT 1000.0,
                cases_opened INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_name TEXT,
                item_price REAL,
                item_icon TEXT
            )
        """)
        await db.commit()

async def get_or_create_user(user_id: int, username: str = "Player"):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id, username, balance, cases_opened FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await db.execute("INSERT INTO users (user_id, username, balance) VALUES (?, ?, 1000.0)", (user_id, username))
                await db.commit()
                return {"user_id": user_id, "username": username, "balance": 1000.0, "cases_opened": 0}
            return {"user_id": row[0], "username": row[1], "balance": row[2], "cases_opened": row[3]}

async def update_user_balance(user_id: int, amount: float):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

# -------------------------------------------------------------------
# TELEGRAM BOT HANDLERS (Aiogram 3)
# -------------------------------------------------------------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await get_or_create_user(message.from_user.id, message.from_user.first_name)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🚀 Открыть Edge Gift Mini App", 
            web_app=WebAppInfo(url=WEBAPP_URL)
        )
    ]])

    text = (
        f"🎁 <b>Добро пожаловать в Edge Gift WebApp!</b>\n\n"
        f"Нажмите кнопку ниже, чтобы открыть графический веб-интерфейс, "
        f"крутить рулетку Telegram Gifts, соревноваться в Edge Battles и забирать редкие Fragment NFT! 💎"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    payload = message.successful_payment.invoice_payload
    if payload.startswith("stars_topup:"):
        stars = int(payload.split(":")[1])
        coins = stars * STARS_RATE
        await update_user_balance(message.from_user.id, coins)
        await message.answer(f"🎉 <b>Успешно!</b> Зачислено: <b>+{coins:,} 🪙</b> (Оплата {stars} Stars)!", parse_mode="HTML")

# -------------------------------------------------------------------
# AIOHTTP WEB SERVER FOR MINI APP FRONTEND & API
# -------------------------------------------------------------------
async def handle_webapp_index(request):
    # Возвращаем графический интерфейс Edge Gift
    return web.FileResponse('edge_gift_app.html')

async def handle_get_user(request):
    user_id = int(request.query.get("user_id", 0))
    if not user_id:
        return web.json_response({"error": "Invalid user_id"}, status=400)
    user = await get_or_create_user(user_id)
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT item_name, item_price, item_icon FROM inventory WHERE user_id = ?", (user_id,)) as cursor:
            inventory = await cursor.fetchall()

    inv_list = [{"name": row[0], "price": row[1], "icon": row[2]} for row in inventory]
    return web.json_response({"user": user, "inventory": inv_list})

async def handle_open_case(request):
    data = await request.json()
    user_id = int(data.get("user_id", 0))
    case_key = data.get("case_key", "starter")

    case = CASES.get(case_key, CASES["starter"])
    user = await get_or_create_user(user_id)

    if user["balance"] < case["price"]:
        return web.json_response({"error": "Недостаточно средств"}, status=400)

    # Списываем стоимость
    await update_user_balance(user_id, -case["price"])

    # Выбираем рандомный предмет
    won_item = random.choice(case["items"])

    # Добавляем в инвентарь
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO inventory (user_id, item_name, item_price, item_icon) VALUES (?, ?, ?, ?)",
                         (user_id, won_item["name"], won_item["price"], won_item["icon"]))
        await db.execute("UPDATE users SET cases_opened = cases_opened + 1 WHERE user_id = ?", (user_id,))
        await db.commit()

    updated_user = await get_or_create_user(user_id)
    return web.json_response({"item": won_item, "new_balance": updated_user["balance"]})

async def handle_sell_all(request):
    data = await request.json()
    user_id = int(data.get("user_id", 0))

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT SUM(item_price) FROM inventory WHERE user_id = ?", (user_id,)) as cursor:
            res = await cursor.fetchone()
            total_price = res[0] or 0.0

        if total_price > 0:
            await db.execute("DELETE FROM inventory WHERE user_id = ?", (user_id,))
            await db.commit()
            await update_user_balance(user_id, total_price)

    updated_user = await get_or_create_user(user_id)
    return web.json_response({"sold_amount": total_price, "new_balance": updated_user["balance"]})

async def handle_pay_stars(request):
    data = await request.json()
    user_id = int(data.get("user_id", 0))
    stars = int(data.get("stars", 10))

    coins = stars * STARS_RATE
    prices = [LabeledPrice(label=f"{coins:,} 🪙", amount=stars)]

    try:
        invoice_link = await bot.create_invoice_link(
            title=f"Edge Gift: +{coins:,} 🪙",
            description=f"Покупка {stars} Telegram Stars (Курс 1:10)",
            payload=f"stars_topup:{stars}",
            provider_token="",  # Пусто для Telegram Stars
            currency="XTR",
            prices=prices
        )
        return web.json_response({"invoice_link": invoice_link})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

# -------------------------------------------------------------------
# ЗАПУСК СЕРВЕРА И БОТА
# -------------------------------------------------------------------
async def start_app():
    await init_db()

    app = web.Application()
    app.router.add_get('/', handle_webapp_index)
    app.router.add_get('/api/user', handle_get_user)
    app.router.add_post('/api/open_case', handle_open_case)
    app.router.add_post('/api/sell_all', handle_sell_all)
    app.router.add_post('/api/pay_stars', handle_pay_stars)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("🌐 WebApp сервер Edge Gift запущен на порту 8080!")

async def main():
    await start_app()
    print("🤖 Telegram Bot Edge Gift запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
