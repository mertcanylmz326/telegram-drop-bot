import asyncio
import sqlite3
import logging
import os
import threading
import aiohttp
import json
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, FSInputFile, WebAppInfo

# --- AYARLAR & CÜZDAN MİMARİSİ ---
BOT_TOKEN = "8917981396:AAFliW6Hl6gT8CQZP9BgJrPYGQEAggga6WA"
ADMIN_ID = 1012940363
ADMIN_GROUP_ID = -1004474292737  

ADMIN_WEB_USERNAME = "dionisus"
ADMIN_WEB_PASSWORD = "weedstanbul34"

CRYPTO_WALLET = "TMDAC83GTrxDCQiQBCEEL11CdHBYPSMpjH"
MAIN_SAVINGS_WALLET = "TVsUkivFz217G7yAZ9w9PDj4WphJZty1tY"
EXIT_WALLET = "TMxF3AFaqpHgRF5S8RkmZtAkwzzYxgwzLn"

USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
if not RENDER_EXTERNAL_URL:
    RENDER_EXTERNAL_URL = "https://weed-istanbul.onrender.com"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
main_loop = None

# --- İSTANBUL İLÇE KOORDİNATLARI (TEMSİLİ MERKEZLER) ---
DISTRICT_COORDS = {
    "BEŞİKTAŞ": [41.0429, 29.0077],
    "KADIKÖY": [40.9901, 29.0254],
    "ÜSKÜDAR": [41.0256, 29.0153],
    "ŞİŞLİ": [41.0615, 28.9877],
    "BEYOĞLU": [41.0369, 28.9776],
    "FATİH": [41.0092, 28.9556],
    "SARIYER": [41.1687, 29.0565],
    "MALTEPE": [40.9273, 29.1303],
    "KARTAL": [40.8885, 29.1856],
    "PENDİK": [40.8763, 29.2366],
    "ATAŞEHİR": [40.9859, 29.1136],
    "ÜMRANİYE": [41.0298, 29.1157],
    "ÇEKMEKÖY": [41.0422, 29.1764],
    "BEYKOZ": [41.1150, 29.1028],
    "BAKIRKÖY": [40.9791, 28.8756],
    "ZEYTİNBURNU": [40.9928, 28.8988],
    "ESENYURT": [41.0261, 28.6811],
    "BAĞCILAR": [41.0375, 28.8503],
    "BAHÇELİEVLER": [40.9981, 28.8584],
    "GENEL": [41.0082, 28.9784]
}

def get_district_coord(category_name):
    if not category_name:
        return [41.0082, 28.9784]
    cat_upper = category_name.upper().strip()
    for key, coord in DISTRICT_COORDS.items():
        if key in cat_upper:
            return coord
    return [41.0082, 28.9784]

async def fetch_wallet_balance(wallet_address):
    try:
        url = f"https://api.trongrid.io/v1/accounts/{wallet_address}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    acc_data = data.get("data", [])
                    if acc_data:
                        trc20 = acc_data[0].get("trc20", [])
                        for token in trc20:
                            if USDT_CONTRACT in token:
                                val_str = token[USDT_CONTRACT]
                                return float(val_str) / 1000000.0
        return 0.0
    except Exception as e:
        logging.error(f"Wallet balance fetch error: {e}")
        return 0.0

# --- ÇEVİRİ SÖZLÜĞÜ ---
LANG = {
    "tr": {
        "welcome": "👋 Merhaba! Güvenli otomatik teslimat botuna hoş geldiniz. Lütfen dil seçiniz:",
        "lang_set": "✅ Dil Türkçe olarak ayarlandı.",
        "btn_products": "🛍️ Ürünler / Droplar",
        "btn_orders": "📦 Geçmiş Siparişlerim",
        "btn_track": "🔍 Sipariş Takip / Sorgula",
        "btn_miniapp": "🗺️ Harita & Mini App",
        "btn_wallet": "💰 Cüzdanım / Bakiye",
        "btn_faq": "❓ Nasıl Çalışır? (SSS)",
        "btn_support": "📞 Destek",
        "btn_lang": "🌐 Dil Değiştir",
        "no_stock": "❌ Şu anda stokta hazır ürün bulunmamaktadır.",
        "select_cat": "🏙️ Lütfen ürünleri incelemek istediğiniz **bölgeyi / semti** seçin:",
        "back_cats": "🔙 Bölgelere Dön",
        "no_cat_stock": "Bu bölgede aktif ürün kalmadı.",
        "my_orders_title": "📦 **Sipariş Geçmişiniz:**",
        "no_orders": "📦 Henüz bir sipariş geçmişiniz bulunmuyor.",
        "order_item": "• **Sipariş #{id}** (Kod: `WEE-{id}`) | {title} - {price} USDT\n  Durum: {status} ({date})\n\n",
        "open_loc": "🔗 Sipariş #{id} Konumunu Aç",
        "sold_out": "⚠️ Bu ürün tükenmiş.",
        "track_prompt": "🔍 Lütfen sorgulamak istediğiniz **Sipariş Kodunu** yazın (Örn: WEE-5 veya sadece 5):",
        "track_not_found": "❌ Bu koda ait bir sipariş bulunamadı veya henüz onaylanmadı.",
        "track_result": "🔍 **Sipariş Sorgulama Sonucu (#{id})**\n\n📌 Ürün: {title}\n💰 Tutar: {price} USDT\n🟢 Durum: {status_text}\n\n👉 [Güvenli Konum Sayfasını Aç]({link})",
        "wallet_menu_text": "💰 **Cüzdan Yönetimi**\n\n💵 Güncel Bakiyeniz: **{balance} USDT**\n\nHesabınıza bakiye yükleyerek siparişlerinizi saniyesinde tek tıkla verebilirsiniz.",
        "deposit_btn": "📥 Bakiye Yükle (USDT)",
        "ask_deposit_amount": "📥 Lütfen hesabınıza yüklemek istediğiniz USDT miktarını rakam olarak yazın (Örn: 20):",
        "deposit_invoice": "📥 **Bakiye Yükleme Talebi (#{id})**\n\n💵 Yüklenecek Tutar: **{amount} USDT**\n🔒 Yatırım Adresi:\n`{wallet}`\n\n⏱️ 15 dakikanız vardır. Sistem ödemeyi otomatik algılayacaktır.",
        "deposit_check_btn": "🔄 Yatırımı Otomatik Kontrol Et",
        "deposit_success": "🎉 Ödemeniz onaylandı! **{amount} USDT** bakiyenize eklendi.\n💵 Yeni Toplam Bakiye: **{balance} USDT**",
        "buy_options": "📌 Ürün: {title}\n💰 Fiyat: {price} USDT\n💵 Bakiyeniz: {balance} USDT\n\nLütfen ödeme yöntemini seçin:",
        "pay_balance": "⚡ Bakiyeden Öde ({price} USDT)",
        "pay_crypto": "🔒 Blokzincir ile Doğrudan Öde",
        "insufficient_balance": "❌ Bakiyeniz yetersiz! Lütfen cüzdanınıza bakiye yükleyin veya doğrudan ödeme yapın.",
        "balance_success": "🎉 Siparişiniz başarıyla onaylandı! {price} USDT bakiyenizden düşüldü.\n\n🔑 Sipariş Takip Kodunuz: `WEE-{id}`\n👉 [Güvenli Konum Sayfasını Aç]({link})",
        "cancel": "❌ İptal",
        "invalid_drop": "⚠️ Ürün artık mevcut değil.",
        "order_created": "✅ Sipariş Oluşturuldu! (Sipariş No: #{id})\n\n📌 Ürün: {title}\n",
        "wallet_text": "🔒 Giriş Cüzdan Adresi:\n`{wallet}`\n\n⏱️ 15 dakikanız vardır. Ödemeyi yapınca sistem otomatik onaylayacaktır.",
        "check_btn": "🔄 Ödemeyi Otomatik Kontrol Et",
        "scan": "Blokzincir taranıyor...",
        "not_found": "İşlem veya sipariş bulunamadı.",
        "already_approved": "Zaten onaylanmış.",
        "expired": "Süresi dolmuş.",
        "time_out": "⏰ Süre aşımı nedeniyle iptal edildi.",
        "success_order": "✅ Sipariş #{id} onaylandı. Takip Kodunuz: `WEE-{id}`",
        "success_msg": "🎉 Ödemeniz onaylandı!\n🔑 Sipariş Takip Kodunuz: `WEE-{id}`\n\n👉 [Güvenli Konum Sayfasını Aç]({link})",
        "wait_tx": "⚠️ Henüz transfer yansımadı, blokzincir bekleniyor...",
        "support_ask": "📞 Canlı destek hattına bağlandınız. Lütfen mesajınızı yazın:\n\n*(Sohbeti sonlandırmak için aşağıdaki butonu kullanabilirsiniz)*",
        "support_sent": "✅ Mesajınız canlı destek ekibimize iletildi. Yanıt bekleniyor...",
        "support_closed": "🔒 Canlı destek oturumu sonlandırıldı.",
        "banned": "❌ Erişiminiz engellenmiştir."
    },
    "en": {
        "welcome": "👋 Hello! Welcome to the secure automated delivery bot. Please select your language:",
        "lang_set": "✅ Language set to English.",
        "btn_products": "🛍️ Products / Drops",
        "btn_orders": "📦 My Orders",
        "btn_track": "🔍 Track Order",
        "btn_miniapp": "🗺️ Map & Mini App",
        "btn_wallet": "💰 My Wallet / Balance",
        "btn_faq": "❓ How It Works (FAQ)",
        "btn_support": "📞 Support",
        "btn_lang": "🌐 Change Language",
        "no_stock": "❌ There are currently no ready products in stock.",
        "select_cat": "🏙️ Please select the **region / district** you want to view:",
        "back_cats": "🔙 Back to Regions",
        "no_cat_stock": "No active products left in this region.",
        "my_orders_title": "📦 **Your Order History:**",
        "no_orders": "📦 You don't have any order history yet.",
        "order_item": "• **Order #{id}** (Code: `WEE-{id}`) | {title} - {price} USDT\n  Status: {status} ({date})\n\n",
        "open_loc": "🔗 Open Order #{id} Location",
        "sold_out": "⚠️ This product is sold out.",
        "track_prompt": "🔍 Please enter your **Order Code** (e.g. WEE-5 or just 5):",
        "track_not_found": "❌ No order found with this code or not approved yet.",
        "track_result": "🔍 **Order Tracking Result (#{id})**\n\n📌 Product: {title}\n💰 Price: {price} USDT\n🟢 Status: {status_text}\n\n👉 [Open Secure Location Page]({link})",
        "wallet_menu_text": "💰 **Wallet Management**\n\n💵 Current Balance: **{balance} USDT**\n\nDeposit funds to your account for instant one-click purchases.",
        "deposit_btn": "📥 Deposit Balance (USDT)",
        "ask_deposit_amount": "📥 Please enter the amount of USDT you want to deposit (e.g. 20):",
        "deposit_invoice": "📥 **Deposit Invoice (#{id})**\n\n💵 Amount: **{amount} USDT**\n🔒 Deposit Address:\n`{wallet}`\n\n⏱️ You have 15 minutes. System will auto-approve.",
        "deposit_check_btn": "🔄 Auto-Check Deposit",
        "deposit_success": "🎉 Payment approved! **{amount} USDT** added to your balance.\n💵 New Total Balance: **{balance} USDT**",
        "buy_options": "📌 Product: {title}\n💰 Price: {price} USDT\n💵 Your Balance: {balance} USDT\n\nPlease select payment method:",
        "pay_balance": "⚡ Pay from Balance ({price} USDT)",
        "pay_crypto": "🔒 Pay Directly via Blockchain",
        "insufficient_balance": "❌ Insufficient balance! Please deposit funds or pay directly.",
        "balance_success": "🎉 Order successfully approved! {price} USDT deducted from your balance.\n🔑 Order Tracking Code: `WEE-{id}`\n\n👉 [Open Secure Location Page]({link})",
        "cancel": "❌ Cancel",
        "invalid_drop": "⚠️ Product is no longer available.",
        "order_created": "✅ Order Created! (Order No: #{id})\n\n📌 Product: {title}\n",
        "wallet_text": "🔒 Entry Wallet Address:\n`{wallet}`\n\n⏱️ You have 15 minutes. System will auto-approve.",
        "check_btn": "🔄 Auto-Check Payment",
        "scan": "Scanning blockchain...",
        "not_found": "Transaction or order not found.",
        "already_approved": "Already approved.",
        "expired": "Expired.",
        "time_out": "⏰ Canceled due to timeout.",
        "success_order": "✅ Order #{id} approved. Tracking Code: `WEE-{id}`",
        "success_msg": "🎉 Your payment is approved!\n🔑 Tracking Code: `WEE-{id}`\n\n👉 [Open Secure Location Page]({link})",
        "wait_tx": "⚠️ Transfer not reflected yet, checking blockchain...",
        "support_ask": "📞 Connected to live support. Type your message below:\n\n*(You can use the button below to end the chat)*",
        "support_sent": "✅ Your message has been sent to our live support team. Waiting for response...",
        "support_closed": "🔒 Live support session has been ended.",
        "banned": "❌ Your access has been restricted."
    }
}

# --- VERİTABANI KURULUMU ---
def init_db():
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS drops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            price REAL,
            photo_ids TEXT,
            description TEXT,
            stock INTEGER DEFAULT 1,
            is_sold INTEGER DEFAULT 0,
            category TEXT DEFAULT 'Genel',
            lat REAL DEFAULT 0.0,
            lon REAL DEFAULT 0.0
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
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            is_banned INTEGER DEFAULT 0,
            language TEXT DEFAULT 'tr',
            balance REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            sender TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            discount REAL,
            uses_left INTEGER DEFAULT 100,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('promo_5g_active', '1')")
    
    for col, def_val in [
        ("is_banned", "INTEGER DEFAULT 0"), 
        ("language", "TEXT DEFAULT 'tr'"), 
        ("balance", "REAL DEFAULT 0.0"),
        ("lat", "REAL DEFAULT 0.0"),
        ("lon", "REAL DEFAULT 0.0")
    ]:
        try:
            cursor.execute(f"ALTER TABLE drops ADD COLUMN {col} {def_val}")
        except:
            pass
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {def_val}")
        except:
            pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)
    ''')
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
    if res and res[0] in ["tr", "en"]:
        return res[0]
    return "tr"

def set_user_lang(user_id: int, lang: str):
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()
    conn.close()

def get_user_balance(user_id: int) -> float:
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res and res[0] is not None else 0.0

def log_panel_event(message, log_type="info"):
    try:
        conn = sqlite3.connect("drop_bot.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO panel_logs (message, log_type) VALUES (?, ?)", (message, log_type))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(e)

def is_admin(user_id: int) -> bool:
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def is_user_banned(user_id: int) -> bool:
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None and res[0] == 1

async def auto_backup_task():
    while True:
        await asyncio.sleep(86400)
        try:
            if os.path.exists("drop_bot.db"):
                file = FSInputFile("drop_bot.db")
                await bot.send_document(ADMIN_GROUP_ID, file, caption="💾 **Otomatik Günlük Veritabanı Yedeği**")
                log_panel_event("💾 Günlük otomatik veritabanı yedeği alındı.", "info")
        except Exception as e:
            logging.error(e)

async def background_payment_worker():
    while True:
        await asyncio.sleep(25)
        try:
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT orders.id, orders.user_id, orders.drop_id, orders.final_price, orders.created_at, drops.title, drops.stock, drops.category 
                FROM orders 
                JOIN drops ON orders.drop_id = drops.id 
                WHERE orders.status = 'pending'
            """)
            pending_orders = cursor.fetchall()
            
            cursor.execute("SELECT id, user_id, amount, created_at FROM deposits WHERE status = 'pending'")
            pending_deposits = cursor.fetchall()
            conn.close()

            if not pending_orders and not pending_deposits:
                continue

            api_url = f"https://api.trongrid.io/v1/accounts/{CRYPTO_WALLET}/trc20-transfers?contract_address={USDT_CONTRACT}&limit=20"
            tx_data = []
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        res_json = await response.json()
                        tx_data = res_json.get("data", [])

            for order in pending_orders:
                o_id, u_id, d_id, f_price, created_at_str, title, stock, category = order
                if datetime.now() - datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S") > timedelta(minutes=15):
                    conn = sqlite3.connect("drop_bot.db")
                    c = conn.cursor()
                    c.execute("UPDATE orders SET status = 'expired' WHERE id = ?", (o_id,))
                    conn.commit()
                    conn.close()
                    continue

                verified = False
                for tx in tx_data:
                    if tx.get("to") == CRYPTO_WALLET and int(tx.get("value", 0)) >= int(float(f_price) * 1000000):
                        verified = True
                        break

                if verified and main_loop:
                    conn = sqlite3.connect("drop_bot.db")
                    c = conn.cursor()
                    new_stock = stock - 1
                    if new_stock <= 0:
                        c.execute("UPDATE drops SET stock = 0, is_sold = 1 WHERE id = ?", (d_id,))
                    else:
                        c.execute("UPDATE drops SET stock = ? WHERE id = ?", (new_stock, d_id))
                    c.execute("UPDATE orders SET status = 'completed' WHERE id = ?", (o_id,))
                    conn.commit()
                    conn.close()

                    u_lang = get_user_lang(u_id)
                    secure_link = f"{RENDER_EXTERNAL_URL}/drop/{o_id}"
                    success_text = LANG[u_lang]["success_msg"].format(id=o_id, link=secure_link)

                    log_panel_event(f"🎉 Otomatik Arka Plan Satışı: #{o_id} - {title} ({f_price} USDT)", "success")
                    asyncio.run_coroutine_threadsafe(bot.send_message(u_id, success_text, parse_mode="Markdown"), main_loop)
                    asyncio.run_coroutine_threadsafe(bot.send_message(ADMIN_GROUP_ID, f"🎉 **OTOMATİK SATIŞ ONAYLANDI!**\n\n📌 Ürün: {title}\n💰 Tutar: {f_price} USDT\n🔑 Takip Kodu: `WEE-{o_id}`"), main_loop)

            for dep in pending_deposits:
                dep_id, u_id, amount, created_at_str = dep
                if datetime.now() - datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S") > timedelta(minutes=15):
                    conn = sqlite3.connect("drop_bot.db")
                    c = conn.cursor()
                    c.execute("UPDATE deposits SET status = 'expired' WHERE id = ?", (dep_id,))
                    conn.commit()
                    conn.close()
                    continue

                verified = False
                for tx in tx_data:
                    if tx.get("to") == CRYPTO_WALLET and int(tx.get("value", 0)) >= int(float(amount) * 1000000):
                        verified = True
                        break

                if verified and main_loop:
                    conn = sqlite3.connect("drop_bot.db")
                    c = conn.cursor()
                    c.execute("UPDATE deposits SET status = 'completed' WHERE id = ?", (dep_id,))
                    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, u_id))
                    conn.commit()
                    new_bal = get_user_balance(u_id)
                    conn.close()

                    u_lang = get_user_lang(u_id)
                    log_panel_event(f"📥 Otomatik Bakiye Yüklendi: Kullanıcı {u_id} - {amount} USDT", "success")
                    asyncio.run_coroutine_threadsafe(bot.send_message(u_id, LANG[u_lang]["deposit_success"].format(amount=amount, balance=new_bal)), main_loop)
                    asyncio.run_coroutine_threadsafe(bot.send_message(ADMIN_GROUP_ID, f"📥 **BAKİYE YÜKLENDİ!**\n\n👤 Kullanıcı ID: `{u_id}`\n💵 Miktar: **{amount} USDT**"), main_loop)

        except Exception as e:
            logging.error(f"Background worker error: {e}")

# --- WEB SUNUCUSU & GELİŞMİŞ TELEGRAM MINI APP ---
class SecureDropHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        cookies_str = self.headers.get('Cookie', '')
        is_logged_in = 'admin_auth=true' in cookies_str

        if parsed_path.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Weed Istanbul Server Active!")
            return

        if parsed_path.path == "/miniapp":
            miniapp_html = f"""
            <!DOCTYPE html>
            <html lang="tr">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Weed Istanbul - Ultimate Mini App</title>
                <script src="https://telegram.org/js/telegram-web-app.js"></script>
                <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
                <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
                <style>
                    :root {{
                        --bg-main: #090d16;
                        --card-bg: #111827;
                        --border-color: #1f2937;
                        --accent-blue: #38bdf8;
                        --accent-green: #10b981;
                        --accent-red: #ef4444;
                        --text-muted: #9ca3af;
                    }}
                    body {{ background-color: var(--bg-main); color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 12px; box-sizing: border-box; }}
                    .nav-tabs {{ display: flex; gap: 6px; overflow-x: auto; margin-bottom: 15px; padding-bottom: 4px; border-bottom: 1px solid var(--border-color); }}
                    .tab-btn {{ background: var(--card-bg); color: var(--text-muted); padding: 10px 14px; border-radius: 8px; border: 1px solid var(--border-color); font-size: 12px; font-weight: bold; cursor: pointer; white-space: nowrap; flex: 1; text-align: center; }}
                    .tab-btn.active {{ background: #2563eb; color: white; border-color: #3b82f6; }}
                    .tab-content {{ display: none; }}
                    .tab-content.active {{ display: block; }}
                    
                    .promo-banner {{ background: linear-gradient(135deg, #1e1b4b, #312e81); border: 1px solid #4338ca; padding: 12px; border-radius: 12px; margin-bottom: 15px; font-size: 13px; }}
                    .coupon-tag {{ background: rgba(16, 185, 129, 0.2); border: 1px dashed var(--accent-green); color: var(--accent-green); padding: 4px 8px; border-radius: 6px; font-family: monospace; font-weight: bold; display: inline-block; margin-top: 4px; }}
                    
                    #mainMap {{ width: 100%; height: 280px; border-radius: 12px; border: 1px solid var(--border-color); margin-bottom: 12px; }}
                    .card {{ background: var(--card-bg); padding: 15px; border-radius: 12px; border: 1px solid var(--border-color); margin-bottom: 12px; }}
                    
                    input, select {{ width: 100%; padding: 10px; background: var(--bg-main); border: 1px solid #374151; border-radius: 8px; color: white; box-sizing: border-box; font-size: 13px; margin-top: 6px; margin-bottom: 10px; }}
                    button {{ background: #2563eb; color: white; padding: 10px 15px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%; font-size: 13px; transition: 0.2s; }}
                    button:hover {{ background: #1d4ed8; }}
                    
                    .btn-received {{ background: var(--accent-green); }}
                    .btn-received:hover {{ background: #059669; }}
                    .btn-close {{ background: var(--accent-red); margin-top: 15px; }}
                    
                    /* Chat box CSS */
                    .chat-box {{ height: 260px; overflow-y: auto; background: var(--bg-main); padding: 10px; border-radius: 8px; border: 1px solid #374151; margin-bottom: 10px; }}
                    .msg {{ margin-bottom: 8px; padding: 8px 12px; border-radius: 8px; font-size: 13px; max-width: 80%; word-break: break-word; }}
                    .msg-user {{ background: #2563eb; margin-left: auto; color: white; }}
                    .msg-admin {{ background: var(--card-bg); border: 1px solid var(--border-color); color: var(--accent-blue); }}
                </style>
            </head>
            <body>
                <!-- ARKA PLAN MÜZİK WİDGET (wo3OCsPNevc) -->
                <div id="musicWidget" style="position: fixed; top: 12px; right: 12px; background: rgba(17, 24, 39, 0.95); border: 1px solid var(--border-color); padding: 6px 12px; border-radius: 20px; display: flex; align-items: center; gap: 8px; z-index: 1000; font-size: 11px; backdrop-filter: blur(5px); box-shadow: 0 4px 12px rgba(0,0,0,0.5);">
                    <span>🎵 Müzik</span>
                    <button onclick="toggleMusic()" id="musicBtn" style="padding: 4px 10px; width: auto; font-size: 11px; background: var(--accent-green); border-radius: 6px;">Oynat</button>
                </div>
                <div id="playerContainer" style="display:none;">
                    <iframe id="ytAudio" width="0" height="0" src="" frameborder="0" allow="autoplay"></iframe>
                </div>

                <div class="nav-tabs" style="margin-top: 45px;">
                    <button class="tab-btn active" onclick="switchTab('tabMap')">🗺️ Aktif Harita</button>
                    <button class="tab-btn" onclick="switchTab('tabProducts')">🛍️ Ürünler</button>
                    <button class="tab-btn" onclick="switchTab('tabWallet')">💰 Cüzdanım</button>
                    <button class="tab-btn" onclick="switchTab('tabOrders')">📦 Geçmiş</button>
                    <button class="tab-btn" onclick="switchTab('tabSupport')">💬 Destek</button>
                </div>

                <!-- 1. TAB: HARİTA -->
                <div id="tabMap" class="tab-content active">
                    <div id="promoContainer"></div>
                    
                    <!-- FİLTRELEME MENÜSÜ -->
                    <div style="display: flex; gap: 8px; margin-bottom: 10px; align-items: center;">
                        <select id="districtFilter" onchange="filterMapDrops()" style="margin:0; font-weight:bold; color:var(--accent-blue);">
                            <option value="ALL">🏙️ Tüm Bölgeler (Genel Harita)</option>
                        </select>
                    </div>

                    <p style="font-size: 11px; color: var(--text-muted); margin-top:0; line-height: 1.4;">📌 <b>Kırmızı Pin:</b> Satın aldığınız tam konum.<br>🌿 <b>Kenevir & Çember:</b> Yaklaşık bölge alanı (Satın alımda tam nokta açılır).</p>
                    <div id="mainMap"></div>
                    <div id="activeOrdersList"></div>
                </div>

                <!-- 2. TAB: ÜRÜN KATALOĞU -->
                <div id="tabProducts" class="tab-content">
                    <h3 style="color: var(--accent-blue); margin-top:0;">🛍️ Aktif Droplar & Stoklar</h3>
                    <div id="productsList"></div>
                </div>

                <!-- 3. TAB: CÜZDANIM & BAKİYE YÜKLEME -->
                <div id="tabWallet" class="tab-content">
                    <div class="card">
                        <h3 style="color: var(--accent-green); margin-top:0;">💰 Güncel Bakiye</h3>
                        <p style="font-size: 24px; font-weight: bold; margin: 5px 0;" id="userBalText">... USDT</p>
                        <hr style="border-color: var(--border-color); margin: 15px 0;">
                        <h4>📥 Bakiye Yükle (USDT TRC-20)</h4>
                        <label style="font-size: 12px; color: var(--text-muted);">Yüklemek İstediğiniz Tutar (USDT):</label>
                        <input type="number" id="depAmount" placeholder="Örn: 50">
                        <button onclick="createDeposit()">Cüzdan Adresi Oluştur</button>
                    </div>
                    <div id="depositResult"></div>
                </div>

                <!-- 4. TAB: GEÇMİŞ SİPARİŞLER -->
                <div id="tabOrders" class="tab-content">
                    <h3 style="color: var(--accent-blue); margin-top:0;">📦 Tamamlanan / Geçmiş Siparişlerim</h3>
                    <div id="pastOrdersList"></div>
                </div>

                <!-- 5. TAB: MİNİ APP İÇİ CHAT DESTEK -->
                <div id="tabSupport" class="tab-content">
                    <h3 style="color: var(--accent-blue); margin-top:0;">💬 Canlı Destek Ekibi</h3>
                    <div class="chat-box" id="chatBox"></div>
                    <div style="display: flex; gap: 6px;">
                        <input type="text" id="chatInput" placeholder="Mesajınızı yazın..." style="margin:0;">
                        <button onclick="sendChatMessage()" style="width: 80px;">Gönder</button>
                    </div>
                </div>

                <button class="btn btn-close" onclick="Telegram.WebApp.close()">🤖 Devam Et / Botu Kapat</button>

                <script>
                    const tg = window.Telegram.WebApp;
                    tg.expand();
                    
                    let userId = 0;
                    if (tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.id) {{
                        userId = tg.initDataUnsafe.user.id;
                    }} else {{
                        const urlParams = new URLSearchParams(window.location.search);
                        userId = urlParams.get('user_id') || 1012940363;
                    }}

                    let map, markersGroup;
                    let globalAppData = null;
                    let isMusicPlaying = false;

                    function toggleMusic() {{
                        const iframe = document.getElementById('ytAudio');
                        const btn = document.getElementById('musicBtn');
                        if(!isMusicPlaying) {{
                            iframe.src = "https://www.youtube.com/embed/wo3OCsPNevc?autoplay=1&loop=1&playlist=wo3OCsPNevc";
                            btn.innerText = "Durdur";
                            btn.style.background = "var(--accent-red)";
                            isMusicPlaying = true;
                        }} else {{
                            iframe.src = "";
                            btn.innerText = "Oynat";
                            btn.style.background = "var(--accent-green)";
                            isMusicPlaying = false;
                        }}
                    }}

                    function switchTab(tabId) {{
                        document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
                        document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
                        document.getElementById(tabId).classList.add('active');
                        event.target.classList.add('active');

                        if(tabId === 'tabMap' && map) {{
                            setTimeout(() => {{ map.invalidateSize(); }}, 200);
                        }}
                    }}

                    async function loadAppData() {{
                        if(!userId) return;
                        try {{
                            const res = await fetch('/api/miniapp-data?user_id=' + userId);
                            const data = await res.json();
                            globalAppData = data;
                            
                            document.getElementById('userBalText').innerText = data.balance.toFixed(2) + " USDT";
                            
                            let promoHtml = "";
                            if(data.promo_5g) {{
                                promoHtml += `<div class="promo-banner">🎁 <b>Özel Kampanya:</b> Toplu alımlarda <b>5 Gram Alana 1 Gram Hediye!</b></div>`;
                            }}
                            if(data.coupons && data.coupons.length > 0) {{
                                data.coupons.forEach(c => {{
                                    promoHtml += `<div class="promo-banner">🎟️ <b>Aktif Kupon:</b> Kod: <span class="coupon-tag">${{c.code}}</span> (-${{c.discount}} USDT İndirim)</div>`;
                                }});
                            }}
                            document.getElementById('promoContainer').innerHTML = promoHtml;

                            // Filtre menüsünü doldur
                            populateDistrictFilter(data.temsili_drops);

                            initMap(data.active_orders, data.temsili_drops);

                            let activeHtml = "";
                            if(data.active_orders.length > 0) {{
                                data.active_orders.forEach(o => {{
                                    activeHtml += `
                                    <div class="card" style="border-left: 4px solid var(--accent-red);">
                                        <h4 style="margin:0 0 5px 0; color:var(--accent-blue);">Sipariş #${{o.id}} - ${{o.title}}</h4>
                                        <p style="font-size:12px; margin:4px 0;"><b>İpucu / Not:</b> ${{o.description}}</p>
                                        <a href="https://www.google.com/maps?q=${{o.lat}},${{o.lon}}" target="_blank" style="color:#38bdf8; font-size:12px; text-decoration:none; font-weight:bold;">📍 Google Maps'te Aç</a>
                                        <button class="btn-received" style="margin-top:10px;" onclick="markReceived(${o.id})">✅ Ürünü Teslim Aldım</button>
                                    </div>`;
                                });
                            }} else {{
                                activeHtml = `<p style="font-size:12px; color:var(--text-muted);">Aktif / Alınmayı bekleyen siparişiniz yok.</p>`;
                            }}
                            document.getElementById('activeOrdersList').innerHTML = activeHtml;

                            let prodHtml = "";
                            data.temsili_drops.forEach(p => {{
                                prodHtml += `
                                <div class="card">
                                    <h4 style="margin:0; color:var(--accent-blue);">${{p.title}} (Semt: ${{p.category}})</h4>
                                    <p style="font-size:13px; font-weight:bold; color:var(--accent-green); margin:5px 0;">Fiyat: ${{p.price}} USDT | Stok: ${{p.stock}} Adet</p>
                                    <p style="font-size:11px; color:var(--text-muted); margin-bottom:8px;">⚠️ Güvenlik gereği tam adres satın alma sonrası görünür.</p>
                                    <button onclick="buyProduct(${{p.id}}, ${{p.price}})">⚡ Bakiyeden Satın Al (${{p.price}} USDT)</button>
                                </div>`;
                            });
                            document.getElementById('productsList').innerHTML = prodHtml;

                            let pastHtml = "";
                            if(data.past_orders.length > 0) {{
                                data.past_orders.forEach(po => {{
                                    pastHtml += `
                                    <div class="card" style="opacity:0.8;">
                                        <h4 style="margin:0;">Sipariş #${{po.id}} - ${{po.title}}</h4>
                                        <p style="font-size:12px; color:var(--accent-green); margin:4px 0;">✅ Teslim Alındı (${{po.date}})</p>
                                    </div>`;
                                }});
                            }} else {{
                                pastHtml = `<p style="font-size:12px; color:var(--text-muted);">Henüz geçmiş siparişiniz bulunmuyor.</p>`;
                            }}
                            document.getElementById('pastOrdersList').innerHTML = pastHtml;

                        }} catch(e) {{
                            console.error(e);
                        }}
                    }}

                    function populateDistrictFilter(drops) {{
                        const select = document.getElementById('districtFilter');
                        const categories = [...new Set(drops.map(d => d.category))];
                        categories.forEach(cat => {{
                            const opt = document.createElement('option');
                            opt.value = cat;
                            opt.innerText = "🏙️ " + cat + " Bölgesi";
                            select.appendChild(opt);
                        }});
                    }}

                    function initMap(activeOrders, temsilidrops) {{
                        if(map) return;
                        map = L.map('mainMap').setView([41.0082, 28.9784], 11);
                        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png').addTo(map);
                        markersGroup = L.layerGroup().addTo(map);

                        renderMapMarkers(activeOrders, temsilidrops);
                    }}

                    function renderMapMarkers(activeOrders, temsilidrops, filterCat = "ALL") {{
                        markersGroup.clearLayers();

                        activeOrders.forEach(o => {{
                            const redIcon = L.divIcon({{
                                html: '<div style="background:#ef4444; border:2px solid white; border-radius:50%; width:24px; height:24px; text-align:center; line-height:24px; font-size:12px; box-shadow:0 2px 6px rgba(0,0,0,0.4);">📍</div>',
                                iconSize: [24, 24]
                            }});
                            L.marker([o.lat, o.lon], {{icon: redIcon}}).addTo(markersGroup)
                                .bindPopup(`<b>Sipariş #${{o.id}}</b><br>${{o.title}}<br><br><button style="padding:4px;" onclick="markReceived(${{o.id}})">Teslim Aldım</button>`);
                        }});

                        temsilidrops.forEach(td => {{
                            if(filterCat !== "ALL" && td.category !== filterCat) return;

                            // BÖLGE ALAN ÇEMBERİ (BLURRING / AREA CIRCLE)
                            L.circle([td.lat, td.lon], {{
                                color: '#38bdf8',
                                fillColor: '#38bdf8',
                                fillOpacity: 0.12,
                                radius: 1100
                            }}).addTo(markersGroup);

                            const weedIcon = L.divIcon({{
                                html: '<div style="background:#2563eb; border:2px solid white; border-radius:50%; width:28px; height:28px; text-align:center; line-height:28px; font-size:14px; box-shadow: 0 2px 6px rgba(0,0,0,0.4);">🌿</div>',
                                iconSize: [28, 28],
                                iconAnchor: [14, 14]
                            }});
                            L.marker([td.lat, td.lon], {{icon: weedIcon}}).addTo(markersGroup)
                                .bindPopup(`<b>${{td.title}}</b><br>Bölge: ${{td.category}}<br>Fiyat: ${{td.price}} USDT<br><span style="font-size:11px; color:#9ca3af;">⚠️ Yaklaşık bölgedir.</span>`);
                        }});
                    }}

                    function filterMapDrops() {{
                        const selectedCat = document.getElementById('districtFilter').value;
                        if(globalAppData) {{
                            renderMapMarkers(globalAppData.active_orders, globalAppData.temsili_drops, selectedCat);
                            if(selectedCat !== "ALL") {{
                                const sample = globalAppData.temsili_drops.find(d => d.category === selectedCat);
                                if(sample) {{
                                    map.setView([sample.lat, sample.lon], 13);
                                }}
                            }} else {{
                                map.setView([41.0082, 28.9784], 11);
                            }}
                        }}
                    }}

                    async function markReceived(orderId) {{
                        if(!confirm("Ürünü teslim aldığınızı onaylıyor musunuz?")) return;
                        try {{
                            const res = await fetch('/api/miniapp-received?id=' + orderId);
                            const data = await res.json();
                            if(data.success) {{
                                alert("Ürün teslim alındı olarak kaydedildi!");
                                location.reload();
                            }}
                        }} catch(e) {{
                            alert("İşlem başarısız.");
                        }}
                    }}

                    async function buyProduct(dropId, price) {{
                        if(!confirm(price + " USDT bakiyenizden düşülecektir. Onaylıyor musunuz?")) return;
                        try {{
                            const res = await fetch(`/api/miniapp-buy?user_id=${{userId}}&drop_id=${{dropId}}`);
                            const data = await res.json();
                            if(data.success) {{
                                alert("🎉 Sipariş onaylandı! Haritanıza tam konum eklendi.");
                                location.reload();
                            }} else {{
                                alert("❌ Hata: " + (data.message || "Bakiyeniz yetersiz olabilir."));
                            }}
                        }} catch(e) {{
                            alert("İşlem yapılırken hata oluştu.");
                        }}
                    }}

                    async function createDeposit() {{
                        const amount = document.getElementById('depAmount').value;
                        if(!amount || amount <= 0) return alert("Geçerli bir miktar girin.");
                        try {{
                            const res = await fetch(`/api/miniapp-deposit?user_id=${{userId}}&amount=${{amount}}`);
                            const data = await res.json();
                            if(data.success) {{
                                document.getElementById('depositResult').innerHTML = `
                                <div class="card" style="border: 1px solid var(--accent-green);">
                                    <h4 style="color:var(--accent-green); margin-top:0;">Yatırım Adresi Oluşturuldu</h4>
                                    <p style="font-size:12px;">Tutar: <b>${{amount}} USDT</b></p>
                                    <input type="text" value="${{data.wallet}}" readonly>
                                    <button onclick="checkDeposit(${{data.deposit_id}}, ${{amount}})" style="background:var(--accent-green);">🔄 Yatırımı Otomatik Kontrol Et</button>
                                </div>`;
                            }}
                        }} catch(e) {{
                            alert("Bakiye yükleme talebi oluşturulamadı.");
                        }}
                    }}

                    async function checkDeposit(depId, amount) {{
                        alert("Blokzincir taranıyor, lütfen bekleyin...");
                        try {{
                            const res = await fetch(`/api/miniapp-check-deposit?dep_id=${{depId}}&user_id=${{userId}}&amount=${{amount}}`);
                            const data = await res.json();
                            if(data.success) {{
                                alert("🎉 Ödemeniz onaylandı ve bakiyenize eklendi!");
                                location.reload();
                            }} else {{
                                alert("⚠️ Transfer henüz algılanmadı.");
                            }}
                        }} catch(e) {{
                            alert("Kontrol başarısız.");
                        }}
                    }}

                    async function loadChatMessages() {{
                        if(!userId) return;
                        try {{
                            const res = await fetch('/api/miniapp-chat?user_id=' + userId);
                            const data = await res.json();
                            let chatHtml = "";
                            data.messages.forEach(m => {{
                                const cls = m.sender === 'user' ? 'msg-user' : 'msg-admin';
                                const senderName = m.sender === 'user' ? 'Sen' : '👑 Destek';
                                chatHtml += `<div class="msg ${{cls}}"><b>${{senderName}}:</b> ${{m.message}}</div>`;
                            }});
                            const box = document.getElementById('chatBox');
                            box.innerHTML = chatHtml;
                            box.scrollTop = box.scrollHeight;
                        }} catch(e) {{}}
                    }}

                    async function sendChatMessage() {{
                        const inp = document.getElementById('chatInput');
                        const msg = inp.value.trim();
                        if(!msg) return;
                        inp.value = '';
                        try {{
                            await fetch('/api/miniapp-chat-send', {{
                                method: 'POST',
                                headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                                body: `user_id=${{userId}}&message=${{encodeURIComponent(msg)}}`
                            }});
                            loadChatMessages();
                        }} catch(e) {{}}
                    }}

                    window.onload = () => {{
                        loadAppData();
                        loadChatMessages();
                        setInterval(loadChatMessages, 4000);
                    }};
                </script>
            </body>
            </html>
            """
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(miniapp_html.encode("utf-8"))
            return

        if parsed_path.path == "/api/miniapp-data":
            uid = int(query_params.get("user_id", ["0"])[0])
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            
            cursor.execute("SELECT balance FROM users WHERE user_id = ?", (uid,))
            u_row = cursor.fetchone()
            bal = u_row[0] if u_row else 0.0

            cursor.execute("SELECT value FROM settings WHERE key = 'promo_5g_active'")
            p_res = cursor.fetchone()
            promo_5g = p_res and p_res[0] == "1"

            cursor.execute("SELECT code, discount FROM coupons WHERE uses_left > 0")
            coupons_rows = cursor.fetchall()
            coupons = [{"code": r[0], "discount": r[1]} for r in coupons_rows]

            cursor.execute("""
                SELECT orders.id, drops.title, drops.lat, drops.lon, drops.description, drops.category
                FROM orders 
                JOIN drops ON orders.drop_id = drops.id 
                WHERE orders.user_id = ? AND orders.status = 'completed'
            """, (uid,))
            active_orders_rows = cursor.fetchall()
            active_orders = []
            for r in active_orders_rows:
                lat = r[2] if r[2] and r[2] != 0.0 else get_district_coord(r[5])[0]
                lon = r[3] if r[3] and r[3] != 0.0 else get_district_coord(r[5])[1]
                active_orders.append({"id": r[0], "title": r[1], "lat": lat, "lon": lon, "description": r[4]})

            cursor.execute("""
                SELECT orders.id, drops.title, orders.created_at
                FROM orders 
                JOIN drops ON orders.drop_id = drops.id 
                WHERE orders.user_id = ? AND orders.status = 'received'
                ORDER BY orders.id DESC
            """, (uid,))
            past_orders_rows = cursor.fetchall()
            past_orders = [{"id": r[0], "title": r[1], "date": r[2]} for r in past_orders_rows]

            cursor.execute("SELECT id, title, price, category, stock FROM drops WHERE is_sold = 0 AND stock > 0")
            temsili_rows = cursor.fetchall()
            temsili_drops = []
            for r in temsili_rows:
                coord = get_district_coord(r[3])
                temsili_drops.append({"id": r[0], "title": r[1], "price": r[2], "category": r[3], "stock": r[4], "lat": coord[0], "lon": coord[1]})

            conn.close()

            resp = {
                "balance": bal,
                "promo_5g": promo_5g,
                "coupons": coupons,
                "active_orders": active_orders,
                "past_orders": past_orders,
                "temsili_drops": temsili_drops
            }
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        if parsed_path.path == "/api/miniapp-buy":
            uid = int(query_params.get("user_id", ["0"])[0])
            did = int(query_params.get("drop_id", ["0"])[0])
            
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("SELECT title, price, stock FROM drops WHERE id = ? AND is_sold = 0 AND stock > 0", (did,))
            drop = cursor.fetchone()
            
            if not drop:
                conn.close()
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": "Stok tükenmiş."}).encode("utf-8"))
                return

            title, price, stock = drop
            bal = get_user_balance(uid)

            if bal < price:
                conn.close()
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": "Bakiyeniz yetersiz."}).encode("utf-8"))
                return

            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, uid))
            new_stock = stock - 1
            if new_stock <= 0:
                cursor.execute("UPDATE drops SET stock = 0, is_sold = 1 WHERE id = ?", (did,))
            else:
                cursor.execute("UPDATE drops SET stock = ? WHERE id = ?", (new_stock, did))

            cursor.execute("INSERT INTO orders (user_id, drop_id, status, final_price) VALUES (?, ?, 'completed', ?)", (uid, did, price))
            oid = cursor.lastrowid
            conn.commit()
            conn.close()

            log_panel_event(f"⚡ Mini App İçinden Satış: Sipariş #{oid} - {title} ({price} USDT)", "success")
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "order_id": oid}).encode("utf-8"))
            return

        if parsed_path.path == "/api/miniapp-deposit":
            uid = int(query_params.get("user_id", ["0"])[0])
            amount = float(query_params.get("amount", ["0"])[0])

            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO deposits (user_id, amount, status) VALUES (?, ?, 'pending')", (uid, amount))
            dep_id = cursor.lastrowid
            conn.commit()
            conn.close()

            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "deposit_id": dep_id, "wallet": CRYPTO_WALLET}).encode("utf-8"))
            return

        if parsed_path.path == "/api/miniapp-check-deposit":
            dep_id = int(query_params.get("dep_id", ["0"])[0])
            uid = int(query_params.get("user_id", ["0"])[0])
            target_amount = float(query_params.get("amount", ["0"])[0])

            api_url = f"https://api.trongrid.io/v1/accounts/{CRYPTO_WALLET}/trc20-transfers?contract_address={USDT_CONTRACT}&limit=15"
            verified = False
            try:
                async def verify_tx():
                    async with aiohttp.ClientSession() as session:
                        async with session.get(api_url) as response:
                            if response.status == 200:
                                res_json = await response.json()
                                for tx in res_json.get("data", []):
                                    if tx.get("to") == CRYPTO_WALLET and int(tx.get("value", 0)) >= int(target_amount * 1000000):
                                        return True
                    return False

                verified = asyncio.run(verify_tx())
            except Exception as e:
                logging.error(e)

            if verified:
                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("UPDATE deposits SET status = 'completed' WHERE id = ?", (dep_id,))
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (target_amount, uid))
                conn.commit()
                conn.close()
                log_panel_event(f"📥 Mini App Bakiye Yükleme Onaylandı: Kullanıcı {uid} - {target_amount} USDT", "success")

            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": verified}).encode("utf-8"))
            return

        if parsed_path.path == "/api/miniapp-chat":
            uid = int(query_params.get("user_id", ["0"])[0])
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("SELECT sender, message, created_at FROM support_messages WHERE user_id = ? ORDER BY id ASC", (uid,))
            msgs = [{"sender": r[0], "message": r[1], "date": r[2]} for r in cursor.fetchall()]
            conn.close()

            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"messages": msgs}).encode("utf-8"))
            return

        if parsed_path.path == "/api/miniapp-received":
            oid = query_params.get("id", ["0"])[0]
            try:
                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("UPDATE orders SET status = 'received' WHERE id = ? AND status = 'completed'", (oid,))
                conn.commit()
                conn.close()
                log_panel_event(f"✅ Mini App üzerinden sipariş #{oid} teslim alındı olarak onaylandı.", "success")
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(b'{"success": true}')
            except:
                self.send_response(500)
                self.end_headers()
            return

        if parsed_path.path == "/api/check-new-messages":
            if not is_logged_in:
                self.send_response(401)
                self.end_headers()
                return
            
            last_id = int(query_params.get("last_id", [0])[0])
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("SELECT sm.id, sm.user_id, sm.message, u.username FROM support_messages sm LEFT JOIN users u ON sm.user_id = u.user_id WHERE sm.id > ? AND sm.sender = 'user' ORDER BY sm.id ASC LIMIT 1", (last_id,))
            new_msg = cursor.fetchone()
            conn.close()

            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            if new_msg:
                m_id, u_id, m_text, uname = new_msg
                display_name = f"@{uname}" if uname else f"Kullanıcı {u_id}"
                resp_data = {"has_new": True, "id": m_id, "user_id": u_id, "username": display_name, "message": m_text}
                self.wfile.write(json.dumps(resp_data).encode("utf-8"))
            else:
                self.wfile.write(b'{"has_new": false}')
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
            
            cursor.execute("SELECT SUM(final_price) FROM orders WHERE status IN ('completed', 'received')")
            rev_res = cursor.fetchone()[0]
            total_revenue = rev_res if rev_res is not None else 0.0

            content_html = ""
            if tab == "home":
                cursor.execute("SELECT id, title, price, stock, category, lat, lon FROM drops WHERE is_sold = 0 AND stock > 0")
                active_drops_for_map = cursor.fetchall()
                
                map_markers_js = ""
                for ad in active_drops_for_map:
                    d_id, d_title, d_price, d_stock, d_cat, d_lat, d_lon = ad
                    lat = d_lat if d_lat and d_lat != 0.0 else get_district_coord(d_cat)[0]
                    lon = d_lon if d_lon and d_lon != 0.0 else get_district_coord(d_cat)[1]
                    map_markers_js += f"""
                    markers[{d_id}] = L.marker([{lat}, {lon}], {{icon: weedIcon}}).addTo(map)
                        .bindPopup("<b>#{d_id} - {d_title}</b><br>Bölge: {d_cat}<br>Fiyat: {d_price} USDT<br>Stok: {d_stock}");
                    """

                cursor.execute("SELECT message, log_type, created_at FROM panel_logs ORDER BY id DESC LIMIT 10")
                logs = cursor.fetchall()
                logs_html = ""
                for l in logs:
                    msg, l_type, l_date = l
                    badge_color = "#ef4444" if l_type == "warning" else ("#10b981" if l_type == "success" else "#3b82f6")
                    logs_html += f"""
                    <div style="background: var(--card-bg-inner); padding: 12px 15px; border-radius: 8px; margin-bottom: 8px; border-left: 4px solid {badge_color}; font-size: 13px;">
                        <span style="color: var(--text-muted); font-size: 11px; display: block; margin-bottom: 2px;">{l_date}</span>
                        {msg}
                    </div>
                    """

                cursor.execute("""
                    SELECT DATE(created_at) as cday, SUM(final_price) 
                    FROM orders WHERE status IN ('completed', 'received') 
                    GROUP BY cday ORDER BY cday ASC LIMIT 7
                """)
                chart_rows = cursor.fetchall()
                labels = [r[0] for r in chart_rows] if chart_rows else ["Bugün"]
                values = [r[1] for r in chart_rows] if chart_rows else [total_revenue]

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                w1_bal = loop.run_until_complete(fetch_wallet_balance(CRYPTO_WALLET))
                w2_bal = loop.run_until_complete(fetch_wallet_balance(EXIT_WALLET))
                w3_bal = loop.run_until_complete(fetch_wallet_balance(MAIN_SAVINGS_WALLET))
                loop.close()

                content_html = f"""
                <div class="stats-grid">
                    <div class="card"><h3>TOTAL REVENUE</h3><p>{total_revenue} USDT</p></div>
                    <div class="card"><h3>ACTIVE STOCK</h3><p>{total_active_stock} Pcs</p></div>
                    <div class="card"><h3>PRODUCT VARIETY</h3><p>{total_drops}</p></div>
                </div>

                <div class="form-box" style="margin-bottom: 30px; border: 1px solid #38bdf8;">
                    <h2 style="color: #38bdf8; margin-top: 0; display: flex; align-items: center; gap: 10px;">
                        🗺️ İstanbul Aktif Konum Haritası 
                        <span style="font-size: 11px; background: var(--card-bg-inner); padding: 4px 10px; border-radius: 6px; color: var(--text-muted);">Ürün No ile Arama</span>
                    </h2>
                    <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                        <input type="number" id="searchProductId" placeholder="Ürün Numarası Yazın (Örn: 1, 2...)" style="margin:0; flex: 1; background: var(--input-bg); border: 1px solid var(--border-color); border-radius: 8px; color: var(--text-color); padding: 10px; font-size: 14px;">
                        <button type="button" onclick="searchMarkerOnMap()" style="width: auto; background: #10b981; padding: 10px 20px; font-weight: bold; border-radius: 8px; border: none; color: white; cursor: pointer;">🔍 Haritada Bul</button>
                    </div>
                    <div id="istanbulMap" style="width: 100%; height: 420px; border-radius: 12px; border: 1px solid var(--border-color); z-index: 1;"></div>
                </div>

                <div class="form-box" style="margin-bottom: 30px; border: 1px solid #38bdf8;">
                    <h2 style="color: #38bdf8; margin-top: 0;">🏦 Cüzdan Mimarisi & Canlı Bakiye Takibi</h2>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; margin-top: 15px;">
                        <div style="background: var(--card-bg-inner); padding: 15px; border-radius: 8px; border-left: 4px solid #3b82f6;">
                            <h4 style="margin: 0 0 5px 0; color: #38bdf8; display: flex; justify-content: space-between; align-items: center;">
                                📥 1. Giriş Hesabı (Bot)
                                <button onclick="copyText('{CRYPTO_WALLET}')" style="background:#2563eb; border:none; padding:3px 8px; font-size:10px; border-radius:4px; cursor:pointer; color:white; width:auto;">Kopyala</button>
                            </h4>
                            <p style="font-size: 12px; font-weight: bold; color: #10b981; margin: 5px 0;">💵 Bakiye: {w1_bal} USDT</p>
                            <p style="font-size: 11px; color: var(--text-muted); word-break: break-all; margin: 0;">`{CRYPTO_WALLET}`</p>
                        </div>
                        <div style="background: var(--card-bg-inner); padding: 15px; border-radius: 8px; border-left: 4px solid #d97706;">
                            <h4 style="margin: 0 0 5px 0; color: #d97706; display: flex; justify-content: space-between; align-items: center;">
                                🔄 2. Çıkış / Ara Hesap (Bitay)
                                <button onclick="copyText('{EXIT_WALLET}')" style="background:#d97706; border:none; padding:3px 8px; font-size:10px; border-radius:4px; cursor:pointer; color:white; width:auto;">Kopyala</button>
                            </h4>
                            <p style="font-size: 12px; font-weight: bold; color: #10b981; margin: 5px 0;">💵 Bakiye: {w2_bal} USDT</p>
                            <p style="font-size: 11px; color: var(--text-muted); word-break: break-all; margin: 0;">`{EXIT_WALLET}`</p>
                        </div>
                        <div style="background: var(--card-bg-inner); padding: 15px; border-radius: 8px; border-left: 4px solid #10b981;">
                            <h4 style="margin: 0 0 5px 0; color: #10b981; display: flex; justify-content: space-between; align-items: center;">
                                💰 3. Ana Birikim / Kasa
                                <button onclick="copyText('{MAIN_SAVINGS_WALLET}')" style="background:#10b981; border:none; padding:3px 8px; font-size:10px; border-radius:4px; cursor:pointer; color:white; width:auto;">Kopyala</button>
                            </h4>
                            <p style="font-size: 12px; font-weight: bold; color: #10b981; margin: 5px 0;">💵 Bakiye: {w3_bal} USDT</p>
                            <p style="font-size: 11px; color: var(--text-muted); word-break: break-all; margin: 0;">`{MAIN_SAVINGS_WALLET}`</p>
                        </div>
                    </div>
                </div>

                <div class="grid-2">
                    <div class="table-box">
                        <h2>📊 Weekly Revenue Trend</h2>
                        <canvas id="revenueChart" style="max-height: 250px;"></canvas>
                    </div>

                    <div class="table-box">
                        <h2>🔔 Live Logs & Alerts</h2>
                        <div style="max-height: 250px; overflow-y: auto;">
                            {logs_html if logs_html else "<p style='text-align:center; color:var(--text-muted);'>No recent logs.</p>"}
                        </div>
                    </div>
                </div>

                <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
                <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
                <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
                <script>
                    const map = L.map('istanbulMap').setView([41.0082, 28.9784], 11);
                    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                        attribution: '&copy; OpenStreetMap contributors',
                        maxZoom: 19
                    }}).addTo(map);

                    const weedIcon = L.divIcon({{
                        className: 'custom-weed-marker',
                        html: '<div style="background: #111827; border: 2px solid #38bdf8; border-radius: 50%; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; font-size: 20px; box-shadow: 0 4px 12px rgba(56,189,248,0.4);">🌿</div>',
                        iconSize: [36, 36],
                        iconAnchor: [18, 18],
                        popupAnchor: [0, -18]
                    }});

                    const markers = {{}};
                    {map_markers_js}

                    function searchMarkerOnMap() {{
                        const id = document.getElementById('searchProductId').value.trim();
                        if (markers[id]) {{
                            map.setView(markers[id].getLatLng(), 16);
                            markers[id].openPopup();
                        }} else {{
                            alert("Bu numaraya ait aktif harita konumu bulunamadı!");
                        }}
                    }}

                    const ctx = document.getElementById('revenueChart').getContext('2d');
                    new Chart(ctx, {{
                        type: 'line',
                        data: {{
                            labels: {labels},
                            datasets: [{{
                                label: 'Revenue (USDT)',
                                data: {values},
                                borderColor: '#38bdf8',
                                backgroundColor: 'rgba(56, 189, 248, 0.1)',
                                fill: true,
                                tension: 0.3
                            }}]
                        }},
                        options: {{
                            responsive: true,
                            plugins: {{ legend: {{ display: false }} }},
                            scales: {{
                                x: {{ grid: {{ color: 'var(--border-color)' }}, ticks: {{ color: 'var(--text-muted)' }} }},
                                y: {{ grid: {{ color: 'var(--border-color)' }}, ticks: {{ color: 'var(--text-muted)' }} }}
                            }}
                        }}
                    }});
                </script>
                """
            elif tab == "support":
                cursor.execute("SELECT DISTINCT user_id FROM support_messages")
                active_chats_users = [row[0] for row in cursor.fetchall()]
                
                selected_user_id = query_params.get("user_id", [str(active_chats_users[0]) if active_chats_users else "0"])[0]
                try:
                    selected_user_id = int(selected_user_id)
                except:
                    selected_user_id = 0

                chat_list_html = ""
                for uid in active_chats_users:
                    cursor.execute("SELECT username FROM users WHERE user_id = ?", (uid,))
                    u_row = cursor.fetchone()
                    uname = f"@{u_row[0]}" if u_row and u_row[0] else f"User {uid}"
                    active_style = "background: var(--sidebar-hover); border-color: #38bdf8;" if uid == selected_user_id else "background: var(--card-bg-inner);"
                    chat_list_html += f"""
                    <a href="/admin-web?tab=support&user_id={uid}" style="display: block; padding: 10px 14px; border-radius: 8px; text-decoration: none; color: var(--text-color); margin-bottom: 6px; border: 1px solid var(--border-color); {active_style}">
                        <div style="font-weight: bold; color: #38bdf8; font-size: 13px;">{uname}</div>
                        <div style="font-size: 11px; color: var(--text-muted);">ID: {uid}</div>
                    </a>
                    """

                messages_html = ""
                if selected_user_id:
                    cursor.execute("SELECT sender, message, created_at FROM support_messages WHERE user_id = ? ORDER BY id ASC", (selected_user_id,))
                    msgs = cursor.fetchall()
                    for m in msgs:
                        sender, msg_text, m_date = m
                        is_admin_msg = sender == "admin"
                        bg_color = "#2563eb" if is_admin_msg else "var(--card-bg-inner)"
                        align = "margin-left: auto;" if is_admin_msg else "margin-right: auto;"
                        sender_label = "👑 Yönetici (Sen)" if is_admin_msg else "👤 Müşteri"
                        messages_html += f"""
                        <div style="max-width: 80%; background: {bg_color}; padding: 10px 14px; border-radius: 10px; margin-bottom: 10px; {align} border: 1px solid var(--border-color);">
                            <div style="font-size: 10px; color: var(--text-muted); margin-bottom: 4px; display:flex; justify-content: space-between; gap: 10px;">
                                <span>{sender_label}</span>
                                <span>{m_date}</span>
                            </div>
                            <div style="font-size: 13px; word-break: break-word;">{msg_text}</div>
                        </div>
                        """

                chat_box_html = ""
                if selected_user_id:
                    chat_box_html = f"""
                    <div style="display: flex; flex-direction: column; height: 100%;">
                        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 10px; margin-bottom: 12px; flex-wrap: wrap; gap: 10px;">
                            <h3 style="margin: 0; color: #38bdf8; font-size: 15px;">💬 Aktif Sohbet (ID: {selected_user_id})</h3>
                            <form action="/admin-close-support" method="POST" style="margin:0;">
                                <input type="hidden" name="user_id" value="{selected_user_id}">
                                <button type="submit" style="background: #ef4444; padding: 6px 12px; font-size: 11px; width: auto; border-radius: 6px;">🔒 Sohbeti Bitir & Temizle</button>
                            </form>
                        </div>
                        <div style="flex: 1; overflow-y: auto; max-height: 350px; padding-right: 5px; margin-bottom: 12px;">
                            {messages_html if messages_html else "<p style='text-align:center; color:var(--text-muted);'>Henüz mesaj yok.</p>"}
                        </div>
                        <form action="/admin-send-support" method="POST" style="display: flex; gap: 8px; margin: 0;">
                            <input type="hidden" name="user_id" value="{selected_user_id}">
                            <input type="text" name="message" required placeholder="Müşteriye yanıt yazın..." style="margin:0; flex: 1; padding: 10px; font-size: 13px;">
                            <button type="submit" style="width: auto; background: #10b981; padding: 0 18px; font-size: 13px;">Gönder</button>
                        </form>
                    </div>
                    """
                else:
                    chat_box_html = "<p style='text-align:center; color:var(--text-muted); padding: 30px;'>Lütfen listeden bir sohbet seçin.</p>"

                content_html = f"""
                <div class="support-container">
                    <div class="chat-main-area">
                        {chat_box_html}
                    </div>
                    <div class="support-sidebar-area">
                        <h3 style="margin-top: 0; color: var(--text-color); font-size: 15px; border-bottom: 1px solid var(--border-color); padding-bottom: 8px; margin-bottom: 10px;">👥 Destek Talepleri</h3>
                        <div style="max-height: 350px; overflow-y: auto;">
                            {chat_list_html if chat_list_html else "<p style='color:var(--text-muted); font-size: 13px;'>Aktif müşteri sohbeti bulunmuyor.</p>"}
                        </div>
                    </div>
                </div>
                <style>
                    .support-container {{ display: flex; flex-direction: column; gap: 20px; background: var(--card-bg); padding: 20px; border-radius: 14px; border: 1px solid var(--border-color); }}
                    .chat-main-area {{ order: 1; background: var(--card-bg-inner); padding: 15px; border-radius: 10px; border: 1px solid var(--border-color); }}
                    .support-sidebar-area {{ order: 2; background: var(--card-bg-inner); padding: 15px; border-radius: 10px; border: 1px solid var(--border-color); }}
                    @media (min-width: 900px) {{
                        .support-container {{ display: grid; grid-template-columns: 1fr 300px; gap: 20px; }}
                        .chat-main-area {{ order: 1; }}
                        .support-sidebar-area {{ order: 2; }}
                    }}
                </style>
                """
            elif tab == "broadcast":
                content_html = """
                <div class="form-box" style="border: 1px solid #38bdf8;">
                    <h2 style="color: #38bdf8; margin-top: 0;">📢 Toplu Duyuru & Kampanya Merkezi (Broadcast)</h2>
                    <p style="color: var(--text-muted); font-size: 13px; margin-bottom: 20px;">Botu kullanan tüm kullanıcılara anında duyuru, kampanya veya indirim mesajı fırlatın.</p>
                    <form action="/admin-broadcast" method="POST">
                        <label>Duyuru Mesajı (Markdown destekler):</label>
                        <textarea name="message" rows="6" required placeholder="🔥 Büyük indirim başladı! Tüm ürünlerde geçerli kupon kodunuz: ..."></textarea>
                        <button type="submit" style="background: #2563eb; margin-top: 15px;">🚀 Tüm Kullanıcılara Gönder</button>
                    </form>
                </div>
                """
            elif tab == "promo5g":
                cursor.execute("SELECT value FROM settings WHERE key = 'promo_5g_active'")
                s_res = cursor.fetchone()
                is_5g_active = s_res and s_res[0] == "1"
                status_text = "🟢 AKTİF (5 Alana 1 Hediye Bilgilendirmesi Açık)" if is_5g_active else "🔴 PASİF"
                toggle_btn_text = "Kampanyayı Kapat" if is_5g_active else "Kampanyayı Aç"
                toggle_val = "0" if is_5g_active else "1"

                content_html = f"""
                <div class="form-box" style="border: 1px solid #10b981;">
                    <h2 style="color: #10b981; margin-top: 0;">🎁 5 Gram Alana 1 Gram Hediye Kampanyası</h2>
                    <p style="color: var(--text-muted); font-size: 14px; margin-bottom: 15px;">Mevcut Durum: <b>{status_text}</b></p>
                    <form action="/admin-toggle-5g" method="POST">
                        <input type="hidden" name="status" value="{toggle_val}">
                        <button type="submit" style="background: {'#ef4444' if is_5g_active else '#10b981'}; width: auto; padding: 12px 25px;">{toggle_btn_text}</button>
                    </form>
                </div>
                """
            elif tab == "coupons":
                cursor.execute("SELECT id, code, discount, uses_left, created_at FROM coupons ORDER BY id DESC")
                c_rows = cursor.fetchall()
                c_table = ""
                for c in c_rows:
                    cid, ccode, cdisc, cuses, cdate = c
                    c_table += f"<tr><td>#{cid}</td><td><code>{ccode}</code></td><td><b>{cdisc} USDT</b></td><td>{cuses} Adet</td><td>{cdate}</td></tr>"

                content_html = f"""
                <div class="grid-2" style="grid-template-columns: 1fr 1fr; gap: 20px;">
                    <div class="form-box" style="margin:0; border: 1px solid #10b981;">
                        <h2 style="color: #10b981; margin-top: 0;">🎟️ Yeni Kupon Oluştur & Bot Duyurusu</h2>
                        <form action="/admin-add-coupon" method="POST">
                            <label>Kupon Kodu:</label>
                            <input type="text" name="code" required placeholder="Örn: YAZ2026">
                            <label>İndirim Tutarı (USDT):</label>
                            <input type="number" step="0.1" name="discount" required placeholder="10.0">
                            <label>Kullanım Limiti:</label>
                            <input type="number" name="uses" value="100" required>
                            <button type="submit" style="background: #10b981; margin-top: 15px;">Kuponu Kaydet & Botu Ateşle</button>
                        </form>
                    </div>
                    <div class="table-box" style="margin:0;">
                        <h2 style="margin-top: 0;">📋 Aktif Kuponlar</h2>
                        <div style="max-height: 320px; overflow-y: auto;">
                            <table>
                                <tr><th>ID</th><th>Kod</th><th>İndirim</th><th>Limit</th><th>Tarih</th></tr>
                                {c_table if c_table else "<tr><td colspan='5' style='text-align:center;'>Kupon bulunmuyor.</td></tr>"}
                            </table>
                        </div>
                    </div>
                </div>
                """
            elif tab == "users":
                cursor.execute("""
                    SELECT u.user_id, u.username, u.language, u.is_banned, u.balance,
                           COUNT(o.id) as total_orders, 
                           COALESCE(SUM(o.final_price), 0.0) as total_spent
                    FROM users u
                    LEFT JOIN orders o ON u.user_id = o.user_id AND o.status IN ('completed', 'received')
                    GROUP BY u.user_id
                    ORDER BY total_spent DESC
                """)
                users_list = cursor.fetchall()
                rows = ""
                for u in users_list:
                    uid, uname, u_lang, is_b, u_bal, t_orders, t_spent = u
                    username_str = f"@{uname}" if uname else "N/A"
                    status_badge = "<span style='color:#ef4444; font-weight:bold;'>BANNED</span>" if is_b == 1 else "<span style='color:#10b981; font-weight:bold;'>ACTIVE</span>"
                    
                    balance_form = f"""
                    <form action="/admin-update-balance" method="POST" style="margin:0; display:flex; gap:8px; align-items:center;">
                        <input type="hidden" name="user_id" value="{uid}">
                        <input type="number" step="0.1" name="new_balance" value="{u_bal}" style="width:110px; margin:0; padding:8px; font-size:13px; font-weight:bold; color:#38bdf8; background:#090d16; border:1px solid #38bdf8; border-radius:6px;">
                        <button type="submit" style="background:#2563eb; padding:8px 12px; font-size:12px; width:auto; border-radius:6px;">Düzenle</button>
                    </form>
                    """
                    ban_btn = f"""
                    <form action="/admin-ban" method="POST" style="margin:0; display:inline;">
                        <input type="hidden" name="user_id" value="{uid}">
                        <input type="hidden" name="action" value="{'unban' if is_b == 1 else 'ban'}">
                        <button type="submit" style="background:{'#10b981' if is_b == 1 else '#ef4444'}; padding:6px 12px; font-size:12px; width:auto; border-radius:6px;">
                            {'Unban' if is_b == 1 else 'Ban'}
                        </button>
                    </form>
                    """
                    rows += f"<tr style='background: var(--card-bg-inner);'><td><b>{uid}</b></td><td>{username_str}</td><td>{u_lang.upper()}</td><td style='padding: 10px;'>{balance_form}</td><td><b>{t_orders} Adet</b></td><td><b>{t_spent} USDT</b></td><td>{status_badge}</td><td>{ban_btn}</td></tr>"

                content_html = f"""
                <div class="table-box" style="border: 1px solid #38bdf8;">
                    <h2 style="color: #38bdf8; margin-top: 0;">👥 Müşteri CRM & Bakiye Yönetimi</h2>
                    <table>
                        <tr><th>User ID</th><th>Username</th><th>Lang</th><th>Güncel Bakiye (USDT)</th><th>Toplam Sipariş</th><th>Toplam Harcama</th><th>Status</th><th>Action</th></tr>
                        {rows if rows else "<tr><td colspan='8' style='text-align:center;'>No users registered yet.</td></tr>"}
                    </table>
                </div>
                """
            elif tab == "active":
                cursor.execute("""
                    SELECT orders.id, users.username, drops.title, orders.final_price, orders.status, orders.created_at 
                    FROM orders 
                    JOIN drops ON orders.drop_id = drops.id 
                    LEFT JOIN users ON orders.user_id = users.user_id
                    WHERE orders.status IN ('completed', 'received')
                    ORDER BY orders.id DESC
                """)
                orders = cursor.fetchall()
                rows = ""
                for o in orders:
                    o_id, uname, title, f_price, status, date = o
                    username_str = f"@{uname}" if uname else "Bulunmuyor"
                    status_badge = "🟢 Teslim Alındı" if status == 'received' else "🔵 Ödendi / Bekliyor"
                    rows += f"<tr><td>#{o_id} (WEE-{o_id})</td><td>{username_str}</td><td>{title}</td><td>{f_price} USDT</td><td>{status_badge}</td><td>{date}</td></tr>"
                
                content_html = f"""
                <div class="table-box">
                    <h2>🟢 Aktif / Tamamlanan & Teslim Alınan Satışlar</h2>
                    <table>
                        <tr><th>Sipariş Kodu</th><th>Kullanıcı Adı</th><th>Ürün</th><th>Tutar</th><th>Durum</th><th>Tarih</th></tr>
                        {rows if rows else "<tr><td colspan='6' style='text-align:center;'>Henüz tamamlanan sipariş yok.</td></tr>"}
                    </table>
                </div>
                """
            elif tab == "pending":
                cursor.execute("""
                    SELECT orders.id, users.username, drops.title, orders.final_price, orders.created_at 
                    FROM orders 
                    JOIN drops ON orders.drop_id = drops.id 
                    LEFT JOIN users ON orders.user_id = users.user_id
                    WHERE orders.status = 'pending'
                    ORDER BY orders.id DESC
                """)
                pending_orders = cursor.fetchall()
                rows = ""
                for o in pending_orders:
                    o_id, uname, title, f_price, date = o
                    username_str = f"@{uname}" if uname else "Bulunmuyor"
                    rows += f"""
                    <tr>
                        <td>#{o_id}</td>
                        <td>{username_str}</td>
                        <td>{title}</td>
                        <td>{f_price} USDT</td>
                        <td>{date}</td>
                        <td>
                            <form action="/admin-approve" method="POST" style="margin:0;">
                                <input type="hidden" name="order_id" value="{o_id}">
                                <button type="submit" style="background:#10b981; padding:6px 12px; font-size:12px; width:auto;">Zorla Onayla</button>
                            </form>
                        </td>
                    </tr>
                    """
                content_html = f"""
                <div class="table-box">
                    <h2>⏳ Bekleyen Siparişler (Manuel Onay)</h2>
                    <table>
                        <tr><th>ID</th><th>Kullanıcı</th><th>Ürün</th><th>Tutar</th><th>Tarih</th><th>İşlem</th></tr>
                        {rows if rows else "<tr><td colspan='6' style='text-align:center;'>Bekleyen sipariş bulunmuyor.</td></tr>"}
                    </table>
                </div>
                """
            elif tab == "passive":
                cursor.execute("SELECT id, title, price, stock, category, description, lat, lon FROM drops WHERE is_sold = 0")
                drops = cursor.fetchall()
                rows = ""
                for d in drops:
                    d_id, title, price, stock, cat, desc, lat, lon = d
                    rows += f"""
                    <tr>
                        <td>#{d_id}</td>
                        <td>{title}</td>
                        <td>{cat or 'Genel'}</td>
                        <td>{price} USDT</td>
                        <td>{stock} Adet</td>
                        <td>
                            <a href="/admin-edit?id={d_id}" class="action-btn edit-btn">Düzenle</a>
                        </td>
                    </tr>
                    """
                content_html = f"""
                <div class="table-box">
                    <h2>📦 Pasif / Stoktaki Ürünler</h2>
                    <table>
                        <tr><th>Ürün No (ID)</th><th>Başlık</th><th>Bölge/Kategori</th><th>Fiyat</th><th>Stok</th><th>İşlem</th></tr>
                        {rows if rows else "<tr><td colspan='6' style='text-align:center;'>Stokta ürün bulunmuyor.</td></tr>"}
                    </table>
                </div>
                """
            elif tab == "add":
                content_html = """
                <div class="grid-2" style="grid-template-columns: 1fr 1fr; gap: 20px;">
                    <div class="form-box" style="margin:0;">
                        <h2 style="color: #38bdf8; margin-top: 0;">➕ Tekli Ürün Ekle</h2>
                        <form action="/admin-add" method="POST" id="addForm">
                            <label>Ürün Başlığı:</label>
                            <input type="text" name="title" required placeholder="Örn: Amnesia Haze">
                            <label>Semt / İlçe:</label>
                            <input type="text" name="category" required placeholder="Kartal">
                            <label>Fiyat (USDT):</label>
                            <input type="number" step="0.1" name="price" required placeholder="65">
                            <label>Stok Adedi:</label>
                            <input type="number" name="count" id="countInput" value="1" min="1" max="30" required onchange="generateFields()">
                            <div id="dynamicFields"></div>
                            <button type="submit" style="margin-top: 20px;">Stoğa Ekle</button>
                        </form>
                    </div>
                    <div class="form-box" style="margin:0; border: 1px solid #10b981;">
                        <h2 style="color: #10b981; margin-top: 0;">📂 Excel / CSV ile Toplu Ürün Yükleme</h2>
                        <form action="/admin-bulk-add" method="POST">
                            <label>Toplu Veri (Her satır bir ürün):</label>
                            <textarea name="bulk_data" rows="8" required placeholder="Amnesia, Kartal, 65, 1, 40.8885, 29.1856, https://..., Açıklama..."></textarea>
                            <button type="submit" style="background: #10b981; margin-top: 15px;">📥 Toplu Yüklemeyi Başlat</button>
                        </form>
                    </div>
                </div>
                <script>
                    function generateFields() {
                        const count = document.getElementById('countInput').value;
                        const container = document.getElementById('dynamicFields');
                        container.innerHTML = '';
                        for (let i = 1; i <= count; i++) {
                            container.innerHTML += `
                                <div style="background: var(--card-bg-inner); padding: 15px; border-radius: 8px; margin-top: 15px; border: 1px solid var(--border-color);">
                                    <h4 style="color: #38bdf8; margin-top: 0;">📍 Ürün / Konum #${i} Detayları</h4>
                                    <label style="color: #38bdf8; font-size: 13px;">Koordinat (Örn: 40.8885, 29.1856):</label>
                                    <input type="text" name="coords_${i}" placeholder="40.8885, 29.1856" style="margin:4px 0 10px 0; padding:10px; font-size:14px;" required>
                                    <label>Fotoğraf URL'si:</label>
                                    <input type="text" name="photo_${i}" placeholder="https://...">
                                    <label>Açıklama / İpucu Notu:</label>
                                    <textarea name="description_${i}" rows="2" required placeholder="Saksının içinde..."></textarea>
                                </div>
                            `;
                        }
                    }
                    window.onload = generateFields;
                </script>
                """

            edit_form_html = ""
            if tab == "edit":
                edit_id = query_params.get("id", ["0"])[0]
                cursor.execute("SELECT title, price, stock, category, photo_ids, description, lat, lon FROM drops WHERE id = ?", (edit_id,))
                drop_data = cursor.fetchone()
                if drop_data:
                    e_title, e_price, e_stock, e_cat, e_photo, e_desc, e_lat, e_lon = drop_data
                    combined_coord = f"{e_lat}, {e_lon}" if e_lat and e_lon else ""
                    edit_form_html = f"""
                    <div class="form-box" style="border: 2px solid #38bdf8; margin-bottom: 30px;">
                        <h2>✏️ Ürün Düzenle (Ürün No: #{edit_id})</h2>
                        <form action="/admin-update" method="POST">
                            <input type="hidden" name="id" value="{edit_id}">
                            <label>Ürün Başlığı:</label>
                            <input type="text" name="title" value="{e_title}" required>
                            <label>Semt / İlçe:</label>
                            <input type="text" name="category" value="{e_cat or 'Genel'}" required>
                            <label>Fiyat (USDT):</label>
                            <input type="number" step="0.1" name="price" value="{e_price}" required>
                            <label>Stok Adedi:</label>
                            <input type="number" name="stock" value="{e_stock}" required>
                            <label style="color: #38bdf8; font-size: 13px;">Koordinat:</label>
                            <input type="text" name="coords" value="{combined_coord}" placeholder="40.8885, 29.1856" required>
                            <label>Fotoğraf URL'si:</label>
                            <input type="text" name="photo" value="{e_photo}">
                            <label>Açıklama:</label>
                            <textarea name="description" rows="3" required>{e_desc}</textarea>
                            <button type="submit" style="background: #10b981; margin-top: 15px;">Güncellemeyi Kaydet</button>
                        </form>
                    </div>
                    """

            cursor.execute("SELECT MAX(id) FROM support_messages")
            max_s_id = cursor.fetchone()[0] or 0
            conn.close()

            dashboard_html = f"""
            <!DOCTYPE html>
            <html lang="tr">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Weed Istanbul Yönetim Paneli</title>
                <style>
                    :root {{
                        --bg-color: #090d16;
                        --text-color: #f8fafc;
                        --sidebar-bg: #111827;
                        --sidebar-hover: #1e293b;
                        --card-bg: #111827;
                        --card-bg-inner: #090d16;
                        --border-color: #1f2937;
                        --input-bg: #090d16;
                        --text-muted: #6b7280;
                    }}
                    body {{ background-color: var(--bg-color); color: var(--text-color); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; display: flex; min-height: 100vh; }}
                    .sidebar {{ width: 260px; background: var(--sidebar-bg); border-right: 1px solid var(--border-color); display: flex; flex-direction: column; padding: 25px 18px; box-sizing: border-box; flex-shrink: 0; }}
                    .sidebar .brand {{ font-size: 20px; font-weight: 800; color: #38bdf8; text-align: center; margin-bottom: 20px; }}
                    .christmas-banner {{ background: linear-gradient(135deg, #ef4444, #10b981); color: white; padding: 8px; border-radius: 8px; text-align: center; font-size: 11px; font-weight: bold; margin-bottom: 20px; }}
                    .sidebar a {{ background: transparent; color: var(--text-muted); padding: 12px 16px; border-radius: 10px; text-decoration: none; font-weight: 600; font-size: 14px; margin-bottom: 6px; display: block; border: 1px solid transparent; }}
                    .sidebar a.active, .sidebar a:hover {{ background: var(--sidebar-hover); color: #38bdf8; border-color: var(--border-color); }}
                    .logout-link {{ background: #ef4444 !important; color: white !important; margin-top: auto; text-align: center; }}
                    .main-content {{ flex: 1; padding: 35px; box-sizing: border-box; overflow-y: auto; max-width: 1200px; }}
                    .header-title {{ color: var(--text-color); font-size: 26px; font-weight: 700; margin-top: 0; margin-bottom: 30px; border-bottom: 1px solid var(--border-color); padding-bottom: 15px; display: flex; justify-content: space-between; align-items: center; }}
                    .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin-bottom: 30px; }}
                    .card {{ background: var(--card-bg); padding: 22px; border-radius: 14px; border: 1px solid var(--border-color); text-align: center; }}
                    .card h3 {{ margin: 0 0 10px 0; color: var(--text-muted); font-size: 13px; font-weight: 700; }}
                    .card p {{ margin: 0; font-size: 26px; font-weight: 800; color: #38bdf8; }}
                    .grid-2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }}
                    .form-box, .table-box {{ background: var(--card-bg); padding: 25px; border-radius: 14px; border: 1px solid var(--border-color); margin-bottom: 30px; }}
                    input, textarea {{ width: 100%; padding: 12px; margin: 8px 0 16px 0; background: var(--input-bg); border: 1px solid var(--border-color); border-radius: 8px; color: var(--text-color); box-sizing: border-box; font-size: 14px; }}
                    button {{ background: #2563eb; color: white; padding: 12px 20px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%; font-size: 14px; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                    th, td {{ padding: 12px 14px; text-align: left; border-bottom: 1px solid var(--border-color); font-size: 14px; }}
                    th {{ color: var(--text-muted); font-weight: 700; font-size: 12px; text-transform: uppercase; }}
                    .action-btn {{ padding: 6px 12px; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: bold; }}
                    .edit-btn {{ background: #d97706; color: white; }}
                </style>
            </head>
            <body>
                <div class="sidebar">
                    <div class="brand">🌿 Weed Istanbul</div>
                    <div class="christmas-banner">🎄 Yönetim Paneli</div>
                    <a href="/admin-web?tab=home" class="{"active" if tab == "home" else ""}">🏠 Home & Harita</a>
                    <a href="/admin-web?tab=support" class="{"active" if tab == "support" else ""}">💬 Canlı Destek</a>
                    <a href="/admin-web?tab=broadcast" class="{"active" if tab == "broadcast" else ""}">📢 Toplu Duyuru</a>
                    <a href="/admin-web?tab=promo5g" class="{"active" if tab == "promo5g" else ""}">🎁 5 Alana 1 Hediye</a>
                    <a href="/admin-web?tab=coupons" class="{"active" if tab == "coupons" else ""}">🎟️ Kupon Yönetimi</a>
                    <a href="/admin-web?tab=active" class="{"active" if tab == "active" else ""}">🟢 Active Orders</a>
                    <a href="/admin-web?tab=pending" class="{"active" if tab == "pending" else ""}">⏳ Pending</a>
                    <a href="/admin-web?tab=passive" class="{"active" if tab in ["passive", "edit"] else ""}">📦 Passive Drops</a>
                    <a href="/admin-web?tab=add" class="{"active" if tab == "add" else ""}">➕ Add Drop / Excel</a>
                    <a href="/admin-web?tab=users" class="{"active" if tab == "users" else ""}">👥 Customer CRM</a>
                    <a href="/admin-logout" class="logout-link">🚪 Logout</a>
                </div>
                <div class="main-content">
                    <div class="header-title"><span>👑 Management System</span></div>
                    {edit_form_html}
                    {content_html}
                </div>
            </body>
            </html>
            """
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(dashboard_html.encode("utf-8"))
            return

        if parsed_path.path == "/admin-edit":
            if not is_logged_in:
                self.send_login_page()
                return
            edit_id = query_params.get("id", ["0"])[0]
            self.send_response(303)
            self.send_header('Location', f'/admin-web?tab=edit&id={edit_id}')
            self.end_headers()
            return

        if parsed_path.path == "/admin-logout":
            self.send_response(303)
            self.send_header('Set-Cookie', 'admin_auth=false; Path=/; Max-Age=0')
            self.send_header('Location', '/admin-web')
            self.end_headers()
            return

        if parsed_path.path.startswith("/drop/"):
            try:
                order_id = int(parsed_path.path.split("/")[-1])
                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT orders.status, drops.title, drops.lat, drops.lon, drops.photo_ids, drops.description 
                    FROM orders 
                    JOIN drops ON orders.drop_id = drops.id 
                    WHERE orders.id = ?
                """, (order_id,))
                row = cursor.fetchone()
                conn.close()

                if not row:
                    self.send_html_error("Ürün veya sipariş bulunamadı.")
                    return

                status, title, lat, lon, photo_url, description = row
                if status not in ['completed', 'received']:
                    self.send_html_error("Bu bağlantı geçerli değil veya süresi dolmuş.")
                    return

                location_url = f"https://www.google.com/maps?q={lat},{lon}"
                photo_tag = f'<img src="{photo_url}" style="width:100%; max-height:260px; object-fit:cover; border-radius:10px; margin-bottom:15px;" />' if photo_url else ''

                received_section = ""
                if status == 'received':
                    received_section = '<div style="background: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; color: #10b981; padding: 10px; border-radius: 8px; font-weight: bold; margin-top: 15px;">✅ Bu ürün başarıyla teslim alındı olarak işaretlendi.</div>'
                else:
                    received_section = f"""
                    <form action="/mark-received/{order_id}" method="POST" style="margin-top: 15px;">
                        <button type="submit" style="background: #10b981; color: white; padding: 12px; border-radius: 8px; border: none; font-weight: bold; cursor: pointer; width: 100%;">✅ Ürünü Teslim Aldım (Onayla)</button>
                    </form>
                    """

                html_content = f"""
                <!DOCTYPE html>
                <html lang="tr">
                <head><meta charset="UTF-8"><title>Secure Delivery - #{order_id}</title>
                <style>
                    body {{ background-color: #090d16; color: #f8fafc; font-family: sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }}
                    .card {{ background: #111827; padding: 25px; border-radius: 16px; width: 100%; max-width: 420px; text-align: center; border: 1px solid #1f2937; }}
                    h2 {{ color: #38bdf8; margin-top: 0; }}
                    .info {{ background: #090d16; padding: 15px; border-radius: 8px; margin: 15px 0; text-align: left; word-break: break-all; font-size: 14px; border: 1px solid #374151; }}
                    .btn {{ display: block; background: #2563eb; color: white; padding: 12px; border-radius: 8px; text-decoration: none; font-weight: bold; margin-top: 15px; }}
                </style>
                </head>
                <body>
                    <div class="card">
                        <h2>🔒 Secure Delivery</h2>
                        <p><b>Product:</b> {title}</p>
                        {photo_tag}
                        <div class="info">
                            <p><b>📍 Location:</b> <a href="{location_url}" target="_blank" style="color: #38bdf8;">Click to Open in Maps</a></p>
                            <p><b>📝 Note:</b> {description}</p>
                        </div>
                        <a href="{location_url}" class="btn" target="_blank">Open Google Maps</a>
                        {received_section}
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
        elif parsed_path.path.startswith("/mark-received/"):
            try:
                order_id = int(parsed_path.path.split("/")[-1])
                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("UPDATE orders SET status = 'received' WHERE id = ? AND status = 'completed'", (order_id,))
                conn.commit()
                conn.close()
                log_panel_event(f"✅ Sipariş #{order_id} teslim alındı olarak onaylandı.", "success")
                
                self.send_response(303)
                self.send_header('Location', f'/drop/{order_id}')
                self.end_headers()
            except Exception:
                self.send_html_error("İşlem gerçekleştirilemedi.")
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed_path = urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        params = parse_qs(post_data)

        if parsed_path.path == "/api/miniapp-chat-send":
            uid = int(params.get("user_id", ["0"])[0])
            msg = params.get("message", [""])[0].strip()
            if uid and msg:
                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO support_messages (user_id, sender, message) VALUES (?, 'user', ?)", (uid, msg))
                conn.commit()
                conn.close()
                log_panel_event(f"💬 Mini App Canlı Destek Mesajı (ID: {uid})", "info")
            
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(b'{"success": true}')
            return

        if parsed_path.path == "/admin-login":
            username = params.get("username", [""])[0]
            password = params.get("password", [""])[0]

            if username == ADMIN_WEB_USERNAME and password == ADMIN_WEB_PASSWORD:
                self.send_response(303)
                self.send_header('Set-Cookie', 'admin_auth=true; Path=/; HttpOnly')
                self.send_header('Location', '/admin-web')
                self.end_headers()
            else:
                self.send_login_page(error="Hatalı kullanıcı adı veya şifre!")
            return

        cookies_str = self.headers.get('Cookie', '')
        if 'admin_auth=true' not in cookies_str:
            self.send_html_error("Yetkisiz Erişim!")
            return

        if parsed_path.path == "/admin-broadcast":
            msg_text = params.get("message", [""])[0].strip()
            if msg_text and main_loop:
                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM users WHERE is_banned = 0")
                all_users = cursor.fetchall()
                conn.close()

                async def send_all():
                    for u in all_users:
                        try:
                            await bot.send_message(u[0], f"📢 **Yönetim Duyurusu:**\n\n{msg_text}", parse_mode="Markdown")
                            await asyncio.sleep(0.05)
                        except:
                            pass

                asyncio.run_coroutine_threadsafe(send_all(), main_loop)
                log_panel_event(f"📢 Toplu duyuru gönderildi.", "success")

            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=broadcast')
            self.end_headers()

        elif parsed_path.path == "/admin-toggle-5g":
            status = params.get("status", ["0"])[0]
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("UPDATE settings SET value = ? WHERE key = 'promo_5g_active'", (status,))
            conn.commit()
            conn.close()
            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=promo5g')
            self.end_headers()

        elif parsed_path.path == "/admin-add-coupon":
            code = params.get("code", [""])[0].strip().upper()
            try:
                discount = float(params.get("discount", [0])[0])
                uses = int(params.get("uses", [100])[0])
            except:
                discount, uses = 5.0, 100

            if code:
                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO coupons (code, discount, uses_left) VALUES (?, ?, ?)", (code, discount, uses))
                conn.commit()
                conn.close()

            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=coupons')
            self.end_headers()

        elif parsed_path.path == "/admin-bulk-add":
            bulk_text = params.get("bulk_data", [""])[0].strip()
            if bulk_text:
                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                for line in bulk_text.split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 4:
                        title, category = parts[0], parts[1]
                        try:
                            price, stock = float(parts[2]), int(parts[3])
                        except:
                            continue
                        lat, lon = get_district_coord(category)
                        desc = parts[6] if len(parts) > 6 else "Güvenli teslimat."
                        cursor.execute("INSERT INTO drops (title, price, description, stock, category, lat, lon) VALUES (?, ?, ?, ?, ?, ?, ?)", (title, price, desc, stock, category, lat, lon))
                conn.commit()
                conn.close()

            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=passive')
            self.end_headers()

        elif parsed_path.path == "/admin-send-support":
            try:
                target_uid = int(params.get("user_id", ["0"])[0])
                msg_text = params.get("message", [""])[0].strip()
                if target_uid and msg_text:
                    conn = sqlite3.connect("drop_bot.db")
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO support_messages (user_id, sender, message) VALUES (?, 'admin', ?)", (target_uid, msg_text))
                    conn.commit()
                    conn.close()

                    if main_loop:
                        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Sohbeti İptal Et", callback_data="close_support_chat")]])
                        asyncio.run_coroutine_threadsafe(bot.send_message(target_uid, f"💬 **Destek Ekibi:**\n\n{msg_text}", reply_markup=kb), main_loop)
            except Exception as e:
                logging.error(e)

            self.send_response(303)
            self.send_header('Location', f'/admin-web?tab=support&user_id={params.get("user_id", ["0"])[0]}')
            self.end_headers()

        elif parsed_path.path == "/admin-close-support":
            try:
                target_uid = int(params.get("user_id", ["0"])[0])
                if target_uid:
                    conn = sqlite3.connect("drop_bot.db")
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM support_messages WHERE user_id = ?", (target_uid,))
                    conn.commit()
                    conn.close()

                    if main_loop:
                        asyncio.run_coroutine_threadsafe(bot.send_message(target_uid, "🔒 Canlı destek oturumu yönetici tarafından sonlandırıldı."), main_loop)
            except Exception as e:
                logging.error(e)

            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=support')
            self.end_headers()

        elif parsed_path.path == "/admin-ban":
            target_uid = params.get("user_id", ["0"])[0]
            action = params.get("action", ["ban"])[0]
            is_b = 1 if action == "ban" else 0

            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (is_b, target_uid))
            conn.commit()
            conn.close()
            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=users')
            self.end_headers()

        elif parsed_path.path == "/admin-update-balance":
            target_uid = params.get("user_id", ["0"])[0]
            try:
                new_bal = float(params.get("new_balance", [0.0])[0])
            except:
                new_bal = 0.0

            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_bal, target_uid))
            conn.commit()
            conn.close()
            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=users')
            self.end_headers()

        elif parsed_path.path == "/admin-add":
            title = params.get("title", [""])[0]
            category = params.get("category", ["Genel"])[0]
            try:
                price = float(params.get("price", [0])[0])
                count = int(params.get("count", [1])[0])
            except:
                price, count = 0.0, 1

            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            for i in range(1, count + 1):
                photo = params.get(f"photo_{i}", [""])[0]
                desc = params.get(f"description_{i}", [""])[0]
                coord_raw = params.get(f"coords_{i}", ["0.0, 0.0"])[0]
                lat, lon = get_district_coord(category)
                try:
                    if "," in coord_raw:
                        c_parts = coord_raw.split(",")
                        lat, lon = float(c_parts[0].strip()), float(c_parts[1].strip())
                except:
                    pass

                if desc:
                    cursor.execute("INSERT INTO drops (title, price, photo_ids, description, stock, category, lat, lon) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (title, price, photo, desc, 1, category, lat, lon))
            conn.commit()
            conn.close()
            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=passive')
            self.end_headers()

        elif parsed_path.path == "/admin-update":
            drop_id = params.get("id", ["0"])[0]
            title = params.get("title", [""])[0]
            category = params.get("category", ["Genel"])[0]
            try:
                price = float(params.get("price", [0])[0])
                stock = int(params.get("stock", [1])[0])
            except:
                price, stock = 0.0, 1

            coord_raw = params.get("coords", ["0.0, 0.0"])[0]
            lat, lon = get_district_coord(category)
            try:
                if "," in coord_raw:
                    c_parts = coord_raw.split(",")
                    lat, lon = float(c_parts[0].strip()), float(c_parts[1].strip())
            except:
                pass

            photo = params.get("photo", [""])[0]
            description = params.get("description", [""])[0]

            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("UPDATE drops SET title = ?, price = ?, stock = ?, category = ?, photo_ids = ?, description = ?, lat = ?, lon = ? WHERE id = ?", (title, price, stock, category, photo, description, lat, lon, drop_id))
            conn.commit()
            conn.close()
            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=passive')
            self.end_headers()

        elif parsed_path.path == "/admin-approve":
            order_id = params.get("order_id", ["0"])[0]
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT orders.user_id, drops.id, drops.stock, orders.status, drops.title, orders.final_price, drops.category 
                FROM orders 
                JOIN drops ON orders.drop_id = drops.id 
                WHERE orders.id = ?
            """, (order_id,))
            row = cursor.fetchone()
            if row:
                u_id, d_id, stock, status, t_title, f_price, t_cat = row
                if status == 'pending':
                    new_stock = stock - 1
                    if new_stock <= 0:
                        cursor.execute("UPDATE drops SET stock = 0, is_sold = 1 WHERE id = ?", (d_id,))
                    else:
                        cursor.execute("UPDATE drops SET stock = ? WHERE id = ?", (new_stock, d_id))
                    cursor.execute("UPDATE orders SET status = 'completed' WHERE id = ?", (order_id,))
                    conn.commit()
                    conn.close()

                    secure_link = f"{RENDER_EXTERNAL_URL}/drop/{order_id}"
                    u_lang = get_user_lang(u_id)
                    success_text = LANG[u_lang]["success_msg"].format(id=order_id, link=secure_link)

                    if main_loop:
                        asyncio.run_coroutine_threadsafe(bot.send_message(u_id, success_text, parse_mode="Markdown"), main_loop)
            else:
                conn.close()

            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=pending')
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def send_login_page(self, error=""):
        err_html = f'<p style="color: #ef4444; margin-bottom: 15px;">{error}</p>' if error else ''
        login_html = f"""
        <!DOCTYPE html>
        <html lang="tr"><head><meta charset="UTF-8"><title>Admin Giriş</title>
        <style>
            body {{ background-color: #090d16; color: #f8fafc; font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
            .login-card {{ background: #111827; padding: 35px; border-radius: 16px; border: 1px solid #1f2937; width: 100%; max-width: 350px; text-align: center; }}
            input {{ width: 100%; padding: 12px; margin: 10px 0; background: #090d16; border: 1px solid #374151; border-radius: 8px; color: white; box-sizing: border-box; }}
            button {{ background: #2563eb; color: white; padding: 12px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%; margin-top: 10px; }}
        </style>
        </head>
        <body>
            <div class="login-card">
                <h2>🔐 Admin Girişi</h2>
                {err_html}
                <form action="/admin-login" method="POST">
                    <input type="text" name="username" required placeholder="Kullanıcı Adı">
                    <input type="password" name="password" required placeholder="Şifre">
                    <button type="submit">Giriş Yap</button>
                </form>
            </div>
        </body>
        </html>
        """
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(login_html.encode("utf-8"))

    def send_html_error(self, message):
        self.send_response(400)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"<h2>⚠️ {message}</h2>".encode("utf-8"))

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SecureDropHandler)
    server.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

# --- FSM VE BOT KODLARI ---
class AdminPassState(StatesGroup):
    password = State()

class SupportState(StatesGroup):
    message = State()

class PromoState(StatesGroup):
    code = State()

class DepositState(StatesGroup):
    amount = State()

class TrackState(StatesGroup):
    code = State()

dp = Dispatcher(storage=MemoryStorage())

def main_keyboard(lang="tr"):
    t = LANG[lang]
    miniapp_url = f"{RENDER_EXTERNAL_URL}/miniapp"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t["btn_products"]), KeyboardButton(text=t["btn_orders"])],
            [KeyboardButton(text=t["btn_track"]), KeyboardButton(text=t["btn_miniapp"], web_app=WebAppInfo(url=miniapp_url))],
            [KeyboardButton(text=t["btn_wallet"]), KeyboardButton(text=t["btn_faq"])],
            [KeyboardButton(text=t["btn_support"]), KeyboardButton(text=t["btn_lang"])]
        ],
        resize_keyboard=True
    )

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.chat.type != "private":
        return
    user_id = message.from_user.id
    if is_user_banned(user_id):
        await message.answer("❌ Erişiminiz engellenmiştir.")
        return
    
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, message.from_user.username))
    conn.commit()
    conn.close()

    lang = get_user_lang(user_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇹🇷 Türkçe", callback_data="setlang_tr"), InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en")]
    ])
    await message.answer(LANG[lang]["welcome"], reply_markup=kb)

@dp.callback_query(F.data.startswith("setlang_"))
async def set_language(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    new_lang = callback.data.split("_")[1]
    set_user_lang(user_id, new_lang)
    t = LANG[new_lang]
    await callback.answer()
    await callback.message.edit_text(t["lang_set"])
    await callback.message.answer(t["welcome"], reply_markup=main_keyboard(new_lang))

@dp.message(F.text.in_([LANG["tr"]["btn_lang"], LANG["en"]["btn_lang"]]))
async def change_lang_menu(message: types.Message):
    if message.chat.type != "private" or is_user_banned(message.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇹🇷 Türkçe", callback_data="setlang_tr"), InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en")]
    ])
    await message.answer("Lütfen dil seçiniz / Please select language:", reply_markup=kb)

@dp.message(F.text.in_([LANG["tr"]["btn_track"], LANG["en"]["btn_track"]]))
async def track_order_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if message.chat.type != "private" or is_user_banned(user_id):
        return
    lang = get_user_lang(user_id)
    t = LANG[lang]
    await state.set_state(TrackState.code)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t["cancel"], callback_data="cancel_track")]])
    await message.answer(t["track_prompt"], reply_markup=kb)

@dp.callback_query(F.data == "cancel_track")
async def cancel_track(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ İşlem iptal edildi.")

@dp.message(TrackState.code)
async def process_track_code(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if message.chat.type != "private" or is_user_banned(user_id):
        return
    lang = get_user_lang(user_id)
    t = LANG[lang]

    raw_input = message.text.strip().upper().replace("WEE-", "").replace("#", "")
    await state.clear()

    try:
        order_id = int(raw_input)
    except:
        await message.answer("⚠️ Lütfen geçerli bir sipariş kodu girin (Örn: WEE-5)")
        return

    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT orders.status, drops.title, orders.final_price 
        FROM orders 
        JOIN drops ON orders.drop_id = drops.id 
        WHERE orders.id = ? AND orders.user_id = ?
    """, (order_id, user_id))
    row = cursor.fetchone()
    conn.close()

    if not row or row[0] not in ['completed', 'received']:
        await message.answer(t["track_not_found"])
        return

    status, title, price = row
    status_text = "✅ Teslim Alındı" if status == 'received' else "🟢 Bekliyor / Aktif"
    secure_link = f"{RENDER_EXTERNAL_URL}/drop/{order_id}"
    res_msg = t["track_result"].format(id=order_id, title=title, price=price, status_text=status_text, link=secure_link)
    await message.answer(res_msg, parse_mode="Markdown")

@dp.message(F.text.in_([LANG["tr"]["btn_wallet"], LANG["en"]["btn_wallet"]]))
async def wallet_menu(message: types.Message):
    user_id = message.from_user.id
    if message.chat.type != "private" or is_user_banned(user_id):
        return
    lang = get_user_lang(user_id)
    t = LANG[lang]
    bal = get_user_balance(user_id)

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t["deposit_btn"], callback_data="start_deposit")]])
    await message.answer(t["wallet_menu_text"].format(balance=bal), reply_markup=kb)

@dp.callback_query(F.data == "start_deposit")
async def start_deposit(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if is_user_banned(user_id):
        return
    lang = get_user_lang(user_id)
    t = LANG[lang]
    await state.set_state(DepositState.amount)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t["cancel"], callback_data="cancel_deposit")]])
    await callback.message.edit_text(t["ask_deposit_amount"], reply_markup=kb)

@dp.callback_query(F.data == "cancel_deposit")
async def cancel_deposit(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ İşlem iptal edildi.")

@dp.message(DepositState.amount)
async def process_deposit_amount(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if message.chat.type != "private" or is_user_banned(user_id):
        return
    lang = get_user_lang(user_id)
    t = LANG[lang]

    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError()
    except:
        await message.answer("⚠️ Lütfen geçerli bir rakam girin (Örn: 25)")
        return

    await state.clear()
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO deposits (user_id, amount, status) VALUES (?, ?, 'pending')", (user_id, amount))
    deposit_id = cursor.lastrowid
    conn.commit()
    conn.close()

    msg = t["deposit_invoice"].format(id=deposit_id, amount=amount, wallet=CRYPTO_WALLET)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t["deposit_check_btn"], callback_data=f"autodeposit_{deposit_id}_{amount}")]])
    await message.answer(msg, reply_markup=kb)

@dp.callback_query(F.data.startswith("autodeposit_"))
async def check_blockchain_deposit(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if is_user_banned(user_id):
        return
    lang = get_user_lang(user_id)
    t = LANG[lang]

    parts = callback.data.split("_")
    deposit_id, target_amount = int(parts[1]), float(parts[2])

    await callback.answer(t["scan"], show_alert=True)
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT status, created_at FROM deposits WHERE id = ? AND user_id = ?", (deposit_id, user_id))
    dep = cursor.fetchone()
    if not dep:
        await callback.answer(t["not_found"], show_alert=True)
        conn.close()
        return
    status, created_at_str = dep
    if status == 'completed':
        await callback.answer(t["already_approved"], show_alert=True)
        conn.close()
        return
    if datetime.now() - datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S") > timedelta(minutes=15):
        cursor.execute("UPDATE deposits SET status = 'expired' WHERE id = ?", (deposit_id,))
        conn.commit()
        conn.close()
        await callback.message.edit_text(t["time_out"])
        return

    api_url = f"https://api.trongrid.io/v1/accounts/{CRYPTO_WALLET}/trc20-transfers?contract_address={USDT_CONTRACT}&limit=15"
    verified = False
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status == 200:
                    res_json = await response.json()
                    for tx in res_json.get("data", []):
                        if tx.get("to") == CRYPTO_WALLET and int(tx.get("value", 0)) >= int(target_amount * 1000000):
                            verified = True
                            break
    except Exception as e:
        logging.error(e)

    if verified:
        cursor.execute("UPDATE deposits SET status = 'completed' WHERE id = ?", (deposit_id,))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (target_amount, user_id))
        conn.commit()
        new_bal = get_user_balance(user_id)
        conn.close()

        await callback.message.edit_text(t["deposit_success"].format(amount=target_amount, balance=new_bal))
    else:
        conn.close()
        await callback.answer(t["wait_tx"], show_alert=True)

@dp.message(F.text.in_([LANG["tr"]["btn_faq"], LANG["en"]["btn_faq"]]))
async def faq_menu(message: types.Message):
    user_id = message.from_user.id
    if message.chat.type != "private" or is_user_banned(user_id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Ödeme / Payment", callback_data="faq_pay")],
        [InlineKeyboardButton(text="⏱️ Teslimat / Delivery", callback_data="faq_delivery")],
        [InlineKeyboardButton(text="🔒 Gizlilik / Privacy", callback_data="faq_security")]
    ])
    await message.answer("💡 **FAQ / SSS**", reply_markup=kb)

@dp.callback_query(F.data.startswith("faq_"))
async def faq_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if is_user_banned(user_id):
        return
    lang = get_user_lang(user_id)
    action = callback.data.split("_")[1]
    if lang == "tr":
        text = "💳 Cüzdanınıza bakiye yükleyerek ürün alabilirsiniz." if action == "pay" else ("⏱️ Ödeme onaylanınca takip kodunuz ve konum linkiniz verilir." if action == "delivery" else "🔒 Konumlar Telegram'da saklanmaz, web üzerinden tek kullanımlıktır.")
    else:
        text = "💳 You can deposit to your wallet." if action == "pay" else ("⏱️ Tracking code sent upon payment." if action == "delivery" else "🔒 Locations are single-use via web.")
    await callback.answer()
    await callback.message.answer(text)

@dp.message(F.text.in_([LANG["tr"]["btn_support"], LANG["en"]["btn_support"]]))
async def support_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if message.chat.type != "private" or is_user_banned(user_id):
        return
    lang = get_user_lang(user_id)
    t = LANG[lang]
    await state.set_state(SupportState.message)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Sohbeti İptal Et", callback_data="close_support_chat")]])
    await message.answer(t["support_ask"], reply_markup=kb)

@dp.callback_query(F.data == "close_support_chat")
async def close_support_callback(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await state.clear()
    
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM support_messages WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    await callback.answer("Sohbet kapatıldı.", show_alert=True)
    await callback.message.edit_text("🔒 Canlı destek oturumu sonlandırıldı.")

@dp.message(SupportState.message)
async def forward_support_to_panel(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if message.chat.type != "private" or is_user_banned(user_id):
        return
    lang = get_user_lang(user_id)
    t = LANG[lang]
    user_msg = message.text
    username = message.from_user.username or f"User {user_id}"

    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    cursor.execute("INSERT INTO support_messages (user_id, sender, message) VALUES (?, 'user', ?)", (user_id, user_msg))
    conn.commit()
    conn.close()

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Sohbeti İptal Et", callback_data="close_support_chat")]])
    await message.answer(t["support_sent"], reply_markup=kb)

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    if message.chat.type != "private" or not is_admin(message.from_user.id):
        return
    await state.set_state(AdminPassState.password)
    await message.answer("🔐 Yönetim paneline erişmek için admin şifresini girin:")

@dp.message(AdminPassState.password)
async def process_admin_password(message: types.Message, state: FSMContext):
    if message.chat.type != "private":
        return
    entered_pass = message.text.strip()
    if entered_pass == "1881":
        await state.clear()
        web_panel_url = f"{RENDER_EXTERNAL_URL}/admin-web"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Web Paneline Giriş Yap", url=web_panel_url)],
            [InlineKeyboardButton(text="📊 Satış Raporları", callback_data="stats")]
        ])
        await message.answer("✅ Şifre Doğru!\n\n👑 **Gelişmiş Yönetim Paneli**", reply_markup=kb)
    else:
        await state.clear()
        await message.answer("❌ Hatalı şifre!")

@dp.callback_query(F.data == "stats")
async def show_stats(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), SUM(stock) FROM drops WHERE is_sold = 0")
    res = cursor.fetchone()
    cursor.execute("SELECT SUM(final_price) FROM orders WHERE status IN ('completed', 'received')")
    rev_res = cursor.fetchone()[0]
    rev = rev_res if rev_res is not None else 0.0
    conn.close()
    await callback.message.edit_text(f"📊 İstatistikler:\nAktif Stok: {res[1] or 0}\nToplam Ciro: {rev} USDT", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Geri", callback_data="back_admin")]]))

@dp.callback_query(F.data == "back_admin")
async def back_admin(callback: types.CallbackQuery):
    web_panel_url = f"{RENDER_EXTERNAL_URL}/admin-web"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Web Paneline Giriş Yap", url=web_panel_url)],
        [InlineKeyboardButton(text="📊 Satış Raporları", callback_data="stats")]
    ])
    await callback.message.edit_text("👑 **Gelişmiş Yönetim Paneli**", reply_markup=kb)

@dp.message(F.text.in_([LANG["tr"]["btn_products"], LANG["en"]["btn_products"]]))
async def list_categories(message: types.Message):
    user_id = message.from_user.id
    if message.chat.type != "private" or is_user_banned(user_id):
        return
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
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"🏙️ {c_name}", callback_data=f"cat_{c_name}")])
    
    await message.answer(t["select_cat"], reply_markup=kb)

@dp.callback_query(F.data.startswith("cat_"))
async def list_drops_by_category(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if is_user_banned(user_id):
        return
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
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"#{d[0]} - {d[1]} - {d[2]} USDT (Stok: {d[3]})", callback_data=f"buy_{d[0]}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text=t["back_cats"], callback_data="back_cats")])

    await callback.message.edit_text(f"📦 **{cat_name}**:", reply_markup=kb)

@dp.callback_query(F.data == "back_cats")
async def back_to_cats(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if is_user_banned(user_id):
        return
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
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"🏙️ {c_name}", callback_data=f"cat_{c_name}")])
    
    await callback.message.edit_text(t["select_cat"], reply_markup=kb)

@dp.message(F.text.in_([LANG["tr"]["btn_orders"], LANG["en"]["btn_orders"]]))
async def my_orders(message: types.Message):
    user_id = message.from_user.id
    if message.chat.type != "private" or is_user_banned(user_id):
        return
    lang = get_user_lang(user_id)
    t = LANG[lang]

    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT orders.id, drops.title, orders.final_price, orders.status, orders.created_at 
        FROM orders 
        JOIN drops ON orders.drop_id = drops.id 
        WHERE orders.user_id = ?
        ORDER BY orders.id DESC
    """, (user_id,))
    orders = cursor.fetchall()
    conn.close()

    if not orders:
        await message.answer(t["no_orders"])
        return

    text = t["my_orders_title"] + "\n\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for o in orders:
        o_id, title, f_price, status, date = o
        st_str = "✅ Teslim Alındı" if status == 'received' else ("🟢 Aktif (Ödendi)" if status == 'completed' else "⏳ Bekliyor")
        text += t["order_item"].format(id=o_id, title=title, price=f_price, status=st_str, date=date)
        if status in ['completed', 'received']:
            secure_link = f"{RENDER_EXTERNAL_URL}/drop/{o_id}"
            kb.inline_keyboard.append([InlineKeyboardButton(text=t["open_loc"].format(id=o_id), url=secure_link)])

    await message.answer(text, reply_markup=kb if kb.inline_keyboard else None)

@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if is_user_banned(user_id):
        return
    lang = get_user_lang(user_id)
    t = LANG[lang]

    drop_id = int(callback.data.split("_")[1])
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT title, price, stock FROM drops WHERE id = ? AND is_sold = 0 AND stock > 0", (drop_id,))
    drop = cursor.fetchone()
    conn.close()

    if not drop:
        await callback.answer(t["sold_out"], show_alert=True)
        return

    title, price, stock = drop
    bal = get_user_balance(user_id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["pay_balance"].format(price=price), callback_data=f"buybal_{drop_id}")],
        [InlineKeyboardButton(text=t["pay_crypto"], callback_data=f"buycrypto_{drop_id}")]
    ])
    await callback.message.edit_text(t["buy_options"].format(title=title, price=price, balance=bal), reply_markup=kb)

@dp.callback_query(F.data.startswith("buybal_"))
async def process_buy_with_balance(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if is_user_banned(user_id):
        return
    lang = get_user_lang(user_id)
    t = LANG[lang]

    drop_id = int(callback.data.split("_")[1])
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT title, price, stock FROM drops WHERE id = ? AND is_sold = 0 AND stock > 0", (drop_id,))
    drop = cursor.fetchone()

    if not drop:
        await callback.answer(t["sold_out"], show_alert=True)
        conn.close()
        return

    title, price, stock = drop
    bal = get_user_balance(user_id)

    if bal < price:
        await callback.answer(t["insufficient_balance"], show_alert=True)
        conn.close()
        return

    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, user_id))
    new_stock = stock - 1
    if new_stock <= 0:
        cursor.execute("UPDATE drops SET stock = 0, is_sold = 1 WHERE id = ?", (drop_id,))
    else:
        cursor.execute("UPDATE drops SET stock = ? WHERE id = ?", (new_stock, drop_id))

    cursor.execute("INSERT INTO orders (user_id, drop_id, status, final_price) VALUES (?, ?, 'completed', ?)", (user_id, drop_id, price))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    secure_link = f"{RENDER_EXTERNAL_URL}/drop/{order_id}"
    success_text = t["balance_success"].format(id=order_id, price=price, link=secure_link)

    await callback.message.edit_text(success_text, parse_mode="Markdown")

async def main():
    global main_loop
    main_loop = asyncio.get_running_loop()
    asyncio.create_task(auto_backup_task())
    asyncio.create_task(background_payment_worker())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
