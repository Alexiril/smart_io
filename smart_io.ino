#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>

#include ".env"
// const char *ssid = "YOUR_SSID";         // Wi-Fi SSID
// const char *password = "YOUR_PASSWORD"; // Wi-Fi password

WebServer server(80);

const int ledPin = 2; // Pin for the LED
const int lightIterations = 20; // Amount of iterations when led will be on

const int lightSensorPin = 15;
const int relayPin = 2;
const int pwmPin = 4;

bool wasServerAction = false; // Flag to check if server action was performed
int currentLightIteration = 0; // Variable to store the current led iteration

// States
String relayState = "off"; // Relay state (on/off)
int pwmValue = 0;          // PWM state (0-255)

int getLigthSensorValue()
{
  return analogRead(lightSensorPin);
}

// Handler for GET /status
void handleStatus()
{
  wasServerAction = true;
  StaticJsonDocument<200> doc;
  doc["lightness"] = getLigthSensorValue();
  doc["relay"] = relayState;
  doc["led-state"] = pwmValue;

  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

// Handler for GET /sensor
void handleGetSensor()
{
  wasServerAction = true;
  StaticJsonDocument<200> doc;
  doc["state"] = getLigthSensorValue();

  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

// Handler for GET /relay
void handleGetRelay()
{
  wasServerAction = true;
  StaticJsonDocument<200> doc;
  doc["state"] = relayState;

  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

// Handler for POST /relay
void handlePostRelay()
{
  wasServerAction = true;
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
  wasServerAction = true;
  StaticJsonDocument<200> doc;
  doc["state"] = pwmValue;

  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

// Handler for POST /led
void handlePostLed()
{
  wasServerAction = true;
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
  pinMode(ledPin, OUTPUT);

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
  server.on("/api/v1/status", HTTP_GET, handleStatus);
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
  wasServerAction = false; // Reset the flag at the beginning of each loop
  if (currentLightIteration > 0) {
    currentLightIteration -= 1;
  }
  digitalWrite(ledPin, currentLightIteration > 0 ? HIGH : LOW);
  // Handle client requests
  server.handleClient();
  if (wasServerAction)
  {
    currentLightIteration = lightIterations;
    digitalWrite(ledPin, HIGH);
  }
}
