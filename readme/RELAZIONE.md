# Cavigliera IMU + sensore di forza – relazione del lavoro svolto

Aggiornata al 22/10/2026.

## 1. Obiettivo

Il progetto (dal tema del professore) consiste nel rilevare l'istante in cui il
tallone tocca il suolo durante la camminata (*heel-strike*) usando un'IMU
posizionata alla caviglia. Il sensore di pressione (FSR) sotto il tallone
fornisce il riferimento ("ground truth") per sapere quando il contatto avviene
davvero. Sul segnale IMU verranno poi confrontati due metodi:

- un rilevatore classico a soglia (baseline della letteratura);
- una rete neurale a impulsi (SNN, con snnTorch).

Finora ho svolto la parte di **acquisizione dati**: firmware sulla scheda,
salvataggio in CSV, prime registrazioni e grafici di controllo.

## 2. Hardware

| Componente | Modello | Collegamento |
|---|---|---|
| Microcontrollore | Adafruit QT Py RP2040 | USB al PC |
| IMU | Bosch BNO055 (accelerometro, giroscopio, magnetometro + fusione a bordo) | I2C `Wire1` (connettore STEMMA QT), indirizzo 0x28 |
| ADC esterno | ADS1115 (16 bit) | I2C `Wire1`, indirizzo 0x48 |
| Sensore di forza | FSR sotto il tallone | canale 0 dell'ADS1115 |

## 3. Struttura dei file

```
heel_strike/
├── cavigliera/cavigliera.ino   firmware definitivo (IMU + forza)
├── pc/
│   ├── cavigliera_logger.py    legge la seriale e salva il CSV
│   ├── grafici.py              grafici di controllo dai CSV
│   ├── dati/                   CSV registrati (non vanno su git)
│   └── grafici/                immagini prodotte da grafici.py
├── readme/
│   ├── RELAZIONE.md            questo file
│   └── SPIEGAZIONE_CODICE.md   spiegazione semplice del codice
└── .venv/                      librerie Python (matplotlib, pandas, pyserial; non va su git)
```

## 4. Firmware (`cavigliera/cavigliera.ino`)

È il programma che gira sulla scheda: il "firmware" del punto 2 del tema.

**Cosa fa:**

1. All'avvio inizializza il BNO055 (modalità di fusione NDOF, quarzo esterno)
   e l'ADS1115. Se un sensore non risponde, stampa un messaggio di errore che
   inizia con `#`.
2. Ogni **20 ms (50 Hz)** legge tutti i sensori e manda **una riga di testo**
   sulla seriale USB, con i valori separati da virgole:

```
tempo_ms,yaw,roll,pitch,acc_x,acc_y,acc_z,gyr_x,gyr_y,gyr_z,forza_V
```

| Colonna | Significato | Unità |
|---|---|---|
| `tempo_ms` | millisecondi dall'accensione della scheda | ms |
| `yaw, roll, pitch` | angoli di Eulero calcolati dal BNO055 (yaw 0–360°) | gradi |
| `acc_x/y/z` | accelerazione sugli assi del sensore, gravità inclusa | m/s² |
| `gyr_x/y/z` | velocità angolare sugli assi del sensore | °/s |
| `forza_V` | tensione dell'FSR (0 V = tallone sollevato, ~3.1 V = appoggiato) | V |

**Scelte adottate:**

- **Lettura sincrona:** IMU e forza sono letti nello stesso ciclo e scritti
  nella stessa riga con lo stesso timestamp. Così la forza può fare da
  riferimento temporale per l'IMU senza problemi di allineamento.
- **Periodo fisso, non `delay()`:** il ciclo parte ogni 20 ms esatti, contati
  con `millis()`. Con `delay()` il tempo di lettura dei sensori si sommerebbe
  alla pausa e l'intervallo non sarebbe costante. Nelle prove tutte le righe
  sono arrivate esattamente ogni 20 ms.
- **50 Hz invece di 100 Hz:** a 10 ms la scheda non riusciva a stare dietro
  (le righe arrivavano ogni 13–15 ms, in modo irregolare). 50 Hz è costante e
  dà una risoluzione di 20 ms. A 10 Hz (`delay(100)`, come nell'esempio visto
  sul Serial Monitor) la risoluzione sarebbe stata 100 ms, troppo grossolana
  per trovare l'istante del contatto. Dai dati a 50 Hz si possono sempre
  ricavare frequenze più basse; il contrario non è possibile.
- **Giroscopio sugli assi del sensore:** in una prima versione era ruotato nel
  sistema di riferimento della terra usando l'orientamento stimato dal
  BNO055. Così il segnale del passo si mescolava sui tre assi e risentiva degli
  errori di stima. Sugli assi del sensore invece il pattern di ogni passo è
  chiaro e ripetibile (vedi sezione 7), ed è quello usato in letteratura.
- **Accelerazione con gravità:** è il dato grezzo dell'accelerometro. Quella
  senza gravità dipende dalla stima dell'orientamento del BNO055; se servirà,
  si potrà ricavare dopo.
- **Forza in volt:** l'ADS1115 converte direttamente in volt
  (`computeVolts`), con guadagno ±4.096 V (adatto a un segnale 0–3.3 V) e alla
  velocità massima di 860 campioni/s, per non rallentare il ciclo.
- **ADS1115 o pin A0:** in cima allo sketch `#define USA_ADS1115 1` sceglie
  l'ADS1115. Con `0` la forza si legge dal pin A0 della QT Py (ADC a 12 bit,
  convertito in volt).

## 5. Logger Python (`pc/cavigliera_logger.py`)

Legge le righe dalla seriale e le salva in un CSV.

**Uso** (dalla cartella `pc/`, con il Serial Monitor dell'Arduino IDE chiuso):

```bash
python3 cavigliera_logger.py normale              # 10 minuti (default)
python3 cavigliera_logger.py veloce --minuti 1    # prova breve
python3 cavigliera_logger.py scale --porta /dev/ttyACM1
```

**Funzionamento e scelte:**

- **Un file nuovo per ogni prova:** il nome contiene stile, data e ora, es.
  `dati/normale_2026-10-23_15-30-12.csv`. Così una prova non sovrascrive mai
  quelle precedenti.
- **Colonna `stile`:** viene aggiunta in fondo a ogni riga. È ridondante
  rispetto al nome del file, ma serve quando i file vengono uniti per
  addestrare la rete.
- **Arresto automatico:** si ferma da solo dopo la durata scelta. Il tempo è
  misurato con il `tempo_ms` della scheda, non con l'orologio del PC.
  Con Ctrl+C ci si ferma prima, e le righe già registrate restano salvate.
- **Controllo delle righe:** vengono scartate le righe incomplete o non
  numeriche (per esempio quelle spezzate all'apertura della porta). Le righe
  che iniziano con `#` sono messaggi della scheda e vengono solo stampate.
- **Primo mezzo secondo:** all'inizio il BNO055 manda per circa 25 righe
  tutti i valori IMU a zero. Queste righe vengono scartate.
- **Salvataggio periodico:** il file viene scritto su disco ogni 250 righe
  (circa 5 s). Un aggiornamento a terminale mostra il tempo mancante e il
  valore della forza.

## 6. Grafici (`pc/grafici.py`)

```bash
python3 grafici.py dati/normale.csv
python3 grafici.py dati/normale.csv dati/veloce.csv dati/scale.csv
python3 grafici.py dati/normale.csv --da 300 --durata 20 --soglia 0.5 --picco 2.0
```

### Rilevamento del contatto dalla forza (bozza di ground truth)

Un contatto del tallone è l'istante in cui `forza_V` **supera 0.5 V salendo**.
Il tratto sopra soglia conta come passo solo se la forza arriva ad **almeno
2 V**: nella prima prova c'erano piccoli tocchi intorno a 1 V (piede
appoggiato di lato o in curva) che non erano passi veri. L'istante viene
interpolato linearmente tra i due campioni a cavallo della soglia, per avere
una precisione migliore dei 20 ms del campionamento.

### Grafici prodotti (cartella `pc/grafici/`)

| File | Asse x | Asse y | A cosa serve |
|---|---|---|---|
| `<nome>_segnali.png` | tempo (s), 20 s di default | forza (V), modulo dell'accelerazione \|acc\| (m/s²), giroscopio sui 3 assi (°/s) | verifica visiva: le linee verticali (contatti trovati) devono cadere sul fronte di salita della forza |
| `<nome>_dt.png` | intervallo tra righe consecutive (ms) | numero di righe | controlla che il campionamento sia regolare (un'unica barra a 20 ms) |
| `<nome>_intorno_contatto.png` | tempo relativo al contatto, da −200 a +200 ms | \|acc\|, gyr_x, gyr_y, gyr_z | sovrappone tutti i contatti (grigio) e la loro media (blu): mostra la forma tipica del segnale IMU al contatto |
| `durata_passo.png` | file | tempo tra due contatti successivi dello stesso piede (s) | boxplot: confronta le velocità di cammino |

Il grafico nel tempo mostra solo 20 s per leggibilità: 10 minuti sono circa
300 passi e in un'unica immagine non si distinguerebbero. Tutti gli altri
grafici usano l'intera registrazione.

## 7. Risultati della prova di test (60 s, camminata normale)

- **Campionamento:** 2975 righe valide, tutte a 20 ms esatti.
- **Forza:** segnale "a gradini" pulito (0 V ↔ ~3.1 V), **41 contatti**
  trovati, tutti corrispondenti a passi veri.
- **Durata del passo:** mediana **1.37 s** (quasi tutti tra 1.3 e 1.45 s). I
  pochi valori tra 1.65 e 1.85 s sono probabilmente curve o rallentamenti.
- **IMU intorno al contatto:** le 41 curve si sovrappongono bene, quindi il
  segnale è ripetibile.
  - **\|acc\|:** piatto prima del contatto, poi un picco netto a circa **+90 ms**
    (fino a 20–27 m/s²).
  - **gyr_x e gyr_z:** rampa regolare da negativo a positivo che passa per zero
    vicino all'istante del contatto. È la rotazione della gamba, che si
    divide fra i due assi probabilmente perché la cavigliera è montata
    leggermente di sbieco.
  - **gyr_y:** oscillazione rapida, minimo a circa +75 ms e massimo a circa
    +110 ms (vibrazione d'impatto). Insieme a \|acc\| è il segnale più "a
    impulso", quindi un buon candidato per l'encoding a spike.
- **Punto aperto:** i picchi IMU arrivano circa **75–100 ms dopo** il
  superamento della soglia di forza. Può dipendere dall'FSR (che si attiva
  prima dell'impatto vero) o da un ritardo dell'IMU. Test proposto: da fermo,
  4–5 colpi secchi di tallone sul pavimento. Se il ritardo resta, è dovuto ai
  sensori; se sparisce, dipende dal modo di camminare.

Una prima prova (più lenta, con curve e pause) aveva un passo di circa 1.95 s
e diversi falsi contatti: da lì sono nati il filtro sul picco minimo di 2 V e
il consiglio di camminare in un corridoio lungo.

## 8. Protocollo di registrazione proposto

1. Cavigliera sempre sulla stessa gamba, nella stessa posizione e con lo
   stesso orientamento (segnarli o fotografarli). FSR sotto il tallone.
2. Calibrazione del BNO055 prima di ogni sessione: qualche secondo da fermo,
   poi rotazioni della caviglia in varie direzioni.
3. Percorso: corridoio lungo e rettilineo, al passo naturale per lo stile
   richiesto, con poche curve.
4. 10 minuti per stile; ogni prova finisce in un file a parte.
5. Annotare soggetto, data, scarpe e luogo.
6. Controllo subito dopo ogni registrazione con `grafici.py`.

## 9. Domande per il professore

**Protocollo**

1. Quali condizioni registrare: **lenta / normale / veloce**, come nel tema,
   oppure normale / veloce / **scale**? Le scale vanno aggiunte come quarta
   condizione o escluse?
2. 10 minuti per condizione vanno bene? Basta una sessione, o ne servono più
   (anche in giorni diversi)?
3. Un solo soggetto (io) o più persone? Se più persone, quante?
4. Su quale gamba va la cavigliera, e in che posizione e orientamento esatti?
   È previsto un solo FSR sotto il tallone, o anche altri punti (avampiede)?
5. Le curve e le pause vanno evitate, o tagliate dopo dai dati?

**Hardware e firmware**

6. Il tema parla di **ESP32**: devo passare a quella scheda o va bene la QT Py
   RP2040? Con l'ESP32 conviene trasmettere i dati senza fili (WiFi/Bluetooth)
   invece che via cavo USB?
7. La frequenza di 50 Hz è sufficiente, o serve 100 Hz o più? Per salire
   bisognerebbe ottimizzare la lettura I2C.
8. Servono gli angoli di Eulero (lo yaw dipende dal magnetometro e può
   derivare) o bastano accelerometro e giroscopio grezzi? Serve anche
   l'accelerazione senza gravità?
9. L'FSR satura a circa 3.1 V. Va bene così (interessa solo l'istante del
   contatto) o serve una misura di forza in Newton, con un partitore diverso
   o una calibrazione?

**Ground truth e valutazione**

10. Il criterio per il contatto (forza che supera 0.5 V salendo, con picco
    almeno 2 V, istante interpolato) è accettabile, o c'è un criterio standard
    da usare?
11. Come gestire il ritardo di circa 80 ms tra FSR e picchi IMU? Va corretto,
    o fa parte di ciò che i metodi devono imparare?
12. Che finestra di tolleranza usare per precision/recall a livello di
    evento (es. ±25 ms, ±50 ms)?

**Encoding e SNN**

13. Quali segnali usare come ingresso: tutti gli assi, solo \|acc\| e un asse
    del giroscopio, o anche gli angoli?
14. Quali schemi di encoding confrontare (es. rate coding, delta/
    threshold-crossing coding, latency coding)?
15. Quale soglia classica della letteratura prendere come baseline? C'è un
    articolo di riferimento?
16. La SNN deve girare solo su PC, o in futuro anche su hardware embedded o
    neuromorfico?
