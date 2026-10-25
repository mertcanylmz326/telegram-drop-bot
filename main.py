import asyncio
import sqlite3
import logging
import os
import threading
import re
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

# --- GÜÇLENDİRİLMİŞ WEB SUNUCUSU (GÜVENLİ KONUM + WEB ADMIN DASHBOARD) ---
class SecureDropHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        
        if parsed_path.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Bot and Secure Web Server are alive and running!")
            return

        if parsed_path.path == "/admin-web":
            password = query_params.get("pass", [""])[0]
            if password != ADMIN_WEB_PASSWORD:
                self.send_html_error("Yetkisiz Erişim! Şifre hatalı.")
                return

            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM drops")
            total_drops = cursor.fetchone()[0]
            cursor.execute("SELECT SUM(stock) FROM drops WHERE is_sold = 0")
            total_active_stock = cursor.fetchone()[0] or 0
            cursor.execute("SELECT SUM(drops.price) FROM orders JOIN drops ON orders.drop_id = drops.id WHERE orders.status = 'completed'")
            total_revenue = cursor.fetchone()[0] or 0.0
            
            cursor.execute("SELECT id, title, price, stock, is_sold FROM drops ORDER BY id DESC LIMIT 10")
            recent_drops = cursor.fetchall()
            conn.close()

            drops_html = ""
            for d in recent_drops:
                d_id, title, price, stock, is_sold = d
                status_badge = "🟢 Aktif" if is_sold == 0 and stock > 0 else "🔴 Tükendi"
                drops_html += f"<tr><td>#{d_id}</td><td>{title}</td><td>{price} USDT</td><td>{stock} Adet</td><td>{status_badge}</td></tr>"

            dashboard_html = f"""
            <!DOCTYPE html>
            <html lang="tr">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Admin Dashboard</title>
                <style>
                    body {{ background-color: #0f172a; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; margin: 0; }}
                    .container {{ max-width: 800px; margin: 0 auto; }}
                    h1 {{ color: #38bdf8; text-align: center; }}
                    .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }}
                    .card {{ background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; text-align: center; }}
                    .card h3 {{ margin: 0 0 10px 0; color: #94a3b8; font-size: 14px; }}
                    .card p {{ margin: 0; font-size: 24px; font-weight: bold; color: #38bdf8; }}
                    .form-box, .table-box {{ background: #1e293b; padding: 25px; border-radius: 12px; border: 1px solid #334155; margin-bottom: 30px; }}
                    input, textarea {{ width: 100%; padding: 10px; margin: 8px 0 15px 0; background: #0f172a; border: 1px solid #475569; border-radius: 6px; color: white; box-sizing: border-box; }}
                    button {{ background: #2563eb; color: white; padding: 12px 20px; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; width: 100%; }}
                    button:hover {{ background: #1d4ed8; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                    th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #334155; font-size: 14px; }}
                    th {{ color: #94a3b8; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>👑 Web Admin Paneli</h1>
                    <div class="stats-grid">
                        <div class="card"><h3>TOPLAM CİRO</h3><p>{total_revenue} USDT</p></div>
                        <div class="card"><h3>AKTİF STOK</h3><p>{total_active_stock} Adet</p></div>
                        <div class="card"><h3>TOPLAM ÇEŞİT</h3><p>{total_drops}</p></div>
                    </div>
                    <div class="form-box">
                        <h2>➕ Hızlı Web'den Drop Ekle</h2>
                        <form action="/admin-add" method="POST">
                            <input type="hidden" name="pass" value="{password}">
                            <label>Ürün Başlığı:</label>
                            <input type="text" name="title" required placeholder="Örn: Taksim Drop">
                            <label>Fiyat (USDT):</label>
                            <input type="number" step="0.1" name="price" required placeholder="20">
                            <label>Stok Adedi:</label>
                            <input type="number" name="stock" required value="1">
                            <label>Google Maps Konum Linki:</label>
                            <input type="text" name="location" required placeholder="https://maps.app.goo.gl/...">
                            <label>Açıklama / İpucu Notu:</label>
                            <textarea name="description" rows="3" required placeholder="Bina girişindeki saksının arkasında..."></textarea>
                            <button type="submit">Stoğa Ekle</button>
                        </form>
                    </div>
                    <div class="table-box">
                        <h2>📦 Son Eklenen Droplar</h2>
                        <table>
                            <tr><th>ID</th><th>Başlık</th><th>Fiyat</th><th>Stok</th><th>Durum</th></tr>
                            {drops_html}
                        </table>
                    </div>
                </div>
            </body>
            </html>
            """
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(dashboard_html.encode("utf-8"))
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
                            <p><b>📍 Konum:</b> <a href="{location_url}" target="_blank" style="color: #38bdf8;">Haritada Aç</a></p>
                            <p><b>📝 Not:</b> {description}</p>
                        </div>
                        <a href="{location_url}" class="btn" target="_blank">Google Maps ile Aç</a>
                        <p class="warning">⚠️ Bu sayfa gizliliğiniz için tek kullanımlıktır.</p>
                    </div>
                </body>
                </html>
                """
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_content.encode("utf-8"))
            except Exception:
                self.send_html_error("Bir hata oluştu.")
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == "/admin-add":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            params = parse_qs(post_data)

            password = params.get("pass", [""])[0]
            if password != ADMIN_WEB_PASSWORD:
                self.send_html_error("Yetkisiz Erişim!")
                return

            title = params.get("title", [""])[0]
            try:
                price = float(params.get("price", [0])[0])
                stock = int(params.get("stock", [1])[0])
            except:
                price, stock = 0.0, 1
            location = params.get("location", [""])[0]
            description = params.get("description", [""])[0]

            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO drops (title, price, location_url, photo_ids, description, stock)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (title, price, location, "", description, stock))
            conn.commit()
            conn.close()

            self.send_response(303)
            self.send_header('Location', f'/admin-web?pass={ADMIN_WEB_PASSWORD}')
            self.end_headers()
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
ADMIN_GROUP_ID = -1004474292737  
ADMIN_WEB_PASSWORD = "guvenlisifre123"

CRYPTO_WALLET = "TMDAC83GTrxDCQiQBCEEL11CdHBYPSMpjH"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://senin-botun.onrender.com")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

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
    await message.answer("👋 Merhaba! Güvenli otomatik teslimat botuna hoş geldiniz.", reply_markup=main_keyboard())

@dp.message(F.text == "❓ Nasıl Çalışır? (SSS)")
async def faq_menu(message: types.Message):
    if message.chat.type != "private":
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Ödeme Nasıl Yapılır?", callback_data="faq_pay")],
        [InlineKeyboardButton(text="⏱️ Teslimat Süreci", callback_data="faq_delivery")],
        [InlineKeyboardButton(text="🔒 Gizlilik", callback_data="faq_security")]
    ])
    await message.answer("💡 **Sık Sorulan Sorular (SSS)**", reply_markup=kb)

@dp.callback_query(F.data.startswith("faq_"))
async def faq_callback(callback: types.CallbackQuery):
    action = callback.data.split("_")[1]
    if action == "pay":
        text = "💳 Ürün seçtikten sonra verilen USDT cüzdanına tutarı gönderip onaylatırsın."
    elif action == "delivery":
        text = "⏱️ Ödeme onaylanınca şifreli web bağlantısı anında iletilir."
    else:
        text = "🔒 Konumlar Telegram'da saklanmaz, web üzerinden tek kullanımlıktır."
    await callback.answer()
    await callback.message.answer(text)

@dp.message(F.text == "📞 Destek")
async def support_start(message: types.Message, state: FSMContext):
    if message.chat.type != "private":
        return
    await state.set_state(SupportState.message)
    await message.answer("📞 Destek mesajınızı yazın, admin grubuna iletilsin:")

@dp.message(SupportState.message)
async def forward_support_to_group(message: types.Message, state: FSMContext):
    if message.chat.type != "private":
        return
    user_msg = message.text
    user_id = message.from_user.id
    await state.clear()
    await message.answer("✅ Destek mesajınız admin grubuna iletildi.")
    try:
        await bot.send_message(ADMIN_GROUP_ID, f"📩 **YENİ DESTEK TALEBİ**\n\n👤 Kullanıcı ID: `{user_id}`\n💬 Mesaj:\n{user_msg}")
    except Exception as e:
        logging.error(e)

# --- 🔒 YENİ: GRUPTAN ANONİM YANITLAMA KÖPRÜSÜ ---
@dp.message(F.chat.id == ADMIN_GROUP_ID)
async def handle_admin_group_reply(message: types.Message):
    # Eğer admin gruptaki bir mesaja "Yanıtla (Reply)" yaptıysa
    if message.reply_to_message:
        original_text = message.reply_to_message.text or ""
        # Mesajın içindeki Kullanıcı ID'sini regex ile yakalıyoruz
        match = re.search(r"Kullanıcı ID:\s*`(\d+)`", original_text)
        if match:
            target_user_id = int(match.group(1))
            admin_reply_text = message.text
            try:
                # Cevabı müşteriye bot üzerinden anonim olarak gönderiyoruz
                await bot.send_message(
                    target_user_id,
                    f"💬 **Destek Ekibi Yanıtı:**\n\n{admin_reply_text}"
                )
                await message.reply("✅ Yanıt müşteriye başarıyla iletildi (Kişisel hesabın gizli tutuldu).")
            except Exception as e:
                await message.reply(f"⚠️ Müşteriye mesaj iletilemedi: {e}")

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
    for d in drops:
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{d[1]} - {d[2]} USDT (Stok: {d[3]})", callback_data=f"buy_{d[0]}")])
    await message.answer("📦 Satın almak istediğiniz drop'u seçin:", reply_markup=kb)

@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: types.CallbackQuery):
    drop_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT title, price, stock FROM drops WHERE id = ? AND is_sold = 0 AND stock > 0", (drop_id,))
    drop = cursor.fetchone()
    if not drop:
        await callback.answer("⚠️ Bu ürün tükenmiş.", show_alert=True)
        conn.close()
        return
    title, price, stock = drop
    cursor.execute("INSERT INTO orders (user_id, drop_id, status) VALUES (?, ?, 'pending')", (user_id, drop_id))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    payment_text = (
        f"✅ Sipariş Oluşturuldu! (Sipariş No: #{order_id})\n\n"
        f"📌 Ürün: {title}\n💰 Tutar: {price} USDT\n\n"
        f"🔒 Cüzdan Adresi:\n`{CRYPTO_WALLET}`\n\n"
        "⏱️ 15 dakikanız vardır. Ödemeyi yapınca aşağıdaki butona basın."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Ödemeyi Otomatik Kontrol Et", callback_data=f"autocheck_{order_id}")]])
    await callback.message.edit_text(payment_text, reply_markup=kb)

@dp.callback_query(F.data.startswith("autocheck_"))
async def check_blockchain_payment(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    await callback.answer("Blokzincir taranıyor...", show_alert=True)
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT orders.user_id, drops.id, drops.price, drops.stock, orders.status, orders.created_at FROM orders JOIN drops ON orders.drop_id = drops.id WHERE orders.id = ?", (order_id,))
    data = cursor.fetchone()
    if not data:
        await callback.answer("Sipariş bulunamadı.", show_alert=True)
        conn.close()
        return
    user_id, drop_id, expected_price, stock, status, created_at_str = data
    if status == 'completed':
        await callback.answer("Zaten onaylanmış.", show_alert=True)
        conn.close()
        return
    if status == 'expired':
        await callback.answer("Süresi dolmuş.", show_alert=True)
        conn.close()
        return
    if datetime.now() - datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S") > timedelta(minutes=15):
        cursor.execute("UPDATE orders SET status = 'expired' WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()
        await callback.message.edit_text("⏰ Süre aşımı nedeniyle iptal edildi.")
        return

    api_url = f"https://api.trongrid.io/v1/accounts/{CRYPTO_WALLET}/trc20-transfers?contract_address={USDT_CONTRACT}&limit=10"
    payment_verified = False
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status == 200:
                    res_json = await response.json()
                    for tx in res_json.get("data", []):
                        if tx.get("to") == CRYPTO_WALLET and int(tx.get("value", 0)) >= int(float(expected_price) * 1000000):
                            payment_verified = True
                            break
    except Exception as e:
        logging.error(e)

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
        await callback.message.edit_text(f"✅ Sipariş #{order_id} onaylandı.")
        await bot.send_message(user_id, f"🎉 Ödemeniz onaylandı!\n\n👉 [Güvenli Konum Sayfasını Aç]({secure_link})", parse_mode="Markdown")
    else:
        conn.close()
        await callback.answer("⚠️ Henüz transfer yansımadı, bekleyin.", show_alert=True)

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.chat.type != "private" or not is_admin(message.from_user.id):
        return
    web_panel_url = f"{RENDER_EXTERNAL_URL}/admin-web?pass={ADMIN_WEB_PASSWORD}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Web Panelini Aç (Tarayıcı)", url=web_panel_url)],
        [InlineKeyboardButton(text="➕ Telegram'dan Drop Ekle", callback_data="add_drop")],
        [InlineKeyboardButton(text="📊 Satış Raporları", callback_data="stats")]
    ])
    await message.answer("👑 **Gelişmiş Yönetim Paneli**", reply_markup=kb)

@dp.callback_query(F.data == "stats")
async def show_stats(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), SUM(stock) FROM drops WHERE is_sold = 0")
    res = cursor.fetchone()
    cursor.execute("SELECT SUM(drops.price) FROM orders JOIN drops ON orders.drop_id = drops.id WHERE orders.status = 'completed'")
    rev = cursor.fetchone()[0] or 0.0
    conn.close()
    await callback.message.edit_text(f"📊 İstatistikler:\nAktif Stok: {res[1] or 0}\nToplam Ciro: {rev} USDT", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Geri", callback_data="back_admin")]]))

@dp.callback_query(F.data == "back_admin")
async def back_admin(callback: types.CallbackQuery):
    web_panel_url = f"{RENDER_EXTERNAL_URL}/admin-web?pass={ADMIN_WEB_PASSWORD}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Web Panelini Aç (Tarayıcı)", url=web_panel_url)],
        [InlineKeyboardButton(text="➕ Telegram'dan Drop Ekle", callback_data="add_drop")],
        [InlineKeyboardButton(text="📊 Satış Raporları", callback_data="stats")]
    ])
    await callback.message.edit_text("👑 **Gelişmiş Yönetim Paneli**", reply_markup=kb)

@dp.callback_query(F.data == "add_drop")
async def start_add_drop(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AddDrop.title)
    await callback.message.answer("1️⃣ Başlık girin:")

@dp.message(AddDrop.title)
async def p_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AddDrop.price)
    await message.answer("2️⃣ Fiyat (USDT):")

@dp.message(AddDrop.price)
async def p_price(message: types.Message, state: FSMContext):
    await state.update_data(price=float(message.text))
    await state.set_state(AddDrop.stock)
    await message.answer("3️⃣ Stok Adedi:")

@dp.message(AddDrop.stock)
async def p_stock(message: types.Message, state: FSMContext):
    await state.update_data(stock=int(message.text))
    await state.set_state(AddDrop.location)
    await message.answer("4️⃣ Konum Linki:")

@dp.message(AddDrop.location)
async def p_loc(message: types.Message, state: FSMContext):
    await state.update_data(location=message.text)
    await state.set_state(AddDrop.description)
    await message.answer("5️⃣ Açıklama Notu:")

@dp.message(AddDrop.description)
async def p_desc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO drops (title, price, location_url, photo_ids, description, stock) VALUES (?, ?, ?, ?, ?, ?)",
                   (data['title'], data['price'], data['location'], "", message.text, data['stock']))
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer("✅ Ürün başarıyla eklendi!")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
