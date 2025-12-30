#include <M5Unified.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME680.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ===== WIFI SETTINGS - FILL IN YOUR INFO =====
const char* ssid = "Mars";           // Your WiFi network name
const char* password = "mn0Tb1T$%s";       // Your WiFi password
const char* serverUrl = "http://192.168.8.100:5020/sensor_data";  // Your Pi's IP
// ==============================================

Adafruit_BME680 bme;
HTTPClient http;

// Display states
enum DisplayMode {
  TEMP,
  HUMIDITY,
  PRESSURE,
  GAS,
  AIR_QUALITY,
  ESTIMATED_CO2
};

DisplayMode currentMode = TEMP;
DisplayMode lastMode = TEMP;  // Track last mode to detect changes

// Sensor readings
float temperature = 0;
float humidity = 0;
float pressure = 0;
float gasResistance = 0;  // Raw gas resistance in KOhms
float airQualityScore = 0;  // Our calculated score (0-500, like IAQ)
float estimatedCO2 = 0;  // Rough CO2 estimate

// Previous readings for change detection
float lastDisplayTemp = -999;
float lastDisplayHumidity = -999;
float lastDisplayPressure = -999;
float lastDisplayGas = -999;
float lastDisplayAQ = -999;
float lastDisplayCO2 = -999;

// Baseline tracking for air quality
float gasBaseline = 0;
int baselineSamples = 0;
const int BASELINE_SAMPLES_NEEDED = 50;  // ~5 minutes of readings

unsigned long lastSendTime = 0;
const unsigned long sendInterval = 60000;  // Send data every 60 seconds

bool wifiConnected = false;

// Function declarations
void connectWiFi();
void readSensors();
void calculateAirQuality();
void sendDataToServer();
void drawTemperatureScreen();
void drawHumidityScreen();
void drawPressureScreen();
void drawGasScreen();
void drawAirQualityScreen();
void drawCO2Screen();
void updateDisplay();

void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);
  M5.Display.setRotation(0);
  M5.Display.setBrightness(100);
  M5.Display.fillScreen(BLACK);
  M5.Display.setTextDatum(middle_center);
  
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("M5Stack Atom S3 ENV Pro with Air Quality Calculation");
  
  // Initialize I2C for Grove connector (Port A on Atom S3)
  Wire.begin(2, 1);  // SDA=GPIO2, SCL=GPIO1
  
  // Initialize BME688 (also works with BME680)
  // Try address 0x77 first, then 0x76
  if (!bme.begin(0x77, &Wire)) {
    Serial.println("Sensor not found at 0x77, trying 0x76...");
    if (!bme.begin(0x76, &Wire)) {
      Serial.println("Could not find BME688/BME680 sensor!");
      M5.Display.setTextSize(1);
      M5.Display.drawString("Sensor Error!", M5.Display.width()/2, M5.Display.height()/2);
      M5.Display.drawString("Check connection", M5.Display.width()/2, M5.Display.height()/2 + 15);
      while (1) delay(10);
    }
  }
  
  Serial.println("BME688 sensor found!");
  
  // Configure BME688
  bme.setTemperatureOversampling(BME680_OS_8X);
  bme.setHumidityOversampling(BME680_OS_2X);
  bme.setPressureOversampling(BME680_OS_4X);
  bme.setIIRFilterSize(BME680_FILTER_SIZE_3);
  bme.setGasHeater(320, 150); // 320°C for 150 ms
  
  Serial.println("BME688 initialized successfully!");
  Serial.println("Establishing baseline... (needs ~5 minutes)");
  
  M5.Display.setTextSize(1);
  M5.Display.drawString("Sensor OK", 64, 50);
  M5.Display.drawString("Calibrating...", 64, 65);
  
  // Connect to WiFi
  connectWiFi();
  
  delay(2000);
}

void connectWiFi() {
  if (strlen(ssid) == 0) {
    Serial.println("WiFi credentials not set!");
    M5.Display.fillScreen(BLACK);
    
    // Draw WiFi icon with X
    M5.Display.drawCircle(64, 35, 15, RED);
    M5.Display.drawCircle(64, 35, 10, RED);
    M5.Display.drawCircle(64, 35, 5, RED);
    M5.Display.fillCircle(64, 45, 3, RED);
    M5.Display.drawLine(50, 25, 78, 50, RED);
    M5.Display.drawLine(51, 25, 79, 50, RED);
    
    M5.Display.setTextSize(2);
    M5.Display.setTextColor(RED);
    M5.Display.drawString("No WiFi", 64, 70);
    M5.Display.setTextSize(1);
    M5.Display.drawString("Credentials", 64, 95);
    delay(2000);
    return;
  }
  
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    Serial.println("\nWiFi Connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    
    M5.Display.fillScreen(BLACK);
    
    // Draw WiFi icon (connected)
    M5.Display.drawCircle(64, 35, 15, GREEN);
    M5.Display.drawCircle(64, 35, 10, GREEN);
    M5.Display.drawCircle(64, 35, 5, GREEN);
    M5.Display.fillCircle(64, 45, 3, GREEN);
    
    M5.Display.setTextSize(2);
    M5.Display.setTextColor(GREEN);
    M5.Display.drawString("WiFi", 64, 65);
    M5.Display.drawString("Connected", 64, 85);
    delay(2000);
  } else {
    wifiConnected = false;
    Serial.println("\nWiFi Connection Failed!");
    
    M5.Display.fillScreen(BLACK);
    
    // Draw WiFi icon with slash (not connected)
    M5.Display.drawCircle(64, 35, 15, RED);
    M5.Display.drawCircle(64, 35, 10, RED);
    M5.Display.drawCircle(64, 35, 5, RED);
    M5.Display.fillCircle(64, 45, 3, RED);
    // Slash through it
    M5.Display.drawLine(50, 25, 78, 50, RED);
    M5.Display.drawLine(51, 25, 79, 50, RED);
    M5.Display.drawLine(50, 26, 78, 51, RED);
    
    M5.Display.setTextSize(2);
    M5.Display.setTextColor(RED);
    M5.Display.drawString("WiFi", 64, 65);
    M5.Display.drawString("Failed", 64, 85);
    delay(2000);
  }
}

void readSensors() {
  if (!bme.performReading()) {
    Serial.println("Failed to perform reading!");
    return;
  }
  
  temperature = bme.temperature;
  humidity = bme.humidity;
  pressure = bme.pressure / 100.0;  // Convert Pa to hPa
  gasResistance = bme.gas_resistance / 1000.0;  // Convert ohms to KOhms
  
  // Build baseline for air quality calculation
  if (baselineSamples < BASELINE_SAMPLES_NEEDED) {
    gasBaseline += gasResistance;
    baselineSamples++;
    if (baselineSamples == BASELINE_SAMPLES_NEEDED) {
      gasBaseline /= BASELINE_SAMPLES_NEEDED;
      Serial.println("Baseline established: " + String(gasBaseline) + " KOhms");
    }
  }
  
  calculateAirQuality();
  
  Serial.println("--- Sensor Readings ---");
  Serial.print("Temperature: "); Serial.print(temperature); Serial.println(" °C");
  Serial.print("Humidity: "); Serial.print(humidity); Serial.println(" %");
  Serial.print("Pressure: "); Serial.print(pressure); Serial.println(" hPa");
  Serial.print("Gas: "); Serial.print(gasResistance); Serial.println(" KOhms");
  Serial.print("Air Quality Score: "); Serial.println(airQualityScore);
  Serial.print("Est. CO2: "); Serial.print(estimatedCO2); Serial.println(" ppm");
}

void calculateAirQuality() {
  if (baselineSamples < BASELINE_SAMPLES_NEEDED) {
    airQualityScore = 0;  // Still calibrating
    estimatedCO2 = 400;   // Default outdoor CO2
    return;
  }
  
  // Calculate air quality score (0-500, similar to IAQ)
  // Higher gas resistance = better air quality = lower score
  // We map the gas resistance relative to our baseline
  
  float gasRatio = gasResistance / gasBaseline;
  
  if (gasRatio >= 1.0) {
    // Air is as good or better than baseline
    airQualityScore = 50.0 * (2.0 - gasRatio);  // 0-50 for excellent air
    if (airQualityScore < 0) airQualityScore = 0;
  } else {
    // Air is worse than baseline
    airQualityScore = 50.0 + (150.0 * (1.0 - gasRatio));  // 50-200 for degrading air
    if (airQualityScore > 500) airQualityScore = 500;
  }
  
  // Estimate CO2 based on air quality score
  // Better correlation: AQ 0-50 = 400-800ppm, AQ 50-100 = 800-1200, AQ 100+ = 1200+
  if (airQualityScore <= 50) {
    estimatedCO2 = 400 + (airQualityScore * 8);  // 400-800 ppm for excellent air
  } else if (airQualityScore <= 100) {
    estimatedCO2 = 800 + ((airQualityScore - 50) * 8);  // 800-1200 ppm for good air
  } else if (airQualityScore <= 200) {
    estimatedCO2 = 1200 + ((airQualityScore - 100) * 8);  // 1200-2000 ppm for moderate/poor
  } else {
    estimatedCO2 = 2000 + ((airQualityScore - 200) * 10);  // 2000+ for bad air
    if (estimatedCO2 > 5000) estimatedCO2 = 5000;
  }
}

void sendDataToServer() {
  if (!wifiConnected || WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected, skipping data send");
    return;
  }
  
  // Create JSON document
  JsonDocument doc;
  doc["temperature"] = temperature;
  doc["humidity"] = humidity;
  doc["pressure"] = pressure;
  doc["gas_resistance"] = gasResistance;
  doc["air_quality_score"] = airQualityScore;
  doc["estimated_co2"] = estimatedCO2;
  doc["calibrated"] = (baselineSamples >= BASELINE_SAMPLES_NEEDED);
  doc["timestamp"] = millis() / 1000;
  
  String jsonString;
  serializeJson(doc, jsonString);
  
  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/json");
  
  int httpResponseCode = http.POST(jsonString);
  
  if (httpResponseCode > 0) {
    Serial.print("Data sent successfully! Response code: ");
    Serial.println(httpResponseCode);
  } else {
    Serial.print("Error sending data: ");
    Serial.println(httpResponseCode);
  }
  
  http.end();
}

void drawTemperatureScreen() {
  // Only do full redraw if mode changed or value changed by more than 0.2 degrees
  if (lastMode != currentMode || abs(temperature - lastDisplayTemp) > 0.2) {
    M5.Display.fillScreen(BLACK);
    M5.Display.drawRect(0, 0, M5.Display.width(), M5.Display.height(), ORANGE);
    M5.Display.drawRect(1, 1, M5.Display.width()-2, M5.Display.height()-2, ORANGE);
    
    M5.Display.fillCircle(64, 55, 10, ORANGE);
    M5.Display.fillRect(61, 25, 6, 35, ORANGE);
    M5.Display.drawRect(60, 25, 8, 35, ORANGE);
    M5.Display.fillRect(63, 28, 2, 28, RED);
    M5.Display.fillCircle(64, 55, 6, RED);
    
    // Clear text area
    M5.Display.fillRect(20, 85, 88, 30, BLACK);
    
    M5.Display.setTextSize(2);
    M5.Display.setTextColor(ORANGE);
    M5.Display.drawString(String(temperature, 1) + "C", 64, 95);
    
    lastDisplayTemp = temperature;
  }
}

void drawHumidityScreen() {
  if (lastMode != currentMode || abs(humidity - lastDisplayHumidity) > 0.5) {
    M5.Display.fillScreen(BLACK);
    M5.Display.drawRect(0, 0, M5.Display.width(), M5.Display.height(), CYAN);
    M5.Display.drawRect(1, 1, M5.Display.width()-2, M5.Display.height()-2, CYAN);
    
    M5.Display.fillCircle(64, 50, 15, CYAN);
    M5.Display.fillTriangle(64, 25, 49, 50, 79, 50, CYAN);
    M5.Display.fillCircle(60, 45, 4, WHITE);
    
    M5.Display.fillRect(20, 80, 88, 30, BLACK);
    
    M5.Display.setTextSize(2);
    M5.Display.setTextColor(CYAN);
    M5.Display.drawString(String(humidity, 1) + "%", 64, 90);
    
    lastDisplayHumidity = humidity;
  }
}

void drawPressureScreen() {
  if (lastMode != currentMode || abs(pressure - lastDisplayPressure) > 1.0) {
    M5.Display.fillScreen(BLACK);
    M5.Display.drawRect(0, 0, M5.Display.width(), M5.Display.height(), YELLOW);
    M5.Display.drawRect(1, 1, M5.Display.width()-2, M5.Display.height()-2, YELLOW);
    
    M5.Display.drawCircle(64, 45, 20, YELLOW);
    M5.Display.drawCircle(64, 45, 18, YELLOW);
    M5.Display.fillCircle(64, 45, 3, YELLOW);
    M5.Display.drawLine(64, 45, 78, 35, YELLOW);
    M5.Display.drawLine(64, 45, 79, 36, YELLOW);
    
    M5.Display.fillRect(20, 75, 88, 40, BLACK);
    
    M5.Display.setTextSize(2);
    M5.Display.setTextColor(YELLOW);
    M5.Display.drawString(String(pressure, 0), 64, 85);
    M5.Display.setTextSize(1);
    M5.Display.drawString("hPa", 64, 105);
    
    lastDisplayPressure = pressure;
  }
}

void drawGasScreen() {
  if (lastMode != currentMode || abs(gasResistance - lastDisplayGas) > 1.0) {
    M5.Display.fillScreen(BLACK);
    M5.Display.drawRect(0, 0, M5.Display.width(), M5.Display.height(), PURPLE);
    M5.Display.drawRect(1, 1, M5.Display.width()-2, M5.Display.height()-2, PURPLE);
    
    M5.Display.fillCircle(50, 40, 10, PURPLE);
    M5.Display.fillCircle(64, 36, 12, PURPLE);
    M5.Display.fillCircle(78, 40, 10, PURPLE);
    M5.Display.fillRect(50, 40, 28, 12, PURPLE);
    M5.Display.fillCircle(64, 52, 14, PURPLE);
    
    M5.Display.fillRect(20, 75, 88, 40, BLACK);
    
    M5.Display.setTextSize(2);
    M5.Display.setTextColor(PURPLE);
    M5.Display.drawString(String(gasResistance, 0), 64, 85);
    M5.Display.setTextSize(1);
    M5.Display.drawString("KOhm", 64, 105);
    
    lastDisplayGas = gasResistance;
  }
}

void drawAirQualityScreen() {
  if (lastMode != currentMode || abs(airQualityScore - lastDisplayAQ) > 5.0 || baselineSamples < BASELINE_SAMPLES_NEEDED) {
    M5.Display.fillScreen(BLACK);
    
    // Color code based on air quality score
    uint16_t color;
    String quality;
    if (airQualityScore <= 50) {
      color = GREEN;
      quality = "Excellent";
    } else if (airQualityScore <= 100) {
      color = GREENYELLOW;
      quality = "Good";
    } else if (airQualityScore <= 150) {
      color = YELLOW;
      quality = "Moderate";
    } else if (airQualityScore <= 200) {
      color = ORANGE;
      quality = "Poor";
    } else {
      color = RED;
      quality = "Bad";
    }
    
    M5.Display.drawRect(0, 0, M5.Display.width(), M5.Display.height(), color);
    M5.Display.drawRect(1, 1, M5.Display.width()-2, M5.Display.height()-2, color);
    
    // Draw air quality icon
    if (airQualityScore <= 100) {
      // Checkmark for good air
      M5.Display.drawLine(50, 50, 58, 58, color);
      M5.Display.drawLine(58, 58, 78, 35, color);
      M5.Display.drawLine(50, 51, 58, 59, color);
      M5.Display.drawLine(58, 59, 78, 36, color);
    } else {
      // X for poor air
      M5.Display.drawLine(50, 35, 78, 58, color);
      M5.Display.drawLine(78, 35, 50, 58, color);
      M5.Display.drawLine(51, 35, 78, 57, color);
      M5.Display.drawLine(77, 35, 50, 57, color);
    }
    
    M5.Display.setTextSize(2);
    M5.Display.setTextColor(color);
    M5.Display.drawString(String((int)airQualityScore), 64, 80);
    M5.Display.setTextSize(1);
    M5.Display.drawString("Air Quality", 64, 100);
    M5.Display.drawString(quality, 64, 115);
    
    // Show calibration status
    if (baselineSamples < BASELINE_SAMPLES_NEEDED) {
      M5.Display.setTextSize(1);
      M5.Display.setTextColor(ORANGE);
      int percent = (baselineSamples * 100) / BASELINE_SAMPLES_NEEDED;
      M5.Display.drawString("Cal:" + String(percent) + "%", 64, 10);
    }
    
    lastDisplayAQ = airQualityScore;
  }
}

void drawCO2Screen() {
  if (lastMode != currentMode || abs(estimatedCO2 - lastDisplayCO2) > 50.0 || baselineSamples < BASELINE_SAMPLES_NEEDED) {
    M5.Display.fillScreen(BLACK);
    
    // Color code based on CO2 value
    uint16_t color;
    String quality;
    if (estimatedCO2 < 1000) {
      color = GREEN;
      quality = "Good";
    } else if (estimatedCO2 < 1500) {
      color = YELLOW;
      quality = "Moderate";
    } else {
      color = RED;
      quality = "Poor";
    }
    
    M5.Display.drawRect(0, 0, M5.Display.width(), M5.Display.height(), color);
    M5.Display.drawRect(1, 1, M5.Display.width()-2, M5.Display.height()-2, color);
    
    // Draw CO2 molecule icon
    M5.Display.fillCircle(54, 45, 8, color);
    M5.Display.fillCircle(64, 45, 10, color);
    M5.Display.fillCircle(74, 45, 8, color);
    M5.Display.setTextSize(1);
    M5.Display.setTextColor(BLACK);
    M5.Display.drawString("CO", 58, 45);
    M5.Display.drawString("2", 72, 48);
    
    M5.Display.setTextSize(2);
    M5.Display.setTextColor(color);
    M5.Display.drawString(String((int)estimatedCO2), 64, 75);
    M5.Display.setTextSize(1);
    M5.Display.drawString("ppm (est)", 64, 95);
    M5.Display.drawString(quality, 64, 110);
    
    if (baselineSamples < BASELINE_SAMPLES_NEEDED) {
      M5.Display.setTextSize(1);
      M5.Display.setTextColor(ORANGE);
      int percent = (baselineSamples * 100) / BASELINE_SAMPLES_NEEDED;
      M5.Display.drawString("Cal:" + String(percent) + "%", 64, 10);
    }
    
    lastDisplayCO2 = estimatedCO2;
  }
}

void updateDisplay() {
  switch (currentMode) {
    case TEMP:
      drawTemperatureScreen();
      break;
    case HUMIDITY:
      drawHumidityScreen();
      break;
    case PRESSURE:
      drawPressureScreen();
      break;
    case GAS:
      drawGasScreen();
      break;
    case AIR_QUALITY:
      drawAirQualityScreen();
      break;
    case ESTIMATED_CO2:
      drawCO2Screen();
      break;
  }
}

void loop() {
  M5.update();
  
  // Check for screen touch to cycle modes
  if (M5.BtnA.wasPressed()) {
    currentMode = (DisplayMode)((currentMode + 1) % 6);
    lastMode = (DisplayMode)-1;  // Force full redraw on mode change
    updateDisplay();
    Serial.print("Mode changed to: ");
    Serial.println(currentMode);
  }
  
  // Read sensors every 2 seconds
  static unsigned long lastRead = 0;
  if (millis() - lastRead > 2000) {
    readSensors();
    updateDisplay();
    lastMode = currentMode;  // Update last mode after drawing
    lastRead = millis();
  }
  
  // Send data to server periodically
  if (wifiConnected && millis() - lastSendTime > sendInterval) {
    sendDataToServer();
    lastSendTime = millis();
  }
  
  delay(10);
}
