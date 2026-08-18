# pyuic5 mainwindow.ui -o MainWindow.py
import sys
import datetime
import os,random,math
from PyQt5 import QtWidgets, uic
from MainWindow import Ui_JTcontrol
from Supervision import Ui_supervision
from page_acquisition import Ui_Page_acquisition
from configuration import Ui_Dialog
from Notes import Ui_notes
from curve_comparaison import Ui_curve_comparaison
from PyQt5.QtGui import QIcon,QColor
from PyQt5.QtWidgets import QColorDialog, QTableWidgetItem, QDialogButtonBox, QComboBox, QDialog, QGridLayout, QPushButton, QFileDialog, QVBoxLayout
from PyQt5.QtCore import QThread, pyqtSignal, QSettings, QSize
import csv
Hauteur = Di = De = Section = Ns1 = Ns2 = Rs = Rh = Freq = Ampli = Gain = Nbre_enregist = Kf = Mu = lm = Epaisseur = Nbre_Bandes = Largeur = 0
Nbre_periode = 2
iteration_max = 10
num_samples = 5000
Resolution=14
Nbre_enregist = 10 
Materiaux = "Fer pur"
Outils = "Tore enroulé"
Type = "Cycle d'hystérèsis"
Forme = "Sinusoïdale"
Nm_ref = "Nom_Ref"


class Worker(QThread):
    finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.parent = parent
    def run(self):
        import ctypes
        import pyvisa as visa
        import sys
        import numpy as np
        import time as tm
        from scipy import integrate
        from scipy.signal import detrend, correlate, correlation_lags,blackmanharris,hilbert,savgol_filter
        from scipy.interpolate import interp1d
        from scipy.fft import fft,rfft, irfft
        from picosdk.ps5000a import ps5000a as ps
        import matplotlib.pyplot as plt
        from matplotlib.animation import FuncAnimation
        from picosdk.functions import adc2mV, assert_pico_ok
        plt.close('all')

        # Adresse VISA du GBF
        # VISA_ADDRESS = "USB0::2391::1031::MY44061101::0::INSTR"
        VISA_ADDRESS = 'USB0::1689::851::1714305::0::INSTR'
        def find_range(f, x):
            uppermin2 = lowermin2 =0
            for i in np.arange(x+1, len(f)):
                if f[i+1] >= f[i]:
                    uppermin2 = i
                    break
            for i in np.arange(x-1, 0, -1):
                if f[i] <= f[i-1]:
                    lowermin2 = i + 1
                    break
            return (lowermin2, uppermin2)

        def symetrie(an,bn):
            for i in range(len(an)):
                if i%2==0:
                    an[i]=0
                    bn[i]=0
            return np.concatenate((an,bn))

        def compute_fft_signals(B_ref_sim,B_sim,V1_sim,dB_dt_ref_sim,dB_dt_sim):
            #Calcul des coefficients de Fourier de la référence de B
            an_B_ref=2*np.real(np.fft.rfft(B_ref_sim))/len(B_ref_sim)
            bn_B_ref=-2*np.imag(np.fft.rfft(B_ref_sim))/len(B_ref_sim)
            Fourier_B_ref=symetrie(an_B_ref,bn_B_ref)
            #Calcul des coefficients de Fourier de B obtenu
            an_B_sim=2*np.real(np.fft.rfft(B_sim))/len(B_sim)
            bn_B_sim=-2*np.imag(np.fft.rfft(B_sim))/len(B_sim)
            Fourier_B_sim=symetrie(an_B_sim,bn_B_sim)
            #Calcul des coefficients de la tension V
            an_V_sim=2*np.real(np.fft.rfft(V1_sim))/len(V1_sim)
            bn_V_sim=-2*np.imag(np.fft.rfft(V1_sim))/len(V1_sim)
            Fourier_V_sim=symetrie(an_V_sim,bn_V_sim)
            #Calcul des coefficients de la tension dB/dt de référence
            an_dB_ref=2*np.real(np.fft.rfft(dB_dt_ref_sim))/len(dB_dt_ref_sim)
            bn_dB_ref=-2*np.imag(np.fft.rfft(dB_dt_ref_sim))/len(dB_dt_ref_sim)
            Fourier_dB_ref=symetrie(an_dB_ref,bn_dB_ref)
            #Calcul des coefficients de la tension dB/dt obtenu
            an_dB_sim=2*np.real(np.fft.rfft(dB_dt_sim))/len(dB_dt_sim)
            bn_dB_sim=-2*np.imag(np.fft.rfft(dB_dt_sim))/len(dB_dt_sim)
            Fourier_dB_sim=symetrie(an_dB_sim,bn_dB_sim)
            return Fourier_dB_ref, Fourier_dB_sim,Fourier_B_ref, Fourier_B_sim, Fourier_V_sim

        def THDN(signal, sample_rate):
            signal -= np.mean(signal)
            windowed = signal * blackmanharris(len(signal))
            total_rms = np.sqrt(np.mean(np.absolute(windowed)**2))
            f = rfft(windowed)
            i = np.argmax(abs(f))
            lowermin, uppermin = find_range(abs(f), i)
            f[lowermin: uppermin] = 0
            noise = irfft(f)
            THDN = np.sqrt(np.mean(np.absolute(noise)**2)) / total_rms
            return THDN*100

        def FF(x, T):
            N = len(x)
            x = np.abs(x)
            x_rms = np.sqrt(np.mean(x**2))
            x_int = (T/N) * np.sum((x[:-1] + x[1:]) / 2)
            ff = x_rms / (x_int / T)
            return ff

        def closest(lst, K):
             
             lst = np.asarray(lst)
             idx = (np.abs(lst - K)).argmin()
             return lst[idx]
        

        # Channel range codes
        Channel_ranges = ["PS5000A_20MV",  # 20 mV
                          "PS5000A_50MV",  # 50 mV
                          "PS5000A_100MV",  # 100 mV
                          "PS5000A_200MV",  # 200 mV
                          "PS5000A_500MV",  # 500 mV
                          "PS5000A_1V",  # 1 V
                          "PS5000A_2V",  # 2 V
                          "PS5000A_5V",  # 5 V
                          "PS5000A_10V",  # 10 V
                          "PS5000A_20V",  # 20 V
                          ]
        iteration = 0
        Nbre_enregistrement = 10
        current_range = -1
        Nbre_periode = 2
        Num_resolution = 14
        Frequence = 1e3
        Amplitude = 0.2
        num_samples = 5000
        Rsh = 1
        N1 = 32
        N2 = 11
        Section = 195.7e-6
        De = 50e-3
        Di = 30e-3
        Mu_air = 1.2566e-6
        Mu = 4300
        Rs = 4.43
        Rtot = Rsh+Rs
        w = Frequence*2*np.pi
        t = np.linspace(0, 1/Frequence, num_samples)
        ChampBdes = Amplitude*np.sin(w*t)
        derivChampBdes = w*Amplitude*np.cos(w*t)
        f2 = interp1d(t, derivChampBdes)
        f3 = interp1d(t, ChampBdes)
        if De > 1.1*Di:
            lm = np.pi*(De-Di)/np.log(De/Di)
        else:
            lm = np.pi*(De+Di)/2

        alpha = (-Rtot*lm/(Mu*Mu_air*N1)/10)
        print(alpha)
        print(N1)
        beta = (-N1*Section/10)
        print(beta)
        entree = alpha*ChampBdes+beta*derivChampBdes
        f1 = interp1d(t, entree)
        while True:
            for i in range(2):
                try:
                    # Create a connection (session) to the instrument
                    resourceManager = visa.ResourceManager()
                    session = resourceManager.open_resource(VISA_ADDRESS)
                except visa.Error:
                    session.close()
                    resourceManager.close()
                    print('Couldn\'t connect to \'%s\', exiting now...' % VISA_ADDRESS)
                    sys.exit()
                
                if session.resource_name.startswith('ASRL') or session.resource_name.endswith('SOCKET'):
                    session.read_termination = '\n'
                    
                if i==0:
                    if np.max(entree) > np.abs(np.min(entree)):
                        pk = np.max(entree)
                    else:
                        pk = np.abs(np.min(entree))
                    e_min, e_max = entree.min(), entree.max()
                    entree_alt = 2*(entree - e_min)/(e_max - e_min) - 1

                    #Create an array with all values set to 0 in the above convention
                    to_transfer = np.ones(len(entree_alt), dtype=np.uint16)*(2**13)
                    
                    # Convert your data to fit within the format
                    to_transfer += np.require(np.rint(8191*entree_alt), np.uint16)
                    #Check for errors
                    if to_transfer.max() > 16383 or to_transfer.min() < 0:
                        raise ValueError('Analogical values out of range.')
                
                session.write('source1:function ememory')
                session.write('output1 on')
                session.write(f'SOUR1:VOLT:LEV:IMM:AMPL {pk}Vpp')
                session.write(f'SOUR1:FREQ {Frequence}')
                session.write(f'SOURce1:VOLTage:LEVel:IMMediate:OFFSet {0}Vpp')
                session.write_binary_values("DATA EMEMory,", to_transfer, datatype='h', is_big_endian = True)
                session.write('DATA:COPY USER1, EMEM')
                session.write('source1:function USER1') 
                
                session.close()
                resourceManager.close()
                
                tm.sleep(1)
            chandle = ctypes.c_int16()
            status = {}
            resolution = ps.PS5000A_DEVICE_RESOLUTION["PS5000A_DR_" +
                                                      str(Num_resolution)+"BIT"]

            status["openunit"] = ps.ps5000aOpenUnit(
                ctypes.byref(chandle), None, resolution)
            # print(ctypes.byref(chandle))
            try:
                assert_pico_ok(status["openunit"])
            except:  # PicoNotOkError:
                powerStatus = status["openunit"]
                if powerStatus == 286:
                    status["changePowerSource"] = ps.ps5000aChangePowerSource(
                        chandle, powerStatus)
                elif powerStatus == 282:
                    status["changePowerSource"] = ps.ps5000aChangePowerSource(
                        chandle, powerStatus)
                else:
                    raise
                assert_pico_ok(status["changePowerSource"])
            current_range = -1
            while True:
                current_range = current_range+1
                maxADC = ctypes.c_int16()
                channel = ps.PS5000A_CHANNEL["PS5000A_CHANNEL_A"]
                # enabled = 1
                coupling_type = ps.PS5000A_COUPLING["PS5000A_DC"]
                chARange = ps.PS5000A_RANGE[Channel_ranges[current_range]]
                # analogue offset = 0 V
                status["setChA"] = ps.ps5000aSetChannel(
                    chandle, channel, 1, coupling_type, chARange, 0)
                assert_pico_ok(status["setChA"])
                status["maximumValue"] = ps.ps5000aMaximumValue(
                    chandle, ctypes.byref(maxADC))
                assert_pico_ok(status["maximumValue"])
                # enabled = 1
                source = ps.PS5000A_CHANNEL["PS5000A_CHANNEL_A"]

                maxADC = ctypes.c_int16()
                status["maximumValue"] = ps.ps5000aMaximumValue(
                    chandle, ctypes.byref(maxADC))
                assert_pico_ok(status["maximumValue"])

                threshold = int(maxADC.value/4)
                # direction = PS5000A_RISING = 2
                # delay = 0 s
                # auto Trigger = 1000 ms
                status["trigger"] = ps.ps5000aSetSimpleTrigger(
                    chandle, 1, source, threshold, 2, 0, 1000)
                assert_pico_ok(status["trigger"])

                preTriggerSamples = num_samples//2
                postTriggerSamples = num_samples//2
                maxSamples = preTriggerSamples + postTriggerSamples
                BuffersMaxA = np.ones((Nbre_enregistrement, maxSamples))
                BuffersMinA = np.ones((Nbre_enregistrement, maxSamples))

                duration = Nbre_periode / (Frequence)
                if Num_resolution == 12 or Num_resolution == 16:
                    if (duration/num_samples)<=8e-9:
                        timebase = round(np.log(duration*500000000/num_samples)/np.log(2)+1)
                    else:
                        timebase = round((duration*62500000/maxSamples)+3)
                else:
                    timebase = round((duration*125000000/maxSamples)+2)

                timeIntervalns = ctypes.c_float()
                returnedMaxSamples = ctypes.c_int32()
                
                status["getTimebase2"] = ps.ps5000aGetTimebase2(chandle, timebase, maxSamples, ctypes.byref(
                    timeIntervalns), ctypes.byref(returnedMaxSamples), 0)
                assert_pico_ok(status["getTimebase2"])

                status["runBlock"] = ps.ps5000aRunBlock(
                    chandle, preTriggerSamples, postTriggerSamples, timebase, None, 0, None, None)
                assert_pico_ok(status["runBlock"])

                ready = ctypes.c_int16(0)
                check = ctypes.c_int16(0)
                while ready.value == check.value:
                    status["isReady"] = ps.ps5000aIsReady(chandle, ctypes.byref(ready))

                bufferAMax = (ctypes.c_int16 * maxSamples)()
                bufferAMin = (ctypes.c_int16 * maxSamples)()

                # ratio mode = PS5000A_RATIO_MODE_NONE = 0
                status["setdataABuffers"] = ps.ps5000aSetDataBuffers(chandle, source, ctypes.byref(
                    bufferAMax), ctypes.byref(bufferAMin), maxSamples, 0, 0)
                assert_pico_ok(status["setdataABuffers"])

                overflow = ctypes.c_int16()
                cmaxSamples = ctypes.c_int32(maxSamples)  # Nbre d'echantillons

                # downsample ratio = 0
                # downsample ratio mode = PS5000A_RATIO_MODE_NONE
                status["getValues"] = ps.ps5000aGetValues(
                    chandle, 0, ctypes.byref(cmaxSamples), 0, 0, 0, ctypes.byref(overflow))
                assert_pico_ok(status["getValues"])
                if overflow.value == 0:
                    break
            BuffersMaxA[0] = adc2mV(bufferAMax, chARange, maxADC)
            BuffersMinA[0] = adc2mV(bufferAMax, chARange, maxADC)
            for i in range(1, Nbre_enregistrement):
                status["runBlock"] = ps.ps5000aRunBlock(
                    chandle, preTriggerSamples, postTriggerSamples, timebase, None, 0, None, None)
                assert_pico_ok(status["runBlock"])

                ready2 = ctypes.c_int16(0)
                check2 = ctypes.c_int16(0)
                while ready2.value == check2.value:
                    status["isReady"] = ps.ps5000aIsReady(
                        chandle, ctypes.byref(ready2))

                bufferAMax = (ctypes.c_int16 * maxSamples)()
                bufferAMin = (ctypes.c_int16 * maxSamples)()
                # handle = chandle
                # ratio mode = PS5000A_RATIO_MODE_NONE = 0
                status["setdataABuffers"] = ps.ps5000aSetDataBuffers(chandle, source, ctypes.byref(
                    bufferAMax), ctypes.byref(bufferAMin), maxSamples, 0, 0)
                assert_pico_ok(status["setdataABuffers"])
                overflow = ctypes.c_int16()
                cmaxSamples = ctypes.c_int32(maxSamples)  # Nbre d'echantillons

                # downsample ratio = 0
                # downsample ratio mode = PS5000A_RATIO_MODE_NONE
                status["getValues"] = ps.ps5000aGetValues(
                    chandle, 0, ctypes.byref(cmaxSamples), 0, 0, 0, ctypes.byref(overflow))
                assert_pico_ok(status["getValues"])
                BuffersMaxA[i] = adc2mV(bufferAMax, chARange, maxADC)
                BuffersMinA[i] = adc2mV(bufferAMin, chARange, maxADC)

            current_range = -1
            while True:
                current_range = current_range+1
                maxADC = ctypes.c_int16()
                channel = ps.PS5000A_CHANNEL["PS5000A_CHANNEL_B"]
                # enabled = 1
                coupling_type = ps.PS5000A_COUPLING["PS5000A_DC"]
                chBRange = ps.PS5000A_RANGE[Channel_ranges[current_range]]
                # analogue offset = 0 V
                status["setChB"] = ps.ps5000aSetChannel(
                    chandle, channel, 1, coupling_type, chBRange, 0)
                assert_pico_ok(status["setChB"])
                status["maximumValue"] = ps.ps5000aMaximumValue(
                    chandle, ctypes.byref(maxADC))
                assert_pico_ok(status["maximumValue"])

                preTriggerSamples = num_samples//2
                postTriggerSamples = num_samples//2
                maxSamples = preTriggerSamples + postTriggerSamples
                BuffersMaxB = np.ones((Nbre_enregistrement, maxSamples))
                BuffersMinB = np.ones((Nbre_enregistrement, maxSamples))

                duration = Nbre_periode / Frequence
                if Num_resolution == 12 or Num_resolution == 16:
                    if (duration/num_samples)<=8e-9:
                        timebase = round(np.log(duration*500000000/num_samples)/np.log(2)+1)
                    else:
                        timebase = round((duration*62500000/maxSamples)+3)
                else:
                    timebase = round((duration*125000000/maxSamples)+2)
                # segment index = 0

                timeIntervalns = ctypes.c_float()
                returnedMaxSamples = ctypes.c_int32()
                # timebasev=timebase.value
                status["getTimebase2"] = ps.ps5000aGetTimebase2(chandle, timebase, maxSamples, ctypes.byref(
                    timeIntervalns), ctypes.byref(returnedMaxSamples), 0)
                assert_pico_ok(status["getTimebase2"])

                # segment index = 0
                # lpReady = None (using ps5000aIsReady rather than ps5000aBlockReady)
                # pParameter = None
                status["runBlock"] = ps.ps5000aRunBlock(
                    chandle, preTriggerSamples, postTriggerSamples, timebase, None, 0, None, None)
                assert_pico_ok(status["runBlock"])

                ready = ctypes.c_int16(0)
                check = ctypes.c_int16(0)
                while ready.value == check.value:
                    status["isReady"] = ps.ps5000aIsReady(chandle, ctypes.byref(ready))

                bufferBMax = (ctypes.c_int16 * maxSamples)()
                bufferBMin = (ctypes.c_int16 * maxSamples)()
                # ratio mode = PS5000A_RATIO_MODE_NONE = 0
                status["setdataABuffersB"] = ps.ps5000aSetDataBuffers(
                    chandle, ps.PS5000A_CHANNEL["PS5000A_CHANNEL_B"], ctypes.byref(bufferBMax), ctypes.byref(bufferBMin), maxSamples, 0, 0)
                assert_pico_ok(status["setdataABuffersB"])

                overflow = ctypes.c_int16()
                cmaxSamples = ctypes.c_int32(maxSamples)  # Nbre d'echantillons

                # downsample ratio = 0
                # downsample ratio mode = PS5000A_RATIO_MODE_NONE
                status["getValues"] = ps.ps5000aGetValues(
                    chandle, 0, ctypes.byref(cmaxSamples), 0, 0, 0, ctypes.byref(overflow))
                assert_pico_ok(status["getValues"])
                if overflow.value == 0:
                    break
            BuffersMaxB[0] = adc2mV(bufferBMax, chBRange, maxADC)
            BuffersMinB[0] = adc2mV(bufferBMax, chBRange, maxADC)
            for i in range(1, Nbre_enregistrement):
                status["runBlock"] = ps.ps5000aRunBlock(
                    chandle, preTriggerSamples, postTriggerSamples, timebase, None, 0, None, None)
                assert_pico_ok(status["runBlock"])

                ready2 = ctypes.c_int16(0)
                check2 = ctypes.c_int16(0)
                while ready2.value == check2.value:
                    status["isReady"] = ps.ps5000aIsReady(
                        chandle, ctypes.byref(ready2))

                bufferBMax = (ctypes.c_int16 * maxSamples)()
                bufferBMin = (ctypes.c_int16 * maxSamples)()
                # handle = chandle
                # ratio mode = PS5000A_RATIO_MODE_NONE = 0
                status["setdataABuffersB"] = ps.ps5000aSetDataBuffers(
                    chandle, ps.PS5000A_CHANNEL["PS5000A_CHANNEL_B"], ctypes.byref(bufferBMax), ctypes.byref(bufferBMin), maxSamples, 0, 0)
                assert_pico_ok(status["setdataABuffersB"])
                overflow = ctypes.c_int16()
                cmaxSamples = ctypes.c_int32(maxSamples)  # Nbre d'echantillons

                # downsample ratio = 0
                # downsample ratio mode = PS5000A_RATIO_MODE_NONE
                status["getValues"] = ps.ps5000aGetValues(
                    chandle, 0, ctypes.byref(cmaxSamples), 0, 0, 0, ctypes.byref(overflow))
                assert_pico_ok(status["getValues"])
                BuffersMaxB[i] = adc2mV(bufferBMax, chBRange, maxADC)
                BuffersMinB[i] = adc2mV(bufferBMin, chBRange, maxADC)

            current_range = -1

            while True:
                current_range = current_range+1
                maxADC = ctypes.c_int16()
                channel = ps.PS5000A_CHANNEL["PS5000A_CHANNEL_C"]
                # enabled = 1
                coupling_type = ps.PS5000A_COUPLING["PS5000A_DC"]
                chCRange = ps.PS5000A_RANGE[Channel_ranges[current_range]]
                # analogue offset = 0 V
                status["setChA"] = ps.ps5000aSetChannel(
                    chandle, channel, 1, coupling_type, chCRange, 0)
                assert_pico_ok(status["setChA"])
                status["maximumValue"] = ps.ps5000aMaximumValue(
                    chandle, ctypes.byref(maxADC))
                assert_pico_ok(status["maximumValue"])

                preTriggerSamples = num_samples//2
                postTriggerSamples = num_samples//2
                maxSamples = preTriggerSamples + postTriggerSamples
                BuffersMaxC = np.ones((Nbre_enregistrement, maxSamples))
                BuffersMinC = np.ones((Nbre_enregistrement, maxSamples))

                duration = Nbre_periode/(Frequence)
                if Num_resolution == 12 or Num_resolution == 16:
                    if (duration/num_samples)<=8e-9:
                        timebase = round(np.log(duration*500000000/num_samples)/np.log(2)+1)
                    else:
                        timebase = round((duration*62500000/maxSamples)+3)
                else:
                    timebase = round((duration*125000000/maxSamples)+2)

                timeIntervalns = ctypes.c_float()
                returnedMaxSamples = ctypes.c_int32()
                # timebasev=timebase.value
                status["getTimebase2"] = ps.ps5000aGetTimebase2(chandle, timebase, maxSamples, ctypes.byref(
                    timeIntervalns), ctypes.byref(returnedMaxSamples), 0)
                assert_pico_ok(status["getTimebase2"])

                # segment index = 0
                # lpReady = None (using ps5000aIsReady rather than ps5000aBlockReady)
                # pParameter = None
                status["runBlock"] = ps.ps5000aRunBlock(
                    chandle, preTriggerSamples, postTriggerSamples, timebase, None, 0, None, None)
                assert_pico_ok(status["runBlock"])

                ready = ctypes.c_int16(0)
                check = ctypes.c_int16(0)
                while ready.value == check.value:
                    status["isReady"] = ps.ps5000aIsReady(chandle, ctypes.byref(ready))

                bufferCMax = (ctypes.c_int16 * maxSamples)()
                bufferCMin = (ctypes.c_int16 * maxSamples)()

                # ratio mode = PS5000A_RATIO_MODE_NONE = 0
                status["setDataBuffersA"] = ps.ps5000aSetDataBuffers(chandle, ps.PS5000A_CHANNEL["PS5000A_CHANNEL_C"], ctypes.byref(
                    bufferCMax), ctypes.byref(bufferCMin), maxSamples, 0, 0)
                assert_pico_ok(status["setDataBuffersA"])

                overflow = ctypes.c_int16()
                cmaxSamples = ctypes.c_int32(maxSamples)  # Nbre d'echantillons

                # downsample ratio = 0
                # downsample ratio mode = PS5000A_RATIO_MODE_NONE
                status["getValues"] = ps.ps5000aGetValues(
                    chandle, 0, ctypes.byref(cmaxSamples), 0, 0, 0, ctypes.byref(overflow))
                assert_pico_ok(status["getValues"])
                BuffersMaxC[0] = adc2mV(bufferCMax, chCRange, maxADC)
                BuffersMinC[0] = adc2mV(bufferCMin, chCRange, maxADC)
                BufferTest = [32000, 32000]
                if np.max(BuffersMaxC[0]) < np.max(adc2mV(BufferTest, chCRange, maxADC)):
                    break

            for i in range(1, Nbre_enregistrement):
                status["runBlock"] = ps.ps5000aRunBlock(
                    chandle, preTriggerSamples, postTriggerSamples, timebase, None, 0, None, None)
                assert_pico_ok(status["runBlock"])

                ready2 = ctypes.c_int16(0)
                check2 = ctypes.c_int16(0)
                while ready2.value == check2.value:
                    status["isReady"] = ps.ps5000aIsReady(
                        chandle, ctypes.byref(ready2))

                bufferCMax = (ctypes.c_int16 * maxSamples)()
                bufferCMin = (ctypes.c_int16 * maxSamples)()

                status["setdataABuffersC"] = ps.ps5000aSetDataBuffers(
                    chandle, ps.PS5000A_CHANNEL["PS5000A_CHANNEL_C"], ctypes.byref(bufferCMax), ctypes.byref(bufferCMin), maxSamples, 0, 0)
                assert_pico_ok(status["setdataABuffersC"])
                overflow = ctypes.c_int16()
                cmaxSamples = ctypes.c_int32(maxSamples)


                status["getValues"] = ps.ps5000aGetValues(
                    chandle, 0, ctypes.byref(cmaxSamples), 0, 0, 0, ctypes.byref(overflow))
                assert_pico_ok(status["getValues"])
                BuffersMaxC[i] = adc2mV(bufferCMax, chCRange, maxADC)
                BuffersMinC[i] = adc2mV(bufferCMin, chCRange, maxADC)

            status["stop"] = ps.ps5000aStop(chandle)
            assert_pico_ok(status["stop"])
            status["close"] = ps.ps5000aCloseUnit(chandle)
            assert_pico_ok(status["close"])
            # print(status)

            BufferMaxAf = np.mean(BuffersMaxA, axis=0)
            BufferMinAf = np.mean(BuffersMinA, axis=0)

            BufferMaxBf = np.mean(BuffersMaxB, axis=0)
            BufferMinBf = np.mean(BuffersMinB, axis=0)

            BufferMaxCf = np.mean(BuffersMaxC, axis=0)
            BufferMinCf = np.mean(BuffersMinC, axis=0)

            adc2mVChAMax = BufferMaxAf
            adc2mVChBMax = BufferMaxBf
            adc2mVChCMax = BufferMaxCf

            MoyenneA = (np.max(adc2mVChAMax)+np.min(adc2mVChAMax))/2
            MoyenneB = (np.max(adc2mVChBMax)+np.min(adc2mVChBMax))/2
            MoyenneC = (np.max(adc2mVChCMax)+np.min(adc2mVChCMax))/2

            num_samples = cmaxSamples.value

            timeI = np.linspace(0, (cmaxSamples.value - 1) *
                                timeIntervalns.value, cmaxSamples.value)
            dataA = np.zeros(num_samples)
            dataA = adc2mVChAMax - MoyenneA
            crossingsA = np.where(np.diff(np.sign(dataA)))[0]

            samples_per_period = np.where(timeI > (1/(Frequence)*1e9))[0][0]-1
            num_periods_in_capture = num_samples // samples_per_period
            samples_to_plotA = dataA[:Nbre_periode*samples_per_period]+MoyenneA
            timeA = np.arange(
                np.array(samples_to_plotA).shape[0]) *timeIntervalns.value/1e9


            dataB = np.zeros(num_samples)
            dataB = adc2mVChBMax - MoyenneB

            samples_to_plotB = dataB[:Nbre_periode*samples_per_period]+MoyenneB
            timeB = np.arange(
                np.array(samples_to_plotB).shape[0]) *timeIntervalns.value/1e9

            dataC = np.zeros(num_samples)
            dataC = adc2mVChCMax - MoyenneC
            crossingsC = np.where(np.diff(np.sign(dataC)))[0]
            samples_per_period2 = int(np.mean(np.diff(crossingsC)))
            samples_to_plotC = dataC[:Nbre_periode*samples_per_period]+MoyenneC
            timeC = np.arange(
                np.array(samples_to_plotC).shape[0]) *timeIntervalns.value/1e9
            Signal_sans_moyenne = detrend(samples_to_plotC, type='constant')
            integral = integrate.cumulative_trapezoid(
                (Signal_sans_moyenne)/1000, timeC, initial=0)
            derivChampBdes = f2(timeC[:samples_per_period])
            ChampBdes = f3(timeC[:samples_per_period])
            integral_corrige = integral
            Maxi = np.max(integral_corrige)
            Mini = np.min(integral_corrige)
            integral_corrige = integral_corrige-((Mini+Maxi)/2)
            ChampB = integral_corrige/(-N2*Section)
            
            derivChampB = samples_to_plotC/(-N2*Section*1000)
            signal_correle = np.correlate(
                ChampBdes, ChampB[:samples_per_period], "same")
            lags = correlation_lags(
                ChampBdes.size, ChampB[:samples_per_period].size, mode="same")
            lag = lags[np.argmax(signal_correle)]
            cross = np.where(np.diff(np.sign(ChampB[:samples_per_period])))[0]
            if len(cross)==2:
                # lag = -cross[0]
                # if ChampB[lag+20]<ChampB[lag-20]:
                #     lag = -cross[1]
                lag = np.where(derivChampB==np.max(derivChampB[:samples_per_period]))[0][0]
                lag = -closest(cross, lag)

            # delay=np.where(np.correlate(V_L_sim_int,tension,"same")==max(np.correlate(V_L_sim_int,tension,"same"))) #delay est l'indice qui donne le max de la corrélation croisée entre les deux vecteurs
            # delay est un tuple, on lit la valeur du tuple[0] pour pouvoir l'utiliser dans np.roll. Synchronisation par rapport à la référence
            ChampB = np.roll(ChampB, lag)
            # delay=np.where(np.correlate(ChampB,ChampBdes,"same")==max(np.correlate(ChampB,ChampBdes,"same")))
            # ChampB=np.roll(ChampB,delay[0])
            ih = samples_to_plotB/(Rsh*1000)

            ChampH1 = ChampB/(Mu*Mu_air)
            ChampH2 = N1*ih/lm
            ChampH2 = np.roll(ChampH2, lag)
            derivChampB = np.roll(derivChampB, lag)            
            if iteration==0:
                entree = f1(timeC[:samples_per_period])
            signalA = np.roll(samples_to_plotA[:samples_per_period]/50,lag)
            
            signalA_analytic = hilbert(signalA)
            entree_analytic = hilbert(entree)
            phase_diff = np.angle(signalA_analytic) - np.angle(entree_analytic) 

            entree_aligne = np.abs(entree_analytic) * np.exp(1j * (np.angle(entree_analytic) + phase_diff))
            entree = np.real(entree_aligne)
            self.parent.main_window.timeC = timeC[:samples_per_period]
            unite_T = "s"
            if timeC[samples_per_period]<1e-6:
                unite_T = "ns"
                timeC = timeC*1e9
            elif timeC[samples_per_period]<1e-3:
                unite_T = "µs"
                timeC = timeC*1e6
            elif timeC[samples_per_period]<1:
                unite_T = "ms"
                timeC = timeC*1e3
                
            self.parent.widget_1.canvas.ax.cla()
            self.parent.widget_2.canvas.ax.cla()
            self.parent.widget_3.canvas.ax.cla()
            self.parent.widget_4.canvas.ax.cla()
            self.parent.widget_2.canvas.ax.plot(timeC[:samples_per_period],ChampBdes,label="B desiré",color='r',linestyle='--')
            self.parent.widget_3.canvas.ax.plot(timeC[:samples_per_period],derivChampBdes*(-N2*Section),label="V2 desiré",color='r',linestyle='--')
            line1, = self.parent.widget_1.canvas.ax.plot(timeC[:samples_per_period],entree,label="eₖ")
            line2, = self.parent.widget_2.canvas.ax.plot(timeC[:samples_per_period],ChampB[:samples_per_period],label="Bₖ")
            line3, = self.parent.widget_3.canvas.ax.plot(timeC[:samples_per_period],derivChampB[:samples_per_period]*(-N2*Section),label="V2")
            line4, = self.parent.widget_4.canvas.ax.plot(timeC[:samples_per_period],ChampH2[:samples_per_period],label="Hₖ")
            self.parent.widget_1.canvas.ax.set_ylabel("Volts",rotation=0)
            self.parent.widget_1.canvas.ax.yaxis.set_label_coords(0, 1)
            self.parent.widget_2.canvas.ax.set_ylabel("T",rotation=0)
            self.parent.widget_2.canvas.ax.yaxis.set_label_coords(0, 1)
            self.parent.widget_3.canvas.ax.set_ylabel("T/s",rotation=0)
            self.parent.widget_3.canvas.ax.yaxis.set_label_coords(0, 1)
            self.parent.widget_4.canvas.ax.set_ylabel("A/m",rotation=0)
            self.parent.widget_4.canvas.ax.yaxis.set_label_coords(0, 1)
            self.parent.widget_1.canvas.ax.set_xlabel(unite_T)
            self.parent.widget_1.canvas.ax.xaxis.set_label_coords(1.05, -0.025)
            self.parent.widget_2.canvas.ax.set_xlabel(unite_T)
            self.parent.widget_2.canvas.ax.xaxis.set_label_coords(1.05, -0.025)
            self.parent.widget_3.canvas.ax.set_xlabel(unite_T)
            self.parent.widget_3.canvas.ax.xaxis.set_label_coords(1.05, -0.025)
            self.parent.widget_4.canvas.ax.set_xlabel(unite_T)
            self.parent.widget_4.canvas.ax.xaxis.set_label_coords(1.05, -0.025)
            self.parent.widget_1.canvas.ax.legend()
            self.parent.widget_2.canvas.ax.legend()
            self.parent.widget_3.canvas.ax.legend()
            self.parent.widget_4.canvas.ax.legend()
            self.parent.widget_1.canvas.draw()
            self.parent.widget_2.canvas.draw()
            self.parent.widget_3.canvas.draw()
            self.parent.widget_4.canvas.draw()
            Fourier_dB_ref, Fourier_dB,Fourier_B_ref, Fourier_B, Fourier_V = compute_fft_signals(ChampBdes,ChampB[:samples_per_period],entree,derivChampBdes,derivChampB[:samples_per_period])
            Fourier_e_k=Fourier_V + alpha* (Fourier_B_ref-Fourier_B) + beta * (Fourier_dB_ref-Fourier_dB)
            e_k=    0.5*len(entree)*np.fft.irfft( Fourier_e_k[0:int(len(Fourier_e_k)/2)] - 1j * Fourier_e_k[int(len(Fourier_e_k)/2):] )
            entree = e_k
            
            entree = savgol_filter(entree, window_length=100, polyorder=3, mode="wrap")
            ChampH2 = savgol_filter(ChampH2, window_length=1000, polyorder=3, mode="wrap")
            ChampH2 = detrend(ChampH2, type='constant')
            RMSE = math.sqrt(np.square(np.subtract(derivChampB[:samples_per_period],derivChampBdes)).mean())
            self.parent.iteration_label.setText("Itération n⁰"+str(iteration))
            self.parent.Brefmax_value.setText(str(round(np.max(ChampBdes),3)))
            self.parent.Bkmax_value.setText(str(round(np.max(ChampB),3)))
            self.parent.FF_value.setText(str(round(FF(derivChampB,timeC[samples_per_period]),2)))
            self.parent.THD_value.setText(str(round(THDN(derivChampB, num_samples), 2))+" %")
            self.parent.RMSE_value.setText(str(round(RMSE,2)))
            self.parent.Hmax_value.setText(str(round(np.max(ChampH2),2)))
            self.parent.Imax_value.setText(str(round(np.max(ih),2)))
            # if iteration == 10:
            if (THDN(derivChampB, num_samples)<THDN(derivChampBdes, num_samples)+2):
                self.parent.THD_value.setStyleSheet("color: green;")
            else:
                self.parent.THD_value.setStyleSheet("color: black;")
            if (Amplitude<(np.max(ChampB)*1.005)) & (Amplitude>(np.max(ChampB)*0.995)):
                self.parent.Bkmax_value.setStyleSheet("color: green;")
            else:
                self.parent.Bkmax_value.setStyleSheet("color: black;")
            if (FF(derivChampB,timeC[samples_per_period])<FF(derivChampBdes,timeC[samples_per_period])*1.01) & (FF(derivChampB,timeC[samples_per_period])>FF(derivChampBdes,timeC[samples_per_period])*0.99):
                self.parent.FF_value.setStyleSheet("color: green;")
            else:
                self.parent.FF_value.setStyleSheet("color: black;")
            self.parent.iteration_label.setStyleSheet("color: black;")
            if ((Amplitude<(np.max(ChampB)*1.005)) & (Amplitude>(np.max(ChampB)*0.995))& (THDN(derivChampB, num_samples)<THDN(derivChampBdes, num_samples)+2)& ((FF(derivChampB,timeC[samples_per_period])<FF(derivChampBdes,timeC[samples_per_period])*1.01) & (FF(derivChampB,timeC[samples_per_period])>FF(derivChampBdes,timeC[samples_per_period])*0.99))) or iteration==30 or self.parent.stop==True:
                self.parent.stop == False
                self.parent.stop_button.setEnabled(True)
                self.parent.iteration_label.setStyleSheet("color: red;")
                break
            iteration += 1
        ChampB_nul = np.where(np.diff(np.sign(ChampB)))[0]
        Hcs = []
        for valeur in ChampB_nul:
            Hcs.append(np.abs(ChampH2[valeur]))
        Hc = np.mean(Hcs)
        ChampH2_nul = np.where(np.diff(np.sign(ChampH2)))[0]
        Brs = []
        for valeur in ChampH2_nul:
            Brs.append(np.abs(ChampB[valeur]))
        Br = np.mean(Brs)
        Pv = (1/timeC[samples_per_period])*integrate.simpson(-ChampH2[:samples_per_period]*derivChampB[:samples_per_period],x=timeC[:samples_per_period])
        self.parent.ChampH = -ChampH2[:samples_per_period]
        self.parent.main_window.ChampH = -ChampH2[:samples_per_period]
        self.parent.ChampB = ChampB[:samples_per_period]
        self.parent.main_window.ChampB = ChampB[:samples_per_period]
        self.parent.main_window.derivChampB = derivChampB[:samples_per_period]
        self.parent.main_window.update_mesures(np.max(ChampB), Frequence, Hc, Br, np.max(ChampH2), Mu, Pv)
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
        global Materiaux, Hauteur, Di, De, Section, Outils, Ns1, Ns2, Rs, Rh, Type, Forme, Freq, Ampli, Gain, Nbre_periode, Kf, Nm_ref, Mu, lm
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
    def __init__(self, main_window, *args, obj=None, **kwargs):
        super(NotesWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)
        self.main_window = main_window
        self.plainTextEdit.insertPlainText(self.main_window.Notes)
        self.setWindowTitle("Notes")
    def accept(self):
        self.main_window.Notes = self.plainTextEdit.toPlainText()
        self.close()
        

class AcquisWindow(QDialog, Ui_Page_acquisition):
    def __init__(self, *args, obj=None, **kwargs):
        super(AcquisWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle("Paramètres d'acquisition")
        self.warning_edit.setVisible(False)
        self.Nbre_iter_spin.setValue(iteration_max)
        self.Nbre_ech_spin.setValue(num_samples)
        self.Nbre_bits_combo.setCurrentText(Resolution)
        self.Nbre_enregi_spin.setValue(Nbre_enregist)
        self.coeff_alpha_spin.setValue(alpha)
        self.coeff_beta_spin.setValue(Beta)
    def accept(self):
        global iteration_max,num_samples,Resolution,Nbre_enregist,alpha,Beta
        iteration_max = self.Nbre_iter_spin.value()
        num_samples = self.Nbre_ech_spin.value()
        Resolution = self.Nbre_bits_combo.currentText()
        Nbre_enregist = self.Nbre_enregi_spin.value()
        alpha = self.coeff_alpha_spin.value()
        Beta = self.coeff_beta_spin.value()

class ComparWindow(QDialog, Ui_curve_comparaison):
    def __init__(self, *args, obj=None, **kwargs):
        super(ComparWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle("Comparaison de courbes")
        self.widget_cpr.canvas.ax.grid()
        self.import_button.clicked.connect(self.import_csv)
        self.clear_button.clicked.connect(self.clear_canva)
        self.colors_button.clicked.connect(self.change_color)
        self.remove_row_button.clicked.connect(self.delete_row)
        self.add_row_button.clicked.connect(self.add_row)
        self.signals = []
        self.lines = []
    
    def add_row(self):
        self.tableWidget.insertRow(self.tableWidget.rowCount())
    
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
            self.widget_cpr.canvas.draw()

    def plot_data_compar(self, a, b, title):
        line, = self.widget_cpr.canvas.ax.plot(a, b, label=title)
        self.lines.append(line)
        self.signals.append(title)
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
        br = variables.get("Br (T) =")
        freq = variables.get("Freq(Hz) =")
        hc = variables.get("Hc =")
        Mu = variables.get("µr =")
        hmax = variables.get("Hmax =")
        W = variables.get("W(J/m³) =")
        Pv = variables.get("P(W/m³) =")
        champ_h = arrays.get("ChampH (A/m)")
        champ_b = arrays.get("ChampB (T)")
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
        self.tableWidget.setItem(empty_row, 1, QTableWidgetItem(str(round(float(bmax),2))))
        self.tableWidget.setItem(empty_row, 2, QTableWidgetItem(freq))
        self.tableWidget.setItem(empty_row, 3, QTableWidgetItem(str(round(float(hc),2))))
        self.tableWidget.setItem(empty_row, 4, QTableWidgetItem(str(round(float(br),2))))
        self.tableWidget.setItem(empty_row, 5, QTableWidgetItem(str(round(float(hmax),2))))
        self.tableWidget.setItem(empty_row, 6, QTableWidgetItem(Mu))
        self.tableWidget.setItem(empty_row, 7, QTableWidgetItem(str(round(float(W),2))))
        self.tableWidget.setItem(empty_row, 8, QTableWidgetItem(str(round(float(Pv),2))))
        
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
    def __init__(self, main_window, *args, obj=None, **kwargs):
        super(SupervisionWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle("Supervision")
        self.main_window = main_window
        self.stop_button.clicked.connect(self.action_stop)
        self.stop = False
        self.ChampH = None
        self.ChampB= None
        self.derivChampB = None
        self.timeC = None
        self.thread = None
        if self.thread is None or not self.thread.isRunning():
            self.thread = Worker(self)
            self.thread.finished.connect(self.on_long_task_finished)
            self.thread.start()

    def on_long_task_finished(self):
        self.main_window.Button_start.setEnabled(True)
        self.thread = None
        self.main_window.plot_data(self.ChampH,self.ChampB)
        self.close()
        
    def action_stop(self):
        self.stop = True
        self.stop_button.setEnabled(False)


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
        x = range(0, 10)
        y = range(0, 20, 2)
        self.Notes = ""
        self.plot_data(x,y)
        self._connectActions()

    def plot_data(self,x,y):
        self.widget.canvas.ax.cla()
        self.widget.canvas.ax.plot(x, y)
        self.widget.canvas.ax.set_ylabel("B(T)")
        self.widget.canvas.ax.set_xlabel("H(A/m)")
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
        
    def update_mesures(self,bmax,Freq,hc,br,hmax,Mu_r,Pv):
        self.Bmax = bmax
        self.Frequence = Freq
        self.Hc = hc
        self.Br = br
        self.Hmax = hmax
        self.Mu = Mu_r
        self.Pv = Pv
        self.W = Pv*3600
        self.Bmax_value.setText(str(round(self.Bmax,2)))
        self.Freq_value.setText(str(round(self.Frequence,2)))
        self.Hc_value.setText(str(round(self.Hc,3)))
        self.Br_value.setText(str(round(self.Br,3)))
        self.Hmax_value.setText(str(round(self.Hmax,2)))
        self.Mu_value.setText(str(round(self.Mu,1)))
        self.W_value.setText(str(round(self.W,2)))
        self.Pv_value.setText(str(round(self.Pv,2)))
        
    def acquisition(self):
        self.w = AcquisWindow()
        self.w.show()

    def comparaison(self):
        self.w = ComparWindow()
        self.w.show()

    def notes(self):
        self.win = NotesWindow(self)
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
            file_name = Nm_ref
            project_dir = os.path.join(selected_dir, file_name)
            if not os.path.exists(project_dir):
                os.makedirs(project_dir)
            now = datetime.datetime.now()
            date_time = now.strftime("%Y-%m-%d_%H-%M-%S")
            settings = QSettings(os.path.join(
                project_dir, f"configuration_{date_time}.cfg"), QSettings.IniFormat)
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
            
            variables = {
                "Bmax (T)": str(self.Bmax),
                "Freq(Hz)": str(self.Frequence),
                "Hc": str(self.Hc),
                "Br (T)": str(self.Br),
                "Hmax": str(self.Hmax),
                "µr": str(self.Mu),
                "W(J/m³)": str(self.W),
                "P(W/m³)": str(self.Pv)
            }

            arrays = {
                "temps (s)": self.timeC,
                "ChampH (A/m)": self.ChampH,
                "ChampB (T)": self.ChampB,
                "dB/dt (T/s)": self.derivChampB
            }

            csv_file = Nm_ref + "_" + str(Materiaux) +"_" + str (Forme) + "_"+ str(self.Frequence) + "_" +str(round(self.Bmax,2)) + ".csv"
            csv_file = os.path.join(project_dir, csv_file)

            with open(csv_file, mode="w", newline="") as csvfile:
                writer = csv.writer(csvfile, delimiter=",")

                variable_row = []
                for key, value in variables.items():
                    variable_row.append(f"{key} =")
                    variable_row.append(value)
                writer.writerow(variable_row)

                # Write array names in the second row
                writer.writerow(list(arrays.keys()))

                # Write array values in the subsequent rows
                for i in range(len(arrays["temps (s)"])):
                    row = [arrays[array][i] for array in arrays.keys()]
                    writer.writerow(row)
            txt_file = os.path.join(project_dir,"Notes_"+str(date_time))
            with open(txt_file, "w") as text_file:
                text_file.write(self.Notes)

    def start(self):
        self.Button_start.setEnabled(False)
        self.w = SupervisionWindow(self)
        self.w.show()

    def closeEvent(self, event):
        for window in QtWidgets.QApplication.topLevelWidgets():
            window.close()
        QtWidgets.QApplication.quit()


app = QtWidgets.QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec()
