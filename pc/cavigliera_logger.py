# =====================================================================
# CAVIGLIERA LOGGER: legge i dati della cavigliera dalla USB e li salva in CSV
# =====================================================================
#
# La scheda (sketch cavigliera.ino) manda 50 righe al secondo del tipo:
#   12034,183.25,-2.10,15.44,0.512,-1.204,9.731,1.2,-0.4,0.3,0.842
# Questo programma le legge, controlla che siano valide e le scrive in
# dati/<stile>_<data>_<ora>.csv, aggiungendo in fondo a ogni riga lo stile
# di camminata.
#
# Uso (dalla cartella pc/, con il Serial Monitor dell'Arduino IDE CHIUSO,
# perche' la porta USB puo' essere usata da un solo programma alla volta):
#   python3 cavigliera_logger.py normale              -> 10 minuti
#   python3 cavigliera_logger.py veloce --minuti 1    -> prova di 1 minuto
#   python3 cavigliera_logger.py scale --porta /dev/ttyACM1

import argparse   # per leggere gli argomenti scritti sulla riga di comando
import os         # per creare cartelle e comporre il percorso del file
import time       # per le pause
from datetime import datetime  # per mettere data e ora nel nome del file

import serial     # libreria pyserial: comunicazione con la porta seriale/USB

# Stili di camminata ammessi. Se si scrive un nome diverso, il programma
# da' errore (cosi' non si creano file con nomi sbagliati per un errore
# di battitura).
STILI = ["normale", "veloce", "scale"]

# Nomi delle colonne, nello STESSO ORDINE in cui la scheda manda i valori.
# La colonna "stile" non arriva dalla scheda: la aggiunge questo programma.
COLONNE = [
    "tempo_ms",
    "yaw", "roll", "pitch",
    "acc_x", "acc_y", "acc_z",
    "gyr_x", "gyr_y", "gyr_z",
    "forza_V",
]

# ---------------------------------------------------------------------
# 1. ARGOMENTI DELLA RIGA DI COMANDO
# ---------------------------------------------------------------------
# "stile" e' obbligatorio; --minuti e --porta sono facoltativi e hanno
# un valore di default. python3 cavigliera_logger.py --help li elenca.
parser = argparse.ArgumentParser(description="Registra una prova della cavigliera in CSV")
parser.add_argument("stile", choices=STILI, help="tipo di camminata")
parser.add_argument("--minuti", type=float, default=10, help="durata della prova (default 10)")
parser.add_argument("--porta", default="/dev/ttyACM0")  # porta USB della scheda su Linux
args = parser.parse_args()

# ---------------------------------------------------------------------
# 2. FILE DI DESTINAZIONE
# ---------------------------------------------------------------------
# Un file nuovo per ogni prova, con data e ora nel nome, es.
#   dati/normale_2026-10-23_15-30-12.csv
# Cosi' una prova non sovrascrive mai quelle precedenti.
os.makedirs("dati", exist_ok=True)  # crea la cartella dati/ se non c'e' (se c'e' non fa niente)
adesso = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
nome_file = os.path.join("dati", f"{args.stile}_{adesso}.csv")

# ---------------------------------------------------------------------
# 3. APERTURA DELLA PORTA SERIALE E DEL FILE
# ---------------------------------------------------------------------
# 115200 = velocita', uguale a Serial.begin(115200) nello sketch.
# timeout=1: se per 1 secondo non arriva niente, readline() non resta
# bloccato per sempre ma restituisce una riga vuota.
porta = serial.Serial(args.porta, 115200, timeout=1)
time.sleep(0.5)
# Butta via tutto quello che era gia' arrivato prima di adesso: di solito
# c'e' un pezzo di riga a meta', che non avrebbe senso salvare.
porta.reset_input_buffer()

# Apre il file in scrittura ("w" = cancella il contenuto precedente)
# e scrive la prima riga con i nomi delle colonne (l'intestazione).
file = open(nome_file, "w")
file.write(",".join(COLONNE + ["stile"]) + "\n")

# Durata della prova convertita in millisecondi (es. 10 min -> 600000 ms).
durata_ms = args.minuti * 60 * 1000
print(f"Stile: {args.stile} | durata: {args.minuti} min | file: {nome_file}")
print("Registrazione iniziata (Ctrl+C per fermare prima)")

# ---------------------------------------------------------------------
# 4. CICLO DI LETTURA: una riga alla volta finche' non scade il tempo
# ---------------------------------------------------------------------
n = 0          # quante righe sono state salvate
inizio = None  # tempo_ms della prima riga valida (ancora sconosciuto)
try:
    while True:
        # Legge una riga dalla USB (fino all'"a capo"). Arriva come byte:
        # decode() la trasforma in testo, strip() toglie spazi e "a capo".
        # errors="ignore" salta eventuali caratteri rovinati.
        riga = porta.readline().decode(errors="ignore").strip()

        # Riga vuota (es. timeout): passa alla prossima.
        if not riga:
            continue

        # Le righe che iniziano con "#" sono messaggi della scheda
        # ("# pronto", "# ERRORE: ..."): le mostro ma non le salvo.
        if riga.startswith("#"):
            print(riga)
            continue

        # Divide la riga nei singoli valori usando la virgola.
        valori = riga.split(",")

        # Controllo 1: il numero di valori deve essere giusto (11).
        # Se no, la riga e' spezzata o rovinata e la scarto.
        if len(valori) != len(COLONNE):
            print("riga ignorata:", repr(riga))
            continue

        # Controllo 2: ogni valore deve essere un numero.
        # float() da' errore (ValueError) se il testo non e' un numero.
        try:
            [float(v) for v in valori]
        except ValueError:
            print("riga ignorata:", repr(riga))
            continue

        # Controllo 3: nel primo mezzo secondo il BNO055 non e' ancora
        # pronto e manda tutti i valori IMU a zero (colonne da 1 a 9).
        # Finche' la registrazione non e' iniziata, quelle righe si saltano.
        if inizio is None and all(float(v) == 0 for v in valori[1:10]):
            continue

        # Quanto tempo e' passato dall'inizio della prova.
        # Uso il tempo della scheda (colonna tempo_ms) e non l'orologio del
        # PC, cosi' la durata corrisponde esattamente ai dati salvati.
        t = float(valori[0])
        if inizio is None:
            inizio = t  # la prima riga valida segna l'inizio
        trascorso = t - inizio

        # Se e' passata la durata richiesta, esce dal ciclo.
        if trascorso >= durata_ms:
            print("Tempo scaduto.")
            break

        # Salva la riga cosi' com'e', con lo stile aggiunto in fondo.
        file.write(f"{riga},{args.stile}\n")
        n += 1

        # Ogni 250 righe (circa 5 secondi a 50 Hz):
        # - stampa a terminale quanto manca e il valore della forza, per
        #   controllare che tutto funzioni (stampare ogni riga rallenterebbe);
        # - flush() scrive davvero su disco quello che e' in memoria, cosi'
        #   se qualcosa si blocca si perdono al massimo pochi secondi.
        if n % 250 == 0:
            mancano = (durata_ms - trascorso) / 1000  # secondi mancanti
            print(f"{n} righe | mancano {mancano // 60:.0f} min {mancano % 60:.0f} s"
                  f" | forza {valori[10]} V")
            file.flush()

# Ctrl+C non fa crashare il programma: esce dal ciclo e arriva qui,
# poi prosegue con il salvataggio qui sotto.
except KeyboardInterrupt:
    print("Interrotto a mano.")

# ---------------------------------------------------------------------
# 5. CHIUSURA
# ---------------------------------------------------------------------
# Chiudere il file garantisce che tutte le righe siano scritte su disco;
# chiudere la porta la libera per altri programmi (es. Serial Monitor).
print(n, "righe salvate in", nome_file)
file.close()
porta.close()
