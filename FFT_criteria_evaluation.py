#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat May 20 16:33:09 2023

@author: sixdenier
"""

from __future__ import division
import numpy as np
from scipy import integrate
from numpy import linalg as LA
from scipy import signal
import matplotlib.pyplot as plt
from IPython import display
import os



def compute_convergence_criteria(dB_dt_ref_sim,dB_dt_sim,B_ref_sim,B_sim,temps_sim):
    # #Calcul des écarts
    delta_B = B_ref_sim - B_sim ; #Vecteur de la sortie de la fonction à minimiser
    delta_dB = (dB_dt_ref_sim - dB_dt_sim)/np.max(dB_dt_ref_sim) ; #Vecteur de la sortie de la fonction à minimiser
    #Calcul de delta_V (incr�ment � ajouter au signal)
    RMSE =  100*np.sqrt(np.mean(delta_dB*delta_dB))
    FF_reel = np.sqrt( integrate.trapz((dB_dt_sim**2),temps_sim)/(max(temps_sim)-min(temps_sim))  ) / (integrate.trapz(np.abs(dB_dt_sim),temps_sim)/(max(temps_sim)-min(temps_sim))) 
    FF_theo= np.sqrt( integrate.trapz((dB_dt_ref_sim**2),temps_sim)/(max(temps_sim)-min(temps_sim))  ) / (integrate.trapz(np.abs(dB_dt_ref_sim),temps_sim)/(max(temps_sim)-min(temps_sim))) 
    FF= 100*np.abs (FF_reel-FF_theo)/FF_theo
    err_dB_amp=100*np.abs((np.max(dB_dt_ref_sim)-np.max(dB_dt_sim))/np.max(dB_dt_ref_sim))
    #print('RMSE=',RMSE,'FF=',FF,'THD=',THD_dB,"err_dB=",err_dB_amp)
    return RMSE, FF, err_dB_amp
    
def compute_fft_signals(B_ref_sim,B_sim,V1_sim,dB_dt_ref_sim,dB_dt_sim):
    harmax=100
    #Calcul des coefficients de Fourier de la référence de B
    an_B_ref=2*np.real(np.fft.rfft(B_ref_sim))/len(B_ref_sim)
    bn_B_ref=-2*np.imag(np.fft.rfft(B_ref_sim))/len(B_ref_sim)
    index=np.linspace(0,len(an_B_ref)-1,len(an_B_ref))
    index_pair=np.where(index %2 ==0)
    an_B_ref[index_pair]=0
    bn_B_ref[index_pair]=0
    index_max=np.where(index > harmax)
    np.delete(an_B_ref, index_max)
    np.delete(bn_B_ref, index_max)
    Fourier_B_ref=np.concatenate((an_B_ref,bn_B_ref))
    #Calcul des coefficients de Fourier de B obtenu
    an_B_sim=2*np.real(np.fft.rfft(B_sim))/len(B_sim)
    bn_B_sim=-2*np.imag(np.fft.rfft(B_sim))/len(B_sim)
    an_B_sim[index_pair]=0
    bn_B_sim[index_pair]=0
    np.delete(an_B_sim, index_max)
    np.delete(bn_B_sim, index_max)
    Fourier_B_sim=np.concatenate((an_B_sim,bn_B_sim))
    #Calcul des coefficients de la tension V
    an_V_sim=2*np.real(np.fft.rfft(V1_sim))/len(V1_sim)
    bn_V_sim=-2*np.imag(np.fft.rfft(V1_sim))/len(V1_sim)
    an_V_sim[index_pair]=0
    bn_V_sim[index_pair]=0
    np.delete(an_V_sim, index_max)
    np.delete(bn_V_sim, index_max)
    Fourier_V_sim=np.concatenate((an_V_sim,bn_V_sim))
    #Calcul des coefficients de la tension dB/dt de référence
    an_dB_ref=2*np.real(np.fft.rfft(dB_dt_ref_sim))/len(dB_dt_ref_sim)
    bn_dB_ref=-2*np.imag(np.fft.rfft(dB_dt_ref_sim))/len(dB_dt_ref_sim)
    an_dB_ref[index_pair]=0
    bn_dB_ref[index_pair]=0
    np.delete(an_dB_ref, index_max)
    np.delete(bn_dB_ref, index_max)
    Fourier_dB_ref=np.concatenate((an_dB_ref,bn_dB_ref))
    #Calcul des coefficients de la tension dB/dt obtenu
    an_dB_sim=2*np.real(np.fft.rfft(dB_dt_sim))/len(dB_dt_sim)
    bn_dB_sim=-2*np.imag(np.fft.rfft(dB_dt_sim))/len(dB_dt_sim)
    an_dB_sim[index_pair]=0
    bn_dB_sim[index_pair]=0
    np.delete(an_dB_sim, index_max)
    np.delete(bn_dB_sim, index_max)
    Fourier_dB_sim=np.concatenate((an_dB_sim,bn_dB_sim))
    coeff_dB=np.sqrt(an_dB_sim**2+bn_dB_sim**2)
    THD_dB = 100*np.sqrt(np.sum(coeff_dB[2:]*coeff_dB[2:]))/np.sqrt(np.sum(coeff_dB[1:]*coeff_dB[1:]))
    return THD_dB, Fourier_dB_ref, Fourier_dB_sim,Fourier_B_ref, Fourier_B_sim, Fourier_V_sim

