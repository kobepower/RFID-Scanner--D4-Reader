# cyber_ninja_rfid_d4_final_fixed.py
# 100% WORKING — BEAUTIFUL CYBERPUNK D4 TOOL
import sys
import time
import json
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QWidget, QListWidget, QListWidgetItem, QFrame, QGridLayout,
    QMessageBox, QInputDialog, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QPalette, QColor, QFont
import pyperclip

# ==================== DATABASE ====================
DB_PATH = "learned_tags.json"

def load_db():
    if not os.path.exists(DB_PATH):
        with open(DB_PATH, "w") as f:
            json.dump({}, f)
        return {}
    try:
        with open(DB_PATH) as f:
            return json.load(f)
    except:
        return {}

def save_db(db):
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=4)

def save_unknown(uid, freq, raw):
    db = load_db()
    if uid not in db:
        db[uid] = {
            "raw": raw,
            "frequency": freq,
            "assigned_type": "Unknown",
            "assigned_subtype": "Pending",
            "notes": "Auto-saved from D4"
        }
        save_db(db)

def label_tag(uid):
    tag_type, ok1 = QInputDialog.getText(None, "Label Tag", "Tag Type (e.g. MIFARE Classic):")
    if not ok1 or not tag_type.strip():
        return
    subtype, ok2 = QInputDialog.getText(None, "Label Tag", "Subtype (e.g. S50 1K):")
    notes, _ = QInputDialog.getText(None, "Label Tag", "Notes (optional):")
    db = load_db()
    db[uid]["assigned_type"] = tag_type.strip()
    db[uid]["assigned_subtype"] = subtype.strip() or "Unknown"
    db[uid]["notes"] = notes.strip()  # FIXED: was missing key name
    save_db(db)
    QMessageBox.information(None, "Success", f"Labeled as:\n{tag_type} • {subtype}")

# ==================== CLASSIFIER ====================
def classify_tag_smart(raw_uid: str):
    uid = raw_uid.strip()
    learned = load_db().get(uid)
    if learned and learned.get("assigned_type", "Unknown") != "Unknown":
        color = "#00ff88" if "MIFARE" in learned["assigned_type"] or "Desfire" in learned["assigned_type"] else "#ff6b35"
        return {"uid": uid, "type": learned["assigned_type"], "subtype": learned["assigned_subtype"],
                "freq": learned["frequency"], "color": color}

    if uid.isdigit() and len(uid) == 10:
        direct_matches = {
            # LF Tags (125kHz)
            "1164124127": ("T5577 Clone", "Keri Tag", "LF 125kHz", "#ff3366"),
            "1315027968": ("ICopyX ID1", "LF Card", "LF 125kHz", "#ff6b35"),
            "0084148994": ("EM410x", "Converted T5577", "LF 125kHz", "#ff8844"),
            "0165462222": ("T5577 Encrypted", "ICopyX Cards", "LF 125kHz", "#ff4488"),
            "1654622220": ("T5577 Encrypted", "ICopyX Cards", "LF 125kHz", "#ff4488"),
            # HF Tags (13.56MHz) - MIFARE
            "1046976037": ("MIFARE Classic 4K", "ICopyX M1-4B", "HF 13.56MHz", "#00d4ff"),
            "0514439285": ("MIFARE Classic 1K", "Blue Tag", "HF 13.56MHz", "#00d4ff"),
            "0378741187": ("MIFARE S70 4K", "Classic", "HF 13.56MHz", "#00d4ff"),
            "2746930474": ("MIFARE Classic 1K", "Client Tag", "HF 13.56MHz", "#00ffff"),
            "3145225728": ("MIFARE Classic 1K", "Standard", "HF 13.56MHz", "#00d4ff"),
            "0043568323": ("MIFARE S50 1K", "Gen3 Blank", "HF 13.56MHz", "#00ffff"),
            # ICopyX M1-4B Cards (MIFARE 4K in special ranges)
            "2403636915": ("MIFARE Classic 4K", "ICopyX M1-4B L3", "HF 13.56MHz", "#00d4ff"),
            "2403648347": ("MIFARE Classic 4K", "ICopyX M1-4B L3", "HF 13.56MHz", "#00d4ff"),
            "2811368341": ("MIFARE Classic 4K", "ICopyX M1-4B L2", "HF 13.56MHz", "#00d4ff"),
            "2814923157": ("MIFARE Classic 4K", "ICopyX M1-4B L2", "HF 13.56MHz", "#00d4ff"),
            # HF Tags (13.56MHz) - DESFire
            "2417522474": ("DESFire EV1/EV2", "Standard", "HF 13.56MHz", "#ff00ff"),
            "2418023930": ("DESFire EV1/EV2", "Blank Card", "HF 13.56MHz", "#ff00ff"),
        }
        if uid in direct_matches:
            t, s, f, c = direct_matches[uid]
            return {"uid": uid, "type": t, "subtype": s, "freq": f, "color": c}

        # Smart classification for unknown tags
        uid_int = int(uid)
        
        # ICopyX M1-4B L3 range (MIFARE 4K pretending to be high UID)
        if 2403000000 <= uid_int <= 2404999999:
            freq = "HF 13.56MHz"
            color = "#00d4ff"
            tag_type = "MIFARE Classic 4K"
            subtype = "ICopyX M1-4B (L3)"
        # ICopyX M1-4B L2 range (MIFARE 4K in 2.8B range)
        elif 2810000000 <= uid_int <= 2819999999:
            freq = "HF 13.56MHz"
            color = "#00d4ff"
            tag_type = "MIFARE Classic 4K"
            subtype = "ICopyX M1-4B (L2)"
        # DESFire range (2.417B - 2.419B is typical DESFire)
        elif 2417000000 <= uid_int <= 2419999999:
            freq = "HF 13.56MHz"
            color = "#ff00ff"
            tag_type = "DESFire (Probable)"
            subtype = "EV1/EV2/EV3"
        # Broader DESFire range
        elif 2415000000 <= uid_int <= 2425000000:
            freq = "HF 13.56MHz"
            color = "#ff00ff"
            tag_type = "DESFire (Probable)"
            subtype = "Unknown Model"
        # High LF range (3B+ are often LF clones)
        elif uid_int >= 3000000000:
            freq = "LF 125kHz"
            color = "#ffaa00"
            tag_type = "LF Tag (Probable)"
            subtype = "Clone/Generic"
        # Low MIFARE range (under 200M is usually genuine MIFARE)
        elif uid_int < 200000000:
            freq = "HF 13.56MHz"
            color = "#00aaff"
            tag_type = "MIFARE (Probable)"
            subtype = "Classic S50/S70"
        # Mid-low MIFARE range (200M - 1.5B)
        elif 200000000 <= uid_int < 1500000000:
            freq = "HF 13.56MHz"
            color = "#00aaff"
            tag_type = "MIFARE (Probable)"
            subtype = "Classic/Ultralight"
        # Mid-range LF (1.5B - 2.4B, excluding ICopyX ranges)
        elif 1500000000 <= uid_int < 2403000000:
            freq = "LF 125kHz"
            color = "#ffaa00"
            tag_type = "LF Tag (Probable)"
            subtype = "EM/T5577"
        # Catch-all for weird ranges
        else:
            freq = "HF 13.56MHz"
            color = "#ffff00"
            tag_type = "Unknown HF"
            subtype = "Unusual Range"
        
        save_unknown(uid, freq, raw_uid)
        return {"uid": uid, "type": tag_type, "subtype": subtype, "freq": freq, "color": color}

    save_unknown(uid, "Unknown", raw_uid)
    return {"uid": uid, "type": "UNKNOWN", "subtype": "Invalid Format", "freq": "?", "color": "#ffff00"}

# ==================== BEEP & KEY LISTENER ====================
def play_beep():
    try:
        import winsound
        winsound.Beep(2200, 90)
    except:
        print("\a", end="")

class KeyListener(QObject):
    new_uid = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.buffer = ""
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.flush)
    
    def key_pressed(self, char):
        if char.isdigit():
            self.buffer += char
            self.timer.start(400)
        elif char in "\r\n" and self.buffer:
            self.flush_now()  # FIXED: immediate flush on Enter
    
    def flush_now(self):
        """Immediate flush when Enter is pressed"""
        self.timer.stop()
        if self.buffer:
            self.new_uid.emit(self.buffer)
            self.buffer = ""
    
    def flush(self):
        """Timeout-based flush"""
        if len(self.buffer) >= 8:
            self.new_uid.emit(self.buffer)
        self.buffer = ""

# ==================== MAIN WINDOW ====================
class CyberNinjaRFID(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CYBER NINJA RFID — D4 EDITION")
        self.resize(1200, 900)
        self.setMinimumSize(900, 650)
        self.original_uid = None
        self.is_scanning = True
        self.sound_enabled = True
        self.key_listener = KeyListener()
        self.key_listener.new_uid.connect(self.process_uid)
        self.init_ui()

    def glow(self, widget, color_hex):
        effect = QGraphicsDropShadowEffect()
        effect.setBlurRadius(40)
        effect.setColor(QColor(color_hex))
        effect.setOffset(0, 0)
        widget.setGraphicsEffect(effect)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main = QVBoxLayout(central)
        main.setContentsMargins(30, 30, 30, 30)
        main.setSpacing(25)

        # Title
        title = QLabel("CYBER NINJA RFID — D4 EDITION")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 46, QFont.Weight.Bold))
        title.setStyleSheet("color: #00ffff;")
        self.glow(title, "#00ffff")
        main.addWidget(title)

        # Card
        card = QFrame()
        card.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #1a1a33,stop:1 #000000); border: 4px solid #00ffff; border-radius: 35px;")
        card_layout = QGridLayout(card)
        card_layout.setContentsMargins(60, 60, 60, 60)

        self.uid_label = QLabel("----------")
        self.uid_label.setFont(QFont("Consolas", 80, QFont.Weight.Bold))
        self.uid_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.uid_label.setStyleSheet("color: #00ff88;")

        self.type_label = QLabel("WAITING FOR D4 SCAN...")
        self.type_label.setFont(QFont("Consolas", 32))
        self.type_label.setStyleSheet("color: #00ff88;")

        self.freq_label = QLabel("---")
        self.freq_label.setFont(QFont("Consolas", 28))
        self.freq_label.setStyleSheet("color: #00ffff;")

        card_layout.addWidget(self.uid_label, 0, 0, 1, 2)
        card_layout.addWidget(self.type_label, 1, 0)
        card_layout.addWidget(self.freq_label, 1, 1, alignment=Qt.AlignmentFlag.AlignRight)
        main.addWidget(card)

        # Toolbar
        toolbar = QFrame()
        toolbar.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #110033,stop:1 #003366); border: 3px solid #00ffff; border-radius: 25px; padding: 12px;")
        tb = QHBoxLayout(toolbar)
        tb.setSpacing(20)

        btn_css = """
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 %s,stop:1 %s);
                color: white;
                border: 2px solid %s;
                border-radius: 18px;
                font-size: 20px;
                font-weight: bold;
                padding: 18px;
                min-width: 170px;
            }
            QPushButton:hover { border: 3px solid white; }
        """

        self.set_btn = QPushButton("SET ORIGINAL")
        self.set_btn.setStyleSheet(btn_css % ("#008800", "#004400", "#00ff00"))
        self.glow(self.set_btn, "#00ff00")
        self.set_btn.clicked.connect(self.set_original)

        self.clear_btn = QPushButton("CLEAR ORIGINAL")
        self.clear_btn.setStyleSheet(btn_css % ("#880000", "#440000", "#ff0066"))
        self.glow(self.clear_btn, "#ff0066")
        self.clear_btn.clicked.connect(self.clear_original)

        self.copy_btn = QPushButton("COPY ALL")
        self.copy_btn.setStyleSheet(btn_css % ("#0066cc", "#003366", "#00ffff"))
        self.glow(self.copy_btn, "#00ffff")
        self.copy_btn.clicked.connect(self.copy_all)

        self.label_btn = QPushButton("LABEL TAG")
        self.label_btn.setStyleSheet(btn_css % ("#8B4513", "#663300", "#ffaa00"))
        self.glow(self.label_btn, "#ffaa00")
        self.label_btn.clicked.connect(self.label_current)

        self.scan_btn = QPushButton("PAUSE SCANNING")
        self.scan_btn.setStyleSheet(btn_css % ("#880000", "#440000", "#ff0066"))
        self.glow(self.scan_btn, "#ff0066")
        self.scan_btn.clicked.connect(self.toggle_scan)

        self.sound_btn = QPushButton("MUTE BEEP")
        self.sound_btn.setStyleSheet(btn_css % ("#556B2F", "#334422", "#00ff88"))
        self.glow(self.sound_btn, "#00ff88")
        self.sound_btn.clicked.connect(self.toggle_sound)

        tb.addWidget(self.set_btn)
        tb.addWidget(self.clear_btn)
        tb.addWidget(self.copy_btn)
        tb.addWidget(self.label_btn)
        tb.addStretch()
        tb.addWidget(self.scan_btn)
        tb.addWidget(self.sound_btn)
        main.addWidget(toolbar)

        # Clone status
        self.clone_label = QLabel("")
        self.clone_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clone_label.setFont(QFont("Arial", 64, QFont.Weight.Bold))
        main.addWidget(self.clone_label)

        # History
        history_label = QLabel("<b>SCAN HISTORY — Double-click to label</b>")
        history_label.setStyleSheet("color:#00ffff;font-size:22px;")
        main.addWidget(history_label)
        
        self.history = QListWidget()
        self.history.setStyleSheet("background:#000;border:3px solid #00ffff;border-radius:20px;color:white;font-size:18px;padding:10px;")
        self.history.itemDoubleClicked.connect(self.on_history_doubleclick)
        main.addWidget(self.history, 1)

        # Status
        self.status = QLabel("D4 Mode Active — Ready for 10-digit scans")
        self.status.setStyleSheet("color:#00ff88;background:#000015;padding:15px;border-radius:15px;font-size:18px;")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main.addWidget(self.status)

    def keyPressEvent(self, e):
        if self.is_scanning:
            # FIXED: Handle Enter key separately from text
            if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.key_listener.key_pressed("\n")
            else:
                text = e.text()
                if text and text.isdigit():
                    self.key_listener.key_pressed(text)
        super().keyPressEvent(e)

    def process_uid(self, raw):
        info = classify_tag_smart(raw)
        self.uid_label.setText(info["uid"])
        self.uid_label.setStyleSheet(f"color: {info['color']};")
        self.glow(self.uid_label, info["color"])
        self.type_label.setText(f"{info['type']} • {info['subtype']}")
        self.freq_label.setText(info["freq"])
        if self.sound_enabled:
            play_beep()

        if self.original_uid == info["uid"]:
            self.clone_label.setText("✓ CLONE MATCH")
            self.clone_label.setStyleSheet("color: #00ff00;")
            self.glow(self.clone_label, "#00ff00")
        elif self.original_uid:
            self.clone_label.setText("✗ NO MATCH")
            self.clone_label.setStyleSheet("color: #ff0066;")
        else:
            self.clone_label.setText("")

        item = QListWidgetItem(f"[{time.strftime('%H:%M:%S')}] {info['type']} | {info['uid']}")
        item.setForeground(QColor(info["color"]))
        self.history.insertItem(0, item)
        if self.history.count() > 40:
            self.history.takeItem(self.history.count() - 1)

    def copy_all(self):
        text = f"{self.uid_label.text()}\n{self.type_label.text()} {self.freq_label.text()}"
        pyperclip.copy(text)
        self.status.setText("✓ Copied to clipboard!")
        QTimer.singleShot(2000, lambda: self.status.setText("D4 Mode Active — Ready for 10-digit scans"))

    def label_current(self):
        uid = self.uid_label.text().strip()
        if uid and uid != "----------" and len(uid) == 10:
            label_tag(uid)
        else:
            QMessageBox.warning(self, "No Tag", "Scan a valid tag first!")

    def on_history_doubleclick(self, item):
        uid = item.text().split(" | ")[-1].strip()
        if len(uid) == 10:
            label_tag(uid)

    def set_original(self):
        uid = self.uid_label.text().strip()
        if uid and uid != "----------" and len(uid) == 10:
            self.original_uid = uid
            self.status.setText(f"✓ Original set: {uid}")
        else:
            QMessageBox.warning(self, "No Tag", "Scan a valid tag first!")

    def clear_original(self):
        self.original_uid = None
        self.clone_label.setText("")
        self.status.setText("Original cleared — Ready for new scans")

    def toggle_scan(self):
        self.is_scanning = not self.is_scanning
        if self.is_scanning:
            self.scan_btn.setText("PAUSE SCANNING")
            self.status.setText("✓ Scanning resumed")
        else:
            self.scan_btn.setText("RESUME SCANNING")
            self.status.setText("⏸ Scanning paused")

    def toggle_sound(self):
        self.sound_enabled = not self.sound_enabled
        self.sound_btn.setText("UNMUTE BEEP" if not self.sound_enabled else "MUTE BEEP")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(10, 10, 30))
    app.setPalette(palette)
    win = CyberNinjaRFID()
    win.show()
    sys.exit(app.exec())