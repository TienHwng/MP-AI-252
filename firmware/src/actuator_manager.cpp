// --- TRONG FILE: src/actuator_manager.cpp ---
#include "actuator_manager.h"

const uint8_t DEVICE_PINS[NUM_DEVICES] = {
    RELAY_1_PIN,
    RELAY_2_PIN,
    RELAY_3_PIN,
    RELAY_4_PIN
};

// 2. Mảng chứa trạng thái hiện tại của từng thiết bị
static bool device_states[NUM_DEVICES] = {false, false, false, false}; // Mặc định tắt hết

// Hàm khởi tạo: Tự động lặp qua tất cả thiết bị để setup
void actuator_init() {
    Serial.println("[INIT] Actuator Manager initializing...");
    for (int i = 0; i < NUM_DEVICES; i++) {
        pinMode(DEVICE_PINS[i], OUTPUT);
        digitalWrite(DEVICE_PINS[i], LOW); // Tắt khi mới cấp nguồn
        device_states[i] = false;
    }
}

// Hàm cốt lõi 1: Ra lệnh ép thiết bị BẬT hoặc TẮT
void set_device_state(DeviceID id, bool state) {
    if (id >= NUM_DEVICES) return; // Bảo vệ lỗi truyền sai ID

    // Cập nhật mảng trạng thái
    device_states[id] = state;
    
    // Xuất tín hiệu ra chân vật lý tương ứng
    digitalWrite(DEVICE_PINS[id], state ? HIGH : LOW);
    
    if (IS_DEBUG_MODE) {
        Serial.printf("[ACTUATOR] Device ID %d -> %s\n", id, state ? "ON" : "OFF");
    }
}

// Hàm cốt lõi 2: Đảo trạng thái thiết bị (Đang bật thành tắt, tắt thành bật)
void toggle_device_state(DeviceID id) {
    if (id >= NUM_DEVICES) return;
    set_device_state(id, !device_states[id]); // Gọi lại hàm trên với trạng thái ngược lại
}

// Hàm cốt lõi 3: Lấy trạng thái hiện tại (Để in ra LCD hoặc gửi lên web)
bool get_device_state(DeviceID id) {
    if (id >= NUM_DEVICES) return false;
    return device_states[id];
}