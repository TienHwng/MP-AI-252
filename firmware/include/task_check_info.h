#ifndef __TASK_CHECK_INFO_H__
#define __TASK_CHECK_INFO_H__

#include <Arduino.h>

bool check_info_File(bool check);
void Load_info_File();
void Delete_info_File();
void Save_info_File(String wifiSsid, String wifiPass, String coreIotToken, String coreIotServer, String coreIotPort);

#endif
