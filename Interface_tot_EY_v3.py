#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Feb  9 15:09:28 2024

@author: caracterisation
"""

# =============================================================================
# Imports morts supprimés (aucun usage réel dans le fichier) :
#   random, math, numpy.linspace, QGridLayout, QRunnable, QThreadPool.
#
# NOTE : l'import « from numpy.fft import fft, ifft » présent dans Worker.run()
#   écrasait « from scipy.fft import fft » importé 5 lignes plus haut. Voir la
#   correction dans Worker.run().
# =============================================================================
import sys
import os
import csv
import json
import time
import logging
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import serial
import serial.tools.list_ports

from PyQt5 import QtWidgets, uic

# Empêche les conflits de plugins Qt sous Linux
# (doit rester AVANT la création de la QApplication)
os.environ.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)

from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtWidgets import (QAction, QActionGroup,
                             QColorDialog, QTableWidgetItem, QDialogButtonBox,
                             QComboBox, QDialog, QPushButton, QFileDialog,
                             QVBoxLayout, QHBoxLayout, QButtonGroup,
                             QMessageBox, QGroupBox, QCheckBox, QLabel)
from PyQt5.QtCore import (QThread, pyqtSignal, QSettings, QSize, Qt, QObject,
                          pyqtSlot)

# --- Fenêtres générées par pyuic5 -------------------------------------------
from Mainwindow_EG import Ui_JTcontrol
from Supervision import Ui_supervision
from page_acquisition_2 import Ui_Page_acquisition
from dialog import Ui_Dialog
from Notes import Ui_notes
from error import Ui_error
from curve_comparaison import Ui_curve_comparaison
from helpwindow import Ui_HelpWindow
from pertesvsfreq import Ui_PertesVsFreq
from amplificateur import Ui_Ampli
from amplificateur_defaut import Ui_Ampli_defaut


# =============================================================================
# JOURNALISATION  —  remplace les 132 journal() du fichier
#
# Pourquoi : les journal() partaient dans une console que l'utilisateur ne voit
# pas toujours
# Fonctionnement :
#   - journal(...) s'utilise EXACTEMENT comme journal() : journal("a =", a)
#   - la console affiche ce qui dépasse le niveau choisi dans l'IHM
#   - un fichier Logs/session.log reçoit TOUJOURS tout, quel que soit le
#     niveau affiché à l'écran (traçabilité complète, coût négligeable)
#
# Le niveau console se règle depuis le menu « Options » de la fenêtre
# principale, ou depuis le cadre « Débogage » de la fenêtre « Paramètres
# d'acquisition ». Les deux appellent regler_verbosite().
# -----------------------------------------------------------------------------
# =============================================================================
NIVEAUX_VERBOSITE = {
    "Silencieux": logging.WARNING,
    "Normal":     logging.INFO,
    "Debug":      logging.DEBUG,
}

VERBOSITE_CONSOLE = "Normal"     # état courant, affiché dans la barre d'état

log = logging.getLogger("banc")
log.setLevel(logging.DEBUG)          # le logger laisse tout passer...
log.propagate = False                # ...ce sont les handlers qui filtrent


def _configurer_journal():
    for handler in list(log.handlers):
        log.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass                     # handler déjà fermé : sans conséquence

    console = logging.StreamHandler(sys.stdout)
    console.set_name("console_banc")
    console.setLevel(NIVEAUX_VERBOSITE.get(VERBOSITE_CONSOLE, logging.INFO))
    console.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(console)

    try:
        os.makedirs("./Logs", exist_ok=True)
        fichier = logging.FileHandler(
            os.path.join("./Logs", "session.log"), encoding="utf-8")
        fichier.set_name("fichier_banc")
        fichier.setLevel(logging.DEBUG)   # le fichier reçoit TOUT
        fichier.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)-7s] %(message)s"))
        log.addHandler(fichier)
    except OSError as err:           # disque plein, droits insuffisants...
        console.handle(logging.LogRecord(
            "banc", logging.WARNING, __file__, 0,
            f"Journal fichier indisponible : {err}", None, None))


_configurer_journal()


def journal(*args, niveau=logging.INFO):
    """Substitut de print() qui passe par le module logging.

    S'utilise exactement comme print() : journal("Frequence :", f, "Hz").
    Le paramètre `niveau` permet de descendre en DEBUG pour les traces
    volumineuses (ex. le détail FFT à chaque itération).
    """
    log.log(niveau, " ".join(str(a) for a in args))


def regler_verbosite(nom_niveau):
    """Règle le niveau AFFICHÉ EN CONSOLE. Le fichier de log garde tout.

    """
    global VERBOSITE_CONSOLE
    VERBOSITE_CONSOLE = nom_niveau
    niveau = NIVEAUX_VERBOSITE.get(nom_niveau, logging.INFO)

    for handler in log.handlers:
        if isinstance(handler, logging.FileHandler):
            continue                 # le fichier reçoit tout, en permanence
        handler.setLevel(niveau)

    # Message de confirmation en DEBUG : il part dans session.log mais PAS dans
    # la console. Le confirmer à l'écran contredirait le mode « Silencieux »,
    # qui doit être silencieux. Le retour visuel se fait par l'indicateur de la
    # barre d'état.
    log.debug("Verbosite console reglee sur : %s", nom_niveau)


# =============================================================================
# NIVEAU D'ENREGISTREMENT DES TRACES SUR DISQUE
#
# Il faut distinguer DEUX choses que le mot « logs » recouvre, et dont les coûts
# n'ont rien à voir :
#
#   1. Les SIGNAUX de chaque itération (waveforms_iter_NNN.csv).
#      Volume mesuré : ~1,3 Mo par itération avec 15 signaux et 5000
#      échantillons par période, soit ~126 Mo pour 99 itérations, PAR MESURE.
#      C'est du matériel de débogage : ces courbes intermédiaires ne servent
#      qu'à comprendre pourquoi un asservissement diverge. 
#
#   2. Les SCALAIRES : metadata.json, metrics.csv (une ligne par itération) et
#      summary.json. Quelques dizaines de kilo-octets au total. Ce n'est PAS du
#      débogage : c'est le procès-verbal de la mesure — les conditions
#      expérimentales, l'historique de convergence et le statut final. Sans eux,
#      un résultat n'est plus rattachable à rien et n'est plus publiable.
#      Ils sont donc écrits à TOUS les niveaux, y compris « Minimal ».
#
# Niveau par défaut : « Standard ». Il conserve les signaux de l'itération
# finale — celle qui produit réellement le résultat, donc celle dont on a besoin
# pour retracer un cycle B(H) — et jette les intermédiaires.
# =============================================================================
NIVEAU_TRACE_COMPLET  = "Complet (toutes les itérations)"
NIVEAU_TRACE_STANDARD = "Standard (itération finale)"
NIVEAU_TRACE_MINIMAL  = "Minimal (aucun signal)"
NIVEAUX_TRACE = (NIVEAU_TRACE_COMPLET, NIVEAU_TRACE_STANDARD, NIVEAU_TRACE_MINIMAL)

NIVEAU_TRACE = NIVEAU_TRACE_STANDARD

from scipy import integrate as _scipy_integrate

try:                                   # SciPy >= 1.6
    cumtrapz_compat = _scipy_integrate.cumulative_trapezoid
    trapz_compat = _scipy_integrate.trapezoid
except AttributeError:                 # SciPy ancien
    cumtrapz_compat = _scipy_integrate.cumtrapz
    trapz_compat = _scipy_integrate.trapz

class MeasurementLogger:
    """
    Logger autonome pour sauvegarder l'historique complet d'une mesure
    d'asservissement (scalaires + courbes + métadonnées).
    
    Structure créée :
        ./Logs/YYYY-MM-DD_HH-MM-SS_Materiau_FxHz_Bx.xT/
            ├── metadata.json           # Paramètres globaux de la mesure
            ├── metrics.csv             # Une ligne par itération (scalaires)
            ├── waveforms_iter_000.npz  # Courbes de l'itération 0
            ├── waveforms_iter_001.npz  # Courbes de l'itération 1
            └── ...
    """
    
    def __init__(self, metadata, root_dir="./Logs", niveau=None):
        # Création du dossier horodaté
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        nom_session = (f"{timestamp}_"
                       f"{metadata.get('Materiaux', 'inconnu')}_"
                       f"F{metadata.get('Frequence_Hz', 0):.1f}Hz_"
                       f"B{metadata.get('Amplitude_T', 0):.2f}T_"
                       f"{metadata.get('Nm_ref', 'inconnu')}")
        # Caractères interdits sur Windows Nm_ref
        for c in [':', '/', '\\', '*', '?', '"', '<', '>', '|']:
            nom_session = nom_session.replace(c, '-')
        
        self.dir = os.path.join(root_dir, nom_session)
        os.makedirs(self.dir, exist_ok=True)
        
        # Sauvegarde des métadonnées (paramètres fixes de la mesure)
        with open(os.path.join(self.dir, 'metadata.json'), 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)
        
        # Préparation du CSV des métriques (en-tête)
        self.csv_path = os.path.join(self.dir, 'metrics.csv')
        
        self.csv_columns = [
                            'iteration', 'timestamp',
                            'RMSE', 'THD_mesure', 'THD_reference', 'FF_mesure', 'FF_reference',
                            'B_max', 'B_max_reference', 'dB_max', 'dB_max_reference',
                            'H_max', 'I_max_mA',
                            'delta_B', 'delta_dB',
                            # --- état interne de l'asservissement---
                            'cycle', 'reinit', 'lag_synchro',
                            'calibreA', 'calibreB',
                            'amplitude_entree_V', 'calibreC',
                            'converge',
                            # === Voie D : sonde de courant N2783B ===
                            'calibreD',
                            'Idc_shunt_mA', 'Idc_probe_mA',
                            'ratio_Iprobe_Ishunt', 'dphi_probe_shunt_deg',
                            'H_max_probe',
                        ]
        with open(self.csv_path, 'w', encoding='utf-8') as f:
            f.write(','.join(self.csv_columns) + '\n')
        
        self.iteration_count = 0

        # Niveau de trace figé au démarrage de la mesure : le changer en cours
        # de route produirait une session incohérente (certaines itérations
        # enregistrées, d'autres non, sans que rien ne le signale).
        self.niveau = niveau if niveau is not None else NIVEAU_TRACE
        self._dernier_iter = None       # signaux de la dernière itération
        self._derniers_signaux = None
        self._dernieres_matrices = None

        # La trace est inscrite dans metadata.json : en relisant une session
        # ancienne, on doit pouvoir savoir POURQUOI il n'y a pas de courbes.
        self.update_metadata({'niveau_trace': self.niveau})

        journal(f"\U0001F4C1 Logger initialisé : {self.dir}")
        journal(f"   Niveau de trace : {self.niveau}")

    def update_metadata(self, extra):
        """Ajoute/complète des clés dans metadata.json après coup
        (ex. offsets mesurés une fois les instruments ouverts)."""
        path = os.path.join(self.dir, 'metadata.json')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        except Exception:
            meta = {}
        meta.update(extra)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2, ensure_ascii=False, default=str)
    
    def log_iteration(self, scalars, waveforms):
        """
        Sauvegarde une itération.
        
        Parameters
        ----------
        scalars : dict
            Dictionnaire des valeurs scalaires (clés = self.csv_columns)
        waveforms : dict
            Dictionnaire des tableaux numpy à sauvegarder
            (entree, ChampB, ChampBdes, ChampH2, derivChampB, derivChampBdes, timeC, ...)
        """
        #  alerte explicite si une grandeur calculée n'a pas de
        # colonne dans le CSV. Sans cela, la perte était totalement silencieuse.
        cles_inconnues = set(scalars) - set(self.csv_columns)
        if cles_inconnues and not getattr(self, '_alerte_colonnes_emise', False):
            log.warning("MeasurementLogger : cles non enregistrees dans "
                        "metrics.csv : %s", sorted(cles_inconnues))
            self._alerte_colonnes_emise = True   # une seule alerte par session

        # 1) Append du CSV
        ligne = []
        for col in self.csv_columns:
            val = scalars.get(col, '')
            if isinstance(val, float):
                ligne.append(f"{val:.6g}")
            else:
                ligne.append(str(val))
        with open(self.csv_path, 'a', encoding='utf-8') as f:
            f.write(','.join(ligne) + '\n')
        
        # 2) Sauvegarde des signaux — CONDITIONNELLE selon le niveau de trace.
        #    (Le CSV des scalaires ci-dessus, lui, est toujours écrit.)
        iter_num = scalars.get('iteration', self.iteration_count)

        if self.niveau != NIVEAU_TRACE_MINIMAL:
            signaux_1d = {}   # signaux 1D -> colonnes d'un même CSV
            matrices_2d = {}  # matrices (ex. Mat_Broyden) -> fichiers séparés
            for cle, arr in waveforms.items():
                arr = np.asarray(arr)
                if arr.ndim <= 1:
                    signaux_1d[cle] = np.atleast_1d(arr).astype(float)
                else:
                    matrices_2d[cle] = arr

            if self.niveau == NIVEAU_TRACE_COMPLET:
                self._ecrire_signaux(iter_num, signaux_1d, matrices_2d)
            else:
                # Niveau Standard : on garde la dernière itération EN MÉMOIRE
                # (~320 ko) et on ne l'écrit qu'une fois, dans finalize().
                # Écrire à chaque tour puis écraser coûterait autant d'E/S que
                # le niveau Complet, ce qui viderait le réglage de son sens.
                self._dernier_iter = iter_num
                self._derniers_signaux = signaux_1d
                self._dernieres_matrices = matrices_2d

        self.iteration_count += 1

    def _ecrire_signaux(self, iter_num, signaux_1d, matrices_2d, suffixe=''):
        """Écrit les courbes d'une itération au format CSV lisible dans Excel."""
        for cle, arr in matrices_2d.items():
            mat_path = os.path.join(self.dir,
                                    f'{cle}_iter_{iter_num:03d}{suffixe}.csv')
            np.savetxt(mat_path, arr, delimiter=',', fmt='%.8g')

        if not signaux_1d:
            return

        noms = list(signaux_1d.keys())
        # Les signaux ont des longueurs différentes (1 période vs 2 périodes) :
        # on aligne tout sur la longueur max et on complète par des NaN.
        longueur_max = max(len(a) for a in signaux_1d.values())
        matrice = np.full((longueur_max, len(noms)), np.nan, dtype=float)
        for j, cle in enumerate(noms):
            a = signaux_1d[cle]
            matrice[:len(a), j] = a

        wf_path = os.path.join(self.dir,
                               f'waveforms_iter_{iter_num:03d}{suffixe}.csv')
        np.savetxt(wf_path, matrice, delimiter=',',
                   header=','.join(noms), comments='', fmt='%.8g')
    
    def finalize(self, status, best_iteration=None):
        """
        Écrit un résumé final lorsque la mesure se termine.
        """
        # Niveau Standard : c'est ICI qu'on écrit les courbes, une seule fois,
        # celles de l'itération qui a réellement produit le résultat affiché.
        if (self.niveau == NIVEAU_TRACE_STANDARD
                and self._derniers_signaux is not None):
            try:
                self._ecrire_signaux(self._dernier_iter,
                                     self._derniers_signaux,
                                     self._dernieres_matrices,
                                     suffixe='_final')
                journal(f"   Courbes de l'iteration finale "
                        f"({self._dernier_iter}) enregistrees.")
            except OSError as err:
                log.warning("Ecriture des courbes finales impossible : %s", err)

        summary = {
            'status': status,  # 'converge', 'iteration_max', 'stop_utilisateur'
            'n_iterations': self.iteration_count,
            'best_iteration': best_iteration,
            'duree_session': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(os.path.join(self.dir, 'summary.json'), 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
        journal(f"✅ Session enregistrée : {self.dir}")

# Initialisation paramètres

#Paramètre d'acquisition
Hauteur = Di = De = Section = Rs = Rh = Freq = Ampli = Gain = Nbre_enregist = mu_r = lm = Epaisseur = Nbre_Bandes = Largeur = alpha = beta = gamma = cycle = 0
Sonde=1
Kf = 1
Nbre_periode = 2
iteration_max = 100
num_samples = 5000
mu_r = 2000
Resolution = 14
Ns1 = 5
Ns2 = 5
mu_0 = 4e-7*np.pi
Nbre_enregist = 10
Materiaux = "Fer pur"
Outils = "Tore enroulé"
Type = "Cycle d'hystérèsis"
Forme = "Sinusoïdale B"   
Nm_ref = "Nom_Ref"
rampe = 5
alpha=beta=0.5
gamma=5
selected_dir=""
mode_filtre = 'mirror'
fenetre_filtre = 500
# youssef : nombre d'harmoniques conserve par filtre_harmonique() lors du
# filtrage FFT du champ H. Auparavant fige en dur (n_harm=15) dans le code,
# desormais reglable depuis la fenetre "Parametres d'acquisition" avant le
# debut de la mesure (voir AcquisWindow / self.Nbre_harm_H_spinBox).
nb_harmoniques_H = 15
ChampBdes = timeC = func_eval = 0
Erreur = []
port_connection=''

# =============================================================================
# SONDE DE COURANT (voie D) 
# ATTENTION : le PicoScope 5000a limite la résolution à 14 bits dès que
# 4 voies sont actives.  Désactiver la sonde permet donc de monter à 15/16 bits
# sur B et H (meilleur rapport signal/bruit sur l'intégrale de B), au prix de la
# perte du contrôle croisé shunt/sonde.  Par défaut : sonde ACTIVE.
# =============================================================================
@dataclass
class ConfigSondeCourant:
    """Paramètres de la pince de courant branchée sur la voie D du PicoScope."""
    active:  bool  = False      # False -> acquisition 3 voies (A, B, C)
    v_per_a: float = 0.1       # sensibilité Keysight N2783B : 0,1 V/A
    n_tours: int   = 1         # nb de passages du conducteur dans la pince (3-5 conseillé)
    signe:   int   = +1        # -1 si la flèche de la pince est dans l'autre sens
    modele:  str   = "Keysight N2783B"

    def courant(self, tension_v):
        """Convertit la tension mesurée sur la voie D (en V) en courant (en A)."""
        return self.signe * tension_v / (self.v_per_a * self.n_tours)

    def resolution_max_bits(self):
        """Résolution ADC maximale admissible compte tenu du nombre de voies."""
        return 14 if self.active else 16


# Instance unique utilisée par tout le programme (modifiable depuis l'IHM).
CONFIG_SONDE = ConfigSondeCourant()

# --- Compatibilité ascendante -------------------------------------------------
USE_PROBE_D    = CONFIG_SONDE.active
PROBE_V_PER_A  = CONFIG_SONDE.v_per_a
PROBE_N_TOURS  = CONFIG_SONDE.n_tours
PROBE_SIGN     = CONFIG_SONDE.signe

MESURE_OFFSETS_AU_DEMARRAGE = False  # True : acquisition excitation OFF au lancement pour
                                     # mesurer l'offset des voies B et D (lent : auto-trigger
                                     # 1 s/bloc sans signal). False : offsets supposés nuls,
                                     # les Idc logués incluent alors l'offset de la chaîne.

# Variables de conversion des unités
facteur_kHz_vers_Hz = 1e3      # Conversion kilohertz → hertz (fréquence saisie en kHz dans l'interface)
facteur_mV_vers_V   = 1e-3     # Conversion millivolts → volts (sorties ADC du PicoScope en mV)
facteur_mm_vers_m   = 1e-3     # Conversion millimètres → mètres (dimensions géométriques saisies en mm)
facteur_mm2_vers_m2 = 1e-6     # Conversion mm² → m² (section transversale saisie en mm²)
facteur_m2_vers_mm2 = 1e6      # Conversion m² → mm² (retour en mm² pour l'affichage)

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


# =============================================================================
# CONSTRUCTION DE LA LISTE DES VOIES PICOSCOPE
# Structure d'une voie (conservée telle quelle pour ne rien casser) :
#   [0] nom PicoScope   [1] clé de statut setChX   [2] clé setdataBuffersX
#   [3] buffer max      [4] buffer min
# =============================================================================
def construire_selection_channel(config_sonde):
    """Retourne la liste des voies à acquérir selon la configuration sonde."""
    voies = [["PS5000A_CHANNEL_A", "setChA", "setdataBuffersA", [], []],
             ["PS5000A_CHANNEL_B", "setChB", "setdataBuffersB", [], []],
             ["PS5000A_CHANNEL_C", "setChC", "setdataBuffersC", [], []]]
    if config_sonde.active:
        # Voie D = pince de courant. Absente -> acquisition 3 voies, ce qui
        # autorise une résolution ADC plus élevée (voir ConfigSondeCourant).
        voies.append(["PS5000A_CHANNEL_D", "setChD", "setdataBuffersD", [], []])
    return voies


Selection_Channel = construire_selection_channel(CONFIG_SONDE)
Temperature_flag = 0
limite = 100

# =============================================================================
# CONSTANTES MATÉRIEL ET SÉCURITÉ
# =============================================================================

# --- Étalonnage de la chaîne de mesure ---------------------------------------
R_SHUNT_OHM = 0.198        # Shunt de mesure du courant primaire, mesuré 4 fils.

# --- Limites de sécurité ------------------------------------------------------
PK_MAX_GBF = 5.0           # PLAFOND DUR d'amplitude envoyée au GBF (V).
                           # À AJUSTER selon : tension max GBF

V2_LIMITE_PICO_V = 20.0    # Pleine échelle max d'une voie PicoScope (calibre 20 V).
                           # Au-delà, V2 est écrêté et l'intégrale de B est fausse.

RESOLUTION_MAX_4_VOIES = 14  # Contrainte matérielle PS5000A en mode 4 voies.

# --- Communication instruments ------------------------------------------------
PICO_READY_TIMEOUT = 10.0  # délai max (s) d'attente que le PicoScope soit prêt
GBF_USB_VENDOR  = 2391     # identifiants USBTMC du GBF (étaient codés en dur)
GBF_USB_PRODUCT = 9991
AMPLI_BAUDRATE  = 9600     # liaison série de l'amplificateur
AMPLI_TIMEOUT_S = 1.0
AMPLI_PREFIXE_PORT = "/dev/ttyUSB"   # préfixe des ports scrutés (Linux)

# --- Trames série de l'amplificateur (étaient des littéraux hexadécimaux nus) --
TRAME_ETAT          = "0210"   # demande de l'octet d'état (ready/overload/...)
TRAME_ERREUR        = "0242"   # demande de l'octet d'erreurs
TRAME_TEMPERATURE   = "0204"   # lecture de la température
TRAME_OUTPUT_ON     = "033501"
TRAME_OUTPUT_OFF    = "033500"

# --- Acquisition --------------------------------------------------------------
MAX_SAMPLES_LIMIT = 50000  # limite mémoire de sécurité PicoScope (par voie)
NBRE_PERIODE_MIN  = 2      

# --- Comportement de l'asservissement ----------------------------------------
#   True  = comportement corrigé (recommandé après validation)
#   False = comportement strictement identique à la version d'origine
FIX_BACKTRACKING_REINIT = True


# =============================================================================
# FICHIERS DE CONFIGURATION  —  outils communs

CONFIG_VERSION = 2          # version du format de fichier .cfg
CONFIG_FILTRE = "Fichiers de configuration (*.cfg)"
# Filtre d'ouverture : le second choix permet de récupérer les fichiers
# enregistrés par les versions précédentes, qui n'avaient PAS d'extension .cfg
# à cause du décalage d'arguments décrit ci-dessus et restaient donc invisibles.
CONFIG_FILTRE_OUVERTURE = ("Fichiers de configuration (*.cfg)"
                           ";;Tous les fichiers (*)")

# Registre applicatif (base de registre / ~/.config), distinct des fichiers .cfg
_REGLAGES_APP = ("LaboMagnetique", "MagHyster")


def _dernier_dossier(cle):
    """Retourne le dernier dossier utilisé pour ce type de fichier."""
    reglages = QSettings(*_REGLAGES_APP)
    defaut = os.path.expanduser("~")
    dossier = str(reglages.value(f"chemins/{cle}", defaut))
    return dossier if os.path.isdir(dossier) else defaut


def _memoriser_dossier(cle, chemin):
    """Mémorise le dossier d'un fichier pour la prochaine ouverture.

    Sans cela, chaque boîte de dialogue repart du répertoire de lancement du
    programme — ce qui obligeait à renaviguer vers le dossier de campagne à
    chaque enregistrement.
    """
    reglages = QSettings(*_REGLAGES_APP)
    reglages.setValue(f"chemins/{cle}", os.path.dirname(os.path.abspath(chemin)))
    reglages.sync()


def _nom_fichier_sur(texte, defaut="configuration"):
    """Rend une chaîne utilisable comme nom de fichier.

    Le nom de référence de l'échantillon peut contenir « / », « : » ou des
    espaces multiples, qui produiraient un chemin invalide.
    """
    propre = "".join(c if (c.isalnum() or c in " -_") else "_"
                     for c in str(texte)).strip()
    return propre or defaut


def demander_fichier_sauvegarde(parent, titre, nom_propose, cle_dossier,
                                filtre=CONFIG_FILTRE, extension=".cfg"):
    """Boîte « Enregistrer sous » avec dossier mémorisé et extension forcée."""
    chemin_propose = os.path.join(_dernier_dossier(cle_dossier), nom_propose)
    chemin, _ = QFileDialog.getSaveFileName(parent, titre, chemin_propose, filtre)
    if not chemin:
        return None
    if not chemin.lower().endswith(extension):
        chemin += extension
    _memoriser_dossier(cle_dossier, chemin)
    return chemin


def demander_fichier_ouverture(parent, titre, cle_dossier,
                               filtre=CONFIG_FILTRE_OUVERTURE):
    """Boîte « Ouvrir » démarrant dans le dernier dossier utilisé."""
    chemin, _ = QFileDialog.getOpenFileName(
        parent, titre, _dernier_dossier(cle_dossier), filtre)
    if not chemin:
        return None
    _memoriser_dossier(cle_dossier, chemin)
    return chemin


# -----------------------------------------------------------------------------
# Lecture typée et tolérante des valeurs d'un fichier .cfg
# -----------------------------------------------------------------------------
def _lire_reel(settings, cle, defaut, manquantes=None):
    """Lit une valeur numérique réelle, quel que soit son encodage."""
    brut = settings.value(cle, None)
    if brut is None:
        if manquantes is not None:
            manquantes.append(cle)
        return defaut
    try:
        return float(str(brut).replace(",", "."))
    except (TypeError, ValueError):
        journal(f"[CONFIG] valeur illisible pour {cle} : {brut!r}, "
                f"valeur par defaut {defaut} utilisee", niveau=logging.WARNING)
        return defaut


def _lire_entier(settings, cle, defaut, manquantes=None):
    """Lit un entier en tolérant une écriture décimale (« 14 » ou « 14.0 »)."""
    valeur = _lire_reel(settings, cle, None, manquantes)
    if valeur is None:
        return defaut
    try:
        return int(round(valeur))
    except (TypeError, ValueError):
        return defaut


def _lire_texte(settings, cle, defaut, manquantes=None):
    brut = settings.value(cle, None)
    if brut is None:
        if manquantes is not None:
            manquantes.append(cle)
        return defaut
    return str(brut)



# =============================================================================
# CALCUL DU TIMEBASE PICOSCOPE  —  implémentation UNIQUE
# =============================================================================
def calculer_timebase(frequence_hz, resolution_bits, nbre_periode, num_samples):
    """Calcule le réglage d'échantillonnage du PicoScope.

    La fenêtre d'acquisition contient EXACTEMENT `nbre_periode` périodes, ce qui
    élimine la fuite spectrale : maxSamples est une SORTIE (il dépend de la
    fréquence), pas une entrée.

    Parameters
    ----------
    frequence_hz : float   Fréquence d'excitation, en HERTZ (pas en kHz !).
    resolution_bits : int  Résolution ADC (8, 12, 14 ou 16).
    nbre_periode : int     Nombre de périodes dans la fenêtre.
    num_samples : int      Nombre d'échantillons souhaité (valeur indicative :
                           la quantification du timebase impose la valeur réelle).

    Returns
    -------
    (timebase, dt, samples_per_period, max_samples)
        timebase           : entier à transmettre au PicoScope
        dt                 : pas d'échantillonnage effectif, en secondes
        samples_per_period : nombre d'échantillons par période (entier exact)
        max_samples        : taille totale du bloc à acquérir
    """
    if frequence_hz <= 0:
        raise ValueError("calculer_timebase : frequence nulle ou negative")
    if nbre_periode < 1:
        raise ValueError("calculer_timebase : nbre_periode doit valoir >= 1")

    # la résolution arrivait de l'IHM sous forme de CHAÎNE.
    # Les tests « == 12 », « == 8 » échouaient donc toujours et TOUTES les
    # résolutions retombaient sur la formule 14 bits. On force l'entier ici.
    resolution_bits = int(resolution_bits)

    P = num_samples // nbre_periode          # points cibles par période
    if P < 1:
        raise ValueError("calculer_timebase : num_samples trop petit "
                         "devant nbre_periode")
    duration = nbre_periode / frequence_hz   # durée de la fenêtre (s)

    if resolution_bits in (12, 16):
        if (duration / num_samples) <= 8e-9:
            # branche log2 : horloge 500 MHz
            timebase = round(np.log(500_000_000 / (frequence_hz * P)) / np.log(2) + 1)
            dt = 2 ** (timebase - 1) / 500_000_000
        else:
            # branche linéaire 62,5 MHz (timebase >= 3)
            timebase = max(3, round(62_500_000 / (frequence_hz * P) + 3))
            dt = (timebase - 3) / 62_500_000
    elif resolution_bits == 8:
        timebase = 1
        dt = 2 ** timebase / 1_000_000_000       # 2 ns (500 MHz)
    else:
        # 14 bits — horloge 125 MHz, timebase minimal = 3 (dt = 8 ns)
        timebase = max(3, round(125_000_000 / (frequence_hz * P) + 2))
        dt = (timebase - 2) / 125_000_000

    samples_per_period = round(1.0 / (frequence_hz * dt))
    if samples_per_period < 2:
        raise ValueError(
            f"calculer_timebase : {samples_per_period} echantillon(s) par "
            f"periode a {frequence_hz} Hz — frequence trop elevee pour cette "
            f"resolution.")

    max_samples = nbre_periode * samples_per_period
    if max_samples % 2 != 0:                 # taille paire imposée par la FFT
        max_samples -= 1
        samples_per_period = max_samples // nbre_periode

    if max_samples > MAX_SAMPLES_LIMIT:
        log.warning("maxSamples=%d depasse la limite %d, bornage en cours",
                    max_samples, MAX_SAMPLES_LIMIT)
        max_samples = MAX_SAMPLES_LIMIT - (MAX_SAMPLES_LIMIT % nbre_periode)
        samples_per_period = max_samples // nbre_periode

    return timebase, dt, samples_per_period, max_samples


class Worker(QThread):
    """
    La class Worker est la partie acquisition du programme
    Elle est appelée par la classe Supervison lors de l'appuie sur le bouton Start
    """
    
    finished          = pyqtSignal()
    update_plot       = pyqtSignal(dict)   # rafraîchissement des 4 courbes
    update_ampli      = pyqtSignal(str, str)   # (texte du bouton, couleur)
    update_output     = pyqtSignal(str, str)   # (texte Output_button, couleur)
    update_resultats  = pyqtSignal(dict)   # valeurs finales -> MainWindow
    mesure_terminee   = pyqtSignal()       # réactivation des widgets de fin

    def __init__(self, parent=None, config_sonde=None):
        super().__init__(parent=parent)
        self.parent = parent
        self.Warnig = '0'        # état ampli (mis à jour par lecture())
        # La configuration de la sonde est INJECTÉE (plus de constante module
        # figée) : l'IHM peut activer/désactiver la voie D sans éditer le source.
        self.config_sonde = config_sonde if config_sonde is not None else CONFIG_SONDE

    def run(self):
        """
        Permet de mesurer les signaux et calculer les valeurs intrasecs de l'élément mesuré.

        Returns
        -------
        Ne renvois rien, mais modifie les variables globales


        """
        global Erreur , mode_filtre, fenetre_filtre, Sonde, gamma, Materiaux, Mode_asservissement, Hauteur, Di, De, Section, Outils, Ns1, Ns2, Rs, Rh, Type, Forme, Freq, Ampli, Gain, Nbre_periode, Kf, Nm_ref, mu_r, lm, num_samples, Resolution, Nbre_enregist, alpha, beta, rampe, iteration_max, cycle
        # ---------------------------------------------------------------------
        # Imports locaux au thread.
        # ---------------------------------------------------------------------
        import ctypes
        import usbtmc
        import time as tm
        from scipy import integrate
        from scipy.signal import hilbert, savgol_filter, sawtooth, resample
        from scipy.signal.windows import blackmanharris
        from scipy.interpolate import interp1d
        from scipy.fft import rfft, irfft
        from picosdk.ps5000a import ps5000a as ps
        from picosdk.functions import adc2mV, assert_pico_ok
        from numpy import linalg as LA
        from numpy.fft import fft, ifft
        from scipy import signal
        import time

       
        # ---------------------------------------------------------------------
        config_sonde  = self.config_sonde
        USE_PROBE_D   = config_sonde.active
        PROBE_SIGN    = config_sonde.signe
        PROBE_V_PER_A = config_sonde.v_per_a
        PROBE_N_TOURS = config_sonde.n_tours

        def find_range(f, x):
            uppermin2 = lowermin2 = 0
            for i in np.arange(x+1, len(f)-1):   # -1 : évite f[i+1] hors tableau
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
            # Calcul des coefficients de la tension dB/dt obtenu2200
            an_dB_sim = 2*np.real(np.fft.rfft(dB_reel))/len(dB_reel)
            bn_dB_sim = -2*np.imag(np.fft.rfft(dB_reel))/len(dB_reel)
            Fourier_dB_reel = symetrie(an_dB_sim, bn_dB_sim)
                      
            return Fourier_dB_des, Fourier_dB_reel, Fourier_B_des, Fourier_B_reel, Fourier_V_reel

        def THDN(signal, sample_rate=None):
            """
            Calcule le taux de distorsion harmonique (critère de convergence).

            CORRECTION #7 (CRITIQUE) : la version d'origine faisait
                signal -= np.mean(signal)
            ce qui, sur un ndarray, est une opération EN PLACE : la fonction
            modifiait le tableau de l'APPELANT. Autrement dit une fonction
            d'observation altérait les données mesurées qui servent ensuite au
            calcul des pertes. On travaille maintenant sur une copie.

            Le paramètre `sample_rate` n'a jamais été utilisé ; il est conservé
            en optionnel pour ne pas casser les appels existants.
            """
            signal = np.asarray(signal, dtype=float) - np.mean(signal)
            windowed = signal * blackmanharris(len(signal))
            total_rms = np.sqrt(np.mean(np.absolute(windowed)**2))
    
            # signal nul → THD = 0, évite NaN et le crash
            if total_rms < 1e-10:
               return 0.0
    
            f = rfft(windowed)
            i = np.argmax(abs(f))
            lowermin, uppermin = find_range(abs(f), i)
            f[lowermin: uppermin] = 0
            noise = irfft(f)
            THDN = np.sqrt(np.mean(np.absolute(noise)**2)) / total_rms
            return THDN * 100

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

        def ouvrir_gbf():
            g = usbtmc.Instrument(GBF_USB_VENDOR, GBF_USB_PRODUCT)
            g.timeout = 5000
            return g

        def couper_excitation(gbf):
            """Coupe la sortie GBF de façon GARANTIE. Ne lève JAMAIS."""
            for tentative in range(2):
                try:
                    if gbf is None:
                        gbf = ouvrir_gbf()
                    gbf.write("OUTP OFF")
                    return gbf
                except Exception as e:
                    journal(f"[SECURITE] echec OUTP OFF (essai {tentative+1}): {e}")
                    try:
                        gbf.close()
                    except Exception:
                        pass
                    gbf = None
            journal("[SECURITE] !!! coupure logicielle impossible — COUPER L'AMPLI A LA MAIN !!!")
            return None

        def attendre_pico_pret(chandle, timeout_s=PICO_READY_TIMEOUT):
            """Attend que le PicoScope soit prêt, avec timeout (remplace le busy-wait infini)."""
            ready = ctypes.c_int16(0)
            t0 = tm.time()
            while ready.value == 0:
                ps.ps5000aIsReady(chandle, ctypes.byref(ready))
                if tm.time() - t0 > timeout_s:
                    raise TimeoutError(f"PicoScope non pret apres {timeout_s}s")
                tm.sleep(0.001)   # évite le spin 100% CPU + rend la main au GIL

        def ouvrir_pico():
            """Ouvre l'unité UNE fois (gestion alim incluse) et renvoie le handle."""
            chandle = ctypes.c_int16()
            status = {}
            resolution = ps.PS5000A_DEVICE_RESOLUTION["PS5000A_DR_" + str(Num_resolution) + "BIT"]
            status["openunit"] = ps.ps5000aOpenUnit(ctypes.byref(chandle), None, resolution)
            try:
                assert_pico_ok(status["openunit"])
            except Exception:
                powerStatus = status["openunit"]
                if powerStatus in (282, 286):   # alim non connectée / port non USB3
                    status["cps"] = ps.ps5000aChangePowerSource(chandle, powerStatus)
                    assert_pico_ok(status["cps"])
                else:
                    raise
            return chandle

        def GBF(entree, gbf, allumer=True):
            """Envoie le signal au GBF via une session DÉJÀ ouverte (gbf).
            N'ouvre/ne ferme PAS la session. Applique un plafond dur d'amplitude."""
            # downsampling pour rester < 160 MSa/s (logique d'origine conservée)
            t = np.linspace(0, 1 / int(Frequence), len(entree))
            interpolation_entree = interp1d(t, entree)
            i = len(entree)
            while len(t) * Frequence > 159000000:
                i -= 1
                t = np.linspace(0, 1 / int(Frequence), i)
            entree = interpolation_entree(t)

            pk = max(np.max(entree), abs(np.min(entree)))
            if pk > PK_MAX_GBF:                              # <-- GARDE-FOU
                raise RuntimeError(f"Amplitude {pk:.3f} V > plafond {PK_MAX_GBF} V — excitation refusee")
            if pk <= 0:
                pk = 1.0                                     # évite la division par zéro

            gbf.write("DATA:VOL:CLE")
            # la concaténation « message2 += ... » dans une
            # boucle de 5000 points est quadratique (chaque += recopie toute la
            # chaîne). Un join est linéaire, pour un résultat identique au
            # caractère près (même format %.3f, même séparateur ", ").
            message2 = 'DATA:ARB myArb' + ''.join(
                ', ' + ("%.3f" % round(v / pk, 3)) for v in entree)
            gbf.write(message2)
            gbf.write('FUNCtion:ARB "myArb"')
            gbf.write(f'APPLy:ARB {len(entree) * Frequence},{pk},{0}')
            gbf.write("OUTP ON" if allumer else "OUTP OFF")

            # vérif erreurs GBF — BORNÉE (l'ancien `while errorCode != 0` pouvait boucler à l'infini)
            for _ in range(20):
                gbf.write('SYST:ERR?')
                rawError = gbf.read()
                parts = rawError.split(',')
                try:
                    errorCode = int(parts[0])
                except (ValueError, IndexError):
                    break
                if errorCode == 0:
                    break
                msg = parts[1].rstrip('\n') if len(parts) > 1 else ''
                journal(f'INSTRUMENT ERROR - code {errorCode}: {msg}')
                gbf.write('*CLS')
                raise RuntimeError(f'Erreur GBF {errorCode}: {msg}')

        def Mesure(Selection_Channel, Channel_ranges, chandle):
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

            status = {}

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

            # --- Étape 2 : choix du calibre, voie par voie (comme avant) ---
            # Ces acquisitions de calibrage ne servent qu'à déterminer ChRange ;
            # leurs données ne sont PAS utilisées dans le résultat final.
            ChRanges = [None] * len(Selection_Channel)      # au lieu de [None, None, None]
            ChRangesStr = [''] * len(Selection_Channel)     # version lisible pour le log
            for idx_channel, Numero_Channel in enumerate(Selection_Channel):  # Boucle séléction channel
                current_range = -1
                calibre_trouve = False
                # la boucle d'origine était un « while True » sans
                # borne. Si le signal dépassait le calibre 20 V (dernier de la
                # liste), current_range valait 10 et Channel_ranges[10] levait un
                # IndexError capturé par le except global : l'utilisateur voyait
                # « erreur » sans savoir qu'il s'agissait d'un dépassement de
                # plage. On borne la boucle et on lève un message explicite.
                while current_range + 1 < len(Channel_ranges):
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

                    timebase, dt, samples_per_period, maxSamples = calculer_timebase(
                        Frequence, Num_resolution, Nbre_periode, num_samples)

                    if Numero_Channel[0] == "PS5000A_CHANNEL_A":
                        journal(f"[acq] Freq={Frequence:.1f}Hz timebase={timebase} "
                                f"dt={dt*1e9:.3f}ns samples_per_period={samples_per_period} "
                                f"maxSamples={maxSamples} "
                                f"N_periodes={maxSamples/samples_per_period:.6f}",
                                niveau=logging.DEBUG)

                    preTriggerSamples = maxSamples // 2
                    postTriggerSamples = maxSamples - preTriggerSamples

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

                    attendre_pico_pret(chandle)

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

                    BuffersMax_calibrage = adc2mV(Numero_Channel[3], ChRange, maxADC)


                    if Num_resolution == 8:
                        # Valeur max pour 8 bit (voir datasheet)
                        Maximum_value = 32512
                    else:
                        # Pour les résolution autre que 8 bits (12, 14 1516), on prend la valeur maximum sur 16 bits
                        Maximum_value = (2**(16))/2-1
                    Maximum_value -= 300  # valeur arbitraire de sécuritée
                    Maximum_value = [Maximum_value, 0]

                    if np.max(BuffersMax_calibrage) < np.max(adc2mV(Maximum_value, ChRange, maxADC)):
                        calibre_trouve = True
                        break

                if not calibre_trouve:
                    raise RuntimeError(
                        f"Voie {Numero_Channel[0]} : le signal depasse le plus "
                        f"grand calibre disponible ({Channel_ranges[-1]}). "
                        f"Verifier le gain de l'amplificateur, la sonde "
                        f"d'attenuation ou le nombre de spires au secondaire.")

                ChRanges[idx_channel] = ChRange
                ChRangesStr[idx_channel] = Channel_ranges[current_range]

            # --- Étape 3 : acquisition finale simultanée des 3 voies dans le même bloc ---
            # Les 3 voies sont activées avec leur calibre retenu, puis chaque
            # ps5000aRunBlock/ps5000aGetValues capture A, B et C ensemble : la phase
            # relative B<->C est ainsi garantie (le jitter de trigger décale les 3
            # voies du même temps).
            coupling_type = ps.PS5000A_COUPLING["PS5000A_DC"]
            for idx_channel, Numero_Channel in enumerate(Selection_Channel):
                channel = ps.PS5000A_CHANNEL[Numero_Channel[0]]
                status[Numero_Channel[1]] = ps.ps5000aSetChannel(
                    chandle, channel, 1, coupling_type, ChRanges[idx_channel], 0)
                assert_pico_ok(status[Numero_Channel[1]])

            timeIntervalns = ctypes.c_float()
            returnedMaxSamples = ctypes.c_int32()
            status["getTimebase2"] = ps.ps5000aGetTimebase2(chandle, timebase, maxSamples, ctypes.byref(
                timeIntervalns), ctypes.byref(returnedMaxSamples), 0)
            assert_pico_ok(status["getTimebase2"])

            BuffersMaxParVoie = [np.ones((Nbre_enregistrement, maxSamples)) for _ in Selection_Channel]
            BuffersMinParVoie = [np.ones((Nbre_enregistrement, maxSamples)) for _ in Selection_Channel]

            for i in range(Nbre_enregistrement):
                status["runBlock"] = ps.ps5000aRunBlock(
                    chandle, preTriggerSamples, postTriggerSamples, timebase, None, 0, None, None)
                assert_pico_ok(status["runBlock"])

                attendre_pico_pret(chandle)

                for Numero_Channel in Selection_Channel:
                    Numero_Channel[3] = (ctypes.c_int16 * maxSamples)()
                    Numero_Channel[4] = (ctypes.c_int16 * maxSamples)()
                    source = ps.PS5000A_CHANNEL[Numero_Channel[0]]
                    status[Numero_Channel[2]] = ps.ps5000aSetDataBuffers(chandle, source, ctypes.byref(
                        Numero_Channel[3]), ctypes.byref(Numero_Channel[4]), maxSamples, 0, 0)
                    assert_pico_ok(status[Numero_Channel[2]])

                overflow = ctypes.c_int16()
                cmaxSamples = ctypes.c_int32(maxSamples)  # Nbre d'echantillons

                # downsample ratio = 0
                # downsample ratio mode = PS5000A_RATIO_MODE_NONE
                # Un seul GetValues remplit les buffers des 3 voies depuis CE MEME bloc
                status["getValues"] = ps.ps5000aGetValues(
                    chandle, 0, ctypes.byref(cmaxSamples), 0, 0, 0, ctypes.byref(overflow))
                assert_pico_ok(status["getValues"])

                for idx_channel, Numero_Channel in enumerate(Selection_Channel):
                    BuffersMaxParVoie[idx_channel][i] = adc2mV(Numero_Channel[3], ChRanges[idx_channel], maxADC)
                    BuffersMinParVoie[idx_channel][i] = adc2mV(Numero_Channel[4], ChRanges[idx_channel], maxADC)

            # La variable stockage sauvegarde les valeurs enregistrées sur les trois voies
            for BuffersMax in BuffersMaxParVoie:
                Stockage.append(BuffersMax)

            status["stop"] = ps.ps5000aStop(chandle)
            assert_pico_ok(status["stop"])

            return Stockage, cmaxSamples, timeIntervalns, ChRangesStr


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
            On reconstruit en temporelle puis on mesure le déphasage
            Pour finir, on enlève le délai aux signaux de base

            Pour un résultat plus précis on réaplique la transformée de Hilbert puis on fait la différence de phase

            Cette fonction fonctionne avec tous les signeaux périodiques (avec du bruit, triangle, ...)


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

            # On applique la transformée de Fourier
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


            # Code Clémentine
            try:
                _, a = start_from_zero(ChampBdes_prim)
                _, b = start_from_zero(ChampB_prim)
                lag = b - a
            except:
                lag = 0
            ChampB = np.roll(ChampB, lag)

            # FIX-SYNC : correction sub-sample par Hilbert SANS modifier l'amplitude.
            # L'ancienne version reconstruisait |H(B)| × exp(j·(angle+diff)), ce qui
            # créait un signal hybride et déformait B.  Ici on calcule seulement le
            # déphasage résiduel moyen (après le np.roll) et on l'applique comme un
            # décalage temporel fractionnaire via déphasage spectral, préservant la forme.
            try:
                Ha = hilbert(ChampBdes)
                Hb = hilbert(ChampB)
                # Phase résiduelle moyenne (on prend la médiane pour robustesse au bruit)
                phase_residual = np.median(np.angle(Ha) - np.angle(Hb))
                # Application du décalage fractionnaire dans le domaine fréquentiel
                N_sync = len(ChampB)
                freqs = np.fft.fftfreq(N_sync)
                spectrum = np.fft.fft(ChampB)
                # phase_residual correspond à un retard en fraction d'échantillon
                frac_delay = phase_residual / (2 * np.pi * freqs[1]) if np.abs(freqs[1]) > 1e-12 else 0
                # Limiter le décalage fractionnaire à ±1 échantillon pour éviter sur-correction
                frac_delay = np.clip(frac_delay, -1.0, 1.0)
                spectrum *= np.exp(-1j * 2 * np.pi * freqs * frac_delay)
                ChampB = np.fft.ifft(spectrum).real
            except Exception:
                pass  # En cas d'erreur, on garde le np.roll seul

            
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
            FF_reel = np.sqrt(trapz_compat(((dB_dt_sim+(1e-6))**2), temps_sim)/(max(temps_sim)-min(temps_sim))) / (
                trapz_compat(np.abs(dB_dt_sim), temps_sim)/(max(temps_sim)-min(temps_sim)))
            FF_theo = np.sqrt(trapz_compat((dB_dt_ref_sim**2), temps_sim)/(max(temps_sim)-min(temps_sim))) / (
                trapz_compat(np.abs(dB_dt_ref_sim), temps_sim)/(max(temps_sim)-min(temps_sim)))
            FF = 100*np.abs(FF_reel-FF_theo)/FF_theo
            err_dB_amp = 100 * \
                np.abs((np.max(dB_dt_ref_sim)-np.max(dB_dt_sim)) /
                       np.max(dB_dt_ref_sim))
          
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
            Mat_Broyden : tableau ()
                matrice de Broyden MISE À JOUR    (CORRECTION #1)
            f_0 : tableau ()
                mémoire de l'itération précédente MISE À JOUR   (CORRECTION #1)
            reinit : float
                facteur de réduction des gains MIS À JOUR       (CORRECTION #2)

            Notes
            -----
            CORRECTION #1 et #2 (CRITIQUES) : `Mat_Broyden`, `f_0` et `reinit`
            sont des PARAMÈTRES, donc des noms locaux. Les réaffecter à
            l'intérieur de la fonction ne modifiait rien chez l'appelant : leur
            mise à jour était détruite au retour. Conséquences :
              * quasi-Newton repartait à chaque itération de la Jacobienne
                initiale et de f_0 = 0 -> ce n'était plus un quasi-Newton mais
                une itération à gain fixe ;
              * le back-tracking restaurait la meilleure entrée mais relançait
                avec les MÊMES gains, donc reproduisait la même divergence.
            Ces trois valeurs sont désormais RETOURNÉES et réaffectées par
            l'appelant.

            Le fait que ce défaut soit passé inaperçu vient de l'usage des
            globales : `cycle`, `alpha`, `beta`, `gamma` sont déclarés `global`
            juste en dessous et se propagent, `reinit` et `Mat_Broyden` non — et
            rien ne le signalait.
            """


            global rampe, cycle, alpha, beta, gamma

            # Sauvegarde de la valeur d'entrée : permet de restituer à l'identique
            # le comportement d'origine si FIX_BACKTRACKING_REINIT vaut False.
            reinit_entree = reinit

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

                alpha_prim = 1 * rampe_alpha[cycle]
                beta_prim  = 1 * rampe_beta[cycle]

                # Calcul de la nouvelle entrée en calculant l'erreur entre les courbes
                #  protection division par zéro sur les normalisations
                norm_B   = np.max(np.abs(Fourier_B_des))   if np.max(np.abs(Fourier_B_des))   > 1e-12 else 1.0
                norm_dB  = np.max(np.abs(Fourier_dB_des))  if np.max(np.abs(Fourier_dB_des))  > 1e-12 else 1.0
                Fourier_e_k = Fourier_V + alpha_prim * (Fourier_B_des-Fourier_B_reel)/norm_B \
                                        + beta_prim  * (Fourier_dB_des-Fourier_dB_reel)/norm_dB

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
                # FIX-BACKTRACK : paramètres intermédiaires.
                # Avec filtre_entree() rétabli, l'entrée est plus propre, donc on peut
                # être un peu plus agressif qu'avec 0.7 (le bruit ne déclenche plus
                # de faux rollbacks), mais moins que l'ancien 0.3 qui bloquait parfois.
                if Forme == 'Sinusoïdale B':
                    if (THDN(derivChampB, num_samples) > 8 or np.max(ChampB) > 1.5*Ampli or np.max(derivChampB) > np.max(derivChampBdes)*1.5 or RMSE > np.min(RMSE_memoire)*1.10) and cycle > 2:
                        journal("Back-Tracking (sinusoïdal)")
                        indice = np.argmin(RMSE_memoire)
                        RMSE_min = RMSE_memoire[indice]
                        while len(RMSE_memoire) != 0:
                            RMSE_memoire.pop(-1)
                        RMSE_memoire.append(RMSE_min)
                        entree = entree_memoire[indice]
                        while len(entree_memoire) != 0:
                            entree_memoire.pop(-1)
                        entree_memoire.append(entree)
                        cycle = 0
                        reinit = max(reinit * 0.5, 0.05)  # 0.5 = compromis entre 0.3 et 0.7
                    else:
                        cycle += 1

                elif Forme == 'Triangulaire B':
                    if (THDN(derivChampB, num_samples) > 30 or np.max(ChampB) > 1.2*Ampli or np.max(derivChampB) > np.max(derivChampBdes)*1.2 or RMSE > np.min(RMSE_memoire)*1.10) and cycle > 2:
                        journal("Back-Tracking (triangulaire)")
                        indice = np.argmin(RMSE_memoire)
                        RMSE_min = RMSE_memoire[indice]
                        while len(RMSE_memoire) != 0:
                            RMSE_memoire.pop(-1)
                        RMSE_memoire.append(RMSE_min)
                        entree = entree_memoire[indice]
                        while len(entree_memoire) != 0:
                            entree_memoire.pop(-1)
                        entree_memoire.append(entree)
                        cycle = 0
                        reinit = max(reinit * 0.5, 0.05)
                    else:
                        cycle += 1
            elif Mode_asservissement == 'Quasi Newton':

                # protection division par zéro (Quasi-Newton)
                norm_B_qn  = np.max(np.abs(Fourier_B_des))  if np.max(np.abs(Fourier_B_des))  > 1e-12 else 1.0
                norm_dB_qn = np.max(np.abs(Fourier_dB_des)) if np.max(np.abs(Fourier_dB_des)) > 1e-12 else 1.0
                f_n = np.concatenate(((Fourier_dB_des - Fourier_dB_reel)/norm_dB_qn,
                                      (Fourier_B_des  - Fourier_B_reel )/norm_B_qn))  # écart sur la sortie f(x)

                
                if (Mat_Broyden is None
                        or np.ndim(Mat_Broyden) != 2
                        or Mat_Broyden.shape[0] != len(f_n)
                        or Mat_Broyden.shape[1] != len(f_n)):
                    log.warning(
                        "Quasi Newton : (re)initialisation de la matrice de "
                        "Broyden en %dx%d. Ce mode n'a PAS ete revalide depuis "
                        "la correction de dimensionnement — voir commentaire.",
                        len(f_n), len(f_n))
                    Mat_Broyden = np.eye(len(f_n)) * np.max(Amplitude)
                    f_0 = np.zeros(len(f_n))


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
                # GARDE : à la convergence, delta_f -> 0 et la division par
                # ||delta_f||² produisait des inf/NaN qui contaminaient
                # définitivement la matrice. On saute la mise à jour dans ce cas.
                norme_delta_f = LA.norm(delta_f)
                if norme_delta_f > 1e-12:
                    Mat_Broyden = Mat_Broyden + \
                        np.outer((Fourier_dk - Mat_Broyden @ delta_f) /
                                 (norme_delta_f * norme_delta_f), delta_f.T)
                else:
                    log.debug("Quasi Newton : delta_f negligeable, "
                              "mise a jour de Broyden ignoree.")

                f_0 = f_n  # Pour garder en mémoire la sortie pour la prochaine itération

            else:
                # mode d'asservissement inconnu -> échec
                # explicite. Auparavant, la fonction retournait silencieusement
                # l'entrée inchangée et la mesure tournait jusqu'à
                # iteration_max sans jamais rien asservir.
                raise ValueError(
                    f"Mode d'asservissement inconnu : {Mode_asservissement!r}. "
                    f"Valeurs attendues : 'PI FFT' ou 'Quasi Newton'.")

            
            if not FIX_BACKTRACKING_REINIT:
                reinit = reinit_entree

            return entree, RMSE, Mat_Broyden, f_0, reinit


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
            # journal("Harmonique optimal : ",optimal_harmoniques)
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

            # -----------------------------------------------------------------
            # Recherche de la fenêtre optimale pour le filtre Savitzky-Golay
            #
            # CORRECTION #20 : la boucle d'origine était un « while » dont la
            # seule condition d'arrêt portait sur la dynamique du RMSE, sans
            # AUCUNE borne sur la largeur de fenêtre. Dès que la fenêtre
            # dépassait la longueur du signal, savgol_filter levait un
            # ValueError non capturé qui interrompait toute la mesure. Rien ne
            # garantissait par ailleurs la terminaison de la boucle.
            #
            # On borne explicitement la fenêtre (et on garde le même pas de 50
            # ainsi que le même critère d'arrêt, pour ne pas changer le résultat
            # dans les cas nominaux).
            # -----------------------------------------------------------------
            fenetre_max = min(len(derivchampB) - 1, 1001)
            if fenetre_max % 2 == 0:          # savgol exige une fenêtre IMPAIRE
                fenetre_max -= 1

            fenetre = 51
            fenetre_opt = fenetre
            RMSE_min = 30
            RMSE = 30
            while (RMSE > 0.8 * RMSE_min and RMSE < 1.2 * RMSE_min
                   and fenetre <= fenetre_max):
                derivchampB4 = savgol_filter(derivchampB, window_length=fenetre,
                                             polyorder=3, mode="nearest")
                delta_dB = (x1_base - derivchampB4) / np.max(x1_base)
                RMSE = 100 * np.sqrt(np.mean(delta_dB * delta_dB))
                if RMSE < RMSE_min:
                    RMSE_min = RMSE
                    fenetre_opt = fenetre
                fenetre += 50

            # Sécurité : si le signal est plus court que 51 points, on ne filtre
            # pas plutôt que de planter.
            if fenetre_opt > fenetre_max:
                journal(f"[filtre] signal trop court ({len(derivchampB)} pts) "
                        f"pour une fenetre Savitzky-Golay : filtrage ignore.",
                        niveau=logging.WARNING)
                return np.asarray(signal_a_filtrer, dtype=float)

            derivchampB4 = savgol_filter(derivchampB, window_length=fenetre_opt,
                                         polyorder=3, mode=mode_filtre)

            if np.max(np.abs(fft_signal))!=0:

                delta_dB = (x1_base - 2*ifft(X1_harmonique*np.exp(1j*np.angle(X1))).real)/np.max(x1_base)
                RMSE_FFT = 100*np.sqrt(np.mean(delta_dB*delta_dB))
                journal('RMSE FFT',RMSE_FFT)
                delta_dB = (x1_base - derivchampB4)/np.max(x1_base)
                RMSE_savgol = 100*np.sqrt(np.mean(delta_dB*delta_dB))
                journal('RMSE Savgol',RMSE_savgol)

                # CORRECTION #20 : cette cascade de comparaisons pouvait sortir
                # SANS return si RMSE_FFT ou RMSE_savgol valait NaN (aucune des
                # deux égalités n'est alors vraie). La fonction renvoyait None,
                # qui se propageait dans adc2mVChCMax et provoquait un TypeError
                # obscur plusieurs dizaines de lignes plus loin.
                # On choisit maintenant explicitement, avec un cas par défaut.
                if not np.isfinite(RMSE_FFT) and not np.isfinite(RMSE_savgol):
                    journal("[filtre] les deux RMSE sont invalides (NaN) : "
                            "signal renvoye sans filtrage.",
                            niveau=logging.WARNING)
                    return np.asarray(signal_a_filtrer, dtype=float)

                rmse_fft_eff = RMSE_FFT if np.isfinite(RMSE_FFT) else np.inf
                rmse_sg_eff = RMSE_savgol if np.isfinite(RMSE_savgol) else np.inf

                if rmse_fft_eff <= rmse_sg_eff:
                    journal('FFT', niveau=logging.DEBUG)
                    return 2*ifft(X1_harmonique*np.exp(1j*np.angle(X1))).real
                journal('Savgol', niveau=logging.DEBUG)
                return derivchampB4

            else:
                # Signal identiquement nul : rien à filtrer. Le code d'origine
                # passait par un tableau factice [0,0,1,0] pour aboutir au même
                # résultat ; on écrit directement l'intention.
                journal("[filtre] spectre nul : signal renvoye tel quel.",
                        niveau=logging.DEBUG)
                return np.asarray(signal_a_filtrer, dtype=float)


        def filtre_entree(signal_entree, frequence_fondamentale, samples_period):
            """
            FIX-FILTRE-ENTREE : Filtre passe-bas sélectif pour le signal d'entrée GBF.
            
            Contrairement à filtre() qui compare au fondamental pur (et supprime les
            harmoniques de correction du PI-FFT), cette fonction conserve TOUS les
            harmoniques jusqu'au 20ème rang, puis coupe le bruit haute fréquence.
            
            Cela préserve la pré-distortion calculée par l'asservissement tout en
            supprimant le bruit numérique des allers-retours FFT/IFFT.
            
            Parameters
            ----------
            signal_entree : array
                Signal d'entrée à filtrer
            frequence_fondamentale : float
                Fréquence fondamentale du signal (Hz)
            samples_period : int
                Nombre d'échantillons par période
                
            Returns
            -------
            signal_filtre : array
                Signal filtré (harmoniques préservés, bruit HF supprimé)
            """
            from scipy.signal import butter, filtfilt
            
            # Fréquence d'échantillonnage effective
            fs = samples_period * frequence_fondamentale
            nyquist = fs / 2.0
            
            # Coupure au 20ème harmonique (préserve toutes les corrections PI-FFT)
            # mais avec une marge de sécurité pour ne pas couper trop près
            cutoff = min(20 * frequence_fondamentale, 0.85 * nyquist)
            
            if cutoff <= 0 or cutoff >= nyquist:
                return signal_entree  # Pas de filtrage possible
            
            try:
                b_filt, a_filt = butter(4, cutoff / nyquist, btype='low')
                signal_filtre = filtfilt(b_filt, a_filt, signal_entree, method='gust')
                return signal_filtre
            except Exception:
                return signal_entree  # En cas d'erreur, renvoyer le signal original


        # =====================================================================
        # SURVEILLANCE DE L'AMPLIFICATEUR
        # =====================================================================
        etat_ampli = {'port': None, 'detection_faite': False}

        def _detecter_port_ampli():
            """Cherche le port série de l'amplificateur. Appelé une seule fois."""
            for port in serial.tools.list_ports.comports():
                if port.device[:-1] != AMPLI_PREFIXE_PORT:
                    continue
                try:
                    with serial.Serial(port.device, baudrate=AMPLI_BAUDRATE,
                                       timeout=AMPLI_TIMEOUT_S) as ser:
                        ser.write(bytes.fromhex(TRAME_ETAT))
                        # Une réponse d'un octet = c'est bien l'amplificateur.
                        if len(ser.read().hex()) == 2:
                            journal(f"[AMPLI] detecte sur {port.device}")
                            return port.device
                except (serial.SerialException, OSError) as err:
                    # CORRECTION : le « except: » nu d'origine masquait tout,
                    # y compris les erreurs de droits sur /dev/ttyUSB*.
                    journal(f"[AMPLI] {port.device} inaccessible : {err}",
                            niveau=logging.DEBUG)
            return None

        def lecture(port_connection):
            """Lit l'état de l'ampli et le renvoie à l'IHM PAR SIGNAL."""
            with serial.Serial(port_connection, baudrate=AMPLI_BAUDRATE,
                               timeout=AMPLI_TIMEOUT_S) as ser:
                ser.write(bytes.fromhex(TRAME_ETAT))
                brut = ser.read().hex()
                if len(brut) != 2:                # pas de réponse exploitable
                    journal("[AMPLI] pas de reponse a la trame d'etat",
                            niveau=logging.WARNING)
                    return
                ready = list("{0:08b}".format(int(brut, 16)))

                if ready[0] == '1':
                    self.update_output.emit("ON", "green")

                # --- Octet d'état -------------------------------------------
                if ready[7] == '1':
                    self.update_ampli.emit("Ready", "green")
                    self.Warnig = '0'
                elif ready[6] == '1':
                    self.update_ampli.emit("Overload", "red")
                    self.Warnig = '1'
                elif ready[5] == '1':
                    self.update_ampli.emit("Overtemp", "red")
                    self.Warnig = '1'
                elif ready[3] == '1':
                    self.update_ampli.emit("Interlock Active", "red")
                    self.Warnig = '1'

                # --- Octet d'erreurs ----------------------------------------
                ser.write(bytes.fromhex(TRAME_ERREUR))
                brut_err = ser.read().hex()
                if len(brut_err) != 2:
                    return
                erreur = list("{0:08b}".format(int(brut_err, 16)))

                # Table (bit -> libellé) : remplace 7 blocs if/elif recopiés.
                defauts = ((7, "Transformateur"),
                           (6, "Limite Tension"),
                           (4, "Perte de puissance dépassée"),
                           (3, "Tension trop basse"),
                           (2, "Limite Courant"),
                           (1, "Erreur Hardware"))
                for bit, libelle in defauts:
                    if erreur[bit] == '1':
                        self.update_ampli.emit(libelle, "red")
                        self.Warnig = '1'
                        break

        def Amplificateur():
            """Met à jour self.Warnig à partir de l'état réel de l'ampli."""
            if not etat_ampli['detection_faite']:
                etat_ampli['port'] = _detecter_port_ampli()
                etat_ampli['detection_faite'] = True
                if etat_ampli['port'] is None:
                    journal("[AMPLI] AUCUN amplificateur detecte : la "
                            "surveillance des defauts est INACTIVE pour cette "
                            "mesure.", niveau=logging.WARNING)

            if etat_ampli['port'] is None:
                return
            try:
                lecture(etat_ampli['port'])
            except (serial.SerialException, OSError, ValueError) as err:
                # Une perte de liaison ne doit pas interrompre la mesure, mais
                # elle doit être VISIBLE : sans surveillance, un défaut ampli
                # (surchauffe, surcharge) ne serait plus détecté.
                journal(f"[AMPLI] liaison perdue : {err}", niveau=logging.WARNING)
                self.update_ampli.emit("Liaison perdue", "orange")
                etat_ampli['detection_faite'] = False   # nouvelle tentative au tour suivant

            
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

        bufferAMax = bufferAMin = bufferBMax = bufferBMin = bufferCMax = bufferCMin = bufferDMax = bufferDMin = []
        Selection_Channel = [["PS5000A_CHANNEL_A", "setChA", "setdataBuffersA", bufferAMax, bufferAMin],
                             ["PS5000A_CHANNEL_B", "setChB", "setdataBuffersB", bufferBMax, bufferBMin],
                             ["PS5000A_CHANNEL_C", "setChC", "setdataBuffersC", bufferCMax, bufferCMin]]
        if USE_PROBE_D:
            # FIX IndexError : cette définition LOCALE masque la globale ;
            # sans cet append, Mesure() n'acquiert que 3 voies et BufferMax[3] plante.
            Selection_Channel.append(["PS5000A_CHANNEL_D", "setChD", "setdataBuffersD", bufferDMax, bufferDMin])

        iteration = 0
        # Similaire à la foncrion moyennage des oscillo traditionnels
        Nbre_enregistrement = Nbre_enregist
        Num_resolution = Resolution
        Frequence = Freq * facteur_kHz_vers_Hz  # Conversion de la fréquence de kHz en Hz
        Amplitude = Ampli  # Amplitude désirée pour le  champ B
        N1 = Ns1
        N2 = Ns2
        Rsh = Rh
        w = Frequence*2*np.pi
        # Choix du nombre d'échantillon pour notre acquisition
        num_samples = int(num_samples)

        _tb_init, _dt, samples_per_period_init, _maxs_init = calculer_timebase(
            Frequence, Num_resolution, Nbre_periode, num_samples)
        journal(f"[init] timebase={_tb_init} dt={_dt*1e9:.3f}ns "
                f"spp_init={samples_per_period_init}", niveau=logging.DEBUG)

        # Garde matérielle : le PS5000A n'accepte pas plus de 14 bits en 4 voies.
        # (Le contrôle est désormais fait AUSSI dans l'IHM avant le lancement, ce
        #  qui évite de créer un dossier de session pour rien.)
        if config_sonde.active and int(Num_resolution) > RESOLUTION_MAX_4_VOIES:
            raise RuntimeError(
                f"Sonde de courant active (4 voies) : le PS5000A impose une "
                f"resolution <= {RESOLUTION_MAX_4_VOIES} bits "
                f"(demande : {Num_resolution} bits).")
        t = np.linspace(0, 1/int(Frequence), samples_per_period_init)

        Mat_Broyden = None
        f_0 = None
        cycle = indice = 0
        reinit = 1
        entree_memoire = []
        delta_B_memoire = []
        delta_dB_memoire = []
        RMSE_memoire = []

        # Suivi de la meilleure itération (BUG1)
        best_RMSE = float('inf')
        best_ChampB_tempo = None
        best_derivChampB_tempo = None
        best_ChampH2 = None
        best_ChampH2_probe = None

          
        # Facteur sonde = GAIN DE RÉCUPÉRATION (ADC -> vraie tension secondaire).
        sonde_str = str(Sonde)
        if   sonde_str == "1":     sonde_gain = 1.0
        elif sonde_str == "1/10":  sonde_gain = 10.0     # sonde ÷10  -> on multiplie par 10
        elif sonde_str == "1/100": sonde_gain = 100.0    # sonde ÷100 -> on multiplie par 100
        else:
            try:
                v = float(sonde_str)
                sonde_gain = (1.0 / v) if 0.0 < v < 1.0 else v   # tolère "0.1" ou "10"
            except (ValueError, TypeError):
                sonde_gain = 1.0
        journal(f"[SONDE] label={sonde_str!r} -> gain de recuperation = {sonde_gain}")

        # ---------------------------------------------------------------------
        # Création du signal désiré
        #
        # CORRECTION #10 (CRITIQUE) : il n'y avait AUCUN cas par défaut. Si
        # `Forme` ne valait exactement aucune des trois chaînes attendues (la
        # valeur initiale du module est d'ailleurs "Sinusoïdale", SANS le " B"),
        # aucun des if ne s'exécutait : ChampBdes gardait sa valeur globale 0 et
        # np.diff(0) plantait quelques lignes plus bas avec un message
        # incompréhensible. On échoue maintenant tout de suite, clairement.
        # ---------------------------------------------------------------------
        FORMES_SUPPORTEES = ('Sinusoïdale B', 'Triangulaire B', 'Trapézoïdal B')
        if Forme not in FORMES_SUPPORTEES:
            raise ValueError(
                f"Forme d'onde inconnue : {Forme!r}. "
                f"Valeurs attendues : {FORMES_SUPPORTEES}. "
                f"Verifier le combo « Forme » de la fenetre de configuration.")

        if Forme == 'Sinusoïdale B':
            ChampBdes = Amplitude*np.sin(w*t)#+Amplitude/20*np.sin(10*w*t)
            entree = 0.1*Amplitude*np.sin(w*t)

        elif Forme == 'Triangulaire B':
            # 1/2 pour éviter de dépasser la limite du GBF
            ChampBdes = Amplitude*sawtooth(w*t+np.pi/2, 0.5)
            entree = Amplitude*sawtooth(w*t+np.pi/2, 0.5)
            # La fenêtre du filtre ne peut pas dépasser la longueur du signal :
            # à haute fréquence, samples_per_period peut descendre sous 300.
            _fen = min(301, len(ChampBdes) - (1 - len(ChampBdes) % 2))
            if _fen >= 5:
                ChampBdes = savgol_filter(ChampBdes, window_length=_fen,
                                          polyorder=3, mode="mirror")  # adoucit le "pic"

        elif Forme == 'Trapézoïdal B':
            # np.asarray : trapzoid_signal renvoie une LISTE Python, pas un
            # ndarray, ce qui faisait échouer les opérations vectorielles en aval.
            ChampBdes = np.asarray(trapzoid_signal(w*t, np.pi/4, 0.05, Amplitude), dtype=float)
            entree = np.asarray(trapzoid_signal(w*t, np.pi/4, 0.05, Amplitude), dtype=float)


        # Calcule Dérivée du champ B désiré
        deriv = np.diff(ChampBdes) / np.diff(t)
        derivChampBdes = np.insert(deriv, 0, deriv[0])

        # Interpolation des signaux dans le but d'être plus fléxible sur le nombre d'échantillon
        f2 = interp1d(t, derivChampBdes)
        f3 = interp1d(t, ChampBdes)
        f1 = interp1d(t, entree)
                # ===== INITIALISATION DU LOGGER =====
        metadata = {
            # Conditions de mesure
            'Materiaux': str(Materiaux),
            'Mode_asservissement': str(Mode_asservissement),
            'Forme': str(Forme),
            'Frequence_Hz': float(Frequence),
            'Amplitude_T': float(Amplitude),
            'Gain_amplificateur': float(Gain),
            'Nm_ref' : str(Nm_ref),
            # Échantillon
            'Outils': str(Outils) if 'Outils' in dir() else 'N/A',
            'Section_mm2': float(Section),
            'lm_mm': float(lm),
            'mu_r_initial': float(mu_r),
            'Hauteur': float(Hauteur) if Hauteur else 0,
            # Configuration du banc
            'Ns1_primaire': int(Ns1),
            'Ns2_secondaire': int(Ns2),
            'Rs_ohm': float(Rs),
            'Rh_ohm': float(Rh),
            'Sonde': str(Sonde),
            'sonde_gain': sonde_gain,

            # Voie D — sonde de courant Keysight N2783B
            'USE_PROBE_D': bool(USE_PROBE_D),
            'PROBE_V_PER_A': float(PROBE_V_PER_A),
            'PROBE_N_TOURS': int(PROBE_N_TOURS),
            'PROBE_SIGN': int(PROBE_SIGN),
            
            # Paramètres de l'algorithme
            'iteration_max': int(iteration_max),
            'num_samples': int(num_samples),
            'Nbre_periode': int(Nbre_periode),
            'alpha_PI': float(alpha),
            'beta_PI': float(beta),
            'gamma_Newton': float(gamma),
            'rampe': int(rampe) if 'rampe' in dir() else 1,
            
            # Filtrage
            'mode_filtre': str(mode_filtre) if 'mode_filtre' in dir() else 'N/A',
            'fenetre_filtre': int(fenetre_filtre) if 'fenetre_filtre' in dir() else 0,
        }

        logger = MeasurementLogger(metadata)
        best_iteration_for_log = 0  # pour mémoriser le numéro de la meilleure itération
        # =====================================

        # début de la boucle d'acquisition
        # === ouverture UNIQUE des instruments (persistants) ===
        self.Warnig = '0'
        gbf = ouvrir_gbf()
        chandle = ouvrir_pico()

        # === Mesure des offsets de chaîne (excitation OFF) ===
        # Sépare l'offset de la voie scope (B) / sonde (D) du vrai courant DC

        offset_ih_shunt = 0.0
        offset_ih_probe = 0.0
        offsets_mesures = True
        if MESURE_OFFSETS_AU_DEMARRAGE:
            try:
                gbf = couper_excitation(gbf)               # sortie OFF garantie
                Buf0, _cmax0, _dt0, _cal0 = Mesure(Selection_Channel, Channel_ranges, chandle)
                offset_ih_shunt = float(np.mean(np.mean(Buf0[1], axis=0))) * facteur_mV_vers_V / Rsh
                if USE_PROBE_D:
                    offset_ih_probe = PROBE_SIGN * float(np.mean(np.mean(Buf0[3], axis=0))) \
                                      * facteur_mV_vers_V / (PROBE_V_PER_A * PROBE_N_TOURS)
                offsets_mesures = True
                journal(f"[OFFSET] shunt={offset_ih_shunt*1e3:.2f} mA  "
                      f"sonde={offset_ih_probe*1e3:.2f} mA (excitation OFF)")
            except Exception as e:
                journal("[OFFSET] mesure des offsets impossible :", e)
        try:
            logger.update_metadata({
                'offset_ih_shunt_mA': offset_ih_shunt * 1e3,
                'offset_ih_probe_mA': offset_ih_probe * 1e3,
                'offsets_mesures_au_demarrage': offsets_mesures,
            })
        except Exception as e:
            journal("[OFFSET] écriture metadata impossible :", e)
        status_log = 'iteration_max_atteinte'
        try:
            while True:
                # 0) Sécurité : état ampli AVANT toute excitation
                Amplificateur()                  # met à jour self.Warnig
                if self.Warnig == '1':
                    journal("[SECURITE] defaut amplificateur — arret de la mesure.")
                    status_log = 'arret_defaut_ampli'
                    break
                if self.parent.stop:
                    status_log = 'stop_utilisateur'
                    break

                if gbf is None:                  # session récupérée après une coupure
                    gbf = ouvrir_gbf()

                # 1) Excitation + acquisition : sortie COUPÉE quoi qu'il arrive
                try:
                    GBF(entree, gbf, allumer=True)
                    BufferMax, cmaxSamples, timeIntervalns, ChRangesStr = Mesure(
                        Selection_Channel, Channel_ranges, chandle)
                finally:
                    gbf = couper_excitation(gbf)   # OUTP OFF garanti à CHAQUE tour
                # Moyenne des Nbre_enregistrement pour lisser le signal
                adc2mVChAMax = np.mean(BufferMax[0], axis=0)
                adc2mVChBMax = np.mean(BufferMax[1], axis=0)
                adc2mVChCMax = np.mean(BufferMax[2], axis=0) * sonde_gain
                adc2mVChDMax = np.mean(BufferMax[3], axis=0) if USE_PROBE_D else None
                # Tableau contenant le nombre d'échantillon obtenu avec un pas régulier de TimeIntervalns
                timeI, interval = np.linspace(0, (cmaxSamples.value - 1) *
                                              timeIntervalns.value, cmaxSamples.value, retstep=True)

                # La fenêtre contient EXACTEMENT Nbre_periode périodes par construction (fix timebase).
                # samples_per_period est entier exact — aucun ré-échantillonnage nécessaire.
                samples_per_period = cmaxSamples.value // Nbre_periode

                # CORRECTION #22 : la période était jusqu'ici obtenue en
                # indexant le tableau des temps à l'indice samples_per_period,
                # ce qui sortait des bornes lorsque Nbre_periode valait 1 (le
                # tableau contient exactement Nbre_periode * samples_per_period
                # éléments, donc l'indice samples_per_period est le dernier
                # valide seulement à partir de 2 périodes). La valeur obtenue
                # est rigoureusement identique, mais elle est maintenant
                # calculée au lieu d'être lue dans le tableau.
                periode_s = 1.0 / Frequence

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
                # FIX-INTEGRAL : correction de la composante continue par (Max+Min)/2 sur
                # chaque période individuellement, puis suppression de la dérive résiduelle.
                # Le detrend(type='linear') sur 2 périodes déformait la forme d'onde B.
                # La vraie cause de non-fermeture du cycle est le résidu DC de V2, qu'on 
                # corrige mieux en soustrayant la moyenne de V2 AVANT intégration.
                v2_for_integration = samples_to_plotC * facteur_mV_vers_V  # Conversion de V2 de mV en V avant intégration
                # Soustraire la composante DC de V2 sur une période entière avant intégration
                # Cela empêche la dérive linéaire dans l'intégrale
                v2_mean_per_period = np.mean(v2_for_integration)  # buffer entier = Nbre_periode périodes
                v2_for_integration = v2_for_integration - v2_mean_per_period
            
                integral = cumtrapz_compat(v2_for_integration, timeC, initial=0)
            
                # Correction résiduelle (Max+Min)/2 pour recentrer
                Maxi = np.max(integral)
                Mini = np.min(integral)
                integral_corrige = integral - ((Mini + Maxi) / 2)

                # récupération de la fonction interpolée f2 calculé en début de PRGM,
                # On adapte notre dérivée à l'axe des temps
                derivChampBdes = f2(timeC[:samples_per_period])
                ChampBdes = f3(timeC[:samples_per_period])

                ChampB = integral_corrige/(-N2*Section*facteur_mm2_vers_m2)  
                derivChampB = samples_to_plotC * facteur_mV_vers_V / (-N2*Section*facteur_mm2_vers_m2)  # Conversion V2 de mV en V et section de mm² en m² pour obtenir dB/dt
            
                #Calcul du courant au primaire
                ih = samples_to_plotB * facteur_mV_vers_V / Rsh  # Conversion de la tension shunt de mV en V, puis division par Rsh pour obtenir le courant (A)
            
                ChampH23 = N1*ih/(lm*facteur_mm_vers_m)  # Conversion de la longueur magnétique lm de mm en m pour obtenir H en A/m
                # filtrage du champ H
                #ChampH2 = savgol_filter(ChampH23, window_length=fenetre_filtre, polyorder=3, mode= mode_filtre)
                #ChampH2 = detrend(ChampH2, type='constant')
                
                # youssef : n_harm est desormais lu sur la globale nb_harmoniques_H
                # (reglable dans la fenetre "Parametres d'acquisition") au lieu
                # d'etre fige a 15.
                def filtre_harmonique(sig, n_harm=nb_harmoniques_H):
                    X  = np.fft.rfft(sig)
                    Xf = np.zeros_like(X)
                    Xf[1:n_harm+1] = X[1:n_harm+1]     # fondamental + n_harm harmoniques, continu retiré
                    return np.fft.irfft(Xf, n=len(sig))

                ChampH2 = filtre_harmonique(ChampH23, n_harm=nb_harmoniques_H)
                if USE_PROBE_D:
                    samples_to_plotD = adc2mVChDMax[:Nbre_periode * samples_per_period]
                    ih_probe = PROBE_SIGN * samples_to_plotD * facteur_mV_vers_V / (PROBE_V_PER_A * PROBE_N_TOURS)
                    ChampH23_probe = N1 * ih_probe / (lm * facteur_mm_vers_m)
                    ChampH2_probe  = filtre_harmonique(ChampH23_probe, n_harm=nb_harmoniques_H)
                    ChampH2_probe_tempo = ChampH2_probe.copy()

                    # Comparaison directe shunt/sonde sur le fondamental (avant toute synchro)
                    ncyc = Nbre_periode          # fondamental au bin Nbre_periode du buffer complet
                    Fs = np.fft.rfft(ChampH23)
                    Fp = np.fft.rfft(ChampH23_probe)

                    ratio_I  = np.abs(Fp[ncyc]) / max(np.abs(Fs[ncyc]), 1e-15)
                    dphi_deg = np.degrees(np.angle(Fp[ncyc] / Fs[ncyc]))
                    dphi_deg = (dphi_deg + 180.0) % 360.0 - 180.0
                    journal(
                        f"[FFT] Bin={ncyc}  "
                        f"Fs={Fs[ncyc]:.6f}  "
                        f"Fp={Fp[ncyc]:.6f}  "
                        f"|Fs|={np.abs(Fs[ncyc]):.6f}  "
                        f"|Fp|={np.abs(Fp[ncyc]):.6f}  "
                        f"∠Fs={np.degrees(np.angle(Fs[ncyc])):+.3f}°  "
                        f"∠Fp={np.degrees(np.angle(Fp[ncyc])):+.3f}°"
                    )
                    # DC réellement injecté par l'ampli = moyenne mesurée - offset de chaîne
                    idc_shunt = float(np.mean(ih[:samples_per_period])) - offset_ih_shunt
                    idc_probe = float(np.mean(ih_probe[:samples_per_period])) - offset_ih_probe
                    journal(f"[SONDE-D] |Ip|/|Ish|={ratio_I:.4f}  Δφ={dphi_deg:+.3f}°  "
                          f"Idc: shunt={idc_shunt*1e3:+.1f} mA  sonde={idc_probe*1e3:+.1f} mA")
                # On conserve nos signaux car ils pourront être modifié par la suite
                derivChampB_tempo = derivChampB.copy()
                ChampB_tempo      = ChampB.copy()
                ChampH2_tempo     = ChampH2.copy()   # CYCLE-FIX2 : sauvegarde avant synchro

                # Synchro des signaux
                ChampB, lag = Synchronisation(
                    ChampBdes, ChampB[:samples_per_period])

                derivChampB, lag1 = Synchronisation(
                    derivChampBdes, derivChampB[:samples_per_period])

                # CYCLE-FIX2 : aligner ChampH2 sur le même décalage que ChampB
                # (sans cela, B et H ont des phases différentes → cycle B-H non fermé)
                ChampH2 = np.roll(ChampH2, lag)
                if USE_PROBE_D:
                   ChampH2_probe = np.roll(ChampH2_probe, lag)
            
            
            

                # Alignement de entree sur la grille samples_per_period (variable selon fréquence).
                # scipy.signal.resample (FFT périodique) préserve la forme d'onde sur une période
                # complète ; fonctionne dans les deux sens (upsampling ET downsampling).
                if len(entree) != samples_per_period:
                    entree = resample(entree, samples_per_period)

                

                # Calcule de la nouvelle entrée après la vérification des conditions de fin pour avoir
                # l'entrée de la convergence et pas la suivante
                # CORRECTIONS #1 et #2 : on récupère MAINTENANT l'état interne mis à
                # jour (matrice de Broyden, mémoire f_0, facteur de gain reinit).
                # Sans cela, ces trois valeurs étaient recalculées puis jetées à
                # chaque itération.
                entree_tempo, RMSE, Mat_Broyden, f_0, reinit = Asservissement(
                    Mode_asservissement, ChampBdes, ChampB[:samples_per_period],
                    derivChampBdes, derivChampB[:samples_per_period], entree,
                    timeC[:samples_per_period], f_0, Mat_Broyden, reinit)

                # CONV2-FIX : remplacement de filtre(entree_tempo) par filtre_entree()
                # L'ancien filtre() comparait au fondamental pur et supprimait les harmoniques
                # de correction. filtre_entree() est un passe-bas qui conserve les 20 premiers
                # harmoniques (corrections PI-FFT) et ne coupe que le bruit HF.
                entree_tempo = filtre_entree(entree_tempo, Frequence, samples_per_period)

                # Sauvegarde de la meilleure itération (BUG1 + CYCLE-FIX2)
                # On sauvegarde ChampH2_tempo (pre-sync) pour cohérence avec ChampB_tempo
                if RMSE < best_RMSE:
                    best_RMSE = RMSE
                    best_ChampB_tempo      = ChampB_tempo.copy()
                    best_derivChampB_tempo = derivChampB_tempo.copy()
                    best_ChampH2           = ChampH2_tempo.copy()
                    if USE_PROBE_D:
                        best_ChampH2_probe = ChampH2_probe_tempo.copy()
                    best_iteration_for_log = iteration

                # Mise en forme de l'axe des temps (pour l'affichage)
                self.parent.main_window.timeC = timeC[:samples_per_period]
                unite_T = "s"
                timeC_scaled = timeC.copy()
                if periode_s < 1e-6:
                    unite_T = "ns"
                    timeC_scaled = timeC * 1e9
                elif periode_s < 1e-3:
                    unite_T = "µs"
                    timeC_scaled = timeC * 1e6
                elif periode_s < 1:
                    unite_T = "ms"
                    timeC_scaled = timeC * 1e3

                # Calcul des indicateurs pour l'affichage labels
                thd_val = THDN(derivChampB, num_samples)
                ff_val = FF(derivChampB, periode_s)
                ff_des = FF(derivChampBdes, periode_s)
                thd_des = THDN(derivChampBdes, num_samples)
                bmax_ok = (Amplitude*0.995 < np.max(np.abs(ChampB))) and (Amplitude*1.005 > np.max(np.abs(ChampB)))
                thd_ok  = thd_val < thd_des + 2
                ff_ok   = (ff_val < ff_des*1.01) and (ff_val > ff_des*0.99)

                # Émission du signal vers le thread principal (BUG2 : thread-safe)
                self.update_plot.emit({
                    'iteration': iteration,
                    'entree': entree[:samples_per_period].tolist(),
                    'ChampB': ChampB[:samples_per_period].tolist(),
                    'ChampBdes': ChampBdes.tolist(),
                    'ChampH': ChampH2[:samples_per_period].tolist(),
                    'derivChampB': derivChampB[:samples_per_period].tolist(),
                    'derivChampBdes': derivChampBdes.tolist(),
                    'timeC': timeC_scaled[:samples_per_period].tolist(),
                    'unite_T': unite_T,
                    'N2': N2,
                    'Section': Section,
                    'thd': round(thd_val, 2),
                    'ff': round(ff_val, 2),
                    'bmax_des': round(np.max(ChampBdes), 3),
                    'bmax': round(np.max(ChampB), 3),
                    'rmse': round(RMSE, 2),
                    'hmax': round(np.max(ChampH2), 2),
                    'imax_mA': round(np.max(ih)*1000),
                    'imax': round(np.max(ih), 2),
                    'bkmax_color': 'green' if bmax_ok else 'black',
                    'thd_color':   'green' if thd_ok  else 'black',
                    'ff_color':    'green' if ff_ok   else 'black',
                })
                            # ===== LOG DE L'ITÉRATION COURANTE =====
                # Calcul du delta_B et delta_dB (cohérent avec ce que fait Asservissement)
                try:
                    deltaB_val = float(np.max(np.abs(ChampBdes - ChampB[:samples_per_period])) / max(np.max(np.abs(ChampBdes)), 1e-12))
                    deltadB_val = float(np.max(np.abs(derivChampBdes - derivChampB[:samples_per_period])) / max(np.max(np.abs(derivChampBdes)), 1e-12))
                except Exception:
                    deltaB_val = deltadB_val = float('nan')

                # Suivi de la meilleure itération
            

                scalars = {
                    'iteration': iteration,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    'RMSE': float(RMSE),
                    'THD_mesure': float(thd_val),
                    'THD_reference': float(thd_des),
                    'FF_mesure': float(ff_val),
                    'FF_reference': float(ff_des),
                    'B_max': float(np.max(np.abs(ChampB[:samples_per_period]))),
                    'B_max_reference': float(np.max(np.abs(ChampBdes))),
                    'dB_max': float(np.max(np.abs(derivChampB[:samples_per_period]))),
                    'dB_max_reference': float(np.max(np.abs(derivChampBdes))),
                    'H_max': float(np.max(np.abs(ChampH2[:samples_per_period]))),
                    'I_max_mA': float(np.max(np.abs(ih)) * 1000),
                    'delta_B': deltaB_val,
                    'delta_dB': deltadB_val,
                    'cycle': int(cycle),
                    'reinit': float(reinit),
                    'Idc_shunt_mA': idc_shunt*1e3 if USE_PROBE_D else float(np.mean(ih[:samples_per_period]))*1e3,
                    'Idc_probe_mA': idc_probe*1e3 if USE_PROBE_D else float('nan'),
                    'ratio_Iprobe_Ishunt': float(ratio_I) if USE_PROBE_D else float('nan'),
                    'dphi_probe_shunt_deg': float(dphi_deg) if USE_PROBE_D else float('nan'),
                    'H_max_probe': float(np.max(np.abs(ChampH2_probe[:samples_per_period]))) if USE_PROBE_D else float('nan'),
                    'calibreA': ChRangesStr[0] if len(ChRangesStr) > 0 else '',
                    'calibreB': ChRangesStr[1] if len(ChRangesStr) > 1 else '',
                    'calibreC': ChRangesStr[2] if len(ChRangesStr) > 2 else '',
                    'calibreD': ChRangesStr[3] if (USE_PROBE_D and len(ChRangesStr) > 3) else '',
                    'amplitude_entree_V': float(np.max(np.abs(entree))),
                    'lag_synchro': int(lag),
                    'converge': int(bool(
                        (Amplitude*1.005 > np.max(np.abs(ChampB))) and
                        (Amplitude*0.995 < np.max(np.abs(ChampB))) and
                        (thd_val < thd_des + 3) and
                        (ff_val < ff_des * 1.01) and (ff_val > ff_des * 0.99)
                    ))
                }
                n_dispo = len(ChampB)                     # taille totale du buffer
                n_2per  = min(2 * samples_per_period, n_dispo) 
                waveforms = {
                    'entree':         np.asarray(entree[:samples_per_period],        dtype=np.float32),
                    'ChampB':         np.asarray(ChampB[:samples_per_period],        dtype=np.float32),
                    'ChampBdes':      np.asarray(ChampBdes,                          dtype=np.float32),
                    'ChampH2':        np.asarray(ChampH2[:samples_per_period],       dtype=np.float32),
                    'derivChampB':    np.asarray(derivChampB[:samples_per_period],   dtype=np.float32),
                    'derivChampBdes': np.asarray(derivChampBdes,                     dtype=np.float32),
                    'timeC':          np.asarray(timeC[:samples_per_period],         dtype=np.float64),
                    'ih':             np.asarray(ih[:samples_per_period],            dtype=np.float32),
                    # === NOUVEAU : signaux sur 2 périodes pour le cycle BH ===
                    'v2_for_integration':    np.asarray(v2_for_integration,   dtype=np.float32),
                    'ChampH23':   np.asarray(ChampH23,  dtype=np.float32),
                    # === Signaux BRUTS de l'itération (avant synchro / roll / filtrage) ===
                    # Buffer complet (Nbre_periode périodes), B et H mutuellement en phase.
                    'ChampB_brut':      np.asarray(ChampB_tempo,      dtype=np.float32),
                    'ChampH2_brut':     np.asarray(ChampH2_tempo,     dtype=np.float32),
                    'derivChampB_brut': np.asarray(derivChampB_tempo, dtype=np.float32),
                }
                if USE_PROBE_D:
                    waveforms['ih_probe'] = np.asarray(ih_probe[:samples_per_period], dtype=np.float32)
                    waveforms['ChampH2_probe_brut'] = np.asarray(ChampH2_probe_tempo, dtype=np.float32)

                # Sauvegarde optionnelle de la Jacobienne (Quasi Newton seulement, gros volume)
                if Mode_asservissement == 'Quasi Newton':
                    # On sauvegarde 1 fois sur 5 pour ne pas exploser le disque
                    if iteration % 5 == 0:
                        waveforms['Mat_Broyden'] = np.asarray(Mat_Broyden, dtype=np.float32)

                logger.log_iteration(scalars, waveforms)
                # ========================================
                # On vérifie les critère de convergence
                # LISIBILITÉ : le test d'origine tenait sur une seule ligne de
                # 300 caractères et recalculait 4 fois THDN et FF déjà obtenus
                # plus haut (thd_val, thd_des, ff_val, ff_des). Les arguments
                # étant identiques, le résultat est RIGOUREUSEMENT le même —
                # seules disparaissent 4 FFT inutiles par itération.
                b_max_mesure = np.max(np.abs(ChampB))
                critere_amplitude = (Amplitude * 0.995 < b_max_mesure < Amplitude * 1.005)
                critere_thd       = (thd_val < thd_des + 3)
                critere_ff        = (ff_des * 0.99 < ff_val < ff_des * 1.01)
                converge = bool(critere_amplitude and critere_thd and critere_ff)
                if converge or iteration == iteration_max or self.parent.stop == True:

                    if converge:
                        # Convergence réelle : restaure signaux avant synchro pour cohérence B/H
                        ChampB      = ChampB_tempo
                        derivChampB = derivChampB_tempo
                        ChampH2     = ChampH2_tempo
                        if USE_PROBE_D:
                            # même itération, même état pré-synchro que ChampH2
                            ChampH2_probe = ChampH2_probe_tempo
                    else:
                        # Stop ou max_iter sans convergence : restaure la meilleure itération (BUG1)
                        if best_ChampB_tempo is not None:
                            ChampB      = best_ChampB_tempo
                            derivChampB = best_derivChampB_tempo
                            ChampH2     = best_ChampH2
                            if USE_PROBE_D and best_ChampH2_probe is not None:
                                ChampH2_probe = best_ChampH2_probe
                        else:
                            ChampB      = ChampB_tempo
                            derivChampB = derivChampB_tempo
                            ChampH2     = ChampH2_tempo
                            if USE_PROBE_D:
                                ChampH2_probe = ChampH2_probe_tempo

                    arret_utilisateur = bool(self.parent.stop)
                    self.mesure_terminee.emit()

                    # ===== FINALISATION DU LOGGER =====
                    if converge:
                        status_log = 'converge'
                    elif arret_utilisateur:
                        status_log = 'stop_utilisateur'
                    else:
                        status_log = 'iteration_max_atteinte'

                    logger.finalize(status=status_log, best_iteration=best_iteration_for_log)
                    # ====================================
                    break
                iteration += 1

                entree=entree_tempo
                # Retour au début de la boucle

            # Résulats de mesures (calcule des pertes)
        
            # -----------------------------------------------------------------
            # Hc et Br étaient calculés sans aucune garde.
            # Si le signal était faible ou bruité, la liste des passages par
            # zéro pouvait être VIDE : np.mean([]) renvoie alors NaN (avec un
            # simple RuntimeWarning), et ce NaN partait tel quel dans le fichier
            # de résultats sans que rien ne le signale. Dans un contexte de
            # métrologie c'est inacceptable : on préfère une valeur nulle
            # explicitement signalée dans le journal.
            # -----------------------------------------------------------------
            ChampB_nul = np.where(np.diff(np.sign(ChampB)))[0]
            Hcs = [np.abs(ChampH2[v]) for v in ChampB_nul if v < len(ChampH2)]
            if Hcs:
                Hc = float(np.mean(Hcs))          # champ coercitif
            else:
                Hc = 0.0
                journal("[RESULTAT] Hc incalculable : aucun passage par zero de "
                        "B detecte. Signal trop faible ou trop bruite ?",
                        niveau=logging.WARNING)

            ChampH2_nul = np.where(np.diff(np.sign(ChampH2)))[0]
            Brs = [np.abs(ChampB[v]) for v in ChampH2_nul[:2] if v < len(ChampB)]
            if Brs:
                Br = float(np.mean(Brs))          # champ rémanent
            else:
                Br = 0.0
                journal("[RESULTAT] Br incalculable : moins de 2 passages par "
                        "zero de H detectes.", niveau=logging.WARNING)

            spp    = samples_per_period
            centre = spp // 4
            start  = int(np.clip(centre , 0, len(ChampB_tempo) - 1.25*spp))
            sl     = slice(start, start + spp)

            Pv = trapz_compat(ChampH2[sl] * derivChampB[sl],
                          x=timeC[:samples_per_period]) / (periode_s)

            if Pv<0 : # dans le cas de faible signaux, on peut avoir le mauvais déphasage (déphasé de pi). 
                ChampB=np.negative(ChampB)
                Pv*=-1
                journal("les pertes inverse")
        
            # division par zéro si le champ H mesuré est nul
            # (sonde débranchée, shunt en court-circuit, excitation absente).
            h_max_mesure = float(np.max(ChampH2))
            if abs(h_max_mesure) > 1e-12:
                mu_r = float(np.max(ChampB)) / (h_max_mesure * mu_0)  # mu_0 = 4π×10⁻⁷ H/m
            else:
                mu_r = 0.0
                journal("[RESULTAT] mu_r incalculable : champ H maximal nul.",
                        niveau=logging.WARNING)
            Pv_probe = None
            if USE_PROBE_D:
                Pv_probe = trapz_compat(ChampH2_probe[sl] * derivChampB[sl],
                                    x=timeC[:samples_per_period]) / (periode_s)
                if Pv < 0:                      # garder les deux dans la même convention de signe
                    Pv_probe *= -1
                ecart = 100.0 * (Pv_probe - abs(Pv)) / max(abs(Pv), 1e-12)
                journal(f"[PERTES] shunt={abs(Pv):.1f} W/m³   sonde={Pv_probe:.1f} W/m³   écart={ecart:+.1f}%")
                                
        

            try:
                # Les tableaux numpy peuvent être partagés entre threads sans
                # danger ici (le worker n'y touche plus après ce point) ;
                # en revanche l'AFFICHAGE doit passer par un signal.
                self.parent.ChampH = ChampH2[sl]
                self.parent.main_window.ChampH = ChampH2[sl]
                self.parent.ChampB = ChampB[sl]
                self.parent.main_window.ChampB = ChampB[sl]
                self.parent.main_window.derivChampB = derivChampB[sl]

                self.update_resultats.emit({
                    'bmax': float(np.max(ChampB)),
                    'freq': float(Frequence),
                    'hc': float(Hc),
                    'br': float(Br),
                    'hmax': float(np.max(ChampH2)),
                    'mu_r': float(mu_r),
                    'pv': float(Pv),
                    'pv_probe': (float(Pv_probe) if Pv_probe is not None else None),
                })

            except Exception as e:   # VÉRIF2 : réactivé avec gestion d'erreur propre
                journal('erreur (post-boucle) : ', e)
                Erreur.append(str(e))
                self.parent.ChampH = np.zeros(num_samples)
                self.parent.main_window.ChampH = np.zeros(num_samples)
                self.parent.ChampB = np.zeros(num_samples)
                self.parent.main_window.ChampB = np.zeros(num_samples)
                self.parent.main_window.derivChampB = np.zeros(num_samples)
                self.update_resultats.emit({'echec': True})

        except Exception as e:
            log.exception("[ERREUR run] %s", e)
            Erreur.append(str(e))
            try:
                self.update_resultats.emit({'echec': True})
            except Exception:
                pass
        finally:
            # COUPURE D'EXCITATION GARANTIE sur TOUS les chemins de sortie
            couper_excitation(gbf)
            try:
                if gbf is not None:
                    gbf.close()
            except Exception:
                pass
            try:
                if chandle is not None:
                    ps.ps5000aStop(chandle)
                    ps.ps5000aCloseUnit(chandle)
            except Exception:
                pass
            self.finished.emit()



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
        self.Rh_spin.setValue(R_SHUNT_OHM)
        self.Rh_spin.setEnabled(False)
        self.Rs_spin.setValue(Rs)
        self.Type_combo.setCurrentText(Type)
        self.forme_combo.setCurrentText(Forme)
        self.freq_spin.setValue(Freq)
        self.Ampli_spin.setValue(Ampli)
        self.GA_spin.setValue(Gain)


        self.nbre_periode_slider.setMinimum(NBRE_PERIODE_MIN)
        self.nbre_periode_slider.setValue(max(Nbre_periode, NBRE_PERIODE_MIN))
        self.Kf_spin.setValue(Kf)
        self.Nm_ref_edit.setText(Nm_ref)
        self.Mu_spin.setValue(mu_r)
        self._connectActions() # connect les boutonds
        self.lm_spin.setValue(lm)
        self.outils_combo.currentTextChanged.connect(self.selectionchange)
        self.section_spin.valueChanged.connect(self.calcul_kf)
        self.Kf_spin.valueChanged.connect(self.calcul_section)
        # GUI-FIX : recalcul Section + lm dès que l'une des dimensions géométriques change
        self.Di_spin.valueChanged.connect(self.recalcul_geometrie)
        self.De_spin.valueChanged.connect(self.recalcul_geometrie)
        self.Hauteur_spin.valueChanged.connect(self.recalcul_geometrie)
        
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
        H=Ampli/(mu_r*mu_0)  # Calcul du champ H à partir de B désiré et de mu_0 (4π5×10⁻⁷ H/m)
        Imax=H*lm*facteur_mm_vers_m/Ns1  # Conversion de lm de mm en m pour obtenir le courant max

        if H!=0 and Imax!=0 and Ns1!=0:

            #Calcule N1
            H=Ampli/(mu_r*mu_0)  # Recalcul de H avec mu_0 = 4π×10⁻⁷ H/m
            w=2*np.pi*Freq*facteur_kHz_vers_Hz  # Conversion de la fréquence de kHz en rad/s
            N1=Ns1
            Imax=H*lm*facteur_mm_vers_m/N1  # Conversion de lm de mm en m
            Imax_des=0.12

            while H*lm*facteur_mm_vers_m/N1<0.9*Imax_des or H*lm*facteur_mm_vers_m/N1>1.1*Imax_des:  # Conversion de lm de mm en m
                e=(Imax_des-(H*lm*facteur_mm_vers_m/N1))/Imax_des  # Conversion de lm de mm en m
                N1=N1-0.5*e
                Imax=H*lm*facteur_mm_vers_m/N1  # Conversion de lm de mm en m

            N1=int(N1)
            Rmax=round(N1*N1*Section*facteur_mm2_vers_m2*Ampli*w/(H*lm*facteur_mm_vers_m),2)  # Conversion section mm²→m² et lm mm→m
            self.R_label.setText(str(Rmax))

            V1max=N1*Section*facteur_mm2_vers_m2*w*Ampli+Rmax*Imax  # Conversion section mm²→m²

            while N1*Section*facteur_mm2_vers_m2*w*Ampli<0.6*V1max:  # Conversion section mm²→m²
                V1max=N1*Section*facteur_mm2_vers_m2*w*Ampli+Rmax*Imax  # Conversion section mm²→m²
                e=(0.7*V1max-(N1*Section*facteur_mm2_vers_m2*w*Ampli))  # Conversion section mm²→m²
                Rmax=Rmax-0.5*e

            self.R_label.setText(str(round(Rmax)))
            Rmax=round(Rmax)
            if Rmax==0:
                self.R_label.setText("< 1 " )

            V1max=N1*Section*facteur_mm2_vers_m2*w*Ampli+Rmax*Imax  # Conversion section mm²→m²
            
            self.N1_label.setText(str(N1))


    def import_sequence(self):
        global Freq_tab,Ampli_tab,Freq_tab_tempo 
        
        config_path = demander_fichier_ouverture(
            self, "Charger une séquence", "sequence")
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
        # CORRECTION #19 : « disconnect() » sans argument supprime TOUTES les
        # connexions du signal, pas seulement celle qu'on veut éviter. Comme la
        # ligne finale ne reconnecte que calcul_section, toute autre connexion
        # (par exemple Calcul_R_N1, branchée ailleurs sur ce même signal) était
        # définitivement perdue au premier changement de valeur.
        # blockSignals() fait exactement ce qui est voulu : suspendre
        # temporairement l'émission, sans toucher aux connexions.
        self.Kf_spin.blockSignals(True)
        Di = self.Di_spin.value()
        De = self.De_spin.value()
        Hauteur = self.Hauteur_spin.value()
        if Di != 0 and De != 0 and Hauteur != 0:
            Stheo = Hauteur*facteur_mm_vers_m*(De*facteur_mm_vers_m-Di*facteur_mm_vers_m)/2  # Conversion des dimensions mm→m pour calculer la section théorique en m²
            Kf = var*facteur_mm2_vers_m2/Stheo  # Conversion de la section mesurée mm²→m² pour calculer le facteur de remplissage (sans unité)
            self.Kf_spin.setValue(Kf)
        self.Kf_spin.blockSignals(False)

    def calcul_section(self, var):
        # CORRECTION #19 : idem calcul_kf — blocage temporaire au lieu d'une
        # déconnexion destructrice.
        self.section_spin.blockSignals(True)
        Di = self.Di_spin.value()
        De = self.De_spin.value()
        Hauteur = self.Hauteur_spin.value()
        if Di != 0 and De != 0 and Hauteur != 0:
            Stheo = Hauteur*facteur_mm_vers_m*((De*facteur_mm_vers_m)-(Di*facteur_mm_vers_m))/2  # Conversion des dimensions mm→m pour calculer la section théorique en m²
            Section = var*Stheo*facteur_m2_vers_mm2  # Conversion du résultat m²→mm² pour l'affichage dans l'interface
            self.section_spin.setValue(Section)
           
        self.section_spin.valueChanged.connect(self.calcul_kf)

    def recalcul_geometrie(self):
        """
        GUI-FIX : recalcule automatiquement Section (mm²) et lm (mm) dès que
        Di, De ou Hauteur changent dans l'interface.
        Appelée via valueChanged de Di_spin, De_spin, Hauteur_spin.
        FIX-SECTION : applique Kf (facteur de remplissage) à la section.
        """
        Di      = self.Di_spin.value()
        De      = self.De_spin.value()
        Hauteur = self.Hauteur_spin.value()
        Kf_val  = self.Kf_spin.value() if self.Kf_spin.value() > 0 else 1.0

        if Di > 0 and De > Di and Hauteur > 0:
            # Section effective du tore : S = Kf × (De - Di)/2 × Hauteur  [mm²]
            S_mm2 = Kf_val * (De - Di) / 2.0 * Hauteur  # mm × mm = mm²
            # Longueur de chemin magnétique moyen (formule logarithmique exacte)
            lm_mm = np.pi * (De - Di) / np.log(De / Di)

            # Bloquer les signaux pour éviter les boucles de rétroaction
            self.section_spin.blockSignals(True)
            self.lm_spin.blockSignals(True)
            self.section_spin.setValue(round(S_mm2, 4))
            self.lm_spin.setValue(round(lm_mm, 4))
            self.section_spin.blockSignals(False)
            self.lm_spin.blockSignals(False)

    def calcul_longueur(self, var=0):
        # Conservé pour compatibilité ascendante — délègue à recalcul_geometrie
        self.recalcul_geometrie()

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
        Rh = R_SHUNT_OHM        # constante unique (cf. en-tete du fichier)
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
        # GUI-FIX : calcul automatique de Section et lm si non renseignés
        # FIX-SECTION : multiplier par Kf pour obtenir la section effective
        if Section == 0 and Di > 0 and De > Di and Hauteur > 0:
            Kf_eff = Kf if Kf > 0 else 1.0
            Section = round(Kf_eff * (De - Di) / 2.0 * Hauteur, 4)  # mm²
        if lm == 0 and Di > 0 and De > Di:
            lm = round(np.pi * (De - Di) / np.log(De / Di), 4)  # mm
        Mode_asservissement=self.Asservissement_Combo.currentText()
        Sonde=self.Sonde_Combo.currentText()
        journal(f"[SONDE][accept] combo lu = {Sonde!r}")

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
   
    finished = pyqtSignal()
    temperature_lue = pyqtSignal(str)      # texte prêt à afficher

    def __init__(self, n, port):
        super().__init__()
        self.n = n              # QLabel cible (conservé pour compatibilité)
        self.port = port
        # Branchement du signal sur le label : la connexion est créée dans le
        # thread GUI, donc Qt effectue automatiquement le passage de thread.
        self.temperature_lue.connect(self.n.setText)

    def run(self):
        try:
            time.sleep(5)       # laisse le temps à l'ampli de se stabiliser
            with serial.Serial(self.port, baudrate=AMPLI_BAUDRATE,
                               timeout=AMPLI_TIMEOUT_S) as ser:
                ser.write(bytes.fromhex(TRAME_TEMPERATURE))
                reponse = ser.read()
                if reponse:
                    self.temperature_lue.emit(f"{reponse[-1]} °C")
                else:
                    journal("[TEMP] pas de reponse de l'amplificateur",
                            niveau=logging.WARNING)
        except (serial.SerialException, OSError) as err:
            # Une erreur de lecture ne doit pas tuer le thread silencieusement.
            journal(f"[TEMP] lecture impossible : {err}", niveau=logging.WARNING)
        finally:
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
        self.fenetre_defauts = Ampli_defaut_Window(self)
        self.fenetre_defauts.show()


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
            journal(f"{port.name} // {port.device} // D={port.description}")
            #if ser.read():
            if port.device[:-1]=="/dev/ttyUSB":
                ser = serial.Serial(port.device, baudrate=9600,timeout=1)
                ser.write(bytes.fromhex("0210"))
                
                read_bytes = ser.read().hex()
                try:
                    if len(read_bytes)==2:
                        self.port_connection=port.device
                        journal("Ampli connecté")
                        connect=1
                        self._connectAction()
                except:
                    pass
    
    
    def lecture(self):
        #global limite
        with serial.Serial(self.port_connection, baudrate=9600, timeout=1) as ser:


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
                journal('erreur')
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
            #journal("bit : ",read_bytes)
            if read_bytes[20:22]=="00":
                #mode limite control courant
                pass
            elif read_bytes[20:22]=="01":
                #mode limite control Tension
                #self.limite()
                self.Limite_Button.setText("Tension")

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
        journal("temperature fini")
        journal(Temperature_flag)
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
            journal('fin')


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
            journal(f"{port.name} // {port.device} // D={port.description}")
            #if ser.read():
            if port.device[:-1]=="/dev/ttyUSB":
                ser = serial.Serial(port.device, baudrate=9600,timeout=1)
                ser.write(bytes.fromhex("0210"))
                
                read_bytes = ser.read().hex()
                # try:

                if len(read_bytes)==2:
                    self.port_connection=port.device
                    journal("Ampli connecté")
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
        with serial.Serial(self.port_connection, baudrate=9600, timeout=1) as ser:

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
        # le nombre d'harmoniques du filtre du champ H etait fige
        # (n_harm=15) dans filtre_harmonique(). On l'expose maintenant ici,
        # reglable avant chaque mesure.
        self._ajouter_reglage_harmoniques_H()
        self._ajouter_cadre_debogage()

    def _ajouter_reglage_harmoniques_H(self):
       
        global nb_harmoniques_H

        self.cadre_harm_H = QtWidgets.QWidget(self)
        ligne_harm = QHBoxLayout(self.cadre_harm_H)
        ligne_harm.setContentsMargins(0, 0, 0, 0)

        self.Nbre_harm_H_spin = QtWidgets.QSpinBox()
        self.Nbre_harm_H_spin.setMinimum(1)
        self.Nbre_harm_H_spin.setMaximum(200)
        self.Nbre_harm_H_spin.setValue(int(nb_harmoniques_H))
        self.Nbre_harm_H_spin.setToolTip(
            "Nombre d'harmoniques (en plus du fondamental) conservees\n"
            "lors du filtrage FFT du champ H avant le trace du cycle B-H.\n"
            "Valeur precedente, fixe dans le code : 15.")

        ligne_harm.addWidget(QLabel("Harmoniques conservees (filtre H) :"))
        ligne_harm.addWidget(self.Nbre_harm_H_spin)

        try:
            disposition_fenetre = self.layout()
            if isinstance(disposition_fenetre, QtWidgets.QBoxLayout):
                index = disposition_fenetre.count()
                for i in range(disposition_fenetre.count()):
                    widget = disposition_fenetre.itemAt(i).widget()
                    if isinstance(widget, QDialogButtonBox):
                        index = i
                        break
                disposition_fenetre.insertWidget(index, self.cadre_harm_H)
            elif disposition_fenetre is not None:
                disposition_fenetre.addWidget(self.cadre_harm_H)
            else:
                # Cas reel de cette fenetre : pas de layout -> positionnement
                # manuel sous les widgets existants, puis agrandissement de
                # la fenetre (meme calcul que _ajouter_cadre_debogage).
                bas = max((w.geometry().bottom()
                           for w in self.findChildren(QtWidgets.QWidget)
                           if w.parent() is self), default=self.height())
                self.cadre_harm_H.setGeometry(10, bas + 10, self.width() - 20, 30)
                self.resize(self.width(), bas + 45)
                self.cadre_harm_H.show()
        except Exception as err:
            journal(f"[IHM] reglage harmoniques H non ajoute : {err}",
                    niveau=logging.WARNING)

    def _ajouter_cadre_debogage(self):
        """Ajoute en bas de la fenêtre un cadre regroupant les réglages de
        débogage : sonde voie D, traces disque, verbosité console.

        Ces widgets sont créés PAR CODE et non dans le fichier .ui, pour deux
        raisons : ils n'existent dans aucun .ui actuel, et le code doit rester
        fonctionnel si les .ui sont régénérés depuis Qt Designer.
        """
        self.boite_debug = QGroupBox("Débogage — sans effet sur le calcul des pertes")
        disposition = QVBoxLayout(self.boite_debug)

        # --- Sonde de courant ---
        self.check_sonde = QCheckBox("Sonde de courant sur voie D (4 voies)")
        self.check_sonde.setChecked(CONFIG_SONDE.active)
        self.check_sonde.setToolTip(
            "Décochée : acquisition sur 3 voies seulement.\n"
            "Le PicoScope autorise alors 15 ou 16 bits au lieu de 14,\n"
            "mais le contrôle croisé shunt / pince de courant est perdu.")
        disposition.addWidget(self.check_sonde)

        # --- Traces disque ---
        ligne_trace = QHBoxLayout()
        ligne_trace.addWidget(QLabel("Signaux enregistrés :"))
        self.combo_trace = QComboBox()
        self.combo_trace.addItems(list(NIVEAUX_TRACE))
        self.combo_trace.setCurrentText(NIVEAU_TRACE)
        self.combo_trace.setToolTip(
            "Complet  : un fichier de courbes par itération (~1,3 Mo chacun,\n"
            "           soit ~126 Mo pour 99 itérations).\n"
            "Standard : uniquement les courbes de l'itération finale.\n"
            "Minimal  : aucune courbe.\n\n"
            "metrics.csv, metadata.json et summary.json sont toujours écrits :\n"
            "ce sont les conditions de mesure, pas du débogage.")
        ligne_trace.addWidget(self.combo_trace)
        disposition.addLayout(ligne_trace)

        # --- Verbosité console ---
        ligne_verb = QHBoxLayout()
        ligne_verb.addWidget(QLabel("Messages console :"))
        self.combo_verbosite = QComboBox()
        self.combo_verbosite.addItems(list(NIVEAUX_VERBOSITE.keys()))
        self.combo_verbosite.setCurrentText(VERBOSITE_CONSOLE)
        self.combo_verbosite.setToolTip(
            "N'affecte QUE l'affichage console.\n"
            "Logs/session.log continue de tout recevoir.")
        ligne_verb.addWidget(self.combo_verbosite)
        disposition.addLayout(ligne_verb)

        # Insertion dans la disposition existante, avant les boutons OK/Cancel.
        # Écrit de façon défensive : si le .ui n'utilise pas de layout, on
        # positionne le cadre à la main plutôt que de tout casser.
        try:
            disposition_fenetre = self.layout()
            if disposition_fenetre is None:
                bas = max((w.geometry().bottom()
                           for w in self.findChildren(QtWidgets.QWidget)
                           if w.parent() is self), default=self.height())
                self.boite_debug.setParent(self)
                self.boite_debug.setGeometry(10, bas + 10, self.width() - 20, 120)
                self.resize(self.width(), bas + 145)
                self.boite_debug.show()
            elif isinstance(disposition_fenetre, QtWidgets.QBoxLayout):
                index = disposition_fenetre.count()
                for i in range(disposition_fenetre.count()):
                    widget = disposition_fenetre.itemAt(i).widget()
                    if isinstance(widget, QDialogButtonBox):
                        index = i
                        break
                disposition_fenetre.insertWidget(index, self.boite_debug)
            else:
                disposition_fenetre.addWidget(self.boite_debug)
        except Exception as err:
            # L'échec de l'ajout ne doit pas empêcher d'ouvrir la fenêtre :
            # les mêmes réglages restent accessibles par le menu Options.
            journal(f"[IHM] cadre de debogage non ajoute : {err}",
                    niveau=logging.WARNING)

    def accept(self):
        global mode_filtre,fenetre_filtre, iteration_max, num_samples, Resolution, Nbre_enregist, alpha, beta, rampe, gamma, nb_harmoniques_H
        iteration_max = self.Nbre_iter_spin.value()
        num_samples = self.Nbre_ech_spin.value()
        Resolution = int(self.Nbre_bits_combo.currentText())
        Nbre_enregist = self.Nbre_enreg_spin.value()
        alpha = self.coeff_alpha_spin.value()
        beta = self.coeff_beta_spin.value()
        rampe = self.coeff_rampe_spin.value()
        gamma= self.coeff_newton_spin.value()
        fenetre_filtre= self.Fenetre_Filtre_spinBox.value()
        mode_filtre = self.Filtre_comboBox.currentText()
        # youssef : recuperation du nombre d'harmoniques choisi pour le filtre du champ H
        nb_harmoniques_H = self.Nbre_harm_H_spin.value()

        # --- Réglages de débogage -----------------------------------------
        global NIVEAU_TRACE
        if hasattr(self, 'check_sonde'):
            CONFIG_SONDE.active = self.check_sonde.isChecked()
            NIVEAU_TRACE = self.combo_trace.currentText()
            regler_verbosite(self.combo_verbosite.currentText())
            journal(f"[REGLAGES] sonde D = {CONFIG_SONDE.active}, "
                    f"traces = {NIVEAU_TRACE}, console = {VERBOSITE_CONSOLE}")

        # Garde matérielle : 4 voies actives -> 14 bits maximum sur PS5000A.
        # On le signale AVANT la mesure plutôt que de lever une RuntimeError
        # une fois le dossier de session déjà créé.
        if CONFIG_SONDE.active and Resolution > RESOLUTION_MAX_4_VOIES:
            QMessageBox.warning(
                self, "Résolution incompatible",
                f"{Resolution} bits demandes avec la sonde de courant active.\n\n"
                f"Le PicoScope 5000a est limite a {RESOLUTION_MAX_4_VOIES} bits "
                f"des que 4 voies sont utilisees.\n\n"
                f"Decochez la sonde, ou choisissez {RESOLUTION_MAX_4_VOIES} bits.")

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
        journal(b)
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

        ampli_trouve = False
        for port in serial.tools.list_ports.comports():
            journal(f"{port.name} // {port.device} // D={port.description}",
                    niveau=logging.DEBUG)
            if port.device[:-1] != AMPLI_PREFIXE_PORT:
                continue
            try:
                with serial.Serial(port.device, baudrate=AMPLI_BAUDRATE,
                                   timeout=AMPLI_TIMEOUT_S) as ser:
                    ser.write(bytes.fromhex(TRAME_ETAT))
                    if len(ser.read().hex()) == 2:
                        port_connection = port.device
                        ampli_trouve = True
                        journal(f"Ampli connecte sur {port.device}")
                        break
            except (serial.SerialException, OSError) as err:
                journal(f"Port {port.device} inaccessible : {err}",
                        niveau=logging.WARNING)

        if ampli_trouve:
            self.Output_button.clicked.connect(self.Output)
        else:
            journal("Aucun amplificateur detecte : le bouton Output est "
                    "desactive et les defauts ne seront pas surveilles.",
                    niveau=logging.WARNING)
            self.Output_button.setEnabled(False)
        # self.Output_button.clicked.connect(self.Output(port_connection))
        if Mode_Auto=="Simple":
            journal("mode Simple")
            if self.thread is None or not self.thread.isRunning():
                # CONFIG SONDE : injectée dans le worker (elle n'est plus une
                # constante figée dans le source).
                self.thread = Worker(self, config_sonde=CONFIG_SONDE)
                self.thread.finished.connect(self.on_long_task_finished)
                self._brancher_signaux_worker()
                self.thread.start()
                self.show()

        elif Mode_Auto=="Auto":
            journal("mode Auto")
            # Freq_tab=[10,100]
            Freq=Freq_tab[0]
            Ampli=Ampli_tab[0]
            journal("Frequence actuelle : ",Freq)
            journal("amplitude actuelle : ",Ampli)
            if self.thread is None or not self.thread.isRunning():
                self.thread = Worker(self, config_sonde=CONFIG_SONDE)
                self.thread.finished.connect(self.on_long_task_finished_Auto)
                self._brancher_signaux_worker()
                self.thread.start()
                self.show()
        else:
            self.main_window.Button_start.setEnabled(True)
            self.thread = None
            self.main_window.plot_data(self.ChampH, self.ChampB)
            self.close()
                
        
    def Output(self):
        global port_connection
        # VÉRIF3 : utilisation de 'with' pour garantir la fermeture du port série
        if self.Output_button.text()=="OFF":
            with serial.Serial(port_connection, baudrate=9600) as ser:
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
            with serial.Serial(port_connection, baudrate=9600) as ser:
                ser.write(bytes.fromhex("033500"))
                ser.write(bytes.fromhex("0210"))
                ready=ser.read().hex()
                ready=list("{0:08b}".format(int(ready, 16)))
                if ready[0]=='0':
                    self.Output_button.setStyleSheet("background-color : red")
                    self.Output_button.setText("OFF")

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
        journal("freq tab : ",Freq_tab_tempo)
        journal("amplitude tab : ",Ampli_tab)

        tm.sleep(1)
        if len(Ampli_tab)!=1:
            
            if len(Freq_tab)!=1:
                journal("fréquence suivante")
                Freq_tab.pop(0)
                Freq=Freq_tab[0]
                # self.w = SupervisionWindow(self)
                # self.w.show()
                self.main_window.start()
            else:
                
                journal("amplitude suivante")
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
                journal("fréquence suivante fin")
                journal(Freq_tab)
                Freq=Freq_tab[0]
                # self.w = SupervisionWindow(self)
                # self.w.show()
                self.main_window.start()
            else :
                journal("Fin de séquence")
                self.main_window.Button_start.setEnabled(True)
                self.thread = None
                self.main_window.plot_data(self.ChampH, self.ChampB)
                self.close()

    @pyqtSlot(dict)
    def on_update_plot(self, data):
        """
        Slot exécuté dans le thread principal (UI-safe) pour rafraîchir les courbes
        et les labels de supervision. Reçoit un dict émis par Worker.update_plot.
        BUG2 : remplace les appels directs aux widgets depuis le thread Worker.
        """
        import numpy as np
        tc   = np.array(data['timeC'])
        N2      = data['N2']
        Section = data['Section']

        # --- Courbes matplotlib ---
        self.widget_1.canvas.ax.cla()
        self.widget_2.canvas.ax.cla()
        self.widget_3.canvas.ax.cla()
        self.widget_4.canvas.ax.cla()

        unite_T = data['unite_T']
        ChampBdes      = np.array(data['ChampBdes'])
        derivChampBdes = np.array(data['derivChampBdes'])
        ChampB         = np.array(data['ChampB'])
        derivChampB    = np.array(data['derivChampB'])
        ChampH         = np.array(data['ChampH'])
        entree         = np.array(data['entree'])

        self.widget_2.canvas.ax.plot(tc, ChampBdes,  label="B desiré", color='r', linestyle='--')
        self.widget_3.canvas.ax.plot(tc, derivChampBdes*(-N2*Section*1e-6), label="V2 desiré", color='r', linestyle='--')
        self.widget_1.canvas.ax.plot(tc, entree,     label="eₖ")
        self.widget_2.canvas.ax.plot(tc, ChampB,     label="Bₖ")
        self.widget_3.canvas.ax.plot(tc, derivChampB*(-N2*Section*1e-6), label="V2")
        self.widget_4.canvas.ax.plot(tc, ChampH,     label="Hₖ")

        for w, ylabel in [(self.widget_1, "Volts"), (self.widget_2, "T"),
                          (self.widget_3, "V"),     (self.widget_4, "A/m")]:
            w.canvas.ax.set_ylabel(ylabel, rotation=0)
            w.canvas.ax.yaxis.set_label_coords(0, 1)
            w.canvas.ax.set_xlabel(unite_T)
            w.canvas.ax.xaxis.set_label_coords(1.05, -0.025)
            w.canvas.ax.legend()
            w.canvas.draw()

        # --- Labels textuels ---
        self.iteration_label.setText("Itération n⁰" + str(data['iteration']))
        self.Courant_label.setText("Imax: " + str(data['imax_mA']) + " mA")
        self.Brefmax_value.setText(str(data['bmax_des']))
        self.Bkmax_value.setText(str(data['bmax']))
        self.FF_value.setText(str(data['ff']))
        self.THD_value.setText(str(data['thd']) + " %")
        self.RMSE_value.setText(str(data['rmse']) + " %")
        self.Hmax_value.setText(str(data['hmax']))
        self.Imax_value.setText(str(data['imax']))

        # --- Couleurs de convergence ---
        self.Bkmax_value.setStyleSheet("color: " + data['bkmax_color'] + ";")
        self.THD_value.setStyleSheet("color: "   + data['thd_color']   + ";")
        self.FF_value.setStyleSheet("color: "    + data['ff_color']    + ";")
        self.iteration_label.setStyleSheet("color: black;")

    def _brancher_signaux_worker(self):
        """Connecte tous les signaux du Worker aux slots de l'IHM."""
        self.thread.update_plot.connect(self.on_update_plot)
        self.thread.update_ampli.connect(self.on_update_ampli)
        self.thread.update_output.connect(self.on_update_output)
        self.thread.mesure_terminee.connect(self.on_mesure_terminee)
        self.thread.update_resultats.connect(
            self.main_window.on_update_resultats)

    @pyqtSlot(str, str)
    def on_update_ampli(self, texte, couleur):
        """Affiche l'état de l'amplificateur (Ready / Overload / ...)."""
        self.ready_Button.setText(texte)
        self.ready_Button.setStyleSheet(f"background-color : {couleur}")

    @pyqtSlot(str, str)
    def on_update_output(self, texte, couleur):
        """Affiche l'état de la sortie de puissance (ON / OFF)."""
        self.Output_button.setText(texte)
        self.Output_button.setStyleSheet(f"background-color : {couleur}")

    @pyqtSlot()
    def on_mesure_terminee(self):
        """Fin de la boucle d'asservissement : réactive les widgets."""
        self.stop_button.setEnabled(True)
        self.iteration_label.setStyleSheet("color: red;")

    def action_stop(self):
        self.stop = True
        self.stop_button.setEnabled(False)

    def closeEvent(self, event):
        """Fermeture propre : stop coopératif, puis coupure d'urgence si nécessaire."""
        self.stop = True
        if self.thread is not None and self.thread.isRunning():
            journal("⏳ Attente fin du thread Worker...")
            if not self.thread.wait(15000):     # laisse finir l'itération en cours
                journal("⚠️ Worker bloqué — coupure d'urgence de l'excitation.")
                try:                            # filet : couper la sortie AVANT de tuer
                    import usbtmc
                    g = usbtmc.Instrument(2391, 9991); g.timeout = 2000
                    g.write("OUTP OFF"); g.close()
                except Exception as e:
                    journal(f"[SECURITE] coupure d'urgence echouee: {e} — couper l'ampli a la main")
                self.thread.terminate()
                self.thread.wait()
        event.accept()

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
        # journal(message)
        for i in range(len(Erreur)):
            Erreur[i]=str(i)+" - "+Erreur[i]
        self.error_label.setText(str("\n".join(Erreur)))
        #self.error_label.setText(str(Erreur))

        Erreur.clear()

class DemagWorker(QThread):
    """
    DEMAG-FIX : thread de démagnetisation séparé.
    Emet 'status' (str) pour mettre à jour la barre de statut sans bloquer l'UI.
    Emet 'finished' à la fin (succès ou erreur).
    """
    status   = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def run(self):
        from scipy.interpolate import interp1d
        import usbtmc
        import time as tm

        try:
            self.status.emit("⏳ Démagnetisation : génération du signal…")

            a, b = 0, 5
            t = np.linspace(a, b, num=5000)
            entree = np.exp(-1.5 * t) * np.cos(2 * np.pi * t * 50)
            dt = t[1] - t[0]
            t_extra = t[-1] + dt * np.arange(1, 101)
            t = np.concatenate([t, t_extra])   # 5000 + 100 = 5100 points
            entree = np.concatenate([entree, np.zeros(100)])  # 5100 points

            # Réduction du nombre de points pour respecter la limite d'échantillonnage (160 MHz)
            interpolation_entree = interp1d(t, entree)
            i = len(entree)
            while len(t) * 50 > 159_000_000:
                i -= 1
                t = np.linspace(0, 1 / 50, i)
            entree = interpolation_entree(t)

            self.status.emit("⏳ Démagnetisation : envoi vers le GBF…")

            instr = usbtmc.Instrument(2391, 9991)
            try:
                instr.write("DATA:VOL:CLE")
                pk = np.max(np.abs(entree))
                message2 = 'DATA:ARB myArb'
                for nbre in entree:
                    message2 += ', ' + str("%.3f" % round(nbre / pk, 3))

                instr.timeout = 5000
                instr.write(message2)
                instr.write('FUNCtion:ARB "myArb"')
                instr.write(f'APPLy:ARB {len(entree) * 50},{pk},{0}')
                instr.write("OUTP ON")

                # Vérification des erreurs GBF
                errorCode = -1
                while errorCode != 0:
                    instr.write('SYST:ERR?')
                    rawError = instr.read()
                    parts = rawError.split(',')
                    errorCode = int(parts[0])
                    if errorCode != 0:
                        msg = parts[1].rstrip('\n')
                        self.status.emit(f"❌ Erreur GBF {errorCode} : {msg}")
                        instr.write('*CLS')
                        return   # finally fermera instr

                self.status.emit("⏳ Démagnetisation : signal en cours (~5 s)…")
                tm.sleep(5)      # durée du signal de démagnetisation

            finally:
                instr.write('DISP OFF')
                instr.write("OUTP OFF")
                instr.write('DISP:TEXT:CLE')
                instr.write('DISP ON')
                instr.close()

        except Exception as e:
            self.status.emit(f"❌ Erreur démagnetisation : {e}")
            journal(f"Erreur demag : {e}")
        finally:
            self.finished.emit()


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
        #self.toolButton_Reset_Pico.setIcon(QIcon('reset.jpeg'))
        self.toolButton_Reset_Pico.setIconSize(QSize(24, 24))
        self.Button_start.clicked.connect(self.start)
        x = range(0, 10)
        y = range(0, 20, 2)
        self.Notes = ""
        self.plot_data(x, y)
        self._connectActions()
        self._creer_menu_options()   # menus ajoutés par code (voir ci-dessous)

    def _creer_menu_options(self):
        """Ajoute un menu « Options » construit par code.

        Ces entrées sont créées ici plutôt que dans les fichiers .ui pour deux
        raisons : elles n'existent dans aucun .ui actuel, et elles pilotent des
        réglages GLOBAUX (journalisation, sonde) qui n'ont pas de raison d'être
        dispersés dans les fenêtres de configuration.
        """
        menu = self.menuBar().addMenu("Options")

        # --- Niveau de journalisation ------------------------------------
        # Remplace l'idée d'un simple bouton « logs ON/OFF » : couper purement
        # et simplement la journalisation ferait perdre la traçabilité des
        # mesures, alors que le gain de temps est négligeable devant le coût du
        # recalibrage des voies. On règle donc la VERBOSITÉ CONSOLE, tandis que
        # le fichier Logs/session.log continue de tout recevoir.
        sous_menu = menu.addMenu("Journalisation (console)")
        groupe = QActionGroup(self)
        groupe.setExclusive(True)
        for nom in ("Silencieux", "Normal", "Debug"):
            action = QAction(nom, self, checkable=True)
            action.setChecked(nom == "Normal")
            action.triggered.connect(
                lambda _coche, n=nom: (regler_verbosite(n),
                                       self._maj_indicateur_options()))
            groupe.addAction(action)
            sous_menu.addAction(action)

        # --- Traces enregistrées sur disque --------------------------------
        sous_menu_trace = menu.addMenu("Debugging")
        self.groupe_trace = QActionGroup(self)
        self.groupe_trace.setExclusive(True)
        self.actions_trace = {}
        for nom in NIVEAUX_TRACE:
            action = QAction(nom, self, checkable=True)
            action.setChecked(nom == NIVEAU_TRACE)
            action.triggered.connect(lambda _c, n=nom: self._regler_trace(n))
            self.groupe_trace.addAction(action)
            sous_menu_trace.addAction(action)
            self.actions_trace[nom] = action

        menu.addSeparator()

        # --- Sonde de courant (voie D) ------------------------------------
        self.action_sonde = QAction(
            "Sonde de courant sur voie D", self, checkable=True)
        self.action_sonde.setChecked(CONFIG_SONDE.active)
        self.action_sonde.setToolTip(
            "Désactiver la sonde libère la voie D : le PicoScope autorise alors "
            "une résolution supérieure à 14 bits, au prix de la perte du "
            "contrôle croisé shunt/sonde.")
        self.action_sonde.triggered.connect(self._basculer_sonde)
        menu.addAction(self.action_sonde)

        # Le menu peut être modifié depuis la fenêtre « Paramètres
        # d'acquisition » : on resynchronise les coches à chaque ouverture.
        menu.aboutToShow.connect(self._synchroniser_menu_options)

        # Indicateur permanent en barre d'état : l'état de ces réglages doit
        # être VISIBLE sans avoir à ouvrir un menu, sinon on finit par mesurer
        # pendant des semaines avec la sonde désactivée sans s'en apercevoir.
        self.label_options = QLabel()
        self.statusBar().addPermanentWidget(self.label_options)
        self._maj_indicateur_options()

    def _synchroniser_menu_options(self):
        """Aligne les coches du menu sur l'état réel des réglages."""
        self.action_sonde.setChecked(CONFIG_SONDE.active)
        for nom, action in self.actions_trace.items():
            action.setChecked(nom == NIVEAU_TRACE)

    def _maj_indicateur_options(self):
        """Rafraîchit l'indicateur permanent de la barre d'état."""
        court = {NIVEAU_TRACE_COMPLET: "Complet",
                 NIVEAU_TRACE_STANDARD: "Standard",
                 NIVEAU_TRACE_MINIMAL: "Minimal"}.get(NIVEAU_TRACE, NIVEAU_TRACE)
        etat_sonde = "ON" if CONFIG_SONDE.active else "OFF"
        self.label_options.setText(
            f"  Sonde D : {etat_sonde}   |   Traces : {court}   |   "
            f"Console : {VERBOSITE_CONSOLE}  ")
        # Mise en évidence quand on n'est PAS dans la configuration nominale.
        nominal = (CONFIG_SONDE.active and NIVEAU_TRACE != NIVEAU_TRACE_MINIMAL)
        self.label_options.setStyleSheet(
            "" if nominal else "color: #b35c00; font-weight: bold;")

    def _regler_trace(self, nom_niveau):
        """Change le niveau d'enregistrement des signaux sur disque."""
        global NIVEAU_TRACE
        NIVEAU_TRACE = nom_niveau
        journal(f"[TRACE] niveau = {nom_niveau}")
        self._maj_indicateur_options()
        if nom_niveau == NIVEAU_TRACE_MINIMAL:
            QMessageBox.information(
                self, "Traces disque",
                "Aucun signal ne sera enregistre.\n\n"
                "metadata.json, metrics.csv et summary.json continuent d'etre "
                "ecrits : ce sont les conditions experimentales et l'historique "
                "de convergence, pas du debogage. Ils pesent quelques dizaines "
                "de ko et sans eux une mesure n'est plus rattachable a rien.\n\n"
                "En revanche vous ne pourrez plus retracer le cycle B(H) a "
                "partir des fichiers : seules les valeurs finales resteront.")

    def _basculer_sonde(self, actif):
        """Active/désactive la voie D et prévient l'utilisateur des effets."""
        CONFIG_SONDE.active = bool(actif)
        if actif:
            message = ("Sonde de courant ACTIVE (4 voies).\n\n"
                       "Le PicoScope 5000a limite alors la resolution a "
                       f"{RESOLUTION_MAX_4_VOIES} bits.\n"
                       "Le controle croise shunt/sonde est disponible.")
        else:
            message = ("Sonde de courant DESACTIVEE (3 voies).\n\n"
                       "Resolution jusqu'a 16 bits possible.\n"
                       "ATTENTION : les colonnes Idc_probe, ratio_Iprobe_Ishunt "
                       "et H_max_probe seront vides (NaN) dans les fichiers de "
                       "resultats, et le controle croise du courant primaire "
                       "n'est plus assure.")
        journal(f"[SONDE] active = {CONFIG_SONDE.active}")
        self._maj_indicateur_options()
        QMessageBox.information(self, "Sonde de courant", message)

    def plot_data(self, x, y):
        if x is None or y is None:
            journal("[plot_data] x ou y est None — rien à tracer (mesure interrompue ?)")
            return
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
        self.actiondemag.triggered.connect(self.demag)
        self.actionManuel_d_Utilisation.triggered.connect(self.manuel)
        self.actionerror.triggered.connect(self.Error)
        self.actionPertesvsFreq.triggered.connect(self.PertesVsFreq)
        self.actionAmpli.triggered.connect(self.Ampli)
    
    def Ampli(self):
     
        self.fenetre_ampli = AmpliWindow(self)
        self.fenetre_ampli.show()
        
    def PertesVsFreq(self):
        self.fenetre_pertes = PertesVsFreqWindow(self)
        self.fenetre_pertes.show()

    def Error(self):
        self.fenetre_erreur = ErrorWindow(self)
        self.fenetre_erreur.show()

    def manuel(self):
        self.fenetre_aide = HelpWindow(self)
        self.fenetre_aide.show()

    def demag(self):
        """
        Lance la démagnetisation dans un thread séparé pour ne pas bloquer l'UI.
        DEMAG-FIX : l'ancienne implémentation bloquait tout le thread principal (~5 s),
        sans aucun feedback. Maintenant : statusBar + thread dédié.
        """
        self.actiondemag.setEnabled(False)
        self.statusBar().showMessage("⏳ Démagnetisation en cours…")
        self._demag_thread = DemagWorker(self)
        self._demag_thread.status.connect(self.statusBar().showMessage)
        self._demag_thread.finished.connect(self._on_demag_finished)
        self._demag_thread.start()

    @pyqtSlot()
    def _on_demag_finished(self):
        self.actiondemag.setEnabled(True)
        self.statusBar().showMessage("✔ Démagnetisation terminée", 5000)



    def set_config(self):
        self.fenetre_config = ConfigWindow(self)
        self.fenetre_config.show()

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

    @pyqtSlot(dict)
    def on_update_resultats(self, data):
        
        if data.get('echec'):
            # La mesure a échoué : on neutralise l'affichage plutôt que
            # d'afficher les valeurs de l'essai précédent, qui seraient prises
            # pour des résultats valides.
            self.update_mesures(0, 1, 0, 0, 0, 0, 0)
            self.statusBar().showMessage(
                "⚠ Mesure interrompue — voir le journal (Logs/session.log)", 10000)
            return
        self.update_mesures(data['bmax'], data['freq'], data['hc'], data['br'],
                            data['hmax'], data['mu_r'], data['pv'],
                            data.get('pv_probe'))

    def update_mesures(self, bmax, Freq, hc, br, hmax, Mu_r, Pv, Pv_probe=None):
        self.Pv_probe = Pv_probe
        self.Bmax = bmax
        self.Frequence = Freq
        self.Hc = hc
        self.Br = br
        self.Hmax = hmax
        self.Mu = Mu_r
        self.Pv = Pv
        # GARDE : Freq peut valoir 0 sur un échec de mesure -> ZeroDivisionError
        # en plein rafraîchissement de l'IHM.
        self.W = (Pv / Freq) if Freq else 0.0
        self.Bmax_value.setText(str(round(self.Bmax, 3)))
        self.Freq_value.setText(str(round(self.Frequence, 2)))
        self.Hc_value.setText(str(round(self.Hc, 3)))
        self.Br_value.setText(str(round(self.Br, 3)))
        self.Hmax_value.setText(str(round(self.Hmax, 3)))
        self.Mu_value.setText(str(round(self.Mu, 0)))
        self.W_value.setText(str(round(self.W, 3)))
        self.Pv_value.setText(str(round(self.Pv, 3)))

    def acquisition(self):
        self.fenetre_acquisition = AcquisWindow()
        self.fenetre_acquisition.show()

    def reset_pico(self):
        
        import subprocess

        script = os.environ.get(
            "BANC_RESET_PICO",
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "Reset_Pico.sh"))

        if not os.path.isfile(script):
            QMessageBox.warning(
                self, "Reset PicoScope",
                f"Script introuvable :\n{script}\n\n"
                "Definir la variable d'environnement BANC_RESET_PICO, ou "
                "placer Reset_Pico.sh a cote du programme.")
            return

        journal(f"[PICO] execution de {script}")
        try:
            resultat = subprocess.run([script], capture_output=True, text=True,
                                      timeout=30)
            if resultat.returncode != 0:
                journal(f"[PICO] echec (code {resultat.returncode}) : "
                        f"{resultat.stderr.strip()}", niveau=logging.WARNING)
                QMessageBox.warning(
                    self, "Reset PicoScope",
                    "Le script a echoue.\n\n"
                    f"{resultat.stderr.strip()}\n\n"
                    "Si l'erreur porte sur les droits d'acces, mettre en place "
                    "la regle udev decrite dans le code (methode recommandee).")
            else:
                self.statusBar().showMessage("✔ PicoScope reinitialise", 5000)
        except (OSError, subprocess.SubprocessError) as err:
            journal(f"[PICO] erreur : {err}", niveau=logging.WARNING)
            QMessageBox.warning(self, "Reset PicoScope", str(err))


    def comparaison(self):
        self.fenetre_comparaison = ComparWindow()
        self.fenetre_comparaison.show()

    def notes(self):
        self.win = NotesWindow(self)
        self.win.show()

    def opens_config(self):
        """Recharge une configuration depuis un fichier .cfg."""
        global Materiaux, Hauteur, Di, De, Section, Outils, Ns1, Ns2, Rs, Rh
        global Type, Forme, Freq, Ampli, Gain, Nbre_periode, Nbre_enregist
        global Nm_ref, mu_r, Kf, lm, Sonde
        global num_samples, Resolution, iteration_max, mode_filtre, fenetre_filtre
        global Mode_asservissement, alpha, beta, gamma, rampe
        global nb_harmoniques_H  # youssef

        config_path = demander_fichier_ouverture(
            self, "Charger une configuration", "config")
        if not config_path:
            return

        settings = QSettings(config_path, QSettings.IniFormat)

        # Contrôle de plausibilité : un fichier .cfg quelconque (ou corrompu)
        # produisait auparavant un chargement silencieux de zéros partout.
        if settings.status() != QSettings.NoError or not settings.contains("Nom_ref"):
            QMessageBox.warning(
                self, "Fichier non reconnu",
                f"{os.path.basename(config_path)} ne semble pas etre une "
                "configuration de ce banc.\n\n"
                "Aucun parametre n'a ete modifie.")
            journal(f"[CONFIG] fichier rejete : {config_path}",
                    niveau=logging.WARNING)
            return

        version = _lire_entier(settings, "version", 1)
        manquantes = []

        # --- Échantillon et géométrie ---
        Nm_ref    = _lire_texte(settings, "Nom_ref", "Nom_Ref", manquantes)
        Materiaux = _lire_texte(settings, "Materiaux_value", "Fer pur", manquantes)
        Outils    = _lire_texte(settings, "Outils_value", "Cadre Epstein", manquantes)
        Hauteur   = _lire_reel(settings, "Hauteur_value", 0.0, manquantes)
        Di        = _lire_reel(settings, "Di_value", 0.0, manquantes)
        De        = _lire_reel(settings, "De_value", 0.0, manquantes)
        Section   = _lire_reel(settings, "Section_value", 0.0, manquantes)
        lm        = _lire_reel(settings, "lm_value", 0.0, manquantes)
        # Kf et mu_r sont des RÉELS (0,95 et 5000,0) : les lire avec int()
        # levait un ValueError et faisait echouer tout le chargement.
        Kf        = _lire_reel(settings, "Kf_value", 1.0, manquantes)
        mu_r      = _lire_reel(settings, "Mu_value", 2000.0, manquantes)
        Ns1       = _lire_entier(settings, "Ns1_value", 0, manquantes)
        Ns2       = _lire_entier(settings, "Ns2_value", 0, manquantes)
        Rs        = _lire_reel(settings, "Rs_value", 0.0, manquantes)
        Sonde     = _lire_texte(settings, "Sonde_value", str(Sonde))

        # Le shunt reste la constante d'étalonnage du banc : on ne le relit pas.
        Rh = R_SHUNT_OHM

        # --- Excitation ---
        Type   = _lire_texte(settings, "Type_value", "Cycle d'hystérèsis", manquantes)
        Forme  = _lire_texte(settings, "Forme_value", "Sinusoïdale B", manquantes)
        Freq   = _lire_reel(settings, "Freq_value", 0.0, manquantes)
        Ampli  = _lire_reel(settings, "Ampli_value", 0.0, manquantes)
        Gain   = _lire_entier(settings, "Gain_value", 0, manquantes)
        Nbre_periode = max(NBRE_PERIODE_MIN,
                           _lire_entier(settings, "Nbre_periode_value",
                                        NBRE_PERIODE_MIN, manquantes))
        Nbre_enregist = _lire_entier(settings, "Nbre_enregist_value", 0, manquantes)

        # --- Acquisition et asservissement ---
        # Compatibilité ascendante : les fichiers de version 1 ne contiennent
        # pas ces clés. On conserve alors le comportement historique — gains
        # forcés à 0,5 / 0,5 / 10 — plutôt que d'inventer des valeurs, mais on
        # le SIGNALE, au lieu de le faire en silence comme auparavant.
        if version >= 2:
            num_samples    = _lire_entier(settings, "num_samples_value", num_samples)
            Resolution     = _lire_entier(settings, "Resolution_value", Resolution)
            iteration_max  = _lire_entier(settings, "iteration_max_value", iteration_max)
            mode_filtre    = _lire_texte(settings, "mode_filtre_value", mode_filtre)
            fenetre_filtre = _lire_entier(settings, "fenetre_filtre_value", fenetre_filtre)
            # youssef : nombre d'harmoniques du filtre H, absent des configs
            # sauvegardees avant ce changement -> on garde la valeur courante.
            nb_harmoniques_H = _lire_entier(settings, "nb_harmoniques_H_value",
                                             nb_harmoniques_H)
            Mode_asservissement = _lire_texte(settings, "Mode_asservissement_value",
                                              Mode_asservissement)
            alpha = _lire_reel(settings, "alpha_value", alpha)
            beta  = _lire_reel(settings, "beta_value", beta)
            gamma = _lire_reel(settings, "gamma_value", gamma)
            rampe = _lire_entier(settings, "rampe_value", rampe)
        else:
            alpha, beta, gamma = 0.5, 0.5, 10
            journal("[CONFIG] fichier au format v1 : les parametres "
                    "d'acquisition et d'asservissement n'y figurent pas. "
                    "alpha=0.5, beta=0.5, gamma=10 appliques (comportement "
                    "historique). Reenregistrez la configuration pour les "
                    "conserver a l'avenir.", niveau=logging.WARNING)

        if manquantes:
            journal(f"[CONFIG] cles absentes du fichier, valeurs par defaut "
                    f"utilisees : {manquantes}", niveau=logging.WARNING)

        self.update_data(Outils, Materiaux, Di, De, Hauteur, Section, lm, Kf)

        journal(f"[CONFIG] chargee (format v{version}) : {config_path}")
        resume = (f"{Nm_ref} — {Materiaux}, {Outils}\n"
                  f"f = {Freq} kHz, B = {Ampli} T, {Mode_asservissement}\n"
                  f"alpha = {alpha}, beta = {beta}")
        if version < 2:
            resume += ("\n\nFichier ancien format : les parametres "
                       "d'acquisition n'ont pas ete restaures.")
        QMessageBox.information(self, "Configuration chargée", resume)

    def saves_config(self):
        """Enregistre la configuration complète dans un fichier .cfg.

        CORRECTION #Config-4 : la version d'origine n'enregistrait QUE la
        géométrie de l'échantillon et l'excitation. Les paramètres
        d'acquisition (nombre d'échantillons, résolution, nombre d'itérations,
        filtre) et surtout les GAINS DE L'ASSERVISSEMENT alpha, beta, gamma et
        rampe n'étaient pas sauvegardés. Un réglage de PI patiemment ajusté
        était donc perdu dès la fermeture du programme, et le rechargement de
        la configuration le remplaçait en silence par 0,5 / 0,5 / 10.
        """
        date_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        nom_propose = f"{_nom_fichier_sur(Nm_ref)}_{date_time}.cfg"

        config_path = demander_fichier_sauvegarde(
            self, "Enregistrer la configuration", nom_propose, "config")
        if not config_path:
            return

        settings = QSettings(config_path, QSettings.IniFormat)
        
        settings.clear()

        settings.setValue("version", CONFIG_VERSION)
        settings.setValue("date_enregistrement", date_time)

        # --- Échantillon et géométrie ---
        settings.setValue("Nom_ref", Nm_ref)
        settings.setValue("Materiaux_value", Materiaux)
        settings.setValue("Outils_value", Outils)
        settings.setValue("Hauteur_value", Hauteur)
        settings.setValue("Di_value", Di)
        settings.setValue("De_value", De)
        settings.setValue("Section_value", Section)
        settings.setValue("lm_value", lm)
        settings.setValue("Kf_value", Kf)
        settings.setValue("Mu_value", mu_r)
        settings.setValue("Ns1_value", Ns1)
        settings.setValue("Ns2_value", Ns2)
        settings.setValue("Rs_value", Rs)
        settings.setValue("Sonde_value", Sonde)
        settings.setValue("Rh_value_information_seulement", R_SHUNT_OHM)

        # --- Excitation ---
        settings.setValue("Type_value", Type)
        settings.setValue("Forme_value", Forme)
        settings.setValue("Freq_value", Freq)
        settings.setValue("Ampli_value", Ampli)
        settings.setValue("Gain_value", Gain)
        settings.setValue("Nbre_periode_value", Nbre_periode)

        # --- Acquisition (AJOUTÉ) ---
        settings.setValue("num_samples_value", num_samples)
        settings.setValue("Resolution_value", Resolution)
        settings.setValue("iteration_max_value", iteration_max)
        settings.setValue("Nbre_enregist_value", Nbre_enregist)
        settings.setValue("mode_filtre_value", mode_filtre)
        settings.setValue("fenetre_filtre_value", fenetre_filtre)
        settings.setValue("nb_harmoniques_H_value", nb_harmoniques_H)  # youssef

        # --- Asservissement (AJOUTÉ — c'est le réglage le plus coûteux à refaire) ---
        settings.setValue("Mode_asservissement_value", Mode_asservissement)
        settings.setValue("alpha_value", alpha)
        settings.setValue("beta_value", beta)
        settings.setValue("gamma_value", gamma)
        settings.setValue("rampe_value", rampe)

        # --- Contexte de mesure (traçabilité) ---
        settings.setValue("sonde_courant_active", CONFIG_SONDE.active)
        settings.setValue("niveau_trace", NIVEAU_TRACE)

        # CORRECTION #Config-5 : QSettings n'écrit sur disque qu'à la
        # destruction de l'objet, et le code d'origine ne vérifiait jamais que
        # l'écriture avait abouti. Un dossier en lecture seule ou un disque
        # plein produisait donc une sauvegarde silencieusement perdue.
        settings.sync()
        if settings.status() != QSettings.NoError:
            journal(f"[CONFIG] echec d'ecriture : {config_path}",
                    niveau=logging.WARNING)
            QMessageBox.critical(
                self, "Enregistrement impossible",
                f"La configuration n'a PAS ete enregistree :\n{config_path}\n\n"
                "Verifiez les droits d'ecriture et l'espace disque disponible.")
            return

        journal(f"[CONFIG] enregistree : {config_path}")
        self.statusBar().showMessage(
            f"✔ Configuration enregistrée : {os.path.basename(config_path)}", 6000)

    def saves_project(self):
            variables = {
                "Bmax (T)": str(self.Bmax),
                "Freq(Hz)": str(self.Frequence),
                "Hc": str(self.Hc),
                "Br (T)": str(self.Br),
                "Hmax": str(self.Hmax),
                "µr": str(self.Mu),
                "W(J/m³)": str(self.W),
                "P(W/m³)": str(self.Pv),
                "P_sonde(W/m³)": str(getattr(self, 'Pv_probe', None)) if getattr(self, 'Pv_probe', None) is not None else "N/A"
            }

            arrays = {
                "temps (s)": self.timeC,
                "ChampH (A/m)": self.ChampH,
                "ChampB (T)": self.ChampB,
                "dB/dt (T/s)": self.derivChampB
            }
            
                    
            csv_file = Nm_ref + "_" + str(Materiaux) + "_" + str(Forme) + "_" + str(
                self.Frequence)+ " Hz" + "_" + str(round(self.Bmax, 3)) + " T" + ".csv"
            
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

    def saves_project_auto(self):
        global selected_dir
        
        if selected_dir:
            file_name = Nm_ref
            project_dir = os.path.join(selected_dir, file_name)
            if not os.path.exists(project_dir):
                os.makedirs(project_dir)

            variables = {
                "Bmax (T)": str(self.Bmax),
                "Freq(Hz)": str(self.Frequence),
                "Hc": str(self.Hc),
                "Br (T)": str(self.Br),
                "Hmax": str(self.Hmax),
                "µr": str(self.Mu),
                "W(J/m³)": str(self.W),
                "P(W/m³)": str(self.Pv),
                "P_sonde(W/m³)": str(getattr(self, 'Pv_probe', None)) if getattr(self, 'Pv_probe', None) is not None else "N/A"
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
        config_path = demander_fichier_sauvegarde(
            self, "Enregistrer la séquence", "sequence.cfg", "sequence")
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
        settings.sync()          # sans cela, l'ecriture n'est pas garantie
        if settings.status() != QSettings.NoError:
            QMessageBox.critical(
                self, "Enregistrement impossible",
                f"La sequence n'a PAS ete enregistree :\n{config_path}")
        else:
            journal(f"[SEQUENCE] enregistree : {config_path}")
        
    
        
    def Verification_Erreur(self):
        """
        Vérifier TOUS les paramètres et afficher les calculs intermédiaires.
        
        Affiche:
        - Chaque paramètre saisi et sa valeur
        - Les vérifications effectuées
        - Les formules de calcul et leurs résultats
        - Toutes les erreurs détectées
        """
        global Materiaux, Hauteur, Di, De, Section, Outils, Ns1, Ns2, Rs, Rh, Type, Forme, Freq, Ampli, Gain, Nbre_periode, Nbre_enregist, Nm_ref, mu_r, Kf, num_samples, alpha, beta, lm, gamma, Sonde
        
        # =========================================================================
        # ÉTAPE 1: AFFICHAGE DES PARAMÈTRES
        # =========================================================================
        journal("\n" + "="*80)
        journal("VERIFICATION PARAMÈTRES - Affichage des valeurs saisies")
        journal("="*80)
        
        # Tableau des paramètres avec leurs valeurs
        Param = [Hauteur, Di, De, Section, Ns1, Ns2, Rs, Rh, Freq, Ampli, Gain, Nbre_periode, Nbre_enregist, mu_r, Kf, num_samples, alpha, beta, lm, gamma]
        Param_str = ["Hauteur", "Di", "De", "Section", "Ns1", "Ns2", "Rs", "Rh", "Freq", "Ampli", "Gain", "Nbre_periode", "Nbre_enregist", "mu_r", "Kf", "num_samples", "alpha", "beta", "lm", "gamma"]
        Param_units = ["mm", "mm", "mm", "mm²", "", "", "Ω", "Ω", "Hz", "V", "", "", "", "", "", "", "", "", "mm", ""]
        
        journal("\n{:<20} {:<15} {:<10}".format("Paramètre", "Valeur", "Unité"))
        journal("-" * 45)
        for i in range(len(Param)):
            unit_str = Param_units[i] if Param_units[i] else "-"
            journal("{:<20} {:<15.6g} {:<10}".format(Param_str[i], Param[i], unit_str))
        
        # =========================================================================
        # ÉTAPE 2: VÉRIFICATION - PARAMÈTRES MANQUANTS
        # =========================================================================
        # `Erreur` était ici une variable LOCALE
        # (aucun `global Erreur` dans la liste de déclarations ci-dessus), alors
        # qu'une globale du même nom existe et est lue ailleurs. Tout ce qui
        # était ajouté à cette liste disparaissait donc au retour de la méthode.
        # Combiné au fait que start() ignorait la valeur de retour, cela rendait
        # la totalité de cette vérification de sécurité INOPÉRANTE : elle
        # affichait de belles croix rouges dans la console et lançait la mesure
        # quand même. On alimente désormais la globale ET on retourne la liste.
        global Erreur
        Erreur = []
        
        journal("\n" + "-"*80)
        journal("VÉRIFICATION 1: Paramètres manquants (= 0)")
        journal("-"*80)
        
        param_zero = []
        for i in range(len(Param)):
            if Param[i] == 0:
                Erreur.append(Param_str[i] + " non renseigné")
                param_zero.append(Param_str[i])
                journal(f"❌ {Param_str[i]} = 0 → ERREUR")
        
        if not param_zero:
            journal("✓ Tous les paramètres sont renseignés")
        
        # =========================================================================
        # ÉTAPE 3: VÉRIFICATION - COHÉRENCE GÉOMÉTRIQUE
        # =========================================================================
        journal("\n" + "-"*80)
        journal("VÉRIFICATION 2: Cohérence géométrique")
        journal("-"*80)
        journal(f"Di (diamètre intérieur) = {Di} mm")
        journal(f"De (diamètre extérieur) = {De} mm")
        
        if De < Di:
            Erreur.append("De < Di (géométrie impossible)")
            journal(f"❌ ERROR: De ({De}) < Di ({Di})")
            journal(f"   → Le diamètre extérieur doit être > diamètre intérieur !")
        else:
            diam_diff = De - Di
            journal(f"✓ De > Di (épaisseur tore = {diam_diff} mm)")
        
        # =========================================================================
        # ÉTAPE 4: CONVERSION SONDE
        # =========================================================================
        journal("\n" + "-"*80)
        journal("VÉRIFICATION 3: Conversion facteur Sonde")
        journal("-"*80)
        
        Sonde_original = Sonde
        # NE PAS écraser le global Sonde (label du combo) : on utilise un local.
        if Sonde == "1":
            sonde_val = 1.0
            journal(f"Sonde input: '{Sonde_original}' → gain = {sonde_val} (pas d'atténuation)")
        elif Sonde == "1/10":
            sonde_val = 10.0
            journal(f"Sonde input: '{Sonde_original}' → gain = {sonde_val} (1/10, ÷10 → ×10)")
        elif Sonde == "1/100":
            sonde_val = 100.0
            journal(f"Sonde input: '{Sonde_original}' → gain = {sonde_val} (1/100, ÷100 → ×100)")
        else:
            try:
                v = float(Sonde)
                sonde_val = (1.0 / v) if 0.0 < v < 1.0 else v
                journal(f"Sonde input: '{Sonde_original}' → gain = {sonde_val} (nombre)")
            except Exception:
                sonde_val = 1.0
                Erreur.append(f"Sonde invalide: '{Sonde_original}'")
                journal(f"❌ ERROR: Sonde '{Sonde_original}' non reconnue → gain = 1.0")
        
        # =========================================================================
        # ÉTAPE 5: CALCUL ET VÉRIFICATION DE LA TENSION DU SECONDAIRE
        # =========================================================================
        journal("\n" + "-"*80)
        journal("VÉRIFICATION 4: Limite de tension du secondaire V₂")
        journal("-"*80)
        
        # Constante de Faraday
        K_faraday = 4.44
        sqrt_2 = np.sqrt(2)
        
        # Conversion de la section de mm² en m²
        Section_m2 = Section * 1e-6

        Freq_Hz = Freq * facteur_kHz_vers_Hz
        V2 = K_faraday * Ns2 * Section_m2 * Ampli * Freq_Hz * sqrt_2 * sonde_val
        
        # Affichage de la formule et du calcul
        journal(f"\nFormule de Faraday:")
        journal(f"V₂ = K × Ns2 × S(m²) × Ampli × Freq × √2 × Sonde")
        journal(f"\nOù:")
        journal(f"  K (Faraday)     = {K_faraday}")
        journal(f"  Ns2 (spires)    = {Ns2}")
        journal(f"  Section (mm²)   = {Section}")
        journal(f"  Section (m²)    = {Section_m2:.10e}")
        journal(f"  Ampli (V)       = {Ampli}")
        journal(f"  Freq (saisie)   = {Freq} kHz")
        journal(f"  Freq (Hz)       = {Freq_Hz}")
        journal(f"  √2              = {sqrt_2:.6f}")
        journal(f"  Sonde (gain)    = {sonde_val}")
        
        journal(f"\nCalcul pas à pas:")
        journal(f"  V₂ = {K_faraday} × {Ns2} × {Section_m2:.10e} × {Ampli} × {Freq_Hz} × {sqrt_2:.6f} × {sonde_val}")
        
        # Vérification de la limite (constante nommée, cf. en-tête du fichier)
        V2_limit = V2_LIMITE_PICO_V
        journal(f"\nVérification:")
        journal(f"  V₂ calculé = {V2:.6f} V")
        journal(f"  V₂ limite  = {V2_limit} V (limite picoscope)")
        
        if V2 >= V2_limit:
            Erreur.append(f"Limite de tension atteinte (V₂ = {V2:.3f} V ≥ {V2_limit} V)")
            journal(f"❌ ERROR: V₂ = {V2:.3f} V >= {V2_limit} V")
            journal(f"   → Le picoscope ne peut pas mesurer plus de {V2_limit} V !")
            journal(f"   → Solutions:")
            journal(f"      • Réduire Ampli (actuellement {Ampli} V)")
            journal(f"      • Augmenter Sonde (actuellement {Sonde})")
            journal(f"      • Réduire Ns2 (actuellement {Ns2} spires)")
            journal(f"      • Réduire Freq (actuellement {Freq} Hz)")
            journal(f"      • Réduire Section (actuellement {Section} mm²)")
        else:
            margin = (1 - V2/V2_limit) * 100
            journal(f"✓ V₂ = {V2:.3f} V < {V2_limit} V")
            journal(f"   Marge de sécurité: {margin:.1f}%")

        # =====================================================================
        # ÉTAPE 6: COHÉRENCE RÉSOLUTION / NOMBRE DE VOIES
        # =====================================================================
        if CONFIG_SONDE.active and int(Resolution) > RESOLUTION_MAX_4_VOIES:
            Erreur.append(
                f"Resolution {Resolution} bits incompatible avec la sonde de "
                f"courant (4 voies -> {RESOLUTION_MAX_4_VOIES} bits max)")
            journal(f"❌ ERROR: {Resolution} bits demandes avec 4 voies actives")
            journal(f"   → Desactiver la sonde (menu Options) ou choisir "
                    f"{RESOLUTION_MAX_4_VOIES} bits")

        journal("\n" + "="*80)
        journal(f"BILAN : {len(Erreur)} erreur(s) detectee(s)")
        journal("="*80)

        # CORRECTION #4 : la liste est maintenant RETOURNÉE (elle ne l'était pas).
        return Erreur


    def start(self):
        """Lance une mesure, APRÈS validation des paramètres.

        CORRECTION #4 (CRITIQUE) : la version d'origine appelait
        Verification_Erreur() en ignorant purement et simplement son résultat,
        puis démarrait la mesure quoi qu'il arrive. Une géométrie impossible
        (De < Di), un paramètre à zéro ou un dépassement de la pleine échelle du
        PicoScope n'empêchaient donc pas le lancement : le banc excitait
        l'échantillon et produisait des résultats faux mais d'apparence normale.
        La vérification BLOQUE désormais le démarrage.
        """
        global Mode_Auto, selected_dir

        erreurs = self.Verification_Erreur()

        if erreurs:
            detail = "\n".join(f"  • {e}" for e in erreurs)
            reponse = QMessageBox.critical(
                self, "Parametres invalides",
                f"{len(erreurs)} probleme(s) detecte(s) :\n\n{detail}\n\n"
                "Lancer la mesure malgre tout ? Les resultats seront "
                "probablement FAUX, et l'echantillon ou l'instrumentation "
                "peuvent etre endommages.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No)                    # « Non » par défaut
            if reponse != QMessageBox.Yes:
                journal("[START] lancement annule par l'utilisateur "
                        "(parametres invalides)")
                return
            journal("[START] ATTENTION : lancement FORCE malgre "
                    f"{len(erreurs)} erreur(s) : {erreurs}",
                    niveau=logging.WARNING)

        if Mode_Auto=="Auto" and selected_dir=="":
            self.saves_sequence()
        self.Button_start.setEnabled(False)

        # CORRECTION #12 : attribut NOMMÉ (voir le commentaire sur self.w).
        self.fenetre_supervision = SupervisionWindow(self)
        self.fenetre_supervision.show()

    def closeEvent(self, event):
        """
        Fermeture propre : on demande aux threads de s'arrêter et on attend leur terminaison
        avant de fermer la QApplication.
        """
        supervision = getattr(self, 'fenetre_supervision', None)
        if supervision is not None:
            try:
                supervision.stop = True  # drapeau coopératif lu dans Worker.run()
                if getattr(supervision, 'thread', None) is not None:
                    if supervision.thread.isRunning():
                        journal("⏳ Arrêt du thread d'asservissement...")
                        if not supervision.thread.wait(5000):  # 5 s max
                            journal("⚠️ Asservissement non terminé, arrêt forcé.")
                            supervision.thread.terminate()
                            supervision.thread.wait()
            except Exception as e:
                journal(f"Erreur arrêt asservissement : {e}")
        
        # 2) Arrête le thread Temperature_Ampli si encore vivant
        if hasattr(self, 'thread') and self.thread is not None:
            try:
                if self.thread.isRunning():
                    journal("⏳ Arrêt du thread Temperature_Ampli...")
                    self.thread.quit()
                    if not self.thread.wait(3000):
                        self.thread.terminate()
                        self.thread.wait()
            except Exception as e:
                journal(f"Erreur arrêt Temperature : {e}")
        
        # 3) Arrête le DemagWorker s'il existe
        if hasattr(self, '_demag_thread') and self._demag_thread is not None:
            try:
                if self._demag_thread.isRunning():
                    journal("⏳ Arrêt du thread DemagWorker...")
                    self._demag_thread.quit()
                    if not self._demag_thread.wait(3000):
                        self._demag_thread.terminate()
                        self._demag_thread.wait()
            except Exception:
                pass
        
        # 4) Ferme toutes les fenêtres et l'application
        for w in QtWidgets.QApplication.topLevelWidgets():
            if w is not self:
                w.close()
        
        event.accept()
    # PAS de QApplication.quit() ici : la fermeture de la dernière fenêtre suffit


if __name__ == "__main__":
    # Récupère la QApplication existante (Spyder/IDE) ou en crée une nouvelle (terminal)
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    
    window = MainWindow()
    window.show()
    
    # Pas de sys.exit() pour rester compatible avec Spyder
    app.exec()
