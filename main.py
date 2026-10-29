# -*- coding: utf-8 -*-
"""
Sorunsuz Çalışan Onaylı Telegram Botu, Gelişmiş Web Yönetim Paneli ve AI Destek Entegrasyonu
"""

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
import aiohttp
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

# AI Support için Gemini API Ayarı (Veritabanından veya varsayılandan alınır)
DEFAULT_GEMINI_API_KEY = "AIzaSy..."

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
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('gemini_api_key', ?)", (DEFAULT_GEMINI_API_KEY,))
    
    conn.commit()
    conn.close()

init_db()

def get_setting(key, default_val=""):
    try:
        conn = sqlite3.connect("drop_bot.db")
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        res = cursor.fetchone()
        conn.close()
        if res and res[0]:
            return res[0]
    except:
        pass
    return default_val

def set_setting(key, value):
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

BOT_TOKEN = get_setting("bot_token", DEFAULT_BOT_TOKEN)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
main_loop = None

# --- GEMINI AI DESTEK FONKSİYONU ---
async def ask_gemini_ai(user_id: int, prompt: str) -> str:
    api_key = get_setting("gemini_api_key", DEFAULT_GEMINI_API_KEY)
    if not api_key or api_key.startswith("AIzaSy..."):
        return "🤖 AI Destek asistanı şu anda yapılandırılmamış. Lütfen canlı destek ekibimize bağlanın."

    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT sender, message FROM support_messages WHERE user_id = ? ORDER BY id DESC LIMIT 6", (user_id,))
    history = cursor.fetchall()
    conn.close()

    system_prompt = (
        "Sen bu otomasyon platformunun profesyonel, yardımsever ve kibar AI Asistanısın. "
        "Kullanıcılara ürünler, bakiye yükleme, sipariş takibi ve konumlar hakkında rehberlik edersin. "
        "Eğer kullanıcı teknik bir sorun yaşarsa veya işlem yapamazsa, onu insan destek ekibine yönlendir."
    )

    contents = [{"role": "user", "parts": [{"text": system_prompt}]}]
    for sender, msg in reversed(history):
        role = "user" if sender == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg}]})
    
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {"contents": contents}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    ai_response = data["candidates"][0]["content"]["parts"][0]["text"]
                    return ai_response
                else:
                    return "🤖 Yapılandırılmış AI yanıt verirken geçici bir hata oluştu. Lütfen canlı desteğe yazın."
    except Exception as e:
        logging.error(f"Gemini API Error: {e}")
        return "🤖 Bağlantı hatası oluştu. Canlı destek ekibimize yazabilirsiniz."

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
        "btn_support": "📞 Destek & AI Asistan",
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
        "support_ask": "🤖 **AI Destek Asistanı Aktif!**\n\nBana merak ettiğin her şeyi sorabilirsin (ürünler, bakiye, siparişler). Canlı ekibe bağlanmak istersen butonu kullanabilirsin:",
        "support_sent": "✅ Mesajınız iletildi.",
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
        "btn_support": "📞 Support & AI Assistant",
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
        "support_ask": "🤖 **AI Support Assistant Active!**\n\nAsk me anything about products, balance or orders.",
        "support_sent": "✅ Message sent.",
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

# --- AI DESTEK BOT ENTEGRASYONU ---
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
async def handle_ai_support_message(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if message.chat.type != "private" or is_user_banned(user_id):
        return
    
    user_text = message.text
    if user_text.startswith("/"):
        return

    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO support_messages (user_id, sender, message) VALUES (?, 'user', ?)", (user_id, user_text))
    conn.commit()
    conn.close()

    wait_msg = await message.answer("🤖 AI Asistan düşünüyor...")
    ai_reply = await ask_gemini_ai(user_id, user_text)

    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO support_messages (user_id, sender, message) VALUES (?, 'ai', ?)", (user_id, ai_reply))
    conn.commit()
    conn.close()

    await wait_msg.delete()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Sohbeti İptal Et", callback_data="close_support_chat")]])
    await message.answer(ai_reply, reply_markup=kb, parse_mode="Markdown")

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

# --- WEB SUNUCUSU & MINI APP (AI CHAT DESTEKLİ) ---
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

        if parsed_path.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Weed Istanbul Server Active!")
            return

        if parsed_path.path == "/miniapp":
            miniapp_html = """
            <!DOCTYPE html>
            <html lang="tr">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Weed Istanbul - Mini App & AI Destek</title>
                <script src="https://telegram.org/js/telegram-web-app.js"></script>
                <style>
                    body { background: #090d16; color: #f8fafc; font-family: sans-serif; margin: 0; padding: 15px; box-sizing: border-box; }
                    .card { background: #111827; padding: 15px; border-radius: 12px; border: 1px solid #1f2937; margin-bottom: 15px; }
                    .chat-box { height: 280px; overflow-y: auto; background: #090d16; padding: 10px; border-radius: 8px; border: 1px solid #374151; margin-bottom: 10px; }
                    .msg { margin-bottom: 8px; padding: 8px 12px; border-radius: 8px; font-size: 13px; max-width: 80%; word-break: break-word; }
                    .msg-user { background: #2563eb; margin-left: auto; color: white; text-align: right; }
                    .msg-ai { background: #334155; margin-right: auto; color: #f8fafc; }
                    input, button { width: 100%; padding: 10px; margin-top: 6px; border-radius: 8px; border: none; box-sizing: border-box; font-size: 13px; }
                    input { background: #090d16; color: white; border: 1px solid #374151; }
                    button { background: #2563eb; color: white; font-weight: bold; cursor: pointer; }
                    button:hover { background: #1d4ed8; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h3 style="color: #38bdf8; margin-top:0;">🤖 AI Destek Asistanı</h3>
                    <div class="chat-box" id="chatBox">
                        <div class="msg msg-ai">Merhaba! Size bakiye, siparişler ve ürünler hakkında nasıl yardımcı olabilirim?</div>
                    </div>
                    <input type="text" id="userInput" placeholder="Mesajınızı yazın...">
                    <button onclick="sendAIChat()">Gönder</button>
                </div>
                <script>
                    const tg = window.Telegram.WebApp;
                    tg.expand();
                    let userId = tg.initDataUnsafe?.user?.id || 12345;

                    async function sendAIChat() {
                        const input = document.getElementById('userInput');
                        const chatBox = document.getElementById('chatBox');
                        const text = input.value.trim();
                        if(!text) return;

                        chatBox.innerHTML += `<div class="msg msg-user">${text}</div>`;
                        input.value = '';
                        chatBox.scrollTop = chatBox.scrollHeight;

                        try {
                            const res = await fetch('/api/miniapp-ai-chat', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({user_id: userId, message: text})
                            });
                            const data = await res.json();
                            chatBox.innerHTML += `<div class="msg msg-ai">${data.reply}</div>`;
                            chatBox.scrollTop = chatBox.scrollHeight;
                        } catch(e) {
                            chatBox.innerHTML += `<div class="msg msg-ai">Bağlantı hatası oluştu.</div>`;
                        }
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

        if parsed_path.path == "/api/miniapp-ai-chat":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                uid = data.get("user_id", 12345)
                msg = data.get("message", "")

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                reply = loop.run_until_complete(ask_gemini_ai(uid, msg))
                loop.close()

                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"reply": reply}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == "/api/miniapp-ai-chat":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                uid = data.get("user_id", 12345)
                msg = data.get("message", "")

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                reply = loop.run_until_complete(ask_gemini_ai(uid, msg))
                loop.close()

                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"reply": reply}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return
        self.send_response(404)
        self.end_headers()

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SecureDropHandler)
    server.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

async def main():
    global main_loop
    main_loop = asyncio.get_running_loop()
    asyncio.create_task(auto_backup_task())
    asyncio.create_task(background_payment_worker())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
