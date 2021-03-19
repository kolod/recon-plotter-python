#!/usr/bin/python3

# Copyright 2021 Oleksandr Kolodkin <alexandr.kolodkin@gmail.com>.
# All rights reserved


import sys
import os
import numpy
from time import time
from typing import List
from PySide2.QtGui import QPalette
from PySide2.QtCore import QCoreApplication, QLocale, QSettings, Qt, QTranslator, QLibraryInfo, QStandardPaths, QEventLoop
from PySide2.QtWidgets import QApplication, QCheckBox, QDoubleSpinBox, QAbstractItemView,\
    QHBoxLayout, QLineEdit, QMainWindow, QHeaderView, QFileDialog, QAction, QDockWidget,\
    QLabel, QProgressBar, QScrollArea, QSizePolicy, QGridLayout, QSpinBox, QTableWidget, QWidget


class Signal(object):

    def __init__(self, name: str = '', unit: str = 'V', data: List[float] = None) -> None:
        self.selected: bool = False
        self.name: str = name
        self.unit: str = unit
        self.smooth: int = 1
        self.scale: float = 1.0
        self.data: List[float] = data or []
        self.maximum: float = float('-inf')
        self.minimum: float = float('inf')

    def smooth(self, n: int):
        window = numpy.ones(n)/n
        self.smooth = numpy.convolve(self.data, window, 'same')

    def setName(self, name: str) -> None:
        self.name = name

    def setUnit(self, unit: str) -> None:
        self.unit = unit

    def setSmooth(self, smooth: int) -> None:
        self.smooth = smooth

    def setSelected(self, selected: bool) -> None:
        self.selected = selected

    def setScale(self, scale: float) -> None:
        self.scale = scale

    def append(self, value: float) -> None:
        self.data.append(value)
        if self.maximum < value:
            self.maximum = value
        if self.minimum > value:
            self.minimum = value


class Recon(QMainWindow):
    def __init__(self) -> None:
        self.name: str = ''
        self.dataFileName: str = ''
        self.plotFileName: str = None
        self.times: list = []
        self.signals: List[Signal] = []
        self.progressBar: QProgressBar = None
        self.dockSignals: QDockWidget = None
        self.dockSignalsWidget: QTableWidget = None

        super().__init__()
        self.initialize()
        self.restoreSession()

    def initialize(self) -> None:
        self.setWindowTitle('Recon plotter')
        self.setMinimumSize(800, 200)

        # Add progress bar
        self.progressBar = QProgressBar(self.statusBar())
        self.progressBar.setMinimum(0)
        self.progressBar.setAlignment(Qt.AlignCenter)
        self.progressBar.hide()

#        image = QImage(800, 600, QImage.Format_ARGB32)

        imageLabel = QLabel(self)
        imageLabel.setBackgroundRole(QPalette.Base)
        imageLabel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        imageLabel.setScaledContents(False)
        # imageLabel.setPixmap(image.pi)

        scrollArea = QScrollArea(self)
        scrollArea.setBackgroundRole(QPalette.Dark)
        scrollArea.setWidget(imageLabel)
        scrollArea.setVisible(False)

        self.setCentralWidget(scrollArea)

        # Signals Dock
        self.dockSignals = QDockWidget(QCoreApplication.translate('SignalsDock', 'Signals'), self)
        self.dockSignals.setObjectName('DockSignals')
        self.dockSignalsWidget = QTableWidget(0, 7)
        self.dockSignalsWidget.setObjectName('DockSignalsWidget')
        self.dockSignalsWidget.setSelectionMode(QAbstractItemView.NoSelection)
        self.dockSignalsWidget.setHorizontalHeaderLabels([
            QCoreApplication.translate('SignalsDock', 'Selected'),
            QCoreApplication.translate('SignalsDock', 'Name'),
            QCoreApplication.translate('SignalsDock', 'Unit'),
            QCoreApplication.translate('SignalsDock', 'Smooth'),
            QCoreApplication.translate('SignalsDock', 'Scale'),
            QCoreApplication.translate('SignalsDock', 'Minimum'),
            QCoreApplication.translate('SignalsDock', 'Maximum'),
        ])
        header = self.dockSignalsWidget.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setForegroundRole(QPalette.Window)
        dockSignalsLayout = QGridLayout(self.dockSignalsWidget)
        dockSignalsLayout.setObjectName('DockSignalsLayout')
        self.dockSignals.setWidget(self.dockSignalsWidget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dockSignals)

        # File actions
        actionOpen = QAction(QCoreApplication.translate('Menu', '&Open...'), self)
        actionOpen.setShortcut(QCoreApplication.translate('Menu', 'Ctrl+O'))
        actionOpen.setStatusTip(QCoreApplication.translate('Menu', 'Open the recon data in the text format'))
        actionOpen.triggered.connect(self.openData)

        actionSave = QAction(QCoreApplication.translate('Menu', '&Save'), self)
        actionSave.setShortcut(QCoreApplication.translate('Menu', 'Ctrl+S'))
        actionSave.setStatusTip(QCoreApplication.translate('Menu', 'Save the recon data in the text format'))
        actionSave.triggered.connect(self.saveData)

        actionSaveAs = QAction(QCoreApplication.translate('Menu', 'Save &as...'), self)
        actionSaveAs.setShortcut(QCoreApplication.translate('Menu', 'Ctrl+Shift+S'))
        actionSaveAs.setStatusTip(QCoreApplication.translate('Menu', 'Save the recon data in the text format as...'))
        actionSaveAs.triggered.connect(self.saveDataAs)

        actionExit = QAction(QCoreApplication.translate('Menu', '&Exit'), self)
        actionExit.setShortcut(QCoreApplication.translate('Menu', 'Ctrl+Q'))
        actionExit.setStatusTip(QCoreApplication.translate('Menu', 'Exit application'))
        actionExit.triggered.connect(self.close)

        # Plot actions
        actionSavePlot = QAction(QCoreApplication.translate('Menu', '&Save plot'), self)
        actionSavePlot.setShortcut(QCoreApplication.translate('Menu', 'Ctrl+Alt+S'))
        actionSavePlot.setStatusTip(QCoreApplication.translate('Menu', 'Save plot'))
        actionSavePlot.triggered.connect(self.savePlot)

        actionSavePlotAs = QAction(QCoreApplication.translate('Menu', 'Save plot &as...'), self)
        actionSavePlotAs.setShortcut(QCoreApplication.translate('Menu', 'Ctrl+Alt+Shift+S'))
        actionSavePlotAs.setStatusTip(QCoreApplication.translate('Menu', 'Save plot as...'))
        actionSavePlotAs.triggered.connect(self.savePlotAs)

        # Viev actions
        actionSignalsDock = self.dockSignals.toggleViewAction()
        actionSignalsDock.setStatusTip(QCoreApplication.translate('Menu', 'Show/hide signals window'))

        # Help actions
        actionAboutQt = QAction(QCoreApplication.translate('Menu', 'About Qt...'), self)
        actionAboutQt.triggered.connect(QApplication.aboutQt)

        menubar = self.menuBar()
        menuFile = menubar.addMenu(QCoreApplication.translate('Menu', '&File'))
        menuPlot = menubar.addMenu(QCoreApplication.translate('Menu', '&Plot'))
        menuView = menubar.addMenu(QCoreApplication.translate('Menu', '&View'))
        menuHelp = menubar.addMenu(QCoreApplication.translate('Menu', '&Help'))

        menuFile.addActions([actionOpen, actionSave, actionSaveAs])
        menuFile.addSeparator()
        menuFile.addAction(actionExit)

        menuPlot.addActions([actionSavePlot, actionSavePlotAs])

        menuView.addAction(actionSignalsDock)

        menuHelp.addAction(actionAboutQt)

    def restoreSession(self) -> None:
        settings = QSettings()
        self.restoreGeometry(settings.value('geometry'))
        self.restoreState(settings.value('state'))

    def saveSession(self) -> None:
        settings = QSettings()
        settings.setValue('geometry', self.saveGeometry())
        settings.setValue('state', self.saveState())

    def closeEvent(self, event) -> None:
        self.saveSession()
        event.accept()

    def rebuildSignalsDock(self) -> None:

        self.dockSignalsWidget.clearContents()
        self.dockSignalsWidget.setRowCount(len(self.signals))

        for i in range(len(self.signals)):

            # Checkbox
            widget = QWidget(self.dockSignalsWidget)
            layout = QHBoxLayout(widget)
            checkBox = QCheckBox('', widget)
            checkBox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            layout.addWidget(checkBox)
            layout.setAlignment(Qt.AlignCenter)
            layout.setMargin(0)
            checkBox.stateChanged.connect(self.signals[i].setSelected)
            self.dockSignalsWidget.setCellWidget(i, 0, widget)

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

    def progressBegin(self, total: int) -> None:
        self.progressBar.setMaximum(total)
        self.progressBar.setValue(0)
        self.statusBar().addWidget(self.progressBar, 100)
        self.progressBar.show()

    def progressUpdate(self, current: int) -> None:
        self.progressBar.setValue(current)
        QCoreApplication.processEvents(QEventLoop.AllEvents)

    def progressEnd(self) -> None:
        self.statusBar().removeWidget(self.progressBar)

    def openData(self) -> None:
        try:
            dialog = QFileDialog(self)
            dialog.setAcceptMode(QFileDialog.AcceptOpen)
            dialog.setDirectory(QSettings().value('default_data_path', QStandardPaths.standardLocations(QStandardPaths.DocumentsLocation)[0]))
            dialog.setNameFilter(QCoreApplication.translate('FileDialog', 'Recon data files(*.txt)'))
            dialog.setWindowTitle(QCoreApplication.translate('FileDialog', 'Open recon data file'))
            dialog.fileSelected.connect(self._load)
            dialog.open()
        except Exception as e:
            print(e)

    def saveData(self):
        if os.path.isfile(self.dataFileName):
            self._save(self.dataFileName)
        else:
            self.saveDataAs()

    def saveDataAs(self):
        try:
            dialog = QFileDialog(self)
            dialog.setAcceptMode(QFileDialog.AcceptSave)
            dialog.setDirectory(QSettings().value('default_data_path', QStandardPaths.standardLocations(QStandardPaths.DocumentsLocation)[0]))
            dialog.setNameFilter(QCoreApplication.translate('FileDialog', 'Recon data files(*.txt)'))
            dialog.setWindowTitle(QCoreApplication.translate('FileDialog', 'Save recon data file'))
            dialog.fileSelected.connect(self._save)
            dialog.open()
        except Exception as e:
            print(e)

    def savePlot(self) -> None:
        if os.path.isfile(self.plotFileName):
            self.savePlotAs()
        else:
            self._savePlot(self.plotFileName)

    def savePlotAs(self) -> None:
        dialog = QFileDialog(self)
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setDirectory(QSettings().value('default_plot_path', QStandardPaths.standardLocations(QStandardPaths.DocumentsLocation)[0]))
        dialog.setNameFilter(QCoreApplication.translate('FileDialog', 'PNG Image(*.png);;SVG Image(*.svg);;PDF Document(*.pdf)'))
        dialog.setWindowTitle(QCoreApplication.translate('FileDialog', 'Save plot'))
        dialog.fileSelected.connect(self._savePlot)
        dialog.open()

    def _load(self, filename: str) -> None:
        if os.path.isfile(filename):
            self.filename = filename

            # Save path for next use
            QSettings().setValue('default_data_path', os.path.dirname(os.path.abspath(filename)))

            # Change window title
            self.setWindowTitle(QCoreApplication.translate('Main', 'Recon plotter - {0}').format(self.filename))

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

    def _save(self, filename: str) -> None:
        with open(filename, 'w', encoding='cp1251') as df:

            self.progressBegin(len(self.times))
            lasttime = time()

            # write header
            df.write(f'{filename},,\n\n')

            # write signals descriptions
            for i in range(len(self.signals)):
                ak = str(f'АК-{i+1}')
                df.write(f'{i+2:4d},{ak:>6s}, {self.signals[i].name}\n')
            df.write('\n         1,              2,')
            for i in range(len(self.signals)):
                df.write(f'{i:10d},')
            df.write('\n         N,              t,')
            for i in range(len(self.signals)):
                ak = str(f'АК-{i+1}')
                df.write(f'{ak:>10s},')
            df.write('\n          ,              s,')
            for i in range(len(self.signals)):
                df.write(f'{self.signals[i].unit:>10s},')
            df.write('\n')

            # write data
            for i in range(len(self.times)):

                # Update progress avery 100 milliseconds
                newtime = time()
                if (newtime - lasttime > 0.1):
                    lasttime = newtime
                    self.progressUpdate(i)

                # add data row
                df.write(f'{i:10d},{self.times[i]:15.6f},')
                for j in range(len(self.signals)):
                    df.write(f'{self.signals[j].data[i]:10.3f},')
                df.write('\n')

            self.progressEnd()

            # Change window title
            self.dataFileName = filename
            self.setWindowTitle(QCoreApplication.translate('Main', 'Recon plotter - {0}').format(self.filename))

    def _savePlot(self, filename: str) -> None:
        pass


if __name__ == "__main__":

    app = QApplication(sys.argv)
    app.setOrganizationName('Oleksandr Kolodkin')
    app.setApplicationName('Recon Plotter')

    qtTranslator = QTranslator(app)
    qtTranslator.load('_qt' + QLocale.system().name(), QLibraryInfo.location(QLibraryInfo.TranslationsPath))
    app.installTranslator(qtTranslator)

    myTranslator = QTranslator(app)
    myTranslator.load(QLocale(), 'recon', '_', '.', '.qm')
    app.installTranslator(myTranslator)

    window = Recon()
    window.show()
    sys.exit(app.exec_())
