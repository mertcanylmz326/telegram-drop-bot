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
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, FSInputFile

# --- AYARLAR VE CÜZDAN İZOLASYONU ---
BOT_TOKEN = "8917981396:AAFliW6Hl6gT8CQZP9BgJrPYGQEAggga6WA"
ADMIN_IDS = [1012940363, 952698894]  # Çoklu Admin Listesi
ADMIN_GROUP_ID = -1004474292737  

ADMIN_WEB_USERNAME = "dionisus"
ADMIN_WEB_PASSWORD = "weedstanbul34"

# Üçlü Cüzdan Yapısı (Güvenlik ve İzolasyon)
WALLET_CONFIG = {
    "weedboot": "TMDAC83GTrxDCQiQBCEEL11CdHBYPSMpjH",  # Operasyon / Bot Cüzdanı
    "giris": "TVsUkivFz217G7yAZ9w9PDj4WphJZty1tY",      # Ana Kasa / Depo Cüzdanı
    "cikis": "TMxF3AFaqpHgRF5S8RkmZtAkwzzYxgwzLn"       # Aracı / Buffer Cüzdanı
}

CRYPTO_WALLET = WALLET_CONFIG["weedboot"]
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://senin-botun.onrender.com")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
main_loop = None

# --- ÇEVİRİ SÖZLÜĞÜ (TR / EN) ---
LANG = {
    "tr": {
        "welcome": "👋 Merhaba! Güvenli otomatik teslimat botuna hoş geldiniz. Lütfen dil seçiniz:",
        "lang_set": "✅ Dil Türkçe olarak ayarlandı.",
        "btn_products": "🛍️ Ürünler / Droplar",
        "btn_orders": "📦 Geçmiş Siparişlerim",
        "btn_wallet": "💰 Cüzdanım / Bakiye",
        "btn_faq": "❓ Nasıl Çalışır? (SSS)",
        "btn_support": "📞 Destek",
        "btn_lang": "🌐 Dil Değiştir",
        "no_stock": "❌ Şu anda stokta hazır drop bulunmamaktadır.",
        "select_cat": "🏙️ Lütfen ürünleri incelemek istediğiniz **bölgeyi / semti** seçin:",
        "back_cats": "🔙 Bölgelere Dön",
        "no_cat_stock": "Bu bölgede aktif ürün kalmadı.",
        "my_orders_title": "📦 **Sipariş Geçmişiniz:**",
        "no_orders": "📦 Henüz bir sipariş geçmişiniz bulunmuyor.",
        "order_item": "• **Sipariş #{id}** | {title} - {price} USDT\n  Durum: {status} ({date})\n\n",
        "open_loc": "🔗 Sipariş #{id} Konumunu Aç",
        "sold_out": "⚠️ Bu ürün tükenmiş.",
        "wallet_menu_text": "💰 **Cüzdan Yönetimi**\n\n💵 Güncel Bakiyeniz: **{balance} USDT**\n\nHesabınıza bakiye yükleyerek siparişlerinizi saniyesinde tek tıkla verebilirsiniz.",
        "deposit_btn": "📥 Bakiye Yükle (USDT)",
        "ask_deposit_amount": "📥 Lütfen hesabınıza yüklemek istediğiniz USDT miktarını rakam olarak yazın (Örn: 20):",
        "deposit_invoice": "📥 **Bakiye Yükleme Talebi (#{id})**\n\n💵 Yüklenecek Tutar: **{amount} USDT**\n🔒 Yatırım Adresi:\n`{wallet}`\n\n⏱️ 15 dakikanız vardır. Tutarı gönderdikten sonra aşağıdaki butona basın.",
        "deposit_check_btn": "🔄 Yatırımı Otomatik Kontrol Et",
        "deposit_success": "🎉 Ödemeniz onaylandı! **{amount} USDT** bakiyenize eklendi.\n💵 Yeni Toplam Bakiye: **{balance} USDT**",
        "buy_options": "📌 Ürün: {title}\n💰 Fiyat: {price} USDT\n💵 Bakiyeniz: {balance} USDT\n\nLütfen ödeme yöntemini seçin:",
        "pay_balance": "⚡ Bakiyeden Öde ({price} USDT)",
        "pay_crypto": "🔒 Blokzincir ile Öde",
        "pay_promo": "🎟️ Kupon Kullan",
        "insufficient_balance": "❌ Bakiyeniz yetersiz! Lütfen önce cüzdanınıza bakiye yükleyin veya doğrudan ödeme yapın.",
        "balance_success": "🎉 Siparişiniz başarıyla onaylandı! {price} USDT bakiyenizden düşüldü.\n\n👉 [Güvenli Konum Sayfasını Aç]({link})",
        "cancel": "❌ İptal",
        "invalid_drop": "⚠️ Ürün artık mevcut değil.",
        "order_created": "✅ Sipariş Oluşturuldu! (Sipariş No: #{id})\n\n📌 Ürün: {title}\n",
        "ask_promo": "🎟️ Lütfen geçerli kupon kodunuzu yazın:",
        "promo_applied": "💰 Normal Tutar: {price} USDT\n🎟️ Kupon İndirimi: -{discount} USDT\n💵 **Ödenecek Tutar: {final} USDT**\n\n",
        "promo_invalid": "❌ Geçersiz veya süresi dolmuş kupon! Tam Tutar: {final} USDT\n\n",
        "wallet_text": "🔒 Cüzdan Adresi:\n`{wallet}`\n\n⏱️ 15 dakikanız vardır. Ödemeyi yapınca aşağıdaki butona basın.",
        "check_btn": "🔄 Ödemeyi Otomatik Kontrol Et",
        "scan": "Blokzincir taranıyor...",
        "not_found": "İşlem veya sipariş bulunamadı.",
        "already_approved": "Zaten onaylanmış.",
        "expired": "Süresi dolmuş.",
        "time_out": "⏰ Süre aşımı nedeniyle iptal edildi.",
        "success_order": "✅ Sipariş #{id} onaylandı.",
        "success_msg": "🎉 Ödemeniz onaylandı!\n\n👉 [Güvenli Konum Sayfasını Aç]({link})",
        "wait_tx": "⚠️ Henüz transfer yansımadı, bekleyin.",
        "support_ask": "📞 Destek mesajınızı yazın, admin grubuna ve web paneline iletilsin:",
        "support_sent": "✅ Destek mesajınız iletildi.",
        "banned": "❌ Erişiminiz engellenmiştir."
    },
    "en": {
        "welcome": "👋 Hello! Welcome to the secure automated delivery bot. Please select your language:",
        "lang_set": "✅ Language set to English.",
        "btn_products": "🛍️ Products / Drops",
        "btn_orders": "📦 My Orders",
        "btn_wallet": "💰 My Wallet / Balance",
        "btn_faq": "❓ How It Works (FAQ)",
        "btn_support": "📞 Support",
        "btn_lang": "🌐 Change Language",
        "no_stock": "❌ There are currently no ready drops in stock.",
        "select_cat": "🏙️ Please select the **region / district** you want to view:",
        "back_cats": "🔙 Back to Regions",
        "no_cat_stock": "No active products left in this region.",
        "my_orders_title": "📦 **Your Order History:**",
        "no_orders": "📦 You don't have any order history yet.",
        "order_item": "• **Order #{id}** | {title} - {price} USDT\n  Status: {status} ({date})\n\n",
        "open_loc": "🔗 Open Order #{id} Location",
        "sold_out": "⚠️ This product is sold out.",
        "wallet_menu_text": "💰 **Wallet Management**\n\n💵 Current Balance: **{balance} USDT**\n\nDeposit funds to your account for instant one-click purchases.",
        "deposit_btn": "📥 Deposit Balance (USDT)",
        "ask_deposit_amount": "📥 Please enter the amount of USDT you want to deposit (e.g. 20):",
        "deposit_invoice": "📥 **Deposit Invoice (#{id})**\n\n💵 Amount: **{amount} USDT**\n🔒 Deposit Address:\n`{wallet}`\n\n⏱️ You have 15 minutes. Click the button below after sending funds.",
        "deposit_check_btn": "🔄 Auto-Check Deposit",
        "deposit_success": "🎉 Payment approved! **{amount} USDT** added to your balance.\n💵 New Total Balance: **{balance} USDT**",
        "buy_options": "📌 Product: {title}\n💰 Price: {price} USDT\n💵 Your Balance: {balance} USDT\n\nPlease select payment method:",
        "pay_balance": "⚡ Pay from Balance ({price} USDT)",
        "pay_crypto": "🔒 Pay via Blockchain",
        "pay_promo": "🎟️ Use Promo Code",
        "insufficient_balance": "❌ Insufficient balance! Please deposit funds or pay directly.",
        "balance_success": "🎉 Order successfully approved! {price} USDT deducted from your balance.\n\n👉 [Open Secure Location Page]({link})",
        "cancel": "❌ Cancel",
        "invalid_drop": "⚠️ Product is no longer available.",
        "order_created": "✅ Order Created! (Order No: #{id})\n\n📌 Product: {title}\n",
        "ask_promo": "🎟️ Please enter your valid promo code:",
        "promo_applied": "💰 Regular Price: {price} USDT\n🎟️ Promo Discount: -{discount} USDT\n💵 **Total to Pay: {final} USDT**\n\n",
        "promo_invalid": "❌ Invalid or expired code! Full Price: {final} USDT\n\n",
        "wallet_text": "🔒 Wallet Address:\n`{wallet}`\n\n⏱️ You have 15 minutes. Click the button below after payment.",
        "check_btn": "🔄 Auto-Check Payment",
        "scan": "Scanning blockchain...",
        "not_found": "Transaction or order not found.",
        "already_approved": "Already approved.",
        "expired": "Expired.",
        "time_out": "⏰ Canceled due to timeout.",
        "success_order": "✅ Order #{id} approved.",
        "success_msg": "🎉 Your payment is approved!\n\n👉 [Open Secure Location Page]({link})",
        "wait_tx": "⚠️ Transfer not reflected yet, please wait.",
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
        CREATE TABLE IF NOT EXISTS promos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            discount REAL,
            usage_limit INTEGER DEFAULT 100,
            used_count INTEGER DEFAULT 0
        )
    ''')

    cursor.execute("INSERT OR IGNORE INTO promos (code, discount, usage_limit) VALUES ('welcomeweedstanbul', 8.0, 500)")

    for col, def_val in [("is_banned", "INTEGER DEFAULT 0"), ("language", "TEXT DEFAULT 'tr'"), ("balance", "REAL DEFAULT 0.0")]:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {def_val}")
        except:
            pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)
    ''')
    for admin_id in ADMIN_IDS:
        cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (admin_id,))
    
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
    return user_id in ADMIN_IDS

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
            logging.error(f"Cüzdan bakiye çekme hatası ({addr}): {e}")
        balances[key] = {"usdt": usdt_bal, "trx": trx_bal}
    return balances

def get_wallet_transfers(addr):
    txs = []
    try:
        import urllib.request
        import json
        url = f"https://api.trongrid.io/v1/accounts/{addr}/trc20-transfers?contract_address={USDT_CONTRACT}&limit=5"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                for tx in data.get("data", []):
                    from_addr = tx.get("from", "")
                    to_addr = tx.get("to", "")
                    val = float(tx.get("value", 0)) / 1000000.0
                    t_type = "Gelen" if to_addr == addr else "Giden"
                    txs.append({"type": t_type, "amount": val, "from": from_addr[:6] + "...", "to": to_addr[:6] + "..."})
    except Exception as e:
        logging.error(e)
    return txs

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
            self.wfile.write(b"Weed Istanbul Christmas Server Active!")
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
                    <div style="background: rgba(15, 23, 42, 0.75); padding: 12px 15px; border-radius: 12px; margin-bottom: 10px; border-left: 4px solid {badge_color}; font-size: 13px; backdrop-filter: blur(8px);">
                        <span style="color: #64748b; font-size: 11px; display: block; margin-bottom: 2px;">{l_date}</span>
                        {msg}
                    </div>
                    """

                cursor.execute("""
                    SELECT DATE(created_at) as cday, SUM(final_price) 
                    FROM orders WHERE status = 'completed' 
                    GROUP BY cday ORDER BY cday ASC LIMIT 7
                """)
                chart_rows = cursor.fetchall()
                labels = [r[0] for r in chart_rows] if chart_rows else ["Today"]
                values = [r[1] for r in chart_rows] if chart_rows else [total_revenue]

                cursor.execute("SELECT category, COUNT(*) FROM orders JOIN drops ON orders.drop_id = drops.id WHERE orders.status = 'completed' GROUP BY category")
                cat_rows = cursor.fetchall()
                cat_labels = [r[0] for r in cat_rows] if cat_rows else ["Genel"]
                cat_values = [r[1] for r in cat_rows] if cat_rows else [1]

                w_bals = get_wallet_balances()

                content_html = f"""
                <div class="stats-grid">
                    <div class="card neon-green"><h3>🎄 TOTAL REVENUE</h3><p>{total_revenue} USDT</p></div>
                    <div class="card neon-red"><h3>🎁 ACTIVE STOCK</h3><p>{total_active_stock} Pcs</p></div>
                    <div class="card neon-gold"><h3>⭐ PRODUCT VARIETY</h3><p>{total_drops}</p></div>
                </div>

                <div class="form-box" style="border: 1px solid rgba(16, 185, 129, 0.4); margin-bottom: 30px;">
                    <h2>🔒 3'lü Cüzdan İzolasyon & Canlı Bakiye Durumu</h2>
                    <p style="color: #94a3b8; font-size: 13px; margin-bottom: 15px;">Operasyonel gizlilik ve fon güvenliği için aktif cüzdan mimarisi ve anlık bakiyeler:</p>
                    <ul style="list-style: none; padding: 0; margin: 0; font-size: 14px;">
                        <li style="padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.05); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                            <div>🟢 <b>weedboot (Bot / Operasyon):</b> <code style="color: #38bdf8;">{WALLET_CONFIG['weedboot']}</code></div>
                            <div style="background: rgba(16, 185, 129, 0.15); padding: 6px 12px; border-radius: 8px; color: #10b981; font-weight: bold; border: 1px solid rgba(16,185,129,0.3);"><b>{w_bals.get('weedboot', {}).get('usdt', 0.0)} USDT</b> | {w_bals.get('weedboot', {}).get('trx', 0.0)} TRX</div>
                        </li>
                        <li style="padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.05); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                            <div>🔵 <b>Giriş (Ana Depo / Kasa):</b> <code style="color: #38bdf8;">{WALLET_CONFIG['giris']}</code></div>
                            <div style="background: rgba(56, 189, 248, 0.15); padding: 6px 12px; border-radius: 8px; color: #38bdf8; font-weight: bold; border: 1px solid rgba(56,189,248,0.3);"><b>{w_bals.get('giris', {}).get('usdt', 0.0)} USDT</b> | {w_bals.get('giris', {}).get('trx', 0.0)} TRX</div>
                        </li>
                        <li style="padding: 12px 0; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                            <div>🟡 <b>Çıkış (Aracı / Buffer):</b> <code style="color: #38bdf8;">{WALLET_CONFIG['cikis']}</code></div>
                            <div style="background: rgba(245, 158, 11, 0.15); padding: 6px 12px; border-radius: 8px; color: #f59e0b; font-weight: bold; border: 1px solid rgba(245,158,11,0.3);"><b>{w_bals.get('cikis', {}).get('usdt', 0.0)} USDT</b> | {w_bals.get('cikis', {}).get('trx', 0.0)} TRX</div>
                        </li>
                    </ul>
                </div>

                <div class="grid-2">
                    <div class="table-box">
                        <h2>📊 Weekly Revenue Trend</h2>
                        <canvas id="revenueChart" style="max-height: 250px;"></canvas>
                    </div>
                    <div class="table-box">
                        <h2>🏙️ Semt Bazlı Satış Dağılımı</h2>
                        <canvas id="categoryChart" style="max-height: 250px;"></canvas>
                    </div>
                </div>

                <div class="table-box" style="margin-top: 20px;">
                    <h2>🔔 Live Logs & Alerts</h2>
                    <div style="max-height: 200px; overflow-y: auto;">
                        {logs_html if logs_html else "<p style='text-align:center; color:#64748b;'>No recent logs.</p>"}
                    </div>
                </div>

                <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
                <script>
                    const ctx = document.getElementById('revenueChart').getContext('2d');
                    new Chart(ctx, {{
                        type: 'line',
                        data: {{
                            labels: {labels},
                            datasets: [{{
                                label: 'Revenue (USDT)',
                                data: {values},
                                borderColor: '#10b981',
                                backgroundColor: 'rgba(16, 185, 129, 0.15)',
                                fill: true,
                                tension: 0.4,
                                borderWidth: 3
                            }}]
                        }},
                        options: {{
                            responsive: true,
                            plugins: {{ legend: {{ display: false }} }},
                            scales: {{
                                x: {{ grid: {{ color: 'rgba(255,255,255,0.05)' }}, ticks: {{ color: '#94a3b8' }} }},
                                y: {{ grid: {{ color: 'rgba(255,255,255,0.05)' }}, ticks: {{ color: '#94a3b8' }} }}
                            }}
                        }}
                    }});

                    const ctxCat = document.getElementById('categoryChart').getContext('2d');
                    new Chart(ctxCat, {{
                        type: 'doughnut',
                        data: {{
                            labels: {cat_labels},
                            datasets: [{{
                                data: {cat_values},
                                backgroundColor: ['#10b981', '#38bdf8', '#f59e0b', '#ef4444', '#8b5cf6']
                            }}]
                        }},
                        options: {{
                            responsive: true,
                            plugins: {{ legend: {{ position: 'bottom', labels: {{ color: '#94a3b8' }} }} }}
                        }}
                    }});
                </script>
                """
            elif tab == "wallet_txs":
                txs = get_wallet_transfers(CRYPTO_WALLET)
                tx_rows = ""
                for tx in txs:
                    color = "#10b981" if tx["type"] == "Gelen" else "#ef4444"
                    tx_rows += f"<tr><td><b>{tx['type']}</b></td><td><b style='color:{color};'>{tx['amount']} USDT</b></td><td><code>{tx['from']}</code></td><td><code>{tx['to']}</code></td></tr>"
                
                content_html = f"""
                <div class="table-box">
                    <h2>💰 Canlı Cüzdan Transfer Hareketleri (Son 5 İşlem)</h2>
                    <p style="color:#94a3b8; font-size:13px; margin-bottom:15px;">Operasyon cüzdanına (`weedboot`) gelen son USDT transferleri:</p>
                    <table>
                        <tr><th>İşlem Tipi</th><th>Tutar</th><th>Gönderen</th><th>Alıcı</th></tr>
                        {tx_rows if tx_rows else "<tr><td colspan='4' style='text-align:center;'>İşlem bulunamadı veya API yanıt vermedi.</td></tr>"}
                    </table>
                </div>
                """
            elif tab == "promos":
                cursor.execute("SELECT id, code, discount, usage_limit, used_count FROM promos ORDER BY id DESC")
                promos = cursor.fetchall()
                p_rows = ""
                for p in promos:
                    pid, pcode, pdisc, plimit, pused = p
                    p_rows += f"<tr><td><b>#{pid}</b></td><td><code>{pcode}</code></td><td><b style='color:#10b981;'>{pdisc} USDT</b></td><td>{pused} / {plimit}</td></tr>"

                content_html = f"""
                <div class="grid-2">
                    <div class="form-box">
                        <h2>🎟️ Yeni Kupon Kodu Oluştur</h2>
                        <form action="/admin-add-promo" method="POST">
                            <label>Kupon Kodu:</label>
                            <input type="text" name="code" required placeholder="Örn: YENIYIL2026">
                            <label>İndirim Tutarı (USDT):</label>
                            <input type="number" step="0.1" name="discount" required placeholder="10">
                            <label>Kullanım Limiti (Adet):</label>
                            <input type="number" name="limit" value="100" required>
                            <button type="submit" style="margin-top:15px;">Kuponu Tanımla</button>
                        </form>
                    </div>
                    <div class="table-box">
                        <h2>📋 Aktif Kuponlar</h2>
                        <table>
                            <tr><th>ID</th><th>Kod</th><th>İndirim</th><th>Kullanım</th></tr>
                            {p_rows}
                        </table>
                    </div>
                </div>
                """
            elif tab == "broadcast":
                content_html = """
                <div class="form-box" style="max-width: 600px; margin: 0 auto;">
                    <h2>📢 Toplu Duyuru / Broadcast Gönder</h2>
                    <p style="color:#94a3b8; font-size:13px; margin-bottom:15px;">Sistemde kayıtlı tüm kullanıcılara anlık bildirim mesajı gönderir.</p>
                    <form action="/admin-broadcast" method="POST">
                        <label>Duyuru Mesajı (Markdown Destekli):</label>
                        <textarea name="message" rows="6" required placeholder="🎄 Mutlu Yıllar! Yeni yıl dropları eklendi, fırsatları kaçırmayın..."></textarea>
                        <button type="submit" style="background:#10b981; margin-top:15px;">Tüm Kullanıcılara Gönder</button>
                    </form>
                </div>
                """
            elif tab == "support":
                cursor.execute("SELECT id, user_id, username, message, status, created_at FROM support_tickets ORDER BY id DESC")
                tickets = cursor.fetchall()
                rows = ""
                for t_item in tickets:
                    t_id, t_uid, t_uname, t_msg, t_status, t_date = t_item
                    uname_str = f"@{t_uname}" if t_uname else "N/A"
                    status_badge = "<span style='color:#10b981; font-weight:bold; background:rgba(16,185,129,0.2); padding:4px 10px; border-radius:8px;'>OPEN</span>" if t_status == 'open' else "<span style='color:#64748b; font-weight:bold;'>CLOSED</span>"
                    reply_form = f"""
                    <form action="/admin-support-reply" method="POST" style="margin:0; display:flex; gap:8px; align-items:center;">
                        <input type="hidden" name="ticket_id" value="{t_id}">
                        <input type="hidden" name="user_id" value="{t_uid}">
                        <input type="text" name="reply_text" placeholder="Yanıtını yaz..." required style="margin:0; padding:6px; font-size:12px; height:30px;">
                        <button type="submit" style="background:#10b981; padding:4px 10px; font-size:11px; width:auto; height:30px;">Gönder</button>
                    </form>
                    """
                    rows += f"<tr><td><b>#{t_id}</b></td><td>{t_uid} ({uname_str})</td><td style='max-width:200px; word-break:break-all;'>{t_msg}</td><td>{t_date}</td><td>{status_badge}</td><td>{reply_form}</td></tr>"

                content_html = f"""
                <div class="table-box">
                    <h2>💬 Canlı Destek CRM Paneli</h2>
                    <table>
                        <tr><th>ID</th><th>Kullanıcı</th><th>Mesaj</th><th>Tarih</th><th>Durum</th><th>İşlem</th></tr>
                        {rows if rows else "<tr><td colspan='6' style='text-align:center;'>Aktif destek talebi yok.</td></tr>"}
                    </table>
                </div>
                """
            elif tab == "users":
                cursor.execute("SELECT user_id, username, is_banned, language, balance FROM users ORDER BY user_id DESC")
                users_list = cursor.fetchall()
                rows = ""
                for u in users_list:
                    uid, uname, is_b, u_lang, u_bal = u
                    username_str = f"@{uname}" if uname else "N/A"
                    status_badge = "<span style='color:#ef4444; font-weight:bold;'>BANNED</span>" if is_b == 1 else "<span style='color:#10b981; font-weight:bold;'>ACTIVE</span>"
                    ban_btn = f"""
                    <form action="/admin-ban" method="POST" style="margin:0; display:inline;">
                        <input type="hidden" name="user_id" value="{uid}">
                        <input type="hidden" name="action" value="{'unban' if is_b == 1 else 'ban'}">
                        <button type="submit" style="background:{'#10b981' if is_b == 1 else '#ef4444'}; padding:4px 8px; font-size:11px; width:auto;">{'Unban' if is_b == 1 else 'Ban'}</button>
                    </form>
                    """
                    bal_form = f"""
                    <form action="/admin-balance" method="POST" style="margin:0; display:flex; gap:5px; align-items:center;">
                        <input type="hidden" name="user_id" value="{uid}">
                        <input type="number" step="0.1" name="amount" placeholder="USDT" style="width:65px; padding:4px; margin:0; font-size:11px; height:26px;">
                        <button type="submit" name="op" value="add" style="background:#10b981; padding:2px 6px; font-size:10px; width:auto; height:26px;">+</button>
                        <button type="submit" name="op" value="sub" style="background:#ef4444; padding:2px 6px; font-size:10px; width:auto; height:26px;">-</button>
                    </form>
                    """
                    rows += f"<tr><td>{uid}</td><td>{username_str}</td><td>{u_lang.upper()}</td><td><b>{u_bal} USDT</b></td><td>{bal_form}</td><td>{status_badge}</td><td>{ban_btn}</td></tr>"

                content_html = f"""
                <div class="table-box">
                    <h2>🎅 CRM & Bakiye Yönetimi</h2>
                    <table>
                        <tr><th>User ID</th><th>Username</th><th>Lang</th><th>Bakiye</th><th>Düzenle</th><th>Status</th><th>İşlem</th></tr>
                        {rows}
                    </table>
                </div>
                """
            elif tab == "active":
                cursor.execute("""
                    SELECT orders.id, users.username, drops.title, orders.final_price, orders.status, orders.created_at 
                    FROM orders JOIN drops ON orders.drop_id = drops.id LEFT JOIN users ON orders.user_id = users.user_id
                    WHERE orders.status = 'completed' ORDER BY orders.id DESC
                """)
                orders = cursor.fetchall()
                rows = ""
                for o in orders:
                    rows += f"<tr><td><b>#{o[0]}</b></td><td>@{o[1] or 'N/A'}</td><td>{o[2]}</td><td><b style='color:#10b981;'>{o[3]} USDT</b></td><td>Tamamlandı</td><td>{o[5]}</td></tr>"
                content_html = f"""<div class="table-box"><h2>🟢 Tamamlanan Siparişler</h2><table><tr><th>ID</th><th>Kullanıcı</th><th>Ürün</th><th>Tutar</th><th>Durum</th><th>Tarih</th></tr>{rows}</table></div>"""
            elif tab == "pending":
                cursor.execute("""
                    SELECT orders.id, users.username, drops.title, orders.final_price, orders.created_at 
                    FROM orders JOIN drops ON orders.drop_id = drops.id LEFT JOIN users ON orders.user_id = users.user_id
                    WHERE orders.status = 'pending' ORDER BY orders.id DESC
                """)
                rows = ""
                for o in cursor.fetchall():
                    rows += f"<tr><td><b>#{o[0]}</b></td><td>@{o[1] or 'N/A'}</td><td>{o[2]}</td><td><b style='color:#f59e0b;'>{o[3]} USDT</b></td><td>{o[4]}</td><td><form action='/admin-approve' method='POST' style='margin:0;'><input type='hidden' name='order_id' value='{o[0]}'><button type='submit' style='background:#10b981; padding:4px 10px; font-size:11px; width:auto;'>Onayla</button></form></td></tr>"
                content_html = f"""<div class="table-box"><h2>⏳ Bekleyen Siparişler</h2><table><tr><th>ID</th><th>Kullanıcı</th><th>Ürün</th><th>Tutar</th><th>Tarih</th><th>İşlem</th></tr>{rows}</table></div>"""
            elif tab == "passive":
                cursor.execute("SELECT id, title, price, stock, category FROM drops WHERE is_sold = 0")
                rows = ""
                for d in cursor.fetchall():
                    rows += f"<tr><td><b>#{d[0]}</b></td><td>{d[1]}</td><td>{d[2]}</td><td>{d[3]} USDT</td><td>{d[4]}</td><td><a href='/admin-edit?id={d[0]}' class='action-btn edit-btn'>Düzenle</a></td></tr>"
                content_html = f"""<div class="table-box"><h2>📦 Pasif / Stoktaki Ürünler</h2><table><tr><th>ID</th><th>Başlık</th><th>Fiyat</th><th>Stok</th><th>Kategori</th><th>İşlem</th></tr>{rows}</table></div>"""
            elif tab == "add":
                content_html = """
                <div class="form-box">
                    <h2>➕ Yeni Drop Ekle</h2>
                    <form action="/admin-add" method="POST" id="addForm">
                        <label>Ürün Başlığı:</label><input type="text" name="title" required placeholder="Örn: Amnesia Haze">
                        <label>Semt / Kategori:</label><input type="text" name="category" required placeholder="Örn: Kadıköy">
                        <label>Fiyat (USDT):</label><input type="number" step="0.1" name="price" required placeholder="65">
                        <label>Stok Adedi:</label><input type="number" name="count" id="countInput" value="1" min="1" max="30" required onchange="generateFields()">
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
                            container.innerHTML += `<div style="background: rgba(5,10,14,0.7); padding: 15px; border-radius: 10px; margin-top: 10px;"><label>Konum Linki #${i}:</label><input type='text' name='location_${i}' required placeholder='https://maps.app.goo.gl/...'><label>Fotoğraf URL:</label><input type='text' name='photo_${i}' placeholder='Resim linki'><label>Not:</label><textarea name='description_${i}' rows='2' required placeholder='Saksının arkasında...'></textarea></div>`;
                        }
                    }
                    window.onload = generateFields;
                </script>
                """

            edit_form_html = ""
            if tab == "edit":
                edit_id = query_params.get("id", ["0"])[0]
                cursor.execute("SELECT title, price, stock, category, location_url, photo_ids, description FROM drops WHERE id = ?", (edit_id,))
                d = cursor.fetchone()
                if d:
                    edit_form_html = f"""
                    <div class="form-box" style="border: 2px solid #10b981; margin-bottom: 25px;">
                        <h2>✏️ Ürün Düzenle (#{edit_id})</h2>
                        <form action="/admin-update" method="POST">
                            <input type="hidden" name="id" value="{edit_id}">
                            <label>Başlık:</label><input type="text" name="title" value="{d[0]}" required>
                            <label>Kategori:</label><input type="text" name="category" value="{d[3]}" required>
                            <label>Fiyat:</label><input type="number" step="0.1" name="price" value="{d[1]}" required>
                            <label>Stok:</label><input type="number" name="stock" value="{d[2]}" required>
                            <label>Konum Linki:</label><input type="text" name="location" value="{d[4]}" required>
                            <label>Fotoğraf:</label><input type="text" name="photo" value="{d[5]}">
                            <label>Açıklama:</label><textarea name="description" rows="3" required>{d[6]}</textarea>
                            <button type="submit" style="background:#10b981; margin-top:15px;">Kaydet</button>
                        </form>
                    </div>
                    """
            conn.close()

            dashboard_html = f"""
            <!DOCTYPE html>
            <html lang="tr">
            <head>
                <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>🎄 Merry Christmas & Happy New Year - Admin Panel 🎁</title>
                <style>
                    body {{ background: #020609 url('https://images.unsplash.com/photo-1543589077-47d59746c2a4?auto=format&fit=crop&w=1920&q=80') no-repeat center center fixed; background-size: cover; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; display: flex; min-height: 100vh; position: relative; overflow-x: hidden; }}
                    body::before {{ content: ""; position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: radial-gradient(circle at 50% 20%, rgba(15, 23, 42, 0.88) 0%, rgba(2, 6, 9, 0.95) 100%); z-index: 0; }}
                    #snowflake-canvas {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 9999; }}
                    
                    /* Üst Header / Hamburger Butonu */
                    .top-nav-bar {{ position: fixed; top: 0; left: 0; right: 0; height: 60px; background: rgba(10, 18, 26, 0.85); backdrop-filter: blur(15px); border-bottom: 1px solid rgba(239, 68, 68, 0.2); display: flex; align-items: center; justify-content: space-between; padding: 0 20px; z-index: 100; box-sizing: border-box; }}
                    .menu-toggle-btn {{ background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.4); color: #f87171; padding: 8px 14px; border-radius: 8px; font-weight: bold; cursor: pointer; display: flex; align-items: center; gap: 8px; font-size: 14px; transition: 0.3s; width: auto; box-shadow: none; }}
                    .menu-toggle-btn:hover {{ background: rgba(239, 68, 68, 0.3); transform: scale(1.02); }}

                    /* Sol Açılır Pencere (Slide-out Drawer) */
                    .sidebar-overlay {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.6); backdrop-filter: blur(4px); z-index: 1000; opacity: 0; visibility: hidden; transition: 0.3s ease; }}
                    .sidebar-overlay.open {{ opacity: 1; visibility: visible; }}

                    .sidebar {{ position: fixed; top: 0; left: -300px; width: 280px; height: 100%; background: rgba(10, 18, 26, 0.95); border-right: 1px solid rgba(239, 68, 68, 0.3); box-shadow: 10px 0 30px rgba(0,0,0,0.7); display: flex; flex-direction: column; padding: 25px 15px; box-sizing: border-box; z-index: 1001; backdrop-filter: blur(20px); transition: left 0.35s cubic-bezier(0.4, 0, 0.2, 1); }}
                    .sidebar.open {{ left: 0; }}

                    .sidebar .brand {{ font-size: 18px; font-weight: 900; color: #f87171; text-align: center; margin-bottom: 25px; text-shadow: 0 0 15px rgba(239, 68, 68, 0.6); display: flex; align-items: center; justify-content: center; gap: 8px; }}
                    .sidebar .close-drawer {{ background: transparent; border: none; color: #94a3b8; font-size: 18px; cursor: pointer; text-align: right; width: 100%; margin-bottom: 10px; padding: 0; box-shadow: none; }}
                    .sidebar .close-drawer:hover {{ color: white; transform: none; background: transparent; }}

                    .sidebar a {{ background: rgba(255, 255, 255, 0.02); color: #cbd5e1; padding: 12px 16px; border-radius: 12px; text-decoration: none; font-weight: 600; font-size: 13px; margin-bottom: 6px; border: 1px solid rgba(255, 255, 255, 0.04); transition: 0.3s; display: flex; align-items: center; gap: 10px; }}
                    .sidebar a.active, .sidebar a:hover {{ background: linear-gradient(135deg, rgba(220, 38, 38, 0.25), rgba(16, 185, 129, 0.2)); color: #f8fafc; border-color: rgba(239, 68, 68, 0.5); transform: translateX(6px); box-shadow: 0 0 15px rgba(220, 38, 38, 0.2); }}
                    .logout-link {{ background: rgba(239, 68, 68, 0.15) !important; color: #fca5a5 !important; margin-top: auto; border: 1px solid rgba(239, 68, 68, 0.3) !important; text-align: center; justify-content: center; }}
                    
                    .main-content {{ flex: 1; padding: 100px 35px 35px 35px; box-sizing: border-box; overflow-y: auto; max-width: 1240px; margin: 0 auto; width: 100%; z-index: 2; }}
                    .header-title {{ color: #f8fafc; font-size: 24px; font-weight: 800; margin-top: 0; margin-bottom: 30px; border-bottom: 1px solid rgba(255, 255, 255, 0.08); padding-bottom: 15px; display: flex; justify-content: space-between; align-items: center; text-shadow: 0 2px 10px rgba(0,0,0,0.5); flex-wrap: wrap; gap: 15px; }}
                    
                    .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin-bottom: 30px; }}
                    .card {{ background: rgba(15, 23, 42, 0.75); padding: 22px; border-radius: 18px; border: 1px solid rgba(255, 255, 255, 0.08); text-align: center; backdrop-filter: blur(12px); box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3); }}
                    .card.neon-green {{ border-color: rgba(16, 185, 129, 0.4); box-shadow: 0 0 25px rgba(16, 185, 129, 0.15); }}
                    .card.neon-red {{ border-color: rgba(239, 68, 68, 0.4); box-shadow: 0 0 25px rgba(239, 68, 68, 0.15); }}
                    .card.neon-gold {{ border-color: rgba(245, 158, 11, 0.4); box-shadow: 0 0 25px rgba(245, 158, 11, 0.15); }}
                    .card h3 {{ margin: 0 0 10px 0; color: #94a3b8; font-size: 12px; font-weight: 700; letter-spacing: 1px; }}
                    .card p {{ margin: 0; font-size: 28px; font-weight: 900; color: #f8fafc; }}
                    
                    .grid-2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 20px; }}
                    .form-box, .table-box {{ background: rgba(15, 23, 42, 0.8); padding: 25px; border-radius: 18px; border: 1px solid rgba(255, 255, 255, 0.08); margin-bottom: 30px; backdrop-filter: blur(15px); box-shadow: 0 10px 30px rgba(0,0,0,0.4); overflow-x: auto; }}
                    
                    input, textarea {{ width: 100%; padding: 12px 15px; margin: 8px 0 16px 0; background: rgba(5, 10, 14, 0.85); border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 10px; color: white; box-sizing: border-box; font-size: 14px; transition: 0.3s; }}
                    input:focus, textarea:focus {{ border-color: #ef4444; outline: none; box-shadow: 0 0 10px rgba(239, 68, 68, 0.3); }}
                    
                    button {{ background: linear-gradient(135deg, #dc2626, #b91c1c); color: white; padding: 12px 20px; border: none; border-radius: 10px; font-weight: bold; cursor: pointer; width: 100%; font-size: 14px; transition: 0.3s; box-shadow: 0 4px 15px rgba(220, 38, 38, 0.4); }}
                    button:hover {{ background: linear-gradient(135deg, #ef4444, #dc2626); transform: translateY(-1px); }}
                    
                    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                    th, td {{ padding: 14px 12px; text-align: left; border-bottom: 1px solid rgba(255, 255, 255, 0.06); font-size: 13px; }}
                    th {{ color: #94a3b8; font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }}
                    
                    .action-btn {{ padding: 6px 14px; border-radius: 8px; text-decoration: none; font-size: 12px; font-weight: bold; display: inline-block; }}
                    .edit-btn {{ background: rgba(217, 119, 6, 0.2); color: #fbbf24; border: 1px solid rgba(217, 119, 6, 0.4); }}
                </style>
            </head>
            <body>
                <canvas id="snowflake-canvas"></canvas>
                
                <!-- Üst Navbar ve Menü Butonu -->
                <div class="top-nav-bar">
                    <button class="menu-toggle-btn" onclick="toggleSidebar()">
                        <span>📂</span> Menüyü Aç / Sekmeler
                    </button>
                    <span style="font-weight: 800; color: #f87171; font-size: 15px; text-shadow: 0 0 10px rgba(239,68,68,0.5);">🎄 Weed Istanbul Admin</span>
                </div>

                <!-- Sol Açılır Pencere / Çekmece (Drawer) -->
                <div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>
                <div class="sidebar" id="sidebarDrawer">
                    <button class="close-drawer" onclick="toggleSidebar()">✕ Kapat</button>
                    <div class="brand">🎄 Weed Istanbul 🎅</div>
                    <a href="/admin-web?tab=home" class="{"active" if tab == "home" else ""}">🏠 Ana Sayfa</a>
                    <a href="/admin-web?tab=wallet_txs" class="{"active" if tab == "wallet_txs" else ""}">💰 Cüzdan Hareketleri</a>
                    <a href="/admin-web?tab=promos" class="{"active" if tab == "promos" else ""}">🎟️ Kupon Yönetimi</a>
                    <a href="/admin-web?tab=broadcast" class="{"active" if tab == "broadcast" else ""}">📢 Toplu Duyuru</a>
                    <a href="/admin-web?tab=support" class="{"active" if tab == "support" else ""}">💬 Canlı Destek CRM</a>
                    <a href="/admin-web?tab=active" class="{"active" if tab == "active" else ""}">🟢 Tamamlanan Siparişler</a>
                    <a href="/admin-web?tab=pending" class="{"active" if tab == "pending" else ""}">⏳ Bekleyen Siparişler</a>
                    <a href="/admin-web?tab=passive" class="{"active" if tab in ["passive", "edit"] else ""}">📦 Pasif / Stok Droplar</a>
                    <a href="/admin-web?tab=add" class="{"active" if tab == "add" else ""}">➕ Yeni Drop Ekle</a>
                    <a href="/admin-web?tab=users" class="{"active" if tab == "users" else ""}">👥 Kullanıcılar & Bakiyeler</a>
                    <a href="/admin-logout" class="logout-link">🚪 Güvenli Çıkış</a>
                </div>

                <div class="main-content">
                    <div class="header-title">
                        <span>🎁 Merry Christmas & Happy New Year Admin Hub 🎄</span>
                        <span style="font-size: 12px; color: #f87171; background: rgba(239, 68, 68, 0.15); padding: 6px 14px; border-radius: 10px; border: 1px solid rgba(239, 68, 68, 0.35);">⭐ Special Edition</span>
                    </div>
                    {edit_form_html}
                    {content_html}
                </div>

                <script>
                    function toggleSidebar() {{
                        const sidebar = document.getElementById('sidebarDrawer');
                        const overlay = document.getElementById('sidebarOverlay');
                        sidebar.classList.toggle('open');
                        overlay.classList.toggle('open');
                    }}

                    const canvas = document.getElementById('snowflake-canvas');
                    const ctx = canvas.getContext('2d');
                    let width = canvas.width = window.innerWidth;
                    let height = canvas.height = window.innerHeight;
                    window.addEventListener('resize', () => {{ width = canvas.width = window.innerWidth; height = canvas.height = window.innerHeight; }});
                    const snowflakes = [];
                    for (let i = 0; i < 75; i++) {{ snowflakes.push({{ x: Math.random() * width, y: Math.random() * height, radius: Math.random() * 2 + 0.5, speed: Math.random() * 0.7 + 0.3 }}); }}
                    function draw() {{
                        ctx.clearRect(0, 0, width, height);
                        ctx.fillStyle = "rgba(255, 255, 255, 0.75)";
                        ctx.beginPath();
                        for (let i = 0; i < snowflakes.length; i++) {{
                            let s = snowflakes[i];
                            ctx.moveTo(s.x, s.y); ctx.arc(s.x, s.y, s.radius, 0, Math.PI * 2, true);
                            s.y += s.speed; if (s.y > height) s.y = 0;
                        }}
                        ctx.fill();
                    }}
                    setInterval(draw, 33);
                </script>
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

                if not row or row[0] != 'completed':
                    self.send_html_error("Bu bağlantı geçerli değil veya süresi dolmuş.")
                    return

                status, title, location_url, photo_url, description = row
                photo_tag = f'<img src="{photo_url}" style="width:100%; max-height:260px; object-fit:cover; border-radius:12px; margin-bottom:15px; border: 1px solid rgba(255,255,255,0.1);" />' if photo_url else ''

                html_content = f"""
                <!DOCTYPE html>
                <html lang="tr">
                <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Secure Delivery - #{order_id}</title>
                <style>body {{ background-color: #020609; color: #f8fafc; font-family: sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; }} .card {{ background: rgba(15, 23, 42, 0.9); padding: 30px; border-radius: 20px; width: 100%; max-width: 420px; text-align: center; border: 1px solid rgba(239,68,68,0.3); backdrop-filter: blur(12px); box-shadow: 0 10px 30px rgba(0,0,0,0.5); }} h2 {{ color: #f87171; margin-top: 0; }} .info {{ background: rgba(5, 10, 14, 0.85); padding: 16px; border-radius: 12px; margin: 20px 0; text-align: left; word-break: break-all; font-size: 14px; }} .btn {{ display: block; background: linear-gradient(135deg, #dc2626, #b91c1c); color: white; padding: 14px; border-radius: 12px; text-decoration: none; font-weight: bold; margin-top: 20px; box-shadow: 0 4px 15px rgba(220, 38, 38, 0.4); }}</style>
                </head>
                <body>
                    <div class="card">
                        <h2>🎁 Secure Delivery 🎄</h2>
                        <p style="color: #94a3b8;"><b>Product:</b> {title}</p>
                        {photo_tag}
                        <div class="info">
                            <p><b>📍 Location:</b> <a href="{location_url}" target="_blank" style="color: #38bdf8;">Open Maps</a></p>
                            <p style="margin-bottom:0;"><b>📝 Note:</b> {description}</p>
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

        if parsed_path.path == "/admin-add-promo":
            code = params.get("code", [""])[0].strip()
            try:
                disc = float(params.get("discount", [0])[0])
                limit = int(params.get("limit", [100])[0])
            except:
                disc, limit = 5.0, 100

            if code:
                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO promos (code, discount, usage_limit) VALUES (?, ?, ?)", (code, disc, limit))
                conn.commit()
                conn.close()
                log_panel_event(f"🎟️ Yeni Kupon Eklendi: {code} ({disc} USDT)", "success")

            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=promos')
            self.end_headers()

        elif parsed_path.path == "/admin-broadcast":
            msg_text = params.get("message", [""])[0].strip()
            if msg_text and main_loop:
                conn = sqlite3.connect("drop_bot.db")
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM users WHERE is_banned = 0")
                users = cursor.fetchall()
                conn.close()

                async def send_all():
                    for u in users:
                        try:
                            await bot.send_message(u[0], f"🎄 **Mutlu Yıllar Duyurusu:**\n\n{msg_text}", parse_mode="Markdown")
                            await asyncio.sleep(0.05)
                        except:
                            pass

                asyncio.run_coroutine_threadsafe(send_all(), main_loop)
                log_panel_event(f"📢 Toplu Duyuru Gönderildi ({len(users)} kullanıcıya)", "success")

            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=home')
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
            self.send_response(303)
            self.send_header('Location', '/admin-web?tab=passive')
            self.end_headers()

        elif parsed_path.path == "/admin-approve":
            order_id = params.get("order_id", ["0"])[0]
            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT orders.user_id, drops.id, drops.stock, orders.status, drops.title, orders.final_price, drops.category 
                FROM orders JOIN drops ON orders.drop_id = drops.id WHERE orders.id = ?
            """, (order_id,))
            row = cursor.fetchone()
            if row and row[3] == 'pending':
                u_id, d_id, stock, status, t_title, f_price, t_cat = row
                new_stock = stock - 1
                if new_stock <= 0:
                    cursor.execute("UPDATE drops SET stock = 0, is_sold = 1 WHERE id = ?", (d_id,))
                else:
                    cursor.execute("UPDATE drops SET stock = ? WHERE id = ?", (new_stock, d_id))
                cursor.execute("UPDATE orders SET status = 'completed' WHERE id = ?", (order_id,))
                conn.commit()
                conn.close()
                secure_link = f"{RENDER_EXTERNAL_URL}/drop/{order_id}"
                if main_loop:
                    asyncio.run_coroutine_threadsafe(bot.send_message(u_id, LANG[get_user_lang(u_id)]["success_msg"].format(link=secure_link), parse_mode="Markdown"), main_loop)
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
        <html lang="tr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Admin Giriş</title>
        <style>body {{ background: #020609 url('https://images.unsplash.com/photo-1543589077-47d59746c2a4?auto=format&fit=crop&w=1920&q=80') no-repeat center center fixed; background-size: cover; color: #f8fafc; font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }} .login-card {{ background: rgba(15, 23, 42, 0.9); padding: 35px; border-radius: 20px; border: 1px solid rgba(239, 68, 68, 0.3); width: 100%; max-width: 360px; text-align: center; backdrop-filter: blur(15px); box-shadow: 0 10px 30px rgba(0,0,0,0.5); }} input {{ width: 100%; padding: 12px; margin: 10px 0; background: rgba(5, 10, 14, 0.85); border: 1px solid rgba(255,255,255,0.15); border-radius: 10px; color: white; box-sizing: border-box; }} button {{ background: linear-gradient(135deg, #dc2626, #b91c1c); color: white; padding: 12px; border: none; border-radius: 10px; font-weight: bold; cursor: pointer; width: 100%; margin-top: 15px; box-shadow: 0 4px 15px rgba(220, 38, 38, 0.4); }}</style>
        </head>
        <body><div class="login-card"><h2>🎅 Admin Girişi 🎄</h2>{err_html}<form action="/admin-login" method="POST"><input type="text" name="username" required placeholder="Kullanıcı Adı"><input type="password" name="password" required placeholder="Şifre"><button type="submit">Giriş Yap</button></form></div></body></html>
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

dp = Dispatcher(storage=MemoryStorage())
bot = Bot(token=BOT_TOKEN)

def main_keyboard(lang="tr"):
    t = LANG[lang]
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t["btn_products"]), KeyboardButton(text=t["btn_orders"])],
            [KeyboardButton(text=t["btn_wallet"]), KeyboardButton(text=t["btn_faq"])],
            [KeyboardButton(text=t["btn_support"]), KeyboardButton(text=t["btn_lang"])]
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
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, message.from_user.username))
    conn.commit()
    conn.close()
    lang = get_user_lang(user_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🇹🇷 Türkçe", callback_data="setlang_tr"), InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en")]])
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
    if message.chat.type != "private" or is_user_banned(message.from_user.id): return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🇹🇷 Türkçe", callback_data="setlang_tr"), InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en")]])
    await message.answer("Lütfen dil seçiniz / Please select language:", reply_markup=kb)

@dp.message(F.text.in_([LANG["tr"]["btn_wallet"], LANG["en"]["btn_wallet"]]))
async def wallet_menu(message: types.Message):
    user_id = message.from_user.id
    if message.chat.type != "private" or is_user_banned(user_id): return
    lang = get_user_lang(user_id)
    t = LANG[lang]
    bal = get_user_balance(user_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t["deposit_btn"], callback_data="start_deposit")]])
    await message.answer(t["wallet_menu_text"].format(balance=bal), reply_markup=kb)

@dp.callback_query(F.data == "start_deposit")
async def start_deposit(callback: types.CallbackQuery, state: FSMContext):
    if is_user_banned(callback.from_user.id): return
    lang = get_user_lang(callback.from_user.id)
    await state.set_state(DepositState.amount)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=LANG[lang]["cancel"], callback_data="cancel_deposit")]])
    await callback.message.edit_text(LANG[lang]["ask_deposit_amount"], reply_markup=kb)

@dp.callback_query(F.data == "cancel_deposit")
async def cancel_deposit(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ İşlem iptal edildi.")

@dp.message(DepositState.amount)
async def process_deposit_amount(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if message.chat.type != "private" or is_user_banned(user_id): return
    lang = get_user_lang(user_id)
    t = LANG[lang]
    try:
        amount = float(message.text.strip().replace(",", "."))
        if amount <= 0: raise ValueError()
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
    if is_user_banned(user_id): return
    lang = get_user_lang(user_id)
    t = LANG[lang]
    parts = callback.data.split("_")
    deposit_id = int(parts[1])
    target_amount = float(parts[2])
    await callback.answer(t["scan"], show_alert=True)
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT status, created_at FROM deposits WHERE id = ? AND user_id = ?", (deposit_id, user_id))
    dep = cursor.fetchone()
    if not dep or dep[0] == 'completed':
        conn.close()
        return
    verified = False
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.trongrid.io/v1/accounts/{CRYPTO_WALLET}/trc20-transfers?contract_address={USDT_CONTRACT}&limit=15") as response:
                if response.status == 200:
                    res_json = await response.json()
                    for tx in res_json.get("data", []):
                        if tx.get("to") == CRYPTO_WALLET and int(tx.get("value", 0)) >= int(target_amount * 1000000):
                            verified = True
                            break
    except Exception as e: logging.error(e)

    if verified:
        cursor.execute("UPDATE deposits SET status = 'completed' WHERE id = ?", (deposit_id,))
        conn.commit()
        conn.close()
        update_user_balance(user_id, target_amount)
        new_bal = get_user_balance(user_id)
        await callback.message.edit_text(t["deposit_success"].format(amount=target_amount, balance=new_bal))
        log_panel_event(f"📥 Bakiye Yükleme Onaylandı: Kullanıcı {user_id} - {target_amount} USDT", "success")
    else:
        conn.close()
        await callback.answer(t["wait_tx"], show_alert=True)

@dp.message(F.text.in_([LANG["tr"]["btn_faq"], LANG["en"]["btn_faq"]]))
async def faq_menu(message: types.Message):
    if message.chat.type != "private" or is_user_banned(message.from_user.id): return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💳 Ödeme", callback_data="faq_pay")], [InlineKeyboardButton(text="⏱️ Teslimat", callback_data="faq_delivery")]])
    await message.answer("💡 **FAQ / SSS**", reply_markup=kb)

@dp.callback_query(F.data.startswith("faq_"))
async def faq_callback(callback: types.CallbackQuery):
    if is_user_banned(callback.from_user.id): return
    lang = get_user_lang(callback.from_user.id)
    text = "💳 Cüzdanınıza bakiye yükleyerek ürün alabilirsiniz." if callback.data.split("_")[1] == "pay" else "⏱️ Ödeme onaylanınca şifreli web bağlantısı anında iletilir."
    await callback.answer()
    await callback.message.answer(text)

@dp.message(F.text.in_([LANG["tr"]["btn_support"], LANG["en"]["btn_support"]]))
async def support_start(message: types.Message, state: FSMContext):
    if message.chat.type != "private" or is_user_banned(message.from_user.id): return
    await state.set_state(SupportState.message)
    await message.answer(LANG[get_user_lang(message.from_user.id)]["support_ask"])

@dp.message(SupportState.message)
async def forward_support_to_group(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if message.chat.type != "private" or is_user_banned(user_id): return
    lang = get_user_lang(user_id)
    user_msg = message.text
    username = message.from_user.username or "Bulunmuyor"
    await state.clear()
    await message.answer(LANG[lang]["support_sent"])
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO support_tickets (user_id, username, message, status) VALUES (?, ?, ?, 'open')", (user_id, username, user_msg))
    conn.commit()
    conn.close()
    await bot.send_message(ADMIN_GROUP_ID, f"📩 **YENİ DESTEK TALEBİ**\n\n👤 Kullanıcı ID: `{user_id}`\n\n💬 Mesaj:\n{user_msg}")

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    if message.chat.type != "private" or not is_admin(message.from_user.id): return
    await state.set_state(AdminPassState.password)
    await message.answer("🔐 Yönetim paneli şifresini girin:")

@dp.message(AdminPassState.password)
async def process_admin_password(message: types.Message, state: FSMContext):
    if message.text.strip() == "1881":
        await state.clear()
        await message.answer("✅ Şifre Doğru!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🌐 Web Paneline Git", url=f"{RENDER_EXTERNAL_URL}/admin-web")]]))
    else:
        await state.clear()
        await message.answer("❌ Hatalı şifre!")

@dp.message(F.text.in_([LANG["tr"]["btn_products"], LANG["en"]["btn_products"]]))
async def list_categories(message: types.Message):
    if message.chat.type != "private" or is_user_banned(message.from_user.id): return
    lang = get_user_lang(message.from_user.id)
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM drops WHERE is_sold = 0 AND stock > 0")
    categories = cursor.fetchall()
    conn.close()
    if not categories:
        await message.answer(LANG[lang]["no_stock"])
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"🏙️ {cat[0] or 'Genel'}", callback_data=f"cat_{cat[0] or 'Genel'}")] for cat in categories])
    await message.answer(LANG[lang]["select_cat"], reply_markup=kb)

@dp.callback_query(F.data.startswith("cat_"))
async def list_drops_by_category(callback: types.CallbackQuery):
    if is_user_banned(callback.from_user.id): return
    lang = get_user_lang(callback.from_user.id)
    cat_name = callback.data.split("_", 1)[1]
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, price, stock FROM drops WHERE category = ? AND is_sold = 0 AND stock > 0", (cat_name,))
    drops = cursor.fetchall()
    conn.close()
    if not drops:
        await callback.answer(LANG[lang]["no_cat_stock"], show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{d[1]} - {d[2]} USDT", callback_data=f"buy_{d[0]}")] for d in drops])
    kb.inline_keyboard.append([InlineKeyboardButton(text=LANG[lang]["back_cats"], callback_data="back_cats")])
    await callback.message.edit_text(f"📦 **{cat_name}**:", reply_markup=kb)

@dp.callback_query(F.data == "back_cats")
async def back_to_cats(callback: types.CallbackQuery):
    if is_user_banned(callback.from_user.id): return
    lang = get_user_lang(callback.from_user.id)
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM drops WHERE is_sold = 0 AND stock > 0")
    categories = cursor.fetchall()
    conn.close()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"🏙️ {cat[0] or 'Genel'}", callback_data=f"cat_{cat[0] or 'Genel'}")] for cat in categories])
    await callback.message.edit_text(LANG[lang]["select_cat"], reply_markup=kb)

@dp.message(F.text.in_([LANG["tr"]["btn_orders"], LANG["en"]["btn_orders"]]))
async def my_orders(message: types.Message):
    user_id = message.from_user.id
    if message.chat.type != "private" or is_user_banned(user_id): return
    lang = get_user_lang(user_id)
    t = LANG[lang]
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT orders.id, drops.title, orders.final_price, orders.status, orders.created_at FROM orders JOIN drops ON orders.drop_id = drops.id WHERE orders.user_id = ? ORDER BY orders.id DESC", (user_id,))
    orders = cursor.fetchall()
    conn.close()
    if not orders:
        await message.answer(t["no_orders"])
        return
    text = t["my_orders_title"] + "\n\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for o in orders:
        text += t["order_item"].format(id=o[0], title=o[1], price=o[2], status=o[3], date=o[4])
        if o[3] == 'completed':
            kb.inline_keyboard.append([InlineKeyboardButton(text=t["open_loc"].format(id=o[0]), url=f"{RENDER_EXTERNAL_URL}/drop/{o[0]}")])
    await message.answer(text, reply_markup=kb if kb.inline_keyboard else None)

@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: types.CallbackQuery):
    if is_user_banned(callback.from_user.id): return
    lang = get_user_lang(callback.from_user.id)
    t = LANG[lang]
    drop_id = int(callback.data.split("_")[1])
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT title, price FROM drops WHERE id = ? AND is_sold = 0 AND stock > 0", (drop_id,))
    drop = cursor.fetchone()
    conn.close()
    if not drop:
        await callback.answer(t["sold_out"], show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["pay_balance"].format(price=drop[1]), callback_data=f"buybal_{drop_id}")],
        [InlineKeyboardButton(text=t["pay_crypto"], callback_data=f"buycrypto_{drop_id}")],
        [InlineKeyboardButton(text=t["pay_promo"], callback_data=f"usepromo_{drop_id}")]
    ])
    await callback.message.edit_text(t["buy_options"].format(title=drop[0], price=drop[1], balance=get_user_balance(callback.from_user.id)), reply_markup=kb)

@dp.callback_query(F.data.startswith("buybal_"))
async def process_buy_with_balance(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if is_user_banned(user_id): return
    lang = get_user_lang(user_id)
    t = LANG[lang]
    drop_id = int(callback.data.split("_")[1])
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT title, price, stock, category FROM drops WHERE id = ? AND is_sold = 0 AND stock > 0", (drop_id,))
    drop = cursor.fetchone()
    if not drop or get_user_balance(user_id) < drop[1]:
        await callback.answer(t["insufficient_balance"], show_alert=True)
        conn.close()
        return
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (drop[1], user_id))
    new_stock = drop[2] - 1
    if new_stock <= 0: cursor.execute("UPDATE drops SET stock = 0, is_sold = 1 WHERE id = ?", (drop_id,))
    else: cursor.execute("UPDATE drops SET stock = ? WHERE id = ?", (new_stock, drop_id))
    cursor.execute("INSERT INTO orders (user_id, drop_id, status, final_price) VALUES (?, ?, 'completed', ?)", (user_id, drop_id, drop[1]))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    await callback.message.edit_text(t["balance_success"].format(price=drop[1], link=f"{RENDER_EXTERNAL_URL}/drop/{order_id}"), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("buycrypto_"))
async def process_buy_crypto(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if is_user_banned(user_id): return
    lang = get_user_lang(user_id)
    t = LANG[lang]
    drop_id = int(callback.data.split("_")[1])
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT title, price FROM drops WHERE id = ? AND is_sold = 0 AND stock > 0", (drop_id,))
    drop = cursor.fetchone()
    if not drop:
        await callback.answer(t["sold_out"], show_alert=True)
        conn.close()
        return
    cursor.execute("INSERT INTO orders (user_id, drop_id, status, final_price) VALUES (?, ?, 'pending', ?)", (user_id, drop_id, drop[1]))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    msg = t["order_created"].format(id=order_id, title=drop[0]) + f"💰 Total: {drop[1]} USDT\n\n" + t["wallet_text"].format(wallet=CRYPTO_WALLET)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t["check_btn"], callback_data=f"autocheck_{order_id}")]])
    await callback.message.edit_text(msg, reply_markup=kb)

@dp.callback_query(F.data.startswith("usepromo_"))
async def ask_promo_code(callback: types.CallbackQuery, state: FSMContext):
    if is_user_banned(callback.from_user.id): return
    lang = get_user_lang(callback.from_user.id)
    drop_id = int(callback.data.split("_")[1])
    await state.update_data(drop_id=drop_id)
    await state.set_state(PromoState.code)
    await callback.message.edit_text(LANG[lang]["ask_promo"])

@dp.message(PromoState.code)
async def verify_promo_code(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if message.chat.type != "private" or is_user_banned(user_id): return
    lang = get_user_lang(user_id)
    t = LANG[lang]
    data = await state.get_data()
    drop_id = data.get("drop_id")
    entered_code = message.text.strip()
    await state.clear()

    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT title, price FROM drops WHERE id = ? AND is_sold = 0 AND stock > 0", (drop_id,))
    drop = cursor.fetchone()
    
    cursor.execute("SELECT discount, usage_limit, used_count FROM promos WHERE code = ?", (entered_code,))
    promo = cursor.fetchone()

    if not drop:
        conn.close()
        await message.answer(t["invalid_drop"])
        return

    if promo and promo[2] < promo[1]:
        disc = promo[0]
        final_price = max(0.0, drop[1] - disc)
        cursor.execute("UPDATE promos SET used_count = used_count + 1 WHERE code = ?", (entered_code,))
        promo_applied = True
    else:
        final_price = drop[1]
        promo_applied = False

    cursor.execute("INSERT INTO orders (user_id, drop_id, status, final_price) VALUES (?, ?, 'pending', ?)", (user_id, drop_id, final_price))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    msg = t["order_created"].format(id=order_id, title=drop[0])
    if promo_applied: msg += t["promo_applied"].format(price=drop[1], discount=disc, final=final_price)
    else: msg += t["promo_invalid"].format(final=final_price)
    msg += t["wallet_text"].format(wallet=CRYPTO_WALLET)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t["check_btn"], callback_data=f"autocheck_{order_id}")]])
    await message.answer(msg, reply_markup=kb)

@dp.callback_query(F.data.startswith("autocheck_"))
async def check_blockchain_payment(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if is_user_banned(user_id): return
    lang = get_user_lang(user_id)
    t = LANG[lang]
    order_id = int(callback.data.split("_")[1])
    await callback.answer(t["scan"], show_alert=True)
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT orders.user_id, drops.id, drops.stock, orders.status, drops.title, orders.final_price FROM orders JOIN drops ON orders.drop_id = drops.id WHERE orders.id = ?", (order_id,))
    data = cursor.fetchone()
    if not data or data[3] != 'pending':
        conn.close()
        return
    
    verified = False
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.trongrid.io/v1/accounts/{CRYPTO_WALLET}/trc20-transfers?contract_address={USDT_CONTRACT}&limit=10") as response:
                if response.status == 200:
                    for tx in (await response.json()).get("data", []):
                        if tx.get("to") == CRYPTO_WALLET and int(tx.get("value", 0)) >= int(float(data[5]) * 1000000):
                            verified = True
                            break
    except Exception as e: logging.error(e)

    if verified:
        new_stock = data[2] - 1
        if new_stock <= 0: cursor.execute("UPDATE drops SET stock = 0, is_sold = 1 WHERE id = ?", (data[1],))
        else: cursor.execute("UPDATE drops SET stock = ? WHERE id = ?", (new_stock, data[1]))
        cursor.execute("UPDATE orders SET status = 'completed' WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()
        await callback.message.edit_text(t["success_order"].format(id=order_id))
        await bot.send_message(user_id, t["success_msg"].format(link=f"{RENDER_EXTERNAL_URL}/drop/{order_id}"), parse_mode="Markdown")
    else:
        conn.close()
        await callback.answer(t["wait_tx"], show_alert=True)

@dp.message()
async def handle_admin_group_reply(message: types.Message):
    if message.chat.id == ADMIN_GROUP_ID and message.reply_to_message:
        match = re.search(r"Kullanıcı ID:\s*`(\d+)`", message.reply_to_message.text or "")
    if match:
            try:
                await bot.send_message(int(match.group(1)), f"💬 **Destek Ekibi Yanıtı:**\n\n{message.text}")
                await message.reply("✅ Yanıt iletildi.")
            except Exception as e: await message.reply(f"⚠️ Hata: {e}")

async def main():
    global main_loop
    main_loop = asyncio.get_running_loop()
    asyncio.create_task(auto_backup_task())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
