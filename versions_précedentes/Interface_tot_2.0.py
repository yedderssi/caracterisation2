# pyuic5 mainwindow.ui -o MainWindow.py
# valeur de configuration s'efface Done
# organiser les threads Done
# import et export de la configuration Done
# ajout de calcul
# enlever le suffixe dans le spin d'enregistrement
import sys
import datetime
import os,random
from PyQt5 import QtWidgets, uic
from MainWindow import Ui_JTcontrol
from Supervision import Ui_supervision
from page_acquisition import Ui_Page_acquisition
from configuration import Ui_Dialog
from Notes import Ui_notes
from curve_comparaison import Ui_curve_comparaison
from PyQt5.QtGui import QIcon,QColor
from PyQt5.QtWidgets import QWidget, QColorDialog, QTableWidgetItem, QDialogButtonBox, QComboBox, QDialog, QGridLayout, QPushButton, QFileDialog, QVBoxLayout
from PyQt5.QtCore import QThread, pyqtSignal, QSettings, QSize
import csv
Hauteur = Di = De = Section = Ns1 = Ns2 = Rs = Rh = Freq = Ampli = Gain = Nbre_enregist = Kf = Mu = lm = Epaisseur = Nbre_Bandes = Largeur = 0
Nbre_periode = 2
Materiaux = "Fer pur"
Outils = "Tore enroulé"
Type = "Cycle d'hystérèsis"
Forme = "Sinusoïdale"
Nm_ref = "Nom_Ref"


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
    def __init__(self, *args, parent=None, **kwargs):
        super(ConfigWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle("Configuration")
        self.warning_edit_ech.setVisible(False)
        self.warning_edit_Mes.setVisible(False)
        self.warning_edit_Bob.setVisible(False)
        if (Outils == "Cadre Epstein personnalisé") or (Outils == "Cadre Epstein Standard"):
            self.Hauteur_label.setText("Epaisseur")
            self.Di_label.setText("Largeur")
            self.De_label.setText("Nbre de Bandes")
            self.De_spin.setDecimals(0)
            self.De_unite.setVisible(False)
        else:
            self.Hauteur_label.setText("Hauteur")
            self.Di_label.setText("Diamètre intérieur Di")
            self.De_label.setText("Diamètre extérieur De")
            self.De_spin.setDecimals(2)
            self.De_unite.setVisible(True)
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
        self.lm_spin.setValue(lm)
        self.outils_combo.currentTextChanged.connect(self.selectionchange)

    def selectionchange(self, var):
        global Outils
        Outils = var
        if (Outils == "Cadre Epstein personnalisé") or (Outils == "Cadre Epstein Standard"):
            self.Hauteur_label.setText("Epaisseur")
            self.Di_label.setText("Largeur")
            self.De_label.setText("Nbre de Bandes")
            self.De_spin.setDecimals(0)
            self.De_unite.setVisible(False)
        else:
            self.Hauteur_label.setText("Hauteur")
            self.Di_label.setText("Diamètre intérieur Di")
            self.De_label.setText("Diamètre extérieur De")
            self.De_spin.setDecimals(2)
            self.De_unite.setVisible(True)

    def accept(self):
        global Materiaux, Hauteur, Di, De, Section, Outils, Ns1, Ns2, Rs, Rh, Type, Forme, Freq, Ampli, Gain, Nbre_periode, Nbre_enregist, Kf, Nm_ref, Mu, lm
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
        lm = self.lm_spin.value()
        main_window = self.parent()
        main_window.update_data(Outils, Materiaux, Di,
                                De, Hauteur, Section, lm, Kf)
        print(Nm_ref, Materiaux, Hauteur, Di, De, Section, Outils, Ns1, Ns2, Rs,
              Rh, Type, Forme, Freq, Ampli, Gain, Nbre_periode, Nbre_enregist, Kf, Mu)
        self.close()


class NotesWindow(QDialog, Ui_notes):
    def __init__(self, *args, obj=None, **kwargs):
        super(NotesWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle("Notes")


class AcquisWindow(QDialog, Ui_Page_acquisition):
    def __init__(self, *args, obj=None, **kwargs):
        super(AcquisWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle("Paramètres d'acquisition")
        self.warning_edit.setVisible(False)


class ComparWindow(QDialog, Ui_curve_comparaison):
    def __init__(self, *args, obj=None, **kwargs):
        super(ComparWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle("Comparaison de courbes")
        self.import_button.clicked.connect(self.import_csv)
        self.clear_button.clicked.connect(self.clear_canva)
        self.colors_button.clicked.connect(self.change_color)
        self.remove_row_button.clicked.connect(self.delete_row)
        self.signals = []
        self.lines = []
        
    def delete_row(self):
        indices = self.tableWidget.selectionModel().selectedRows()
        for each_row in reversed(sorted(indices)):
            if self.is_row_empty(each_row.row())==False:
                line = self.lines[each_row.row()]
                line.remove()
                self.lines.pop(each_row.row())
                self.signals.pop(each_row.row())
                self.tableWidget.removeRow(each_row.row())
                self.tableWidget.insertRow(self.tableWidget.rowCount())
        self.widget_cpr.canvas.ax.legend(self.lines, self.signals)
        self.widget_cpr.canvas.draw()
    
    def change_color(self):
        signal_dialog = SignalSelectionDialog(self.signals, self)
        signal_dialog.signal_selected.connect(self.color_selection)
        signal_dialog.exec_()

    def color_selection(self, signal_idx):
        color = QColorDialog.getColor()
        if color.isValid():
            self.update_color(color.name(), signal_idx)

    def update_color(self, color, signal_idx):
        if signal_idx < len(self.lines):
            line = self.lines[signal_idx]
            for column in range(self.tableWidget.columnCount()):
                item = self.tableWidget.item(signal_idx, column)
                if item != None:
                    rgb_color = QColor(color)
                    item.setForeground(rgb_color)
            line.set_color(color)
            self.widget_cpr.canvas.ax.legend(self.lines, self.signals)
            self.widget_cpr.canvas.draw()

    def plot_data_compar(self, a, b, title):
        line, = self.widget_cpr.canvas.ax.plot(a, b, label=title)
        self.lines.append(line)
        self.signals.append(title)
        self.widget_cpr.canvas.ax.legend()
        self.widget_cpr.canvas.draw()

    def import_csv(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self, "Select CSV File", "", "CSV Files (*.csv)")
        if file_path:
            self.load_csv_data(file_path)

    def is_row_empty(self, row):
        for column in range(self.tableWidget.columnCount()):
            item = self.tableWidget.item(row, column)
            if item is not None and item.text():
                return False
            return True

    def load_csv_data(self, file_path):
        with open(file_path, newline='') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            data = list(reader)

        variables = {}
        arrays = {}

        variables_row = data[0]
        arrays_data = data[1:]

        for i, value in enumerate(variables_row):
            if i % 2 == 1:
                variable_name = variables_row[i - 1].strip()
                variable_value = value.strip()
                variables[variable_name] = variable_value

        num_rows = len(arrays_data)
        self.num_columns = len(arrays_data[0])

        for col in range(0, self.num_columns):
            array_name = arrays_data[0][col].strip()
            array_values = [arrays_data[row][col].strip()
                            for row in range(1, num_rows)]
            arrays[array_name] = array_values
            
        basic_colors = [
            "#FF0000",  # Red
            "#008000",  # Dark Green
            "#0000FF",  # Blue
            "#000000",  # Black
            "#FFA500",  # Orange
            "#FFFF00",  # Yellow
            "#800080",  # Purple
            "#00FFFF",  # Cyan
            "#FF00FF",  # Magenta
            "#00FF00",  # Green
            "#800000",  # Maroon
            "#808080",  # Gray
            "#FFFF99",  # Light Yellow
            "#CC99FF",  # Lavender
            "#00CCFF",  # Sky Blue
            "#99FF99",  # Light Green
            "#FF99CC"   # Light Pink
                        ]   
        file_name = os.path.basename(file_path)[:-4]
        bmax = variables.get("Bmax (T) =")
        freq = variables.get("Freq(Hz) =")
        hc = variables.get("Hc =")
        Mu = variables.get("µr =")
        hmax = variables.get("Hmax =")
        W = variables.get("W(J/m³) =")
        Pv = variables.get("P(W/m³) =")
        champ_h = arrays.get("ChampH")
        champ_b = arrays.get("ChampB")
        champ_h = [float(numeric_string) for numeric_string in champ_h]
        champ_b = [float(numeric_string) for numeric_string in champ_b]
        self.plot_data_compar(champ_h, champ_b, file_name)
        for i in range(self.tableWidget.rowCount()):
            if self.is_row_empty(i) == True:
                empty_row = i
                break
            else:
                empty_row=None
        if self.tableWidget.rowCount()==None:
            self.tableWidget.insertRow(self.tableWidget.rowCount())
            empty_row = self.tableWidget.rowCount()
        self.tableWidget.setItem(empty_row, 0, QTableWidgetItem(file_name))
        self.tableWidget.setItem(empty_row, 1, QTableWidgetItem(bmax))
        self.tableWidget.setItem(empty_row, 2, QTableWidgetItem(freq))
        self.tableWidget.setItem(empty_row, 3, QTableWidgetItem(hc))
        self.tableWidget.setItem(empty_row, 4, QTableWidgetItem(hmax))
        self.tableWidget.setItem(empty_row, 5, QTableWidgetItem(Mu))
        self.tableWidget.setItem(empty_row, 6, QTableWidgetItem(W))
        self.tableWidget.setItem(empty_row, 7, QTableWidgetItem(Pv))
        
        # color = "#"+"%06x" % random.randint(0, 0xFFFFFF)
        color = basic_colors[empty_row]
        self.update_color(color,empty_row)

    def clear_canva(self):
        self.widget_cpr.canvas.ax.clear()
        self.widget_cpr.canvas.draw()
        for row in reversed(range(self.tableWidget.rowCount())):
            if self.is_row_empty(row)==False:
                line = self.lines[row]
                line.remove()
                self.lines.pop(row)
                self.signals.pop(row)
            self.tableWidget.removeRow(row)
            self.tableWidget.insertRow(self.tableWidget.rowCount())


class SignalSelectionDialog(QDialog):
    signal_selected = pyqtSignal(int)

    def __init__(self, signals, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Signal")
        self.layout = QVBoxLayout(self)
        self.combo_box = QComboBox()
        self.combo_box.addItems(signals)
        self.layout.addWidget(self.combo_box)
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout.addWidget(button_box)

    def accept(self):
        signal_idx = self.combo_box.currentIndex()
        self.signal_selected.emit(signal_idx)
        super().accept()


class SupervisionWindow(QDialog, Ui_supervision):
    def __init__(self, *args, obj=None, **kwargs):
        super(SupervisionWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle("Supervision")
        self.plot_data()

    def plot_data(self):
        x = range(0, 10)
        y = range(0, 20, 2)
        self.widget_1.canvas.ax.plot(x, y)
        self.widget_1.canvas.draw()
        self.widget_2.canvas.ax.plot(x, y)
        self.widget_2.canvas.draw()
        self.widget_3.canvas.ax.plot(x, y)
        self.widget_3.canvas.draw()
        self.widget_4.canvas.ax.plot(x, y)
        self.widget_4.canvas.draw()


class MainWindow(QtWidgets.QMainWindow, Ui_JTcontrol):
    def __init__(self, *args, obj=None, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowIcon(QIcon('Logo2.png'))
        self.setWindowTitle("MagHyster")
        self.toolButton_Comparaison.setIcon(QIcon('music.png'))
        self.toolButton_Comparaison.setIconSize(QSize(24, 24))
        self.toolButton_Save.setIcon(QIcon('diskette.png'))
        self.toolButton_Save.setIconSize(QSize(24, 24))
        self.Button_start.clicked.connect(self.start)
        self.plot_data()
        self.thread = None
        self._connectActions()

    def plot_data(self):
        x = range(0, 10)
        y = range(0, 20, 2)
        self.widget.canvas.ax.plot(x, y)
        self.widget.canvas.draw()

    def _connectActions(self):
        # Connect File actions
        self.actionConfiguration.triggered.connect(self.set_config)
        self.actionOuvrir_une_configuration.triggered.connect(
            self.opens_config)
        self.actionEnregistrer_sous.triggered.connect(self.saves_config)
        self.actionEnregistrer.triggered.connect(self.saves_project)
        self.actionAcquisition.triggered.connect(self.acquisition)
        self.actionComparaison.triggered.connect(self.comparaison)
        self.actionNotes.triggered.connect(self.notes)

    def set_config(self):
        self.w = ConfigWindow(self)
        self.w.show()

    def update_data(self, Outils, Materiaux, Di, De, Hauteur, Section, lm, Kf):
        if (Outils == "Cadre Epstein personnalisé") or (Outils == "Cadre Epstein Standard"):
            self.Outils_value.setText("Cadre Epstein")
            self.Hauteur_label_main.setText("Epaisseur")
            self.Di_label_main.setText("Largeur")
            self.De_label_main.setText("Nbre de Bandes")
        else:
            self.Outils_value.setText(str(Outils))
            self.Hauteur_label_main.setText("Hauteur")
            self.Di_label_main.setText("Diamètre intérieur Di")
            self.De_label_main.setText("Diamètre extérieur De")
        self.Materiaux_value.setText(str(Materiaux))
        self.Di_value.setText(str(Di) + " mm")
        self.De_value.setText(str(De)+" mm")
        self.Hauteur_value.setText(str(Hauteur)+" mm")
        self.Section_value.setText(str(Section)+" mm²")
        self.lm_value.setText(str(lm)+" mm")
        self.Kf_value.setText(str(Kf))

    def acquisition(self):
        self.w = AcquisWindow()
        self.w.show()

    def comparaison(self):
        self.w = ComparWindow()
        self.w.show()

    def notes(self):
        self.win = NotesWindow()
        self.win.show()

    def opens_config(self):
        global Materiaux, Hauteur, Di, De, Section, Outils, Ns1, Ns2, Rs, Rh, Type, Forme, Freq, Ampli, Gain, Nbre_periode, Nbre_enregist, Nm_ref, Mu, Kf
        config_path, _ = QFileDialog.getOpenFileName(
            self, 'Load Configuration', '', 'Config Files (*.cfg)')
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
        config_path, _ = QFileDialog.getSaveFileName(
            self, 'Save Configuration', f"configuration_{date_time}.cfg", 'Config Files (*.cfg)')
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
        selected_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Select a directory')
        if selected_dir:
            config_dir = os.path.join(selected_dir, Nm_ref)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
            now = datetime.datetime.now()
            date_time = now.strftime("%Y-%m-%d_%H-%M-%S")
            settings = QSettings(os.path.join(
                config_dir, f"configuration_{date_time}.cfg"), QSettings.IniFormat)
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
        self.w = SupervisionWindow()
        self.w.show()
        if self.thread is None or not self.thread.isRunning():
            self.Button_start.setEnabled(False)
            self.thread = Worker()
            self.thread.finished.connect(self.on_long_task_finished)
            self.thread.start()

    def on_long_task_finished(self):
        self.Button_start.setEnabled(True)
        print("Done.")
        self.thread = None

    def closeEvent(self, event):
        for window in QtWidgets.QApplication.topLevelWidgets():
            window.close()
        QtWidgets.QApplication.quit()


app = QtWidgets.QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec()
