# GRAFICI DELLE REGISTRAZIONI
# Cosa fa: dai CSV crea in grafici/<nome>/ segnali nel tempo, IMU intorno al contatto, durata dello stride,
#          tallone a terra, ciclo del passo normalizzato, ritratto di fase e accelerazione verticale/sagittale
#          contro la forza intorno al contatto; con piu' file anche il confronto.
# A cosa serve: controllare a occhio i dati e mostrare com'e' fatto il passo. Non modifica i CSV.
# Uso: python3 grafici.py dati/normale.csv [dati/veloce.csv ...] [--salta 30 --da 155 --durata 20]
#      con --solo-acc-forza fa solo il grafico accelerazione verticale/sagittale contro forza
#      con --solo-confronto rifa' solo i grafici di confronto tra piu' file

import argparse
import os
import sys
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# comune.py e' in pc/, una cartella sopra questo script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comune import acc_tibia, contatti, omega_sagittale  # noqa: E402

BLU, ARANCIO, ACQUA = "#2a78d6", "#eb6834", "#1baf7a"
GRIGIO, GRIGIO_CHIARO = "#52514e", "#c3c2b7"

parser = argparse.ArgumentParser(description="Grafici dai CSV della cavigliera")
parser.add_argument("file", nargs="+", help="uno o piu' CSV, es. dati/normale.csv dati/veloce.csv")
parser.add_argument("--soglia", type=float, default=0.5, help="soglia FSR in volt per il contatto (default 0.5)")
parser.add_argument("--picco", type=float, default=2.0,
                    help="forza minima (V) raggiunta perche' sia un passo vero (default 2.0)")
parser.add_argument("--min-contatto", type=float, default=40,
                    help="durata minima (ms) sopra soglia perche' sia un passo vero (default 40)")
parser.add_argument("--unisci", type=float, default=0.2,
                    help="pezzi di contatto separati da meno di questi secondi sono un solo passo (default 0.2)")
parser.add_argument("--salta", type=float, default=30,
                    help="secondi iniziali scartati, mentre si prende il ritmo (default 30)")
parser.add_argument("--da", type=float, default=None,
                    help="secondo da cui iniziare il grafico nel tempo (default = --salta)")
parser.add_argument("--durata", type=float, default=20, help="secondi mostrati nel grafico nel tempo")
parser.add_argument("--solo-confronto", action="store_true",
                    help="fa solo i grafici di confronto, senza rifare quelli dei singoli file")
parser.add_argument("--solo-acc-forza", action="store_true",
                    help="fa solo il grafico accelerazione verticale/sagittale contro forza (acc_forza.png)")
args = parser.parse_args()
if args.da is None:
    args.da = args.salta

plt.rcParams.update({
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": GRIGIO, "axes.labelcolor": GRIGIO,
    "xtick.color": GRIGIO, "ytick.color": GRIGIO,
    "axes.grid": True, "grid.color": "#e8e7e3", "grid.linewidth": 0.8,
    "lines.linewidth": 1.5, "figure.dpi": 110,
})


def cicli(t, inizi, fini, segnali, n=101):
    """Ogni ciclo contatto -> contatto ricampionato su n punti (0-100%). Scarta i cicli che si
    discostano piu' del 30% dalla mediana (giri, pause). Aggiunge l'angolo sagittale, integrato
    dentro ogni ciclo, e la quota del ciclo con il tallone a terra."""
    st = np.diff(inizi)
    validi = np.abs(st / np.median(st) - 1) < 0.3
    perc = np.linspace(0, 1, n)
    out = {k: [] for k in list(segnali) + ["angolo", "tallone"]}
    for a, b, f in zip(inizi[:-1][validi], inizi[1:][validi], fini[:-1][validi]):
        for k, v in segnali.items():
            out[k].append(np.interp(a + perc * (b - a), t, v))
        w = out["omega"][-1]
        ang = np.concatenate([[0], np.cumsum((w[1:] + w[:-1]) / 2)]) * (b - a) / (n - 1)
        # Deriva del giroscopio: inizio e fine del ciclo allo stesso angolo
        ang -= np.linspace(0, ang[-1], n)
        out["angolo"].append(ang - ang.mean())
        out["tallone"].append(100 * (f - a) / (b - a))
    return {k: np.array(v) for k, v in out.items()}


def carica(percorso):
    """Legge un CSV e prepara i dati. Restituisce (tabella, nome del file senza estensione, nome della
    prova nei grafici: lo stile di camminata, normale/veloce, se il CSV lo contiene)."""
    d = pd.read_csv(percorso)

    imu = ["yaw", "roll", "pitch", "acc_x", "acc_y", "acc_z", "gyr_x", "gyr_y", "gyr_z"]
    d = d[~(d[imu] == 0).all(axis=1)].reset_index(drop=True)

    d["t"] = (d["tempo_ms"] - d["tempo_ms"].iloc[0]) / 1000
    # Scarta l'inizio della prova; il tempo resta contato dall'inizio della registrazione
    d = d[d["t"] >= args.salta].reset_index(drop=True)
    d["acc_norma"] = np.sqrt(d.acc_x**2 + d.acc_y**2 + d.acc_z**2)

    nome = os.path.splitext(os.path.basename(percorso))[0]
    prova = d["stile"].iloc[0] if "stile" in d else nome
    return d, nome, prova


def grafico_acc_forza(d, t, hs, prova, cartella):
    """Grafico 3b: forza e accelerazione verticale/sagittale (assi della tibia) intorno al contatto."""
    finestra = np.linspace(-0.3, 0.5, 161)
    dentro = [e for e in hs if e - 0.3 >= t[0] and e + 0.5 <= t[-1]]
    fig, ax = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    pannelli = [("forza_V", "forza tallone (V)"), ("acc_vert", "acc. verticale (m/s²)"),
                ("acc_sag", "acc. sagittale, + avanti (m/s²)")]
    for a, (col, etichetta) in zip(ax, pannelli):
        tracce = np.array([np.interp(e + finestra, t, d[col]) for e in dentro])
        for tr in tracce:
            a.plot(finestra * 1000, tr, color=GRIGIO_CHIARO, linewidth=0.5)
        if len(tracce):
            a.plot(finestra * 1000, tracce.mean(axis=0), color=BLU, linewidth=2, label="media")
        a.axvline(0, color=GRIGIO, linestyle="--", linewidth=1)
        a.set_ylabel(etichetta)
    ax[0].axhline(args.soglia, color=GRIGIO, linestyle=":", linewidth=1)
    ax[0].legend(loc="upper right", frameon=False)
    ax[2].set_xlabel("tempo dal contatto del tallone (ms)")
    ax[0].set_title(f"{prova}: accelerazione verticale e sagittale rispetto alla forza, {len(dentro)} contatti",
                    loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(f"{cartella}/acc_forza.png")
    plt.close(fig)


durate_passo = {}
cicli_prova = {}

for percorso in args.file:
    d, nome, prova = carica(percorso)
    # Due prove dello stesso stile: si aggiunge il nome del file per distinguerle
    if prova in durate_passo or prova in cicli_prova:
        prova = f"{prova} ({nome})"
    t = d["t"].to_numpy()

    hs, fine_hs = contatti(t, d["forza_V"].to_numpy(), args.soglia, args.picco, args.min_contatto / 1000, args.unisci)
    d["omega"] = omega_sagittale(d[["gyr_x", "gyr_y", "gyr_z"]].to_numpy(), hs, t)
    d["acc_vert"], d["acc_sag"] = acc_tibia(d[["acc_x", "acc_y", "acc_z"]].to_numpy(),
                                            d[["gyr_x", "gyr_y", "gyr_z"]].to_numpy(), hs, fine_hs, t)
    dt_ms = np.diff(d["tempo_ms"].to_numpy())

    # Ogni prova nella sua cartella: le prove successive non la sovrascrivono
    cartella = os.path.join("grafici", nome)
    if not args.solo_confronto:
        os.makedirs(cartella, exist_ok=True)

    if args.solo_acc_forza:
        if len(hs) > 0:
            grafico_acc_forza(d, t, hs, prova, cartella)
        continue

    print(f"{percorso}: {len(d)} righe, {t[-1]:.1f} s, dt mediano {np.median(dt_ms):.0f} ms, {len(hs)} contatti")

    if not args.solo_confronto:
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
        ax[0].set_title(f"{prova}: segnali nel tempo (linee verticali = contatti del tallone dalla forza)",
                        loc="left", fontsize=11)
        fig.tight_layout()
        fig.savefig(f"{cartella}/segnali.png")
        plt.close(fig)

        # Grafico 2: regolarita' del campionamento
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.hist(dt_ms, bins=np.arange(dt_ms.min() - 0.5, dt_ms.max() + 1.5, 1), color=BLU, rwidth=0.9)
        ax.set_xlabel("Δt tra righe consecutive (ms)")
        ax.set_ylabel("numero di righe")
        ax.set_title(f"{prova}: campionamento (mediana {np.median(dt_ms):.0f} ms)", loc="left", fontsize=11)
        fig.tight_layout()
        fig.savefig(f"{cartella}/dt.png")
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
            ax[0].set_title(f"{prova}: IMU intorno ai {len(hs)} contatti (grigio = singoli, blu = media)",
                            loc="left", fontsize=11)
            fig.tight_layout()
            fig.savefig(f"{cartella}/intorno_contatto.png")
            plt.close(fig)
            grafico_acc_forza(d, t, hs, prova, cartella)

    if len(hs) > 1:
        durate_passo[prova] = np.diff(hs)
        # CV = deviazione standard / media: variabilita' dello stride in percentuale
        st = durate_passo[prova]
        print(f"  stride: media {st.mean():.3f} s, dev. std {st.std():.3f} s, CV {100 * st.std() / st.mean():.1f}%")

    if len(hs) > 2:
        c = cicli(t, hs, fine_hs, {"forza_V": d.forza_V.to_numpy(), "omega": d.omega.to_numpy()})
        cicli_prova[prova] = c
        perc = np.linspace(0, 100, c["omega"].shape[1])
        print(f"  {len(c['omega'])} cicli validi, tallone a terra {c['tallone'].mean():.0f}% del ciclo")

        if not args.solo_confronto:
            # Grafico 5: ciclo del passo normalizzato 0-100%, media +- deviazione standard
            fig, ax = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
            pannelli = [("forza_V", "forza (V)"), ("omega", "vel. angolare sagittale (°/s)"),
                        ("angolo", "angolo sagittale (°)")]
            for a, (col, etichetta) in zip(ax, pannelli):
                m, s = c[col].mean(axis=0), c[col].std(axis=0)
                a.fill_between(perc, m - s, m + s, color=BLU, alpha=0.2, linewidth=0)
                a.plot(perc, m, color=BLU, linewidth=2)
                a.axvline(c["tallone"].mean(), color=GRIGIO, linestyle="--", linewidth=1)
                a.set_ylabel(etichetta)
            ax[0].text(c["tallone"].mean() + 1, ax[0].get_ylim()[1], "il tallone si stacca", color=GRIGIO,
                       va="top", fontsize=9)
            ax[2].set_xlabel("ciclo del passo (%), 0 = contatto del tallone")
            ax[0].set_title(f"{prova}: ciclo del passo normalizzato, {len(c['omega'])} cicli (banda = ± dev. std)",
                            loc="left", fontsize=11)
            fig.tight_layout()
            fig.savefig(f"{cartella}/ciclo_normalizzato.png")
            plt.close(fig)

            # Grafico 6: ritratto di fase, angolo contro velocita' angolare; ogni ciclo e' un anello
            fig, ax = plt.subplots(figsize=(7, 6))
            for ang, w in zip(c["angolo"], c["omega"]):
                ax.plot(ang, w, color=GRIGIO_CHIARO, linewidth=0.6)
            am, wm = c["angolo"].mean(axis=0), c["omega"].mean(axis=0)
            ax.plot(am, wm, color=BLU, linewidth=2, label="media")
            ax.plot(am[0], wm[0], "o", color=ARANCIO, markersize=8, label="contatto del tallone")
            ax.set_xlabel("angolo sagittale (°)")
            ax.set_ylabel("velocità angolare sagittale (°/s)")
            ax.legend(loc="upper left", frameon=False)
            ax.set_title(f"{prova}: ritratto di fase ({len(c['omega'])} cicli)", loc="left", fontsize=11)
            fig.tight_layout()
            fig.savefig(f"{cartella}/ritratto_fase.png")
            plt.close(fig)

# Grafico 4: durata del ciclo del passo (stride: contatto -> contatto successivo dello stesso piede)
# Con un solo file va nella sua cartella, con piu' file in grafici/confronto_<data>_<ora>/
if durate_passo:
    if len(args.file) == 1:
        cartella = os.path.join("grafici", nome)
    else:
        cartella = os.path.join("grafici", "confronto_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
    os.makedirs(cartella, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.boxplot(list(durate_passo.values()), tick_labels=[n.replace("_", "\n", 1) for n in durate_passo], widths=0.5,
               medianprops={"color": BLU, "linewidth": 2},
               boxprops={"color": GRIGIO}, whiskerprops={"color": GRIGIO},
               capprops={"color": GRIGIO}, flierprops={"markeredgecolor": GRIGIO})
    ax.set_ylabel("durata del ciclo, stride (s)")
    ax.set_title(f"Durata del ciclo del passo (stride), primi {args.salta:g} s esclusi", loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(f"{cartella}/durata_passo.png")
    plt.close(fig)

# Grafico 7: quota del ciclo con il tallone a terra (l'FSR e' solo sul tallone: non e' tutto l'appoggio)
if cicli_prova:
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.boxplot([c["tallone"] for c in cicli_prova.values()], tick_labels=[n.replace("_", "\n", 1) for n in cicli_prova], widths=0.5,
               medianprops={"color": BLU, "linewidth": 2},
               boxprops={"color": GRIGIO}, whiskerprops={"color": GRIGIO},
               capprops={"color": GRIGIO}, flierprops={"markeredgecolor": GRIGIO})
    ax.set_ylabel("tallone a terra (% del ciclo)")
    ax.set_title("Quota del ciclo con il tallone a terra (FSR sopra soglia)", loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(f"{cartella}/tallone_a_terra.png")
    plt.close(fig)

# Grafico 8: cicli medi delle prove sovrapposti, solo con piu' file
if len(cicli_prova) > 1:
    fig, ax = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    pannelli = [("forza_V", "forza (V)"), ("omega", "vel. angolare sagittale (°/s)"),
                ("angolo", "angolo sagittale (°)")]
    for (prova, c), colore in zip(cicli_prova.items(), [BLU, ARANCIO, ACQUA, GRIGIO]):
        perc = np.linspace(0, 100, c["omega"].shape[1])
        for a, (col, etichetta) in zip(ax, pannelli):
            m, s = c[col].mean(axis=0), c[col].std(axis=0)
            a.fill_between(perc, m - s, m + s, color=colore, alpha=0.15, linewidth=0)
            a.plot(perc, m, color=colore, linewidth=2, label=prova)
            a.set_ylabel(etichetta)
    ax[0].legend(loc="upper right", frameon=False, fontsize=9)
    ax[2].set_xlabel("ciclo del passo (%), 0 = contatto del tallone")
    ax[0].set_title("Ciclo del passo medio a confronto (banda = ± dev. std)", loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(f"{cartella}/ciclo_confronto.png")
    plt.close(fig)

print("Grafici salvati in", os.path.abspath("grafici"))
