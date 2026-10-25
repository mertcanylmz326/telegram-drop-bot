import asyncio
import sqlite3
import logging
import os
import threading
import aiohttp
from http.server import HTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# --- RENDER PORT HATASI ÇÖZÜCÜ (MİNİ WEB SUNUCUSU) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive and running!")

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# Arka planda portu açık tutmak için web sunucusunu başlatıyoruz
threading.Thread(target=run_health_server, daemon=True).start()

# --- AYARLAR ---
BOT_TOKEN = "8994954068:AAFWrg9dLaMrXkK2uR2vpTTNke84vn449RM"
ADMIN_ID = 1012940363
CRYPTO_WALLET = "TMDAC83GTrxDCQiQBCEEL11CdHBYPSMpjH"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"  # Tron ağındaki resmi USDT kontratı

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- VERİTABANI KURULUMU ---
def init_db():
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS drops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            price REAL,
            location_url TEXT,
            photo_ids TEXT,
            description TEXT,
            is_sold INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            drop_id INTEGER,
            status TEXT DEFAULT 'pending'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- FSM DURUMLARI ---
class AddDrop(StatesGroup):
    title = State()
    price = State()
    location = State()
    photo = State()
    description = State()

# --- KULLANICI MENÜSÜ ---
def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍️ Ürünler / Droplar")],
            [KeyboardButton(text="❓ Nasıl Çalışır?"), KeyboardButton(text="📞 Destek")]
        ],
        resize_keyboard=True
    )

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Merhaba! Otomatik teslimat botuna hoş geldiniz.\n\n"
        "Aşağıdaki menüden mevcut dropları inceleyebilir ve sipariş verebilirsiniz.",
        reply_markup=main_keyboard()
    )

# --- ÜRÜN LİSTELEME ---
@dp.message(F.text == "🛍️ Ürünler / Droplar")
async def list_drops(message: types.Message):
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, price FROM drops WHERE is_sold = 0")
    drops = cursor.fetchall()
    conn.close()

    if not drops:
        await message.answer("❌ Şu anda stokta hazır drop bulunmamaktadır.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for drop in drops:
        drop_id, title, price = drop
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"{title} - {price} USDT", callback_data=f"buy_{drop_id}")
        ])

    await message.answer("📦 Satın almak istediğiniz drop'u seçin:", reply_markup=kb)

# --- SİPARİŞ OLUŞTURMA ---
@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: types.CallbackQuery):
    drop_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id

    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT title, price FROM drops WHERE id = ? AND is_sold = 0", (drop_id,))
    drop = cursor.fetchone()

    if not drop:
        await callback.answer("⚠️ Bu ürün tükenmiş veya başka biri tarafından alınmış.", show_alert=True)
        conn.close()
        return

    title, price = drop
    
    cursor.execute("INSERT INTO orders (user_id, drop_id) VALUES (?, ?)", (user_id, drop_id))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    payment_text = (
        f"✅ Sipariş Oluşturuldu! (Sipariş No: #{order_id})\n\n"
        f"📌 Ürün: {title}\n"
        f"💰 Tutar: {price} USDT\n\n"
        "🔒 Ödeme Yöntemi (USDT TRC20):\n"
        "Lütfen aşağıdaki cüzdan adresine **tam olarak bu tutarı** gönderin:\n\n"
        f"`{CRYPTO_WALLET}`\n\n"
        "⚠️ Ödemeyi yaptıktan sonra aşağıdaki **'Ödemeyi Otomatik Kontrol Et'** butonuna basın.\n"
        "Sistem blokzinciri tarayıp onaylandığı an konum ve fotoğrafları otomatik gönderecektir."
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Ödemeyi Otomatik Kontrol Et", callback_data=f"autocheck_{order_id}")]
    ])

    await callback.message.edit_text(payment_text, reply_markup=kb)

# --- TAM OTOMATİK BLOKZİNCİR ÖDEME KONTROLÜ ---
@dp.callback_query(F.data.startswith("autocheck_"))
async def check_blockchain_payment(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    
    await callback.answer("Blokzincir taranıyor, lütfen bekleyin...", show_alert=True)

    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT orders.user_id, drops.id, drops.price, drops.location_url, drops.photo_ids, drops.description, orders.status 
        FROM orders 
        JOIN drops ON orders.drop_id = drops.id 
        WHERE orders.id = ?
    """, (order_id,))
    data = cursor.fetchone()

    if not data:
        await callback.answer("Sipariş bulunamadı.", show_alert=True)
        conn.close()
        return

    user_id, drop_id, expected_price, location_url, photo_ids, description, status = data

    if status == 'completed':
        await callback.answer("Bu sipariş zaten onaylanmış ve teslim edilmiştir.", show_alert=True)
        conn.close()
        return

    # TronGrid API ile cüzdana gelen son USDT transferlerini çekiyoruz
    api_url = f"https://api.trongrid.io/v1/accounts/{CRYPTO_WALLET}/trc20-transfers?contract_address={USDT_CONTRACT}&limit=10"
    
    payment_verified = False
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status == 200:
                    res_json = await response.json()
                    transfers = res_json.get("data", [])
                    
                    # USDT 6 basamaklı hassasiyete sahiptir (Örn: 10 USDT = 10000000)
                    expected_value_scaled = int(float(expected_price) * 1000000)

                    for tx in transfers:
                        # Cüzdanımıza gelen transferleri kontrol ediyoruz
                        if tx.get("to") == CRYPTO_WALLET:
                            tx_value = int(tx.get("value", 0))
                            # Tutar eşleşmesini kontrol ediyoruz (küçük kuruş farklarına tolerans bırakılabilir veya birebir eşleşme)
                            if tx_value >= expected_value_scaled:
                                payment_verified = True
                                break
    except Exception as e:
        logging.error(f"API Hatası: {e}")

    if payment_verified:
        # Ödeme doğrulandı! Ürünü stoktan düş ve otomatik teslim et
        cursor.execute("UPDATE drops SET is_sold = 1 WHERE id = ?", (drop_id,))
        cursor.execute("UPDATE orders SET status = 'completed' WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()

        msg_text = (
            "🎉 Ödemeniz Blokzincir Üzerinden Otomatik Onaylandı!\n\n"
            f"📍 Konum Linki: {location_url}\n"
            f"📝 Açıklama/Not: {description}\n\n"
            "⚠️ Lütfen ürünü teslim aldıktan sonra bölgeden hızlıca ayrılın."
        )
        
        await callback.message.edit_text(f"✅ Sipariş #{order_id} için ödeme blokzincirde doğrulandı ve bilgiler müşteriye iletildi.")
        
        await bot.send_message(user_id, msg_text)
        if photo_ids:
            for p_id in photo_ids.split(","):
                if p_id.strip():
                    await bot.send_photo(user_id, p_id.strip())
    else:
        conn.close()
        await callback.answer(
            "⚠️ Henüz cüzdanınıza yansıyan eşleşen bir USDT transferi bulunamadı. "
            "Transferin ağda onaylanması 1-2 dakika sürebilir, lütfen biraz sonra tekrar deneyin.", 
            show_alert=True
        )

# --- ADMIN PANELİ ---
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yeni Drop Ekle", callback_data="add_drop")]
    ])
    await message.answer("👑 Admin Paneli (Tam Otomatik Mod)", reply_markup=kb)

@dp.callback_query(F.data == "add_drop")
async def start_add_drop(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AddDrop.title)
    await callback.message.answer("1️⃣ Drop için bir Başlık/İsim girin:")

@dp.message(AddDrop.title)
async def process_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AddDrop.price)
    await message.answer("2️⃣ Fiyatı girin (**USDT cinsinden**, örn: 20):")

@dp.message(AddDrop.price)
async def process_price(message: types.Message, state: FSMContext):
    await state.update_data(price=float(message.text))
    await state.set_state(AddDrop.location)
    await message.answer("3️⃣ Google Maps / Konum Linkini girin:")

@dp.message(AddDrop.location)
async def process_location(message: types.Message, state: FSMContext):
    await state.update_data(location=message.text)
    await state.set_state(AddDrop.photo)
    await message.answer("4️⃣ Drop yerinin Fotoğrafını gönderin (Sadece 1 adet):")

@dp.message(AddDrop.photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await state.set_state(AddDrop.description)
    await message.answer("5️⃣ Müşteri için Açıklama / İpucu Notu girin:")

@dp.message(AddDrop.description)
async def process_desc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO drops (title, price, location_url, photo_ids, description)
        VALUES (?, ?, ?, ?, ?)
    """, (data['title'], data['price'], data['location'], data['photo'], message.text))
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer("✅ Yeni Drop Başarıyla Veritabanına Eklendi ve Stoğa Girdi!")

# --- BOTU BAŞLATMA ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
