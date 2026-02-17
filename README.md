# Galatea

A Telegram bot that helps users create and edit documents through natural conversation.

> **Disclaimer**: This codebase is purely vibe coded. No fancy patterns, just works.

## Features

- **Document Creation** - Create Word, PDF, Excel, and PowerPoint files through chat
- **Document Editing** - Upload files and edit them with AI assistance
- **Multi-language** - English and Indonesian support
- **Rate Limiting** - Monthly request limits with VIP unlimited access
- **Admin Controls** - VIP management, user banning, activity monitoring

## Tech Stack

| Component | Technology |
|-----------|------------|
| Runtime | Python 3.11+ |
| Database | SQLite |
| Bot | python-telegram-bot |
| AI | Claude (Anthropic) |
| Docs | python-docx, python-pptx, openpyxl, reportlab |

## Commands

### User Commands

| Command | Description |
|---------|-------------|
| `/start` | Start new session |
| `/new` | Create new document |
| `/edit` | Edit current document |
| `/analyze` | Get improvement suggestions |
| `/preview` | Preview document content |
| `/done` | Finish and download |
| `/cancel` | Cancel operation |
| `/status` | Session information |
| `/usage` | Check request limits |
| `/lang` | Change language |

### Admin Commands

| Command | Description |
|---------|-------------|
| `/addvip <user_id>` | Add VIP user |
| `/removevip <user_id>` | Remove VIP user |
| `/listvip` | List all VIPs |
| `/ban <user_id>` | Ban user |
| `/unban <user_id>` | Unban user |
| `/listban` | List banned users |
| `/stats` | Bot statistics |
| `/broadcast <msg>` | Send message to all users |
| `/activity [n]` | Recent activity log |
| `/sessions` | Active sessions summary |
| `/health` | System health status |

## Setup

1. Clone repo
   ```bash
   git clone https://github.com/Arfahd/Galatea.git
   cd Galatea
   ```

2. Install dependencies
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Configure environment
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. Run
   ```bash
   python main.py
   ```

## Project Structure

```
Galatea/
├── main.py
├── activity_logger.py
├── requirements.txt
├── .env.example
├── src/
│   ├── config.py
│   ├── database.py
│   ├── handlers/
│   ├── services/
│   ├── models/
│   ├── templates/
│   └── utils/
├── scripts/
└── data/
```

## Open Source

Vibe coded with Claude.
