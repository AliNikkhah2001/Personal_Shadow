"""Clock, dialogs, body scans, and PDF library actions."""

from __future__ import annotations

import base64
import contextlib
import json
import os

try:
    import pymupdf
except ImportError:
    try:
        import fitz as pymupdf
    except ImportError:
        pymupdf = None

if pymupdf is None:
    print("WARNING: pymupdf not available. PDF functionality will be disabled.")

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, Qt, QTime
from PyQt6.QtGui import QBrush, QColor, QImage, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QFileDialog

from core_sys import config
from horology import draw_clock_complications, draw_clock_face, draw_clock_ticks_and_indices, draw_horological_hand
from ui import TimelapseDialog


class MediaActionsMixin:
    """Render clocks and handle media-oriented bridge actions."""

    def emit_clock(self):
        try:
            img = QImage(300, 300, QImage.Format.Format_ARGB32_Premultiplied)
            img.fill(Qt.GlobalColor.transparent)
            painter = QPainter(img)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            radius = 120
            painter.translate(150, 150)

            style = config.get("clock_style", "Analog Classic")
            hand_style = config.get("clock_hands", "Classic")
            complication = config.get("clock_complication", "None")

            if "Minimal" in style:
                bg_col = QColor(0, 0, 0, 80)
                hand_col = QColor("white")
            elif "Neon" in style:
                bg_col = QColor(10, 132, 255, 50)
                hand_col = QColor("white")
            else:
                bg_col = QColor(15, 15, 17, 220)
                hand_col = QColor("white")

            draw_clock_face(painter, radius, bg_col)
            draw_clock_ticks_and_indices(painter, radius)
            draw_clock_complications(painter, radius)

            current_time = QTime.currentTime()

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(hand_col))

            painter.save()
            painter.rotate(30.0 * (current_time.hour() + current_time.minute() / 60.0))
            draw_horological_hand(painter, hand_style, 60, 4, True)
            painter.restore()
            painter.save()
            painter.rotate(6.0 * (current_time.minute() + current_time.second() / 60.0))
            draw_horological_hand(painter, hand_style, 90, 3, False)
            painter.restore()

            sec_col = QColor("#0a84ff")
            if complication == "Small Seconds":
                painter.save()
                painter.translate(0, int(radius - 40))
                painter.setBrush(QBrush(sec_col))
                painter.setPen(QPen(sec_col, 1))
                painter.rotate(6.0 * current_time.second())
                painter.drawLine(0, 0, 0, -15)
                painter.restore()
            else:
                painter.setBrush(QBrush(sec_col))
                painter.setPen(QPen(sec_col, 2))
                painter.save()
                painter.rotate(6.0 * current_time.second())
                if hand_style in ["Serpentine", "Sword", "Arrow"]:
                    draw_horological_hand(painter, hand_style, 100, 1, False)
                else:
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRect(-1, 0, 2, -100)
                painter.restore()

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("white")))
            painter.drawEllipse(-4, -4, 8, 8)
            painter.end()

            buf = QByteArray()
            buffer = QBuffer(buf)
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            img.save(buffer, "PNG")

            raw_bytes = bytes(buf) if hasattr(buf, "__bytes__") else bytes(buf.data())
            encoded = base64.b64encode(raw_bytes).decode("utf-8")
            self.clock_feed.emit(f"data:image/png;base64,{encoded}")
        except Exception as e:
            print(f"Horology render failed: {e}")

    def _handle_play_timelapse(self, req):
        try:
            path = req.get("path")
            if os.path.exists(path):
                if not hasattr(self, "tl_dlg"):
                    self.tl_dlg = None
                self.tl_dlg = TimelapseDialog(
                    path,
                    req.get("duration", 0),
                    req.get("distractions", 0),
                    req.get("data", {}),
                )
                self.tl_dlg.show()
                self.tl_dlg.raise_()
                self.tl_dlg.activateWindow()
        except Exception:
            import traceback

            print("Timelapse Playback Error:", traceback.format_exc())
        return json.dumps({"status": "ok"})

    def _handle_save_file(self, req):
        parent = QApplication.activeWindow()
        ext = req.get("ext", "txt")
        content = req.get("content", "")
        title = req.get("title", "Export")
        file_path, _ = QFileDialog.getSaveFileName(parent, "Save File", f"{title}.{ext}", f"Files (*.{ext})")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return json.dumps({"status": "saved", "path": file_path})
            except Exception as e:
                return json.dumps({"status": "error", "message": str(e)})
        return json.dumps({"status": "cancelled"})

    def _handle_set_vision_ui(self, req):
        self.vision.ui_active = req.get("active", False)
        return json.dumps({"status": "ok"})

    def _handle_toggle_feed(self, req):
        self.feed_active = req.get("enabled", False)
        return json.dumps({"status": "ok"})

    def _handle_open_file_dialog(self, req):
        parent = QApplication.activeWindow()
        file_path, _ = QFileDialog.getOpenFileName(
            parent,
            "Select a file",
            "",
            "All Files (*.*);;JSON (*.json);;Images (*.png *.jpg)",
        )
        return json.dumps({"path": file_path if file_path else ""})

    def _handle_open_folder_dialog(self, req):
        parent = QApplication.activeWindow()
        folder_path = QFileDialog.getExistingDirectory(parent, "Select a folder", "")
        return json.dumps({"path": folder_path if folder_path else ""})

    def _handle_lib_list(self, req):
        lib_files = []
        if os.path.exists(self.lib_path):
            for filename in os.listdir(self.lib_path):
                if filename.lower().endswith(".pdf"):
                    full_path = os.path.join(self.lib_path, filename)
                    lib_files.append(
                        {
                            "name": filename,
                            "path": full_path,
                            "size": os.path.getsize(full_path),
                        }
                    )
        return json.dumps({"files": lib_files})

    def _handle_lib_open(self, req):
        filename = req.get("filename")
        path = os.path.join(self.lib_path, filename)
        if os.path.exists(path):
            try:
                if self.active_pdf:
                    self.active_pdf.close()
                self.active_pdf = pymupdf.open(path)
                self.active_pdf_name = filename
                return json.dumps({"status": "ok", "total_pages": len(self.active_pdf)})
            except Exception as e:
                return json.dumps({"error": f"Failed to open PDF: {str(e)}"})
        return json.dumps({"error": f"File not found at {path}"})

    def _handle_lib_page(self, req):
        page_num = req.get("page", 0)
        zoom = req.get("zoom", 1.5)
        if self.active_pdf and 0 <= page_num < len(self.active_pdf):
            page = self.active_pdf[page_num]
            mat = pymupdf.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            img_data = pix.tobytes("png")
            encoded = base64.b64encode(img_data).decode("utf-8")

            annots = []
            annot = page.first_annot
            while annot:
                info = annot.info
                annots.append(
                    {
                        "subject": info.get("subject", "Unknown"),
                        "title": info.get("title", ""),
                        "content": info.get("content", ""),
                    }
                )
                annot = annot.next

            return json.dumps(
                {
                    "b64": encoded,
                    "width": pix.width,
                    "height": pix.height,
                    "annots": annots,
                }
            )
        return json.dumps({"error": "Invalid page"})

    def _handle_lib_annot(self, req):
        page_num = req.get("page")
        rect_coords = req.get("rect")
        tool = req.get("tool")
        text = req.get("text", "")

        if self.active_pdf and 0 <= page_num < len(self.active_pdf):
            page = self.active_pdf[page_num]
            x0, y0, x1, y1 = rect_coords
            pdf_rect = pymupdf.Rect(x0, y0, x1, y1)

            dirty = False
            if tool in ["Highlight", "Underline"]:
                words = page.get_text("words")
                quads = [pymupdf.Rect(word[:4]) for word in words if pymupdf.Rect(word[:4]).intersects(pdf_rect)]
                if quads:
                    annot = page.add_highlight_annot(quads) if tool == "Highlight" else page.add_underline_annot(quads)
                    annot.set_colors(stroke=(1, 1, 0) if tool == "Highlight" else (0, 0, 1))
                    annot.set_info(
                        info={
                            "title": "Web UI",
                            "subject": tool,
                            "content": "Marked via Web UI",
                        }
                    )
                    annot.update()
                    dirty = True
            elif tool == "Note":
                annot = page.add_text_annot(pdf_rect.tl, text)
                annot.set_info(info={"title": "Web UI", "subject": "Note", "content": text})
                annot.update()
                dirty = True

            if dirty:
                with contextlib.suppress(Exception):
                    self.active_pdf.save(
                        self.active_pdf.name,
                        incremental=True,
                        encryption=pymupdf.PDF_ENCRYPT_KEEP,
                    )
            return json.dumps({"status": "ok"})
        return json.dumps({"error": "Failed to add annotation"})

    def _handle_lib_open_native(self, req):
        try:
            from native_pdf_editor import NativePDFEditor

            filename = req.get("filename")
            filepath = os.path.join(self.lib_path, filename)
            if os.path.exists(filepath):
                if not hasattr(self, "pdf_editors"):
                    self.pdf_editors = []
                editor = NativePDFEditor(filepath)
                editor.show()
                self.pdf_editors.append(editor)
                return json.dumps({"status": "opened"})
            return json.dumps({"error": f"File not found at {filepath}"})
        except Exception as e:
            import traceback

            print(traceback.format_exc())
            return json.dumps({"error": f"Native boot failure: {e!s}"})

    def _handle_get_processes(self, req):
        return json.dumps(
            {
                "processes": [
                    {"name": p["name"], "pid": p["pid"], "cpu": p["cpu"], "memory": p["memory"]}
                    for p in self.get_running_processes()[:50]
                ],
            }
        )

    def _handle_get_app_monitoring_status(self, req):
        return json.dumps(
            {
                "enabled": config.get("app_monitoring_enabled", False),
                "allowed_apps": config.get("allowed_apps", []),
                "blocked_apps": config.get("blocked_apps", []),
                "auto_block": config.get("auto_block", False),
            }
        )

    def _handle_set_allowed_apps(self, req):
        apps = req.get("apps", [])
        config.set("allowed_apps", apps)
        return json.dumps({"status": "ok", "allowed_apps": apps})

    def _handle_set_blocked_apps(self, req):
        apps = req.get("apps", [])
        config.set("blocked_apps", apps)
        return json.dumps({"status": "ok", "blocked_apps": apps})

    def _handle_set_app_monitoring(self, req):
        enabled = req.get("enabled", False)
        config.set("app_monitoring_enabled", enabled)
        return json.dumps({"status": "ok", "enabled": enabled})

    def _handle_set_auto_block(self, req):
        enabled = req.get("enabled", False)
        config.set("auto_block", enabled)
        return json.dumps({"status": "ok", "auto_block": enabled})

    def _handle_check_distractions(self, req):
        return json.dumps({"distractions": self.check_processes_for_distraction()})

    def _handle_import_body_scan(self, req):
        parent = QApplication.activeWindow()
        file_path, _ = QFileDialog.getOpenFileName(
            parent,
            "Select Body Scan Image",
            "",
            "Images (*.png *.jpg *.jpeg)",
        )
        if not file_path:
            return json.dumps({"status": "cancelled"})

        try:
            from health_parser import BodyScanParser

            parser = BodyScanParser(rois_file="rois.json")
            data = parser.parse_image(file_path)

            if not data:
                return json.dumps({"status": "error", "message": "Failed to parse image."})

            data["file_path"] = file_path
            return json.dumps({"status": "success", "parsed_data": data})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})
