#!/usr/bin/python3

# Copyright 2021 Oleksandr Kolodkin <alexandr.kolodkin@gmail.com>.
# All rights reserved

import os
import sys
import math
import numpy
import logging

from time import time
from typing import Any, List, Optional
from distutils.util import strtobool

# Qt
from PyQt5.QtGui import (
    QColor, QCursor, QIcon, QValidator, QDoubleValidator, QIntValidator,
    QPalette, QMouseEvent)

from PyQt5.QtCore import (
    QMessageLogContext, QtMsgType, pyqtSlot, qDebug, qInstallMessageHandler, qVersion, QObject, QSizeF, pyqtSignal, QCoreApplication, QLocale,
    QSettings, Qt, QTranslator, QLibraryInfo, QStandardPaths, QEventLoop)

from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QAbstractItemView, QComboBox, QFormLayout,
    QHBoxLayout, QLineEdit, QMainWindow, QHeaderView, QFileDialog, QAction,
    QDockWidget, QLabel, QMenu, QProgressBar, QPushButton, QSizePolicy, QGridLayout,
    QTableWidget,  QWidget, QStyleFactory, QColorDialog)

# Matplotlib
import matplotlib
import matplotlib.pyplot
import matplotlib.widgets
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.backend_bases import MouseEvent, LocationEvent, KeyEvent

if qVersion() >= "5.":
    from matplotlib.backends.backend_qt5agg import FigureCanvas
else:
    from matplotlib.backends.backend_qt4agg import FigureCanvas


def prettyFloor(value: float, places: int = 2) -> float:
    try:
        result = value
        f = math.pow(10, int(round(math.log10(abs(value)))) - places + 1)
        result = math.floor(value / f) * f
    finally:
        return result


def prettyCeil(value: float, places: int = 2) -> float:
    try:
        result = value
        f = math.pow(10, int(round(math.log10(abs(value)))) - places + 1)
        result = math.ceil(value / f) * f
    finally:
        return result


def readCommaSeparatedLine(line: str) -> List[str]:
    result = []
    isStringStarted = False
    value = ''
    for i in range(len(line)):
        if line[i] == '"':
            if isStringStarted:
                if i > 1 and line[i-1] == '"':
                    value += '"'
            else:
                isStringStarted = True
        elif line[i] == ',':
            if (i > 2 and line[i-1] == '"' and line[i-2] == '"') or (isStringStarted and line[i-1] != '"'):
                value += line[i]
            else:
                result.append(value.strip())
                isStringStarted = False
                value = ''
        else:
            value += line[i]

    if len(value):
        result.append(value.strip())
    return result


def writeCommaSeparatedLine(values: List[Any]) -> str:
    result = []
    for value in values:
        if type(value) == list:
            result.append(writeCommaSeparatedLine(value))
        elif type(value) == str:
            if '"' in value:
                value = value.replace('"', '""')
                value = f'"{value}"'
            elif ',' in value:
                value = f'"{value}"'
            result.append(value)
        else:
            result.append(str(value))
    return ', '.join(result)


class CheckBox(QWidget):
    stateChanged = pyqtSignal(bool)

    def __init__(self, state: Optional[bool] = False, parent: Optional[QWidget] = None) -> None:
        super(CheckBox, self).__init__(parent)
        self.setAutoFillBackground(True)
        self.checkbox = QCheckBox('', self)
        self.checkbox.setChecked(state)
        self.checkbox.stateChanged.connect(self.stateChanged.emit)
        self.setLayout(QHBoxLayout(self))
        self.layout().addWidget(self.checkbox)
        self.layout().setAlignment(Qt.AlignCenter)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.mousePressEvent = self.on_mousePressEvent

    def on_mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.checkbox.setChecked(not self.checkbox.isChecked())

    def setChecked(self, state: bool) -> None:
        self.checkbox.setChecked(state)


class ClicableLabel(QLabel):
    clicked = pyqtSignal()

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
    valueChanged = pyqtSignal(float)

    def __init__(self, parent: Optional[QWidget]) -> None:
        super().__init__(parent=parent)
        self.setAlignment(Qt.AlignCenter)
        self.setValidator(DoubleValidator())
        self.textChanged.connect(self.onTextChanged)

    def onTextChanged(self, text: str) -> None:
        value = 0 if text == '' else float(text.replace(QLocale().decimalPoint(), '.'))
        self.valueChanged.emit(value)

    @pyqtSlot(int)
    def setDecimals(self, decimals: int) -> None:
        validator: DoubleValidator = self.validator()
        validator.setDecimals(decimals)

    @pyqtSlot(float, float)
    def setRange(self, bottom: float, top: float) -> None:
        validator: DoubleValidator = self.validator()
        validator.setBottom(bottom)
        validator.setTop(top)

    def value(self) -> float:
        text = self.text()
        return 0 if text == '' else float(text.replace(QLocale().decimalPoint(), '.'))

    @pyqtSlot(float)
    def setValue(self, value: float) -> None:
        if value is None:
            self.setText('')
        else:
            self.setText(f'{value:g}')


class AnalogSignal(QObject):
    minimumChanged = pyqtSignal(float)
    maximumChanged = pyqtSignal(float)

    def __init__(self, name: str = '', unit: str = 'V', data: List[float] = None) -> None:
        super(AnalogSignal, self).__init__()
        self.selected: bool = False
        self.inverted: bool = False
        self.name: str = name
        self.unit: str = unit
        self.smooth: int = 1
        self.scale: float = 1.0
        self.data: List[float] = data or []
        self.smoothedData: List[float] = None
        self.maximum: float = float('-inf')
        self.minimum: float = float('inf')
        self.color: str = None

    def update(self):
        if self.smooth > 1:
            window = numpy.ones(self.smooth)/self.smooth
            self.smoothedData = numpy.convolve(self.data, window, 'same')
            self.maximum = float('-inf')
            self.minimum = float('inf')
            for value in self.smoothedData * self.scale:
                self.maximum = max(self.maximum, value)
                self.minimum = min(self.minimum, value)

        self.minimumChanged.emit(self.minimum)
        self.maximumChanged.emit(self.maximum)

    def getData(self) -> List[float]:
        result = self.data if self.smooth == 1 else self.smoothedData
        result = [-v for v in result] if self.inverted else result
        return result if math.isclose(self.scale, 1.0, abs_tol=0.0001) else [v * self.scale for v in result]

    def getName(self) -> str:
        if math.isclose(self.scale, 1.0, abs_tol=0.0001):
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

    def setInverted(self, inverted: bool) -> None:
        self.inverted = inverted

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


class Range(object):

    def __init__(self, left: float = 0, right: float = 1.0, bottom: float = -1.0, top: float = 1.0) -> None:
        self.top = top
        self.bottom = bottom
        self.left = left
        self.right = right
        super().__init__()


class Recon(QMainWindow):

    def __init__(self) -> None:
        self.name: str = ''
        self.dataFileName: str = ''
        self.plotFileName: str = ''
        self.times: list = []
        self.signals: List[AnalogSignal] = []
        self.progressBar: QProgressBar = None
        self.dockSignals: QDockWidget = None
        self.dockSignalsWidget: QTableWidget = None
        self.menuRecent: QMenu = None
        self.title: str = ''
        self.device: str = ''
        self.originalFileName: str = ''
        self.axisX: str = ''
        self.axisY: str = ''
        self.range: Range = Range()
        self.dpi: float = None
        self.pageSize: QSizeF = None
        self.figure: Figure = Figure()
        self.ax: Axes = None
        self.lineWidth = 0.5

        super().__init__()
        self.initialize()
        self.restoreSession()
        self._update_recent_list()

    @pyqtSlot(int)
    def setPageSize(self, index: int) -> None:
        self.pageSize = self.widgetSize.itemData(index)

    @pyqtSlot(float)
    def setDPI(self, dpi: float) -> None:
        self.dpi = dpi

    @pyqtSlot(str)
    def setTitle(self, title: str) -> None:
        self.title = title

    @pyqtSlot(str)
    def setAxisX(self, axisX: str) -> None:
        self.axisX = axisX

    @pyqtSlot(str)
    def setAxisY(self, axisY: str) -> None:
        self.axisY = axisY

    @pyqtSlot(float)
    def setLineWidth(self, width: float) -> None:
        self.lineWidth = width

    @pyqtSlot(float)
    def setLeft(self, value: float) -> None:
        self.range.left = value
        if self.widgetLeft.value() != value:
            self.widgetLeft.setValue(value)

    @pyqtSlot(float)
    def setRight(self, value: float) -> None:
        self.range.right = value
        if self.widgetRight.value() != value:
            self.widgetRight.setValue(value)

    @pyqtSlot(float)
    def setBottom(self, value: float) -> None:
        self.range.bottom = value
        if self.widgetBottom.value() != value:
            self.widgetBottom.setValue(value)

    @pyqtSlot(float)
    def setTop(self, value: float) -> None:
        self.range.top = value
        if self.widgetTop.value() != value:
            self.widgetTop.setValue(value)

    def timeToIndex(self, time: float) -> int:
        if len(self.times) > 3:
            if (time >= -0.000001) and (time <= (self.times[-1] + 0.00001)):
                delta = self.times[-1] / (len(self.times) - 1)
                return int(time / delta)
        return -1

    def isSignalsNotSelected(self) -> bool:
        for signal in self.signals:
            if signal.selected:
                return False
        return True

    @pyqtSlot()
    @pyqtSlot(bool)
    def autoRange(self):
        if len(self.times) and len(self.signals):

            # X range
            left = 0
            right = self.times[-1]

            # Y range
            bottom = float('inf')
            top = float('-inf')

            for signal in self.signals:
                if self.isSignalsNotSelected() or signal.selected:
                    signal.update()
                    bottom = min(bottom, signal.minimum)
                    top = max(top, signal.maximum)

            self.range = Range(
                left=prettyFloor(left),
                right=prettyCeil(right),
                bottom=prettyFloor(bottom),
                top=prettyCeil(top)
            )

            self.updateRange()
            self._update()

    def updateRange(self):
        # Update validators
        # self.widgetMinX.setRange(self.range.left, self.range.right)
        # self.widgetMaxX.setRange(self.range.left, self.range.right)
        # self.widgetMinY.setRange(self.range.bottom, self.range.top)
        # self.widgetMaxY.setRange(self.range.bottom, self.range.top)

        # Update range
        self.widgetLeft.setValue(self.range.left)
        self.widgetRight.setValue(self.range.right)
        self.widgetBottom.setValue(self.range.bottom)
        self.widgetTop.setValue(self.range.top)

    def initialize(self) -> None:
        self.setWindowTitle('Recon plotter')
        self.setMinimumSize(800, 200)

        # Add progress bar
        self.progressBar = QProgressBar(self.statusBar())
        self.progressBar.setMinimum(0)
        self.progressBar.setAlignment(Qt.AlignCenter)
        self.progressBar.hide()

        self.figure.canvas.mpl_connect('key_press_event', self._key)
        self.figure.canvas.mpl_connect('motion_notify_event', self._mouse_move)
        self.figure.canvas.mpl_connect('axes_enter_event', self._mouse_enter)
        self.figure.canvas.mpl_connect('axes_leave_event', self._mouse_leave)

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
        self.labelLeft = QLabel(QCoreApplication.translate('PlotSettingsDock', 'Left:'), self.plotSettingsWidget)
        self.widgetLeft = DoubleLineEdit(self.plotSettingsWidget)
        self.widgetLeft.setDecimals(3)
        self.widgetLeft.valueChanged.connect(self.setLeft)
        self.plotSettingsLayout.addRow(self.labelLeft, self.widgetLeft)

        # Maximum X
        self.labelRight = QLabel(QCoreApplication.translate('PlotSettingsDock', 'Right:'), self.plotSettingsWidget)
        self.widgetRight = DoubleLineEdit(self.plotSettingsWidget)
        self.widgetRight.setDecimals(3)
        self.widgetRight.valueChanged.connect(self.setRight)
        self.plotSettingsLayout.addRow(self.labelRight, self.widgetRight)

        # Minimum Y
        self.labelBottom = QLabel(QCoreApplication.translate('PlotSettingsDock', 'Bottom:'), self.plotSettingsWidget)
        self.widgetBottom = DoubleLineEdit(self.plotSettingsWidget)
        self.widgetBottom.setDecimals(3)
        self.widgetBottom.valueChanged.connect(self.setBottom)
        self.plotSettingsLayout.addRow(self.labelBottom, self.widgetBottom)

        # Maximum Y
        self.labelTop = QLabel(QCoreApplication.translate('PlotSettingsDock', 'Top:'), self.plotSettingsWidget)
        self.widgetTop = DoubleLineEdit(self.plotSettingsWidget)
        self.widgetTop.setDecimals(3)
        self.widgetTop.valueChanged.connect(self.setTop)
        self.plotSettingsLayout.addRow(self.labelTop, self.widgetTop)

        # Line width
        self.labelLineWidth = QLabel(QCoreApplication.translate('PlotSettingsDock', 'Line width:'), self.plotSettingsWidget)
        self.widgetLineWidth = DoubleLineEdit(self.plotSettingsWidget)
        self.widgetLineWidth.setDecimals(2)
        self.widgetLineWidth.setValue(self.lineWidth)
        self.widgetLineWidth.valueChanged.connect(self.setLineWidth)
        self.plotSettingsLayout.addRow(self.labelLineWidth, self.widgetLineWidth)

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

        # Align center
        self.widgetSize.setEditable(True)
        self.widgetSize.lineEdit().setReadOnly(True)
        self.widgetSize.lineEdit().setAlignment(Qt.AlignCenter)
        for i in range(self.widgetSize.count()):
            self.widgetSize.setItemData(i, Qt.AlignCenter, Qt.TextAlignmentRole)

        self.widgetSize.currentIndexChanged.connect(self.setPageSize)
        self.plotSettingsLayout.addRow(self.labelSize, self.widgetSize)

        # Update button
        self.widgetUpdate = QPushButton(QCoreApplication.translate('PlotSettingsDock', 'Update Plot'))
        self.widgetUpdate.setDisabled(True)
        self.widgetUpdate.clicked.connect(self._update)
        self.plotSettingsLayout.addWidget(self.widgetUpdate)

        self.plotSettingsDock.setWidget(self.plotSettingsWidget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.plotSettingsDock)

        # Signals Dock
        self.dockSignals = QDockWidget(QCoreApplication.translate('SignalsDock', 'Signals'), self)
        self.dockSignals.setObjectName('DockSignals')
        self.dockSignalsWidget = QTableWidget(0, 9)
        self.dockSignalsWidget.setAutoFillBackground(True)
        self.dockSignalsWidget.setObjectName('DockSignalsWidget')
        self.dockSignalsWidget.setSelectionMode(QAbstractItemView.NoSelection)
        self.dockSignalsWidget.setHorizontalHeaderLabels([
            QCoreApplication.translate('SignalsDock', 'Selected'),
            QCoreApplication.translate('SignalsDock', 'Name'),
            QCoreApplication.translate('SignalsDock', 'Unit'),
            QCoreApplication.translate('SignalsDock', 'Inverted'),
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
        self.actionOpen.setIcon(QIcon('icons/document-open-symbolic.svg'))
        self.actionOpen.setShortcut(QCoreApplication.translate('Menu', 'Ctrl+O'))
        self.actionOpen.setStatusTip(QCoreApplication.translate('Menu', 'Open the recon data in the text format'))
        self.actionOpen.triggered.connect(self.openData)

        self.actionSave = QAction(QCoreApplication.translate('Menu', '&Save'), self)
        self.actionSave.setIcon(QIcon('icons/document-save-symbolic.svg'))
        self.actionSave.setShortcut(QCoreApplication.translate('Menu', 'Ctrl+S'))
        self.actionSave.setStatusTip(QCoreApplication.translate('Menu', 'Save the recon data in the text format'))
        self.actionSave.setDisabled(True)
        self.actionSave.triggered.connect(self.saveData)

        self.actionSaveAs = QAction(QCoreApplication.translate('Menu', 'Save &as...'), self)
        self.actionSaveAs.setIcon(QIcon('icons/document-save-as-symbolic.svg'))
        self.actionSaveAs.setShortcut(QCoreApplication.translate('Menu', 'Ctrl+Shift+S'))
        self.actionSaveAs.setDisabled(True)
        self.actionSaveAs.setStatusTip(QCoreApplication.translate('Menu', 'Save the recon data in the text format as...'))
        self.actionSaveAs.triggered.connect(self.saveDataAs)

        self.actionExit = QAction(QCoreApplication.translate('Menu', '&Exit'), self)
        self.actionExit.setIcon(QIcon('icons/window-close-symbolic.svg'))
        self.actionExit.setShortcut(QCoreApplication.translate('Menu', 'Ctrl+Q'))
        self.actionExit.setStatusTip(QCoreApplication.translate('Menu', 'Exit application'))
        self.actionExit.triggered.connect(self.close)

        # Plot actions
        self.actionAutoRange = QAction(QCoreApplication.translate('Menu', 'Fit to signal &range'))
        self.actionAutoRange.setIcon(QIcon('icons/zoom-fit-best-symbolic.svg'))
        self.actionAutoRange.setShortcut(QCoreApplication.translate('Menu', 'F4'))
        self.actionAutoRange.setStatusTip(QCoreApplication.translate('Menu', 'Recalculate signals limits & update plot ranges'))
        self.actionAutoRange.setDisabled(True)
        self.actionAutoRange.triggered.connect(self.autoRange)

        self.actionBuildPlot = QAction(QCoreApplication.translate('Menu', '&Update'), self)
        self.actionBuildPlot.setIcon(QIcon('icons/view-refresh-symbolic.svg'))
        self.actionBuildPlot.setShortcut(QCoreApplication.translate('Menu', 'F5'))
        self.actionBuildPlot.setStatusTip(QCoreApplication.translate('Menu', 'Update plot'))
        self.actionBuildPlot.setDisabled(True)
        self.actionBuildPlot.triggered.connect(self._update)

        self.actionSavePlot = QAction(QCoreApplication.translate('Menu', '&Save plot'), self)
        self.actionSavePlot.setIcon(QIcon('icons/document-save-symbolic.svg'))
        self.actionSavePlot.setShortcut(QCoreApplication.translate('Menu', 'Ctrl+Alt+S'))
        self.actionSavePlot.setStatusTip(QCoreApplication.translate('Menu', 'Save plot'))
        self.actionSavePlot.setDisabled(True)
        self.actionSavePlot.triggered.connect(self.savePlot)

        self.actionSavePlotAs = QAction(QCoreApplication.translate('Menu', 'Save plot &as...'), self)
        self.actionSavePlotAs.setIcon(QIcon('icons/document-save-as-symbolic.svg'))
        self.actionSavePlotAs.setShortcut(QCoreApplication.translate('Menu', 'Ctrl+Alt+Shift+S'))
        self.actionSavePlotAs.setStatusTip(QCoreApplication.translate('Menu', 'Save plot as...'))
        self.actionSavePlotAs.setDisabled(True)
        self.actionSavePlotAs.triggered.connect(self.savePlotAs)

        # Viev actions
        self.actionSignalsDock = self.dockSignals.toggleViewAction()
        self.actionSignalsDock.setStatusTip(QCoreApplication.translate('Menu', 'Show/hide signals window'))

        self.actionSettingsDock = self.plotSettingsDock.toggleViewAction()
        self.actionSettingsDock.setStatusTip(QCoreApplication.translate('Menu', 'Show/hide plot settings window'))

        self.actionFullScreen = QAction(QCoreApplication.translate('Menu', '&Full screan'))
        self.actionFullScreen.setIcon(QIcon('icons/view-fullscreen-symbolic.svg'))
        self.actionFullScreen.setStatusTip(QCoreApplication.translate('Menu', 'Show plot in full screan'))
        self.actionFullScreen.setShortcut(QCoreApplication.translate('Menu', 'F11'))
        self.actionFullScreen.triggered.connect(self._fullscreen)

        # Help actions
        self.actionAboutQt = QAction(QCoreApplication.translate('Menu', 'About Qt...'), self)
        self.actionAboutQt.setIcon(QIcon('icons/help-about-symbolic.svg'))
        self.actionAboutQt.triggered.connect(QApplication.aboutQt)

        self.actionHelp = QAction(QCoreApplication.translate('Menu', 'Show manual'))
        self.actionHelp.setIcon(QIcon('icons/help-contents-symbolic.svg'))
        self.actionHelp.setShortcut(QCoreApplication.translate('Menu', 'F1'))
        self.actionHelp.setStatusTip(QCoreApplication.translate('Menu', 'Show application manual'))
        self.actionHelp.triggered.connect(self._help)

        menubar = self.menuBar()

        self.menuRecent = QMenu(QCoreApplication.translate('Menu', 'Open &recent'))
        self.menuRecent.setIcon(QIcon('icons/document-open-recent-symbolic.svg'))

        menuFile = menubar.addMenu(QCoreApplication.translate('Menu', '&File'))
        menuFile.addActions([self.actionOpen, self.actionSave, self.actionSaveAs])
        menuFile.addSeparator()
        menuFile.addMenu(self.menuRecent)
        menuFile.addSeparator()
        menuFile.addAction(self.actionExit)

        menuPlot = menubar.addMenu(QCoreApplication.translate('Menu', '&Plot'))
        menuPlot.addActions([self.actionAutoRange, self.actionBuildPlot])
        menuPlot.addSeparator()
        menuPlot.addActions([self.actionSavePlot, self.actionSavePlotAs])

        menuView = menubar.addMenu(QCoreApplication.translate('Menu', '&View'))
        menuView.addActions([self.actionSignalsDock, self.actionSettingsDock])
        menuView.addSeparator()
        menuView.addAction(self.actionFullScreen)

        menuHelp = menubar.addMenu(QCoreApplication.translate('Menu', '&Help'))
        menuHelp.addActions([self.actionHelp, self.actionAboutQt])

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
            widgetSelected = CheckBox(self.signals[i].selected, self.dockSignalsWidget)
            widgetSelected.stateChanged.connect(self.signals[i].setSelected)
            self.dockSignalsWidget.setCellWidget(i, 0, widgetSelected)

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

            # Inverted
            invertedWidget = CheckBox(self.signals[i].inverted, self.dockSignalsWidget)
            invertedWidget.stateChanged.connect(self.signals[i].setInverted)
            self.dockSignalsWidget.setCellWidget(i, 3, invertedWidget)

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
            self.dockSignalsWidget.setCellWidget(i, 4, smoothWidget)

            # Scale
            scaleWidget = DoubleLineEdit(self.dockSignalsWidget)
            scaleWidget.setRange(0, float('inf'))
            scaleWidget.setFrame(False)
            scaleWidget.setAlignment(Qt.AlignCenter)
            scaleWidget.setValue(self.signals[i].scale)
            scaleWidget.valueChanged.connect(self.signals[i].setScale)
            scaleWidget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            self.dockSignalsWidget.setCellWidget(i, 5, scaleWidget)

            # Minimum
            minWidget = DoubleLineEdit(self.dockSignalsWidget)
            minWidget.setFrame(False)
            minWidget.setReadOnly(True)
            minWidget.setValue(self.signals[i].minimum)
            minWidget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            self.dockSignalsWidget.setCellWidget(i, 6, minWidget)
            self.signals[i].minimumChanged.connect(minWidget.setValue)

            # Maximum
            maxWidget = DoubleLineEdit(self.dockSignalsWidget)
            maxWidget.setFrame(False)
            maxWidget.setReadOnly(True)
            maxWidget.setValue(self.signals[i].maximum)
            maxWidget.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            self.dockSignalsWidget.setCellWidget(i, 7, maxWidget)
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
            self.dockSignalsWidget.setCellWidget(i, 8, colorWidget)

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
            dialog.setNameFilter(QCoreApplication.translate('FileDialog', 'Recon data files(*.txt);;COMTRADE data files(*.cfg)'))
            dialog.setWindowTitle(QCoreApplication.translate('FileDialog', 'Open recon data file'))
            dialog.fileSelected.connect(self._load)
            dialog.open()
        except Exception as e:
            qDebug(e)

    def saveData(self):
        os.path.isfile(self.dataFileName) if self._saveReconText(self.dataFileName) else self.saveDataAs()

    def saveDataAs(self):
        try:
            dialog = QFileDialog(self)
            dialog.setAcceptMode(QFileDialog.AcceptSave)
            dialog.setDirectory(QSettings().value('default_data_path', QStandardPaths.standardLocations(QStandardPaths.DocumentsLocation)[0]))
            dialog.setNameFilter(QCoreApplication.translate('FileDialog', 'Recon data files(*.txt)'))
            dialog.setWindowTitle(QCoreApplication.translate('FileDialog', 'Save recon data file'))
            dialog.fileSelected.connect(self._saveReconText)
            dialog.open()
        except Exception as e:
            qDebug(e)

    def savePlot(self) -> None:
        if hasattr(self, 'plotFileName') and self.plotFileName is not None and os.path.isfile(self.plotFileName):
            self._savePlot(self.plotFileName)
        else:
            self.savePlotAs()

    def savePlotAs(self) -> None:
        dialog = QFileDialog(self)
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setDirectory(QSettings().value('default_plot_path', QStandardPaths.standardLocations(QStandardPaths.DocumentsLocation)[0]))
        dialog.setNameFilter(QCoreApplication.translate('FileDialog', 'PDF Document(*.pdf);;SVG Image(*.svg)'))
        dialog.setWindowTitle(QCoreApplication.translate('FileDialog', 'Save plot'))
        dialog.fileSelected.connect(self._savePlot)
        dialog.open()

    def _select_callback(self, eclick: MouseEvent, erelease: MouseEvent):
        self.setLeft(prettyFloor(min(eclick.xdata, erelease.xdata)))
        self.setRight(prettyCeil(max(eclick.xdata, erelease.xdata)))
        self.setBottom(prettyFloor(min(eclick.ydata, erelease.ydata)))
        self.setTop(prettyCeil(max(eclick.ydata, erelease.ydata)))
        self._update()
        pass

    def _mouse_move(self, event: MouseEvent) -> None:
        if event.inaxes:
            self._show_status_message(event.xdata)
        else:
            self.statusBar().clearMessage()

    def _show_status_message(self, x: float) -> None:
        msg = QCoreApplication.translate('Status', 'Time: {0:g} [s]').format(x)
        i = self.timeToIndex(x)
        if i >= 0:
            for signal in self.signals:
                if signal.selected:
                    msg += f',  {signal.name:s}: {signal.data[i]:g} [{signal.unit}]'
        self.statusBar().showMessage(msg)

    def _mouse_enter(self, event: LocationEvent) -> None:
        cursor: QCursor = self.plot.cursor()
        cursor.setShape(Qt.CrossCursor)
        self.plot.setCursor(cursor)

    def _mouse_leave(self, event: LocationEvent) -> None:
        cursor: QCursor = self.plot.cursor()
        cursor.setShape(Qt.ArrowCursor)
        self.plot.setCursor(cursor)

    def _add_to_recent(self, filename: str):
        settings: QSettings = QSettings()
        last_recent: List[str] = settings.value('recent', list())
        new_recent: List[str] = [filename]
        for i in range(min(len(last_recent), 10)):
            if last_recent[i] not in new_recent:
                new_recent.append(last_recent[i])
        settings.setValue('recent', new_recent)
        self._update_recent_list()

    def _update_recent_list(self):
        settings: QSettings = QSettings()
        recent: List[str] = settings.value('recent', list())
        self.menuRecent.clear()
        self.actionsRecent = []
        for filename in recent:
            action = QAction(filename)
            action.triggered.connect(self._open_recent)
            self.actionsRecent.append(action)
        self.menuRecent.addActions(self.actionsRecent)

    def _open_recent(self):
        action: QAction = self.sender()
        self._loadReconText(action.text())

    @pyqtSlot()
    def _help(self):
        os.startfile(QCoreApplication.translate('Help', '"manual\\Recon Plotter Manual.pdf"'))

    def _key(self, event: KeyEvent):
        if event.key in ['escape', 'f11']:
            self._fullscreen()

    @pyqtSlot()
    @pyqtSlot(bool)
    def _fullscreen(self):
        if self.plot.isFullScreen():
            self.plot.setWindowFlags(Qt.SubWindow)
            self.plot.showNormal()
            self.restoreState(self._state)
            self.restoreGeometry(self._geometry)
            self._update()
        else:
            self._geometry = self.saveGeometry()
            self._state = self.saveState()
            self.plot.setWindowFlags(Qt.Window)
            self.plot.showFullScreen()
            self._update()

    def _set_colors(self):
        colors = matplotlib.pyplot.rcParams['axes.prop_cycle'].by_key()['color']
        for i in range(len(self.signals)):
            if self.signals[i].color is None:
                self.signals[i].color = colors[i % len(colors)]

    # TODO: Use mime types
    def _load(self, filename: str) -> None:
        if os.path.isfile(filename):
            dialog: QFileDialog = self.sender()
            if dialog.selectedNameFilter() == QCoreApplication.translate('FileDialog', 'Recon data files(*.txt)'):
                self._loadReconText(filename)
            elif dialog.selectedNameFilter() == QCoreApplication.translate('FileDialog', 'COMTRADE data files(*.cfg)'):
                self._loadComtrade(filename)

    def _loadComtrade(self, filename: str) -> None:
        pass

    def _loadReconText(self, filename: str) -> None:
        if os.path.isfile(filename):
            self.dataFileName = filename
            doAutoRange = True

            # Save path for next use
            QSettings().setValue('default_data_path', os.path.dirname(os.path.abspath(filename)))
            self._add_to_recent(filename)

            # Change window title
            self.setWindowTitle(QCoreApplication.translate('Main', 'Recon plotter - {0}').format(self.dataFileName))

            # Reset signals
            self.times.clear()
            self.signals.clear()

            # Open data file
            with open(self.dataFileName, 'r', encoding='cp1251') as df:

                # Get total size
                total = os.fstat(df.fileno()).st_size
                self.progressBegin(total)

                # Get name of the recon record
                if line := df.readline():
                    data = readCommaSeparatedLine(line)
                    if len(data) >= 1:
                        self.title = data[0]
                    if len(data) >= 2:
                        self.device = data[1]
                    if len(data) >= 3:
                        self.originalFileName = data[2]
                    if len(data) >= 4:
                        self.axisX = data[3]
                    if len(data) >= 5:
                        self.axisY = data[4]
                    if len(data) >= 6:
                        self.range.left = float(data[5])
                    if len(data) >= 7:
                        self.range.right = float(data[6])
                    if len(data) >= 8:
                        self.range.bottom = float(data[7])
                    if len(data) >= 9:
                        self.range.top = float(data[8])
                    if len(data) >= 10:
                        self.lineWidth = float(data[9])
                        doAutoRange = False

                # Get signal names
                while (line := df.readline()) != '':
                    signal = None
                    data = readCommaSeparatedLine(line)
                    if len(data) and data[0] == '1':
                        continue
                    if len(data) and data[0] == 'N':
                        break
                    if len(data) >= 3:
                        signal = AnalogSignal(data[2])
                    if len(data) >= 4 and data[3] != '':
                        signal.selected = strtobool(data[3])
                    if len(data) >= 5:
                        signal.scale = float(data[4])
                    if len(data) >= 6:
                        signal.smooth = int(data[5])
                    if signal is not None:
                        self.signals.append(signal)

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
            self.actionAutoRange.setEnabled(True)
            self.widgetUpdate.setEnabled(True)
            self.widgetTitle.setText(self.title)
            self.widgetAxisX.setText(self.axisX)
            self.widgetAxisY.setText(self.axisY)
            self.autoRange() if doAutoRange else self.updateRange()
            self.rebuildSignalsDock()
            self._update()

    def _saveReconText(self, filename: str) -> None:
        with open(filename, 'w', encoding='cp1251') as df:

            self._add_to_recent(filename)

            self.progressBegin(len(self.times))
            lasttime = time()

            # write header
            df.write(writeCommaSeparatedLine([
                self.title,
                self.device,
                self.originalFileName,
                self.axisX,
                self.axisY,
                f'{self.range.left:g}',
                f'{self.range.right:g}',
                f'{self.range.bottom:g}',
                f'{self.range.top:g}',
                f'{self.lineWidth:g}'
            ]) + '\n\n')

            # write signals descriptions
            for i in range(len(self.signals)):
                df.write(writeCommaSeparatedLine([
                    f'{i+3:4d}',
                    f'АК-{i+1}',
                    self.signals[i].name,
                    self.signals[i].selected,
                    self.signals[i].scale,
                    self.signals[i].smooth,
                    self.signals[i].color
                ]) + '\n')

            # write table header
            df.write('\n         1,              2,')
            for i in range(len(self.signals)):
                df.write(f'{i+3:10d},')
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
                    if self.signals[j].inverted:
                        df.write(f'{-self.signals[j].data[i]+0:10.3f},')
                    else:
                        df.write(f'{self.signals[j].data[i]:10.3f},')
                df.write('\n')

            self.progressEnd()

            # Change window title
            self.dataFileName = filename
            self.setWindowTitle(QCoreApplication.translate('Main', 'Recon plotter - {0}').format(self.dataFileName))

    def _update(self):

        self.figure.clear()
        self.ax: Axes = self.figure.subplots()

        addLegend: bool = False
        for signal in self.signals:
            if signal.selected:
                signal.update()
                self.ax.plot(self.times, signal.getData(), label=signal.getName(), linewidth=self.lineWidth, color=signal.color)
                addLegend = True

        self.ax.axis([self.range.left, self.range.right, self.range.bottom, self.range.top])
        self.ax.set_title(self.title)
        self.ax.set_xlabel(self.axisX)
        self.ax.set_ylabel(self.axisY)
        if addLegend:
            self.ax.legend(loc='best')
        self.ax.grid(b=True, which='major', linestyle='-')
        self.ax.grid(b=True, which='minor', linestyle=':')
        self.ax.minorticks_on()

        self.selector = matplotlib.widgets.RectangleSelector(
            ax=self.ax,
            onselect=self._select_callback,
            drawtype='box',
            useblit=True,
            button=[matplotlib.backend_bases.MouseButton.RIGHT],
            rectprops=dict(facecolor="red", edgecolor="black", alpha=0.2, fill=True)
        )

        self.figure.tight_layout()
        self.figure.canvas.draw()

        self.actionSavePlot.setEnabled(True)
        self.actionSavePlotAs.setEnabled(True)

    def _savePlot(self, filename: str) -> None:
        self.plotFileName = filename
        QSettings().setValue('default_plot_path', os.path.dirname(os.path.abspath(filename)))

        fig: Figure = Figure()
        ax: Axes = fig.subplots()

        for signal in self.signals:
            if signal.selected:
                ax.plot(self.times, signal.getData(), label=signal.getName(), linewidth=self.lineWidth, color=signal.color)

        ax.axis([self.range.left, self.range.right, self.range.bottom, self.range.top])
        ax.set_title(self.title)
        ax.set_xlabel(self.axisX)
        ax.set_ylabel(self.axisY)
        ax.legend(loc='best')
        ax.grid(b=True, which='major', linestyle='-')
        ax.grid(b=True, which='minor', linestyle=':')
        ax.minorticks_on()

        fig.tight_layout()
        fig.set_size_inches(self.pageSize.width(), self.pageSize.height())
        fig.savefig(filename, dpi=self.dpi)
        fig.clf()

        self.statusBar().showMessage(
            QCoreApplication.translate('Status', 'Plot "{0}" saved.').format(filename),
            timeout=5000
        )


def qt_message_handler(mode: QtMsgType, context: QMessageLogContext, message: str):
    if mode == QtMsgType.QtDebugMsg:
        logging.debug(message)
    elif mode == QtMsgType.QtCriticalMsg:
        logging.critical(message)
    elif mode == QtMsgType.QtFatalMsg:
        logging.critical(message)
    elif mode == QtMsgType.QtInfoMsg:
        logging.info(message)
    elif mode == QtMsgType.QtSystemMsg:
        logging.debug(message)
    elif mode == QtMsgType.QtWarningMsg:
        logging.warning(message)
    print(message)


def main():
    path = os.path.dirname(os.path.realpath(__file__))
    logging.basicConfig(
        format='%(asctime)s %(levelname)s: %(message)s',
        filename=f'{path}/recon.log',
        filemode='w',
        encoding='utf-8',
        level=logging.DEBUG
    )
    qInstallMessageHandler(qt_message_handler)

    qDebug(f'Qt version: {qVersion()}')

    # Increase matplotlib limit
    matplotlib.rcParams['agg.path.chunksize'] = 100000

    app = QApplication(sys.argv)
    app.setOrganizationName('Oleksandr Kolodkin')
    app.setApplicationName('Recon Plotter')
    app.setStyle(QStyleFactory.create('Fusion'))

    qtTranslator = QTranslator(app)
    ok: bool = qtTranslator.load(QLocale(), 'qt', '_', QLibraryInfo.location(QLibraryInfo.TranslationsPath))
    qDebug('The system translation loaded successfully.' if ok else 'Failed to load the system translation.')
    app.installTranslator(qtTranslator)

    myTranslator = QTranslator(app)
    ok: bool = myTranslator.load(QLocale(), 'recon', '_', '.', '.qm')
    qDebug('The application translation loaded successfully.' if ok else 'Failed to load the application translation.')
    app.installTranslator(myTranslator)

    window = Recon()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
