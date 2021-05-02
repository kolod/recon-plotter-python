#!/usr/bin/python3

from typing import Optional
from PySide2.QtCore import QLocale, QObject
from PySide2.QtGui import QValidator, QDoubleValidator
from PySide2.QtWidgets import QApplication


class DoubleValidator(QDoubleValidator):

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super(DoubleValidator, self).__init__(parent=parent)

    def validate(self, string: str, pos: int) -> QValidator.State:
        string = string.replace('.', QLocale().decimalPoint())
        string = string.replace(',', QLocale().decimalPoint())
        return super(DoubleValidator, self).validate(string, pos)


if __name__ == '__main__':
    import sys

    app = QApplication(sys.argv)

    val = DoubleValidator()
    print(val.validate('50.2', 0))
    print(val.validate('50,2', 0))
