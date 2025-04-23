#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>

#include ".env"
// const char *ssid = "YOUR_SSID";         // Wi-Fi SSID
// const char *password = "YOUR_PASSWORD"; // Wi-Fi password

WebServer server(80);

const int lightSensorPin = 15;
const int relayPin = 2;
const int pwmPin = 4;

// States
String relayState = "off"; // Relay state (on/off)
int pwmValue = 0;          // PWM state (0-255)

int getLigthSensorValue()
{
  return analogRead(lightSensorPin);
}

// Handler for GET /sensor
void handleGetSensor()
{
  StaticJsonDocument<200> doc;
  doc["state"] = getLigthSensorValue();

  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

// Handler for GET /relay
void handleGetRelay()
{
  StaticJsonDocument<200> doc;
  doc["state"] = relayState;

  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

// Handler for POST /relay
void handlePostRelay()
{
  if (server.hasArg("plain") == false)
  { // No body received
    server.send(400, "application/json", "{\"state\":\"error\",\"error\":\"Bad request\"}");
    return;
  }

  StaticJsonDocument<200> doc;
  DeserializationError error = deserializeJson(doc, server.arg("plain"));

  if (error)
  {
    server.send(400, "application/json", "{\"state\":\"error\",\"error\":\"Invalid JSON\"}");
    return;
  }

  if (!doc["state"].is<String>())
  {
    server.send(400, "application/json", "{\"state\":\"error\",\"error\":\"JSON doesn't contain state\"}");
    return;
  }

  String state = doc["state"].as<String>();

  if (state != "on" && state != "off")
  {
    server.send(400, "application/json", "{\"state\":\"error\",\"error\":\"State is incorrect (expected 'on' or 'off')\"}");
    return;
  }

  relayState = state;

  if (state == "on")
  {
    digitalWrite(relayPin, HIGH);
  }
  else
  {
    digitalWrite(relayPin, LOW);
  }

  server.send(200, "application/json", "{\"state\":\"success\"}");
}

// Handler for GET /led
void handleGetLed()
{
  StaticJsonDocument<200> doc;
  doc["state"] = pwmValue;

  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

// Handler for POST /led
void handlePostLed()
{
  if (server.hasArg("plain") == false)
  { // No body received
    server.send(400, "application/json", "{\"state\":\"error\",\"error\":\"Bad request\"}");
    return;
  }

  StaticJsonDocument<200> doc;
  DeserializationError error = deserializeJson(doc, server.arg("plain"));

  if (error)
  {
    server.send(400, "application/json", "{\"state\":\"error\",\"error\":\"Invalid JSON\"}");
    return;
  }

  if (!doc["state"].is<int>())
  {
    server.send(400, "application/json", "{\"state\":\"error\",\"error\":\"JSON doesn't contain state\"}");
    return;
  }

  pwmValue = min(max(doc["state"].as<int>(), 0), 255);

  analogWrite(pwmPin, pwmValue);

  server.send(200, "application/json", "{\"state\":\"success\"}");
}

void setup()
{
  Serial.begin(115200);

  pinMode(lightSensorPin, INPUT);
  pinMode(relayPin, OUTPUT);
  pinMode(pwmPin, OUTPUT);

  digitalWrite(relayPin, LOW);
  digitalWrite(pwmPin, LOW);

  // Connect to Wi-Fi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED)
  {
    delay(1000);
    Serial.print(".");
  }
  Serial.println("Connected to WiFi");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());

  // Define API endpoints
  server.on("/api/v1/sensor", HTTP_GET, handleGetSensor);
  server.on("/api/v1/relay", HTTP_GET, handleGetRelay);
  server.on("/api/v1/relay", HTTP_POST, handlePostRelay);
  server.on("/api/v1/led", HTTP_GET, handleGetLed);
  server.on("/api/v1/led", HTTP_POST, handlePostLed);

  // Start the server
  server.begin();
  Serial.println("HTTP server started");
}

void loop()
{
  server.handleClient();
}
