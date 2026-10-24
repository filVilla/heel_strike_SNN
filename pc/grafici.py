# Grafici di controllo sui CSV registrati con cavigliera_logger.py
# Uso: python3 grafici.py dati/normale.csv [dati/veloce.csv ...] [--da 300 --durata 20]

import argparse
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BLU, ARANCIO, ACQUA = "#2a78d6", "#eb6834", "#1baf7a"
GRIGIO, GRIGIO_CHIARO = "#52514e", "#c3c2b7"

parser = argparse.ArgumentParser(description="Grafici dai CSV della cavigliera")
parser.add_argument("file", nargs="+", help="uno o piu' CSV, es. dati/normale.csv dati/veloce.csv")
parser.add_argument("--soglia", type=float, default=0.5, help="soglia FSR in volt per il contatto (default 0.5)")
parser.add_argument("--picco", type=float, default=2.0,
                    help="forza minima (V) raggiunta perche' sia un passo vero (default 2.0)")
parser.add_argument("--da", type=float, default=0, help="secondo da cui iniziare il grafico nel tempo")
parser.add_argument("--durata", type=float, default=20, help="secondi mostrati nel grafico nel tempo")
args = parser.parse_args()

os.makedirs("grafici", exist_ok=True)

plt.rcParams.update({
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": GRIGIO, "axes.labelcolor": GRIGIO,
    "xtick.color": GRIGIO, "ytick.color": GRIGIO,
    "axes.grid": True, "grid.color": "#e8e7e3", "grid.linewidth": 0.8,
    "lines.linewidth": 1.5, "figure.dpi": 110,
})


def contatti(t, forza, soglia, picco_min):
    """Istanti (s) dei contatti del tallone: fronti di salita sopra soglia con picco >= picco_min."""
    eventi = []
    i = 1
    while i < len(forza):
        if forza[i - 1] < soglia <= forza[i]:
            j = i
            while j < len(forza) and forza[j] >= soglia:
                j += 1
            if forza[i:j].max() >= picco_min:
                # Interpolazione lineare sulla soglia
                f0, f1 = forza[i - 1], forza[i]
                eventi.append(t[i - 1] + (soglia - f0) / (f1 - f0) * (t[i] - t[i - 1]))
            i = j
        i += 1
    return np.array(eventi)


def carica(percorso):
    """Legge un CSV e prepara i dati. Restituisce (tabella, nome del file senza estensione)."""
    d = pd.read_csv(percorso)

    imu = ["yaw", "roll", "pitch", "acc_x", "acc_y", "acc_z", "gyr_x", "gyr_y", "gyr_z"]
    d = d[~(d[imu] == 0).all(axis=1)].reset_index(drop=True)

    d["t"] = (d["tempo_ms"] - d["tempo_ms"].iloc[0]) / 1000
    d["acc_norma"] = np.sqrt(d.acc_x**2 + d.acc_y**2 + d.acc_z**2)

    nome = os.path.splitext(os.path.basename(percorso))[0]
    return d, nome


durate_passo = {}

for percorso in args.file:
    d, nome = carica(percorso)
    t = d["t"].to_numpy()

    hs = contatti(t, d["forza_V"].to_numpy(), args.soglia, args.picco)
    dt_ms = np.diff(d["tempo_ms"].to_numpy())

    print(f"{percorso}: {len(d)} righe, {t[-1]:.1f} s, dt mediano {np.median(dt_ms):.0f} ms, {len(hs)} contatti")

    # Grafico 1: segnali nel tempo con i contatti
    fin = (t >= args.da) & (t <= args.da + args.durata)

    fig, ax = plt.subplots(3, 1, figsize=(11, 7), sharex=True)

    ax[0].plot(t[fin], d.forza_V[fin], color=BLU)
    ax[0].axhline(args.soglia, color=GRIGIO, linestyle="--", linewidth=1)
    ax[0].set_ylabel("forza (V)")

    ax[1].plot(t[fin], d.acc_norma[fin], color=BLU)
    ax[1].set_ylabel("|acc| (m/s²)")

    for col, colore in zip(["gyr_x", "gyr_y", "gyr_z"], [BLU, ARANCIO, ACQUA]):
        ax[2].plot(t[fin], d[col][fin], color=colore, label=col)
    ax[2].set_ylabel("giroscopio (°/s)")
    ax[2].legend(loc="upper right", frameon=False, ncol=3)
    ax[2].set_xlabel("tempo (s)")

    for a in ax:
        for e in hs[(hs >= args.da) & (hs <= args.da + args.durata)]:
            a.axvline(e, color=GRIGIO_CHIARO, linewidth=1, zorder=0)
    ax[0].set_title(f"{nome}: segnali nel tempo (linee verticali = contatti del tallone dalla forza)",
                    loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(f"grafici/{nome}_segnali.png")
    plt.close(fig)

    # Grafico 2: regolarita' del campionamento
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(dt_ms, bins=np.arange(dt_ms.min() - 0.5, dt_ms.max() + 1.5, 1), color=BLU, rwidth=0.9)
    ax.set_xlabel("Δt tra righe consecutive (ms)")
    ax.set_ylabel("numero di righe")
    ax.set_title(f"{nome}: campionamento (mediana {np.median(dt_ms):.0f} ms)", loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(f"grafici/{nome}_dt.png")
    plt.close(fig)

    # Grafico 3: IMU nei +-200 ms intorno a ogni contatto
    if len(hs) > 0:
        finestra = np.linspace(-0.2, 0.2, 81)

        fig, ax = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
        ax = ax.ravel()
        pannelli = [("acc_norma", "|acc| (m/s²)"), ("gyr_x", "gyr_x (°/s)"),
                    ("gyr_y", "gyr_y (°/s)"), ("gyr_z", "gyr_z (°/s)")]

        for a, (col, etichetta) in zip(ax, pannelli):
            tracce = np.array([np.interp(e + finestra, t, d[col]) for e in hs
                               if e - 0.2 >= t[0] and e + 0.2 <= t[-1]])
            for tr in tracce:
                a.plot(finestra * 1000, tr, color=GRIGIO_CHIARO, linewidth=0.8)
            if len(tracce):
                a.plot(finestra * 1000, tracce.mean(axis=0), color=BLU, linewidth=2, label="media")
            a.axvline(0, color=GRIGIO, linestyle="--", linewidth=1)
            a.set_xlabel("tempo dal contatto (ms)")
            a.set_ylabel(etichetta)
            a.legend(loc="upper right", frameon=False)
        ax[0].set_title(f"{nome}: IMU intorno ai {len(hs)} contatti (grigio = singoli, blu = media)",
                        loc="left", fontsize=11)
        fig.tight_layout()
        fig.savefig(f"grafici/{nome}_intorno_contatto.png")
        plt.close(fig)

    if len(hs) > 1:
        durate_passo[nome] = np.diff(hs)

# Grafico 4: durata del passo per file
if durate_passo:
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.boxplot(list(durate_passo.values()), tick_labels=list(durate_passo.keys()), widths=0.5,
               medianprops={"color": BLU, "linewidth": 2},
               boxprops={"color": GRIGIO}, whiskerprops={"color": GRIGIO},
               capprops={"color": GRIGIO}, flierprops={"markeredgecolor": GRIGIO})
    ax.set_ylabel("durata del passo (s)")
    ax.set_title("Durata del passo per file", loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig("grafici/durata_passo.png")
    plt.close(fig)

print("Grafici salvati in", os.path.abspath("grafici"))
