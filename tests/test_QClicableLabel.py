
from PySide2.QtCore import Qt, Signal
from PySide2.QtGui import QMouseEvent, QPalette
from PySide2.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QColorDialog


class QClicableLabel(QLabel):
    clicked = Signal()

    def __init__(self) -> None:
        super(QClicableLabel, self).__init__()
        self.mousePressEvent = self.on_mousePressEvent

    def on_mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()


class Widget(QWidget):
    def __init__(self, *args, **kwargs):
        QWidget.__init__(self, *args, **kwargs)
        lay = QVBoxLayout(self)
        self.label = QClicableLabel()
        self.label.setAutoFillBackground(True)
        self.label.setFixedSize(100, 100)
        self.label.clicked.connect(self.on_clicked)
        lay.addWidget(self.label)

    def on_clicked(self):
        sender: QClicableLabel = self.sender()
        color = QColorDialog.getColor()
        if color.isValid():
            palette = sender.palette()
            palette.setColor(QPalette.Background, color)
            sender.setPalette(palette)


if __name__ == '__main__':
    import sys

    app = QApplication(sys.argv)
    w = Widget()
    w.show()
    sys.exit(app.exec_())
