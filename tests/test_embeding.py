import sys
from PySide2.QtCore import Slot
from PySide2.QtWidgets import QAction, QMenu, QMenuBar

import numpy as np

from matplotlib.backends.qt_compat import QtCore, QtWidgets
if QtCore.qVersion() >= "5.":
    from matplotlib.backends.backend_qt5agg import (
        FigureCanvas, NavigationToolbar2QT as NavigationToolbar)
else:
    from matplotlib.backends.backend_qt4agg import (
        FigureCanvas, NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure


class ApplicationWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.fig: Figure = Figure()

        self.plot: FigureCanvas = FigureCanvas(self.fig)
        self.setCentralWidget(self.plot)

        self.actionUpdate: QAction = QAction('Update', self)
        self.actionUpdate.setShortcut('F5')
        self.actionUpdate.triggered.connect(self.update)

        menubar: QMenuBar = self.menuBar()
        menuPlot: QMenu = menubar.addMenu('plot')
        menuPlot.addAction(self.actionUpdate)

    @Slot()
    def update(self):
        t = np.linspace(0, 10, 501)
        self.fig.clear()
        ax = self.fig.subplots()
        ax.plot(t, np.tan(t), ".")
        self.fig.tight_layout()
        self.fig.canvas.draw()


if __name__ == "__main__":
    # Check whether there is already a running QApplication (e.g., if running
    # from an IDE).
    qapp = QtWidgets.QApplication.instance()
    if not qapp:
        qapp = QtWidgets.QApplication(sys.argv)

    app = ApplicationWindow()
    app.show()
    app.activateWindow()
    app.raise_()
    qapp.exec_()
