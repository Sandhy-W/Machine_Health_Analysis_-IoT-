#include <WiFiS3.h>            // Wi-Fi support for Arduino Uno R4
#include <ArduinoHttpClient.h> // HTTP client for sending data
#include <DHT.h>

#define DHTPIN 2
#define DHTTYPE DHT11
#define buzzer 8
#define inPlus 9  // minus input for fan motor
#define inMinus 10 // plus input for fan motor
#define vibrationPin A1  // Piezo Vibration Sensor connected to A1
#define buttonPin 3  // Button connected to pin 3

const char* ssid = "NOKIA-6161-2.4GHz";       
const char* password = "NOKIA12345";          
IPAddress server(192, 168, 18, 16);           
const int port = 5050;                        

DHT dht(DHTPIN, DHTTYPE);
WiFiClient wifi;
HttpClient client(wifi, server, port);

// Toggle state variables
bool toggleState = false;
bool lastButtonState = HIGH;  // Because we use INPUT_PULLUP

// Converts analogRead value to voltage
float readVibrationVoltage(int analogValue) {
  return analogValue * (5.0 / 1023.0);
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(buzzer, OUTPUT); 
  pinMode(inPlus, OUTPUT);
  pinMode(inMinus, OUTPUT);
  pinMode(buttonPin, INPUT_PULLUP);  // Setup button

  dht.begin(); // Initialize DHT sensor

  Serial.println("System Ready. Press Button to Start/Stop.");
}

void loop() {
  // Always check button first
  bool currentButtonState = digitalRead(buttonPin);

  if (lastButtonState == HIGH && currentButtonState == LOW) {
    toggleState = !toggleState;  // Toggle ON/OFF
    Serial.print("System is ");
    Serial.println(toggleState ? "ON" : "OFF");
    delay(100);  // debounce
  }
  lastButtonState = currentButtonState;

  // If system is OFF, skip everything
  if (!toggleState) {
    digitalWrite(buzzer, LOW);
    digitalWrite(inPlus, LOW);
    digitalWrite(inMinus, LOW);
    return;
  }

  // ---- ONLY if system is ON, do Wi-Fi, DHT, vibration, etc ----

  float temperature = dht.readTemperature();
  int rawVibration = analogRead(vibrationPin);
  float vibrationVoltage = readVibrationVoltage(rawVibration);

  if (isnan(temperature)) {
    Serial.println("Failed to read from DHT sensor!");
    delay(2000);
    return;
  }

  // Check Wi-Fi only if system ON
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.disconnect();  
    delay(500);
    WiFi.begin(ssid, password);
    delay(5000);  // shorter waiting time
  }

  // Create JSON payload
  String postData = "{\"temperature\": " + String(temperature) +
                    ", \"vibration\": " + String(vibrationVoltage, 2) + "}";

  // Alert control
  if (temperature >= 25 || vibrationVoltage > 2.5) {
    digitalWrite(buzzer, HIGH);
  } else {
    digitalWrite(buzzer, LOW);
  }

  analogWrite(inPlus, LOW); 
  digitalWrite(inMinus, 200);

  client.beginRequest();
  client.post("/data");
  client.sendHeader("Content-Type", "application/json");
  client.sendHeader("Content-Length", postData.length());
  client.beginBody();
  client.print(postData);
  client.endRequest();

  delay(2000);
}

