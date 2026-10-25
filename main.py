import asyncio
import sqlite3
import logging
import os
import threading
import aiohttp
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# --- GÜÇLENDİRİLMİŞ WEB SUNUCUSU (WEB KONUM SAYFASI DESTEKLİ) ---
class SecureDropHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        # Sağlık kontrolü (Render için)
        if parsed_path.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Bot and Secure Web Server are alive and running!")
            return

        # Şifreli / süreli drop görüntüleme sayfası (/drop/SİPARİŞ_ID)
        if parsed_path.path.startswith("/drop/"):
            try:
                order_id = int(parsed_path.path.split("/")[-1])
                
                # Veritabanından sipariş ve konum bilgilerini çek
                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT orders.status, drops.title, drops.location_url, drops.description 
                    FROM orders 
                    JOIN drops ON orders.drop_id = drops.id 
                    WHERE orders.id = ?
                """, (order_id,))
                row = cursor.fetchone()
                conn.close()

                if not row:
                    self.send_html_error("Ürün veya sipariş bulunamadı.")
                    return

                status, title, location_url, description = row

                if status != 'completed':
                    self.send_html_error("Bu bağlantı geçerli değil veya süresi dolmuş.")
                    return

                # Şık, karanlık temalı gizli web arayüzü
                html_content = f"""
                <!DOCTYPE html>
                <html lang="tr">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Güvenli Teslimat - #{order_id}</title>
                    <style>
                        body {{ background-color: #0f172a; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
                        .card {{ background: #1e293b; padding: 30px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); width: 100%; max-width: 400px; text-align: center; border: 1px solid #334155; }}
                        h2 {{ color: #38bdf8; margin-top: 0; }}
                        .info {{ background: #0f172a; padding: 15px; border-radius: 8px; margin: 20px 0; text-align: left; word-break: break-all; font-size: 14px; border: 1px solid #475569; }}
                        .btn {{ display: block; background: #2563eb; color: white; padding: 12px; border-radius: 8px; text-decoration: none; font-weight: bold; margin-top: 15px; transition: background 0.2s; }}
                        .btn:hover {{ background: #1d4ed8; }}
                        .warning {{ color: #f87171; font-size: 12px; margin-top: 15px; }}
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h2>🔒 Güvenli Teslimat</h2>
                        <p><b>Ürün:</b> {title}</p>
                        <div class="info">
                            <p><b>📍 Konum:</b> <a href="{location_url}" target="_blank" style="color: #38bdf8;">Haritada Açmak İçin Tıkla</a></p>
                            <p><b>📝 Not:</b> {description}</p>
                        </div>
                        <a href="{location_url}" class="btn" target="_blank">Google Maps ile Aç</a>
                        <p class="warning">⚠️ Bu sayfa gizliliğiniz için tek kullanımlıktır. İşleminiz bitince bölgeden ayrılın.</p>
                    </div>
                </body>
                </html>
                """
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_content.encode("utf-8"))

            except Exception as e:
                self.send_html_error("Bir hata oluştu.")
        else:
            self.send_response(404)
            self.end_headers()

    def send_html_error(self, message):
        self.send_response(400)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        err_html = f"""
        <!DOCTYPE html>
        <html lang="tr">
        <head><meta charset="UTF-8"><title>Hata</title></head>
        <body style="background:#0f172a;color:#f8fafc;font-family:sans-serif;text-align:center;padding-top:50px;">
            <h2>⚠️ {message}</h2>
        </body>
        </html>
        """
        self.wfile.write(err_html.encode("utf-8"))

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SecureDropHandler)
    server.serve_forever()

# Web sunucusunu arka planda başlatıyoruz
threading.Thread(target=run_health_server, daemon=True).start()

# --- AYARLAR ---
BOT_TOKEN = "8994954068:AAFWrg9dLaMrXkK2uR2vpTTNke84vn449RM"
ADMIN_ID = 1012940363
CRYPTO_WALLET = "TMDAC83GTrxDCQiQBCEEL11CdHBYPSMpjH"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

# Render üzerindeki web servis adresini otomatik alıyoruz (Gerekirse manuel de yazılabilir)
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://senin-botun.onrender.com")

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
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)
    ''')
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (ADMIN_ID,))
    conn.commit()
    conn.close()

init_db()

def is_admin(user_id: int) -> bool:
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

# --- FSM DURUMLARI ---
class AddDrop(StatesGroup):
    title = State()
    price = State()
    location = State()
    photo = State()
    description = State()

class BroadcastState(StatesGroup):
    message = State()

class BulkAddState(StatesGroup):
    data = State()

class AdminManageState(StatesGroup):
    user_id = State()

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
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    conn.close()

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
    
    cursor.execute("INSERT INTO orders (user_id, drop_id, status) VALUES (?, ?, 'pending')", (user_id, drop_id))
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
        "⏱️ **Süre:** Bu sipariş için 15 dakikanız vardır.\n"
        "⚠️ Ödemeyi yaptıktan sonra aşağıdaki **'Ödemeyi Otomatik Kontrol Et'** butonuna basın."
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Ödemeyi Otomatik Kontrol Et", callback_data=f"autocheck_{order_id}")]
    ])

    await callback.message.edit_text(payment_text, reply_markup=kb)

# --- BLOKZİNCİR KONTROLÜ VE ŞİFRELİ LİNK TESLİMATI ---
@dp.callback_query(F.data.startswith("autocheck_"))
async def check_blockchain_payment(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    
    await callback.answer("Blokzincir ve sipariş süresi taranıyor...", show_alert=True)

    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT orders.user_id, drops.id, drops.price, orders.status, orders.created_at 
        FROM orders 
        JOIN drops ON orders.drop_id = drops.id 
        WHERE orders.id = ?
    """, (order_id,))
    data = cursor.fetchone()

    if not data:
        await callback.answer("Sipariş bulunamadı.", show_alert=True)
        conn.close()
        return

    user_id, drop_id, expected_price, status, created_at_str = data

    if status == 'completed':
        await callback.answer("Bu sipariş zaten onaylanmış ve teslim edilmiştir.", show_alert=True)
        conn.close()
        return

    if status == 'expired':
        await callback.answer("⚠️ Bu siparişin süresi dolduğu için iptal edilmiştir.", show_alert=True)
        conn.close()
        return

    # Timeout (15 Dakika) Kontrolü
    created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
    if datetime.now() - created_at > timedelta(minutes=15):
        cursor.execute("UPDATE orders SET status = 'expired' WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()
        await callback.message.edit_text("⏰ Süre Aşımı: 15 dakika içinde ödeme yapılmadığı için bu sipariş otomatik iptal edilmiştir.")
        return

    api_url = f"https://api.trongrid.io/v1/accounts/{CRYPTO_WALLET}/trc20-transfers?contract_address={USDT_CONTRACT}&limit=10"
    
    payment_verified = False
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status == 200:
                    res_json = await response.json()
                    transfers = res_json.get("data", [])
                    expected_value_scaled = int(float(expected_price) * 1000000)

                    for tx in transfers:
                        if tx.get("to") == CRYPTO_WALLET:
                            tx_value = int(tx.get("value", 0))
                            if tx_value >= expected_value_scaled:
                                payment_verified = True
                                break
    except Exception as e:
        logging.error(f"API Hatası: {e}")

    if payment_verified:
        cursor.execute("UPDATE drops SET is_sold = 1 WHERE id = ?", (drop_id,))
        cursor.execute("UPDATE orders SET status = 'completed' WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()

        # Şifreli / süreli web sayfasının linkini oluşturuyoruz
        secure_link = f"{RENDER_EXTERNAL_URL}/drop/{order_id}"

        msg_text = (
            "🎉 Ödemeniz Blokzincir Üzerinden Otomatik Onaylandı!\n\n"
            "🔐 Gizliliğiniz için konum bilgileri Telegram üzerinden gönderilmemiştir.\n"
            "Aşağıdaki size özel güvenli web bağlantısına tıklayarak konuma ulaşabilirsiniz:\n\n"
            f"👉 [Güvenli Konum Sayfasını Aç]({secure_link})\n\n"
            "⚠️ Bu bağlantı tamamen şifrelidir ve kısa süre sonra devre dışı kalacaktır."
        )
        
        await callback.message.edit_text(f"✅ Sipariş #{order_id} onaylandı. Güvenli bağlantı müşteriye iletildi.")
        await bot.send_message(user_id, msg_text, parse_mode="Markdown")
    else:
        conn.close()
        await callback.answer(
            "⚠️ Henüz cüzdanınıza yansıyan eşleşen bir USDT transferi bulunamadı. Lütfen bekleyin.", 
            show_alert=True
        )

# --- ADMIN PANELİ ---
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Tekli Drop Ekle", callback_data="add_drop")],
        [InlineKeyboardButton(text="📦 Toplu Drop Ekle", callback_data="bulk_add")],
        [InlineKeyboardButton(text="📊 Satış Raporları & İstatistik", callback_data="stats")],
        [InlineKeyboardButton(text="📢 Toplu Duyuru Gönder", callback_data="start_broadcast")],
        [InlineKeyboardButton(text="👥 Admin Ekle / Çıkar", callback_data="manage_admins")]
    ])
    await message.answer("👑 **Gelişmiş Yönetim Paneli (Güvenli Mod)**", reply_markup=kb)

@dp.callback_query(F.data == "stats")
async def show_stats(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM drops")
    total_drops = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM drops WHERE is_sold = 1")
    sold_drops = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM drops WHERE is_sold = 0")
    active_drops = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(drops.price) FROM orders JOIN drops ON orders.drop_id = drops.id WHERE orders.status = 'completed'")
    total_revenue = cursor.fetchone()[0] or 0.0
    conn.close()

    stats_text = (
        "📊 **Satış Raporları ve İstatistikler**\n\n"
        f"📦 Toplam Drop Sayısı: `{total_drops}`\n"
        f"🟢 Aktif Stok: `{active_drops}`\n"
        f"🔴 Satılan Ürün: `{sold_drops}`\n"
        f"💰 Toplam Ciro: `{total_revenue} USDT`"
    )
    await callback.message.edit_text(stats_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Panele Dön", callback_data="back_to_admin")]
    ]))

@dp.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Tekli Drop Ekle", callback_data="add_drop")],
        [InlineKeyboardButton(text="📦 Toplu Drop Ekle", callback_data="bulk_add")],
        [InlineKeyboardButton(text="📊 Satış Raporları & İstatistik", callback_data="stats")],
        [InlineKeyboardButton(text="📢 Toplu Duyuru Gönder", callback_data="start_broadcast")],
        [InlineKeyboardButton(text="👥 Admin Ekle / Çıkar", callback_data="manage_admins")]
    ])
    await callback.message.edit_text("👑 **Gelişmiş Yönetim Paneli (Güvenli Mod)**", reply_markup=kb)

@dp.callback_query(F.data == "manage_admins")
async def manage_admins(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⚠️ Bu alanı sadece ana kurucu yönetebilir!", show_alert=True)
        return
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins")
    admins = cursor.fetchall()
    conn.close()
    admin_list_str = "\n".join([f"• `{a[0]}`" for a in admins])
    text = f"👥 **Admin Yönetimi**\n\nMevcut Adminler:\n{admin_list_str}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Admin Ekle", callback_data="add_admin")],
        [InlineKeyboardButton(text="🔙 Panele Dön", callback_data="back_to_admin")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data == "add_admin")
async def start_add_admin(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminManageState.user_id)
    await callback.message.answer("➕ Eklemek istediğiniz kişinin Telegram User ID numarasını yazın:")

@dp.message(AdminManageState.user_id)
async def process_add_admin(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        new_id = int(message.text.strip())
        conn = sqlite3.connect("drop_bot.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (new_id,))
        conn.commit()
        conn.close()
        await state.clear()
        await message.answer(f"✅ Kullanıcı (`{new_id}`) başarıyla admin yapıldı!")
    except Exception:
        await message.answer("⚠️ Geçersiz ID.")

@dp.callback_query(F.data == "add_drop")
async def start_add_drop(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AddDrop.title)
    await callback.message.answer("1️⃣ Drop için bir Başlık/İsim girin:")

@dp.message(AddDrop.title)
async def process_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AddDrop.price)
    await message.answer("2️⃣ Fiyatı girin (USDT cinsinden, örn: 20):")

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
    await message.answer("✅ Tekli Drop Başarıyla Eklendi ve Stoğa Girdi!")

@dp.callback_query(F.data == "bulk_add")
async def start_bulk_add(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(BulkAddState.data)
    await callback.message.answer(
        "📦 **Toplu Drop Ekleme Modu**\n\n"
        "Her satıra bir ürün gelecek şekilde şu formatta gönder:\n"
        "`Başlık | Fiyat | KonumLink | Aciklama`"
    )

@dp.message(BulkAddState.data)
async def process_bulk_data(message: types.Message, state: FSMContext):
    lines = message.text.split("\n")
    added_count = 0
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    for line in lines:
        parts = line.split("|")
        if len(parts) >= 4:
            title = parts[0].strip()
            try:
                price = float(parts[1].strip())
            except:
                price = 0.0
            location = parts[2].strip()
            desc = parts[3].strip()
            cursor.execute("""
                INSERT INTO drops (title, price, location_url, photo_ids, description)
                VALUES (?, ?, ?, ?, ?)
            """, (title, price, location, "", desc))
            added_count += 1
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer(f"✅ Toplam **{added_count} adet** drop toplu olarak eklendi!")

@dp.callback_query(F.data == "start_broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(BroadcastState.message)
    await callback.message.answer("📢 Tüm kullanıcılara göndermek istediğin duyuru mesajını yaz/gönder:")

@dp.message(BroadcastState.message)
async def send_broadcast(message: types.Message, state: FSMContext):
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    await state.clear()
    sent_count = 0
    status_msg = await message.answer("🚀 Duyuru gönderiliyor...")
    for (u_id,) in users:
        try:
            await message.send_copy(chat_id=u_id)
            sent_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await status_msg.edit_text(f"✅ Duyuru **{sent_count}** kullanıcıya iletildi!")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
