// FIRMWARE DELLA CAVIGLIERA (Adafruit QT Py RP2040)
// Cosa fa: ogni 20 ms (50 Hz) legge l'IMU BNO055 (angoli, accelerometro, giroscopio, quaternione,
//          calibrazione) e la forza del tallone (FSR tramite ADS1115) e manda tutto su una riga CSV via USB.

#include <Wire.h>              
#include <Adafruit_Sensor.h>   
#include <Adafruit_BNO055.h>   

#define USA_ADS1115 1

#if USA_ADS1115
#include <Adafruit_ADS1X15.h>  
Adafruit_ADS1115 ads;          
#endif

Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28, &Wire1);

const unsigned long PERIODO_MS = 20;  // 50 Hz

unsigned long prossimo = 0;

void setup() {
  
  Serial.begin(115200);
 
  while (!Serial) {}

  if (!bno.begin()) {
    while (1) {
      Serial.println("# ERRORE: BNO055 non trovato");
      delay(1000);
    }
  }
  delay(1000);                 
  bno.setExtCrystalUse(true);  

#if USA_ADS1115

// 0x48 e' il suo indirizzo I2C, &Wire1 il bus a cui e' collegato.
  if (!ads.begin(0x48, &Wire1)) {
    while (1) {
      Serial.println("# ERRORE: ADS1115 non trovato");
      delay(1000);
    }
  }
  
  ads.setGain(GAIN_ONE);
 

  ads.setDataRate(RATE_ADS1115_860SPS);
#else
  // Se si usa il pin A0: l'ADC della QT Py restituisce numeri da 0 a 4095
  // (12 bit), dove 0 = 0 V e 4095 = 3.3 V.
  analogReadResolution(12);
#endif

  
  Serial.println("# pronto");

 
  prossimo = millis();
}


void loop() {
 

  if ((long)(millis() - prossimo) < 0) return;
  prossimo += PERIODO_MS;  // fissa l'appuntamento successivo: +20 ms

  unsigned long t = millis();

  // Lettura dell'IMU
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
  // Orientamento come quaternione (w, x, y, z): a differenza degli angoli
  // di Eulero non ha posizioni in cui i valori diventano instabili.
  imu::Quaternion q    = bno.getQuat();
  // Accelerazione senza la gravita' (m/s^2): da fermo vale circa 0.
  imu::Vector<3> lin   = bno.getVector(Adafruit_BNO055::VECTOR_LINEARACCEL);   // m/s^2
  // Calibrazione da 0 (non calibrato) a 3 (calibrato) per sistema,
  // giroscopio, accelerometro e magnetometro.
  uint8_t cal_sys, cal_gyr, cal_acc, cal_mag;
  bno.getCalibration(&cal_sys, &cal_gyr, &cal_acc, &cal_mag);

  // Lettura del sensore di forza, convertita in volt 
#if USA_ADS1115
  // readADC_SingleEnded(0) legge il canale 0 (numero grezzo),
  // computeVolts lo converte in volt.
  float forza = ads.computeVolts(ads.readADC_SingleEnded(0));
#else
  // Numero da 0 a 4095 -> volt da 0 a 3.3 con una proporzione.
  float forza = analogRead(A0) * 3.3 / 4095.0;
#endif

  
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
  Serial.print(forza, 3);     Serial.print(',');  // volt
  Serial.print(q.w(), 4);     Serial.print(',');
  Serial.print(q.x(), 4);     Serial.print(',');
  Serial.print(q.y(), 4);     Serial.print(',');
  Serial.print(q.z(), 4);     Serial.print(',');
  Serial.print(lin.x(), 3);   Serial.print(',');
  Serial.print(lin.y(), 3);   Serial.print(',');
  Serial.print(lin.z(), 3);   Serial.print(',');
  Serial.print(cal_sys);      Serial.print(',');
  Serial.print(cal_gyr);      Serial.print(',');
  Serial.print(cal_acc);      Serial.print(',');
  Serial.println(cal_mag);
}
