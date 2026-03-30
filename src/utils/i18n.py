"""
Internationalization (i18n) module for multi-language support.
Supports English (en) and Indonesian (id).

Cloud version - includes messages for new admin commands.
"""

from typing import Optional

# All bot messages in both languages
MESSAGES: dict[str, dict[str, str]] = {
    # Welcome and general
    "welcome": {
        "en": """Welcome to Galatea.

I help you create and edit documents through chat.

Supported formats: Word, PDF, Excel, PowerPoint

Send a file to edit, or describe what you want to create.""",
        "id": """Selamat datang di Galatea.

Saya membantu Anda membuat dan mengedit dokumen melalui chat.

Format yang didukung: Word, PDF, Excel, PowerPoint

Kirim file untuk diedit, atau jelaskan apa yang ingin Anda buat.""",
    },
    "help": {
        "en": """Galatea Help

Commands:
/new - Create new document
/edit - Edit current document
/analyze - Get improvement suggestions
/preview - View document content
/done - Finish and download
/cancel - Cancel operation
/status - Session info
/usage - Check request limits
/lang - Change language

Supported formats: Word, PDF, Excel, PowerPoint

Session expires after 1 hour of inactivity.""",
        "id": """Bantuan Galatea

Perintah:
/new - Buat dokumen baru
/edit - Edit dokumen saat ini
/analyze - Dapatkan saran perbaikan
/preview - Lihat isi dokumen
/done - Selesai dan unduh
/cancel - Batalkan operasi
/status - Info sesi
/usage - Cek batas permintaan
/lang - Ubah bahasa

Format yang didukung: Word, PDF, Excel, PowerPoint

Sesi berakhir setelah 1 jam tidak aktif.""",
    },
    # Actions
    "choose_action": {
        "en": "What would you like to do?",
        "id": "Apa yang ingin Anda lakukan?",
    },
    "choose_doc_type": {
        "en": "What type of document do you want to create?",
        "id": "Jenis dokumen apa yang ingin Anda buat?",
    },
    "choose_template": {
        "en": "Choose a template to start with:",
        "id": "Pilih template untuk memulai:",
    },
    "describe_document": {
        "en": "Please describe what you want to create. Be as detailed as you like - I'll help you build it.",
        "id": "Silakan jelaskan apa yang ingin Anda buat. Jelaskan sedetail mungkin - saya akan membantu membuatnya.",
    },
    "describe_changes": {
        "en": "What changes would you like to make? Just describe them naturally.",
        "id": "Perubahan apa yang ingin Anda buat? Cukup jelaskan secara natural.",
    },
    # File operations
    "file_received": {
        "en": "File received: {filename}\nType: {filetype}\n\nAnalyzing content...",
        "id": "File diterima: {filename}\nTipe: {filetype}\n\nMenganalisis konten...",
    },
    "file_loaded": {
        "en": "File loaded successfully!\n\nFile: {filename}\nType: {filetype}\nSize: {size}\n\nWhat would you like to do with this file?",
        "id": "File berhasil dimuat!\n\nFile: {filename}\nTipe: {filetype}\nUkuran: {size}\n\nApa yang ingin Anda lakukan dengan file ini?",
    },
    "file_created": {
        "en": "Document created: {filename}",
        "id": "Dokumen dibuat: {filename}",
    },
    "file_updated": {
        "en": "Document updated.",
        "id": "Dokumen diperbarui.",
    },
    # Operation-specific feedback
    "file_summarized": {
        "en": "Summary complete.",
        "id": "Ringkasan selesai.",
    },
    "file_translated": {
        "en": "Translation complete.",
        "id": "Terjemahan selesai.",
    },
    "file_grammar_fixed": {
        "en": "Grammar corrections applied.",
        "id": "Koreksi tata bahasa diterapkan.",
    },
    "file_rewritten": {
        "en": "Document rewritten.",
        "id": "Dokumen ditulis ulang.",
    },
    "file_formatted": {
        "en": "Formatting improved.",
        "id": "Format diperbaiki.",
    },
    "no_file": {
        "en": "No document in current session.\n\nSend me a file or use /new to create one.",
        "id": "Tidak ada dokumen di sesi saat ini.\n\nKirim file atau gunakan /new untuk membuat baru.",
    },
    "file_too_large": {
        "en": "File is too large. Maximum size is {max_size}MB.",
        "id": "File terlalu besar. Ukuran maksimum adalah {max_size}MB.",
    },
    "unsupported_format": {
        "en": "Sorry, I don't support {extension} files.\nSupported formats: {formats}",
        "id": "Maaf, saya tidak mendukung file {extension}.\nFormat yang didukung: {formats}",
    },
    # Preview
    "preview_header": {
        "en": "Preview - Page {current}/{total}",
        "id": "Pratinjau - Halaman {current}/{total}",
    },
    "preview_empty": {
        "en": "Document is empty. Start adding content by describing what you want.",
        "id": "Dokumen kosong. Mulai tambahkan konten dengan menjelaskan apa yang Anda inginkan.",
    },
    # Todos
    "todos_header": {
        "en": "Suggested Actions ({count}):",
        "id": "Saran Tindakan ({count}):",
    },
    "todos_empty": {
        "en": "No suggestions available. Use /analyze to analyze your document.",
        "id": "Tidak ada saran tersedia. Gunakan /analyze untuk menganalisis dokumen Anda.",
    },
    "todo_executed": {
        "en": "Action completed: {description}",
        "id": "Tindakan selesai: {description}",
    },
    "todos_all_executed": {
        "en": "All suggested actions have been applied!",
        "id": "Semua saran tindakan telah diterapkan!",
    },
    "analyzing": {
        "en": "Analyzing your document...",
        "id": "Menganalisis dokumen Anda...",
    },
    "analysis_complete": {
        "en": "Analysis complete. Found {count} suggestions.",
        "id": "Analisis selesai. Ditemukan {count} saran.",
    },
    "todos_list_footer": {
        "en": "Select a number to view details:",
        "id": "Pilih nomor untuk melihat detail:",
    },
    "todo_detail": {
        "en": """Suggestion #{number}

Priority: {priority}
Type: {action_type}
Target: {target}

Description:
{description}

Suggested change:
{suggestion}""",
        "id": """Saran #{number}

Prioritas: {priority}
Tipe: {action_type}
Target: {target}

Deskripsi:
{description}

Perubahan yang disarankan:
{suggestion}""",
    },
    # Session
    "session_status": {
        "en": """Session Status

Document: {filename}
Type: {filetype}
Language: {language}
Expires in: {time_remaining}
Suggestions: {pending_todos} pending""",
        "id": """Status Sesi

Dokumen: {filename}
Tipe: {filetype}
Bahasa: {language}
Berakhir dalam: {time_remaining}
Saran: {pending_todos} tertunda""",
    },
    "session_expired": {
        "en": "Your session has expired due to inactivity. Please start a new session with /start.",
        "id": "Sesi Anda telah berakhir karena tidak aktif. Silakan mulai sesi baru dengan /start.",
    },
    "session_cleared": {
        "en": "Session cleared. Send a file or describe what you'd like to create.",
        "id": "Sesi dihapus. Kirim file atau jelaskan apa yang ingin Anda buat.",
    },
    "no_active_session": {
        "en": "No active session. Use /start to begin.",
        "id": "Tidak ada sesi aktif. Gunakan /start untuk memulai.",
    },
    # Done/Export
    "confirm_done": {
        "en": """Ready to finish?

File: {filename}
Format: {filetype}

The session will end after download.""",
        "id": """Siap menyelesaikan?

File: {filename}
Format: {filetype}

Sesi akan berakhir setelah unduhan.""",
    },
    "sending_file": {
        "en": "Preparing your file...",
        "id": "Menyiapkan file Anda...",
    },
    "file_sent": {
        "en": "Here is your document!\n\nSession completed. Use /start to begin a new session.",
        "id": "Ini dokumen Anda!\n\nSesi selesai. Gunakan /start untuk memulai sesi baru.",
    },
    "enter_filename": {
        "en": "Please enter a filename (without extension):",
        "id": "Silakan masukkan nama file (tanpa ekstensi):",
    },
    # Cancel
    "operation_cancelled": {
        "en": "Operation cancelled.",
        "id": "Operasi dibatalkan.",
    },
    "nothing_to_cancel": {
        "en": "Nothing to cancel. What would you like to do?",
        "id": "Tidak ada yang dibatalkan. Apa yang ingin Anda lakukan?",
    },
    # Language
    "language_changed": {
        "en": "Language changed to English.",
        "id": "Bahasa diubah ke Bahasa Indonesia.",
    },
    "choose_language": {
        "en": "Choose your preferred language:",
        "id": "Pilih bahasa yang Anda inginkan:",
    },
    # Processing
    "processing": {
        "en": "Processing...",
        "id": "Memproses...",
    },
    "please_wait": {
        "en": "Please wait...",
        "id": "Mohon tunggu...",
    },
    "thinking": {
        "en": "Thinking...",
        "id": "Sedang berpikir...",
    },
    # Errors (bilingual)
    "error_general": {
        "en": "An error occurred. Please try again or use /cancel.",
        "id": "Terjadi kesalahan. Silakan coba lagi atau gunakan /cancel.",
    },
    "error_file_read": {
        "en": "Error reading file: {error}",
        "id": "Gagal membaca file: {error}",
    },
    "error_file_write": {
        "en": "Error saving file: {error}",
        "id": "Gagal menyimpan file: {error}",
    },
    "error_processing": {
        "en": "Error: {error}",
        "id": "Kesalahan: {error}",
    },
    "error_ai": {
        "en": "AI service unavailable. Please try again.",
        "id": "Layanan AI tidak tersedia. Silakan coba lagi.",
    },
    "error_not_private": {
        "en": "This bot only works in private chats.",
        "id": "Bot ini hanya berfungsi di chat pribadi.",
    },
    "error_not_authorized": {
        "en": "You are not authorized to use this bot.",
        "id": "Anda tidak memiliki izin untuk menggunakan bot ini.",
    },
    # Buttons (used in keyboards)
    "btn_create_new": {
        "en": "Create New Document",
        "id": "Buat Dokumen Baru",
    },
    "btn_upload": {
        "en": "Upload File",
        "id": "Upload File",
    },
    "btn_help": {
        "en": "Help",
        "id": "Bantuan",
    },
    "btn_word": {
        "en": "Word Document",
        "id": "Dokumen Word",
    },
    "btn_pdf": {
        "en": "PDF",
        "id": "PDF",
    },
    "btn_excel": {
        "en": "Excel Spreadsheet",
        "id": "Spreadsheet Excel",
    },
    "btn_powerpoint": {
        "en": "PowerPoint",
        "id": "PowerPoint",
    },
    "btn_cancel": {
        "en": "Cancel",
        "id": "Batal",
    },
    "btn_back": {
        "en": "Back",
        "id": "Kembali",
    },
    "btn_next": {
        "en": "Next",
        "id": "Berikutnya",
    },
    "btn_previous": {
        "en": "Previous",
        "id": "Sebelumnya",
    },
    "btn_done": {
        "en": "Done",
        "id": "Selesai",
    },
    "btn_preview": {
        "en": "Preview",
        "id": "Pratinjau",
    },
    "btn_edit": {
        "en": "Edit",
        "id": "Edit",
    },
    "btn_analyze": {
        "en": "Analyze",
        "id": "Analisis",
    },
    "btn_todos": {
        "en": "View Suggestions",
        "id": "Lihat Saran",
    },
    "btn_execute": {
        "en": "Execute",
        "id": "Jalankan",
    },
    "btn_execute_all": {
        "en": "Execute All",
        "id": "Jalankan Semua",
    },
    "btn_skip": {
        "en": "Skip",
        "id": "Lewati",
    },
    "btn_skip_all": {
        "en": "Skip All",
        "id": "Lewati Semua",
    },
    "btn_yes": {
        "en": "Yes",
        "id": "Ya",
    },
    "btn_no": {
        "en": "No",
        "id": "Tidak",
    },
    "btn_confirm": {
        "en": "Confirm",
        "id": "Konfirmasi",
    },
    "btn_english": {
        "en": "English",
        "id": "English",
    },
    "btn_indonesian": {
        "en": "Bahasa Indonesia",
        "id": "Bahasa Indonesia",
    },
    "btn_blank": {
        "en": "Blank",
        "id": "Kosong",
    },
    # Edit operations
    "btn_summarize": {
        "en": "Summarize",
        "id": "Ringkas",
    },
    "btn_translate": {
        "en": "Translate",
        "id": "Terjemahkan",
    },
    "btn_rewrite": {
        "en": "Rewrite",
        "id": "Tulis Ulang",
    },
    "btn_format": {
        "en": "Format",
        "id": "Format",
    },
    "btn_add_content": {
        "en": "Add Content",
        "id": "Tambah Konten",
    },
    "btn_fix_grammar": {
        "en": "Fix Grammar",
        "id": "Perbaiki Grammar",
    },
    # Status messages
    "status_idle": {
        "en": "Idle",
        "id": "Tidak aktif",
    },
    "status_editing": {
        "en": "Editing",
        "id": "Mengedit",
    },
    "status_processing": {
        "en": "Processing",
        "id": "Memproses",
    },
    # Time
    "minutes": {
        "en": "{count} minutes",
        "id": "{count} menit",
    },
    "hours": {
        "en": "{count} hour(s)",
        "id": "{count} jam",
    },
    # Rate limiting
    "rate_limit_reached": {
        "en": """Monthly request limit reached.

Used: {used}/{limit}
Resets: {reset_date}

VIP users have unlimited requests.""",
        "id": """Batas permintaan bulanan tercapai.

Terpakai: {used}/{limit}
Reset: {reset_date}

Pengguna VIP memiliki permintaan tak terbatas.""",
    },
    "rate_limit_warning": {
        "en": "Requests remaining this month: {remaining}/{limit}",
        "id": "Sisa permintaan bulan ini: {remaining}/{limit}",
    },
    "rate_limit_status": {
        "en": """Usage Status

Status: {status_text}
Requests: {used}/{limit}
Remaining: {remaining}
Resets: {reset_date}""",
        "id": """Status Penggunaan

Status: {status_text}
Permintaan: {used}/{limit}
Sisa: {remaining}
Reset: {reset_date}""",
    },
    # Files command
    "files_header": {
        "en": "Your files:",
        "id": "File Anda:",
    },
    "files_empty": {
        "en": "No files found.",
        "id": "Tidak ada file ditemukan.",
    },
    # Upload prompt
    "upload_prompt": {
        "en": "Send me a file (PDF, Word, Excel, or PowerPoint) and I'll help you work with it.",
        "id": "Kirim file (PDF, Word, Excel, atau PowerPoint) dan saya akan membantu Anda.",
    },
    # Admin commands
    "admin_only": {
        "en": "This command is for administrators only.",
        "id": "Perintah ini hanya untuk administrator.",
    },
    "vip_added": {
        "en": "User {user_id} has been added to VIP list.",
        "id": "Pengguna {user_id} telah ditambahkan ke daftar VIP.",
    },
    "vip_already": {
        "en": "User {user_id} is already a VIP.",
        "id": "Pengguna {user_id} sudah menjadi VIP.",
    },
    "vip_removed": {
        "en": "User {user_id} has been removed from VIP list.",
        "id": "Pengguna {user_id} telah dihapus dari daftar VIP.",
    },
    "vip_not_found": {
        "en": "User {user_id} is not a VIP or cannot be removed (env VIP).",
        "id": "Pengguna {user_id} bukan VIP atau tidak dapat dihapus (VIP dari env).",
    },
    "vip_list": {
        "en": """VIP Users

From environment: {env_count}
{env_list}

Added by admin: {runtime_count}
{runtime_list}

Total VIPs: {total}""",
        "id": """Pengguna VIP

Dari environment: {env_count}
{env_list}

Ditambah admin: {runtime_count}
{runtime_list}

Total VIP: {total}""",
    },
    "vip_list_empty": {
        "en": "(none)",
        "id": "(tidak ada)",
    },
    "invalid_user_id": {
        "en": "Invalid user ID. Please provide a valid numeric user ID.",
        "id": "ID pengguna tidak valid. Berikan ID pengguna numerik yang valid.",
    },
    "usage_addvip": {
        "en": "Usage: /addvip <user_id>",
        "id": "Penggunaan: /addvip <user_id>",
    },
    "usage_removevip": {
        "en": "Usage: /removevip <user_id>",
        "id": "Penggunaan: /removevip <user_id>",
    },
    # Ban messages
    "user_banned": {
        "en": "Your access to this bot has been restricted.",
        "id": "Akses Anda ke bot ini telah dibatasi.",
    },
    "ban_success": {
        "en": "User {user_id} has been banned.",
        "id": "Pengguna {user_id} telah diblokir.",
    },
    "ban_already": {
        "en": "User {user_id} is already banned.",
        "id": "Pengguna {user_id} sudah diblokir.",
    },
    "unban_success": {
        "en": "User {user_id} has been unbanned.",
        "id": "Pengguna {user_id} telah dibuka blokirnya.",
    },
    "unban_not_found": {
        "en": "User {user_id} is not banned.",
        "id": "Pengguna {user_id} tidak diblokir.",
    },
    "ban_list": {
        "en": "Banned Users ({count}):\n{list}",
        "id": "Pengguna Diblokir ({count}):\n{list}",
    },
    "ban_list_empty": {
        "en": "No banned users.",
        "id": "Tidak ada pengguna yang diblokir.",
    },
    "usage_ban": {
        "en": "Usage: /ban <user_id>",
        "id": "Penggunaan: /ban <user_id>",
    },
    "usage_unban": {
        "en": "Usage: /unban <user_id>",
        "id": "Penggunaan: /unban <user_id>",
    },
    "cannot_ban_admin": {
        "en": "Cannot ban an administrator.",
        "id": "Tidak dapat memblokir administrator.",
    },
    # Stats messages
    "stats_summary": {
        "en": """Bot Statistics

Users: {total_users} total, {active_sessions} active
VIP: {vip_count}
Banned: {banned_count}

This month: {total_requests} requests

Top users:
{top_users}""",
        "id": """Statistik Bot

Pengguna: {total_users} total, {active_sessions} aktif
VIP: {vip_count}
Diblokir: {banned_count}

Bulan ini: {total_requests} permintaan

Pengguna teratas:
{top_users}""",
    },
    # Broadcast messages
    "broadcast_result": {
        "en": "Broadcast complete.\n\nSent: {success}\nFailed: {failed}",
        "id": "Siaran selesai.\n\nTerkirim: {success}\nGagal: {failed}",
    },
    "usage_broadcast": {
        "en": "Usage: /broadcast <message>",
        "id": "Penggunaan: /broadcast <pesan>",
    },
    # Cache messages
    "cache_hit": {
        "en": "(from cache)",
        "id": "(dari cache)",
    },
    "analysis_outdated": {
        "en": "Note: Document has changed since last analysis. Run /analyze again for updated suggestions.",
        "id": "Catatan: Dokumen telah berubah sejak analisis terakhir. Jalankan /analyze lagi untuk saran terbaru.",
    },
    # ==================== NEW: Cloud Admin Commands ====================
    # /activity command
    "activity_header": {
        "en": """Recent Activity ({count} entries)

{entries}""",
        "id": """Aktivitas Terbaru ({count} entri)

{entries}""",
    },
    "activity_empty": {
        "en": "No activity recorded yet.",
        "id": "Belum ada aktivitas tercatat.",
    },
    "activity_entry": {
        "en": "{time} | {action} | {user_id} | {details}",
        "id": "{time} | {action} | {user_id} | {details}",
    },
    "usage_activity": {
        "en": "Usage: /activity [count]\nDefault: 20 entries, max: 100",
        "id": "Penggunaan: /activity [jumlah]\nDefault: 20 entri, maks: 100",
    },
    # /sessions command
    "sessions_summary": {
        "en": """Sessions Summary

Total sessions: {total}

State breakdown:
  IDLE: {idle}
  CHATTING: {chatting}
  PROCESSING: {processing}
  Other: {other}""",
        "id": """Ringkasan Sesi

Total sesi: {total}

Pembagian status:
  IDLE: {idle}
  CHATTING: {chatting}
  PROCESSING: {processing}
  Lainnya: {other}""",
    },
    "sessions_empty": {
        "en": "No active sessions.",
        "id": "Tidak ada sesi aktif.",
    },
    # /health command
    "health_info": {
        "en": """System Health

Uptime: {uptime}
Memory: {memory}
Database: {db_size}
Sessions: {sessions}
Activity entries: {activity_count}""",
        "id": """Kesehatan Sistem

Waktu aktif: {uptime}
Memori: {memory}
Database: {db_size}
Sesi: {sessions}
Entri aktivitas: {activity_count}""",
    },
    "health_status_ok": {
        "en": "All systems operational",
        "id": "Semua sistem beroperasi normal",
    },
    "health_status_warning": {
        "en": "Warning: High memory usage",
        "id": "Peringatan: Penggunaan memori tinggi",
    },
    "health_status_error": {
        "en": "Error: System issues detected",
        "id": "Error: Masalah sistem terdeteksi",
    },
}


def get_message(key: str, lang: str = "en", **kwargs) -> str:
    """
    Get a message in the specified language.

    Args:
        key: Message key
        lang: Language code ("en" or "id")
        **kwargs: Format arguments for the message

    Returns:
        Formatted message string
    """
    if key not in MESSAGES:
        return f"[Missing message: {key}]"

    message_dict = MESSAGES[key]

    # Default to English if language not found
    if lang not in message_dict:
        lang = "en"

    message = message_dict.get(lang, message_dict.get("en", ""))

    # Format with kwargs if provided
    if kwargs:
        try:
            message = message.format(**kwargs)
        except KeyError:
            pass  # Return unformatted if format fails

    return message


def get_button_text(key: str, lang: str = "en") -> str:
    """
    Get button text in the specified language.
    Shorthand for get_message with btn_ prefix.

    Args:
        key: Button key (without btn_ prefix)
        lang: Language code

    Returns:
        Button text string
    """
    return get_message(f"btn_{key}", lang)
