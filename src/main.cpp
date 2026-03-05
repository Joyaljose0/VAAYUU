#include "DFRobot_OxygenSensor.h"
#include <Adafruit_BME280.h>
#include <Arduino.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <Wire.h>
#include <math.h>

#include <Preferences.h>

#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

String backendIp = "vaayuu-backend.onrender.com"; // Default cloud fallback
Preferences preferences;
WebServer server(80);

/* ================= LED INDICATOR ================= */
#define LED_PIN 2

/* ================= PIN CONFIG ================= */
#define SDA_PIN 21
#define SCL_PIN 22

#define MQ7_A_PIN 35
#define MQ7_D_PIN 25

#define MQ135_A_PIN 34
#define MQ135_D_PIN 27

/* ================= OBJECTS ================= */
Adafruit_BME280 bme;
DFRobot_OxygenSensor oxygen;
WiFiClientSecure
    securedClient; // Persistent SSL client to prevent fragmentation
unsigned long lastCloudSend = 0;
unsigned long lastWarmupHeartbeat = 0;

/* ================= OXYGEN SENSOR ================= */
#define Oxygen_IICAddress ADDRESS_3 // 0x73
#define COLLECT_NUMBER 20

/* ================= CALIBRATION VALUES ================= */
/* Calculated dynamically during setup() */
float MQ7_R0 = 10.0;
float MQ135_R0 = 10.0;

/* --- Smoothing States --- */
float filtered_humidity = -1.0;
float filtered_temperature = -1.0;
const float EMA_ALPHA = 0.1; // Smoothing factor (lower = slower/more stable)

/* High-Sensitivity Coefficients for CO and CO2 */
#define MQ7_A_CO 100.0
#define MQ7_B_CO -1.53
#define MQ135_A_CO2 110.47
#define MQ135_B_CO2 -2.862

/* ================= FILTERING ================= */
float getMedian(float *data, int n) {
  for (int i = 0; i < n - 1; i++) {
    for (int j = 0; j < n - i - 1; j++) {
      if (data[j] > data[j + 1]) {
        float temp = data[j];
        data[j] = data[j + 1];
        data[j + 1] = temp;
      }
    }
  }
  return data[n / 2];
}

float getMQ7_PPM(int raw_adc) {
  if (raw_adc < 1)
    return 0.5;
  float v_out = (raw_adc * 3.3) / 4095.0;
  if (v_out < 0.1)
    return 0.5;
  float Rs = (3.3 - v_out) / v_out;
  float ratio = Rs / MQ7_R0;
  // ratio = 1.0 in clean air (0.5ppm CO).
  float ppm = 0.5 * pow(ratio, -4.5);
  return (ppm > 2000.0) ? 2000.0 : ppm;
}

float getMQ135_PPM(int raw_adc) {
  if (raw_adc < 1)
    return 400.0;
  float v_out = (raw_adc * 3.3) / 4095.0;
  if (v_out < 0.1)
    return 400.0;
  float Rs = (3.3 - v_out) / v_out;
  float ratio = Rs / MQ135_R0;
  // ratio = 1.0 in clean air (400ppm CO2).
  float ppm = 400.0 * pow(ratio, -3.5);
  return (ppm > 50000.0) ? 50000.0 : ppm;
}

void sendCloudWarmupHeartbeat();
void startAPMode();

void sendCloudWarmupHeartbeat() {
  if (WiFi.status() == WL_CONNECTED && backendIp != "") {
    if (millis() - lastWarmupHeartbeat > 5000) { // Every 5s
      lastWarmupHeartbeat = millis();
      bool isHttps = backendIp.startsWith("https://") ||
                     backendIp.indexOf("onrender.com") != -1;
      String url =
          (isHttps ? "https://" : "http://") + backendIp + "/sensor-data";

      Serial.printf("DEBUG: Cloud Warmup Heartbeat to: %s\n", url.c_str());
      securedClient.stop();
      delay(100); // Wait for socket cleanup
      HTTPClient https;
      https.setTimeout(30000); // 30s for slow Render cold-starts
      if (https.begin(securedClient, url)) {
        https.addHeader("Content-Type", "application/json");
        https.addHeader("Connection", "close");
        String payload =
            "{\"co\":0,\"gas\":400,\"temperature\":0,\"humidity\":0,"
            "\"pressure\":0,\"oxygen\":20.9,\"is_warming_up\":true}";
        int httpResponseCode = https.POST(payload);
        Serial.printf("Cloud Warmup Heartbeat Result: %d\n", httpResponseCode);
        if (httpResponseCode < 0) {
          Serial.printf("Heartbeat ERROR: %s\n",
                        https.errorToString(httpResponseCode).c_str());
        }
        https.end();
        securedClient.stop();
      } else {
        Serial.println(
            "Heartbeat ERROR: Unable to begin connection with securedClient");
      }
    }
  }
}

void startAPMode();

// Replaced old float methods with mapAnalogToPPM

/* ================= SETUP ================= */
void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  pinMode(MQ7_D_PIN, INPUT);
  pinMode(MQ135_D_PIN, INPUT);

  Wire.begin(SDA_PIN, SCL_PIN);
  analogSetAttenuation(ADC_11db); // Enable full 0-3.3V range

  /* -------- BME280 -------- */
  if (!bme.begin(0x76)) {
    Serial.println("BME280_ERROR: Proceeding with dummy values.");
  }

  // --- SSL Stability Config ---
  securedClient.setInsecure();
  securedClient.setHandshakeTimeout(10000); // 10s for slow WiFi handshakes

  /* -------- OLED Display -------- */
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println(F("SSD1306 allocation failed"));
  }
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(WHITE);
  display.setCursor(0, 0);
  display.println("VAAYUU v2.2");
  display.println("Initializing...");
  display.display();
  Serial.println("BOOT: VAAYUU v2.2 INITIALIZING");

  /* -------- Oxygen Sensor -------- */
  while (!oxygen.begin(Oxygen_IICAddress)) {
    Serial.println("Oxygen Sensor Error!");
    delay(1000);
  }

  // MQ and Oxygen sensors need a longer warm-up for a stable baseline
  long mq7_cal = 0;
  long mq135_cal = 0;
  int samples = 1800; // 3 minutes (1800 * 100ms) for stable MQ warmup
  for (int i = 0; i < samples; i++) {
    int r7 = analogRead(MQ7_A_PIN);
    int r135 = analogRead(MQ135_A_PIN);
    mq7_cal += r7;
    mq135_cal += r135;

    if (i % 20 == 0) { // Every 2 seconds
      Serial.println("STATUS:WARMING_UP");
      sendCloudWarmupHeartbeat(); // WiFi Heartbeat
      display.clearDisplay();
      display.setCursor(0, 0);
      display.println("SENSOR WARMUP (3m)");
      display.print("Progress: ");
      display.print((i * 100) / samples);
      display.println("%");
      display.print("ADC7: ");
      display.println(r7);
      display.print("ADC135: ");
      display.println(r135);
      display.display();
    }
    delay(100);
  }

  // --- Post-Warmup Stabilization for Oxygen ---
  Serial.println("Stabilizing Oxygen sensor (30s)...");
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("O2 STABILIZING (30s)");
  display.display();

  // 30 seconds for O2
  for (int i = 0; i < 30; i++) {
    Serial.println("STATUS:WARMING_UP"); // Keep backend informed
    sendCloudWarmupHeartbeat();          // WiFi Heartbeat
    delay(1000);
    if (i % 2 == 0) {
      display.fillRect(0, 16, 128, 8, BLACK);
      display.setCursor(0, 16);
      display.print("O2 Prep: ");
      display.print((i * 100) / 30);
      display.println("%");
      display.display();
    }
  }

  // -------- Oxygen Sensor Calibration (Triple Stage) --------
  Serial.println("Calibrating Oxygen sensor to 20.9% reference...");
  for (int c = 0; c < 3; c++) {
    oxygen.calibrate(20.9, Oxygen_IICAddress);
    delay(1000);
  }

  float postCal = oxygen.getOxygenData(20);
  Serial.print("Oxygen Post-Calibration Raw: ");
  Serial.print(postCal);
  Serial.println("%");

  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("O2 Calibrated:");
  display.println("Base: 20.9%");
  display.display();
  delay(3000);

  // Average ADC reading
  float mq7_adc = mq7_cal / (float)samples;
  float mq135_adc = mq135_cal / (float)samples;
  if (mq7_adc < 1)
    mq7_adc = 1;
  if (mq135_adc < 1)
    mq135_adc = 1;

  // Calculate Rs in current air
  float v_out7 = (mq7_adc * 3.3) / 4095.0;
  float Rs7 = (3.3 - v_out7) / v_out7;

  float v_out135 = (mq135_adc * 3.3) / 4095.0;
  float Rs135 = (3.3 - v_out135) / v_out135;

  // Set R0 as the actual resistance in current (clean) air
  // Sanity check: If ADC is too low (saturation), don't lock a broken baseline
  if (v_out7 > 0.05) {
    MQ7_R0 = Rs7;
  } else {
    MQ7_R0 = 1.0; // Fail-safe default
    Serial.println(
        "WARN: MQ7 ADC too low during calibration, using default R0");
  }

  if (v_out135 > 0.05) {
    MQ135_R0 = Rs135;
  } else {
    MQ135_R0 = 1.0; // Fail-safe default
    Serial.println(
        "WARN: MQ135 ADC too low during calibration, using default R0");
  }

  Serial.println("OK: Calibration complete. Baselines locked.");
  Serial.println("STATUS:READY");

  // --- Check for manual setup trigger (e.g., hold MQ7 Digital Pin 25 at boot)
  // ---
  pinMode(MQ7_D_PIN, INPUT_PULLUP);
  delay(100);
  if (digitalRead(MQ7_D_PIN) == LOW) {
    Serial.println("Manual Setup Mode Triggered!");
    preferences.begin("wifi-config", false);
    preferences.clear();
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("FORCING SETUP...");
    display.display();
    delay(2000);
  }

  // -------- NVS Auto-Connect --------
  preferences.begin("wifi-config", false);
  String savedSSID = preferences.getString("ssid", "");
  String savedPassword = preferences.getString("password", "");
  String savedIp = preferences.getString("ip", "");

  if (savedSSID != "" && savedIp != "") {
    Serial.println("Found Saved WiFi Credentials. Connecting...");
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("Connecting to:");
    display.println(savedSSID);
    display.display();

    // Configure Static DNS for reliability (Google DNS)
    IPAddress dns1(8, 8, 8, 8);
    IPAddress dns2(8, 8, 4, 4);
    if (!WiFi.config(INADDR_NONE, INADDR_NONE, INADDR_NONE, dns1, dns2)) {
      Serial.println("Error: Failed to configure Static DNS");
    }

    WiFi.begin(savedSSID.c_str(), savedPassword.c_str());
    backendIp = savedIp;

    // Blink LED while connecting
    int timeout = 0;
    while (WiFi.status() != WL_CONNECTED && timeout < 20) {
      digitalWrite(LED_PIN, !digitalRead(LED_PIN)); // Toggle
      delay(500);
      Serial.print(".");
      timeout++;
    }

    if (WiFi.status() == WL_CONNECTED) {
      Serial.println("\nWiFi Connected! Backend IP: " + backendIp);
      digitalWrite(LED_PIN, HIGH); // Solid ON means connected

      display.clearDisplay();
      display.setCursor(0, 0);
      display.println("WIFI CONNECTED!");
      display.println("IP: " + WiFi.localIP().toString());
      display.println("Backend: " + backendIp);
      display.display();
      delay(2000);
    } else {
      Serial.println("\nWiFi Connection Failed. Starting Setup Mode...");
      startAPMode();
    }
  } else {
    Serial.println("No WiFi credentials saved. Starting Access Point Mode...");
    startAPMode();
  }
}

void startAPMode() {
  WiFi.mode(WIFI_AP);
  WiFi.softAPdisconnect(true);
  delay(100);

  bool success = WiFi.softAP("VAAYUU-Setup", "12345678");
  if (success) {
    Serial.println(
        "AP Mode Started. Connect to 'VAAYUU-Setup' (Pass: 12345678)");
    Serial.print("AP IP Address: ");
    Serial.println(WiFi.softAPIP());
    Serial.println("Visit http://192.168.4.1 in your browser.");
  } else {
    Serial.println("CRITICAL ERROR: Failed to start WiFi Access Point.");
    // Fallback attempt with different channel
    WiFi.softAP("VAAYUU-Setup", "12345678", 6);
  }

  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("WIFI SETUP MODE");
  display.println("Connect to:");
  display.println("VAAYUU-Setup");
  display.println("IP: 192.168.4.1");
  display.display();

  // Scan for networks
  int n = WiFi.scanNetworks();
  String networkOptions = "";
  for (int i = 0; i < n; ++i) {
    networkOptions += "<option value='" + WiFi.SSID(i) + "'>" + WiFi.SSID(i) +
                      " (" + WiFi.RSSI(i) + " dBm)</option>";
  }

  server.on("/", HTTP_GET, [networkOptions]() {
    String html = "<html><head><meta name='viewport' "
                  "content='width=device-width, initial-scale=1'><style>";
    html += "body { font-family: sans-serif; padding: 20px; background: "
            "#f4f4f4; text-align: center; }";
    html += "form { background: white; padding: 20px; border-radius: 8px; "
            "box-shadow: 0 2px 10px rgba(0,0,0,0.1); display: inline-block; "
            "text-align: left; max-width: 400px; width: 100%; }";
    html +=
        "input, select { width: 100%; padding: 12px; margin: 10px 0; border: "
        "1px solid #ddd; border-radius: 4px; box-sizing: border-box; }";
    html += "input[type='submit'] { background: #4a90e2; color: white; border: "
            "none; font-weight: bold; cursor: pointer; }";
    html += "label { font-size: 14px; color: #666; }";
    html += "</style></head><body><h1>VAAYUU WiFi Setup</h1>";
    html += "<form method='POST' action='/save'>";
    html += "<label>Select Network:</label><select "
            "onchange='document.getElementById(\"ssid\").value=this.value'><"
            "option value=''>-- Choose Network --</option>" +
            networkOptions + "</select>";
    html += "<input type='text' id='ssid' name='ssid' placeholder='WiFi Name "
            "(SSID)'>";
    html += "<input type='password' name='pass' placeholder='Password'>";
    html += "<label>Backend (e.g. vaayuu-backend.onrender.com):</label>";
    html += "<input type='text' name='ip' placeholder='Backend URL' "
            "value='vaayuu-backend.onrender.com'>";
    html += "<input type='submit' value='Save & Connect'>";
    html += "</form></body></html>";
    server.send(200, "text/html", html);
  });

  server.on("/save", HTTP_POST, []() {
    String ssid = server.arg("ssid");
    String pass = server.arg("pass");
    String ip = server.arg("ip");

    if (ssid != "" && ip != "") {
      preferences.putString("ssid", ssid);
      preferences.putString("password", pass);
      preferences.putString("ip", ip);
      server.send(200, "text/plain",
                  "Credentials Saved! VAAYUU is restarting...");
      delay(2000);
      ESP.restart();
    } else {
      server.send(200, "text/plain", "Missing SSID or Backend URL!");
    }
  });

  server.begin();
  // We'll keep running the server in the loop
}

/* ================= LOOP ================= */
void loop() {
  server.handleClient();

  /* -------- Handle Backend Commands -------- */
  if (Serial.available() > 0) {
    String msg = Serial.readStringUntil('\n');
    msg.trim();
    if (msg.startsWith("WIFI:")) {
      String credentials = msg.substring(5);
      int firstComma = credentials.indexOf(',');
      int secondComma = credentials.indexOf(',', firstComma + 1);

      if (firstComma > 0 && secondComma > 0) {
        String ssid = credentials.substring(0, firstComma);
        String password = credentials.substring(firstComma + 1, secondComma);
        backendIp = credentials.substring(secondComma + 1);

        // Save to NVS
        preferences.putString("ssid", ssid);
        preferences.putString("password", password);
        preferences.putString("ip", backendIp);

        // Configure Static DNS for reliability (Google DNS)
        IPAddress dns1(8, 8, 8, 8);
        IPAddress dns2(8, 8, 4, 4);
        if (!WiFi.config(INADDR_NONE, INADDR_NONE, INADDR_NONE, dns1, dns2)) {
          Serial.println("Error: Failed to configure Static DNS");
        }

        WiFi.disconnect();
        WiFi.begin(ssid.c_str(), password.c_str());
        Serial.println("Connecting to WiFi: " + ssid);
        Serial.println("Backend IP Set to: " + backendIp);

        display.clearDisplay();
        display.setCursor(0, 0);
        display.println("Connecting to:");
        display.println(ssid);
        display.display();

        int timeout = 0;
        while (WiFi.status() != WL_CONNECTED && timeout < 20) {
          digitalWrite(LED_PIN, !digitalRead(LED_PIN));
          delay(500);
          timeout++;
        }

        if (WiFi.status() == WL_CONNECTED) {
          digitalWrite(LED_PIN, HIGH);

          display.clearDisplay();
          display.setCursor(0, 0);
          display.println("WIFI CONNECTED!");
          display.println("IP: " + WiFi.localIP().toString());
          display.println("Backend: " + backendIp);
          display.display();
          delay(2000);
        } else {
          digitalWrite(LED_PIN, LOW);

          display.clearDisplay();
          display.setCursor(0, 0);
          display.println("WiFi Failed.");
          display.display();
        }
      }
    } else if (msg.startsWith("UPDATE_IP:")) {
      String newIp = msg.substring(10);
      newIp.trim();

      if (newIp != "" && newIp != backendIp) {
        backendIp = newIp;
        preferences.putString("ip", backendIp);
        Serial.println("Backend IP Auto-Updated to: " + backendIp);

        display.clearDisplay();
        display.setCursor(0, 0);
        display.println("USB IP SYNC:");
        display.println("New IP:");
        display.println(backendIp);
        display.display();

        // Pause briefly so user can read the OLED
        delay(2000);
      }
    } else if (msg == "CAL_O2") {
      Serial.println("Manual Oxygen Calibration to 20.9% triggered...");
      oxygen.calibrate(20.9, Oxygen_IICAddress);
      delay(1000);
      float post = oxygen.getOxygenData(20);
      Serial.print("New O2 Reading: ");
      Serial.println(post, 2);
    } else if (msg == "CAL_CO2") {
      Serial.println("Manual CO2 Zeroing (400ppm) triggered...");
      int raw135 = analogRead(MQ135_A_PIN);
      float v_out135 = (raw135 * 3.3) / 4095.0;
      float Rs135 = (3.3 - v_out135) / v_out135;
      MQ135_R0 = Rs135 / 4.4;
      Serial.print("New MQ135_R0: ");
      Serial.println(MQ135_R0);
    } else if (msg == "CAL_CO7") {
      Serial.println("Manual CO7 Zeroing (Clean Air) triggered...");
      int raw7 = analogRead(MQ7_A_PIN);
      float v_out7 = (raw7 * 3.3) / 4095.0;
      float Rs7 = (3.3 - v_out7) / v_out7;
      MQ7_R0 = Rs7 / 27.0;
      Serial.print("New MQ7_R0: ");
      Serial.println(MQ7_R0);
    } else if (msg == "CAL_ALL") {
      Serial.println("Full System Calibration Triggered...");
      // 1. Oxygen
      oxygen.calibrate(20.9, Oxygen_IICAddress);
      // 2. MQ135 (Baseline Reset)
      int r135 = analogRead(MQ135_A_PIN);
      float v135 = (r135 * 3.3) / 4095.0;
      if (v135 > 0.1)
        MQ135_R0 = (3.3 - v135) / v135;
      // 3. MQ7 (Baseline Reset)
      int r7 = analogRead(MQ7_A_PIN);
      float v7 = (r7 * 3.3) / 4095.0;
      if (v7 > 0.1)
        MQ7_R0 = (3.3 - v7) / v7;
      Serial.println("OK: All Baselines Reset.");
    } else if (msg == "RAW") {
      int r7 = analogRead(MQ7_A_PIN);
      int r135 = analogRead(MQ135_A_PIN);
      Serial.print("RAW_ADC_CO7: ");
      Serial.println(r7);
      Serial.print("RAW_ADC_CO2_135: ");
      Serial.println(r135);
      Serial.print("MQ7_R0: ");
      Serial.println(MQ7_R0);
      Serial.print("MQ135_R0: ");
      Serial.println(MQ135_R0);
    } else if (msg == "RESET_WIFI") {
      Serial.println("Manual WiFi Reset Triggered. Clearing credentials and "
                     "starting AP mode...");
      preferences.begin("wifi-config", false);
      preferences.clear();
      preferences.end();
      display.clearDisplay();
      display.setCursor(0, 0);
      display.println("WIFI RESET...");
      display.println("Starting AP Mode");
      display.display();
      delay(2000);
      ESP.restart();
    }
  }

  /* MQ Sensors (Median Filtering for stability) */
  float mq7_samples[11];
  float mq135_samples[11];
  for (int i = 0; i < 11; i++) {
    mq7_samples[i] = analogRead(MQ7_A_PIN);
    mq135_samples[i] = analogRead(MQ135_A_PIN);
    delay(5);
  }
  int mq7_val = getMedian(mq7_samples, 11);
  int mq135_val = getMedian(mq135_samples, 11);

  float co_ppm = getMQ7_PPM(mq7_val);
  float gas_ppm = getMQ135_PPM(mq135_val);

  /* BME280 (Hybrid Filter to prevent rapid humidity jumps) */
  float temp_samples[11];
  float hum_samples[11];
  for (int i = 0; i < 11; i++) {
    temp_samples[i] = bme.readTemperature();
    hum_samples[i] = bme.readHumidity();
    delay(20);
  }
  float raw_temp = getMedian(temp_samples, 11);
  float raw_hum = getMedian(hum_samples, 11);

  // Apply Exponential Moving Average (EMA) to dampen speed of change
  if (filtered_temperature < 0) {
    filtered_temperature = raw_temp;
    filtered_humidity = raw_hum;
  } else {
    filtered_temperature =
        (EMA_ALPHA * raw_temp) + ((1.0 - EMA_ALPHA) * filtered_temperature);
    filtered_humidity =
        (EMA_ALPHA * raw_hum) + ((1.0 - EMA_ALPHA) * filtered_humidity);
  }

  float temperature = filtered_temperature;
  float humidity = filtered_humidity;
  float pressure = bme.readPressure() / 100.0;

  /* Oxygen (Sanitized and Filtered) */
  float o2_samples[7];
  for (int i = 0; i < 7; i++) {
    float raw_o2 = oxygen.getOxygenData(COLLECT_NUMBER);
    // Sanitize: Oxygen cannot physically be > 25% or < 0% in normal Earth
    // atmosphere
    if (raw_o2 > 25.0 || raw_o2 < 0) {
      // Log a warning once in a while to Serial, but don't flood
      // We'll use a static var to track if we should notify
      o2_samples[i] = (i > 0) ? o2_samples[i - 1] : 20.9;
    } else {
      o2_samples[i] = raw_o2;
    }
    delay(10);
  }
  float oxygenLevel = getMedian(o2_samples, 7);

  /* ========== SERIAL DATA PACKET ========== */
  Serial.print("DATA:");
  Serial.print(co_ppm, 2);
  Serial.print(",");
  Serial.print(gas_ppm, 2);
  Serial.print(",");
  Serial.print(temperature, 2);
  Serial.print(",");
  Serial.print(humidity, 2);
  Serial.print(",");
  Serial.print(pressure, 2);
  Serial.print(",");
  Serial.println(oxygenLevel, 2);

  // --- RAW TELEMETRY for Debugging ---
  Serial.print("INFO: RAW_ADC_CO7=");
  Serial.print(mq7_val);
  Serial.print(" | RAW_ADC_CO2=");
  Serial.print(mq135_val);
  Serial.print(" | O2_RAW=");
  Serial.print(oxygenLevel);
  Serial.print(" | R0_CO7=");
  Serial.print(MQ7_R0);
  Serial.print(" | R0_CO2=");
  Serial.println(MQ135_R0);

  /* ========== OLED LIVE METRICS ========== */
  display.clearDisplay();
  display.setCursor(0, 0);
  if (WiFi.status() == WL_CONNECTED) {
    display.println("WIFI: ONLINE");
  } else {
    display.println("WIFI: OFFLINE");
  }
  display.print("Temp: ");
  display.print(temperature, 1);
  display.println(" C");
  display.print("CO2:  ");
  display.print(gas_ppm, 0);
  display.println(" ppm");
  display.print("CO:   ");
  display.print(co_ppm, 1);
  display.println(" ppm");
  display.print("O2:   ");
  display.print(oxygenLevel, 1);
  display.println(" %");
  display.display();

  /* ========== WIFI HTTP POST ========== */
  // Make sure LED reflects live WiFi status for headless operation
  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(LED_PIN, HIGH);
  } else {
    digitalWrite(LED_PIN, LOW);
  }

  if (WiFi.status() == WL_CONNECTED && backendIp != "") {
    String url = "";
    bool isHttps = backendIp.startsWith("https://") ||
                   backendIp.indexOf("onrender.com") != -1;

    // Auto-fix URL if only domain is provided
    if (!backendIp.startsWith("http")) {
      url = (isHttps ? "https://" : "http://") + backendIp;
    } else {
      url = backendIp;
    }

    // Add path if missing
    if (url.indexOf("/sensor-data") == -1) {
      url += "/sensor-data";
    }

    if (isHttps) {
      if (millis() - lastCloudSend > 3000) {
        lastCloudSend = millis();
        securedClient.stop(); // Explicitly stop any previous session
        delay(100);           // Wait for socket cleanup
        Serial.printf("DEBUG: POSTing to Cloud: %s\n", url.c_str());
        HTTPClient https;
        https.setTimeout(30000); // 30s for slow Render cold-starts
        if (https.begin(securedClient, url)) {
          https.addHeader("Content-Type", "application/json");
          https.addHeader("Connection", "close");
          String payload = "{\"co\":" + String(co_ppm, 2) +
                           ",\"gas\":" + String(gas_ppm, 2) +
                           ",\"temperature\":" + String(temperature, 2) +
                           ",\"humidity\":" + String(humidity, 2) +
                           ",\"pressure\":" + String(pressure, 2) +
                           ",\"oxygen\":" + String(oxygenLevel, 2) + "}";
          int httpResponseCode = https.POST(payload);
          Serial.printf("HTTPS Output: %d | Free Heap: %u\n", httpResponseCode,
                        ESP.getFreeHeap());
          if (httpResponseCode < 0) {
            Serial.printf("HTTPS ERROR: %s\n",
                          https.errorToString(httpResponseCode).c_str());
          }
          https.end();
          securedClient.stop();
        } else {
          Serial.println(
              "HTTPS ERROR: Unable to begin connection with securedClient");
        }
      }
    } else {
      WiFiClient client;
      HTTPClient http;
      http.begin(client, url);
      http.addHeader("Content-Type", "application/json");
      String payload = "{\"co\":" + String(co_ppm, 2) +
                       ",\"gas\":" + String(gas_ppm, 2) +
                       ",\"temperature\":" + String(temperature, 2) +
                       ",\"humidity\":" + String(humidity, 2) +
                       ",\"pressure\":" + String(pressure, 2) +
                       ",\"oxygen\":" + String(oxygenLevel, 2) + "}";
      int httpResponseCode = http.POST(payload);
      Serial.print("HTTP Output: ");
      Serial.println(httpResponseCode);
      http.end();
    }
  }

  delay(1000); // 1Hz update rate for responsiveness
}