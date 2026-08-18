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
from page_acquisition import Ui_Page_acquisition
from configuration import Ui_Dialog
from Notes import Ui_notes
from curve_comparaison import Ui_curve_comparaison
from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtWidgets import QColorDialog, QTableWidgetItem, QDialogButtonBox, QComboBox, QDialog, QGridLayout, QPushButton, QFileDialog, QVBoxLayout
from PyQt5.QtCore import QThread, pyqtSignal, QSettings, QSize, Qt
import numpy as np
import csv
# Initialisation paramètres
Hauteur = Di = De = Section = Rs = Rh = Freq = Ampli = Gain = Nbre_enregist = mu_r = lm = Epaisseur = Nbre_Bandes = Largeur = alpha = beta = cycle = 0
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

ChampBdes = timeC = func_eval = 0

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

Fourier_test = []


class Worker(QThread):
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
        global Materiaux, Hauteur, Di, De, Section, Outils, Ns1, Ns2, Rs, Rh, Type, Forme, Freq, Ampli, Gain, Nbre_periode, Kf, Nm_ref, mu_r, lm, num_samples, Resolution, Nbre_enregist, alpha, beta, rampe, iteration_max, cycle
        import ctypes
        import usbtmc
        import time as tm
        from scipy import integrate
        from scipy.signal import detrend, correlate, correlation_lags, blackmanharris, hilbert, savgol_filter, sawtooth
        from scipy.interpolate import interp1d
        from scipy.fft import fft, rfft, irfft
        from picosdk.ps5000a import ps5000a as ps
        import matplotlib.pyplot as plt
        from picosdk.functions import adc2mV, assert_pico_ok
        from numpy import linalg as LA
        from numpy.fft import fft, ifft
        from scipy import signal
        
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
            for i in range(len(an)):
                if i % 2 == 0:
                    an[i] = 0
                    bn[i] = 0
            return np.concatenate((an, bn))

        def compute_fft_signals(B_des, B_reel, V1_sim, dB_des, dB_reel):
            # Calcul des coefficients de Fourier de la référence de B
            an_B_ref = 2*np.real(np.fft.rfft(B_des))/len(B_des)
            bn_B_ref = -2*np.imag(np.fft.rfft(B_des))/len(B_des)
            Fourier_B_des = symetrie(an_B_ref, bn_B_ref)
            # Calcul des coefficients de Fourier de B obtenu
            an_B_sim = 2*np.real(np.fft.rfft(B_reel))/len(B_reel)
            bn_B_sim = -2*np.imag(np.fft.rfft(B_reel))/len(dB_reel)
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

            return Fourier_dB_des, Fourier_dB_reel, Fourier_B_des, Fourier_B_reel, Fourier_V_reel

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

        def GBF(entree):
            """
            Envoie le signal en entrée du GBF (sous forme d'un tableau de point)
            Le GBF prend en compte la fréquence d'échantillonnage et le nombre de point pour générer le signal. 
            La fréquence d'échantillonnage est bloqué à 160 000 000 échantillon par seconde.
            Le paramètre len(entree)*Frequence permet de calculer de calculer la fréquence d'échantillonnage,
            Donc lo'rsque l'on veut augmenter la fréquence, il faut diminuer le nombre de point à envoyer.
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

            # On recalcule la nouvel entree avec moins de point (si nécessaire)
            entree = interpolation_entree(t)
            ##
            # with open('entree.npy', 'wb') as f:
            #     np.save(f, entree)
            # with open('time.npy', 'wb') as f:
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
                    str("%.2f" % round(nbre/np.max(entree), 3))
                index += 1
            instr.timeout = 5000
            instr.write(message2)
            instr.write('FUNCtion:ARB "myArb"')
            # Définission des paramètres du GBF
            # Fréquence d'échantillonnage, Max amplitude, Offset
            instr.write(f'APPLy:ARB {len(entree)*Frequence},{pk},{np.mean(entree)}')
            instr.write(f'APPLy:ARB {len(entree)*Frequence},{pk},{0}')

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

            chandle = ctypes.c_int16()
            status = {}
            resolution = ps.PS5000A_DEVICE_RESOLUTION["PS5000A_DR_" +
                                                      str(Num_resolution)+"BIT"]

            status["openunit"] = ps.ps5000aOpenUnit(
                ctypes.byref(chandle), None, resolution)

            # if pk > 10:
            #     entree = (entree/pk)*10

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

            V1 = [adc2mVChAMax, np.negative(
                adc2mVChBMax), np.negative(adc2mVChBMax/Rs)]  # tension au primaire du transformateur

            V1 = np.sum(V1, axis=0)  # Somme le long des colonnes

            V2 = adc2mVChCMax  # Tension en sortie de transformateur
            print(np.amax(V1)/1000)
            print(np.amax(V2)/1000)
            # Calcule du déphasage entre V1 et V2
            signal_correle = np.correlate(V1, V2, "same")
            lags = correlation_lags(V1.size, V2.size)
            lag = lags[np.argmax(signal_correle)]

            # On inverse la tension V2 si les bornes ne sont pas homologuées
            if lag <= -num_samples/2:
                Bornes_homologues = "oui"
                adc2mVChCMax = adc2mVChCMax
            else:
                Bornes_homologues = "non"
                adc2mVChCMax = np.negative(adc2mVChCMax)

            #adc2mVChBMax = np.negative(adc2mVChBMax)
            #adc2mVChBMax=np.roll(adc2mVChBMax,2500)

            return adc2mVChBMax, adc2mVChCMax

        def Detection_Bornes2(adc2mVChAMax, adc2mVChBMax, adc2mVChCMax):
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

            V1 = [adc2mVChAMax, np.negative(adc2mVChBMax/Rsh)]  # tension au primaire du transformateur

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
            # On inverse la tension V2 si les bornes ne sont pas homologuées
            if lag >= num_samples/2:
                Bornes_homologues = "oui"
                adc2mVChCMax = adc2mVChCMax
            else:
                Bornes_homologues = "non"
                adc2mVChCMax = np.negative(adc2mVChCMax)

            #adc2mVChBMax = np.negative(adc2mVChBMax)
            #adc2mVChBMax=np.roll(adc2mVChBMax,2500)
            #print('bornes homoogues : ',Bornes_homologues)
            return adc2mVChBMax, adc2mVChCMax

        def start_from_zero(sig):
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

            #ChampB = savgol_filter(ChampB, window_length=10, polyorder=3, mode="wrap")

            return ChampB, lag

        def compute_convergence_criteria(dB_dt_ref_sim, dB_dt_sim, B_ref_sim, B_sim, temps_sim):
            # #Calcul des écarts
            delta_B = B_ref_sim - B_sim  # Vecteur de la sortie de la fonction à minimiser
            # Vecteur de la sortie de la fonction à minimiser
            delta_dB = (dB_dt_ref_sim - dB_dt_sim)/np.max(dB_dt_ref_sim)
            # Calcul de delta_V (incr�ment � ajouter au signal)
            RMSE = 100*np.sqrt(np.mean(delta_dB*delta_dB))
            FF_reel = np.sqrt(integrate.trapz((dB_dt_sim**2), temps_sim)/(max(temps_sim)-min(temps_sim))) / (
                integrate.trapz(np.abs(dB_dt_sim), temps_sim)/(max(temps_sim)-min(temps_sim)))
            FF_theo = np.sqrt(integrate.trapz((dB_dt_ref_sim**2), temps_sim)/(max(temps_sim)-min(temps_sim))) / (
                integrate.trapz(np.abs(dB_dt_ref_sim), temps_sim)/(max(temps_sim)-min(temps_sim)))
            FF = 100*np.abs(FF_reel-FF_theo)/FF_theo
            err_dB_amp = 100 * \
                np.abs((np.max(dB_dt_ref_sim)-np.max(dB_dt_sim)) /
                       np.max(dB_dt_ref_sim))
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
            global rampe, cycle, alpha, beta
            #coef = 2  # réglage fait sur un échantillonnage de 5000 à une fréquence de 10 KHz
            coef = 1
            #coef = 2*Frequence*num_samples/(10000*5000)
            # print("Coef : ",coef)

            Fourier_dB_des, Fourier_dB_reel, Fourier_B_des, Fourier_B_reel, Fourier_V = compute_fft_signals(
                ChampBdes, ChampB[:samples_per_period], entree, derivChampBdes, derivChampB[:samples_per_period])
            RMSE, err_dB_amp = compute_convergence_criteria(
                derivChampBdes, derivChampB[:samples_per_period], ChampBdes, ChampB[:samples_per_period], timeC[:samples_per_period])

            #RMSE=math.sqrt(np.square(np.subtract(ChampB, ChampBdes)/np.max(ChampBdes)).mean())*100

            if Mode_asservissement == 'PI_FFT':
                rampe_alpha = np.concatenate(
                    (np.linspace(0.1, alpha, num=rampe), alpha*np.ones(iteration_max)))
                rampe_beta = np.concatenate(
                    (np.linspace(0.1, beta, num=rampe), beta*np.ones(iteration_max)))
                rampe_alpha *= reinit
                rampe_beta *= reinit

                if Forme == 'Sinusoïdale B':

                    if RMSE < 0.1 and cycle > 1:
                        alpha_prim = 0.6*rampe_alpha[cycle]*coef
                        beta_prim = 0.4*rampe_beta[cycle]/coef
                        print("allure réduite")

                    else:
                        alpha_prim = 1*rampe_alpha[cycle]*coef
                        beta_prim = 1*rampe_beta[cycle]/coef
                        print("allure normale")

                if Forme == 'Triangulaire B':
                    if RMSE < 40 and cycle > 1:
                        alpha_prim = 1*rampe_alpha[cycle]*coef
                        beta_prim = 0.7*rampe_beta[cycle]/coef
                        print("allure réduite")

                    else:
                        alpha_prim = 1*rampe_alpha[cycle]*coef
                        beta_prim = 1*rampe_beta[cycle]/coef
                        print("allure normale")

                Fourier_e_k = Fourier_V + alpha_prim * (Fourier_B_des-Fourier_B_reel)/np.max(
                    Fourier_B_des) + beta_prim * (Fourier_dB_des-Fourier_dB_reel)/np.max(Fourier_dB_des)

                e_k = 0.5*len(entree)*np.fft.irfft(Fourier_e_k[0:int(
                    len(Fourier_e_k)/2)] - 1j * Fourier_e_k[int(len(Fourier_e_k)/2):])
                entree = e_k

                delta_B = np.max(
                    (Fourier_B_des-Fourier_B_reel) / np.max(Fourier_B_des))
                delta_dB = np.max(
                    (Fourier_dB_des-Fourier_dB_reel)/np.max(Fourier_dB_des))
                RMSE_memoire.append(RMSE)
                entree_memoire.append(entree)
                delta_B_memoire.append(delta_B)
                delta_dB_memoire.append(delta_dB)
                
                if Forme == 'Sinusoïdale B':
                    if (THDN(derivChampB, num_samples) > 8 or np.max(ChampB) > 1.5*Ampli or np.max(derivChampB) > np.max(derivChampBdes)*1.5 or RMSE > np.min(RMSE_memoire)) and cycle > 2:
                    #if ( RMSE > np.min(RMSE_memoire)) and cycle > 2:
    
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
                        reinit *= 0.5
                    else:
                        cycle += 1

                elif Forme == 'Triangulaire B':
                    if (THDN(derivChampB, num_samples) > 30 or np.max(ChampB) > 1.2*Ampli or np.max(derivChampB) > np.max(derivChampBdes)*1.2 or RMSE > np.min(RMSE_memoire)) and cycle > 2:
                        print("init")
                        indice = np.argmin(RMSE_memoire)
                        entree = entree_memoire[indice]
                        cycle = 0
                        reinit *= 0.75
                    else:
                        cycle += 1

            elif Mode_asservissement == 'FFT_QN_dB_B':
                rampe = np.concatenate(
                    (np.linspace(0.1, 0.3, num=5), 0.5*np.ones(50)))

                f_n = np.concatenate(((Fourier_dB_des - Fourier_dB_reel)/np.max(Fourier_dB_des), (Fourier_B_des -
                                     Fourier_B_reel)/np.max(Fourier_B_des)))  # On sauvegarde l'écart sur la sortie f(x)
                if iteration < 2:
                    gamma = 0.2

                else:
                    gamma = 0.5

                #gamma = rampe[cycle]
                #print('Mat_Broyden=',np.shape(Mat_Broyden),'f_n=',np.shape(f_n), 'nb_points_dB', np.shape(derivChampB[:samples_per_period]) )
                # Calcul de la direction
                Fourier_dk = - gamma * Mat_Broyden  @ (f_n)

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
                #Mat_Broyden= Mat_Broyden + (Fourier_dk - Mat_Broyden @ delta_f )/(delta_f.T @ delta_f)@delta_f.T

                # a=(Fourier_dk - Mat_Broyden @ delta_f )
                # print('f_n= ', f_n.shape)

                # print('Fourier_dk= ', Fourier_dk.shape)
                # print('Mat_Broyden= ', Mat_Broyden.shape)

                # print('a= ', a.shape)
                # print('delta_f= ', delta_f.shape)

                # b=np.outer(a,delta_f)
                # print('b= ', b.shape)

                # c=b/(delta_f.T @ delta_f)
                # print('c= ', c.shape)
                # Mat_Broyden= Mat_Broyden + c

                print('conditionnement matrice = ',
                      np.linalg.cond(Mat_Broyden))
                f_0 = f_n  # Pour garder en mémoire la sortie pouyr la prochaine itération

            entree = entree+alpha*(ChampBdes-ChampB)/np.max(ChampBdes) + \
                beta*(derivChampBdes-derivChampB)/np.max(derivChampBdes)
            

            print('iter=', iteration, 'Amp_V=', round(np.max(entree), 3), 'delta_B=', round(np.max((Fourier_B_des-Fourier_B_reel) /
                                                                                                   np.max(Fourier_B_des)), 3), 'delta_dB=', round(np.max((Fourier_dB_des-Fourier_dB_reel)/np.max(Fourier_dB_des)), 3))
            print ('RMSE ',RMSE )

            return entree, RMSE

        def Visualisation(entree):
            # Envoie du signal au GBF
            GBF(entree)

            # Acquisition des données

            BufferMax, cmaxSamples, timeIntervalns = Mesure(
                Selection_Channel, Channel_ranges)

            # Moyenne des Nbre_enregistrement pour lisser le signal
            adc2mVChAMax = np.mean(BufferMax[0], axis=0)
            adc2mVChBMax = np.mean(BufferMax[1], axis=0)
            adc2mVChCMax = np.mean(BufferMax[2], axis=0)
            # print('V2 max réel : ',np.max(adc2mVChCMax)*1e-3)
            # print('V2 max théorique : ',Section*1e-6*Frequence*2*np.pi*N2*Amplitude)
            # print('V1 max réel : ',np.max(adc2mVChAMax)*1e-3)
            


            # Tableau contenant le nombre d'échantillon obtenu avec un pas régulier de TimeIntervalns
            timeI, interval = np.linspace(0, (cmaxSamples.value - 1) *
                                          timeIntervalns.value, cmaxSamples.value, retstep=True)
            #plt.plot(timeI,adc2mVChAMax)
            # On récupère la plage de temps pour ne garder qu'une période
            # Récupère le première indice supérieur à la période
            samples_per_period = np.where(
                timeI > (1/(Frequence)*1e9))[0][0]-1

            # Interpolation des signaux en vu d'avoir plus de point si nécessaire
            adc2mVChAMa = interp1d(timeI, adc2mVChAMax, kind='quadratic')
            adc2mVChBMa = interp1d(timeI, adc2mVChBMax, kind='quadratic')
            adc2mVChCMa = interp1d(timeI, adc2mVChCMax, kind='quadratic')
            x = num_samples
            
            # Diminution du nombre de point pour avoir le bon nombre de point dans une période
            while samples_per_period != num_samples//Nbre_periode:
                x -= 1
                if x<=10:
                    x=2*num_samples
                timeI, interval = np.linspace(
                    0, timeI[-1], x, retstep=True)
                samples_per_period = np.where(
                    timeI > (1/(Frequence)*1e9))[0][0]-1
            
            samples_per_period = np.where(
                timeI > (1/(Frequence)*1e9))[0][0]-1
            # print(interval)
            # print(samples_per_period*interval*1e-9)
            # print(1/(samples_per_period*interval*1e-9))
            # recalcule des signaux avec la nouvelle base de temps
            adc2mVChAMax = adc2mVChAMa(timeI)
            adc2mVChBMax = adc2mVChBMa(timeI)
            adc2mVChCMax = adc2mVChCMa(timeI)
            
            # Détection Bornes hanalogues
            # 0 pour bornes inversées et 1 pour bornes hanalogues
            adc2mVChBMax, adc2mVChCMax = Detection_Bornes2(
                adc2mVChAMax, adc2mVChBMax, adc2mVChCMax)


            # Détermination de la composante continue
            # MoyenneA = (np.max(adc2mVChAMax)+np.min(adc2mVChAMax))/2
            # MoyenneB = (np.max(adc2mVChBMax)+np.min(adc2mVChBMax))/2
            # MoyenneC = (np.max(adc2mVChCMax)+np.min(adc2mVChCMax))/2
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
            # Signal_sans_moyenne = detrend(
            #     samples_to_plotC, type='constant')
            # integral = integrate.cumulative_trapezoid(
            #     (Signal_sans_moyenne)/1000, timeC, initial=0)
            integral = integrate.cumtrapz(
                (samples_to_plotC)/1000, timeC, initial=0)
            # integral = np.trapz((Signal_sans_moyenne)/1000)

            # récupération de la fonction interpolée f2 calculé en début de PRGM,
            # On adapte notre dérivée à l'axe des temps


            Maxi = np.max(integral)
            Mini = np.min(integral)
            # Supression de la composante continue (Une deuxième fois ???)
            integral_corrige = integral-((Mini+Maxi)/2)
            ChampB = integral_corrige/(-N2*Section*1e-6)

            derivChampB = samples_to_plotC / \
                (-N2*Section*1e-6*1000)  # Sample_to_Plot_C = U2
            
            # Divisé par 1000 pour transformer les miliVolt en volt
            # 1.3 pour shunt1
            # 2.17 pour le shunt2
            ih = samples_to_plotB/(Rsh*1000)

            ChampH2 = N1*ih/(lm*1e-3)
            #ChampH2 = savgol_filter(ChampH2, window_length=100, polyorder=3, mode="wrap")
            
            fft_ChampdB = fft(ChampB[:samples_per_period])
            fft_ChampH = fft(ChampH2[:samples_per_period])

            # recherche du fondamentale pour obtenir deux signaux simples
            fond_ChampdB = np.zeros(len(fft_ChampdB))
            fond_ChampdB[np.argmax(np.abs(fft_ChampdB))] = np.max(
                np.abs(fft_ChampdB))
            fond_ChampH = np.zeros(len(fft_ChampH))
            fond_ChampH[np.argmax(np.abs(fft_ChampH))] = np.max(
                np.abs(fft_ChampH))
            
            # Transformée de Fourier inverse
            ChampdB_prim = ifft(
                fond_ChampdB*np.exp(1j*np.angle(fft_ChampdB))).real
            ChampH_prim = ifft(
                fond_ChampH*np.exp(1j*np.angle(fft_ChampH))).real

            
            try:
                _, a = start_from_zero(ChampdB_prim)
                _, b = start_from_zero(ChampH_prim)
            
                lag_dB_H=b-a
                #lag_dB_H=587
            except:
                lag_dB_H=0
            
            print('lag_dB_H : ',lag_dB_H*interval*1e-9)
            ChampH2 = savgol_filter(ChampH2, window_length=100, polyorder=3, mode="wrap")

            return ChampB,ChampH2,derivChampB

            
            
            
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

        Mat_Broyden = np.hstack((np.eye(num_Fourier), np.eye(num_Fourier)))
        f_0 = np.zeros(num_Fourier*2)
        cycle = indice = 0
        reinit = 1
        entree_memoire = []
        delta_B_memoire = []
        delta_dB_memoire = []
        RMSE_memoire = []

        # Création du signal désirée
        if Forme == 'Sinusoïdale B':
            ChampBdes = Amplitude*np.sin(w*t)
            entree = Amplitude*np.sin(w*t)

        elif Forme == 'Triangulaire B':
            # 1/2 pour éviter de dépasser la limite du GBF
            ChampBdes = Amplitude*sawtooth(w*t+np.pi/2, 0.5)
            entree = Amplitude*sawtooth(w*t+np.pi/2, 0.5)

        elif Forme == 'Trapézoïdal B':
            ChampBdes = trapzoid_signal(w*t, np.pi/4, 0.05, Amplitude)
            entree = trapzoid_signal(w*t, np.pi/4, 0.05, Amplitude)

        #ChampBdes=savgol_filter(ChampBdes, window_length=200, polyorder=3, mode="wrap")

        # Calcule Dérivée du champ B désiré
        deriv = np.diff(ChampBdes) / np.diff(t)
        derivChampBdes = np.insert(deriv, 0, deriv[0])

        # Interpolation des signaux dans le but d'être plus fléxible sur le nombre d'échantillon
        f2 = interp1d(t, derivChampBdes)
        f3 = interp1d(t, ChampBdes)
        f1 = interp1d(t, entree)

        #try:
            # début de la boucle d'acquisition
        while True:
            # Envoie du signal au GBF
            GBF(entree)

            # Acquisition des données

            BufferMax, cmaxSamples, timeIntervalns = Mesure(
                Selection_Channel, Channel_ranges)

            # Moyenne des Nbre_enregistrement pour lisser le signal
            adc2mVChAMax = np.mean(BufferMax[0], axis=0)
            adc2mVChBMax = np.mean(BufferMax[1], axis=0)
            adc2mVChCMax = np.mean(BufferMax[2], axis=0)
            # print('V2 max réel : ',np.max(adc2mVChCMax)*1e-3)
            # print('V2 max théorique : ',Section*1e-6*Frequence*2*np.pi*N2*Amplitude)
            # print('V1 max réel : ',np.max(adc2mVChAMax)*1e-3)
            


            # Tableau contenant le nombre d'échantillon obtenu avec un pas régulier de TimeIntervalns
            timeI, interval = np.linspace(0, (cmaxSamples.value - 1) *
                                          timeIntervalns.value, cmaxSamples.value, retstep=True)
            #plt.plot(timeI,adc2mVChAMax)
            # On récupère la plage de temps pour ne garder qu'une période
            # Récupère le première indice supérieur à la période
            samples_per_period = np.where(
                timeI > (1/(Frequence)*1e9))[0][0]-1
            print("samples_per_period : ",samples_per_period)
            downsampling=len(timeI)
            #if samples_per_period<num_samples//2:
            # # Interpolation des signaux en vu d'avoir plus de point si nécessaire
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
            # # print(interval)
            # # print(samples_per_period*interval*1e-9)
            # # print(1/(samples_per_period*interval*1e-9))
            # # recalcule des signaux avec la nouvelle base de temps
            adc2mVChAMax = adc2mVChAMa(timeI)
            adc2mVChBMax = adc2mVChBMa(timeI)
            adc2mVChCMax = adc2mVChCMa(timeI)
            #adc2mVChAMax = signal.resample_poly(adc2mVChAMax, len(timeI), downsampling)
            #adc2mVChBMax = signal.resample_poly(adc2mVChBMax, len(timeI), downsampling)
            #adc2mVChCMax = signal.resample_poly(adc2mVChCMax, len(timeI), downsampling)
            #sos = signal.butter(100, 5000, 'lp', fs=1/(1/Frequence/num_samples), output='sos') 
            # Filter the signal by the filter using signal.sosfilt 
            # Use signal.sosfiltfilt to get output inphase with input 
            #adc2mVChCMax = signal.sosfiltfilt(sos, adc2mVChCMax) 
            
                
            
            # Détection Bornes hanalogues
            # 0 pour bornes inversées et 1 pour bornes hanalogues
            adc2mVChBMax, adc2mVChCMax = Detection_Bornes2(
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
            # Signal_sans_moyenne = detrend(
            #     samples_to_plotC, type='constant')
            # integral = integrate.cumulative_trapezoid(
            #     (Signal_sans_moyenne)/1000, timeC, initial=0)
            integral = integrate.cumtrapz(
                (samples_to_plotC)/1000, timeC, initial=0)
            # integral = np.trapz((Signal_sans_moyenne)/1000)

            # récupération de la fonction interpolée f2 calculé en début de PRGM,
            derivChampBdes = f2(timeC[:samples_per_period])
            # On adapte notre dérivée à l'axe des temps

            ChampBdes = f3(timeC[:samples_per_period])

            Maxi = np.max(integral)
            Mini = np.min(integral)
            # Supression de la composante continue (Une deuxième fois ???)
            integral_corrige = integral-((Mini+Maxi)/2)
            ChampB = integral_corrige/(-N2*Section*1e-6)

            derivChampB = samples_to_plotC / \
                (-N2*Section*1e-6*1000)  # Sample_to_Plot_C = U2
            
            # Divisé par 1000 pour transformer les miliVolt en volt
            ih = samples_to_plotB/(Rsh*1000)

            ChampH2 = N1*ih/(lm*1e-3)



            #### Récupération décalage dB et H
            #ChampH2 = savgol_filter(ChampH2, window_length=100, polyorder=3, mode="wrap")

            # # On applique la transformer de Fourier
            # fft_ChampdB = fft(ChampB[:samples_per_period])
            # fft_ChampH = fft(ChampH2[:samples_per_period])

            # # recherche du fondamentale pour obtenir deux signaux simples
            # fond_ChampdB = np.zeros(len(fft_ChampdB))
            # fond_ChampdB[np.argmax(np.abs(fft_ChampdB))] = np.max(
            #     np.abs(fft_ChampdB))
            # fond_ChampH = np.zeros(len(fft_ChampH))
            # fond_ChampH[np.argmax(np.abs(fft_ChampH))] = np.max(
            #     np.abs(fft_ChampH))

            # # Transformée de Fourier inverse
            # ChampdB_prim = ifft(
            #     fond_ChampdB*np.exp(1j*np.angle(fft_ChampdB))).real
            # ChampH_prim = ifft(
            #     fond_ChampH*np.exp(1j*np.angle(fft_ChampH))).real

            # # Correlation des deux sinus obtenu et mesure du retard
            # # signal_correle = np.correlate(
            # #     ChampdB_prim, ChampH_prim, "full")
            # # lags = correlation_lags(ChampdB_prim.size, ChampH_prim.size)
            # # lag_dB_H = lags[np.argmax(signal_correle)]
            # try:
            #     _, a = start_from_zero(ChampdB_prim)
            #     _, b = start_from_zero(ChampH_prim)
            
            #     lag_dB_H=a-b
            #     #lag_dB_H=587
            # except:
            #     lag_dB_H=0
            # # lag_dB_H=int(3.6e-6/(interval*1e-9))   
            # try:
            #     _, a = start_from_zero(samples_to_plotB[:samples_per_period])
            #     _, b = start_from_zero(samples_to_plotC[:samples_per_period])
            
            #     lag_entree_V2=b-a
            #     #lag_dB_H=587
            # except:
            #     lag_entree_V2=0
                
            # print('lag_entree_V2 : ',lag_entree_V2*interval)
            # # print(len(entree))
            # # print(len(samples_to_plotA[:samples_per_period]))
            # # entree, lag_entree = Synchronisation(
            # #       samples_to_plotA[:samples_per_period],entree)
            
            # ####

            # Synchro des signaux

            ChampB, lag = Synchronisation(
                ChampBdes, ChampB[:samples_per_period])

            derivChampB, lag1 = Synchronisation(
                derivChampBdes, derivChampB[:samples_per_period])
            
            # fc=500
            # f_nyq=1/((1/Frequence)/len(derivChampB))/2
            # b, a = signal.butter(4, fc/f_nyq, 'low', analog=False)
            # #Application du filtre
            # derivChampB = signal.filtfilt(b, a, derivChampB)
            
            
            
            # signalA=np.roll(samples_to_plotA[:samples_per_period]/1000,lag)
            # _, a = start_from_zero(samples_to_plotA)
            # _, b = start_from_zero(entree)

            # lag_entree=b-a
            # entree=np.roll(entree,lag_entree)
            
            # signalA_analytic = hilbert(signalA)
            # entree_analytic = hilbert(entree)
            # phase_diff = np.angle(signalA_analytic) - np.angle(entree_analytic) 

            # entree_aligne = np.abs(entree_analytic) * np.exp(1j * (np.angle(entree_analytic) + phase_diff))
            # entree = np.real(entree_aligne)

            #ChampH2 = np.roll(ChampH2[:samples_per_period], lag)
            try:
                _, a = start_from_zero(ChampB)
                _, b = start_from_zero(ChampH2)

                lag=b-a
            except:
                lag=0
            #print('lag_dB_H : ',lag_dB_H*interval*1e-9)
            #ChampH2=np.roll(ChampH2,lag-(lag_dB_H-1250))
            ChampH2=np.roll(ChampH2,lag)#+lag_dB_H)

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

            ###################################################################
            # Boucle Asservissement de reconstruction du signal
            Mode_asservissement = 'PI_FFT'
            #Mode_asservissement = 'FFT_QN_dB_B'
            #Mode_asservissement = 'PI_temp'

            # Calcule de la noucelle entrée après la vérification des conditions de fin pour avoir
            # l'entrée de la convergence et pas la suivante
            entree_tempo, RMSE = Asservissement(Mode_asservissement, ChampBdes, ChampB[:samples_per_period], derivChampBdes, derivChampB[
                                          :samples_per_period], entree, timeC[:samples_per_period], f_0, Mat_Broyden, reinit)
            ###################################################################

            ChampH2 = savgol_filter(ChampH2, window_length=100, polyorder=3, mode="wrap")
            entree_tempo = savgol_filter(
                entree_tempo, window_length=100, polyorder=3, mode="wrap")
            ChampH2 = detrend(ChampH2, type='constant')

            self.parent.iteration_label.setText(
                "Itération n⁰"+str(iteration))
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
            if (Amplitude < (np.max(ChampB)*1.01)) & (Amplitude > (np.max(ChampB)*0.99)):
                self.parent.Bkmax_value.setStyleSheet("color: green;")
            else:
                self.parent.Bkmax_value.setStyleSheet("color: black;")
            if (FF(derivChampB, timeC[samples_per_period]) < FF(derivChampBdes, timeC[samples_per_period])*1.01) & (FF(derivChampB, timeC[samples_per_period]) > FF(derivChampBdes, timeC[samples_per_period])*0.99):
                self.parent.FF_value.setStyleSheet("color: green;")
            else:
                self.parent.FF_value.setStyleSheet("color: black;")
            self.parent.iteration_label.setStyleSheet("color: black;")
            if ((Amplitude < (np.max(ChampB)*1.01)) & (Amplitude > (np.max(ChampB)*0.99)) & (THDN(derivChampB, num_samples) < THDN(derivChampBdes, num_samples)+3) & ((FF(derivChampB, timeC[samples_per_period]) < FF(derivChampBdes, timeC[samples_per_period])*1.01) & (FF(derivChampB, timeC[samples_per_period]) > FF(derivChampBdes, timeC[samples_per_period])*0.99))) or iteration == iteration_max or self.parent.stop == True:
                
                ChampB,ChampH2, derivChampB =Visualisation(entree)
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
        Hc = np.mean(Hcs)
        ChampH2_nul = np.where(np.diff(np.sign(ChampH2)))[0]
        Brs = []
        for valeur in ChampH2_nul[:2]:
            Brs.append(np.abs(ChampB[valeur]))
        Br = np.mean(Brs)

        Pv = np.trapz(ChampH2[:samples_per_period] * derivChampB[:samples_per_period],
                      x=timeC[:samples_per_period]) / (timeC[samples_per_period])
        
        if Pv<0 : 
            ChampH2=np.negative(ChampH2)
            Pv*=-1
        
        mu_r = max(ChampB)/(max(ChampH2)*4e-7*np.pi)

        # Aire = np.trapz(ChampB[samples_per_period//4:3*samples_per_period//4],
        #                 x=ChampH2[samples_per_period//4:3*samples_per_period//4])

        # monteeB = np.concatenate(
        #     (ChampB[3*samples_per_period//4:samples_per_period], ChampB[:samples_per_period//4]), axis=None)
        # monteeH = np.concatenate(
        #     (ChampH2[3*samples_per_period//4:samples_per_period], ChampH2[:samples_per_period//4]), axis=None)

        # #Aire = (Aire - np.trapz(ChampB[:samples_per_period//4],x=ChampH2[:samples_per_period//4]))*2
        # Aire = (Aire - np.trapz(monteeB, x=monteeH))

        #print('Pv avec aire : ',Aire*Frequence)

        # with open('entree.npy', 'wb') as f:
        #     np.save(f, entree)
        # with open('time.npy', 'wb') as f:
        #     np.save(f, timeC[:samples_per_period])

        self.parent.ChampH = ChampH2[:samples_per_period]
        self.parent.main_window.ChampH = ChampH2[:samples_per_period]
        self.parent.ChampB = ChampB[:samples_per_period]
        self.parent.main_window.ChampB = ChampB[:samples_per_period]
        self.parent.main_window.derivChampB = derivChampB[:samples_per_period]
        self.parent.main_window.update_mesures(
            np.max(ChampB), Frequence, Hc, Br, np.max(ChampH2), mu_r, Pv)
        self.finished.emit()

        # except Exception as e:
        #     print('erreur : ', e)
        #     self.parent.ChampH = np.zeros(num_samples)
        #     self.parent.main_window.ChampH = np.zeros(num_samples)
        #     self.parent.ChampB = np.zeros(num_samples)
        #     self.parent.main_window.ChampB = np.zeros(num_samples)
        #     self.parent.main_window.derivChampB = np.zeros(num_samples)
        #     self.parent.main_window.update_mesures(1, 1, 1, 1, 1, 1, 1)
        #     self.finished.emit()


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
        self.lm_spin.setValue(lm)
        self.outils_combo.currentTextChanged.connect(self.selectionchange)
        self.section_spin.valueChanged.connect(self.calcul_kf)
        self.Kf_spin.valueChanged.connect(self.calcul_section)
        self.De_spin.valueChanged.connect(self.calcul_longueur)

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
            Stheo = Hauteur*1e-3*(De*1e-3-Di*1e-3)/2
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
        mu_r = self.Mu_spin.value()
        lm = self.lm_spin.value()
        if Section == 0:
            Section = De*Di*Hauteur*Kf
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


class AcquisWindow(QDialog, Ui_Page_acquisition):
    def __init__(self, *args, obj=None, **kwargs):
        global iteration_max, num_samples, Resolution, Nbre_enregist, alpha, beta, rampe
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

    def accept(self):
        global iteration_max, num_samples, Resolution, Nbre_enregist, alpha, beta, rampe
        iteration_max = self.Nbre_iter_spin.value()
        num_samples = self.Nbre_ech_spin.value()
        Resolution = self.Nbre_bits_combo.currentText()
        Nbre_enregist = self.Nbre_enreg_spin.value()
        alpha = self.coeff_alpha_spin.value()
        beta = self.coeff_beta_spin.value()
        rampe = self.coeff_rampe_spin.value()
        self.close()


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


class SupervisionWindow(QDialog, Ui_supervision):
    def __init__(self, main_window, *args, obj=None, **kwargs):
        super(SupervisionWindow, self).__init__(*args, **kwargs)
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
        if self.thread is None or not self.thread.isRunning():
            self.thread = Worker(self)
            self.thread.finished.connect(self.on_long_task_finished)
            self.thread.start()

    def on_long_task_finished(self):
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
        self.main_window.Button_start.setEnabled(True)
        self.close()


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
        self.toolButton_Reset_Pico.setIcon(QIcon('reset.jpeg'))
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
        self.actionComparaison.triggered.connect(self.comparaison)
        self.actionNotes.triggered.connect(self.notes)
        self.actionReset_Pico.triggered.connect(self.reset_pico)

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


    def comparaison(self):
        self.w = ComparWindow()
        self.w.show()

    def notes(self):
        self.win = NotesWindow(self)
        self.win.show()

    def opens_config(self):
        global Materiaux, Hauteur, Di, De, Section, Outils, Ns1, Ns2, Rs, Rh, Type, Forme, Freq, Ampli, Gain, Nbre_periode, Nbre_enregist, Nm_ref, mu_r, Kf, num_samples, alpha, beta, lm
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
        # if Freq>50e3:
        #     num_samples = Nbre_periode//(Freq*8e-9)

        self.update_data(Outils, Materiaux, Di, De, Hauteur, Section, lm, Kf)

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
                self.Frequence) + "_" + str(round(self.Bmax, 3)) + ".csv"
            
            
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
