# ======================================================================
#  แฟร้งคลิกคลิก - ร้านคลิกเกอร์คีย์บอร์ดและพวงกุญแจกดมันส์ลายตุ๊กตาน่ารัก (เวอร์ชัน v26-qty-input)
# ======================================================================
import datetime, sqlite3, hashlib, secrets, time, json, os, sys, re, csv, io, base64, socketserver, webbrowser, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlparse, quote
from html import escape

# ตั้งค่าหน้าจอ Terminal ให้ใช้ UTF-8 เพื่อพิมพ์ภาษาไทยได้บน Windows
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ======================================================================
# ส่วนที่ 1: ค่าตั้งต้น
# ======================================================================
BASE = os.path.dirname(os.path.abspath(__file__))  # โฟลเดอร์ที่เก็บไฟล์โค้ดนี้
DB_NAME = os.path.join(BASE, "clicker_shop.db")      # ไฟล์ฐานข้อมูล
AVATAR_DIR = os.path.join(BASE, "avatars")         # รูปโปรไฟล์ของสมาชิก (ตั้งชื่อตามเลขผู้ใช้ เช่น 3.jpg)
# โหมดสาธิต: True = เก็บรหัสผ่านตัวจริงไว้ในคอลัมน์ users.password_plain ให้เปิดดูในฐานข้อมูลได้ (ใช้ทดสอบ/พรีเซนต์ในเครื่องตัวเองเท่านั้น)
# ตอนใช้งานจริงต้องเปลี่ยนเป็น False (การล็อกอินยังตรวจจากรหัสที่เข้ารหัส password เสมอ ไม่ได้ใช้คอลัมน์นี้)
STORE_PLAIN_PASSWORD = True
QR_UPLOAD = "qr_upload.jpg"                         # รูป QR ที่แอดมินอัปโหลดเอง (วางข้างไฟล์โค้ด)
SLIP_DIR = os.path.join(BASE, "slips")             # สลิปโอนเงินที่ลูกค้าแนบ (ตั้งชื่อตามเลขคำสั่งซื้อ)
PORT = 8080                                        # พอร์ตของเว็บ
SHOP_NAME = "แฟร้งคลิกคลิก"
VAT_RATE = 0.07               # ภาษีมูลค่าเพิ่ม 7% (บวกเพิ่มจากราคาสินค้า)
DEFAULT_ADMIN = ("admin", "admin1234", "admin@frankclickclick.local")  # บัญชีแอดมินตั้งต้น (สร้างครั้งแรกครั้งเดียว)
SLIP_MAX_BYTES = 2_000_000    # ขนาดสลิปสูงสุด (หลังย่อภาพแล้ว)
AVATAR_MAX_BYTES = 500_000    # ขนาดรูปโปรไฟล์สูงสุด (หน้าเว็บย่อเป็น 256x256 ก่อนส่ง จึงเล็กมาก)

# สถานะคำสั่งซื้อ: รหัส -> (ข้อความ, ชื่อ class สี)
STATUS = {
    "awaiting": ("รอชำระเงิน", "st-wait"), "paid": ("รอแอดมินตรวจสลิป", "st-paid"),
    "verified": ("ชำระเงินแล้ว", "st-ok"), "cancelled": ("ยกเลิกแล้ว", "st-no"),
}

# หมวดหมู่สินค้า: รหัสหมวด -> (อีโมจิ, ชื่อ, คำอธิบายใต้หัวข้อ) ใช้สร้างแท็บ หัวข้อแต่ละส่วน และตรวจว่าหมวดที่ส่งมาถูกต้อง
CAT_INFO = {
    "multi": ("⌨️", "แพ็กหลายปุ่ม", "คลิกเกอร์ 4-16 ปุ่ม กดรัวๆ ได้ทั้งถาด แต่ละปุ่มเสียงไม่ซ้ำกัน"),
    "single": ("🔘", "ปุ่มเดี่ยวน่ารัก", "ตุ๊กตาตัวเดียว กดแล้วป๊อป! เหมาะห้อยกระเป๋า"),
    "name": ("🔤", "พวงกุญแจชื่อ", "ทำเป็นชื่อของคุณเอง เลือกตัวอักษรบนปุ่มได้เอง"),
    "accessory": ("🎀", "อุปกรณ์เสริม", "โซ่ กล่องของขวัญ และของจุกจิกน่ารักๆ"),
}

# ชุดสีพาสเทล 6 สี (ใช้ซ้ำกับหลายสินค้า)
P6 = "#fbcfe8,#bfdbfe,#fde68a,#bbf7d0,#fecdd3,#ddd6fe"
# ข้อมูลสินค้าตั้งต้น: (ชื่อ, หมวด, ราคา, สต็อก, คำอธิบาย, look)
# look = สูตรวาดภาพสินค้า รูปแบบ "คอลัมน์|แถว|ถาด|เสียง|ลายบนปุ่ม(คั่นด้วย ,)|สีปุ่ม(คั่นด้วย ,)"
#   ลาย t:A = ตัวอักษร A | ถาด cup:#สี = แก้วสีที่กำหนด | ชื่อเสียงดูในตาราง SND ของ JavaScript
# จะถูกใส่ลงฐานข้อมูลครั้งแรกที่ตารางสินค้ายังว่าง
SEED = [
    ("Teddy Party Clicker 6 ปุ่ม", "multi", 169, 30, "หมีน้อย 6 ปุ่มในถาดครีม กดแล้วเสียงทุ้มนุ่ม พร้อมพวงกุญแจ", "3|2|white|thock|bear|#fde2c8,#f9d5b8,#fbe7d3"),
    ("Bunny Garden Clicker 9 ปุ่ม", "multi", 189, 26, "กระต่ายกับดอกไม้ 9 ปุ่ม เสียงฟองป๊อปใสๆ", "3|3|pink|bubble|bunny,flower|#fbcfe8,#ffe4ec,#ddd6fe"),
    ("Panda Bamboo Clicker 9 ปุ่ม", "multi", 179, 26, "แพนด้าหน้ากลม 9 ปุ่ม กดแล้วเสียงไม้ก๊อกๆ", "3|3|clear|wood|panda|#ffffff,#e5e7eb,#d1fae5"),
    ("Fox Autumn Clicker 6 ปุ่ม", "multi", 159, 28, "จิ้งจอกกับคุกกี้ 6 ปุ่ม เสียงคลิกแหลมใส", "3|2|wood|clack|fox,cookie|#fed7aa,#fde68a,#fdba74"),
    ("Penguin Snow Clicker 6 ปุ่ม", "multi", 149, 30, "เพนกวินกับก้อนเมฆ 6 ปุ่ม เสียงหยดน้ำใส", "3|2|clear|drop|penguin,cloud|#bfdbfe,#e0f2fe,#dbeafe"),
    ("Strawberry Cake Clicker 12 ปุ่ม", "multi", 219, 24, "เค้กสตรอว์เบอร์รี 12 ปุ่ม เสียงแคลกใส", "4|3|white|clack|strawberry,cake|#fecdd3,#fde68a,#fbcfe8"),
    ("Sweet Donut Clicker 6 ปุ่ม", "multi", 139, 32, "โดนัทหวานๆ 6 ปุ่ม สีพาสเทล เสียงฟองป๊อป", "3|2|pink|bubble|donut|#fbcfe8,#fde68a,#ddd6fe"),
    ("Rainbow Cloud Clicker 12 ปุ่ม", "multi", 229, 20, "ก้อนเมฆ สายรุ้ง ดวงดาว 12 ปุ่ม เสียงกระดิ่งก้อง", "4|3|clear|chime|cloud,rainbow,star|#bfdbfe,#fde68a,#fbcfe8"),
    ("Sushi Bento Clicker 4 ปุ่ม", "multi", 119, 35, "กล่องเบนโตะ ซูชิ ข้าวปั้น ไข่ดาว กดสนุกทุกเมนู", "2|2|bento|thock|sushi,onigiri,egg,carrot|#fecaca,#e5e7eb,#fef08a,#fed7aa"),
    ("Pastel Cube Clicker 9 ปุ่ม", "multi", 189, 25, "คิวบ์สีพาสเทลมาการอง 9 ปุ่ม เสียงคลิกใสๆ", "3|3|clear|artisan|-|#fbcfe8,#bfdbfe,#bbf7d0,#fde68a,#ddd6fe,#fecdd3,#a7f3d0,#fed7aa,#c7d2fe"),
    ("Chick & Pig Farm Clicker 8 ปุ่ม", "multi", 159, 28, "ลูกเจี๊ยบกับหมูน้อยในฟาร์ม 8 ปุ่ม เสียงพิมพ์ดีด", "4|2|wood|typewriter|chick,pig|#fef08a,#fbcfe8"),
    ("Unicorn Dream Clicker 9 ปุ่ม", "multi", 239, 18, "ยูนิคอร์นกับดวงดาว 9 ปุ่ม เสียงพิณก้องใส", "3|3|pink|harp|unicorn,star|#f3e1ff,#fbcfe8,#c4b5fd"),
    ("Dino Land Clicker 6 ปุ่ม", "multi", 169, 22, "ไดโนเสาร์น้อยสีมินต์ 6 ปุ่ม เสียงสปริงบึ้ง", "3|2|clear|boing|dino|#bbf7d0,#a7f3d0,#d9f99d"),
    ("Kitty Cup Pop-Up Clicker", "single", 79, 50, "แมวน้อยในแก้วสีชมพู ปุ่มเดี่ยว กดแล้วป๊อป!", "1|1|cup:#fbcfe8|pop|cat|#ffe4e6"),
    ("Bear Boba Clicker", "single", 89, 36, "หมีน้อยในแก้วชานมไข่มุก เสียงยุบนุ่ม", "1|1|cup:#d6b48a|squish|bear|#fde68a"),
    ("Bunny Cloud Clicker", "single", 79, 44, "กระต่ายขาวบนก้อนเมฆสีฟ้า เสียงฟองป๊อป", "1|1|cup:#bfdbfe|bubble|bunny|#e0f2fe"),
    ("Fox Pot Pop-Up Clicker", "single", 89, 42, "จิ้งจอกส้มในกระถางครีม เสียงกระดิ่งใส", "1|1|cup:#fde7c7|chime|fox|#fed7aa"),
    ("Panda Pop-Up Clicker", "single", 79, 40, "แพนด้าอ้วนกลมในแก้วสีเทา กดแล้วป๊อป", "1|1|cup:#e5e7eb|pop|panda|#ffffff"),
    ("Penguin Pop-Up Clicker", "single", 79, 40, "เพนกวินน้อยในแก้วสีฟ้า เสียงหยดน้ำ", "1|1|cup:#bfdbfe|drop|penguin|#e0f2fe"),
    ("Frog Pop-Up Clicker", "single", 79, 38, "กบเขียวในแก้วสีเขียวอ่อน เสียงสปริง", "1|1|cup:#bbf7d0|boing|frog|#d9f99d"),
    ("Piggy Pop-Up Clicker", "single", 79, 38, "หมูน้อยสีชมพู เสียงลูกแก้วทุ้มๆ", "1|1|cup:#fbcfe8|marble|pig|#fce7f3"),
    ("Unicorn Pop-Up Clicker", "single", 89, 30, "ยูนิคอร์นในแก้วสีม่วงอ่อน เสียงพิณใส", "1|1|cup:#e9d5ff|harp|unicorn|#f3e1ff"),
    ("Cupcake Pop-Up Clicker", "single", 89, 34, "คัพเค้กช็อกโกแลตในถ้วยสีชมพู กดแล้วป๊อป", "1|1|cup:#f9a8d4|pop|cupcake|#7c4a2d"),
    ("Rainbow Name Keychain 5 ตัวอักษร", "name", 199, 20, "พวงกุญแจชื่อ 5 ตัวสีรุ้ง เลือกตัวอักษรบนปุ่มได้เอง", "5|1|white|clack|t:J,t:E,t:N,t:G,t:Y|#f9a8d4,#fdba74,#fde047,#86efac,#93c5fd"),
    ("Laser Name Keychain 4 ตัวอักษร", "name", 169, 18, "พวงกุญแจชื่อ 4 ตัว เสียงเลเซอร์ เลือกตัวอักษรบนปุ่มได้เอง", "4|1|clear|laser|t:K,t:E,t:Y,t:S|#a5b4fc,#f0abfc,#67e8f9,#fde047"),
    ("Letter Clicker ตัวอักษรเดี่ยว", "name", 59, 60, "คลิกเกอร์ตัวอักษร A-Z เลือกตัวอักษรบนปุ่มได้เอง", "1|1|white|red|t:A|#c4b5fd"),
    ("Ball Chain Keychain Set", "accessory", 39, 100, "โซ่ลูกปัดโลหะ 5 เส้น สำหรับห้อยคลิกเกอร์", "1|1|white|chime|chain|#e5e7eb"),
    ("Gift Box ห่อของขวัญ", "accessory", 29, 80, "กล่องของขวัญลายน่ารักพร้อมริบบิ้น", "1|1|white|bubble|gift|#fecdd3"),
    ("Ribbon Charm โบว์น่ารัก", "accessory", 35, 90, "โบว์สีชมพูห้อยพวงกุญแจ", "1|1|white|bubble|ribbon|#fbcfe8"),
    ("Crown Charm มงกุฎ", "accessory", 45, 60, "ชาร์มมงกุฎทองสำหรับห้อยคลิกเกอร์", "1|1|white|bell|crown|#fde68a"),
    # --- สินค้าใหม่หน้าตาเหมือนของจริง (ฝักถั่ว / ปุ่มพาสเทลฐานใส / ชีส / สวิตช์ใส) ---
    ("Edamame Pea Pod Clicker 3 ปุ่ม", "multi", 129, 40, "ฝักถั่วเขียว 3 เม็ด หน้ายิ้มน่ารัก กดแล้วเสียงป๊อป", "1|3|pod|pop|face1,face2,face3|#a3e635,#bef264,#a3e635"),
    ("Macaron Strip Clicker 8 ปุ่ม", "multi", 199, 30, "ปุ่มพาสเทลชมพู ฟ้า ครีม บนฐานอะคริลิกใส เสียงคลิกใสๆ", "4|2|strip|chime|blank|#f9c6d3,#bfe3f2,#fbeab0"),
    ("Crystal Switch Clicker 4 ปุ่ม", "multi", 189, 26, "สวิตช์ใสมองเห็นแกนสีพาสเทลข้างใน กดแล้วนุ่มมือ", "4|1|glass|marble|blank|#a7f3d0,#fbcfe8,#c4b5fd,#fde68a"),
    ("Cheesy Clicker ชีสก้อน", "single", 99, 36, "ชีสก้อนมีรูในกล่องสีเหลือง กดยุบได้ เสียงกรุบกริบ", "1|1|cheese:#f4b92c|squish|blank|#fbbf24"),
    ("Cheesy Trio Clicker 3 ก้อน", "multi", 259, 22, "ชีส 3 ก้อนในกล่องเดียว กดได้ทีละก้อน เสียงไม่ซ้ำกัน", "3|1|cheese:#f4b92c|drop|blank|#fbbf24"),
    ("Crystal Switch Single สวิตช์ใสเดี่ยว", "single", 99, 34, "สวิตช์ใสปุ่มเดียว แกนสีมินต์ เสียงลูกแก้ว", "1|1|glass|marble|blank|#a7f3d0"),
]

# ======================================================================
# ส่วนที่ 2: ฐานข้อมูล (SQLite เก็บเป็นไฟล์เดียว)
# ======================================================================
def db():
    """เปิดการเชื่อมต่อฐานข้อมูล 1 ครั้ง (เรียกใหม่ทุกคำขอ แล้วปิดเมื่อจบ)
    row_factory = Row ทำให้ดึงค่าด้วยชื่อคอลัมน์ได้ เช่น row["price"]"""
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def schema_ok(conn):
    """ตรวจว่าไฟล์ฐานข้อมูลเดิมมีคอลัมน์ที่โค้ดนี้ต้องใช้ครบไหม (products.look, users.avatar, cart.note)"""
    need = {"products": "look", "users": "avatar", "cart": "note"}
    for table, col in need.items():
        cols = [r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)]
        if cols and col not in cols:
            return False
    return True


def init_db():
    """เตรียมฐานข้อมูลตอนเริ่มโปรแกรม: สร้างตาราง ใส่สินค้าตั้งต้น สร้างแอดมิน
    ถ้าเจอไฟล์ฐานข้อมูลของเวอร์ชันอื่นที่โครงตารางไม่ตรง จะเปลี่ยนชื่อเก็บสำรองเป็น .old แล้วสร้างใหม่"""
    conn = db()
    if not schema_ok(conn):
        conn.close()
        os.replace(DB_NAME, DB_NAME + ".old")
        print("พบฐานข้อมูลเวอร์ชันเก่าที่ไม่ตรงกับโค้ดนี้ เก็บสำรองเป็น %s.old แล้วสร้างฐานข้อมูลใหม่" % os.path.basename(DB_NAME))
        conn = db()
    try:  # โหมด WAL เขียนเร็วขึ้นและอ่าน/เขียนพร้อมกันได้ดีขึ้น
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    except sqlite3.Error:
        pass
    # ตารางทั้งหมด (สร้างเมื่อยังไม่มี)
    #   users       = บัญชีผู้ใช้ (role = user ลูกค้า / admin แอดมิน, nickname ชื่อเล่น, avatar เวลาที่อัปโหลดรูปโปรไฟล์ล่าสุด 0 = ไม่มีรูป)
    #   sessions    = คนที่ล็อกอินอยู่ (โทเคนในคุกกี้ -> ผู้ใช้)
    #   cart        = ตะกร้าของแต่ละคน (note = ตัวอักษรที่ลูกค้าเลือกบนพวงกุญแจชื่อ สินค้าอื่นเว้นว่าง)
    #   orders      = คำสั่งซื้อ (เลขบิล ยอด ภาษี สถานะ สลิป)
    #   order_items = รายการสินค้าในแต่ละคำสั่งซื้อ (เก็บชื่อและราคา ณ วันที่ซื้อ)
    #   products    = สินค้าและสต็อก (look = สูตรวาดภาพสินค้า ดูคำอธิบาย SEED)
    #   resets      = รหัส 6 หลักสำหรับลืมรหัสผ่าน (มีเวลาหมดอายุ)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL, created REAL NOT NULL,
            email TEXT NOT NULL DEFAULT '', role TEXT NOT NULL DEFAULT 'user',
            nickname TEXT NOT NULL DEFAULT '', avatar INTEGER NOT NULL DEFAULT 0,
            password_plain TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS cart (
            user_id INTEGER NOT NULL, product_id INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '', qty INTEGER NOT NULL,
            PRIMARY KEY (user_id, product_id, note));
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT NOT NULL,
            phone TEXT NOT NULL, address TEXT NOT NULL, total REAL NOT NULL, created REAL NOT NULL,
            bill_no TEXT NOT NULL, subtotal REAL NOT NULL, vat REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'awaiting', slip TEXT NOT NULL DEFAULT '',
            verified_by TEXT NOT NULL DEFAULT '', verified_at REAL NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL,
            product_name TEXT NOT NULL, price INTEGER NOT NULL, qty INTEGER NOT NULL, product_id INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            category TEXT NOT NULL, price INTEGER NOT NULL, stock INTEGER NOT NULL,
            description TEXT NOT NULL, look TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS resets (email TEXT PRIMARY KEY, code TEXT NOT NULL, expires REAL NOT NULL);
        """
    )
    # ถ้าตารางสินค้าว่าง ให้ใส่สินค้าตั้งต้นจาก SEED ทั้งหมดในครั้งเดียว
    if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO products (name, category, price, stock, description, look) VALUES (?,?,?,?,?,?)", SEED
        )
    # ฐานข้อมูลเก่า (user_version < 2): เติมสินค้าใหม่จาก SEED ที่ยังไม่มีชื่อซ้ำ แล้วจดเลขเวอร์ชันไว้ (สินค้าที่แอดมินลบทีหลังจะไม่ถูกเติมกลับ)
    if conn.execute("PRAGMA user_version").fetchone()[0] < 2:
        for p in SEED:
            if not conn.execute("SELECT 1 FROM products WHERE name=?", (p[0],)).fetchone():
                conn.execute("INSERT INTO products (name, category, price, stock, description, look) VALUES (?,?,?,?,?,?)", p)
        conn.execute("PRAGMA user_version = 2")
    # ฐานข้อมูลเดิมที่ยังไม่มีคอลัมน์ password_plain: เพิ่มให้ (ผู้ใช้เดิมจะเป็นค่าว่างจนกว่าจะเปลี่ยนรหัส)
    if "password_plain" not in [r[1] for r in conn.execute("PRAGMA table_info(users)")]:
        conn.execute("ALTER TABLE users ADD COLUMN password_plain TEXT NOT NULL DEFAULT ''")
    # ถ้ายังไม่มีแอดมินเลย สร้างบัญชีแอดมินตั้งต้น
    if not conn.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
        uname, pw, mail = DEFAULT_ADMIN
        conn.execute("INSERT OR IGNORE INTO users (username,password,created,email,role,password_plain) VALUES (?,?,?,?,'admin',?)",
                     (uname, hash_pw(pw), time.time(), mail, plain_pw(pw)))
        print("สร้างบัญชีแอดมินตั้งต้นแล้ว  ชื่อผู้ใช้: %s  รหัสผ่าน: %s  (ควรเปลี่ยนรหัสผ่านทันที)" % (uname, pw))
    conn.commit()
    conn.close()


# ======================================================================
# ส่วนที่ 3: เครื่องมือเล็กๆ
# ======================================================================
def plain_pw(pw):
    """ค่าที่จะเก็บในคอลัมน์ password_plain: รหัสจริงถ้าเปิดโหมดสาธิต (STORE_PLAIN_PASSWORD) ไม่งั้นเก็บค่าว่าง"""
    return pw if STORE_PLAIN_PASSWORD else ""


def hash_pw(pw, salt=None):
    """เข้ารหัสรหัสผ่านแบบทางเดียว: ผสม salt (ค่าสุ่มกันรหัสซ้ำได้ผลเหมือนกัน) แล้ววน PBKDF2 100,000 รอบ
    ผลลัพธ์เก็บเป็น "salt$hash" ไม่มีใครย้อนกลับเป็นรหัสผ่านจริงได้"""
    salt = salt or secrets.token_hex(8)
    return salt + "$" + hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100000).hex()


def check_pw(pw, stored):
    """ตรวจรหัสผ่านตอนล็อกอิน: ดึง salt เดิมมาเข้ารหัสรหัสที่พิมพ์ แล้วเทียบกับที่เก็บไว้ (compare_digest กัน timing attack)"""
    return secrets.compare_digest(hash_pw(pw, stored.split("$")[0]), stored)


def money(n):
    """จัดรูปแบบราคา เช่น 1200 -> ฿1,200 และ 1187.7 -> ฿1,187.70"""
    n = round(float(n), 2)
    return "฿{:,.0f}".format(n) if n == int(n) else "฿{:,.2f}".format(n)


def money2(n):
    """ราคาแบบทศนิยม 2 ตำแหน่งเสมอ (ใช้ในใบเสร็จและหน้าชำระเงิน)"""
    return "{:,.2f}".format(float(n))


def calc_total(subtotal):
    """คิดภาษี 7% และยอดรวมสุทธิ (ปัดทศนิยม 2 ตำแหน่ง) คืนค่า (ภาษี, ยอดรวม)"""
    vat = round(subtotal * VAT_RATE + 1e-9, 2)
    return vat, round(subtotal + vat, 2)


def make_bill_no(conn):
    """สร้างเลขบิลรูปแบบ FC + ปี พ.ศ.2หลัก + เดือน + วัน + ชั่วโมง + นาที เช่น FC6910121930
    ถ้าซ้ำ (สั่งในนาทีเดียวกัน) ต่อท้าย -1, -2, ..."""
    t = time.localtime()
    base = "FC%02d%02d%02d%02d%02d" % ((t.tm_year + 543) % 100, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min)
    bill, k = base, 0
    while conn.execute("SELECT 1 FROM orders WHERE bill_no=?", (bill,)).fetchone():
        k += 1
        bill = "%s-%d" % (base, k)
    return bill


def be_date(ts, with_time=True):
    """แปลงเวลา (วินาที) เป็นข้อความ วว/ดด/ปี พ.ศ. [ชม:นาที]"""
    t = time.localtime(ts)
    s = "%02d/%02d/%d" % (t.tm_mday, t.tm_mon, t.tm_year + 543)
    return s + (" %02d:%02d" % (t.tm_hour, t.tm_min) if with_time else "")


def period_label(k, view):
    """แปลงคีย์ช่วงเวลา (2026-10-26 / 2026-10 / 2026) เป็นข้อความ พ.ศ. เช่น 26/10/2569, 10/2569, 2569"""
    p = k.split("-")
    if view == "day":
        return "%s/%s/%d" % (p[2], p[1], int(p[0]) + 543)
    if view == "month":
        return "%s/%d" % (p[1], int(p[0]) + 543)
    return str(int(p[0]) + 543)


def qr_file():
    """คืนชื่อไฟล์รูป QR ที่แอดมินอัปโหลดไว้ (qr_upload.jpg) หรือ None ถ้ายังไม่เคยอัปโหลด
    (ถ้าเป็น None ระบบใช้รูปที่ฝังท้ายไฟล์ QR_B64 แทน)"""
    return QR_UPLOAD if os.path.isfile(os.path.join(BASE, QR_UPLOAD)) else None

# ======================================================================
# ส่วนที่ 4: หน้าตาเว็บ (CSS / JavaScript)
# ======================================================================
# CSS = ชุดคำสั่งตกแต่งหน้าเว็บทั้งหมด เก็บเป็นข้อความก้อนเดียวแล้วฝังในทุกหน้า
# ธีม: ร้านตุ๊กตาสไตล์พาสเทล พื้นครีมลายจุด การ์ดมนใหญ่ ปุ่มกลมนูนเหมือนสติกเกอร์
CSS = """
:root{/* ---------- จานสี (แก้สีทั้งเว็บที่นี่ที่เดียว) ---------- */
  --bg:#fff7f3;          /* พื้นหลังหน้าเว็บ (ครีม) */
  --paper:#fff;          /* พื้นการ์ด/กล่อง */
  --text:#5b3a36;        /* ตัวอักษรหลัก (น้ำตาลโกโก้) */
  --muted:#a08580;       /* ตัวอักษรรอง */
  --pink:#ff8fab;        /* ชมพูหลัก (ปุ่ม ลิงก์) */
  --pink-deep:#e8668b;   /* ชมพูเข้ม (เงาปุ่ม ราคา) */
  --pink-soft:#ffe3ec;   /* ชมพูอ่อน (พื้นป้าย) */
  --peach:#ffe5d0;       /* พีช */
  --mint:#d7f5e6;        /* มิ้นต์ */
  --lilac:#ebe1ff;       /* ม่วงลาเวนเดอร์ */
  --border:#ffd6e0;      /* เส้นขอบ */
  --cocoa:#5b3a36;       /* น้ำตาลเข้ม (แถบเมนูแอดมิน) */}
*{box-sizing:border-box;margin:0;padding:0}
a{color:inherit;text-decoration:none}
main{max-width:1160px;margin:0 auto;padding:28px 24px 40px}
h2.t{font-size:26px;margin-bottom:18px}
.empty{text-align:center;color:var(--muted);padding:40px}
.stock{font-size:13px;color:var(--muted)}
/* ---------- แถบเมนูบน ---------- */
nav .sp{flex:1}
nav a.l{font-size:14px;font-weight:600;white-space:nowrap}
nav a.l:hover{color:var(--pink-deep)}
.srch{flex:1;max-width:380px}
.srch input{margin:0;padding:9px 18px;border-radius:99px;font-size:14px;background:var(--bg)}
.badge{background:var(--pink);color:#fff;border-radius:99px;padding:1px 8px;font-size:12px;margin-left:4px}
/* ---------- ปุ่ม (กลมนูนเหมือนสติกเกอร์) ---------- */
.btn:hover{filter:brightness(1.05)}
.btn:disabled{opacity:.45;cursor:not-allowed}
.btn.sm{padding:6px 14px;font-size:13px;color:var(--text);background:#fff;border:2px solid var(--border);box-shadow:0 3px 0 var(--border)}
.btn.wide{width:100%;font-size:16px;padding:13px}
.tabs{display:flex;gap:10px;flex-wrap:wrap;justify-content:center;margin:20px 0}
.tab{padding:9px 20px;border-radius:99px;background:#fff;border:2px solid var(--border);font-weight:600;font-size:14px;box-shadow:0 3px 0 var(--border)}
.tab:hover{color:var(--pink-deep)}
/* ---------- ฟอร์ม / กล่อง / ข้อความแจ้ง ---------- */
input,textarea,select{width:100%;padding:12px 16px;margin-bottom:12px;border-radius:16px;border:2px solid var(--border);
background:#fff;color:var(--text);font:15px 'Mali','Segoe UI',Tahoma,sans-serif;outline:none}
select{width:auto;margin:0}
input:focus,textarea:focus,select:focus{border-color:var(--pink);box-shadow:0 0 0 4px rgba(255,143,171,.2)}
.panel{background:var(--paper);border:3px solid var(--border);border-radius:28px;padding:24px;margin-bottom:20px}
.msg.err{background:#fff1f3;border:2px solid #ffc9d3;color:#b02a45}
.msg.ok{background:#effbf4;border:2px solid #bfe9d0;color:#25683f}
.center{max-width:520px;margin:30px auto}
.two{display:grid;grid-template-columns:1.3fr 1fr;gap:20px}
.pc .row{flex-wrap:wrap}.pc .row .btn{white-space:nowrap;padding:10px 18px}.qty{width:58px;text-align:center;padding:8px 6px;margin:0;font-weight:700}.pc .row form{display:flex;gap:8px;align-items:center}
.qw{color:#c2185b;font-size:12px;font-weight:600}.pc .qw:empty{display:none}.pc .qw{margin-top:6px}.line .qw:empty{display:none}.line .q{align-items:center}.line .q form{margin:0}.line .q .qty{width:70px}
button:disabled{opacity:.45;cursor:not-allowed}
.line{display:flex;align-items:center;gap:14px;padding:14px 0;border-bottom:2px dashed var(--border)}
.line:last-of-type{border:none}
.line .nm{flex:1}
.line .nm small{display:block;color:var(--muted)}
.q{display:flex;align-items:center;gap:8px}
.q form{display:inline}
.sum{display:flex;justify-content:space-between;padding:6px 0;color:var(--muted)}
.sum.big,.total{display:flex;justify-content:space-between;font-size:22px;font-weight:800;color:var(--text);padding-top:14px}
/* ---------- แบนเนอร์หน้าแรก ---------- */
.hero h1 span{color:var(--pink-deep)}
.hero p{color:#7a5a55;margin-bottom:22px;font-size:16px}
@keyframes bob{0%,100%{transform:translateY(0) rotate(-4deg)}50%{transform:translateY(-12px) rotate(4deg)}}
.perks{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:10px}
.perk b{display:block;font-size:14px}
.perk small{color:var(--muted);font-size:12px}
/* ---------- สินค้า ---------- */
.toolbar{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:12px;font-size:14px;color:var(--muted)}
.sorts{display:flex;gap:8px;align-items:center}
.sorts .tab{padding:5px 14px;font-size:13px}
.sec{margin-bottom:34px}
.sh h2{font-size:24px}
.sh p{color:var(--muted);font-size:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(235px,1fr));gap:20px}
.pc h3{font-size:16px;margin-bottom:4px;line-height:1.3}
.pc p{font-size:13px;color:var(--muted);min-height:38px;margin-bottom:10px}
/* ---------- ปุ่มคีย์แคปการ์ตูน (.ck) และถาดคลิกเกอร์ (.tray) ---------- */
.ck{width:var(--ks,44px);height:var(--ks,44px);position:relative;border-radius:calc(var(--ks,44px)*.24);cursor:pointer;display:flex;align-items:center;justify-content:center;
user-select:none;-webkit-tap-highlight-color:transparent;
background:linear-gradient(160deg,color-mix(in srgb,var(--c) 78%,#fff),color-mix(in srgb,var(--c) 78%,#000));
box-shadow:0 6px 0 color-mix(in srgb,var(--c) 52%,#000),0 11px 14px rgba(40,10,30,.22),inset 0 0 0 1px rgba(255,255,255,.4);transition:transform .05s,box-shadow .05s}
.ck::before{content:"";position:absolute;inset:8% 8% 15% 8%;border-radius:calc(var(--ks,44px)*.19);
background:radial-gradient(ellipse at 32% 22%,rgba(255,255,255,.8),transparent 58%),linear-gradient(color-mix(in srgb,var(--c) 45%,#fff),var(--c));
box-shadow:inset 0 -3px 5px rgba(0,0,0,.13),inset 0 2px 0 rgba(255,255,255,.85),0 1px 2px rgba(0,0,0,.28)}
.ck:active,.ck.press{transform:translateY(5px);box-shadow:0 1px 0 color-mix(in srgb,var(--c) 52%,#000),0 3px 5px rgba(40,10,30,.2),inset 0 0 0 1px rgba(255,255,255,.4)}
.ck svg,.ck .em,.ck .tx{position:relative;z-index:1;margin-top:-7%;pointer-events:none}
.ck svg{width:64%;height:64%;filter:drop-shadow(0 1px 1px rgba(0,0,0,.25))}
.ck .em{font-size:calc(var(--ks,44px)*.55);line-height:1}
.ck .tx{font-weight:800;font-size:calc(var(--ks,44px)*.52);color:#fff;text-shadow:0 2px 0 rgba(0,0,0,.18)}
.ck.wave{transform:translateY(-4px);filter:brightness(1.12) saturate(1.4)}
.fx{position:fixed;pointer-events:none;color:var(--pink);font-weight:800;font-size:20px;z-index:99;animation:fly .9s ease-out forwards}
@keyframes fly{to{transform:translateY(-70px) scale(1.4);opacity:0}}
.tray{position:relative;display:grid;grid-template-columns:repeat(var(--cols),var(--ks));gap:8px;padding:10px 10px 14px;margin:46px auto 24px;
width:max-content;max-width:100%;border-radius:20px;border:3px solid var(--tbd);
background:linear-gradient(145deg,color-mix(in srgb,var(--tb) 62%,#fff),var(--tb) 45%,color-mix(in srgb,var(--tb) 86%,#000));
box-shadow:0 8px 0 var(--tsh),0 18px 24px rgba(40,10,30,.18),inset 0 3px 0 rgba(255,255,255,.75),inset 0 -5px 8px rgba(0,0,0,.1)}
.tray::before{content:"";position:absolute;left:-8px;top:-20px;width:24px;height:24px;border:3px solid #aab2bd;border-radius:50%;z-index:1;pointer-events:none;box-shadow:0 2px 3px rgba(0,0,0,.3),inset 0 1px 2px #fff}
.tray::after{content:"";position:absolute;left:-2px;top:-48px;width:14px;height:34px;border:3px solid #c3c9d2;border-radius:10px;box-shadow:0 1px 2px rgba(0,0,0,.25);pointer-events:none}
.hero .tray::before{width:34px;height:34px;left:-10px;top:-28px;border-width:4px}
.hero .tray::after{left:-4px;top:-70px;width:18px;height:44px;border-width:4px}
/* ---------- หน้าออกแบบคีย์บอร์ดเอง ---------- */
.ctl{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:center;margin:20px 0 8px;color:var(--muted);font-size:14px}
.ctl .tab{cursor:pointer;font-family:inherit}
.dot{width:26px;height:26px;border-radius:50%;border:2px solid var(--border);cursor:pointer;box-shadow:0 3px 0 var(--border)}
.dot.on{outline:2px solid var(--pink);outline-offset:2px}
.boardwrap{overflow-x:auto;padding:14px 8px 26px}
.board{--u:clamp(32px,4.9vw,58px);--sel:#f9a8d4;--kf:#fff;--kf2:#eceff3;--ks:#bcc3cc;--kt:#374151;
width:max-content;margin:0 auto;padding:18px 18px 14px;border-radius:24px;display:flex;flex-direction:column;gap:6px;
background:linear-gradient(145deg,#f3f4f6,#d5d9df);box-shadow:0 20px 44px rgba(17,24,39,.2),inset 0 3px 0 #fff,inset 0 -5px 0 #b8bec7}
.board[data-theme=retro]{--kf:#eadfc4;--kf2:#d9cba5;--ks:#a79b78;--kt:#5b5136}
.board[data-theme=sakura]{--kf:#ffe9ec;--kf2:#fed3da;--ks:#e39aa8;--kt:#9f3a4d}
.board[data-theme=dark]{--kf:#3a3f4a;--kf2:#272b33;--ks:#0c0e12;--kt:#e5e7eb}
.kr{display:flex;gap:6px}
.k{position:relative;height:var(--u);width:calc((var(--u) + 6px)*var(--w,1) - 6px);margin-bottom:5px;border-radius:9px;display:flex;flex-direction:column;gap:1px;line-height:1.05;
align-items:center;justify-content:center;font-weight:700;font-size:calc(var(--u)*.3);cursor:pointer;user-select:none;color:var(--kt);
background:linear-gradient(var(--kf),var(--kf2));box-shadow:0 5px 0 var(--ks),0 9px 10px rgba(17,24,39,.15),inset 0 1px 0 rgba(255,255,255,.7);transition:transform .05s,box-shadow .05s}
.k::before{content:"";position:absolute;inset:4px 4px 8px;border-radius:7px;background:linear-gradient(rgba(255,255,255,.6),rgba(0,0,0,.04));box-shadow:inset 0 -2px 3px rgba(0,0,0,.08),0 0 0 1px rgba(0,0,0,.06)}
.k>*{position:relative;z-index:1}
.k small{font-size:calc(var(--u)*.17);opacity:.55;font-weight:600}
.k .em{font-size:calc(var(--u)*.5);line-height:1}
.k:active{transform:translateY(4px);box-shadow:0 1px 0 var(--ks)}
.k.sel{color:#831843;background:linear-gradient(color-mix(in srgb,var(--sel) 55%,#fff),var(--sel));
box-shadow:0 5px 0 color-mix(in srgb,var(--sel) 60%,#000),0 0 0 3px #fff,0 0 0 5px var(--sel)}
.k.sel::after{content:"✓";position:absolute;top:-8px;right:-6px;width:17px;height:17px;border-radius:50%;background:var(--pink);color:#fff;font-size:11px;display:flex;align-items:center;justify-content:center;z-index:2}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}
.chips span{background:#fde6dc;color:var(--text);border-radius:8px;padding:2px 9px;font-size:13px;font-weight:700}
.sumrow{display:flex;justify-content:space-between;padding:6px 0;color:var(--muted)}
.stage .tray{margin:44px auto 18px}
.lis{align-self:flex-start;margin-bottom:12px}
.cnt{color:var(--muted);font-size:14px}
.cnt b{color:var(--pink-deep)}
/* ---------- ส่วนท้าย ---------- */
.ft{max-width:1160px;margin:0 auto;display:grid;grid-template-columns:2fr 1fr 1fr;gap:24px}
.ft h4{margin-bottom:8px}
.ft p,.ft a{display:block;font-size:14px;color:var(--muted);margin-bottom:5px}
.ft a:hover{color:var(--pink-deep)}
.copy{text-align:center;color:var(--muted);font-size:12px;margin-top:18px}
/* ---------- หน้าล็อกอิน / สมัคร / ลืมรหัสผ่าน ---------- */
.scene{position:relative;min-height:100vh;display:grid;place-items:center;padding:30px 16px;overflow:hidden;
background:linear-gradient(160deg,#ffe3ec,#ffe5d0 50%,#ebe1ff)}
.mas{position:absolute;line-height:1;font-size:100px;filter:drop-shadow(0 8px 6px rgba(120,60,50,.2));animation:bob 3.6s ease-in-out infinite}
.m0{left:6%;top:10%}
.m1{right:8%;top:8%;font-size:120px;animation-delay:.5s}
.m2{left:10%;bottom:8%;font-size:80px;animation-delay:1s}
.m3{right:12%;bottom:10%;animation-delay:1.5s}
.m4{left:42%;top:3%;font-size:64px;animation-delay:2s}
.m5{right:34%;bottom:3%;font-size:70px;animation-delay:.8s}
.acard{position:relative;z-index:2;width:100%;max-width:420px;background:#fff;border:4px solid #fff;border-radius:40px;padding:26px 34px 28px;text-align:center;
box-shadow:0 20px 50px rgba(232,102,139,.25)}
.authkey{display:inline-grid;place-items:center;width:84px;height:84px;margin:-62px 0 8px;border-radius:50%;background:var(--pink-soft);border:5px solid #fff;font-size:46px;box-shadow:0 8px 20px rgba(232,102,139,.25)}
.acard h1{font-size:30px;margin-bottom:4px}
.acard .sub{color:var(--muted);font-size:14px;margin-bottom:18px}
.pill{display:flex;align-items:center;gap:8px;background:var(--bg);border:2px solid var(--border);border-radius:99px;padding:0 8px 0 16px;margin-bottom:12px}
.pill input{border:none;background:none;margin:0;padding:12px 4px;box-shadow:none!important}
.pill .show{border:none;background:#fff;border-radius:99px;padding:5px 12px;font-size:12px;font-weight:700;color:var(--pink-deep);cursor:pointer}
.alinks{display:flex;justify-content:space-between;font-size:13px;margin-top:14px;color:var(--pink-deep)}
.swrole{margin-top:12px;font-size:12px;color:var(--muted)}
.swrole a{text-decoration:underline}
/* ---------- หน้าชำระเงิน / คำสั่งซื้อ ---------- */
.paywrap{display:grid;grid-template-columns:1fr 1fr;gap:20px;align-items:start}
.pitem{display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:2px dashed var(--border)}
.pitem small{display:block;color:var(--muted)}
.qrbox{text-align:center}
.qrbox h3{margin:10px 0 8px;font-size:20px}
.qrset{display:flex;gap:18px;align-items:center;flex-wrap:wrap}.qrset img{width:150px;border-radius:14px;border:3px solid var(--border)}.qrset>div{flex:1;min-width:220px}
.qr{width:300px;max-width:100%;border-radius:20px;border:3px solid var(--border)}
.pay-amount{margin:8px 0 14px;font-size:15px}
.pay-amount b{color:var(--pink-deep);font-size:24px}
.st{display:inline-block;border-radius:99px;padding:2px 12px;font-size:12px;font-weight:700}
.st-wait{background:#fff3cf;color:#8a6200}
.st-paid{background:#e3efff;color:#1f5aa8}
.st-ok{background:#dff6e8;color:#25683f}
.st-no{background:#ffe1e6;color:#b02a45}
.order{border:2px dashed var(--border);border-radius:22px;padding:16px 18px;margin-bottom:14px}
.order h4{display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px;margin-bottom:8px}
.order ul{margin-left:20px;font-size:14px}
/* ---------- ใบเสร็จ ---------- */
.rh{display:flex;gap:12px;align-items:center;margin-bottom:12px}
.rh b{display:block;font-size:18px}
.rh span,.rh small{color:var(--muted)}
.rmeta{display:flex;justify-content:space-between;font-size:14px;margin:4px 0}
.ver{color:#25683f;font-weight:700}
.rcpt h4{text-align:center;margin:14px 0 8px;color:var(--muted)}
.ri,.rt div{display:flex;justify-content:space-between;font-size:14px;padding:3px 0}
.rt{border-top:2px dashed #e8c9a0;margin-top:10px;padding-top:8px}
.rsign{margin-top:18px;text-align:center;font-size:13px;color:var(--muted)}
.sig{font:italic 22px Georgia,serif;color:var(--pink-deep);margin-top:4px}
.thx{text-align:center;margin-top:14px;font-weight:700}
/* ---------- หลังบ้านแอดมิน ---------- */
.adm{display:grid;grid-template-columns:230px 1fr;min-height:100vh}
.abrand{display:flex;align-items:center;gap:8px;font-size:16px;font-weight:800;margin-bottom:14px}
.abrand span{font-size:11px;background:var(--pink);border-radius:99px;padding:2px 10px}
.sbi b{display:block}
.sbi small{opacity:.7;font-size:12px}
.sbi:hover{background:rgba(255,255,255,.1)}
.sbi.out{margin-top:auto;text-align:center}
.aMain{padding:26px 30px;background:var(--bg)}
.atop{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}
.atop span{color:var(--muted);font-size:14px}
.rfilter{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:18px}
.rfilter input{width:auto;margin:0}
.tbl{width:100%;border-collapse:collapse;background:#fff;border-radius:20px;overflow:hidden;border:3px solid var(--border)}
.tbl th{background:var(--pink);color:#fff;padding:12px 14px;text-align:left;font-size:14px}
.tbl td{padding:10px 14px;border-bottom:2px dashed var(--border);font-size:14px}
.tbl .r{text-align:right}
.bigtotal{text-align:center;font-size:26px;font-weight:800;margin:30px 0 8px;color:var(--pink-deep)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:20px}
.stat{background:#fff;border:3px solid var(--border);border-radius:24px;padding:18px}
.stat small{color:var(--muted);font-size:13px}
.stat b{display:block;font-size:28px;color:var(--pink-deep);margin-top:4px}
.dfilter{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.dfilter input[type=date]{width:auto}.vts{display:flex;gap:6px;background:var(--pink-soft);padding:5px;border-radius:99px}
.vt{cursor:pointer;text-decoration:none;padding:7px 18px;border-radius:99px;font-weight:700;color:var(--muted)}.vt input{display:none}.vt.on{background:linear-gradient(var(--pink),var(--pink-deep));color:#fff;box-shadow:0 3px 0 rgba(0,0,0,.12)}
.bars{overflow-x:auto}.bar1{min-width:46px}
.bars{display:flex;gap:14px;align-items:flex-end;height:190px;padding-top:10px}
.bar1{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;font-size:12px;color:var(--muted);gap:4px}
.bar1 i{display:block;width:100%;max-width:56px;border-radius:12px 12px 0 0;background:linear-gradient(var(--pink),var(--pink-deep));min-height:3px}
.prow{display:grid;grid-template-columns:2fr 90px 90px 2fr auto auto;gap:8px;align-items:center;padding:10px 0;border-bottom:2px dashed var(--border)}
.prow input{margin:0;padding:8px 12px}
.prow.low .stk{border-color:#e11d48;background:#fff1f2}
.pform{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;align-items:end;margin-bottom:10px}
.pform label{font-size:12px;color:var(--muted)}
.pform select{width:100%}
.slip img{max-width:140px;max-height:140px;border-radius:14px;border:2px solid var(--border)}
/* ======================================================================
   ตกแต่งเพิ่มความน่ารักและมิติ (ทับกฎด้านบน): เงาหลายชั้น ไฮไลต์เงา 3 มิติ ก้อนเมฆ ประกายระยิบ และการ์ดที่ลอยตอนชี้เมาส์
   ====================================================================== */
:root{--lift:0 2px 0 rgba(255,255,255,.9) inset,0 10px 24px rgba(232,102,139,.14),0 2px 4px rgba(91,58,54,.06)}
body{min-height:100vh;font-family:'Mali','Sarabun','Segoe UI',Tahoma,sans-serif;color:var(--text);background:
 radial-gradient(circle at 12px 12px,rgba(255,143,171,.22) 2px,transparent 3px) 0 0/36px 36px,
 radial-gradient(ellipse 60% 40% at 8% 0%,#ffe0ec 0,transparent 70%),radial-gradient(ellipse 50% 40% at 100% 20%,#e8dcff 0,transparent 70%),
 radial-gradient(ellipse 60% 40% at 0% 100%,#ffe9d6 0,transparent 70%),var(--bg);background-attachment:fixed}
@keyframes twinkle{0%,100%{opacity:.25;transform:scale(.7) rotate(0)}50%{opacity:1;transform:scale(1.15) rotate(20deg)}}
@keyframes rise{from{opacity:0;transform:translateY(18px) scale(.97)}to{opacity:1;transform:none}}
.sparkle{position:absolute;pointer-events:none;color:#fff;text-shadow:0 0 8px #ffb3c8,0 0 2px #ff8fab;animation:twinkle 2.6s ease-in-out infinite}
/* แถบเมนูกระจกฝ้า + แถบประกาศลายริบบิ้น */
nav{position:sticky;top:0;z-index:10;display:flex;align-items:center;gap:16px;padding:12px 28px;background:rgba(255,255,255,.92);backdrop-filter:blur(8px);border-bottom:3px solid #fff;box-shadow:0 6px 20px rgba(232,102,139,.14)}
.bar{background:linear-gradient(90deg,var(--pink-soft),var(--peach),var(--lilac));text-align:center;font-size:13px;padding:7px;color:var(--text);border-bottom:3px dotted #fff;font-weight:600;letter-spacing:.2px}
/* ปุ่มเงาแก้วนูน: ไฮไลต์ด้านบน + เงาแข็งด้านล่าง กดแล้วยุบลง */
.btn{border:none;cursor:pointer;display:inline-block;text-align:center;font:700 14px 'Mali','Segoe UI',Tahoma,sans-serif;padding:11px 20px;border-radius:99px;color:#fff;background:linear-gradient(#ffb0c6,var(--pink) 55%,#ff7fa0);box-shadow:0 5px 0 var(--pink-deep),0 10px 14px rgba(232,102,139,.3),inset 0 2px 0 rgba(255,255,255,.55);transition:transform .08s,box-shadow .08s}
.btn:active{transform:translateY(3px);box-shadow:0 1px 0 var(--pink-deep),0 3px 6px rgba(232,102,139,.3),inset 0 2px 0 rgba(255,255,255,.4)}
.btn.dark{background:linear-gradient(#8a5d56,var(--cocoa));box-shadow:0 5px 0 #2e1b18,0 10px 14px rgba(46,27,24,.3),inset 0 2px 0 rgba(255,255,255,.25)}
.btn.green{background:linear-gradient(#7fe0b0,#4cc38a);box-shadow:0 5px 0 #2f9a67,0 10px 14px rgba(47,154,103,.3),inset 0 2px 0 rgba(255,255,255,.5)}
.btn.cream{color:var(--text);background:linear-gradient(#fffaf4,#ffe7d6);box-shadow:0 5px 0 #e2bfa5,0 10px 14px rgba(226,191,165,.4),inset 0 2px 0 #fff}
.btn.sm,.tab{box-shadow:0 4px 0 var(--border),0 8px 12px rgba(232,102,139,.1),inset 0 2px 0 #fff}
.btn.red{color:#c0364f;background:#fff1f3;border-color:#ffc9d3;box-shadow:0 4px 0 #ffc9d3,inset 0 2px 0 #fff}
.tab.on{color:#fff;background:linear-gradient(#ffb0c6,var(--pink));border-color:var(--pink);box-shadow:0 4px 0 var(--pink-deep),0 8px 12px rgba(232,102,139,.25),inset 0 2px 0 rgba(255,255,255,.5)}
/* แบนเนอร์: ก้อนเมฆ + ประกาย + เงาพื้นใต้ถาดคลิกเกอร์ ให้ดูลอยเป็น 3 มิติ */
.hero{position:relative;overflow:hidden;display:grid;grid-template-columns:1.1fr 1fr;align-items:center;gap:20px;border-radius:40px;padding:44px 48px;margin-bottom:26px;background:radial-gradient(circle at 12% 18%,rgba(255,255,255,.75) 0 38px,transparent 39px),radial-gradient(circle at 20% 14%,rgba(255,255,255,.7) 0 30px,transparent 31px),
radial-gradient(circle at 92% 82%,rgba(255,255,255,.65) 0 46px,transparent 47px),radial-gradient(circle at 84% 88%,rgba(255,255,255,.6) 0 34px,transparent 35px),
linear-gradient(135deg,#ffd6e5,#ffe3cf 52%,#e4d8ff);box-shadow:0 22px 40px -12px rgba(232,102,139,.35),inset 0 3px 0 rgba(255,255,255,.8),inset 0 -8px 0 rgba(255,255,255,.35);border:4px solid #fff}
.hero::before,.hero::after{content:"✦";position:absolute;color:#fff;font-size:34px;text-shadow:0 0 10px #ff9ebb;animation:twinkle 2.4s ease-in-out infinite;pointer-events:none}
.hero::before{top:26px;right:44%}
.hero::after{bottom:30px;left:46%;font-size:24px;animation-delay:1.2s}
.hero .chip{display:inline-block;background:#fff;border-radius:99px;padding:5px 16px;font-size:13px;font-weight:700;color:var(--pink-deep);margin-bottom:14px;box-shadow:0 3px 0 var(--border),0 8px 14px rgba(232,102,139,.15)}
.hero h1{font-size:44px;line-height:1.2;margin-bottom:14px;text-shadow:0 3px 0 #fff,0 8px 16px rgba(232,102,139,.18)}
.hero-art{display:flex;flex-direction:column;align-items:center;position:relative}
.hero-art::after{content:"";position:absolute;left:50%;bottom:24px;width:260px;height:30px;transform:translateX(-50%);
background:radial-gradient(ellipse,rgba(91,58,54,.28),transparent 70%);z-index:0}
.hero .tray{--ks:78px;gap:12px;padding:18px 18px 22px;margin:70px auto 34px;border-radius:30px;position:relative;z-index:1;transform:perspective(900px) rotateX(10deg) rotateZ(-3deg);transition:transform .3s}
.hero .tray:hover{transform:perspective(900px) rotateX(2deg) rotateZ(0) translateY(-6px)}
/* จุดเด่นของร้าน: ไอคอนในวงกลมสีพาสเทลคนละสี */
.perk{display:flex;align-items:center;gap:12px;background:#fff;border:3px solid var(--border);border-radius:24px;padding:14px 16px;box-shadow:var(--lift);transition:transform .2s}
.perk:hover{transform:translateY(-4px) rotate(-1deg)}
.perk .pi{font-size:28px;display:grid;place-items:center;width:52px;height:52px;border-radius:18px;box-shadow:inset 0 3px 0 rgba(255,255,255,.8),0 4px 0 rgba(0,0,0,.06)}
.perks>:nth-child(1) .pi{background:#ffe3ec}
.perks>:nth-child(2) .pi{background:#e4f6ff}
.perks>:nth-child(3) .pi{background:#ece1ff}
.perks>:nth-child(4) .pi{background:#fff0c9}
/* หัวข้อหมวด: ป้ายสติกเกอร์ + เส้นประจุดไข่ปลา */
.sh{display:flex;align-items:center;gap:14px;margin-bottom:16px;padding-bottom:12px;border-bottom:4px dotted var(--border)}
.sh .se{font-size:32px;display:grid;place-items:center;width:58px;height:58px;border-radius:20px;background:#fff;box-shadow:var(--lift);transform:rotate(-6deg)}
.cc{margin-left:auto;background:var(--pink-soft);color:var(--pink-deep);border-radius:99px;padding:3px 14px;font-size:13px;font-weight:700;box-shadow:0 3px 0 #ffc4d4,inset 0 2px 0 rgba(255,255,255,.7);transform:rotate(2deg)}
/* การ์ดสินค้า: เงาหลายชั้น เวทีพื้นไล่สี มีเงาพื้น ลอยและเอียงนิดๆ ตอนชี้เมาส์ */
.pc:nth-child(2){animation-delay:.05s}
.pc:nth-child(3){animation-delay:.1s}
.pc:nth-child(4){animation-delay:.15s}
.pc:nth-child(even):hover{transform:translateY(-8px) rotate(.8deg)}
.stage::after{content:"";position:absolute;left:18%;right:18%;bottom:8px;height:12px;background:radial-gradient(ellipse,rgba(91,58,54,.2),transparent 70%)}
.tag{font-size:12px;color:var(--pink-deep);font-weight:700;margin-bottom:4px;display:inline-block;background:var(--pink-soft);border-radius:99px;padding:1px 10px}
.price{font-weight:800;font-size:20px;color:var(--pink-deep);text-shadow:0 2px 0 #fff}
.bdg{position:absolute;top:22px;left:22px;background:linear-gradient(#ff9ebb,var(--pink-deep));border-radius:99px;padding:2px 12px;font-size:12px;font-weight:700;color:#fff;box-shadow:0 3px 0 #b8456a;transform:rotate(-6deg)}
/* กล่อง ฟอร์ม และช่องกรอก: มีขอบสองชั้นกับเงาด้านใน */
.panel,.stat,.order,.tbl{box-shadow:var(--lift);border:4px solid #fff;outline:2px solid var(--border);outline-offset:-2px}
input,textarea,select{box-shadow:inset 0 3px 6px rgba(232,102,139,.08)}
.msg{padding:11px 16px;border-radius:16px;margin-bottom:18px;font-size:14px;box-shadow:0 4px 0 rgba(0,0,0,.04)}
/* หน้า Login: การ์ดนูนมีไฮไลต์ + ตัวการ์ตูนลอยมีเงาพื้น */
.scene{background:radial-gradient(circle at 20% 20%,rgba(255,255,255,.7) 0 90px,transparent 91px),radial-gradient(circle at 82% 78%,rgba(255,255,255,.6) 0 120px,transparent 121px),
linear-gradient(160deg,#ffd6e5,#ffe5d0 50%,#e4d8ff)}
.acard{box-shadow:0 30px 60px -10px rgba(232,102,139,.4),inset 0 4px 0 #fff,inset 0 -6px 0 #ffe3ec;outline:3px dashed var(--border);outline-offset:-14px}
.authkey{box-shadow:0 6px 0 var(--border),0 14px 24px rgba(232,102,139,.3),inset 0 3px 0 #fff}
.pill{box-shadow:inset 0 3px 6px rgba(232,102,139,.12),0 2px 0 #fff}
.mas{filter:drop-shadow(0 14px 8px rgba(120,60,50,.22))}
/* ใบเสร็จ: ขอบหยัก + เงากระดาษ */
.rcpt{max-width:440px;margin:20px auto;padding:30px 34px;background:linear-gradient(#fffdf7,#fff6e6);border:3px dashed #e8c9a0;border-radius:20px;font-family:'Segoe UI',Tahoma,sans-serif;box-shadow:0 18px 30px -10px rgba(91,58,54,.3),0 2px 0 #fff inset}
/* แถบข้างหลังบ้าน: ปุ่มเมนูนูน */
.side{background:linear-gradient(#6b4640,var(--cocoa));color:#fff;padding:22px 16px;display:flex;flex-direction:column;gap:8px;box-shadow:6px 0 24px rgba(46,27,24,.25)}
.sbi{display:block;padding:12px 16px;border-radius:18px;color:#f3d9d3;box-shadow:0 3px 0 rgba(0,0,0,.2)}
.sbi.on{background:linear-gradient(#ffb0c6,var(--pink));color:#fff;box-shadow:0 4px 0 var(--pink-deep),inset 0 2px 0 rgba(255,255,255,.5)}
/* ส่วนท้าย: ขอบบนเป็นคลื่นเมฆ */
footer{background:linear-gradient(#fff,#fff0f5);border-top:none;padding:30px 24px 16px;margin-top:50px;position:relative}
footer::before{content:"";position:absolute;left:0;right:0;top:-18px;height:20px;
background:radial-gradient(circle at 14px 20px,#fff 14px,transparent 15px) 0 0/28px 20px repeat-x}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
/* ======================================================================
   ส่วนเพิ่มของเวอร์ชันนี้: โลโก้แป้นคีย์บอร์ด รูปโปรไฟล์ ช่องพิมพ์ตัวอักษร และสีธีมประจำหมวดตามตัวการ์ตูน
   ====================================================================== */
/* โลโก้ = ปุ่ม F กับ C และแถบ Space bar วาดด้วย CSS (ขนาดทั้งหมดอิงตัวแปร --s ปรับขนาดที่เดียว) */
.klogo{--s:15px;display:inline-flex;flex-direction:column;gap:.2em;font-size:var(--s);transform:rotate(-7deg);flex:none}
.klogo.big{--s:24px}
.klogo .r{display:flex;gap:.2em}
.klogo i{display:grid;place-items:center;width:1.7em;height:1.7em;border-radius:.45em;font:800 .95em/1 'Segoe UI',sans-serif;font-style:normal;color:#fff;
background:linear-gradient(#ffb0c6,#ff7fa0);box-shadow:0 .2em 0 #d94f78,inset 0 .1em 0 rgba(255,255,255,.6)}
.klogo i:last-child{background:linear-gradient(#c4e4ff,#7fb8ff);box-shadow:0 .2em 0 #4f86d9,inset 0 .1em 0 rgba(255,255,255,.6)}
.klogo b{display:block;height:.65em;margin-top:.15em;border-radius:.4em;background:linear-gradient(#fff,#ffd6e0);box-shadow:0 .2em 0 #e8a3b8}
.brand{display:flex;align-items:center;gap:12px;font-size:21px;font-weight:800;white-space:nowrap}
/* รูปโปรไฟล์ (วงกลม) ที่แถบเมนู และแบบใหญ่ในหน้าโปรไฟล์ */
.me{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:700;padding:3px 14px 3px 3px;border-radius:99px;background:#fff;border:2px solid var(--border);box-shadow:0 3px 0 var(--border)}
.av{display:inline-grid;place-items:center;width:34px;height:34px;border-radius:50%;object-fit:cover;background:linear-gradient(#ffb0c6,var(--pink));color:#fff;font-weight:800;box-shadow:0 2px 0 var(--pink-deep)}
.av.big{width:150px;height:150px;font-size:64px;border:6px solid #fff;box-shadow:0 0 0 3px var(--border),0 12px 24px rgba(232,102,139,.3);margin:6px auto 14px}
.profile{text-align:center}
.profile h3{margin-bottom:4px}
.profile form{display:inline-block;margin:8px 4px 0}
/* ช่องพิมพ์ตัวอักษรของพวงกุญแจชื่อ */
.letters{text-transform:uppercase;margin-bottom:6px;font-weight:700;letter-spacing:2px}
.pv{display:flex;gap:8px;flex-wrap:wrap;min-height:4px;margin-bottom:10px}
/* สีธีมประจำหมวด: แต่ละหมวดมีสีของตัวเอง (--th) ใช้กับหัวข้อ ป้าย ขอบการ์ด และพื้นหลังรูปที่ไล่จากสีปุ่มของสินค้านั้น (--c) */
.t-multi{--th:#ff7fa0;--th-soft:#ffe3ec}
.t-single{--th:#2fb593;--th-soft:#d7f5e6}
.t-name{--th:#8a68e8;--th-soft:#ebe1ff}
.t-accessory{--th:#ff9040;--th-soft:#ffe5d0}
.sec .sh h2{color:var(--th)}
.sec .cc{background:var(--th-soft);color:var(--th);box-shadow:0 3px 0 var(--th)}
.sec .sh{border-bottom-color:var(--th-soft)}
.pc{position:relative;background:#fff;border:4px solid #fff;border-radius:30px;padding:14px 14px 18px;transition:transform .15s,box-shadow .15s;box-shadow:0 0 0 2px var(--th-soft),0 14px 26px -8px color-mix(in srgb,var(--th) 45%,transparent),0 3px 0 var(--th-soft);animation:rise .5s both}
.pc:hover{transform:translateY(-8px) rotate(-.8deg);box-shadow:0 0 0 2px var(--th),0 26px 36px -10px color-mix(in srgb,var(--th) 55%,transparent),0 3px 0 var(--th)}
.pc .tag{background:var(--th-soft);color:var(--th)}
.pc .row{display:flex;align-items:center;justify-content:space-between;gap:8px;border-top:3px dotted var(--border);padding-top:10px;border-top-color:var(--th-soft)}
.stage{background:radial-gradient(circle at 50% 28%,rgba(255,255,255,.7) 0,transparent 60%),linear-gradient(160deg,color-mix(in srgb,var(--c,#fbcfe8) 60%,#fff),color-mix(in srgb,var(--c,#fbcfe8) 22%,#fff));border-radius:22px;padding:4px 10px 14px;margin-bottom:12px;min-height:190px;display:flex;align-items:center;justify-content:center;position:relative;box-shadow:inset 0 3px 8px rgba(255,255,255,.9),inset 0 -6px 12px rgba(232,102,139,.1)}
/* ---------- สินค้าแบบเหมือนของจริง: ฝักถั่ว / ชีส / สวิตช์ใส / ปุ่มพาสเทลฐานใส (เลือกด้วยคลาส v-ชื่อถาด) ---------- */
.v-pod{border-radius:46px 46px 46px 46px/78px 78px 46px 46px;padding:18px 14px 22px;gap:12px;background:linear-gradient(100deg,#34b36a,#1f9d55 40%,#14733b)}
.v-pod .ck{border-radius:50%;background:radial-gradient(circle at 35% 28%,color-mix(in srgb,var(--c) 35%,#fff),var(--c) 50%,color-mix(in srgb,var(--c) 68%,#000));box-shadow:0 6px 9px rgba(0,40,0,.4),inset 0 -5px 9px rgba(0,70,0,.35),inset 0 3px 4px rgba(255,255,255,.75)}
.v-pod .ck::before{display:none}
.face{position:relative;width:62%;height:46%;margin-top:0!important;pointer-events:none;background:radial-gradient(circle at 18% 30%,#1c2a12 0 2.2px,transparent 2.8px),radial-gradient(circle at 82% 30%,#1c2a12 0 2.2px,transparent 2.8px)}
.face::after{content:"";position:absolute;left:34%;top:42%;width:32%;height:30%;border-bottom:2.2px solid #1c2a12;border-radius:0 0 50% 50%}
.face.face2{background:radial-gradient(circle at 82% 30%,#1c2a12 0 2.2px,transparent 2.8px)}
.face.face2::before{content:"";position:absolute;left:8%;top:14%;width:20%;height:22%;border-top:2.2px solid #1c2a12;border-radius:50% 50% 0 0}
.face.face3::after{left:26%;top:34%;width:48%;height:34%;border:0;background:radial-gradient(circle at 30% 0,transparent 0 55%,#1c2a12 56% 72%,transparent 73%),radial-gradient(circle at 70% 0,transparent 0 55%,#1c2a12 56% 72%,transparent 73%);background-size:50% 100%;background-repeat:no-repeat;background-position:0 0,100% 0}
.v-cheese .ck{border-radius:9px;background:radial-gradient(circle at 24% 30%,#d99a1c 0 13%,transparent 14%),radial-gradient(circle at 70% 24%,#d99a1c 0 9%,transparent 10%),radial-gradient(circle at 62% 68%,#d99a1c 0 16%,transparent 17%),radial-gradient(circle at 20% 78%,#d99a1c 0 8%,transparent 9%),linear-gradient(150deg,#ffe58a,#fbbf24 55%,#e9a413);box-shadow:0 7px 0 #cf9210,0 12px 12px rgba(80,40,0,.28),inset 0 3px 0 rgba(255,255,255,.7)}
.v-cheese .ck::before{display:none}
.v-glass .ck{border:2px solid rgba(255,255,255,.95);background:linear-gradient(160deg,rgba(255,255,255,.85),rgba(255,255,255,.28));box-shadow:0 7px 0 rgba(150,178,212,.6),0 13px 14px rgba(40,70,120,.24),inset 0 0 12px rgba(255,255,255,.8)}
.v-glass .ck::before{inset:27% 27% 31% 27%;border-radius:6px;background:linear-gradient(color-mix(in srgb,var(--c) 55%,#fff),var(--c));box-shadow:inset 0 1px 0 rgba(255,255,255,.9),0 3px 4px rgba(0,0,0,.22)}
.v-strip{background:linear-gradient(145deg,rgba(255,255,255,.95),rgba(222,236,250,.85))}
.v-strip .ck{border-radius:7px;background:var(--c);box-shadow:0 7px 0 rgba(255,255,255,.85),0 9px 0 rgba(165,188,214,.55),0 15px 14px rgba(40,60,100,.2),inset 0 0 0 1px rgba(255,255,255,.35)}
.v-strip .ck::before{inset:0;border-radius:7px;background:linear-gradient(160deg,rgba(255,255,255,.4),transparent 55%);box-shadow:inset 0 -7px 8px rgba(0,0,0,.06)}
@media print{nav,.side,.noprint,.bar,footer,.atop a{display:none!important}.adm{display:block}.aMain{background:#fff;padding:0}body{background:#fff}}
@media(max-width:800px){.hero{grid-template-columns:1fr;padding:30px 24px}.hero h1{font-size:32px}.hero-art{display:none}
.perks{grid-template-columns:1fr 1fr}.ft,.two,.paywrap{grid-template-columns:1fr}.srch{display:none}nav{flex-wrap:wrap;padding:10px 16px}
.adm{grid-template-columns:1fr}.side{flex-direction:row;flex-wrap:wrap}.prow{grid-template-columns:1fr 1fr}.mas{display:none}}
"""

# ข้อความแจ้งเตือนบนหน้าเว็บ: รหัส (ส่งมาใน URL เช่น ?e=bad) -> (ชนิด, ข้อความ)
MESSAGES = {
    "bad": ("err", "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"),
    "empty": ("err", "กรุณากรอกข้อมูลให้ครบ"),
    "name": ("err", "ชื่อผู้ใช้ต้องมี 3-20 ตัว (a-z, 0-9, _)"),
    "short": ("err", "รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร"),
    "dup": ("err", "ชื่อผู้ใช้นี้ถูกใช้แล้ว"),
    "dupmail": ("err", "อีเมลนี้สมัครไว้แล้ว"),
    "mail": ("err", "รูปแบบอีเมลไม่ถูกต้อง"),
    "mismatch": ("err", "รหัสผ่านและยืนยันรหัสผ่านไม่ตรงกัน"),
    "regok": ("ok", "สมัครสมาชิกสำเร็จ! เข้าสู่ระบบได้เลย"),
    "login": ("err", "กรุณาเข้าสู่ระบบก่อนใช้งาน"),
    "isadmin": ("err", "บัญชีนี้เป็นแอดมิน กรุณาเข้าสู่ระบบที่หน้าแอดมิน"),
    "notadmin": ("err", "บัญชีนี้ไม่ใช่แอดมิน"),
    "forbid": ("err", "ต้องเข้าสู่ระบบแอดมินก่อน"),
    "sent": ("ok", "ถ้าอีเมลนี้อยู่ในระบบ เราได้ส่งรหัส 6 หลักให้แล้ว (โหมดทดสอบ: ดูรหัสใน Terminal ที่รันโปรแกรม)"),
    "badcode": ("err", "รหัสไม่ถูกต้องหรือหมดอายุ"),
    "resetok": ("ok", "ตั้งรหัสผ่านใหม่สำเร็จ เข้าสู่ระบบได้เลย"),
    "limit": ("err", "จำนวนที่เลือกเกินสต็อกที่มี ระบบปรับให้เป็นจำนวนสูงสุดที่เหลือแล้ว"),
    "soldout": ("err", "สินค้านี้หมดสต็อกแล้ว"),
    "stock": ("err", "สินค้าบางรายการมีไม่พอ กรุณาปรับจำนวน"),
    "info": ("err", "กรุณากรอกชื่อ เบอร์โทร (ตัวเลข 9-12 หลัก) และที่อยู่ให้ครบ"),
    "added": ("ok", "เพิ่มสินค้าลงตะกร้าแล้ว ✓"),
    "none": ("err", "กรุณาเลือกอย่างน้อย 1 ปุ่มก่อนใส่ตะกร้า"),
    "noslip": ("err", "กรุณาเลือกภาพสลิปโอนเงินก่อน (รองรับไฟล์ภาพ)"),
    "paid": ("ok", "ส่งสลิปเรียบร้อย รอแอดมินตรวจสอบ"),
    "cancelled": ("ok", "ยกเลิกคำสั่งซื้อแล้ว และคืนสต็อกเรียบร้อย"),
    "verified": ("ok", "ยืนยันการชำระเงินแล้ว"),
    "saved": ("ok", "บันทึกแล้ว ✓"),
    "deleted": ("ok", "ลบสินค้าแล้ว"),
    "badname": ("err", "พิมพ์ตัวอักษรบนปุ่มก่อน (A-Z หรือ 0-9 ไม่เกินจำนวนปุ่มของสินค้านี้)"),
    "badimg": ("err", "รูปไม่ถูกต้อง กรุณาเลือกไฟล์ภาพ (jpg/png)"),
    "wrongpw": ("err", "รหัสผ่านปัจจุบันไม่ถูกต้อง"),
    "pwchanged": ("ok", "เปลี่ยนรหัสผ่านเรียบร้อยแล้ว ✓"),
    "badnick": ("err", "ชื่อเล่นต้องมี 1-20 ตัวอักษร"),
    "badval": ("err", "ข้อมูลไม่ถูกต้อง (ราคา/สต็อกต้องเป็นตัวเลขจำนวนเต็ม)"),
}

# CLICK_JS = โค้ด JavaScript สร้างเสียงคลิกด้วย Web Audio API (สังเคราะห์เสียงสดๆ ไม่ใช้ไฟล์เสียง)
# SND คือสูตรเสียงแต่ละแบบ: เสียงทุ้มของตัวปุ่ม + เสียงคลิกแหลมจากสัญญาณรบกวนที่กรองความถี่
# ปุ่มแต่ละปุ่มเสียงสูงต่ำไม่เท่ากัน และแพนเสียงซ้าย-ขวาตามตำแหน่งบนจอ
CLICK_JS = r"""
var AC,NB;
function ctx(){if(!AC){AC=new(window.AudioContext||window.webkitAudioContext)();var n=AC.sampleRate*0.3,b=AC.createBuffer(1,n,AC.sampleRate),d=b.getChannelData(0);for(var i=0;i<n;i++)d[i]=Math.random()*2-1;NB=b}
if(AC.state=='suspended')AC.resume();return AC}
/* f=เสียงทุ้ม td=ความยาว tg=ความดัง nf/nq/nd/ng=เสียงคลิก up=เสียงตอนปล่อย(คลิก-แคลก) */
var SND={
 blue:{f:210,td:.07,tg:.20,nf:4200,nq:1.2,nd:.03,ng:.9,up:.55,uf:3000},
 brown:{f:170,td:.09,tg:.32,nf:1600,nq:.9,nd:.035,ng:.45,up:0},
 artisan:{f:330,td:.05,tg:.30,nf:3200,nq:1.4,nd:.025,ng:.6,up:.3,uf:2200},
 pop:{f:430,td:.09,tg:.42,nf:2000,nq:1,nd:.02,ng:.25,up:0},
 red:{f:150,td:.10,tg:.34,nf:1200,nq:.8,nd:.04,ng:.40,up:0},
 thock:{f:120,td:.12,tg:.45,nf:900,nq:.7,nd:.05,ng:.35,up:.25,uf:900},
 clack:{f:300,td:.05,tg:.20,nf:5200,nq:1.6,nd:.025,ng:1,up:.7,uf:3800},
 squish:{f:90,td:.14,tg:.40,nf:600,nq:.6,nd:.07,ng:.30,up:0,sw:1.3},
 bubble:{f:560,td:.12,tg:.35,nf:2800,nq:2,nd:.015,ng:.15,up:0,sw:.55},
 chime:{f:880,td:.38,tg:.18,nf:6000,nq:3,nd:.01,ng:.20,up:0,sw:1},
 /* ---- เสียงใหม่ 8 แบบ ---- sw=ตัวคูณความถี่ตอนเริ่ม (เสียงไหลลง/ขึ้น) sr=เวลาที่ใช้ไหล */
 marble:{f:95,td:.16,tg:.5,nf:700,nq:.6,nd:.06,ng:.3,up:.2,uf:700,sw:1.2},        /* ลูกแก้วกระทบ: ทุ้มหนัก */
 typewriter:{f:200,td:.05,tg:.25,nf:4800,nq:1.8,nd:.03,ng:1,up:.9,uf:3200,sw:1.4}, /* พิมพ์ดีด: กด-ปล่อยชัด */
 drop:{f:700,td:.1,tg:.35,nf:3500,nq:3,nd:.01,ng:.1,up:0,sw:.4,sr:.06},            /* หยดน้ำ: ไหลขึ้นเร็ว */
 bell:{f:1320,td:.5,tg:.15,nf:7000,nq:3,nd:.01,ng:.15,up:0,sw:1},                  /* กระดิ่งเสียงสูง ก้องยาว */
 wood:{f:420,td:.04,tg:.4,nf:2400,nq:2.5,nd:.02,ng:.5,up:0,sw:1.1},                /* ไม้ก๊อกๆ สั้นแห้ง */
 boing:{f:230,td:.28,tg:.3,nf:1500,nq:1,nd:.02,ng:.2,up:0,sw:.45,sr:.2},           /* สปริงบึ้ง: ไหลขึ้นช้า */
 harp:{f:660,td:.65,tg:.15,nf:5000,nq:2,nd:.01,ng:.1,up:0,sw:1},                   /* พิณ: ก้องยาวมาก */
 laser:{f:900,td:.15,tg:.22,nf:6000,nq:2,nd:.01,ng:.15,up:0,sw:3,sr:.12}};          /* เลเซอร์: ไหลลงเร็ว */
function tick(a,out,t,f,q,d,gn){var s=a.createBufferSource();s.buffer=NB;var bp=a.createBiquadFilter();bp.type='bandpass';bp.frequency.value=f;bp.Q.value=q;
var g=a.createGain();g.gain.setValueAtTime(gn,t);g.gain.exponentialRampToValueAtTime(.0001,t+d);s.connect(bp);bp.connect(g);g.connect(out);s.start(t,Math.random()*.2,d+.01)}
function play(kind,pitch,pan){var a=ctx(),p=SND[kind]||SND.brown,t=a.currentTime,m=a.createGain(),pn=a.createStereoPanner?a.createStereoPanner():null;
m.gain.value=.9;if(pn){pn.pan.value=pan||0;m.connect(pn);pn.connect(a.destination)}else m.connect(a.destination);
var o=a.createOscillator(),g=a.createGain();o.type='sine';
o.frequency.setValueAtTime(p.f*pitch*(p.sw||1.6),t);o.frequency.exponentialRampToValueAtTime(p.f*pitch,t+(p.sr||.02));
g.gain.setValueAtTime(p.tg,t);g.gain.exponentialRampToValueAtTime(.0001,t+p.td);o.connect(g);g.connect(m);o.start(t);o.stop(t+p.td+.02);
tick(a,m,t,p.nf*pitch,p.nq,p.nd,p.ng);
if(p.up)setTimeout(function(){tick(a,m,a.currentTime,p.uf*pitch,1,.02,p.ng*p.up)},70)}
function pitchOf(s){var h=0;for(var i=0;i<s.length;i++)h=(h*31+s.charCodeAt(i))%97;return .88+(h%13)*.022}
/* ปุ่มที่ i ของแต่ละชุดเสียงไม่เหมือนกัน (ไล่โน้ตขึ้นไป) */
function hit(el){var i=+el.dataset.i||0,r=el.getBoundingClientRect();
 play(el.dataset.snd,.85+(i%12)*.04,Math.max(-.7,Math.min(.7,(r.left+r.width/2)/innerWidth*2-1)))}
document.addEventListener('pointerdown',function(e){var s=e.target.closest('[data-snd]');if(s)hit(s)});
/* กดเลข 1-9 บนคีย์บอร์ดเพื่อเล่นคลิกเกอร์ตัวใหญ่ในหน้าแรก */
document.addEventListener('keydown',function(e){if(e.repeat||/INPUT|TEXTAREA/.test(e.target.tagName))return;
 var n="1234567890-=".indexOf(e.key);if(n<0)return;var k=document.querySelectorAll('.hero .ck')[n];
 if(k){k.classList.add('press');hit(k);setTimeout(function(){k.classList.remove('press')},110)}});
/* ปุ่มทั่วไป: เสียงสั้น ๆ คนละระดับตามข้อความบนปุ่ม */
document.addEventListener('mousedown',function(e){var t=e.target.closest('.btn,.tab');
 if(!t||t.dataset.snd)return;play('brown',pitchOf(t.textContent.trim()||'x'),0)});
"""
# JavaScript เพิ่มเติม: นับจำนวนครั้งที่กด และทำสัญลักษณ์ลอยขึ้นตรงที่คลิก
CLICK_JS += r"""
document.addEventListener('pointerdown',function(e){var s=e.target.closest('[data-snd]');if(!s)return;
 if(s.closest('.hero')){var c=document.getElementById('cn');if(c)c.textContent=+c.textContent+1}
 var f=document.createElement('div');f.className='fx';f.textContent=['♪','✦','↵','⌥','⌘'][Math.floor(Math.random()*5)];
 f.style.left=(e.clientX-10)+'px';f.style.top=(e.clientY-20)+'px';document.body.appendChild(f);setTimeout(function(){f.remove()},900)});
"""


# รายชื่อเสียงทั้งหมดที่มีในสูตร SND (ดึงจากข้อความ JavaScript ด้านบน) ใช้ตรวจตอนแอดมินเพิ่มสินค้า
SOUND_NAMES = re.findall(r"^\s*(\w+):\{f:", CLICK_JS, re.M)
# JAVASCRIPT เล็กๆ ที่ฝังในทุกหน้า (ทำงานในเบราว์เซอร์ของผู้ใช้)
#   - ปุ่ม Show/Hide สลับ type ของช่องรหัสผ่านระหว่าง password กับ text
#   - ไฟวิ่งบนถาดหน้าแรก (เพิ่ม/ลบ class wave ทีละปุ่ม)
#   - สลิป: อ่านไฟล์ภาพ ย่อให้กว้างไม่เกิน 900px แล้วแปลงเป็นข้อความ base64 ใส่ช่องซ่อน
#     (ส่งไปกับฟอร์มธรรมดา เซิร์ฟเวอร์ตรวจว่าเป็น JPEG จริงก่อนบันทึก)
#   - รูปโปรไฟล์: เลือกไฟล์ > ตัดกลางภาพเป็นสี่เหลี่ยม ย่อเป็น 256x256 > ส่งขึ้นเซิร์ฟเวอร์
#   - พวงกุญแจชื่อ: พิมพ์ตัวอักษร > แปลงเป็นตัวพิมพ์ใหญ่ A-Z/0-9 > โชว์ตัวอย่างปุ่มทันที (กดแล้วมีเสียง)
UI_JS = r"""
[].forEach.call(document.querySelectorAll('[data-show]'),function(s){s.onclick=function(){
 var i=s.parentNode.querySelector('input'),h=i.type=='password';i.type=h?'text':'password';s.textContent=h?'Hide':'Show'}});
/* รูปโปรไฟล์: เลือกไฟล์ -> ตัดกลางภาพเป็นสี่เหลี่ยมจัตุรัส 256x256 -> แปลงเป็น JPEG ใส่ช่องซ่อน -> โชว์ตัวอย่างทันที */
var av=document.getElementById('avfile');
if(av)av.onchange=function(){var file=av.files[0];if(!file)return;var r=new FileReader();
 r.onload=function(){var im=new Image();im.onload=function(){var m=Math.min(im.width,im.height),c=document.createElement('canvas');
  c.width=c.height=256;c.getContext('2d').drawImage(im,(im.width-m)/2,(im.height-m)/2,m,m,0,0,256,256);
  var d=c.toDataURL('image/jpeg',.85),p=document.getElementById('avprev');document.getElementById('avdata').value=d;
  if(p.tagName=='IMG')p.src=d;else{var i=document.createElement('img');i.id='avprev';i.className=p.className;i.src=d;p.replaceWith(i)}
  document.getElementById('avsave').disabled=false};im.src=r.result};r.readAsDataURL(file)};
/* พวงกุญแจชื่อ: พิมพ์ตัวอักษร -> แปลงเป็นตัวพิมพ์ใหญ่ A-Z/0-9 -> สร้างปุ่มตัวอย่างใต้ช่อง (กดฟังเสียงได้) */
[].forEach.call(document.querySelectorAll('[data-pv]'),function(inp){var box=document.getElementById(inp.dataset.pv),cols=inp.dataset.colors.split(',');
 inp.oninput=function(){var v=inp.value.toUpperCase().replace(/[^A-Z0-9]/g,'');inp.value=v;box.textContent='';
  for(var k=0;k<v.length;k++){var d=document.createElement('div');d.className='ck';d.style.setProperty('--c',cols[k%cols.length]);
   d.dataset.snd=inp.dataset.snd;d.dataset.i=k;d.innerHTML='<span class="tx">'+v[k]+'</span>';box.appendChild(d)}}});
var ks=document.querySelectorAll('.hero .ck'),n=0;
if(ks.length)setInterval(function(){for(var j=0;j<ks.length;j++)ks[j].classList.remove('wave');ks[n%ks.length].classList.add('wave');n++},420);
/* แอดมินเลือกรูป QR: ย่อให้กว้างไม่เกิน 900px เป็น JPEG แล้วแสดงตัวอย่างก่อนกดบันทึก */
var qf=document.getElementById('qrfile');
if(qf)qf.onchange=function(){var file=qf.files[0];if(!file)return;var r=new FileReader();
 r.onload=function(){var im=new Image();im.onload=function(){var k=Math.min(1,900/Math.max(im.width,im.height)),c=document.createElement('canvas');
  c.width=im.width*k;c.height=im.height*k;var x=c.getContext('2d');x.fillStyle='#fff';x.fillRect(0,0,c.width,c.height);x.drawImage(im,0,0,c.width,c.height);
  var d=c.toDataURL('image/jpeg',.9);document.getElementById('qrdata').value=d;document.getElementById('qrprev').src=d;document.getElementById('qrsave').disabled=false};im.src=r.result};r.readAsDataURL(file)};
/* ช่องพิมพ์จำนวน (หน้าร้านและตะกร้า): ห้ามเกินสต็อก ถ้าพิมพ์เกินจะปรับเป็นค่าสูงสุดและขึ้นข้อความเตือนใต้ช่อง */
[].forEach.call(document.querySelectorAll('input.qty'),function(q){var w=document.getElementById(q.dataset.w),m=+q.dataset.max;
 q.oninput=function(){var v=parseInt(q.value,10);if(isNaN(v))return;
  if(v>m){q.value=m;if(w)w.textContent='มีสินค้าเพียง '+m+' ชิ้น (ครบจำนวนสต็อก)';
   if(q.form&&!q.form.over){q.form.insertAdjacentHTML('beforeend','<input type="hidden" name="over" value="1">')}}
  else if(v<1&&!q.dataset.auto){q.value=1}else if(w&&v<m){w.textContent=''}};
 q.onkeydown=function(e){if(e.key=='Enter'&&q.dataset.auto){e.preventDefault();q.form.submit()}}});
var f=document.getElementById('slipfile');
if(f)f.onchange=function(){var file=f.files[0];if(!file)return;var r=new FileReader();
 r.onload=function(){var im=new Image();im.onload=function(){var s=Math.min(1,900/Math.max(im.width,im.height)),c=document.createElement('canvas');
  c.width=im.width*s;c.height=im.height*s;c.getContext('2d').drawImage(im,0,0,c.width,c.height);
  document.getElementById('slipdata').value=c.toDataURL('image/jpeg',.75);
  document.getElementById('slipname').textContent='เลือกแล้ว: '+file.name;document.getElementById('payok').disabled=false};
  im.src=r.result};r.readAsDataURL(file)};
"""

# ======================================================================
# ส่วนที่ 5: ฟังก์ชันสร้างหน้าเว็บ
# ======================================================================
def flash(code):
    """แปลงรหัสใน URL (?e=...) เป็นกล่องข้อความแจ้งเตือน ถ้ารหัสไม่รู้จักก็ไม่แสดงอะไร"""
    if code in MESSAGES:
        return '<div class="msg %s">%s</div>' % MESSAGES[code]
    return ""


# ====================================================================
# 5.1 ชิ้นส่วนเล็กที่ใช้ซ้ำทุกหน้า
#   logo()        = โลโก้แป้นคีย์บอร์ด F C วาดด้วย CSS ล้วน (ไม่มีรูป ไม่มีอีโมจิ)
#   avatar_html() = วงกลมรูปโปรไฟล์ ถ้าไม่มีรูปจะแสดงตัวอักษรแรกของชื่อแทน
#   head()        = ส่วน <head> ของ HTML: ใส่ CSS ทั้งหมดและตั้งค่าหน้าจอมือถือ
# ====================================================================
def logo(big=False):
    """โลโก้ร้าน: ปุ่มคีย์บอร์ด 2 ปุ่ม (F, C) กับแถบ Space bar ด้านล่าง วาดด้วย CSS ล้วน (ไม่ใช้รูป ไม่ใช้อีโมจิ)"""
    return '<span class="klogo%s"><span class="r"><i>F</i><i>C</i></span><b></b></span>' % (" big" if big else "")


def avatar_html(u, cls="av"):
    """รูปโปรไฟล์วงกลม: ถ้าอัปโหลดรูปไว้ใช้รูป (ใส่เลขเวลาต่อท้าย URL เพื่อให้เบราว์เซอร์โหลดรูปใหม่ทันทีที่เปลี่ยน)
    ถ้ายังไม่มีรูป แสดงตัวอักษรแรกของชื่อบนปุ่มสีชมพูแทน"""
    if u["avatar"]:
        return '<img class="%s" src="/avatar?v=%d" alt="">' % (cls, u["avatar"])
    return '<span class="%s">%s</span>' % (cls, escape((u["nickname"] or u["username"])[:1].upper()))


def head(title):
    """ส่วนหัวของทุกหน้า HTML (ภาษา ชื่อแท็บ และ CSS ทั้งหมด (ไม่โหลดอะไรจากอินเทอร์เน็ต เปิดออฟไลน์ได้))"""
    return ('<!DOCTYPE html><html lang="th"><head><meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>%s</title><style>%s</style></head><body>' % (escape(title), CSS))


# EMOJI = ลายตุ๊กตา/ของน่ารักบนปุ่ม ใช้อีโมจิแทนการวาด (เพิ่มลายใหม่แค่เติมอีกหนึ่งบรรทัด)
# ====================================================================
# 5.2 ภาพสินค้า (วาดจาก HTML/CSS ไม่ใช้ไฟล์รูป)
#   EMOJI / TRAYS = พจนานุกรมลายการ์ตูนบนปุ่ม และสีถาด
#   motif() > key_html() > visual() = ประกอบเป็นปุ่มคีย์แคป 1 ปุ่ม แล้วรวมเป็นถาดทั้งแผง
#   สูตรของสินค้าอยู่ในช่อง look (ดูหัวข้อ SEED): กี่คอลัมน์|กี่แถว|ถาด|เสียง|ลาย|สี
# ====================================================================
EMOJI = {
    # สัตว์
    "cat": "🐱", "panda": "🐼", "bear": "🐻", "bunny": "🐰", "fox": "🦊", "penguin": "🐧", "frog": "🐸", "chick": "🐥", "pig": "🐷",
    "dino": "🦖", "unicorn": "🦄", "paw": "🐾",
    # อาหาร
    "bun": "🥟", "egg": "🍳", "sushi": "🍣", "onigiri": "🍙", "pizza": "🍕", "carrot": "🥕", "donut": "🍩", "strawberry": "🍓",
    "cake": "🍰", "icecream": "🍦", "cone": "🍦", "cookie": "🍪", "cupcake": "🧁", "burger": "🍔", "cherry": "🍒",
    "avocado": "🥑", "lemon": "🍋", "watermelon": "🍉",
    # ของน่ารักอื่นๆ
    "heart": "💖", "star": "⭐", "flower": "🌸", "cloud": "☁️", "ribbon": "🎀", "rainbow": "🌈", "moon": "🌙", "sun": "☀️",
    "music": "🎵", "bolt": "⚡", "crown": "👑", "ghost": "👻", "alien": "👽", "gem": "💎", "planet": "🪐",
    "chain": "🔗", "gift": "🎁",
}
# สีถาดคลิกเกอร์: ชื่อ -> (สีพื้น, สีขอบ, สีเงา)
TRAYS = {
    "white": ("#ffffff", "#e5e7eb", "#cfd4db"), "pink": ("#fbcfe8", "#f9a8d4", "#ec7fb0"),
    "wood": ("#e8c58a", "#c99a57", "#a37a3f"), "bento": ("#ef4444", "#b91c1c", "#7f1d1d"),
    "egg": ("#fde68a", "#f5b83d", "#d99a1c"), "clear": ("#f8fafc", "#cbd5e1", "#aeb9c7"),
    # 4 แบบตามสินค้าจริง: ฝักถั่ว (pod) | ฐานอะคริลิกใส + ปุ่มพาสเทลด้าน (strip) | สวิตช์ใส (glass) | ชีส (ใช้ถาด cup: สีเหลือง)
    "pod": ("#1f9d55", "#14663a", "#0f4d2c"), "strip": ("#f4f9ff", "#d9e6f4", "#bccde0"), "glass": ("#dfeafb", "#c8d8f0", "#a9bdd9"),
}


def motif(m):
    """HTML ของลายบนปุ่ม: ขึ้นต้น t: = ตัวอักษร, อยู่ใน EMOJI = อีโมจิ"""
    if m.startswith("t:"):
        return '<span class="tx">%s</span>' % escape(m[2:])
    if m.startswith("face"):  # หน้ายิ้มบนลูกถั่ว (face1 ยิ้ม | face2 ขยิบตา | face3 ปากแมว) วาดด้วย CSS
        return '<span class="face %s"></span>' % m
    return '<span class="em">%s</span>' % EMOJI[m] if m in EMOJI else ""


def key_html(m, color, snd, i):
    """ปุ่มคีย์แคป 1 ปุ่ม ใส่ชนิดเสียง (data-snd) และลำดับปุ่ม (data-i) เพื่อให้ JavaScript เล่นเสียงได้"""
    attrs = ' data-snd="%s" data-i="%d"' % (snd, i) if snd else ""
    return '<div class="ck" style="--c:%s"%s>%s</div>' % (color, attrs, motif(m))


def thumb(p):
    """ภาพย่อปุ่มเดียวสำหรับแสดงในตะกร้า (ถ้าเป็นพวงกุญแจชื่อ จะโชว์ตัวอักษรแรกที่ลูกค้าเลือก)"""
    f = p["look"].split("|")
    note = p["note"] if "note" in p.keys() else ""
    return '<div style="--ks:46px;flex:none">%s</div>' % key_html("t:" + note[0] if note else f[4].split(",")[0], f[5].split(",")[0], "", 0)


def visual(p):
    """ภาพสินค้า: วาดถาดคลิกเกอร์ด้วย HTML/CSS จากสูตร look ของสินค้า (กดแต่ละปุ่มมีเสียง ไม่ต้องใช้ไฟล์รูป)"""
    cols, rows, tray, snd, motifs, colors = p["look"].split("|")
    cols, rows, motifs, colors = int(cols), int(rows), motifs.split(","), colors.split(",")
    snds = snd.split(",")  # ใส่ชื่อเสียงหลายชื่อคั่นด้วย , = ปุ่มแต่ละปุ่มใช้เสียงคนละแบบ (ใช้ที่แบนเนอร์หน้าแรก)
    keys = "".join(key_html(motifs[i % len(motifs)], colors[i % len(colors)], snds[i % len(snds)], i) for i in range(cols * rows))
    name, _, col = tray.partition(":")
    if name in ("cup", "cheese"):  # cheese = กล่องสีเหลืองเหมือน cup แต่ปุ่มเป็นก้อนชีส
        tb, tbd, tsh = col, "color-mix(in srgb,%s 78%%,#000)" % col, "color-mix(in srgb,%s 62%%,#000)" % col
    else:
        tb, tbd, tsh = TRAYS.get(name, TRAYS["white"])
    return '<div class="tray v-%s" style="--cols:%d;--ks:%dpx;--tb:%s;--tbd:%s;--tsh:%s">%s</div>' % (
        name, cols, 44 if cols <= 3 else 34, tb, tbd, tsh, keys)


# ====================================================================
# 5.3 โครงหน้าเว็บกลาง
#   page() ห่อเนื้อหาทุกหน้าด้วย: แถบเมนูบน (โลโก้ ค้นหา ตะกร้า โปรไฟล์) + ส่วนท้าย
#   auth_page() ใช้กับหน้าที่ยังไม่ล็อกอิน (ล็อกอิน/สมัคร/ลืมรหัส) จึงไม่มีเมนูร้าน
# ====================================================================
def page(title, body, user=None, cart_n=0):
    """โครงหน้าฝั่งลูกค้า: แถบเมนู + เนื้อหา + ส่วนท้าย + JavaScript (เมนูเปลี่ยนตามว่าล็อกอินหรือยัง)"""
    links = ""
    if user:
        links = ('<a class="l" href="/orders">คำสั่งซื้อ</a><a class="l" href="/cart">ตะกร้า<span class="badge">%d</span></a>'
                 '<a class="me" href="/profile">%s<span>%s</span></a><a class="l" href="/logout">ออกจากระบบ</a>'
                 % (cart_n, avatar_html(user), escape(user["nickname"] or user["username"])))
    shop_links = "".join('<a href="/?cat=%s">%s %s</a>' % (k, v[0], v[1]) for k, v in CAT_INFO.items()) + '<a href="/build">🎹 ออกแบบคีย์บอร์ดเอง</a>'
    return (
        head(title)
        + '<nav><a class="brand" href="/">' + logo() + '%s</a>'
        '<a class="l" href="/build">ออกแบบเอง</a><form class="srch" action="/"><input name="q" placeholder="ค้นหาคลิกเกอร์ ชื่อสินค้า..." autocomplete="off"></form>'
        '<span class="sp"></span>%s</nav>' % (SHOP_NAME, links)
        + '<div class="bar">ลองกดได้ทุกชิ้นก่อนซื้อ · ทุกปุ่มเสียงไม่เหมือนกัน · ออกแบบคีย์บอร์ดเองได้</div>'
        + '<main>%s</main>' % body
        + '<footer><div class="ft"><div><h4>%s</h4><p>ร้านคลิกเกอร์และพวงกุญแจกดมันส์ ลายตุ๊กตาน่ารัก ลองกดฟังเสียงได้ทุกชิ้นก่อนซื้อ</p></div>'
        '<div><h4>เลือกซื้อ</h4>%s</div>'
        '<div><h4>บัญชีของฉัน</h4><a href="/profile">โปรไฟล์</a><a href="/cart">ตะกร้า</a><a href="/orders">คำสั่งซื้อ</a></div></div>'
        '<div class="copy">© %s · v26-qty-input</div></footer>' % (SHOP_NAME, shop_links, SHOP_NAME)
        + '<script>%s</script></body></html>' % (CLICK_JS + UI_JS)
    )


def auth_page(title, card):
    """โครงหน้าล็อกอิน/สมัคร/ลืมรหัสผ่าน: ไม่มีแถบเมนู มีตุ๊กตาอีโมจิลอยอยู่รอบการ์ด"""
    floaters = "".join('<span class="mas m%d">%s</span>' % (i, e) for i, e in enumerate("🐰🧸🐼🦊🐥🐧"))
    return head(title) + '<div class="scene">%s%s</div><script>%s</script></body></html>' % (floaters, card, UI_JS)


# ====================================================================
# 5.4 หน้าสมาชิก (ล็อกอิน / สมัคร / ลืมรหัสผ่าน)
#   pill() = ช่องกรอกข้อมูล 1 ช่อง, acard() = การ์ดฟอร์มทั้งใบ
#   login_body / register_body / forgot_body / reset_body = เนื้อหาของแต่ละหน้า
# ====================================================================
def pill(icon, name, ph, typ="text", show=False):
    """ช่องกรอกทรงแคปซูลพร้อมไอคอน (และปุ่ม Show ถ้าเป็นช่องรหัสผ่าน)"""
    btn = '<button type="button" class="show" data-show>Show</button>' if show else ""
    return ('<label class="pill"><span>%s</span><input name="%s" type="%s" placeholder="%s" '
            'autocomplete="off" required>%s</label>' % (icon, name, typ, ph, btn))


def acard(action, heading, sub, code, fields, button, links):
    """การ์ดขาวมนของหน้าล็อกอิน/สมัคร: ไอคอนหมีด้านบน หัวข้อ ช่องกรอก ปุ่มหลัก และลิงก์ด้านล่าง"""
    return ('<form class="acard" method="post" action="%s"><div class="authkey">%s</div><h1>%s</h1><div class="sub">%s</div>%s%s'
            '<button class="btn wide">%s</button>%s</form>' % (action, logo(True), heading, sub, flash(code), fields, button, links))


def login_body(code, admin=False):
    """หน้าล็อกอิน: ใช้ฟอร์มเดียวกัน 2 ทาง /login (ลูกค้า) กับ /admin/login (แอดมิน)"""
    fields = pill("👤", "username", "Username") + pill("🔒", "password", "Password", "password", True)
    if admin:
        links = '<div class="swrole"><a href="/login">← กลับไปหน้าลูกค้า</a></div>'
        return acard("/admin/login", "Admin Login", "ระบบหลังบ้าน %s" % SHOP_NAME, code, fields, "Login", links)
    links = ('<div class="alinks"><a href="/forgot">Forgot Password</a><a href="/register">Create Account</a></div>'
             '<div class="swrole"><a href="/admin/login">เข้าสู่ระบบแอดมิน</a></div>')
    return acard("/login", "Login", "เข้าสู่ระบบเพื่อเลือกซื้อตุ๊กตาน่ารัก", code, fields, "Login", links)


def register_body(code):
    """หน้าสมัครสมาชิก: ชื่อผู้ใช้ อีเมล รหัสผ่าน และยืนยันรหัสผ่าน"""
    fields = (pill("👤", "username", "Username") + pill("✉", "email", "Gmail / Email", "email")
              + pill("🔒", "password", "Password (6 ตัวขึ้นไป)", "password", True)
              + pill("🔒", "confirm", "Confirm Password", "password", True))
    return acard("/register", "Create Account", "สมัครสมาชิกเพื่อเริ่มช้อป", code, fields, "Create Account",
                 '<div class="alinks"><a href="/login">← Back to Login</a></div>')


def forgot_body(code):
    """หน้าลืมรหัสผ่านขั้นที่ 1: กรอกอีเมล ระบบสร้างรหัส 6 หลัก"""
    return acard("/forgot", "Forgot Password ?", "กรอกอีเมลที่สมัครไว้", code, pill("✉", "email", "Please enter your email", "email"),
                 "Submit", '<div class="alinks"><a href="/login">← Back to Login</a><a href="/reset">มีรหัสแล้ว?</a></div>')


def reset_body(code):
    """หน้าลืมรหัสผ่านขั้นที่ 2: กรอกอีเมล รหัส 6 หลัก และรหัสผ่านใหม่"""
    fields = (pill("✉", "email", "Email", "email") + pill("#", "code", "รหัส 6 หลัก")
              + pill("🔒", "password", "รหัสผ่านใหม่ (6 ตัวขึ้นไป)", "password", True) + pill("🔒", "confirm", "ยืนยันรหัสผ่านใหม่", "password", True))
    return acard("/reset", "Reset Password", "ตั้งรหัสผ่านใหม่", code, fields, "Reset",
                 '<div class="alinks"><a href="/login">← Back to Login</a></div>')


# แบนเนอร์หน้าแรก: ข้อความต้อนรับ + ถาดคลิกเกอร์ 12 ปุ่มที่กดเล่นได้ + ตัวนับจำนวนครั้งที่กด
HERO = (
    '<div class="hero"><div><span class="chip">🎹 ลองกดได้เลย!</span>'
    '<h1>%s<br><span>กดมันส์</span> ลายตุ๊กตาน่ารัก</h1>'
    '<p>กดปุ่มทางขวาเพื่อฟังเสียงได้เลย ทุกปุ่มเสียงไม่เหมือนกัน (หรือกดแถวตัวเลข 1 2 3 … บนคีย์บอร์ด)</p>'
    '<a class="btn" href="/build">ออกแบบคีย์บอร์ดเอง</a> <a class="btn cream" href="#shop">เลือกซื้อเลย</a></div>'
    '<div class="hero-art">%s<div class="cnt">กดไปแล้ว <b id="cn">0</b> ครั้ง</div></div></div>'
    % (SHOP_NAME, visual({"id": 0, "look": "4|3|pink|blue,brown,artisan,pop,red,thock,clack,squish,bubble,chime,marble,typewriter|bear,bunny,panda,fox,penguin,chick,pig,frog,cat,unicorn,donut,strawberry|" + P6 + ",#a7f3d0,#fed7aa,#c7d2fe"}))
)

# ====================================================================
# 5.5 หน้าร้านค้า
#   card() = การ์ดสินค้า 1 ใบ: ภาพถาด (กดปุ่มบนถาดเพื่อฟังเสียง) > ชื่อ > (ช่องพิมพ์ตัวอักษร) > ราคา+ปุ่มใส่ตะกร้า
#   section() = จัดการ์ดเป็นหมวด พร้อมหัวข้อและสีธีมของหมวดนั้น
#   shop_body() = ประกอบแบนเนอร์ + แถบหมวด + การเรียงลำดับ + ทุกหมวด
# ====================================================================
# แถวจุดเด่นของร้าน 4 ช่องใต้แบนเนอร์ (%d = จำนวนเสียงคลิก)
PERKS = (
    '<div class="perks">'
    '<div class="perk"><span class="pi">👆</span><div><b>ลองกดได้ทุกชิ้น</b><small>ฟังเสียงก่อนตัดสินใจ</small></div></div>'
    '<div class="perk"><span class="pi">🎵</span><div><b>เสียงคลิก %d แบบ</b><small>ไม่ซ้ำกันทุกชุด</small></div></div>'
    '<a class="perk" href="/build"><span class="pi">🎹</span><div><b>ออกแบบเองได้</b><small>เลือกปุ่มเอง คิดราคาทันที</small></div></a>'
    '<div class="perk"><span class="pi">🎁</span><div><b>มีกล่องของขวัญ</b><small>พร้อมริบบิ้นน่ารัก</small></div></div>'
    "</div>"
)


def card(p, cat):
    """การ์ดสินค้า 1 ใบ (เรียงจากบนลงล่าง): รูปสินค้า > แผงทดลองเสียง > ชื่อ/คำอธิบาย
    > ช่องพิมพ์ตัวอักษร (เฉพาะพวงกุญแจชื่อ) > ราคา + ปุ่มใส่ตะกร้า (ส่งแบบ POST ไป /cart/add)"""
    out = p["stock"] <= 0
    cols, rows_, tray, snd, motifs, colors = p["look"].split("|")
    emoji, title, _ = CAT_INFO.get(p["category"], ("", p["category"], ""))
    badge = '<span class="bdg">%s</span>' % ("สินค้าหมด" if out else "เหลือน้อย") if p["stock"] <= 20 else ""
    letters = ""
    if p["category"] == "name":  # ช่องพิมพ์ตัวอักษร + ตัวอย่างปุ่มที่เปลี่ยนตามที่พิมพ์ (JavaScript ชุด data-pv)
        n = int(cols) * int(rows_)
        letters = ('<input class="letters" name="note" form="f%d" maxlength="%d" placeholder="พิมพ์ตัวอักษรบนปุ่ม (A-Z, 0-9 ไม่เกิน %d ตัว)" '
                   'data-pv="pv%d" data-snd="%s" data-colors="%s" autocomplete="off" required><div class="pv" id="pv%d" style="--ks:38px"></div>'
                   % (p["id"], n, n, p["id"], snd, colors, p["id"]))
    return (
        '<div class="pc t-%s"><div class="stage" style="--c:%s">%s</div>%s<div class="tag">%s %s</div><h3>%s</h3><p>%s</p>%s'
        '<div class="row"><div><div class="price">%s</div><div class="stock">%s</div></div>'
        '<form id="f%d" method="post" action="/cart/add"><input type="hidden" name="product_id" value="%d">'
        '<input type="hidden" name="next" value="/?cat=%s&e=added">%s<button class="btn" %s>%s</button></form></div><div class="qw" id="qw%d"></div></div>'
        % (p["category"], colors.split(",")[0], visual(p), badge,
           emoji, escape(title), escape(p["name"]), escape(p["description"]), letters,
           money(p["price"]), "สินค้าหมด" if out else "เหลือ %d ชิ้น" % p["stock"], p["id"], p["id"], cat,
           "" if out else '<input class="qty" type="number" name="qty" value="1" min="1" max="%d" data-max="%d" data-w="qw%d" title="จำนวนที่ต้องการ">' % (p["stock"], p["stock"], p["id"]),
           "disabled" if out else "", "หมด" if out else "ใส่ตะกร้า", p["id"])
    )


def section(key, items, cat):
    """ส่วนของ 1 หมวด: หัวข้อ + จำนวนรายการ + ตารางการ์ดสินค้า (class t-หมวด ใช้กำหนดสีธีมของหมวดนั้นใน CSS)"""
    emoji, title, sub = CAT_INFO[key]
    return ('<section class="sec t-%s"><div class="sh"><span class="se">%s</span><div><h2>%s</h2><p>%s</p></div>'
            '<span class="cc">%d รายการ</span></div><div class="grid">%s</div></section>'
            % (key, emoji, title, sub, len(items), "".join(card(p, cat) for p in items)))


def shop_body(products, cat, code, qs="", sort=""):
    """เนื้อหาหน้าร้านทั้งหมด: แบนเนอร์ แท็บหมวด แถบเรียง และสินค้าแยกตามหมวด (ถ้าค้นหาจะซ่อนแบนเนอร์)"""
    base = "/?cat=%s&q=%s" % (cat, quote(qs))
    cats = [("all", "ทั้งหมด")] + [(k, "%s %s" % (v[0], v[1])) for k, v in CAT_INFO.items()]
    tabs = "".join('<a class="tab%s" href="/?cat=%s&q=%s">%s</a>' % (" on" if k == cat else "", k, quote(qs), v) for k, v in cats)
    sorts = "".join('<a class="tab%s" href="%s&sort=%s">%s</a>' % (" on" if sort == k else "", base, k, v)
                    for k, v in (("", "ล่าสุด"), ("asc", "ราคาต่ำ → สูง"), ("desc", "ราคาสูง → ต่ำ")))
    keys = list(CAT_INFO) if cat == "all" else [cat]
    secs = "".join(section(k, [p for p in products if p["category"] == k], cat) for k in keys if any(p["category"] == k for p in products))
    n = len(products)
    msg = ('ผลการค้นหา "<b>%s</b>" พบ %d รายการ — <a href="/" style="color:var(--pink-deep)">ล้างการค้นหา</a>' % (escape(qs), n)) if qs else "สินค้าทั้งหมด %d รายการ" % n
    top = "" if qs else HERO + PERKS % len(SOUND_NAMES)
    return (top + flash(code) + '<div class="tabs" id="shop">' + tabs + '</div><div class="toolbar"><span>' + msg +
            '</span><div class="sorts">เรียงตาม: ' + sorts + "</div></div>" + (secs or '<div class="empty">ไม่พบสินค้า</div>'))


# ====================================================================
# 5.6 ตะกร้า / โปรไฟล์ / ชำระเงิน / ใบเสร็จ
#   cart_body = รายการในตะกร้า + ฟอร์มที่อยู่
#   profile_body = หน้าโปรไฟล์ (เปลี่ยนรูป ตั้งชื่อเล่น)
#   pay_body = QR + ยอดโอน + แนบสลิป | orders_body = ประวัติคำสั่งซื้อ | receipt_body = ใบเสร็จ
# ====================================================================
def cart_body(rows, code):
    """หน้าตะกร้า: รายการสินค้า ปุ่มเพิ่ม/ลด/ลบ ราคารวม (ยังไม่รวมภาษี) และฟอร์มที่อยู่จัดส่ง"""
    if not rows:
        return '<h2 class="t">ตะกร้าสินค้า</h2>%s<div class="panel empty">ตะกร้าว่างเปล่า — <a href="/" style="color:var(--pink-deep)">ไปเลือกสินค้า</a></div>' % flash(code)
    sub = sum(r["price"] * r["qty"] for r in rows)  # ราคารวม = ผลรวมของ (ราคาต่อชิ้น x จำนวน)
    vat, total = calc_total(sub)
    btn = lambda r, d, label: ('<form method="post" action="/cart/update"><input type="hidden" name="product_id" value="%d">'
                               '<input type="hidden" name="note" value="%s"><input type="hidden" name="delta" value="%d">'
                               '<button class="btn sm">%s</button></form>' % (r["id"], escape(r["note"]), d, label))
    used = {}  # จำนวนรวมต่อสินค้า (พวงกุญแจชื่อหลายแถวใช้สต็อกก้อนเดียวกัน) เพื่อคำนวณว่าแถวนี้ขอเพิ่มได้อีกกี่ชิ้น
    for r in rows:
        used[r["id"]] = used.get(r["id"], 0) + r["qty"]
    room = lambda r: r["stock"] - (used[r["id"]] - r["qty"])  # จำนวนสูงสุดที่แถวนี้ตั้งได้
    qinput = lambda r: ('<form method="post" action="/cart/set"><input type="hidden" name="product_id" value="%d"><input type="hidden" name="note" value="%s">'
                        '<input class="qty" type="number" name="qty" value="%d" min="1" max="%d" data-max="%d" data-w="cw%d_%s" data-auto="1" onchange="this.form.submit()"></form>'
                        % (r["id"], escape(r["note"]), r["qty"], room(r), room(r), r["id"], r["note"]))
    lines = "".join(
        '<div class="line">%s<div class="nm">%s<small>%s%s ต่อชิ้น · เหลือสต็อก %d ชิ้น</small>%s</div><div class="q">%s%s%s</div>'
        '<div class="price" style="min-width:90px;text-align:right">%s</div>'
        '<form method="post" action="/cart/remove"><input type="hidden" name="product_id" value="%d"><input type="hidden" name="note" value="%s">'
        '<button class="btn sm red">ลบ</button></form></div>'
        % (thumb(r), escape(r["name"]), "ชื่อบนปุ่ม: %s · " % escape(r["note"]) if r["note"] else "", money(r["price"]), r["stock"],
           '<div class="qw" id="cw%d_%s">%s</div>' % (r["id"], r["note"], "ครบจำนวนสต็อกแล้ว ไม่สามารถเพิ่มได้อีก" if r["qty"] >= room(r) else ""),
           btn(r, -1, "−"), qinput(r), btn(r, 1, "+").replace("<button", "<button disabled" if r["qty"] >= room(r) else "<button"),
           money(r["price"] * r["qty"]), r["id"], escape(r["note"]))
        for r in rows)
    return (
        '<h2 class="t">ตะกร้าสินค้า</h2>%s<div class="two"><div class="panel">%s'
        '<div class="sum"><span>ราคาสินค้า</span><span>%s</span></div><div class="sum"><span>VAT 7 เปอร์เซ็นต์</span><span>%s</span></div>'
        '<div class="total"><span>รวมทั้งหมด</span><span style="color:var(--pink-deep)">%s</span></div></div>'
        '<form class="panel" method="post" action="/checkout"><h2 class="t" style="font-size:20px">ที่อยู่จัดส่ง</h2>'
        '<input name="name" placeholder="ชื่อ-นามสกุล" required><input name="phone" placeholder="เบอร์โทรศัพท์" required>'
        '<textarea name="address" rows="4" placeholder="ที่อยู่จัดส่ง" required></textarea>'
        '<button class="btn wide">ไปหน้าชำระเงิน</button></form></div>' % (flash(code), lines, money2(sub), money2(vat), money2(total))
    )


def profile_body(u, code):
    """หน้าโปรไฟล์: รูปโปรไฟล์ (เปลี่ยนหรือลบได้ตลอดเวลา) + ชื่อเล่น + ข้อมูลบัญชี
    เลือกรูป -> JavaScript ตัดเป็นสี่เหลี่ยมจัตุรัส 256x256 แปลงเป็น JPEG ใส่ช่องซ่อน #avdata -> กด "บันทึกรูป" ส่งไป /profile/avatar"""
    remove = ('<form method="post" action="/profile/avatar/remove"><button class="btn sm red">ลบรูป</button></form>' if u["avatar"] else "")
    html = (
        '<h2 class="t">โปรไฟล์ของฉัน</h2>%s<div class="two"><div class="panel profile">%s'
        '<h3>รูปโปรไฟล์</h3><p class="stock">เปลี่ยนได้ตลอดเวลา ไฟล์ jpg / png ก็ได้ ระบบย่อรูปให้อัตโนมัติ</p>'
        '<form method="post" action="/profile/avatar"><input type="hidden" name="avatar" id="avdata">'
        '<input type="file" id="avfile" accept="image/*" hidden>'
        '<button type="button" class="btn dark" onclick="document.getElementById(\'avfile\').click()">เลือกรูปใหม่</button> '
        '<button class="btn" id="avsave" disabled>บันทึกรูป</button></form>%s</div>'
        '<div class="panel"><h3>ข้อมูลบัญชี</h3>'
        '<form method="post" action="/profile/nickname"><label class="stock">ชื่อเล่น (แสดงบนแถบเมนู)</label>'
        '<input name="nickname" value="%s" maxlength="20" placeholder="ชื่อเล่น" required><button class="btn">บันทึกชื่อเล่น</button></form>'
        '<div class="sum"><span>ชื่อผู้ใช้</span><span>%s</span></div><div class="sum"><span>อีเมล</span><span>%s</span></div>'
        '<div class="sum"><span>สมัครเมื่อ</span><span>%s</span></div></div></div>'
        '<div class="panel" style="margin-top:20px"><h3>เปลี่ยนรหัสผ่าน</h3><form method="post" action="/profile/password" class="pwform">%s</form></div>'
        % (flash(code), avatar_html(u, "av big").replace('class="av big"', 'class="av big" id="avprev"'), remove,
           escape(u["nickname"], True), escape(u["username"]), escape(u["email"] or "-"), be_date(u["created"], False),
           pill("🔑", "current", "รหัสผ่านปัจจุบัน", "password", True) + pill("🔒", "password", "รหัสผ่านใหม่ (6 ตัวขึ้นไป)", "password", True)
           + pill("🔒", "confirm", "ยืนยันรหัสผ่านใหม่", "password", True) + '<button class="btn">เปลี่ยนรหัสผ่าน</button>')
    )
    # แอดมินใช้หน้าเดียวกัน แต่ฟอร์มส่งไปที่ /admin/profile/... (ผ่านด่านตรวจสิทธิ์แอดมิน)
    if u["role"] == "admin":  # ตัดหัวข้อซ้ำออก (หน้าแอดมินมีหัวข้อด้านบนอยู่แล้ว)
        return html.replace('<h2 class="t">โปรไฟล์ของฉัน</h2>', "").replace('action="/profile/', 'action="/admin/profile/')
    return html


def pay_body(o, items, code):
    """หน้าชำระเงิน: ซ้าย = รายการสั่งซื้อ ขวา = รูป QR PromptPay + ยอดที่ต้องโอน + ปุ่มเลือกสลิป/ยืนยัน
    QR เป็นรูปนิ่งของร้าน (qr.png) จึงแสดงยอดที่ต้องโอนเป็นตัวใหญ่ให้ลูกค้ากรอกเองในแอปธนาคาร"""
    st, cls = STATUS.get(o["status"], ("", ""))
    lis = "".join('<div class="pitem"><div><b>%s</b><small>จำนวน %d ชิ้น</small></div><span class="price">฿%s</span></div>'
                  % (escape(i["product_name"]), i["qty"], money2(i["price"] * i["qty"])) for i in items)
    left = '<div class="panel"><h2 class="t" style="text-align:center;font-size:22px">รายการสั่งซื้อของคุณ</h2>%s</div>' % lis
    sums = ('<div class="sum"><span>รวมราคาสินค้า</span><span>฿%s</span></div><div class="sum"><span>VAT 7 เปอร์เซ็นต์</span><span>฿%s</span></div>'
            '<div class="sum big"><span>รวมทั้งหมด</span><span>฿%s</span></div>' % (money2(o["subtotal"]), money2(o["vat"]), money2(o["total"])))
    head_ = '<div class="qrbox"><div class="stock">เลขที่บิล %s · <span class="st %s">%s</span></div>' % (escape(o["bill_no"]), cls, st)
    if o["status"] != "awaiting":
        extra = '<a class="btn dark wide" href="/receipt?id=%d" style="margin-top:12px">ดูใบเสร็จ</a>' % o["id"] if o["status"] == "verified" else ""
        right = head_ + '</div>' + sums + extra
    else:
        qr = '<img class="qr" src="/qr" alt="QR PromptPay">'  # รูป QR ของร้าน (ดู QR_B64 ท้ายไฟล์)
        right = (head_ + qr + '<h3>สแกนเพื่อชำระผ่าน PromptPay</h3><div class="pay-amount">โอนยอด <b>฿%s</b></div></div>' % money2(o["total"]) + sums
                 + '<form method="post" action="/pay" style="margin-top:14px"><input type="hidden" name="id" value="%d">'
                 '<input type="hidden" name="slip" id="slipdata"><input type="file" id="slipfile" accept="image/*" hidden>'
                 '<button type="button" class="btn dark wide" onclick="document.getElementById(\'slipfile\').click()">เลือกภาพสลิปโอนเงิน</button>'
                 '<div id="slipname" class="stock" style="text-align:center;margin:8px 0">ยังไม่ได้เลือกสลิป</div>'
                 '<button class="btn cream wide" id="payok" disabled>ยืนยันการชำระเงิน</button></form>'
                 '<form method="post" action="/order/cancel" style="margin-top:10px"><input type="hidden" name="id" value="%d">'
                 '<button class="btn sm red wide">ยกเลิกคำสั่งซื้อ</button></form>' % (o["id"], o["id"]))
    return '<h2 class="t">ชำระสินค้า</h2>%s<div class="paywrap">%s<div class="panel">%s</div></div>' % (flash(code), left, right)


def orders_body(orders, items, code):
    """หน้าประวัติคำสั่งซื้อของลูกค้า: เลขบิล สถานะ รายการ และปุ่มที่ทำต่อได้ตามสถานะ"""
    if not orders:
        return '<h2 class="t">คำสั่งซื้อของฉัน</h2>%s<div class="panel empty">ยังไม่มีคำสั่งซื้อ</div>' % flash(code)
    html = ""
    for o in orders:
        li = "".join("<li>%s × %d — %s</li>" % (escape(i["product_name"]), i["qty"], money(i["price"] * i["qty"])) for i in items.get(o["id"], []))
        st, cls = STATUS.get(o["status"], ("", ""))
        act = ""
        if o["status"] == "awaiting":
            act = '<a class="btn sm" href="/pay?id=%d">ชำระเงิน</a>' % o["id"]
        elif o["status"] == "verified":
            act = '<a class="btn sm" href="/receipt?id=%d">ดูใบเสร็จ</a>' % o["id"]
        html += (
            '<div class="order"><h4><span>บิล %s · %s</span><span><span class="st %s">%s</span> <b style="color:var(--pink-deep)">%s</b></span></h4><ul>%s</ul>'
            '<p class="stock" style="margin-top:8px">จัดส่งถึง: %s · %s · %s</p><div style="margin-top:8px">%s</div></div>'
            % (escape(o["bill_no"]), be_date(o["created"]), cls, st, money(o["total"]), li, escape(o["name"]), escape(o["phone"]), escape(o["address"]), act)
        )
    return '<h2 class="t">คำสั่งซื้อของฉัน</h2>%s<div class="panel">%s</div>' % (flash(code), html)


def receipt_body(o, items, customer):
    """ใบยืนยันการชำระเงิน (หน้าตาเหมือนกระดาษ) แสดงรายการ ภาษี ยอดรวม และตราว่าแอดมินยืนยันแล้ว"""
    rows = "".join('<div class="ri"><span>%s x %d</span><span>%s B</span></div>' % (escape(i["product_name"]), i["qty"], money2(i["price"] * i["qty"])) for i in items)
    return (
        '<div class="rcpt"><div class="rh">' + logo() + '<div><b>ใบยืนยันการชำระเงิน</b><span>(Payment Receipt)</span><br><small>%s · ร้านตุ๊กตาและของน่ารัก</small></div></div>'
        '<div class="rmeta"><span>Order : %s</span><span class="ver">✔ Verified</span></div>'
        '<div class="rmeta"><span>วันที่ %s</span><span></span></div>'
        '<h4>- Order Details -</h4>%s'
        '<div class="rt"><div><span>Customer</span><span>%s</span></div><div><span>Subtotal</span><span>%s B</span></div>'
        '<div><span>Vat 7 percent</span><span>%s B</span></div><div><b>Total Payment</b><b>%s B</b></div></div>'
        '<div class="rsign">Verified by Admin<div class="sig">%s</div></div><div class="thx">Thank you for your payment</div></div>'
        '<p class="noprint" style="text-align:center"><button class="btn dark" onclick="window.print()">พิมพ์ใบเสร็จ</button> '
        '<a class="btn sm" href="/orders">กลับ</a></p>'
        % (SHOP_NAME, escape(o["bill_no"]), be_date(o["created"]), rows, escape(customer), money2(o["subtotal"]),
           money2(o["vat"]), money2(o["total"]), escape(o["verified_by"] or "admin"))
    )


# ---------------- ออกแบบคีย์บอร์ดเอง ----------------
# ---------------- หน้าออกแบบคีย์บอร์ดเอง ----------------
# สร้างรายการปุ่มตัวอักษรจากข้อความ เช่น "QWE" -> ปุ่ม q, w, e ราคาปุ่มละ 15 บาท
def _L(txt):
    return [(c.lower(), c, 1, 15) for c in txt]


# แผนผังคีย์บอร์ดทีละแถว: แต่ละปุ่มคือ (รหัสปุ่ม, ข้อความบนปุ่ม, ความกว้าง, ราคา)
ROWS = [
    [(k, e, 2, 25) for k, e in (("cat", "🐱"), ("bear", "🐻"), ("bunny", "🐰"), ("fox", "🦊"), ("star", "⭐"), ("donut", "🍩"))],
    [(k, e, 2, 25) for k, e in (("panda", "🐼"), ("penguin", "🐧"), ("frog", "🐸"), ("chick", "🐥"), ("pig", "🐷"), ("rainbow", "🌈"), ("moon", "🌙"))],
    [(c, c, 1, 15) for c in "1234567890"] + [("minus", "-", 1, 15), ("equal", "=", 1, 15), ("back", "⌫", 3, 20)],
    [("tab", "Tab", 1.5, 20)] + _L("QWERTYUIOP") + [("lb", "[", 1, 15), ("rb", "]", 1, 15), ("bsl", "\\", 1.5, 15)],
    [("caps", "Caps", 1.75, 20)] + _L("ASDFGHJKL") + [("semi", ";", 1, 15), ("quote", "'", 1, 15), ("enter", "Enter", 2.25, 20)],
    [("shl", "Shift", 2.25, 20)] + _L("ZXCVBNM") + [("comma", ",", 1, 15), ("dot", ".", 1, 15), ("slash", "/", 1, 15), ("shr", "Shift", 2.75, 20)],
    [("ctl", "Ctrl", 2, 20), ("al", "Alt", 2, 20), ("space", "Space", 7, 30), ("ar", "Alt", 2, 20), ("ctr", "Ctrl", 2, 20)],
]
# KEYS = ตารางค้นหาเร็ว รหัสปุ่ม -> (ชื่อ, ราคา) ใช้ตรวจและคิดราคาที่ฝั่งเซิร์ฟเวอร์
KEYS = {i: (lab, pr) for row in ROWS for (i, lab, w, pr) in row}
# ตัวเลือกฐานคีย์บอร์ด: รหัส -> (ชื่อ, ราคาฐาน)
BASES = {"white": ("ขาวมินิมอล", 49), "sakura": ("ซากุระ", 59), "retro": ("เรโทร", 59), "dark": ("ดำ", 59)}
# สีปุ่มที่ผู้ใช้เลือกได้ (ชื่อ -> รหัสสี)
THEMES = {"pink": "#f9a8d4", "blue": "#93c5fd", "mint": "#86efac", "lilac": "#c4b5fd", "cream": "#fde68a"}
# ตัวเลือกเสียงของคีย์บอร์ดที่ออกแบบเอง
SOUND_OPTS = [("blue", "คลิกแคลก (Blue)"), ("red", "นุ่มเรียบ (Red)"), ("brown", "ทุ้มนุ่ม (Brown)"), ("thock", "ทุ้มหนัก (Thock)"),
              ("clack", "แหลมใส (Clack)"), ("bubble", "ฟองป๊อป"), ("chime", "กระดิ่ง"), ("squish", "ยุบนุ่ม"),
              ("marble", "ลูกแก้วทุ้ม"), ("typewriter", "พิมพ์ดีด"), ("drop", "หยดน้ำ"), ("bell", "กระดิ่งใหญ่"),
              ("wood", "ไม้ก๊อก"), ("boing", "สปริง"), ("harp", "พิณ"), ("laser", "เลเซอร์")]

# JavaScript ของหน้าออกแบบ: คลิกปุ่มเพื่อเลือก/ยกเลิก แล้วคำนวณจำนวนปุ่ม ราคารวม และส่งรายการปุ่มที่เลือกไปกับฟอร์ม
BUILD_JS = r"""
(function(){
var bd=document.getElementById('bd'),base='white',BP=__BASEP__;
var keys=[].slice.call(bd.querySelectorAll('.k'));
function $(i){return document.getElementById(i)}
function upd(){var ids=[],labs=[],sum=0;
 keys.forEach(function(k){if(k.classList.contains('sel')){ids.push(k.dataset.id);labs.push(k.dataset.l);sum+=+k.dataset.p}});
 var n=ids.length,tot=n?BP[base]+sum:0;
 $('cnt').textContent=n;$('ksum').textContent='฿'+sum.toLocaleString();$('bp').textContent='฿'+(n?BP[base]:0);
 $('tot').textContent='฿'+tot.toLocaleString();$('btot').textContent='฿'+tot.toLocaleString();
 $('chips').textContent='';labs.forEach(function(l){var s=document.createElement('span');s.textContent=l;$('chips').appendChild(s)});
 $('f_keys').value=ids.join(',');$('f_base').value=base;$('go').disabled=!n}
keys.forEach(function(k){k.addEventListener('click',function(){k.classList.toggle('sel');upd()})});
[].forEach.call(document.querySelectorAll('[data-b]'),function(b){b.addEventListener('click',function(){
 base=b.dataset.b;bd.dataset.theme=base;[].forEach.call(document.querySelectorAll('[data-b]'),function(x){x.classList.toggle('on',x===b)});upd()})});
[].forEach.call(document.querySelectorAll('[data-c]'),function(d){d.addEventListener('click',function(){
 bd.style.setProperty('--sel',d.dataset.c);$('f_color').value=d.dataset.n;
 [].forEach.call(document.querySelectorAll('[data-c]'),function(x){x.classList.toggle('on',x===d)})})});
$('snd').addEventListener('change',function(){var v=this.value;keys.forEach(function(k){k.dataset.snd=v});$('f_snd').value=v;play(v,1,0)});
$('all').onclick=function(){keys.forEach(function(k){k.classList.add('sel')});upd()};
$('none').onclick=function(){keys.forEach(function(k){k.classList.remove('sel')});upd()};
$('rnd').onclick=function(){keys.forEach(function(k){k.classList.toggle('sel',Math.random()<.3)});upd()};
upd()})();
"""


# สร้าง HTML ของหน้าออกแบบ: บอร์ดปุ่มทุกแถว ตัวเลือกฐาน/สี/เสียง และกล่องสรุปราคา
def build_body(code):
    n = 0
    board = ""
    for row in ROWS:
        cells = ""
        for i, lab, w, pr in row:
            inner = '<span class="em">%s</span>' % lab if i in EMOJI else escape(lab)
            cells += (
                '<div class="k" data-id="%s" data-p="%d" data-l="%s" data-snd="blue" data-i="%d" style="--w:%s" title="%s ฿%d">%s<small>฿%d</small></div>'
                % (i, pr, escape(lab), n % 12, w, escape(lab), pr, inner, pr)
            )
            n += 1
        board += '<div class="kr">%s</div>' % cells
    bases = "".join(
        '<button type="button" class="tab%s" data-b="%s">%s · ฿%d</button>' % (" on" if k == "white" else "", k, v[0], v[1]) for k, v in BASES.items()
    )
    dots = "".join(
        '<span class="dot%s" data-c="%s" data-n="%s" style="background:%s"></span>' % (" on" if k == "pink" else "", c, k, c) for k, c in THEMES.items()
    )
    opts = "".join('<option value="%s">%s</option>' % o for o in SOUND_OPTS)
    js = BUILD_JS.replace("__BASEP__", json.dumps({k: v[1] for k, v in BASES.items()}))
    return (
        '<h2 class="t">ออกแบบคีย์บอร์ดคลิกเกอร์ของคุณ</h2>%s'
        '<p class="stock" style="margin-bottom:6px">คลิกปุ่มที่อยากได้ (กดแล้วมีเสียง) ปุ่มที่เลือกจะเป็นสีสดมีเครื่องหมาย ✓ — ราคารวมคิดให้ทันที</p>'
        '<p class="stock">ตัวอักษร/ตัวเลข ฿15 · ปุ่มพิเศษ ฿20 · Space ฿30 · ปุ่มการ์ตูน ฿25 · บวกค่าฐาน</p>'
        '<div class="ctl"><b>ฐาน:</b>%s</div>'
        '<div class="ctl"><b>สีปุ่มที่เลือก:</b>%s<b style="margin-left:14px">เสียง:</b><select id="snd">%s</select></div>'
        '<div class="ctl"><button type="button" class="btn sm" id="all">เลือกทั้งหมด</button>'
        '<button type="button" class="btn sm" id="rnd">สุ่ม</button><button type="button" class="btn sm red" id="none">ล้าง</button></div>'
        '<div class="boardwrap"><div class="board" id="bd" data-theme="white" style="--sel:#f9a8d4">%s</div></div>'
        '<form class="panel center" style="max-width:520px;text-align:left" method="post" action="/build/add">'
        '<h2 class="t" style="font-size:20px">สรุปรายการ</h2>'
        '<div class="sumrow"><span>ฐานคีย์บอร์ด</span><b id="bp">฿0</b></div>'
        '<div class="sumrow"><span>ปุ่มที่เลือก <b id="cnt">0</b> ปุ่ม</span><b id="ksum">฿0</b></div>'
        '<div class="chips" id="chips"></div>'
        '<div class="total"><span>ราคารวม</span><span style="color:var(--accent)" id="tot">฿0</span></div>'
        '<input type="hidden" name="keys" id="f_keys"><input type="hidden" name="base" id="f_base" value="white">'
        '<input type="hidden" name="snd" id="f_snd" value="blue"><input type="hidden" name="color" id="f_color" value="pink">'
        '<button class="btn wide" id="go" style="margin-top:14px" disabled>ใส่ตะกร้า <span id="btot">฿0</span></button></form>'
        '<script>%s</script>' % (flash(code), bases, dots, opts, board, js)
    )

# ---------------- หลังบ้านแอดมิน ----------------
# เมนูซ้าย 4 ปุ่ม: (รหัสหน้า, ชื่อบนปุ่ม, คำอธิบายเล็ก)
ADMIN_TABS = [("report", "Report", "รายงานยอดขาย"), ("orders", "Order", "ตรวจสลิป/คำสั่งซื้อ"),
              ("products", "Product", "สินค้าและสต็อก"), ("dashboard", "Dashboard", "ภาพรวมร้าน"),
              ("profile", "Profile", "โปรไฟล์แอดมิน")]


def admin_page(title, active, heading, body, user, code=""):
    """โครงหน้าแอดมิน: แถบเมนูซ้ายสีน้ำตาลโกโก้ + พื้นที่เนื้อหาด้านขวา"""
    side = "".join('<a class="sbi%s" href="/admin/%s"><b>%s</b><small>%s</small></a>' % (" on" if k == active else "", k, en, th)
                   for k, en, th in ADMIN_TABS)
    return (head("แอดมิน - " + title)
            + '<div class="adm"><aside class="side"><div class="abrand">' + logo() + '%s<span>Admin</span></div>%s'
            '<a class="sbi out" href="/logout">ออกจากระบบ</a></aside>'
            '<section class="aMain"><div class="atop"><h2>%s</h2><a class="me" href="/admin/profile">%s<span>%s</span></a></div>%s%s</section></div>'
            '<script>%s</script></body></html>' % (SHOP_NAME, side, heading, avatar_html(user), escape(user["nickname"] or user["username"]), flash(code), body, UI_JS))


def report_body(table, view, d1, d2, sm):
    """Report: แถบเลือกมุมมอง + ช่วงวันที่ + ปุ่มลัด + การ์ดสรุป + ตารางตามมุมมอง + ปุ่มส่งออก Excel/พิมพ์"""
    names = {"bill": "รายบิล", "day": "รายวัน", "month": "รายเดือน", "year": "รายปี", "product": "ตามสินค้า"}
    qs = lambda v, a_, b_: "v=%s&from=%s&to=%s" % (v, a_, b_)
    tabs = "".join('<a class="vt%s" href="/admin/report?%s">%s</a>' % (" on" if k == view else "", qs(k, d1, d2), n) for k, n in names.items())
    t = datetime.date.today()
    quick = "".join('<a class="btn sm cream" href="/admin/report?%s">%s</a>' % (qs(view, x, y), n) for n, x, y in (
        ("วันนี้", t, t), ("7 วัน", t - datetime.timedelta(days=6), t), ("30 วัน", t - datetime.timedelta(days=29), t),
        ("เดือนนี้", t.replace(day=1), t), ("ปีนี้", t.replace(month=1, day=1), t)))
    form = ('<form class="panel dfilter" method="get" action="/admin/report"><div class="vts">%s</div><input type="hidden" name="v" value="%s">'
            '<span class="stock">ช่วงวันที่</span><input type="date" name="from" value="%s"><b>ถึง</b><input type="date" name="to" value="%s">'
            '<button class="btn sm">ค้นหา</button><span class="noprint">%s</span></form>' % (tabs, view, d1, d2, quick))
    cards = "".join('<div class="stat"><small>%s</small><b>%s</b></div>' % c for c in (
        ("ยอดขายรวม (รวม VAT)", "฿" + money2(sm["total"])), ("จำนวนบิล", sm["bills"]), ("เฉลี่ยต่อบิล", "฿" + money2(sm["avg"])),
        ("ภาษี VAT รวม", "฿" + money2(sm["vat"])), ("จำนวนสินค้าที่ขาย", "%d ชิ้น" % sm["items"])))
    empty = lambda n: '<tr><td colspan="%d" class="empty">ไม่มีข้อมูลในช่วงนี้</td></tr>' % n
    if view == "bill":
        head = "<th>เลขที่บิล</th><th>วันที่ขาย</th><th>ลูกค้า</th><th class=\"r\">ราคาสินค้า</th><th class=\"r\">VAT</th><th class=\"r\">ยอดเงิน (บาท)</th>"
        body = "".join('<tr><td>%s</td><td>%s</td><td>%s</td><td class="r">%s</td><td class="r">%s</td><td class="r">%s</td></tr>' % (
            escape(r["bill_no"]), be_date(r["created"]), escape(r["username"] or "-"), money2(r["subtotal"]), money2(r["vat"]), money2(r["total"])) for r in table)
        n = 6
    elif view == "product":
        head = '<th>สินค้า</th><th class="r">จำนวนที่ขาย (ชิ้น)</th><th class="r">ยอดขาย (บาท)</th>'
        body = "".join('<tr><td>%s</td><td class="r">%d</td><td class="r">%s</td></tr>' % (escape(r["k"]), r["n"], money2(r["total"])) for r in table)
        n = 3
    else:
        head = '<th>%s</th><th class="r">จำนวนบิล</th><th class="r">ราคาสินค้า</th><th class="r">VAT</th><th class="r">ยอดเงิน (บาท)</th>' % {"day": "วันที่", "month": "เดือน", "year": "ปี"}[view]
        body = "".join('<tr><td>%s</td><td class="r">%d</td><td class="r">%s</td><td class="r">%s</td><td class="r">%s</td></tr>' % (
            period_label(r["k"], view), r["n"], money2(r["sub"]), money2(r["vat"]), money2(r["total"])) for r in table)
        n = 5
    tbl = '<table class="tbl"><tr>%s</tr>%s</table>' % (head, body or empty(n))
    actions = ('<div class="noprint" style="text-align:center;margin-top:18px"><a class="btn green" href="/admin/report.csv?%s">Export Excel (%s)</a> '
               '<button type="button" class="btn dark" onclick="window.print()">พิมพ์สรุป</button></div>' % (qs(view, d1, d2), names[view]))
    note = '<p class="stock" style="text-align:center;margin-top:12px">นับเฉพาะคำสั่งซื้อที่แอดมินยืนยันการชำระเงินแล้ว · ช่วงวันที่ %s ถึง %s</p>' % (
        be_date(time.mktime(d1.timetuple()), False), be_date(time.mktime(d2.timetuple()), False))
    if view == "product":
        note += '<p class="stock" style="text-align:center">ยอดขายรายสินค้าเป็นราคาก่อน VAT (รวมทุกสินค้า %s บาท)</p>' % money2(sm["sub"])
    return form + '<div class="cards">' + cards + "</div>" + tbl + '<div class="bigtotal">ยอดขายรวม: %s บาท</div>' % money2(sm["total"]) + note + actions


def admin_orders_body(orders, items, flt):
    """Order: รายการคำสั่งซื้อทั้งหมด กรองตามสถานะ ดูสลิป กดยืนยัน/ยกเลิก (ยกเลิกแล้วคืนสต็อก)"""
    tabs = '<div class="tabs">%s</div>' % "".join('<a class="tab%s" href="/admin/orders?s=%s">%s</a>' % (" on" if flt == k else "", k, v)
           for k, v in (("", "ทั้งหมด"), ("paid", "รอตรวจสลิป"), ("awaiting", "รอชำระ"), ("verified", "ชำระแล้ว"), ("cancelled", "ยกเลิก")))
    html = ""
    for o in orders:
        st, cls = STATUS.get(o["status"], ("", ""))
        li = "".join("<li>%s × %d — %s</li>" % (escape(i["product_name"]), i["qty"], money2(i["price"] * i["qty"])) for i in items.get(o["id"], []))
        slip = '<div class="slip"><a href="/slip?id=%d" target="_blank"><img src="/slip?id=%d" alt="slip"></a></div>' % (o["id"], o["id"]) if o["slip"] else '<span class="stock">ยังไม่มีสลิป</span>'
        acts = ""
        if o["status"] in ("paid", "awaiting"):
            acts = ('<form method="post" action="/admin/order/verify" style="display:inline"><input type="hidden" name="id" value="%d"><button class="btn green sm" style="color:#fff">ยืนยันการชำระเงิน</button></form> '
                    '<form method="post" action="/admin/order/cancel" style="display:inline"><input type="hidden" name="id" value="%d"><button class="btn sm red">ยกเลิก (คืนสต็อก)</button></form>' % (o["id"], o["id"]))
        elif o["status"] == "verified":
            acts = '<a class="btn sm" href="/receipt?id=%d" target="_blank">ดูใบเสร็จ</a>' % o["id"]
        html += ('<div class="order"><h4><span>บิล %s · %s</span><span><span class="st %s">%s</span> <b style="color:var(--accent-deep)">฿%s</b></span></h4>'
                 '<p class="stock">ลูกค้า: %s (%s) · %s · %s</p><ul>%s</ul><div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap;margin-top:8px">%s<div>%s</div></div></div>'
                 % (escape(o["bill_no"]), be_date(o["created"]), cls, st, money2(o["total"]), escape(o["name"]), escape(o["username"] or "-"),
                    escape(o["phone"]), escape(o["address"]), li, slip, acts))
    return tabs + (html or '<div class="panel empty">ไม่มีคำสั่งซื้อ</div>')



def admin_products_body(rows):
    """Product: แก้ชื่อ/ราคา/สต็อก ลบสินค้า และเพิ่มสินค้าใหม่ (ช่องสต็อกขึ้นกรอบแดงเมื่อเหลือ 10 ชิ้นหรือน้อยกว่า)"""
    opt = lambda items: "".join('<option value="%s">%s</option>' % (escape(k), escape(v)) for k, v in items)
    motifs = [(k, k) for k in list(EMOJI)]
    sounds = [(k, k) for k in SOUND_NAMES]
    cats = [(k, CAT_INFO[k][1]) for k in CAT_INFO]
    add = ('<form class="panel" method="post" action="/admin/product/add"><h2 class="t" style="font-size:20px">เพิ่มสินค้าใหม่</h2><div class="pform">'
           '<div><label>ชื่อสินค้า</label><input name="name" required></div><div><label>ราคา (บาท)</label><input name="price" type="number" min="1" required></div>'
           '<div><label>สต็อก</label><input name="stock" type="number" min="0" required></div><div><label>หมวด</label><select name="category">%s</select></div>'
           '<div><label>ลายบนปุ่ม</label><select name="motif">%s</select></div><div><label>เสียง</label><select name="snd">%s</select></div>'
           '<div><label>สีปุ่ม</label><input name="color" type="color" value="#fbcfe8" style="padding:2px"></div>'
           '<div><label>จำนวนคอลัมน์</label><input name="cols" type="number" min="1" max="6" value="1"></div>'
           '<div><label>จำนวนแถว</label><input name="rows" type="number" min="1" max="4" value="1"></div></div>'
           '<label style="font-size:12px;color:var(--muted)">คำอธิบาย</label><input name="description" required>'
           '<button class="btn">เพิ่มสินค้า</button></form>' % (opt(cats), opt(motifs), opt(sounds)))
    lst = ""
    qrp = ('<form class="panel" method="post" action="/admin/qr"><h2 class="t" style="font-size:20px">รูป QR รับเงิน</h2>'
           '<div class="qrset"><img id="qrprev" src="/qr?v=%d" alt="QR"><div><p class="stock">รูปที่ลูกค้าเห็นในหน้าชำระเงิน (รองรับ QR PromptPay / Thai QR Payment สแกนได้ทุกธนาคาร)</p>'
           '<input type="hidden" name="qr" id="qrdata"><input type="file" id="qrfile" accept="image/*" hidden>'
           '<button type="button" class="btn dark sm" onclick="document.getElementById(\'qrfile\').click()">เลือกรูป QR ใหม่</button> '
           '<button class="btn sm" id="qrsave" disabled>บันทึกรูป QR</button> '
           '<button class="btn sm red" formaction="/admin/qr/reset" onclick="return confirm(\'กลับไปใช้รูป QR ตั้งต้น?\')">ใช้รูปตั้งต้น</button></div></div></form>'
           % int(time.time()))
    for p in rows:
        lst += ('<form class="prow%s" method="post" action="/admin/product/save"><input type="hidden" name="id" value="%d">'
                '<input name="name" value="%s"><input name="price" type="number" min="1" value="%d"><input class="stk" name="stock" type="number" min="0" value="%d">'
                '<input name="description" value="%s"><button class="btn sm">บันทึก</button>'
                '<button class="btn sm red" formaction="/admin/product/delete" onclick="return confirm(\'ลบสินค้านี้?\')">ลบ</button></form>'
                % (" low" if p["stock"] <= 10 else "", p["id"], escape(p["name"], True), p["price"], p["stock"], escape(p["description"], True)))
    head_ = '<div class="prow" style="font-weight:700;border-bottom:2px solid var(--border)"><span>ชื่อ</span><span>ราคา</span><span>สต็อก</span><span>คำอธิบาย</span><span></span><span></span></div>'
    return qrp + add + '<div class="panel"><h2 class="t" style="font-size:20px">สินค้าทั้งหมด (%d รายการ)</h2>%s%s</div>' % (len(rows), head_, lst)


def dashboard_body(st, top, low, series, view, d1, d2):
    """Dashboard: แถบเลือกมุมมอง (รายวัน/เดือน/ปี) + ช่วงวันที่ + ตัวเลขสรุป + กราฟแท่ง + สินค้าขายดี + สินค้าใกล้หมด
    series = [(ป้ายชื่อแท่ง, ยอดขาย), ...] ที่ page_dashboard รวมไว้ให้แล้วตามมุมมองที่เลือก"""
    names = {"day": "รายวัน", "month": "รายเดือน", "year": "รายปี"}
    tabs = "".join('<label class="vt%s"><input type="radio" name="v" value="%s"%s onchange="this.form.from.value=\'\';this.form.to.value=\'\';this.form.submit()">%s</label>' % (" on" if k == view else "", k, " checked" if k == view else "", n)
                   for k, n in names.items())
    rng = "%s ถึง %s" % (be_date(time.mktime(d1.timetuple()), False), be_date(time.mktime(d2.timetuple()), False))
    form = ('<form class="panel dfilter" method="get" action="/admin/dashboard"><div class="vts">%s</div>'
            '<span class="stock">ช่วงวันที่</span><input type="date" name="from" value="%s"><b>ถึง</b><input type="date" name="to" value="%s">'
            '<button class="btn sm">แสดงผล</button><a class="btn sm cream" href="/admin/dashboard">ล้างค่า</a></form>' % (tabs, d1, d2))
    cards = "".join('<div class="stat"><small>%s</small><b>%s</b></div>' % c for c in (
        ("ยอดขายในช่วงที่เลือก", "฿" + money2(st["sales"])), ("บิลที่ชำระแล้วในช่วงนี้", st["verified"]), ("รอตรวจสลิป (ตอนนี้)", st["paid"]),
        ("รอชำระเงิน (ตอนนี้)", st["awaiting"]), ("สมาชิก", st["users"])))
    mx = max([d[1] for d in series] + [1])
    bars = "".join('<div class="bar1"><span>%s</span><i style="height:%d%%"></i><span>%s</span></div>' % (money(v), int(v / mx * 70), lab) for lab, v in series)
    toplist = "".join("<li>%s — ขายแล้ว %d ชิ้น (฿%s)</li>" % (escape(t["product_name"]), t["q"], money2(t["rev"])) for t in top) or "<li>ยังไม่มีข้อมูลในช่วงนี้</li>"
    lowlist = "".join("<li>%s — เหลือ %d ชิ้น</li>" % (escape(p["name"]), p["stock"]) for p in low) or "<li>สต็อกปกติทุกรายการ</li>"
    return (form + '<div class="cards">' + cards + '</div>'
            + '<div class="panel"><h2 class="t" style="font-size:20px">ยอดขาย%s <small class="stock">(%s)</small></h2><div class="bars">%s</div></div>' % (names[view], rng, bars)
            + '<div class="two"><div class="panel"><h2 class="t" style="font-size:20px">สินค้าขายดี 5 อันดับ (ในช่วงที่เลือก)</h2><ul style="margin-left:20px;line-height:1.9">%s</ul></div>'
            '<div class="panel"><h2 class="t" style="font-size:20px">สินค้าใกล้หมด (10 ชิ้นหรือน้อยกว่า)</h2><ul style="margin-left:20px;line-height:1.9">%s</ul></div></div>' % (toplist, lowlist))


# ======================================================================
# ส่วนที่ 6: เซิร์ฟเวอร์
# ======================================================================
# ====================================================================
# ส่วนที่ 6.0 ตัวเซิร์ฟเวอร์
#   FastServer = เซิร์ฟเวอร์ที่รับได้หลายคำขอพร้อมกัน
#   Handler    = ตัวรับคำขอ: do_GET (ขอดูหน้า) และ do_POST (ส่งฟอร์ม) แล้วส่งต่อไปฟังก์ชันที่เกี่ยวข้อง
# ====================================================================
class FastServer(ThreadingHTTPServer):
    """เซิร์ฟเวอร์ที่ปรับให้เร็วขึ้น: daemon_threads ให้ปิดโปรแกรมได้ทันที และข้ามการหาชื่อเครื่อง (getfqdn) ที่ช้าบน Windows"""
    daemon_threads = True

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = "localhost", self.server_address[1]


# หน้าที่ไม่ต้องล็อกอิน (ที่เหลือบังคับล็อกอิน) และเส้นทางที่แอดมินใช้ได้นอกเหนือจาก /admin
PUBLIC_PATHS = {"/login", "/register", "/forgot", "/reset", "/admin/login"}
SHARED_PATHS = {"/logout", "/receipt", "/slip", "/qr", "/avatar"}


class Handler(BaseHTTPRequestHandler):
    """ตัวจัดการคำขอ: เบราว์เซอร์ส่งอะไรมา do_GET / do_POST จะถูกเรียกให้ตอบกลับ
    wbufsize = ส่งข้อมูลทีเดียวเป็นก้อน ลดอาการหน่วง"""
    wbufsize = 65536

    def log_message(self, fmt, *args):
        pass  # ปิดการพิมพ์บันทึกทุกคำขอลง Terminal เพื่อไม่ให้รก

    def send(self, code, body="", cookie=None, location=None, ctype="text/html; charset=utf-8", extra=None):
        """ส่งคำตอบกลับ: รหัสสถานะ (200 สำเร็จ, 303 ย้ายหน้า, 404 ไม่พบ) + ส่วนหัว + เนื้อหา (bytes หรือข้อความ)"""
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        if location:
            self.send_header("Location", location)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location, cookie=None):
        """สั่งให้เบราว์เซอร์ไปหน้าอื่น (303) ใช้หลังประมวลผลฟอร์มเสร็จ กันการกดรีเฟรชแล้วส่งซ้ำ"""
        self.send(303, location=location, cookie=cookie)

    def serve_file(self, folder, name, cache=300):
        """ส่งไฟล์ภาพจากโฟลเดอร์ที่กำหนด ตรวจนามสกุลที่อนุญาตและใช้ basename กันการเข้าถึงไฟล์นอกโฟลเดอร์"""
        types = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
        ext = name.rsplit(".", 1)[-1].lower()
        path = os.path.join(folder, os.path.basename(name))
        if ext not in types or not os.path.isfile(path):
            return self.send(404, "not found")
        with open(path, "rb") as f:
            data = f.read()
        self.send(200, data, ctype=types[ext], extra={"Cache-Control": "max-age=%d" % cache})

    def current_user(self, conn):
        """หาว่าใครกำลังใช้งานอยู่: อ่านคุกกี้ sid แล้วค้นในตาราง sessions ถ้าไม่เจอแปลว่ายังไม่ล็อกอิน"""
        c = SimpleCookie(self.headers.get("Cookie", ""))
        if "sid" not in c:
            return None
        return conn.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?", (c["sid"].value,)
        ).fetchone()

    def start_session(self, conn, user):
        """เริ่มการล็อกอิน: สร้างโทเคนสุ่มยาว เก็บคู่ (โทเคน, ผู้ใช้) ลงฐานข้อมูล แล้วส่งโทเคนเป็นคุกกี้ HttpOnly
        แอดมินไปหน้า Report ลูกค้าไปหน้าร้าน"""
        token = secrets.token_hex(24)
        conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user["id"]))
        conn.commit()
        self.redirect("/admin/report" if user["role"] == "admin" else "/", "sid=%s; Path=/; HttpOnly; SameSite=Lax" % token)

    def render(self, conn, user, title, body):
        """ประกอบหน้าฝั่งลูกค้า: นับจำนวนสินค้าในตะกร้าไว้แสดงที่เมนู แล้วส่งหน้าตอบกลับ"""
        n = 0
        if user:
            n = conn.execute("SELECT COALESCE(SUM(qty),0) FROM cart WHERE user_id=?", (user["id"],)).fetchone()[0]
        self.send(200, page(title, body, user, n))

    def handle_one_request(self):
        """ครอบการจัดการทุกคำขอด้วย try: ถ้าเกิดข้อผิดพลาดจะแสดงหน้าแจ้ง error แทนที่จะให้เซิร์ฟเวอร์พัง
        และพิมพ์เตือนถ้าคำขอใดใช้เวลานานเกิน 0.5 วินาที"""
        t0 = time.time()
        try:
            super().handle_one_request()
            if time.time() - t0 > 0.5 and getattr(self, "path", ""):
                print("คำขอช้า %.1f วินาที: %s" % (time.time() - t0, self.path))
        except (ConnectionError, TimeoutError):
            pass  # เบราว์เซอร์ปิดการเชื่อมต่อกลางคัน
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                self.send(500, page("Error", '<div class="empty"><h2 class="t">เกิดข้อผิดพลาด</h2><p>%s</p></div>' % escape(str(e))))
            except Exception:
                pass

    def guard(self, u, path):
        """ด่านตรวจสิทธิ์ (ใช้ทั้ง GET และ POST) คืน URL ที่ต้องเปลี่ยนไป หรือ None ถ้าผ่าน
          - ยังไม่ล็อกอิน เข้าได้เฉพาะหน้า PUBLIC_PATHS (ล็อกอิน/สมัคร/ลืมรหัส)
          - /admin/... ต้องเป็นแอดมินเท่านั้น
          - แอดมินเข้าหน้าร้านของลูกค้าไม่ได้ (ถูกส่งไปหลังบ้าน)"""
        if path in PUBLIC_PATHS:
            return None
        if not u:
            return "/admin/login?e=forbid" if path.startswith("/admin") else "/login?e=login"
        if path.startswith("/admin"):
            return None if u["role"] == "admin" else "/admin/login?e=forbid"
        if u["role"] == "admin" and path not in SHARED_PATHS:
            return "/admin/report"
        return None

    def do_GET(self):
        """do_GET = จัดการคำขอแบบ "ขอดูหน้า" (พิมพ์ URL หรือกดลิงก์) เลือกว่าจะแสดงหน้าไหนจาก url.path"""
        url = urlparse(self.path)
        q = parse_qs(url.query)
        path = url.path
        code = q.get("e", [""])[0]
        arg = lambda k, d="": q.get(k, [d])[0]
        if path == "/favicon.ico":
            return self.send(204)
        conn = db()
        try:
            u = self.current_user(conn)
            to = self.guard(u, path)
            if to:
                return self.redirect(to)
            if path in PUBLIC_PATHS and u:  # ล็อกอินอยู่แล้วไม่ต้องเห็นหน้าล็อกอินอีก
                return self.redirect("/admin/report" if u["role"] == "admin" else "/")
            if path == "/":
                self.page_shop(conn, u, q, code)
            elif path == "/profile":
                self.render(conn, u, "โปรไฟล์ของฉัน", profile_body(u, code))
            elif path == "/avatar":  # รูปโปรไฟล์ของตัวเองเท่านั้น (ไม่มีรูป = 404 แล้วหน้าเว็บแสดงปุ่มตัวอักษรแทน)
                self.serve_file(AVATAR_DIR, "%d.jpg" % u["id"], cache=0) if u["avatar"] else self.send(404, "no avatar")
            elif path == "/build":
                self.render(conn, u, "ออกแบบคีย์บอร์ด", build_body(code))
            elif path == "/qr":  # ถ้ามีไฟล์ qr.png ข้างโค้ดใช้ไฟล์นั้น ไม่มีก็ใช้รูปที่ฝังไว้ท้ายไฟล์นี้
                if qr_file():
                    self.serve_file(BASE, qr_file())
                else:
                    self.send(200, base64.b64decode(QR_B64), ctype="image/webp", extra={"Cache-Control": "max-age=300"})
            elif path == "/login":
                self.send(200, auth_page("เข้าสู่ระบบ", login_body(code)))
            elif path == "/admin/login":
                self.send(200, auth_page("แอดมิน", login_body(code, admin=True)))
            elif path == "/register":
                self.send(200, auth_page("สมัครสมาชิก", register_body(code)))
            elif path == "/forgot":
                self.send(200, auth_page("ลืมรหัสผ่าน", forgot_body(code)))
            elif path == "/reset":
                self.send(200, auth_page("ตั้งรหัสผ่านใหม่", reset_body(code)))
            elif path == "/cart":
                rows = conn.execute(
                    "SELECT p.*, c.qty, c.note FROM cart c JOIN products p ON p.id=c.product_id WHERE c.user_id=? ORDER BY p.id, c.note", (u["id"],)).fetchall()
                self.render(conn, u, "ตะกร้าสินค้า", cart_body(rows, code))
            elif path == "/pay":
                o = self.own_order(conn, u, arg("id"))
                if not o:
                    return self.redirect("/orders")
                items = conn.execute("SELECT * FROM order_items WHERE order_id=?", (o["id"],)).fetchall()
                self.render(conn, u, "ชำระเงิน", pay_body(o, items, code))
            elif path == "/orders":
                orders = conn.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (u["id"],)).fetchall()
                items = self.items_by_order(conn, "WHERE o.user_id=?", (u["id"],))
                self.render(conn, u, "คำสั่งซื้อของฉัน", orders_body(orders, items, code))
            elif path == "/receipt":
                o = self.own_order(conn, u, arg("id"))
                if not o or o["status"] != "verified":
                    return self.redirect("/orders")
                items = conn.execute("SELECT * FROM order_items WHERE order_id=?", (o["id"],)).fetchall()
                cust = conn.execute("SELECT username FROM users WHERE id=?", (o["user_id"],)).fetchone()
                self.send(200, head("ใบเสร็จ") + '<main>%s</main><script>%s</script></body></html>' % (receipt_body(o, items, cust["username"] if cust else "-"), UI_JS))
            elif path == "/slip":
                o = self.own_order(conn, u, arg("id"))
                if not o or not o["slip"]:
                    return self.send(404, "not found")
                self.serve_file(SLIP_DIR, o["slip"], cache=0)
            elif path == "/logout":
                c = SimpleCookie(self.headers.get("Cookie", ""))
                if "sid" in c:
                    conn.execute("DELETE FROM sessions WHERE token=?", (c["sid"].value,))
                    conn.commit()
                self.redirect("/login", "sid=; Path=/; Max-Age=0")
            elif path in ("/admin", "/admin/report", "/admin/report.csv"):
                self.page_report(conn, u, q, csv_mode=path.endswith(".csv"))
            elif path == "/admin/orders":
                flt = arg("s") if arg("s") in STATUS else ""
                sql = "SELECT o.*, u.username FROM orders o LEFT JOIN users u ON u.id=o.user_id %s ORDER BY o.id DESC"
                orders = conn.execute(sql % ("WHERE o.status=?" if flt else ""), (flt,) if flt else ()).fetchall()
                items = self.items_by_order(conn, "", ())
                self.send(200, admin_page("Order", "orders", "Order · คำสั่งซื้อ", admin_orders_body(orders, items, flt), u, code))
            elif path == "/admin/products":
                rows = conn.execute("SELECT * FROM products WHERE category!='custom' ORDER BY category, id").fetchall()
                self.send(200, admin_page("Product", "products", "Product · สินค้าและสต็อก", admin_products_body(rows), u, code))
            elif path == "/admin/profile":
                self.send(200, admin_page("Profile", "profile", "Profile · โปรไฟล์แอดมิน", profile_body(u, ""), u, code))
            elif path == "/admin/dashboard":
                self.page_dashboard(conn, u, code, q)
            else:
                self.send(404, page("404", '<div class="empty"><h2 class="t">404 ไม่พบหน้านี้</h2></div>'))
        finally:
            conn.close()

    # ---------- ตัวช่วยของ do_GET ----------
    def own_order(self, conn, u, oid):
        """ดึงคำสั่งซื้อ: ลูกค้าเห็นได้เฉพาะของตัวเอง แอดมินเห็นได้ทุกใบ (ใช้กับหน้าชำระ ใบเสร็จ สลิป)"""
        try:
            oid = int(oid)
        except (TypeError, ValueError):
            return None
        if u["role"] == "admin":
            return conn.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
        return conn.execute("SELECT * FROM orders WHERE id=? AND user_id=?", (oid, u["id"])).fetchone()

    def items_by_order(self, conn, where, params):
        """ดึงรายการสินค้าของหลายคำสั่งซื้อทีเดียว แล้วจัดกลุ่มเป็น {เลขคำสั่งซื้อ: [รายการ...]}"""
        out = {}
        for i in conn.execute("SELECT oi.* FROM order_items oi JOIN orders o ON o.id=oi.order_id " + where, params):
            out.setdefault(i["order_id"], []).append(i)
        return out

    def page_shop(self, conn, u, q, code):
        """หน้าแรก: อ่านหมวด คำค้น และวิธีเรียงจาก URL แล้วดึงสินค้าจากฐานข้อมูล
        ค้นหา = เก็บเฉพาะสินค้าที่ชื่อหรือคำอธิบายมีคำค้น (ไม่สนตัวพิมพ์) | เรียง asc = ต่ำไปสูง, desc = สูงไปต่ำ"""
        cat = q.get("cat", ["all"])[0]
        if cat != "all" and cat not in CAT_INFO:
            cat = "all"
        if cat == "all":
            rows = conn.execute("SELECT * FROM products WHERE category!='custom' ORDER BY id").fetchall()
        else:
            rows = conn.execute("SELECT * FROM products WHERE category=? ORDER BY id", (cat,)).fetchall()
        qs = q.get("q", [""])[0].strip()[:40]
        sort = q.get("sort", [""])[0]
        if qs:
            rows = [r for r in rows if qs.lower() in (r["name"] + r["description"]).lower()]
        if sort == "asc":
            rows = sorted(rows, key=lambda r: r["price"])
        elif sort == "desc":
            rows = sorted(rows, key=lambda r: -r["price"])
        self.render(conn, u, SHOP_NAME + " - ร้านคลิกเกอร์ลายตุ๊กตา", shop_body(rows, cat, code, qs, sort))

    def page_report(self, conn, u, q, csv_mode=False):
        """Report: รายงานยอดขายแบบสมบูรณ์ (นับเฉพาะบิลที่แอดมินยืนยันชำระแล้ว)
        q["v"]  = bill (รายบิล) | day | month | year | product (ตามสินค้า)   q["from"], q["to"] = ช่วงวันที่ YYYY-MM-DD (ค่าเริ่มต้น 30 วันล่าสุด)
        แสดงการ์ดสรุป (ยอดรวม จำนวนบิล เฉลี่ยต่อบิล VAT จำนวนชิ้น) + ตารางตามมุมมองที่เลือก และส่งออก CSV ตามมุมมองเดียวกันได้
        CSV ใส่ BOM ให้ Excel อ่านภาษาไทยไม่เพี้ยน และกัน CSV injection"""
        today = datetime.date.today()
        view = q.get("v", ["bill"])[0]
        view = view if view in ("bill", "day", "month", "year", "product") else "bill"
        def pick(key, fallback):
            try:
                return datetime.datetime.strptime(q.get(key, [""])[0], "%Y-%m-%d").date()
            except ValueError:
                return fallback
        d1, d2 = pick("from", today - datetime.timedelta(days=29)), pick("to", today)
        if d1 > d2:
            d1, d2 = d2, d1
        rng = (time.mktime(d1.timetuple()), time.mktime((d2 + datetime.timedelta(days=1)).timetuple()))
        where = "o.status='verified' AND o.created>=? AND o.created<?"
        bills = conn.execute("SELECT o.*, u.username FROM orders o LEFT JOIN users u ON u.id=o.user_id WHERE " + where + " ORDER BY o.created DESC", rng).fetchall()
        items = conn.execute("SELECT COALESCE(SUM(oi.qty),0) FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE " + where, rng).fetchone()[0]
        total = sum(r["total"] for r in bills)
        sm = {"total": total, "bills": len(bills), "avg": total / len(bills) if bills else 0,
              "vat": sum(r["vat"] for r in bills), "sub": sum(r["subtotal"] for r in bills), "items": items}
        if view in ("day", "month", "year"):  # รวมตามช่วงเวลา: key = วัน/เดือน/ปี ของเวลาท้องถิ่น
            fmt = {"day": "%Y-%m-%d", "month": "%Y-%m", "year": "%Y"}[view]
            table = conn.execute("SELECT strftime(?, o.created, 'unixepoch', 'localtime') k, COUNT(*) n, SUM(o.subtotal) sub, SUM(o.vat) vat, SUM(o.total) total "
                                 "FROM orders o WHERE " + where + " GROUP BY k ORDER BY k DESC", (fmt,) + rng).fetchall()
        elif view == "product":  # รวมตามสินค้า (ชื่อสินค้าตอนซื้อ รวมตัวอักษรบนพวงกุญแจชื่อ)
            table = conn.execute("SELECT oi.product_name k, SUM(oi.qty) n, SUM(oi.price*oi.qty) total FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE "
                                 + where + " GROUP BY oi.product_name ORDER BY total DESC", rng).fetchall()
        else:
            table = bills
        if not csv_mode:
            return self.send(200, admin_page("Report", "report", "Report · รายงานยอดขาย", report_body(table, view, d1, d2, sm), u))
        out = io.StringIO()
        w = csv.writer(out)
        safe = lambda v: ("'" + v) if v[:1] in "=+-@" else v
        if view == "bill":
            w.writerow(["เลขที่บิล", "วันที่ขาย", "ลูกค้า", "ราคาสินค้า", "VAT", "ยอดเงิน (บาท)"])
            for r in table:
                w.writerow([safe(r["bill_no"]), be_date(r["created"]), safe(r["username"] or "-"), "%.2f" % r["subtotal"], "%.2f" % r["vat"], "%.2f" % r["total"]])
            w.writerow(["", "", "รวม", "%.2f" % sm["sub"], "%.2f" % sm["vat"], "%.2f" % total])
        elif view == "product":
            w.writerow(["สินค้า", "จำนวนที่ขาย (ชิ้น)", "ยอดขาย (บาท)"])
            for r in table:
                w.writerow([safe(r["k"]), r["n"], "%.2f" % r["total"]])
            w.writerow(["รวม", items, "%.2f" % sm["sub"]])
        else:
            w.writerow([{"day": "วันที่", "month": "เดือน", "year": "ปี"}[view], "จำนวนบิล", "ราคาสินค้า", "VAT", "ยอดเงิน (บาท)"])
            for r in table:
                w.writerow([period_label(r["k"], view), r["n"], "%.2f" % r["sub"], "%.2f" % r["vat"], "%.2f" % r["total"]])
            w.writerow(["รวม", sm["bills"], "%.2f" % sm["sub"], "%.2f" % sm["vat"], "%.2f" % total])
        self.send(200, "\ufeff" + out.getvalue(), ctype="text/csv; charset=utf-8",
                  extra={"Content-Disposition": 'attachment; filename="report_%s_%s_%s.csv"' % (view, d1, d2)})

    def page_dashboard(self, conn, u, code, q):
        """Dashboard: เลือกดูแบบ รายวัน / รายเดือน / รายปี และเลือกช่วงวันที่ (จาก-ถึง) ได้
        q["v"] = day | month | year   q["from"], q["to"] = วันที่รูปแบบ YYYY-MM-DD (ค่าเริ่มต้นขึ้นกับแบบที่เลือก)
        ตัวเลขยอดขาย กราฟ และสินค้าขายดี คิดเฉพาะบิลที่ยืนยันแล้วในช่วงที่เลือก ส่วนบิลรอตรวจ/รอชำระ/สมาชิก/สต็อกคือค่าปัจจุบัน"""
        one = lambda sql, p=(): conn.execute(sql, p).fetchone()[0]
        view = q.get("v", ["day"])[0]
        view = view if view in ("day", "month", "year") else "day"
        today = datetime.date.today()
        # ช่วงเริ่มต้น: รายวัน = 7 วันล่าสุด | รายเดือน = 12 เดือนล่าสุด | รายปี = 5 ปีล่าสุด
        dflt = {"day": today - datetime.timedelta(days=6), "month": datetime.date(today.year - 1, today.month, 1) if today.month < 12 else datetime.date(today.year, 1, 1),
                "year": datetime.date(today.year - 4, 1, 1)}[view]
        def pick(key, fallback):
            try:
                return datetime.datetime.strptime(q.get(key, [""])[0], "%Y-%m-%d").date()
            except ValueError:
                return fallback
        d1, d2 = pick("from", dflt), pick("to", today)
        if d1 > d2:
            d1, d2 = d2, d1
        limit = {"day": 366, "month": 3660, "year": 36600}[view]  # กันช่วงยาวเกินจนกราฟแน่น (ตัดเหลือช่วงท้ายสุด)
        if (d2 - d1).days > limit:
            d1 = d2 - datetime.timedelta(days=limit)
        t1 = time.mktime(d1.timetuple())
        t2 = time.mktime((d2 + datetime.timedelta(days=1)).timetuple())
        rng = (t1, t2)
        st = {"sales": one("SELECT COALESCE(SUM(total),0) FROM orders WHERE status='verified' AND created>=? AND created<?", rng),
              "verified": one("SELECT COUNT(*) FROM orders WHERE status='verified' AND created>=? AND created<?", rng),
              "paid": one("SELECT COUNT(*) FROM orders WHERE status='paid'"),
              "awaiting": one("SELECT COUNT(*) FROM orders WHERE status='awaiting'"),
              "users": one("SELECT COUNT(*) FROM users WHERE role='user'")}
        top = conn.execute("SELECT oi.product_name, SUM(oi.qty) q, SUM(oi.price*oi.qty) rev FROM order_items oi JOIN orders o ON o.id=oi.order_id "
                           "WHERE o.status='verified' AND o.created>=? AND o.created<? GROUP BY oi.product_name ORDER BY q DESC LIMIT 5", rng).fetchall()
        low = conn.execute("SELECT name, stock FROM products WHERE category!='custom' AND stock<=10 ORDER BY stock LIMIT 10").fetchall()
        # รวมยอดตามช่วงเวลาที่เลือก: key คือ วัน(YYYY-MM-DD) / เดือน(YYYY-MM) / ปี(YYYY) ของเวลาท้องถิ่น
        fmt = {"day": "%Y-%m-%d", "month": "%Y-%m", "year": "%Y"}[view]
        sums = {r[0]: r[1] for r in conn.execute(
            "SELECT strftime(?, created, 'unixepoch', 'localtime') k, SUM(total) FROM orders WHERE status='verified' AND created>=? AND created<? GROUP BY k",
            (fmt,) + rng)}
        keys, cur = [], d1
        while cur <= d2:  # สร้างแท่งให้ครบทุกช่วง (ช่วงที่ไม่มียอดแสดงเป็น 0)
            k = cur.strftime(fmt)
            if not keys or keys[-1] != k:
                keys.append(k)
            cur = cur + datetime.timedelta(days=1)
        def label(k):
            p = k.split("-")
            if view == "day":
                return "%s/%s" % (p[2], p[1])
            if view == "month":
                return "%s/%d" % (p[1], int(p[0]) + 543)
            return str(int(p[0]) + 543)  # รายปี แสดงเป็น พ.ศ.
        series = [(label(k), sums.get(k, 0)) for k in keys]
        self.send(200, admin_page("Dashboard", "dashboard", "Dashboard · ภาพรวมร้าน", dashboard_body(st, top, low, series, view, d1, d2), u, code))

    def do_POST(self):
        """do_POST = จัดการคำขอแบบ "ส่งข้อมูลฟอร์ม" (ล็อกอิน สมัคร ใส่ตะกร้า สั่งซื้อ จัดการหลังบ้าน)
        อ่านข้อมูลฟอร์ม: ความยาวอยู่ในส่วนหัว Content-Length แล้วแยกเป็นคู่ ชื่อ=ค่า (จำกัดไม่เกิน 4MB)"""
        url = urlparse(self.path)
        path = url.path
        length = int(self.headers.get("Content-Length", 0))
        if length > 4_000_000:
            return self.send(413, "too large")
        f = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
        get = lambda k: f.get(k, [""])[0].strip()
        conn = db()
        try:
            u = self.current_user(conn)
            to = self.guard(u, path)
            if to:
                return self.redirect(to)
            if path == "/login":
                self.do_login(conn, get, f, admin=False)
            elif path == "/admin/login":
                self.do_login(conn, get, f, admin=True)
            elif path == "/register":
                self.do_register(conn, get, f)
            elif path == "/forgot":
                self.do_forgot(conn, get)
            elif path == "/reset":
                self.do_reset(conn, get, f)
            elif path == "/build/add":
                self.build_add(conn, u, get)
            elif path.startswith("/profile/"):
                self.profile_action(conn, u, path, get)
            elif path in ("/cart/add", "/cart/update", "/cart/set", "/cart/remove"):
                self.cart_action(conn, u, path, get)
            elif path == "/checkout":
                self.do_checkout(conn, u, get)
            elif path == "/pay":
                self.do_pay(conn, u, get)
            elif path == "/order/cancel":
                o = self.own_order(conn, u, get("id"))
                if o and o["status"] == "awaiting":
                    self.cancel_order(conn, o)
                self.redirect("/orders?e=cancelled")
            elif path.startswith("/admin/"):
                self.admin_action(conn, u, path, get)
            else:
                self.send(404, page("404", '<div class="empty"><h2 class="t">404</h2></div>'))
        finally:
            conn.close()

    # ---------- โปรไฟล์ (รูปโปรไฟล์ + ชื่อเล่น) ----------
    def profile_action(self, conn, u, path, get):
        """/profile/avatar = บันทึกรูปโปรไฟล์ (หน้าเว็บย่อเป็น JPEG 256x256 แล้วส่งมาเป็นข้อความ data:image/jpeg;base64,...)
        ตรวจว่าเป็น JPEG จริง (ไบต์แรก FF D8 FF) และไม่ใหญ่เกินกำหนด แล้วเซฟเป็น avatars/<เลขผู้ใช้>.jpg ทับของเดิม
        /profile/avatar/remove = ลบรูป | /profile/nickname = เปลี่ยนชื่อเล่น (1-20 ตัวอักษร)
        /profile/password = เปลี่ยนรหัสผ่าน (ต้องใส่รหัสเดิมถูก)"""
        base = "/admin/profile" if u["role"] == "admin" else "/profile"  # กลับไปหน้าโปรไฟล์ของตัวเอง
        if path == "/profile/avatar":
            s, prefix = get("avatar"), "data:image/jpeg;base64,"
            try:
                raw = base64.b64decode(s[len(prefix):], validate=True) if s.startswith(prefix) else b""
            except ValueError:
                raw = b""
            if not raw or len(raw) > AVATAR_MAX_BYTES or raw[:3] != b"\xff\xd8\xff":
                return self.redirect(base + "?e=badimg")
            os.makedirs(AVATAR_DIR, exist_ok=True)
            with open(os.path.join(AVATAR_DIR, "%d.jpg" % u["id"]), "wb") as fh:
                fh.write(raw)
            conn.execute("UPDATE users SET avatar=? WHERE id=?", (int(time.time()), u["id"]))
        elif path == "/profile/avatar/remove":
            try:
                os.remove(os.path.join(AVATAR_DIR, "%d.jpg" % u["id"]))
            except OSError:
                pass
            conn.execute("UPDATE users SET avatar=0 WHERE id=?", (u["id"],))
        elif path == "/profile/password":  # เปลี่ยนรหัสผ่าน: ต้องใส่รหัสเดิมให้ถูก + รหัสใหม่ 6 ตัวขึ้นไป + ยืนยันตรงกัน
            new = get("password")
            if not check_pw(get("current"), u["password"]):
                return self.redirect(base + "?e=wrongpw")
            if len(new) < 6:
                return self.redirect(base + "?e=short")
            if new != get("confirm"):
                return self.redirect(base + "?e=mismatch")
            conn.execute("UPDATE users SET password=?, password_plain=? WHERE id=?", (hash_pw(new), plain_pw(new), u["id"]))
            keep = SimpleCookie(self.headers.get("Cookie", ""))["sid"].value  # เครื่องนี้ล็อกอินต่อ ส่วนเครื่องอื่นถูกเตะออก
            conn.execute("DELETE FROM sessions WHERE user_id=? AND token<>?", (u["id"], keep))
            conn.commit()
            return self.redirect(base + "?e=pwchanged")
        elif path == "/profile/nickname":
            if not 1 <= len(get("nickname")) <= 20:
                return self.redirect(base + "?e=badnick")
            conn.execute("UPDATE users SET nickname=? WHERE id=?", (get("nickname"), u["id"]))
        conn.commit()
        self.redirect(base + "?e=saved")

    # ---------- บัญชีผู้ใช้ ----------
    def do_login(self, conn, get, f, admin):
        """ล็อกอิน: ค้นผู้ใช้จากชื่อ แล้วตรวจรหัสผ่านด้วย check_pw ถ้าถูกต้องเริ่ม session
        แยกทางเข้า: หน้า /login รับเฉพาะลูกค้า หน้า /admin/login รับเฉพาะแอดมิน"""
        base = "/admin/login" if admin else "/login"
        row = conn.execute("SELECT * FROM users WHERE username=?", (get("username"),)).fetchone()
        if not (row and check_pw(f.get("password", [""])[0], row["password"])):
            return self.redirect(base + "?e=bad")
        if admin and row["role"] != "admin":
            return self.redirect(base + "?e=notadmin")
        if not admin and row["role"] == "admin":
            return self.redirect(base + "?e=isadmin")
        self.start_session(conn, row)

    def do_register(self, conn, get, f):
        """สมัครสมาชิก: ตรวจทีละเงื่อนไข (กรอกครบ ชื่อถูกรูปแบบ อีเมลถูกรูปแบบ รหัสยาวพอและตรงกัน) แล้วจึงบันทึก
        ลูกค้าที่สมัครเองได้ role = user เสมอ (แอดมินสร้างจากโค้ดเท่านั้น)"""
        name, mail = get("username"), get("email").lower()
        pw, cf = f.get("password", [""])[0], f.get("confirm", [""])[0]
        if not (name and mail and pw):
            return self.redirect("/register?e=empty")
        if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", name):
            return self.redirect("/register?e=name")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", mail) or len(mail) > 80:
            return self.redirect("/register?e=mail")
        if len(pw) < 6:
            return self.redirect("/register?e=short")
        if pw != cf:
            return self.redirect("/register?e=mismatch")
        if conn.execute("SELECT 1 FROM users WHERE email=?", (mail,)).fetchone():
            return self.redirect("/register?e=dupmail")
        try:
            conn.execute("INSERT INTO users (username,password,created,email,role,password_plain) VALUES (?,?,?,?,'user',?)", (name, hash_pw(pw), time.time(), mail, plain_pw(pw)))
            conn.commit()
        except sqlite3.IntegrityError:  # ชื่อซ้ำ (คอลัมน์ username เป็น UNIQUE)
            return self.redirect("/register?e=dup")
        self.redirect("/login?e=regok")

    def do_forgot(self, conn, get):
        """ลืมรหัสผ่าน ขั้นที่ 1: ถ้าอีเมลมีในระบบ สร้างรหัส 6 หลักอายุ 15 นาที
        ตอนนี้ยังไม่ได้ต่อระบบส่งอีเมลจริง จึงพิมพ์รหัสลง Terminal แทน (ตอบข้อความเดียวกันเสมอ กันคนเดาว่าอีเมลไหนสมัครไว้)"""
        mail = get("email").lower()
        if conn.execute("SELECT 1 FROM users WHERE email=?", (mail,)).fetchone():
            code = "%06d" % secrets.randbelow(1000000)
            conn.execute("INSERT OR REPLACE INTO resets (email, code, expires) VALUES (?,?,?)", (mail, code, time.time() + 900))
            conn.commit()
            print("รหัสรีเซ็ตรหัสผ่านของ %s คือ %s (หมดอายุใน 15 นาที)" % (mail, code))
        self.redirect("/reset?e=sent")

    def do_reset(self, conn, get, f):
        """ลืมรหัสผ่าน ขั้นที่ 2: ตรวจอีเมล+รหัส 6 หลักที่ยังไม่หมดอายุ แล้วตั้งรหัสผ่านใหม่ (ใช้รหัสได้ครั้งเดียว และล้าง session เก่า)"""
        mail, code = get("email").lower(), get("code")
        pw, cf = f.get("password", [""])[0], f.get("confirm", [""])[0]
        if len(pw) < 6:
            return self.redirect("/reset?e=short")
        if pw != cf:
            return self.redirect("/reset?e=mismatch")
        r = conn.execute("SELECT * FROM resets WHERE email=?", (mail,)).fetchone()
        if not (r and secrets.compare_digest(r["code"], code) and r["expires"] > time.time()):
            return self.redirect("/reset?e=badcode")
        conn.execute("UPDATE users SET password=?, password_plain=? WHERE email=?", (hash_pw(pw), plain_pw(pw), mail))
        conn.execute("DELETE FROM resets WHERE email=?", (mail,))
        conn.execute("DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE email=?)", (mail,))
        conn.commit()
        self.redirect("/login?e=resetok")

    # ---------- ตะกร้า / สั่งซื้อ / ชำระเงิน ----------
    def build_add(self, conn, u, get):
        """รับรายการปุ่มที่ผู้ใช้เลือกในหน้าออกแบบ ตรวจความถูกต้อง คิดราคา แล้วสร้างเป็น "สินค้าพิเศษ" 1 ชิ้นใส่ตะกร้า
        กรองรหัสปุ่มให้เหลือเฉพาะที่มีจริงใน KEYS และไม่ซ้ำ (กันข้อมูลปลอม)"""
        ids = []
        for x in get("keys").split(","):
            if x in KEYS and x not in ids:
                ids.append(x)
        if not ids:
            return self.redirect("/build?e=none")
        base = get("base") if get("base") in BASES else "white"
        snd = get("snd") if get("snd") in dict(SOUND_OPTS) else "blue"
        hexc = THEMES.get(get("color"), THEMES["pink"])
        price = BASES[base][1] + sum(KEYS[i][1] for i in ids)  # คิดราคาใหม่ที่ฝั่งเซิร์ฟเวอร์เสมอ = ราคาฐาน + ราคาทุกปุ่ม
        first = ids[0]
        m = first if (first in EMOJI) else "t:" + KEYS[first][0]
        desc = "ฐาน%s · เสียง %s · ปุ่ม: %s" % (BASES[base][0], snd, " ".join(KEYS[i][0] for i in ids))
        cur = conn.execute(
            "INSERT INTO products (name, category, price, stock, description, look) VALUES (?,?,?,?,?,?)",
            ("Custom Keyboard Clicker %d ปุ่ม" % len(ids), "custom", price, 1, desc, "1|1|white|%s|%s|%s" % (snd, m, hexc)),
        )
        conn.execute("INSERT INTO cart (user_id, product_id, qty) VALUES (?,?,1)", (u["id"], cur.lastrowid))
        conn.commit()
        self.redirect("/cart")

    def cart_action(self, conn, u, path, get):
        """จัดการตะกร้าตาม path: /cart/add เพิ่มตามจำนวนที่พิมพ์, /cart/update เพิ่ม-ลดทีละ 1, /cart/set พิมพ์จำนวนเอง, /cart/remove ลบ
        หนึ่งแถวในตะกร้า = สินค้า 1 ชนิด + ตัวอักษร (note) พวงกุญแจชื่อที่พิมพ์ชื่อต่างกันจึงเป็นคนละแถว
        ชุดที่ออกแบบเอง (category custom) จะถูกลบทิ้งจากตารางสินค้าเมื่อออกจากตะกร้า ไม่ให้ขยะสะสม"""
        try:
            pid = int(get("product_id") or 0)
        except ValueError:
            pid = 0
        prod = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        note = get("note").upper()

        def drop_custom():
            conn.execute("DELETE FROM products WHERE id=? AND category='custom' AND NOT EXISTS (SELECT 1 FROM cart WHERE product_id=?)", (pid, pid))
        if path == "/cart/add" and prod and prod["stock"] <= 0:
            return self.redirect("/?e=soldout")
        if path == "/cart/add" and prod and prod["stock"] > 0:
            if prod["category"] == "name":  # พวงกุญแจชื่อ: ต้องพิมพ์ A-Z / 0-9 ไม่เกินจำนวนปุ่มของสินค้านั้น
                cols, rows_ = prod["look"].split("|")[:2]
                if not re.fullmatch(r"[A-Z0-9]{1,%d}" % (int(cols) * int(rows_)), note):
                    return self.redirect("/?cat=name&e=badname")
            else:
                note = ""
            # ใส่ตะกร้า: เพิ่มตามจำนวนที่พิมพ์ (ค่าเริ่มต้น 1) แต่รวมแล้วต้องไม่เกินสต็อก ถ้าเกินจะใส่เท่าที่เหลือและแจ้งเตือน (e=limit)
            try:
                want = max(1, int(get("qty") or 1))
            except ValueError:
                want = 1
            have = conn.execute("SELECT COALESCE(SUM(qty),0) FROM cart WHERE user_id=? AND product_id=?", (u["id"], pid)).fetchone()[0]
            add = min(want, max(0, prod["stock"] - have))
            if add > 0:
                conn.execute("INSERT INTO cart (user_id, product_id, note, qty) VALUES (?,?,?,?) "
                             "ON CONFLICT(user_id, product_id, note) DO UPDATE SET qty=qty+?", (u["id"], pid, note, add, add))
                conn.commit()
            nxt = get("next")
            if add < want or get("over") == "1":  # over=1: หน้าเว็บตัดค่าที่เกินสต็อกให้แล้ว ยังต้องแจ้งเตือน
                nxt = nxt.replace("e=added", "e=limit")
            return self.redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else "/")
        if path == "/cart/update" and prod:
            row = conn.execute("SELECT qty FROM cart WHERE user_id=? AND product_id=? AND note=?", (u["id"], pid, note)).fetchone()
            if row:
                new = row["qty"] + (1 if get("delta") == "1" else -1)
                if new <= 0:
                    conn.execute("DELETE FROM cart WHERE user_id=? AND product_id=? AND note=?", (u["id"], pid, note))
                    drop_custom()
                else:
                    other = conn.execute("SELECT COALESCE(SUM(qty),0) FROM cart WHERE user_id=? AND product_id=? AND note<>?", (u["id"], pid, note)).fetchone()[0]
                    top = max(0, prod["stock"] - other)
                    conn.execute("UPDATE cart SET qty=? WHERE user_id=? AND product_id=? AND note=?", (min(new, top), u["id"], pid, note))
                    if new > top:
                        conn.commit()
                        return self.redirect("/cart?e=limit")
                conn.commit()
            return self.redirect("/cart")
        if path == "/cart/set" and prod:  # พิมพ์จำนวนเองในหน้าตะกร้า: 0 หรือน้อยกว่า = ลบ, เกินสต็อก = ปรับเป็นจำนวนสูงสุดแล้วแจ้งเตือน
            try:
                want = int(get("qty"))
            except ValueError:
                return self.redirect("/cart")
            if want <= 0:
                conn.execute("DELETE FROM cart WHERE user_id=? AND product_id=? AND note=?", (u["id"], pid, note))
                drop_custom()
                conn.commit()
                return self.redirect("/cart")
            other = conn.execute("SELECT COALESCE(SUM(qty),0) FROM cart WHERE user_id=? AND product_id=? AND note<>?", (u["id"], pid, note)).fetchone()[0]
            top = max(0, prod["stock"] - other)
            if top == 0:
                conn.execute("DELETE FROM cart WHERE user_id=? AND product_id=? AND note=?", (u["id"], pid, note))
                conn.commit()
                return self.redirect("/cart?e=stock")
            conn.execute("UPDATE cart SET qty=? WHERE user_id=? AND product_id=? AND note=?", (min(want, top), u["id"], pid, note))
            conn.commit()
            return self.redirect("/cart?e=limit" if want > top or get("over") == "1" else "/cart")  # over=1: หน้าเว็บตัดค่าที่เกินให้แล้ว แต่ยังต้องแจ้งเตือน
        if path == "/cart/remove":
            conn.execute("DELETE FROM cart WHERE user_id=? AND product_id=? AND note=?", (u["id"], pid, note))
            drop_custom()
            conn.commit()
            return self.redirect("/cart")
        self.redirect("/")

    def do_checkout(self, conn, u, get):
        """กด "ไปหน้าชำระเงิน": สร้างคำสั่งซื้อสถานะ awaiting และ "ตัดสต็อกทันที" ในทรานแซกชันเดียว
        (สำเร็จครบทุกขั้นหรือยกเลิกทั้งหมด) ราคา ภาษี ยอดรวม คิดจากฐานข้อมูลที่ฝั่งเซิร์ฟเวอร์
        ตัดสต็อกด้วย UPDATE ... WHERE stock>=จำนวน ถ้าไม่พอ rowcount=0 แล้ว rollback ทั้งหมด"""
        name, phone, addr = get("name"), get("phone"), get("address")
        if not (name and addr and phone.isdigit() and 9 <= len(phone) <= 12):
            return self.redirect("/cart?e=info")
        try:
            conn.execute("BEGIN IMMEDIATE")  # ล็อกฐานข้อมูลตั้งแต่ต้น กันสองคนซื้อชิ้นสุดท้ายพร้อมกัน
            rows = conn.execute("SELECT p.*, c.qty, c.note FROM cart c JOIN products p ON p.id=c.product_id WHERE c.user_id=?", (u["id"],)).fetchall()
            if not rows:
                conn.rollback()
                return self.redirect("/cart")
            for r in rows:
                cur = conn.execute("UPDATE products SET stock=stock-? WHERE id=? AND stock>=?", (r["qty"], r["id"], r["qty"]))
                if cur.rowcount == 0:
                    conn.rollback()
                    return self.redirect("/cart?e=stock")
            sub = sum(r["price"] * r["qty"] for r in rows)
            vat, total = calc_total(sub)
            cur = conn.execute(
                "INSERT INTO orders (user_id,name,phone,address,total,created,bill_no,subtotal,vat,status) VALUES (?,?,?,?,?,?,?,?,?,'awaiting')",
                (u["id"], name, phone, addr, total, time.time(), make_bill_no(conn), sub, vat))
            oid = cur.lastrowid
            for r in rows:
                conn.execute("INSERT INTO order_items (order_id,product_name,price,qty,product_id) VALUES (?,?,?,?,?)",
                             (oid, r["name"] + (" [ชื่อ: %s]" % r["note"] if r["note"] else ""), r["price"], r["qty"], r["id"]))  # ตัวอักษรที่เลือกต่อท้ายชื่อสินค้าในบิล
            conn.execute("DELETE FROM cart WHERE user_id=?", (u["id"],))
            conn.execute("DELETE FROM products WHERE category='custom' AND stock<=0 AND id NOT IN (SELECT product_id FROM cart)")
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            return self.redirect("/cart?e=stock")
        self.redirect("/pay?id=%d" % oid)

    def do_pay(self, conn, u, get):
        """กด "ยืนยันการชำระเงิน": รับสลิปที่หน้าเว็บย่อมาแล้ว (ข้อความ data:image/jpeg;base64,...)
        ตรวจว่าเป็น JPEG จริง (ไบต์แรก FF D8 FF) และไม่ใหญ่เกินกำหนด แล้วบันทึกเป็นไฟล์ slips/<เลขคำสั่งซื้อ>.jpg
        เปลี่ยนสถานะเป็น paid (รอแอดมินตรวจ)"""
        o = self.own_order(conn, u, get("id"))
        if not o or o["status"] != "awaiting":
            return self.redirect("/orders")
        s = get("slip")
        prefix = "data:image/jpeg;base64,"
        try:
            raw = base64.b64decode(s[len(prefix):], validate=True) if s.startswith(prefix) else b""
        except ValueError:
            raw = b""
        if not raw or len(raw) > SLIP_MAX_BYTES or raw[:3] != b"\xff\xd8\xff":
            return self.redirect("/pay?id=%d&e=noslip" % o["id"])
        os.makedirs(SLIP_DIR, exist_ok=True)
        fname = "%d.jpg" % o["id"]
        with open(os.path.join(SLIP_DIR, fname), "wb") as fh:
            fh.write(raw)
        conn.execute("UPDATE orders SET slip=?, status='paid' WHERE id=?", (fname, o["id"]))
        conn.commit()
        self.redirect("/pay?id=%d&e=paid" % o["id"])

    def cancel_order(self, conn, o):
        """ยกเลิกคำสั่งซื้อ: เปลี่ยนสถานะเป็น cancelled และ "คืนสต็อก" ให้สินค้าทุกรายการในบิลนั้น
        (ทำเฉพาะบิลที่ยังไม่ยกเลิก กันคืนซ้ำ)"""
        if o["status"] == "cancelled":
            return
        conn.execute("UPDATE orders SET status='cancelled' WHERE id=?", (o["id"],))
        for i in conn.execute("SELECT product_id, qty FROM order_items WHERE order_id=?", (o["id"],)).fetchall():
            conn.execute("UPDATE products SET stock=stock+? WHERE id=?", (i["qty"], i["product_id"]))
        conn.commit()

    # ---------- หลังบ้านแอดมิน ----------
    def admin_action(self, conn, u, path, get):
        """การกระทำของแอดมิน (ผ่านด่าน guard มาแล้วว่าเป็นแอดมินจริง)
          /admin/order/verify  ยืนยันการชำระเงิน บันทึกว่าใครยืนยันและเมื่อไร
          /admin/order/cancel  ยกเลิกบิลที่ยังไม่ชำระ และคืนสต็อก
          /admin/product/add | save | delete  จัดการสินค้า
          /admin/qr | /admin/qr/reset  เปลี่ยน/รีเซ็ตรูป QR รับเงิน"""
        def num(k, lo, hi):
            try:
                v = int(get(k))
            except ValueError:
                return None
            return v if lo <= v <= hi else None
        if path.startswith("/admin/profile/"):  # โปรไฟล์ของแอดมิน: ใช้ฟังก์ชันเดียวกับลูกค้า (ตัด /admin ออกจาก path)
            return self.profile_action(conn, u, path[6:], get)
        if path in ("/admin/qr", "/admin/qr/reset"):  # แอดมินเปลี่ยน/รีเซ็ตรูป QR รับเงิน
            target = os.path.join(BASE, QR_UPLOAD)
            if path.endswith("reset"):
                if os.path.isfile(target):
                    os.remove(target)
                return self.redirect("/admin/products?e=saved")
            s, prefix = get("qr"), "data:image/jpeg;base64,"
            try:
                raw = base64.b64decode(s[len(prefix):], validate=True) if s.startswith(prefix) else b""
            except ValueError:
                raw = b""
            if not raw or len(raw) > 2_000_000 or raw[:3] != b"\xff\xd8\xff":
                return self.redirect("/admin/products?e=badimg")
            with open(target, "wb") as fh:
                fh.write(raw)
            return self.redirect("/admin/products?e=saved")
        if path in ("/admin/order/verify", "/admin/order/cancel"):
            o = conn.execute("SELECT * FROM orders WHERE id=?", (num("id", 1, 10**9) or 0,)).fetchone()
            if o and path.endswith("verify") and o["status"] in ("awaiting", "paid"):
                conn.execute("UPDATE orders SET status='verified', verified_by=?, verified_at=? WHERE id=?", (u["username"], time.time(), o["id"]))
                conn.commit()
                return self.redirect("/admin/orders?e=verified")
            if o and path.endswith("cancel") and o["status"] in ("awaiting", "paid"):
                self.cancel_order(conn, o)
                return self.redirect("/admin/orders?e=cancelled")
            return self.redirect("/admin/orders")
        if path == "/admin/product/delete":
            pid = num("id", 1, 10**9)
            if pid:
                conn.execute("DELETE FROM cart WHERE product_id=?", (pid,))
                conn.execute("DELETE FROM products WHERE id=?", (pid,))
                conn.commit()
            return self.redirect("/admin/products?e=deleted")
        if path == "/admin/product/save":
            pid, price, stock = num("id", 1, 10**9), num("price", 1, 1000000), num("stock", 0, 100000)
            if not (pid and price and stock is not None and get("name")):
                return self.redirect("/admin/products?e=badval")
            conn.execute("UPDATE products SET name=?, price=?, stock=?, description=? WHERE id=?", (get("name")[:80], price, stock, get("description")[:200], pid))
            conn.commit()
            return self.redirect("/admin/products?e=saved")
        if path == "/admin/product/add":
            price, stock, cols, rows_ = num("price", 1, 1000000), num("stock", 0, 100000), num("cols", 1, 6), num("rows", 1, 4)
            motif, snd, color, cat = get("motif"), get("snd"), get("color"), get("category")
            if not (price and stock is not None and cols and rows_ and get("name") and get("description")
                    and motif in EMOJI and snd in SOUND_NAMES and re.fullmatch(r"#[0-9a-fA-F]{6}", color) and cat in CAT_INFO):
                return self.redirect("/admin/products?e=badval")
            look = "%d|%d|white|%s|%s|%s" % (cols, rows_, snd, motif, color)  # สูตรวาดภาพสินค้า (ดูคำอธิบาย SEED ด้านบน)
            conn.execute("INSERT INTO products (name,category,price,stock,description,look) VALUES (?,?,?,?,?,?)",
                         (get("name")[:80], cat, price, stock, get("description")[:200], look))
            conn.commit()
            return self.redirect("/admin/products?e=saved")
        self.redirect("/admin/report")


# ======================================================================
# ส่วนที่ 7: รูป QR รับเงินตั้งต้น (ฝังในไฟล์นี้ จึงใช้ไฟล์เดียวได้)
# ======================================================================
# QR_B64 = รูป QR (WebP ย่อให้เล็กแล้ว) แปลงเป็นข้อความ base64 บรรทัดเดียวด้านล่าง ไม่ต้องอ่าน/แก้
# อยากเปลี่ยนรูป: ให้แอดมินอัปโหลดที่หน้า Product (ไม่ต้องแก้โค้ด) รูปที่อัปโหลดจะใช้แทนรูปนี้
QR_B64 = "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"


# ======================================================================
# จุดเริ่มต้นของโปรแกรม (ทำงานเมื่อรันไฟล์นี้โดยตรง)
# ======================================================================
def main():
    """เริ่มโปรแกรม: เตรียมฐานข้อมูล หาพอร์ตว่าง เปิดเซิร์ฟเวอร์ และเปิดเบราว์เซอร์"""
    init_db()
    os.makedirs(SLIP_DIR, exist_ok=True)
    os.makedirs(AVATAR_DIR, exist_ok=True)
    server = None
    for port in range(PORT, PORT + 10):  # ถ้า 8080 ไม่ว่าง ลอง 8081, 8082, ... สูงสุด 10 พอร์ต
        try:
            server = FastServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            print("พอร์ต %d ถูกใช้อยู่ ลองพอร์ตถัดไป..." % port)
    if server is None:
        print("ไม่มีพอร์ตว่างเลย กรุณาปิด Terminal เก่าที่รันโปรแกรมนี้ค้างอยู่ แล้วรันใหม่")
        raise SystemExit(1)
    url = "http://127.0.0.1:%d" % server.server_address[1]
    print("%s v26-qty-input เปิดแล้วที่  %s   (กด Ctrl+C เพื่อหยุด)" % (SHOP_NAME, url))
    print("หลังบ้านแอดมิน: %s/admin/login" % url)
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()  # หน่วง 0.8 วินาทีแล้วเปิดเบราว์เซอร์ให้อัตโนมัติ
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nหยุดเซิร์ฟเวอร์แล้ว")
        server.server_close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        input("เกิดข้อผิดพลาดตอนเริ่มโปรแกรม (ข้อความด้านบน) กด Enter เพื่อปิด")
