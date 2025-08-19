## 📂 Struktur Repo
```bash
super-telegram-bot/
├── 📂 bot.py
├── 📂 requirements.txt
├── 📂 .env.example
├── 📂 README.md
└── 📂 LICENSE
```

## 📄 .env.example
***
# Ganti dengan token bot kamu dari BotFather
BOT_TOKEN=isi_token_bot_disini

# API Key OpenWeatherMap
OPENWEATHER_API_KEY=isi_api_key_openweather

# Timezone (default Asia/Jakarta)
TZ=Asia/Jakarta

# Lokasi database SQLite
DATABASE_PATH=bot_data.sqlite3
***

# 🤖 Telegram Bot

Bot Telegram serbaguna dengan fitur:
- 📅 Reminder (sekali, harian, mingguan)
- 📝 Catatan (tambah, lihat, hapus)
- 💰 Keuangan (pemasukan/pengeluaran, saldo, laporan bulanan)
- 🌦️  Cuaca (via OpenWeatherMap)

---

## 🚀 Instalasi

### 1. Clone Repository
```bash
git clone https://github.com/username/super-telegram-bot.git
cd super-telegram-bot
```

## Buat Virtual Environment (opsional tapi disarankan)
```bash
python3 -m venv .venv
source .venv/bin/activate
```

## Install Dependensi
```bash
pip install -r requirements.txt
```

## Siapkan File .env
**Buat file .env berdasarkan .env.example lalu isi:**
```bash
BOT_TOKEN=isi_token_bot_dari_botfather
OPENWEATHER_API_KEY=isi_api_key_openweather
TZ=Asia/Jakarta
DATABASE_PATH=bot_data.sqlite3
```

## ▶️ Menjalankan Bot
```bash
python bot.py
```
**Bot akan otomatis membuat file database SQLite sesuai path di .env.**

## 📌 Contoh Pemakaian
## CATATAN
```bash
/note_add Beli kopi susu
/note_list
/note_del 3
```

## Keuangan
```bash
/money_add +150000 Gaji
/money_add -20000 Kopi
/money_balance
/money_report
/money_report 08 2025
/money_report Agustus 2025
```

## Cuaca
```bash
/weather Jakarta
```

## Reminder
```bash
/reminder_once 2025-08-20 07:15 Bangun
/reminder_daily 06:00 Olahraga
/reminder_weekly Jumat 16:00 Rapat
/reminder_list
/reminder_del 7
```

## 🛠️  Teknologi
🛠️  [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)<br/>
🛠️  SQLite (default DB)<br/>
🛠️  OpenWeatherMap API<br/>

## 📄 LICENSE (MIT)
```bash
MIT License

Copyright (c) 2025 Dani

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

STAY SAVE BRO
