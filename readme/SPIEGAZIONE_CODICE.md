# Come funziona il codice – spiegazione semplice

Questo file spiega, in parole semplici, il codice scritto finora e perché è
stato fatto in un certo modo. Per i risultati delle prove e le domande aperte
vedi `RELAZIONE.md`.

## 1. L'idea in breve

Una cavigliera registra il movimento della gamba (con l'IMU) e, nello stesso
momento, quanto il tallone preme a terra (con il sensore di forza). Tutti i
dati finiscono in un file CSV sul PC, che poi si controlla con dei grafici.

Il percorso dei dati è questo:

```
sensori ──> scheda QT Py ──USB──> cavigliera_logger.py ──> file CSV ──> grafici.py ──> immagini PNG
```

I programmi sono tre:

| File | Dove gira | Cosa fa |
|---|---|---|
| `cavigliera/cavigliera.ino` | sulla scheda | legge i sensori e manda i valori al PC |
| `pc/cavigliera_logger.py` | sul PC | riceve i valori e li salva in un CSV |
| `pc/grafici.py` | sul PC | legge i CSV e disegna i grafici di controllo |

## 2. Il programma sulla scheda (`cavigliera.ino`)

Un programma Arduino ha due parti:

- **`setup()`** viene eseguita una volta sola, quando la scheda si accende;
- **`loop()`** viene ripetuta all'infinito.

### setup(): preparazione

1. Apre la comunicazione USB con il PC (velocità 115200).
2. Aspetta che il PC apra la porta, così non si perdono i primi messaggi.
3. Avvia l'IMU (BNO055). Se non risponde, scrive `# ERRORE: BNO055 non
   trovato` ogni secondo e si ferma lì.
4. Avvia il convertitore ADS1115 che legge il sensore di forza, con lo
   stesso controllo degli errori.
5. Scrive `# pronto`.

### loop(): la lettura, 50 volte al secondo

1. Controlla se sono passati 20 ms dall'ultima lettura. Se no, esce e
   riprova subito.
2. Legge l'ora della scheda in millisecondi (`millis()`).
3. Legge dall'IMU angoli, accelerazione e rotazione (giroscopio).
4. Legge la forza sotto il tallone, già convertita in volt.
5. Manda tutto al PC in **una sola riga**, con i valori separati da virgole:

```
tempo_ms,yaw,roll,pitch,acc_x,acc_y,acc_z,gyr_x,gyr_y,gyr_z,forza_V
```

Le righe che iniziano con `#` sono messaggi, non dati: il PC le riconosce e
non le salva.

## 3. Il programma che salva i dati (`cavigliera_logger.py`)

Si avvia dal terminale indicando lo stile di camminata:

```bash
python3 cavigliera_logger.py normale              # 10 minuti
python3 cavigliera_logger.py veloce --minuti 1    # prova di 1 minuto
```

Cosa fa, passo per passo:

1. **Crea un file nuovo** in `dati/`, con stile, data e ora nel nome
   (es. `dati/normale_2026-10-23_17-24-08.csv`) e ci scrive l'intestazione.
2. **Apre la porta USB** e butta via quello che era già arrivato (di solito
   un pezzo di riga a metà).
3. **Legge una riga alla volta** e la controlla:
   - riga vuota → la salta;
   - riga che inizia con `#` → la stampa a schermo e non la salva;
   - numero di valori sbagliato o valori che non sono numeri → la scarta;
   - IMU tutto a zero all'inizio (il BNO055 non è ancora pronto) → la salta.
4. **Salva la riga buona** aggiungendo in fondo lo stile (`normale`,
   `veloce` o `scale`).
5. **Ogni 250 righe** (circa 5 secondi) stampa quanto manca e il valore della
   forza, e scrive davvero il file su disco.
6. **Si ferma da solo** quando è passato il tempo scelto, oppure con Ctrl+C.
   In entrambi i casi le righe già lette restano salvate.

## 4. Il programma dei grafici (`grafici.py`)

Si avvia passando uno o più CSV:

```bash
python3 grafici.py dati/normale_test2.csv
```

Per ogni file:

1. **Carica il CSV** e scarta le righe con l'IMU tutto a zero.
2. **Calcola due colonne nuove:**
   - `t`, il tempo in secondi da inizio prova;
   - `acc_norma`, la "forza totale" dell'accelerazione, che non dipende da
     come è girata la cavigliera (da fermo vale circa 9.8, la gravità).
3. **Trova i contatti del tallone** dalla forza (funzione `contatti`):
   - un contatto è quando la forza **sale sopra 0.5 V**;
   - conta solo se poi arriva **almeno a 2 V**, così i tocchi leggeri non
     vengono presi per passi;
   - l'istante esatto è stimato tra i due campioni vicini alla soglia, per
     essere più precisi dei 20 ms tra una riga e l'altra.
4. **Disegna i grafici** nella cartella `grafici/`:

| Immagine | Cosa mostra | A cosa serve |
|---|---|---|
| `grafici/<nome>/segnali.png` | forza, accelerazione e giroscopio per 20 s, con una linea verticale a ogni contatto | vedere a occhio che i contatti trovati sono giusti |
| `grafici/<nome>/dt.png` | quanto tempo passa tra una riga e la successiva | controllare che le righe arrivino davvero ogni 20 ms |
| `grafici/<nome>/intorno_contatto.png` | i segnali IMU da 200 ms prima a 200 ms dopo ogni contatto, tutti sovrapposti, più la media | vedere la "forma tipica" del segnale quando il tallone tocca |
| `grafici/<nome>/durata_passo.png` | quanto dura ogni ciclo del passo (stride: da un contatto al successivo dello stesso piede), per ogni file, esclusi i primi 30 s | confrontare prove e velocità diverse |

## 5. Scelte di progettazione

Qui sotto le decisioni principali e il motivo, in breve.

**Sulla scheda**

- **IMU e forza nella stessa riga.** Sono letti nello stesso giro e hanno lo
  stesso orario. Così si sa con certezza cosa faceva la gamba nell'istante in
  cui il tallone ha toccato terra, senza dover allineare due file diversi.
- **50 letture al secondo (ogni 20 ms).** A 100 al secondo la scheda non
  ce la faceva e le righe arrivavano irregolari. A 10 al secondo (come nella
  prima versione) il contatto si sarebbe trovato solo con un errore fino a
  100 ms. 50 Hz è il giusto compromesso: è stabile e abbastanza preciso.
- **Orario fisso invece di `delay()`.** Con `delay(20)` il tempo di lettura
  dei sensori si aggiungerebbe alla pausa e gli intervalli varierebbero. Il
  programma invece si dà un "appuntamento" ogni 20 ms. Nelle prove registrate
  tutte le righe sono arrivate a 20 ms esatti.
- **Dati grezzi dei sensori.** Il giroscopio è misurato sugli assi del
  sensore e l'accelerazione include la gravità. Una prima versione ruotava il
  giroscopio usando l'orientamento stimato dal BNO055, ma il segnale del
  passo veniva più confuso. I dati grezzi sono più puliti e si possono sempre
  elaborare dopo.
- **ADS1115 per la forza, con alternativa.** L'ADS1115 è più preciso
  (16 bit) del pin analogico della scheda (12 bit). È impostato alla
  velocità massima per non rallentare il ciclo. Cambiando `USA_ADS1115` da 1
  a 0 si può leggere la forza dal pin A0, senza riscrivere il codice.
- **Messaggi con `#`.** Errori e avvisi viaggiano sulla stessa USB dei dati,
  ma iniziano con `#`, così il PC li distingue e non li mescola ai dati.
- **Se un sensore manca, la scheda si ferma.** Meglio un errore chiaro che
  una registrazione con dati sbagliati.

**Sul PC (logger)**

- **Un file per ogni prova, con data e ora nel nome.** Nessuna prova
  sovrascrive le precedenti.
- **Colonna `stile` in ogni riga.** Sembra un doppione del nome del file,
  ma serve quando più file verranno uniti per addestrare la rete.
- **Stili ammessi fissi** (`normale`, `veloce`, `scale`). Un errore di
  battitura dà subito errore invece di creare un file con il nome sbagliato.
- **Durata misurata con l'orologio della scheda.** Così 10 minuti di prova
  sono 10 minuti di dati salvati, anche se il PC rallenta.
- **Controllo di ogni riga.** Righe spezzate o rovinate vengono scartate,
  così il CSV si apre sempre senza problemi.
- **Salvataggio ogni 5 secondi.** Se qualcosa si blocca, si perdono al
  massimo pochi secondi di dati.

**Sul PC (grafici)**

- **Soglia a 0.5 V e picco minimo a 2 V.** Il primo valore cattura l'inizio
  del contatto, il secondo è stato aggiunto dopo la prima prova, dove alcuni
  tocchi leggeri (piede di lato, curve) venivano presi per passi.
- **Grafico nel tempo di soli 20 s.** Una prova di 10 minuti ha circa 300
  passi e in un'unica immagine non si vedrebbe nulla. Gli altri grafici usano
  tutta la registrazione.
- **Il nome dei grafici viene dal nome del file.** Così due prove dello
  stesso stile non si sovrascrivono le immagini a vicenda.
- **Codice molto commentato.** Ogni passaggio è spiegato nel codice stesso,
  per poterlo rileggere e modificare facilmente.

## 6. Com'era all'inizio e cosa è cambiato

La prima versione (commit del 1/10/2026) era molto più semplice:

| | Prima versione | Versione attuale |
|---|---|---|
| Sensori | solo IMU | IMU + sensore di forza |
| Dati inviati | tempo + 3 angoli | tempo + angoli, accelerazione, giroscopio, forza |
| Frequenza | 10 al secondo (`delay(100)`) | 50 al secondo, a orario fisso |
| File salvato | sempre `dati.csv`, sovrascritto ogni volta | un file per prova con stile, data e ora |
| Controlli sulle righe | solo il numero di valori | numero di valori, numeri validi, messaggi `#`, righe iniziali a zero |
| Fine registrazione | solo con Ctrl+C | automatica dopo il tempo scelto, o con Ctrl+C |
| Grafici | nessuno | 4 tipi di grafico di controllo |

## 7. Le prove fatte finora

| File | Durata | Contatti trovati | Passo (mediana) | Righe non a 20 ms |
|---|---|---|---|---|
| `dati/normale_test1.csv` | 64.2 s | 36 | 1.36 s | 0 |
| `dati/normale_test2.csv` | 126.3 s | 85 | 1.36 s | 0 |

In tutte le prove il campionamento è stato perfettamente regolare e la durata
del passo è stabile intorno a 1.36 s.


// =====================================================================
// CAVIGLIERA: IMU BNO055 + sensore di forza (FSR) -> righe CSV sulla USB
// =====================================================================
//
// Scheda: Adafruit QT Py RP2040
// Sensori:
//   - BNO055 (IMU): accelerometro + giroscopio + magnetometro, con un
//     processore interno che calcola anche gli angoli di Eulero.
//     Collegato al bus I2C "Wire1" (il connettore STEMMA QT della QT Py).
//   - FSR (sensore di forza) sotto il tallone, letto tramite l'ADS1115,
//     un convertitore analogico-digitale esterno, anche lui su Wire1.
//
// Ogni 20 ms (50 volte al secondo) la scheda legge tutti i sensori e
// manda al PC una riga di testo con i valori separati da virgole:
//
//   tempo_ms, yaw, roll, pitch, acc_x, acc_y, acc_z, gyr_x, gyr_y, gyr_z, forza_V
//
// Sul PC lo script Python cavigliera_logger.py legge queste righe e le
// salva in un file CSV.
// Le righe che iniziano con "#" sono messaggi (errori, "pronto"), non dati.

// ---------------------------------------------------------------------
// LIBRERIE
// ---------------------------------------------------------------------
#include <Wire.h>              // comunicazione I2C (il "bus" a cui sono collegati i sensori)
#include <Adafruit_Sensor.h>   // libreria base di Adafruit, richiesta da quella del BNO055
#include <Adafruit_BNO055.h>   // funzioni per leggere il BNO055

// ---------------------------------------------------------------------
// SCELTA DI COME E' COLLEGATO IL SENSORE DI FORZA
// ---------------------------------------------------------------------
// 1 = l'FSR e' letto con l'ADS1115 (I2C), canale 0   <- configurazione attuale
// 0 = l'FSR e' collegato direttamente al pin A0 della QT Py
// "#define" crea una costante che il compilatore usa PRIMA di compilare:
// le parti tra "#if" e "#endif" vengono incluse solo se la condizione e' vera.
#define USA_ADS1115 1

#if USA_ADS1115
#include <Adafruit_ADS1X15.h>  // funzioni per leggere l'ADS1115
Adafruit_ADS1115 ads;          // oggetto che rappresenta il convertitore ADS1115
#endif

// Oggetto che rappresenta il BNO055.
//   55     = un numero identificativo qualsiasi del sensore (non conta)
//   0x28   = indirizzo I2C del BNO055 (trovato con i2c_scanner.ino)
//   &Wire1 = il bus I2C a cui e' collegato
Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28, &Wire1);

// ---------------------------------------------------------------------
// TEMPORIZZAZIONE
// ---------------------------------------------------------------------
// Ogni quanti millisecondi mandare una riga.
// 20 ms -> 1000 / 20 = 50 righe al secondo (50 Hz).
// A 10 ms la scheda non riusciva a leggere tutto in tempo e le righe
// arrivavano in modo irregolare; a 100 ms sarebbe troppo lento per
// trovare con precisione l'istante del contatto del tallone.
const unsigned long PERIODO_MS = 20;  // 50 Hz: costante e sufficiente per la camminata

// Istante (in ms) in cui fare la prossima lettura.
unsigned long prossimo = 0;

// =====================================================================
// setup(): viene eseguita UNA volta sola, all'accensione della scheda
// =====================================================================
void setup() {
  // Avvia la comunicazione seriale via USB con il PC.
  // 115200 e' la velocita' (baud); deve essere uguale a quella nel Python.
  Serial.begin(115200);

  // Aspetta che il PC apra la porta seriale, cosi' non si perdono
  // i primi messaggi.
  while (!Serial) {}

  // --- Avvio del BNO055 ---
  // bno.begin() restituisce false se il sensore non risponde
  // (es. cavo staccato). In quel caso il programma si blocca qui e
  // stampa l'errore ogni secondo, invece di mandare dati sbagliati.
  if (!bno.begin()) {
    while (1) {
      Serial.println("# ERRORE: BNO055 non trovato");
      delay(1000);
    }
  }
  delay(1000);                 // lascia al BNO055 il tempo di avviarsi
  bno.setExtCrystalUse(true);  // usa il quarzo esterno della scheda: orologio interno piu' preciso

#if USA_ADS1115
  // --- Avvio dell'ADS1115 ---
  // 0x48 e' il suo indirizzo I2C, &Wire1 il bus a cui e' collegato.
  if (!ads.begin(0x48, &Wire1)) {
    while (1) {
      Serial.println("# ERRORE: ADS1115 non trovato");
      delay(1000);
    }
  }
  // Guadagno: l'ADS1115 misura tensioni fino a +-4.096 V.
  // L'FSR da' al massimo ~3.3 V, quindi questo intervallo va bene.
  ads.setGain(GAIN_ONE);
  // Velocita' massima di conversione (860 misure al secondo).
  // Con la velocita' di default ogni lettura richiederebbe ~8 ms e
  // rallenterebbe il ciclo.
  ads.setDataRate(RATE_ADS1115_860SPS);
#else
  // Se si usa il pin A0: l'ADC della QT Py restituisce numeri da 0 a 4095
  // (12 bit), dove 0 = 0 V e 4095 = 3.3 V.
  analogReadResolution(12);
#endif

  // Messaggio per il PC: tutto pronto, da ora arrivano i dati.
  Serial.println("# pronto");

  // La prima lettura avviene subito.
  // millis() = millisecondi trascorsi dall'accensione della scheda.
  prossimo = millis();
}

// =====================================================================
// loop(): viene eseguita in continuazione, all'infinito
// =====================================================================
void loop() {
  // --- 1. Aspetta che sia il momento della prossima lettura ---
  // Se non sono ancora passati 20 ms, esce subito da loop() (che
  // ripartira' immediatamente) e ricontrolla.
  // Non uso delay(20) perche' il delay si SOMMEREBBE al tempo impiegato
  // per leggere i sensori: le righe arriverebbero ogni 20 ms + qualcosa,
  // e quel "qualcosa" varia. Cosi' invece l'intervallo e' sempre 20 ms.
  // (La sottrazione con il cast a long funziona anche quando millis()
  // dopo ~49 giorni riparte da zero.)
  if ((long)(millis() - prossimo) < 0) return;
  prossimo += PERIODO_MS;  // fissa l'appuntamento successivo: +20 ms

  // --- 2. Timestamp della riga ---
  unsigned long t = millis();

  // --- 3. Lettura dell'IMU ---
  // Ogni getVector restituisce un vettore di 3 valori (x, y, z).
  // Angoli di Eulero in gradi: x = yaw (direzione, 0..360),
  // y = roll (inclinazione laterale), z = pitch (punta su/giu').
  imu::Vector<3> euler = bno.getVector(Adafruit_BNO055::VECTOR_EULER);         // gradi
  // Accelerazione in m/s^2 sui 3 assi del sensore, gravita' compresa
  // (da fermo il modulo vale circa 9.8).
  imu::Vector<3> acc   = bno.getVector(Adafruit_BNO055::VECTOR_ACCELEROMETER); // m/s^2
  // Velocita' angolare (quanto velocemente ruota) in gradi al secondo,
  // sui 3 assi del sensore. Da fermo vale circa 0.
  imu::Vector<3> gyr   = bno.getVector(Adafruit_BNO055::VECTOR_GYROSCOPE);     // gradi/s, assi del sensore

  // --- 4. Lettura del sensore di forza, convertita in volt ---
#if USA_ADS1115
  // readADC_SingleEnded(0) legge il canale 0 (numero grezzo),
  // computeVolts lo converte in volt.
  float forza = ads.computeVolts(ads.readADC_SingleEnded(0));
#else
  // Numero da 0 a 4095 -> volt da 0 a 3.3 con una proporzione.
  float forza = analogRead(A0) * 3.3 / 4095.0;
#endif

  // --- 5. Invio della riga al PC ---
  // Serial.print scrive un valore senza andare a capo; il secondo numero
  // indica quante cifre decimali scrivere. Tra un valore e l'altro va una
  // virgola. Serial.println alla fine scrive l'ultimo valore e va a capo:
  // il "a capo" segna la fine della riga per il programma Python.
  // L'ORDINE dei valori deve essere uguale a COLONNE in cavigliera_logger.py.
  Serial.print(t);            Serial.print(',');
  Serial.print(euler.x(), 2); Serial.print(',');  // yaw
  Serial.print(euler.y(), 2); Serial.print(',');  // roll
  Serial.print(euler.z(), 2); Serial.print(',');  // pitch
  Serial.print(acc.x(), 3);   Serial.print(',');
  Serial.print(acc.y(), 3);   Serial.print(',');
  Serial.print(acc.z(), 3);   Serial.print(',');
  Serial.print(gyr.x(), 3);   Serial.print(',');
  Serial.print(gyr.y(), 3);   Serial.print(',');
  Serial.print(gyr.z(), 3);   Serial.print(',');
  Serial.println(forza, 3);   // volt
}
