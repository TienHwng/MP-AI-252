#include "actuator_manager.h"

const uint8_t DEVICE_PINS[NUM_DEVICES] = {
    DIGITAL_PORT_1_PIN,
    DIGITAL_PORT_2_PIN,
    DIGITAL_PORT_3_PIN,
    DIGITAL_PORT_4_PIN
};

static bool device_states[NUM_DEVICES] = {
    false, 
    false, 
    false, 
    false
};

void actuator_init() {
    Serial.println("[INIT] Actuator Manager initializing...");
    
    for (int i = 0; i < NUM_DEVICES; i++) {
        pinMode(DEVICE_PINS[i], OUTPUT);
        digitalWrite(DEVICE_PINS[i], LOW); // Tắt khi mới cấp nguồn
        device_states[i] = false;
    }
}

void set_device_state(DeviceID id, bool state) {
    if (id >= NUM_DEVICES) return; // Bảo vệ lỗi truyền sai ID

    device_states[id] = state;
    
    digitalWrite(DEVICE_PINS[id], state ? HIGH : LOW);
    
    if (IS_DEBUG_MODE) {
        Serial.printf("[ACTUATOR] Device ID %d -> %s\n", id, state ? "ON" : "OFF");
    }
}

void toggle_device_state(DeviceID id) {
    if (id >= NUM_DEVICES) return;
    set_device_state(id, !device_states[id]);
}

bool get_device_state(DeviceID id) {
    if (id >= NUM_DEVICES) return false;
    return device_states[id];
}