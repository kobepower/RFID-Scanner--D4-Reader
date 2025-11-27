🕶️ CyberNinja RFID — D4 Edition

A cyberpunk-style RFID scanner GUI for Windows, built with Python and PyQt6. Designed for quickly scanning, classifying, and labeling 10-digit RFID tags, with sound alerts, history logging, and smart unknown tag handling.

Features

🎨 Cyberpunk GUI with glowing effects and gradient panels

📡 Smart tag classification (LF 125kHz / HF 13.56MHz)

💾 Auto-save unknown tags to learned_tags.json

📝 Manual labeling for unknown tags via GUI dialogs

🔊 Beep sound alert on each scan (can mute/unmute)

📋 Copy scanned tag info to clipboard

🕑 Scan history with double-click label functionality

✅ Clone detection — mark original tag and detect matches

Screenshots

Example: Tag scanning in action with glowing effects and scan history.

Requirements

Python 3.9+ (Windows recommended)

PyQt6

pyperclip

Install dependencies:

python -m pip install PyQt6 pyperclip

Usage

Open PowerShell in your project folder:

cd "D:\CyberNinja\CyberNinja_RFID_SCANNER"


Run the scanner:

python cyber_ninja_rfid_d4_final_fixed.py


Scan tags using your RFID reader or keyboard input.

Use the GUI buttons to:

Set/clear original tag

Copy info to clipboard

Pause/resume scanning

Mute/unmute beep

Label unknown tags

How It Works

Tag detection — Reads 10-digit IDs via simulated keyboard input.

Classification — Checks database and smart rules to detect LF/HF, MIFARE/DESFire, or unknown tags.

Storage — Unknown tags are automatically saved to learned_tags.json.

GUI Feedback — Color-coded UID and type display, scan history, and clone match alerts.

Manual labeling — Double-click a history entry to label unknown tags for future scans.

Database

learned_tags.json stores all scanned tags:

{
  "1234567890": {
    "raw": "1234567890",
    "frequency": "HF 13.56MHz",
    "assigned_type": "MIFARE Classic",
    "assigned_subtype": "S50 1K",
    "notes": "Auto-saved from D4"
  }
}

License

MIT License — free to use, modify, and distribute.
