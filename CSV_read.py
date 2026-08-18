import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QPushButton, QVBoxLayout, QWidget, QFileDialog
import csv
import matplotlib.pyplot as plt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CSV Table")
        self.table = QTableWidget()
        self.load_button = QPushButton("Load CSV")
        self.load_button.clicked.connect(self.load_csv_dialog)

        layout = QVBoxLayout()
        layout.addWidget(self.table)
        layout.addWidget(self.load_button)

        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

    def load_csv_dialog(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Select CSV File", "", "CSV Files (*.csv)")

        if file_path:
            self.load_csv_data(file_path)

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
        num_columns = len(arrays_data[0])

        for col in range(0, num_columns):
            array_name = arrays_data[0][col].strip()
            array_values = [arrays_data[row][col].strip() for row in range(1, num_rows)]
            arrays[array_name] = array_values

        bmax = variables.get("Bmax (T) =")
        freq = variables.get("Freq(Hz) =")
        hc = variables.get("Hc =")
        Mu = variables.get("µr =")
        w = variables.get("W(J/m³) =")
        p = variables.get("P(W/m³) =")

        champ_h = arrays.get("ChampH")
        champ_b = arrays.get("ChampB")
        champ_h = [float(numeric_string) for numeric_string in champ_h]
        champ_b = [float(numeric_string) for numeric_string in champ_b]
        # Print the extracted variables and arrays
        print(f"Bmax: {bmax}")
        print(f"Freq: {freq}")
        print(f"Hc: {hc}")
        print(f"µr: {Mu}")
        print(f"W: {w}")
        print(f"P: {p}")
        print(f"ChampH: {champ_h}")
        print(f"ChampB: {champ_b}")
        fig,ax = plt.subplots()
        ax.plot(champ_h,champ_b)
        plt.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
