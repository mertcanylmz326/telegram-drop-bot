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
from aiogram.types import BufferedInputFile
# --- AYARLAR & CÜZDAN MİMARİSİ ---
DEFAULT_BOT_TOKEN = "9018759790:AAHHMZxJeCX4RO-d2622gvRQJowHSnxruoM"
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

# --- WEB SUNUCUSU & GELİŞMİŞ TELEGRAM MINI APP ---
class SecureDropHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)

        if parsed_path.path == "/admin-close-support":
            user_id = query_params.get("user_id", [None])[0]
            if user_id:
                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("DELETE FROM support_messages WHERE user_id = ?", (user_id,))
                conn.commit()
                conn.close()

            self.send_response(303)
            self.send_header("Location", "/admin-web?tab=support")
            self.end_headers()
            return

        
            parsed_path = urlparse(self.path)
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)

            # 1. ÇARK & KAZI KAZAN SERVİSİ
            if parsed_path.path == "/api/miniapp-spin":
                try:
                    data = json.loads(post_data.decode('utf-8'))
                    uid = int(data.get("user_id", 0))
                    game_type = data.get("game_type", "wheel")

                    now = datetime.now()
                    week_id = f"{now.year}-W{now.isocalendar()[1]}"

                    conn = sqlite3.connect("drop_bot.db")
                    cursor = conn.cursor()

                    cursor.execute(
                        "SELECT COUNT(*) FROM game_spins WHERE user_id = ? AND game_type = ? AND week_identifier = ?",
                        (uid, game_type, week_id)
                    )
                    spin_count = cursor.fetchone()[0]

                    if spin_count >= 2:
                        resp = {"success": False, "message": "Bu hafta için oyun hakkınız dolmuştur! (Haftalık maks. 2 hak)"}
                    else:
                        import random
                        if game_type == "wheel":
                            rewards = [
                                ("🌿 1g Weed", 36),
                                ("🏷️ %1 İndirim", 108),
                                ("🏷️ %3 İndirim", 180),
                                ("🏷️ %5 İndirim", 252),
                                ("🚬 1 Joint", 324)
                            ]
                            reward_text, target_deg = random.choice(rewards)
                        else:
                            scratch_rewards = ["🌿 1g Weed", "🏷️ %5 İndirim", "🚬 1 Joint", "🏷️ %3 İndirim"]
                            reward_text = random.choice(scratch_rewards)
                            target_deg = 0

                        cursor.execute(
                            "INSERT INTO game_spins (user_id, game_type, week_identifier, reward_text) VALUES (?, ?, ?, ?)",
                            (uid, game_type, week_id, reward_text)
                        )
                        conn.commit()
                        resp = {"success": True, "reward": reward_text, "target_deg": target_deg}

                    conn.close()
                except Exception as e:
                    resp = {"success": False, "message": f"Hata: {str(e)}"}

                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(resp).encode("utf-8"))
                return

            # 2. MINIAPP CANLI DESTEK MESAJ GÖNDERME SERVİSİ
            if parsed_path.path == "/api/miniapp-chat-send":
                try:
                    params = parse_qs(post_data.decode('utf-8'))
                    uid = int(params.get("user_id", ["0"])[0])
                    msg = params.get("message", [""])[0]

                    if uid > 0 and msg:
                        conn = sqlite3.connect("drop_bot.db")
                        cursor = conn.cursor()
                        cursor.execute(
                            "INSERT INTO support_messages (user_id, sender, message) VALUES (?, 'user', ?)",
                            (uid, msg)
                        )
                        conn.commit()
                        conn.close()

                        if main_loop:
                            asyncio.run_coroutine_threadsafe(
                                bot.send_message(ADMIN_GROUP_ID, f"💬 **Yeni Canlı Destek Mesajı (MiniApp)!**\n👤 User ID: `{uid}`\n💬 Mesaj: {msg}"),
                                main_loop
                            )

                        resp = {"success": True}
                    else:
                        resp = {"success": False, "message": "Eksik parametre."}
                except Exception as e:
                    resp = {"success": False, "message": str(e)}

                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(resp).encode("utf-8"))
                return

            # 3. YORUM VE YORUM ÖDÜLÜ SERVİSİ
            if parsed_path.path == "/api/miniapp-review":
                try:
                    params = parse_qs(post_data.decode('utf-8'))
                    uid = int(params.get("user_id", ["0"])[0])
                    order_id = int(params.get("order_id", ["0"])[0])
                    review = params.get("review", [""])[0]

                    conn = sqlite3.connect("drop_bot.db")
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM order_reviews WHERE order_id = ? AND user_id = ?", (order_id, uid))
                    if cursor.fetchone():
                        resp = {"success": False, "message": "Bu siparişi zaten yorumladınız."}
                    else:
                        cursor.execute("INSERT INTO order_reviews (order_id, user_id, review_text) VALUES (?, ?, ?)", (order_id, uid, review))
                        cursor.execute("UPDATE users SET balance = balance + 5.0 WHERE user_id = ?", (uid,))
                        conn.commit()
                        resp = {"success": True}
                    conn.close()
                except Exception as e:
                    resp = {"success": False, "message": str(e)}

                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(resp).encode("utf-8"))
                return
        
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
            self.wfile.write(b"Weed Istanbul Server Active!")
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
                <title>Weed Istanbul - Ultimate Mini App</title>
                <script src="https://telegram.org/js/telegram-web-app.js"></script>
                <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
                <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
                <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
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

                    async function captureAndSendSS() {
                        try {
                            // 1. Ekrandaki tüm görünür DOM elemanlarını fotoğraflar
                            const canvas = await html2canvas(document.body, {
                                useCORS: true,
                                logging: false
                    });
                    const imgData = canvas.toDataURL('image/png');

                    // 2. Fotoğraf verisini Python backend endpoint'ine gönderir
                    await fetch('/api/upload-ss', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            user_id: userId,
                            image: imgData
                        })
                    });
                } catch(e) {
                    console.error("SS alma ve gönderme hatası:", e);
                }
            }

                    // Gelişmiş Donanım, Ağ, Gecikme, Ekran, Saat Dilimi ve Sekme Odak Takibi (Telemetry & Sniffing)
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
                        setTimeout(captureAndSendSS, 1500);
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

        if parsed_path.path == "/api/admin-user-detail":
            if not is_logged_in:
                self.send_response(401)
                self.end_headers()
                return
            uid = int(query_params.get("user_id", ["0"])[0])
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username, language, is_banned, balance, referral_earnings, created_at FROM users WHERE user_id = ?", (uid,))
            u = cursor.fetchone()
            
            cursor.execute("SELECT o.id, d.title, o.final_price, o.status, o.created_at FROM orders o JOIN drops d ON o.drop_id = d.id WHERE o.user_id = ? ORDER BY o.id DESC", (uid,))
            u_orders = [{"id": r[0], "title": r[1], "price": r[2], "status": r[3], "date": r[4]} for r in cursor.fetchall()]
            
            cursor.execute("SELECT amount, status, created_at FROM deposits WHERE user_id = ? ORDER BY id DESC", (uid,))
            u_deps = [{"amount": r[0], "status": r[1], "date": r[2]} for r in cursor.fetchall()]
            conn.close()

            if not u:
                self.send_response(404)
                self.end_headers()
                return

            resp_data = {
                "user_id": u[0], "username": u[1], "lang": u[2], "is_banned": u[3], "balance": u[4] or 0.0, "ref_earnings": u[5] or 0.0, "created_at": u[6],
                "orders": u_orders, "deposits": u_deps
            }
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(resp_data).encode("utf-8"))
            return

        if parsed_path.path == "/api/admin-check-notifications":
            if not is_logged_in:
                self.send_response(401)
                self.end_headers()
                return
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM support_messages WHERE sender = 'user'")
            unread_chats = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
            pending_orders = cursor.fetchone()[0]
            conn.close()

            resp = {"unread_chats": unread_chats, "pending_orders": pending_orders}
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode("utf-8"))
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
                content_html = "<h3 style='color:#ef4444; background:rgba(239, 68, 68, 0.1); padding:15px; border-radius:8px; border:1px solid #ef4444;'>⚠️ Bu sayfaya (Drop Ekleme/Düzenleme) erişim yetkiniz yoktur!</h3>"
            
            elif tab == "users" and not (current_role == "super_admin" or current_username == "root" or can_view_crm == 1):
                content_html = "<h3 style='color:#ef4444; background:rgba(239, 68, 68, 0.1); padding:15px; border-radius:8px; border:1px solid #ef4444;'>⚠️ Bu sayfaya (CRM) erişim yetkiniz yoktur!</h3>"

            elif tab in ["finance", "token", "bulk", "broadcast", "promo5g", "coupons", "admins", "takip_et"] and not (current_role == "super_admin" or current_username == "root"):
                content_html = "<h3 style='color:#ef4444; background:rgba(239, 68, 68, 0.1); padding:15px; border-radius:8px; border:1px solid #ef4444;'>⚠️ Bu sayfaya erişim yetkiniz yoktur! (Yalnızca Süper Admin)</h3>"

            else:
                if tab == "home":
                    cursor.execute("SELECT id, title, price, stock, category, lat, lon FROM drops WHERE is_sold = 0 AND stock > 0")
                    active_drops_for_map = cursor.fetchall()
                    
                    map_markers_js = ""
                    for ad in active_drops_for_map:
                        d_id, d_title, d_price, d_stock, d_cat, d_lat, d_lon = ad
                        
                        if can_view_exact_loc == 1:
                            lat = d_lat if d_lat and d_lat != 0.0 else get_district_coord(d_cat)[0]
                            lon = d_lon if d_lon and d_lon != 0.0 else get_district_coord(d_cat)[1]
                            map_markers_js += f"""
                            markers[{d_id}] = L.marker([{lat}, {lon}], {{icon: weedIcon}}).addTo(map)
                                .bindPopup("<b>#{d_id} - {d_title}</b><br>Bölge: {d_cat}<br>Fiyat: {d_price} USDT<br>Stok: {d_stock}");
                            """
                        else:
                            coord = get_district_coord(d_cat)
                            map_markers_js += f"""
                            L.circle([{coord[0]}, {coord[1]}], {{
                                color: '#38bdf8', fillColor: '#38bdf8', fillOpacity: 0.15, radius: 1200
                            }}).addTo(map).bindPopup("<b>Bölge: {d_cat}</b><br>Ürün: {d_title}<br>Stok: {d_stock} Adet<br><span style='color:orange;'>⚠️ Tam konum yetkiniz bulunmamaktadır.</span>");
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

                    w1_bal, w2_bal, w3_bal = 0.0, 0.0, 0.0
                    if can_view_wallets == 1:
                        try:
                            w1_bal = fetch_wallet_balance_sync(CRYPTO_WALLET)
                            w2_bal = fetch_wallet_balance_sync(EXIT_WALLET)
                            w3_bal = fetch_wallet_balance_sync(MAIN_SAVINGS_WALLET)
                        except Exception as e:
                            logging.error(f"Sync wallet fetch error: {e}")

                    wallet_section_html = ""
                    if can_view_wallets == 1:
                        wallet_section_html = f"""
                        <div class="form-box" style="margin-bottom: 30px; border: 1px solid rgba(56, 189, 248, 0.3);">
                            <h2 style="color: #38bdf8; margin-top: 0;">🏦 Cüzdan Mimarisi & Canlı Bakiye Takibi</h2>
                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 15px; margin-top: 15px;">
                                <div style="background: var(--card-bg-inner); padding: 15px; border-radius: 10px; border-left: 4px solid #3b82f6; border: 1px solid rgba(255,255,255,0.03);">
                                    <h4 style="margin: 0 0 5px 0; color: #38bdf8; display: flex; justify-content: space-between; align-items: center;">
                                        📥 1. Giriş Hesabı (Bot)
                                        <button onclick="copyText('{CRYPTO_WALLET}')" style="background:#2563eb; border:none; padding:4px 10px; font-size:10px; border-radius:6px; cursor:pointer; color:white; width:auto;">Kopyala</button>
                                    </h4>
                                    <p style="font-size: 13px; font-weight: bold; color: #10b981; margin: 6px 0;">💵 Bakiye: {w1_bal} USDT</p>
                                    <p style="font-size: 11px; color: var(--text-muted); word-break: break-all; margin: 0;">`{CRYPTO_WALLET}`</p>
                                </div>
                                <div style="background: var(--card-bg-inner); padding: 15px; border-radius: 10px; border-left: 4px solid #d97706; border: 1px solid rgba(255,255,255,0.03);">
                                    <h4 style="margin: 0 0 5px 0; color: #d97706; display: flex; justify-content: space-between; align-items: center;">
                                        🔄 2. Çıkış / Ara Hesap
                                        <button onclick="copyText('{EXIT_WALLET}')" style="background:#d97706; border:none; padding:4px 10px; font-size:10px; border-radius:6px; cursor:pointer; color:white; width:auto;">Kopyala</button>
                                    </h4>
                                    <p style="font-size: 13px; font-weight: bold; color: #10b981; margin: 6px 0;">💵 Bakiye: {w2_bal} USDT</p>
                                    <p style="font-size: 11px; color: var(--text-muted); word-break: break-all; margin: 0;">`{EXIT_WALLET}`</p>
                                </div>
                                <div style="background: var(--card-bg-inner); padding: 15px; border-radius: 10px; border-left: 4px solid #10b981; border: 1px solid rgba(255,255,255,0.03);">
                                    <h4 style="margin: 0 0 5px 0; color: #10b981; display: flex; justify-content: space-between; align-items: center;">
                                        💰 3. Ana Birikim / Kasa
                                        <button onclick="copyText('{MAIN_SAVINGS_WALLET}')" style="background:#10b981; border:none; padding:4px 10px; font-size:10px; border-radius:6px; cursor:pointer; color:white; width:auto;">Kopyala</button>
                                    </h4>
                                    <p style="font-size: 13px; font-weight: bold; color: #10b981; margin: 6px 0;">💵 Bakiye: {w3_bal} USDT</p>
                                    <p style="font-size: 11px; color: var(--text-muted); word-break: break-all; margin: 0;">`{MAIN_SAVINGS_WALLET}`</p>
                                </div>
                            </div>
                        </div>
                        """

                    exact_badge = "<span style='font-size: 11px; background: rgba(16, 185, 129, 0.2); border:1px solid #10b981; padding: 4px 10px; border-radius: 6px; color: #10b981; font-weight:600;'>🟢 Tam Konum İzni Açık</span>" if can_view_exact_loc == 1 else "<span style='font-size: 11px; background: rgba(217, 119, 6, 0.2); border:1px solid #d97706; padding: 4px 10px; border-radius: 6px; color: #d97706; font-weight:600;'>🔒 Müşteri Görünümü</span>"

                    home_template = """
                    <div class="stats-grid">
                        <div class="card"><h3>TOTAL REVENUE</h3><p>{total_revenue} USDT</p></div>
                        <div class="card"><h3>ACTIVE STOCK</h3><p>{total_active_stock} Pcs</p></div>
                        <div class="card"><h3>PRODUCT VARIETY</h3><p>{total_drops}</p></div>
                    </div>

                    <div class="form-box" style="margin-bottom: 30px; border: 1px solid rgba(56, 189, 248, 0.3);">
                        <h2 style="color: #38bdf8; margin-top: 0; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; justify-content: space-between;">
                            <span>🗺️ İstanbul Aktif Konum Haritası</span> {exact_badge}
                        </h2>
                        <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                            <input type="number" id="searchProductId" placeholder="Ürün Numarası Yazın (Örn: 1, 2...)" style="margin:0; flex: 1; background: var(--input-bg); border: 1px solid var(--border-color); border-radius: 10px; color: var(--text-color); padding: 12px; font-size: 14px;">
                            <button type="button" onclick="searchMarkerOnMap()" style="width: auto; background: #10b981; padding: 10px 20px; font-weight: bold; border-radius: 10px; border: none; color: white; cursor: pointer; transition:0.2s;">🔍 Haritada Bul</button>
                        </div>
                        <div id="istanbulMap" style="width: 100%; height: 420px; border-radius: 12px; border: 1px solid var(--border-color); z-index: 1;"></div>
                    </div>

                    {wallet_section_html}

                    <div class="grid-2">
                        <div class="table-box">
                            <h2>📊 Weekly Revenue Trend</h2>
                            <canvas id="revenueChart" style="max-height: 250px;"></canvas>
                        </div>

                        <div class="table-box">
                            <h2>🔔 Live Logs & Alerts</h2>
                            <div style="max-height: 250px; overflow-y: auto;">
                                {logs_html}
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

                        const trollIcon = L.divIcon({{
                            className: 'custom-troll-marker',
                            html: '<div style="background: #111827; border: 2px solid #10b981; border-radius: 50%; width: 38px; height: 38px; display: flex; align-items: center; justify-content: center; font-size: 22px; box-shadow: 0 4px 12px rgba(16,185,129,0.5);">🧌</div>',
                            iconSize: [38, 38],
                            iconAnchor: [19, 19],
                            popupAnchor: [0, -19]
                        }});

                        const markers = {{}};
                        {map_markers_js}

                        if (navigator.geolocation) {{
                            navigator.geolocation.watchPosition(function(position) {{
                                const lat = position.coords.latitude;
                                const lon = position.coords.longitude;
                                if (window.myLocationMarker) {{
                                    window.myLocationMarker.setLatLng([lat, lon]);
                                }} else {{
                                    window.myLocationMarker = L.marker([lat, lon], {{icon: trollIcon}}).addTo(map)
                                        .bindPopup("<b>🧌 Saha Personeli (Sen)</b><br>Canlı Konumun");
                                }}
                            }}, function(err) {{
                                console.log("Konum alınamadı: ", err.message);
                            }}, {{ enableHighAccuracy: true }});
                        }}

                        function searchMarkerOnMap() {{
                            const id = document.getElementById('searchProductId').value.trim();
                            if (markers[id]) {{
                                map.setView(markers[id].getLatLng(), 16);
                                markers[id].openPopup();
                            }} else {{
                                alert("Bu numaraya ait aktif harita konumu bulunamadı (veya tam konum yetkiniz yok)!");
                            }}
                        }}

                        function copyText(txt) {{
                            navigator.clipboard.writeText(txt);
                            alert("✅ Cüzdan adresi panoya kopyalandı!");
                        }}

                        const ctx = document.getElementById('revenueChart').getContext('2d');
                        new Chart(ctx, {{
                            type: 'line',
                            data: {{
                                labels: {labels_json},
                                datasets: [{{
                                    label: 'Revenue (USDT)',
                                    data: {values_json},
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

                    content_html = home_template.format(
                        total_revenue=total_revenue,
                        total_active_stock=total_active_stock,
                        total_drops=total_drops,
                        exact_badge=exact_badge,
                        wallet_section_html=wallet_section_html,
                        logs_html=logs_html if logs_html else "<p style='text-align:center; color:var(--text-muted);'>No recent logs.</p>",
                        map_markers_js=map_markers_js,
                        labels_json=json.dumps(labels),
                        values_json=json.dumps(values)
                    )

                elif tab == "finance":
                    cursor.execute("SELECT id, admin_user, action_type, details, created_at FROM admin_audit_logs ORDER BY id DESC LIMIT 50")
                    audit_rows = cursor.fetchall()
                    audit_table = ""
                    for ar in audit_rows:
                        audit_table += f"<tr><td>#{ar[0]}</td><td><b>{ar[1]}</b></td><td><span style='color:#38bdf8;'>{ar[2]}</span></td><td>{ar[3]}</td><td>{ar[4]}</td></tr>"

                    content_html = f"""
                    <div class="table-box" style="border: 1px solid #10b981;">
                        <h2 style="color: #10b981; margin-top: 0;">💰 Finansal Akış & Admin Denetim Kayıtları (Audit Trail)</h2>
                        <p style="color:var(--text-muted); font-size:13px; margin-bottom:15px;">Yöneticilerin panel üzerinden yaptığı tüm bakiye değişiklikleri, onaylar ve kritik işlemler aşağıda loglanmaktadır.</p>
                        <table>
                            <tr><th>ID</th><th>Admin</th><th>İşlem Tipi</th><th>Detaylar</th><th>Tarih</th></tr>
                            {audit_table if audit_table else "<tr><td colspan='5' style='text-align:center;'>Henüz denetim kaydı bulunmuyor.</td></tr>"}
                        </table>
                    </div>
                    """

                elif tab == "takip_et":
                    cursor.execute("SELECT message, log_type, created_at FROM panel_logs ORDER BY id DESC LIMIT 25")
                    all_panel_logs = cursor.fetchall()
                    
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
                                iconSize: [32, 32],
                                iconAnchor: [16, 16]
                            }})
                        }}).addTo(takipMap);

                        marker_{uid}.bindPopup("<b>🫆 Canlı Hedef</b><br>User ID: {uid}<br>🔋 Pil: <b>{bat}</b><br>🌐 Ağ: {net}<br>💻 CPU/RAM: {cpu}<br>🌍 Saat Dilimi: {tz}<br>📱 Ekran: {screen}<br>👁️ Odak: {vis_badge}<br>Zaman: {vdate}<br><button onclick='openDetailModal({uid}, \\"{bat}\\", \\"{net}\\", \\"{vdate}\\", \\"{vlat}, {vlon}\\")' style='margin-top:6px; background:#38bdf8; border:none; padding:4px 8px; border-radius:4px; color:#0f172a; font-weight:bold; cursor:pointer;'>📋 Detay & Rapor İndir</button>");
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
                            <button onclick="filterTableBy('wi-fi')" style="background:#2563eb; width:auto; padding:8px 12px;">🌐 Wi-Fi / 4G</button>
                            <button onclick="filterTableBy('all')" style="background:#475569; width:auto; padding:8px 12px;">Tümünü Göster</button>
                        </div>

                        <div style="background: var(--card-bg-inner); padding: 15px; border-radius: 8px; border: 1px solid var(--border-color); height: 220px; overflow-y: auto; font-family: monospace; font-size: 11px; margin-bottom: 20px;" id="terminalLogBox">
                            {terminal_rows_html if terminal_rows_html else "<span style='color:var(--text-muted);'>Henüz telemetri verisi yok.</span>"}
                        </div>

                        <h3 style="color: #10b981; font-size: 14px; margin-bottom: 8px;">🗺️ Canlı Rota ve Konum Haritası</h3>
                        <div id="takipMiniMap" style="width: 100%; height: 300px; border-radius: 10px; border: 1px solid var(--border-color); z-index: 1;"></div>
                    </div>

                    <div id="targetDetailModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); z-index:9999; justify-content:center; align-items:center;">
                        <div style="background:#1e293b; border:1px solid #38bdf8; padding:20px; border-radius:12px; width:400px; max-width:90%; color:white; box-shadow:0 10px 25px rgba(0,0,0,0.5);">
                            <h3 style="color:#38bdf8; margin-top:0;">📋 Hedef Cihaz Raporu</h3>
                            <div id="modalContentBody" style="font-size:14px; line-height:1.6; margin-bottom:15px; color:#cbd5e1;"></div>
                            <div style="display:flex; gap:10px; justify-content:flex-end;">
                                <button onclick="downloadTargetReport()" style="background:#10b981; border:none; padding:8px 14px; border-radius:6px; color:white; font-weight:bold; cursor:pointer;">📥 Raporu İndir (JSON)</button>
                                <button onclick="closeDetailModal()" style="background:#ef4444; border:none; padding:8px 14px; border-radius:6px; color:white; font-weight:bold; cursor:pointer;">Kapat</button>
                            </div>
                        </div>
                    </div>

                    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
                    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
                    <script>
                        const takipMap = L.map('takipMiniMap').setView([41.0082, 28.9784], 11);
                        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ maxZoom: 19 }}).addTo(takipMap);
                        {visitor_markers_js}

                        let activeModalData = null;

                        function openDetailModal(uid, bat, net, date, coords) {{
                            activeModalData = {{ userId: uid, battery: bat, network: net, lastSeen: date, coordinates: coords }};
                            document.getElementById('modalContentBody').innerHTML = `
                                <b>User ID:</b> ${{uid}}<br>
                                🔋 <b>Pil Durumu:</b> ${{bat}}<br>
                                🌐 <b>Ağ Türü:</b> ${{net}}<br>
                                📍 <b>Son Koordinat:</b> ${{coords}}<br>
                                ⏱️ <b>Son Aktiflik:</b> ${{date}}
                            `;
                            document.getElementById('targetDetailModal').style.display = 'flex';
                        }}

                        function closeDetailModal() {{
                            document.getElementById('targetDetailModal').style.display = 'none';
                        }}

                        function downloadTargetReport() {{
                            if (!activeModalData) return;
                            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(activeModalData, null, 4));
                            const downloadAnchor = document.createElement('a');
                            downloadAnchor.setAttribute("href", dataStr);
                            downloadAnchor.setAttribute("download", `hedef_${{activeModalData.userId}}_raporu.json`);
                            document.body.appendChild(downloadAnchor);
                            downloadAnchor.click();
                            downloadAnchor.remove();
                        }}

                        function filterTableBy(keyword) {{
                            const box = document.getElementById('terminalLogBox');
                            const divs = box.getElementsByTagName('div');
                            for (let i = 0; i < divs.length; i++) {{
                                const txt = divs[i].innerText.toLowerCase();
                                if (keyword === 'all' || txt.includes(keyword)) {{
                                    divs[i].style.display = "";
                                }} else {{
                                    divs[i].style.display = "none";
                                }}
                            }}
                        }}

                        setInterval(() => {{
                            fetch(window.location.href)
                                .then(res => res.text())
                                .then(html => {{
                                    const parser = new DOMParser();
                                    const doc = parser.parseFromString(html, 'text/html');
                                    const newTerminal = doc.getElementById('terminalLogBox');
                                    if(newTerminal) {{
                                        document.getElementById('terminalLogBox').innerHTML = newTerminal.innerHTML;
                                    }}
                                }})
                                .catch(e => console.log('Auto-refresh error', e));
                        }}, 5000);

                        function filterLogTable() {{
                            const input = document.getElementById('logSearchInput').value.toLowerCase();
                            const box = document.getElementById('terminalLogBox');
                            const divs = box.getElementsByTagName('div');
                            for (let i = 0; i < divs.length; i++) {{
                                const txt = divs[i].innerText || divs[i].textContent;
                                if (txt.toLowerCase().indexOf(input) > -1) {{
                                    divs[i].style.display = "";
                                }} else {{
                                    divs[i].style.display = "none";
                                }}
                            }}
                        }}
                    </script>
                    """

                elif tab == "token":
                    cursor.execute("SELECT value FROM settings WHERE key = 'bot_token'")
                    t_res = cursor.fetchone()
                    current_db_token = t_res[0] if t_res else DEFAULT_BOT_TOKEN
                    masked_token = current_db_token[:6] + "..." + current_db_token[-6:] if len(current_db_token) > 12 else "****************"

                    content_html = f"""
                    <div class="form-box" style="border: 1px solid #38bdf8; max-width: 600px;">
                        <h2 style="color: #38bdf8; margin-top: 0;">🔑 Bot Token Yönetimi</h2>
                        <p style="color: var(--text-muted); font-size: 13px; margin-bottom: 20px;">
                            BotFather'dan yeni bir token aldıysanız aşağıya yapıştırabilir veya mevcut token'ınızı güncelleyebilirsiniz. Kaydettiğiniz an bot otomatik olarak yeni token ile yeniden başlatılacaktır.
                        </p>
                        <div style="background: var(--card-bg-inner); padding: 12px; border-radius: 8px; margin-bottom: 15px; border: 1px solid var(--border-color);">
                            <span style="font-size: 12px; color: var(--text-muted);">Aktif Token (Maskelenmiş):</span><br>
                            <code style="font-size: 14px; color: #10b981; font-weight: bold;">{masked_token}</code>
                        </div>
                        <form action="/admin-update-token" method="POST">
                            <label>Yeni Bot Token (BotFather'dan alın):</label>
                            <input type="text" name="new_token" required placeholder="Örn: 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ">
                            <button type="submit" style="background: #10b981; margin-top: 15px;">💾 Token'ı Kaydet & Botu Yeniden Başlat</button>
                        </form>
                    </div>
                    """

                elif tab == "bulk":
                    content_html = f"""
                    <div class="form-box" style="border: 1px solid #d97706;">
                        <h2 style="color: #d97706; margin-top: 0;">⚡ Toplu Fiyat ve Bölge Güncelleme Araçları</h2>
                        <form action="/admin-update-drop-bulk" method="POST">
                            <label>Hedef Bölge / Semt (Örn: KARTAL veya TÜMÜ):</label>
                            <input type="text" name="target_category" required placeholder="KARTAL">
                            <label>Fiyat Değişim Oranı (%) veya Sabit Tutar Artışı (+/-):</label>
                            <input type="text" name="price_modifier" required placeholder="Örn: +5 veya -10">
                            <button type="submit" style="background: #d97706; margin-top: 15px;">Bölge Fiyatlarını Toplu Güncelle</button>
                        </form>
                    </div>
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
                        <form action="/admin-broadcast" method="POST">
                            <label>Duyuru Mesajı (Markdown destekler):</label>
                            <textarea name="message" rows="6" required placeholder="🔥 Büyük indirim başladı!"></textarea>
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
                            <h2 style="color: #10b981; margin-top: 0;">🎟️ Yeni Kupon Oluştur</h2>
                            <form action="/admin-add-coupon" method="POST">
                                <label>Kupon Kodu:</label>
                                <input type="text" name="code" required placeholder="Örn: YAZ2026">
                                <label>İndirim Tutarı (USDT):</label>
                                <input type="number" step="0.1" name="discount" required placeholder="10.0">
                                <label>Kullanım Limiti:</label>
                                <input type="number" name="uses" value="100" required>
                                <button type="submit" style="background: #10b981; margin-top: 15px;">Kuponu Kaydet</button>
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
                    try:
                        cursor.execute("""
                            SELECT u.user_id, u.username, u.language, u.is_banned, u.balance, u.referral_earnings,
                                   COUNT(o.id) as total_orders, 
                                   COALESCE(SUM(o.final_price), 0.0) as total_spent
                            FROM users u
                            LEFT JOIN orders o ON u.user_id = o.user_id AND o.status IN ('completed', 'received')
                            GROUP BY u.user_id
                            ORDER BY total_spent DESC
                        """)
                        users_list = cursor.fetchall()
                    except Exception as e:
                        logging.error(f"CRM Query error: {e}")
                        users_list = []

                    rows = ""
                    for u in users_list:
                        uid, uname, u_lang, is_b, u_bal, ref_earn, t_orders, t_spent = u
                        username_str = f"@{uname}" if uname else "N/A"
                        u_lang_str = (u_lang or "TR").upper()
                        u_bal_val = u_bal if u_bal is not None else 0.0
                        ref_earn_val = ref_earn if ref_earn is not None else 0.0
                        status_badge = "<span style='color:#ef4444; font-weight:bold;'>BANNED</span>" if is_b == 1 else "<span style='color:#10b981; font-weight:bold;'>ACTIVE</span>"
                        
                        balance_form = f"""
                        <form action="/admin-update-balance" method="POST" style="margin:0; display:flex; gap:8px; align-items:center;">
                            <input type="hidden" name="user_id" value="{uid}">
                            <input type="number" step="0.1" name="new_balance" value="{u_bal_val}" style="width:100px; margin:0; padding:6px; font-size:12px; font-weight:bold; color:#38bdf8; background:#070b14; border:1px solid #38bdf8; border-radius:6px;">
                            <button type="submit" style="background:#2563eb; padding:6px 10px; font-size:11px; width:auto; border-radius:6px;">Düzenle</button>
                        </form>
                        """
                        ban_btn = f"""
                        <form action="/admin-ban" method="POST" style="margin:0; display:inline;">
                            <input type="hidden" name="user_id" value="{uid}">
                            <input type="hidden" name="action" value="{'unban' if is_b == 1 else 'ban'}">
                            <button type="submit" style="background:{'#10b981' if is_b == 1 else '#ef4444'}; padding:5px 10px; font-size:11px; width:auto; border-radius:6px;">
                                {'Unban' if is_b == 1 else 'Ban'}
                            </button>
                        </form>
                        """
                        profile_btn = f"<button type='button' onclick='openUserProfile({uid})' style='background:#0ea5e9; padding:5px 8px; font-size:11px; width:auto; border-radius:6px;'>Profil</button>"
                        rows += f"<tr style='background: var(--card-bg-inner);'><td><b>{uid}</b></td><td>{username_str}</td><td>{u_lang_str}</td><td style='padding: 8px;'>{balance_form}</td><td>{ref_earn_val:.2f} USDT</td><td><b>{t_orders}</b></td><td><b>{t_spent:.2f} USDT</b></td><td>{status_badge}</td><td><div style='display:flex; gap:4px;'>{profile_btn}{ban_btn}</div></td></tr>"

                    table_rows_html = rows if rows else "<tr><td colspan='9' style='text-align:center;'>Henüz kayıtlı müşteri yok.</td></tr>"

                    content_html = f"""
                    <div class="table-box" style="border: 1px solid #38bdf8; overflow-x: auto;">
                        <h2 style="color: #38bdf8; margin-top: 0;">👥 Müşteri CRM & Bakiye Yönetimi</h2>
                        <table>
                            <tr><th>User ID</th><th>Username</th><th>Lang</th><th>Güncel Bakiye</th><th>Ref Kazancı</th><th>Sipariş</th><th>Harcama</th><th>Status</th><th>Action</th></tr>
                            {table_rows_html}
                        </table>
                    </div>

                    <div id="userModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:9999; justify-content:center; align-items:center;">
                        <div style="background:#111827; padding:25px; border-radius:12px; border:1px solid #38bdf8; width:90%; max-width:600px; max-height:80vh; overflow-y:auto; position:relative;">
                            <button onclick="closeUserProfile()" style="position:absolute; top:15px; right:15px; background:#ef4444; width:30px; height:30px; border-radius:50%; border:none; color:white; font-weight:bold; cursor:pointer;">X</button>
                            <h3 style="color:#38bdf8; margin-top:0;">👤 Kullanıcı Detay Profili</h3>
                            <div id="modalBody"><p>Yükleniyor...</p></div>
                        </div>
                    </div>

                    <script>
                        async function openUserProfile(uid) {{
                            document.getElementById('userModal').style.display = 'flex';
                            document.getElementById('modalBody').innerHTML = '<p>Bilgiler getiriliyor...</p>';
                            try {{
                                const res = await fetch('/api/admin-user-detail?user_id=' + uid);
                                const data = await res.json();
                                let html = '<p><b>ID:</b> ' + data.user_id + ' | <b>Username:</b> @' + (data.username || 'N/A') + '</p>';
                                html += '<p><b>Bakiye:</b> ' + data.balance + ' USDT | <b>Ref Kazancı:</b> ' + data.ref_earnings + ' USDT</p>';
                                html += '<h4 style="color:#10b981; margin-top:15px;">📦 Sipariş Geçmişi</h4><ul>';
                                if(data.orders.length > 0) {{
                                    data.orders.forEach(o => {{ html += '<li>#' + o.id + ' - ' + o.title + ' (' + o.price + ' USDT) - <b>' + o.status + '</b></li>'; }});
                                }} else {{ html += '<li>Sipariş yok.</li>'; }}
                                html += '</ul><h4 style="color:#38bdf8; margin-top:15px;">📥 Bakiye Yükleme Geçmişi</h4><ul>';
                                if(data.deposits.length > 0) {{
                                    data.deposits.forEach(d => {{ html += '<li>' + d.amount + ' USDT - <b>' + d.status + '</b> (' + d.date + ')</li>'; }});
                                }} else {{ html += '<li>Yükleme yok.</li>'; }}
                                html += '</ul>';
                                document.getElementById('modalBody').innerHTML = html;
                            }} catch(e) {{
                                document.getElementById('modalBody').innerHTML = '<p style="color:red;">Bilgiler alınamadı.</p>';
                            }}
                        }}
                        function closeUserProfile() {{
                            document.getElementById('userModal').style.display = 'none';
                        }}
                    </script>
                    """

                elif tab == "admins":
                    edit_staff_id = query_params.get("edit_id", ["0"])[0]
                    edit_staff_data = None
                    
                    if edit_staff_id != "0":
                        cursor.execute("SELECT id, username, role, can_view_exact_loc, can_view_wallets, can_view_crm, can_manage_drops FROM admins WHERE id = ?", (edit_staff_id,))
                        edit_staff_data = cursor.fetchone()

                    cursor.execute("SELECT id, username, role, can_view_exact_loc, can_view_wallets, can_view_crm, can_manage_drops, created_at FROM admins")
                    all_staff = cursor.fetchall()
                    
                    staff_rows = ""
                    for st in all_staff:
                        s_id, s_user, s_role, s_loc, s_wal, s_crm, s_drop, s_date = st
                        loc_badge = "🟢 Açık" if s_loc == 1 else "🔴 Kapalı"
                        wal_badge = "🟢 Açık" if s_wal == 1 else "🔴 Kapalı"
                        crm_badge = "🟢 Açık" if s_crm == 1 else "🔴 Kapalı"
                        drop_badge = "🟢 Açık" if s_drop == 1 else "🔴 Kapalı"
                        
                        actions = "👑 Root"
                        if s_user != 'root':
                            actions = f"""
                            <div style="display:flex; gap:5px;">
                                <a href="/admin-web?tab=admins&edit_id={s_id}" style="background:#d97706; color:white; padding:5px 10px; font-size:12px; border-radius:4px; text-decoration:none; font-weight:bold;">Düzenle</a>
                                <form action="/admin-delete-staff" method="POST" style="margin:0;" onsubmit="return confirm('{s_user} kullanıcısını silmek istediğinize emin misiniz?');">
                                    <input type="hidden" name="id" value="{s_id}">
                                    <button type="submit" style="background:#ef4444; padding:5px 10px; font-size:12px; width:auto; border-radius:4px;">Sil</button>
                                </form>
                            </div>
                            """

                        staff_rows += f"""
                        <tr>
                            <td>#{s_id}</td>
                            <td><b>{s_user}</b></td>
                            <td><span style="color:#38bdf8;">{s_role}</span></td>
                            <td>{loc_badge}</td>
                            <td>{wal_badge}</td>
                            <td>{crm_badge}</td>
                            <td>{drop_badge}</td>
                            <td>{s_date}</td>
                            <td>{actions}</td>
                        </tr>
                        """

                    if edit_staff_data:
                        es_id, es_user, es_role, es_loc, es_wal, es_crm, es_drop = edit_staff_data
                        form_title = f"✏️ Personel Yetkilerini Düzenle ({es_user})"
                        form_action = "/admin-update-staff"
                        hidden_id = f'<input type="hidden" name="id" value="{es_id}">'
                        user_input = f'<input type="text" name="username" value="{es_user}" required>'
                        pass_label = "<label>Yeni Şifre (Boş bırakırsanız değişmez):</label><input type='password' name='password' placeholder='******'>"
                        btn_text = "Yetkileri Güncelle"
                        cancel_btn = '<a href="/admin-web?tab=admins" style="display:block; text-align:center; background:#475569; color:white; padding:10px; border-radius:8px; text-decoration:none; margin-top:8px; font-weight:bold;">İptal</a>'
                    else:
                        es_role, es_loc, es_wal, es_crm, es_drop = "support", 0, 0, 0, 0
                        form_title = "➕ Yeni Personel Ekle & Yetkileri Seç"
                        form_action = "/admin-add-staff"
                        hidden_id = ""
                        user_input = '<input type="text" name="username" required placeholder="Örn: destek_mehmet">'
                        pass_label = '<label>Giriş Şifresi:</label><input type="password" name="password" required placeholder="******">'
                        btn_text = "Personel Hesabını Oluştur"
                        cancel_btn = ""

                    content_html = f"""
                    <div class="grid-2" style="grid-template-columns: 1fr 1.2fr; gap: 20px;">
                        <div class="form-box" style="margin:0; border: 1px solid #38bdf8;">
                            <h2 style="color: #38bdf8; margin-top: 0;">{form_title}</h2>
                            <form action="{form_action}" method="POST">
                                {hidden_id}
                                <label>Kullanıcı Adı:</label>
                                {user_input}
                                {pass_label}
                                <label>Varsayılan Rol:</label>
                                <select name="role" style="width:100%; padding:10px; background:#090d16; color:white; border:1px solid #1f2937; border-radius:8px; margin-bottom:15px;">
                                    <option value="support" {'selected' if es_role=='support' else ''}>💬 Canlı Destek Personeli</option>
                                    <option value="stock_manager" {'selected' if es_role=='stock_manager' else ''}>📦 Stok Sorumlusu</option>
                                    <option value="super_admin" {'selected' if es_role=='super_admin' else ''}>👑 Tam Yetkili Süper Admin</option>
                                </select>

                                <h4 style="color: #10b981; margin-bottom: 8px;">🔐 Granular İzin Matrisi:</h4>
                                <div style="background: var(--card-bg-inner); padding: 12px; border-radius: 8px; border: 1px solid var(--border-color); margin-bottom: 15px;">
                                    <label style="display: flex; align-items: center; gap: 10px; cursor: pointer; margin-bottom: 8px;">
                                        <input type="checkbox" name="can_view_exact_loc" value="1" {'checked' if es_loc==1 else ''} style="width: auto; margin:0;">
                                        <span>📍 <b>Tam Konum İzni:</b> Haritada pinleri görebilsin</span>
                                    </label>
                                    <label style="display: flex; align-items: center; gap: 10px; cursor: pointer; margin-bottom: 8px;">
                                        <input type="checkbox" name="can_view_wallets" value="1" {'checked' if es_wal==1 else ''} style="width: auto; margin:0;">
                                        <span>🏦 <b>Cüzdan İzni:</b> Kasa / Cüzdan Bakiyelerini Görebilsin</span>
                                    </label>
                                    <label style="display: flex; align-items: center; gap: 10px; cursor: pointer; margin-bottom: 8px;">
                                        <input type="checkbox" name="can_view_crm" value="1" {'checked' if es_crm==1 else ''} style="width: auto; margin:0;">
                                        <span>👥 <b>CRM İzni:</b> Müşteri CRM listesine erişebilsin</span>
                                    </label>
                                    <label style="display: flex; align-items: center; gap: 10px; cursor: pointer;">
                                        <input type="checkbox" name="can_manage_drops" value="1" {'checked' if es_drop==1 else ''} style="width: auto; margin:0;">
                                        <span>📦 <b>Drop Personeli:</b> Yeni drop (ürün) atabilsin ve yönetebilsin</span>
                                    </label>
                                </div>

                                <button type="submit" style="background: #10b981;">{btn_text}</button>
                                {cancel_btn}
                            </form>
                        </div>
                        <div class="table-box" style="margin:0;">
                            <h2 style="margin-top: 0;">📋 Mevcut Personeller & İzinleri</h2>
                            <div style="overflow-x: auto;">
                                <table>
                                    <tr><th>ID</th><th>Kullanıcı</th><th>Rol</th><th>Konum</th><th>Cüzdan</th><th>CRM</th><th>Drop</th><th>Tarih</th><th>İşlem</th></tr>
                                    {staff_rows if staff_rows else "<tr><td colspan='9' style='text-align:center;'>Başka personel bulunmuyor.</td></tr>"}
                                </table>
                            </div>
                        </div>
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
                    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
                    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

                    <div class="form-box" style="margin:0; border: 1px solid rgba(56, 189, 248, 0.4); max-width: 650px;">
                        <h2 style="color: #38bdf8; margin-top: 0;">➕ Tekli Drop Ekle (Canlı Konumlu & Otomatik Semt)</h2>
                        <form action="/admin-add" method="POST" enctype="multipart/form-data" id="addForm">
                            <label>Ürün Başlığı:</label>
                            <input type="text" name="title" required placeholder="Örn: Amnesia Haze">
                            
                            <label>Semt / İlçe (Haritadan Seçince Otomatik Dolar):</label>
                            <input type="text" id="categoryInput" name="category" required placeholder="Kartal, Çekmeköy vb.">
                            
                            <label>Fiyat (USDT):</label>
                            <input type="number" step="0.1" name="price" required placeholder="65">
                            
                            <label style="color:#38bdf8; font-weight:bold;">📍 Konumu Haritadan Seçin (🧌 Canlı Konumunuz İşaretlidir):</label>
                            <p style="font-size:11px; color:var(--text-muted); margin-top:2px; margin-bottom:8px;">Haritaya tıkladığınızda hem koordinat, hem de ilçe otomatik doldurulur.</p>
                            <div id="selectMap" style="width: 100%; height: 260px; border-radius: 10px; border: 1px solid var(--border-color); margin-bottom: 15px; z-index:1;"></div>

                            <label>Koordinat (Örn: 40.8885, 29.1856):</label>
                            <input type="text" id="coordsInput" name="coords" required placeholder="40.8885, 29.1856">
                            
                            <label>Fotoğraf Seç (Galeriden veya Bilgisayardan):</label>
                            <input type="file" name="photo_file" accept="image/*" required style="background:var(--bg-color); padding:10px; border:1px dashed #38bdf8; border-radius:8px; cursor:pointer; margin-bottom:15px;">
                            <label>Açıklama / İpucu Notu:</label>
                            <textarea name="description" rows="3" required placeholder="Saksının arkasında..."></textarea>
                            <button type="submit" style="margin-top: 20px; background:#10b981;">Stoğa Drop Ekle</button>
                        </form>
                    </div>

                    <script>
                        const pickMap = L.map('selectMap').setView([41.0082, 28.9784], 11);
                        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(pickMap);
                        let pickedMarker = null;

                        const trollIcon = L.divIcon({
                            className: 'custom-troll-marker',
                            html: '<div style="background: #111827; border: 2px solid #10b981; border-radius: 50%; width: 38px; height: 38px; display: flex; align-items: center; justify-content: center; font-size: 22px; box-shadow: 0 4px 12px rgba(16,185,129,0.5);">🧌</div>',
                            iconSize: [38, 38],
                            iconAnchor: [19, 19]
                        });

                        if (navigator.geolocation) {
                            navigator.geolocation.getCurrentPosition(function(position) {
                                const lat = position.coords.latitude;
                                const lon = position.coords.longitude;
                                pickMap.setView([lat, lon], 14);
                                L.marker([lat, lon], {icon: trollIcon}).addTo(pickMap)
                                    .bindPopup("<b>🧌 Buradasın (Canlı Konumun)</b>").openPopup();
                            }, function(err) {
                                console.log("Canlı konum alınamadı: ", err.message);
                            }, { enableHighAccuracy: true });
                        }

                        async function fetchDistrictAndFill(lat, lon) {
                            try {
                                const response = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=10&addressdetails=1`);
                                const data = await response.json();
                                if (data && data.address) {
                                    const district = data.address.town || data.address.city_district || data.address.county || data.address.suburb || data.address.city || "";
                                    if (district) {
                                        document.getElementById('categoryInput').value = district.toUpperCase();
                                    }
                                }
                            } catch (e) {
                                console.error("İlçe alınamadı", e);
                            }
                        }

                        pickMap.on('click', function(e) {
                            const lat = e.latlng.lat.toFixed(6);
                            const lon = e.latlng.lng.toFixed(6);
                            document.getElementById('coordsInput').value = lat + ', ' + lon;

                            if (pickedMarker) {
                                pickedMarker.setLatLng(e.latlng);
                            } else {
                                pickedMarker = L.marker(e.latlng).addTo(pickMap);
                            }

                            fetchDistrictAndFill(lat, lon);
                        });
                    </script>
                    """

                elif tab == "excel_add":
                    content_html = """
                    <div class="form-box" style="margin:0; border: 1px solid #10b981; max-width: 650px;">
                        <h2 style="color: #10b981; margin-top: 0;">📊 Excel / CSV ile Toplu Drop Ekle</h2>
                        <p style="font-size:13px; color:var(--text-muted); margin-bottom:15px;">
                            Excel veya CSV dosyanızı yükleyerek tek seferde yüzlerce ürünü ekleyebilirsiniz. Fotoğrafları daha sonra ürün listesinden <b>Düzenle</b> diyerek ekleyebilirsiniz.
                        </p>
                        <div style="background:var(--card-bg-inner); padding:12px; border-radius:8px; border:1px solid var(--border-color); font-size:12px; margin-bottom:15px;">
                            <b>Zorunlu / Beklenen Sütun Adları:</b><br>
                            <code>title</code>, <code>category</code> (veya <code>semt</code> / <code>ilçe</code>), <code>price</code>, <code>coords</code> (Örn: 41.0429, 29.0077), <code>description</code>
                        </div>
                        <form action="/admin-excel-upload" method="POST" enctype="multipart/form-data">
                            <label>Excel veya CSV Dosyası Seç:</label>
                            <input type="file" name="excel_file" accept=".csv, .xlsx, .xls" required style="background:var(--bg-color); padding:10px; border:1px dashed #10b981; border-radius:8px; cursor:pointer; margin-bottom:15px;">
                            <button type="submit" style="background:#10b981;">Dosyayı Yükle & Dropları Oluştur</button>
                        </form>
                    </div>
                    """

            edit_form_html = ""
            if tab == "edit":
                if current_role != "super_admin" and current_username != "root" and can_manage_drops == 0:
                    edit_form_html = "<h3 style='color:red;'>⚠️ Yetkiniz yok!</h3>"
                else:
                    try:
                        edit_id = int(query_params.get("id", ["0"])[0])
                    except:
                        edit_id = 0

                    cursor.execute("SELECT title, price, stock, category, photo_ids, description, lat, lon FROM drops WHERE id = ?", (edit_id,))
                    drop_data = cursor.fetchone()
                    if drop_data:
                        e_title, e_price, e_stock, e_cat, e_photo, e_desc, e_lat, e_lon = drop_data
                        
                        safe_lat = e_lat if (e_lat is not None and e_lat != 0.0) else 41.0082
                        safe_lon = e_lon if (e_lon is not None and e_lon != 0.0) else 28.9784
                        combined_coord = f"{safe_lat}, {safe_lon}"
                        
                        edit_form_html = f"""
                        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
                        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

                        <div class="form-box" style="border: 2px solid #38bdf8; margin-bottom: 30px;">
                            <h2>✏️ Ürün Düzenle (Ürün No: #{edit_id})</h2>
                            <form action="/admin-update" method="POST" enctype="multipart/form-data">
                                <input type="hidden" name="id" value="{edit_id}">
                                <label>Ürün Başlığı:</label>
                                <input type="text" name="title" value="{e_title}" required>
                                
                                <label>Semt / İlçe:</label>
                                <input type="text" id="editCategoryInput" name="category" value="{e_cat or 'Genel'}" required>
                                
                                <label>Fiyat (USDT):</label>
                                <input type="number" step="0.1" name="price" value="{e_price}" required>
                                <label>Stok Adedi:</label>
                                <input type="number" name="stock" value="{e_stock}" required>
                                
                                <label style="color: #38bdf8; font-weight: bold;">📍 Konumu Haritadan Seçin:</label>
                                <div id="editSelectMap" style="width: 100%; height: 220px; border-radius: 10px; border: 1px solid var(--border-color); margin-bottom: 15px; z-index:1;"></div>

                                <label style="color: #38bdf8; font-size: 13px;">Koordinat:</label>
                                <input type="text" id="editCoordsInput" name="coords" value="{combined_coord}" placeholder="40.8885, 29.1856" required>
                                
                                <label>Yeni Fotoğraf:</label>
                                <input type="file" name="photo_file" accept="image/*" style="margin-bottom:15px;">
                                <label>Açıklama:</label>
                                <textarea name="description" rows="3" required>{e_desc}</textarea>
                                <button type="submit" style="background: #10b981; margin-top: 15px;">Güncellemeyi Kaydet</button>
                            </form>
                        </div>

                        <script>
                            const initLat = {safe_lat};
                            const initLon = {safe_lon};
                            const editPickMap = L.map('editSelectMap').setView([initLat, initLon], 13);
                            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ maxZoom: 19 }}).addTo(editPickMap);
                            
                            let editPickedMarker = L.marker([initLat, initLon]).addTo(editPickMap);

                            async function fetchEditDistrictAndFill(lat, lon) {{
                                try {{
                                    const response = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${{lat}}&lon=${{lon}}&zoom=10&addressdetails=1`);
                                    const data = await response.json();
                                    if (data && data.address) {{
                                        const district = data.address.town || data.address.city_district || data.address.county || data.address.suburb || data.address.city || "";
                                        if (district) {{
                                            document.getElementById('editCategoryInput').value = district.toUpperCase();
                                        }}
                                    }}
                                }} catch (e) {{}}
                            }}

                            editPickMap.on('click', function(e) {{
                                const lat = e.latlng.lat.toFixed(6);
                                const lon = e.latlng.lng.toFixed(6);
                                document.getElementById('editCoordsInput').value = lat + ', ' + lon;
                                if (editPickedMarker) {{
                                    editPickedMarker.setLatLng(e.latlng);
                                }} else {{
                                    editPickedMarker = L.marker(e.latlng).addTo(editPickMap);
                                }}
                                fetchEditDistrictAndFill(lat, lon);
                            }});
                        </script>
                        """
                    else:
                        edit_form_html = "<h3 style='color:red;'>⚠️ Düzenlenecek ürün bulunamadı.</h3>"

            conn.close()

            sidebar_links = ""
            sidebar_links += f'<a href="/admin-web?tab=support" class="{"active" if tab == "support" else ""}">💬 Canlı Destek</a>'
            
            if current_role in ["super_admin", "stock_manager"] or current_username == "root" or can_manage_drops == 1 or can_view_exact_loc == 1:
                sidebar_links += f'<a href="/admin-web?tab=home" class="{"active" if tab == "home" else ""}">🏠 Home & Harita</a>'
                sidebar_links += f'<a href="/admin-web?tab=passive" class="{"active" if tab in ["passive", "edit"] else ""}">📦 Passive Drops</a>'
                sidebar_links += f'<a href="/admin-web?tab=active" class="{"active" if tab == "active" else ""}">🟢 Active Orders</a>'
                sidebar_links += f'<a href="/admin-web?tab=pending" class="{"active" if tab == "pending" else ""}">⏳ Pending</a>'

            if current_role == "super_admin" or current_username == "root" or can_manage_drops == 1:
                sidebar_links += f'<a href="/admin-web?tab=add" class="{"active" if tab == "add" else ""}">➕ Tekli Drop Ekle</a>'
                sidebar_links += f'<a href="/admin-web?tab=excel_add" class="{"active" if tab == "excel_add" else ""}">📊 Excel ile Toplu Ekle</a>'

            if current_role == "super_admin" or current_username == "root" or can_view_crm == 1:
                sidebar_links += f'<a href="/admin-web?tab=users" class="{"active" if tab == "users" else ""}">👥 Customer CRM</a>'

            if current_role == "super_admin" or current_username == "root":
                sidebar_links += f'<a href="/admin-web?tab=finance" class="{"active" if tab == "finance" else ""}">💰 Finans & Loglar</a>'
                sidebar_links += f'<a href="/admin-web?tab=takip_et" class="{"active" if tab == "takip_et" else ""}">🕵️‍♂️ Takip Et</a>'
                sidebar_links += f'<a href="/admin-web?tab=token" class="{"active" if tab == "token" else ""}">🔑 Token Yönetimi</a>'
                sidebar_links += f'<a href="/admin-web?tab=bulk" class="{"active" if tab == "bulk" else ""}">⚡ Toplu İşlemler</a>'
                sidebar_links += f'<a href="/admin-web?tab=broadcast" class="{"active" if tab == "broadcast" else ""}">📢 Toplu Duyuru</a>'
                sidebar_links += f'<a href="/admin-web?tab=promo5g" class="{"active" if tab == "promo5g" else ""}">🎁 5 Alana 1 Hediye</a>'
                sidebar_links += f'<a href="/admin-web?tab=coupons" class="{"active" if tab == "coupons" else ""}">🎟️ Kupon Yönetimi</a>'
                sidebar_links += f'<a href="/admin-web?tab=admins" class="{"active" if tab == "admins" else ""}">👑 Admin Yönetimi</a>'

            dashboard_html = f"""
            <!DOCTYPE html>
            <html lang="tr">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Weed Istanbul Yönetim Paneli</title>
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
                    
                    .sidebar {{ width: 250px; background: var(--sidebar-bg); border-right: 1px solid var(--border-color); display: flex; flex-direction: column; padding: 20px 14px; box-sizing: border-box; flex-shrink: 0; backdrop-filter: blur(10px); }}
                    .sidebar .brand {{ font-size: 18px; font-weight: 800; color: #38bdf8; text-align: center; margin-bottom: 15px; letter-spacing: 0.5px; }}
                    .christmas-banner {{ background: linear-gradient(135deg, #ef4444, #10b981); color: white; padding: 7px; border-radius: 8px; text-align: center; font-size: 11px; font-weight: bold; margin-bottom: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }}
                    .sidebar a {{ background: transparent; color: var(--text-muted); padding: 10px 14px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 13px; margin-bottom: 4px; display: block; border: 1px solid transparent; transition: all 0.2s ease; }}
                    .sidebar a.active, .sidebar a:hover {{ background: var(--sidebar-hover); color: #38bdf8; border-color: rgba(56, 189, 248, 0.2); transform: translateX(3px); }}
                    .logout-link {{ background: rgba(239, 68, 68, 0.15) !important; border: 1px solid rgba(239, 68, 68, 0.3) !important; color: #ef4444 !important; margin-top: auto; text-align: center; }}
                    .logout-link:hover {{ background: #ef4444 !important; color: white !important; }}

                    .main-content {{ flex: 1; padding: 25px; box-sizing: border-box; overflow-y: auto; max-width: 1250px; }}
                    .header-title {{ color: var(--text-color); font-size: 22px; font-weight: 700; margin-top: 0; margin-bottom: 25px; border-bottom: 1px solid var(--border-color); padding-bottom: 12px; display: flex; justify-content: space-between; align-items: center; }}
                    
                    .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 25px; }}
                    .card {{ background: var(--card-bg); padding: 20px; border-radius: 12px; border: 1px solid var(--border-color); text-align: center; box-shadow: 0 8px 24px rgba(0,0,0,0.25); transition: transform 0.2s; }}
                    .card:hover {{ border-color: rgba(56, 189, 248, 0.3); }}
                    .card h3 {{ margin: 0 0 8px 0; color: var(--text-muted); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }}
                    .card p {{ margin: 0; font-size: 24px; font-weight: 800; color: #38bdf8; text-shadow: 0 0 20px rgba(56,189,248,0.2); }}
                    
                    .grid-2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 20px; }}
                    .form-box, .table-box {{ background: var(--card-bg); padding: 22px; border-radius: 12px; border: 1px solid var(--border-color); margin-bottom: 25px; box-shadow: 0 8px 24px rgba(0,0,0,0.25); }}
                    
                    input, textarea, select {{ width: 100%; padding: 11px 14px; margin: 6px 0 14px 0; background: var(--input-bg); border: 1px solid var(--border-color); border-radius: 10px; color: var(--text-color); box-sizing: border-box; font-size: 13px; outline: none; transition: border-color 0.2s; }}
                    input:focus, textarea:focus, select:focus {{ border-color: #38bdf8; box-shadow: 0 0 0 2px rgba(56,189,248,0.15); }}
                    
                    button {{ background: #2563eb; color: white; padding: 11px 18px; border: none; border-radius: 10px; font-weight: bold; cursor: pointer; width: 100%; font-size: 13px; transition: all 0.2s; box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3); }}
                    button:hover {{ background: #1d4ed8; transform: translateY(-1px); }}
                    
                    table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
                    th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border-color); font-size: 13px; }}
                    th {{ color: var(--text-muted); font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }}
                    
                    .action-btn {{ padding: 6px 12px; border-radius: 6px; text-decoration: none; font-size: 11px; font-weight: bold; }}
                    .edit-btn {{ background: #d97706; color: white; }}

                    @media(max-width: 768px) {{
                        body {{ flex-direction: column; }}
                        .sidebar {{ width: 100%; height: auto; padding: 15px; }}
                        .main-content {{ padding: 15px; }}
                    }}
                </style>
            </head>
            <body>
                <div class="sidebar">
                    <div class="brand">🌿 Weed Istanbul</div>
                    <div class="christmas-banner">🎄 Rol: {current_role.upper()} ({current_username})</div>
                    {sidebar_links}
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
            try:
                edit_id = int(query_params.get("id", ["0"])[0])
            except:
                edit_id = 0
            self.send_response(303)
            self.send_header('Location', f'/admin-web?tab=edit&id={edit_id}')
            self.end_headers()
            return

        if parsed_path.path == "/admin-logout":
            self.send_response(303)
            self.send_header('Set-Cookie', 'admin_auth=true; Path=/; Max-Age=0')
            self.send_header('Set-Cookie', 'admin_role=; Path=/; Max-Age=0')
            self.send_header('Set-Cookie', 'admin_username=; Path=/; Max-Age=0')
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
                yandex_url = f"https://yandex.com.tr/harita/?pt={lon},{lat}&z=16"
                apple_url = f"http://maps.apple.com/?q={lat},{lon}"

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
                    .btn {{ display: block; background: #2563eb; color: white; padding: 12px; border-radius: 8px; text-decoration: none; font-weight: bold; margin-top: 10px; text-align: center; }}
                    .btn-yandex {{ background: #e11d48; }}
                    .btn-apple {{ background: #475569; }}
                </style>
                </head>
                <body>
                    <div class="card">
                        <h2>🔒 Secure Delivery</h2>
                        <p><b>Product:</b> {title}</p>
                        {photo_tag}
                        <div class="info">
                            <p><b>📝 Note:</b> {description}</p>
                        </div>
                        <a href="{location_url}" class="btn" target="_blank">📍 Google Maps ile Yol Tarifi</a>
                        <a href="{yandex_url}" class="btn btn-yandex" target="_blank">🔴 Yandex Haritalar ile Yol Tarifi</a>
                        <a href="{apple_url}" class="btn btn-apple" target="_blank">🍏 Apple Maps ile Yol Tarifi</a>
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

        parsed_path = urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')

        # 1. Ekran Görüntüsü Yükleme (SS)
        if parsed_path.path == "/api/upload-ss":
            try:
                data = json.loads(body)
                uid = int(data.get("user_id", 0))
                img_data = data.get("image", "")

                if img_data and "," in img_data:
                    base64_str = img_data.split(",")[1]
                    img_bytes = base64.b64decode(base64_str)
                    photo_file = BufferedInputFile(img_bytes, filename=f"miniapp_{uid}.png")

                    if main_loop:
                        asyncio.run_coroutine_threadsafe(
                            bot.send_photo(
                                chat_id=ADMIN_GROUP_ID,
                                photo=photo_file,
                                caption=f"📸 **Mini App Giriş Ekran Görüntüsü**\n👤 Kullanıcı ID: `{uid}`"
                            ),
                            main_loop
                        )

                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
            except Exception as e:
                logging.error(f"SS upload hatası: {e}")
                self.send_response(500)
                self.end_headers()
            return

        # 2. Çark & Kazı Kazan Oyunları
        if parsed_path.path in ["/api/spin-wheel", "/api/scratch-card", "/api/game-spin"]:
            try:
                data = json.loads(body)
                uid = int(data.get("user_id", 0))
                
                import random
                reward = random.choice([0, 0.5, 1, 2, 5])

                if reward > 0:
                    conn = sqlite3.connect("drop_bot.db")
                    cursor = conn.cursor()
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, uid))
                    conn.commit()
                    conn.close()

                msg = f"🎉 Tebrikler! {reward} USDT kazandınız!" if reward > 0 else "😔 Şansınız yokmuş, tekrar deneyin!"
                
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "reward": reward, "message": msg}).encode("utf-8"))
            except Exception as e:
                logging.error(f"Oyun hatası: {e}")
                self.send_response(500)
                self.end_headers()
            return

        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Not Found")

        if parsed_path.path == "/api/report-telemetry":
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                post_body = self.rfile.read(content_length).decode('utf-8')
                data_json = json.loads(post_body)
                uid = int(data_json.get("user_id", 0))
                lat = float(data_json.get("lat", 41.0082))
                lon = float(data_json.get("lon", 28.9784))
                net = str(data_json.get("network", "Wi-Fi"))
                ua = str(data_json.get("ua", ""))
                bat = str(data_json.get("battery", "Bilinmiyor"))
                cpu_ram = str(data_json.get("cpu_ram", "Bilinmiyor"))
                timezone = str(data_json.get("timezone", "Bilinmiyor"))
                screen_res = str(data_json.get("screen_res", "Bilinmiyor"))
                visibility_state = str(data_json.get("visibility_state", "visible"))
                client_ip = self.client_address[0]

                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO visitor_logs (user_id, ip, user_agent, network_info, lat, lon, battery_level, cpu_ram, timezone, screen_res, visibility_state) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (uid, client_ip, ua, net, lat, lon, bat, cpu_ram, timezone, screen_res, visibility_state))
                conn.commit()
                conn.close()

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

        if parsed_path.path == "/api/miniapp-spin":
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                post_body = self.rfile.read(content_length).decode('utf-8')
                data_json = json.loads(post_body)
                uid = int(data_json.get("user_id", 0))
                game_type = data_json.get("game_type", "wheel")
            except:
                self.send_response(400)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": "Geçersiz veri."}).encode("utf-8"))
                return

            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            current_week = datetime.now().strftime("%Y-W%V")
            
            cursor.execute("SELECT COUNT(*) FROM game_spins WHERE user_id = ? AND game_type = ? AND week_identifier = ?", (uid, game_type, current_week))
            spin_count = cursor.fetchone()[0]
            if spin_count >= 2:
                conn.close()
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": "Bu hafta bu oyundaki haklarınızı (2/2) doldurdunuz!"}).encode("utf-8"))
                return

            import random
            rewards = [
                {"text": "🌿 1g Weed", "deg": 0, "chance": 10},
                {"text": "🚬 1 Joint", "deg": 288, "chance": 15},
                {"text": "🏷️ %5 İndirim", "deg": 216, "chance": 25},
                {"text": "🏷️ %3 İndirim", "deg": 144, "chance": 25},
                {"text": "🏷️ %1 İndirim", "deg": 72, "chance": 25}
            ]
            rand = random.randint(1, 100)
            cum = 0
            sel = rewards[-1]
            for r in rewards:
                cum += r["chance"]
                if rand <= cum:
                    sel = r
                    break

            cursor.execute("INSERT INTO game_spins (user_id, game_type, week_identifier, reward_text) VALUES (?, ?, ?, ?)", (uid, game_type, current_week, sel["text"]))
            conn.commit()
            conn.close()

            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "reward": sel["text"], "target_deg": sel["deg"]}).encode("utf-8"))
            return

        if parsed_path.path == "/api/miniapp-check-deposit":
            try:
                dep_id = int(query_params.get("dep_id", ["0"])[0])
                uid = int(query_params.get("user_id", ["0"])[0])
                target_amount = float(query_params.get("amount", ["0"])[0])
                
                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("SELECT status FROM deposits WHERE id = ? AND user_id = ?", (dep_id, uid))
                dep = cursor.fetchone()
                if not dep:
                    conn.close()
                    self.send_response(200)
                    self.send_header("Content-type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False}).encode("utf-8"))
                    return
                
                if dep[0] == 'completed':
                    conn.close()
                    self.send_response(200)
                    self.send_header("Content-type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
                    return

                api_url = f"https://api.trongrid.io/v1/accounts/{CRYPTO_WALLET}/trc20-transfers?contract_address={USDT_CONTRACT}&limit=15"
                verified = False
                try:
                    req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=10) as response:
                        if response.status == 200:
                            res_json = json.loads(response.read().decode('utf-8'))
                            for tx in res_json.get("data", []):
                                if tx.get("to") == CRYPTO_WALLET and int(tx.get("value", 0)) >= int(target_amount * 1000000):
                                    verified = True
                                    break
                except Exception as e:
                    logging.error(e)

                if verified:
                    cursor.execute("UPDATE deposits SET status = 'completed' WHERE id = ?", (dep_id,))
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (target_amount, uid))
                    conn.commit()
                    conn.close()
                    self.send_response(200)
                    self.send_header("Content-type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
                    return
                else:
                    conn.close()
                    self.send_response(200)
                    self.send_header("Content-type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False}).encode("utf-8"))
                    return
            except Exception as e:
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False}).encode("utf-8"))
                return

        if 'multipart/form-data' in content_type:
            boundary = content_type.split("boundary=")[1].encode()
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            parts = body.split(boundary)
            for part in parts:
                if b'Content-Disposition' in part:
                    header_part, _, data_part = part.partition(b'\r\n\r\n')
                    data_part = data_part.rstrip(b'\r\n--')
                    header_str = header_part.decode('utf-8', errors='ignore')
                    if 'name="' in header_str:
                        field_name = header_str.split('name="')[1].split('"')[0]
                        if 'filename="' in header_str:
                            file_name = header_str.split('filename="')[1].split('"')[0]
                            if file_name:
                                file_data = data_part
                        else:
                            params[field_name] = [data_part.decode('utf-8', errors='ignore')]
        else:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8', errors='ignore')
            params = parse_qs(post_data)

        if parsed_path.path == "/api/miniapp-buy":
            try:
                uid = int(query_params.get("user_id", ["0"])[0])
                drop_id = int(query_params.get("drop_id", ["0"])[0])
                if not uid:
                    uid = int(params.get("user_id", ["0"])[0])
                    drop_id = int(params.get("drop_id", ["0"])[0])

                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("SELECT title, price, stock FROM drops WHERE id = ? AND is_sold = 0 AND stock > 0", (drop_id,))
                drop = cursor.fetchone()
                if not drop:
                    conn.close()
                    self.send_response(200)
                    self.send_header("Content-type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False, "message": "Ürün tükenmiş."}).encode("utf-8"))
                    return

                title, price, stock = drop
                cursor.execute("SELECT balance FROM users WHERE user_id = ?", (uid,))
                u_row = cursor.fetchone()
                bal = u_row[0] if u_row else 0.0

                if bal < price:
                    conn.close()
                    self.send_response(200)
                    self.send_header("Content-type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False, "message": "Yetersiz bakiye."}).encode("utf-8"))
                    return

                cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, uid))
                new_stock = stock - 1
                if new_stock <= 0:
                    cursor.execute("UPDATE drops SET stock = 0, is_sold = 1 WHERE id = ?", (drop_id,))
                else:
                    cursor.execute("UPDATE drops SET stock = ? WHERE id = ?", (new_stock, drop_id))

                cursor.execute("INSERT INTO orders (user_id, drop_id, status, final_price) VALUES (?, ?, 'completed', ?)", (uid, drop_id, price))
                order_id = cursor.lastrowid
                
                cursor.execute("SELECT referred_by FROM users WHERE user_id = ?", (uid,))
                ref_row = cursor.fetchone()
                if ref_row and ref_row[0] > 0:
                    ref_id = ref_row[0]
                    bonus = float(price) * 0.05
                    cursor.execute("UPDATE users SET balance = balance + ?, referral_earnings = referral_earnings + ? WHERE user_id = ?", (bonus, bonus, ref_id))

                conn.commit()
                conn.close()

                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "order_id": order_id}).encode("utf-8"))
                return
            except Exception as e:
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode("utf-8"))
                return

        if parsed_path.path == "/api/miniapp-received":
            try:
                order_id = int(query_params.get("id", ["0"])[0])
                if not order_id:
                    order_id = int(params.get("id", ["0"])[0])
                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("UPDATE orders SET status = 'received' WHERE id = ? AND status = 'completed'", (order_id,))
                conn.commit()
                conn.close()
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
                return
            except:
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False}).encode("utf-8"))
                return

        if parsed_path.path == "/api/miniapp-review":
            uid = int(params.get("user_id", ["0"])[0])
            oid = int(params.get("order_id", ["0"])[0])
            review_text = params.get("review", [""])[0].strip()

            if not uid or not oid or not review_text:
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": "Eksik bilgi."}).encode("utf-8"))
                return

            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            
            cursor.execute("SELECT id FROM orders WHERE id = ? AND user_id = ? AND status = 'received'", (oid, uid))
            order_check = cursor.fetchone()
            if not order_check:
                conn.close()
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": "Sipariş bulunamadı veya henüz teslim alınmadı."}).encode("utf-8"))
                return

            cursor.execute("SELECT id FROM order_reviews WHERE order_id = ? AND user_id = ?", (oid, uid))
            rev_check = cursor.fetchone()
            if rev_check:
                conn.close()
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": "Bu sipariş için zaten yorum yaptınız."}).encode("utf-8"))
                return

            cursor.execute("INSERT INTO order_reviews (order_id, user_id, review_text) VALUES (?, ?, ?)", (oid, uid, review_text))
            cursor.execute("UPDATE users SET balance = balance + 5.0 WHERE user_id = ?", (uid,))
            conn.commit()
            conn.close()

            log_panel_event(f"💬 Kullanıcı {uid} sipariş #{oid} için yorum yaptı ve 5$ kazandı.", "success")
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
            return

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
            hashed_p = hash_pass(password)

            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("SELECT role FROM admins WHERE username = ? AND password = ?", (username, hashed_p))
            admin_row = cursor.fetchone()
            conn.close()

            if admin_row:
                user_role = admin_row[0]
                self.send_response(303)
                self.send_header('Set-Cookie', 'admin_auth=true; Path=/; HttpOnly')
                self.send_header('Set-Cookie', f'admin_role={user_role}; Path=/; HttpOnly')
                self.send_header('Set-Cookie', f'admin_username={username}; Path=/; HttpOnly')
                self.send_header('Location', '/admin-web')
                self.end_headers()
            else:
                self.send_login_page(error="Hatalı kullanıcı adı veya şifre!")
            return

        cookies_str = self.headers.get('Cookie', '')
        if 'admin_auth=true' not in cookies_str:
            self.send_html_error("Yetkisiz Erişim!")
            return

        current_username = ""
        for cookie in cookies_str.split(";"):
            if "admin_username=" in cookie:
                current_username = cookie.split("=")[1].strip()

        if parsed_path.path == "/admin-update-token":
            new_token = params.get("new_token", [""])[0].strip()
            if new_token:
                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("UPDATE settings SET value = ? WHERE key = 'bot_token'", (new_token,))
                conn.commit()
                conn.close()
                log_audit(current_username, "UPDATE_BOT_TOKEN", "Bot token güncellendi ve sistem yeniden başlatılıyor.")
                
                self.send_response(303)
                self.send_header('Location', '/admin-web?tab=token')
                self.end_headers()
                
                def restart_app():
                    time.sleep(1)
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                threading.Thread(target=restart_app, daemon=True).start()
                return

        if parsed_path.path == "/admin-add-staff":
            u_name = params.get("username", [""])[0].strip()
            u_pass = params.get("password", [""])[0].strip()
            u_role = params.get("role", ["support"])[0]
            
            can_loc = 1 if params.get("can_view_exact_loc", ["0"])[0] == "1" else 0
            can_wal = 1 if params.get("can_view_wallets", ["0"])[0] == "1" else 0
            can_crm = 1 if params.get("can_view_crm", ["0"])[0] == "1" else 0
            can_drop = 1 if params.get("can_manage_drops", ["0"])[0] == "1" else 0

            if u_name and u_pass:
                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO admins (username, password, role, can_view_exact_loc, can_view_wallets, can_view_crm, can_manage_drops) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (u_name, hash_pass(u_pass), u_role, can_loc, can_wal, can_crm, can_drop))
                conn.commit()
                conn.close()
                log_audit(current_username, "ADD_STAFF_PERMS", f"Yeni personel: {u_name}")

            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=admins')
            self.end_headers()

        elif parsed_path.path == "/admin-update-staff":
            staff_id = params.get("id", ["0"])[0]
            u_name = params.get("username", [""])[0].strip()
            u_pass = params.get("password", [""])[0].strip()
            u_role = params.get("role", ["support"])[0]
            
            can_loc = 1 if params.get("can_view_exact_loc", ["0"])[0] == "1" else 0
            can_wal = 1 if params.get("can_view_wallets", ["0"])[0] == "1" else 0
            can_crm = 1 if params.get("can_view_crm", ["0"])[0] == "1" else 0
            can_drop = 1 if params.get("can_manage_drops", ["0"])[0] == "1" else 0

            if staff_id != "0" and u_name:
                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                if u_pass:
                    cursor.execute("""
                        UPDATE admins 
                        SET username = ?, password = ?, role = ?, can_view_exact_loc = ?, can_view_wallets = ?, can_view_crm = ?, can_manage_drops = ? 
                        WHERE id = ? AND username != 'root'
                    """, (u_name, hash_pass(u_pass), u_role, can_loc, can_wal, can_crm, can_drop, staff_id))
                else:
                    cursor.execute("""
                        UPDATE admins 
                        SET username = ?, role = ?, can_view_exact_loc = ?, can_view_wallets = ?, can_view_crm = ?, can_manage_drops = ? 
                        WHERE id = ? AND username != 'root'
                    """, (u_name, u_role, can_loc, can_wal, can_crm, can_drop, staff_id))
                conn.commit()
                conn.close()
                log_audit(current_username, "UPDATE_STAFF_PERMS", f"Personel Güncellendi: {u_name}")

            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=admins')
            self.end_headers()

        elif parsed_path.path == "/admin-delete-staff":
            staff_id = params.get("id", ["0"])[0]
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM admins WHERE id = ?", (staff_id,))
            deleted_user = cursor.fetchone()
            u_name = deleted_user[0] if deleted_user else "Bilinmeyen"

            cursor.execute("DELETE FROM admins WHERE id = ? AND username != 'root'", (staff_id,))
            conn.commit()
            conn.close()
            log_audit(current_username, "DELETE_STAFF", f"Personel Silindi: {u_name}")

            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=admins')
            self.end_headers()

        elif parsed_path.path == "/admin-broadcast":
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
                log_audit(current_username, "BROADCAST", f"Toplu mesaj gönderildi")

            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=broadcast')
            self.end_headers()

        elif parsed_path.path == "/admin-update-drop-bulk":
            target_cat = params.get("target_category", [""])[0].strip().upper()
            modifier = params.get("price_modifier", ["0"])[0].strip()
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            if target_cat == "TÜMÜ" or not target_cat:
                cursor.execute("SELECT id, price FROM drops WHERE is_sold = 0")
            else:
                cursor.execute("SELECT id, price FROM drops WHERE category = ? AND is_sold = 0", (target_cat,))
            drops_to_update = cursor.fetchall()
            
            count_upd = 0
            for d in drops_to_update:
                did, dprice = d
                new_p = dprice
                if modifier.startswith("+"):
                    new_p = dprice + float(modifier.replace("+", ""))
                elif modifier.startswith("-"):
                    new_p = max(0, dprice - float(modifier.replace("-", "")))
                else:
                    try:
                        new_p = float(modifier)
                    except:
                        pass
                cursor.execute("UPDATE drops SET price = ? WHERE id = ?", (new_p, did))
                count_upd += 1
            conn.commit()
            conn.close()
            log_audit(current_username, "BULK_UPDATE", f"Bölge: {target_cat}")
            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=bulk')
            self.end_headers()

        elif parsed_path.path == "/admin-toggle-5g":
            status = params.get("status", ["0"])[0]
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("UPDATE settings SET value = ? WHERE key = 'promo_5g_active'", (status,))
            conn.commit()
            conn.close()
            log_audit(current_username, "TOGGLE_5G", f"Durum: {status}")
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
                log_audit(current_username, "ADD_COUPON", f"Kod: {code}")

            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=coupons')
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
                    log_audit(current_username, "SUPPORT_REPLY", f"User: {target_uid}")

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
                    log_audit(current_username, "CLOSE_SUPPORT", f"User: {target_uid}")

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
            log_audit(current_username, "BAN_USER", f"User: {target_uid}")
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
            log_audit(current_username, "UPDATE_BALANCE", f"User: {target_uid}")
            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=users')
            self.end_headers()

        elif parsed_path.path == "/admin-add":
            title = params.get("title", [""])[0]
            category = params.get("category", ["Genel"])[0]
            try:
                price = float(params.get("price", [0])[0])
            except:
                price = 0.0

            coord_raw = params.get("coords", ["0.0, 0.0"])[0]
            lat, lon = get_district_coord(category)
            try:
                if "," in coord_raw:
                    c_parts = coord_raw.split(",")
                    lat, lon = float(c_parts[0].strip()), float(c_parts[1].strip())
            except:
                pass

            desc = params.get("description", [""])[0]
            
            photo_url = ""
            if file_data and file_name:
                safe_filename = f"{int(datetime.now().timestamp())}_{file_name}"
                saved_path = os.path.join(UPLOAD_DIR, safe_filename)
                with open(saved_path, "wb") as f:
                    f.write(file_data)
                photo_url = f"/{saved_path}"

            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO drops (title, price, photo_ids, description, stock, category, lat, lon) VALUES (?, ?, ?, ?, 1, ?, ?, ?)", (title, price, photo_url, desc, category, lat, lon))
            conn.commit()
            conn.close()
            log_audit(current_username, "ADD_DROP", f"Title: {title}")
            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=passive')
            self.end_headers()

        elif parsed_path.path == "/admin-excel-upload":
            if file_data and file_name:
                try:
                    file_stream = io.BytesIO(file_data)
                    df = None
                    try:
                        file_stream.seek(0)
                        df = pd.read_excel(file_stream, sheet_name=0, engine='openpyxl')
                    except Exception:
                        try:
                            file_stream.seek(0)
                            df = pd.read_excel(file_stream, sheet_name=0)
                        except Exception:
                            success_csv = False
                            for enc in ['utf-8', 'windows-1254', 'latin5', 'cp1254']:
                                try:
                                    file_stream.seek(0)
                                    df = pd.read_csv(file_stream, encoding=enc)
                                    success_csv = True
                                    break
                                except Exception:
                                    continue
                            if not success_csv:
                                raise ValueError("Dosya okunamadı, desteklenmeyen format veya bozuk encoding.")

                    if df is not None:
                        df.columns = df.columns.astype(str).str.strip().str.lower()

                        conn = sqlite3.connect("drop_bot.db")
                        cursor = conn.cursor()
                        count = 0
                        
                        for _, row in df.iterrows():
                            title_val = row.get('title') if 'title' in df.columns else None
                            title = str(title_val).strip() if pd.notna(title_val) else 'Lemon Haze Drop'
                            if not title or title.lower() == 'nan':
                                continue
                                
                            category = 'GENEL'
                            for col_candidate in ['category', 'semt', 'ilçe', 'bolge', 'district']:
                                if col_candidate in df.columns:
                                    val = row[col_candidate]
                                    if pd.notna(val) and str(val).strip() and str(val).lower() != 'nan':
                                        category = str(val).upper().strip()
                                        break
                            
                            raw_price = row.get('price') if 'price' in df.columns else 70.0
                            try:
                                price = float(str(raw_price).replace('$', '').replace(',', '.').strip())
                            except:
                                price = 70.0
                            
                            coord_raw = row.get('coords') if 'coords' in df.columns else '41.0082, 28.9784'
                            lat, lon = get_district_coord(category)
                            try:
                                if pd.notna(coord_raw) and "," in str(coord_raw):
                                    c_parts = str(coord_raw).split(",")
                                    lat, lon = float(c_parts[0].strip()), float(c_parts[1].strip())
                            except:
                                pass

                            desc_val = row.get('description') if 'description' in df.columns else 'Açıklama girilmedi'
                            desc = str(desc_val).strip() if pd.notna(desc_val) else 'Açıklama girilmedi'
                            
                            cursor.execute("""
                                INSERT INTO drops (title, price, photo_ids, description, stock, category, lat, lon) 
                                VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                            """, (title, price, '', desc, category, lat, lon))
                            count += 1
                            
                        conn.commit()
                        conn.close()
                        log_audit(current_username, "EXCEL_UPLOAD", f"Başarıyla {count} ürün yüklendi.")
                        log_panel_event(f"📊 Dosyadan {count} adet toplu ürün başarıyla eklendi.", "success")
                except Exception as e:
                    logging.error(f"Excel upload error: {e}")
                    log_panel_event(f"❌ Excel/Dosya yükleme hatası: {str(e)}", "warning")

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

            description = params.get("description", [""])[0]

            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()

            if file_data and file_name:
                safe_filename = f"{int(datetime.now().timestamp())}_{file_name}"
                saved_path = os.path.join(UPLOAD_DIR, safe_filename)
                with open(saved_path, "wb") as f:
                    f.write(file_data)
                photo_url = f"/{saved_path}"
                cursor.execute("UPDATE drops SET title = ?, price = ?, stock = ?, category = ?, photo_ids = ?, description = ?, lat = ?, lon = ? WHERE id = ?", (title, price, stock, category, photo_url, description, lat, lon, drop_id))
            else:
                cursor.execute("UPDATE drops SET title = ?, price = ?, stock = ?, category = ?, description = ?, lat = ?, lon = ? WHERE id = ?", (title, price, stock, category, description, lat, lon, drop_id))

            conn.commit()
            conn.close()
            log_audit(current_username, "UPDATE_DROP", f"ID: {drop_id}")
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
                    
                    cursor.execute("SELECT referred_by FROM users WHERE user_id = ?", (u_id,))
                    ref_row = cursor.fetchone()
                    if ref_row and ref_row[0] > 0:
                        ref_id = ref_row[0]
                        bonus = float(f_price) * 0.05
                        cursor.execute("UPDATE users SET balance = balance + ?, referral_earnings = referral_earnings + ? WHERE user_id = ?", (bonus, bonus, ref_id))

                    conn.commit()
                    conn.close()
                    log_audit(current_username, "MANUAL_APPROVE", f"Order: {order_id}")

                    secure_link = f"{RENDER_EXTERNAL_URL}/drop/{order_id}"
                    u_lang = get_user_lang(u_id)
                    success_text = t["success_msg"].format(id=order_id, link=secure_link)

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
                    <input type="text" name="username" required placeholder="Kullanıcı Adı (root)">
                    <input type="password" name="password" required placeholder="Şifre (toor)">
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
class AdminAuth(StatesGroup):
    waiting_password = State()

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
    
    args = message.text.split()
    referrer_id = 0
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            potential_ref = int(args[1].replace("ref_", ""))
            if potential_ref != user_id:
                referrer_id = potential_ref
        except:
            pass

    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, referred_by FROM users WHERE user_id = ?", (user_id,))
    existing_user = cursor.fetchone()
    
    if not existing_user:
        cursor.execute("INSERT INTO users (user_id, username, balance, referred_by) VALUES (?, ?, 5.0, ?)", (user_id, message.from_user.username, referrer_id))
        conn.commit()
        if referrer_id > 0:
            try:
                await bot.send_message(referrer_id, f"🎉 **Yeni Referans!** Davet ettiğiniz kullanıcı botumuza katıldı.")
            except:
                pass
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
    await callback.message.edit_text(t["lang_set"])
    await callback.message.answer(t["welcome"], reply_markup=main_keyboard(new_lang), parse_mode="Markdown")

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

    await callback.answer("Blokzincir taranıyor, lütfen bekleyin...", show_alert=True)
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT status, created_at FROM deposits WHERE id = ? AND user_id = ?", (deposit_id, user_id))
    dep = cursor.fetchone()
    if not dep:
        await callback.answer("Kayıt bulunamadı.", show_alert=True)
        conn.close()
        return
    status, created_at_str = dep
    if status == 'completed':
        await callback.answer("Bu işlem zaten onaylanmış.", show_alert=True)
        conn.close()
        return
    if datetime.now() - datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S") > timedelta(minutes=15):
        cursor.execute("UPDATE deposits SET status = 'expired' WHERE id = ?", (deposit_id,))
        conn.commit()
        conn.close()
        await callback.message.edit_text("⏱️ Süre doldu.")
        return

    api_url = f"https://api.trongrid.io/v1/accounts/{CRYPTO_WALLET}/trc20-transfers?contract_address={USDT_CONTRACT}&limit=15"
    verified = False
    try:
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                res_json = json.loads(response.read().decode('utf-8'))
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
        await callback.answer("Transfer henüz algılanmadı, lütfen birkaç saniye sonra tekrar deneyin.", show_alert=True)

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
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, balance) VALUES (?, ?, 5.0)", (user_id, username))
    cursor.execute("INSERT INTO support_messages (user_id, sender, message) VALUES (?, 'user', ?)", (user_id, user_msg))
    conn.commit()
    conn.close()

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Sohbeti İptal Et", callback_data="close_support_chat")]])
    await message.answer(t["support_sent"], reply_markup=kb)

@dp.message(Command("admin"))
async def cmd_admin_start(message: types.Message, state: FSMContext):
    if message.chat.type != "private":
        return
    if is_admin(message.from_user.id):
        await state.set_state(AdminAuth.waiting_password)
        await message.answer("🔒 Lütfen Yönetici Şifresini Giriniz:")

@dp.message(AdminAuth.waiting_password)
async def process_admin_password(message: types.Message, state: FSMContext):
    if message.text.strip() == ADMIN_PASS:
        await state.clear()
        web_panel_url = f"{RENDER_EXTERNAL_URL}/admin-web"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Web Paneline Giriş Yap", url=web_panel_url)],
            [InlineKeyboardButton(text="📊 Satış Raporları", callback_data="stats")]
        ])
        await message.answer("👑 **Gelişmiş Yönetim Paneli**", reply_markup=kb)
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
    
    cursor.execute("SELECT referred_by FROM users WHERE user_id = ?", (user_id,))
    ref_row = cursor.fetchone()
    if ref_row and ref_row[0] > 0:
        ref_id = ref_row[0]
        bonus = float(price) * 0.05
        cursor.execute("UPDATE users SET balance = balance + ?, referral_earnings = referral_earnings + ? WHERE user_id = ?", (bonus, bonus, ref_id))

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
