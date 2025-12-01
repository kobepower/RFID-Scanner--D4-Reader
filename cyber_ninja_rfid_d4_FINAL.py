# cyber_ninja_rfid_d4_FIXED_DEBUG.py
# THE ULTIMATE D4 TOOL - WITH EXTENSIVE DEBUG LOGGING
import sys
import time
import json
import os
import serial
import serial.tools.list_ports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QWidget, QListWidget, QListWidgetItem, QFrame, QGridLayout,
    QMessageBox, QInputDialog, QGraphicsDropShadowEffect, QTextEdit
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QPalette, QColor, QFont
import pyperclip

# ==================== FULL BINARY UART THREAD ====================
class D4UartThread(QThread):
    uid_detected = pyqtSignal(str)
    raw_uid_bytes = pyqtSignal(bytes)
    log = pyqtSignal(str)
    debug = pyqtSignal(str)  # NEW: Detailed debug output

    def __init__(self):
        super().__init__()
        self.running = True
        self.ser = None
        self.buffer = bytearray()

    def find_d4(self):
        """Find D4 device - with detailed port scanning"""
        self.debug.emit("=== SCANNING COM PORTS ===")
        ports = list(serial.tools.list_ports.comports())
        
        if not ports:
            self.debug.emit("❌ NO COM PORTS FOUND!")
            return None
            
        for p in ports:
            self.debug.emit(f"Found: {p.device} | {p.description} | VID:PID={p.vid}:{p.pid}")
            # Expanded search terms
            if any(k in p.description.upper() for k in ["CH340", "CH341", "CP210", "CP2102", "USB-SERIAL", "USB SERIAL", "USB-SER", "D4", "USB HID", "UART", "TTL"]):
                self.debug.emit(f"✅ MATCHED: {p.device}")
                return p.device
        
        # If no match, try the first available port
        if ports:
            self.debug.emit(f"⚠️ No match found, trying first port: {ports[0].device}")
            return ports[0].device
            
        return None

    def open_serial(self):
        port = self.find_d4()
        if not port:
            self.debug.emit("❌ NO SERIAL PORT DETECTED")
            return False
        try:
            self.ser = serial.Serial(port, 115200, timeout=0.1)
            time.sleep(2.3)
            self.log.emit(f"✅ D4 Connected → {port}")
            self.debug.emit(f"Serial opened: {port} @ 115200 baud")
            return True
        except Exception as e:
            self.log.emit(f"❌ Connection Error: {e}")
            self.debug.emit(f"Failed to open {port}: {e}")
            return False

    def switch_to_uart_mode(self):
        """Force D4 into UART mode"""
        pkt = b'\xAA\x02\x10\x01\xBB'
        try:
            if self.ser and self.ser.is_open:
                self.ser.write(pkt)
                self.log.emit("📡 FORCED → UART MODE")
                self.debug.emit(f"Sent UART mode command: {pkt.hex().upper()}")
                time.sleep(0.3)
                self.ser.reset_input_buffer()
                # Try to request a card immediately after
                self.debug.emit("Sending initial REQA...")
                self.send_frame(b'\x20')
        except Exception as e:
            self.log.emit("❌ UART switch failed")
            self.debug.emit(f"UART switch error: {e}")

    def send_frame(self, cmd: bytes):
        if not self.ser or not self.ser.is_open:
            self.debug.emit("❌ Cannot send - serial not open")
            return False
        frame = b'\xAA' + len(cmd).to_bytes(1, 'big') + cmd + b'\xBB'
        try:
            self.ser.write(frame)
            self.debug.emit(f"TX → {frame.hex().upper()}")
            return True
        except Exception as e:
            self.debug.emit(f"Send error: {e}")
            return False

    def request_select_sequence(self):
        """Rock-solid REQA → Anticollision → Select"""
        self.debug.emit("🔄 Starting REQA sequence...")
        self.send_frame(b'\x20')   # REQA / WUPA
        time.sleep(0.06)
        self.send_frame(b'\x01')   # Anticollision CL1
        time.sleep(0.06)
        self.send_frame(b'\x21')   # Select CL1
        time.sleep(0.06)

    def parse_frame(self, data: bytes):
        """Parse incoming UART frames"""
        self.buffer.extend(data)
        self.debug.emit(f"RX → Buffer: {self.buffer.hex().upper()} (len={len(self.buffer)})")
        
        while len(self.buffer) >= 5:
            if self.buffer[0] != 0xAA:
                self.debug.emit(f"❌ Bad header byte: {self.buffer[0]:02X}, skipping")
                self.buffer = self.buffer[1:]
                continue
                
            length = self.buffer[1]
            expected_len = 4 + length
            
            if len(self.buffer) < expected_len:
                self.debug.emit(f"⏳ Incomplete frame: have {len(self.buffer)}, need {expected_len}")
                break
                
            frame = self.buffer[:expected_len]
            
            if frame[-1] != 0xBB:
                self.debug.emit(f"❌ Bad tail byte: {frame[-1]:02X}, skipping")
                self.buffer = self.buffer[1:]
                continue

            payload = frame[2:2+length]
            self.debug.emit(f"✅ Valid frame: {frame.hex().upper()} | Payload: {payload.hex().upper()}")
            
            # Look for UID response patterns
            if len(payload) >= 6:
                self.debug.emit(f"Payload analysis: [0]={payload[0]:02X} [1]={payload[1]:02X}")
                
                # Pattern 1: 0x10 0x04 XX XX XX XX CS (4-byte UID)
                if payload[0] == 0x10 and payload[1] == 0x04:
                    uid_bytes = payload[2:6]
                    uid_int = int.from_bytes(uid_bytes, 'big')
                    uid_str = str(uid_int).zfill(10)
                    self.uid_detected.emit(uid_str)
                    self.raw_uid_bytes.emit(uid_bytes)
                    self.log.emit(f"🎯 UID DETECTED → {uid_str}")
                    self.debug.emit(f"4-byte UID: {uid_bytes.hex().upper()} = {uid_str}")
                
                # Pattern 2: 0x10 0x07 XX XX XX XX XX XX XX CS (7-byte UID)
                elif payload[0] == 0x10 and payload[1] == 0x07 and len(payload) >= 9:
                    uid_bytes = payload[2:9]
                    uid_int = int.from_bytes(uid_bytes, 'big')
                    uid_str = str(uid_int).zfill(10)
                    self.uid_detected.emit(uid_str)
                    self.raw_uid_bytes.emit(uid_bytes)
                    self.log.emit(f"🎯 UID DETECTED (7-byte) → {uid_str}")
                    self.debug.emit(f"7-byte UID: {uid_bytes.hex().upper()} = {uid_str}")
                
                # Pattern 3: Direct UID in payload (some firmware sends this)
                elif len(payload) == 4:
                    uid_bytes = payload
                    uid_int = int.from_bytes(uid_bytes, 'big')
                    uid_str = str(uid_int).zfill(10)
                    self.uid_detected.emit(uid_str)
                    self.raw_uid_bytes.emit(uid_bytes)
                    self.log.emit(f"🎯 UID DETECTED (raw) → {uid_str}")
                    self.debug.emit(f"Raw 4-byte UID: {uid_bytes.hex().upper()} = {uid_str}")

            self.buffer = self.buffer[expected_len:]

    def run(self):
        """Main thread loop - FIXED VERSION"""
        scan_counter = 0
        uart_mode_sent = False
        self.debug.emit("🚀 D4 Thread started")
        
        while self.running:
            if not self.ser or not self.ser.is_open:
                if self.open_serial():
                    # CRITICAL FIX: Give D4 time to fully boot before switching modes
                    self.log.emit(f"✅ D4 Connected → {self.ser.port}")
                    self.debug.emit("⏳ Waiting 800ms for D4 to stabilize...")
                    time.sleep(0.8)  # Let D4 fully boot
                    self.switch_to_uart_mode()
                    uart_mode_sent = True
                    scan_counter = 0  # Reset counter
                else:
                    self.debug.emit("⏳ Waiting 2s before retry...")
                    time.sleep(2)
                    continue

            try:
                # Continuous scanning - send REQA every 500ms
                scan_counter += 1
                if scan_counter % 50 == 0:  # Every 500ms (50 * 10ms)
                    self.send_frame(b'\x20')  # REQA
                    
                # Check for incoming data
                if self.ser.in_waiting:
                    raw_data = self.ser.read(self.ser.in_waiting)
                    self.debug.emit(f"📥 Received {len(raw_data)} bytes")
                    self.parse_frame(raw_data)
            except Exception as e:
                self.ser = None
                uart_mode_sent = False
                self.log.emit("❌ D4 Disconnected")
                self.debug.emit(f"Connection lost: {e}")
                
            time.sleep(0.01)

    def stop(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.debug.emit("🛑 Serial port closed")

# ==================== DATABASE & CLASSIFIER ====================
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
    if uid not in db:
        db[uid] = {}
    db[uid]["assigned_type"] = tag_type.strip()
    db[uid]["assigned_subtype"] = subtype.strip() or "Unknown"
    db[uid]["notes"] = notes.strip() if notes else ""
    save_db(db)
    QMessageBox.information(None, "Success", f"Labeled as:\n{tag_type} • {subtype}")

def classify_tag_smart(raw_uid: str):
    uid = raw_uid.strip()
    learned = load_db().get(uid)
    if learned and learned.get("assigned_type", "Unknown") != "Unknown":
        color = "#00ff88" if "MIFARE" in learned["assigned_type"] or "Desfire" in learned["assigned_type"] else "#ff6b35"
        return {
            "uid": uid,
            "type": learned["assigned_type"],
            "subtype": learned["assigned_subtype"],
            "freq": learned.get("frequency", "Unknown"),
            "color": color
        }

    if uid.isdigit() and len(uid) == 10:
        direct_matches = {
            "1164124127": ("T5577 Clone", "Keri Tag", "LF 125kHz", "#ff3366"),
            "1315027968": ("ICopyX ID1", "LF Card", "LF 125kHz", "#ff6b35"),
            "0084148994": ("EM410x", "Converted T5577", "LF 125kHz", "#ff8844"),
            "0165462222": ("T5577 Encrypted", "ICopyX", "LF 125kHz", "#ff4488"),
            "1654622220": ("T5577 Encrypted", "ICopyX", "LF 125kHz", "#ff4488"),
            "1046976037": ("MIFARE Classic 4K", "ICopyX M1-4B", "HF 13.56MHz", "#00d4ff"),
            "0514439285": ("MIFARE Classic 1K", "Blue Tag", "HF 13.56MHz", "#00d4ff"),
            "0378741187": ("MIFARE S70 4K", "Classic", "HF 13.56MHz", "#00d4ff"),
            "2746930474": ("MIFARE Classic 1K", "Client Tag", "HF 13.56MHz", "#00ffff"),
            "3145225728": ("MIFARE Classic 1K", "Standard", "HF 13.56MHz", "#00d4ff"),
            "0043568323": ("MIFARE S50 1K", "Gen3 Blank", "HF 13.56MHz", "#00ffff"),
            "2403636915": ("MIFARE Classic 4K", "ICopyX M1-4B L3", "HF 13.56MHz", "#00d4ff"),
            "2403648347": ("MIFARE Classic 4K", "ICopyX M1-4B L3", "HF 13.56MHz", "#00d4ff"),
            "2811368341": ("MIFARE Classic 4K", "ICopyX M1-4B L2", "HF 13.56MHz", "#00d4ff"),
            "2814923157": ("MIFARE Classic 4K", "ICopyX M1-4B L2", "HF 13.56MHz", "#00d4ff"),
            "2417522474": ("DESFire EV1/EV2", "Standard", "HF 13.56MHz", "#ff00ff"),
            "2418023930": ("DESFire EV1/EV2", "Blank", "HF 13.56MHz", "#ff00ff"),
        }
        if uid in direct_matches:
            t, s, f, c = direct_matches[uid]
            return {"uid": uid, "type": t, "subtype": s, "freq": f, "color": c}

        uid_int = int(uid)
        if 2403000000 <= uid_int <= 2404999999:
            freq, color, tag_type, subtype = "HF 13.56MHz", "#00d4ff", "MIFARE Classic 4K", "ICopyX L3"
        elif 2810000000 <= uid_int <= 2819999999:
            freq, color, tag_type, subtype = "HF 13.56MHz", "#00d4ff", "MIFARE Classic 4K", "ICopyX L2"
        elif 2415000000 <= uid_int <= 2425000000:
            freq, color, tag_type, subtype = "HF 13.56MHz", "#ff00ff", "DESFire (Probable)", "EV1/EV2"
        elif uid_int >= 3000000000:
            freq, color, tag_type, subtype = "LF 125kHz", "#ffaa00", "LF Clone", "T5577/EM"
        elif uid_int < 200000000:
            freq, color, tag_type, subtype = "HF 13.56MHz", "#00aaff", "MIFARE Classic", "S50/S70"
        else:
            freq, color, tag_type, subtype = "HF 13.56MHz", "#ffff00", "Unknown HF", "Check Range"

        save_unknown(uid, freq, raw_uid)
        return {"uid": uid, "type": tag_type, "subtype": subtype, "freq": freq, "color": color}

    save_unknown(uid, "Unknown", raw_uid)
    return {"uid": uid, "type": "UNKNOWN", "subtype": "Invalid", "freq": "?", "color": "#ffff00"}

def play_beep():
    try:
        import winsound
        winsound.Beep(3000, 130)
    except:
        print("\a", end="")

# ==================== MAIN WINDOW ====================
class CyberNinjaRFID(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CYBER NINJA RFID — D4 ULTIMATE SNIFFER [DEBUG MODE]")
        self.resize(1600, 1100)
        self.original_uid = None
        self.current_uid_bytes = None
        self.is_scanning = True
        self.sound_enabled = True

        self.init_ui()

        self.d4 = D4UartThread()
        self.d4.uid_detected.connect(self.on_new_uid)
        self.d4.raw_uid_bytes.connect(self.save_raw_uid)
        self.d4.log.connect(self.on_log_message)
        self.d4.debug.connect(self.on_debug_message)  # NEW
        self.d4.start()

    def on_log_message(self, message):
        if hasattr(self, 'status'):
            self.status.setText(message)

    def on_debug_message(self, message):
        """Display debug messages in the debug console"""
        if hasattr(self, 'debug_console'):
            self.debug_console.append(message)
            # Auto-scroll to bottom
            self.debug_console.verticalScrollBar().setValue(
                self.debug_console.verticalScrollBar().maximum()
            )

    def glow(self, widget, color):
        effect = QGraphicsDropShadowEffect()
        effect.setBlurRadius(50)
        effect.setColor(QColor(color))
        effect.setOffset(0, 0)
        widget.setGraphicsEffect(effect)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main = QVBoxLayout(central)
        main.setContentsMargins(30, 30, 30, 30)
        main.setSpacing(25)

        title = QLabel("CYBER NINJA RFID — D4 DEBUG MODE")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 42, QFont.Weight.Bold))
        title.setStyleSheet("color:#00ffff;")
        self.glow(title, "#00ffff")
        main.addWidget(title)

        card = QFrame()
        card.setStyleSheet("background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #1a1a50,stop:1 #000030);border:5px solid #00ffff;border-radius:40px;")
        cl = QGridLayout(card)
        cl.setContentsMargins(60, 60, 60, 60)

        self.uid_label = QLabel("----------")
        self.uid_label.setFont(QFont("Consolas", 72, QFont.Weight.Bold))
        self.uid_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.uid_label.setStyleSheet("color:#00ff88;")

        self.type_label = QLabel("WAITING FOR CARD...")
        self.type_label.setFont(QFont("Consolas", 28))
        self.type_label.setStyleSheet("color:#00ff88;")

        self.freq_label = QLabel("---")
        self.freq_label.setFont(QFont("Consolas", 26))
        self.freq_label.setStyleSheet("color:#00ffff;")

        cl.addWidget(self.uid_label, 0, 0, 1, 2)
        cl.addWidget(self.type_label, 1, 0)
        cl.addWidget(self.freq_label, 1, 1, alignment=Qt.AlignmentFlag.AlignRight)
        main.addWidget(card)

        toolbar = QFrame()
        toolbar.setStyleSheet("background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #110044,stop:1 #003377);border:4px solid #00ffff;border-radius:28px;padding:18px;")
        tb = QHBoxLayout(toolbar)
        tb.setSpacing(18)

        btn = "QPushButton{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 %s,stop:1 %s);color:white;border:3px solid %s;border-radius:18px;font-size:18px;font-weight:bold;padding:18px;min-width:160px;}QPushButton:hover{border:5px solid white;}"

        self.set_btn = QPushButton("SET ORIGINAL")
        self.set_btn.setStyleSheet(btn % ("#008800", "#004400", "#00ff00"))
        self.glow(self.set_btn, "#00ff00")
        self.set_btn.clicked.connect(self.set_original)

        self.clear_btn = QPushButton("CLEAR ORIGINAL")
        self.clear_btn.setStyleSheet(btn % ("#880000", "#440000", "#ff0066"))
        self.glow(self.clear_btn, "#ff0066")
        self.clear_btn.clicked.connect(self.clear_original)

        self.copy_btn = QPushButton("COPY ALL")
        self.copy_btn.setStyleSheet(btn % ("#0066cc", "#003366", "#00ffff"))
        self.glow(self.copy_btn, "#00ffff")
        self.copy_btn.clicked.connect(self.copy_all)

        self.label_btn = QPushButton("LABEL TAG")
        self.label_btn.setStyleSheet(btn % ("#8B4513", "#663300", "#ffaa00"))
        self.glow(self.label_btn, "#ffaa00")
        self.label_btn.clicked.connect(self.label_current)

        self.auth_btn = QPushButton("TRIGGER AUTH")
        self.auth_btn.setStyleSheet(btn % ("#ff00aa", "#aa0066", "#ff00ff"))
        self.glow(self.auth_btn, "#ff00ff")
        self.auth_btn.clicked.connect(self.trigger_auth)

        self.uart_btn = QPushButton("FORCE UART")
        self.uart_btn.setStyleSheet(btn % ("#ff6600", "#cc3300", "#ff8800"))
        self.glow(self.uart_btn, "#ff8800")
        self.uart_btn.clicked.connect(self.force_uart_mode)

        tb.addWidget(self.set_btn)
        tb.addWidget(self.clear_btn)
        tb.addWidget(self.copy_btn)
        tb.addWidget(self.label_btn)
        tb.addWidget(self.auth_btn)
        tb.addWidget(self.uart_btn)
        tb.addStretch()
        main.addWidget(toolbar)

        self.clone_label = QLabel("")
        self.clone_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clone_label.setFont(QFont("Arial", 60, QFont.Weight.Bold))
        main.addWidget(self.clone_label)

        # Debug Console - NEW!
        debug_label = QLabel("<b>🔍 DEBUG CONSOLE (Check for errors here!)</b>")
        debug_label.setStyleSheet("color:#ffff00;font-size:22px;")
        main.addWidget(debug_label)

        self.debug_console = QTextEdit()
        self.debug_console.setReadOnly(True)
        self.debug_console.setStyleSheet("background:#000;border:4px solid #ffff00;border-radius:15px;color:#00ff00;font-family:Consolas;font-size:14px;padding:10px;")
        self.debug_console.setMaximumHeight(200)
        main.addWidget(self.debug_console)

        history_label = QLabel("<b>SCAN HISTORY</b>")
        history_label.setStyleSheet("color:#00ffff;font-size:20px;")
        main.addWidget(history_label)

        self.history = QListWidget()
        self.history.setStyleSheet("background:#000;border:4px solid #00ffff;border-radius:20px;color:white;font-size:17px;padding:12px;")
        self.history.itemDoubleClicked.connect(self.on_history_doubleclick)
        main.addWidget(self.history, 1)

        self.status = QLabel("Starting up — Initializing D4 connection...")
        self.status.setStyleSheet("color:#00ff88;background:#000020;padding:18px;border-radius:15px;font-size:18px;")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main.addWidget(self.status)

    def force_uart_mode(self):
        if hasattr(self, 'd4'):
            self.d4.switch_to_uart_mode()

    def save_raw_uid(self, uid_bytes: bytes):
        self.current_uid_bytes = uid_bytes

    def on_new_uid(self, uid_str: str):
        uid_int = int(uid_str)
        self.current_uid_bytes = uid_int.to_bytes(4, 'big')

        info = classify_tag_smart(uid_str)
        self.uid_label.setText(info["uid"])
        self.uid_label.setStyleSheet(f"color:{info['color']};")
        self.glow(self.uid_label, info["color"])
        self.type_label.setText(f"{info['type']} • {info['subtype']}")
        self.freq_label.setText(info["freq"])
        if self.sound_enabled:
            play_beep()

        if self.original_uid == uid_str:
            self.clone_label.setText("✅ CLONE MATCH")
            self.clone_label.setStyleSheet("color:#00ff00;")
            self.glow(self.clone_label, "#00ff00")
        elif self.original_uid:
            self.clone_label.setText("❌ NO MATCH")
            self.clone_label.setStyleSheet("color:#ff0066;")
        else:
            self.clone_label.setText("")

        item = QListWidgetItem(f"[{time.strftime('%H:%M:%S')}] {info['type']} | {info['uid']}")
        item.setForeground(QColor(info["color"]))
        self.history.insertItem(0, item)
        if self.history.count() > 40:
            self.history.takeItem(self.history.count() - 1)

    def trigger_auth(self):
        if not self.current_uid_bytes:
            QMessageBox.critical(self, "No Card", "No valid MIFARE card detected yet!")
            return

        block, ok = QInputDialog.getInt(self, "Block Number", "Authenticate block (0-255):", 0, 0, 255)
        if not ok:
            return

        key, ok = QInputDialog.getText(self, "Key (hex)", "Enter 6-byte key (12 hex chars):", text="FFFFFFFFFFFF")
        if not ok or len(key) != 12:
            QMessageBox.warning(self, "Invalid", "Key must be 12 hex chars!")
            return

        try:
            key_bytes = bytes.fromhex(key)
        except ValueError:
            QMessageBox.warning(self, "Invalid", "Key must be valid hex!")
            return

        self.d4.request_select_sequence()
        time.sleep(0.15)

        self.d4.send_frame(bytes([0x60, block]) + key_bytes)
        time.sleep(0.12)
        self.d4.send_frame(bytes([0x61, block]) + key_bytes)

        self.status.setText(f"AUTH A+B SENT → Block {block}")
        play_beep()
        play_beep()

    def copy_all(self):
        text = f"{self.uid_label.text()}\n{self.type_label.text()} {self.freq_label.text()}"
        pyperclip.copy(text)
        self.status.setText("Copied to clipboard!")
        QTimer.singleShot(2000, lambda: self.status.setText("Ready"))

    def label_current(self):
        uid = self.uid_label.text().strip()
        if len(uid) == 10:
            label_tag(uid)

    def on_history_doubleclick(self, item):
        uid = item.text().split(" | ")[-1].strip()
        if len(uid) == 10:
            label_tag(uid)

    def set_original(self):
        uid = self.uid_label.text().strip()
        if len(uid) == 10:
            self.original_uid = uid
            self.status.setText(f"Original set: {uid}")

    def clear_original(self):
        self.original_uid = None
        self.clone_label.setText("")
        self.status.setText("Original cleared")

    def closeEvent(self, event):
        self.d4.stop()
        self.d4.wait()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(10, 10, 35))
    app.setPalette(palette)
    win = CyberNinjaRFID()
    win.show()
    sys.exit(app.exec())