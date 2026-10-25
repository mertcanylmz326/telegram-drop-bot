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

# Üçlü Cüzdan Yapısı (Güvenlik ve İzolasyon)
WALLET_CONFIG = {
    "weedboot": "TMDAC83GTrxDCQiQBCEEL11CdHBYPSMpjH",  # Operasyon / Bot Cüzdanı
    "giris": "TVsUkivFz217G7yAZ9w9PDj4WphJZty1tY",      # Ana Kasa / Depo Cüzdanı
    "cikis": "TMxF3AFaqpHgRF5S8RkmZtAkwzzYxgwzLn"       # Aracı / Buffer Cüzdanı
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
        "welcome": "👋 Merhaba! Güvenli otomatik teslimat Mini App mağazamıza hoş geldiniz. Aşağıdaki butona tıklayarak dükkanı açabilirsiniz:",
        "lang_set": "✅ Dil Türkçe olarak ayarlandı.",
        "btn_webapp": "🛍️ Mağazayı Aç (Mini App)",
        "btn_faq": "❓ Nasıl Çalışır? (SSS)",
        "btn_support": "📞 Canlı Destek",
        "btn_lang": "🌐 Dil Değiştir",
        "support_ask": "📞 Destek mesajınızı yazın, admin ekibine ve web paneline iletilsin:",
        "support_sent": "✅ Destek mesajınız iletildi. En kısa sürede yanıt alacaksınız.",
        "banned": "❌ Erişiminiz engellenmiştir."
    },
    "en": {
        "welcome": "👋 Hello! Welcome to our secure automated delivery Mini App store. Click the button below to open the shop:",
        "lang_set": "✅ Language set to English.",
        "btn_webapp": "🛍️ Open Store (Mini App)",
        "btn_faq": "❓ How It Works (FAQ)",
        "btn_support": "📞 Live Support",
        "btn_lang": "🌐 Change Language",
        "support_ask": "📞 Type your support message to send to the admin team:",
        "support_sent": "✅ Your support message has been sent to the admin team.",
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

def get_user_profile(user_id: int):
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance, total_spent FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    if res:
        return res[0] or 0.0, res[1] or 0.0
    return 0.0, 0.0

def update_user_balance(user_id: int, amount: float):
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

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

def get_wallet_balances():
    balances = {}
    for key, addr in WALLET_CONFIG.items():
        usdt_bal = 0.0
        trx_bal = 0.0
        try:
            import urllib.request
            import json
            url = f"https://api.trongrid.io/v1/accounts/{addr}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    acc_data = data.get("data", [])
                    if acc_data:
                        trx_bal = acc_data[0].get("balance", 0) / 1000000.0
                        trc20 = acc_data[0].get("trc20", [])
                        for token in trc20:
                            if USDT_CONTRACT in token:
                                usdt_bal = float(token[USDT_CONTRACT]) / 1000000.0
                                break
        except Exception as e:
            logging.error(e)
        balances[key] = {"usdt": usdt_bal, "trx": trx_bal}
    return balances

async def check_user_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        if member.status in ["left", "kicked"]:
            return False
        return True
    except Exception as e:
        logging.error(e)
        return True

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

async def check_expired_orders_task():
    while True:
        await asyncio.sleep(60)
        try:
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            expiry_limit = datetime.now() - timedelta(minutes=15)
            cursor.execute("SELECT id, drop_id FROM orders WHERE status = 'pending' AND created_at < ?", (expiry_limit.strftime("%Y-%m-%d %H:%M:%S"),))
            expired_orders = cursor.fetchall()
            for ord_id, drp_id in expired_orders:
                cursor.execute("UPDATE orders SET status = 'expired' WHERE id = ?", (ord_id,))
                cursor.execute("UPDATE drops SET stock = stock + 1, is_sold = 0 WHERE id = ?", (drp_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(e)

# --- 🎄 TELEGRAM MINI APP & WEB SUNUCUSU ---
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
            self.wfile.write(b"Weed Istanbul Mini App Server Active!")
            return

        # --- TELEGRAM MINI APP (MÜŞTERİ MAĞAZA ARAYÜZÜ) ---
        if parsed_path.path == "/webapp":
            user_id = query_params.get("user_id", ["0"])[0]
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("SELECT balance, total_spent FROM users WHERE user_id = ?", (user_id,))
            u_row = cursor.fetchone()
            bal = u_row[0] if u_row and u_row[0] is not None else 0.0
            spent = u_row[1] if u_row and u_row[1] is not None else 0.0
            is_vip = spent >= 100

            # Kategoriler ve Ürünler
            cursor.execute("SELECT DISTINCT category FROM drops WHERE is_sold = 0 AND stock > 0")
            categories = [r[0] for r in cursor.fetchall()]

            cursor.execute("SELECT id, title, price, stock, category, photo_ids, description FROM drops WHERE is_sold = 0 AND stock > 0")
            drops = cursor.fetchall()

            # Referanslar
            cursor.execute("SELECT customer_name, rating, photo_url, comment, created_at FROM testimonials ORDER BY id DESC LIMIT 5")
            testimonials = cursor.fetchall()

            # Siparişler
            cursor.execute("""
                SELECT orders.id, drops.title, orders.final_price, orders.status, orders.created_at 
                FROM orders JOIN drops ON orders.drop_id = drops.id 
                WHERE orders.user_id = ? ORDER BY orders.id DESC
            """, (user_id,))
            orders = cursor.fetchall()
            conn.close()

            drops_html = ""
            for d in drops:
                d_id, title, price, stock, cat, photo, desc = d
                eff_price = round(price * 0.9, 2) if is_vip else price
                price_display = f"<span style='text-decoration:line-through; color:#94a3b8; font-size:13px;'>{price} USDT</span> <b style='color:#10b981; font-size:18px;'>{eff_price} USDT</b>" if is_vip else f"<b style='color:#10b981; font-size:18px;'>{price} USDT</b>"
                img_tag = f"<img src='{photo}' style='width:100%; height:140px; object-fit:cover; border-radius:10px; margin-bottom:10px;' />" if photo else ""
                
                drops_html += f"""
                <div class="product-card" data-category="{cat or 'Genel'}">
                    {img_tag}
                    <h3 style="margin:0 0 5px 0; color:#f8fafc; font-size:16px;">{title}</h3>
                    <p style="margin:0 0 8px 0; font-size:12px; color:#38bdf8;">🏙️ {cat or 'Genel'} | Stok: {stock}</p>
                    <p style="margin:0 0 12px 0; font-size:13px; color:#94a3b8;">{desc or 'Özel güvenli teslimat drop.'}</p>
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>{price_display}</div>
                        <button onclick="buyProduct({d_id}, {eff_price})" class="buy-btn">Satın Al</button>
                    </div>
                </div>
                """

            tests_html = ""
            for tr in testimonials:
                c_name, rating, p_url, comment, c_date = tr
                stars = "⭐" * rating
                p_tag = f"<img src='{p_url}' style='width:100%; height:120px; object-fit:cover; border-radius:8px; margin-top:8px;' />" if p_url else ""
                tests_html += f"""
                <div class="testi-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:5px;">
                        <b>{c_name}</b>
                        <span style="font-size:12px;">{stars}</span>
                    </div>
                    <p style="margin:0; font-size:13px; color:#cbd5e1;">"{comment}"</p>
                    {p_tag}
                </div>
                """

            orders_html = ""
            for o in orders:
                o_id, title, f_price, status, date = o
                st_badge = "<span style='color:#10b981;'>Tamamlandı</span>" if status == 'completed' else ("<span style='color:#ef4444;'>Süresi Doldu</span>" if status == 'expired' else "<span style='color:#f59e0b;'>Ödeme Bekliyor</span>")
                link_btn = f"<a href='/drop/{o_id}' target='_blank' class='loc-btn'>Konumu Aç</a>" if status == 'completed' else ""
                orders_html += f"""
                <div class="order-item">
                    <div><b>#{o_id}</b> - {title} ({f_price} USDT)</div>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:5px; font-size:12px;">
                        <span>{st_badge} ({date})</span>
                        {link_btn}
                    </div>
                </div>
                """

            cats_filter_html = "<button class='cat-btn active' onclick='filterCat(\"all\")'>Tümü</button>"
            for c in categories:
                cats_filter_html += f"<button class='cat-btn' onclick='filterCat(\"{c}\")'>{c}</button>"

            webapp_html = f"""
            <!DOCTYPE html>
            <html lang="tr">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Weed Istanbul Mini App</title>
                <script src="https://telegram.org/js/telegram-web-app.js"></script>
                <style>
                    body {{
                        background: #050a0e;
                        color: #f8fafc;
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        margin: 0;
                        padding: 15px;
                        box-sizing: border-box;
                    }}
                    .header {{
                        background: rgba(15, 23, 42, 0.85);
                        padding: 15px;
                        border-radius: 14px;
                        border: 1px solid rgba(16, 185, 129, 0.3);
                        margin-bottom: 20px;
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                    }}
                    .nav-tabs {{
                        display: flex;
                        gap: 8px;
                        margin-bottom: 20px;
                        overflow-x: auto;
                        padding-bottom: 5px;
                    }}
                    .tab-btn {{
                        background: #1e293b;
                        color: #94a3b8;
                        border: none;
                        padding: 8px 14px;
                        border-radius: 8px;
                        font-weight: bold;
                        cursor: pointer;
                        font-size: 13px;
                        white-space: nowrap;
                    }}
                    .tab-btn.active {{
                        background: #10b981;
                        color: white;
                    }}
                    .section {{ display: none; }}
                    .section.active {{ display: block; }}
                    .product-card, .testi-card, .order-item {{
                        background: rgba(15, 23, 42, 0.75);
                        padding: 15px;
                        border-radius: 12px;
                        border: 1px solid rgba(255, 255, 255, 0.08);
                        margin-bottom: 15px;
                    }}
                    .buy-btn, .loc-btn {{
                        background: #10b981;
                        color: white;
                        border: none;
                        padding: 8px 14px;
                        border-radius: 6px;
                        font-weight: bold;
                        cursor: pointer;
                        font-size: 13px;
                        text-decoration: none;
                    }}
                    .loc-btn {{ background: #38bdf8; }}
                    .cat-container {{
                        display: flex;
                        gap: 8px;
                        margin-bottom: 15px;
                        overflow-x: auto;
                    }}
                    .cat-btn {{
                        background: #0f172a;
                        color: #94a3b8;
                        border: 1px solid #334155;
                        padding: 6px 12px;
                        border-radius: 6px;
                        cursor: pointer;
                        font-size: 12px;
                        white-space: nowrap;
                    }}
                    .cat-btn.active {{
                        background: rgba(16, 185, 129, 0.2);
                        color: #10b981;
                        border-color: #10b981;
                    }}
                </style>
            </head>
            <body>
                <script>
                    let tg = window.Telegram.WebApp;
                    tg.expand();
                </script>

                <div class="header">
                    <div>
                        <h3 style="margin:0; color:#10b981;">🌿 Weed Istanbul</h3>
                        <p style="margin:2px 0 0 0; font-size:12px; color:#94a3b8;">{"👑 VIP Müşteri (%10 İndirimli)" if is_vip else "⭐ Standart Üye"}</p>
                    </div>
                    <div style="text-align:right;">
                        <span style="font-size:12px; color:#94a3b8; display:block;">Bakiye</span>
                        <b style="color:#38bdf8; font-size:16px;">{bal} USDT</b>
                    </div>
                </div>

                <div class="nav-tabs">
                    <button class="tab-btn active" onclick="switchTab('shop')">🛍️ Mağaza</button>
                    <button class="tab-btn" onclick="switchTab('orders')">📦 Siparişlerim</button>
                    <button class="tab-btn" onclick="switchTab('refs')">⭐ Referanslar</button>
                </div>

                <!-- MAĞAZA SEKMESİ -->
                <div id="shop" class="section active">
                    <div class="cat-container">
                        {cats_filter_html}
                    </div>
                    <div id="product-list">
                        {drops_html if drops_html else "<p style='text-align:center; color:#64748b;'>Şu an aktif stok bulunmuyor.</p>"}
                    </div>
                </div>

                <!-- SİPARİŞLERİM -->
                <div id="orders" class="section">
                    <h3 style="color:#10b981; margin-top:0;">📦 Geçmiş Siparişler</h3>
                    {orders_html if orders_html else "<p style='text-align:center; color:#64748b;'>Henüz siparişiniz yok.</p>"}
                </div>

                <!-- REFERANSLAR -->
                <div id="refs" class="section">
                    <h3 style="color:#10b981; margin-top:0;">⭐ Müşteri Yorumları</h3>
                    {tests_html if tests_html else "<p style='text-align:center; color:#64748b;'>Henüz yorum eklenmemiş.</p>"}
                </div>

                <script>
                    function switchTab(tabId) {{
                        document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
                        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                        document.getElementById(tabId).classList.add('active');
                        event.currentTarget.classList.add('active');
                    }}

                    function filterCat(cat) {{
                        document.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
                        event.currentTarget.classList.add('active');
                        document.querySelectorAll('.product-card').forEach(card => {{
                            if (cat === 'all' || card.dataset.category === cat) {{
                                card.style.display = 'block';
                            }} else {{
                                card.style.display = 'none';
                            }}
                        }});
                    }}

                    function buyProduct(dropId, price) {{
                        tg.openInvoice("pay_" + dropId, function(status) {{}});
                        alert("Satın alma talebi alındı! Bot sohbetine dönerek ödeme yöntemini seçebilirsiniz.");
                    }}
                </script>
            </body>
            </html>
            """
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(webapp_html.encode("utf-8"))
            return

        # --- ADMIN PANEL & DİĞER SAYFALAR (Aynen korundu) ---
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
            rev_res = cursor.fetchone()[0]
            total_revenue = rev_res if rev_res is not None else 0.0

            content_html = ""
            if tab == "home":
                cursor.execute("SELECT message, log_type, created_at FROM panel_logs ORDER BY id DESC LIMIT 10")
                logs = cursor.fetchall()
                logs_html = ""
                for l in logs:
                    msg, l_type, l_date = l
                    badge_color = "#ef4444" if l_type == "warning" else ("#10b981" if l_type == "success" else "#38bdf8")
                    logs_html += f"""
                    <div style="background: rgba(15, 23, 42, 0.7); padding: 12px 15px; border-radius: 10px; margin-bottom: 10px; border-left: 4px solid {badge_color}; font-size: 13px; backdrop-filter: blur(5px);">
                        <span style="color: #64748b; font-size: 11px; display: block; margin-bottom: 2px;">{l_date}</span>
                        {msg}
                    </div>
                    """

                w_bals = get_wallet_balances()

                content_html = f"""
                <div class="stats-grid">
                    <div class="card neon-green"><h3>🎅 TOTAL REVENUE</h3><p>{total_revenue} USDT</p></div>
                    <div class="card neon-red"><h3>🎄 ACTIVE STOCK</h3><p>{total_active_stock} Pcs</p></div>
                    <div class="card neon-gold"><h3>🌿 PRODUCT VARIETY</h3><p>{total_drops}</p></div>
                </div>

                <div class="form-box" style="border: 1px solid rgba(16, 185, 129, 0.4); margin-bottom: 30px;">
                    <h2>🔒 3'lü Cüzdan İzolasyon & Canlı Bakiye Durumu</h2>
                    <ul style="list-style: none; padding: 0; margin: 0; font-size: 14px;">
                        <li style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                            <div>🟢 <b>weedboot (Bot / Operasyon):</b> <code style="color: #38bdf8;">{WALLET_CONFIG['weedboot']}</code></div>
                            <div style="background: rgba(16, 185, 129, 0.15); padding: 4px 10px; border-radius: 6px; color: #10b981; font-weight: bold;"><b>{w_bals.get('weedboot', {}).get('usdt', 0.0)} USDT</b> | {w_bals.get('weedboot', {}).get('trx', 0.0)} TRX</div>
                        </li>
                        <li style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                            <div>🔵 <b>Giriş (Ana Depo / Kasa):</b> <code style="color: #38bdf8;">{WALLET_CONFIG['giris']}</code></div>
                            <div style="background: rgba(56, 189, 248, 0.15); padding: 4px 10px; border-radius: 6px; color: #38bdf8; font-weight: bold;"><b>{w_bals.get('giris', {}).get('usdt', 0.0)} USDT</b> | {w_bals.get('giris', {}).get('trx', 0.0)} TRX</div>
                        </li>
                        <li style="padding: 10px 0; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                            <div>🟡 <b>Çıkış (Aracı / Buffer):</b> <code style="color: #38bdf8;">{WALLET_CONFIG['cikis']}</code></div>
                            <div style="background: rgba(245, 158, 11, 0.15); padding: 4px 10px; border-radius: 6px; color: #f59e0b; font-weight: bold;"><b>{w_bals.get('cikis', {}).get('usdt', 0.0)} USDT</b> | {w_bals.get('cikis', {}).get('trx', 0.0)} TRX</div>
                        </li>
                    </ul>
                </div>
                """
            elif tab == "testimonials":
                cursor.execute("SELECT id, customer_name, rating, photo_url, comment, created_at FROM testimonials ORDER BY id DESC")
                tests = cursor.fetchall()
                rows = ""
                for tr in tests:
                    t_id, c_name, rating, p_url, c_text, c_date = tr
                    stars = "⭐" * rating
                    img_preview = f"<img src='{p_url}' style='width:50px; height:50px; object-fit:cover; border-radius:6px;' />" if p_url else "Görsel Yok"
                    del_btn = f"""
                    <form action="/admin-del-testimonial" method="POST" style="margin:0;">
                        <input type="hidden" name="id" value="{t_id}">
                        <button type="submit" style="background:#ef4444; padding:6px 10px; font-size:11px; width:auto;">Sil</button>
                    </form>
                    """
                    rows += f"<tr><td>#{t_id}</td><td><b>{c_name}</b></td><td>{stars} ({rating}/5)</td><td>{img_preview}</td><td style='max-width:250px;'>{c_text}</td><td>{c_date}</td><td>{del_btn}</td></tr>"

                content_html = f"""
                <div class="form-box">
                    <h2>➕ Yeni Müşteri Yorumu / Referans Ekle</h2>
                    <form action="/admin-add-testimonial" method="POST">
                        <label>Müşteri Adı / Rumuz:</label>
                        <input type="text" name="customer_name" required placeholder="Örn: Burak K. (@burak...)">
                        <label>Yıldız Puanı (1 - 5):</label>
                        <input type="number" name="rating" min="1" max="5" value="5" required>
                        <label>Ürün / Kutu Fotoğrafı URL'si:</label>
                        <input type="text" name="photo_url" placeholder="https://imgur.com/...">
                        <label>Müşteri Yorumu:</label>
                        <textarea name="comment" rows="3" required placeholder="Saniyeler içinde teslimat..."></textarea>
                        <button type="submit" style="margin-top: 15px;">Yorumu Ekle & Yayınla</button>
                    </form>
                </div>
                <div class="table-box">
                    <h2>⭐ Yayınlanan Müşteri Referansları</h2>
                    <table>
                        <tr><th>ID</th><th>Müşteri</th><th>Puan</th><th>Fotoğraf</th><th>Yorum</th><th>Tarih</th><th>İşlem</th></tr>
                        {rows if rows else "<tr><td colspan='7' style='text-align:center;'>Henüz müşteri yorumu eklenmemiş.</td></tr>"}
                    </table>
                </div>
                """
            elif tab == "support":
                cursor.execute("SELECT id, user_id, username, message, status, created_at FROM support_tickets ORDER BY id DESC")
                tickets = cursor.fetchall()
                rows = ""
                for t_item in tickets:
                    t_id, t_uid, t_uname, t_msg, t_status, t_date = t_item
                    uname_str = f"@{t_uname}" if t_uname else "N/A"
                    status_badge = "<span style='color:#10b981; font-weight:bold; background:rgba(16,185,129,0.2); padding:3px 8px; border-radius:6px;'>OPEN</span>" if t_status == 'open' else "<span style='color:#64748b; font-weight:bold; background:rgba(100,116,139,0.2); padding:3px 8px; border-radius:6px;'>CLOSED</span>"
                    reply_form = f"""
                    <form action="/admin-support-reply" method="POST" style="margin:0; display:flex; gap:8px; align-items:center;">
                        <input type="hidden" name="ticket_id" value="{t_id}">
                        <input type="hidden" name="user_id" value="{t_uid}">
                        <input type="text" name="reply_text" placeholder="Yanıtını yaz..." required style="margin:0; padding:6px; font-size:12px; height:32px;">
                        <button type="submit" style="background:#10b981; padding:6px 12px; font-size:12px; width:auto; height:32px; line-height:12px;">Gönder</button>
                    </form>
                    """
                    rows += f"<tr><td>#{t_id}</td><td>{t_uid} ({uname_str})</td><td style='max-width:250px; word-break:break-all;'>{t_msg}</td><td>{t_date}</td><td>{status_badge}</td><td>{reply_form}</td></tr>"

                content_html = f"""
                <div class="table-box">
                    <h2>💬 Canlı Destek CRM Paneli</h2>
                    <table>
                        <tr><th>Ticket ID</th><th>Kullanıcı</th><th>Mesaj</th><th>Tarih</th><th>Durum</th><th>İşlem</th></tr>
                        {rows if rows else "<tr><td colspan='6' style='text-align:center;'>Aktif destek talebi bulunmuyor.</td></tr>"}
                    </table>
                </div>
                """
            elif tab == "users":
                cursor.execute("SELECT user_id, username, is_banned, language, balance, total_spent FROM users ORDER BY user_id DESC")
                users_list = cursor.fetchall()
                rows = ""
                for u in users_list:
                    uid, uname, is_b, u_lang, u_bal, u_spent = u
                    username_str = f"@{uname}" if uname else "N/A"
                    status_badge = "<span style='color:#ef4444; font-weight:bold; background:rgba(239,68,68,0.2); padding:3px 8px; border-radius:6px;'>BANNED</span>" if is_b == 1 else "<span style='color:#10b981; font-weight:bold; background:rgba(16,185,129,0.2); padding:3px 8px; border-radius:6px;'>ACTIVE</span>"
                    vip_badge = "👑 <b>VIP</b>" if (u_spent or 0) >= 100 else "⭐ Standart"
                    ban_btn = f"""
                    <form action="/admin-ban" method="POST" style="margin:0; display:inline;">
                        <input type="hidden" name="user_id" value="{uid}">
                        <input type="hidden" name="action" value="{'unban' if is_b == 1 else 'ban'}">
                        <button type="submit" style="background:{'#10b981' if is_b == 1 else '#ef4444'}; padding:6px 12px; font-size:11px; width:auto; border-radius:6px;">
                            {'Unban' if is_b == 1 else 'Ban'}
                        </button>
                    </form>
                    """
                    bal_form = f"""
                    <form action="/admin-balance" method="POST" style="margin:0; display:flex; gap:5px; align-items:center;">
                        <input type="hidden" name="user_id" value="{uid}">
                        <input type="number" step="0.1" name="amount" placeholder="USDT" style="width:70px; padding:5px; margin:0; font-size:12px; height:28px;">
                        <button type="submit" name="op" value="add" style="background:#10b981; padding:4px 8px; font-size:11px; width:auto; height:28px; line-height:10px;">+</button>
                        <button type="submit" name="op" value="sub" style="background:#ef4444; padding:4px 8px; font-size:11px; width:auto; height:28px; line-height:10px;">-</button>
                    </form>
                    """
                    rows += f"<tr><td>{uid}</td><td>{username_str}</td><td>{vip_badge}</td><td><b style='color:#38bdf8; font-size:15px;'>{u_bal} USDT</b></td><td>{u_spent or 0} USDT</td><td>{bal_form}</td><td>{status_badge}</td><td>{ban_btn}</td></tr>"

                content_html = f"""
                <div class="table-box">
                    <h2>🎅 CRM & VIP Yönetimi</h2>
                    <table>
                        <tr><th>ID</th><th>Username</th><th>Statü</th><th>Bakiye</th><th>Harcama</th><th>Düzenle</th><th>Durum</th><th>İşlem</th></tr>
                        {rows if rows else "<tr><td colspan='8' style='text-align:center;'>Kayıtlı kullanıcı yok.</td></tr>"}
                    </table>
                </div>
                """
            elif tab == "active":
                cursor.execute("""
                    SELECT orders.id, users.username, drops.title, orders.final_price, orders.status, orders.created_at 
                    FROM orders JOIN drops ON orders.drop_id = drops.id 
                    LEFT JOIN users ON orders.user_id = users.user_id
                    WHERE orders.status = 'completed' ORDER BY orders.id DESC
                """)
                orders = cursor.fetchall()
                rows = ""
                for o in orders:
                    o_id, uname, title, f_price, status, date = o
                    username_str = f"@{uname}" if uname else "Bulunmuyor"
                    rows += f"<tr><td>#{o_id}</td><td>{username_str}</td><td>{title}</td><td>{f_price} USDT</td><td>🟢 Tamamlandı</td><td>{date}</td></tr>"
                content_html = f"""
                <div class="table-box">
                    <h2>🟢 Aktif / Tamamlanan Siparişler</h2>
                    <table>
                        <tr><th>ID</th><th>Kullanıcı</th><th>Ürün</th><th>Tutar</th><th>Durum</th><th>Tarih</th></tr>
                        {rows if rows else "<tr><td colspan='6' style='text-align:center;'>Tamamlanan sipariş yok.</td></tr>"}
                    </table>
                </div>
                """
            elif tab == "pending":
                cursor.execute("""
                    SELECT orders.id, users.username, drops.title, orders.final_price, orders.created_at 
                    FROM orders JOIN drops ON orders.drop_id = drops.id 
                    LEFT JOIN users ON orders.user_id = users.user_id
                    WHERE orders.status = 'pending' ORDER BY orders.id DESC
                """)
                pending_orders = cursor.fetchall()
                rows = ""
                for o in pending_orders:
                    o_id, uname, title, f_price, date = o
                    username_str = f"@{uname}" if uname else "Bulunmuyor"
                    rows += f"""
                    <tr>
                        <td>#{o_id}</td><td>{username_str}</td><td>{title}</td><td>{f_price} USDT</td><td>{date}</td>
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
                    <h2>⏳ Bekleyen Siparişler</h2>
                    <table>
                        <tr><th>ID</th><th>Kullanıcı</th><th>Ürün</th><th>Tutar</th><th>Tarih</th><th>İşlem</th></tr>
                        {rows if rows else "<tr><td colspan='6' style='text-align:center;'>Bekleyen sipariş yok.</td></tr>"}
                    </table>
                </div>
                """
            elif tab == "passive":
                cursor.execute("SELECT id, title, price, stock, category, description, location_url FROM drops WHERE is_sold = 0")
                drops = cursor.fetchall()
                rows = ""
                for d in drops:
                    d_id, title, price, stock, cat, desc, loc = d
                    rows += f"<tr><td>#{d_id}</td><td>{title}</td><td>{cat or 'Genel'}</td><td>{price} USDT</td><td>{stock} Adet</td><td><a href='/admin-edit?id={d_id}' class='action-btn edit-btn'>Düzenle</a></td></tr>"
                content_html = f"""
                <div class="table-box">
                    <h2>📦 Pasif / Stoktaki Ürünler</h2>
                    <table>
                        <tr><th>ID</th><th>Başlık</th><th>Bölge</th><th>Fiyat</th><th>Stok</th><th>İşlem</th></tr>
                        {rows if rows else "<tr><td colspan='6' style='text-align:center;'>Stokta ürün yok.</td></tr>"}
                    </table>
                </div>
                """
            elif tab == "add":
                content_html = """
                <div class="form-box">
                    <h2>➕ Yeni Drop Ekle</h2>
                    <form action="/admin-add" method="POST" id="addForm">
                        <label>Ürün Başlığı:</label>
                        <input type="text" name="title" required placeholder="Örn: Amnesia Haze">
                        <label>Semt / Şehir (Kategori):</label>
                        <input type="text" name="category" required placeholder="Örn: Kadıköy">
                        <label>Fiyat (USDT):</label>
                        <input type="number" step="0.1" name="price" required placeholder="65">
                        <label>Stok Adedi:</label>
                        <input type="number" name="count" id="countInput" value="1" min="1" max="30" required onchange="generateFields()">
                        <div id="dynamicFields"></div>
                        <button type="submit" style="margin-top: 20px;">Stoğa Ekle</button>
                    </form>
                </div>
                <script>
                    function generateFields() {
                        const count = document.getElementById('countInput').value;
                        const container = document.getElementById('dynamicFields');
                        container.innerHTML = '';
                        for (let i = 1; i <= count; i++) {
                            container.innerHTML += `
                                <div style="background: rgba(15, 23, 42, 0.8); padding: 15px; border-radius: 8px; margin-top: 15px; border: 1px solid #1e293b;">
                                    <h4 style="color: #10b981; margin-top: 0;">📍 Drop #${i} Detayları</h4>
                                    <label>Google Maps Konum Linki:</label>
                                    <input type="text" name="location_${i}" required placeholder="https://maps.app.goo.gl/...">
                                    <label>Fotoğraf URL'si:</label>
                                    <input type="text" name="photo_${i}" placeholder="https://...">
                                    <label>Açıklama / İpucu:</label>
                                    <textarea name="description_${i}" rows="2" required placeholder="Bina arkasında..."></textarea>
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
                cursor.execute("SELECT title, price, stock, category, location_url, photo_ids, description FROM drops WHERE id = ?", (edit_id,))
                drop_data = cursor.fetchone()
                if drop_data:
                    e_title, e_price, e_stock, e_cat, e_loc, e_photo, e_desc = drop_data
                    edit_form_html = f"""
                    <div class="form-box" style="border: 2px solid #10b981; margin-bottom: 30px;">
                        <h2>✏️ Ürün Düzenle (ID: #{edit_id})</h2>
                        <form action="/admin-update" method="POST">
                            <input type="hidden" name="id" value="{edit_id}">
                            <label>Ürün Başlığı:</label>
                            <input type="text" name="title" value="{e_title}" required>
                            <label>Semt:</label>
                            <input type="text" name="category" value="{e_cat or 'Genel'}" required>
                            <label>Fiyat:</label>
                            <input type="number" step="0.1" name="price" value="{e_price}" required>
                            <label>Stok:</label>
                            <input type="number" name="stock" value="{e_stock}" required>
                            <label>Maps Linki:</label>
                            <input type="text" name="location" value="{e_loc}" required>
                            <label>Fotoğraf URL:</label>
                            <input type="text" name="photo" value="{e_photo}">
                            <label>Açıklama:</label>
                            <textarea name="description" rows="3" required>{e_desc}</textarea>
                            <button type="submit" style="background: #10b981;">Güncellemeyi Kaydet</button>
                        </form>
                    </div>
                    """

            conn.close()

            dashboard_html = f"""
            <!DOCTYPE html>
            <html lang="tr">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>🎄 Weed Istanbul Christmas Panel 🌿</title>
                <style>
                    body {{
                        background: #050a0e url('https://images.unsplash.com/photo-1543589077-47d59746c2a4?auto=format&fit=crop&w=1920&q=80') no-repeat center center fixed;
                        background-size: cover; color: #f8fafc; font-family: -apple-system, sans-serif; margin: 0; display: flex; min-height: 100vh; position: relative; overflow-x: hidden;
                    }}
                    body::before {{ content: ""; position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: rgba(5, 10, 14, 0.88); z-index: 0; }}
                    #snowflake-canvas {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 9999; }}
                    .sidebar {{ width: 270px; background: rgba(10, 18, 26, 0.85); border-right: 1px solid rgba(16, 185, 129, 0.2); display: flex; flex-direction: column; padding: 25px 18px; box-sizing: border-box; z-index: 2; backdrop-filter: blur(12px); }}
                    .sidebar .brand {{ font-size: 22px; font-weight: 900; color: #10b981; text-align: center; margin-bottom: 30px; }}
                    .sidebar a {{ background: transparent; color: #94a3b8; padding: 12px 16px; border-radius: 10px; text-decoration: none; font-weight: 600; font-size: 14px; margin-bottom: 8px; display: block; }}
                    .sidebar a.active, .sidebar a:hover {{ background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.4); }}
                    .logout-link {{ background: rgba(239, 68, 68, 0.2) !important; color: #ef4444 !important; margin-top: auto; text-align: center; }}
                    .main-content {{ flex: 1; padding: 35px; box-sizing: border-box; overflow-y: auto; max-width: 1200px; z-index: 2; }}
                    .header-title {{ color: #f8fafc; font-size: 26px; font-weight: 800; margin-top: 0; margin-bottom: 30px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 15px; display: flex; justify-content: space-between; align-items: center; }}
                    .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin-bottom: 30px; }}
                    .card {{ background: rgba(15, 23, 42, 0.75); padding: 22px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.08); text-align: center; backdrop-filter: blur(8px); }}
                    .card.neon-green {{ border-color: rgba(16, 185, 129, 0.4); }} .card.neon-red {{ border-color: rgba(239, 68, 68, 0.4); }} .card.neon-gold {{ border-color: rgba(245, 158, 11, 0.4); }}
                    .card h3 {{ margin: 0 0 10px 0; color: #94a3b8; font-size: 13px; }} .card p {{ margin: 0; font-size: 28px; font-weight: 900; }}
                    .form-box, .table-box {{ background: rgba(15, 23, 42, 0.75); padding: 25px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.08); margin-bottom: 30px; backdrop-filter: blur(8px); }}
                    input, textarea {{ width: 100%; padding: 12px; margin: 8px 0 16px 0; background: rgba(5, 10, 14, 0.7); border: 1px solid rgba(255,255,255,0.15); border-radius: 8px; color: white; box-sizing: border-box; }}
                    button {{ background: #10b981; color: white; padding: 12px 20px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%; font-size: 14px; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                    th, td {{ padding: 12px 14px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 14px; }}
                    th {{ color: #94a3b8; font-size: 12px; text-transform: uppercase; }}
                    .action-btn {{ padding: 6px 12px; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: bold; }}
                    .edit-btn {{ background: #d97706; color: white; }}
                </style>
            </head>
            <body>
                <canvas id="snowflake-canvas"></canvas>
                <div class="sidebar">
                    <div class="brand">🎄 Weed Istanbul 🌿</div>
                    <a href="/admin-web?tab=home" class="{"active" if tab == "home" else ""}">🏠 Home</a>
                    <a href="/admin-web?tab=testimonials" class="{"active" if tab == "testimonials" else ""}">⭐ Testimonials</a>
                    <a href="/admin-web?tab=support" class="{"active" if tab == "support" else ""}">💬 Live Support</a>
                    <a href="/admin-web?tab=active" class="{"active" if tab == "active" else ""}">🟢 Active Orders</a>
                    <a href="/admin-web?tab=pending" class="{"active" if tab == "pending" else ""}">⏳ Pending</a>
                    <a href="/admin-web?tab=passive" class="{"active" if tab in ["passive", "edit"] else ""}">📦 Passive Drops</a>
                    <a href="/admin-web?tab=add" class="{"active" if tab == "add" else ""}">➕ Add Drop</a>
                    <a href="/admin-web?tab=users" class="{"active" if tab == "users" else ""}">🎅 CRM & VIP</a>
                    <a href="/admin-logout" class="logout-link">🚪 Logout</a>
                </div>
                <div class="main-content">
                    <div class="header-title">
                        <span>🎅 Weed Istanbul Management</span>
                        <span style="font-size: 13px; color: #10b981; background: rgba(16, 185, 129, 0.1); padding: 6px 12px; border-radius: 8px;">🎄 Mini App Active</span>
                    </div>
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
                    SELECT orders.status, drops.title, drops.location_url, drops.photo_ids, drops.description 
                    FROM orders JOIN drops ON orders.drop_id = drops.id WHERE orders.id = ?
                """, (order_id,))
                row = cursor.fetchone()
                conn.close()

                if not row:
                    self.send_html_error("Ürün veya sipariş bulunamadı.")
                    return

                status, title, location_url, photo_url, description = row
                if status != 'completed':
                    self.send_html_error("Bu bağlantı geçerli değil veya süresi dolmuş.")
                    return

                photo_tag = f'<img src="{photo_url}" style="width:100%; max-height:260px; object-fit:cover; border-radius:10px; margin-bottom:15px; border: 1px solid #374151;" />' if photo_url else ''

                html_content = f"""
                <!DOCTYPE html>
                <html lang="tr">
                <head>
                    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Secure Delivery - #{order_id}</title>
                    <style>
                        body {{ background-color: #090d16; color: #f8fafc; font-family: sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; }}
                        .card {{ background: #111827; padding: 25px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); width: 100%; max-width: 420px; text-align: center; border: 1px solid #1f2937; }}
                        h2 {{ color: #10b981; margin-top: 0; }}
                        .info {{ background: #090d16; padding: 15px; border-radius: 8px; margin: 15px 0; text-align: left; word-break: break-all; font-size: 14px; border: 1px solid #374151; }}
                        .btn {{ display: block; background: #10b981; color: white; padding: 12px; border-radius: 8px; text-decoration: none; font-weight: bold; margin-top: 15px; }}
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h2>🔒 Secure Delivery</h2>
                        <p style="margin-bottom: 15px;"><b>Product:</b> {title}</p>
                        {photo_tag}
                        <div class="info">
                            <p><b>📍 Location:</b> <a href="{location_url}" target="_blank" style="color: #38bdf8;">Click to Open in Maps</a></p>
                            <p><b>📝 Note:</b> {description}</p>
                        </div>
                        <a href="{location_url}" class="btn" target="_blank">Open Google Maps</a>
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
        post_data = self.rfile.read(content_length).decode('utf-8')
        params = parse_qs(post_data)

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

        if parsed_path.path == "/admin-add-testimonial":
            c_name = params.get("customer_name", [""])[0]
            try: rating = int(params.get("rating", [5])[0])
            except: rating = 5
            photo_url = params.get("photo_url", [""])[0]
            comment = params.get("comment", [""])[0]
            if c_name and comment:
                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO testimonials (customer_name, rating, photo_url, comment) VALUES (?, ?, ?, ?)", (c_name, rating, photo_url, comment))
                conn.commit()
                conn.close()
                log_panel_event(f"⭐ Yeni Müşteri Yorumu Eklendi: {c_name} ({rating}/5)", "success")
            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=testimonials')
            self.end_headers()

        elif parsed_path.path == "/admin-del-testimonial":
            t_id = params.get("id", ["0"])[0]
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM testimonials WHERE id = ?", (t_id,))
            conn.commit()
            conn.close()
            log_panel_event(f"🗑️ Müşteri Yorumu Silindi: ID #{t_id}", "warning")
            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=testimonials')
            self.end_headers()

        elif parsed_path.path == "/admin-support-reply":
            ticket_id = params.get("ticket_id", ["0"])[0]
            target_uid = int(params.get("user_id", ["0"])[0])
            reply_text = params.get("reply_text", [""])[0]
            if reply_text and target_uid:
                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("UPDATE support_tickets SET status = 'closed' WHERE id = ?", (ticket_id,))
                conn.commit()
                conn.close()
                if main_loop:
                    asyncio.run_coroutine_threadsafe(bot.send_message(target_uid, f"💬 **Destek Ekibi Yanıtı:**\n\n{reply_text}"), main_loop)
                log_panel_event(f"💬 Canlı Destek Yanıtlandı: Kullanıcı {target_uid}", "success")
            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=support')
            self.end_headers()

        elif parsed_path.path == "/admin-balance":
            target_uid = params.get("user_id", ["0"])[0]
            op = params.get("op", ["add"])[0]
            try: amount = float(params.get("amount", [0])[0])
            except: amount = 0.0
            if amount > 0:
                change = amount if op == "add" else -amount
                update_user_balance(int(target_uid), change)
                log_panel_event(f"💰 Bakiye İşlemi: Kullanıcı {target_uid} -> {'+' if op == 'add' else '-'}{amount} USDT", "info")
            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=users')
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
            log_panel_event(f"🛡️ User {target_uid} status updated: {'BANNED' if is_b == 1 else 'UNBANNED'}", "warning" if is_b == 1 else "info")
            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=users')
            self.end_headers()

        elif parsed_path.path == "/admin-add":
            title = params.get("title", [""])[0]
            category = params.get("category", ["Genel"])[0]
            try: price = float(params.get("price", [0])[0]); count = int(params.get("count", [1])[0])
            except: price, count = 0.0, 1
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            for i in range(1, count + 1):
                loc = params.get(f"location_{i}", [""])[0]
                photo = params.get(f"photo_{i}", [""])[0]
                desc = params.get(f"description_{i}", [""])[0]
                if loc and desc:
                    cursor.execute("INSERT INTO drops (title, price, location_url, photo_ids, description, stock, category) VALUES (?, ?, ?, ?, ?, ?, ?)", (title, price, loc, photo, desc, 1, category))
            conn.commit()
            conn.close()
            log_panel_event(f"➕ Yeni Ürün Eklendi: {title} ({count} Adet)", "success")
            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=passive')
            self.end_headers()

        elif parsed_path.path == "/admin-update":
            drop_id = params.get("id", ["0"])[0]
            title = params.get("title", [""])[0]
            category = params.get("category", ["Genel"])[0]
            try: price = float(params.get("price", [0])[0]); stock = int(params.get("stock", [1])[0])
            except: price, stock = 0.0, 1
            location = params.get("location", [""])[0]
            photo = params.get("photo", [""])[0]
            description = params.get("description", [""])[0]
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("UPDATE drops SET title = ?, price = ?, stock = ?, category = ?, location_url = ?, photo_ids = ?, description = ? WHERE id = ?", (title, price, stock, category, location, photo, description, drop_id))
            conn.commit()
            conn.close()
            log_panel_event(f"✏️ Ürün Güncellendi: #{drop_id}", "info")
            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=passive')
            self.end_headers()

        elif parsed_path.path == "/admin-approve":
            order_id = params.get("order_id", ["0"])[0]
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT orders.user_id, drops.id, drops.stock, orders.status, drops.title, orders.final_price, drops.category, users.referred_by 
                FROM orders JOIN drops ON orders.drop_id = drops.id LEFT JOIN users ON orders.user_id = users.user_id WHERE orders.id = ?
            """, (order_id,))
            row = cursor.fetchone()
            if row:
                u_id, d_id, stock, status, t_title, f_price, t_cat, ref_by = row
                if status == 'pending':
                    new_stock = stock - 1
                    if new_stock <= 0: cursor.execute("UPDATE drops SET stock = 0, is_sold = 1 WHERE id = ?", (d_id,))
                    else: cursor.execute("UPDATE drops SET stock = ? WHERE id = ?", (new_stock, d_id))
                    cursor.execute("UPDATE orders SET status = 'completed' WHERE id = ?", (order_id,))
                    cursor.execute("UPDATE users SET total_spent = total_spent + ? WHERE user_id = ?", (f_price, u_id))
                    if ref_by:
                        cursor.execute("UPDATE users SET balance = balance + 5.0 WHERE user_id = ?", (ref_by,))
                        try:
                            asyncio.run_coroutine_threadsafe(bot.send_message(ref_by, f"🎉 **Davet Bonusu Kazandınız!** Cüzdanınıza **5 USDT** eklendi!"), main_loop)
                        except: pass
                    conn.commit()
                    conn.close()
                    secure_link = f"{RENDER_EXTERNAL_URL}/drop/{order_id}"
                    u_lang = get_user_lang(u_id)
                    success_text = LANG[u_lang]["banned"].replace("❌ Erişiminiz engellenmiştir.", f"🎉 Ödemeniz onaylandı!\n\n👉 [Konumu Aç]({secure_link})") # Fallback safe formatting
                    if main_loop:
                        asyncio.run_coroutine_threadsafe(bot.send_message(u_id, f"🎉 **Siparişiniz Onaylandı!**\n\n👉 [Güvenli Konum Sayfasını Aç]({secure_link})", parse_mode="Markdown"), main_loop)
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
        <html lang="tr">
        <head><meta charset="UTF-8"><title>Admin Giriş</title>
        <style>
            body {{ background: #050a0e; color: #f8fafc; font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
            .login-card {{ background: #0f172a; padding: 35px; border-radius: 20px; border: 1px solid rgba(16, 185, 129, 0.3); width: 100%; max-width: 360px; text-align: center; }}
            input {{ width: 100%; padding: 12px; margin: 10px 0; background: #050a0e; border: 1px solid #334155; border-radius: 8px; color: white; box-sizing: border-box; }}
            button {{ background: #10b981; color: white; padding: 12px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%; margin-top: 10px; }}
        </style>
        </head>
        <body>
            <div class="login-card">
                <h2>🎅 Admin Girişi</h2>
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
        self.wfile.write(f"<body style='background:#050a0e;color:white;text-align:center;padding-top:50px;'><h2>⚠️ {message}</h2></body>".encode("utf-8"))

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(('0.0.0.0', port), SecureDropHandler).serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

# --- FSM VE BOT KODLARI ---
class AdminPassState(StatesGroup):
    password = State()

class SupportState(StatesGroup):
    message = State()

class BroadcastState(StatesGroup):
    message = State()

dp = Dispatcher(storage=MemoryStorage())
bot = Bot(token=BOT_TOKEN)

def main_keyboard(lang="tr", user_id=0):
    t = LANG[lang]
    webapp_url = f"{RENDER_EXTERNAL_URL}/webapp?user_id={user_id}"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t["btn_webapp"], web_app=WebAppInfo(url=webapp_url))],
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
    referred_by = None
    if len(args) > 1 and args[1].startswith("ref"):
        try:
            ref_id = int(args[1].replace("ref", ""))
            if ref_id != user_id: referred_by = ref_id
        except: pass

    is_member = await check_user_subscription(user_id)
    if not is_member:
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
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇹🇷 Türkçe", callback_data="setlang_tr"), InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en")]
    ])
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

@dp.message(F.text.in_([LANG["tr"]["btn_faq"], LANG["en"]["btn_faq"]]))
async def faq_menu(message: types.Message):
    user_id = message.from_user.id
    if message.chat.type != "private" or is_user_banned(user_id): return
    await message.answer("💡 **SSS / FAQ:**\n\nMini App mağazamızdan dilediğiniz ürünü inceleyebilir, bakiyenizle veya kripto ile anında güvenli teslimat alabilirsiniz.")

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

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message, state: FSMContext):
    if message.chat.type != "private" or not is_admin(message.from_user.id): return
    await state.set_state(BroadcastState.message)
    await message.answer("📢 Duyuru mesajını yazın:")

@dp.message(BroadcastState.message)
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.chat.type != "private" or not is_admin(message.from_user.id): return
    broadcast_text = message.text
    await state.clear()
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE is_banned = 0")
    users = cursor.fetchall()
    conn.close()
    sent = 0
    for u in users:
        try:
            await bot.send_message(u[0], f"📢 **Duyuru:**\n\n{broadcast_text}")
            sent += 1
            await asyncio.sleep(0.05)
        except: pass
    await message.answer(f"✅ Duyuru {sent} kullanıcıya iletildi.")

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    if message.chat.type != "private" or not is_admin(message.from_user.id): return
    await state.set_state(AdminPassState.password)
    await message.answer("🔐 Admin şifresini girin:")

@dp.message(AdminPassState.password)
async def process_admin_password(message: types.Message, state: FSMContext):
    if message.chat.type != "private": return
    if message.text.strip() == "1881":
        await state.clear()
        web_url = f"{RENDER_EXTERNAL_URL}/admin-web"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🌐 Web Paneli Aç", url=web_url)]])
        await message.answer("✅ Şifre Doğru!", reply_markup=kb)
    else:
        await state.clear()
        await message.answer("❌ Hatalı şifre!")

async def main():
    global main_loop
    main_loop = asyncio.get_running_loop()
    asyncio.create_task(auto_backup_task())
    asyncio.create_task(check_expired_orders_task())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
