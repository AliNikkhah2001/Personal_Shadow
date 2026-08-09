cat << 'EOF' > ui/tabs/settings.py
import os
from datetime import datetime, timedelta
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from core.config import config
from core.database import db
from core.signals import bus

class SettingsWidget(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Settings", objectName="AppTitle"))
        
        scr = QScrollArea()
        scr.setWidgetResizable(True)
        scr.setStyleSheet("border: none; background: transparent;")
        cw = QWidget()
        ul = QGridLayout(cw)
        
        r = 0
        
        # --- HAUTE HORLOGERIE & CLOCK SETTINGS ---
        ul.addWidget(QLabel("--- Watch & Clock Styling ---", styleSheet="font-weight:bold; color:#0a84ff;"), r, 0, 1, 2); r+=1
        
        ul.addWidget(QLabel("Watch Brand/Logo:"), r, 0)
        self.c_brand = QComboBox()
        self.c_brand.addItems(["None", "Rolex", "Omega", "Audemars Piguet", "Seiko", "Citizen"])
        self.c_brand.setCurrentText(config.get("clock_brand", "None"))
        ul.addWidget(self.c_brand, r, 1); r+=1
        
        ul.addWidget(QLabel("Dial Color:"), r, 0)
        self.c_dial = QComboBox()
        self.c_dial.addItems(["Deep Blue", "Panda (White/Black)", "Tiffany Blue", "Emerald Green", "Matte Black", "Silver Sunburst"])
        self.c_dial.setCurrentText(config.get("clock_dial", "Deep Blue"))
        ul.addWidget(self.c_dial, r, 1); r+=1

        ul.addWidget(QLabel("Strap/Bracelet:"), r, 0)
        self.c_strap = QComboBox()
        self.c_strap.addItems(["Leather", "Oyster (Steel)", "Jubilee (Steel)", "Mesh (Milanese)", "Rubber (Diver)"])
        self.c_strap.setCurrentText(config.get("clock_strap", "Leather"))
        ul.addWidget(self.c_strap, r, 1); r+=1

        ul.addWidget(QLabel("Clock Theme:"), r, 0)
        self.cc = QComboBox()
        self.cc.addItems(["Analog Classic", "Analog Minimal", "Analog Neon", "Digital LED", "Digital Retro"])
        self.cc.setCurrentText(config.get("clock_style", "Analog Classic"))
        ul.addWidget(self.cc, r, 1); r+=1
        
        ul.addWidget(QLabel("Case Shape:"), r, 0)
        self.c_case = QComboBox()
        self.c_case.addItems(["Round", "Square", "Cushion", "Tonneau", "Octagonal (AP)"])
        self.c_case.setCurrentText(config.get("clock_case", "Round"))
        ul.addWidget(self.c_case, r, 1); r+=1
        
        ul.addWidget(QLabel("Bezel:"), r, 0)
        self.c_bezel = QComboBox()
        self.c_bezel.addItems(["Plain", "Fluted", "Diver", "GMT", "Coin-Edge"])
        self.c_bezel.setCurrentText(config.get("clock_bezel", "Plain"))
        ul.addWidget(self.c_bezel, r, 1); r+=1
        
        ul.addWidget(QLabel("Indices:"), r, 0)
        self.c_ind = QComboBox()
        self.c_ind.addItems(["None", "Arabic", "Roman", "Baton", "Dot", "California"])
        self.c_ind.setCurrentText(config.get("clock_indices", "Baton"))
        ul.addWidget(self.c_ind, r, 1); r+=1
        
        ul.addWidget(QLabel("Ticks:"), r, 0)
        self.c_ticks = QComboBox()
        self.c_ticks.addItems(["Standard", "Clean", "Railroad", "Crosshair"])
        self.c_ticks.setCurrentText(config.get("clock_ticks", "Standard"))
        ul.addWidget(self.c_ticks, r, 1); r+=1
        
        ul.addWidget(QLabel("Hands:"), r, 0)
        self.ch = QComboBox()
        self.ch.addItems(["Classic", "Spade", "Breguet", "Dauphine", "Alpha", "Pencil", "Serpentine", "Mercedes", "Sword", "Arrow", "Baton", "Snowflake", "Syringe", "Cathedral"])
        self.ch.setCurrentText(config.get("clock_hands", "Classic"))
        ul.addWidget(self.ch, r, 1); r+=1
        
        ul.addWidget(QLabel("Complication:"), r, 0)
        self.c_comp = QComboBox()
        self.c_comp.addItems(["None", "Date Window", "Small Seconds", "Chronograph", "Perpetual Calendar"])
        self.c_comp.setCurrentText(config.get("clock_comp", "None"))
        ul.addWidget(self.c_comp, r, 1); r+=1
        
        ul.addWidget(QLabel("Clock Numbers:"), r, 0)
        self.cn = QComboBox()
        self.cn.addItems(["None", "Arabic (1, 2, 3)", "Roman (I, II, III)"])
        self.cn.setCurrentText(config.get("clock_numbers", "None"))
        ul.addWidget(self.cn, r, 1); r+=1

        # --- TYPOGRAPHY ---
        ul.addWidget(QLabel("--- Typography ---", styleSheet="font-weight:bold; color:#0a84ff; padding-top:15px;"), r, 0, 1, 2); r+=1
        
        ul.addWidget(QLabel("Font Family:"), r, 0)
        self.fc = QComboBox()
        self.fc.addItems(["Helvetica Neue", "Georgia", "Arial"])
        self.fc.setCurrentText(config.get("font_family", "Helvetica Neue"))
        ul.addWidget(self.fc, r, 1); r+=1

        ul.addWidget(QLabel("Custom Font (.ttf/.otf):"), r, 0)
        self.cf_lbl = QLabel(os.path.basename(config.get("custom_font_path", "")) or "None")
        self.cf_lbl.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        ul.addWidget(self.cf_lbl, r, 1); r+=1
        cf_btn = QPushButton("Select Custom Font")
        cf_btn.clicked.connect(self.select_font)
        ul.addWidget(cf_btn, r, 0, 1, 2); r+=1
        
        ul.addWidget(QLabel("Size:"), r, 0)
        self.ss = QSpinBox()
        self.ss.setRange(10,36)
        self.ss.setValue(int(config.get("font_size", 16)))
        ul.addWidget(self.ss, r, 1); r+=1

        # --- PRODUCTIVITY & AUDIO ---
        ul.addWidget(QLabel("--- Productivity & Alerts ---", styleSheet="font-weight:bold; color:#0a84ff; padding-top:15px;"), r, 0, 1, 2); r+=1
        
        ul.addWidget(QLabel("Deadline Name:"), r, 0)
        self.dl_name = QLineEdit()
        self.dl_name.setText(config.get("deadline_name", "Goal"))
        ul.addWidget(self.dl_name, r, 1); r+=1
        
        ul.addWidget(QLabel("Deadline Date/Time:"), r, 0)
        self.dl_date = QDateTimeEdit()
        self.dl_date.setDisplayFormat("yyyy-MM-dd HH:mm")
        try:
            self.dl_date.setDateTime(QDateTime.fromString(config.get("deadline_date", (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M")), "yyyy-MM-dd HH:mm"))
        except: 
            pass
        ul.addWidget(self.dl_date, r, 1); r+=1
        
        ul.addWidget(QLabel("Force Close Apps After (min):"), r, 0)
        self.fc_mins = QSpinBox()
        self.fc_mins.setValue(config.get("force_close_apps_mins", 5))
        ul.addWidget(self.fc_mins, r, 1); r+=1
        
        system_sounds = ["Basso", "Blow", "Bottle", "Frog", "Funk", "Glass", "Hero", "Morse", "Ping", "Pop", "Purr", "Sosumi", "Submarine", "Tink"]
        ul.addWidget(QLabel("App Distraction Sound:"), r, 0)
        self.snd_app_combo = QComboBox()
        self.snd_app_combo.addItems(system_sounds)
        self.snd_app_combo.setCurrentText(config.get("sound_app_dist", "Ping"))
        ul.addWidget(self.snd_app_combo, r, 1); r+=1
        
        ul.addWidget(QLabel("Camera Distraction Sound:"), r, 0)
        self.snd_cam_combo = QComboBox()
        self.snd_cam_combo.addItems(system_sounds)
        self.snd_cam_combo.setCurrentText(config.get("sound_cam_dist", "Basso"))
        ul.addWidget(self.snd_cam_combo, r, 1); r+=1
        
        ul.addWidget(QLabel("Camera Error Sound:"), r, 0)
        self.snd_cam_err = QComboBox()
        self.snd_cam_err.addItems(system_sounds)
        self.snd_cam_err.setCurrentText(config.get("sound_cam_err", "Hero"))
        ul.addWidget(self.snd_cam_err, r, 1); r+=1
        
        ul.addWidget(QLabel("Beep Frequency (sec):"), r, 0)
        self.beep_freq_spin = QSpinBox()
        self.beep_freq_spin.setRange(1, 60)
        self.beep_freq_spin.setValue(config.get("beep_freq", 3))
        ul.addWidget(self.beep_freq_spin, r, 1); r+=1
        
        ul.addWidget(QLabel("1m Distraction Loops:"), r, 0)
        self.l1m = QSpinBox()
        self.l1m.setRange(1, 100)
        self.l1m.setValue(config.get("loop_1m", 2))
        ul.addWidget(self.l1m, r, 1); r+=1
        
        ul.addWidget(QLabel("5m Distraction Loops:"), r, 0)
        self.l5m = QSpinBox()
        self.l5m.setRange(1, 100)
        self.l5m.setValue(config.get("loop_5m", 5))
        ul.addWidget(self.l5m, r, 1); r+=1
        
        ul.addWidget(QLabel("15m Distraction Loops:"), r, 0)
        self.l15m = QSpinBox()
        self.l15m.setRange(1, 100)
        self.l15m.setValue(config.get("loop_15m", 10))
        ul.addWidget(self.l15m, r, 1); r+=1
        
        ul.addWidget(QLabel("30m Distraction Loops:"), r, 0)
        self.l30m = QSpinBox()
        self.l30m.setRange(1, 100)
        self.l30m.setValue(config.get("loop_30m", 20))
        ul.addWidget(self.l30m, r, 1); r+=1
        
        ul.addWidget(QLabel("60m Distraction Loops:"), r, 0)
        self.l60m = QSpinBox()
        self.l60m.setRange(1, 100)
        self.l60m.setValue(config.get("loop_60m", 30))
        ul.addWidget(self.l60m, r, 1); r+=1
        
        ul.addWidget(QLabel("Distraction Phrase:"), r, 0)
        self.speech_dist_edit = QLineEdit()
        self.speech_dist_edit.setText(config.get("speech_dist", "You have been distracted. Please return to work."))
        ul.addWidget(self.speech_dist_edit, r, 1); r+=1
        
        ul.addWidget(QLabel("Completion Phrase:"), r, 0)
        self.speech_comp_edit = QLineEdit()
        self.speech_comp_edit.setText(config.get("speech_comp", "Fantastic job! Your deep work session is complete."))
        ul.addWidget(self.speech_comp_edit, r, 1); r+=1

        # --- VISION ENGINE ---
        ul.addWidget(QLabel("--- Vision Tracker ---", styleSheet="font-weight:bold; color:#0a84ff; padding-top:15px;"), r, 0, 1, 2); r+=1
        
        ul.addWidget(QLabel("Face Scale Factor:"), r, 0)
        self.fsf = QDoubleSpinBox()
        self.fsf.setRange(1.01, 2.0)
        self.fsf.setSingleStep(0.05)
        self.fsf.setValue(config.get("face_scale_factor", 1.2))
        ul.addWidget(self.fsf, r, 1); r+=1

        ul.addWidget(QLabel("Face Min Neighbors:"), r, 0)
        self.fmn = QSpinBox()
        self.fmn.setRange(1, 30)
        self.fmn.setValue(config.get("face_min_neighbors", 8))
        ul.addWidget(self.fmn, r, 1); r+=1

        ul.addWidget(QLabel("Face Min Size:"), r, 0)
        self.fms = QSpinBox()
        self.fms.setRange(20, 500)
        self.fms.setValue(config.get("face_min_size", 120))
        ul.addWidget(self.fms, r, 1); r+=1

        ul.addWidget(QLabel("Vision Sample Rate (ms):"), r, 0)
        self.vsi = QSpinBox()
        self.vsi.setRange(10, 5000)
        self.vsi.setSingleStep(10)
        self.vsi.setValue(config.get("vision_sample_interval", 30))
        ul.addWidget(self.vsi, r, 1); r+=1
        
        ul.addWidget(QLabel("Distraction Delay (s):"), r, 0)
        self.dds = QSpinBox()
        self.dds.setRange(1,60)
        self.dds.setValue(int(config.get("dist_delay", 3)))
        ul.addWidget(self.dds, r, 1); r+=1
        
        ul.addWidget(QLabel("Vision Mode:"), r, 0)
        self.vm = QComboBox()
        self.vm.addItems(["Strict (Face & Eyes)", "Visible (Face Only)", "Presence (Motion/Whiteboard)"])
        self.vm.setCurrentText(config.get("vision_mode", "Strict (Face & Eyes)"))
        ul.addWidget(self.vm, r, 1); r+=1

        # --- SYSTEM & UI ---
        ul.addWidget(QLabel("--- UI & Paths ---", styleSheet="font-weight:bold; color:#0a84ff; padding-top:15px;"), r, 0, 1, 2); r+=1

        ul.addWidget(QLabel("Panel Opacity:"), r, 0)
        self.po = QSlider(Qt.Orientation.Horizontal)
        self.po.setRange(50, 255)
        self.po.setValue(int(config.get("panel_opacity", 180)))
        ul.addWidget(self.po, r, 1); r+=1

        ul.addWidget(QLabel("Background Image:"), r, 0)
        self.bg_lbl = QLabel(config.get("bg_image_path", "Default (Online/None)"))
        self.bg_lbl.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        ul.addWidget(self.bg_lbl, r, 1); r+=1
        
        bg_btn = QPushButton("Select Background")
        bg_btn.clicked.connect(self.select_bg)
        ul.addWidget(bg_btn, r, 0, 1, 2); r+=1

        ul.addWidget(QLabel("Quotes JSON:"), r, 0)
        self.qt_lbl = QLabel(config.get("quotes_path", "Default (Turing/CS)"))
        self.qt_lbl.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        ul.addWidget(self.qt_lbl, r, 1); r+=1
        
        qt_btn = QPushButton("Select Quotes")
        qt_btn.clicked.connect(self.select_quotes)
        ul.addWidget(qt_btn, r, 0, 1, 2); r+=1
        
        sb = QPushButton("Apply All Settings")
        sb.setStyleSheet("background-color: #30a14e; color: white; padding: 12px; font-weight: bold; margin-top: 15px;")
        sb.clicked.connect(self.sf)
        ul.addWidget(sb, r, 0, 1, 2)
        
        scr.setWidget(cw)
        lay.addWidget(scr)
        
        # --- ADD COURSE ---
        cf = QFrame()
        cf.setObjectName("Panel")
        cl = QVBoxLayout(cf)
        cl.addWidget(QLabel("Add Course", styleSheet="font-weight:bold; color:#0a84ff;"))
        self.ci = QLineEdit()
        self.ci.setPlaceholderText("Enter new course name...")
        cb = QPushButton("Save Course")
        cb.clicked.connect(self.ac)
        cl.addWidget(self.ci)
        cl.addWidget(cb)
        lay.addWidget(cf)

    def select_font(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Font", "", "Font Files (*.ttf *.otf)")
        if f:
            self.cf_lbl.setText(os.path.basename(f))
            config.set("custom_font_path", f)

    def select_bg(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Background Image", "", "Image Files (*.png *.jpg *.jpeg)")
        if f:
            self.bg_lbl.setText(f)
            config.set("bg_image_path", f)

    def select_quotes(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Quotes JSON", "", "JSON Files (*.json)")
        if f:
            self.qt_lbl.setText(f)
            config.set("quotes_path", f)

    def sf(self): 
        config.set("clock_brand", self.c_brand.currentText())
        config.set("clock_dial", self.c_dial.currentText())
        config.set("clock_strap", self.c_strap.currentText())
        config.set("clock_style", self.cc.currentText())
        config.set("clock_case", self.c_case.currentText())
        config.set("clock_bezel", self.c_bezel.currentText())
        config.set("clock_indices", self.c_ind.currentText())
        config.set("clock_ticks", self.c_ticks.currentText())
        config.set("clock_hands", self.ch.currentText())
        config.set("clock_comp", self.c_comp.currentText())
        config.set("clock_numbers", self.cn.currentText())
        
        config.set("font_family", self.fc.currentText())
        config.set("font_size", self.ss.value())
        
        config.set("deadline_name", self.dl_name.text())
        config.set("deadline_date", self.dl_date.dateTime().toString("yyyy-MM-dd HH:mm"))
        config.set("force_close_apps_mins", self.fc_mins.value())
        
        config.set("sound_app_dist", self.snd_app_combo.currentText())
        config.set("sound_cam_dist", self.snd_cam_combo.currentText())
        config.set("sound_cam_err", self.snd_cam_err.currentText())
        config.set("beep_freq", self.beep_freq_spin.value())
        
        config.set("loop_1m", self.l1m.value())
        config.set("loop_5m", self.l5m.value())
        config.set("loop_15m", self.l15m.value())
        config.set("loop_30m", self.l30m.value())
        config.set("loop_60m", self.l60m.value())
        
        config.set("speech_dist", self.speech_dist_edit.text())
        config.set("speech_comp", self.speech_comp_edit.text())
        
        config.set("face_scale_factor", self.fsf.value())
        config.set("face_min_neighbors", self.fmn.value())
        config.set("face_min_size", self.fms.value())
        config.set("vision_sample_interval", self.vsi.value())
        config.set("dist_delay", self.dds.value())
        config.set("vision_mode", self.vm.currentText())
        config.set("panel_opacity", self.po.value())
        
        bus.settings_changed.emit()
        
    def ac(self):
        if self.ci.text().strip():
            try: 
                import sqlite3
                db.c.execute("INSERT INTO courses (name) VALUES (?)", (self.ci.text().strip(),))
                db.conn.commit()
                self.ci.clear()
                bus.course_added.emit()
            except sqlite3.IntegrityError: 
                pass
EOF
