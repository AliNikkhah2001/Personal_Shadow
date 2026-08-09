import os, json, subprocess, cv2
from datetime import datetime, timedelta
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QTimer, QRect, QRectF, QUrl
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QPixmap, QImage
from PyQt6.QtMultimedia import QSoundEffect
from core.config import config
from core.database import db
from core.signals import bus
from core.utils import get_color, get_active_app, trigger_mac_notification, speak_text, max_volume
from vision.tracker import VisionTracker
from ui.overlay import OverlayWidget
from ui.dialogs import SessionStartDialog, AppWhitelistDialog, WebcamCheckDialog, AutoPlanDialog, TimelapseDialog
from ui.charts import GanttTimelineWidget

class ProductivityWidget(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        
        self.snd_app = QSoundEffect()
        self.snd_vis = QSoundEffect()
        self.snd_cam_err = QSoundEffect()
        
        self.sw = QSoundEffect()
        self.sw.setSource(QUrl.fromLocalFile("/System/Library/Sounds/Glass.aiff"))
        self.sw.setVolume(1.0)
        
        self.sb = QSoundEffect()
        self.sb.setSource(QUrl.fromLocalFile("/System/Library/Sounds/Tink.aiff"))
        self.sb.setVolume(1.0)
        
        self.upd_audio_files()
        
        self.tbs = QTabWidget()
        
        self.pt = QWidget()
        sl = QVBoxLayout(self.pt)
        
        al = QHBoxLayout()
        self.qc = QComboBox()
        self.ld_c()
        bus.course_added.connect(self.ld_c)
        
        self.qd = QSpinBox()
        self.qd.setSuffix(" m")
        self.qd.setValue(25)
        
        self.qt = QComboBox()
        self.qt.addItems(["Work", "Break"])
        self.qt.currentTextChanged.connect(self.t_chg)
        
        ba = QPushButton("+ Add")
        ba.clicked.connect(self.a_q)
        b_ap = QPushButton("Auto-Plan Day")
        b_ap.clicked.connect(self.auto_plan)
        be = QPushButton("Edit")
        be.clicked.connect(self.e_q)
        br = QPushButton("- Remove")
        br.clicked.connect(self.r_q)
        bc = QPushButton("Clear All")
        bc.clicked.connect(self.c_q)
        
        al.addWidget(self.qc)
        al.addWidget(self.qd)
        al.addWidget(self.qt)
        al.addWidget(ba)
        al.addWidget(b_ap)
        al.addWidget(be)
        al.addWidget(br)
        al.addWidget(bc)
        sl.addLayout(al)
        
        self.ql = QListWidget()
        self.ql.setStyleSheet("background: transparent; border: 1px solid rgba(255,255,255,20); border-radius: 6px;")
        self.ql.itemClicked.connect(self.pop_edit)
        sl.addWidget(self.ql)
        
        self.tl = GanttTimelineWidget()
        sl.addWidget(self.tl)
        
        pc = QHBoxLayout()
        self.lbl = QLabel("00:00")
        self.lbl.setObjectName("DigitalTimeText")
        bs = QPushButton("Start/Resume")
        bs.clicked.connect(self.sts)
        bp = QPushButton("Pause")
        bp.clicked.connect(self.pas)
        bx = QPushButton("Stop")
        bx.setObjectName("DangerButton")
        bx.clicked.connect(self.sps)
        
        pc.addWidget(self.lbl)
        pc.addStretch()
        pc.addWidget(bs)
        pc.addWidget(bp)
        pc.addWidget(bx)
        sl.addLayout(pc)
        self.tbs.addTab(self.pt, "Timeline")
        
        self.vt = QWidget()
        cl = QVBoxLayout(self.vt)
        self.cd = QLabel("Offline")
        self.cd.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cd.setStyleSheet("background:#000; border:1px solid #fff; border-radius:8px;")
        self.cd.setFixedSize(640, 480)
        self.tcb = QCheckBox("Enable Vision Tracker & Timelapse")
        self.tcb.stateChanged.connect(self.tgt)
        cl.addWidget(self.cd, alignment=Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(self.tcb, alignment=Qt.AlignmentFlag.AlignCenter)
        self.tbs.addTab(self.vt, "Vision")
        
        self.mt = QWidget()
        ml = QVBoxLayout(self.mt)
        adl = QHBoxLayout()
        self.ti = QLineEdit()
        self.ti.setPlaceholderText("Enter task...")
        self.qcb = QComboBox()
        self.qcb.addItems(["Urgent & Important", "Not Urgent & Important", "Urgent & Not Important", "Not Urgent & Not Important"])
        bt = QPushButton("Add Task")
        bt.clicked.connect(self.add_t)
        adl.addWidget(self.ti)
        adl.addWidget(self.qcb)
        adl.addWidget(bt)
        ml.addLayout(adl)
        
        self.g = QGridLayout()
        self.qs = {}
        for t,r,c in [("Urgent & Important",0,0), ("Not Urgent & Important",0,1), ("Urgent & Not Important",1,0), ("Not Urgent & Not Important",1,1)]:
            bx_f = QFrame()
            bx_f.setStyleSheet("border: 1px solid rgba(255,255,255,20); border-radius: 8px;")
            qll = QVBoxLayout(bx_f)
            qll.addWidget(QLabel(t))
            sa = QScrollArea()
            sa.setWidgetResizable(True)
            cw = QWidget()
            vl = QVBoxLayout(cw)
            vl.setAlignment(Qt.AlignmentFlag.AlignTop)
            sa.setWidget(cw)
            qll.addWidget(sa)
            self.qs[t] = vl
            self.g.addWidget(bx_f, r, c)
            
        ml.addLayout(self.g)
        self.tbs.addTab(self.mt, "Matrix")
        lay.addWidget(self.tbs)
        
        self.sq = []
        self.cidx = -1
        self.tt = 0
        self.tr = 0
        self.st = "Stopped"
        self.s_dist = 0
        self.ps = None
        self.cur_vid = ""
        self.alw_apps = []
        self.app_ok = True
        self.vis_ok = True
        self.dist_type = "None"
        self.beep_ctr = 0
        
        self.tmr = QTimer(self)
        self.tmr.timeout.connect(self.tk)
        self.f_tmr = QTimer(self)
        self.f_tmr.timeout.connect(self.chk_fcs)
        
        self.vtr = VisionTracker()
        bus.settings_changed.connect(self.vtr.upd_settings)
        bus.settings_changed.connect(self.upd_audio_files)
        self.vtr.err_msg.connect(self.err)
        self.vtr.frame_ready.connect(self.upc)
        self.vtr.att_lost.connect(self.al)
        self.vtr.att_restored.connect(self.ar)
        
        self.ovl = OverlayWidget()
        self.ld_db_q()
        self.ld_t()
        bus.db_updated.connect(self.upq)
        bus.db_updated.connect(self.ld_t)

    def upd_audio_files(self):
        self.snd_app.setSource(QUrl.fromLocalFile(f"/System/Library/Sounds/{config.get('sound_app_dist', 'Ping')}.aiff"))
        self.snd_vis.setSource(QUrl.fromLocalFile(f"/System/Library/Sounds/{config.get('sound_cam_dist', 'Basso')}.aiff"))
        self.snd_app.setVolume(1.0)
        self.snd_vis.setVolume(1.0)

    def ld_c(self): 
        self.qc.clear()
        self.qc.addItem("General")
        try:
            db.c.execute("SELECT title FROM cascading_goals")
            for r in db.c.fetchall(): 
                self.qc.addItem(r[0])
        except Exception:
            pass
        
    def t_chg(self, t): 
        if t == "Break": 
            self.qc.setDisabled(True)
        else: 
            self.qc.setDisabled(False)

    def auto_plan(self):
        db.c.execute("SELECT title FROM cascading_goals")
        courses = [r[0] for r in db.c.fetchall()]
        dlg = AutoPlanDialog(courses, self)
        if dlg.exec():
            plan = dlg.get_plan()
            for p in plan:
                self.sq.append({"course": p["course"], "duration": p["duration"], "type": p["type"], "distractions": [], "worked": 0, "start_time": None})
            self.sv_db_q()
            self.upq()
        
    def ld_db_q(self):
        db.c.execute("SELECT course, duration, type, distractions, worked, timelapse_path, start_time FROM queue ORDER BY list_order")
        self.sq = [{"course": r[0], "duration": r[1], "type": r[2], "distractions": json.loads(r[3] if r[3] else "[]"), "worked": r[4] or 0, "timelapse_path": r[5] or "", "start_time": r[6] if len(r)>6 else None} for r in db.c.fetchall()]
        self.upq()
        
    def sv_db_q(self):
        db.c.execute("DELETE FROM queue")
        for i, b in enumerate(self.sq): 
            db.c.execute("INSERT INTO queue (course, duration, type, list_order, distractions, worked, timelapse_path, start_time) VALUES (?,?,?,?,?,?,?,?)", (b['course'], b['duration'], b['type'], i, json.dumps(b.get('distractions',[])), b.get('worked', 0), b.get('timelapse_path', ''), b.get('start_time', None)))
        db.conn.commit()
        
    def a_q(self): 
        self.sq.append({"course": "Break" if self.qt.currentText()=="Break" else self.qc.currentText(), "duration": self.qd.value(), "type": self.qt.currentText(), "distractions": [], "worked": 0, "start_time": None})
        self.sv_db_q()
        self.upq()
        
    def pop_edit(self, item): 
        idx = self.ql.row(item)
        b = self.sq[idx]
        self.qc.setCurrentText("General" if b['course']=="Break" else b['course'])
        self.qd.setValue(b['duration'])
        self.qt.setCurrentText(b['type'])
        
    def e_q(self):
        r = self.ql.currentRow()
        if r >= 0: 
            self.sq[r]['course'] = "Break" if self.qt.currentText()=="Break" else self.qc.currentText()
            self.sq[r]['duration'] = self.qd.value()
            self.sq[r]['type'] = self.qt.currentText()
            self.sv_db_q()
            self.upq()
            
    def r_q(self): 
        if self.ql.currentRow() >= 0: 
            self.sq.pop(self.ql.currentRow())
            self.sv_db_q()
            self.upq()
            
    def c_q(self): 
        self.sq.clear()
        self.sv_db_q()
        self.upq()

    def upq(self):
        self.ql.clear()
        pl_mins = 0
        st_proj = datetime.now()
        
        for i, b in enumerate(self.sq):
            rem = max(0, b['duration'] - b.get('worked', 0))
            if i < self.cidx: 
                it = QListWidgetItem(f"[Done] [{b['type']}] {b['course']}")
                it.setForeground(QColor("gray"))
            elif i == self.cidx: 
                et = st_proj + timedelta(minutes=rem)
                ds = f" (+{sum(d[1] for d in b.get('distractions',[])):.1f}m delay)" if b.get('distractions') else ""
                it = QListWidgetItem(f"[Active] [{b['type']}] {b['course']} ({rem:.1f}m left) [Ends: {et.strftime('%H:%M')}]{ds}")
                it.setBackground(QColor(10, 132, 255, 80))
                st_proj = et
            else:
                et = st_proj + timedelta(minutes=rem)
                it = QListWidgetItem(f"[{st_proj.strftime('%H:%M')} - {et.strftime('%H:%M')}] [{b['type']}] {b['course']}")
                st_proj = et

            self.ql.addItem(it)
            if b['type'] == 'Work' and i >= self.cidx: 
                pl_mins += rem
            
        self.tl.update_t(self.sq, self.cidx, self.st, self.ps)
        db.c.execute("SELECT sum(duration) FROM pomodoro_sessions WHERE type='Work' AND date(timestamp) = date('now')")
        tdy_studied = db.c.fetchone()[0] or 0
        bus.progress_update.emit(tdy_studied, tdy_studied + pl_mins)
        
        if self.cidx >= 0 and self.cidx < len(self.sq):
            bus.active_color_changed.emit(get_color(self.sq[self.cidx]['course']))
        else:
            bus.active_color_changed.emit(QColor("#0a84ff"))

    def chk_fcs(self):
        if self.st in ["Paused", "Attention Lost - Paused"] and self.ps is not None:
            abs_mins = (datetime.now() - self.ps).total_seconds() / 60.0
            
            kill_time = config.get("force_close_apps_mins", 5.0)
            if abs_mins >= kill_time:
                p_win = self.window()
                if p_win:
                    p_win.setWindowState(p_win.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
                    p_win.raise_()
                    p_win.activateWindow()
                
                subprocess.run(["osascript", "-e", 'tell application "System Events" to set visible of process "Terminal" to false'])
                subprocess.run(["osascript", "-e", 'tell application "System Events" to set visible of process "python" to false'])
                subprocess.run(["osascript", "-e", 'tell application "System Events" to set visible of process "Python" to false'])
                
                try:
                    out = subprocess.run(["osascript", "-e", 'tell application "System Events" to get name of every application process whose background only is false'], capture_output=True, text=True)
                    open_apps = [x.strip() for x in out.stdout.split(",") if x.strip()]
                    safe_sys = ["python", "Python", "Terminal", "Finder", "loginwindow", "WindowManager", "ControlCenter", "NotificationCenter", "Siri", "Spotlight", "Second Brain OS"]
                    for app_name in open_apps:
                        if app_name not in self.alw_apps and app_name not in safe_sys:
                            subprocess.run(["osascript", "-e", f'tell application "{app_name}" to quit'])
                except: 
                    pass

            self.beep_ctr += 1
            freq = max(1, config.get("beep_freq", 3))
            
            if self.beep_ctr % freq == 0:
                msg = config.get("speech_dist", "You are distracted.")
                loops = 1
                if abs_mins >= 60.0: loops = config.get("loop_60m", 30)
                elif abs_mins >= 30.0: loops = config.get("loop_30m", 20)
                elif abs_mins >= 15.0: loops = config.get("loop_15m", 10)
                elif abs_mins >= 5.0: loops = config.get("loop_5m", 5)
                elif abs_mins >= 1.0: loops = config.get("loop_1m", 2)
                
                subprocess.run(["osascript", "-e", "set volume output volume 100"])
                if self.dist_type == "Camera":
                    self.snd_vis.setLoopCount(loops)
                    self.snd_vis.play()
                else:
                    self.snd_app.setLoopCount(loops)
                    self.snd_app.play()
                
                if self.beep_ctr % (freq * 4) == 0:
                    speak_text(msg)
                    trigger_mac_notification("Focus Alert", f"Sustained distraction level: {int(abs_mins)}m off task!")

        if self.st not in ["Focus", "Attention Lost - Paused"]: 
            return
            
        act = get_active_app()
        if act in ["", "loginwindow", "WindowManager", "ControlCenter", "NotificationCenter", "Spotlight", "Siri"]: 
            self.app_ok = True
        else: 
            self.app_ok = (not self.alw_apps) or (act in self.alw_apps)
        
        all_good = self.vis_ok and self.app_ok
        
        if self.st == "Focus" and not all_good:
            self.s_dist += 1
            self.ps = datetime.now()
            self.tmr.stop()
            self.beep_ctr = 0
            
            subprocess.run(["osascript", "-e", "set volume output volume 100"])
            if not self.vis_ok: 
                self.dist_type = "Camera"
                self.snd_vis.setLoopCount(2)
                self.snd_vis.play()
                bus.attention_alert.emit("Camera")
            else: 
                self.dist_type = "App"
                self.snd_app.setLoopCount(2)
                self.snd_app.play()
                bus.attention_alert.emit("App")
                
            self.st = "Attention Lost - Paused"
            bus.timer_tick.emit("PAUSED", self.st, 0)
            self.vtr.stop_rec()
            self.upq()
            
        elif self.st == "Attention Lost - Paused" and all_good:
            bus.attention_alert.emit("None")
            self.sts()

    def initiate_work_sequence(self):
        ready_dlg = SessionStartDialog(self)
        if not ready_dlg.exec():
            self.trigger_start_distraction("Camera")
            return
            
        try:
            out = subprocess.run(["osascript", "-e", 'tell application "System Events" to get name of every application process whose background only is false'], capture_output=True, text=True)
            apps = [x.strip() for x in out.stdout.split(",") if x.strip()]
        except: 
            apps = []
            
        dlg = AppWhitelistDialog(apps, self)
        if not dlg.exec(): 
            self.trigger_start_distraction("App")
            return
            
        self.alw_apps = dlg.get_allowed()

        if self.tcb.isChecked():
            wdlg = WebcamCheckDialog(self.vtr, self)
            if not wdlg.exec():
                self.trigger_start_distraction("Camera")
                return
                
        self.tmr.start(1000)
        self.ovl.show()
        if self.tcb.isChecked():
            self.vtr.start()
            self.vtr.start_rec(self.cur_vid)
            
    def trigger_start_distraction(self, dtype):
        self.s_dist += 1
        self.ps = datetime.now()
        self.st = "Attention Lost - Paused"
        self.dist_type = dtype
        self.ovl.show()
        subprocess.run(["osascript", "-e", "set volume output volume 100"])
        if dtype == "Camera":
            self.snd_vis.setLoopCount(3)
            self.snd_vis.play()
        else:
            self.snd_app.setLoopCount(3)
            self.snd_app.play()
        bus.timer_tick.emit("PAUSED", self.st, 0)
        bus.attention_alert.emit(dtype)
        self.upq()

    def sts(self):
        if not self.sq: return
        
        if self.st in ["Paused", "Attention Lost - Paused"]:
            if self.ps and self.cidx >= 0:
                d_mins = (datetime.now() - self.ps).total_seconds() / 60.0
                self.sq[self.cidx]['distractions'].append((self.sq[self.cidx]['worked'], d_mins, self.dist_type))
                self.sv_db_q()
                
            self.st = "Focus" if self.sq[self.cidx]['type'] == "Work" else "Break"
            bus.attention_alert.emit("None")
            self.upq()
            
            if self.st == "Focus" and self.sq[self.cidx].get('worked', 0) == 0:
                self.initiate_work_sequence()
            else:
                self.tmr.start(1000)
                self.ovl.show()
                if self.st == "Focus" and self.tcb.isChecked(): 
                    self.vtr.start()
                    self.vtr.start_rec(self.cur_vid)
            return
            
        if self.cidx == -1 or self.st == "Stopped":
            try:
                c = cv2.VideoCapture(0)
                if not c.isOpened(): 
                    QMessageBox.critical(self, "Camera", "Camera permission required!")
                    return
                c.release()
            except: 
                QMessageBox.critical(self, "Camera", "Camera blocked by macOS.")
                return
                
            self.cidx = 0
            for i, b in enumerate(self.sq):
                if b.get('worked',0) < b['duration']: 
                    self.cidx = i
                    break
                    
            self.f_tmr.start(1000)
            self.plc()

    def pas(self):
        if self.tmr.isActive(): 
            self.tmr.stop()
            self.st = "Paused"
            self.dist_type = "Pause"
            self.ps = datetime.now()
            self.lbl.setText(self.lbl.text() + " [PAUSED]")
            self.vtr.stop_rec()
            self.upq()

    def plc(self):
        if self.cidx >= len(self.sq): 
            self.sps()
            QMessageBox.information(self, "Done", "Sequence Complete!")
            return
            
        b = self.sq[self.cidx]
        if not b.get('start_time'):
            b['start_time'] = datetime.now().isoformat()
        
        self.st = "Focus" if b['type'] == "Work" else "Break"
        self.tt = b['duration'] * 60
        self.tr = self.tt - int(b.get('worked', 0) * 60)
        self.ps = None
        self.s_dist = 0
        self.vis_ok = True
        self.app_ok = True
        self.dist_type = "None"
        self.beep_ctr = 0
        
        self.upq()
        
        course_safe = b['course'].replace(' ', '_').replace('/', '')
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.cur_vid = f"timelapses/Work_{course_safe}_{ts}.avi"
        b['timelapse_path'] = self.cur_vid

        if self.st == "Focus":
            self.initiate_work_sequence()
        else:
            self.tmr.start(1000)
            self.ovl.show()

    def sps(self):
        self.f_tmr.stop()
        self.tmr.stop()
        bus.attention_alert.emit("None")
        self.st = "Stopped"
        self.lbl.setText("00:00")
        bus.timer_tick.emit("00:00", self.st, 0)
        self.cidx = -1
        self.upq()
        self.vtr.stop_rec()
        self.ovl.hide()

    def tk(self):
        if self.tr > 0:
            self.tr -= 1
            m, s = divmod(self.tr, 60)
            self.lbl.setText(f"{m:02d}:{s:02d}")
            self.sq[self.cidx]['worked'] = (self.tt - self.tr) / 60.0
            bus.timer_tick.emit(f"{m:02d}:{s:02d}", self.st, 100 - int((self.tr/self.tt)*100) if self.tt > 0 else 0)
            if self.tr % 10 == 0: 
                self.sv_db_q()
        else:
            b = self.sq[self.cidx]
            if b['type'] == 'Work':
                self.sw.play()
                speak_text(config.get("speech_comp", "Great job!"))
            else:
                self.sb.play()
                
            self.vtr.stop_rec()
            try: 
                db.c.execute("INSERT INTO pomodoro_sessions (course, duration, actual_duration, timestamp, type, distractions, timelapse_path) VALUES (?,?,?,?,?,?,?)", (b['course'], b['duration'], b['duration']+sum(d[1] for d in b.get('distractions',[])), datetime.now().isoformat(), b['type'], self.s_dist, self.cur_vid if b['type']=='Work' else ""))
            except: 
                pass
                
            if b['type'] == 'Work':
                meta = {
                    "course": b['course'],
                    "date": datetime.now().isoformat(),
                    "duration_planned_mins": b['duration'],
                    "duration_actual_mins": b['duration'] + sum(d[1] for d in b.get('distractions',[])),
                    "distraction_count": self.s_dist,
                    "distractions": b.get('distractions', [])
                }
                try:
                    with open(self.cur_vid.replace('.avi', '.json'), 'w') as f:
                        json.dump(meta, f, indent=4)
                except:
                    pass
                
            b['worked'] = b['duration']
            db.conn.commit()
            bus.db_updated.emit()
            
            if b['type'] == 'Work':
                if os.path.exists(self.cur_vid): 
                    TimelapseDialog(self.cur_vid, b['duration'], self.s_dist, b).exec()
            
            self.cidx += 1
            self.plc()

    def add_t(self):
        if self.ti.text().strip(): 
            db.c.execute("INSERT INTO todos (task, is_done, quadrant) VALUES (?, 0, ?)", (self.ti.text().strip(), self.qcb.currentText()))
            db.conn.commit()
            self.ti.clear()
            bus.db_updated.emit()
            
    def ld_t(self):
        for l in self.qs.values():
            for i in reversed(range(l.count())): 
                w = l.itemAt(i).widget()
                if w: w.deleteLater()
                
        db.c.execute("SELECT id, task, quadrant FROM todos WHERE is_done=0")
        for tid, txt, q in db.c.fetchall():
            cb = QCheckBox(txt)
            cb.stateChanged.connect(lambda s, t=tid: self.c_t(t, s))
            if q in self.qs: 
                self.qs[q].addWidget(cb)
                
    def c_t(self, tid, s):
        if s == 2: 
            self.sw.play()
            db.c.execute("UPDATE todos SET is_done=1 WHERE id=?", (tid,))
            db.conn.commit()
            QTimer.singleShot(400, lambda: bus.db_updated.emit())
            
    def tgt(self, s):
        if s==2: 
            self.cd.setText("Initializing...")
            self.vtr.start()
        else: 
            self.vtr.stop()
            self.cd.clear()
            self.cd.setText("Offline")
            
    def err(self, m):
        self.tcb.blockSignals(True)
        self.tcb.setChecked(False)
        self.tcb.blockSignals(False)
        self.cd.setText(m)
        self.vis_ok = False
        bus.attention_alert.emit("Camera")
        
    def upc(self, img): 
        self.cd.setPixmap(QPixmap.fromImage(img).scaled(640, 480, Qt.AspectRatioMode.KeepAspectRatio))
        
    def al(self): 
        self.vis_ok = False
        
    def ar(self): 
        self.vis_ok = True