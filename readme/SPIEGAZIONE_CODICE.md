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
| `<nome>_segnali.png` | forza, accelerazione e giroscopio per 20 s, con una linea verticale a ogni contatto | vedere a occhio che i contatti trovati sono giusti |
| `<nome>_dt.png` | quanto tempo passa tra una riga e la successiva | controllare che le righe arrivino davvero ogni 20 ms |
| `<nome>_intorno_contatto.png` | i segnali IMU da 200 ms prima a 200 ms dopo ogni contatto, tutti sovrapposti, più la media | vedere la "forma tipica" del segnale quando il tallone tocca |
| `durata_passo.png` | quanto dura ogni passo, per ogni file | confrontare prove e velocità diverse |

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
