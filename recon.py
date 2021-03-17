#!/usr/bin/python3

# Copyright 2021 Oleksandr Kolodkin <alexandr.kolodkin@gmail.com>.
# All rights reserved


from datetime import date
import sys, os, numpy
from time import time
from typing import List
from PySide2.QtGui import QImage, QPalette, QImage
from PySide2.QtCore import QCoreApplication, QLocale, QSettings, Qt, QTranslator, QLibraryInfo, QStandardPaths, QEventLoop
from PySide2.QtWidgets import QApplication, QCheckBox, QDoubleSpinBox, QLineEdit,  QMainWindow, QFileDialog, QAction, QDockWidget, QLabel, QProgressBar, QScrollArea, QSizePolicy, QGridLayout, QSpinBox, QTableWidget, QWidget, QSpacerItem
from numpy.lib.shape_base import column_stack


class Signal:

    def __init__(self, name:str = '', unit:str = 'V', data:list = []) -> None:
        self.selected:bool = False
        self.name:str = name
        self.unit:str = unit
        self.smooth:int = 1
        self.scale:float = 1.0
        self.data:List[float] = data
        self.maximum:float = float('-inf')
        self.minimum:float = float('inf')

    def smooth(self, n:int):
        window = numpy.ones(n)/n
        self.smooth = numpy.convolve(self.data, window, 'same')

    def setName(self, name:str) -> None:
        self.name = name

    def setUnit(self, unit:str) -> None:
        self.unit = unit

    def setSmooth(self, smooth:int) -> None:
        self.smooth = smooth

    def setSelected(self, selected:bool) -> None:
        self.selected = selected

    def setScale(self, scale: float) -> None:
        self.scale = scale

    def append(self, value:float) -> None:
        self.data.append(value)
        if self.maximum < value:
            self.maximum = value
        if self.minimum > value:
            self.minimum = value


class Recon(QMainWindow):
    def __init__(self):
        self.name:str = ''
        self.filename:str = ''
        self.plotName:str = None
        self.times:list = []
        self.signals:List[Signal] = []
        self.progressBar:QProgressBar = None
        self.dockSignals:QDockWidget = None
        self.dockSignalsWidget:QTableWidget = None

        super().__init__()
        self.initialize()
        self.restoreSession()

    def initialize(self):
        self.setWindowTitle('Recon plotter')
        self.setMinimumSize(800, 200)

        # Add progress bar
        self.progressBar = QProgressBar(self.statusBar())
        self.progressBar.setMinimum(0)
        self.progressBar.setAlignment(Qt.AlignCenter)
        self.progressBar.hide()

        image = QImage(800, 600, QImage.Format_ARGB32)

        imageLabel = QLabel(self)
        imageLabel.setBackgroundRole(QPalette.Base)
        imageLabel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        imageLabel.setScaledContents(False)
        #imageLabel.setPixmap(image.pi)

        scrollArea = QScrollArea(self)
        scrollArea.setBackgroundRole(QPalette.Dark)
        scrollArea.setWidget(imageLabel)
        scrollArea.setVisible(False)

        self.setCentralWidget(scrollArea)

        # Signals Dock
        self.dockSignals = QDockWidget('Signals', self)
        self.dockSignals.setObjectName('DockSignals')
        self.dockSignalsWidget = QTableWidget(0, 7)
        self.dockSignalsWidget.setObjectName('DockSignalsWidget')
        self.dockSignalsWidget.setHorizontalHeaderLabels([
            self.tr('Selected'),
            self.tr('Name'),
            self.tr('Unit'),
            self.tr('Smooth'),
            self.tr('Scale'),
            self.tr('Minimum'),
            self.tr('Maximum'),
        ])
        dockSignalsLayout = QGridLayout(self.dockSignalsWidget)
        dockSignalsLayout.setObjectName('DockSignalsLayout')
        self.dockSignals.setWidget(self.dockSignalsWidget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dockSignals)

        actionExit = QAction(self.tr('&Exit'), self)
        actionExit.setShortcut(self.tr('Ctrl+Q'))
        actionExit.setStatusTip(self.tr('Exit application'))
        actionExit.triggered.connect(self.close)

        actionOpen = QAction(self.tr('&Open...'), self)
        actionOpen.setShortcut(self.tr('Ctrl+O'))
        actionOpen.setStatusTip(self.tr('Open the recon data in the text format'))
        actionOpen.triggered.connect(self.open)

        actionSave = QAction(self.tr('&Save'), self)
        actionSave.setShortcut(self.tr('Ctrl+S'))
        actionSave.setStatusTip(self.tr('Save plot'))
        actionSave.triggered.connect(self.save)

        actionSaveAs = QAction(self.tr('Save &as...'), self)
        actionSaveAs.setShortcut(self.tr('Ctrl+Shift+S'))
        actionSaveAs.setStatusTip(self.tr('Save plot as...'))
        actionSaveAs.triggered.connect(self.saveAs)

        actionSignalsDock = self.dockSignals.toggleViewAction()
        actionSignalsDock.setStatusTip(self.tr('Show/hide signals window'))

        actionAboutQt = QAction(self.tr('About Qt...'), self)
        actionAboutQt.triggered.connect(QApplication.aboutQt)

        menubar = self.menuBar()
        menuFile = menubar.addMenu(self.tr('&File'))
        menuView = menubar.addMenu(self.tr('&View'))
        menuHelp = menubar.addMenu(self.tr('&Help'))

        menuFile.addAction(actionOpen)
        menuFile.addSeparator()
        menuFile.addAction(actionSave)
        menuFile.addAction(actionSaveAs)
        menuFile.addSeparator()
        menuFile.addAction(actionExit)

        menuView.addAction(actionSignalsDock)

        menuHelp.addAction(actionAboutQt)

    def restoreSession(self):
        settings = QSettings()
        self.restoreGeometry(settings.value('geometry'))
        self.restoreState(settings.value('state'))

    def saveSession(self):
        settings = QSettings()
        settings.setValue('geometry', self.saveGeometry())
        settings.setValue('state', self.saveState())

    def closeEvent(self, event):
        self.saveSession()
        event.accept()

    def open(self):
        try:
            dialog = QFileDialog(self)
            dialog.setAcceptMode(QFileDialog.AcceptOpen)
            dialog.setDirectory(QSettings().value('default_path', QStandardPaths.DocumentsLocation))
            dialog.setNameFilter(self.tr('Recon data files(*.txt)'))
            dialog.setWindowTitle(self.tr('Open recon data file'))
            dialog.fileSelected.connect(self.load)
            dialog.open()
        except Exception as e:
            print(e)

    def load(self, filename:str):
        if os.path.isfile(filename):
            self.filename = filename

            # Save path for next use
            QSettings().setValue('default_path', os.path.dirname(os.path.abspath(filename)))

            # Change window title
            self.setWindowTitle(self.tr('Recon plotter - {0}').format(self.filename))

            # Reset signals
            self.times.clear()
            self.signals.clear()

            # Open data file
            with open(self.filename, 'r', encoding='cp1251') as df:

                # Get total size
                total = os.fstat(df.fileno()).st_size
                self.progressBegin(total)

                # Get name of the recon record
                if line := df.readline():
                    if len(line):
                        self.name = line.split(',')[0]

                # Get signal names
                while (line := df.readline()) != '':
                    if line.startswith('         1'):
                        continue
                    if line.startswith('         N'):
                        break
                    if len(line) and line != '\n':
                        data = line.split(',')
                        if len(data) >= 3:
                            self.signals.append(Signal(data[2].strip()))

                # Update progress
                self.progressUpdate(df.tell())
                lasttime = time()

                # Get signal data
                while line := df.readline():
                    values = line.split(',')
                    if len(values) == (len(self.signals) + 3):
                        if values[0].strip() == 'N':
                            continue
                        if values[0].strip() == '':
                            for i in range(len(self.signals)):
                                self.signals[i].unit = values[i+2].strip()
                            continue
                        for i in range(len(self.signals)):
                            self.signals[i].append(float(values[i+2].strip()))
                        self.times.append(float(values[1].strip()))

                    # Update progress avery 100 milliseconds
                    newtime = time()
                    if (newtime - lasttime > 0.1):
                        lasttime = newtime
                        self.progressUpdate(df.tell())

            self.progressEnd()
            self.rebuildSignalsDock()

    def rebuildSignalsDock(self):

        self.dockSignalsWidget.clearContents()
        self.dockSignalsWidget.setRowCount(len(self.signals))


        for i in range(len(self.signals)):

            # Checkbox
            checkBox = QCheckBox('', self.dockSignalsWidget)
            checkBox.stateChanged.connect(self.signals[i].setSelected)
            self.dockSignalsWidget.setCellWidget(i, 0, checkBox)

            # Signal name
            nameWidget = QLineEdit(self.dockSignalsWidget)
            nameWidget.setFrame(False)
            nameWidget.setText(self.signals[i].name)
            nameWidget.setAlignment(Qt.AlignCenter)
            nameWidget.textChanged.connect(self.signals[i].setName)
            self.dockSignalsWidget.setCellWidget(i, 1, nameWidget)

            # Signal unit
            unitWidget = QLineEdit(self.dockSignalsWidget)
            unitWidget.setFrame(False)
            unitWidget.setText(self.signals[i].unit)
            unitWidget.setAlignment(Qt.AlignCenter)
            unitWidget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            unitWidget.textChanged.connect(self.signals[i].setUnit)
            self.dockSignalsWidget.setCellWidget(i, 2, unitWidget)

            # Smooth level
            smoothWidget = QSpinBox(self.dockSignalsWidget)
            smoothWidget.setFrame(False)
            smoothWidget.setValue(self.signals[i].smooth)
            smoothWidget.setRange(1, 1000000)
            smoothWidget.setAlignment(Qt.AlignCenter)
            smoothWidget.valueChanged.connect(self.signals[i].setSmooth)
            smoothWidget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            self.dockSignalsWidget.setCellWidget(i, 3, smoothWidget)

            # Scale
            scaleWidget = QDoubleSpinBox(self.dockSignalsWidget)
            scaleWidget.setFrame(False)
            scaleWidget.setAlignment(Qt.AlignCenter)
            scaleWidget.setValue(self.signals[i].scale)
            scaleWidget.valueChanged.connect(self.signals[i].setScale)
            scaleWidget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            self.dockSignalsWidget.setCellWidget(i, 4, scaleWidget)

            # Minimum
            minWidget = QLineEdit(self.dockSignalsWidget)
            minWidget.setFrame(False)
            minWidget.setAlignment(Qt.AlignCenter)
            minWidget.setReadOnly(True)
            minWidget.setText(f'{self.signals[i].minimum:g}')
            minWidget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            self.dockSignalsWidget.setCellWidget(i, 5, minWidget)

            # Maximum
            maxWidget = QLineEdit(self.dockSignalsWidget)
            maxWidget.setFrame(False)
            maxWidget.setAlignment(Qt.AlignCenter)
            maxWidget.setReadOnly(True)
            maxWidget.setText(f'{self.signals[i].maximum:g}')
            maxWidget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            self.dockSignalsWidget.setCellWidget(i, 6, maxWidget)

    def progressBegin(self, total:int) -> None:
        self.progressBar.setMaximum(total)
        self.progressBar.setValue(0)
        self.statusBar().addWidget(self.progressBar, 100)
        self.progressBar.show()

    def progressUpdate(self, current:int) -> None:
        self.progressBar.setValue(current)
        QCoreApplication.processEvents(QEventLoop.AllEvents)

    def progressEnd(self) -> None:
        self.statusBar().removeWidget(self.progressBar)

    def save(self):
        if self.plotName is None:
            self.saveAs()
        else:
            self.savePlot(self.plotName)

    def saveAs(self):
        try:
            dialog = QFileDialog(self)
            dialog.setAcceptMode(QFileDialog.AcceptSave)
            dialog.setDirectory(QSettings().value('default_path', '/home'))
            dialog.setNameFilter(self.tr('PNG Image(*.png);;SVG Image(*.svg);;PDF Document(*.pdf)'))
            dialog.setWindowTitle(self.tr('Save plot'))
            dialog.fileSelected.connect(self.savePlot)
            dialog.open()
        except Exception as e:
            print(e)

    def savePlot(self, filename:str) -> None:
        pass


if __name__ == "__main__":
    qtTranslator = QTranslator()
    qtTranslator.load('_qt' + QLocale.system().name(), QLibraryInfo.location(QLibraryInfo.TranslationsPath))

    myTranslator = QTranslator()
    myTranslator.load(QLocale(), 'recon', '_', '.')

    app = QApplication([])
    app.setOrganizationName('Oleksandr Kolodkin')
    app.setApplicationName('Recon Plotter')
    app.installTranslator(qtTranslator)
    app.installTranslator(myTranslator)

    window = Recon()
    window.show()
    sys.exit(app.exec_())
