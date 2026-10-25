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
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, FSInputFile, WebAppInfo

# --- AYARLAR VE CÜZDAN İZOLASYONU ---
BOT_TOKEN = "8994954068:AAFWrg9dLaMrXkK2uR2vpTTNke84vn449RM"
ADMIN_ID = 1012940363
ADMIN_GROUP_ID = -1004474292737  

ADMIN_WEB_USERNAME = "dionisus"
ADMIN_WEB_PASSWORD = "weedstanbul34"

PROMO_CODE = "welcomeweedstanbul"
PROMO_DISCOUNT = 8.0

WALLET_CONFIG = {
    "weedboot": "TMDAC83GTrxDCQiQBCEEL11CdHBYPSMpjH",
    "giris": "TVsUkivFz217G7yAZ9w9PDj4WphJZty1tY",
    "cikis": "TMxF3AFaqpHgRF5S8RkmZtAkwzzYxgwzLn"
}

CRYPTO_WALLET = WALLET_CONFIG["weedboot"]
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://senin-botun.onrender.com")

REQUIRED_CHANNEL = -1004474292737
REQUIRED_CHANNEL_URL = "https://t.me/+NReAegSp4l85NWZk"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
main_loop = None

# --- ÇEVİRİ SÖZLÜĞÜ (TR / EN) ---
LANG = {
    "tr": {
        "welcome": "👋 Merhaba! Güvenli otomatik teslimat botumuza hoş geldiniz.\n\nİster Mini App mağazamızdan hızlıca alışveriş yapın, ister 'Bot ile Devam Et' diyerek sohbet üzerinden ilerleyin:",
        "lang_set": "✅ Dil Türkçe olarak ayarlandı.",
        "btn_webapp": "🛍️ Mağazayı Aç (Mini App)",
        "btn_botshop": "🤖 Bot ile Devam Et",
        "btn_faq": "❓ Nasıl Çalışır? (SSS)",
        "btn_support": "📞 Canlı Destek",
        "btn_lang": "🌐 Dil Değiştir",
        "no_stock": "❌ Şu anda stokta hazır drop bulunmamaktadır.",
        "select_cat": "🏙️ Lütfen ürünleri incelemek istediğiniz **bölgeyi / semti** seçin:",
        "back_cats": "🔙 Bölgelere Dön",
        "no_cat_stock": "Bu bölgede aktif ürün kalmadı.",
        "buy_options": "📌 Ürün: {title}\n💰 Fiyat: {price} USDT {vip_info}\n💵 Bakiyeniz: {balance} USDT\n\nLütfen ödeme yöntemini seçin:",
        "pay_balance": "⚡ Bakiyeden Öde ({price} USDT)",
        "pay_crypto": "🔒 Blokzincir ile Öde",
        "insufficient_balance": "❌ Bakiyeniz yetersiz! Lütfen cüzdanınıza bakiye yükleyin.",
        "balance_success": "🎉 Siparişiniz onaylandı! {price} USDT düşüldü.\n\n👉 [Güvenli Konum Sayfasını Aç]({link})",
        "order_created": "✅ Sipariş Oluşturuldu! (Sipariş No: #{id})\n\n📌 Ürün: {title}\n",
        "wallet_text": "🔒 Cüzdan Adresi:\n`{wallet}`\n\n⏱️ 15 dakikanız vardır. Ödemeyi yapınca aşağıdaki butona basın.",
        "check_btn": "🔄 Ödemeyi Otomatik Kontrol Et",
        "support_ask": "📞 Destek mesajınızı yazın, admin ekibine iletilsin:",
        "support_sent": "✅ Destek mesajınız iletildi.",
        "banned": "❌ Erişiminiz engellenmiştir."
    },
    "en": {
        "welcome": "👋 Hello! Welcome to our secure automated delivery bot.\n\nYou can shop via our Mini App or continue directly through the bot:",
        "lang_set": "✅ Language set to English.",
        "btn_webapp": "🛍️ Open Store (Mini App)",
        "btn_botshop": "🤖 Continue via Bot",
        "btn_faq": "❓ How It Works (FAQ)",
        "btn_support": "📞 Live Support",
        "btn_lang": "🌐 Change Language",
        "no_stock": "❌ There are currently no ready drops in stock.",
        "select_cat": "🏙️ Please select the **region / district** you want to view:",
        "back_cats": "🔙 Back to Regions",
        "no_cat_stock": "No active products left in this region.",
        "buy_options": "📌 Product: {title}\n💰 Price: {price} USDT {vip_info}\n💵 Your Balance: {balance} USDT\n\nPlease select payment method:",
        "pay_balance": "⚡ Pay from Balance ({price} USDT)",
        "pay_crypto": "🔒 Pay via Blockchain",
        "insufficient_balance": "❌ Insufficient balance!",
        "balance_success": "🎉 Order successfully approved! {price} USDT deducted.\n\n👉 [Open Secure Location Page]({link})",
        "order_created": "✅ Order Created! (Order No: #{id})\n\n📌 Product: {title}\n",
        "wallet_text": "🔒 Wallet Address:\n`{wallet}`\n\n⏱️ You have 15 minutes. Click the button below after payment.",
        "check_btn": "🔄 Auto-Check Payment",
        "support_ask": "📞 Type your support message to send to the admin team:",
        "support_sent": "✅ Your support message has been sent.",
        "banned": "❌ Your access has been restricted."
    }
}

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
            is_sold INTEGER DEFAULT 0,
            category TEXT DEFAULT 'Genel'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            drop_id INTEGER,
            status TEXT DEFAULT 'pending',
            final_price REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS panel_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT,
            log_type TEXT DEFAULT 'info',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            message TEXT,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS testimonials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            rating INTEGER DEFAULT 5,
            photo_url TEXT,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            is_banned INTEGER DEFAULT 0,
            language TEXT DEFAULT 'tr',
            balance REAL DEFAULT 0.0,
            total_spent REAL DEFAULT 0.0,
            referred_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    for col, def_val in [("is_banned", "INTEGER DEFAULT 0"), ("language", "TEXT DEFAULT 'tr'"), ("balance", "REAL DEFAULT 0.0"), ("total_spent", "REAL DEFAULT 0.0"), ("referred_by", "INTEGER")]:
        try: cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {def_val}")
        except: pass
    cursor.execute('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)''')
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (ADMIN_ID,))
    conn.commit()
    conn.close()

init_db()

def get_user_lang(user_id: int) -> str:
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res and res[0] in ["tr", "en"] else "tr"

def set_user_lang(user_id: int, lang: str):
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()
    conn.close()

def get_user_profile(user_id: int):
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance, total_spent FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return (res[0] or 0.0, res[1] or 0.0) if res else (0.0, 0.0)

def log_panel_event(message, log_type="info"):
    try:
        conn = sqlite3.connect("drop_bot.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO panel_logs (message, log_type) VALUES (?, ?)", (message, log_type))
        conn.commit()
        conn.close()
    except Exception as e: logging.error(e)

def is_user_banned(user_id: int) -> bool:
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None and res[0] == 1

def get_wallet_balances():
    balances = {}
    for key, addr in WALLET_CONFIG.items():
        usdt_bal, trx_bal = 0.0, 0.0
        try:
            import urllib.request, json
            url = f"https://api.trongrid.io/v1/accounts/{addr}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    acc_data = data.get("data", [])
                    if acc_data:
                        trx_bal = acc_data[0].get("balance", 0) / 1000000.0
                        for token in acc_data[0].get("trc20", []):
                            if USDT_CONTRACT in token:
                                usdt_bal = float(token[USDT_CONTRACT]) / 1000000.0
                                break
        except Exception as e: logging.error(e)
        balances[key] = {"usdt": usdt_bal, "trx": trx_bal}
    return balances

async def check_user_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        return member.status not in ["left", "kicked"]
    except Exception as e:
        logging.error(e)
        return True

async def auto_backup_task():
    while True:
        await asyncio.sleep(86400)
        try:
            if os.path.exists("drop_bot.db"):
                await bot.send_document(ADMIN_GROUP_ID, FSInputFile("drop_bot.db"), caption="💾 **Otomatik Günlük Veritabanı Yedeği**")
                log_panel_event("💾 Günlük otomatik veritabanı yedeği alındı.", "info")
        except Exception as e: logging.error(e)

async def check_expired_orders_task():
    while True:
        await asyncio.sleep(60)
        try:
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            expiry_limit = datetime.now() - timedelta(minutes=15)
            cursor.execute("SELECT id, drop_id FROM orders WHERE status = 'pending' AND created_at < ?", (expiry_limit.strftime("%Y-%m-%d %H:%M:%S"),))
            for ord_id, drp_id in cursor.fetchall():
                cursor.execute("UPDATE orders SET status = 'expired' WHERE id = ?", (ord_id,))
                cursor.execute("UPDATE drops SET stock = stock + 1, is_sold = 0 WHERE id = ?", (drp_id,))
            conn.commit()
            conn.close()
        except Exception as e: logging.error(e)

# --- 🎄 WEB SUNUCUSU & ADMIN PANELİ (MOBİL UYUMLU HAMBURGER MENÜ) ---
class SecureDropHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        is_logged_in = 'admin_auth=true' in self.headers.get('Cookie', '')

        if parsed_path.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Weed Istanbul Server Active!")
            return

        if parsed_path.path == "/admin-web":
            if not is_logged_in:
                self.send_login_page()
                return
            tab = query_params.get("tab", ["home"])[0]
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM drops")
            total_drops = cursor.fetchone()[0]
            cursor.execute("SELECT SUM(stock) FROM drops WHERE is_sold = 0")
            total_active_stock = cursor.fetchone()[0] or 0
            cursor.execute("SELECT SUM(final_price) FROM orders WHERE status = 'completed'")
            total_revenue = cursor.fetchone()[0] or 0.0

            content_html = ""
            if tab == "home":
                cursor.execute("SELECT message, log_type, created_at FROM panel_logs ORDER BY id DESC LIMIT 10")
                logs_html = "".join([f"<div style='background:rgba(15,23,42,0.7); padding:10px; border-radius:8px; margin-bottom:8px; font-size:13px;'>{l[2]} - {l[0]}</div>" for l in cursor.fetchall()])
                content_html = f"""
                <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:15px; margin-bottom:20px;">
                    <div style="background:#0f172a; padding:15px; border-radius:12px; border:1px solid #10b981;"><h3>TOPLAM CİRO</h3><p style="font-size:24px; font-weight:bold;">{total_revenue} USDT</p></div>
                    <div style="background:#0f172a; padding:15px; border-radius:12px; border:1px solid #ef4444;"><h3>AKTİF STOK</h3><p style="font-size:24px; font-weight:bold;">{total_active_stock}</p></div>
                </div>
                <div style="background:#0f172a; padding:15px; border-radius:12px;"><h3>Canlı Loglar</h3>{logs_html}</div>
                """
            elif tab == "testimonials":
                content_html = "<h2>⭐ Yorum Yönetimi</h2><p>Yorumlar burada listelenir.</p>"
            elif tab == "support":
                content_html = "<h2>💬 Canlı Destek Talepleri</h2><p>Aktif destek talepleri burada görünür.</p>"
            elif tab == "pending":
                content_html = "<h2>⏳ Bekleyen Siparişler</h2><p>Onay bekleyen siparişler.</p>"
            elif tab == "active":
                content_html = "<h2>🟢 Tamamlanan Siparişler</h2><p>Tamamlanan satışlar.</p>"
            elif tab == "passive":
                content_html = "<h2>📦 Stoktakiler / Pasifler</h2><p>Tüm ürün stok yönetimi.</p>"
            elif tab == "add":
                content_html = "<h2>➕ Ürün Ekle</h2><p>Yeni drop ekleme formu.</p>"
            elif tab == "users":
                content_html = "<h2>👥 Kullanıcı Listesi</h2><p>Kayıtlı üyeler ve VIP durumları.</p>"
            conn.close()

            dashboard_html = f"""
            <!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Admin Panel</title>
            <style>
                body {{ background:#050a0e; color:white; font-family:sans-serif; margin:0; display:flex; height:100vh; overflow:hidden; }}
                .sidebar {{ width:250px; background:#0f172a; padding:20px; border-right:1px solid #334155; transition: transform 0.3s ease; z-index: 100; }}
                .sidebar a {{ color:#94a3b8; display:block; padding:10px; text-decoration:none; margin-bottom:5px; border-radius:6px; }}
                .sidebar a:hover {{ background:#10b981; color:white; }}
                .main {{ flex:1; padding:20px; overflow-y:auto; box-sizing: border-box; }}
                .mobile-header {{ display:none; background:#0f172a; padding:15px; border-bottom:1px solid #334155; align-items:center; justify-content:space-between; }}
                .menu-btn {{ background:#10b981; color:white; border:none; padding:8px 12px; border-radius:6px; cursor:pointer; font-size:16px; }}
                @media(max-width: 768px) {{
                    body {{ flex-direction: column; }}
                    .sidebar {{ position: fixed; height: 100%; top: 0; left: 0; transform: translateX(-100%); }}
                    .sidebar.open {{ transform: translateX(0); }}
                    .mobile-header {{ display: flex; }}
                    .main {{ height: calc(100vh - 60px); }}
                }}
            </style>
            </head>
            <body>
                <div class="mobile-header">
                    <h3 style="margin:0; color:#10b981;">🎄 Admin Panel</h3>
                    <button class="menu-btn" onclick="toggleMenu()">☰ Menü</button>
                </div>
                <div class="sidebar" id="sidebar">
                    <h2>🎄 Admin Panel</h2>
                    <a href="/admin-web?tab=home">🏠 Anasayfa</a>
                    <a href="/admin-web?tab=testimonials">⭐ Yorumlar</a>
                    <a href="/admin-web?tab=support">💬 Destek</a>
                    <a href="/admin-web?tab=pending">⏳ Bekleyenler</a>
                    <a href="/admin-web?tab=active">🟢 Tamamlananlar</a>
                    <a href="/admin-web?tab=passive">📦 Stoktakiler</a>
                    <a href="/admin-web?tab=add">➕ Ürün Ekle</a>
                    <a href="/admin-web?tab=users">👥 Kullanıcılar</a>
                    <a href="/admin-logout" style="color:#ef4444; margin-top:20px;">🚪 Çıkış</a>
                </div>
                <div class="main">
                    {content_html}
                </div>
                <script>
                    function toggleMenu() {{
                        document.getElementById('sidebar').classList.toggle('open');
                    }}
                </script>
            </body></html>
            """
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(dashboard_html.encode("utf-8"))
            return

        if parsed_path.path == "/admin-logout":
            self.send_response(303)
            self.send_header('Set-Cookie', 'admin_auth=false; Path=/; Max-Age=0')
            self.send_header('Location', '/admin-web')
            self.end_headers()
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed_path = urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        params = parse_qs(self.rfile.read(content_length).decode('utf-8'))

        if parsed_path.path == "/admin-login":
            if params.get("username", [""])[0] == ADMIN_WEB_USERNAME and params.get("password", [""])[0] == ADMIN_WEB_PASSWORD:
                self.send_response(303)
                self.send_header('Set-Cookie', 'admin_auth=true; Path=/; HttpOnly')
                self.send_header('Location', '/admin-web')
                self.end_headers()
            else: self.send_login_page("Hatalı şifre!")
            return
        self.send_response(404)
        self.end_headers()

    def send_login_page(self, error=""):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Giriş</title></head>
        <body style="background:#050a0e;color:white;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;">
        <div style="background:#0f172a;padding:30px;border-radius:15px;border:1px solid #10b981;width:100%;max-width:320px;text-align:center;">
        <h2>Admin Giriş</h2><p style="color:#ef4444;">{error}</p>
        <form action="/admin-login" method="POST">
        <input type="text" name="username" required placeholder="Kullanıcı Adı" style="width:100%;padding:10px;margin:8px 0;background:#050a0e;border:1px solid #334155;color:white;border-radius:6px;box-sizing:border-box;">
        <input type="password" name="password" required placeholder="Şifre" style="width:100%;padding:10px;margin:8px 0;background:#050a0e;border:1px solid #334155;color:white;border-radius:6px;box-sizing:border-box;">
        <button type="submit" style="background:#10b981;color:white;border:none;padding:10px;width:100%;border-radius:6px;font-weight:bold;cursor:pointer;margin-top:10px;">Giriş Yap</button>
        </form></div></body></html>""".encode("utf-8"))

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), SecureDropHandler).serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

# --- FSM VE BOT KODLARI ---
class SupportState(StatesGroup):
    message = State()

dp = Dispatcher(storage=MemoryStorage())
bot = Bot(token=BOT_TOKEN)

def main_keyboard(lang="tr", user_id=0):
    t = LANG[lang]
    webapp_url = f"{RENDER_EXTERNAL_URL}/webapp?user_id={user_id}"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t["btn_webapp"], web_app=WebAppInfo(url=webapp_url)), KeyboardButton(text=t["btn_botshop"])],
            [KeyboardButton(text=t["btn_faq"]), KeyboardButton(text=t["btn_support"])],
            [KeyboardButton(text=t["btn_lang"])]
        ],
        resize_keyboard=True
    )

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.chat.type != "private": return
    user_id = message.from_user.id
    if is_user_banned(user_id):
        await message.answer("❌ Erişiminiz engellenmiştir.")
        return
    
    args = message.text.split()
    referred_by = int(args[1].replace("ref", "")) if len(args) > 1 and args[1].startswith("ref") and args[1].replace("ref", "").isdigit() else None

    if not await check_user_subscription(user_id):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanala Katıl", url=REQUIRED_CHANNEL_URL)],
            [InlineKeyboardButton(text="🔄 Kontrol Et", callback_data="check_sub")]
        ])
        await message.answer(f"🚀 Kanala katılmalısınız: {REQUIRED_CHANNEL_URL}", reply_markup=kb)
        return

    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)", (user_id, message.from_user.username, referred_by))
    conn.commit()
    conn.close()

    lang = get_user_lang(user_id)
    await message.answer(LANG[lang]["welcome"], reply_markup=main_keyboard(lang, user_id))

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not await check_user_subscription(user_id):
        await callback.answer("❌ Henüz kanala katılmadınız!", show_alert=True)
        return
    await callback.answer("✅ Üyelik onaylandı!")
    lang = get_user_lang(user_id)
    await callback.message.answer(LANG[lang]["welcome"], reply_markup=main_keyboard(lang, user_id))

@dp.callback_query(F.data.startswith("setlang_"))
async def set_language(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    new_lang = callback.data.split("_")[1]
    set_user_lang(user_id, new_lang)
    t = LANG[new_lang]
    await callback.answer()
    await callback.message.edit_text(t["lang_set"])
    await callback.message.answer(t["welcome"], reply_markup=main_keyboard(new_lang, user_id))

@dp.message(F.text.in_([LANG["tr"]["btn_lang"], LANG["en"]["btn_lang"]]))
async def change_lang_menu(message: types.Message):
    if message.chat.type != "private" or is_user_banned(message.from_user.id): return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇹🇷 Türkçe", callback_data="setlang_tr"), InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en")]
    ])
    await message.answer("Lütfen dil seçiniz:", reply_markup=kb)

# --- 🤖 BOT İLE DEVAM ET (KLASİK MAĞAZA AKIŞI) ---
@dp.message(F.text.in_([LANG["tr"]["btn_botshop"], LANG["en"]["btn_botshop"]]))
async def bot_shop_categories(message: types.Message):
    user_id = message.from_user.id
    if message.chat.type != "private" or is_user_banned(user_id): return
    lang = get_user_lang(user_id)
    t = LANG[lang]

    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM drops WHERE is_sold = 0 AND stock > 0")
    categories = cursor.fetchall()
    conn.close()

    if not categories:
        await message.answer(t["no_stock"])
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in categories:
        c_name = cat[0] or "Genel"
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"🏙️ {c_name}", callback_data=f"botcat_{c_name}")])
    
    await message.answer(t["select_cat"], reply_markup=kb)

@dp.callback_query(F.data.startswith("botcat_"))
async def bot_list_drops(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if is_user_banned(user_id): return
    lang = get_user_lang(user_id)
    t = LANG[lang]

    cat_name = callback.data.split("_", 1)[1]
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, price, stock FROM drops WHERE category = ? AND is_sold = 0 AND stock > 0", (cat_name,))
    drops = cursor.fetchall()
    conn.close()

    if not drops:
        await callback.answer(t["no_cat_stock"], show_alert=True)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for d in drops:
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{d[1]} - {d[2]} USDT (Stok: {d[3]})", callback_data=f"botbuy_{d[0]}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=t["back_cats"], callback_data="botback_cats")])

    await callback.message.edit_text(f"📦 **{cat_name}**:", reply_markup=kb)

@dp.callback_query(F.data == "botback_cats")
async def bot_back_to_cats(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if is_user_banned(user_id): return
    lang = get_user_lang(user_id)
    t = LANG[lang]

    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM drops WHERE is_sold = 0 AND stock > 0")
    categories = cursor.fetchall()
    conn.close()

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in categories:
        c_name = cat[0] or "Genel"
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"🏙️ {c_name}", callback_data=f"botcat_{c_name}")])
    
    await callback.message.edit_text(t["select_cat"], reply_markup=kb)

@dp.callback_query(F.data.startswith("botbuy_"))
async def bot_process_buy(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if is_user_banned(user_id): return
    lang = get_user_lang(user_id)
    t = LANG[lang]

    drop_id = int(callback.data.split("_")[1])
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT title, price, stock FROM drops WHERE id = ? AND is_sold = 0 AND stock > 0", (drop_id,))
    drop = cursor.fetchone()
    conn.close()

    if not drop:
        await callback.answer("⚠️ Bu ürün tükenmiş.", show_alert=True)
        return

    title, price, stock = drop
    bal, spent = get_user_profile(user_id)
    is_vip = spent >= 100
    final_buy_price = round(price * 0.9, 2) if is_vip else price
    vip_info_str = "(👑 VIP İndirimli!)" if is_vip else ""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["pay_balance"].format(price=final_buy_price), callback_data=f"botpaybal_{drop_id}")],
        [InlineKeyboardButton(text=t["pay_crypto"], callback_data=f"botpaycrypto_{drop_id}")]
    ])
    await callback.message.edit_text(t["buy_options"].format(title=title, price=final_buy_price, vip_info=vip_info_str, balance=bal), reply_markup=kb)

@dp.callback_query(F.data.startswith("botpaybal_"))
async def bot_pay_with_balance(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if is_user_banned(user_id): return
    lang = get_user_lang(user_id)
    t = LANG[lang]

    drop_id = int(callback.data.split("_")[1])
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT title, price, stock, category FROM drops WHERE id = ? AND is_sold = 0 AND stock > 0", (drop_id,))
    drop = cursor.fetchone()

    if not drop:
        await callback.answer("⚠️ Ürün mevcut değil.", show_alert=True)
        conn.close()
        return

    title, price, stock, category = drop
    bal, spent = get_user_profile(user_id)
    is_vip = spent >= 100
    final_buy_price = round(price * 0.9, 2) if is_vip else price

    if bal < final_buy_price:
        await callback.answer(t["insufficient_balance"], show_alert=True)
        conn.close()
        return

    cursor.execute("UPDATE users SET balance = balance - ?, total_spent = total_spent + ? WHERE user_id = ?", (final_buy_price, final_buy_price, user_id))
    new_stock = stock - 1
    if new_stock <= 0: cursor.execute("UPDATE drops SET stock = 0, is_sold = 1 WHERE id = ?", (drop_id,))
    else: cursor.execute("UPDATE drops SET stock = ? WHERE id = ?", (new_stock, drop_id))

    cursor.execute("INSERT INTO orders (user_id, drop_id, status, final_price) VALUES (?, ?, 'completed', ?)", (user_id, drop_id, final_buy_price))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    secure_link = f"{RENDER_EXTERNAL_URL}/drop/{order_id}"
    await callback.message.edit_text(t["balance_success"].format(price=final_buy_price, link=secure_link), parse_mode="Markdown")
    log_panel_event(f"⚡ Bot Üzerinden Bakiye Satışı: #{order_id} - {title} ({final_buy_price} USDT)", "success")

@dp.callback_query(F.data.startswith("botpaycrypto_"))
async def bot_pay_crypto(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if is_user_banned(user_id): return
    lang = get_user_lang(user_id)
    t = LANG[lang]

    drop_id = int(callback.data.split("_")[1])
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT title, price, stock FROM drops WHERE id = ? AND is_sold = 0 AND stock > 0", (drop_id,))
    drop = cursor.fetchone()
    if not drop:
        await callback.answer("⚠️ Ürün mevcut değil.", show_alert=True)
        conn.close()
        return
    title, price, stock = drop
    _, spent = get_user_profile(user_id)
    final_price = round(price * 0.9, 2) if spent >= 100 else price

    cursor.execute("INSERT INTO orders (user_id, drop_id, status, final_price) VALUES (?, ?, 'pending', ?)", (user_id, drop_id, final_price))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    msg = t["order_created"].format(id=order_id, title=title) + f"💰 Total: {final_price} USDT\n\n" + t["wallet_text"].format(wallet=CRYPTO_WALLET)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t["check_btn"], callback_data=f"autocheck_{order_id}")]])
    await callback.message.edit_text(msg, reply_markup=kb)

# --- FAQ & SUPPORT ---
@dp.message(F.text.in_([LANG["tr"]["btn_faq"], LANG["en"]["btn_faq"]]))
async def faq_menu(message: types.Message):
    if message.chat.type != "private" or is_user_banned(message.from_user.id): return
    await message.answer("💡 **SSS / FAQ:**\n\nİster Mini App butonuna basarak modern arayüzden, ister 'Bot ile Devam Et' diyerek klasik sohbetten alışveriş yapabilirsiniz.")

@dp.message(F.text.in_([LANG["tr"]["btn_support"], LANG["en"]["btn_support"]]))
async def support_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if message.chat.type != "private" or is_user_banned(user_id): return
    lang = get_user_lang(user_id)
    await state.set_state(SupportState.message)
    await message.answer(LANG[lang]["support_ask"])

@dp.message(SupportState.message)
async def forward_support_to_group(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if message.chat.type != "private" or is_user_banned(user_id): return
    lang = get_user_lang(user_id)
    user_msg = message.text
    username = message.from_user.username or "Bulunmuyor"
    await state.clear()
    await message.answer(LANG[lang]["support_sent"])
    try:
        conn = sqlite3.connect("drop_bot.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO support_tickets (user_id, username, message, status) VALUES (?, ?, ?, 'open')", (user_id, username, user_msg))
        conn.commit()
        conn.close()
        await bot.send_message(ADMIN_GROUP_ID, f"📩 **YENİ DESTEK TALEBİ**\n\n👤 ID: `{user_id}` (@{username})\n💬 Mesaj:\n{user_msg}")
    except Exception as e: logging.error(e)

async def main():
    global main_loop
    main_loop = asyncio.get_running_loop()
    asyncio.create_task(auto_backup_task())
    asyncio.create_task(check_expired_orders_task())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
