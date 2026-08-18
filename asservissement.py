#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb  6 13:23:47 2024

@author: caracterisation
"""
from __future__ import division

import ctypes
import numpy as np
from picosdk.ps5000a import ps5000a as ps
import matplotlib.pyplot as plt
from picosdk.functions import adc2mV, assert_pico_ok, mV2adc
from scipy.signal import savgol_filter
from scipy.integrate import cumtrapz
from scipy import integrate
from scipy.signal import detrend, correlate, correlation_lags,blackmanharris,hilbert,savgol_filter,sawtooth
from FFT_criteria_evaluation import compute_convergence_criteria, compute_fft_signals
from scipy.fft import fft,rfft, irfft
from numpy import linalg as LA


import numpy as np
from IPython import get_ipython
from scipy import integrate
from numpy import linalg as LA
from scipy import signal
import matplotlib.pyplot as plt
from IPython import display
from FFT_criteria_evaluation import compute_convergence_criteria, compute_fft_signals
import os







#Boucle Asservissement de reconstruction du signal




get_ipython().magic('reset -sf')

#Définition du signal d'entrée
N1=43;
Sec=93.1e-6;
Lm=37.6e-3;
R3=100;
f=100;
T=1/f;
Amp=0.5;
nb_points=1000;  #nb_points par periode
nb_periodes=5
temps=np.linspace( 0,(nb_periodes*T-T/nb_points),nb_periodes*nb_points);
temps2=np.linspace( 0,T,nb_points);

# mu_0=4e-7*np.pi;
# mu_r=2000;
# B_max=0.4;      #Amplitude de B souhaitée
# B_ref=B_max*np.sin(2*np.pi*f*temps);
# H_ref=B_ref*mu_0*mu_r
# dB_dt_ref=2*np.pi*f*B_max*np.cos(2*np.pi*f*temps);
# signal=N1*Sec*dB_dt_ref + R3*H_ref*Lm/N1 ;
# e_k=np.interp(temps2, temps, signal)



###############################################################################
#Parametre de convergence
iteration=0
nb_iter_max=200 
Tolmax=0.5
#Kp = N1*Sec
#Ki=0.9*R3*Lm/(N1*mu_0*mu_r)
Kp=1
Ki=1
harm=100
alpha=1
###############################################################################

#On simule une première fois avant de rentrer dans la boucle de NR
iteration=0
THD_dB=1


time=np.linspace(0,2*np.pi,101)
champs_H=np.sin(time+0.3)
# #champs_H=sawtooth(time,0.5)

champs_B=np.sin(time)

entree=champs_H
#derivChampBdes=np.diff(champs_B) / np.diff(time)


num_samples = len(time)  #Nombre de points par periode
num_Fourier = int(num_samples+1)
Mat_Broyden = np.hstack((np.eye(num_Fourier), np.eye(num_Fourier)))
f_0 = np.zeros(num_Fourier*2)


temps_sim=time
temps_sim=np.delete(temps_sim,-1)
V1_sim=champs_H
B_sim=champs_B
B_ref_sim=np.sin(time)
dB_dt_sim=champs_B
dB_dt_ref_sim=champs_B
dB_dt_sim=np.diff(champs_B) / np.diff(time)
dB_dt_ref_sim=np.diff(B_ref_sim) / np.diff(time)




THD_dB, Fourier_dB_ref, Fourier_dB,Fourier_B_ref, Fourier_B, Fourier_V = compute_fft_signals(B_ref_sim,B_sim,V1_sim,dB_dt_ref_sim,dB_dt_sim)
RMSE, FF, err_dB_amp = compute_convergence_criteria(dB_dt_ref_sim,dB_dt_sim,B_ref_sim,B_sim,temps_sim)



f_n=np.concatenate(( (Fourier_dB - Fourier_dB_ref)/np.max(Fourier_dB_ref), (Fourier_B - Fourier_B_ref)/np.max(Fourier_B_ref) ))  #On sauvegarde l'écart sur la sortie f(x)
#f_n=np.append(f_n,0)
if iteration<2:
    gamma=0.5
else:
    gamma=0.5
#print('Mat_Broyden=',np.shape(Mat_Broyden),'f_n=',np.shape(f_n), 'nb_points_dB', np.shape(derivChampB[:samples_per_period]) )
Fourier_dk = - gamma * Mat_Broyden @ (f_n) #Calcul de la direction
Fourier_e_k= (Fourier_V +  Fourier_dk) #Calcul de la nouvelle tension
#On reconvertit en temporel
e_k=    0.5*len(entree)*np.fft.irfft( Fourier_e_k[0:int(len(Fourier_e_k)/2)] - 1j * Fourier_e_k[int(len(Fourier_e_k)/2):] )
entree = e_k
delta_f = f_n - f_0
#Actualisation de la matrice Broyden (Bad Broyden)
Mat_Broyden = Mat_Broyden + np.outer((Fourier_dk - Mat_Broyden @ delta_f )/(LA.norm(delta_f)*LA.norm(delta_f)),delta_f.T)
print('conditionnement matrice = ',np.linalg.cond(Mat_Broyden))
f_0 = f_n #Pour garder en mémoire la sortie pouyr la prochaine itération

















