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
