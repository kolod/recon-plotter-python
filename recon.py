#!/usr/bin/python3

# Copyright 2021 Oleksandr Kolodkin <alexandr.kolodkin@gmail.com>.
# All rights reserved


import sys
import os
import numpy
from time import time
from typing import List, Optional
import matplotlib.pyplot as plt
from PySide2.QtGui import QColor, QValidator, QDoubleValidator, QIntValidator, QPalette, QMouseEvent, QBrush, QPixmap
from PySide2.QtCore import QObject, Signal, QCoreApplication, QLocale, QSettings, Qt, QTranslator, QLibraryInfo, QStandardPaths, QEventLoop, QTemporaryFile
from PySide2.QtWidgets import QApplication, QCheckBox, QAbstractItemView, QFormLayout,\
    QHBoxLayout, QLineEdit, QMainWindow, QHeaderView, QFileDialog, QAction, QDockWidget,\
    QLabel, QProgressBar, QScrollArea, QSizePolicy, QGridLayout, QTableWidget, QWidget,\
    QStyleFactory, QColorDialog


class ClicableLabel(QLabel):
    clicked = Signal()

    def __init__(self, text: str, parent: QWidget) -> None:
        super(ClicableLabel, self).__init__(text, parent)
        self.mousePressEvent = self.on_mousePressEvent

    def on_mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()


class DoubleValidator(QDoubleValidator):

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super(DoubleValidator, self).__init__(parent=parent)

    def validate(self, string: str, pos: int) -> QValidator.State:
        string = string.replace('.', QLocale().decimalPoint())
        string = string.replace(',', QLocale().decimalPoint())
        return super(DoubleValidator, self).validate(string, pos)


class AnalogSignal(QObject):

    def __init__(self, name: str = '', unit: str = 'V', data: List[float] = None) -> None:
        super(AnalogSignal, self).__init__()
        self.selected: bool = False
        self.name: str = name
        self.unit: str = unit
        self.smooth: int = 1
        self.scale: float = 1.0
        self.data: List[float] = data or []
        self.maximum: float = float('-inf')
        self.minimum: float = float('inf')
        self.color: str = 'green'

    def smoothed(self):
        window = numpy.ones(self.smooth)/self.smooth
        smooth = numpy.convolve(self.data, window, 'same')
        return smooth

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

    def setColor(self, color: str) -> None:
        self.color = color

    def append(self, value: float) -> None:
        self.data.append(value)
        if self.maximum < value:
            self.maximum = value
        if self.minimum > value:
            self.minimum = value

    def _color(self):
        sender: ClicableLabel = self.sender()
        color = QColorDialog.getColor()
        if color.isValid():
            palette = sender.palette()
            palette.setColor(QPalette.Base, color)
            sender.setPalette(palette)
            sender.setText(color.name())
            self.color = color.name()


class Recon(QMainWindow):
    def __init__(self) -> None:
        self.name: str = ''
        self.dataFileName: str = ''
        self.plotFileName: str = None
        self.times: list = []
        self.signals: List[AnalogSignal] = []
        self.progressBar: QProgressBar = None
        self.dockSignals: QDockWidget = None
        self.dockSignalsWidget: QTableWidget = None
        self.title: str = ''
        self.axisX: str = ''
        self.axisY: str = ''
        self.min_x: float = None
        self.min_y: float = None
        self.max_x: float = None
        self.max_y: float = None

        super().__init__()
        self.initialize()
        self.restoreSession()

    def setTitle(self, title: str) -> None:
        self.title = title

    def setAxisX(self, axisX: str) -> None:
        self.axisX = axisX

    def setAxisY(self, axisY: str) -> None:
        self.axisY = axisY

    def setMinX(self, value: float) -> None:
        self.min_x = value

    def setMinY(self, value: float) -> None:
        self.min_y = value

    def setMaxX(self, value: float) -> None:
        self.max_x = value

    def setMaxY(self, value: float) -> None:
        self.max_y = value

    def autoRange(self):
        if len(self.times) and len(self.signals):

            # X range
            self.min_x = 0
            self.max_x = self.times[-1]

            # Y range
            self.min_y = float('inf')
            self.max_y = float('-inf')
            for signal in self.signals:
                self.min_y = min(self.min_y, signal.minimum * signal.scale)
                self.max_y = max(self.max_y, signal.maximum * signal.scale)

            # Update validators
            self.validatorMinX.setBottom(self.min_x)
            self.validatorMinX.setTop(self.max_x)
            self.validatorMaxX.setBottom(self.min_x)
            self.validatorMaxX.setTop(self.max_x)
            self.validatorMinY.setBottom(self.min_y)
            self.validatorMinY.setTop(self.max_y)
            self.validatorMaxY.setBottom(self.min_y)
            self.validatorMaxY.setTop(self.max_y)

            # Update range
            self.widgetMinX.setText(str(self.min_x))
            self.widgetMinY.setText(str(self.min_y))
            self.widgetMaxX.setText(str(self.max_x))
            self.widgetMaxY.setText(str(self.max_y))

    def initialize(self) -> None:
        self.setWindowTitle('Recon plotter')
        self.setMinimumSize(800, 200)

        # Add progress bar
        self.progressBar = QProgressBar(self.statusBar())
        self.progressBar.setMinimum(0)
        self.progressBar.setAlignment(Qt.AlignCenter)
        self.progressBar.hide()

        # Add plot display
        centralwidget = QWidget(self)
        gridLayout = QGridLayout(centralwidget)
        scrollArea = QScrollArea(centralwidget)
        scrollArea.setWidgetResizable(True)
        scrollAreaWidgetContents = QWidget()
        self.imageLabel = QLabel(scrollAreaWidgetContents)
        self.imageLabel.setScaledContents(False)
        scrollArea.setWidget(scrollAreaWidgetContents)
        gridLayout.addWidget(scrollArea, 0, 0, 1, 1)

        self.setCentralWidget(centralwidget)

        # Plot Settings Dock
        self.plotSettingsDock = QDockWidget(QCoreApplication.translate('PlotSettingsDock', 'Plot Settings'), self)
        self.plotSettingsDock.setObjectName('PlotSettingsDock')
        self.plotSettingsWidget = QWidget()
        self.plotSettingsLayout = QFormLayout(self.plotSettingsWidget)
        self.plotSettingsLayout.setObjectName('PlotSettingsLayout')
        self.plotSettingsLayout.setLabelAlignment(Qt.AlignRight)

        # Title
        self.labelTitle = QLabel(QCoreApplication.translate('PlotSettingsDock', 'Title:'), self.plotSettingsWidget)
        self.widgetTitle = QLineEdit(self.plotSettingsWidget)
        self.widgetTitle.setAlignment(Qt.AlignCenter)
        self.widgetTitle.textChanged.connect(self.setTitle)
        self.plotSettingsLayout.addRow(self.labelTitle, self.widgetTitle)

        # X Axis label
        self.labelAxisX = QLabel(QCoreApplication.translate('PlotSettingsDock', 'X axis label:'), self.plotSettingsWidget)
        self.widgetAxisX = QLineEdit(self.plotSettingsWidget)
        self.widgetAxisX.setAlignment(Qt.AlignCenter)
        self.widgetAxisX.textChanged.connect(self.setAxisX)
        self.plotSettingsLayout.addRow(self.labelAxisX, self.widgetAxisX)

        # Y Axis label
        self.labelAxisY = QLabel(QCoreApplication.translate('PlotSettingsDock', 'Y axis label:'), self.plotSettingsWidget)
        self.widgetAxisY = QLineEdit(self.plotSettingsWidget)
        self.widgetAxisY.setAlignment(Qt.AlignCenter)
        self.widgetAxisY.textChanged.connect(self.setAxisY)
        self.plotSettingsLayout.addRow(self.labelAxisY, self.widgetAxisY)

        # Minimum X
        self.labelMinX = QLabel(QCoreApplication.translate('PlotSettingsDock', 'X from:'), self.plotSettingsWidget)
        self.widgetMinX = QLineEdit(self.plotSettingsWidget)
        self.validatorMinX = DoubleValidator(self.widgetMinX)
        self.validatorMinX.setDecimals(3)
        self.widgetMinX.setValidator(self.validatorMinX)
        self.widgetMinX.setAlignment(Qt.AlignCenter)
        self.widgetMinX.textChanged.connect(self.setMinX)
        self.plotSettingsLayout.addRow(self.labelMinX, self.widgetMinX)

        # Maximum X
        self.labelMaxX = QLabel(QCoreApplication.translate('PlotSettingsDock', 'X to:'), self.plotSettingsWidget)
        self.widgetMaxX = QLineEdit(self.plotSettingsWidget)
        self.validatorMaxX = DoubleValidator(self.widgetMinX)
        self.validatorMaxX.setDecimals(3)
        self.widgetMaxX.setValidator(self.validatorMaxX)
        self.widgetMaxX.setAlignment(Qt.AlignCenter)
        self.widgetMaxX.textChanged.connect(self.setMaxX)
        self.plotSettingsLayout.addRow(self.labelMaxX, self.widgetMaxX)

        # Minimum Y
        self.labelMinY = QLabel(QCoreApplication.translate('PlotSettingsDock', 'Y from:'), self.plotSettingsWidget)
        self.widgetMinY = QLineEdit(self.plotSettingsWidget)
        self.validatorMinY = DoubleValidator(self.widgetMinY)
        self.validatorMinY.setDecimals(3)
        self.widgetMinY.setValidator(self.validatorMinY)
        self.widgetMinY.setAlignment(Qt.AlignCenter)
        self.widgetMinY.textChanged.connect(self.setMinY)
        self.plotSettingsLayout.addRow(self.labelMinY, self.widgetMinY)

        # Maximum Y
        self.labelMaxY = QLabel(QCoreApplication.translate('PlotSettingsDock', 'Y to:'), self.plotSettingsWidget)
        self.widgetMaxY = QLineEdit(self.plotSettingsWidget)
        self.validatorMaxY = DoubleValidator(self.widgetMinY)
        self.validatorMaxY.setDecimals(3)
        self.widgetMaxY.setValidator(self.validatorMaxY)
        self.widgetMaxY.setAlignment(Qt.AlignCenter)
        self.widgetMaxY.textChanged.connect(self.setMaxY)
        self.plotSettingsLayout.addRow(self.labelMaxY, self.widgetMaxY)

        self.plotSettingsDock.setWidget(self.plotSettingsWidget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.plotSettingsDock)

        # Signals Dock
        self.dockSignals = QDockWidget(QCoreApplication.translate('SignalsDock', 'Signals'), self)
        self.dockSignals.setObjectName('DockSignals')
        self.dockSignalsWidget = QTableWidget(0, 8)
        dockSignalsWidgetPalette = self.dockSignalsWidget.palette()
        dockSignalsWidgetPalette.setBrush(QPalette.Highlight, QBrush(Qt.white))
        dockSignalsWidgetPalette.setBrush(QPalette.HighlightedText, QBrush(Qt.black))
        self.dockSignalsWidget.setPalette(dockSignalsWidgetPalette)
        self.dockSignalsWidget.setAutoFillBackground(True)
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
            QCoreApplication.translate('SignalsDock', 'Color'),
        ])
        header = self.dockSignalsWidget.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setForegroundRole(QPalette.Window)
        dockSignalsLayout = QGridLayout(self.dockSignalsWidget)
        dockSignalsLayout.setObjectName('DockSignalsLayout')
        self.dockSignals.setWidget(self.dockSignalsWidget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dockSignals)

        # File actions
        self.actionOpen = QAction(QCoreApplication.translate('Menu', '&Open...'), self)
        self.actionOpen.setShortcut(QCoreApplication.translate('Menu', 'Ctrl+O'))
        self.actionOpen.setStatusTip(QCoreApplication.translate('Menu', 'Open the recon data in the text format'))
        self.actionOpen.triggered.connect(self.openData)

        self.actionSave = QAction(QCoreApplication.translate('Menu', '&Save'), self)
        self.actionSave.setShortcut(QCoreApplication.translate('Menu', 'Ctrl+S'))
        self.actionSave.setStatusTip(QCoreApplication.translate('Menu', 'Save the recon data in the text format'))
        self.actionSave.setDisabled(True)
        self.actionSave.triggered.connect(self.saveData)

        self.actionSaveAs = QAction(QCoreApplication.translate('Menu', 'Save &as...'), self)
        self.actionSaveAs.setShortcut(QCoreApplication.translate('Menu', 'Ctrl+Shift+S'))
        self.actionSaveAs.setDisabled(True)
        self.actionSaveAs.setStatusTip(QCoreApplication.translate('Menu', 'Save the recon data in the text format as...'))
        self.actionSaveAs.triggered.connect(self.saveDataAs)

        self.actionExit = QAction(QCoreApplication.translate('Menu', '&Exit'), self)
        self.actionExit.setShortcut(QCoreApplication.translate('Menu', 'Ctrl+Q'))
        self.actionExit.setStatusTip(QCoreApplication.translate('Menu', 'Exit application'))
        self.actionExit.triggered.connect(self.close)

        # Plot actions
        self.actionBuildPlot = QAction(QCoreApplication.translate('Menu', '&Update'), self)
        self.actionBuildPlot.setShortcut(QCoreApplication.translate('Menu', 'F5'))
        self.actionBuildPlot.setStatusTip(QCoreApplication.translate('Menu', 'Update plot'))
        self.actionBuildPlot.setDisabled(True)
        self.actionBuildPlot.triggered.connect(self._update)

        self.actionSavePlot = QAction(QCoreApplication.translate('Menu', '&Save plot'), self)
        self.actionSavePlot.setShortcut(QCoreApplication.translate('Menu', 'Ctrl+Alt+S'))
        self.actionSavePlot.setStatusTip(QCoreApplication.translate('Menu', 'Save plot'))
        self.actionSavePlot.setDisabled(True)
        self.actionSavePlot.triggered.connect(self.savePlot)

        self.actionSavePlotAs = QAction(QCoreApplication.translate('Menu', 'Save plot &as...'), self)
        self.actionSavePlotAs.setShortcut(QCoreApplication.translate('Menu', 'Ctrl+Alt+Shift+S'))
        self.actionSavePlotAs.setStatusTip(QCoreApplication.translate('Menu', 'Save plot as...'))
        self.actionSavePlotAs.setDisabled(True)
        self.actionSavePlotAs.triggered.connect(self.savePlotAs)

        # Viev actions
        self.actionSignalsDock = self.dockSignals.toggleViewAction()
        self.actionSignalsDock.setStatusTip(QCoreApplication.translate('Menu', 'Show/hide signals window'))

        # Help actions
        self.actionAboutQt = QAction(QCoreApplication.translate('Menu', 'About Qt...'), self)
        self.actionAboutQt.triggered.connect(QApplication.aboutQt)

        menubar = self.menuBar()

        menuFile = menubar.addMenu(QCoreApplication.translate('Menu', '&File'))
        menuFile.addActions([self.actionOpen, self.actionSave, self.actionSaveAs])
        menuFile.addSeparator()
        menuFile.addAction(self.actionExit)

        menuPlot = menubar.addMenu(QCoreApplication.translate('Menu', '&Plot'))
        menuPlot.addAction(self.actionBuildPlot)
        menuPlot.addSeparator()
        menuPlot.addActions([self.actionSavePlot, self.actionSavePlotAs])

        menuView = menubar.addMenu(QCoreApplication.translate('Menu', '&View'))
        menuView.addAction(self.actionSignalsDock)

        menuHelp = menubar.addMenu(QCoreApplication.translate('Menu', '&Help'))
        menuHelp.addAction(self.actionAboutQt)

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
            widget = QLabel('', self.dockSignalsWidget)
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
            smoothWidget = QLineEdit(self.dockSignalsWidget)
            smoothWidget.setFrame(False)
            smoothWidget.setText(str(self.signals[i].smooth))
            smoothValidator = QIntValidator(smoothWidget)
            smoothValidator.setRange(1, 1000000)
            smoothWidget.setValidator(smoothValidator)
            smoothWidget.setAlignment(Qt.AlignCenter)
            smoothWidget.textChanged.connect(self.signals[i].setSmooth)
            smoothWidget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            self.dockSignalsWidget.setCellWidget(i, 3, smoothWidget)

            # Scale
            scaleWidget = QLineEdit(self.dockSignalsWidget)
            scaleWidget.setFrame(False)
            scaleWidget.setAlignment(Qt.AlignCenter)
            scaleWidget.setText(str(self.signals[i].scale))
            scaleWidget.textChanged.connect(self.signals[i].setScale)
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

            # Color
            color = QColor(self.signals[i].color)
            colorWidget = ClicableLabel(color.name(), self.dockSignalsWidget)
            colorWidget.setAlignment(Qt.AlignCenter)
            colorWidget.setAutoFillBackground(True)
            colorWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            palette = colorWidget.palette()
            palette.setColor(QPalette.Base, color)
            colorWidget.setPalette(palette)
            colorWidget.clicked.connect(self.signals[i]._color)
            self.dockSignalsWidget.setCellWidget(i, 7, colorWidget)

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

    def _set_colors(self):
        colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
        for i in range(len(self.signals)):
            self.signals[i].color = colors[i % len(colors)]

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
                            self.signals.append(AnalogSignal(data[2].strip()))

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
            self._set_colors()
            self.actionSave.setEnabled(True)
            self.actionSaveAs.setEnabled(True)
            self.actionBuildPlot.setEnabled(True)
            self.autoRange()
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

    def _update(self):
        fig, ax = plt.subplots()

        temp: QTemporaryFile = QTemporaryFile()
        temp.open()
        temp.close()

        print(temp.fileName())

        for signal in self.signals:
            if signal.selected:
                ax.plot(signal.smoothed(), self.times, label=signal.name, linewidth=0.25)

        plt.minorticks_on()
        plt.tight_layout()

#        ax.axis(axis)
        ax.legend(loc='best')
        ax.grid(which='minor', linestyle=':')
        ax.grid(which='major', linestyle='-')

        fig.set_size_inches(11.0, 7.5)
        fig.tight_layout()

        plt.savefig(temp.fileName(), format='svg')
        plt.close()

        pixmap = QPixmap(temp.fileName())
        self.imageLabel.setPixmap(pixmap)

        self.actionSavePlot.setEnabled(True)
        self.actionSavePlotAs.setEnabled(True)

    def _savePlot(self, filename: str) -> None:
        pass


if __name__ == "__main__":

    app = QApplication(sys.argv)
    app.setOrganizationName('Oleksandr Kolodkin')
    app.setApplicationName('Recon Plotter')
    app.setStyle(QStyleFactory.create('Fusion'))

    qtTranslator = QTranslator(app)
    qtTranslator.load(QLocale(), 'qt', '_', QLibraryInfo.location(QLibraryInfo.TranslationsPath))
    app.installTranslator(qtTranslator)

    myTranslator = QTranslator(app)
    myTranslator.load(QLocale(), 'recon', '_', '.', '.qm')
    app.installTranslator(myTranslator)

    window = Recon()
    window.show()

    sys.exit(app.exec_())
