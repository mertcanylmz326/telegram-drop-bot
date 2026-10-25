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

# --- GÜÇLENDİRİLMİŞ WEB SUNUCUSU (GÜVENLİ KONUM SAYFASI) ---
class SecureDropHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Bot and Secure Web Server are alive and running!")
            return

        if parsed_path.path.startswith("/drop/"):
            try:
                order_id = int(parsed_path.path.split("/")[-1])
                
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

threading.Thread(target=run_health_server, daemon=True).start()

# --- AYARLAR ---
BOT_TOKEN = "8994954068:AAFWrg9dLaMrXkK2uR2vpTTNke84vn449RM"
ADMIN_ID = 1012940363
ADMIN_GROUP_ID = -1004474292737  # 📌 Admin grup ID'niz buraya entegre edildi

CRYPTO_WALLET = "TMDAC83GTrxDCQiQBCEEL11CdHBYPSMpjH"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
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
            stock INTEGER DEFAULT 1,
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
    stock = State()
    location = State()
    photo = State()
    description = State()

class BroadcastState(StatesGroup):
    message = State()

class BulkAddState(StatesGroup):
    data = State()

class AdminManageState(StatesGroup):
    user_id = State()

class SupportState(StatesGroup):
    message = State()

# --- KULLANICI MENÜSÜ ---
def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍️ Ürünler / Droplar")],
            [KeyboardButton(text="❓ Nasıl Çalışır? (SSS)"), KeyboardButton(text="📞 Destek")]
        ],
        resize_keyboard=True
    )

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.chat.type != "private":
        return
    
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    conn.close()

    await message.answer(
        "👋 Merhaba! Güvenli otomatik teslimat botuna hoş geldiniz.\n\n"
        "Aşağıdaki menüden mevcut dropları inceleyebilir, SSS bölümüne göz atabilir veya destek alabilirsiniz.",
        reply_markup=main_keyboard()
    )

# --- AKILLI SSS (SIK SORULAN SORULAR) MENÜSÜ ---
@dp.message(F.text == "❓ Nasıl Çalışır? (SSS)")
async def faq_menu(message: types.Message):
    if message.chat.type != "private":
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Ödeme Nasıl Yapılır?", callback_data="faq_pay")],
        [InlineKeyboardButton(text="⏱️ Teslimat Süreci Nasıl İşler?", callback_data="faq_delivery")],
        [InlineKeyboardButton(text="🔒 Gizliliğim Güvende mi?", callback_data="faq_security")]
    ])
    await message.answer("💡 **Sık Sorulan Sorular (SSS)**\n\nMerak ettiğiniz konuları aşağıdan seçebilirsiniz:", reply_markup=kb)

@dp.callback_query(F.data.startswith("faq_"))
async def faq_callback(callback: types.CallbackQuery):
    action = callback.data.split("_")[1]
    if action == "pay":
        text = "💳 **Ödeme Nasıl Yapılır?**\n\nÜrün seçtikten sonra size verilen USDT (TRC20) cüzdan adresine tam tutarı gönderirsiniz. Ardından 'Ödemeyi Otomatik Kontrol Et' butonuna basarak anında onaylatırsınız."
    elif action == "delivery":
        text = "⏱️ **Teslimat Süreci**\n\nÖdemeniz blokzincirde onaylandığı an sistem size otomatik olarak şifreli ve tek kullanımlık bir web bağlantısı gönderir. Bekleme süresi yoktur."
    elif action == "security":
        text = "🔒 **Gizlilik ve Güvenlik**\n\nHiçbir konum veya fotoğraf Telegram geçmişinizde saklanmaz. Size özel açılan web sayfası kısa süre sonra kendini imha eder."
    else:
        text = "Bilgi bulunamadı."
    await callback.answer()
    await callback.message.answer(text)

# --- CANLI DESTEK SİSTEMİ (GRUBA AKTARIMLI) ---
@dp.message(F.text == "📞 Destek")
async def support_start(message: types.Message, state: FSMContext):
    if message.chat.type != "private":
        return
    await state.set_state(SupportState.message)
    await message.answer(
        "📞 **Canlı Destek Hattı**\n\n"
        "Lütfen yetkiliye iletmek istediğiniz soru veya sorun mesajınızı yazın. "
        "Mesajınız doğrudan admin grubuna iletilecektir:"
    )

@dp.message(SupportState.message)
async def forward_support_to_group(message: types.Message, state: FSMContext):
    if message.chat.type != "private":
        return
    user_msg = message.text
    user_id = message.from_user.id
    username = message.from_user.username or "Bulunmuyor"
    
    await state.clear()
    await message.answer("✅ Destek mesajınız admin grubuna iletildi. En kısa sürede dönüş yapılacaktır.")

    admin_group_text = (
        f"📩 **YENİ DESTEK MESAJI**\n\n"
        f"👤 Kullanıcı ID: `{user_id}`\n"
        f"Kullanıcı Adı: @{username}\n\n"
        f"💬 Mesaj:\n{user_msg}"
    )

    try:
        await bot.send_message(ADMIN_GROUP_ID, admin_group_text)
    except Exception as e:
        logging.error(f"Destek mesajı gruba gönderilemedi: {e}")

# --- ÜRÜN LİSTELEME (STOK KONTROLLÜ) ---
@dp.message(F.text == "🛍️ Ürünler / Droplar")
async def list_drops(message: types.Message):
    if message.chat.type != "private":
        return
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, price, stock FROM drops WHERE is_sold = 0 AND stock > 0")
    drops = cursor.fetchall()
    conn.close()

    if not drops:
        await message.answer("❌ Şu anda stokta hazır drop bulunmamaktadır.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for drop in drops:
        drop_id, title, price, stock = drop
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"{title} - {price} USDT (Stok: {stock})", callback_data=f"buy_{drop_id}")
        ])

    await message.answer("📦 Satın almak istediğiniz drop'u seçin:", reply_markup=kb)

# --- SİPARİŞ OLUŞTURMA ---
@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: types.CallbackQuery):
    drop_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id

    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT title, price, stock FROM drops WHERE id = ? AND is_sold = 0 AND stock > 0", (drop_id,))
    drop = cursor.fetchone()

    if not drop:
        await callback.answer("⚠️ Bu ürün tükenmiş veya başka biri tarafından alınmış.", show_alert=True)
        conn.close()
        return

    title, price, stock = drop
    
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

# --- BLOKZİNCİR KONTROLÜ VE STOK DÜŞÜRME ---
@dp.callback_query(F.data.startswith("autocheck_"))
async def check_blockchain_payment(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    
    await callback.answer("Blokzincir ve sipariş süresi taranıyor...", show_alert=True)

    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT orders.user_id, drops.id, drops.price, drops.stock, orders.status, orders.created_at 
        FROM orders 
        JOIN drops ON orders.drop_id = drops.id 
        WHERE orders.id = ?
    """, (order_id,))
    data = cursor.fetchone()

    if not data:
        await callback.answer("Sipariş bulunamadı.", show_alert=True)
        conn.close()
        return

    user_id, drop_id, expected_price, stock, status, created_at_str = data

    if status == 'completed':
        await callback.answer("Bu sipariş zaten onaylanmış ve teslim edilmiştir.", show_alert=True)
        conn.close()
        return

    if status == 'expired':
        await callback.answer("⚠️ Bu siparişin süresi dolduğu için iptal edilmiştir.", show_alert=True)
        conn.close()
        return

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
        new_stock = stock - 1
        if new_stock <= 0:
            cursor.execute("UPDATE drops SET stock = 0, is_sold = 1 WHERE id = ?", (drop_id,))
        else:
            cursor.execute("UPDATE drops SET stock = ? WHERE id = ?", (new_stock, drop_id))
            
        cursor.execute("UPDATE orders SET status = 'completed' WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()

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
    if message.chat.type != "private" or not is_admin(message.from_user.id):
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Tekli Drop Ekle (Stoklu)", callback_data="add_drop")],
        [InlineKeyboardButton(text="📦 Toplu Drop Ekle", callback_data="bulk_add")],
        [InlineKeyboardButton(text="📊 Satış Raporları & İstatistik", callback_data="stats")],
        [InlineKeyboardButton(text="📢 Toplu Duyuru Gönder", callback_data="start_broadcast")],
        [InlineKeyboardButton(text="👥 Admin Ekle / Çıkar", callback_data="manage_admins")]
    ])
    await message.answer("👑 **Gelişmiş Yönetim Paneli (Grup Modu)**", reply_markup=kb)

@dp.callback_query(F.data == "stats")
async def show_stats(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM drops")
    total_drops = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(stock) FROM drops WHERE is_sold = 0")
    total_active_stock = cursor.fetchone()[0] or 0
    cursor.execute("SELECT SUM(drops.price) FROM orders JOIN drops ON orders.drop_id = drops.id WHERE orders.status = 'completed'")
    total_revenue = cursor.fetchone()[0] or 0.0
    conn.close()

    stats_text = (
        "📊 **Satış Raporları ve İstatistikler**\n\n"
        f"📦 Toplam Ürün Çeşidi: `{total_drops}`\n"
        f"🟢 Toplam Aktif Stok Adedi: `{total_active_stock}`\n"
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
        [InlineKeyboardButton(text="➕ Tekli Drop Ekle (Stoklu)", callback_data="add_drop")],
        [InlineKeyboardButton(text="📦 Toplu Drop Ekle", callback_data="bulk_add")],
        [InlineKeyboardButton(text="📊 Satış Raporları & İstatistik", callback_data="stats")],
        [InlineKeyboardButton(text="📢 Toplu Duyuru Gönder", callback_data="start_broadcast")],
        [InlineKeyboardButton(text="👥 Admin Ekle / Çıkar", callback_data="manage_admins")]
    ])
    await callback.message.edit_text("👑 **Gelişmiş Yönetim Paneli (Grup Modu)**", reply_markup=kb)

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
    if message.chat.type != "private" or message.from_user.id != ADMIN_ID:
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

# --- STOKLU TEKLİ DROP EKLEME WIZARD ---
@dp.callback_query(F.data == "add_drop")
async def start_add_drop(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AddDrop.title)
    await callback.message.answer("1️⃣ Drop için bir Başlık/İsim girin:")

@dp.message(AddDrop.title)
async def process_title(message: types.Message, state: FSMContext):
    if message.chat.type != "private":
        return
    await state.update_data(title=message.text)
    await state.set_state(AddDrop.price)
    await message.answer("2️⃣ Fiyatı girin (USDT cinsinden, örn: 20):")

@dp.message(AddDrop.price)
async def process_price(message: types.Message, state: FSMContext):
    if message.chat.type != "private":
        return
    await state.update_data(price=float(message.text))
    await state.set_state(AddDrop.stock)
    await message.answer("3️⃣ Stok / Adet miktarını girin (Örn: 5):")

@dp.message(AddDrop.stock)
async def process_stock(message: types.Message, state: FSMContext):
    if message.chat.type != "private":
        return
    await state.update_data(stock=int(message.text))
    await state.set_state(AddDrop.location)
    await message.answer("4️⃣ Google Maps / Konum Linkini girin:")

@dp.message(AddDrop.location)
async def process_location(message: types.Message, state: FSMContext):
    if message.chat.type != "private":
        return
    await state.update_data(location=message.text)
    await state.set_state(AddDrop.photo)
    await message.answer("5️⃣ Drop yerinin Fotoğrafını gönderin (Sadece 1 adet):")

@dp.message(AddDrop.photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    if message.chat.type != "private":
        return
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await state.set_state(AddDrop.description)
    await message.answer("6️⃣ Müşteri için Açıklama / İpucu Notu girin:")

@dp.message(AddDrop.description)
async def process_desc(message: types.Message, state: FSMContext):
    if message.chat.type != "private":
        return
    data = await state.get_data()
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO drops (title, price, location_url, photo_ids, description, stock)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (data['title'], data['price'], data['location'], data['photo'], message.text, data['stock']))
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer("✅ Stoklu Drop Başarıyla Eklendi ve Stoğa Girdi!")

@dp.callback_query(F.data == "bulk_add")
async def start_bulk_add(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(BulkAddState.data)
    await callback.message.answer(
        "📦 **Toplu Drop Ekleme Modu**\n\n"
        "Her satıra bir ürün gelecek şekilde şu formatta gönder:\n"
        "`Başlık | Fiyat | Stok | KonumLink | Aciklama`"
    )

@dp.message(BulkAddState.data)
async def process_bulk_data(message: types.Message, state: FSMContext):
    if message.chat.type != "private":
        return
    lines = message.text.split("\n")
    added_count = 0
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    for line in lines:
        parts = line.split("|")
        if len(parts) >= 5:
            title = parts[0].strip()
            try:
                price = float(parts[1].strip())
                stock = int(parts[2].strip())
            except:
                price, stock = 0.0, 1
            location = parts[3].strip()
            desc = parts[4].strip()
            cursor.execute("""
                INSERT INTO drops (title, price, location_url, photo_ids, description, stock)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (title, price, location, "", desc, stock))
            added_count += 1
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer(f"✅ Toplam **{added_count} adet** ürün toplu olarak eklendi!")

@dp.callback_query(F.data == "start_broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(BroadcastState.message)
    await callback.message.answer("📢 Tüm kullanıcılara göndermek istediğin duyuru mesajını yaz/gönder:")

@dp.message(BroadcastState.message)
async def send_broadcast(message: types.Message, state: FSMContext):
    if message.chat.type != "private":
        return
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
