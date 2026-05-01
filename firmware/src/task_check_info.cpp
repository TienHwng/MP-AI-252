#include "task_check_info.h"

#include "LittleFS.h"
#include "global.h"
#include "task_webserver.h"
#include "task_wifi.h"

#include <ArduinoJson.h>
#include <Preferences.h>

namespace {
constexpr char PREF_NAMESPACE[] = "hera_cfg";
constexpr char LEGACY_INFO_FILE[] = "/info.dat";
constexpr char FACTORY_RESET_KEY[] = "factory_reset";

bool s_littleFsReady = false;
bool s_infoLoaded	 = false;

String cleanString(String value) {
	value.trim();
	return value;
}

String jsonString(JsonVariantConst value, const String &fallback = "") {
	if (value.isNull()) {
		return fallback;
	}

	return cleanString(value.as<String>());
}

uint16_t parsePort(const String &value, uint16_t fallback = 1883) {
	const int port = value.toInt();
	if (port > 0 && port <= 65535) {
		return static_cast<uint16_t>(port);
	}

	return fallback;
}

bool ensureLittleFs() {
	if (s_littleFsReady) {
		return true;
	}

	s_littleFsReady = LittleFS.begin(true);
	if (!s_littleFsReady) {
		Serial.println("[CONFIG] LittleFS mount failed.");
	}

	return s_littleFsReady;
}

bool hasRequiredConfig() {
	const String ssid   = cleanString(WIFI_SSID);
	const String broker = cleanString(CORE_IOT_SERVER);
	const uint16_t port = parsePort(CORE_IOT_PORT, 0);

	return ssid.length() > 0 && broker.length() > 0 && port > 0;
}

void savePreferences() {
	Preferences prefs;
	if (!prefs.begin(PREF_NAMESPACE, false)) {
		Serial.println("[CONFIG] Preferences write open failed.");
		return;
	}

	prefs.putString("wifi_ssid", WIFI_SSID);
	prefs.putString("wifi_pass", WIFI_PASS);
	prefs.putString("mqtt_host", CORE_IOT_SERVER);
	prefs.putString("mqtt_port", String(parsePort(CORE_IOT_PORT)));
	prefs.putString("token", CORE_IOT_TOKEN);
	prefs.putBool(FACTORY_RESET_KEY, false);
	prefs.end();
}

bool loadPreferences() {
	Preferences prefs;
	if (!prefs.begin(PREF_NAMESPACE, true)) {
		Serial.println("[CONFIG] Preferences read open failed.");
		return false;
	}

	if (prefs.getBool(FACTORY_RESET_KEY, false)) {
		WIFI_SSID		= "";
		WIFI_PASS		= "";
		CORE_IOT_SERVER = "";
		CORE_IOT_PORT	= "1883";
		CORE_IOT_TOKEN	= "";
		prefs.end();
		return true;
	}

	const bool hasSavedConfig =
		prefs.isKey("wifi_ssid") || prefs.isKey("wifi_pass") ||
		prefs.isKey("mqtt_host") || prefs.isKey("mqtt_port") ||
		prefs.isKey("token");

	if (hasSavedConfig) {
		WIFI_SSID		= prefs.getString("wifi_ssid", WIFI_SSID);
		WIFI_PASS		= prefs.getString("wifi_pass", WIFI_PASS);
		CORE_IOT_SERVER = prefs.getString("mqtt_host", CORE_IOT_SERVER);
		CORE_IOT_PORT	= prefs.getString("mqtt_port", CORE_IOT_PORT);
		CORE_IOT_TOKEN	= prefs.getString("token", CORE_IOT_TOKEN);
	}

	prefs.end();
	return hasSavedConfig;
}

bool loadLegacyFile() {
	if (!ensureLittleFs() || !LittleFS.exists(LEGACY_INFO_FILE)) {
		return false;
	}

	File file = LittleFS.open(LEGACY_INFO_FILE, "r");
	if (!file) {
		return false;
	}

	StaticJsonDocument<768> doc;
	const DeserializationError error = deserializeJson(doc, file);
	file.close();

	if (error) {
		Serial.print("[CONFIG] Legacy info.dat parse failed: ");
		Serial.println(error.c_str());
		return false;
	}

	WIFI_SSID = jsonString(doc["wifi_ssid"], jsonString(doc["ssid"], jsonString(doc["WIFI_SSID"], WIFI_SSID)));
	WIFI_PASS = jsonString(doc["wifi_pass"], jsonString(doc["pass"], jsonString(doc["WIFI_PASS"], WIFI_PASS)));
	CORE_IOT_SERVER =
		jsonString(doc["mqtt_broker"], jsonString(doc["server"], jsonString(doc["CORE_IOT_SERVER"], CORE_IOT_SERVER)));
	CORE_IOT_PORT =
		String(parsePort(jsonString(doc["mqtt_port"], jsonString(doc["port"], jsonString(doc["CORE_IOT_PORT"], CORE_IOT_PORT)))));
	CORE_IOT_TOKEN =
		jsonString(doc["sys_token"], jsonString(doc["token"], jsonString(doc["CORE_IOT_TOKEN"], CORE_IOT_TOKEN)));

	savePreferences();
	Serial.println("[CONFIG] Migrated legacy info.dat to Preferences.");
	return true;
}
} // namespace

boolean is_first_time = true;

void Load_info_File() {
	if (s_infoLoaded) {
		return;
	}

	const bool loadedFromPrefs = loadPreferences();
	const bool loadedFromFile	= loadedFromPrefs ? false : loadLegacyFile();
	s_infoLoaded				= true;

	if (loadedFromPrefs || loadedFromFile) {
		Serial.println("[CONFIG] Loaded board configuration.");
	}
	else {
		Serial.println("[CONFIG] No saved configuration found; using compiled defaults.");
	}
}

void Delete_info_File() {
	Serial.println("[CONFIG] Factory reset requested. Clearing saved configuration...");

	Preferences prefs;
	if (prefs.begin(PREF_NAMESPACE, false)) {
		prefs.clear();
		prefs.putBool(FACTORY_RESET_KEY, true);
		prefs.end();
	}

	if (ensureLittleFs() && LittleFS.exists(LEGACY_INFO_FILE)) {
		LittleFS.remove(LEGACY_INFO_FILE);
	}

	delay(200);
	ESP.restart();
}

void Save_info_File(String wifiSsid, String wifiPass, String coreIotToken,
					String coreIotServer, String coreIotPort) {
	WIFI_SSID		= cleanString(wifiSsid);
	WIFI_PASS		= wifiPass;
	CORE_IOT_TOKEN	= cleanString(coreIotToken);
	CORE_IOT_SERVER = cleanString(coreIotServer);
	CORE_IOT_PORT	= String(parsePort(coreIotPort));

	savePreferences();
	s_infoLoaded = true;

	Serial.println("[CONFIG] Configuration saved.");
}

bool check_info_File(bool check) {
	if (!check) {
		Load_info_File();
	}

	if (hasRequiredConfig()) {
		is_first_time = false;
		return true;
	}

	if (!check) {
		is_first_time = false;
		Serial.println("[CONFIG] Missing WiFi/MQTT configuration. Starting config portal.");
		startAP();
		Webserver_reconnect();
	}

	return false;
}
