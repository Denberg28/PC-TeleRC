#pragma once
#include <stdint.h>

namespace config {
constexpr char VERSION[] = "0.1.0-test-candidate";
constexpr char WIFI_SSID[] = "TeleRC-MiniRover";
constexpr char WIFI_PASSWORD[] = "telerc123"; // Change here before upload; >=8 characters.
constexpr uint16_t UDP_PORT = 14550;
constexpr uint8_t SYSTEM_ID = 1;
constexpr uint8_t COMPONENT_ID = 1;
constexpr uint8_t GCS_SYSTEM_ID = 255;
constexpr uint8_t GCS_COMPONENT_ID = 190;
constexpr uint32_t CONTROL_TIMEOUT_MS = 500;
constexpr uint32_t PEER_TIMEOUT_MS = 3000;
constexpr uint32_t NEUTRAL_HOLD_MS = 250;
constexpr uint32_t MOTOR_TICK_MS = 5;
constexpr uint32_t REVERSAL_COAST_MS = 30;
constexpr uint32_t PWM_HZ = 20000;
constexpr uint8_t MAX_PWM = 180; // 180/255=71%; not a current limit.
constexpr int RC_DEADBAND_US = 25;
constexpr float STEER_GAIN = 0.50f; // Additional onboard skid-steer limit.
constexpr int BOOT_STOP_PIN = 0;
constexpr int STATUS_LED_PIN = 21; // External ordinary LED + 330 ohm; -1 disables.
// Motor order: left front, left rear, right front, right rear.
constexpr uint8_t MOTOR_PINS[4][2] = {{4,5},{6,7},{8,9},{10,11}};
constexpr bool MOTOR_INVERT[4] = {false,false,false,false};
static_assert(sizeof(WIFI_PASSWORD) >= 9 && sizeof(WIFI_PASSWORD) <= 64,
              "Wi-Fi password must be 8..63 characters");
static_assert(SYSTEM_ID > 0 && SYSTEM_ID < 255, "Invalid vehicle system ID");
static_assert(STEER_GAIN > 0 && STEER_GAIN <= 1, "Invalid steering gain");
}
