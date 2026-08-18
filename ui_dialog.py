# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'dialog.ui'
##
## Created by: Qt User Interface Compiler version 6.5.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QAbstractButton, QApplication, QComboBox, QDialog,
    QDialogButtonBox, QDoubleSpinBox, QGridLayout, QLabel,
    QLayout, QSizePolicy, QSlider, QSpinBox,
    QTabWidget, QWidget)

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        if not Dialog.objectName():
            Dialog.setObjectName(u"Dialog")
        Dialog.resize(580, 424)
        Dialog.setSizeGripEnabled(True)
        self.buttonBox = QDialogButtonBox(Dialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setGeometry(QRect(360, 370, 191, 32))
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Apply|QDialogButtonBox.Close)
        self.buttonBox.setCenterButtons(False)
        self.tabWidget = QTabWidget(Dialog)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tabWidget.setGeometry(QRect(0, 0, 571, 411))
        self.tabWidget.setTabShape(QTabWidget.Rounded)
        self.Tab_ech = QWidget()
        self.Tab_ech.setObjectName(u"Tab_ech")
        self.gridLayoutWidget = QWidget(self.Tab_ech)
        self.gridLayoutWidget.setObjectName(u"gridLayoutWidget")
        self.gridLayoutWidget.setGeometry(QRect(90, 60, 391, 241))
        self.gridLayout = QGridLayout(self.gridLayoutWidget)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setSizeConstraint(QLayout.SetDefaultConstraint)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.comboBox = QComboBox(self.gridLayoutWidget)
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.addItem("")
        self.comboBox.setObjectName(u"comboBox")
        self.comboBox.setMinimumSize(QSize(100, 0))

        self.gridLayout.addWidget(self.comboBox, 0, 1, 1, 1)

        self.label_2 = QLabel(self.gridLayoutWidget)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.label_2.setMargin(6)

        self.gridLayout.addWidget(self.label_2, 1, 0, 1, 1)

        self.doubleSpinBox_3 = QDoubleSpinBox(self.gridLayoutWidget)
        self.doubleSpinBox_3.setObjectName(u"doubleSpinBox_3")
        self.doubleSpinBox_3.setAlignment(Qt.AlignCenter)
        self.doubleSpinBox_3.setMaximum(10000000000000000000000.000000000000000)

        self.gridLayout.addWidget(self.doubleSpinBox_3, 3, 1, 1, 1)

        self.doubleSpinBox_2 = QDoubleSpinBox(self.gridLayoutWidget)
        self.doubleSpinBox_2.setObjectName(u"doubleSpinBox_2")
        self.doubleSpinBox_2.setAlignment(Qt.AlignCenter)
        self.doubleSpinBox_2.setMaximum(999999999999999983222784.000000000000000)

        self.gridLayout.addWidget(self.doubleSpinBox_2, 2, 1, 1, 1)

        self.doubleSpinBox = QDoubleSpinBox(self.gridLayoutWidget)
        self.doubleSpinBox.setObjectName(u"doubleSpinBox")
        self.doubleSpinBox.setAlignment(Qt.AlignCenter)
        self.doubleSpinBox.setDecimals(2)
        self.doubleSpinBox.setMaximum(999999999999999983222784.000000000000000)

        self.gridLayout.addWidget(self.doubleSpinBox, 1, 1, 1, 1)

        self.label_4 = QLabel(self.gridLayoutWidget)
        self.label_4.setObjectName(u"label_4")
        self.label_4.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.label_4.setMargin(6)

        self.gridLayout.addWidget(self.label_4, 3, 0, 1, 1)

        self.label = QLabel(self.gridLayoutWidget)
        self.label.setObjectName(u"label")
        self.label.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.label.setMargin(6)

        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)

        self.label_3 = QLabel(self.gridLayoutWidget)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.label_3.setMargin(6)

        self.gridLayout.addWidget(self.label_3, 2, 0, 1, 1)

        self.label_5 = QLabel(self.gridLayoutWidget)
        self.label_5.setObjectName(u"label_5")
        self.label_5.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.label_5.setMargin(6)

        self.gridLayout.addWidget(self.label_5, 4, 0, 1, 1)

        self.label_6 = QLabel(self.gridLayoutWidget)
        self.label_6.setObjectName(u"label_6")
        self.label_6.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.label_6, 1, 2, 1, 1)

        self.label_7 = QLabel(self.gridLayoutWidget)
        self.label_7.setObjectName(u"label_7")
        self.label_7.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.label_7, 2, 2, 1, 1)

        self.label_8 = QLabel(self.gridLayoutWidget)
        self.label_8.setObjectName(u"label_8")
        self.label_8.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.label_8, 3, 2, 1, 1)

        self.label_9 = QLabel(self.gridLayoutWidget)
        self.label_9.setObjectName(u"label_9")
        self.label_9.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.label_9, 4, 2, 1, 1)

        self.doubleSpinBox_4 = QDoubleSpinBox(self.gridLayoutWidget)
        self.doubleSpinBox_4.setObjectName(u"doubleSpinBox_4")
        self.doubleSpinBox_4.setAlignment(Qt.AlignCenter)
        self.doubleSpinBox_4.setMaximum(100000000000000004764729344.000000000000000)

        self.gridLayout.addWidget(self.doubleSpinBox_4, 4, 1, 1, 1)

        self.tabWidget.addTab(self.Tab_ech, "")
        self.tab_bobine = QWidget()
        self.tab_bobine.setObjectName(u"tab_bobine")
        self.gridLayoutWidget_2 = QWidget(self.tab_bobine)
        self.gridLayoutWidget_2.setObjectName(u"gridLayoutWidget_2")
        self.gridLayoutWidget_2.setGeometry(QRect(50, 60, 409, 241))
        self.gridLayout_2 = QGridLayout(self.gridLayoutWidget_2)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setSizeConstraint(QLayout.SetDefaultConstraint)
        self.gridLayout_2.setContentsMargins(0, 0, 0, 0)
        self.comboBox_2 = QComboBox(self.gridLayoutWidget_2)
        self.comboBox_2.addItem("")
        self.comboBox_2.addItem("")
        self.comboBox_2.addItem("")
        self.comboBox_2.addItem("")
        self.comboBox_2.setObjectName(u"comboBox_2")
        self.comboBox_2.setMinimumSize(QSize(122, 0))

        self.gridLayout_2.addWidget(self.comboBox_2, 0, 1, 1, 1)

        self.label_10 = QLabel(self.gridLayoutWidget_2)
        self.label_10.setObjectName(u"label_10")
        self.label_10.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.label_10.setMargin(6)

        self.gridLayout_2.addWidget(self.label_10, 1, 0, 1, 1)

        self.doubleSpinBox_5 = QDoubleSpinBox(self.gridLayoutWidget_2)
        self.doubleSpinBox_5.setObjectName(u"doubleSpinBox_5")
        self.doubleSpinBox_5.setAlignment(Qt.AlignCenter)
        self.doubleSpinBox_5.setMaximum(9999999.000000000000000)

        self.gridLayout_2.addWidget(self.doubleSpinBox_5, 3, 1, 1, 1)

        self.label_11 = QLabel(self.gridLayoutWidget_2)
        self.label_11.setObjectName(u"label_11")
        self.label_11.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.label_11.setMargin(6)

        self.gridLayout_2.addWidget(self.label_11, 3, 0, 1, 1)

        self.label_12 = QLabel(self.gridLayoutWidget_2)
        self.label_12.setObjectName(u"label_12")
        self.label_12.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.label_12.setMargin(6)

        self.gridLayout_2.addWidget(self.label_12, 0, 0, 1, 1)

        self.label_14 = QLabel(self.gridLayoutWidget_2)
        self.label_14.setObjectName(u"label_14")
        self.label_14.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.label_14.setMargin(6)

        self.gridLayout_2.addWidget(self.label_14, 4, 0, 1, 1)

        self.label_17 = QLabel(self.gridLayoutWidget_2)
        self.label_17.setObjectName(u"label_17")
        self.label_17.setAlignment(Qt.AlignCenter)

        self.gridLayout_2.addWidget(self.label_17, 3, 2, 1, 1)

        self.label_18 = QLabel(self.gridLayoutWidget_2)
        self.label_18.setObjectName(u"label_18")
        self.label_18.setAlignment(Qt.AlignCenter)

        self.gridLayout_2.addWidget(self.label_18, 4, 2, 1, 1)

        self.doubleSpinBox_8 = QDoubleSpinBox(self.gridLayoutWidget_2)
        self.doubleSpinBox_8.setObjectName(u"doubleSpinBox_8")
        self.doubleSpinBox_8.setAlignment(Qt.AlignCenter)
        self.doubleSpinBox_8.setMaximum(9999999.000000000000000)

        self.gridLayout_2.addWidget(self.doubleSpinBox_8, 4, 1, 1, 1)

        self.label_15 = QLabel(self.gridLayoutWidget_2)
        self.label_15.setObjectName(u"label_15")
        self.label_15.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.label_15.setMargin(6)

        self.gridLayout_2.addWidget(self.label_15, 2, 0, 1, 1)

        self.spinBox = QSpinBox(self.gridLayoutWidget_2)
        self.spinBox.setObjectName(u"spinBox")
        self.spinBox.setAlignment(Qt.AlignCenter)
        self.spinBox.setMaximum(999999)

        self.gridLayout_2.addWidget(self.spinBox, 1, 1, 1, 1)

        self.spinBox_2 = QSpinBox(self.gridLayoutWidget_2)
        self.spinBox_2.setObjectName(u"spinBox_2")
        self.spinBox_2.setAlignment(Qt.AlignCenter)
        self.spinBox_2.setMaximum(999999)

        self.gridLayout_2.addWidget(self.spinBox_2, 2, 1, 1, 1)

        self.tabWidget.addTab(self.tab_bobine, "")
        self.tab_mesure = QWidget()
        self.tab_mesure.setObjectName(u"tab_mesure")
        self.gridLayoutWidget_3 = QWidget(self.tab_mesure)
        self.gridLayoutWidget_3.setObjectName(u"gridLayoutWidget_3")
        self.gridLayoutWidget_3.setGeometry(QRect(110, 30, 381, 291))
        self.gridLayout_3 = QGridLayout(self.gridLayoutWidget_3)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.gridLayout_3.setSizeConstraint(QLayout.SetDefaultConstraint)
        self.gridLayout_3.setContentsMargins(0, 0, 0, 0)
        self.comboBox_3 = QComboBox(self.gridLayoutWidget_3)
        self.comboBox_3.addItem("")
        self.comboBox_3.setObjectName(u"comboBox_3")
        self.comboBox_3.setEnabled(False)
        self.comboBox_3.setMinimumSize(QSize(150, 0))
        self.comboBox_3.setEditable(False)

        self.gridLayout_3.addWidget(self.comboBox_3, 0, 1, 1, 1)

        self.spinBox_3 = QSpinBox(self.gridLayoutWidget_3)
        self.spinBox_3.setObjectName(u"spinBox_3")
        self.spinBox_3.setAlignment(Qt.AlignCenter)

        self.gridLayout_3.addWidget(self.spinBox_3, 6, 1, 1, 1)

        self.label_20 = QLabel(self.gridLayoutWidget_3)
        self.label_20.setObjectName(u"label_20")
        self.label_20.setAlignment(Qt.AlignCenter)

        self.gridLayout_3.addWidget(self.label_20, 2, 2, 1, 1)

        self.comboBox_4 = QComboBox(self.gridLayoutWidget_3)
        self.comboBox_4.addItem("")
        self.comboBox_4.addItem("")
        self.comboBox_4.addItem("")
        self.comboBox_4.setObjectName(u"comboBox_4")

        self.gridLayout_3.addWidget(self.comboBox_4, 1, 1, 1, 1)

        self.doubleSpinBox_7 = QDoubleSpinBox(self.gridLayoutWidget_3)
        self.doubleSpinBox_7.setObjectName(u"doubleSpinBox_7")
        self.doubleSpinBox_7.setAlignment(Qt.AlignCenter)
        self.doubleSpinBox_7.setMinimum(-9999.000000000000000)
        self.doubleSpinBox_7.setMaximum(9999.000000000000000)

        self.gridLayout_3.addWidget(self.doubleSpinBox_7, 3, 1, 1, 1)

        self.doubleSpinBox_6 = QDoubleSpinBox(self.gridLayoutWidget_3)
        self.doubleSpinBox_6.setObjectName(u"doubleSpinBox_6")
        self.doubleSpinBox_6.setAlignment(Qt.AlignCenter)
        self.doubleSpinBox_6.setMaximum(999999999.000000000000000)

        self.gridLayout_3.addWidget(self.doubleSpinBox_6, 2, 1, 1, 1)

        self.label_13 = QLabel(self.gridLayoutWidget_3)
        self.label_13.setObjectName(u"label_13")
        self.label_13.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.label_13.setMargin(6)

        self.gridLayout_3.addWidget(self.label_13, 0, 0, 1, 1)

        self.label_24 = QLabel(self.gridLayoutWidget_3)
        self.label_24.setObjectName(u"label_24")
        self.label_24.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.label_24.setMargin(6)

        self.gridLayout_3.addWidget(self.label_24, 6, 0, 1, 1)

        self.label_16 = QLabel(self.gridLayoutWidget_3)
        self.label_16.setObjectName(u"label_16")
        self.label_16.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.label_16.setMargin(6)

        self.gridLayout_3.addWidget(self.label_16, 1, 0, 1, 1)

        self.horizontalSlider = QSlider(self.gridLayoutWidget_3)
        self.horizontalSlider.setObjectName(u"horizontalSlider")
        font = QFont()
        font.setStyleStrategy(QFont.PreferDefault)
        self.horizontalSlider.setFont(font)
        self.horizontalSlider.setCursor(QCursor(Qt.ClosedHandCursor))
        self.horizontalSlider.setAcceptDrops(True)
        self.horizontalSlider.setMinimum(2)
        self.horizontalSlider.setMaximum(50)
        self.horizontalSlider.setOrientation(Qt.Horizontal)
        self.horizontalSlider.setTickPosition(QSlider.NoTicks)

        self.gridLayout_3.addWidget(self.horizontalSlider, 5, 1, 1, 1)

        self.label_19 = QLabel(self.gridLayoutWidget_3)
        self.label_19.setObjectName(u"label_19")
        self.label_19.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.label_19.setMargin(6)

        self.gridLayout_3.addWidget(self.label_19, 2, 0, 1, 1)

        self.label_periode = QLabel(self.gridLayoutWidget_3)
        self.label_periode.setObjectName(u"label_periode")
        self.label_periode.setAlignment(Qt.AlignCenter)

        self.gridLayout_3.addWidget(self.label_periode, 5, 2, 1, 1)

        self.label_23 = QLabel(self.gridLayoutWidget_3)
        self.label_23.setObjectName(u"label_23")
        self.label_23.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.label_23.setMargin(6)

        self.gridLayout_3.addWidget(self.label_23, 5, 0, 1, 1)

        self.label_22 = QLabel(self.gridLayoutWidget_3)
        self.label_22.setObjectName(u"label_22")
        self.label_22.setAlignment(Qt.AlignCenter)

        self.gridLayout_3.addWidget(self.label_22, 3, 2, 1, 1)

        self.label_21 = QLabel(self.gridLayoutWidget_3)
        self.label_21.setObjectName(u"label_21")
        self.label_21.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.label_21.setMargin(6)

        self.gridLayout_3.addWidget(self.label_21, 3, 0, 1, 1)

        self.label_25 = QLabel(self.gridLayoutWidget_3)
        self.label_25.setObjectName(u"label_25")
        self.label_25.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.label_25.setMargin(6)

        self.gridLayout_3.addWidget(self.label_25, 4, 0, 1, 1)

        self.spinBox_4 = QSpinBox(self.gridLayoutWidget_3)
        self.spinBox_4.setObjectName(u"spinBox_4")
        self.spinBox_4.setAlignment(Qt.AlignCenter)
        self.spinBox_4.setMaximum(1000)

        self.gridLayout_3.addWidget(self.spinBox_4, 4, 1, 1, 1)

        self.tabWidget.addTab(self.tab_mesure, "")
        self.tabWidget.raise_()
        self.buttonBox.raise_()

        self.retranslateUi(Dialog)
        self.buttonBox.accepted.connect(Dialog.accept)
        self.buttonBox.rejected.connect(Dialog.reject)
        self.horizontalSlider.valueChanged.connect(self.label_periode.setNum)

        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(Dialog)
    # setupUi

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QCoreApplication.translate("Dialog", u"Dialog", None))
        self.comboBox.setItemText(0, QCoreApplication.translate("Dialog", u"Fer pur", None))
        self.comboBox.setItemText(1, QCoreApplication.translate("Dialog", u"Fe-Si (N.O.)", None))
        self.comboBox.setItemText(2, QCoreApplication.translate("Dialog", u"Fe-Si (G.O.)", None))
        self.comboBox.setItemText(3, QCoreApplication.translate("Dialog", u"Fe-Ni (50-50) Hypernik", None))
        self.comboBox.setItemText(4, QCoreApplication.translate("Dialog", u"Fe-Ni (22-78) Permalloy", None))
        self.comboBox.setItemText(5, QCoreApplication.translate("Dialog", u"Supermalloy", None))
        self.comboBox.setItemText(6, QCoreApplication.translate("Dialog", u"Mum\u00e9tal", None))
        self.comboBox.setItemText(7, QCoreApplication.translate("Dialog", u"Fe-Co (65-35) Hyperco", None))
        self.comboBox.setItemText(8, QCoreApplication.translate("Dialog", u"Fe-Co (50-50) Permendur", None))
        self.comboBox.setItemText(9, QCoreApplication.translate("Dialog", u"Base amorphe Fe", None))
        self.comboBox.setItemText(10, QCoreApplication.translate("Dialog", u"Base amorphe Co", None))
        self.comboBox.setItemText(11, QCoreApplication.translate("Dialog", u"Acier doux", None))
        self.comboBox.setItemText(12, QCoreApplication.translate("Dialog", u"Ferrite Mn-Zn", None))
        self.comboBox.setItemText(13, QCoreApplication.translate("Dialog", u"Ferrite Ni-Zn", None))
        self.comboBox.setItemText(14, QCoreApplication.translate("Dialog", u"2V-Permendur", None))
        self.comboBox.setItemText(15, QCoreApplication.translate("Dialog", u"Fe-Ai (96-4)", None))
        self.comboBox.setItemText(16, QCoreApplication.translate("Dialog", u"Brose", None))

        self.label_2.setText(QCoreApplication.translate("Dialog", u"Hauteur", None))
        self.doubleSpinBox_3.setSuffix("")
        self.label_4.setText(QCoreApplication.translate("Dialog", u"Diam\u00e8tre ext\u00e9rieur De", None))
        self.label.setText(QCoreApplication.translate("Dialog", u"Mat\u00e9riaux", None))
        self.label_3.setText(QCoreApplication.translate("Dialog", u"Diam\u00e8tre int\u00e9rieur Di", None))
        self.label_5.setText(QCoreApplication.translate("Dialog", u"Section", None))
        self.label_6.setText(QCoreApplication.translate("Dialog", u"mm", None))
        self.label_7.setText(QCoreApplication.translate("Dialog", u"mm", None))
        self.label_8.setText(QCoreApplication.translate("Dialog", u"mm", None))
        self.label_9.setText(QCoreApplication.translate("Dialog", u"mm\u00b2", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.Tab_ech), QCoreApplication.translate("Dialog", u"Echantillon", None))
        self.comboBox_2.setItemText(0, QCoreApplication.translate("Dialog", u"Cadre Epstein", None))
        self.comboBox_2.setItemText(1, QCoreApplication.translate("Dialog", u"Tore empil\u00e9", None))
        self.comboBox_2.setItemText(2, QCoreApplication.translate("Dialog", u"Tore enroul\u00e9", None))
        self.comboBox_2.setItemText(3, QCoreApplication.translate("Dialog", u"SST", None))

        self.label_10.setText(QCoreApplication.translate("Dialog", u"Nombres de spires au primaire", None))
        self.label_11.setText(QCoreApplication.translate("Dialog", u"R\u00e9sistance shunt", None))
        self.label_12.setText(QCoreApplication.translate("Dialog", u"Outils de mesures", None))
        self.label_14.setText(QCoreApplication.translate("Dialog", u"R\u00e9sistance s\u00e9rie", None))
        self.label_17.setText(QCoreApplication.translate("Dialog", u"ohms", None))
        self.label_18.setText(QCoreApplication.translate("Dialog", u"ohms", None))
        self.label_15.setText(QCoreApplication.translate("Dialog", u"Nombres de spires au secondaire", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_bobine), QCoreApplication.translate("Dialog", u"Bobine", None))
        self.comboBox_3.setItemText(0, QCoreApplication.translate("Dialog", u"Cycle d'hyst\u00e9r\u00e8sis", None))

        self.spinBox_3.setSuffix(QCoreApplication.translate("Dialog", u"0", None))
        self.label_20.setText(QCoreApplication.translate("Dialog", u"Hz", None))
        self.comboBox_4.setItemText(0, QCoreApplication.translate("Dialog", u"Sinuso\u00efdale B", None))
        self.comboBox_4.setItemText(1, QCoreApplication.translate("Dialog", u"Trap\u00e9zo\u00efdal B", None))
        self.comboBox_4.setItemText(2, QCoreApplication.translate("Dialog", u"Triangulaire B", None))
        self.label_13.setText(QCoreApplication.translate("Dialog", u"Type de mesures", None))
        self.label_24.setText(QCoreApplication.translate("Dialog", u"Nombres d'enregistrement", None))
        self.label_16.setText(QCoreApplication.translate("Dialog", u"Forme d'onde", None))
        self.label_19.setText(QCoreApplication.translate("Dialog", u"Fr\u00e9quence", None))
        self.label_periode.setText(QCoreApplication.translate("Dialog", u"2", None))
        self.label_23.setText(QCoreApplication.translate("Dialog", u"Nombres de p\u00e9riodes", None))
        self.label_21.setText(QCoreApplication.translate("Dialog", u"Amplitude", None))
        self.label_22.setText(QCoreApplication.translate("Dialog", u"(T)", None))
        self.label_25.setText(QCoreApplication.translate("Dialog", u"Gain de l'amplificateur", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_mesure), QCoreApplication.translate("Dialog", u"Mesure", None))
     #retranslateUi

