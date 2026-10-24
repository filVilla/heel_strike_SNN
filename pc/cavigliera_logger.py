# Legge i dati della cavigliera dalla USB e li salva in dati/<stile>_<data>_<ora>.csv
# Uso: python3 cavigliera_logger.py normale [--minuti 1] [--porta /dev/ttyACM0]

import argparse
import os
import time
from datetime import datetime

import serial

STILI = ["normale", "veloce", "scale"]

# Stesso ordine dei valori mandati dalla scheda
COLONNE = [
    "tempo_ms",
    "yaw", "roll", "pitch",
    "acc_x", "acc_y", "acc_z",
    "gyr_x", "gyr_y", "gyr_z",
    "forza_V",
]

parser = argparse.ArgumentParser(description="Registra una prova della cavigliera in CSV")
parser.add_argument("stile", choices=STILI, help="tipo di camminata")
parser.add_argument("--minuti", type=float, default=10, help="durata della prova (default 10)")
parser.add_argument("--porta", default="/dev/ttyACM0")
args = parser.parse_args()

os.makedirs("dati", exist_ok=True)
adesso = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
nome_file = os.path.join("dati", f"{args.stile}_{adesso}.csv")

porta = serial.Serial(args.porta, 115200, timeout=1)
time.sleep(0.5)
porta.reset_input_buffer()

file = open(nome_file, "w")
file.write(",".join(COLONNE + ["stile"]) + "\n")

durata_ms = args.minuti * 60 * 1000
print(f"Stile: {args.stile} | durata: {args.minuti} min | file: {nome_file}")
print("Registrazione iniziata (Ctrl+C per fermare prima)")

n = 0
inizio = None
try:
    while True:
        riga = porta.readline().decode(errors="ignore").strip()

        if not riga:
            continue

        # Messaggi della scheda
        if riga.startswith("#"):
            print(riga)
            continue

        valori = riga.split(",")

        if len(valori) != len(COLONNE):
            print("riga ignorata:", repr(riga))
            continue

        try:
            [float(v) for v in valori]
        except ValueError:
            print("riga ignorata:", repr(riga))
            continue

        # BNO055 non ancora pronto: IMU tutto a zero
        if inizio is None and all(float(v) == 0 for v in valori[1:10]):
            continue

        t = float(valori[0])
        if inizio is None:
            inizio = t
        trascorso = t - inizio

        if trascorso >= durata_ms:
            print("Tempo scaduto.")
            break

        file.write(f"{riga},{args.stile}\n")
        n += 1

        # Ogni ~5 s
        if n % 250 == 0:
            mancano = (durata_ms - trascorso) / 1000
            print(f"{n} righe | mancano {mancano // 60:.0f} min {mancano % 60:.0f} s"
                  f" | forza {valori[10]} V")
            file.flush()

except KeyboardInterrupt:
    print("Interrotto a mano.")

print(n, "righe salvate in", nome_file)
file.close()
porta.close()
