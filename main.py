import asyncio
import sqlite3
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# --- AYARLAR ---
BOT_TOKEN = "6884909797:AAG7eXs6_whJCNkWpoDInGrYGCg92Yn2_fM"
ADMIN_ID = 1012940363

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
            InlineKeyboardButton(text=f"{title} - {price} TL", callback_data=f"buy_{drop_id}")
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
        f"✅ **Sipariş Oluşturuldu!** (Sipariş No: #{order_id})\n\n"
        f"📌 **Ürün:** {title}\n"
        f"💰 **Tutar:** {price} TL\n\n"
        "💳 **Ödeme Yöntemi:**\n"
        "Lütfen ödemeyi yaptıktan sonra aşağıdaki onay butonuna basın.\n"
        "Ödeme onaylandığı an konum ve fotoğraflar otomatik olarak iletilecektir."
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ödemeyi Yaptım (Onay İste)", callback_data=f"payonay_{order_id}")]
    ])

    await callback.message.edit_text(payment_text, reply_markup=kb, parse_mode="Markdown")

# --- ÖDEME BİLDİRİMİ ---
@dp.callback_query(F.data.startswith("payonay_"))
async def process_payment_notification(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    
    await callback.answer("Ödeme bildiriminiz yöneticilere iletildi. İnceleniyor...", show_alert=True)
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ödemeyi Onayla & Konumu Gönder", callback_data=f"adm_approve_{order_id}"),
            InlineKeyboardButton(text="❌ Reddet", callback_data=f"adm_reject_{order_id}")
        ]
    ])

    await bot.send_message(
        ADMIN_ID, 
        f"🔔 **YENİ ÖDEME BİLDİRİMİ**\n\nSipariş No: #{order_id}\nKullanıcı ID: `{callback.from_user.id}`",
        reply_markup=admin_kb,
        parse_mode="Markdown"
    )

# --- ADMIN: ÖDEME ONAYLAMA ---
@dp.callback_query(F.data.startswith("adm_approve_"))
async def admin_approve(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    order_id = int(callback.data.split("_")[2])

    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT orders.user_id, drops.id, drops.location_url, drops.photo_ids, drops.description 
        FROM orders 
        JOIN drops ON orders.drop_id = drops.id 
        WHERE orders.id = ?
    """, (order_id,))
    data = cursor.fetchone()

    if not data:
        await callback.answer("Sipariş bulunamadı.")
        conn.close()
        return

    user_id, drop_id, location_url, photo_ids, description = data

    cursor.execute("UPDATE drops SET is_sold = 1 WHERE id = ?", (drop_id,))
    cursor.execute("UPDATE orders SET status = 'completed' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()

    msg_text = (
        "🎉 **Ödemeniz Onaylandı!**\n\n"
        f"📍 **Konum Linki:** {location_url}\n"
        f"📝 **Açıklama/Not:** {description}\n\n"
        "⚠️ *Lütfen ürünü teslim aldıktan sonra bölgeden hızlıca ayrılın.*"
    )
    
    await bot.send_message(user_id, msg_text, parse_mode="Markdown")
    
    if photo_ids:
        for p_id in photo_ids.split(","):
            if p_id.strip():
                await bot.send_photo(user_id, p_id.strip())

    await callback.message.edit_text(f"✅ Sipariş #{order_id} onaylandı ve bilgiler müşteriye iletildi.")

# --- ADMIN PANELİ ---
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yeni Drop Ekle", callback_data="add_drop")]
    ])
    await message.answer("👑 **Admin Paneli**", reply_markup=kb)

@dp.callback_query(F.data == "add_drop")
async def start_add_drop(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AddDrop.title)
    await callback.message.answer("1️⃣ Drop için bir **Başlık/İsim** girin:")

@dp.message(AddDrop.title)
async def process_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AddDrop.price)
    await message.answer("2️⃣ **Fiyatı** girin (Sadece sayı, örn: 1500):")

@dp.message(AddDrop.price)
async def process_price(message: types.Message, state: FSMContext):
    await state.update_data(price=float(message.text))
    await state.set_state(AddDrop.location)
    await message.answer("3️⃣ **Google Maps / Konum Linkini** girin:")

@dp.message(AddDrop.location)
async def process_location(message: types.Message, state: FSMContext):
    await state.update_data(location=message.text)
    await state.set_state(AddDrop.photo)
    await message.answer("4️⃣ Drop yerinin **Fotoğrafını** gönderin (Sadece 1 adet):")

@dp.message(AddDrop.photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await state.set_state(AddDrop.description)
    await message.answer("5️⃣ Müşteri için **Açıklama / İpucu Notu** girin:")

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
    await message.answer("✅ **Yeni Drop Başarıyla Veritabanına Eklendi!** Stoğa girdi.")

# --- BOTU BAŞLATMA ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
