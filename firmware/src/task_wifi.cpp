#include "task_wifi.h"

namespace {
bool s_apActive			   = false;
bool s_internetSignalGiven = false;

const char *configApSsid() {
#ifdef BOARD_CONFIG_AP_SSID
	return BOARD_CONFIG_AP_SSID;
#else
	return "HERA-Board-Config";
#endif
}

const char *configApPass() {
#ifdef BOARD_CONFIG_AP_PASS
	return BOARD_CONFIG_AP_PASS;
#else
	return "12345678";
#endif
}

void giveInternetReadySignal() {
	if (xBinarySemaphoreInternet != NULL && !s_internetSignalGiven) {
		xSemaphoreGive(xBinarySemaphoreInternet);
		s_internetSignalGiven = true;
	}
}
} // namespace

bool wifiHasCredentials() {
	String ssid = WIFI_SSID;
	ssid.trim();
	return ssid.length() > 0;
}

bool startAP() {
	WiFi.disconnect(false, false);
	WiFi.mode(WIFI_AP);
	const bool ok = WiFi.softAP(configApSsid(), configApPass());
	s_apActive	   = ok;
	isWifiConnected	   = false;

	Serial.print("[WIFI] Config AP SSID: ");
	Serial.println(configApSsid());
	Serial.print("[WIFI] Config AP IP: ");
	Serial.println(WiFi.softAPIP());
	return ok;
}

bool stopAP() {
	if (!s_apActive && WiFi.getMode() != WIFI_AP && WiFi.getMode() != WIFI_AP_STA) {
		return true;
	}

	WiFi.softAPdisconnect(true);
	s_apActive = false;

	if (WiFi.status() == WL_CONNECTED || wifiHasCredentials()) {
		WiFi.mode(WIFI_STA);
	}
	else {
		WiFi.mode(WIFI_OFF);
	}

	Serial.println("[WIFI] Config AP stopped.");
	return true;
}

bool startSTA(uint32_t timeoutMs) {
	if (!wifiHasCredentials()) {
		Serial.println("[WIFI] Missing SSID. STA connection skipped.");
		isWifiConnected = false;
		return false;
	}

	if (s_apActive) {
		WiFi.softAPdisconnect(true);
		s_apActive = false;
	}

	WiFi.mode(WIFI_STA);
	WiFi.setSleep(false);
	WiFi.disconnect(false, false);

	Serial.print("[WIFI] Connecting to SSID: ");
	Serial.println(WIFI_SSID);

	if (WIFI_PASS.isEmpty()) {
		WiFi.begin(WIFI_SSID.c_str());
	}
	else {
		WiFi.begin(WIFI_SSID.c_str(), WIFI_PASS.c_str());
	}

	const unsigned long startMs = millis();
	while (WiFi.status() != WL_CONNECTED && millis() - startMs < timeoutMs) {
		vTaskDelay(pdMS_TO_TICKS(250));
	}

	isWifiConnected = (WiFi.status() == WL_CONNECTED);

	if (isWifiConnected) {
		Serial.print("[WIFI] Connected. IP: ");
		Serial.println(WiFi.localIP());
		giveInternetReadySignal();
		return true;
	}

	Serial.println("[WIFI] STA connect timeout.");
	return false;
}

bool Wifi_reconnect(uint32_t timeoutMs) {
	const wl_status_t status = WiFi.status();

	if (status == WL_CONNECTED) {
		isWifiConnected = true;
		giveInternetReadySignal();
		return true;
	}

	isWifiConnected = false;
	return startSTA(timeoutMs);
}
