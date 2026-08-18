# pyuic5 mainwindow.ui -o MainWindow.py
# valeur de configuration s'efface Done
# organiser les threads Done
# import et export de la configuration Done
# ajout de calcul
# enlever le suffixe dans le spin d'enregistrement
import sys,datetime,os
from PyQt5 import QtWidgets, uic
from MainWindow import Ui_JTcontrol
from configuration import Ui_Dialog
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget, QDialog, QGridLayout,QPushButton, QFileDialog
from PyQt5.QtCore import QThread, pyqtSignal, QSettings
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

Hauteur = Di = De = Section = Ns1 = Ns2 = Rs = Rh = Freq = Ampli = Gain = Nbre_enregist = Kf = Mu = 0
Nbre_periode = 2
Materiaux = "Fer pur"
Outils = "Cadre Epstein"
Type = "Cycle d'hystérèsis"
Forme = "Sinusoïdale"
Nm_ref = "Nom_Ref"
cnf = None
class MplCanvas(FigureCanvasQTAgg):
    
    #Configuration de l'intialisation du canva pour le trace
    
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)

class Worker(QThread):
    finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def run(self):
        import time
        time.sleep(5)
        # Picoscope
        self.finished.emit()

class ConfigWindow(QDialog, Ui_Dialog):
    def __init__(self, *args, obj=None, **kwargs):
        super(ConfigWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle("Configuration")
        self.warning_edit_ech.setVisible(False)
        self.warning_edit_Mes.setVisible(False)
        self.warning_edit_Bob.setVisible(False)
        self.Materiaux_combo.setCurrentText(Materiaux)
        self.Hauteur_spin.setValue(Hauteur)
        self.Di_spin.setValue(Di)
        self.De_spin.setValue(De)
        self.section_spin.setValue(Section)
        self.outils_combo.setCurrentText(Outils)
        self.Ns1_spin.setValue(Ns1)
        self.Ns2_spin.setValue(Ns2)
        self.Rh_spin.setValue(Rh)
        self.Rs_spin.setValue(Rs)
        self.Type_combo.setCurrentText(Type)
        self.forme_combo.setCurrentText(Forme)
        self.freq_spin.setValue(Freq)
        self.Ampli_spin.setValue(Ampli)
        self.GA_spin.setValue(Gain)
        self.nbre_periode_slider.setValue(Nbre_periode)
        self.Nbre_enregi_spin.setValue(Nbre_enregist)
        self.Kf_spin.setValue(Kf)
        self.Nm_ref_edit.setText(Nm_ref)
        self.Mu_spin.setValue(Mu)
        self.outils_combo.currentTextChanged.connect(self.selectionchange)
    
    def selectionchange(self,var):
        global Outils
        Outils = var
        print(Outils)

    def accept(self):
        global Materiaux,Hauteur,Di,De,Section,Outils,Ns1,Ns2,Rs,Rh,Type,Forme,Freq,Ampli,Gain,Nbre_periode,Nbre_enregist,Kf,Nm_ref,Mu
        Materiaux = self.Materiaux_combo.currentText()
        Hauteur = self.Hauteur_spin.value()
        Di = self.Di_spin.value()
        De = self.De_spin.value()
        Section = self.section_spin.value()
        Outils = self.outils_combo.currentText()
        Ns1 = self.Ns1_spin.value()
        Ns2 = self.Ns2_spin.value()
        Rh = self.Rh_spin.value()
        Rs = self.Rs_spin.value()
        Type = self.Type_combo.currentText()
        Forme = self.forme_combo.currentText()
        Freq = self.freq_spin.value()
        Ampli = self.Ampli_spin.value()
        Gain = self.GA_spin.value()
        Nbre_periode = self.nbre_periode_slider.value()
        Nbre_enregist = self.Nbre_enregi_spin.value()
        Kf = self.Kf_spin.value()
        Nm_ref = self.Nm_ref_edit.text()
        Mu = self.Mu_spin.value()
        print(Nm_ref,Materiaux,Hauteur,Di,De,Section,Outils,Ns1,Ns2,Rs,Rh,Type,Forme,Freq,Ampli,Gain,Nbre_periode,Nbre_enregist,Kf,Mu)
        self.close()

class MainWindow(QtWidgets.QMainWindow, Ui_JTcontrol):
    def __init__(self, *args, obj=None, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowIcon(QIcon('Logo.png'))
        self.setWindowTitle("JTcontrol")
        self.sc1 = MplCanvas(self, width=5, height=4, dpi=100)
        self.sc2 = MplCanvas(self, width=5, height=4, dpi=100)
        self.sc3 = MplCanvas(self, width=5, height=4, dpi=100)
        self.sc1.axes.plot([0,1,2,3,4], [10,1,20,3,40])
        self.sc2.axes.plot([0,1,2,3,4], [5,30,20,25,40])
        self.sc3.axes.plot([0,1,2,3,4], [30,35,20,10,40])

        toolbar1 = NavigationToolbar(self.sc1, self)
        toolbar2 = NavigationToolbar(self.sc2, self)
        toolbar3 = NavigationToolbar(self.sc3, self)
        
        self.start_btn = QPushButton('Start')
        self.start_btn.clicked.connect(self.start)
        self.start_btn.setEnabled(True)
        
        layout2 = QGridLayout()
        layout2.addWidget(toolbar1,4,0,1,10)
        layout2.addWidget(self.sc1,5,0,1,10)
        layout2.addWidget(toolbar2,6,0,1,10)
        layout2.addWidget(self.sc2,7,0,1,10)
        layout2.addWidget(toolbar3,4,11,1,10)
        layout2.addWidget(self.sc3,5,11,1,10)
        layout2.addWidget(self.start_btn,3,11)
        widget = QWidget()
        widget.setLayout(layout2)
        self.setCentralWidget(widget)
        self.thread = None
        self._connectActions()
        
    def _connectActions(self):
        # Connect File actions
        self.actionConfiguration.triggered.connect(self.set_config)
        self.actionOuvrir_une_configuration.triggered.connect(self.opens_config)
        self.actionEnregistrer_sous.triggered.connect(self.saves_config)
        self.actionEnregistrer.triggered.connect(self.saves_project)
    def set_config(self):
            self.w = ConfigWindow()
            self.w.show()
            
    def opens_config(self):
        global Materiaux,Hauteur,Di,De,Section,Outils,Ns1,Ns2,Rs,Rh,Type,Forme,Freq,Ampli,Gain,Nbre_periode,Nbre_enregist,Nm_ref,Mu,Kf
        config_path, _ = QFileDialog.getOpenFileName(self, 'Load Configuration', '', 'Config Files (*.cfg)')
        if not config_path:
            return

        # create a QSettings object with the given configuration file path
        settings = QSettings(config_path, QSettings.IniFormat)
        
        Nm_ref = str(settings.value("Nom_ref", "Nom_Ref"))
        Materiaux = str(settings.value("Materiaux_value", "Fer pur"))
        Hauteur = float(settings.value("Hauteur_value", 0))
        Di = float(settings.value("Di_value", 0))
        De = float(settings.value("De_value", 0))
        Section = float(settings.value("Section_value", 0))
        Outils = str(settings.value("Outils_value", "Cadre Epstein"))
        Ns1 = int(settings.value("Ns1_value", 0))
        Ns2 = int(settings.value("Ns2_value", 0))
        Rs = float(settings.value("Rs_value", 0))
        Rh = float(settings.value("Rh_value", 0))
        Type = str(settings.value("Type_value", "Cycle d'hystérèsis"))
        Forme = str(settings.value("Forme_value", "Sinusoïdale"))
        Freq = float(settings.value("Freq_value", 0.0))
        Ampli = float(settings.value("Ampli_value", 0.0))
        Gain = int(settings.value("Gain_value", 0.0))
        Nbre_periode = int(settings.value("Nbre_periode_value", 2))
        Nbre_enregist = int(settings.value("Nbre_enregist_value", 0))
        Kf = int(settings.value("Kf_value", 0))
        Mu = int(settings.value("Mu_value", 0))
    
    def saves_config(self):
        now = datetime.datetime.now()
        date_time = now.strftime("%Y-%m-%d_%H-%M-%S")
        config_path, _ = QFileDialog.getSaveFileName(self, 'Save Configuration', f"configuration_{date_time}.cfg", 'Config Files (*.cfg)')
        if not config_path:
            return
        settings = QSettings(config_path, QSettings.IniFormat)
        settings.setValue("Nom_ref", Nm_ref)
        settings.setValue("Materiaux_value", Materiaux)
        settings.setValue("Hauteur_value", Hauteur)
        settings.setValue("Di_value", Di)
        settings.setValue("De_value", De)
        settings.setValue("Section_value", Section)
        settings.setValue("Outils_value", Outils)
        settings.setValue("Ns1_value", Ns1)
        settings.setValue("Ns2_value", Ns2)
        settings.setValue("Rs_value", Rs)
        settings.setValue("Rh_value", Rh)
        settings.setValue("Type_value", Type)
        settings.setValue("Forme_value", Forme)
        settings.setValue("Freq_value", Freq)
        settings.setValue("Ampli_value", Ampli)
        settings.setValue("Gain_value", Gain)
        settings.setValue("Nbre_periode_value", Nbre_periode)
        settings.setValue("Nbre_enregist_value", Nbre_enregist)
        settings.setValue("Kf_value", Kf)
        settings.setValue("Mu_value", Mu)
            
    def saves_project(self):
        selected_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select a directory')
        if selected_dir:
            config_dir = os.path.join(selected_dir, Nm_ref)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
            now = datetime.datetime.now()
            date_time = now.strftime("%Y-%m-%d_%H-%M-%S")
            settings = QSettings(os.path.join(config_dir, f"configuration_{date_time}.cfg"), QSettings.IniFormat)
            settings.setValue("Nom_ref", Nm_ref)
            settings.setValue("Materiaux_value", Materiaux)
            settings.setValue("Hauteur_value", Hauteur)
            settings.setValue("Di_value", Di)
            settings.setValue("De_value", De)
            settings.setValue("Section_value", Section)
            settings.setValue("Outils_value", Outils)
            settings.setValue("Ns1_value", Ns1)
            settings.setValue("Ns2_value", Ns2)
            settings.setValue("Rs_value", Rs)
            settings.setValue("Rh_value", Rh)
            settings.setValue("Type_value", Type)
            settings.setValue("Forme_value", Forme)
            settings.setValue("Freq_value", Freq)
            settings.setValue("Ampli_value", Ampli)
            settings.setValue("Gain_value", Gain)
            settings.setValue("Nbre_periode_value", Nbre_periode)
            settings.setValue("Nbre_enregist_value", Nbre_enregist)
            settings.setValue("Kf_value", Kf)
            settings.setValue("Mu_value", Mu)
    def start(self):
        if self.thread is None or not self.thread.isRunning():
            self.start_btn.setEnabled(False)
            self.thread = Worker()
            self.thread.finished.connect(self.on_long_task_finished)
            self.thread.start()

    def on_long_task_finished(self):
        self.start_btn.setEnabled(True)
        print("Done.")
        self.thread = None
        
    def closeEvent(self,event):
        for window in QtWidgets.QApplication.topLevelWidgets():
            window.close()
        QtWidgets.QApplication.quit()
        
    def get_data(self):
        # Check if the QDialog was accepted
        if self.result() == QDialog.Accepted:
            # Retrieve the values of the QWidgets and return them
            my_text = self.text_edit.text()
            my_value = self.spin_box.value()
            return my_text, my_value
        else:
            # Return None if the QDialog was rejected
            return None
app = QtWidgets.QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec()
                          