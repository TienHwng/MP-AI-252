#include "ir_receiver.h"
#include <IRremote.h>


void setup_ir_receiver() {
    Serial.printf("[IR] IR_RECEIVE_PIN=%d\n", IR_RECEIVE_PIN);

    // IrReceiver.begin(IR_RECEIVE_PIN, ENABLE_LED_FEEDBACK, 48);
    IrReceiver.begin(IR_RECEIVE_PIN, DISABLE_LED_FEEDBACK);
    Serial.println("[IR] begin OK");

    if (IS_DEBUG_MODE || 1) {
        Serial.printf("[IR] Listening on GPIO %d\n", IR_RECEIVE_PIN);
    }
}

void ir_receiver_task(void *pvParameters) {
    setup_ir_receiver();

    while (1) {
        if (IrReceiver.decode()) {
            const uint16_t address = IrReceiver.decodedIRData.address;
            const uint16_t command = IrReceiver.decodedIRData.command;
            const uint8_t  flags   = IrReceiver.decodedIRData.flags;
            const uint8_t  proto   = IrReceiver.decodedIRData.protocol;

            Serial.printf("[IR] proto %u, addr 0x%04X, cmd 0x%04X, flags 0x%02X\n", proto, address, command, flags);

            IrReceiver.resume();
        }

        vTaskDelay(pdMS_TO_TICKS(10));
    }
}
