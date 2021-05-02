#!/usr/bin/python3


from typing import Optional
from PySide2.QtCore import Qt, Signal, Slot
from PySide2.QtGui import QMouseEvent
from PySide2.QtWidgets import QApplication, QCheckBox, QHBoxLayout, QWidget


class CheckBox(QWidget):
    stateChanged = Signal(bool)

    def __init__(self, state: Optional[bool] = False, parent: Optional[QWidget] = None) -> None:
        super(CheckBox, self).__init__(parent)

        self.checkbox = QCheckBox('', self)
        self.checkbox.setChecked(state)
        self.checkbox.stateChanged.connect(self.stateChanged.emit)
        self.setLayout(QHBoxLayout(self))
        self.layout().addWidget(self.checkbox)
        self.layout().setAlignment(Qt.AlignCenter)
        self.layout().setMargin(0)
        self.mousePressEvent = self.on_mousePressEvent

    def on_mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.checkbox.setChecked(not self.checkbox.isChecked())

    def setChecked(self, state: bool) -> None:
        self.checkbox.setChecked(state)


@Slot(bool)
def printState(state: bool):
    print(state)


if __name__ == '__main__':
    import sys

    app = QApplication(sys.argv)
    w = CheckBox()
    w.stateChanged.connect(printState)
    w.show()
    sys.exit(app.exec_())
