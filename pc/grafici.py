# =====================================================================
# GRAFICI: controlli visivi sui CSV registrati con cavigliera_logger.py
# =====================================================================
#
# Per ogni CSV crea 3 immagini nella cartella grafici/, con il nome del
# file (es. dati/normale_2026-10-23_15-30-12.csv -> normale_2026-10-23_15-30-12):
#   <nome>_segnali.png          forza, accelerazione e giroscopio nel tempo
#   <nome>_dt.png               regolarita' del campionamento
#   <nome>_intorno_contatto.png IMU nei +-200 ms intorno a ogni contatto
# e una immagine che confronta tutti i file passati:
#   durata_passo.png            durata del passo per ogni file
#
# Uso (dalla cartella pc/):
#   python3 grafici.py dati/normale.csv
#   python3 grafici.py dati/normale.csv dati/veloce.csv dati/scale.csv
#   python3 grafici.py dati/normale.csv --da 300 --durata 20

import argparse                   # argomenti della riga di comando
import os                         # cartelle e nomi di file

import matplotlib.pyplot as plt   # per disegnare i grafici
import numpy as np                # calcoli su array di numeri
import pandas as pd               # per leggere il CSV come una tabella

# Colori usati nei grafici (codici esadecimali RGB).
BLU, ARANCIO, ACQUA = "#2a78d6", "#eb6834", "#1baf7a"   # per le curve
GRIGIO, GRIGIO_CHIARO = "#52514e", "#c3c2b7"            # per assi, testi, linee secondarie

# ---------------------------------------------------------------------
# 1. ARGOMENTI DELLA RIGA DI COMANDO
# ---------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Grafici dai CSV della cavigliera")
# nargs="+" = uno o piu' file
parser.add_argument("file", nargs="+", help="uno o piu' CSV, es. dati/normale.csv dati/veloce.csv")
# Soglia sulla forza per dire "il tallone ha toccato terra".
parser.add_argument("--soglia", type=float, default=0.5, help="soglia FSR in volt per il contatto (default 0.5)")
# Valore minimo che la forza deve raggiungere perche' sia un passo vero
# e non un tocco leggero.
parser.add_argument("--picco", type=float, default=2.0,
                    help="forza minima (V) raggiunta perche' sia un passo vero (default 2.0)")
# Quale tratto di tempo mostrare nel grafico "segnali" (gli altri grafici
# usano sempre tutti i dati).
parser.add_argument("--da", type=float, default=0, help="secondo da cui iniziare il grafico nel tempo")
parser.add_argument("--durata", type=float, default=20, help="secondi mostrati nel grafico nel tempo")
args = parser.parse_args()

os.makedirs("grafici", exist_ok=True)  # crea la cartella grafici/ se non esiste

# Stile comune a tutti i grafici: niente bordo in alto e a destra,
# assi e testi grigi, griglia chiara, linee sottili.
plt.rcParams.update({
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": GRIGIO, "axes.labelcolor": GRIGIO,
    "xtick.color": GRIGIO, "ytick.color": GRIGIO,
    "axes.grid": True, "grid.color": "#e8e7e3", "grid.linewidth": 0.8,
    "lines.linewidth": 1.5, "figure.dpi": 110,
})


# ---------------------------------------------------------------------
# 2. FUNZIONI
# ---------------------------------------------------------------------
def contatti(t, forza, soglia, picco_min):
    """Istanti (s) in cui la forza supera la soglia salendo = contatto del tallone.

    Un tratto sopra soglia conta come contatto solo se arriva almeno a picco_min:
    i piccoli tocchi (piede appoggiato di lato, sensore sfiorato) non sono passi.
    L'istante e' interpolato tra i due campioni a cavallo della soglia.

    t      = array dei tempi in secondi
    forza  = array dei valori dell'FSR in volt (stessa lunghezza di t)
    Restituisce un array con gli istanti dei contatti, in secondi.
    """
    eventi = []
    i = 1
    while i < len(forza):
        # Fronte di salita: il campione precedente e' SOTTO la soglia e
        # quello attuale e' SOPRA (o uguale). E' il tallone che si appoggia.
        if forza[i - 1] < soglia <= forza[i]:
            # Cerca dove la forza torna sotto soglia (tallone che si alza):
            # j sara' il primo campione di nuovo sotto soglia.
            j = i
            while j < len(forza) and forza[j] >= soglia:
                j += 1
            # Il tratto da i a j e' un appoggio. Lo conto come passo solo
            # se il valore massimo raggiunto e' almeno picco_min.
            if forza[i:j].max() >= picco_min:
                # Interpolazione lineare: la soglia e' stata superata in un
                # punto tra il campione i-1 e il campione i. Tracciando una
                # retta tra i due punti, calcolo in che istante esatto la
                # retta vale "soglia". Cosi' la precisione e' migliore dei
                # 20 ms tra un campione e l'altro.
                f0, f1 = forza[i - 1], forza[i]
                eventi.append(t[i - 1] + (soglia - f0) / (f1 - f0) * (t[i] - t[i - 1]))
            # Riparte a cercare dopo la fine di questo appoggio.
            i = j
        i += 1
    return np.array(eventi)


def carica(percorso):
    """Legge un CSV e prepara i dati. Restituisce (tabella, nome del file senza estensione)."""
    d = pd.read_csv(percorso)  # tabella: una colonna per ogni nome dell'intestazione

    # Scarta le righe con l'IMU tutto a zero (succede nel primo mezzo
    # secondo, quando il BNO055 non e' ancora pronto). Serve per i CSV
    # registrati prima che il logger le scartasse da solo.
    imu = ["yaw", "roll", "pitch", "acc_x", "acc_y", "acc_z", "gyr_x", "gyr_y", "gyr_z"]
    d = d[~(d[imu] == 0).all(axis=1)].reset_index(drop=True)

    # Nuova colonna "t": tempo in secondi dall'inizio della prova
    # (tempo_ms parte da quando e' stata accesa la scheda, non da zero).
    d["t"] = (d["tempo_ms"] - d["tempo_ms"].iloc[0]) / 1000

    # Nuova colonna "acc_norma": modulo dell'accelerazione = lunghezza del
    # vettore (acc_x, acc_y, acc_z), con Pitagora in 3D. Non dipende da come
    # e' girata la cavigliera; da fermo vale circa 9.8 (la gravita').
    d["acc_norma"] = np.sqrt(d.acc_x**2 + d.acc_y**2 + d.acc_z**2)

    # Nome della prova: il nome del file senza cartella e senza ".csv"
    # (es. dati/normale_2026-10-23_15-30-12.csv -> "normale_2026-10-23_15-30-12").
    # Non uso la colonna "stile": due prove dello stesso stile avrebbero lo
    # stesso nome e i loro grafici si sovrascriverebbero.
    nome = os.path.splitext(os.path.basename(percorso))[0]
    return d, nome


# ---------------------------------------------------------------------
# 3. GRAFICI PER OGNI FILE
# ---------------------------------------------------------------------
# Qui raccolgo le durate dei passi di ogni file, per l'ultimo grafico.
# E' un dizionario: {"normale_...": [1.35, 1.40, ...], "veloce_...": [...], ...}
durate_passo = {}

for percorso in args.file:
    d, nome = carica(percorso)
    t = d["t"].to_numpy()  # tempi in secondi come array numpy

    # hs = "heel strikes": istanti dei contatti del tallone trovati dalla forza
    hs = contatti(t, d["forza_V"].to_numpy(), args.soglia, args.picco)

    # Intervalli tra righe consecutive in ms (np.diff fa la differenza
    # tra ogni elemento e il precedente). Dovrebbero essere tutti 20.
    dt_ms = np.diff(d["tempo_ms"].to_numpy())

    # Riassunto a terminale
    print(f"{percorso}: {len(d)} righe, {t[-1]:.1f} s, dt mediano {np.median(dt_ms):.0f} ms, {len(hs)} contatti")

    # --- GRAFICO 1: segnali nel tempo con i contatti ----------------------
    # fin = "finestra": True per le righe nel tratto da mostrare
    # (da args.da a args.da + args.durata secondi), False per le altre.
    fin = (t >= args.da) & (t <= args.da + args.durata)

    # 3 grafici uno sopra l'altro con lo stesso asse x (sharex=True).
    fig, ax = plt.subplots(3, 1, figsize=(11, 7), sharex=True)

    # In alto: forza + linea tratteggiata orizzontale alla soglia
    ax[0].plot(t[fin], d.forza_V[fin], color=BLU)
    ax[0].axhline(args.soglia, color=GRIGIO, linestyle="--", linewidth=1)
    ax[0].set_ylabel("forza (V)")

    # Al centro: modulo dell'accelerazione
    ax[1].plot(t[fin], d.acc_norma[fin], color=BLU)
    ax[1].set_ylabel("|acc| (m/s²)")

    # In basso: i tre assi del giroscopio, un colore per asse
    for col, colore in zip(["gyr_x", "gyr_y", "gyr_z"], [BLU, ARANCIO, ACQUA]):
        ax[2].plot(t[fin], d[col][fin], color=colore, label=col)
    ax[2].set_ylabel("giroscopio (°/s)")
    ax[2].legend(loc="upper right", frameon=False, ncol=3)
    ax[2].set_xlabel("tempo (s)")

    # Su tutti e 3 i grafici: una linea verticale per ogni contatto che
    # cade nel tratto mostrato (zorder=0 = disegnata dietro alle curve).
    for a in ax:
        for e in hs[(hs >= args.da) & (hs <= args.da + args.durata)]:
            a.axvline(e, color=GRIGIO_CHIARO, linewidth=1, zorder=0)
    ax[0].set_title(f"{nome}: segnali nel tempo (linee verticali = contatti del tallone dalla forza)",
                    loc="left", fontsize=11)
    fig.tight_layout()                            # sistema gli spazi tra i grafici
    fig.savefig(f"grafici/{nome}_segnali.png")   # salva l'immagine
    plt.close(fig)                                # libera la memoria

    # --- GRAFICO 2: regolarita' del campionamento -------------------------
    # Istogramma degli intervalli tra righe: una barra per ogni valore in
    # ms (bins larghi 1 ms). Se tutto va bene c'e' una sola barra a 20 ms.
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(dt_ms, bins=np.arange(dt_ms.min() - 0.5, dt_ms.max() + 1.5, 1), color=BLU, rwidth=0.9)
    ax.set_xlabel("Δt tra righe consecutive (ms)")
    ax.set_ylabel("numero di righe")
    ax.set_title(f"{nome}: campionamento (mediana {np.median(dt_ms):.0f} ms)", loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(f"grafici/{nome}_dt.png")
    plt.close(fig)

    # --- GRAFICO 3: IMU intorno a ogni contatto (+-200 ms) ----------------
    # Per ogni contatto ritaglio il segnale da 200 ms prima a 200 ms dopo e
    # sovrappongo tutti i ritagli, allineati sul contatto (= tempo 0).
    # Cosi' si vede la forma "tipica" del segnale quando il tallone tocca.
    if len(hs) > 0:
        # 81 istanti relativi da -0.2 s a +0.2 s (uno ogni 5 ms)
        finestra = np.linspace(-0.2, 0.2, 81)

        # 4 riquadri in una griglia 2x2; ravel() li mette in una lista semplice
        fig, ax = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
        ax = ax.ravel()
        pannelli = [("acc_norma", "|acc| (m/s²)"), ("gyr_x", "gyr_x (°/s)"),
                    ("gyr_y", "gyr_y (°/s)"), ("gyr_z", "gyr_z (°/s)")]

        for a, (col, etichetta) in zip(ax, pannelli):
            # Per ogni contatto e: valori del segnale agli istanti e + finestra.
            # np.interp calcola il valore anche tra due campioni (i contatti
            # non cadono esattamente su una riga). I contatti troppo vicini
            # all'inizio o alla fine della prova (finestra incompleta) sono esclusi.
            tracce = np.array([np.interp(e + finestra, t, d[col]) for e in hs
                               if e - 0.2 >= t[0] and e + 0.2 <= t[-1]])
            # Ogni contatto e' una linea grigia sottile...
            for tr in tracce:
                a.plot(finestra * 1000, tr, color=GRIGIO_CHIARO, linewidth=0.8)
            # ...e la media di tutti (istante per istante) una linea blu spessa
            if len(tracce):
                a.plot(finestra * 1000, tracce.mean(axis=0), color=BLU, linewidth=2, label="media")
            a.axvline(0, color=GRIGIO, linestyle="--", linewidth=1)  # istante del contatto
            a.set_xlabel("tempo dal contatto (ms)")
            a.set_ylabel(etichetta)
            a.legend(loc="upper right", frameon=False)
        ax[0].set_title(f"{nome}: IMU intorno ai {len(hs)} contatti (grigio = singoli, blu = media)",
                        loc="left", fontsize=11)
        fig.tight_layout()
        fig.savefig(f"grafici/{nome}_intorno_contatto.png")
        plt.close(fig)

    # Durata di ogni passo = tempo tra un contatto e il successivo
    # (dello stesso piede). Servono almeno 2 contatti.
    if len(hs) > 1:
        durate_passo[nome] = np.diff(hs)

# ---------------------------------------------------------------------
# 4. GRAFICO 4: durata del passo per file (tutti i file insieme)
# ---------------------------------------------------------------------
# Boxplot: per ogni file una "scatola". La linea blu e' la mediana, la
# scatola contiene la meta' centrale dei passi, i baffi l'intervallo dei
# valori normali, i cerchietti i valori anomali (pause, curve).
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
