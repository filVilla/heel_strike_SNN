import serial

porta = serial.Serial("/dev/ttyACM0", 115200)
file = open("dati.csv", "w")
file.write("tempo,x,y,z\n")

print("Leggo i dati... (Ctrl+C per fermare)")

try:
    while True:
        riga = porta.readline().decode(errors="ignore").strip()
        valori = riga.split(",")

        if len(valori) == 4:
            print("tempo:", valori[0], " x:", valori[1], " y:", valori[2], " z:", valori[3])
            file.write(riga + "\n")

except KeyboardInterrupt:
    print("Fine")

file.close()
porta.close()