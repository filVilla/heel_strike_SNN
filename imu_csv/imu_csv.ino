#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>

// il sensore è collegato con il cavo STEMMA QT, quindi va su Wire1
Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28, &Wire1);

void setup() {
  Serial.begin(115200);
  while (!Serial) {}   // aspetto che si apra la seriale

  if (!bno.begin()) {
    Serial.println("BNO055 non trovato");
    while (1);
  }

  delay(1000);
  bno.setExtCrystalUse(true);
}

void loop() {
  sensors_event_t event;
  bno.getEvent(&event);

  // stampo tempo,x,y,z
  Serial.print(millis());
  Serial.print(",");
  Serial.print(event.orientation.x);
  Serial.print(",");
  Serial.print(event.orientation.y);
  Serial.print(",");
  Serial.println(event.orientation.z);

  delay(100);
}