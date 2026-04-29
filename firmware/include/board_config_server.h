#ifndef BOARD_CONFIG_SERVER_H
#define BOARD_CONFIG_SERVER_H

#include <Arduino.h>

void board_config_server_task(void *pvParameters);
void load_board_config_from_storage();
void save_board_config_to_storage();

#endif
