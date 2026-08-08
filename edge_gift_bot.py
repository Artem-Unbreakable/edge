import asyncio
import logging
import random
import os
import aiosqlite
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, LabeledPrice, PreCheckoutQuery

BOT_TOKEN = "ВАШ_ТОКЕН_ОТ_BOTFATHER"  # 👈 Вставьте ваш токен от BotFather
WEBAPP_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:8080")

DB_NAME = "edge_gift_webapp.db"
STARS_RATE = 10

logging.basicConfig(level=logging.INFO)

CASES = {
    "starter": {
        "name": "🎁 Starter Box",
        "price": 100,
        "items": [
            {"name": "🌟 Telegram Star (x10)", "price": 15, "icon": "🌟"},
            {"name": "🎁 Delicious Cake", "price": 50, "icon": "🎁"},
            {"name": "🎁 Red Star Gift", "price": 140, "icon": "🎁"},
            {"name": "🎁 Plush Bear", "price": 750, "icon": "🧸"},
            {"name": "🖼 Santa Hat NFT", "price": 4200, "icon": "🖼"},
        ]
    },
    "stars": {
        "name": "⭐ Stars Box",
        "price": 500,
        "items": [
            {"name": "🎁 Heart Gift", "price": 120, "icon": "💖"},
            {"name": "🎁 Party Sparkler", "price": 380, "icon": "🎉"},
            {"name": "📱 Номер +888 0102", "price": 1200, "icon": "📱"},
            {"name": "🖼 Pepe NFT (#888)", "price": 4500, "icon": "🖼"},
            {"name": "🖼 Spotted Dog (#420)", "price": 14000, "icon": "🐶"},
        ]
    },
    "vip": {
        "name": "💎 High Roller NFT",
        "price": 2500,
        "items": [
            {"name": "🎁 Precious Peach", "price": 850, "icon": "🍑"},
            {"name": "📱 Номер +888 7777", "price": 3200, "icon": "📱"},
            {"name": "🖼 Astral Skull (#66)", "price": 15000, "icon": "💀"},
            {"name": "🏷 @crypto Fragment", "price": 45000, "icon": "🏷"},
            {"name": "🏷 @durov Fragment", "price": 150000, "icon": "👑"},
        ]
    }
}

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance REAL DEFAULT 1000.0
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
        async with db.execute("SELECT user_id, username, balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await db.execute("INSERT INTO users (user_id, username, balance) VALUES (?, ?, 1000.0)", (user_id, username))
                await db.commit()
                return {"user_id": user_id, "username": username, "balance": 1000.0}
            return {"user_id": row[0], "username": row[1], "balance": row[2]}

async def update_user_balance(user_id: int, amount: float):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

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
        f"Нажмите кнопку ниже, чтобы запустить графическое приложение с рулеткой кейсов!"
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
        await message.answer(f"🎉 Зачислено: <b>+{coins:,} 🪙</b>!", parse_mode="HTML")

# HTTP handlers для Mini App
async def handle_webapp_index(request):
    return web.FileResponse('edge_gift_app.html')

async def handle_get_user(request):
    user_id = int(request.query.get("user_id", 123456789))
    user = await get_or_create_user(user_id)
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT item_name, item_price, item_icon FROM inventory WHERE user_id = ?", (user_id,)) as cursor:
            inventory = await cursor.fetchall()

    inv_list = [{"name": row[0], "price": row[1], "icon": row[2]} for row in inventory]
    return web.json_response({"user": user, "inventory": inv_list})

async def handle_open_case(request):
    data = await request.json()
    user_id = int(data.get("user_id", 123456789))
    case_key = data.get("case_key", "starter")

    case = CASES.get(case_key, CASES["starter"])
    user = await get_or_create_user(user_id)

    if user["balance"] < case["price"]:
        return web.json_response({"error": "Недостаточно монет!"}, status=400)

    await update_user_balance(user_id, -case["price"])
    won_item = random.choice(case["items"])

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO inventory (user_id, item_name, item_price, item_icon) VALUES (?, ?, ?, ?)",
                         (user_id, won_item["name"], won_item["price"], won_item["icon"]))
        await db.commit()

    return web.json_response({"item": won_item})

async def handle_sell_all(request):
    data = await request.json()
    user_id = int(data.get("user_id", 123456789))

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT SUM(item_price) FROM inventory WHERE user_id = ?", (user_id,)) as cursor:
            res = await cursor.fetchone()
            total_price = res[0] or 0.0

        if total_price > 0:
            await db.execute("DELETE FROM inventory WHERE user_id = ?", (user_id,))
            await db.commit()
            await update_user_balance(user_id, total_price)

    return web.json_response({"sold_amount": total_price})

async def handle_pay_stars(request):
    data = await request.json()
    stars = int(data.get("stars", 10))
    coins = stars * STARS_RATE
    prices = [LabeledPrice(label=f"{coins:,} 🪙", amount=stars)]

    try:
        invoice_link = await bot.create_invoice_link(
            title=f"Edge Gift: +{coins:,} 🪙",
            description=f"Покупка {stars} Telegram Stars",
            payload=f"stars_topup:{stars}",
            provider_token="",
            currency="XTR",
            prices=prices
        )
        return web.json_response({"invoice_link": invoice_link})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def start_app():
    await init_db()
    app = web.Application()
    app.router.add_get('/', handle_webapp_index)
    app.router.add_get('/api/user', handle_get_user)
    app.router.add_post('/api/open_case', handle_open_case)
    app.router.add_post('/api/sell_all', handle_sell_all)
    app.router.add_post('/api/pay_stars', handle_pay_stars)

    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌐 WebApp запущен на порту {port}")

async def main():
    await start_app()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
