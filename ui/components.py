from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout

class GlassPanel(QFrame):
    def __init__(self, parent=None, layout_type="V"):
        super().__init__(parent)
        self.setObjectName("GlassPanel")
        if layout_type == "V":
            self.lay = QVBoxLayout(self)
        else:
            self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(15, 15, 15, 15)
