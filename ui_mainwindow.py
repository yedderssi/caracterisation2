# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'mainwindow.ui'
##
## Created by: Qt User Interface Compiler version 6.5.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PyQt5.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PyQt5.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PyQt5.QtWidgets import (QApplication, QMainWindow, QMenu, QMenuBar,
    QSizePolicy, QStatusBar, QWidget)

from matplot import Matplot

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(595, 524)
        self.actionNouveau = QAction(MainWindow)
        self.actionNouveau.setObjectName(u"actionNouveau")
        self.actionOuvrir = QAction(MainWindow)
        self.actionOuvrir.setObjectName(u"actionOuvrir")
        self.actionOuvrir_une_configuration = QAction(MainWindow)
        self.actionOuvrir_une_configuration.setObjectName(u"actionOuvrir_une_configuration")
        self.actionEnregistrer = QAction(MainWindow)
        self.actionEnregistrer.setObjectName(u"actionEnregistrer")
        self.actionEnregistrer_sous = QAction(MainWindow)
        self.actionEnregistrer_sous.setObjectName(u"actionEnregistrer_sous")
        self.actionConfiguration = QAction(MainWindow)
        self.actionConfiguration.setObjectName(u"actionConfiguration")
        self.actionContact = QAction(MainWindow)
        self.actionContact.setObjectName(u"actionContact")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.widget = Matplot(self.centralwidget)
        self.widget.setObjectName(u"widget")
        self.widget.setGeometry(QRect(10, 20, 561, 441))
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 595, 22))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        self.menuModifier = QMenu(self.menubar)
        self.menuModifier.setObjectName(u"menuModifier")
        self.menuAide = QMenu(self.menubar)
        self.menuAide.setObjectName(u"menuAide")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuModifier.menuAction())
        self.menubar.addAction(self.menuAide.menuAction())
        self.menuFile.addAction(self.actionNouveau)
        self.menuFile.addAction(self.actionOuvrir)
        self.menuFile.addAction(self.actionOuvrir_une_configuration)
        self.menuFile.addAction(self.actionEnregistrer)
        self.menuFile.addAction(self.actionEnregistrer_sous)
        self.menuModifier.addAction(self.actionConfiguration)
        self.menuAide.addAction(self.actionContact)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.actionNouveau.setText(QCoreApplication.translate("MainWindow", u"Nouveau", None))
        self.actionOuvrir.setText(QCoreApplication.translate("MainWindow", u"Ouvrir", None))
        self.actionOuvrir_une_configuration.setText(QCoreApplication.translate("MainWindow", u"Ouvrir une configuration", None))
        self.actionEnregistrer.setText(QCoreApplication.translate("MainWindow", u"Enregistrer", None))
        self.actionEnregistrer_sous.setText(QCoreApplication.translate("MainWindow", u"Enregistrer sous", None))
        self.actionConfiguration.setText(QCoreApplication.translate("MainWindow", u"Configuration", None))
        self.actionContact.setText(QCoreApplication.translate("MainWindow", u"Contact", None))
        self.menuFile.setTitle(QCoreApplication.translate("MainWindow", u"Fichier", None))
        self.menuModifier.setTitle(QCoreApplication.translate("MainWindow", u"Modifier", None))
        self.menuAide.setTitle(QCoreApplication.translate("MainWindow", u"Aide", None))
    # retranslateUi

