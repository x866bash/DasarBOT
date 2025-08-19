import os
import asyncio
import sqlite3
from datetime import datetime, timedelta
import re
import requests
import pytz
from dotenv import load_dotenv

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# ========= ENV & KONFIGURASI =========
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
DB_PATH = os.getenv("DATABASE_PATH", "bot_data.sqlite3")
TZ_NAME = os.getenv("TZ", "Asia/Jakarta")
TZ = pytz.timezone(TZ_NAME)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN kosong. Isi di file .env")

# ========= DATABASE (SQLite) =========
def db_connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

CONN = db_connect()

def init_db():
    with CONN:
        CONN.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER UNIQUE NOT NULL
        )
        """)
        CONN.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
        CONN.execute("""
        CREATE TABLE IF NOT EXISTS money (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL
        )
        """)
        CONN.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            kind TEXT NOT NULL,      -- 'once' | 'daily' | 'weekly'
            message TEXT NOT NULL,
            run_at TEXT,             -- ISO: utk 'once'
            time_of_day TEXT,        -- 'HH:MM' utk 'daily' & 'weekly'
            weekday INTEGER,         -- 0=Mon..6=Sun utk 'weekly'
            created_at TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        )
        """)

def ensure_user(chat_id: int):
    with CONN:
        CONN.execute("INSERT OR IGNORE INTO users (chat_id) VALUES (?)", (chat_id,))

# ========= UTIL =========
def now_local():
    return datetime.now(TZ)

def parse_hhmm(s: str):
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", s.strip())
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return None
    return hh, mm

def iso(dt: datetime) -> str:
    return dt.isoformat()

def from_iso(s: str) -> datetime:
    return datetime.fromisoformat(s)

# ========= START / HELP =========
START_TEXT = (
    "Halo! 🤖 *Super Bot*\n\n"
    "Fitur & perintah:\n"
    "• /reminder_help – bantuan reminder\n"
    "• /note_add <teks> – tambah catatan\n"
    "• /note_list – lihat catatan\n"
    "• /note_del <id> – hapus catatan\n"
    "• /money_add <+/-nominal> <keterangan> – catat transaksi\n"
    "• /money_balance – lihat saldo & ringkas\n"
    "• /money_report [mm yyyy] – laporan bulan berjalan/tertentu\n"
    "• /weather <kota> – cuaca saat ini\n"
)

REMINDER_HELP = (
    "📅 *Reminder Help*\n"
    "Format:\n"
    "• /reminder_once <YYYY-MM-DD> <HH:MM> <pesan>\n"
    "  Contoh: /reminder_once 2025-08-19 14:30 Meeting PM\n"
    "• /reminder_daily <HH:MM> <pesan>\n"
    "  Contoh: /reminder_daily 06:00 Sholat Subuh\n"
    "• /reminder_weekly <Senin..Minggu> <HH:MM> <pesan>\n"
    "  Contoh: /reminder_weekly Jumat 16:00 Rapat mingguan\n"
    "• /reminder_list – daftar reminder aktif\n"
    "• /reminder_del <id> – matikan reminder\n"
)

# ========= HANDLERS DASAR =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_chat.id)
    await update.message.reply_text(START_TEXT, parse_mode=ParseMode.MARKDOWN)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START_TEXT + "\n" + REMINDER_HELP, parse_mode=ParseMode.MARKDOWN)

# ========= CATATAN =========
async def note_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ensure_user(chat_id)
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("Contoh: /note_add Beli kopi susu.")
        return
    with CONN:
        CONN.execute(
            "INSERT INTO notes (chat_id, content, created_at) VALUES (?,?,?)",
            (chat_id, text, iso(now_local()))
        )
    await update.message.reply_text("📝 Catatan ditambahkan.")

async def note_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    rows = CONN.execute(
        "SELECT id, content, created_at FROM notes WHERE chat_id=? ORDER BY id DESC", (chat_id,)
    ).fetchall()
    if not rows:
        await update.message.reply_text("Belum ada catatan.")
        return
    lines = [f"{r['id']}. {r['content']}  _({r['created_at']})_" for r in rows[:100]]
    await update.message.reply_text("📒 *Catatan:*\n" + "\n".join(lines), parse_mode=ParseMode.MARKDOWN)

async def note_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Contoh: /note_del 12")
        return
    rid = int(context.args[0])
    with CONN:
        cur = CONN.execute("DELETE FROM notes WHERE id=? AND chat_id=?", (rid, chat_id))
    if cur.rowcount:
        await update.message.reply_text(f"Catatan {rid} dihapus.")
    else:
        await update.message.reply_text("ID tidak ditemukan.")

# ========= KEUANGAN =========
async def money_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ensure_user(chat_id)
    if len(context.args) < 2:
        await update.message.reply_text("Format: /money_add <+/-nominal> <keterangan>\nContoh: /money_add -15000 Beli kopi")
        return
    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Nominal harus angka (boleh negatif/positif).")
        return
    desc = " ".join(context.args[1:]).strip()
    with CONN:
        CONN.execute(
            "INSERT INTO money (chat_id, amount, description, created_at) VALUES (?,?,?,?)",
            (chat_id, amount, desc, iso(now_local()))
        )
    await update.message.reply_text("✅ Transaksi dicatat.")

async def money_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    row = CONN.execute("SELECT COALESCE(SUM(amount),0) AS saldo FROM money WHERE chat_id=?", (chat_id,)).fetchone()
    saldo = row["saldo"] if row else 0
    # ringkas 10 transaksi terakhir
    rows = CONN.execute(
        "SELECT amount, description, created_at FROM money WHERE chat_id=? ORDER BY id DESC LIMIT 10", (chat_id,)
    ).fetchall()
    lines = [f"{r['created_at']}: {r['amount']} ({r['description']})" for r in rows]
    await update.message.reply_text(
        f"💰 *Saldo:* {saldo}\n\n*Terakhir:* \n" + ("\n".join(lines) if lines else "-"),
        parse_mode=ParseMode.MARKDOWN
    )

BULAN_MAP = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "agustus": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12
}

async def money_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    now = now_local()
    if len(context.args) >= 2:
        # /money_report 08 2025  atau  /money_report Agustus 2025
        bulan_arg = context.args[0].lower()
        tahun = int(context.args[1])
        if bulan_arg.isdigit():
            bulan = int(bulan_arg)
        else:
            bulan = BULAN_MAP.get(bulan_arg, now.month)
    else:
        bulan, tahun = now.month, now.year

    start = datetime(tahun, bulan, 1, tzinfo=TZ)
    if bulan == 12:
        end = datetime(tahun+1, 1, 1, tzinfo=TZ)
    else:
        end = datetime(tahun, bulan+1, 1, tzinfo=TZ)

    rows = CONN.execute(
        "SELECT amount, description, created_at FROM money WHERE chat_id=? AND created_at>=? AND created_at<? ORDER BY id",
        (chat_id, iso(start), iso(end))
    ).fetchall()
    total = sum(r["amount"] for r in rows)
    pemasukan = sum(r["amount"] for r in rows if r["amount"] > 0)
    pengeluaran = sum(-r["amount"] for r in rows if r["amount"] < 0)
    head = f"📊 Laporan {bulan:02d}/{tahun}\nTotal: {total}\nPemasukan: {pemasukan}\nPengeluaran: {pengeluaran}\n"
    detail = "\n".join([f"{r['created_at']}: {r['amount']} ({r['description']})" for r in rows]) or "-"
    await update.message.reply_text(head + "\n" + detail)

# ========= CUACA =========
async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not OPENWEATHER_API_KEY:
        await update.message.reply_text("OPENWEATHER_API_KEY belum diisi di .env")
        return
    if not context.args:
        await update.message.reply_text("Contoh: /weather Jakarta")
        return
    city = " ".join(context.args)
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&lang=id&units=metric"

    # Jalankan request blocking di thread terpisah agar tidak menghambat event loop
    def do_request():
        return requests.get(url, timeout=12).json()
    try:
        data = await asyncio.to_thread(do_request)
    except Exception as e:
        await update.message.reply_text(f"Gagal mengambil data: {e}")
        return

    if str(data.get("cod")) != "200":
        await update.message.reply_text("Kota tidak ditemukan atau API error.")
        return

    desc = data["weather"][0]["description"].title()
    temp = data["main"]["temp"]
    humid = data["main"]["humidity"]
    wind = data["wind"]["speed"]
    await update.message.reply_text(
        f"🌦️ Cuaca *{city}*\n"
        f"{desc}\n"
        f"Suhu: {temp}°C | Kelembapan: {humid}% | Angin: {wind} m/s",
        parse_mode=ParseMode.MARKDOWN
    )

# ========= REMINDER =========
# Helpers untuk menyimpan & menjadwalkan
HARI_MAP = {
    "senin": 0, "selasa": 1, "rabu": 2, "kamis": 3,
    "jumat": 4, "jum'at": 4, "sabtu": 5, "minggu": 6
}

def _save_reminder_once(chat_id: int, run_at: datetime, message: str) -> int:
    with CONN:
        cur = CONN.execute("""
            INSERT INTO reminders (chat_id, kind, message, run_at, created_at, active)
            VALUES (?,?,?,?,?,1)
        """, (chat_id, "once", message, iso(run_at), iso(now_local())))
        return cur.lastrowid

def _save_reminder_daily(chat_id: int, hhmm: str, message: str) -> int:
    with CONN:
        cur = CONN.execute("""
            INSERT INTO reminders (chat_id, kind, message, time_of_day, created_at, active)
            VALUES (?,?,?,?,?,1)
        """, (chat_id, "daily", message, hhmm, iso(now_local())))
        return cur.lastrowid

def _save_reminder_weekly(chat_id: int, weekday: int, hhmm: str, message: str) -> int:
    with CONN:
        cur = CONN.execute("""
            INSERT INTO reminders (chat_id, kind, message, time_of_day, weekday, created_at, active)
            VALUES (?,?,?,?,?,1)
        """, (chat_id, "weekly", message, hhmm, weekday, iso(now_local())))
        return cur.lastrowid

async def reminder_once(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ensure_user(chat_id)
    if len(context.args) < 3:
        await update.message.reply_text("Format: /reminder_once <YYYY-MM-DD> <HH:MM> <pesan>")
        return
    date_str, time_str = context.args[0], context.args[1]
    msg = " ".join(context.args[2:])
    try:
        hhmm = parse_hhmm(time_str)
        if not hhmm:
            raise ValueError("jam")
        y,m,d = map(int, date_str.split("-"))
        hour, minute = hhmm
        run_at = TZ.localize(datetime(y, m, d, hour, minute))
        if run_at < now_local():
            await update.message.reply_text("Waktu sudah lewat. Pilih waktu di masa depan.")
            return
        rid = _save_reminder_once(chat_id, run_at, msg)
        await update.message.reply_text(f"⏰ Reminder sekali dibuat (ID {rid}) untuk {run_at.strftime('%Y-%m-%d %H:%M')}.")
    except Exception:
        await update.message.reply_text("Format salah. Contoh: /reminder_once 2025-08-19 14:30 Meeting")

async def reminder_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ensure_user(chat_id)
    if len(context.args) < 2:
        await update.message.reply_text("Format: /reminder_daily <HH:MM> <pesan>")
        return
    hhmm_str = context.args[0]
    msg = " ".join(context.args[1:])
    hhmm = parse_hhmm(hhmm_str)
    if not hhmm:
        await update.message.reply_text("Jam tidak valid. Contoh: 06:30")
        return
    rid = _save_reminder_daily(chat_id, f"{hhmm[0]:02d}:{hhmm[1]:02d}", msg)
    await update.message.reply_text(f"🔁 Reminder harian dibuat (ID {rid}) pada {hhmm_str}.")

async def reminder_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ensure_user(chat_id)
    if len(context.args) < 3:
        await update.message.reply_text("Format: /reminder_weekly <Senin..Minggu> <HH:MM> <pesan>")
        return
    day_name = context.args[0].lower()
    hhmm_str = context.args[1]
    msg = " ".join(context.args[2:])
    if day_name not in HARI_MAP:
        await update.message.reply_text("Hari tidak valid. Gunakan: Senin, Selasa, Rabu, Kamis, Jumat, Sabtu, Minggu")
        return
    hhmm = parse_hhmm(hhmm_str)
    if not hhmm:
        await update.message.reply_text("Jam tidak valid. Contoh: 16:00")
        return
    rid = _save_reminder_weekly(chat_id, HARI_MAP[day_name], f"{hhmm[0]:02d}:{hhmm[1]:02d}", msg)
    await update.message.reply_text(f"🗓️ Reminder mingguan dibuat (ID {rid}) setiap {day_name.title()} {hhmm_str}.")

async def reminder_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    rows = CONN.execute("""
        SELECT id, kind, message, run_at, time_of_day, weekday, active
        FROM reminders
        WHERE chat_id=? AND active=1
        ORDER BY id DESC
    """, (chat_id,)).fetchall()
    if not rows:
        await update.message.reply_text("Tidak ada reminder aktif.")
        return
    inv_hari = {v:k.title() for k,v in HARI_MAP.items()}
    lines = []
    for r in rows:
        if r["kind"] == "once":
            lines.append(f"{r['id']}. [Sekali] {r['run_at']} – {r['message']}")
        elif r["kind"] == "daily":
            lines.append(f"{r['id']}. [Harian] {r['time_of_day']} – {r['message']}")
        else:
            day = inv_hari.get(r["weekday"], "?")
            lines.append(f"{r['id']}. [Mingguan] {day} {r['time_of_day']} – {r['message']}")
    await update.message.reply_text("📋 *Reminder Aktif:*\n" + "\n".join(lines), parse_mode=ParseMode.MARKDOWN)

async def reminder_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Contoh: /reminder_del 7")
        return
    rid = int(context.args[0])
    with CONN:
        cur = CONN.execute("UPDATE reminders SET active=0 WHERE id=? AND chat_id=?", (rid, chat_id))
    if cur.rowcount:
        await update.message.reply_text(f"Reminder {rid} dimatikan.")
    else:
        await update.message.reply_text("ID reminder tidak ditemukan.")

# ========= JOB QUEUE (Scheduler) =========
async def scheduler_tick(context: ContextTypes.DEFAULT_TYPE):
    """Dijalankan tiap 30 detik: kirim reminder yang saatnya jalan."""
    app = context.application
    now = now_local()

    # 1) Reminder sekali
    rows_once = CONN.execute("""
        SELECT id, chat_id, message, run_at FROM reminders
        WHERE kind='once' AND active=1
    """).fetchall()
    to_disable = []
    for r in rows_once:
        run_at = from_iso(r["run_at"])
        if run_at <= now:
            try:
                await app.bot.send_message(chat_id=r["chat_id"], text=f"⏰ Reminder: {r['message']}")
            except Exception:
                pass
            to_disable.append(r["id"])
    if to_disable:
        with CONN:
            CONN.executemany("UPDATE reminders SET active=0 WHERE id=?", [(i,) for i in to_disable])

    # 2) Harian
    rows_daily = CONN.execute("""
        SELECT id, chat_id, message, time_of_day FROM reminders
        WHERE kind='daily' AND active=1
    """).fetchall()
    now_hhmm = now.strftime("%H:%M")
    # agar tidak kirim berulang-ulang selama 1 menit penuh, kita pakai "penanda" per menit via cache table sederhana:
    CONN.execute("""CREATE TABLE IF NOT EXISTS _sent_guard (
        key TEXT PRIMARY KEY, created_at TEXT
    )""")
    guard_key = f"daily-{now.strftime('%Y-%m-%d %H:%M')}"
    guard_exists = CONN.execute("SELECT key FROM _sent_guard WHERE key=?", (guard_key,)).fetchone()
    if not guard_exists:
        for r in rows_daily:
            if r["time_of_day"] == now_hhmm:
                try:
                    await app.bot.send_message(chat_id=r["chat_id"], text=f"⏰ Reminder: {r['message']}")
                except Exception:
                    pass
        with CONN:
            CONN.execute("INSERT OR IGNORE INTO _sent_guard (key, created_at) VALUES (?,?)", (guard_key, iso(now)))

    # 3) Mingguan
    rows_weekly = CONN.execute("""
        SELECT id, chat_id, message, time_of_day, weekday FROM reminders
        WHERE kind='weekly' AND active=1
    """).fetchall()
    guard_key2 = f"weekly-{now.strftime('%Y-%m-%d %H:%M')}"
    guard_exists2 = CONN.execute("SELECT key FROM _sent_guard WHERE key=?", (guard_key2,)).fetchone()
    if not guard_exists2:
        for r in rows_weekly:
            if r["weekday"] == now.weekday() and r["time_of_day"] == now_hhmm:
                try:
                    await app.bot.send_message(chat_id=r["chat_id"], text=f"⏰ Reminder: {r['message']}")
                except Exception:
                    pass
        with CONN:
            CONN.execute("INSERT OR IGNORE INTO _sent_guard (key, created_at) VALUES (?,?)", (guard_key2, iso(now)))

# ========= FALLBACK ECHO =========
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    if text.startswith("/"):
        return  # biar command tidak dibalas echo
    await update.message.reply_text("Perintah tidak dikenal. Ketik /help untuk daftar fitur.")

# ========= MAIN =========
def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # Command map
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))

    # Notes
    app.add_handler(CommandHandler("note_add", note_add))
    app.add_handler(CommandHandler("note_list", note_list))
    app.add_handler(CommandHandler("note_del", note_del))

    # Money
    app.add_handler(CommandHandler("money_add", money_add))
    app.add_handler(CommandHandler("money_balance", money_balance))
    app.add_handler(CommandHandler("money_report", money_report))

    # Weather
    app.add_handler(CommandHandler("weather", weather))

    # Reminders
    app.add_handler(CommandHandler("reminder_help", lambda u,c: u.message.reply_text(REMINDER_HELP, parse_mode=ParseMode.MARKDOWN)))
    app.add_handler(CommandHandler("reminder_once", reminder_once))
    app.add_handler(CommandHandler("reminder_daily", reminder_daily))
    app.add_handler(CommandHandler("reminder_weekly", reminder_weekly))
    app.add_handler(CommandHandler("reminder_list", reminder_list))
    app.add_handler(CommandHandler("reminder_del", reminder_del))

    # Fallback
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Scheduler tick tiap 30 detik
    app.job_queue.run_repeating(scheduler_tick, interval=30, first=5)

    print("🤖 Bot berjalan...")
    app.run_polling(close_loop=False)  # close_loop=False agar bersih saat exit

if __name__ == "__main__":
    main()
