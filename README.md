# 🗂 File ID Management Bot

A professional internal tool to capture, organise, and reuse Telegram `file_id`s.
Designed to integrate perfectly with your UPSC bot's `data/resources.py` structure.

---

## 🚀 Quick Start

### 1. Create a Telegram bot
- Open [@BotFather](https://t.me/BotFather) → `/newbot`
- Copy the token

### 2. Get your Telegram user ID
- Message [@userinfobot](https://t.me/userinfobot)
- Copy your numeric ID

### 3. Set environment variables

| Variable           | Required | Description                              |
|--------------------|----------|------------------------------------------|
| `FILEID_BOT_TOKEN` | ✅        | Token from BotFather                     |
| `ADMIN_IDS`        | ✅        | Comma-separated Telegram IDs: `123,456`  |
| `PORT`             | ❌        | Default `8080` (set by Render)           |

### 4. Run locally
```bash
pip install -r requirements.txt
export FILEID_BOT_TOKEN="your_token"
export ADMIN_IDS="your_telegram_id"
python bot.py
```

### 5. Deploy on Render
- Push to GitHub
- Create a new **Web Service** on Render
- Set `buildCommand: pip install -r requirements.txt`
- Set `startCommand: python bot.py`
- Add environment variables on dashboard

---

## 📂 Project Structure

```
fileid-bot/
├── bot.py                 # Entry point, routing
├── config.py              # All settings & constants
├── requirements.txt
├── render.yaml

├── handlers/
│   ├── keyboards.py       # All InlineKeyboardMarkup definitions
│   ├── start.py           # /start command
│   ├── capture.py         # File upload flow (core)
│   └── manage.py          # View / Search / Export / Delete

├── utils/
│   ├── logger.py          # Rotating file + console logging
│   ├── formatter.py       # Key generation, message templates
│   └── storage.py         # JSON CRUD engine

├── data/
│   └── file_store.json    # Persistent storage

└── images/
    └── capture.png        # Optional banner image
```

---

## 🧠 Full Workflow

### Uploading a file

1. **Send any file** (PDF, image, video, audio)
2. Bot shows:
   ```
   📁 File Captured
   📄 Name: polity.pdf
   📦 Size: 12.4 MB
   🆔 File ID: BQACAgUAAxkBA...
   ```
3. Choose **✅ Use Original Name** or **✏️ Rename**
4. If rename → send new display name (e.g. `Laxmikanth Polity 6th Edition`)
5. If key exists → **Overwrite** or **Auto-rename** (_2, _3…)
6. Select **Category** (Books / PYQs / Practice / Mocks)
7. Select **Subject** (History / Polity / etc.)
8. Bot outputs:

```
✅ Saved Successfully
📘 Name: Laxmikanth Polity 6th Edition
🔑 Key:  laxmikanth_polity_6th_edition
📂 books › Polity
🆔 File ID: BQACAgUAAxkBA...

📋 Paste into resources.py:
"laxmikanth_polity_6th_edition": ("Laxmikanth Polity 6th Edition", "BQACAgUAAxkBA..."),
```

---

## 📋 Commands

| Command          | Description                        |
|------------------|------------------------------------|
| `/start`         | Welcome screen + main menu         |
| `/view_books`    | Browse Books by subject            |
| `/view_pyqs`     | Browse PYQs                        |
| `/view_practice` | Browse Practice files              |
| `/view_mocks`    | Browse Mock tests                  |
| `/search`        | Search by keyword                  |
| `/export`        | Export as JSON + resources.py text |
| `/delete`        | Delete entry by safe_key           |
| `/batch`         | Enable batch upload mode           |
| `/done`          | End batch mode                     |
| `/stats`         | Show storage statistics            |

---

## 💾 Storage Schema (`data/file_store.json`)

```json
{
  "books": {
    "Polity": {
      "laxmikanth_polity_6th_edition": [
        "Laxmikanth Polity 6th Edition",
        "BQACAgUAAxkBA..."
      ]
    }
  },
  "pyqs": {
    "Prelims": {
      "upsc_prelims_2023": ["UPSC Prelims 2023", "FILE_ID"]
    }
  },
  "practice": {},
  "mocks": {}
}
```

---

## 🔁 resources.py Compatibility

Export produces lines directly pasteable into your UPSC bot:

```python
# BOOKS
# Polity
    "laxmikanth_polity_6th_edition": ("Laxmikanth Polity 6th Edition", "BQACAgUAAxkBA..."),
```

---

## 🔐 Security

- All handlers are admin-gated — non-admins are silently ignored
- No data is sent to any third party
- All storage is local JSON

---

## 🔄 Batch Mode

```
/batch          → Enable batch mode
[upload file 1] → Save it
[upload file 2] → Save it
/done           → End batch, see total count
```

After each file in batch mode, you'll see **➕ Add Another** / **✅ Done** buttons.

---

## 🔍 Search

```
/search laxmikanth
```
Or type `/search` then send the keyword as the next message.

Returns all matching entries with their resources.py line ready to copy.

---

## 📤 Export

`/export` → choose scope:
- Per category (Books / PYQs / Practice / Mocks)
- **Export All** → sends full `file_store_export.json` as a file

---

## 🗑 Delete

```
/delete laxmikanth_polity_6th_edition
```
Or type `/delete` then send the key.

---

## 🛠 Adding Categories / Subjects

Edit `config.py`:

```python
CATEGORIES = {
    "books":    "📚 Books",
    "pyqs":     "📄 PYQs",
    "practice": "🏹 Practice",
    "mocks":    "🧪 Mocks",
    "notes":    "📝 Notes",   # ← add new category here
}

SUBJECTS = {
    "notes": ["Short Notes", "Handwritten", "Formula Sheets"],
}
```

No code changes needed anywhere else.

---

## 📌 Notes

- `file_id` is valid only for the bot that received the file
- For large files, Telegram still provides the `file_id` instantly
- The bot never downloads files — it only reads metadata
