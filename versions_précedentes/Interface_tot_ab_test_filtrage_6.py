#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Feb  9 15:09:28 2024

@author: caracterisation
"""

# pyuic5 mainwindow.ui -o MainWindow.py
import sys
import datetime
import os
import random
import math
from PyQt5 import QtWidgets, uic
from Mainwindow_EG import Ui_JTcontrol
from Supervision import Ui_supervision
from page_acquisition_2 import Ui_Page_acquisition
from dialog import Ui_Dialog
from Notes import Ui_notes
from error import Ui_error
import pandas as pd

from analyse_fft_bh import Ui_analyse

from curve_comparaison import Ui_curve_comparaison
from helpwindow import Ui_HelpWindow
from pertesvsfreq import Ui_PertesVsFreq
from amplificateur import Ui_Ampli
from amplificateur_defaut import Ui_Ampli_defaut

from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtWidgets import QColorDialog, QTableWidgetItem, QDialogButtonBox, QComboBox, QDialog, QGridLayout, QPushButton, QFileDialog, QVBoxLayout,QButtonGroup
from PyQt5.QtCore import QThread, pyqtSignal, QSettings, QSize, Qt, QObject, QRunnable, QThreadPool,pyqtSlot
import numpy as np
from numpy import linspace
import csv
import time

import serial
import serial.tools.list_ports

# Initialisation paramètres

#Paramètre d'acquisition
Hauteur = Harmo= Di = De = Section = Rs = Rh = Freq = Ampli = Gain = Nbre_enregist = mu_r = lm = Epaisseur = Nbre_Bandes = Largeur = alpha = beta = gamma = cycle = 0
Sonde=1
Kf = 1
Nbre_periode = 2
iteration_max = 100
num_samples = 5000
mu_r = 2000
Resolution = 14
Ns1 = 6
Ns2 = 6
mu_0 = 4e-7*np.pi
Nbre_enregist = 10
Materiaux = "Fer pur"
Outils = "Tore enroulé"
Type = "Cycle d'hystérèsis"
Forme = "Sinusoïdale"
Nm_ref = "Nom_Ref"
rampe = 5
alpha=beta=0.5
gamma=5
selected_dir=""
mode_filtre = 'mirror'
fenetre_filtre = 500
ChampBdes = timeC = func_eval = 0
Erreur = []
port_connection=''

# tableau de fréquence pour le mode Séquence
Freq_depart=Freq_fin=Ampli_fin=Ampli_fin=0
Freq_1=Freq_2=Freq_3=Freq_4=Freq_5=Freq_6=Freq_7=Freq_8=Freq_9=Freq_10=0
Ampli_1=Ampli_2=Ampli_3=Ampli_4=Ampli_5=Ampli_6=Ampli_7=Ampli_8=Ampli_9=Ampli_10=Freq_pt=Ampli_pt=0
Freq_tab=[]
Freq_tab_tempo=[]
Ampli_tab=[]
Mode_Lineaire="Lineaire"
Mode_Auto="Simple"
Mode_asservissement="PI FFT"

# tableau de configuration de la range du Pico
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


bufferAMax = bufferAMin = bufferBMax = bufferBMin = bufferCMax = bufferCMin = []
Selection_Channel = [["PS5000A_CHANNEL_A", "setChA", "setdataBuffersA", bufferAMax, bufferAMin],
                     ["PS5000A_CHANNEL_B", "setChA",
                         "setdataBuffersB", bufferBMax, bufferBMin],
                     ["PS5000A_CHANNEL_C", "setChA", "setdataBuffersC", bufferCMax, bufferCMin]]

Temperature_flag=0
limite=100

class Worker(QThread):
    """
    La class Worker est la partie acquisition du programme
    Elle est appelée par la classe Supervison lors de l'appuie sur le bouton Start
    """

    finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.parent = parent

    def run(self):
        """
        Permet de mesurer les signaux et calculer les valeurs intrasecs de l'élément mesuré.

        Returns
        -------
        Ne renvois rien, mais modifie les variables globales


        """
        global Erreur , mode_filtre, fenetre_filtre, Sonde, gamma, Materiaux, Mode_asservissement, Hauteur, Di, De, Section, Outils, Ns1, Ns2, Rs, Rh, Type, Forme, Freq, Ampli, Gain, Nbre_periode, Kf, Nm_ref, mu_r, lm, num_samples, Resolution, Nbre_enregist, alpha, beta, rampe, iteration_max, cycle
        import ctypes
        import usbtmc
        import time as tm
        from scipy import integrate
        from scipy.signal import get_window,detrend, correlate, correlation_lags,  hilbert, savgol_filter, sawtooth, butter
        from scipy.signal.windows import blackmanharris
        from scipy.interpolate import interp1d
        from scipy.fft import fft, rfft, irfft
        from picosdk.ps5000a import ps5000a as ps
        import matplotlib.pyplot as plt
        from picosdk.functions import adc2mV, assert_pico_ok
        from numpy import linalg as LA
        from numpy.fft import fft, ifft
        from scipy import signal
        import time

        def find_range(f, x):
            uppermin2 = lowermin2 = 0
            for i in np.arange(x+1, len(f)):
                if f[i+1] >= f[i]:
                    uppermin2 = i
                    break
            for i in np.arange(x-1, 0, -1):
                if f[i] <= f[i-1]:
                    lowermin2 = i + 1
                    break
            return (lowermin2, uppermin2)

        def symetrie(an, bn):
            """
            Permet supprimer tous les harmonique de rang paire car nous travaillons avec un sinus
            """
            for i in range(len(an)):
                if i % 2 == 0:
                    an[i] = 0
                    bn[i] = 0
         
            return np.concatenate((an, bn))

        def compute_fft_signals(B_des, B_reel, V1_sim, dB_des, dB_reel):
            """
            Cette fonction calcul la transformée de Fourier des signaux mesurés
            """

            # Calcul des coefficients de Fourier de la référence de B
            an_B_ref = 2*np.real(np.fft.rfft(B_des))/len(B_des)
            bn_B_ref = -2*np.imag(np.fft.rfft(B_des))/len(B_des)
            Fourier_B_des = symetrie(an_B_ref, bn_B_ref)
            # Calcul des coefficients de Fourier de B obtenu
            an_B_sim = 2*np.real(np.fft.rfft(B_reel))/len(B_reel)
            bn_B_sim = -2*np.imag(np.fft.rfft(B_reel))/len(B_reel)
            Fourier_B_reel = symetrie(an_B_sim, bn_B_sim)
            # Calcul des coefficients de la tension V
            an_V_reel = 2*np.real(np.fft.rfft(V1_sim))/len(V1_sim)
            bn_V_reel = -2*np.imag(np.fft.rfft(V1_sim))/len(V1_sim)
            Fourier_V_reel = symetrie(an_V_reel, bn_V_reel)
            # Calcul des coefficients de la tension dB/dt de référence
            an_dB_ref = 2*np.real(np.fft.rfft(dB_des)
                                  )/len(dB_des)
            bn_dB_ref = -2 * \
                np.imag(np.fft.rfft(dB_des))/len(dB_des)
            Fourier_dB_des = symetrie(an_dB_ref, bn_dB_ref)
            # Calcul des coefficients de la tension dB/dt obtenu
            an_dB_sim = 2*np.real(np.fft.rfft(dB_reel))/len(dB_reel)
            bn_dB_sim = -2*np.imag(np.fft.rfft(dB_reel))/len(dB_reel)
            Fourier_dB_reel = symetrie(an_dB_sim, bn_dB_sim)
                      
            #NbEch = len(Fourier_V_reel)
 
            #t = linspace(0,(NbEch-1),NbEch)
            #t = t[0:(len(Fourier_V_reel))]
            #plt.plot(t, Fourier_V_reel, 'k', linewidth=2)
            #plt.show()
            return Fourier_dB_des, Fourier_dB_reel, Fourier_B_des, Fourier_B_reel, Fourier_V_reel

        def THDN(signal, sample_rate):
            """
            Calcul le taux d'harmonique d'ordre 3 (THD)
            Le THD est un critère de convergence
            """
            signal -= np.mean(signal) # supression de la valeur moyenne
            windowed = signal * blackmanharris(len(signal)) # Applique le filtre Blackmanharris au signal
            total_rms = np.sqrt(np.mean(np.absolute(windowed)**2)) # valeur efficase
            f = rfft(windowed) # Transformée de Fourier
            i = np.argmax(abs(f)) # indice du fondamental
            lowermin, uppermin = find_range(abs(f), i)
            f[lowermin: uppermin] = 0
            noise = irfft(f)
            #print('noise=',noise)
            THDN = np.sqrt(np.mean(np.absolute(noise)**2)) / total_rms
            #print('THDN =',THDN*100 )
            print('total_rms=',total_rms )
            return THDN*100

        def FF(x, T):
            """
            Calcul le facteur de forme
            """
            N = len(x)
            x = np.abs(x)
            x_rms = np.sqrt(np.mean(x**2))
            x_int = (T/N) * np.sum((x[:-1] + x[1:]) / 2)
            ff = x_rms / (x_int / T)
            return ff

        def GBF(entree):
            """
            Envoie le signal en entrée du GBF (sous forme d'un tableau de point)
            Le GBF prend en compte la fréquence d'échantillonnage et le nombre de point pour générer le signal. 
            La fréquence d'échantillonnage est bloqué à 160 000 000 échantillon par seconde.
            Le paramètre len(entree)*Frequence permet de calculer de calculer la fréquence d'échantillonnage,
            Donc lorsque l'on veut augmenter la fréquence, il faut diminuer le nombre de point à envoyer.
            Dans le cas contraire, Le GBF enverra un signal avec un fréquence inférieur pour garder le nombre de point.

            Parameters
            ----------
            entree : Array
                Signal à envoyer sous forme d'un tableau de point

            Returns
            -------
            entree : Array
                Returne le signal envoyé par le GBF (pas de modification sur l'entrée)
            pk : Float
                Maximum du signal envoyé

            """
                        
            

            # Fonction qui permets de diminuer le nombre de point du signal pour que
            # la fréquence d'échantillonnage ne dépasse pas 160 000 000 échantillons par seconde
            t = np.linspace(0, 1/int(Frequence), len(entree))


            interpolation_entree = interp1d(t, entree)
            i = len(entree)
            while len(t)*Frequence > 159000000:
                # on suprime un point tant qu'on dépasse la la limite d'échantillonnage
                i -= 1
                t = np.linspace(0, 1/int(Frequence), i)

            # On recalcule la nouvelle entree avec moins de point (si nécessaire)
            entree = interpolation_entree(t)
            ##
            # with open('/home/caracterisation/Documents/Stage Evan Gossard/entree.npy', 'wb') as f:
            #     np.save(f, entree)
            # with open('/home/caracterisation/Documents/Stage Evan Gossard/time.npy', 'wb') as f:
            #     np.save(f, t)
                
            # tps1 = time.clock()
 
            # Connection au GBF
            instr = usbtmc.Instrument(2391, 9991)  # Identifiant GBF
            # Supression des anciens messages d'erreures
            instr.write("DATA:VOL:CLE")
            index = 0
            message2 = 'DATA:ARB myArb'

            # Recherhce du max du signal d'entree
            if np.max(entree) > np.abs(np.min(entree)):
                pk = np.max(entree)
            else:
                pk = np.abs(np.min(entree))

            # envoi des valeurs du signal d'entree
            # A noter que les valeurs doivent être normaliser (entre 0 et 1)
            for nbre in entree:
                message2 = message2 + ', ' + \
                    str("%.3f" % round(nbre/pk, 3))
                index += 1
            instr.timeout = 5000
            instr.write(message2)
            instr.write('FUNCtion:ARB "myArb"')
            # Définission des paramètres du GBF
            # Fréquence d'échantillonnage, Max amplitude, Offset
            #instr.write(f'APPLy:ARB {len(entree)*Frequence},{pk},{np.mean(entree)}')
            instr.write(f'APPLy:ARB {len(entree)*Frequence},{pk},{0}')

            instr.write("OUTP ON")
            # tps2 = time.clock()
            # print("temps de transfert : ",tps2-tps1)

            # Recherche des erreurs
            rawError = ''
            errorCode = -1
            while errorCode != 0:
                instr.write('SYST:ERR?')
                rawError = instr.read()
                errorParts = rawError.split(',')
                errorCode = int(errorParts[0])
                errorMessage = errorParts[1].rstrip('\n')
                if not errorCode == 0:
                    print('INSTRUMENT ERROR - Error code: %d, error message: %s' %
                          (errorCode, errorMessage))
                    instr.write('*CLS')
                    # Close the connection to the instrument
                    instr.close()
                    raise Exception ('INSTRUMENT ERROR - Error code: %d, error message: %s' %
                          (errorCode, errorMessage))

                    self.parent.ChampH = np.zeros(num_samples)
                    self.parent.main_window.ChampH = np.zeros(num_samples)
                    self.parent.ChampB = np.zeros(num_samples)
                    self.parent.main_window.ChampB = np.zeros(num_samples)
                    self.parent.main_window.derivChampB = np.zeros(num_samples)
                    self.parent.main_window.update_mesures(1, 1, 1, 1, 1, 1, 1)
                    self.finished.emit()
            instr.write('DISP OFF')
            # affichage nombre d'itération
            instr.write(f'DISP:TEXT "Iteration n{iteration}"')
            tm.sleep(1)
            instr.write('DISP:TEXT:CLE')
            instr.write('DISP ON')
            instr.close()

        def Mesure(Selection_Channel, Channel_ranges):
            """
            Acquisition des données du Pico Scope.

            Cette fonction fonctionne en 3 étapes : 
                - 1 = Initiliation des paramètres du Pico
                - 2 = Première acquisition pour faire le choix du calibre (commence au plus petit calibre puis augmente tant que la valeur max ne dépasse plus de la fenêtre de capture)
                - 3 = Acquisition des signaux dans la variable BuffersMax
            Une boucle for permets l'aquisition sur les trois voies (étapes 2 et 3)

            Les signaux sont ensuite mis dans la variable stockage, puis renvoyée

            Parameters
            ----------
            Selection_Channel : tableau (3x5)
                Tableau qui permet de séléctionner la voie du Pico et de la configurer. 
                Selection_Channel[i] = Voie oscillo
                Selection_Channel[i][u] = Paramètre de la voie
                EX pour la voie 1 : 
                        u=0 : "PS5000A_CHANNEL_A",
                        u=1 : "setChA",
                        u=2 : "setdataBuffersA",
                        u=3 : variable de stockage du bufferMax,
                        u=4 : variable de stockage du bufferMin,

            Channelranges : Tableau (9x1)
                Contient les paramètres pour configurer la plage de données des voies de l'oscillo
            entree : Tableau
                Signal à envoyer sous forme d'un tableau de point

            Returns
            -------
            Stockage : Tableau ((Nbre_enregistrement x Nbre de Mesures) x Nbre de voies)
                Contient les valeurs récupérées par l'oscillo
            cmaxSamples : Int ?
                Nombre maximum d'échantillon
            timeIntervalns : Int ?
                Temps entre deux échantillon en nanoseconde

            """
            Stockage = []
            # time.clock = time.time

            chandle = ctypes.c_int16()
            status = {}
            resolution = ps.PS5000A_DEVICE_RESOLUTION["PS5000A_DR_" +
                                                      str(Num_resolution)+"BIT"]

            status["openunit"] = ps.ps5000aOpenUnit(
                ctypes.byref(chandle), None, resolution)


            # Teste connection du PICO
            try:
                assert_pico_ok(status["openunit"])
            except:  # PicoNotOkError:
                powerStatus = status["openunit"]
                if powerStatus == 286:  # PICO_USB3_0_DEVICE_NON_USB3_0_PORT
                    status["changePowerSource"] = ps.ps5000aChangePowerSource(
                        chandle, powerStatus)
                elif powerStatus == 282:  # PICO_POWER_SUPPLY_NOT_CONNECTED
                    status["changePowerSource"] = ps.ps5000aChangePowerSource(
                        chandle, powerStatus)
                else:
                    raise
                assert_pico_ok(status["changePowerSource"])

            maxADC = ctypes.c_int16()
            status["maximumValue"] = ps.ps5000aMaximumValue(
                chandle, ctypes.byref(maxADC))
            assert_pico_ok(status["maximumValue"])
            # enabled = 1
            threshold = int(maxADC.value/4)
            # direction = PS5000A_RISING = 2
            # delay = 0 s
            # auto Trigger = 1000 ms
            status["trigger"] = ps.ps5000aSetSimpleTrigger(
                chandle, 1, ps.PS5000A_CHANNEL["PS5000A_CHANNEL_A"], threshold, 2, 0, 1000)
            assert_pico_ok(status["trigger"])

            for Numero_Channel in Selection_Channel:  # Boucle séléction channel
                current_range = -1
                #print("Numéro de voie oscillo : ",Numero_Channel[0])
                # tps1 = time.clock()
                while True:
                    current_range = current_range+1
                    # séléction channel
                    channel = ps.PS5000A_CHANNEL[Numero_Channel[0]]
                    # enabled = 1
                    coupling_type = ps.PS5000A_COUPLING["PS5000A_DC"]
                    # Séléction calibre du PICO
                    ChRange = ps.PS5000A_RANGE[Channel_ranges[current_range]]
                    # analogue offset = 0 V
                    status[Numero_Channel[1]] = ps.ps5000aSetChannel(
                        chandle, channel, 1, coupling_type, ChRange, 0)
                    assert_pico_ok(status[Numero_Channel[1]])

                    preTriggerSamples = num_samples//2
                    postTriggerSamples = num_samples//2
                    maxSamples = preTriggerSamples + postTriggerSamples  # Nombre d'échantillon capturé
                    # Initialisation des variables de stockage des données
                    BuffersMax = np.ones((Nbre_enregistrement, maxSamples))
                    BuffersMin = np.ones((Nbre_enregistrement, maxSamples))

                    duration = Nbre_periode / \
                        (Frequence)  # Durée de la période

                    # Calcule du timebase (ce nombre corespond à l'interval entre les points (voir datasheat p.22))
                    if Num_resolution == 12 or Num_resolution == 16:
                        if (duration/num_samples) <= 8e-9:
                            timebase = round(
                                np.log(duration*500000000/maxSamples)/np.log(2)+1)
                        else:
                            timebase = round((duration*62500000/maxSamples)+3)
                    elif Num_resolution == 8:
                        timebase = 1
                        maxSamples = int(
                            Nbre_periode / (Frequence)*1e9/2**(timebase))
                        preTriggerSamples = int(maxSamples//2)
                        postTriggerSamples = int(maxSamples//2)
                        BuffersMax = np.ones((Nbre_enregistrement, maxSamples))
                        BuffersMin = np.ones((Nbre_enregistrement, maxSamples))
                    else:
                        timebase = round((duration*125000000/maxSamples)+2)
                        # 14 bit est limité à la base de temps 3 (8 ns)
                        if timebase < 3:
                            timebase = 3  # On le bloque si on est en dessous pour avoir l'échelle de temps minimum
                            maxSamples = int(
                                Nbre_periode / (Frequence)*125000000/(timebase-2))

                            # On vérifi que le nombre d'échantillon est paire sinon il y aura une erreur lors de l'affichage
                            if maxSamples % 2 == 0:
                                maxSamples = int(
                                    Nbre_periode / (Frequence)*125000000/(timebase-2))
                            else:
                                maxSamples = int(
                                    Nbre_periode / (Frequence)*125000000/(timebase-2))-1

                            preTriggerSamples = int(maxSamples//2)
                            postTriggerSamples = int(maxSamples//2)
                            BuffersMax = np.ones(
                                (Nbre_enregistrement, maxSamples))
                            BuffersMin = np.ones(
                                (Nbre_enregistrement, maxSamples))

                    timeIntervalns = ctypes.c_float()
                    returnedMaxSamples = ctypes.c_int32()

                    status["getTimebase2"] = ps.ps5000aGetTimebase2(chandle, timebase, maxSamples, ctypes.byref(
                        timeIntervalns), ctypes.byref(returnedMaxSamples), 0)
                    assert_pico_ok(status["getTimebase2"])

                    # Run Block est la fonction qui enregistre les donées dans la mémoire tempon
                    # ici les donées enregistrées servent à régler le calibre (les données de mesures seront remesurées par la suite)
                    status["runBlock"] = ps.ps5000aRunBlock(
                        chandle, preTriggerSamples, postTriggerSamples, timebase, None, 0, None, None)
                    assert_pico_ok(status["runBlock"])

                    ready = ctypes.c_int16(0)
                    check = ctypes.c_int16(0)
                    while ready.value == check.value:
                        status["isReady"] = ps.ps5000aIsReady(
                            chandle, ctypes.byref(ready))

                    Numero_Channel[3] = (ctypes.c_int16 * maxSamples)()
                    Numero_Channel[4] = (ctypes.c_int16 * maxSamples)()

                    source = ps.PS5000A_CHANNEL[Numero_Channel[0]]
                    # pointer to buffer max = ctypes.byref(bufferAMax)
                    # pointer to buffer min = ctypes.byref(bufferAMin)
                    # buffer length = maxSamples
                    # segment index = 0
                    # ratio mode = PS5000A_RATIO_MODE_NONE = 0
                    status[Numero_Channel[2]] = ps.ps5000aSetDataBuffers(chandle, source, ctypes.byref(
                        Numero_Channel[3]), ctypes.byref(Numero_Channel[4]), maxSamples, 0, 0)
                    assert_pico_ok(status[Numero_Channel[2]])

                    overflow = ctypes.c_int16()
                    cmaxSamples = ctypes.c_int32(
                        maxSamples)  # Nbre d'echantillons

                    # downsample ratio = 0
                    # downsample ratio mode = PS5000A_RATIO_MODE_NONE
                    status["getValues"] = ps.ps5000aGetValues(
                        chandle, 0, ctypes.byref(cmaxSamples), 0, 0, 0, ctypes.byref(overflow))
                    assert_pico_ok(status["getValues"])

                    BuffersMax[0] = adc2mV(Numero_Channel[3], ChRange, maxADC)
                    BuffersMin[0] = adc2mV(Numero_Channel[4], ChRange, maxADC)

                    # ATTENTION : Regarder la variable overflow ne fonctionne pas sur la voie C et D,
                    # il est donc préférable de vérifier par rapport à la valeur maximal en décimal pour chaque calibres

                    if Num_resolution == 8:
                        # Valeur max pour 8 bit (voir datasheet)
                        Maximum_value = 32512
                    else:
                        # Pour les résolution autre que 8 bits (12, 14 1516), on prend la valeur maximum sur 16 bits
                        Maximum_value = (2**(16))/2-1
                    Maximum_value -= 300  # valeur arbitraire de sécuritée
                    Maximum_value = [Maximum_value, 0]

                    if np.max(BuffersMax[0]) < np.max(adc2mV(Maximum_value, ChRange, maxADC)):
                        break

                # Aquisition des données
                for i in range(1, Nbre_enregistrement):
                    status["runBlock"] = ps.ps5000aRunBlock(
                        chandle, preTriggerSamples, postTriggerSamples, timebase, None, 0, None, None)
                    assert_pico_ok(status["runBlock"])

                    ready2 = ctypes.c_int16(0)
                    check2 = ctypes.c_int16(0)
                    while ready2.value == check2.value:
                        status["isReady"] = ps.ps5000aIsReady(
                            chandle, ctypes.byref(ready2))

                    Numero_Channel[3] = (ctypes.c_int16 * maxSamples)()
                    Numero_Channel[4] = (ctypes.c_int16 * maxSamples)()
                    # handle = chandle
                    # ratio mode = PS5000A_RATIO_MODE_NONE = 0
                    status[Numero_Channel[2]] = ps.ps5000aSetDataBuffers(chandle, source, ctypes.byref(
                        Numero_Channel[3]), ctypes.byref(Numero_Channel[4]), maxSamples, 0, 0)
                    assert_pico_ok(status[Numero_Channel[2]])
                    overflow = ctypes.c_int16()
                    cmaxSamples = ctypes.c_int32(
                        maxSamples)  # Nbre d'echantillons

                    # downsample ratio = 0
                    # downsample ratio mode = PS5000A_RATIO_MODE_NONE
                    status["getValues"] = ps.ps5000aGetValues(
                        chandle, 0, ctypes.byref(cmaxSamples), 0, 0, 0, ctypes.byref(overflow))
                    assert_pico_ok(status["getValues"])
                    BuffersMax[i] = adc2mV(Numero_Channel[3], ChRange, maxADC)
                    BuffersMin[i] = adc2mV(Numero_Channel[4], ChRange, maxADC)

                # La variable stockage sauvegarde les valeurs enregistrées sur les trois voies
                Stockage.append(BuffersMax)
                # tps2 = time.clock()
                #print("temps de calcul : ",tps2 - tps1)
            status["stop"] = ps.ps5000aStop(chandle)
            assert_pico_ok(status["stop"])
            status["close"] = ps.ps5000aCloseUnit(chandle)
            assert_pico_ok(status["close"])

            return Stockage, cmaxSamples, timeIntervalns


        def Detection_Bornes(adc2mVChAMax, adc2mVChBMax, adc2mVChCMax):
            """
            Permet de détecter si le transformateur est branché avec ses bornes homologues ou non
            Le but est de comparer la phase des tensions aux bornes du transformateur
            On veut toujours mesurer V2 dans le même sens peut importe comment est branché le transformateur

            1- Pour cela on calcule V1 étant la tension en sortie de l'ampli moins les tensions de la résistance série et de shunt
            2- On apllique la fonction de correlation sur les V1 et V2 obtenues
            3- On compare la lag entre eux. Si on est inférieur à la moitier de la période (num_sample) alors on est en phase sinon non

            Le changement des bornes ce fait dans la fonction run pour ne pas modifier de signaux dans cette fonction
            Dans le cas des bornes non homologues, on inverse la tension V2 (ici ça sera -adc2mVChCMax)

            Parameters
            ----------
            adc2mVChAMax : 
                Tension de sortie du GBF (A noter qu'il faut le multiplier par le gain de l'ampli)
            adc2mVChBMax : 
                Tension aux bornes de la résisatance de shunt
            adc2mVChCMax : 
                Tension de sortie V2

            Returns
            -------
            Bornes_homologues : string
                "oui" pour les bornes sont homologues
                "non" pour les bornes sont non homologues

            """
            V1 = adc2mVChAMax*Gain  # tension à la sortie du GBF multiplié par le gain de l'ampli

            V1 = [adc2mVChAMax, np.negative(adc2mVChBMax/Rsh*Rs)]  # tension au primaire du transformateur

            V1 = np.sum(V1, axis=0)  # Somme le long des colonnes

            V2 = adc2mVChCMax  # Tension en sortie de transformateur
           
            # On applique la transformer de Fourier
            fft_ChampBdes = fft(V1)
            fft_ChampB = fft(V2)

            # recherche du fondamentale pour obtenir deux signaux simples
            fond_ChampBdes = np.zeros(len(fft_ChampBdes))
            fond_ChampBdes[np.argmax(np.abs(fft_ChampBdes))] = np.max(
                np.abs(fft_ChampBdes))
            fond_ChampB = np.zeros(len(fft_ChampB))
            fond_ChampB[np.argmax(np.abs(fft_ChampB))] = np.max(
                np.abs(fft_ChampB))

            # Transformée de Fourier inverse
            ChampBdes_prim = ifft(
                fond_ChampBdes*np.exp(1j*np.angle(fft_ChampBdes))).real
            ChampB_prim = ifft(
                fond_ChampB*np.exp(1j*np.angle(fft_ChampB))).real


            # Code Clémentine (recherche du zéros)
            try:
                _, a = start_from_zero(ChampBdes_prim)
                _, b = start_from_zero(ChampB_prim)

                lag=b-a
            except:
                lag=0
            # On inverse la tension V2 si les bornes ne sont pas homologuées
            if lag >= num_samples/2:
                Bornes_homologues = "oui"
                adc2mVChCMax = adc2mVChCMax
            else:
                Bornes_homologues = "non"
                adc2mVChCMax = np.negative(adc2mVChCMax)

            return adc2mVChBMax, adc2mVChCMax

        def start_from_zero(sig):
            """
            Détection du passage par zéros et supression du déphasage entre 2 signaux
            """

            # Détection du passage à 0 du champ B
            zero_logical = (sig == 0)  # Exact zero points
            # Points where we cross zero without reaching it
            zero_crossing_logical = (sig * np.roll(sig, 1) < 0)
            # Keep only the rising zeros from both previous set
            rising_crossing_logical = (zero_logical & np.roll(
                sig > 0, -1)) | (zero_crossing_logical & (sig > 0))
            eligibles = np.where(rising_crossing_logical)[0]  # Get the indexes
            # Make an only vector with the starting 0, then find the closest
            choosen = np.argmin(
                np.min([eligibles, len(sig) - eligibles], axis=0))
            increment = -eligibles[choosen] + 1
            sig_out = np.roll(sig, increment)
            return sig_out, increment

        def Synchronisation(ChampBdes, ChampB):
            """
            Cette fonction permet de synchroniser 2 signaux.
            On applique la transformée de Fourier puis on récupère leurs fondamentales
            On reconstruit en temporelle puis on mesure le déphasage avec la correlation
            Pour finir, on enlève le délai aux signaux de base

            Pour un résultat plus précis on réaplique la transformée de Hilbert puis on fait la différence de phase

            Cette fonction fonctionne avec tous les signeaux périodeiques (avec du bruit, triangle, ...)


            Parameters
            ----------
            ChampBdes : tableaux () -> Une période
                Signale de référence
            ChampB : tableaux () -> Une période
                Signal à synchroniser

            Returns
            -------
            ChampB : tableau ()
                Signal synchroniser 
            lag : TYPE
                lag obtenu

            """

            # On applique la transformer de Fourier
            fft_ChampBdes = fft(ChampBdes)
            fft_ChampB = fft(ChampB)

            # recherche du fondamentale pour obtenir deux signaux simples
            fond_ChampBdes = np.zeros(len(fft_ChampBdes))
            fond_ChampBdes[np.argmax(np.abs(fft_ChampBdes))] = np.max(
                np.abs(fft_ChampBdes))
            fond_ChampB = np.zeros(len(fft_ChampB))
            fond_ChampB[np.argmax(np.abs(fft_ChampB))] = np.max(
                np.abs(fft_ChampB))

            # Transformée de Fourier inverse
            ChampBdes_prim = ifft(
                fond_ChampBdes*np.exp(1j*np.angle(fft_ChampBdes))).real
            ChampB_prim = ifft(
                fond_ChampB*np.exp(1j*np.angle(fft_ChampB))).real

            # # Correlation des deux sinus obtenu et mesure du retard
            # signal_correle = np.correlate(
            #     ChampBdes_prim, ChampB_prim, "full")
            # lags = correlation_lags(ChampBdes_prim.size, ChampB_prim.size)
            # lag = lags[np.argmax(signal_correle)]

            # # Application du lag obetnu à notre signale
            # ChampB = np.roll(ChampB,  lag)

            # Code Clémentine
            try:
                _, a = start_from_zero(ChampBdes_prim)
                _, b = start_from_zero(ChampB_prim)

                lag=b-a
            except:
                lag=0
            ChampB=np.roll(ChampB,lag)
            
            ## Fourier
            # fft_ChampBdes = fft(ChampBdes)
            # fft_ChampB = fft(ChampB)

            # # Différence de phase
            # phase_diff = np.angle(fft_ChampBdes) - np.angle(fft_ChampB)
            # ChampB = np.abs(
            #     fft_ChampB) * np.exp(1j * (np.angle(fft_ChampB) + phase_diff))
            # ChampB = ifft(ChampB).real
            
            
            # # Transformée de Hilbert
            Hilbert_ChampBdes = hilbert(ChampBdes)
            Hilbert_ChampB = hilbert(ChampB)
            phase_diff = np.angle(Hilbert_ChampBdes) - np.angle(Hilbert_ChampB)

            aligne = np.abs(
                Hilbert_ChampB) * np.exp(1j * (np.angle(Hilbert_ChampB) + phase_diff))
            ChampB = np.real(aligne)

            ChampB = savgol_filter(ChampB, window_length=10, polyorder=3, mode="wrap")

            return ChampB, lag

        def compute_convergence_criteria(dB_dt_ref_sim, dB_dt_sim, B_ref_sim, B_sim, temps_sim):
            """
            Calcul des critères convergences
            """

            # #Calcul des écarts
            delta_B = B_ref_sim - B_sim  # Vecteur de la sortie de la fonction à minimiser
            # Vecteur de la sortie de la fonction à minimiser
            delta_dB = (dB_dt_ref_sim - dB_dt_sim)/np.max(dB_dt_ref_sim)
            # Calcul de delta_V (incr�ment � ajouter au signal)
            RMSE = 100*np.sqrt(np.mean(delta_dB*delta_dB))
            FF_reel = np.sqrt(integrate.trapz(((dB_dt_sim+(1e-6))**2), temps_sim)/(max(temps_sim)-min(temps_sim))) / (
                integrate.trapz(np.abs(dB_dt_sim), temps_sim)/(max(temps_sim)-min(temps_sim)))
            FF_theo = np.sqrt(integrate.trapz((dB_dt_ref_sim**2), temps_sim)/(max(temps_sim)-min(temps_sim))) / (
                integrate.trapz(np.abs(dB_dt_ref_sim), temps_sim)/(max(temps_sim)-min(temps_sim)))
            FF = 100*np.abs(FF_reel-FF_theo)/FF_theo
            err_dB_amp = 100 * \
                np.abs((np.max(dB_dt_ref_sim)-np.max(dB_dt_sim)) /
                       np.max(dB_dt_ref_sim))
            print('fftheo=',FF_theo)
           # print('RMSE=',RMSE,'FF=',FF,'THD=',THD_dB,"err_dB=",err_dB_amp)
            return RMSE, err_dB_amp

        def trapzoid_signal(xin, width=1, slope=1, amp=1):
            u = []
            i = xin % (8*width)
            for x in i:
                if (x*slope <= amp):
                    # Ascending line
                    x = x*slope
                elif (x <= 2*width):
                    # Top horizontal line
                    x = amp
                elif (amp - (x-2*width)*slope >= 0):
                    # Descending line
                    x = amp - (x-2*width)*slope
                elif (x <= 4*width):
                    # Bottom horizontal line
                    x = 0

                elif (-(x-4*width)*slope >= -amp):
                    # Descending line
                    x = -(x-4*width)*slope
                elif (x <= 6*width):
                    # Top horizontal line
                    x = -amp
                elif ((x-6*width)*slope-amp <= 0):
                    # Ascending line
                    x = (x-6*width)*slope - amp
                elif (x <= 8*width):
                    # Bottom horizontal line
                    x = 0

                u.append(x)
            return u

        def Asservissement(Mode_asservissement, ChampBdes, ChampB, derivChampBdes, derivChampB, entree, timeC, f_0, Mat_Broyden, reinit):
            """
            Cette fonction permet l'asservissement des signaux.
            On peut utiliser la méthode du PI FFT ou Quasi Newton


            Parameters
            ----------
            Mode_asservissement : string -> choix de la méthode d'asservissement
            ChampBdes : tableaux () -> Une période 
                Signal de référence
            ChampB : tableaux () -> Une période
                Signal à synchroniser
            derivChampBdes : tableaux () -> Une période 
                Signale de référence
            derivChampB : tableaux () -> Une période
                Signal à synchroniser
            entree : tableaux () -> une période
                Signal à asservir
            timeC : tableaux () -> une période
                Tableux des temps
            f_0 : tableaux () -> mémoire de l'état précédent pour la méthode quasi Newton (initialisé à 0) 
            Mat_Broyden : tableaux () -> matrice de Broyden
            reinit : float -> variable qui permet de diminuer les gains pour converger plus rapidement

            Returns
            -------
            entree : tableau ()
                nouveau signal d'entree
            RMSE : float
                valeur RMSE de l'asservissement actuel (pour l'affichage)

           """

            global rampe, cycle, alpha, beta, gamma
            entree, lag = Synchronisation(
                derivChampBdes, entree) # synchronisation de l'entree sur le dB pour faciliter la convergence
            
            # Transformée de Fourier des signaux
            Fourier_dB_des, Fourier_dB_reel, Fourier_B_des, Fourier_B_reel, Fourier_V = compute_fft_signals(
                ChampBdes, ChampB[:samples_per_period], entree, derivChampBdes, derivChampB[:samples_per_period])
            # Calcul des critère de convergence
            RMSE, err_dB_amp = compute_convergence_criteria(
                derivChampBdes, derivChampB[:samples_per_period], ChampBdes, ChampB[:samples_per_period], timeC[:samples_per_period])

            
            if Mode_asservissement == 'PI FFT':
                # augmentation progressive des gain pour ne pas diverger lors des première itération
                rampe_alpha = np.concatenate(
                    (np.linspace(0.00001, alpha, num=rampe), alpha*np.ones(iteration_max)))
                rampe_beta = np.concatenate(
                    (np.linspace(0.00001, beta, num=rampe), beta*np.ones(iteration_max)))
                # calcul de alpha et beta lors du back Tracking (si les mesure de RMSE augmente on diminue les gains pour converger plus rapidement)
                rampe_alpha *= reinit
                rampe_beta *= reinit

                if Forme == 'Sinusoïdale B':
                    alpha_prim = 1*rampe_alpha[cycle]
                    beta_prim = 1*rampe_beta[cycle]

                if Forme == 'Triangulaire B':
                    alpha_prim = 1*rampe_alpha[cycle]
                    beta_prim = 1*rampe_beta[cycle]

                # Calcul de la nouvelle entrée en calculant l'erreur entre les courbes
                Fourier_e_k = Fourier_V + alpha_prim * (Fourier_B_des-Fourier_B_reel)/np.max(
                    Fourier_B_des) + beta_prim * (Fourier_dB_des-Fourier_dB_reel)/np.max(Fourier_dB_des)

                e_k = 0.5*len(entree)*np.fft.irfft(Fourier_e_k[0:int(
                    len(Fourier_e_k)/2)] - 1j * Fourier_e_k[int(len(Fourier_e_k)/2):]) # transformée inverse
                entree = e_k

                # mise en mémoire des paramètres pour vérifier qu'on converge toujours
                delta_B = np.max(
                    (Fourier_B_des-Fourier_B_reel) / np.max(Fourier_B_des))
                delta_dB = np.max(
                    (Fourier_dB_des-Fourier_dB_reel)/np.max(Fourier_dB_des))
                RMSE_memoire.append(RMSE)
                entree_memoire.append(entree)
                delta_B_memoire.append(delta_B)
                delta_dB_memoire.append(delta_dB)
                #algo de Back Tracking
                if Forme == 'Sinusoïdale B':
                    if (THDN(derivChampB, num_samples) > 8 or np.max(ChampB) > 1.5*Ampli or np.max(derivChampB) > np.max(derivChampBdes)*1.5 or RMSE > np.min(RMSE_memoire)) and cycle > 2:
                        # On vérifie si notre erreur diminue sinon on reprend l'ancienne entree et on diminue les gains
                        print("init")
                        indice = np.argmin(RMSE_memoire)
                        RMSE_min=RMSE_memoire[indice]
                        while len(RMSE_memoire)!=0:
                            RMSE_memoire.pop(-1)
                        RMSE_memoire.append(RMSE_min)
                        entree = entree_memoire[indice]
                        while len(entree_memoire)!=0:
                            entree_memoire.pop(-1)
                        entree_memoire.append(entree)
                        cycle = 0
                        reinit *= 0.3
                    else:
                        cycle += 1

                elif Forme == 'Triangulaire B':
                    if (THDN(derivChampB, num_samples) > 30 or np.max(ChampB) > 1.2*Ampli or np.max(derivChampB) > np.max(derivChampBdes)*1.2 or RMSE > np.min(RMSE_memoire)) and cycle > 2:
                        print("init")
                        indice = np.argmin(RMSE_memoire)
                        RMSE_min=RMSE_memoire[indice]
                        while len(RMSE_memoire)!=0:
                            RMSE_memoire.pop(-1)
                        RMSE_memoire.append(RMSE_min)
                        entree = entree_memoire[indice]
                        while len(entree_memoire)!=0:
                            entree_memoire.pop(-1)
                        entree_memoire.append(entree)
                        cycle = 0
                        reinit *= 0.3
                    else:
                        cycle += 1
            elif Mode_asservissement == 'Quasi Newton':
                

                f_n = np.concatenate(((Fourier_dB_des - Fourier_dB_reel)/np.max(Fourier_dB_des), (Fourier_B_des -
                                     Fourier_B_reel)/np.max(Fourier_B_des)))  # On sauvegarde l'écart sur la sortie f(x)
                

                Fourier_dk = - gamma * Mat_Broyden  @ (f_n) # calcul de l'erreur entre les signaux.
                # ici gamma sert à augmenter ou diminuer la vitesse de l'algorithme

                # Calcul de la nouvelle tension
                Fourier_e_k = (Fourier_V + Fourier_dk)

                # On reconvertit en temporel
                e_k = 0.5*len(entree)*np.fft.irfft(Fourier_e_k[0:int(
                    len(Fourier_e_k)/2)] - 1j * Fourier_e_k[int(len(Fourier_e_k)/2):])
                entree = e_k
                delta_f = f_n - f_0
                # Actualisation de la matrice Broyden (Bad Broyden)
                Mat_Broyden = Mat_Broyden + \
                    np.outer((Fourier_dk - Mat_Broyden @ delta_f) /
                             (LA.norm(delta_f)*LA.norm(delta_f)), delta_f.T)

                f_0 = f_n  # Pour garder en mémoire la sortie pour la prochaine itération

            
            
            print('iter=', iteration, 'Amp_V=', round(np.max(entree), 3), 'delta_B=', round(np.max((Fourier_B_des-Fourier_B_reel) /
                                                                                       np.max(Fourier_B_des)), 3), 'delta_dB=', round(np.max((Fourier_dB_des-Fourier_dB_reel)/np.max(Fourier_dB_des)), 3))
            print ('RMSE ',RMSE,'entree',entree )
          
            return entree, RMSE


        def filtre(signal_a_filtrer):
            """
            Cette fonction permet de choisir le meilleur filtre à appliquer à nos signaux


            Parameters
            ----------
            signal_a_filtrer : tableaux () -> Une période 
                Signale à filtrer


            Returns
            -------
            entree : tableau ()
                nouveau signal filtré


            """
            global fenetre_filtre,mode_filtre
            from scipy import signal


            fft_signal = fft(signal_a_filtrer)
            # recherche du fondamentale pour obtenir deux signaux simples
            fond_signal = np.zeros(len(fft_signal))
            fond_signal[np.argmax(np.abs(fft_signal))] = np.max(np.abs(fft_signal))

            # Transformée de Fourier inverse
            x1_base = 2*ifft(
                fond_signal*np.exp(1j*np.angle(fft_signal))).real # fondamental pour obtenir le signal idéale
            if np.max(x1_base)==0:
                x1_base=np.ones(len(x1_base))
            derivchampB=signal_a_filtrer

            X1 = fft(derivchampB) # transformée de Fourier du signal

            # Filtre par FFT

            # Optimisation du nombre d'harmoniques à récupérer
            optimal_harmoniques = 0
            min_RMSE = 51
            for num_harmoniques in range(1, 20):  # Tester de 1 à 20 harmoniques
                X1_harmonique = np.zeros(len(X1)) # création du vecteur qui conserve les harmonique
                index = 0
                i = 0
                while index != num_harmoniques and i < len(X1):
                    X1_harmonique[i] = np.abs(X1[i])
                    if np.abs(X1[i]) > 1:
                        index += 1
                    i += 1

                delta_dB = (x1_base - 2 * ifft(X1_harmonique * np.exp(1j * np.angle(X1))).real) / np.max(x1_base) # calcul de l'erreur entre le signal bruité et idéal
                RMSE = 100 * np.sqrt(np.mean(delta_dB * delta_dB))
                if RMSE < min_RMSE: # si on obtient une erreur plus petite on modifie le nombre d'harmonique optimal
                    min_RMSE = RMSE
                    optimal_harmoniques = num_harmoniques
            # print("Harmonique optimal : ",optimal_harmoniques)
            # Application du nombre optimal d'harmoniques
            X1_harmonique = np.zeros(len(X1))
            index = 0
            i = 0
            while index != optimal_harmoniques and i < len(X1):
                X1_harmonique[i] = np.abs(X1[i])
                if np.abs(X1[i]) > 1:
                    index += 1
                i += 1


            # Filtre savgol 

            # Recherche de la fenêtre optimale pour le filtre Savitzky-Golay
            fenetre = 51
            fenetre_opt = fenetre
            RMSE_min = 30#float('inf')
            RMSE=30
            # while fenetre <= len(x1_base):
            while RMSE>0.8*RMSE_min and RMSE<1.2*RMSE_min:

                derivchampB4 = savgol_filter(derivchampB, window_length=fenetre, polyorder=1, mode="nearest")
                delta_dB = (x1_base - derivchampB4) / np.max(x1_base)
                RMSE = 100 * np.sqrt(np.mean(delta_dB * delta_dB))
                # print(RMSE)
                # print(RMSE_min)
                if RMSE < RMSE_min:
                    RMSE_min = RMSE
                    fenetre_opt = fenetre
                fenetre += 50#2 
            derivchampB4=savgol_filter(derivchampB, window_length=fenetre_opt, polyorder=1, mode=mode_filtre)

            if np.max(np.abs(fft_signal))!=0:

                delta_dB = (x1_base - 2*ifft(X1_harmonique*np.exp(1j*np.angle(X1))).real)/np.max(x1_base)
                RMSE_FFT = 100*np.sqrt(np.mean(delta_dB*delta_dB))
                # print('RMSE FFT',RMSE_FFT)
                delta_dB = (x1_base - derivchampB4)/np.max(x1_base)
                RMSE_savgol = 100*np.sqrt(np.mean(delta_dB*delta_dB))
                # print('RMSE Savgol',RMSE_savgol)

                RMSE_tab=[RMSE_FFT,RMSE_savgol]
                if np.min(RMSE_tab)==RMSE_tab[0]:
                    # print('FFT')
                    return 2*ifft(X1_harmonique*np.exp(1j*np.angle(X1))).real
                elif np.min(RMSE_tab)==RMSE_tab[1]:
                    # print('Savgol')            
                    return derivchampB4

            else: 
                RMSE_tab=[0,0,1,0]
                if np.min(RMSE_tab)==RMSE_tab[0]:
                    # print('FFT')
                    return signal_a_filtrer
                    # return 2*ifft(X1_harmonique*np.exp(1j*np.angle(X1))).real
                elif np.min(RMSE_tab)==RMSE_tab[2]:
                    # print('Savgol')            
                    # return derivchampB4
                    return signal_a_filtrer



        def Amplificateur():
            """"
            Cette fonction permet de controler l'amplificateur depuis la fenêtre de supervision
            On se connecte à l'amplificateur grâce à la fonction Connection()
            Puis la fonction lecture permets de récupérer l'état de l'amplificateur actuel (ON/OFF ici)

            """
            Connection()


        def lecture(port_connection):
            #global limite
            ser = serial.Serial(port_connection, baudrate=9600, timeout=1)
            ser.write(bytes.fromhex("0210"))
            ready=ser.read().hex()
            ready=list("{0:08b}".format(int(ready, 16)))

            if ready[0]=='1':
                self.parent.Output_button.setStyleSheet("background-color : green")
                self.parent.Output_button.setText("ON")


            if ready[7]=='1':
                self.parent.ready_Button.setStyleSheet("background-color : green")
                self.parent.ready_Button.setText("Ready")
                self.Warnig='0'
            elif ready[6]=='1':
                self.parent.ready_Button.setStyleSheet("background-color : red")
                self.parent.ready_Button.setText("Overload")
                self.Warnig='1'
            elif ready[5]=='1':
                self.parent.ready_Button.setStyleSheet("background-color : red")
                self.parent.ready_Button.setText("Overtemp")
                self.Warnig='1'
            elif ready[3]=='1':
                self.parent.ready_Button.setStyleSheet("background-color : red")
                self.parent.ready_Button.setText("Interlock Active")
                self.Warnig='1'

            # Autre Erreur à surveiller #
            ser.write(bytes.fromhex("0242"))
            erreur=ser.read().hex()
            erreur=list("{0:08b}".format(int(erreur, 16)))
            if erreur[7]=='1':
                self.parent.ready_Button.setStyleSheet("background-color : red")
                self.parent.ready_Button.setText("Transformateur")
                self.Warnig='1'
            elif erreur[6]=='1':
                self.parent.ready_Button.setStyleSheet("background-color : red")
                self.parent.ready_Button.setText("Limite Tension")
                self.Warnig='1'
            elif erreur[4]=='1':
                self.parent.ready_Button.setStyleSheet("background-color : red")
                self.parent.ready_Button.setText("Perte de puissance dépassée")
                self.Warnig='1'
            elif erreur[3]=='1':
                self.parent.ready_Button.setStyleSheet("background-color : red")
                self.parent.ready_Button.setText("Tension trop basse")
                self.Warnig='1'
            elif erreur[2]=='1':
                self.parent.ready_Button.setStyleSheet("background-color : red")
                self.parent.ready_Button.setText("Limite Courant")
                self.Warnig='1'
            elif erreur[1]=='1':
                self.parent.ready_Button.setStyleSheet("background-color : red")
                self.parent.ready_Button.setText("Erreur Hardware")
                self.Warnig='1'
        
        
        def Connection():
            """
            Permet de se connecter à l'amplificateur
            """
                
            connect=0
            
            serial_port = serial.tools.list_ports.comports() # récupère tous les ports actifs du pc
            
            for port in serial_port: # on parcours tous les ports
                if port.device[:-1]=="/dev/ttyUSB0": # on récupère l'amplificateur branché sur le port USB
                    ser = serial.Serial(port.device, baudrate=9600,timeout=1) 
                    ser.write(bytes.fromhex("0210")) # envoie la commande pour savoir si c'est bien l'ampli (commande état de l'ampli)
                    
                    read_bytes = ser.read().hex() # lecture de la réponse de l'ampli
                    try:
                        if len(read_bytes)==2: # Si il y a un réponse on considère que le port USB est connecté à l'ampli
                            port_connection=port.device
                            lecture(port_connection)
                    except:
                        pass

            
        # Set up Variables

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

        # Selection du channel et des paramètres associés
        # Selection[i]= Channel
        # Selection[i][u] = paramètres du channel i

        bufferAMax = bufferAMin = bufferBMax = bufferBMin = bufferCMax = bufferCMin = []
        Selection_Channel = [["PS5000A_CHANNEL_A", "setChA", "setdataBuffersA", bufferAMax, bufferAMin],
                             ["PS5000A_CHANNEL_B", "setChA", "setdataBuffersB", bufferBMax, bufferBMin],
                             ["PS5000A_CHANNEL_C", "setChA", "setdataBuffersC", bufferCMax, bufferCMin]]

        iteration = 0
        # Similaire à la foncrion moyennage des oscillo traditionnels
        Nbre_enregistrement = Nbre_enregist
        Num_resolution = Resolution
        Frequence = Freq*1e3
        Amplitude = Ampli  # Amplitude désirée pour le  champ B
        N1 = Ns1
        N2 = Ns2
        Rsh = Rh
        w = Frequence*2*np.pi
        # Choix du nombre d'échantillon pour notre acquisition
        num_samples = int(num_samples)
        t = np.linspace(0, 1/int(Frequence), int(num_samples//Nbre_periode))
        num_Fourier = int(num_samples/2+2)

        Mat_Broyden = np.hstack((np.eye(num_Fourier), np.eye(num_Fourier)))*np.max(Amplitude)
        f_0 = np.zeros(num_Fourier*2)
        cycle = indice = 0
        reinit = 1
        entree_memoire = []
        delta_B_memoire = []
        delta_dB_memoire = []
        RMSE_memoire = []

          
        if Sonde=="1":
            Sonde=1
        elif Sonde=="1/10":
            Sonde=0.1
        elif Sonde=="1/100":
            Sonde=0.01

        # Création du signal désirée
        if Forme == 'Sinusoïdale B':
            ChampBdes = Amplitude*np.sin(w*t)#+Amplitude/20*np.sin(10*w*t)
            entree = 0.1*Amplitude*np.sin(w*t)

        elif Forme == 'Triangulaire B':
            # 1/2 pour éviter de dépasser la limite du GBF
            ChampBdes = Amplitude*sawtooth(w*t+np.pi/2, 0.5)
            entree = Amplitude*sawtooth(w*t+np.pi/2, 0.5)
            ChampBdes=savgol_filter(ChampBdes, window_length=300, polyorder=3, mode="mirror") # filtre pour éviter que le "pic" ne pose problème lors de l'asservissement

        elif Forme == 'Trapézoïdal B':
            ChampBdes = trapzoid_signal(w*t, np.pi/4, 0.05, Amplitude)
            entree = trapzoid_signal(w*t, np.pi/4, 0.05, Amplitude)


        # Calcule Dérivée du champ B désiré
        deriv = np.diff(ChampBdes) / np.diff(t)
        derivChampBdes = np.insert(deriv, 0, deriv[0])

        # Interpolation des signaux dans le but d'être plus fléxible sur le nombre d'échantillon
        f2 = interp1d(t, derivChampBdes)
        f3 = interp1d(t, ChampBdes)
        f1 = interp1d(t, entree)


        # try:
        # début de la boucle d'acquisition
        while True:
            # Connection à l'amplificateur
            Amplificateur()

            # Envoie du signal au GBF
            GBF(entree)
            
            # Acquisition des données
            BufferMax, cmaxSamples, timeIntervalns = Mesure(Selection_Channel, Channel_ranges)
            
            entree_nul=[]
            for i in range(len(entree)):
                entree_nul.append(0.1)
            # On éteint le GBF
            GBF(entree_nul)
            # Moyenne des Nbre_enregistrement pour lisser le signal
            adc2mVChAMax = np.mean(BufferMax[0], axis=0)
            adc2mVChBMax = np.mean(BufferMax[1], axis=0)
            adc2mVChCMax = np.mean(BufferMax[2], axis=0)*Sonde
            # Tableau contenant le nombre d'échantillon obtenu avec un pas régulier de TimeIntervalns
            timeI, interval = np.linspace(0, (cmaxSamples.value - 1) *
                                          timeIntervalns.value, cmaxSamples.value, retstep=True)

            # On récupère la plage de temps pour ne garder qu'une période
            # Récupère le première indice supérieur à la période
            samples_per_period = np.where(
                timeI > (1/(Frequence)*1e9))[0][0]-1

            # Interpolation des signaux en vu d'avoir plus de point si nécessaire
            adc2mVChAMa = interp1d(timeI, adc2mVChAMax, kind='quadratic')
            adc2mVChBMa = interp1d(timeI, adc2mVChBMax, kind='quadratic')
            adc2mVChCMa = interp1d(timeI, adc2mVChCMax, kind='quadratic')
            x = 2*num_samples

            # Diminution du nombre de point pour avoir le bon nombre de point dans une période
            while samples_per_period != num_samples//Nbre_periode:
                x -= 1
                if x==0:
                    x=2*num_samples
                timeI, interval = np.linspace(
                    0, timeI[-1], x, retstep=True)
                samples_per_period = np.where(
                    timeI > (1/(Frequence)*1e9))[0][0]-1

            samples_per_period = np.where(
                timeI > (1/(Frequence)*1e9))[0][0]-1

            # # recalcule des signaux avec la nouvelle base de temps
            adc2mVChAMax = adc2mVChAMa(timeI)
            adc2mVChBMax = adc2mVChBMa(timeI)
            adc2mVChCMax = adc2mVChCMa(timeI)

            V2=adc2mVChCMax # variable qui permet d'analyser le bruit de la tension au secondaire

            
            # adc2mVChCMax = savgol_filter(adc2mVChCMax, window_length=fenetre_filtre, polyorder=3, mode= mode_filtre)
            adc2mVChCMax = filtre(adc2mVChCMax)
            
            
            # Détection Bornes homologues
            adc2mVChBMax, adc2mVChCMax = Detection_Bornes(
                adc2mVChAMax, adc2mVChBMax, adc2mVChCMax)

            # # Détermination de la composante continue
            MoyenneA = (np.max(adc2mVChAMax)+np.min(adc2mVChAMax))/2
            MoyenneB = (np.max(adc2mVChBMax)+np.min(adc2mVChBMax))/2
            MoyenneC = (np.max(adc2mVChCMax)+np.min(adc2mVChCMax))/2

            # Détermination de la composante continue
            MoyenneA = 0
            MoyenneB = 0
            MoyenneC = 0


            # Mise en forme des données pour n'avoir qu'une période
            dataA = np.zeros(num_samples)
            dataA = adc2mVChAMax - MoyenneA
            samples_to_plotA = dataA[:Nbre_periode *
                                     samples_per_period]+MoyenneA

            dataB = np.zeros(num_samples)
            dataB = adc2mVChBMax - MoyenneB
            samples_to_plotB = dataB[:Nbre_periode *
                                     samples_per_period]+MoyenneB

            dataC = np.zeros(num_samples)
            dataC = adc2mVChCMax - MoyenneC
            samples_to_plotC = dataC[:Nbre_periode *
                                     samples_per_period]+MoyenneC

            # Deuxieme tableaux pour avoir l'axe des temps
            #timeC = np.arange(np.array(samples_to_plotC).shape[0]) * timeIntervalns.value/1e9
            timeC = np.arange(
                np.array(samples_to_plotC).shape[0]) * (1/Frequence/samples_per_period)

            # Calcul du champ B
            # Supression de la composante continue
            samples_to_plotC = samples_to_plotC - np.mean(samples_to_plotC)
            integral = integrate.cumtrapz(
                (samples_to_plotC)/1000, timeC, initial=0)

            # récupération de la fonction interpolée f2 calculé en début de PRGM,
            # On adapte notre dérivée à l'axe des temps
            derivChampBdes = f2(timeC[:samples_per_period])
            ChampBdes = f3(timeC[:samples_per_period])
          #  plt.plot(timeC[:samples_per_period], ChampBdes, '-')
            #plt.show()
            
            # Supression de la composante continue 
            Maxi = np.max(integral)
            Mini = np.min(integral)
            #integral_corrige = integral-((Mini+Maxi)/2)
            integral_corrige = integral-np.mean(integral)
            ChampB = integral_corrige/(-N2*Section*1e-6)
            print("champB=")
            # Affichage ligne par ligne
            for val in ChampB:
                  print(val)
            derivChampB = samples_to_plotC / (-N2*Section*1e-6*1000)  # Sample_to_Plot_C = U2
            
            #Calcul du courant au primaire
            # Divisé par 1000 pour transformer les miliVolt en volt
            ih = samples_to_plotB/(Rsh*1000)
            
            ChampH2 = N1*ih/(lm*1e-3)

            # On conserve nos signaux car ils pourront être modifié par la suite
            derivChampB_tempo=derivChampB
            ChampB_tempo=ChampB

            # Synchro des signaux
            ChampB, lag = Synchronisation(
                ChampBdes, ChampB[:samples_per_period])
           
            derivChampB, lag1 = Synchronisation(
                derivChampBdes, derivChampB[:samples_per_period])
      
            # filtrage du champ H
            ChampH2 = savgol_filter(ChampH2, window_length=fenetre_filtre, polyorder=3, mode= mode_filtre)
            ChampH2 = detrend(ChampH2, type='constant')

            # Affichage Courbes
            self.parent.main_window.timeC = timeC[:samples_per_period]
            unite_T = "s"
            if timeC[samples_per_period] < 1e-6:
                unite_T = "ns"
                timeC= timeC*1e9
            elif timeC[samples_per_period] < 1e-3:
                unite_T = "µs"
                timeC = timeC*1e6
            elif timeC[samples_per_period] < 1:
                unite_T = "ms"
                timeC = timeC*1e3
            self.parent.widget_1.canvas.ax.cla()
            self.parent.widget_2.canvas.ax.cla()
            self.parent.widget_3.canvas.ax.cla()
            self.parent.widget_4.canvas.ax.cla()
            self.parent.widget_2.canvas.ax.plot(
                timeC[:samples_per_period], ChampBdes, label="B desiré", color='r', linestyle='--')
            self.parent.widget_3.canvas.ax.plot(
                timeC[:samples_per_period], derivChampBdes*(-N2*Section*1e-6), label="V2 desiré", color='r', linestyle='--')
            line1, = self.parent.widget_1.canvas.ax.plot(
                timeC[:samples_per_period], entree, label="eₖ")
            # line1, = self.parent.widget_1.canvas.ax.plot(
            #     timeC[:samples_per_period], samples_to_plotA[:samples_per_period], label="eₖ")
            line2, = self.parent.widget_2.canvas.ax.plot(
                timeC[:samples_per_period], ChampB[:samples_per_period], label="Bₖ")
            line3, = self.parent.widget_3.canvas.ax.plot(
                timeC[:samples_per_period], derivChampB[:samples_per_period]*(-N2*Section*1e-6), label="V2")
            line4, = self.parent.widget_4.canvas.ax.plot(
                timeC[:samples_per_period], ChampH2[:samples_per_period], label="Hₖ")
            self.parent.widget_1.canvas.ax.set_ylabel("Volts", rotation=0)
            self.parent.widget_1.canvas.ax.yaxis.set_label_coords(0, 1)
            self.parent.widget_2.canvas.ax.set_ylabel("T", rotation=0)
            self.parent.widget_2.canvas.ax.yaxis.set_label_coords(0, 1)
            self.parent.widget_3.canvas.ax.set_ylabel("V", rotation=0)
            self.parent.widget_3.canvas.ax.yaxis.set_label_coords(0, 1)
            self.parent.widget_4.canvas.ax.set_ylabel("A/m", rotation=0)
            self.parent.widget_4.canvas.ax.yaxis.set_label_coords(0, 1)
            self.parent.widget_1.canvas.ax.set_xlabel(unite_T)
            self.parent.widget_1.canvas.ax.xaxis.set_label_coords(
                1.05, -0.025)
            self.parent.widget_2.canvas.ax.set_xlabel(unite_T)
            self.parent.widget_2.canvas.ax.xaxis.set_label_coords(
                1.05, -0.025)
            self.parent.widget_3.canvas.ax.set_xlabel(unite_T)
            self.parent.widget_3.canvas.ax.xaxis.set_label_coords(
                1.05, -0.025)
            self.parent.widget_4.canvas.ax.set_xlabel(unite_T)
            self.parent.widget_4.canvas.ax.xaxis.set_label_coords(
                1.05, -0.025)
            self.parent.widget_1.canvas.ax.legend()
            self.parent.widget_2.canvas.ax.legend()
            self.parent.widget_3.canvas.ax.legend()
            self.parent.widget_4.canvas.ax.legend()
            self.parent.widget_1.canvas.draw()
            self.parent.widget_2.canvas.draw()
            self.parent.widget_3.canvas.draw()
            self.parent.widget_4.canvas.draw()
            

            # Calcule de la nouvelle entrée après la vérification des conditions de fin pour avoir
            # l'entrée de la convergence et pas la suivante
            entree_tempo, RMSE = Asservissement(Mode_asservissement, ChampBdes, ChampB[:samples_per_period], derivChampBdes, derivChampB[
                                          :samples_per_period], entree, timeC[:samples_per_period], f_0, Mat_Broyden, reinit)

            entree_tempo = filtre(entree_tempo)
            # entree_tempo = savgol_filter(
            #     entree_tempo, window_length=100, polyorder=3, mode="mirror")

            # Affichage des infos sur la fenêtre de supervision
            self.parent.iteration_label.setText(
                "Itération n⁰"+str(iteration))
            self.parent.Courant_label.setText(
                "Imax: "+str(round(np.max(ih)*1000))+" mA")
            self.parent.Brefmax_value.setText(
                str(round(np.max(ChampBdes), 3)))
            self.parent.Bkmax_value.setText(str(round(np.max(ChampB), 3)))
            self.parent.FF_value.setText(
                str(round(FF(derivChampB, timeC[samples_per_period]), 2)))
            self.parent.THD_value.setText(
                str(round(THDN(derivChampB, num_samples), 2))+" %")
            self.parent.RMSE_value.setText(str(round(RMSE, 2))+" %")
            self.parent.Hmax_value.setText(str(round(np.max(ChampH2), 2)))
            self.parent.Imax_value.setText(str(round(np.max(ih), 2)))
            # if iteration == 10:
            if (THDN(derivChampB, num_samples) < THDN(derivChampBdes, num_samples)+2):
                self.parent.THD_value.setStyleSheet("color: green;")
            else:
                self.parent.THD_value.setStyleSheet("color: black;")
            # if (Amplitude < (np.max(ChampB)*1.005)) & (Amplitude > (np.max(ChampB)*0.995)):
            #     self.parent.Bkmax_value.setStyleSheet("color: green;")
            if (Amplitude*0.995 < (np.max(np.abs(ChampB)))) & (Amplitude*1.005 > (np.max(np.abs(ChampB)))):
                self.parent.Bkmax_value.setStyleSheet("color: green;")
            else:
                self.parent.Bkmax_value.setStyleSheet("color: black;")
            if (FF(derivChampB, timeC[samples_per_period]) < FF(derivChampBdes, timeC[samples_per_period])*1.01) & (FF(derivChampB, timeC[samples_per_period]) > FF(derivChampBdes, timeC[samples_per_period])*0.99):
                self.parent.FF_value.setStyleSheet("color: green;")
            else:
                self.parent.FF_value.setStyleSheet("color: black;")
            self.parent.iteration_label.setStyleSheet("color: black;")
            
            # On vérifie les critère de convergence
            if ((Amplitude*1.005 > (np.max(np.abs(ChampB)))) & (Amplitude*0.995 < (np.max(np.abs(ChampB)))) & (THDN(derivChampB, num_samples) < THDN(derivChampBdes, num_samples)+3) & ((FF(derivChampB, timeC[samples_per_period]) < FF(derivChampBdes, timeC[samples_per_period])*1.01) & (FF(derivChampB, timeC[samples_per_period]) > FF(derivChampBdes, timeC[samples_per_period])*0.99))) or iteration == iteration_max or self.parent.stop == True:
                
                ChampB=ChampB_tempo
                derivChampB=derivChampB_tempo

                self.parent.stop == False
                self.parent.stop_button.setEnabled(True)
                self.parent.iteration_label.setStyleSheet("color: red;")
                break
            iteration += 1

            entree=entree_tempo
            # Retour au début de la boucle

        # Résulats de mesures (calcule des pertes)
        
        ChampB_nul = np.where(np.diff(np.sign(ChampB)))[0]
        Hcs = []
        for valeur in ChampB_nul:
            Hcs.append(np.abs(ChampH2[valeur]))
        Hc = np.mean(Hcs) # Calcul du champ coercitif
        ChampH2_nul = np.where(np.diff(np.sign(ChampH2)))[0]
        Brs = []
        for valeur in ChampH2_nul[:2]:
            Brs.append(np.abs(ChampB[valeur]))
        Br = np.mean(Brs) # calcul du champ rémanant

        Pv = np.trapz(ChampH2[:samples_per_period] * derivChampB[:samples_per_period],
                      x=timeC[:samples_per_period]) / (timeC[samples_per_period])

        if Pv<0 : # dans le cas de faible signaux, on peut avoir le mauvais déphasage (déphasé de pi). 
            ChampB=np.negative(ChampB)
            Pv*=-1
        
        mu_r = max(ChampB)/(max(ChampH2)*4e-7*np.pi) # calcul perméabilité

                    
        # derivChampB=derivChampB_tempo
        # ChampB=ChampB_tempo
        # ChampH2=ChampH2_tempo

        # enregistrement des signaux pour débugger

        # with open('/home/caracterisation/Documents/Stage Evan Gossard/entree.npy', 'wb') as f:
        #     np.save(f, entree)
        # with open('/home/caracterisation/Documents/Stage Evan Gossard/V2.npy', 'wb') as f:
        #     np.save(f, V2[:samples_per_period])
        # with open('/home/caracterisation/Documents/Stage Evan Gossard/time.npy', 'wb') as f:
        #     np.save(f, timeC[:samples_per_period])
        # with open('/home/caracterisation/Documents/Stage Evan Gossard/champB.npy', 'wb') as f:
        #     np.save(f, ChampB[:samples_per_period])
        # with open('/home/caracterisation/Documents/Stage Evan Gossard/derivchampB.npy', 'wb') as f:
        #     np.save(f, derivChampB[:samples_per_period])
        # with open('/home/caracterisation/Documents/Stage Evan Gossard/champH.npy', 'wb') as f:
        #     np.save(f, ChampH2[:samples_per_period])
        # with open('/home/caracterisation/Documents/Stage Evan Gossard/V2_filtre.npy', 'wb') as f:
        #     np.save(f, adc2mVChCMax[:samples_per_period])
        # with open('/home/caracterisation/Documents/Stage Evan Gossard/entree.npy', 'wb') as f:
        #     np.save(f, 10*entree[:samples_per_period])

        # enregistrement des signaux pour l'affichage des résultats
        self.parent.ChampH = ChampH2[:samples_per_period]
        self.parent.main_window.ChampH = ChampH2[:samples_per_period]
        self.parent.ChampB = ChampB[:samples_per_period]
        self.parent.main_window.ChampB = ChampB[:samples_per_period]
        self.parent.main_window.derivChampB = derivChampB[:samples_per_period]
        
        self.parent.main_window.update_mesures(
            np.max(ChampB), Frequence, Hc, Br, np.max(ChampH2), mu_r, Pv)
        self.finished.emit() # fin du thread de supervision

        # except Exception as e:
        #     print('erreur : ', e)
        #     Erreur.append(str(e))
            
        #     self.parent.ChampH = np.zeros(num_samples)
        #     self.parent.main_window.ChampH = np.zeros(num_samples)
        #     self.parent.ChampB = np.zeros(num_samples)
        #     self.parent.main_window.ChampB = np.zeros(num_samples)
        #     self.parent.main_window.derivChampB = np.zeros(num_samples)
        #     self.parent.main_window.update_mesures(1, 1, 1, 1, 1, 1, 1)
        #     self.finished.emit()
        #     #self.parent.main_window.Error()



class ConfigWindow(QDialog, Ui_Dialog):
    def __init__(self, *args, parent=None, **kwargs):
        super(ConfigWindow, self).__init__(*args, **kwargs)
        global Freq_tab,ampli_freq, Mode_asservissement,Sonde
        self.setupUi(self)

        self.setWindowTitle("Configuration") # nom de la fenêtre
        # self._connectActions() # connect les boutonds
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
            self.De_spin.setDecimals(3)
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
        self.Kf_spin.setValue(Kf)
        self.Nm_ref_edit.setText(Nm_ref)
        self.Mu_spin.setValue(mu_r)
        self._connectActions() # connect les boutonds
        self.lm_spin.setValue(lm)
        self.outils_combo.currentTextChanged.connect(self.selectionchange)
        self.section_spin.valueChanged.connect(self.calcul_kf)
        self.Kf_spin.valueChanged.connect(self.calcul_section)
        self.De_spin.valueChanged.connect(self.calcul_longueur)
        
        self.Asservissement_Combo.setCurrentText(Mode_asservissement)
        self.Sonde_Combo.setCurrentText(str(Sonde))
        
        #Radio
        self.Radio_Simple.toggled.connect(lambda: self.Mode_Mesure("Simple"))
        self.Radio_Auto.toggled.connect(lambda: self.Mode_Mesure("Auto"))
        
        self.Radio_Lineaire.toggled.connect(lambda: self.Choix_Mesure("Linéaire"))
        self.Radio_Utilisateur.toggled.connect(lambda: self.Choix_Mesure("Utilisateur"))

        #Spin Linéaire
        self.Freq_Spin_depart.setValue(Freq_depart)
        self.Freq_Spin_fin.setValue(Freq_fin)
        self.Freq_Spin_pt.setValue(Freq_pt)

        self.Ampli_Spin_depart.setValue(Ampli_fin)
        self.Ampli_Spin_fin.setValue(Ampli_fin)
        self.Ampli_Spin_pt.setValue(Ampli_pt)

        
               
        #Spin Freq + Spin Amplitude
        self.Freq_Spin_1.setValue(Freq_1)
        self.Freq_Spin_2.setValue(Freq_2)    
        self.Freq_Spin_3.setValue(Freq_3)
        self.Freq_Spin_4.setValue(Freq_4)
        self.Freq_Spin_5.setValue(Freq_5)
        self.Freq_Spin_6.setValue(Freq_6)
        self.Freq_Spin_7.setValue(Freq_7)
        self.Freq_Spin_8.setValue(Freq_8)
        self.Freq_Spin_9.setValue(Freq_9)
        self.Freq_Spin_10.setValue(Freq_10)
        
        self.Ampli_Spin_1.setValue(Ampli_1)
        self.Ampli_Spin_2.setValue(Ampli_2)
        self.Ampli_Spin_3.setValue(Ampli_3)
        self.Ampli_Spin_4.setValue(Ampli_4)
        self.Ampli_Spin_5.setValue(Ampli_5)
        self.Ampli_Spin_6.setValue(Ampli_6)
        self.Ampli_Spin_7.setValue(Ampli_7)
        self.Ampli_Spin_8.setValue(Ampli_8)
        self.Ampli_Spin_9.setValue(Ampli_9)
        self.Ampli_Spin_10.setValue(Ampli_10)
        
    def _connectActions(self):
        # Connect File actions
        self.actionImport_Sequence.triggered.connect(self.import_sequence)
        self.Ns1_spin.valueChanged.connect(self.Calcul_R_N1)
        self.section_spin.valueChanged.connect(self.Calcul_R_N1)
        self.lm_spin.valueChanged.connect(self.Calcul_R_N1)
        self.freq_spin.valueChanged.connect(self.Calcul_R_N1)
        self.Ampli_spin.valueChanged.connect(self.Calcul_R_N1)
        self.Mu_spin.valueChanged.connect(self.Calcul_R_N1)
        self.Rs_spin.valueChanged.connect(self.Calcul_R_N1)
        
    def Calcul_R_N1(self): 
        #global mu_r,Ampli,Ns1,Section,Freq,lm,Rs
        Ampli = self.Ampli_spin.value()
        Ns1 = self.Ns1_spin.value()
        Section = self.section_spin.value()
        Freq = self.freq_spin.value()
        lm = self.lm_spin.value()
        Rs = self.Rs_spin.value()
        mu_r = self.Mu_spin.value()
        H=Ampli/(mu_r*4*np.pi*1e-7)
        Imax=H*lm*1e-3/Ns1

        if H!=0 and Imax!=0 and Ns1!=0:
            
            #Calcule N1
            H=Ampli/(mu_r*4*np.pi*1e-7)
            w=2*np.pi*Freq*1e3
            N1=Ns1
            Imax=H*lm*1e-3/N1
            Imax_des=0.12

            while H*lm*1e-3/N1<0.9*Imax_des or H*lm*1e-3/N1>1.1*Imax_des:
                e=(Imax_des-(H*lm*1e-3/N1))/Imax_des
                N1=N1-0.5*e
                Imax=H*lm*1e-3/N1

            N1=int(N1)
            Rmax=round(N1*N1*Section*1e-6*Ampli*w/(H*lm*1e-3),2)
            self.R_label.setText(str(Rmax))

            V1max=N1*Section*1e-6*w*Ampli+Rmax*Imax
            
            while N1*Section*1e-6*w*Ampli<0.6*V1max:
                V1max=N1*Section*1e-6*w*Ampli+Rmax*Imax
                e=(0.7*V1max-(N1*Section*1e-6*w*Ampli))
                Rmax=Rmax-0.5*e

            self.R_label.setText(str(round(Rmax)))
            Rmax=round(Rmax)
            if Rmax==0:
                self.R_label.setText("< 1 " )

            V1max=N1*Section*1e-6*w*Ampli+Rmax*Imax
            
            self.N1_label.setText(str(N1))


    def import_sequence(self):
        global Freq_tab,Ampli_tab,Freq_tab_tempo 
        
        config_path, _ = QFileDialog.getOpenFileName(
            self, 'Load sequence', '', 'Config Files (*.cfg)')
        if not config_path:
            return

        # create a QSettings object with the given configuration file path
        settings = QSettings(config_path, QSettings.IniFormat)

        Freq_tab_var = settings.value("Frequence", 0).split("/")
        Freq_tab_var=Freq_tab_var[1:]
        Ampli_tab_tempo = settings.value("Amplitude", 0).split("/")
        Ampli_tab_tempo=Ampli_tab_tempo[1:]
        Ampli_tab = [float(i) for i in Ampli_tab_tempo]

        Freq_tab = [float(i) for i in Freq_tab_var]
        Freq_tab_tempo=[float(i) for i in Freq_tab_var]
        
    def Mode_Mesure(self, option):
        global Mode_Auto
        if  self.Radio_Simple.isChecked()==True:
            Mode_Auto="Simple"
        elif self.Radio_Auto.isChecked()==True:
            Mode_Auto="Auto"
    
    def Choix_Mesure(self, option):
        global Mode_Lineaire
        if  self.Radio_Lineaire.isChecked()==True:
            Mode_Lineaire="Linéaire"
        elif self.Radio_Utilisateur.isChecked()==True:
            Mode_Lineaire="Utilisateur"



    def selectionchange(self, var):
        global Outils
        Outils = var
        if (Outils == "Cadre Epstein personnalisé") or (Outils == "Cadre Epstein Standard"):
            self.Hauteur_label.setText("Epaisseur")
            self.Di_label.setText("Largeur")
            self.De_label.setText("Nbre de Bandes")
            self.Ns1_spin.setValue(700)
            self.Ns2_spin.setValue(700)
            self.Di_spin.setValue(30)
            self.lm_spin.setValue(0.94)
            self.De_spin.setDecimals(0)
            self.De_unite.setVisible(False)
        else:
            self.Hauteur_label.setText("Hauteur")
            self.Di_label.setText("Diamètre intérieur Di")
            self.De_label.setText("Diamètre extérieur De")
            self.De_spin.setDecimals(3)
            self.De_unite.setVisible(True)

    def calcul_kf(self, var):
        self.Kf_spin.valueChanged.disconnect()
        Di = self.Di_spin.value()
        De = self.De_spin.value()
        Hauteur = self.Hauteur_spin.value()
        if Di != 0 and De != 0 and Hauteur != 0:
            Stheo = Hauteur*1e-3*(De*1e-3-Di*1e-3)/2
            Kf = var*1e-6/Stheo
            self.Kf_spin.setValue(Kf)
        self.Kf_spin.valueChanged.connect(self.calcul_section)

    def calcul_section(self, var):
        self.section_spin.valueChanged.disconnect()
        Di = self.Di_spin.value()
        De = self.De_spin.value()
        Hauteur = self.Hauteur_spin.value()
        if Di != 0 and De != 0 and Hauteur != 0:
            Stheo = Hauteur*1e-3*((De*(1e-3))-(Di*(1e-3)))/2
            Section = var*Stheo*1e6
            self.section_spin.setValue(Section)
           
        self.section_spin.valueChanged.connect(self.calcul_kf)

    def calcul_longueur(self, var):
        # self.lm_spin.valueChanged.disconnect()
        Di = self.Di_spin.value()
        De = self.De_spin.value()
        if Di != 0 and De != 0:
            lm = np.pi*(De-Di)/(np.log(De/Di))
            self.lm_spin.setValue(lm)

    def accept(self):
        global Materiaux, Hauteur, mu_0, Di, De, Section, alpha, beta, Outils, Ns1, Ns2, Rs, Rh, Type, Forme, Freq, Ampli, Gain, Nbre_periode, Kf, Nm_ref, mu_r, lm, num_samples
        global Freq_1,Freq_2,Freq_3,Freq_4,Freq_5,Freq_6,Freq_7,Freq_8,Freq_9,Freq_10
        global Ampli_1,Ampli_2,Ampli_3,Ampli_4,Ampli_5,Ampli_6,Ampli_7,Ampli_8,Ampli_9,Ampli_10
        global Freq_depart,Freq_fin,Ampli_depart,Ampli_fin,Mode_Lineaire,Mode_Auto,Freq_tab,Ampli_tab,Freq_tab_tempo,Freq_pt,Ampli_pt
        global Mode_asservissement,Mode__Auto, Sonde
        
        Materiaux = self.Materiaux_combo.currentText()
        Hauteur = self.Hauteur_spin.value()
        Di = self.Di_spin.value()
        De = self.De_spin.value()
        Section = self.section_spin.value()    ##################################################################
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
        mu_r = self.Mu_spin.value()
        lm = self.lm_spin.value()
        if Section == 0:
           Section = (Hauteur*1e-3*((De*(1e-3))-(Di*(1e-3)))/2)*1e6
           Section = round(Section)
           #Section = De*Di*Hauteur*Kf
        Mode_asservissement=self.Asservissement_Combo.currentText()
        Sonde=self.Sonde_Combo.currentText()
        
        Freq_depart=self.Freq_Spin_depart.value()
        Freq_fin=self.Freq_Spin_fin.value()

        Ampli_depart=self.Ampli_Spin_depart.value()
        Ampli_fin=self.Ampli_Spin_fin.value()
        
        Freq_1=self.Freq_Spin_1.value()
        Freq_2=self.Freq_Spin_2.value()   
        Freq_3=self.Freq_Spin_3.value()   
        Freq_4=self.Freq_Spin_4.value()   
        Freq_5=self.Freq_Spin_5.value()   
        Freq_6=self.Freq_Spin_6.value()   
        Freq_7=self.Freq_Spin_7.value()   
        Freq_8=self.Freq_Spin_8.value()   
        Freq_9=self.Freq_Spin_9.value()   
        Freq_10=self.Freq_Spin_10.value()  
        
        Ampli_1=self.Ampli_Spin_1.value()
        Ampli_2=self.Ampli_Spin_2.value()
        Ampli_3=self.Ampli_Spin_3.value()
        Ampli_4=self.Ampli_Spin_4.value()
        Ampli_5=self.Ampli_Spin_5.value()
        Ampli_6=self.Ampli_Spin_6.value()
        Ampli_7=self.Ampli_Spin_7.value()
        Ampli_8=self.Ampli_Spin_8.value()
        Ampli_9=self.Ampli_Spin_9.value()
        Ampli_10=self.Ampli_Spin_10.value()
        
        if Mode_Lineaire=="Utilisateur" and Mode_Auto=="Auto":
            Freq_tab=[Freq_1,Freq_2,Freq_3,Freq_4,Freq_5,Freq_6,Freq_7,Freq_8,Freq_9,Freq_10]
            Freq_tab_tempo=[Freq_1,Freq_2,Freq_3,Freq_4,Freq_5,Freq_6,Freq_7,Freq_8,Freq_9,Freq_10]
            Ampli_tab=[Ampli_1,Ampli_2,Ampli_3,Ampli_4,Ampli_5,Ampli_6,Ampli_7,Ampli_8,Ampli_9,Ampli_10]
            
            try:
                while(True):
                    Freq_tab.remove(0)
                    Freq_tab_tempo.remove(0)
            except:
                pass
            try:
                while(True):
                    Ampli_tab.remove(0)
            except:
                pass
        elif Mode_Lineaire=="Linéaire" and Mode_Auto=="Auto":
            Freq_pt=self.Freq_Spin_pt.value()
            Ampli_pt=self.Ampli_Spin_pt.value()
            Freq_tab=list(np.linspace(Freq_depart,Freq_fin,Freq_pt))
            Freq_tab_tempo=list(np.linspace(Freq_depart,Freq_fin,Freq_pt))
            Ampli_tab=list(np.linspace(Ampli_depart,Ampli_fin,Ampli_pt))
                        
            
        main_window = self.parent()
        #alpha = ((Rs+Rh)*lm*1e-3/(mu_r*mu_0*Ns1))
        #beta = (Ns1*Section*(1e-6))
        main_window.update_data(Outils, Materiaux, Di,
                                De, Hauteur, Section, lm, Kf)
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


class Temperature_Ampli(QObject):
    finished=pyqtSignal()
    # progress= pyqtSignal(int)
    def __init__(self,n,port):
        super().__init__()
        self.n = n
        self.port=port
        
    def run(self):
        for i in range(1):
            time.sleep(5)
            ser = serial.Serial(self.port, baudrate=9600)
            ser.write(bytes.fromhex("0204"))
            temp=ser.read()[-1]
            self.n.setText(str(temp)+" °C")

            
        self.finished.emit()
    
    
class AmpliWindow(QDialog, Ui_Ampli):
    def __init__(self, main_window, *args, obj=None, **kwargs):
        super(AmpliWindow, self).__init__(*args, **kwargs)
        global Temperature_flag,limite
        self.setupUi(self)
        self.port_connection=''
        self.Connection_Button.clicked.connect(self.Connection)
        self.Warnig='0'
        self.Connection()
        
        
        
        
    def _connectAction(self):  
        global Temperature_flag
        self.Mode_Button.clicked.connect(self.Mode)
        self.Limite_Button.clicked.connect(self.Limite)
        self.Courant_Button.clicked.connect(self.Courant_Range)
        self.Amplifier_Button.clicked.connect(self.Output)
        self.defaut_Button.clicked.connect(self.defaut)
    
        self.Sensing_comboBox.activated.connect(self.Sensing)
        self.Network_comboBox.activated.connect(self.Network)

        self.group = QButtonGroup()
        self.group.setExclusive(True)  # Radio buttons are not exclusive
        self.group.buttonPressed.connect(self.check_buttons)   
        self.plus_h=0
        self.plus_m=0
        self.ps_p_h_radioButton.toggled.connect(lambda: self.Power_Supply_plus(self.ps_p_h_radioButton))
        self.ps_p_m_radioButton.toggled.connect(lambda: self.Power_Supply_plus(self.ps_p_m_radioButton))
        self.group.addButton(self.ps_p_h_radioButton)
        self.group.addButton(self.ps_p_m_radioButton)
        self.group.addButton(self.ps_p_tempo)

        
        self.group2 = QButtonGroup()
        self.group2.setExclusive(True)  # Radio buttons are not exclusive
        self.group2.buttonPressed.connect(self.check_buttons2)
        self.moins_h=0
        self.moins_m=0
        self.ps_m_h_radioButton.toggled.connect(lambda: self.Power_Supply_moins())
        self.ps_m_m_radioButton.toggled.connect(lambda: self.Power_Supply_moins())
        self.group2.addButton(self.ps_m_h_radioButton)
        self.group2.addButton(self.ps_m_m_radioButton)
        self.group2.addButton(self.ps_m_tempo)
        self.lecture()
        

        self.Limite_spinBox.valueChanged.connect(lambda: self.spin_method()) 
        
        # self.pool = QThreadPool.globalInstance()
        # temp=Temperature_Ampli(self.Temp_label)
        # self.pool.start(temp)
        Temperature_flag=1
        # Step 2: Create a QThread object
        self.thread = QThread()
        # Step 3: Create a worker object
        self.worker = Temperature_Ampli(self.Temp_label,self.port_connection)
        # Step 4: Move worker to the thread
        self.worker.moveToThread(self.thread)
        # Step 5: Connect signals and slots
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        #self.worker.finished.connect(self.deleteLater)
        self.worker.finished.connect(self.finished_temp)
        
        self.thread.start()


    def defaut(self):
        self.w=Ampli_defaut_Window(self)
        self.w.show()


    def check_buttons(self, radioButton):
    # Uncheck every other button in this group
        # for button in self.group.buttons():
        #     if button is not radioButton:
        #         button.setChecked(True)
        if radioButton.isChecked():
            self.group.setExclusive(False)
            self.ps_p_tempo.setChecked(True)
            self.group.setExclusive(True)


    def check_buttons2(self, radioButton):
    # Uncheck every other button in this group
        # for button in self.group.buttons():
        #     if button is not radioButton:
        #         button.setChecked(True)
        if radioButton.isChecked():
            self.group2.setExclusive(False)
            self.ps_m_tempo.setChecked(True)
            self.group2.setExclusive(True)

        
    def spin_method(self):
        global limite
        
        limite=int(self.Limite_spinBox.value()*4095/100)

        limite_hex=format(limite,'04x')
        ser = serial.Serial(self.port_connection, baudrate=9600)
        ser.write(bytes.fromhex("042D"+limite_hex))

    def Connection(self):
        serial_port = serial.tools.list_ports.comports()

        connect=0
        
        serial_port = serial.tools.list_ports.comports()
        
        for port in serial_port:
            print(f"{port.name} // {port.device} // D={port.description}")
            #if ser.read():
            if port.device[:-1]=="/dev/ttyUSB":
                ser = serial.Serial(port.device, baudrate=9600,timeout=1)
                ser.write(bytes.fromhex("0210"))
                
                read_bytes = ser.read().hex()
                try:
                    if len(read_bytes)==2:
                        self.port_connection=port.device
                        print("Ampli connecté")
                        connect=1
                        self._connectAction()
                except:
                    pass
    
    
    def lecture(self):
        #global limite
        ser = serial.Serial(self.port_connection, baudrate=9600, timeout=1)


        ser.write(bytes.fromhex("0210"))
        ready=ser.read().hex()
        ready=list("{0:08b}".format(int(ready, 16)))

        if ready[0]=='1':
            self.Amplifier_Button.setStyleSheet("background-color : green")
            self.Amplifier_Button.setText("ON")

        if ready[7]=='1':
            self.ready_Button.setStyleSheet("background-color : green")
            self.ready_Button.setText("Ready")
            self.Warnig='0'
        elif ready[6]=='1':
            self.ready_Button.setStyleSheet("background-color : red")
            self.ready_Button.setText("Overload")
            self.Warnig='1'
        elif ready[5]=='1':
            self.ready_Button.setStyleSheet("background-color : red")
            self.ready_Button.setText("Overtemp")
            self.Warnig='1'
        elif ready[3]=='1':
            self.ready_Button.setStyleSheet("background-color : red")
            self.ready_Button.setText("Interlock Active")
            self.Warnig='1'

        # Autre Erreur à surveiller #
        ser.write(bytes.fromhex("0242"))
        erreur=ser.read().hex()
        erreur=list("{0:08b}".format(int(erreur, 16)))
        if erreur[7]=='1':
            self.ready_Button.setStyleSheet("background-color : red")
            self.ready_Button.setText("Transformateur")
            self.Warnig='1'
        elif erreur[6]=='1':
            self.ready_Button.setStyleSheet("background-color : red")
            self.ready_Button.setText("Limite Tension")
            self.Warnig='1'
        elif erreur[4]=='1':
            self.ready_Button.setStyleSheet("background-color : red")
            self.ready_Button.setText("Perte de puissance dépassée")
            self.Warnig='1'
        elif erreur[3]=='1':
            self.ready_Button.setStyleSheet("background-color : red")
            self.ready_Button.setText("Tension trop basse")
            self.Warnig='1'
        elif erreur[2]=='1':
            self.ready_Button.setStyleSheet("background-color : red")
            self.ready_Button.setText("Limite Courant")
            self.Warnig='1'
        elif erreur[1]=='1':
            self.ready_Button.setStyleSheet("background-color : red")
            self.ready_Button.setText("Erreur Hardware")
            self.Warnig='1'

        if self.Warnig=='1':
            print('erreur')
            self.Mode_Button.setEnabled(False)
            self.Limite_Button.setEnabled(False)
            self.Courant_Button.setEnabled(False)
            self.Amplifier_Button.setEnabled(False)
            self.defaut_Button.setEnabled(False)
            self.Sensing_comboBox.setEnabled(False)
            self.Network_comboBox.setEnabled(False)
            self.ps_p_h_radioButton.setEnabled(False)
            self.ps_p_m_radioButton.setEnabled(False)
            self.ps_m_h_radioButton.setEnabled(False)
            self.ps_m_m_radioButton.setEnabled(False)
            self.Limite_spinBox.setEnabled(False)
        else:
            self.Mode_Button.setEnabled(True)
            self.Limite_Button.setEnabled(True)
            self.Courant_Button.setEnabled(True)
            self.Amplifier_Button.setEnabled(True)
            self.defaut_Button.setEnabled(True)            
            self.Sensing_comboBox.setEnabled(True)
            self.Network_comboBox.setEnabled(True)
            self.ps_p_h_radioButton.setEnabled(True)
            self.ps_p_m_radioButton.setEnabled(True)
            self.ps_m_h_radioButton.setEnabled(True)
            self.ps_m_m_radioButton.setEnabled(True)
            self.Limite_spinBox.setEnabled(True)

        # if read_bytes[2]=='1'and read_bytes[1]=='1':
        #     self.ps_p_h_radioButton.setChecked(True)
        #     self.ps_m_h_radioButton.setChecked(True)

        # if read_bytes[1]=='0' and read_bytes[2]=='1':
        #     self.ps_p_m_radioButton.setChecked(True)
        #     self.ps_m_m_radioButton.setChecked(True)
        ser.write(bytes.fromhex("0238"))

        read_bytes = str(ser.readline().hex())
        #read_bytes = read_bytes[2:]
        #print("bit : ",read_bytes)
        if read_bytes[20:22]=="00":
            #mode limite control courant
            pass
        elif read_bytes[20:22]=="01":
            #mode limite control Tension
            #self.limite()
            self.Limite_Button.setText("Tension")

        

        # if read_bytes[0:2]=="00":
        #     #current measuring range high
        #     pass
        # elif read_bytes[20:22]=="01":
        #     #current measuring range low
        #     self.Courant_Range()
        if read_bytes[23]=="1":
            self.ps_p_h_radioButton.setChecked(False)
            self.ps_p_m_radioButton.setChecked(False)
            self.ps_m_h_radioButton.setChecked(False)
            self.ps_m_m_radioButton.setChecked(False)
        elif read_bytes[23]=="2":
            self.ps_p_h_radioButton.setChecked(False)
            self.ps_p_m_radioButton.setChecked(True)
            self.ps_m_h_radioButton.setChecked(False)
            self.ps_m_m_radioButton.setChecked(False)
        elif read_bytes[23]=="3":
            self.ps_p_h_radioButton.setChecked(True)
            self.ps_p_m_radioButton.setChecked(False)
            self.ps_p_h_radioButton.setChecked(False)
            self.ps_m_m_radioButton.setChecked(False)
        elif read_bytes[23]=="4":
            self.ps_p_h_radioButton.setChecked(False)
            self.ps_p_m_radioButton.setChecked(False)
            self.ps_m_h_radioButton.setChecked(False)
            self.ps_m_m_radioButton.setChecked(True)
        elif read_bytes[23]=="5":
            self.ps_p_h_radioButton.setChecked(False)
            self.ps_p_m_radioButton.setChecked(True)
            self.ps_m_h_radioButton.setChecked(False)
            self.ps_m_m_radioButton.setChecked(True)
        elif read_bytes[23]=="6":
            self.ps_p_h_radioButton.setChecked(True)
            self.ps_p_m_radioButton.setChecked(False)
            self.ps_m_h_radioButton.setChecked(False)
            self.ps_m_m_radioButton.setChecked(True)
        elif read_bytes[23]=="7":
            self.ps_p_h_radioButton.setChecked(False)
            self.ps_p_m_radioButton.setChecked(False)
            self.ps_m_h_radioButton.setChecked(True)
            self.ps_m_m_radioButton.setChecked(False)
        elif read_bytes[23]=="8":
            self.ps_p_h_radioButton.setChecked(False)
            self.ps_p_m_radioButton.setChecked(True)
            self.ps_m_h_radioButton.setChecked(True)
            self.ps_m_m_radioButton.setChecked(False)
        elif read_bytes[23]=="9":
            self.ps_p_h_radioButton.setChecked(True)
            self.ps_p_m_radioButton.setChecked(False)
            self.ps_m_h_radioButton.setChecked(True)
            self.ps_m_m_radioButton.setChecked(False)

        # if read_bytes[0:2]=="00":
        #     #current measuring range high
        # elif read_bytes[20:22]=="01":
        #     #current measuring range low

        limite=round(int(read_bytes[8:12],16)*100/4095)
        self.Limite_spinBox.setValue(limite)
        # self.ready_Button.setStyleSheet("background-color : green")
        # self.ready_Button.setText("Ready")

        ser.write(bytes.fromhex("0238"))
        read_bytes = list(ser.readline().hex())
        self.Network_comboBox.setCurrentText(read_bytes[3])
        
        ser.write(bytes.fromhex("025E"))
        read_bytes = str(ser.readline().hex())
        if read_bytes=='00':
            self.Sensing_comboBox.setCurrentText("off")
        elif read_bytes=='01':
            self.Sensing_comboBox.setCurrentText("500 mV")
        elif read_bytes=='02':
            self.Sensing_comboBox.setCurrentText("1000 mV")
        elif read_bytes=='03':
            self.Sensing_comboBox.setCurrentText("2000 mV")

            
        
    
    def finished_temp(self):
        global Temperature_flag
        print("temperature fini")
        print(Temperature_flag)
        self.lecture()
        



        if Temperature_flag==1:

            time.sleep(1)
            self.thread = QThread()

            # Step 3: Create a worker object
            self.worker = Temperature_Ampli(self.Temp_label,self.port_connection)
            # Step 4: Move worker to the thread
            self.worker.moveToThread(self.thread)
            # Step 5: Connect signals and slots
            self.thread.started.connect(self.worker.run)
            self.worker.finished.connect(self.thread.quit)
            self.worker.finished.connect(self.finished_temp)
            # Temperature_Ampli(self.Temp_label,self.port_connection)
            self.thread.start()
        else:
            print('fin')


    def Power_Supply_plus(self,radiobutton):
        if self.Amplifier_Button.text()=="OFF":
            if  self.ps_p_h_radioButton.isChecked()==True:
                self.plus_h=1
                # self.ps_p_m_radioButton.setChecked(False)
            elif self.ps_p_h_radioButton.isChecked()==False:
                self.plus_h=0

            if  self.ps_p_m_radioButton.isChecked()==True:
                self.plus_m=1
                # self.ps_p_h_radioButton.setChecked(False)
            elif self.ps_p_m_radioButton.isChecked()==False:
                self.plus_m=0
            self.radioButton_change()
        else:
            self.lecture()
            
    def Power_Supply_moins(self):
        if self.Amplifier_Button.text()=="OFF":
            if  self.ps_m_h_radioButton.isChecked()==True:
                self.moins_h=1
            elif self.ps_m_h_radioButton.isChecked()==False:
                self.moins_h=0

            if  self.ps_m_m_radioButton.isChecked()==True:
                self.moins_m=1
            elif self.ps_m_m_radioButton.isChecked()==False:
                self.moins_m=0        
            self.radioButton_change()   
        else:
            self.lecture() 

    def Limite(self):
        if self.Limite_Button.text()=="Tension":
            self.Limite_Button.setText("Courant")
            ser = serial.Serial(self.port_connection, baudrate=9600,timeout=1)
            ser.write(bytes.fromhex("035300"))
        else:
            self.Limite_Button.setText("Tension")
            ser = serial.Serial(self.port_connection, baudrate=9600,timeout=1)
            ser.write(bytes.fromhex("035301"))
    
    def closeEvent(self,event):
        global Temperature_flag
        Temperature_flag=0

    def accept(self):
        global Temperature_flag

        Temperature_flag=0
        self.close()
    
    def radioButton_change(self):
        ser = serial.Serial(self.port_connection, baudrate=9600)
        
        if self.plus_h==0 and self.plus_m==0 and self.moins_h==0 and self.moins_m==0:
            ser.write(bytes.fromhex("035401"))
        elif self.plus_h==0 and self.plus_m==1 and self.moins_h==0 and self.moins_m==0:
            ser.write(bytes.fromhex("035402"))
        elif self.plus_h==1 and self.plus_m==0 and self.moins_h==0 and self.moins_m==0:
            ser.write(bytes.fromhex("035403"))
        elif self.plus_h==0 and self.plus_m==0 and self.moins_h==0 and self.moins_m==1:
            ser.write(bytes.fromhex("035404"))
        elif self.plus_h==0 and self.plus_m==1 and self.moins_h==0 and self.moins_m==1:
            ser.write(bytes.fromhex("035405"))
        elif self.plus_h==1 and self.plus_m==0 and self.moins_h==0 and self.moins_m==1:
            ser.write(bytes.fromhex("035406"))
        elif self.plus_h==0 and self.plus_m==0 and self.moins_h==1 and self.moins_m==0:
            ser.write(bytes.fromhex("035407"))
        elif self.plus_h==0 and self.plus_m==1 and self.moins_h==1 and self.moins_m==0:
            ser.write(bytes.fromhex("035408"))
        elif self.plus_h==1 and self.plus_m==0 and self.moins_h==1 and self.moins_m==0:
            ser.write(bytes.fromhex("035409"))

    
    def Courant_Range(self):
        if self.Courant_Button.text()=="High":
            self.Courant_Button.setText("Low")
            ser = serial.Serial(self.port_connection, baudrate=9600)
            ser.write(bytes.fromhex("032801"))
        else:
            self.Courant_Button.setText("High")
            ser = serial.Serial(self.port_connection, baudrate=9600)
            ser.write(bytes.fromhex("032800"))
        
    def Mode(self):
        if self.Mode_Button.text()=="Tension":
            self.Mode_Button.setText("Courant")
            ser = serial.Serial(self.port_connection, baudrate=9600)
            ser.write(bytes.fromhex("032A01"))
        else:
            self.Mode_Button.setText("Tension")
            ser = serial.Serial(self.port_connection, baudrate=9600)
            ser.write(bytes.fromhex("032A00"))
       
     
    def Output(self):
        if self.Amplifier_Button.text()=="OFF":
            self.Amplifier_Button.setText("ON")
            self.Amplifier_Button.setStyleSheet("background-color : green")
            ser = serial.Serial(self.port_connection, baudrate=9600)
            ser.write(bytes.fromhex("033501"))
            
            
        else:
            self.Amplifier_Button.setText("OFF")
            self.Amplifier_Button.setStyleSheet("background-color : red")
            ser = serial.Serial(self.port_connection, baudrate=9600)
            ser.write(bytes.fromhex("033500"))

        ser.write(bytes.fromhex("0210"))

        read_bytes = bin(int(ser.read().hex(),16))


    def Network(self):
        ser = serial.Serial(self.port_connection, baudrate=9600)
        
        net=int(self.Network_comboBox.currentText())
        net=format(net,'02x')
        ser.write(bytes.fromhex("0329"+net))

    def Sensing(self):
        sensing=str(self.Sensing_comboBox.currentText())
        ser = serial.Serial(self.port_connection, baudrate=9600)
        if sensing=='off':
            ser.write(bytes.fromhex("035D00"))
        if sensing=='500 mV':
            ser.write(bytes.fromhex("035D01"))
        if sensing=='1000 mV':
            ser.write(bytes.fromhex("035D02"))
        if sensing=='2000 mV':
            ser.write(bytes.fromhex("035D03"))
        
        
class Ampli_defaut_Window(QDialog, Ui_Ampli_defaut):
    def __init__(self, main_window, *args, obj=None, **kwargs):
        super(Ampli_defaut_Window, self).__init__(*args, **kwargs)
        global Temperature_flag,limite
        self.setupUi(self)
        self.port_connection=''
        self.SwitchOn=[]
        self.amp_on=[]

        self.Connection()

    def Connection(self):
        serial_port = serial.tools.list_ports.comports()

        connect=0
        
        serial_port = serial.tools.list_ports.comports()
        
        for port in serial_port:
            print(f"{port.name} // {port.device} // D={port.description}")
            #if ser.read():
            if port.device[:-1]=="/dev/ttyUSB":
                ser = serial.Serial(port.device, baudrate=9600,timeout=1)
                ser.write(bytes.fromhex("0210"))
                
                read_bytes = ser.read().hex()
                # try:

                if len(read_bytes)==2:
                    self.port_connection=port.device
                    print("Ampli connecté")
                    connect=1
                    self._connectAction()
                # except:
                #     pass

    def _connectAction(self):  
        global Temperature_flag
        self.Mode_Button.clicked.connect(self.Mode)
        self.Limite_Button.clicked.connect(self.Limite)
        self.Courant_Button.clicked.connect(self.Courant_Range)
        # # A faire fonction
        self.Interlock_Button.clicked.connect(self.Interlock)
        self.Overload_Button.clicked.connect(self.Overload)
        self.Restart_Button.clicked.connect(self.Restart)
        self.Power_Button.clicked.connect(self.Power)

        self.Sensing_comboBox.activated.connect(self.Sensing)
        self.Network_comboBox.activated.connect(self.Network)
        self.Timer_SpinBox.valueChanged.connect(self.Timer)

        self.lecture()
        self.group = QButtonGroup()
        self.group.setExclusive(True)  # Radio buttons are not exclusive
        self.group.buttonPressed.connect(self.check_buttons)   
        self.plus_h=0
        self.plus_m=0
        self.ps_p_h_radioButton.toggled.connect(lambda: self.Power_Supply_plus(self.ps_p_h_radioButton))
        self.ps_p_m_radioButton.toggled.connect(lambda: self.Power_Supply_plus(self.ps_p_m_radioButton))
        self.group.addButton(self.ps_p_h_radioButton)
        self.group.addButton(self.ps_p_m_radioButton)
        self.group.addButton(self.ps_p_tempo)

        
        self.group2 = QButtonGroup()
        self.group2.setExclusive(True)  # Radio buttons are not exclusive
        self.group2.buttonPressed.connect(self.check_buttons2)
        self.moins_h=0
        self.moins_m=0
        self.ps_m_h_radioButton.toggled.connect(lambda: self.Power_Supply_moins())
        self.ps_m_m_radioButton.toggled.connect(lambda: self.Power_Supply_moins())
        self.group2.addButton(self.ps_m_h_radioButton)
        self.group2.addButton(self.ps_m_m_radioButton)
        self.group2.addButton(self.ps_m_tempo)
        
        

        self.Limite_spinBox.valueChanged.connect(lambda: self.spin_method()) 
        
        # nouveau bouton +combo box



    def check_buttons(self, radioButton):
    # Uncheck every other button in this group
        # for button in self.group.buttons():
        #     if button is not radioButton:
        #         button.setChecked(True)
         if radioButton.isChecked():
            self.group.setExclusive(False)
            self.ps_p_tempo.setChecked(True)
            self.group.setExclusive(True)


    def check_buttons2(self, radioButton):
    # Uncheck every other button in this group
        # for button in self.group.buttons():
        #     if button is not radioButton:
        #         button.setChecked(True)
        if radioButton.isChecked():
            self.group2.setExclusive(False)
            self.ps_m_tempo.setChecked(True)
            self.group2.setExclusive(True)

        
    def spin_method(self):
        global limite
        limite=int(self.Limite_spinBox.value()*4095/100)
        limite_hex=list(format(limite,'04x'))
        self.SwitchOn[9]=limite_hex[1]
        self.SwitchOn[10]=limite_hex[2]
        self.SwitchOn[11]=limite_hex[3]

    def lecture(self):
        #global limite
        ser = serial.Serial(self.port_connection, baudrate=9600, timeout=1)

        # Interlock
        ser.write(bytes.fromhex("022F"))
        self.SwitchOn = list(ser.readline().hex())
        # interlock
        if self.SwitchOn[13]=="0":
            self.Interlock_Button.setText("Latching")
        elif self.SwitchOn[13]=="1":
            self.Interlock_Button.setText("Live")
        elif self.SwitchOn[13]=="2":
            self.Interlock_Button.setText("Don't Care")

        self.Network_comboBox.setCurrentText(self.SwitchOn[3])
        
        ser.write(bytes.fromhex("025E"))
        read_bytes = str(ser.readline().hex())
        if read_bytes=='00':
            self.Sensing_comboBox.setCurrentText("off")
        elif read_bytes=='01':
            self.Sensing_comboBox.setCurrentText("500 mV")
        elif read_bytes=='02':
            self.Sensing_comboBox.setCurrentText("1000 mV")
        elif read_bytes=='03':
            self.Sensing_comboBox.setCurrentText("2000 mV")

        # Restart after
        ser.write(bytes.fromhex("0222"))
        res = ser.read().hex()
        res=list("{0:08b}".format(int(res, 16))) 
        self.amp_on=res

        if res[7]=="0":
            self.Overload_Button.setText("OFF")
        elif res[7]=="1":
            self.Overload_Button.setText("ON")
        if res[6]=="0":
            self.Power_Button.setText("OFF")
        elif res[6]=="1":
            self.Power_Button.setText("ON")
        if res[5]=="0":
            self.Restart_Button.setText("OFF")
        elif res[5]=="1":
            self.Restart_Button.setText("ON")

        # Restart Timer Time
        ser.write(bytes.fromhex("0223"))
        read_bytes = int(ser.readline().hex(),16)
        self.Timer_SpinBox.setValue(read_bytes)


        # Current Range + Operating mode + Power Supply +
        ser.write(bytes.fromhex("022F"))
        read_bytes = str(ser.readline().hex())
        if read_bytes[15]=="0":
            #mode limite control courant
            self.Limite_Button.setText("Courant")
        elif read_bytes[15]=="1":
            self.Limite_Button.setText("Tension")


        if read_bytes[1]=="0":
            #current measuring range high
            self.Courant_Button.setText("high")
        elif read_bytes[1]=="1":
            #current measuring range low
            self.Courant_Button.setText("Low")

        limite=round(int(read_bytes[8:12],16)*100/4095)
        self.Limite_spinBox.setValue(limite)
        # self.ready_Button.setStyleSheet("background-color : green")
        # self.ready_Button.setText("Ready")


        if read_bytes[17]=="1":
            self.ps_p_h_radioButton.setChecked(False)
            self.ps_p_m_radioButton.setChecked(False)
            self.ps_m_h_radioButton.setChecked(False)
            self.ps_m_m_radioButton.setChecked(False)
        elif read_bytes[17]=="2":
            self.ps_p_h_radioButton.setChecked(False)
            self.ps_p_m_radioButton.setChecked(True)
            self.ps_m_h_radioButton.setChecked(False)
            self.ps_m_m_radioButton.setChecked(False)
        elif read_bytes[17]=="3":
            self.ps_p_h_radioButton.setChecked(True)
            self.ps_p_m_radioButton.setChecked(False)
            self.ps_p_h_radioButton.setChecked(False)
            self.ps_m_m_radioButton.setChecked(False)
        elif read_bytes[17]=="4":
            self.ps_p_h_radioButton.setChecked(False)
            self.ps_p_m_radioButton.setChecked(False)
            self.ps_m_h_radioButton.setChecked(False)
            self.ps_m_m_radioButton.setChecked(True)
        elif read_bytes[17]=="5":
            self.ps_p_h_radioButton.setChecked(False)
            self.ps_p_m_radioButton.setChecked(True)
            self.ps_m_h_radioButton.setChecked(False)
            self.ps_m_m_radioButton.setChecked(True)
        elif read_bytes[17]=="6":
            self.ps_p_h_radioButton.setChecked(True)
            self.ps_p_m_radioButton.setChecked(False)
            self.ps_m_h_radioButton.setChecked(False)
            self.ps_m_m_radioButton.setChecked(True)
        elif read_bytes[17]=="7":
            self.ps_p_h_radioButton.setChecked(False)
            self.ps_p_m_radioButton.setChecked(False)
            self.ps_m_h_radioButton.setChecked(True)
            self.ps_m_m_radioButton.setChecked(False)
        elif read_bytes[17]=="8":
            self.ps_p_h_radioButton.setChecked(False)
            self.ps_p_m_radioButton.setChecked(True)
            self.ps_m_h_radioButton.setChecked(True)
            self.ps_m_m_radioButton.setChecked(False)
        elif read_bytes[17]=="9":
            self.ps_p_h_radioButton.setChecked(True)
            self.ps_p_m_radioButton.setChecked(False)
            self.ps_m_h_radioButton.setChecked(True)
            self.ps_m_m_radioButton.setChecked(False)



        
            


    def Power_Supply_plus(self,radiobutton):
        if  self.ps_p_h_radioButton.isChecked()==True:
            self.plus_h=1
            # self.ps_p_m_radioButton.setChecked(False)
        elif self.ps_p_h_radioButton.isChecked()==False:
            self.plus_h=0

        if  self.ps_p_m_radioButton.isChecked()==True:
            self.plus_m=1
            # self.ps_p_h_radioButton.setChecked(False)
        elif self.ps_p_m_radioButton.isChecked()==False:
            self.plus_m=0
        self.radioButton_change()
        
            
    def Power_Supply_moins(self):
        if  self.ps_m_h_radioButton.isChecked()==True:
            self.moins_h=1
        elif self.ps_m_h_radioButton.isChecked()==False:
            self.moins_h=0

        if  self.ps_m_m_radioButton.isChecked()==True:
            self.moins_m=1
        elif self.ps_m_m_radioButton.isChecked()==False:
            self.moins_m=0        
        self.radioButton_change()   
        

    def Limite(self):
        if self.Limite_Button.text()=="Tension":
            self.Limite_Button.setText("Courant")
            self.SwitchOn[15]="0"     

        else:
            self.Limite_Button.setText("Tension")
            self.SwitchOn[15]="1"     
        
    
    def closeEvent(self,event):
        global Temperature_flag
        Temperature_flag=0

    def accept(self):
           
        ser = serial.Serial(self.port_connection, baudrate=9600)
        res=''.join(self.SwitchOn)
        ser.write(bytes.fromhex('0A2E'+str(res)))
        # read_bytes = ser.read().hex()
        self.close()
    
    def radioButton_change(self):
        ser = serial.Serial(self.port_connection, baudrate=9600)
        
        if self.plus_h==0 and self.plus_m==0 and self.moins_h==0 and self.moins_m==0:
            self.SwitchOn[17]="1"  
        elif self.plus_h==0 and self.plus_m==1 and self.moins_h==0 and self.moins_m==0:
            self.SwitchOn[17]="2"  
        elif self.plus_h==1 and self.plus_m==0 and self.moins_h==0 and self.moins_m==0:
            self.SwitchOn[17]="3"  
        elif self.plus_h==0 and self.plus_m==0 and self.moins_h==0 and self.moins_m==1:
            self.SwitchOn[17]="4"  
        elif self.plus_h==0 and self.plus_m==1 and self.moins_h==0 and self.moins_m==1:
            self.SwitchOn[17]="5"  
        elif self.plus_h==1 and self.plus_m==0 and self.moins_h==0 and self.moins_m==1:
            self.SwitchOn[17]="6"  
        elif self.plus_h==0 and self.plus_m==0 and self.moins_h==1 and self.moins_m==0:
            self.SwitchOn[17]="7"  
        elif self.plus_h==0 and self.plus_m==1 and self.moins_h==1 and self.moins_m==0:
            self.SwitchOn[17]="8"  
        elif self.plus_h==1 and self.plus_m==0 and self.moins_h==1 and self.moins_m==0:
            self.SwitchOn[17]="9"  

    
    def Courant_Range(self):
        if self.Courant_Button.text()=="High":
            self.Courant_Button.setText("Low")
            self.SwitchOn[1]="1"     
        else:
            self.Courant_Button.setText("High")
            ser = serial.Serial(self.port_connection, baudrate=9600)
            self.SwitchOn[1]="0"
            
        
    def Mode(self):
        if self.Mode_Button.text()=="Tension":
            self.Mode_Button.setText("Courant")
            self.SwitchOn[5]="1"
        else:
            self.Mode_Button.setText("Tension")
            self.SwitchOn[5]="0"
       
     
    def Output(self):
        if self.Amplifier_Button.text()=="OFF":
            self.Amplifier_Button.setText("ON")
            self.Amplifier_Button.setStyleSheet("background-color : green")
            ser = serial.Serial(self.port_connection, baudrate=9600)
            ser.write(bytes.fromhex("033501"))        
        else:
            self.Amplifier_Button.setText("OFF")
            self.Amplifier_Button.setStyleSheet("background-color : red")
            ser = serial.Serial(self.port_connection, baudrate=9600)
            ser.write(bytes.fromhex("033500"))


    def Interlock(self):
        if self.Interlock_Button.text()=="Latching":
            self.Interlock_Button.setText("Live")
            self.SwitchOn[12]="0"
            self.SwitchOn[13]="1"
                        
        elif self.Interlock_Button.text()=="Live":
            self.Interlock_Button.setText("Don't Care")
            self.SwitchOn[12]="0"
            self.SwitchOn[13]="2"
            
        elif self.Interlock_Button.text()=="Don't Care":
            self.Interlock_Button.setText("Latching")
            self.SwitchOn[12]="0"
            self.SwitchOn[13]="0"

    def Network(self):
        self.SwitchOn[3]=str(self.Network_comboBox.currentText())

    def Sensing(self):
        sensing=str(self.Sensing_comboBox.currentText())
        ser = serial.Serial(self.port_connection, baudrate=9600)
        if sensing=='off':
            ser.write(bytes.fromhex("035D00"))
        if sensing=='500 mV':
            ser.write(bytes.fromhex("035D01"))
        if sensing=='1000 mV':
            ser.write(bytes.fromhex("035D02"))
        if sensing=='2000 mV':
            ser.write(bytes.fromhex("035D03"))

    def Timer(self):
        time=int(self.Timer_SpinBox.value())
        ser = serial.Serial(self.port_connection, baudrate=9600,timeout=1)

        ser.write(bytes.fromhex('0321'+format(time, '02x')))

    def Overload(self):
        if self.Overload_Button.text()=="OFF":
            self.Overload_Button.setText("ON")
            self.amp_on[7]='1'       
        else:
            self.Overload_Button.setText("OFF")
            self.amp_on[7]='0' 

        res=''.join(self.amp_on)
        res=int(''.join(map(str, res)), 2)
        res=format(res,'02x')
        ser = serial.Serial(self.port_connection, baudrate=9600)
        ser.write(bytes.fromhex("0320"+str(res))) 

    def Power(self):
        if self.Power_Button.text()=="OFF":
            self.Power_Button.setText("ON")
            self.amp_on[6]='1'       
        else:
            self.Power_Button.setText("OFF")
            self.amp_on[6]='0' 

        res=''.join(self.amp_on)
        res=int(''.join(map(str, res)), 2)
        res=format(res,'02x')
        ser = serial.Serial(self.port_connection, baudrate=9600)
        ser.write(bytes.fromhex("0320"+str(res))) 

    def Restart(self):
        if self.Restart_Button.text()=="OFF":
            self.Restart_Button.setText("ON")
            self.amp_on[5]='1'       
        else:
            self.Restart_Button.setText("OFF")
            self.amp_on[5]='0' 

        res=''.join(self.amp_on)
        res=int(''.join(map(str, res)), 2)
        res=format(res,'02x')
        ser = serial.Serial(self.port_connection, baudrate=9600)
        ser.write(bytes.fromhex("0320"+str(res))) 

    

        
            

            


class AcquisWindow(QDialog, Ui_Page_acquisition):
    def __init__(self, *args, obj=None, **kwargs):
        global iteration_max, num_samples, Resolution, Nbre_enregist, alpha, beta, rampe, gamma, mode_filtre, fenetre_filtre
        super(AcquisWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle("Paramètres d'acquisition")
        self.warning_edit.setVisible(False)
        self.Nbre_iter_spin.setValue(int(iteration_max))
        self.Nbre_ech_spin.setValue(int(num_samples))
        self.Nbre_bits_combo.setCurrentText(str(Resolution))
        self.Nbre_enreg_spin.setValue(int(Nbre_enregist))
        self.coeff_alpha_spin.setValue(float(alpha))
        self.coeff_beta_spin.setValue(float(beta))
        self.coeff_rampe_spin.setValue(int(rampe))
        self.coeff_newton_spin.setValue(float(gamma))
        self.Fenetre_Filtre_spinBox.setValue(int(fenetre_filtre))
        self.Filtre_comboBox.setCurrentText(str(mode_filtre))

    def accept(self):
        global mode_filtre,fenetre_filtre, iteration_max, num_samples, Resolution, Nbre_enregist, alpha, beta, rampe, gamma
        iteration_max = self.Nbre_iter_spin.value()
        num_samples = self.Nbre_ech_spin.value()
        Resolution = self.Nbre_bits_combo.currentText()
        Nbre_enregist = self.Nbre_enreg_spin.value()
        alpha = self.coeff_alpha_spin.value()
        beta = self.coeff_beta_spin.value()
        rampe = self.coeff_rampe_spin.value()
        gamma= self.coeff_newton_spin.value()
        fenetre_filtre= self.Fenetre_Filtre_spinBox.value()
        mode_filtre = self.Filtre_comboBox.currentText()

        self.close()


class PertesVsFreqWindow(QDialog, Ui_PertesVsFreq):
    def __init__(self, *args, onj=None, **kwargs):
        super(PertesVsFreqWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle("Pertes vs Fréquences")
        self.widget.canvas.ax.grid()
        self.import_button.clicked.connect(self.import_csv)
        self.curve_Button.clicked.connect(self.import_manuel)
        self.point_Button.clicked.connect(self.ajouter_point)
        self.valider_Button.clicked.connect(self.valider)
        self.b=[]
        self.Nom=''
        self.Freq_tab_manuel=[]
        self.Pv_tab_manuel=[]

    def import_csv(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileNames(
            self, "Select CSV File", "", "CSV Files (*.csv)")
        if file_path:
            self.load_csv_data(file_path)     
    
    def plot_data(self, a, b, title, bmax):
        #line, = self.widget.canvas.ax.plot(a, b, label=title)
        print(b)
        #line, = self.widget.canvas.ax.semilogy(a, b, label=title)
        self.widget.canvas.ax.loglog(a, b)
        
        # self.lines.append(line)
        # self.signals.append(title)
        self.widget.canvas.ax.legend(bmax)
        self.widget.canvas.ax.set_xlabel("Fréquence (Hz)")
        self.widget.canvas.ax.set_ylabel("Pertes (W/m³)")
        self.widget.canvas.ax.grid(True, which="both",ls="-")
        self.widget.canvas.draw()
        
    def plot_file(self,File,bmax):
        for i in range(len(File)):
            File[i]=str(i)+" - "+File[i]
        File.insert(0,"Courbre : "+bmax[-1])
        #self.import_list.addItems(str("\n".join(File)))
        self.import_list.addItems(File)

    def import_manuel(self):
        self.Nom=self.lineEdit.text()
        self.Freq_tab_manuel.clear()
        self.Pv_tab_manuel.clear()
    
    def ajouter_point(self):
        self.Freq_tab_manuel.append(str(self.freq_SpinBox_2.value()*1000))
        self.Pv_tab_manuel.append(self.pertes_SpinBox.value())
        self.pertes_SpinBox.setValue(0.00)
        self.freq_SpinBox_2.setValue(0.00)
    
    def valider(self):
        tab_manuel=[]
        for i in range(len(self.Freq_tab_manuel)):
            tab_manuel.append(str(i)+" - "+str(self.Pv_tab_manuel[i])+" W/m³ - "+str(self.Freq_tab_manuel[i])+" Hz")
        tab_manuel.insert(0,"Courbre : "+ self.Nom)
        #self.import_list.addItems(str("\n".join(File)))
        self.import_list.addItems(tab_manuel)
        
        self.b.append(self.Nom)
        self.plot_data(self.Freq_tab_manuel, self.Pv_tab_manuel, self.Nom, self.b)
        self.lineEdit.clear()
        self.pertes_SpinBox.setValue(0.00)
        self.freq_SpinBox_2.setValue(0.00)
        
    def load_csv_data(self, file_path):
        self.b
        Pv_tab=[]
        Freq_tab=[]
        bmax_tab=[]
        for file in file_path:
        
            with open(file, newline='') as csvfile:
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
            file_name = os.path.basename(file)[:-4]
            bmax = variables.get("Bmax (T) =")
            br = variables.get("Br (T) =")
            freq = variables.get("Freq(Hz) =")
            hc = variables.get("Hc =")
            Mu_r = variables.get("µr =")
            hmax = variables.get("Hmax =")
            W = variables.get("W(J/m³) =")
            Pv = variables.get("P(W/m³) =")
            champ_h = arrays.get("ChampH (A/m)")
            champ_b = arrays.get("ChampB (T)")
            champ_h = [float(numeric_string) for numeric_string in champ_h]
            champ_b = [float(numeric_string) for numeric_string in champ_b]
            Pv_tab.append(round(float(Pv),2))
            bmax_tab.append(round(float(bmax),3))
            Freq_tab.append(freq)
    
        Freq_tab.sort()
        Pv_tab.sort()
        bmax=str(np.round(np.mean(bmax_tab),3))
        self.b.append(bmax+' T')
        self.plot_data(Freq_tab, Pv_tab, file_name,self.b)
        path=[os.path.split(i)[1] for i in file_path]
        self.plot_file(path,self.b)
    
            

class AnalyseWindow(QDialog, Ui_analyse):
    def __init__(self, *args, obj=None, **kwargs):
        super(AnalyseWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle("Correction des courbes")
        self.widget_H.canvas.ax.grid()
                
        self.widget_analyse.canvas.ax.grid()
        
        self.widget_analyse_2.canvas.ax.grid() 
                
        self.clear_button.clicked.connect(self.clear_canva)
        self.toolButton_Save.clicked.connect(self.saves_project)
        self.Start_filtrage_button.clicked.connect(self.start_filtrage)
        
        self.Harmo_spin.setValue(Harmo)
        self.file_path=0
        self.signals = []
        self.lines = []

        self.Bmax= None
        self.Frequence= None
        self.Br = None
        self.Hc = None
        self.Hmax= None
        self.Mu = None
        self.W = None
        self.Pv = None
        self.champH = None
        self.champB = None
        self.champH_filtré = None
        self.champB_filtré = None
        self.timeC_filtre = None


# tracer l'hysteresis avec filtrage
    def export_table(self):
        
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self, "Select CSV File", "", "CSV Files (*.csv)")
        
        self.update_mesures(file_path)
        
        df = pd.read_csv(file_path, skiprows=1)
        
        
        
        temps = pd.to_numeric(df.iloc[:, 0], errors='coerce')
        self.timeC_filtre=temps
        champH = pd.to_numeric(df.iloc[:, 1], errors='coerce')
        champB = pd.to_numeric(df.iloc[:, 2], errors='coerce')
        mask = temps.notna() & champH.notna() & champB.notna()
        return temps[mask].to_numpy(), champH[mask].to_numpy(), champB[mask].to_numpy()

    
    def calculer_fft(self,signal, temps, nb_harmoniques):
        
        n = len(signal)
        print("n:",n)
        dt = temps[1] - temps[0]
        freqs = np.fft.fftfreq(n, d=dt)
        fft_vals = np.fft.fft(signal)

        freqs = freqs[:n//2]
        fft_vals = fft_vals[:n//2]

        amp_spectrum = np.abs(fft_vals)
        idx_f0 = np.argmax(amp_spectrum[1:]) + 1
        f0 = freqs[idx_f0]

        harm_freqs = [k * f0 for k in range(1, nb_harmoniques + 1)]
        harm_amps = []

        for f in harm_freqs:
            idx = np.argmin(np.abs(freqs - f))
            harm_amps.append(np.abs(fft_vals[idx]))

        return harm_freqs, harm_amps,f0
    
    def extraire_harmoniques(self,signal, temps, nb_harmoniques):
        
        n = len(signal)
        dt = temps[1] - temps[0]
        freqs = np.fft.fftfreq(n, d=dt)
        fft_vals = np.fft.fft(signal)

        freqs_pos = freqs[:n//2]
        fft_vals_pos = fft_vals[:n//2]
        amp_spectrum = np.abs(fft_vals_pos)

        idx_f0 = np.argmax(amp_spectrum[1:]) + 1
        f0 = freqs_pos[idx_f0]

        fft_filtered = np.zeros(n, dtype=complex)
        for k in range(1, nb_harmoniques + 1):
            freq_k = k * f0
            idx_pos = np.argmin(np.abs(freqs - freq_k))
            idx_neg = np.argmin(np.abs(freqs + freq_k))
            fft_filtered[idx_pos] = fft_vals[idx_pos]
            fft_filtered[idx_neg] = fft_vals[idx_neg]

        signal_reconstruit = np.fft.ifft(fft_filtered).real
        return signal_reconstruit

    def update_mesures(self,file_path):
        with open(file_path, newline='') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            data = list(reader)

        variables = {}

        variables_row = data[0]

        for i, value in enumerate(variables_row):
            if i % 2 == 1:
                variable_name = variables_row[i - 1].strip()
                variable_value = value.strip()
                variables[variable_name] = variable_value

        bmax = variables.get("Bmax (T) =")
        br = variables.get("Br (T) =")
        freq = variables.get("Freq(Hz) =")
        hc = variables.get("Hc =")
        Mu_r = variables.get("µr =")
        hmax = variables.get("Hmax =")
        W = variables.get("W(J/m³) =")
        Pv = variables.get("P(W/m³) =")           
        self.label_Bmax_value_brut.setText(str(round(float(bmax), 3)))
        self.label_Hmax_value_brut.setText(str(round(float(hmax), 3)))
        self.label_Hc_value_brut.setText(str(round(float(hc), 3)))
        self.label_Br_value_brut.setText(str(round(float(br), 3)))
        self.label_Area_value_brut.setText(str(round(float(W), 3)))
        self.label_Pv_value_brut.setText(str(round(float(Pv))))
        
        self.Frequence = freq
        self.Mu = Mu_r
        

# === Calcul d'aire de cycle filtrer B(H) (interpolation) ===
    def get_point(self,H, champH_filtré, champB_filtré):
        i = 0
        while H > champH_filtré[i]:
            if i < len(champH_filtré) - 1:
                i += 1
            else:
                i = 0
                break
        k = (H - champH_filtré[i-1]) / (champH_filtré[i] - champH_filtré[i-1])
        y1 = champB_filtré[i-1] + k * (champB_filtré[i] - champB_filtré[i-1])

        while H < champH_filtré[i]:
            if i < len(champH_filtré) - 1:
                i += 1
            else:
                i = 0
                break
        k = (H - champH_filtré[i-1]) / (champH_filtré[i] - champH_filtré[i-1])
        y2 = champB_filtré[i-1] + k * (champB_filtré[i] - champB_filtré[i-1])

        return y1, y2

    def calc_A(self,champH_filtré, champB_filtré):
        n_point = 5001
        hmin = min(champH_filtré)
        hmax = max(champH_filtré)

        dH = (hmax - hmin) / n_point
        hrange = np.arange(hmin, hmax, dH)

        A = 0
        y1, y2 = self.get_point(hrange[1], champH_filtré, champB_filtré)
        A += dH * np.abs(y1 - y2) / 2
        last_y1, last_y2 = y1, y2

        for H in hrange[2:-1]:
            y1, y2 = self.get_point(H, champH_filtré, champB_filtré)
            A += dH * (np.abs(y1 - y2) + np.abs(last_y1 - last_y2)) / 2
            last_y1, last_y2 = y1, y2

        A += dH * np.abs(last_y1 - last_y2) / 2
        print(A)
        return A
        
    
    def calculer_champ_coercitif(self,champH_filtré, champB_filtré):
        ChampB_nul = np.where(np.diff(np.sign(champB_filtré)))[0]
        Hcs = []
        for valeur in ChampB_nul:
            Hcs.append(np.abs(champH_filtré[valeur]))
        Hc = np.mean(Hcs) # Calcul du champ coercitif
        champ_coercitif_moyen = round(Hc,3)
        return champ_coercitif_moyen

    def calculer_champ_remanent(self,champH_filtré, champB_filtré):
        ChampH2_nul = np.where(np.diff(np.sign(champH_filtré)))
        Brs = []
        for valeur in ChampH2_nul[:2]:
            Brs.append(np.abs(champB_filtré[valeur]))
        Br_filtre = np.mean(Brs) # calcul du champ rémanant
        Br = round(Br_filtre,3)
        return Br
    
    def start_filtrage(self): 
        # Chargement des données
        self.clear_canva()
        Harmo = self.Harmo_spin.value()
        temps, champH, champB = self.export_table()
        
        
        # FFT : extraction des N premières harmoniques pour affichage
        print("ChampsH:", champH)
        freq_H, amp_H,f0_H = self.calculer_fft(champH, temps, Harmo)
        self.freq_H = freq_H
        print("freq_H:", freq_H)
        print("f0_H:", f0_H)
        freq_B, amp_B,f0_B = self.calculer_fft(champB, temps, Harmo)
        print("freq_B:", freq_B)
        print("amp_B:", amp_B)
        
        champH_filtré = self.extraire_harmoniques(champH, temps, Harmo)
        self.champH_filtré  = champH_filtré
        print("champH_filtré:", champH_filtré)
        champB_filtré = self.extraire_harmoniques(champB, temps, Harmo)
        self.champB_filtré  = champB_filtré
        print("champB_filtré:", champB_filtré)
        
       #calcukl Parametre filtrage harmonique 
        W_filtre= self.calc_A(champH_filtré,champB_filtré)
        self.W = W_filtre
        self.label_Area_value_filtre.setText(str(round(W_filtre,3)))
        Pv_filtre = round(f0_H*W_filtre)
        self.Pv = Pv_filtre
        print("Pv_filtre:", Pv_filtre)
        self.label_Pv_value_filtre.setText(str(Pv_filtre))
        B_max = np.max(np.abs(champB_filtré))
        self.Bmax=B_max
        self.label_Bmax_value_filtre.setText(str(round(B_max,3)))
        H_max = np.max(np.abs(champH_filtré))
        self.Hmax= H_max
        self.label_Hmax_value_filtre.setText(str(round(H_max,3)))
        Hc_filtre=self.calculer_champ_coercitif(champH_filtré, champB_filtré)
        self.Hc = Hc_filtre
        self.label_Hc_value_filtre.setText(str(Hc_filtre))
        print("Hc_filtre:", Hc_filtre)
        Br_filtre = self.calculer_champ_remanent(champH_filtré, champB_filtré)
        self.Br = Br_filtre
        self.label_Br_value_filtre.setText(str(Br_filtre))
        print("Br_filtre:", Br_filtre)
        
        
       # tracer courbes
        self.widget_analyse.canvas.ax.set_ylabel("B",rotation=0)
        self.widget_analyse.canvas.ax.yaxis.set_label_coords(0,1)
        self.widget_analyse.canvas.ax.set_xlabel("H")
        self.widget_analyse.canvas.ax.xaxis.set_label_coords(1.05, -0.025)
        self.signals.append("hysteresis")
        line, = self.widget_analyse.canvas.ax.plot(champH, champB, label="hysteresis brut")
        self.lines.append(line)
        self.widget_analyse.canvas.ax.legend()
        self.widget_analyse.canvas.draw()
        
        line, = self.widget_analyse.canvas.ax.plot(champH_filtré, champB_filtré, label="hysteresis filtré")
        self.lines.append(line)
        self.signals.append("hysteresis")
        self.widget_analyse.canvas.ax.legend()
        self.widget_analyse.canvas.draw()
        
      
        
        NbEch = 2500
        t = linspace(0,(NbEch-1),NbEch)
        t = t[0:(NbEch)]
        
        self.widget_H.canvas.ax.set_ylabel("H",rotation=0)        
        self.widget_H.canvas.ax.yaxis.set_label_coords(0,1)
        self.widget_H.canvas.ax.set_xlabel("µs")
        self.widget_H.canvas.ax.xaxis.set_label_coords(1.05, -0.025)
        line2, =self.widget_H.canvas.ax.plot(t, champH, label="H_brut")
        self.lines.append(line2)
        self.signals.append("H_brut")
        line2, =self.widget_H.canvas.ax.plot(t, champH_filtré, label="H_filtre")
        self.lines.append(line2)
        self.signals.append("H_filtre")
        self.widget_analyse.canvas.ax.legend()
        self.widget_H.canvas.draw()
        
        self.widget_analyse_2.canvas.ax.set_ylabel("B",rotation=0)
        self.widget_analyse_2.canvas.ax.yaxis.set_label_coords(0,1)
        self.widget_analyse_2.canvas.ax.set_xlabel("µs")
        self.widget_analyse_2.canvas.ax.xaxis.set_label_coords(1.05, -0.025)
        line3, =self.widget_analyse_2.canvas.ax.plot(t, champB, label="B_brut",)
        self.lines.append(line3)
        self.signals.append("B_brut")
        line3, =self.widget_analyse_2.canvas.ax.plot(t, champB_filtré, label="B_filtre")
        self.lines.append(line3)
        self.signals.append("B_filtre")
        self.widget_analyse.canvas.ax.legend()
        self.widget_analyse_2.canvas.draw()

    def clear_canva(self):
        self.widget_analyse.canvas.ax.clear()
        self.widget_analyse.canvas.ax.grid()
        self.widget_analyse.canvas.draw()
        
        self.widget_H.canvas.ax.clear()
        self.widget_H.canvas.ax.grid()
        self.widget_H.canvas.draw()
        
        self.widget_analyse_2.canvas.ax.clear()
        self.widget_analyse_2.canvas.ax.grid()
        self.widget_analyse_2.canvas.draw()
    
        self.label_Bmax_value_brut.setText(str(0))
        self.label_Hmax_value_brut.setText(str(0))
        self.label_Br_value_brut.setText(str(0))
        self.label_Hc_value_brut.setText(str(0))
        self.label_Area_value_brut.setText(str(0))
        self.label_Pv_value_brut.setText(str(0))
        self.label_Bmax_value_brut.setText(str(0))
        self.label_Hmax_value_brut.setText(str(0))
        self.label_Br_value_brut.setText(str(0))
        self.label_Hc_value_brut.setText(str(0))
        self.label_Area_value_brut.setText(str(0))
        self.label_Pv_value_brut.setText(str(0))
    
    def saves_project(self):
        # selected_dir = QtWidgets.QFileDialog.getExistingDirectory(
        #     self, 'Select a directory')
        # if selected_dir:
        # file_name = Nm_ref
        # project_dir = os.path.join(selected_dir, file_name)
        # if not os.path.exists(project_dir):
        #     os.makedirs(project_dir)
        # now = datetime.datetime.now()
        # date_time = now.strftime("%Y-%m-%d_%H-%M-%S")
        # settings = QSettings(os.path.join(
        #     project_dir, f"configuration_{date_time}.cfg"), QSettings.IniFormat)
        # settings.setValue("Nom_ref", Nm_ref)
        # settings.setValue("Materiaux_value", Materiaux)
        # settings.setValue("Hauteur_value", Hauteur)
        # settings.setValue("Di_value", Di)
        # settings.setValue("De_value", De)
        # settings.setValue("Section_value", Section)
        # settings.setValue("Outils_value", Outils)
        # settings.setValue("Ns1_value", Ns1)
        # settings.setValue("Ns2_value", Ns2)
        # settings.setValue("Rs_value", Rs)
        # settings.setValue("Rh_value", Rh)
        # settings.setValue("Type_value", Type)
        # settings.setValue("Forme_value", Forme)
        # settings.setValue("Freq_value", Freq)
        # settings.setValue("Ampli_value", Ampli)
        # settings.setValue("Gain_value", Gain)
        # settings.setValue("Nbre_periode_value", Nbre_periode)
        # settings.setValue("Nbre_enregist_value", Nbre_enregist)
        # settings.setValue("Kf_value", Kf)
        # settings.setValue("Mu_value", mu_r)
        # settings.setValue("lm_value", lm)

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
                  "temps (s)": self.timeC_filtre,
                  "ChampH (A/m)": self.champH_filtré,
                  "ChampB (T)": self.champB_filtré
              }
              print("self.timeC_filtre:",self.timeC_filtre)
              print("self.champH_filtré:",self.champH_filtré)
                      
              csv_file = Nm_ref +"Correction filtrage harmoniques"+ "_" + str(Materiaux) + "_" + str(Forme) + str(self.Frequence)+ " Hz" + "_" + str(round(self.Bmax, 3)) + " T" + ".csv"
              
              
              # config_path, _ = QFileDialog.getSaveFileName(self, "Save Result",csv_file, "CSV files (*.csv")
              # if not config_path:
              #     return
              #csv_file = QSettings(config_path, QSettings.IniFormat)
              selected_dir = QtWidgets.QFileDialog.getExistingDirectory(
                  self, 'Select a directory')
              
              csv_file = os.path.join(selected_dir, csv_file)

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
              # txt_file = os.path.join(project_dir, "Notes_"+str(date_time))
              # with open(txt_file, "w") as text_file:
              #     text_file.write(self.Notes)
        
        
        
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
        self.export_table_button.clicked.connect(self.export_table)
        self.signals = []
        self.lines = []

    def export_table(self):
        model = self.tableWidget.model()
        rows = model.rowCount()
        columns = model.columnCount()

        # Open file dialog to select save location
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            None, "Export Table to CSV", "Comparaison de courbes.csv", "CSV Files (*.csv)")

        if filename:
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)

                header_data = [model.headerData(
                    col, Qt.Horizontal) for col in range(columns)]
                writer.writerow(header_data)

                for row in range(rows):
                    row_data = []
                    for col in range(columns):
                        index = model.index(row, col)
                        data = model.data(index)
                        row_data.append(data)
                    writer.writerow(row_data)

    def add_row(self):
        self.tableWidget.insertRow(self.tableWidget.rowCount())

    def delete_row(self):
        indices = self.tableWidget.selectionModel().selectedRows()
        for each_row in reversed(sorted(indices)):
            if self.is_row_empty(each_row.row()) == False:
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
        Mu_r = variables.get("µr =")
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
                empty_row = None
        if self.tableWidget.rowCount() == None:
            self.tableWidget.insertRow(self.tableWidget.rowCount())
            empty_row = self.tableWidget.rowCount()
        self.tableWidget.setItem(empty_row, 0, QTableWidgetItem(file_name))
        self.tableWidget.setItem(
            empty_row, 1, QTableWidgetItem(str(round(float(bmax), 3))))
        self.tableWidget.setItem(empty_row, 2, QTableWidgetItem(freq))
        self.tableWidget.setItem(
            empty_row, 3, QTableWidgetItem(str(round(float(hc), 3))))
        self.tableWidget.setItem(
            empty_row, 4, QTableWidgetItem(str(round(float(br), 3))))
        self.tableWidget.setItem(
            empty_row, 5, QTableWidgetItem(str(round(float(hmax), 3))))
        self.tableWidget.setItem(empty_row, 6, QTableWidgetItem(Mu_r))
        self.tableWidget.setItem(
            empty_row, 7, QTableWidgetItem(str(round(float(W), 3))))
        self.tableWidget.setItem(
            empty_row, 8, QTableWidgetItem(str(round(float(Pv), 3))))

        # color = "#"+"%06x" % random.randint(0, 0xFFFFFF)
        color = basic_colors[empty_row]
        self.update_color(color, empty_row)

    def clear_canva(self):
        self.widget_cpr.canvas.ax.clear()
        self.widget_cpr.canvas.draw()
        for row in reversed(range(self.tableWidget.rowCount())):
            if self.is_row_empty(row) == False:
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

# class Worker2(QThread):
#     finished = pyqtSignal()

#     def __init__(self, parent=None):
#         super().__init__(parent=parent)
#         self.parent = parent

#     def run(self):
#         while(self.thread.isRunning()):
#             pass
    

class SupervisionWindow(QDialog, Ui_supervision):
    def __init__(self, main_window, *args, obj=None, **kwargs):
        super(SupervisionWindow, self).__init__(*args, **kwargs)
        global Freq_1,Freq_2,Freq_3,Freq_4,Freq_5,Freq_6,Freq_7,Freq_8,Freq_9,Freq_10
        global Ampli_1,Ampli_2,Ampli_3,Ampli_4,Ampli_5,Ampli_6,Ampli_7,Ampli_8,Ampli_9,Ampli_10
        global Freq_depart,Freq_fin,Ampli_depart,Ampli_fin,Mode_Lineaire,Mode_Auto,Freq_tab,Ampli_tab
        global Freq,Ampli, port_connection
        import time as tm

        
        
        self.setupUi(self)
        self.setWindowTitle("Supervision")
        self.main_window = main_window
        self.stop_button.clicked.connect(self.action_stop)
        self.stop = False
        self.ChampH = None
        self.ChampB = None
        self.derivChampB = None
        self.timeC = None
        self.thread = None
        self.show()

        serial_port = serial.tools.list_ports.comports()

        connect=0
        
        serial_port = serial.tools.list_ports.comports()
        
        for port in serial_port:
            print(f"{port.name} // {port.device} // D={port.description}")
            #if ser.read():
            if port.device[:-1]=="/dev/ttyUSB":
                ser = serial.Serial(port.device, baudrate=9600,timeout=1)
                ser.write(bytes.fromhex("0210"))
                
                read_bytes = ser.read().hex()
                # try:
                if len(read_bytes)==2:
                    port_connection=port.device
                    print("Ampli connecté")
                    connect=1
                    print(type(port_connection))
                    # self.parent.actionOutput.triggered.connect(Output(port_connection))
                    self.Output_button.clicked.connect(self.Output)
                # except:
                #     pass
        # self.Output_button.clicked.connect(self.Output(port_connection))
        if Mode_Auto=="Simple":
            print("mode Simple")
            if self.thread is None or not self.thread.isRunning():
                self.thread = Worker(self)
                self.thread.finished.connect(self.on_long_task_finished)
                self.thread.start()
                self.show()

        elif Mode_Auto=="Auto":
            print("mode Auto")
            # Freq_tab=[10,100]
            Freq=Freq_tab[0]
            Ampli=Ampli_tab[0]
            print("Frequence actuelle : ",Freq)
            print("amplitude actuelle : ",Ampli)
            if self.thread is None or not self.thread.isRunning():
                self.thread = Worker(self)
                self.thread.finished.connect(self.on_long_task_finished_Auto)
                self.thread.start()
                self.show()
        else:
            self.main_window.Button_start.setEnabled(True)
            self.thread = None
            self.main_window.plot_data(self.ChampH, self.ChampB)
            self.close()
                
        
    def Output(self):
        global port_connection
        # print("output")
        if self.Output_button.text()=="OFF":
            ser = serial.Serial(port_connection, baudrate=9600)
            ser.write(bytes.fromhex("033501"))

            ser.write(bytes.fromhex("0210"))
            ready=ser.read().hex()
            ready=list("{0:08b}".format(int(ready, 16)))

            if ready[0]=='1':
                self.Output_button.setStyleSheet("background-color : green")
                self.Output_button.setText("ON")
        
            
        else:
            self.Output_button.setText("OFF")
            self.Output_button.setStyleSheet("background-color : red")
            ser = serial.Serial(port_connection, baudrate=9600)
            ser.write(bytes.fromhex("033500"))

            ser.write(bytes.fromhex("0210"))
            ready=ser.read().hex()
            ready=list("{0:08b}".format(int(ready, 16)))

            if ready[0]=='0':
                self.Output_button.setStyleSheet("background-color : red")
                self.Output_button.setText("OFF")
            
        # ser.write(bytes.fromhex("0210"))

        # read_bytes = bin(int(ser.read().hex(),16))
        # print("output")

    def on_long_task_finished(self):
        self.main_window.Button_start.setEnabled(True)
        self.thread = None
        self.main_window.plot_data(self.ChampH, self.ChampB)
        self.close()
    
    def on_long_task_finished_Auto(self):
        global Freq_tab,Freq, Ampli_tab,Ampli, Freq_tab_tempo
        import time as tm

        self.thread = None
        self.close()
        self.main_window.saves_project_auto()
        print("freq tab : ",Freq_tab_tempo)
        print("amplitude tab : ",Ampli_tab)

        tm.sleep(1)
        if len(Ampli_tab)!=1:
            
            if len(Freq_tab)!=1:
                print("fréquence suivante")
                Freq_tab.pop(0)
                Freq=Freq_tab[0]
                # self.w = SupervisionWindow(self)
                # self.w.show()
                self.main_window.start()
            else:
                
                print("amplitude suivante")
                Ampli_tab.pop(0)
                Ampli=Ampli_tab[0]
                Freq_tab.pop(0)
                for i in Freq_tab_tempo:
                    Freq_tab.append(i)
                #Freq_tab=Freq_tab_tempo
                # self.w = SupervisionWindow(self)
                # self.w.show()
                self.main_window.start()
                            
        else:
            Freq_tab.pop(0)
            if len(Freq_tab)!=0 and len(Ampli_tab)!=0:
                #Freq_tab.pop(0)
                print("fréquence suivante fin")
                print(Freq_tab)
                Freq=Freq_tab[0]
                # self.w = SupervisionWindow(self)
                # self.w.show()
                self.main_window.start()
            else :
                print("Fin de séquence")
                self.main_window.Button_start.setEnabled(True)
                self.thread = None
                self.main_window.plot_data(self.ChampH, self.ChampB)
                self.close()

    def action_stop(self):
        self.stop = True
        self.stop_button.setEnabled(False)

    def closeEvent(self, event):
        self.stop = True
        self.stop_button.setEnabled(True)
        #self.main_window.Button_start.setEnabled(True)
        self.close()

class HelpWindow(QDialog, Ui_HelpWindow):
    def __init__(self, *args, parent=None, **kwargs):
        super(HelpWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)

class ErrorWindow(QDialog, Ui_error):
    def __init__(self, *args, parent=None, **kwargs):
        super(ErrorWindow, self).__init__(*args, **kwargs)
        global Erreur
        self.setupUi(self)
        # message=[(str(i)+" - "+Erreur[i]+"\n") for i in range(len(Erreur))]
        # print(message)
        for i in range(len(Erreur)):
            Erreur[i]=str(i)+" - "+Erreur[i]
        self.error_label.setText(str("\n".join(Erreur)))
        #self.error_label.setText(str(Erreur))

        Erreur.clear()

class MainWindow(QtWidgets.QMainWindow, Ui_JTcontrol):
    def __init__(self, *args, obj=None, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.setupUi(self)
        
        self.toolButton_Analyse.setIcon(QIcon('hibou.png'))    #### correction
        self.toolButton_Analyse.setIconSize(QSize(24, 24))     #### correction
                
        self.setWindowIcon(QIcon('Logo2.png'))
        self.setWindowTitle("MagHyster")
        self.toolButton_Comparaison.setIcon(QIcon('music.png'))
        self.toolButton_Comparaison.setIconSize(QSize(24, 24))
        self.toolButton_Save.setIcon(QIcon('diskette.png'))
        self.toolButton_Save.setIconSize(QSize(24, 24))
        #self.toolButton_Reset_Pico.setIcon(QIcon('reset.jpeg'))
        self.toolButton_Reset_Pico.setIconSize(QSize(24, 24))
        self.Button_start.clicked.connect(self.start)
        x = range(0, 10)
        y = range(0, 20, 2)
        self.Notes = ""
        self.plot_data(x, y)
        self._connectActions()

    def plot_data(self, x, y):
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
        
        self.actionAnalyse.triggered.connect(self.analyse)
        
        self.actionComparaison.triggered.connect(self.comparaison)
        self.actionNotes.triggered.connect(self.notes)
        self.actionReset_Pico.triggered.connect(self.reset_pico)
        self.actiondemag.triggered.connect(self.demag)
        self.actionManuel_d_Utilisation.triggered.connect(self.manuel)
        self.actionerror.triggered.connect(self.Error)
        self.actionPertesvsFreq.triggered.connect(self.PertesVsFreq)
        self.actionAmpli.triggered.connect(self.Ampli)
    
    def Ampli(self):
        self.w= AmpliWindow(self)
        self.w.show()
        
    def PertesVsFreq(self):
        self.w = PertesVsFreqWindow(self)
        self.w.show()

    def Error(self):
        self.w = ErrorWindow(self)
        self.w.show()

    def manuel(self):
        self.w = HelpWindow(self)
        self.w.show()

    def demag(self):
        from scipy.interpolate import interp1d
        import usbtmc
        import time as tm
        a,b = 0,5
        t = np.linspace(a,b,num=1000)
        # Boucherot
        #V=4.44*50*section*Ns1*Bsat
        entree = np.exp(-t) * np.cos(2*np.pi*t*50)

        entree=entree[:int(len(entree)/2)]
        Z=np.zeros(50)

        entree=[*entree, *Z] 
        t=t[:int(len(entree))]
        print("demagnetisation")
        
        # Fonction qui permets de diminuer le nombre de point du signal pour que
        # la fréquence d'échantillonnage ne dépasse pas 160 000 000 échantillons par seconde


        interpolation_entree = interp1d(t, entree)
        i = len(entree)
        while len(t)*50 > 159000000:
            # on suprime un point tant qu'on dépasse la la limite d'échantillonnage
            i -= 1
            t = np.linspace(0, 1/int(50), i)

        # On recalcule la nouvel entree avec moins de point (si nécessaire)
        entree = interpolation_entree(t)
        ##
        # with open('/home/caracterisation/Documents/Stage Evan Gossard/entree.npy', 'wb') as f:
        #     np.save(f, entree)
        # with open('/home/caracterisation/Documents/Stage Evan Gossard/time.npy', 'wb') as f:
        #     np.save(f, t)
            
            
        # Connection au GBF
        instr = usbtmc.Instrument(2391, 9991)  # Identifiant GBF
        # Supression des anciens messages d'erreures
        instr.write("DATA:VOL:CLE")
        index = 0
        message2 = 'DATA:ARB myArb'

        # Recherhce du max du signal d'entree
        if np.max(entree) > np.abs(np.min(entree)):
            pk = np.max(entree)
        else:
            pk = np.abs(np.min(entree))

        # envoi des valeurs du signal d'entree
        # A noter que les valeurs doivent être normaliser (entre 0 et 1)
        for nbre in entree:
            message2 = message2 + ', ' + \
                str("%.3f" % round(nbre/pk, 3))
            index += 1
        instr.timeout = 5000
        instr.write(message2)
        instr.write('FUNCtion:ARB "myArb"')
        # Définission des paramètres du GBF
        # Fréquence d'échantillonnage, Max amplitude, Offset
        #instr.write(f'APPLy:ARB {len(entree)*Frequence},{pk},{np.mean(entree)}')
        instr.write(f'APPLy:ARB {len(entree)*50},{pk},{0}')

        instr.write("OUTP ON")

        # Recherche des erreures
        rawError = ''
        errorCode = -1
        while errorCode != 0:
            instr.write('SYST:ERR?')
            rawError = instr.read()
            errorParts = rawError.split(',')
            errorCode = int(errorParts[0])
            errorMessage = errorParts[1].rstrip('\n')
            if not errorCode == 0:
                print('INSTRUMENT ERROR - Error code: %d, error message: %s' %
                      (errorCode, errorMessage))
                instr.write('*CLS')
                # Close the connection to the instrument
                instr.close()
                
                self.parent.ChampH = np.zeros(num_samples)
                self.parent.main_window.ChampH = np.zeros(num_samples)
                self.parent.ChampB = np.zeros(num_samples)
                self.parent.main_window.ChampB = np.zeros(num_samples)
                self.parent.main_window.derivChampB = np.zeros(num_samples)
                self.parent.main_window.update_mesures(1, 1, 1, 1, 1, 1, 1)
                self.finished.emit()
        instr.write('DISP OFF')
        tm.sleep(0.01)
        instr.write("OUTP OFF")

        instr.write('DISP:TEXT:CLE')
        instr.write('DISP ON')
        instr.close()



    def set_config(self):
        self.w = ConfigWindow(self)
        self.w.show()

    def update_data(self, Outils, Materiaux, Di, De, Hauteur, Section, lm, Kf):
        if (Outils == "Cadre Epstein personnalisé") or (Outils == "Cadre Epstein Standard"):
            self.Outils_value.setText("Cadre Epstein")
            self.Hauteur_label_main.setText("Epaisseur")
            self.Di_label_main.setText("Largeur")
            self.De_label_main.setText("Nbre de Bandes")
            self.De_value.setText(str((De)))
        else:
            self.Outils_value.setText(str(Outils))
            self.De_value.setText(str(De)+" mm")
            self.Hauteur_label_main.setText("Hauteur")
            self.Di_label_main.setText("Diamètre intérieur Di")
            self.De_label_main.setText("Diamètre extérieur De")
        self.Materiaux_value.setText(str(Materiaux))
        self.Di_value.setText(str(Di) + " mm")
        self.Hauteur_value.setText(str(Hauteur)+" mm")
        self.Section_value.setText(str(Section)+" mm²")
        self.lm_value.setText(str(lm)+" mm")
        self.Kf_value.setText(str(Kf))

    def update_mesures(self, bmax, Freq, hc, br, hmax, Mu_r, Pv):
        self.Bmax = bmax
        self.Frequence = Freq
        self.Hc = hc
        self.Br = br
        self.Hmax = hmax
        self.Mu = Mu_r
        self.Pv = Pv
        self.W = Pv/Freq
        self.Bmax_value.setText(str(round(self.Bmax, 3)))
        self.Freq_value.setText(str(round(self.Frequence, 2)))
        self.Hc_value.setText(str(round(self.Hc, 3)))
        self.Br_value.setText(str(round(self.Br, 3)))
        self.Hmax_value.setText(str(round(self.Hmax, 3)))
        self.Mu_value.setText(str(round(self.Mu, 0)))
        self.W_value.setText(str(round(self.W, 3)))
        self.Pv_value.setText(str(round(self.Pv, 3)))

    def acquisition(self):
        self.w = AcquisWindow()
        self.w.show()

    def reset_pico(self):
        print("reset")
        sudoPassword = 'Magnetique'
        command = '''/home/caracterisation/Documents/'Stage Evan Gossard'/Reset_Pico.sh'''
        os.system('echo %s|sudo -S %s' % (sudoPassword, command))

    def analyse(self):
        self.w = AnalyseWindow()
        self.w.show()
    
    def comparaison(self):
        self.w = ComparWindow()
        self.w.show()

    def notes(self):
        self.win = NotesWindow(self)
        self.win.show()

    def opens_config(self):
        global Materiaux, Hauteur, Di, De, Section, Outils, Ns1, Ns2, Rs, Rh, Type, Forme, Freq, Ampli, Gain, Nbre_periode, Nbre_enregist, Nm_ref, mu_r, Kf, num_samples, alpha, beta, lm, gamma
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
        mu_r = int(settings.value("Mu_value", 0))
        lm = float(settings.value("lm_value", 0))
        #alpha = ((Rs+Rh)*lm*1e-3/(mu_r*mu_0*Ns1))
        #beta = (Ns1*Section*(1e-6))
        alpha = 0.5
        beta = 0.5
        gamma= 10
        # if Freq>50e3:
        #     num_samples = Nbre_periode//(Freq*8e-9)

        self.update_data(Outils, Materiaux, Di, De, Hauteur, Section, lm, Kf)

    def saves_config(self):
        now = datetime.datetime.now()
        date_time = now.strftime("%Y-%m-%d_%H-%M-%S")
        config_path, _ = QFileDialog.getSaveFileName(
            self, f'{Nm_ref}','Save Configuration', f"configuration_{date_time}.cfg", 'Config Files (*.cfg)')
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
        settings.setValue("lm_value", lm)
        settings.setValue("Mu_value", mu_r)

    def saves_project(self):
        # selected_dir = QtWidgets.QFileDialog.getExistingDirectory(
        #     self, 'Select a directory')
        # if selected_dir:
            # file_name = Nm_ref
            # project_dir = os.path.join(selected_dir, file_name)
            # if not os.path.exists(project_dir):
            #     os.makedirs(project_dir)
            # now = datetime.datetime.now()
            # date_time = now.strftime("%Y-%m-%d_%H-%M-%S")
            # settings = QSettings(os.path.join(
            #     project_dir, f"configuration_{date_time}.cfg"), QSettings.IniFormat)
            # settings.setValue("Nom_ref", Nm_ref)
            # settings.setValue("Materiaux_value", Materiaux)
            # settings.setValue("Hauteur_value", Hauteur)
            # settings.setValue("Di_value", Di)
            # settings.setValue("De_value", De)
            # settings.setValue("Section_value", Section)
            # settings.setValue("Outils_value", Outils)
            # settings.setValue("Ns1_value", Ns1)
            # settings.setValue("Ns2_value", Ns2)
            # settings.setValue("Rs_value", Rs)
            # settings.setValue("Rh_value", Rh)
            # settings.setValue("Type_value", Type)
            # settings.setValue("Forme_value", Forme)
            # settings.setValue("Freq_value", Freq)
            # settings.setValue("Ampli_value", Ampli)
            # settings.setValue("Gain_value", Gain)
            # settings.setValue("Nbre_periode_value", Nbre_periode)
            # settings.setValue("Nbre_enregist_value", Nbre_enregist)
            # settings.setValue("Kf_value", Kf)
            # settings.setValue("Mu_value", mu_r)
            # settings.setValue("lm_value", lm)

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
            
                    
            csv_file = Nm_ref + "_" + str(Materiaux) + "_" + str(Forme) + "_" + str(
                self.Frequence)+ " Hz" + "_" + str(round(self.Bmax, 3)) + " T" + ".csv"
            
            
            # config_path, _ = QFileDialog.getSaveFileName(self, "Save Result",csv_file, "CSV files (*.csv")
            # if not config_path:
            #     return
            #csv_file = QSettings(config_path, QSettings.IniFormat)
            selected_dir = QtWidgets.QFileDialog.getExistingDirectory(
                self, 'Select a directory')
            
            csv_file = os.path.join(selected_dir, csv_file)

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
            # txt_file = os.path.join(project_dir, "Notes_"+str(date_time))
            # with open(txt_file, "w") as text_file:
            #     text_file.write(self.Notes)

    def saves_project_auto(self):
        global selected_dir
        # selected_dir = QtWidgets.QFileDialog.getExistingDirectory(
        #     self, 'Select a directory')
        #selected_dir='/home/caracterisation/Bureau/Interface_UI/Ferrite_N49/Fichier auto'
        if selected_dir:
            file_name = Nm_ref
            project_dir = os.path.join(selected_dir, file_name)
            if not os.path.exists(project_dir):
                os.makedirs(project_dir)
            # now = datetime.datetime.now()
            # date_time = now.strftime("%Y-%m-%d_%H-%M-%S")
            # settings = QSettings(os.path.join(
            #     project_dir, f"configuration_{date_time}.cfg"), QSettings.IniFormat)
            # settings.setValue("Nom_ref", Nm_ref)
            # settings.setValue("Materiaux_value", Materiaux)
            # settings.setValue("Hauteur_value", Hauteur)
            # settings.setValue("Di_value", Di)
            # settings.setValue("De_value", De)
            # settings.setValue("Section_value", Section)
            # settings.setValue("Outils_value", Outils)
            # settings.setValue("Ns1_value", Ns1)
            # settings.setValue("Ns2_value", Ns2)
            # settings.setValue("Rs_value", Rs)
            # settings.setValue("Rh_value", Rh)
            # settings.setValue("Type_value", Type)
            # settings.setValue("Forme_value", Forme)
            # settings.setValue("Freq_value", Freq)
            # settings.setValue("Ampli_value", Ampli)
            # settings.setValue("Gain_value", Gain)
            # settings.setValue("Nbre_periode_value", Nbre_periode)
            # settings.setValue("Nbre_enregist_value", Nbre_enregist)
            # settings.setValue("Kf_value", Kf)
            # settings.setValue("Mu_value", mu_r)
            # settings.setValue("lm_value", lm)

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

            csv_file = Nm_ref + "_" + str(Materiaux) + "_" + str(Forme) + "_" + str(
                self.Frequence) + "_" + str(round(self.Bmax, 3)) + ".csv"
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
                    
    def saves_sequence(self):
        global selected_dir, Freq_tab, Ampli_tab
        config_path, _ = QFileDialog.getSaveFileName(
            self, 'Save Configuration', "sequence.cfg", 'Config Files (*.cfg)')
        if not config_path:
            return
        selected_dir=os.path.split(config_path)
        selected_dir=selected_dir[0]
        settings = QSettings(config_path, QSettings.IniFormat)
        str_freq=""
        for i in Freq_tab:
            str_freq=str_freq+"/"+str(i)
        str_ampli=""
        for i in Ampli_tab:
            str_ampli=str_ampli+"/"+str(i)
        settings.setValue("Frequence", str_freq)
        settings.setValue("Amplitude", str_ampli)
        
    def Verification_Erreur(self):
        global Materiaux, Hauteur, Di, De, Section, Outils, Ns1, Ns2, Rs, Rh, Type, Forme, Freq, Ampli, Gain, Nbre_periode, Nbre_enregist, Nm_ref, mu_r, Kf, num_samples, alpha, beta, lm, gamma,Sonde
        Param=[Hauteur, Di, De, Section, Ns1, Ns2, Rs, Rh, Freq, Ampli, Gain, Nbre_periode, Nbre_enregist, mu_r, Kf, num_samples, alpha, beta, lm, gamma]         
        Param_str=["Hauteur", "Di", "De", "Section", "Ns1", "Ns2", "Rs", "Rh", "Freq", "Ampli", "Gain", "Nbre_periode", "Nbre_enregist", "mu_r", "Kf", "num_samples", "alpha", "beta", "lm", "gamma"]
        
        for i in range(len(Param)):
            if Param[i]==0:
                Erreur.append(Param_str[i]+" non renseigné")
        
        if De<Di:
            Erreur.append("De < Di")
        
        if Sonde=="1":
            Sonde=1
        elif Sonde=="1/10":
            Sonde=0.1
        elif Sonde=="1/100":
            Sonde=0.01
    
        if (4.44*Ns2*Section*1e-6*Ampli*Freq*1000*np.sqrt(2)*Sonde)>=20:
            Erreur.append("Limite de tension atteinte")
 
        
        if Erreur:
            #self.Error()
            raise Exception (Erreur)

    def start(self):
        global Mode_Auto, selected_dir
        self.Verification_Erreur()
        if Mode_Auto=="Auto" and selected_dir=="":
            #selected_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select a directory')
            self.saves_sequence()
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
