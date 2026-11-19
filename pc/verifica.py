# CONTROLLO DI QUALITA' DELLE REGISTRAZIONI
# Cosa fa: per ogni CSV stampa un report (durata, campionamento, cadenza, regolarita' dello stride,
#          durata dell'appoggio, spostamento della cavigliera) e dice se la registrazione PASSA.
# A cosa serve: decidere se un file e' abbastanza buono per i grafici e il training delle reti.
#               I controlli bloccanti riguardano acc, gyr e forza; quelli sull'orientamento sono solo avvisi.
# Uso: python3 verifica.py dati/normale.csv [dati/veloce.csv ...] [--da 30]

import argparse

import numpy as np
import pandas as pd

from comune import contatti

parser = argparse.ArgumentParser(description="Controllo di qualita' dei CSV della cavigliera")
parser.add_argument("file", nargs="+", help="uno o piu' CSV")
parser.add_argument("--da", type=float, default=30, help="secondi iniziali esclusi dal controllo (default 30)")
args = parser.parse_args()


def controlla(percorso):
    d = pd.read_csv(percorso)
    t = ((d["tempo_ms"] - d["tempo_ms"].iloc[0]) / 1000).to_numpy()
    hs, fini = contatti(t, d["forza_V"].to_numpy())
    appoggi = fini - hs
    appoggi, hs = appoggi[hs >= args.da], hs[hs >= args.da]
    d, t = d[t >= args.da], t[t >= args.da]

    st = np.diff(hs)
    fuori = np.mean((st < 0.6 * np.median(st)) | (st > 1.5 * np.median(st)))

    # Direzione della gravita' minuto per minuto: se cambia, la cavigliera si e' spostata
    minuto = (t // 60).astype(int)
    g = d.groupby(minuto)[["acc_x", "acc_y", "acc_z"]].mean().to_numpy()
    g = g / np.linalg.norm(g, axis=1, keepdims=True)
    media = g.mean(axis=0) / np.linalg.norm(g.mean(axis=0))
    spostamento = np.degrees(np.arccos(np.clip(g @ media, -1, 1))).max()

    # (descrizione, valore misurato, passa?)
    righe = [
        ("durata analizzata >= 120 s", f"{t[-1] - t[0]:.0f} s", t[-1] - t[0] >= 120),
        ("campionamento senza buchi (dt max <= 25 ms)", f"{d['tempo_ms'].diff().max():.0f} ms",
         d["tempo_ms"].diff().max() <= 25),
        ("passi al minuto tra 40 e 70", f"{60 * len(hs) / (t[-1] - t[0]):.0f}",
         40 <= 60 * len(hs) / (t[-1] - t[0]) <= 70),
        ("stride regolare (CV <= 10%)", f"{100 * st.std() / st.mean():.1f}%", st.std() / st.mean() <= 0.1),
        ("stride anomali (pause, contatti doppi) <= 1%", f"{100 * fuori:.1f}%", fuori <= 0.01),
        ("appoggio mediano tra 0.15 e 0.45 s", f"{np.median(appoggi):.2f} s",
         0.15 <= np.median(appoggi) <= 0.45),
        ("cavigliera ferma (gravita' entro 10° dalla media)", f"{spostamento:.1f}°", spostamento <= 10),
    ]

    # Avvisi sull'orientamento; i CSV vecchi non hanno lo stato di calibrazione
    avvisi = []
    if "cal_gyr" in d:
        pitch_min = d.groupby(minuto)["pitch"].median()
        # Lo yaw passa da 360 a 0 normalmente: i salti contano solo su roll e pitch
        salti = (d[["roll", "pitch"]].diff().abs() > 90).sum().sum()
        avvisi = [
            ("giroscopio calibrato (cal_gyr = 3 per >= 90%)", f"{100 * (d['cal_gyr'] == 3).mean():.0f}%",
             (d["cal_gyr"] == 3).mean() >= 0.9),
            ("pitch senza deriva (mediane per minuto entro 10°)", f"{pitch_min.max() - pitch_min.min():.1f}°",
             pitch_min.max() - pitch_min.min() <= 10),
            ("pitch lontano da 90° (|pitch| > 85° per <= 10%)", f"{100 * (d['pitch'].abs() > 85).mean():.0f}%",
             (d["pitch"].abs() > 85).mean() <= 0.1),
            ("nessun salto di roll/pitch (> 90° tra due campioni)", f"{salti}", salti == 0),
        ]

    print(f"\n{percorso} (da {args.da:.0f} s, {len(hs)} contatti, stride mediano {np.median(st):.2f} s)")
    for descrizione, valore, ok in righe:
        print(f"  {'OK  ' if ok else 'NO  '} {descrizione:52s} {valore}")
    for descrizione, valore, ok in avvisi:
        print(f"  {'ok  ' if ok else '!   '} {descrizione:52s} {valore}")
    bocciati = sum(not ok for _, _, ok in righe)
    esito = "PASSA" if bocciati == 0 else f"NON PASSA ({bocciati} controlli falliti)"
    n_avvisi = sum(not ok for _, _, ok in avvisi)
    print(f"  -> {esito}" + (f", {n_avvisi} avvisi sull'orientamento" if n_avvisi else ""))


for percorso in args.file:
    controlla(percorso)
