from PyQt5.QtWidgets import*
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvas,FigureCanvasQTAgg,NavigationToolbar2QT
from matplotlib.figure import Figure
class MplCanvas(FigureCanvasQTAgg):

    #Configuration de l'intialisation du canva pour le trace
    
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)
        
class Matplot(QWidget):
   def __init__(self, parent=None):
        super().__init__(parent)
 
        self.sc = MplCanvas(self, width=5, height=4, dpi=100)
        # sc.axes.plot([0,1,2,3,4], [10,1,20,3,40])
    
        
        layout2 = QVBoxLayout()
        layout2.addWidget(self.sc)
        