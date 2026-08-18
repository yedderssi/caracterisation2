"""
Visualiseur interactif des sessions de mesure avec slider et boutons.


    
"""
import os
import json
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button

LOGS_DIR = "./Logs"   # ← modifie ici si tes logs sont ailleurs


def list_sessions():
    """Liste toutes les sessions disponibles, triées par date décroissante."""
    if not os.path.exists(LOGS_DIR):
        print(f"❌ Dossier {LOGS_DIR} introuvable.")
        sys.exit(1)

    sessions = sorted(
        [d for d in os.listdir(LOGS_DIR)
         if os.path.isdir(os.path.join(LOGS_DIR, d))],
        reverse=True
    )

    if not sessions:
        print(f"❌ Aucune session trouvée dans {LOGS_DIR}.")
        sys.exit(1)

    print("\n📂 Sessions disponibles :\n")
    for i, s in enumerate(sessions):
        summary_path = os.path.join(LOGS_DIR, s, 'summary.json')
        if os.path.exists(summary_path):
            with open(summary_path, 'r', encoding='utf-8') as f:
                summ = json.load(f)
            statut = f"[{summ.get('status', '?')}] {summ.get('n_iterations', '?')} itér."
        else:
            statut = "[en cours ou interrompu]"
        print(f"  [{i:2d}] {s}  {statut}")

    print()
    choix = input(f"Numéro de la session à ouvrir (0-{len(sessions)-1}) : ")
    return os.path.join(LOGS_DIR, sessions[int(choix)])


def load_session(session_dir):
    """Charge une session complète.

    Nouveau format : les courbes de chaque itération sont enregistrées dans
    waveforms_iter_XXX.csv (1 colonne = 1 signal). Les anciennes sessions au
    format .npz restent lisibles (repli automatique).
    """
    with open(os.path.join(session_dir, 'metadata.json'), 'r', encoding='utf-8') as f:
        meta = json.load(f)

    metrics = pd.read_csv(os.path.join(session_dir, 'metrics.csv'))

    waveforms = []

    # --- Nouveau format CSV ---
    csv_files = sorted([f for f in os.listdir(session_dir)
                        if f.startswith('waveforms_iter_') and f.endswith('.csv')])
    if csv_files:
        for f in csv_files:
            df = pd.read_csv(os.path.join(session_dir, f))
            wf = {}
            for col in df.columns:
                arr = df[col].to_numpy(dtype=float)
                # Les signaux courts ont été complétés par des NaN pour s'aligner
                # sur les plus longs : on retire ce remplissage de fin.
                valides = np.where(~np.isnan(arr))[0]
                if valides.size:
                    arr = arr[:valides[-1] + 1]
                wf[col] = arr
            waveforms.append(wf)
        return meta, metrics, waveforms

    # --- Ancien format .npz (repli) ---
    npz_files = sorted([f for f in os.listdir(session_dir)
                        if f.startswith('waveforms_iter_') and f.endswith('.npz')])
    for f in npz_files:
        data = np.load(os.path.join(session_dir, f))
        waveforms.append({key: data[key] for key in data.files})

    return meta, metrics, waveforms
def fenetre_signaux_bruts(meta, metrics, waveforms, iter_init=0):
    """Fenêtre dédiée aux signaux BRUTS (pré-synchro/filtrage) et au cycle B-H brut."""
    from matplotlib.widgets import Slider, Button

    def get_raw(wf):
        # Priorité aux signaux bruts complets ; repli sur _2per puis 1 période.
        if 'ChampB_brut' in wf and 'ChampH2_brut' in wf:
            return wf['ChampB_brut'], wf['ChampH2_brut'], wf.get('derivChampB_brut')
        if 'ChampB_2per' in wf and 'ChampH2_2per' in wf:
            return wf['ChampB_2per'], wf['ChampH2_2per'], None
        return wf['ChampB'], wf['ChampH2'], wf.get('derivChampB')

    fig = plt.figure(figsize=(13, 8))
    fig.suptitle(
        f"SIGNAUX BRUTS — {meta['Materiaux']} | {meta['Frequence_Hz']} Hz | "
        f"B={meta['Amplitude_T']} T",
        fontsize=12, fontweight='bold'
    )
    ax_B  = plt.subplot2grid((3, 3), (0, 0), colspan=2, fig=fig)
    ax_dB = plt.subplot2grid((3, 3), (1, 0), colspan=2, fig=fig)
    ax_H  = plt.subplot2grid((3, 3), (2, 0), colspan=2, fig=fig)
    ax_BH = plt.subplot2grid((3, 3), (0, 2), rowspan=3, fig=fig)

    def update(iter_num):
        iter_num = int(iter_num)
        if iter_num < 0 or iter_num >= len(waveforms):
            return
        wf = waveforms[iter_num]
        B, H, dB = get_raw(wf)
        dt = float(wf['timeC'][1] - wf['timeC'][0])   # pas d'échantillonnage (s)
        t_ms = np.arange(len(B)) * dt * 1000           # axe temps reconstruit (buffer complet)

        ax_B.clear()
        ax_B.plot(t_ms, B, 'b-', linewidth=1)
        ax_B.set_ylabel('B brut (T)'); ax_B.grid(True, alpha=0.3)
        ax_B.set_title(f'Itération {iter_num} — signaux bruts (pré-synchro)')

        ax_dB.clear()
        if dB is not None:
            ax_dB.plot(np.arange(len(dB)) * dt * 1000, dB, 'r-', linewidth=1)
        ax_dB.set_ylabel('dB/dt brut (T/s)'); ax_dB.grid(True, alpha=0.3)

        ax_H.clear()
        ax_H.plot(np.arange(len(H)) * dt * 1000, H, color='darkorange', linewidth=1)
        ax_H.set_xlabel('t (ms)'); ax_H.set_ylabel('H brut (A/m)'); ax_H.grid(True, alpha=0.3)

        ax_BH.clear()                                   # cycle B-H brut (B et H en phase → fermé)
        n = min(len(H), len(B))
        ax_BH.plot(H[:n], B[:n], 'b-', linewidth=0.8)
        ax_BH.set_xlabel('H (A/m)'); ax_BH.set_ylabel('B (T)')
        ax_BH.set_title('Cycle B-H brut'); ax_BH.grid(True, alpha=0.3)
        fig.canvas.draw_idle()

    ax_slider = plt.axes([0.15, 0.02, 0.6, 0.02])
    fig._slider = Slider(ax_slider, 'Itération', 0, len(waveforms) - 1,
                         valinit=iter_init, valstep=1, valfmt='%d')
    fig._slider.on_changed(update)

    ax_prev = plt.axes([0.78, 0.015, 0.06, 0.03])
    ax_next = plt.axes([0.86, 0.015, 0.06, 0.03])
    fig._btn_prev = Button(ax_prev, '◀ Préc')
    fig._btn_next = Button(ax_next, 'Suiv ▶')
    fig._btn_prev.on_clicked(lambda e: fig._slider.set_val(max(0, int(fig._slider.val) - 1)))
    fig._btn_next.on_clicked(lambda e: fig._slider.set_val(min(len(waveforms) - 1, int(fig._slider.val) + 1)))

    def on_key(event):
        if event.key == 'right':
            fig._slider.set_val(min(len(waveforms) - 1, int(fig._slider.val) + 1))
        elif event.key == 'left':
            fig._slider.set_val(max(0, int(fig._slider.val) - 1))
    fig.canvas.mpl_connect('key_press_event', on_key)

    update(iter_init)
    fig.tight_layout(rect=[0, 0.06, 1, 0.96])
    return fig
def fenetre_H_compare(meta, metrics, waveforms, iter_init=0):
    """Fenêtre comparant H avant filtrage (ChampH23) et H après filtrage (ChampH2) sur le même graphe."""
    from matplotlib.widgets import Slider, Button

    fig, ax = plt.subplots(figsize=(11, 5))
    plt.subplots_adjust(bottom=0.15, top=0.88)
    fig.suptitle(
        f"H avant / après filtrage — {meta['Materiaux']} | {meta['Frequence_Hz']} Hz | "
        f"B={meta['Amplitude_T']} T",
        fontsize=11, fontweight='bold'
    )

    def update(iter_num):
        iter_num = int(iter_num)
        if iter_num < 0 or iter_num >= len(waveforms):
            return
        wf = waveforms[iter_num]
        dt = float(wf['timeC'][1] - wf['timeC'][0])

        ax.clear()

        H_filt = wf.get('ChampH2_brut')
        if H_filt is not None:
            t_filt = np.arange(len(H_filt)) * dt * 1000
            ax.plot(t_filt, H_filt, color='darkorange', linewidth=1.2,
                    label='H filtré (ChampH2)')

        H_brut = wf.get('ChampH23')
        if H_brut is not None:
            t_brut = np.arange(len(H_brut)) * dt * 1000
            ax.plot(t_brut, H_brut, color='steelblue', linewidth=1,
                    alpha=0.8, label='H avant filtrage (ChampH23)')

        ax.set_xlabel('t (ms)')
        ax.set_ylabel('H (A/m)')
        ax.set_title(f'Itération {iter_num}')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)
        fig.canvas.draw_idle()

    ax_slider = plt.axes([0.15, 0.04, 0.6, 0.025])
    fig._slider = Slider(ax_slider, 'Itération', 0, len(waveforms) - 1,
                         valinit=iter_init, valstep=1, valfmt='%d')
    fig._slider.on_changed(update)

    ax_prev = plt.axes([0.78, 0.03, 0.06, 0.035])
    ax_next = plt.axes([0.86, 0.03, 0.06, 0.035])
    fig._btn_prev = Button(ax_prev, '◀ Préc')
    fig._btn_next = Button(ax_next, 'Suiv ▶')
    fig._btn_prev.on_clicked(lambda e: fig._slider.set_val(max(0, int(fig._slider.val) - 1)))
    fig._btn_next.on_clicked(lambda e: fig._slider.set_val(min(len(waveforms) - 1, int(fig._slider.val) + 1)))

    def on_key(event):
        if event.key == 'right':
            fig._slider.set_val(min(len(waveforms) - 1, int(fig._slider.val) + 1))
        elif event.key == 'left':
            fig._slider.set_val(max(0, int(fig._slider.val) - 1))
    fig.canvas.mpl_connect('key_press_event', on_key)

    update(iter_init)
    return fig
def fenetre_i_compare(meta, metrics, waveforms, iter_init=0):
    """Fenêtre comparant H avant filtrage (ChampH23) et H après filtrage (ChampH2) sur le même graphe."""
    from matplotlib.widgets import Slider, Button

    fig, ax = plt.subplots(figsize=(11, 5))
    plt.subplots_adjust(bottom=0.15, top=0.88)
    fig.suptitle(
        f"i avant / après filtrage — {meta['Materiaux']} | {meta['Frequence_Hz']} Hz | "
        f"B={meta['Amplitude_T']} T",
        fontsize=11, fontweight='bold'
    )

    def update(iter_num):
        iter_num = int(iter_num)
        if iter_num < 0 or iter_num >= len(waveforms):
            return
        wf = waveforms[iter_num]
        dt = float(wf['timeC'][1] - wf['timeC'][0])

        ax.clear()

        H_filt = wf.get('ih_probe')
        if H_filt is not None:
            t_filt = np.arange(len(H_filt)) * dt * 1000
            ax.plot(t_filt, H_filt, color='darkorange', linewidth=1.2,
                    label='ih_probe')

        H_brut = wf.get('ih')
        if H_brut is not None:
            t_brut = np.arange(len(H_brut)) * dt * 1000
            ax.plot(t_brut, H_brut, color='steelblue', linewidth=1,
                    alpha=0.8, label='ih avant filtrage (ChampH23)')

        ax.set_xlabel('t (ms)')
        ax.set_ylabel('ih A')
        ax.set_title(f'Itération {iter_num}')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)
        fig.canvas.draw_idle()

    ax_slider = plt.axes([0.15, 0.04, 0.6, 0.025])
    fig._slider = Slider(ax_slider, 'Itération', 0, len(waveforms) - 1,
                         valinit=iter_init, valstep=1, valfmt='%d')
    fig._slider.on_changed(update)

    ax_prev = plt.axes([0.78, 0.03, 0.06, 0.035])
    ax_next = plt.axes([0.86, 0.03, 0.06, 0.035])
    fig._btn_prev = Button(ax_prev, '◀ Préc')
    fig._btn_next = Button(ax_next, 'Suiv ▶')
    fig._btn_prev.on_clicked(lambda e: fig._slider.set_val(max(0, int(fig._slider.val) - 1)))
    fig._btn_next.on_clicked(lambda e: fig._slider.set_val(min(len(waveforms) - 1, int(fig._slider.val) + 1)))

    def on_key(event):
        if event.key == 'right':
            fig._slider.set_val(min(len(waveforms) - 1, int(fig._slider.val) + 1))
        elif event.key == 'left':
            fig._slider.set_val(max(0, int(fig._slider.val) - 1))
    fig.canvas.mpl_connect('key_press_event', on_key)

    update(iter_init)
    return fig
def viewer_interactif(meta, metrics, waveforms):
    """Fenêtre interactive avec slider et boutons pour parcourir les itérations."""
    fig = plt.figure(figsize=(14, 10.5))
    fig.suptitle(
        f"{meta['Materiaux']} | {meta['Frequence_Hz']} Hz | "
        f"B={meta['Amplitude_T']} T | Mode: {meta['Mode_asservissement']}",
        fontsize=12, fontweight='bold'
    )

    # ----- Grille 4 lignes × 3 colonnes -----
    # Colonne de gauche (cols 0-1) : 4 plots temporels empilés
    ax_B  = plt.subplot2grid((4, 3), (0, 0), colspan=2, fig=fig)
    ax_dB = plt.subplot2grid((4, 3), (1, 0), colspan=2, fig=fig)
    ax_H  = plt.subplot2grid((4, 3), (2, 0), colspan=2, fig=fig)   # NEW : H(t)
    ax_V  = plt.subplot2grid((4, 3), (3, 0), colspan=2, fig=fig)

    # Colonne de droite (col 2) : cycle BH, convergence, infos
    ax_BH   = plt.subplot2grid((4, 3), (0, 2), fig=fig)
    ax_conv = plt.subplot2grid((4, 3), (1, 2), fig=fig)
    ax_info = plt.subplot2grid((4, 3), (2, 2), rowspan=2, fig=fig)

    # Courbe RMSE globale (toujours visible)
    ax_conv.semilogy(metrics['iteration'], metrics['RMSE'], 'b-', linewidth=1)
    ax_conv.set_xlabel('Itération'); ax_conv.set_ylabel('RMSE')
    ax_conv.set_title('Convergence globale'); ax_conv.grid(True, alpha=0.3)
    vline = ax_conv.axvline(0, color='r', linewidth=2)

    def update(iter_num):
        iter_num = int(iter_num)
        if iter_num < 0 or iter_num >= len(waveforms):
            return
        wf = waveforms[iter_num]
        row = metrics.iloc[iter_num]
        t_ms = wf['timeC'] * 1000

        # ---- Champ B ----
        ax_B.clear()
        ax_B.plot(t_ms, wf['ChampBdes'], 'k--', label='B référence', linewidth=1.5)
        ax_B.plot(t_ms, wf['ChampB'],    'b-',  label='B mesuré',   linewidth=1)
        ax_B.set_ylabel('B (T)'); ax_B.legend(loc='upper right')
        ax_B.grid(True, alpha=0.3); ax_B.set_title(f'Itération {iter_num}')

        # ---- dB/dt ----
        ax_dB.clear()
        ax_dB.plot(t_ms, wf['derivChampBdes'], 'k--', label='dB/dt réf',    linewidth=1.5)
        ax_dB.plot(t_ms, wf['derivChampB'],    'r-',  label='dB/dt mesuré', linewidth=1)
        ax_dB.set_ylabel('dB/dt (T/s)'); ax_dB.legend(loc='upper right')
        ax_dB.grid(True, alpha=0.3)

        # ---- Champ H (NEW) ----
        # On préfère ChampH2_raw (pré-synchro, cohérent avec le cycle BH).
        # Fallback sur ChampH2 (post-roll) pour les vieilles sessions.
        ax_H.clear()
        if 'ChampH2_raw' in wf:
            H_t = wf['ChampH2_raw']
        else:
            H_t = wf['ChampH2']
        # Sécurité : tronquer si la longueur diffère de timeC
        n = min(len(H_t), len(t_ms))
        ax_H.plot(t_ms[:n], H_t[:n], color='darkorange', linewidth=1, label='H mesuré')
        ax_H.set_ylabel('H (A/m)'); ax_H.legend(loc='upper right')
        ax_H.grid(True, alpha=0.3)

        # ---- Tension GBF ----
        ax_V.clear()
        ax_V.plot(t_ms, wf['entree'], 'g-', linewidth=1)
        ax_V.set_xlabel('t (ms)'); ax_V.set_ylabel('Tension GBF (V)')
        ax_V.grid(True, alpha=0.3)

        # ---- Cycle B-H ----
        # Priorité aux clés _2per (idéalement pré-synchro depuis le patch interface).
        # Fallback : bouclage artificiel des signaux 1 période.
        ax_BH.clear()
        if 'ChampB_2per' in wf and 'ChampH2_2per' in wf:
            H_plot = wf['ChampH2_2per']
            B_plot = wf['ChampB_2per']
            # Si on a vraiment 2 périodes, on les trace en superposition fermée
            # comme dans l'interface temps réel.
        else:
            H_plot = np.append(wf['ChampH2'], wf['ChampH2'][0])
            B_plot = np.append(wf['ChampB'],  wf['ChampB'][0])

        ax_BH.plot(H_plot, B_plot, 'b-', linewidth=0.8)
        ax_BH.set_xlabel('H (A/m)'); ax_BH.set_ylabel('B (T)')
        ax_BH.set_title('Cycle B-H'); ax_BH.grid(True, alpha=0.3)

        # ---- Ligne sur la convergence ----
        vline.set_xdata([iter_num, iter_num])

        # ---- Infos textuelles ----
        ax_info.clear(); ax_info.axis('off')
        infos = (
            f"RMSE      : {row['RMSE']:.3f}\n"
            f"THD mesuré: {row['THD_mesure']:.2f} %\n"
            f"THD réf.  : {row['THD_reference']:.2f} %\n"
            f"FF mesuré : {row['FF_mesure']:.4f}\n"
            f"FF réf.   : {row['FF_reference']:.4f}\n"
            f"B max     : {row['B_max']:.4f} T\n"
            f"H max     : {row['H_max']:.2f} A/m\n"
            f"I max     : {row['I_max_mA']:.2f} mA\n"
            f"V entrée  : {row['amplitude_entree_V']:.3f} V\n"
            f"Cycle     : {int(row['cycle'])}\n"
            f"Converge  : {'✅' if row['converge'] else '❌'}"
        )
        ax_info.text(0.05, 0.95, infos, transform=ax_info.transAxes,
                     fontfamily='monospace', fontsize=9, verticalalignment='top',
                     bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        fig.canvas.draw_idle()

    # === Slider (attaché à la figure pour éviter garbage collection) ===
    ax_slider = plt.axes([0.15, 0.02, 0.55, 0.02])
    fig._slider = Slider(ax_slider, 'Itération', 0, len(waveforms)-1,
                         valinit=0, valstep=1, valfmt='%d')
    fig._slider.on_changed(update)

    # === Boutons de navigation ===
    ax_first = plt.axes([0.72, 0.015, 0.05, 0.03])
    ax_prev  = plt.axes([0.78, 0.015, 0.05, 0.03])
    ax_next  = plt.axes([0.84, 0.015, 0.05, 0.03])
    ax_last  = plt.axes([0.90, 0.015, 0.05, 0.03])

    fig._btn_first = Button(ax_first, '⏮ 0')
    fig._btn_prev  = Button(ax_prev,  '◀ Préc')
    fig._btn_next  = Button(ax_next,  'Suiv ▶')
    fig._btn_last  = Button(ax_last,  'Fin ⏭')

    # Bouton "meilleure itération" (celle qui a la RMSE minimale)
    ax_best = plt.axes([0.02, 0.015, 0.10, 0.03])
    fig._btn_best = Button(ax_best, '⭐ Meilleure', color='lightyellow')

    def on_first(event):
        fig._slider.set_val(0)

    def on_prev(event):
        new_val = max(0, int(fig._slider.val) - 1)
        fig._slider.set_val(new_val)

    def on_next(event):
        new_val = min(len(waveforms) - 1, int(fig._slider.val) + 1)
        fig._slider.set_val(new_val)

    def on_last(event):
        fig._slider.set_val(len(waveforms) - 1)

    def on_best(event):
        best_iter = int(metrics['RMSE'].idxmin())
        fig._slider.set_val(best_iter)

    fig._btn_first.on_clicked(on_first)
    fig._btn_prev.on_clicked(on_prev)
    fig._btn_next.on_clicked(on_next)
    fig._btn_last.on_clicked(on_last)
    fig._btn_best.on_clicked(on_best)

    # === Navigation clavier (flèches gauche/droite, Home/End) ===
    def on_key(event):
        if event.key == 'right':
            on_next(None)
        elif event.key == 'left':
            on_prev(None)
        elif event.key == 'r':       # R comme "raw / brut" → ouvre la fenêtre des signaux bruts
            f = fenetre_signaux_bruts(meta, metrics, waveforms, int(fig._slider.val))
            fig._raw_windows = getattr(fig, '_raw_windows', [])
            fig._raw_windows.append(f)   # garde une référence (sinon la fenêtre est récupérée par le GC)
            f.show()
        elif event.key == 'home':
            on_first(None)
        elif event.key == 'end':
            on_last(None)
        elif event.key == 'b':       # B comme "best"
            on_best(None)
        elif event.key == 'a':
            f = fenetre_H_compare(meta, metrics, waveforms, int(fig._slider.val))
            fig._h_windows = getattr(fig, '_h_windows', [])
            fig._h_windows.append(f)
            f.show()
        elif event.key == 'i':
            f = fenetre_i_compare(meta, metrics, waveforms, int(fig._slider.val))
            fig._h_windows = getattr(fig, '_h_windows', [])
            fig._h_windows.append(f)
            f.show()

    fig.canvas.mpl_connect('key_press_event', on_key)

    update(0)  # affichage initial
    plt.tight_layout(rect=[0, 0.06, 1, 0.96])
    plt.show()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        session_dir = sys.argv[1]
    else:
        session_dir = list_sessions()

    print(f"\n📂 Chargement : {session_dir}")
    meta, metrics, waveforms = load_session(session_dir)
    print(f"✅ {len(waveforms)} itérations chargées.\n")

    print(f"=== Résumé ===")
    print(f"Matériau    : {meta['Materiaux']}")
    print(f"Fréquence   : {meta['Frequence_Hz']} Hz")
    print(f"Amplitude   : {meta['Amplitude_T']} T")
    print(f"Mode        : {meta['Mode_asservissement']}")
    print(f"RMSE finale : {metrics['RMSE'].iloc[-1]:.3f}")
    print(f"Meilleure   : {metrics['RMSE'].min():.3f} (itér. {metrics['RMSE'].idxmin()})\n")

    print("=== Contrôles ===")
    print("• Slider          : navigation libre")
    print("• ◀ / ▶ ou flèches: itération précédente/suivante")
    print("• ⏮ / ⏭ ou Home/End: première/dernière itération")
    print("• ⭐ ou touche B   : meilleure itération (RMSE min)\n")

    viewer_interactif(meta, metrics, waveforms)