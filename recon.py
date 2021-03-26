#!/usr/bin/python3

# Copyright 2021 Oleksandr Kolodkin <alexandr.kolodkin@gmail.com>.
# All rights reserved


import sys
import os
import numpy
import tempfile
from time import time
from typing import List, Optional
from PySide2.QtGui import QColor, QGuiApplication, QValidator, QDoubleValidator, QIntValidator, QPalette, QMouseEvent, QBrush, QPixmap
from PySide2.QtCore import qVersion, QObject, QSizeF, Signal, QCoreApplication, QLocale, QSettings, Qt, QTranslator, QLibraryInfo, QStandardPaths, QEventLoop, Slot
from PySide2.QtWidgets import QApplication, QCheckBox, QAbstractItemView, QComboBox, QFormLayout,\
    QHBoxLayout, QLineEdit, QMainWindow, QHeaderView, QFileDialog, QAction, QDockWidget,\
    QLabel, QProgressBar, QScrollArea, QSizePolicy, QGridLayout, QTableWidget, QWidget,\
    QStyleFactory, QColorDialog
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from numpy.core.numeric import isclose
if qVersion() >= "5.":
    from matplotlib.backends.backend_qt5agg import FigureCanvas, FigureCanvasQTAgg
else:
    from matplotlib.backends.backend_qt4agg import FigureCanvas, FigureCanvasQTAgg


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


class DoubleLineEdit(QLineEdit):
    valueChanged = Signal(float)

    def __init__(self, parent: Optional[QWidget]) -> None:
        super().__init__(parent=parent)
        self.setAlignment(Qt.AlignCenter)
        self.setValidator(DoubleValidator())
        self.textChanged.connect(self.onTextChanged)

    def onTextChanged(self, text: str) -> None:
        value = float(text.replace(QLocale().decimalPoint(), '.'))
        self.valueChanged.emit(value)

    @Slot(int)
    def setDecimals(self, decimals: int) -> None:
        validator: DoubleValidator = self.validator()
        validator.setDecimals(decimals)

    @Slot(float, float)
    def setRange(self, bottom: float, top: float) -> None:
        validator: DoubleValidator = self.validator()
        validator.setBottom(bottom)
        validator.setTop(top)

    @Slot(float)
    def setValue(self, value: float) -> None:
        if value is None:
            self.setText('')
        else:
            self.setText(f'{value:g}')


class AnalogSignal(QObject):
    minimumChanged = Signal(float)
    maximumChanged = Signal(float)

    def __init__(self, name: str = '', unit: str = 'V', data: List[float] = None) -> None:
        super(AnalogSignal, self).__init__()
        self.selected: bool = False
        self.name: str = name
        self.unit: str = unit
        self.smooth: int = 1
        self.scale: float = 1.0
        self.data: List[float] = data or []
        self.smoothedData: List[float] = None
        self.maximum: float = float('-inf')
        self.minimum: float = float('inf')
        self.color: str = 'green'

    def update(self):
        if self.smooth > 1:
            window = numpy.ones(self.smooth)/self.smooth
            self.smoothedData = numpy.convolve(self.data, window, 'same') * self.scale
            self.maximum = float('-inf')
            self.minimum = float('inf')
            for value in self.smoothedData:
                self.maximum = max(self.maximum, value)
                self.minimum = min(self.minimum, value)

        self.minimumChanged.emit(self.minimum)
        self.maximumChanged.emit(self.maximum)

    def getData(self) -> List[float]:
        if isclose(self.smooth, 1.0, rtol=0.0001):
            if isclose(self.scale, 1.0, rtol=0.0001):
                return self.data
            return self.smoothedData
        if isclose(self.scale, 1.0, rtol=0.0001):
            return self.smoothedData
        return self.smoothedData * self.scale

    def getName(self) -> str:
        if isclose(self.scale, 1.0, rtol=0.0001):
            return self.name
        return f'{self.name} × {self.scale:0.3g}'

    def setName(self, name: str) -> None:
        self.name = name

    def setUnit(self, unit: str) -> None:
        self.unit = unit

    def setSmooth(self, smooth: int) -> None:
        self.smooth = int(smooth)

    def setSelected(self, selected: bool) -> None:
        self.selected = bool(selected)

    def setScale(self, scale: float) -> None:
        self.scale = float(scale)

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
        self.dpi: float = None
        self.pageSize: QSizeF = None
        self.figure: Figure = Figure()

        super().__init__()
        self.initialize()
        self.restoreSession()

    @Slot(int)
    def setPageSize(self, index: int) -> None:
        self.pageSize = self.widgetSize.itemData(index)

    @Slot(float)
    def setDPI(self, dpi: float) -> None:
        self.dpi = dpi

    @Slot(str)
    def setTitle(self, title: str) -> None:
        self.title = title

    @Slot(str)
    def setAxisX(self, axisX: str) -> None:
        self.axisX = axisX

    @Slot(str)
    def setAxisY(self, axisY: str) -> None:
        self.axisY = axisY

    @Slot(float)
    def setMinX(self, value: float) -> None:
        self.min_x = value

    @Slot(float)
    def setMinY(self, value: float) -> None:
        self.min_y = value

    @Slot(float)
    def setMaxX(self, value: float) -> None:
        self.max_x = value

    @Slot(float)
    def setMaxY(self, value: float) -> None:
        self.max_y = value

    def isSignalsNotSelected(self) -> bool:
        for signal in self.signals:
            if signal.selected:
                return False
        return True

    @Slot()
    @Slot(bool)
    def autoRange(self):
        if len(self.times) and len(self.signals):

            # X range
            self.min_x = 0
            self.max_x = self.times[-1]

            # Y range
            self.min_y = float('inf')
            self.max_y = float('-inf')

            for signal in self.signals:
                if self.isSignalsNotSelected() or signal.selected:
                    signal.update()
                    self.min_y = min(self.min_y, signal.minimum)
                    self.max_y = max(self.max_y, signal.maximum)

            # TODO: Round values to more beautiful

            # Update validators
            self.widgetMinX.setRange(self.min_x, self.max_x)
            self.widgetMaxX.setRange(self.min_x, self.max_x)
            self.widgetMinY.setRange(self.min_y, self.max_y)
            self.widgetMaxY.setRange(self.min_y, self.max_y)

            # Update range
            self.widgetMinX.setValue(self.min_x)
            self.widgetMaxX.setValue(self.max_x)
            self.widgetMinY.setValue(self.min_y)
            self.widgetMaxY.setValue(self.max_y)

    def initialize(self) -> None:
        self.setWindowTitle('Recon plotter')
        self.setMinimumSize(800, 200)

        # Add progress bar
        self.progressBar = QProgressBar(self.statusBar())
        self.progressBar.setMinimum(0)
        self.progressBar.setAlignment(Qt.AlignCenter)
        self.progressBar.hide()

        # Add plot display
        self.plot = FigureCanvas(self.figure)
        self.setCentralWidget(self.plot)

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
        self.widgetMinX = DoubleLineEdit(self.plotSettingsWidget)
        self.widgetMinX.setDecimals(3)
        self.widgetMinX.valueChanged.connect(self.setMinX)
        self.plotSettingsLayout.addRow(self.labelMinX, self.widgetMinX)

        # Maximum X
        self.labelMaxX = QLabel(QCoreApplication.translate('PlotSettingsDock', 'X to:'), self.plotSettingsWidget)
        self.widgetMaxX = DoubleLineEdit(self.plotSettingsWidget)
        self.widgetMaxX.setDecimals(3)
        self.widgetMaxX.valueChanged.connect(self.setMaxX)
        self.plotSettingsLayout.addRow(self.labelMaxX, self.widgetMaxX)

        # Minimum Y
        self.labelMinY = QLabel(QCoreApplication.translate('PlotSettingsDock', 'Y from:'), self.plotSettingsWidget)
        self.widgetMinY = DoubleLineEdit(self.plotSettingsWidget)
        self.widgetMinY.setDecimals(3)
        self.widgetMinY.valueChanged.connect(self.setMinY)
        self.plotSettingsLayout.addRow(self.labelMinY, self.widgetMinY)

        # Maximum Y
        self.labelMaxY = QLabel(QCoreApplication.translate('PlotSettingsDock', 'Y to:'), self.plotSettingsWidget)
        self.widgetMaxY = DoubleLineEdit(self.plotSettingsWidget)
        self.widgetMaxY.setDecimals(3)
        self.widgetMaxY.valueChanged.connect(self.setMaxY)
        self.plotSettingsLayout.addRow(self.labelMaxY, self.widgetMaxY)

        # DPI
        self.labelDPI = QLabel(QCoreApplication.translate('PlotSettingsDock', 'DPI:'), self.plotSettingsWidget)
        self.widgetDPI = DoubleLineEdit(self.plotSettingsWidget)
        self.widgetDPI.setDecimals(3)
        self.widgetDPI.setValue(self.dpi)
        self.widgetDPI.valueChanged.connect(self.setDPI)
        self.plotSettingsLayout.addRow(self.labelDPI, self.widgetDPI)

        # Page size
        landscape = QCoreApplication.translate('PlotSettingsDock', '{0} landscape')
        portrate = QCoreApplication.translate('PlotSettingsDock', '{0} portrate')

        self.labelSize = QLabel(QCoreApplication.translate('PlotSettingsDock', 'Page size:'), self.plotSettingsWidget)
        self.widgetSize = QComboBox(self.plotSettingsWidget)

        self.widgetSize.addItem(landscape.format('A3'), QSizeF(16.535, 11.693))
        self.widgetSize.addItem(landscape.format('A4'), QSizeF(11.693, 8.268))
        self.widgetSize.addItem(landscape.format('A5'), QSizeF(8.268, 5.827))

        self.widgetSize.addItem(portrate.format('A3'), QSizeF(11.693, 16.535))
        self.widgetSize.addItem(portrate.format('A4'), QSizeF(8.268, 11.693))
        self.widgetSize.addItem(portrate.format('A5'), QSizeF(5.827, 8.268))

        for i in range(self.widgetSize.count()):
            self.widgetSize.setItemData(i, Qt.AlignCenter, Qt.TextAlignmentRole)

        self.widgetSize.currentIndexChanged.connect(self.setPageSize)
        self.plotSettingsLayout.addRow(self.labelSize, self.widgetSize)

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
        self.widgetDPI.setValue(float(settings.value('dpi', 600.0)))
        self.widgetSize.setCurrentIndex(settings.value('size', self.widgetSize.currentIndex()))

    def saveSession(self) -> None:
        settings = QSettings()
        settings.setValue('geometry', self.saveGeometry())
        settings.setValue('state', self.saveState())
        settings.setValue('dpi', self.dpi)
        settings.setValue('size', self.widgetSize.currentIndex())

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
            checkBox.stateChanged.connect(self.autoRange)
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
            smoothWidget.textChanged.connect(self.autoRange)
            smoothWidget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            self.dockSignalsWidget.setCellWidget(i, 3, smoothWidget)

            # Scale
            scaleWidget = DoubleLineEdit(self.dockSignalsWidget)
            scaleWidget.setFrame(False)
            scaleWidget.setAlignment(Qt.AlignCenter)
            scaleWidget.setValue(self.signals[i].scale)
            scaleWidget.valueChanged.connect(self.signals[i].setScale)
            scaleWidget.valueChanged.connect(self.autoRange)
            scaleWidget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            self.dockSignalsWidget.setCellWidget(i, 4, scaleWidget)

            # Minimum
            minWidget = DoubleLineEdit(self.dockSignalsWidget)
            minWidget.setFrame(False)
            minWidget.setReadOnly(True)
            minWidget.setValue(self.signals[i].minimum)
            minWidget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            self.dockSignalsWidget.setCellWidget(i, 5, minWidget)
            self.signals[i].minimumChanged.connect(minWidget.setValue)

            # Maximum
            maxWidget = DoubleLineEdit(self.dockSignalsWidget)
            maxWidget.setFrame(False)
            maxWidget.setReadOnly(True)
            maxWidget.setValue(self.signals[i].maximum)
            maxWidget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            self.dockSignalsWidget.setCellWidget(i, 6, maxWidget)
            self.signals[i].maximumChanged.connect(maxWidget.setValue)

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

        self.figure.clear()
        ax = self.figure.subplots()

        for signal in self.signals:
            if signal.selected:
                ax.plot(self.times, signal.getData(), label=signal.getName(), linewidth=0.25)

        plt.title(self.title)
        plt.xlabel(self.axisX)
        plt.ylabel(self.axisY)
        plt.minorticks_on()
        plt.tight_layout()

        ax.axis([self.min_x, self.max_x, self.min_y, self.max_y])
        ax.legend(loc='best')
        ax.grid(which='minor', linestyle=':')
        ax.grid(which='major', linestyle='-')

#        self.figure.set_dpi(self.dpi)
#        self.figure.set_size_inches(self.pageSize.width(), self.pageSize.height())

        self.figure.tight_layout()
        self.figure.canvas.draw()

        self.actionSavePlot.setEnabled(True)
        self.actionSavePlotAs.setEnabled(True)

        print('finished')

    def _savePlot(self, filename: str) -> None:
        pass


if __name__ == "__main__":

    print(f'Qt version: {qVersion()}')

    # Increase matplotlib limit
    mpl.rcParams['agg.path.chunksize'] = 100000

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
