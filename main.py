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

# --- AYARLAR ---
BOT_TOKEN = "8994954068:AAFWrg9dLaMrXkK2uR2vpTTNke84vn449RM"
ADMIN_ID = 1012940363
ADMIN_GROUP_ID = -1004474292737  

ADMIN_WEB_USERNAME = "dionisus"
ADMIN_WEB_PASSWORD = "weedstanbul34"

PROMO_CODE = "welcomeweedstanbul"
PROMO_DISCOUNT = 8.0

CRYPTO_WALLET = "TMDAC83GTrxDCQiQBCEEL11CdHBYPSMpjH"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://senin-botun.onrender.com")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
main_loop = None

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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")
    except:
        pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)
    ''')
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (ADMIN_ID,))
    conn.commit()
    conn.close()

init_db()

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

# --- OTOMATİK VERİTABANI YEDEĞİ GÖREVİ (24 Saatte Bir) ---
async def auto_backup_task():
    while True:
        await asyncio.sleep(86400) # 24 Saat
        try:
            if os.path.exists("drop_bot.db"):
                file = FSInputFile("drop_bot.db")
                await bot.send_document(ADMIN_GROUP_ID, file, caption="💾 **Otomatik Günlük Veritabanı Yedeği**")
                log_panel_event("💾 Günlük otomatik veritabanı yedeği alındı.", "info")
        except Exception as e:
            logging.error(f"Yedek alma hatası: {e}")

# --- GELİŞMİŞ WEB SUNUCUSU (PROFESYONEL UI) ---
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
                    badge_color = "#ef4444" if l_type == "warning" else ("#10b981" if l_type == "success" else "#3b82f6")
                    logs_html += f"""
                    <div style="background: #0f172a; padding: 12px 15px; border-radius: 8px; margin-bottom: 8px; border-left: 4px solid {badge_color}; font-size: 13px;">
                        <span style="color: #64748b; font-size: 11px; display: block; margin-bottom: 2px;">{l_date}</span>
                        {msg}
                    </div>
                    """

                # Chart.js Verileri
                cursor.execute("""
                    SELECT DATE(created_at) as cday, SUM(final_price) 
                    FROM orders WHERE status = 'completed' 
                    GROUP BY cday ORDER BY cday ASC LIMIT 7
                """)
                chart_rows = cursor.fetchall()
                labels = [r[0] for r in chart_rows] if chart_rows else ["Bugün"]
                values = [r[1] for r in chart_rows] if chart_rows else [total_revenue]

                content_html = f"""
                <div class="stats-grid">
                    <div class="card"><h3>TOTAL REVENUE</h3><p>{total_revenue} USDT</p></div>
                    <div class="card"><h3>ACTIVE STOCK</h3><p>{total_active_stock} Pcs</p></div>
                    <div class="card"><h3>PRODUCT VARIETY</h3><p>{total_drops}</p></div>
                </div>

                <div class="grid-2">
                    <div class="table-box">
                        <h2>📊 Weekly Revenue Trend</h2>
                        <canvas id="revenueChart" style="max-height: 250px;"></canvas>
                    </div>

                    <div class="table-box">
                        <h2>🔔 Live Logs & Alerts</h2>
                        <div style="max-height: 250px; overflow-y: auto;">
                            {logs_html if logs_html else "<p style='text-align:center; color:#64748b;'>No recent logs.</p>"}
                        </div>
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
                                x: {{ grid: {{ color: '#334155' }}, ticks: {{ color: '#94a3b8' }} }},
                                y: {{ grid: {{ color: '#334155' }}, ticks: {{ color: '#94a3b8' }} }}
                            }}
                        }}
                    }});
                </script>
                """
            elif tab == "users":
                cursor.execute("SELECT user_id, username, is_banned FROM users ORDER BY user_id DESC")
                users_list = cursor.fetchall()
                rows = ""
                for u in users_list:
                    uid, uname, is_b = u
                    username_str = f"@{uname}" if uname else "N/A"
                    status_badge = "<span style='color:#ef4444; font-weight:bold;'>BANNED</span>" if is_b == 1 else "<span style='color:#10b981; font-weight:bold;'>ACTIVE</span>"
                    ban_btn = f"""
                    <form action="/admin-ban" method="POST" style="margin:0; display:inline;">
                        <input type="hidden" name="user_id" value="{uid}">
                        <input type="hidden" name="action" value="{'unban' if is_b == 1 else 'ban'}">
                        <button type="submit" style="background:{'#10b981' if is_b == 1 else '#ef4444'}; padding:5px 10px; font-size:11px; width:auto;">
                            {'Unban User' if is_b == 1 else 'Ban User'}
                        </button>
                    </form>
                    """
                    rows += f"<tr><td>{uid}</td><td>{username_str}</td><td>{status_badge}</td><td>{ban_btn}</td></tr>"

                content_html = f"""
                <div class="table-box">
                    <h2>👥 User Management (CRM)</h2>
                    <table>
                        <tr><th>User ID</th><th>Username</th><th>Status</th><th>Action</th></tr>
                        {rows if rows else "<tr><td colspan='4' style='text-align:center;'>No users registered yet.</td></tr>"}
                    </table>
                </div>
                """
            elif tab == "active":
                cursor.execute("""
                    SELECT orders.id, users.username, drops.title, orders.final_price, orders.status, orders.created_at 
                    FROM orders 
                    JOIN drops ON orders.drop_id = drops.id 
                    LEFT JOIN users ON orders.user_id = users.user_id
                    WHERE orders.status = 'completed'
                    ORDER BY orders.id DESC
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
                        <tr><th>Sipariş ID</th><th>Kullanıcı Adı</th><th>Ürün</th><th>Tutar</th><th>Durum</th><th>Tarih</th></tr>
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
                cursor.execute("SELECT id, title, price, stock, category, description, location_url FROM drops WHERE is_sold = 0")
                drops = cursor.fetchall()
                rows = ""
                for d in drops:
                    d_id, title, price, stock, cat, desc, loc = d
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
                    <h2>📦 Pasif / Stoktaki Ürünler (Düzenlenebilir)</h2>
                    <table>
                        <tr><th>ID</th><th>Başlık</th><th>Bölge/Kategori</th><th>Fiyat</th><th>Stok</th><th>İşlem</th></tr>
                        {rows if rows else "<tr><td colspan='6' style='text-align:center;'>Stokta ürün bulunmuyor.</td></tr>"}
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
                        <input type="text" name="category" required placeholder="Örn: Kadıköy, Taksim vb.">
                        
                        <label>Fiyat (USDT):</label>
                        <input type="number" step="0.1" name="price" required placeholder="65">
                        
                        <label>Kaç Adet Ekleyeceksin? (Stok):</label>
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
                                <div style="background: #0f172a; padding: 15px; border-radius: 8px; margin-top: 15px; border: 1px solid #334155;">
                                    <h4 style="color: #38bdf8; margin-top: 0;">📍 Drop #${i} Detayları</h4>
                                    <label>Google Maps Konum Linki:</label>
                                    <input type="text" name="location_${i}" required placeholder="https://maps.app.goo.gl/...">
                                    <label>Fotoğraf URL'si (Görsel Linki):</label>
                                    <input type="text" name="photo_${i}" placeholder="https://imgur.com/... veya resim linki">
                                    <label>Açıklama / İpucu Notu:</label>
                                    <textarea name="description_${i}" rows="2" required placeholder="Bina arkasında saksının içinde..."></textarea>
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
                    <div class="form-box" style="border: 2px solid #38bdf8; margin-bottom: 30px;">
                        <h2>✏️ Ürün Düzenle (ID: #{edit_id})</h2>
                        <form action="/admin-update" method="POST">
                            <input type="hidden" name="id" value="{edit_id}">
                            <label>Ürün Başlığı:</label>
                            <input type="text" name="title" value="{e_title}" required>
                            <label>Semt / Şehir (Kategori):</label>
                            <input type="text" name="category" value="{e_cat or 'Genel'}" required>
                            <label>Fiyat (USDT):</label>
                            <input type="number" step="0.1" name="price" value="{e_price}" required>
                            <label>Stok Adedi:</label>
                            <input type="number" name="stock" value="{e_stock}" required>
                            <label>Google Maps Konum Linki:</label>
                            <input type="text" name="location" value="{e_loc}" required>
                            <label>Fotoğraf URL'si (Görsel Linki):</label>
                            <input type="text" name="photo" value="{e_photo}" placeholder="https://...">
                            <label>Açıklama / İpucu Notu:</label>
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
                <title>Weed Istanbul Yönetim Paneli</title>
                <style>
                    body {{ background-color: #090d16; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; display: flex; min-height: 100vh; }}
                    
                    /* Modern Sleek Sidebar */
                    .sidebar {{ width: 260px; background: #111827; border-right: 1px solid #1f2937; display: flex; flex-direction: column; padding: 25px 18px; box-sizing: border-box; }}
                    .sidebar .brand {{ font-size: 20px; font-weight: 800; color: #38bdf8; text-align: center; margin-bottom: 30px; letter-spacing: 0.5px; }}
                    .sidebar a {{ background: transparent; color: #9ca3af; padding: 12px 16px; border-radius: 10px; text-decoration: none; font-weight: 600; font-size: 14px; margin-bottom: 6px; border: 1px solid transparent; transition: all 0.2s ease; display: block; }}
                    .sidebar a.active, .sidebar a:hover {{ background: #1e293b; color: #38bdf8; border-color: #334155; }}
                    .logout-link {{ background: #ef4444 !important; color: white !important; margin-top: auto; text-align: center; border: none !important; }}
                    .logout-link:hover {{ background: #dc2626 !important; }}
                    
                    /* Right Main Content Panel */
                    .main-content {{ flex: 1; padding: 35px; box-sizing: border-box; overflow-y: auto; max-width: 1200px; }}
                    .header-title {{ color: #f8fafc; font-size: 26px; font-weight: 700; margin-top: 0; margin-bottom: 30px; border-bottom: 1px solid #1f2937; padding-bottom: 15px; }}
                    
                    .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin-bottom: 30px; }}
                    .card {{ background: #111827; padding: 22px; border-radius: 14px; border: 1px solid #1f2937; text-align: center; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2); }}
                    .card h3 {{ margin: 0 0 10px 0; color: #6b7280; font-size: 13px; font-weight: 700; letter-spacing: 0.5px; }}
                    .card p {{ margin: 0; font-size: 26px; font-weight: 800; color: #38bdf8; }}
                    
                    .grid-2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }}
                    .form-box, .table-box {{ background: #111827; padding: 25px; border-radius: 14px; border: 1px solid #1f2937; margin-bottom: 30px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2); }}
                    input, textarea {{ width: 100%; padding: 12px; margin: 8px 0 16px 0; background: #090d16; border: 1px solid #374151; border-radius: 8px; color: white; box-sizing: border-box; font-size: 14px; }}
                    button {{ background: #2563eb; color: white; padding: 12px 20px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%; font-size: 14px; transition: 0.2s; }}
                    button:hover {{ background: #1d4ed8; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                    th, td {{ padding: 12px 14px; text-align: left; border-bottom: 1px solid #1f2937; font-size: 14px; }}
                    th {{ color: #6b7280; font-weight: 700; font-size: 12px; text-transform: uppercase; }}
                    .action-btn {{ padding: 6px 12px; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: bold; }}
                    .edit-btn {{ background: #d97706; color: white; }}
                    .edit-btn:hover {{ background: #b45309; }}

                    @media (max-width: 768px) {{
                        body {{ flex-direction: column; }}
                        .sidebar {{ width: 100%; flex-direction: row; flex-wrap: wrap; gap: 5px; padding: 15px; }}
                        .sidebar .brand {{ width: 100%; margin-bottom: 15px; }}
                        .sidebar a {{ flex: 1; min-width: 100px; font-size: 12px; text-align: center; padding: 10px 5px; margin-bottom: 0; }}
                        .main-content {{ padding: 20px; }}
                        .grid-2 {{ grid-template-columns: 1fr; }}
                    }}
                </style>
            </head>
            <body>
                <div class="sidebar">
                    <div class="brand">🌿 Weed Istanbul</div>
                    <a href="/admin-web?tab=home" class="{"active" if tab == "home" else ""}">🏠 Ana Sayfa</a>
                    <a href="/admin-web?tab=active" class="{"active" if tab == "active" else ""}">🟢 Aktif Siparişler</a>
                    <a href="/admin-web?tab=pending" class="{"active" if tab == "pending" else ""}">⏳ Bekleyenler</a>
                    <a href="/admin-web?tab=passive" class="{"active" if tab in ["passive", "edit"] else ""}">📦 Pasif Ürünler</a>
                    <a href="/admin-web?tab=add" class="{"active" if tab == "add" else ""}">➕ Drop Ekle</a>
                    <a href="/admin-web?tab=users" class="{"active" if tab == "users" else ""}">👥 Müşteriler (CRM)</a>
                    <a href="/admin-logout" class="logout-link">🚪 Çıkış Yap</a>
                </div>

                <div class="main-content">
                    <h1 class="header-title">👑 Weed Istanbul Management System</h1>
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
                    FROM orders 
                    JOIN drops ON orders.drop_id = drops.id 
                    WHERE orders.id = ?
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
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Güvenli Teslimat - #{order_id}</title>
                    <style>
                        body {{ background-color: #090d16; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }}
                        .card {{ background: #111827; padding: 25px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); width: 100%; max-width: 420px; text-align: center; border: 1px solid #1f2937; }}
                        h2 {{ color: #38bdf8; margin-top: 0; }}
                        .info {{ background: #090d16; padding: 15px; border-radius: 8px; margin: 15px 0; text-align: left; word-break: break-all; font-size: 14px; border: 1px solid #374151; }}
                        .btn {{ display: block; background: #2563eb; color: white; padding: 12px; border-radius: 8px; text-decoration: none; font-weight: bold; margin-top: 15px; transition: background 0.2s; }}
                        .btn:hover {{ background: #1d4ed8; }}
                        .warning {{ color: #ef4444; font-size: 12px; margin-top: 15px; }}
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h2>🔒 Güvenli Teslimat</h2>
                        <p style="margin-bottom: 15px;"><b>Ürün:</b> {title}</p>
                        {photo_tag}
                        <div class="info">
                            <p><b>📍 Konum:</b> <a href="{location_url}" target="_blank" style="color: #38bdf8;">Haritada Açmak İçin Tıkla</a></p>
                            <p><b>📝 İpucu Notu:</b> {description}</p>
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

        if parsed_path.path == "/admin-ban":
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
            try:
                price = float(params.get("price", [0])[0])
                count = int(params.get("count", [1])[0])
            except:
                price, count = 0.0, 1

            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()

            for i in range(1, count + 1):
                loc = params.get(f"location_{i}", [""])[0]
                photo = params.get(f"photo_{i}", [""])[0]
                desc = params.get(f"description_{i}", [""])[0]
                if loc and desc:
                    cursor.execute("""
                        INSERT INTO drops (title, price, location_url, photo_ids, description, stock, category)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (title, price, loc, photo, desc, 1, category))

            conn.commit()
            conn.close()

            log_panel_event(f"➕ Yeni Ürün Eklendi: {title} ({count} Adet, Bölge: {category})", "success")

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
            location = params.get("location", [""])[0]
            photo = params.get("photo", [""])[0]
            description = params.get("description", [""])[0]

            conn = sqlite3.connect("drop_bot.db")
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE drops SET title = ?, price = ?, stock = ?, category = ?, location_url = ?, photo_ids = ?, description = ?
                WHERE id = ?
            """, (title, price, stock, category, location, photo, description, drop_id))
            conn.commit()
            conn.close()

            log_panel_event(f"✏️ Ürün Güncellendi: #{drop_id} - {title}", "info")

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
                    
                    cursor.execute("SELECT SUM(stock) FROM drops WHERE category = ? AND is_sold = 0", (t_cat,))
                    rem_stock = cursor.fetchone()[0] or 0

                    conn.commit()
                    conn.close()

                    secure_link = f"{RENDER_EXTERNAL_URL}/drop/{order_id}"

                    log_msg = f"🎉 Manuel Onay & Satış: #{order_id} - {t_title} ({f_price} USDT)"
                    log_panel_event(log_msg, "success")

                    if main_loop:
                        asyncio.run_coroutine_threadsafe(
                            bot.send_message(u_id, f"🎉 Ödemeniz admin tarafından onaylandı!\n\n👉 [Güvenli Konum Sayfasını Aç]({secure_link})", parse_mode="Markdown"),
                            main_loop
                        )
                        asyncio.run_coroutine_threadsafe(
                            bot.send_message(ADMIN_GROUP_ID, f"🎉 **MANUEL ONAY / SATIŞ GERÇEKLEŞTİ!**\n\n📌 Ürün: {t_title}\n💰 Tutar: {f_price} USDT\n👤 Alıcı ID: `{u_id}`\n🆔 Sipariş ID: `#{order_id}`"),
                            main_loop
                        )
                        if rem_stock <= 2:
                            warn_msg = f"⚠️ KRİTİK STOK UYARISI: {t_cat} bölgesinde kalan aktif stok: {rem_stock} adet!"
                            log_panel_event(warn_msg, "warning")
                            asyncio.run_coroutine_threadsafe(
                                bot.send_message(ADMIN_GROUP_ID, f"⚠️ **KRİTİK STOK UYARISI!**\n\n🏙️ `{t_cat}` bölgesinde toplam kalan aktif stok: **{rem_stock} adet**! Takviye yapman önerilir."),
                                main_loop
                            )
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
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Admin Giriş</title>
            <style>
                body {{ background-color: #090d16; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
                .login-card {{ background: #111827; padding: 35px; border-radius: 16px; border: 1px solid #1f2937; width: 100%; max-width: 350px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
                h2 {{ color: #38bdf8; margin-top: 0; }}
                input {{ width: 100%; padding: 12px; margin: 10px 0; background: #090d16; border: 1px solid #374151; border-radius: 8px; color: white; box-sizing: border-box; }}
                button {{ background: #2563eb; color: white; padding: 12px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%; margin-top: 10px; font-size: 14px; }}
                button:hover {{ background: #1d4ed8; }}
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
        err_html = f"""
        <!DOCTYPE html>
        <html lang="tr">
        <head><meta charset="UTF-8"><title>Hata</title></head>
        <body style="background:#090d16;color:#f8fafc;font-family:sans-serif;text-align:center;padding-top:50px;">
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

# --- FSM VE BOT KODLARI ---
class AdminPassState(StatesGroup):
    password = State()

class SupportState(StatesGroup):
    message = State()

class PromoState(StatesGroup):
    code = State()

dp = Dispatcher(storage=MemoryStorage())
bot = Bot(token=BOT_TOKEN)

def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍️ Ürünler / Droplar"), KeyboardButton(text="📦 Geçmiş Siparişlerim")],
            [KeyboardButton(text="❓ Nasıl Çalışır? (SSS)"), KeyboardButton(text="📞 Destek")]
        ],
        resize_keyboard=True
    )

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.chat.type != "private":
        return
    if is_user_banned(message.from_user.id):
        await message.answer("❌ Erişiminiz engellenmiştir.")
        return
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, username) VALUES (?, ?)", (message.from_user.id, message.from_user.username))
    conn.commit()
    conn.close()
    await message.answer("👋 Merhaba! Güvenli otomatik teslimat botuna hoş geldiniz.", reply_markup=main_keyboard())

@dp.message(F.text == "❓ Nasıl Çalışır? (SSS)")
async def faq_menu(message: types.Message):
    if message.chat.type != "private" or is_user_banned(message.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Ödeme Nasıl Yapılır?", callback_data="faq_pay")],
        [InlineKeyboardButton(text="⏱️ Teslimat Süreci", callback_data="faq_delivery")],
        [InlineKeyboardButton(text="🔒 Gizlilik", callback_data="faq_security")]
    ])
    await message.answer("💡 **Sık Sorulan Sorular (SSS)**", reply_markup=kb)

@dp.callback_query(F.data.startswith("faq_"))
async def faq_callback(callback: types.CallbackQuery):
    if is_user_banned(callback.from_user.id):
        return
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
    if message.chat.type != "private" or is_user_banned(message.from_user.id):
        return
    await state.set_state(SupportState.message)
    await message.answer("📞 Destek mesajınızı yazın, admin grubuna iletilsin:")

@dp.message(SupportState.message)
async def forward_support_to_group(message: types.Message, state: FSMContext):
    if message.chat.type != "private" or is_user_banned(message.from_user.id):
        return
    user_msg = message.text
    user_id = message.from_user.id
    username = message.from_user.username or "Bulunmuyor"
    await state.clear()
    await message.answer("✅ Destek mesajınız admin grubuna iletildi.")
    try:
        conn = sqlite3.connect("drop_bot.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        conn.commit()
        conn.close()
        log_panel_event(f"📩 Yeni Destek Talebi: @{username} (ID: {user_id})", "info")
        await bot.send_message(ADMIN_GROUP_ID, f"📩 **YENİ DESTEK TALEBİ**\n\n👤 Kullanıcı ID: `{user_id}`\nKullanıcı Adı: @{username}\n\n💬 Mesaj:\n{user_msg}")
    except Exception as e:
        logging.error(e)

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    if message.chat.type != "private" or not is_admin(message.from_user.id):
        return
    await state.set_state(AdminPassState.password)
    await message.answer("🔐 Yönetim paneline erişmek için lütfen admin şifresini girin:")

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
        await message.answer("❌ Hatalı şifre! Erişim reddedildi.")

@dp.callback_query(F.data == "stats")
async def show_stats(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), SUM(stock) FROM drops WHERE is_sold = 0")
    res = cursor.fetchone()
    cursor.execute("SELECT SUM(final_price) FROM orders WHERE status = 'completed'")
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

# --- 🏙️ KATEGORİ SEÇİM SİSTEMİ ---
@dp.message(F.text == "🛍️ Ürünler / Droplar")
async def list_categories(message: types.Message):
    if message.chat.type != "private" or is_user_banned(message.from_user.id):
        return
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM drops WHERE is_sold = 0 AND stock > 0")
    categories = cursor.fetchall()
    conn.close()

    if not categories:
        await message.answer("❌ Şu anda stokta hazır drop bulunmamaktadır.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in categories:
        c_name = cat[0] or "Genel"
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"🏙️ {c_name}", callback_data=f"cat_{c_name}")])
    
    await message.answer("🏙️ Lütfen ürünleri incelemek istediğiniz **bölgeyi / semti** seçin:", reply_markup=kb)

@dp.callback_query(F.data.startswith("cat_"))
async def list_drops_by_category(callback: types.CallbackQuery):
    if is_user_banned(callback.from_user.id):
        return
    cat_name = callback.data.split("_", 1)[1]
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, price, stock FROM drops WHERE category = ? AND is_sold = 0 AND stock > 0", (cat_name,))
    drops = cursor.fetchall()
    conn.close()

    if not drops:
        await callback.answer("Bu bölgede aktif ürün kalmadı.", show_alert=True)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for d in drops:
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{d[1]} - {d[2]} USDT (Stok: {d[3]})", callback_data=f"buy_{d[0]}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Bölgelere Dön", callback_data="back_cats")])

    await callback.message.edit_text(f"📦 **{cat_name}** bölgesindeki mevcut droplar:", reply_markup=kb)

@dp.callback_query(F.data == "back_cats")
async def back_to_cats(callback: types.CallbackQuery):
    if is_user_banned(callback.from_user.id):
        return
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM drops WHERE is_sold = 0 AND stock > 0")
    categories = cursor.fetchall()
    conn.close()

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in categories:
        c_name = cat[0] or "Genel"
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"🏙️ {c_name}", callback_data=f"cat_{c_name}")])
    
    await callback.message.edit_text("🏙️ Lütfen ürünleri incelemek istediğiniz **bölgeyi / semti** seçin:", reply_markup=kb)

# --- 📦 GEÇMİŞ SİPARİŞLERİM ---
@dp.message(F.text == "📦 Geçmiş Siparişlerim")
async def my_orders(message: types.Message):
    if message.chat.type != "private" or is_user_banned(message.from_user.id):
        return
    user_id = message.from_user.id
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
        await message.answer("📦 Henüz bir sipariş geçmişiniz bulunmuyor.")
        return

    text = "📦 **Sipariş Geçmişiniz:**\n\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for o in orders:
        o_id, title, f_price, status, date = o
        status_emoji = "🟢 Tamamlandı" if status == 'completed' else ("⏰ Süresi Doldu" if status == 'expired' else "⏳ Onay Bekliyor")
        text += f"• **Sipariş #{o_id}** | {title} - {f_price} USDT\n  Durum: {status_emoji} ({date})\n\n"
        if status == 'completed':
            secure_link = f"{RENDER_EXTERNAL_URL}/drop/{o_id}"
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"🔗 Sipariş #{o_id} Konumunu Aç", url=secure_link)])

    await message.answer(text, reply_markup=kb if kb.inline_keyboard else None)

# --- 🎟️ PROMO KODLU SATIN ALMA AKIŞI ---
@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: types.CallbackQuery, state: FSMContext):
    if is_user_banned(callback.from_user.id):
        return
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
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟️ İndirim Kuponu Kullan", callback_data=f"usepromo_{drop_id}")],
        [InlineKeyboardButton(text="💳 Kuponsuz Devam Et", callback_data=f"nopromo_{drop_id}")]
    ])
    await callback.message.edit_text(f"📌 Ürün: {title}\n💰 Normal Tutar: {price} USDT\n\nİndirim kuponu kullanmak ister misiniz?", reply_markup=kb)

@dp.callback_query(F.data.startswith("usepromo_"))
async def ask_promo_code(callback: types.CallbackQuery, state: FSMContext):
    if is_user_banned(callback.from_user.id):
        return
    drop_id = int(callback.data.split("_")[1])
    await state.update_data(drop_id=drop_id)
    await state.set_state(PromoState.code)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ İptal", callback_data=f"buy_{drop_id}")]])
    await callback.message.edit_text("🎟️ Lütfen indirim kuponu kodunu yazın:", reply_markup=kb)

@dp.message(PromoState.code)
async def verify_promo_code(message: types.Message, state: FSMContext):
    if message.chat.type != "private" or is_user_banned(message.from_user.id):
        return
    data = await state.get_data()
    drop_id = data.get("drop_id")
    entered_code = message.text.strip()
    await state.clear()

    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT title, price, stock FROM drops WHERE id = ? AND is_sold = 0 AND stock > 0", (drop_id,))
    drop = cursor.fetchone()
    conn.close()

    if not drop:
        await message.answer("⚠️ Ürün artık mevcut değil.")
        return

    title, price, stock = drop
    if entered_code == PROMO_CODE:
        final_price = max(0.0, price - PROMO_DISCOUNT)
        promo_applied = True
    else:
        final_price = price
        promo_applied = False

    user_id = message.from_user.id
    username = message.from_user.username

    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    cursor.execute("INSERT INTO orders (user_id, drop_id, status, final_price) VALUES (?, ?, 'pending', ?)", (user_id, drop_id, final_price))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    msg = f"✅ Sipariş Oluşturuldu! (Sipariş No: #{order_id})\n\n📌 Ürün: {title}\n"
    if promo_applied:
        msg += f"💰 Normal Tutar: {price} USDT\n🎟️ Kupon İndirimi: -{PROMO_DISCOUNT} USDT\n💵 **Ödenecek Tutar: {final_price} USDT**\n\n"
    else:
        msg += f"❌ Geçersiz kupon! Tam Tutar: {final_price} USDT\n\n"

    msg += f"🔒 Cüzdan Adresi:\n`{CRYPTO_WALLET}`\n\n⏱️ 15 dakikanız vardır. Ödemeyi yapınca aşağıdaki butona basın."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Ödemeyi Otomatik Kontrol Et", callback_data=f"autocheck_{order_id}")]])
    await message.answer(msg, reply_markup=kb)

@dp.callback_query(F.data.startswith("nopromo_"))
async def process_buy_no_promo(callback: types.CallbackQuery):
    if is_user_banned(callback.from_user.id):
        return
    drop_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    username = callback.from_user.username

    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    
    cursor.execute("SELECT title, price, stock FROM drops WHERE id = ? AND is_sold = 0 AND stock > 0", (drop_id,))
    drop = cursor.fetchone()
    if not drop:
        await callback.answer("⚠️ Bu ürün tükenmiş.", show_alert=True)
        conn.close()
        return
    title, price, stock = drop
    final_price = price
    cursor.execute("INSERT INTO orders (user_id, drop_id, status, final_price) VALUES (?, ?, 'pending', ?)", (user_id, drop_id, final_price))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    payment_text = (
        f"✅ Sipariş Oluşturuldu! (Sipariş No: #{order_id})\n\n"
        f"📌 Ürün: {title}\n💰 Tutar: {final_price} USDT\n\n"
        f"🔒 Cüzdan Adresi:\n`{CRYPTO_WALLET}`\n\n"
        "⏱️ 15 dakikanız vardır. Ödemeyi yapınca aşağıdaki butona basın.NOT:Ödeme yapıldıktan 2-3 dk sonra 'ONAY İSTE' butonuna tıklamanız önerilir!!!"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Ödemeyi Otomatik Kontrol Et", callback_data=f"autocheck_{order_id}")]])
    await callback.message.edit_text(payment_text, reply_markup=kb)

@dp.callback_query(F.data.startswith("autocheck_"))
async def check_blockchain_payment(callback: types.CallbackQuery):
    if is_user_banned(callback.from_user.id):
        return
    order_id = int(callback.data.split("_")[1])
    await callback.answer("Blokzincir taranıyor...", show_alert=True)
    conn = sqlite3.connect("drop_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT orders.user_id, drops.id, drops.stock, orders.status, orders.created_at, drops.title, orders.final_price, drops.category 
        FROM orders 
        JOIN drops ON orders.drop_id = drops.id 
        WHERE orders.id = ?
    """, (order_id,))
    data = cursor.fetchone()
    if not data:
        await callback.answer("Sipariş bulunamadı.", show_alert=True)
        conn.close()
        return
    user_id, drop_id, stock, status, created_at_str, title, final_price, category = data
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
                        if tx.get("to") == CRYPTO_WALLET and int(tx.get("value", 0)) >= int(float(final_price) * 1000000):
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
        
        cursor.execute("SELECT SUM(stock) FROM drops WHERE category = ? AND is_sold = 0", (category,))
        rem_stock = cursor.fetchone()[0] or 0

        conn.commit()
        conn.close()

        secure_link = f"{RENDER_EXTERNAL_URL}/drop/{order_id}"
        await callback.message.edit_text(f"✅ Sipariş #{order_id} onaylandı.")
        await bot.send_message(user_id, f"🎉 Ödemeniz onaylandı!\n\n👉 [Güvenli Konum Sayfasını Aç]({secure_link})", parse_mode="Markdown")
        
        log_msg = f"🎉 Otomatik Satış: #{order_id} - {title} ({final_price} USDT)"
        log_panel_event(log_msg, "success")

        try:
            await bot.send_message(ADMIN_GROUP_ID, f"🎉 **YENİ BLOKZİNCİR SATIŞI ONAYLANDI!**\n\n📌 Ürün: {title}\n💰 Tutar: {final_price} USDT\n👤 Alıcı ID: `{user_id}`\n🆔 Sipariş ID: `#{order_id}`")
            if rem_stock <= 2:
                warn_msg = f"⚠️ KRİTİK STOK UYARISI: {category} bölgesinde kalan aktif stok: {rem_stock} adet!"
                log_panel_event(warn_msg, "warning")
                await bot.send_message(ADMIN_GROUP_ID, f"⚠️ **KRİTİK STOK UYARISI!**\n\n🏙️ `{category}` bölgesinde toplam kalan aktif stok: **{rem_stock} adet**! Takviye yapman önerilir.")
        except Exception as e:
            logging.error(e)
    else:
        conn.close()
        await callback.answer("⚠️ Henüz transfer yansımadı, bekleyin.", show_alert=True)

# --- ANONİM YANITLAMA KÖPRÜSÜ ---
@dp.message()
async def handle_admin_group_reply(message: types.Message):
    if message.chat.id == ADMIN_GROUP_ID and message.reply_to_message:
        original_text = message.reply_to_message.text or ""
        match = re.search(r"Kullanıcı ID:\s*`(\d+)`", original_text)
        if match:
            target_user_id = int(match.group(1))
            admin_reply_text = message.text
            try:
                await bot.send_message(
                    target_user_id,
                    f"💬 **Destek Ekibi Yanıtı:**\n\n{admin_reply_text}"
                )
                await message.reply("✅ Yanıt müşteriye başarıyla iletildi.")
            except Exception as e:
                await message.reply(f"⚠️ Müşteriye mesaj iletilemedi: {e}")

async def main():
    global main_loop
    main_loop = asyncio.get_running_loop()
    asyncio.create_task(auto_backup_task()) # Arka planda 24 saatlik veritabanı yedeği al
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
