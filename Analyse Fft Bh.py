#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue May 20 09:10:17 2025

@author: caracterisation
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def charger_donnees(fichier_csv):
    df = pd.read_csv(fichier_csv, skiprows=1)
    temps = pd.to_numeric(df.iloc[:, 0], errors='coerce')
    champH = pd.to_numeric(df.iloc[:, 1], errors='coerce')
    champB = pd.to_numeric(df.iloc[:, 2], errors='coerce')
    mask = temps.notna() & champH.notna() & champB.notna()
    return temps[mask].to_numpy(), champH[mask].to_numpy(), champB[mask].to_numpy()

def extraire_harmoniques(signal, temps, nb_harmoniques):
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

def calculer_fft(signal, temps, nb_harmoniques):
    n = len(signal)
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

    return harm_freqs, harm_amps, f0

def afficher_harmoniques(freq_H, amp_H, freq_B, amp_B):
    fig, axs = plt.subplots(1, 2, figsize=(14, 5))
    axs[0].stem(freq_H, amp_H, use_line_collection=True)
    axs[0].set_title("FFT du Champ H")
    axs[0].set_xlabel("Fréquence (Hz)")
    axs[0].set_ylabel("Amplitude")
    axs[0].grid(True)

    axs[1].stem(freq_B, amp_B, use_line_collection=True, linefmt='r-', markerfmt='ro')
    axs[1].set_title("FFT du Champ B")
    axs[1].set_xlabel("Fréquence (Hz)")
    axs[1].set_ylabel("Amplitude")
    axs[1].grid(True)

    plt.tight_layout()
    plt.show()

def afficher_bh_complet(champH, champB):
    plt.figure(figsize=(6,6))
    plt.plot(champH, champB, color='red')
    plt.xlabel("Champ H (A/m)")
    plt.ylabel("Champ B (T)")
    plt.title("Courbe B(H) - Signal complet")
    plt.ylim(-0.1, 0.1)
    plt.grid(True)
    plt.show()

def afficher_bh_filtré(champH_filtré, champB_filtré, nb_harmoniques):
    plt.figure(figsize=(6,6))
    plt.plot(champH_filtré, champB_filtré, color='purple')
    plt.xlabel("Champ H (A/m)")
    plt.ylabel("Champ B (T)")
    plt.title(f"Courbe B(H) - {nb_harmoniques} harmoniques")
    plt.ylim(-0.1, 0.1)
    plt.grid(True)
    plt.show()

def get_point(H, champH_filtré, champB_filtré):
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

def calc_A(champH_filtré, champB_filtré):
    n_point = 5001
    hmin = min(champH_filtré)
    hmax = max(champH_filtré)
    dH = (hmax - hmin) / n_point
    hrange = np.arange(hmin, hmax, dH)

    A = 0
    y1, y2 = get_point(hrange[1], champH_filtré, champB_filtré)
    A += dH * np.abs(y1 - y2) / 2
    last_y1, last_y2 = y1, y2

    for H in hrange[2:-1]:
        y1, y2 = get_point(H, champH_filtré, champB_filtré)
        A += dH * (np.abs(y1 - y2) + np.abs(last_y1 - last_y2)) / 2
        last_y1, last_y2 = y1, y2

    A += dH * np.abs(last_y1 - last_y2) / 2
    print("Aire de l'hystérésis:", A)
    return A
