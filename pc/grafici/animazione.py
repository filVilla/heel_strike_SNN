# ANIMAZIONE 3D DELLA CAVIGLIERA
# Cosa fa: crea un video (grafici/<nome>/animazione_3d.mp4) con un blocco 3D che ruota come il sensore,
#          arancio quando il tallone e' a terra, accanto ai grafici di forza e angoli. Usa il quaternione
#          del BNO055 (o gli angoli di Eulero nei CSV vecchi), verificato confrontandolo con il giroscopio.

# Uso: python3 animazione.py dati/normale.csv [--da 60 --durata 10 --rallenta 1]

import argparse
import os
import shutil

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.animation import FFMpegWriter, FuncAnimation
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

BLU, ARANCIO, ACQUA = "#2a78d6", "#eb6834", "#1baf7a"
GRIGIO, GRIGIO_CHIARO = "#52514e", "#c3c2b7"

parser = argparse.ArgumentParser(description="Animazione 3D dell'orientamento della cavigliera")
parser.add_argument("file", help="CSV registrato con cavigliera_logger.py")
parser.add_argument("--da", type=float, default=60, help="secondo di inizio (default 60)")
parser.add_argument("--durata", type=float, default=10, help="secondi animati (default 10)")
parser.add_argument("--rallenta", type=float, default=1, help="fattore di rallentamento (default 1 = tempo reale)")
parser.add_argument("--fps", type=int, default=25, help="fotogrammi al secondo del video (default 25)")
parser.add_argument("--soglia", type=float, default=0.5, help="soglia FSR in volt per il contatto (default 0.5)")
args = parser.parse_args()

plt.rcParams.update({
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": GRIGIO, "axes.labelcolor": GRIGIO,
    "xtick.color": GRIGIO, "ytick.color": GRIGIO,
    "axes.grid": True, "grid.color": "#e8e7e3", "grid.linewidth": 0.8,
    "lines.linewidth": 1.5, "figure.dpi": 100,
})


def rot(asse, a):
    """Matrici di rotazione (N, 3, 3) attorno a un asse, angoli in radianti."""
    c, s, z, u = np.cos(a), np.sin(a), np.zeros_like(a), np.ones_like(a)
    if asse == "x":
        m = [[u, z, z], [z, c, -s], [z, s, c]]
    elif asse == "y":
        m = [[c, z, s], [z, u, z], [-s, z, c]]
    else:
        m = [[c, -s, z], [s, c, z], [z, z, u]]
    return np.moveaxis(np.array(m), [0, 1], [-2, -1])


def orientamento(d, segno_yaw):
    """Rotazione sensore -> mondo: yaw attorno a z, roll attorno a y, pitch attorno a x.
    Convenzione ricavata confrontando la rotazione con il giroscopio; il verso dello yaw
    viene scelto per ogni file con verifica()."""
    y, r, p = (np.radians(d[c].to_numpy()) for c in ["yaw", "roll", "pitch"])
    return rot("z", segno_yaw * y) @ rot("y", -r) @ rot("x", -p)


def da_quaternione(q):
    """Matrici di rotazione (N, 3, 3) da quaternioni (N, 4) nell'ordine (w, x, y, z)."""
    w, x, y, z = (q / np.linalg.norm(q, axis=1, keepdims=True)).T
    m = [[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
         [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
         [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]]
    return np.moveaxis(np.array(m), [0, 1], [-2, -1])


def a_quaternione(R):
    """Quaternioni (w, x, y, z) da matrici di rotazione (N, 3, 3): autovettore della matrice K
    di Bar-Itzhack, stabile anche per rotazioni vicine a 180°."""
    r = R.reshape(-1, 9).T
    xx, xy, xz, yx, yy, yz, zx, zy, zz = r
    K = np.array([[xx - yy - zz, yx + xy, zx + xz, zy - yz],
                  [yx + xy, yy - xx - zz, zy + yz, xz - zx],
                  [zx + xz, zy + yz, zz - xx - yy, yx - xy],
                  [zy - yz, xz - zx, yx - xy, xx + yy + zz]]) / 3
    _, v = np.linalg.eigh(np.moveaxis(K, [0, 1], [-2, -1]))
    x, y, z, w = v[:, :, -1].T
    return np.stack([w, x, y, z], 1)


def slerp(q, t, tf):
    """Quaternioni agli istanti tf, interpolati sul tratto piu' corto tra i campioni vicini."""
    q = q.copy()
    for i in range(1, len(q)):  # stesso emisfero del precedente: q e -q sono la stessa rotazione
        if q[i] @ q[i - 1] < 0:
            q[i] = -q[i]
    i0 = np.searchsorted(t, tf, side="right") - 1
    i1 = np.minimum(i0 + 1, len(t) - 1)
    passo = t[i1] - t[i0]
    u = np.where(passo > 0, (tf - t[i0]) / np.where(passo > 0, passo, 1), 0)[:, None]
    a, b = q[i0], q[i1]
    angolo = np.arccos(np.clip(np.sum(a * b, axis=1), -1, 1))[:, None]
    s = np.sin(angolo)
    piccolo = s < 1e-6  # campioni quasi uguali: basta l'interpolazione lineare
    sicuro = np.where(piccolo, 1, s)
    ka = np.where(piccolo, 1 - u, np.sin((1 - u) * angolo) / sicuro)
    kb = np.where(piccolo, u, np.sin(u * angolo) / sicuro)
    return ka * a + kb * b, i0


def verifica(R, d):
    """Velocita' angolare (°/s, assi del sensore) ricavata dalle rotazioni successive, confrontata
    con il giroscopio. Restituisce l'errore mediano e la correlazione per asse."""
    D = np.einsum("nji,njk->nik", R[:-1], R[1:])
    dt = np.diff(d["tempo_ms"].to_numpy()) / 1000
    w = np.stack([D[:, 2, 1] - D[:, 1, 2], D[:, 0, 2] - D[:, 2, 0], D[:, 1, 0] - D[:, 0, 1]], 1)
    w = np.degrees(w / 2 / dt[:, None])
    g = d[["gyr_x", "gyr_y", "gyr_z"]].to_numpy()
    g = (g[1:] + g[:-1]) / 2
    errore = np.median(np.linalg.norm(w - g, axis=1))
    return errore, [np.corrcoef(w[:, i], g[:, i])[0, 1] for i in range(3)]


d = pd.read_csv(args.file)
imu = ["yaw", "roll", "pitch", "acc_x", "acc_y", "acc_z", "gyr_x", "gyr_y", "gyr_z"]
d = d[~(d[imu] == 0).all(axis=1)].reset_index(drop=True)
d["t"] = (d["tempo_ms"] - d["tempo_ms"].iloc[0]) / 1000
d = d[(d.t >= args.da) & (d.t <= args.da + args.durata)].reset_index(drop=True)
nome = os.path.splitext(os.path.basename(args.file))[0]

# Rotazioni candidate: il quaternione se il CSV lo contiene (firmware nuovo), altrimenti gli angoli
# di Eulero con i due versi dello yaw. Si tiene quella che somiglia di piu' al giroscopio.
candidati = {"Eulero, yaw +1": orientamento(d, 1), "Eulero, yaw -1": orientamento(d, -1)}
if "q_w" in d:
    Rq = da_quaternione(d[["q_w", "q_x", "q_y", "q_z"]].to_numpy())
    candidati = {"quaternione": Rq, "quaternione inverso": np.swapaxes(Rq, 1, 2)}
prove = {k: verifica(R, d) for k, R in candidati.items()}
scelta = min(prove, key=lambda k: prove[k][0])
errore, corr = prove[scelta]
g_mediana = np.median(np.linalg.norm(d[["gyr_x", "gyr_y", "gyr_z"]], axis=1))
print(f"{nome}: {scelta}, errore mediano rispetto al giroscopio {errore:.0f} °/s "
      f"(giroscopio mediano {g_mediana:.0f} °/s), correlazione x/y/z "
      + " / ".join(f"{c:.2f}" for c in corr))

# Toglie la direzione media (riferita al nord magnetico, non per forza quella di marcia), usando
# l'asse del sensore che in media resta piu' orizzontale
R = candidati[scelta]
k = np.argmin(np.abs(R[:, 2, :]).mean(axis=0))
yaw0 = np.angle(np.mean(R[:, 0, k] + 1j * R[:, 1, k]))
R = rot("z", np.full(len(d), -yaw0)) @ R

# Un orientamento per fotogramma, interpolato (slerp) tra i due campioni vicini; forza e
# angoli mostrati sono quelli dell'ultimo campione
t = d.t.to_numpy()
tf = np.arange(t[0], t[-1], 1 / (args.fps * args.rallenta))
Qf, idx = slerp(a_quaternione(R), t, tf)
Rf = da_quaternione(Qf)

# Parallelepipedo nel sistema del sensore (lati lungo x, y, z) e assi del sensore
lati = np.array([1.5, 1.0, 0.3])
vertici = np.array([[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]) * lati
facce = [[0, 1, 3, 2], [4, 5, 7, 6], [0, 1, 5, 4], [2, 3, 7, 6], [0, 2, 6, 4], [1, 3, 7, 5]]
assi = np.eye(3) * 2.2

fig = plt.figure(figsize=(11, 5.5))
ax3 = fig.add_subplot(1, 2, 1, projection="3d")
axf = fig.add_subplot(2, 2, 2)
axa = fig.add_subplot(2, 2, 4, sharex=axf)

ax3.set_xlim(-2.5, 2.5)
ax3.set_ylim(-2.5, 2.5)
ax3.set_zlim(-2.5, 2.5)
ax3.set_box_aspect((1, 1, 1))
ax3.set_xticklabels([])
ax3.set_yticklabels([])
ax3.set_zticklabels([])
scatola = Poly3DCollection([], edgecolor=GRIGIO, linewidth=0.8, alpha=0.85)
ax3.add_collection3d(scatola)
linee_assi = [ax3.plot([], [], [], color=c, linewidth=2.5, label=f"asse {n} ")[0]
              for c, n in zip([BLU, ARANCIO, ACQUA], "xyz")]
scia, = ax3.plot([], [], [], color=GRIGIO_CHIARO, linewidth=1)
ax3.legend(loc="upper left", frameon=False, fontsize=8)

axf.plot(t, d.forza_V, color=BLU)
axf.axhline(args.soglia, color=GRIGIO, linestyle="--", linewidth=1)
axf.set_ylabel("forza (V)")
yaw_rad = np.radians(d.yaw)
yaw_rel = np.degrees(np.angle(np.exp(1j * (yaw_rad - np.angle(np.mean(np.exp(1j * yaw_rad)))))))
for v, c, n in zip([yaw_rel, d.roll, d.pitch], [BLU, ARANCIO, ACQUA], ["yaw (relativo)", "roll", "pitch"]):
    axa.plot(t, v, color=c, label=n)
axa.set_ylabel("angoli (°)")
axa.set_xlabel("tempo (s)")
axa.legend(loc="lower left", bbox_to_anchor=(0, 1), frameon=False, ncol=3, fontsize=8)
cursori = [a.axvline(t[0], color=GRIGIO, linewidth=1) for a in (axf, axa)]
titolo = fig.suptitle("", x=0.02, ha="left", fontsize=11)
fig.tight_layout()

punte = (Rf @ assi[:, 0])  # punta dell'asse x del sensore, per la scia
fotogrammi_al_secondo = int(args.fps * args.rallenta)


def disegna(k):
    i = idx[k]
    v = vertici @ Rf[k].T
    scatola.set_verts([v[f] for f in facce])
    scatola.set_facecolor(ARANCIO if d.forza_V[i] >= args.soglia else GRIGIO_CHIARO)
    for linea, a in zip(linee_assi, (Rf[k] @ assi).T):
        linea.set_data_3d([0, a[0]], [0, a[1]], [0, a[2]])
    j = max(0, k - fotogrammi_al_secondo)  # scia dell'ultimo secondo
    scia.set_data_3d(punte[j:k + 1, 0], punte[j:k + 1, 1], punte[j:k + 1, 2])
    for c in cursori:
        c.set_xdata([t[i], t[i]])
    stato = "tallone a terra" if d.forza_V[i] >= args.soglia else "tallone sollevato"
    titolo.set_text(f"camminata {d.stile[i]}   {stato}")
    return [scatola, scia, titolo, *linee_assi, *cursori]


os.makedirs(os.path.join("grafici", nome), exist_ok=True)
uscita = os.path.join("grafici", nome, "animazione_3d.mp4")
anim = FuncAnimation(fig, disegna, frames=len(idx), blit=False)
if shutil.which("ffmpeg") is None:
    import imageio_ffmpeg
    plt.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()
anim.save(uscita, writer=FFMpegWriter(fps=args.fps, codec="libx264", extra_args=["-pix_fmt", "yuv420p"]))
print("Animazione salvata in", os.path.abspath(uscita))
