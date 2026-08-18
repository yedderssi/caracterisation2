# Imports
from PyQt5 import QtWidgets
from matplotlib.figure import Figure
import matplotlib.pyplot
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as Canvas, NavigationToolbar2QT as NavigationToolbar
import matplotlib

# Ensure using PyQt5 backend
matplotlib.use('QT5Agg')
matplotlib.pyplot.ion()
# Matplotlib canvas class to create figure
class MplCanvas(Canvas):
    def __init__(self):
        self.fig = Figure()
        self.ax = self.fig.add_subplot(111)
        Canvas.__init__(self, self.fig)
        Canvas.setSizePolicy(self, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        Canvas.updateGeometry(self)

# Matplotlib widget
class MplWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)   # Inherit from QWidget
        self.canvas = MplCanvas()                  # Create canvas object
        self.vbl = QtWidgets.QVBoxLayout()         # Set box for plotting
        toolbar1 = NavigationToolbar(self.canvas, self)   
        self.vbl.addWidget(toolbar1)
        self.vbl.addWidget(self.canvas)
        self.setLayout(self.vbl)
