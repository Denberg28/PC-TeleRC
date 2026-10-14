// TeleRC bridge dropout-diagnostic candidate 0.1.4, 2026-10-14
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <esp_system.h>
#include <cstring>

// ESP32-S3 DevKitC-1 example. Change GPIOs if your S3 board exposes different pins.
// FC T3 -> GPIO18 (RX); FC R3 <- GPIO17 (TX); FC GND <-> ESP GND.
constexpr int FC_RX_GPIO = 18;
constexpr int FC_TX_GPIO = 17;
// 0 = original Wi-Fi bridge; 1 = ELRS receiver MAVLink UART relay.
#ifndef TELERC_LINK_MODE
#define TELERC_LINK_MODE 0
#endif
static_assert(TELERC_LINK_MODE == 0 || TELERC_LINK_MODE == 1, "Invalid link mode");
constexpr bool ELRS_MODE = TELERC_LINK_MODE == 1;
constexpr uint32_t FC_BAUD = ELRS_MODE ? 460800 : 115200;
constexpr int ELRS_RX_GPIO = 16; // ELRS receiver TX -> ESP GPIO16
constexpr int ELRS_TX_GPIO = 15; // ELRS receiver RX <- ESP GPIO15
HardwareSerial elrs(2);
// This sketch relays native MAVLink. It does not implement ELRS RF or CRSF.
uint8_t elrsFrame[280];
uint16_t elrsSize = 0, elrsExpected = 0;
uint32_t elrsByteMs = 0;
uint32_t elrsFramesSeen = 0;

constexpr uint16_t UDP_PORT = 14550;
const char DISCOVERY[] = "TELERC_DISCOVER_V1"; // routing only; never sent to the FC
const char DISCONNECT[] = "TELERC_DISCONNECT_V1";
const char AP_SSID[] = "TeleRC-Rover";
// Fixed WPA2 AP password. No application Preferences/NVS dependency.
const char PERSONAL_AP_PASSWORD[] = "telerc123";
static_assert(sizeof(PERSONAL_AP_PASSWORD) >= 9 && sizeof(PERSONAL_AP_PASSWORD) <= 64,
              "Wi-Fi password must contain 8-63 characters");
constexpr uint32_t WIFI_RETRY_MS = 2000;
bool apReady = false, udpReady = false;
uint32_t lastWifiAttemptMs = 0, lastUdpAttemptMs = 0, lastWifiCheckMs = 0;
uint32_t wifiAttempts = 0;
const char* wifiState = "starting";
const IPAddress AP_IP(192, 168, 4, 1);
const IPAddress AP_BROADCAST(192, 168, 4, 255);

HardwareSerial fc(1);
void consumeElrsByte(uint8_t b) {
  if (elrsSize && millis() - elrsByteMs > 100) {
    elrsSize = 0;
    elrsExpected = 0;
  }
  elrsByteMs = millis();
  if (!elrsSize && b != 0xfe && b != 0xfd) return;
  elrsFrame[elrsSize++] = b;
  if (elrsSize == 3) {
    const bool v2 = elrsFrame[0] == 0xfd;
    elrsExpected = (v2 ? 10 : 6) + elrsFrame[1] + 2 +
                   ((v2 && (elrsFrame[2] & 1)) ? 13 : 0);
    if (elrsExpected > sizeof(elrsFrame)) {
      elrsSize = 0;
      elrsExpected = 0;
      return;
    }
  }
  if (elrsExpected && elrsSize == elrsExpected) {
    // Preserve CRC/signature and source IDs. FC validates the MAVLink message.
    // No generated overrides/ARM; FC owns ELRS RC and loss-of-link failsafes.
    fc.write(elrsFrame, elrsSize);
    elrsFramesSeen++;
    elrsSize = 0;
    elrsExpected = 0;
  }
}

WiFiUDP udp;
IPAddress phone(0, 0, 0, 0);
uint32_t lastPhonePacketMs = 0;
uint32_t lastControlMs = 0;
bool controlActive = false;
uint8_t ownedChannels = 0;
bool neutralRequired = true;
uint32_t controlTimeouts = 0;
uint32_t neutralRejects = 0, uartShortWrites = 0;
uint32_t lastStopAtMs = 0, lastStopGapMs = 0, maxControlGapMs = 0;
const char* lastStopReason = "startup";
int bootResetReason = 0;
char usbDiagnostic[512];
size_t usbLength = 0, usbOffset = 0;
void serviceUsbDiagnostic() {
  if (usbOffset >= usbLength) return;
  int room = Serial.availableForWrite();
  if (room <= 0) return;
  size_t n = usbLength - usbOffset;
  if (n > 32) n = 32;
  if (n > static_cast<size_t>(room)) n = static_cast<size_t>(room);
  usbOffset += Serial.write(reinterpret_cast<const uint8_t*>(usbDiagnostic + usbOffset), n);
}
uint8_t targetSystem = 0;
uint8_t bridgeSequence = 0;

uint8_t serialFrame[280];
uint16_t serialSize = 0;
uint16_t serialExpected = 0;
uint32_t serialByteMs = 0;
uint32_t serialBytesSeen = 0;
uint32_t serialFramesSeen = 0;
uint32_t lastDiagnosticMs = 0;

// Passive diagnostics for phone-to-bridge control packets.
uint32_t diagnosticReceived = 0;
uint32_t diagnosticAccepted = 0;
uint32_t diagnosticUartTxBytes = 0;
uint16_t diagnosticSteer = 1500;
uint16_t diagnosticDrive = 1500;

uint16_t crcByte(uint16_t crc, uint8_t byte) {
  uint8_t tmp = byte ^ (crc & 0xff);
  tmp ^= tmp << 4;
  return (crc >> 8) ^ (uint16_t(tmp) << 8) ^ (uint16_t(tmp) << 3) ^ (tmp >> 4);
}

// Only TeleRC's complete MAVLink 1 RC_CHANNELS_OVERRIDE commands enter the FC.
// This filters malformed packets; CRC and source ID are not authentication.
bool validTeleRcCommand(const uint8_t *p, size_t n) {
  if (n != 26 || p[0] != 0xfe || p[1] != 18 || p[3] != 255 ||
      p[4] != 190 || p[5] != 70 || p[22] == 0 || p[22] == 255 || p[23] != 1)
    return false;
  uint16_t crc = 0xffff;
  for (size_t i = 1; i < 24; ++i) crc = crcByte(crc, p[i]);
  // Accept TeleRC 0.8.9's legacy CRC during migration; FC always gets CRC 124.
  const uint16_t standardCrc = crcByte(crc, 124);
  const uint16_t legacyCrc = crcByte(crc, 50);
  const uint16_t receivedCrc = uint16_t(p[24]) | (uint16_t(p[25]) << 8);
  if (receivedCrc != standardCrc && receivedCrc != legacyCrc) return false;
  bool active = false, release = false, addressed = false;
  for (int channel = 0; channel < 8; ++channel) {
    const uint16_t value = uint16_t(p[6 + channel * 2]) |
                           (uint16_t(p[7 + channel * 2]) << 8);
    if (value == 65535) continue; // PC TeleRC leaves unused channels alone.
    if (channel >= 4) return false; // Preserve original four-channel scope.
    addressed = true;
    if (value == 0) release = true;
    else if (value >= 1000 && value <= 2000) active = true;
    else return false;
  }
  return addressed && !(active && release);
}

uint16_t channelValue(const uint8_t* p, uint8_t channel) {
  return uint16_t(p[6 + channel * 2]) | (uint16_t(p[7 + channel * 2]) << 8);
}

// PC TeleRC's GCS heartbeat and explicit normal ARM/DISARM requests.
// This is a whitelist, not an arbitrary MAVLink command tunnel over Wi-Fi.
bool validPcAuxiliary(const uint8_t* p, size_t n) {
  if (n < 8 || p[0] != 0xfe || p[3] != 255 || p[4] != 190) return false;
  uint8_t extra = 0;
  if (n == 17 && p[1] == 9 && p[5] == 0 && p[10] == 6 && p[14] == 3) {
    extra = 50;
  } else if (n == 41 && p[1] == 33 && p[5] == 76 &&
             p[34] == 0x90 && p[35] == 0x01 && p[36] > 0 &&
             p[36] < 255 && p[37] == 1) {
    // param1 float is exactly 0 or 1; all other params zero (no force magic).
    if (p[6] || p[7] || !((p[8] == 0 && p[9] == 0) ||
                         (p[8] == 0x80 && p[9] == 0x3f))) return false;
    for (size_t i = 10; i < 34; ++i) if (p[i]) return false;
    if (ownedChannels && p[36] != targetSystem) return false;
    extra = 152;
  } else return false;
  uint16_t crc = 0xffff;
  for (size_t i = 1; i < n - 2; ++i) crc = crcByte(crc, p[i]);
  crc = crcByte(crc, extra);
  return crc == (uint16_t(p[n-2]) | uint16_t(p[n-1]) << 8);
}

// Recompute CRC before UART so even legacy app packets decode on ArduRover.
size_t writeFcCommand(uint8_t *p, size_t n) {
  uint16_t crc = 0xffff;
  for (size_t i = 1; i < 24; ++i) crc = crcByte(crc, p[i]);
  crc = crcByte(crc, 124);
  p[24] = uint8_t(crc);
  p[25] = uint8_t(crc >> 8);
  return fc.write(p, n);
}

void sendOverride(uint16_t value) {
  uint8_t p[26] = {0xfe, 18, bridgeSequence++, 255, 190, 70};
  for (int i = 0; i < 4; ++i) {
    const uint16_t output = (ownedChannels & (1U << i)) ? value : 65535;
    p[6 + i * 2] = uint8_t(output);
    p[7 + i * 2] = uint8_t(output >> 8);
  }
  for (int i = 4; i < 8; ++i) {
    p[6 + i * 2] = 0xff;
    p[7 + i * 2] = 0xff;
  }
  p[22] = targetSystem;
  p[23] = 1;
  uint16_t crc = 0xffff;
  for (size_t i = 1; i < 24; ++i) crc = crcByte(crc, p[i]);
  crc = crcByte(crc, 124);
  p[24] = uint8_t(crc);
  p[25] = uint8_t(crc >> 8);
  fc.write(p, sizeof(p));
}

// This helper owns only channels previously accepted from the current client.
void stopWifiControl(const char* reason = "release") {
  if (controlActive) {
    lastStopReason = reason;
    lastStopAtMs = millis();
    lastStopGapMs = millis() - lastControlMs;
  }
  if (ownedChannels && targetSystem) {
    sendOverride(1500);
    sendOverride(0);
  }
  ownedChannels = 0;
  controlActive = false;
  neutralRequired = true;
}

bool acceptOverride(uint8_t* p, size_t count) {
  if (!validTeleRcCommand(p, count)) return false;
  bool release = false, neutral = true;
  uint8_t mask = 0;
  for (uint8_t i = 0; i < 4; ++i) {
    uint16_t value = channelValue(p, i);
    if (value == 65535) continue;
    mask |= 1U << i;
    if (value == 0) release = true;
    else if (value < 1465 || value > 1535) neutral = false;
  }
  if (ownedChannels && targetSystem != p[22]) return false;
  if (!release && neutralRequired && !neutral) { ++neutralRejects; return false; }
  // Releasing a channel we do not own must not disturb a transmitter.
  if (release && !(mask & ownedChannels)) return true;
  if (release) {
    for (uint8_t i = 0; i < 4; ++i) {
      if (!(ownedChannels & (1U << i))) p[6+i*2] = p[7+i*2] = 0xff;
    }
  }
  targetSystem = p[22];
  // Track before write so a short UART write also triggers best-effort release.
  if (!release) ownedChannels |= mask;
  const size_t written = writeFcCommand(p, count);
  diagnosticUartTxBytes += written;
  if (written != count) { ++uartShortWrites; stopWifiControl("uart-short"); return false; }
  if (controlActive) {
    const uint32_t gap = millis() - lastControlMs;
    if (gap > maxControlGapMs) maxControlGapMs = gap;
  }
  if (release) ownedChannels &= ~mask;
  else neutralRequired = false;
  controlActive = ownedChannels != 0;
  if (!controlActive) neutralRequired = true;
  lastControlMs = millis();
  diagnosticSteer = channelValue(p, 0);
  diagnosticDrive = channelValue(p, 1); // PC CH1/CH2 default
  diagnosticAccepted++;
  return true;
}

void toPhone(const uint8_t *frame, size_t length) {
  if (ELRS_MODE) {
    elrs.write(frame, length);
    return;
  }
  // TeleRC sends nothing before a heartbeat. Broadcast full frames until we
  // learn its address from a command, then use that address for five seconds.
  IPAddress destination =
      (phone != IPAddress(0, 0, 0, 0) && millis() - lastPhonePacketMs < 5000)
          ? phone : AP_BROADCAST;
  if (udp.beginPacket(destination, UDP_PORT)) {
    udp.write(frame, length);
    udp.endPacket(); // UDP source port is also 14550 (the bound socket).
  }
}

void consumeFcByte(uint8_t b) {
  serialBytesSeen++;
  if (serialSize && millis() - serialByteMs > 100) {
    serialSize = 0;
    serialExpected = 0;
  }
  serialByteMs = millis();
  if (!serialSize && b != 0xfe && b != 0xfd) return;
  serialFrame[serialSize++] = b;
  if (serialSize == 3) {
    bool v2 = serialFrame[0] == 0xfd;
    serialExpected = (v2 ? 10 : 6) + serialFrame[1] + 2 +
                     ((v2 && (serialFrame[2] & 1)) ? 13 : 0);
    if (serialExpected > sizeof(serialFrame)) {
      serialSize = 0;
      serialExpected = 0;
      return;
    }
  }
  if (serialExpected && serialSize == serialExpected) {
    serialFramesSeen++;
    toPhone(serialFrame, serialSize);
    serialSize = 0;
    serialExpected = 0;
  }
}

// Retry only failed startup or a detected AP-mode/IP loss. Zero clients is normal.
void serviceWifi() {
  const uint32_t now = millis();
  if (apReady && uint32_t(now - lastWifiCheckMs) >= 1000) {
    lastWifiCheckMs = now;
    if (!(WiFi.getMode() & WIFI_AP) || WiFi.softAPIP() != AP_IP) {
      stopWifiControl("ap-lost");
      udp.stop();
      apReady = udpReady = false;
      phone = IPAddress(0, 0, 0, 0);
      wifiState = "ap-lost";
      lastWifiAttemptMs = now - WIFI_RETRY_MS;
    }
  }
  if (!apReady && uint32_t(now - lastWifiAttemptMs) >= WIFI_RETRY_MS) {
    lastWifiAttemptMs = now;
    ++wifiAttempts;
    WiFi.mode(WIFI_OFF);
    if (!WiFi.mode(WIFI_AP)) { wifiState = "mode-failed"; return; }
    if (!WiFi.softAPConfig(AP_IP, AP_IP, IPAddress(255,255,255,0))) {
      wifiState = "ip-failed"; WiFi.mode(WIFI_OFF); return;
    }
    // Explicitly broadcast SSID on channel 1; allow up to four clients.
    if (!WiFi.softAP(AP_SSID, PERSONAL_AP_PASSWORD, 1, 0, 4)) {
      wifiState = "ap-start-failed"; WiFi.mode(WIFI_OFF); return;
    }
    apReady = true;
    lastWifiCheckMs = now;
    wifiState = "ap-ready";
    lastUdpAttemptMs = now - WIFI_RETRY_MS;
  }
  if (apReady && !udpReady && uint32_t(now - lastUdpAttemptMs) >= WIFI_RETRY_MS) {
    lastUdpAttemptMs = now;
    udpReady = udp.begin(UDP_PORT);
    wifiState = udpReady ? "ready" : "udp-retry";
  }
}

void setup() {
  bootResetReason = static_cast<int>(esp_reset_reason());
  Serial.begin(115200);
  fc.setRxBufferSize(4096);
  fc.begin(FC_BAUD, SERIAL_8N1, FC_RX_GPIO, FC_TX_GPIO);
  if (ELRS_MODE) {
    WiFi.mode(WIFI_OFF);
    elrs.setRxBufferSize(4096);
    elrs.begin(460800, SERIAL_8N1, ELRS_RX_GPIO, ELRS_TX_GPIO);
    const int n = snprintf(usbDiagnostic, sizeof(usbDiagnostic),
      "ROLE=BRIDGE v0.1.4 MODE=ELRS WiFi=OFF; set TELERC_LINK_MODE=0 for TeleRC-Rover; reset=%d\n",
      bootResetReason);
    usbLength = n > 0 && n < int(sizeof(usbDiagnostic)) ? size_t(n) : 0;
  } else {
    lastWifiAttemptMs = millis() - WIFI_RETRY_MS;
    serviceWifi();
    const int n = snprintf(usbDiagnostic, sizeof(usbDiagnostic),
      "ROLE=BRIDGE v0.1.4 MODE=WIFI SSID=TeleRC-Rover channel=1 visible=1 IP=192.168.4.1 state=%s reset=%d\n",
      wifiState, bootResetReason);
    usbLength = n > 0 && n < int(sizeof(usbDiagnostic)) ? size_t(n) : 0;
  }
  usbOffset = 0;
  serviceUsbDiagnostic();
}

void loop() {
  if (ELRS_MODE) {
    for (int n = 0; n < 512 && elrs.available(); ++n)
      consumeElrsByte(uint8_t(elrs.read()));
    for (int n = 0; n < 512 && fc.available(); ++n)
      consumeFcByte(uint8_t(fc.read()));
    if (millis() - lastDiagnosticMs >= 3000) {
      lastDiagnosticMs = millis();
      if (usbOffset >= usbLength) {
        const int n = snprintf(usbDiagnostic, sizeof(usbDiagnostic),
          "ROLE=BRIDGE MODE=ELRS WiFi=OFF up=%lu reset=%d%s RXframes=%lu FCframes=%lu\n",
          static_cast<unsigned long>(millis()), bootResetReason,
          bootResetReason == ESP_RST_BROWNOUT ? "/brownout" : "",
          static_cast<unsigned long>(elrsFramesSeen),
          static_cast<unsigned long>(serialFramesSeen));
        usbLength = n > 0 && n < int(sizeof(usbDiagnostic)) ? size_t(n) : 0;
        usbOffset = 0;
      }
    }
    serviceUsbDiagnostic();
    delay(1);
    return;
  }
  if (controlActive && millis() - lastControlMs >= 500) {
    ++controlTimeouts;
    stopWifiControl("command-timeout");
  }
  serviceWifi();
  if (!apReady || !udpReady) {
    if (millis() - lastDiagnosticMs >= 3000 && usbOffset >= usbLength) {
      lastDiagnosticMs = millis();
      const int n = snprintf(usbDiagnostic, sizeof(usbDiagnostic),
        "ROLE=BRIDGE MODE=WIFI SSID=TeleRC-Rover state=%s attempts=%lu up=%lu reset=%d\n",
        wifiState, static_cast<unsigned long>(wifiAttempts),
        static_cast<unsigned long>(millis()), bootResetReason);
      usbLength = n > 0 && n < int(sizeof(usbDiagnostic)) ? size_t(n) : 0;
      usbOffset = 0;
    }
    serviceUsbDiagnostic();
    delay(1);
    return;
  }
  int packetSize = udp.parsePacket();
  if (packetSize > 0) {
    const IPAddress sender = udp.remoteIP();
    const uint16_t senderPort = udp.remotePort();
    uint8_t p[280];
    int count = udp.read(p, sizeof(p));
    if (packetSize == 26) diagnosticReceived++;
    while (udp.available()) udp.read();
    bool local = sender[0] == 192 && sender[1] == 168 && sender[2] == 4 &&
                 sender[3] > 1 && sender[3] < 255;
    bool paired = phone == IPAddress(0, 0, 0, 0) || phone == sender ||
                  millis() - lastPhonePacketMs >= 5000;
    if (packetSize == sizeof(DISCOVERY) - 1 && count == packetSize &&
        senderPort == UDP_PORT && local && paired &&
        memcmp(p, DISCOVERY, sizeof(DISCOVERY) - 1) == 0) {
      phone = sender;
      lastPhonePacketMs = millis();
    } else if (packetSize == sizeof(DISCONNECT) - 1 && count == packetSize &&
        sender == phone && senderPort == UDP_PORT && local &&
        memcmp(p, DISCONNECT, sizeof(DISCONNECT) - 1) == 0) {
      stopWifiControl("disconnect");
      phone = IPAddress(0, 0, 0, 0);
    } else if (packetSize == 26 && count == 26 && senderPort == UDP_PORT && local &&
        paired && acceptOverride(p, count)) {
      phone = sender;
      lastPhonePacketMs = millis();
    } else if (count == packetSize && senderPort == UDP_PORT && local &&
               paired && validPcAuxiliary(p, size_t(count))) {
      if (p[5] == 76 && p[8] == 0 && p[9] == 0) stopWifiControl("disarm");
      if (fc.write(p, size_t(count)) != size_t(count)) { ++uartShortWrites; stopWifiControl("uart-short"); }
      phone = sender;
      lastPhonePacketMs = millis();
    }
  }
  for (int n = 0; n < 512 && fc.available(); ++n)
    consumeFcByte(uint8_t(fc.read()));
  if (millis() - lastDiagnosticMs >= 3000) {
    lastDiagnosticMs = millis();
    if (phone != IPAddress(0, 0, 0, 0) && millis() - lastPhonePacketMs < 5000) {
      char report[80];
      int length = snprintf(report, sizeof(report), "TELERC_STATUS_V1,%lu,%lu",
                            static_cast<unsigned long>(serialBytesSeen),
                            static_cast<unsigned long>(serialFramesSeen));
      if (length > 0 && length < int(sizeof(report)) && udp.beginPacket(phone, UDP_PORT)) {
        udp.write(reinterpret_cast<const uint8_t *>(report), size_t(length));
        udp.endPacket();
      }
    }
    if (usbOffset >= usbLength) {
      const int n = snprintf(usbDiagnostic, sizeof(usbDiagnostic),
        "ROLE=BRIDGE MODE=WIFI AP=ready SSID=TeleRC-Rover up=%lu reset=%d%s RX=%lu accepted=%lu timeout=%lu mask=%u neutralWait=%u CH1=%u CH2=%u last=%s at=%lu gapMs=%lu maxGapMs=%lu neutralReject=%lu uartShort=%lu\n",
        static_cast<unsigned long>(millis()), bootResetReason,
        bootResetReason == ESP_RST_BROWNOUT ? "/brownout" : "",
        static_cast<unsigned long>(diagnosticReceived),
        static_cast<unsigned long>(diagnosticAccepted),
        static_cast<unsigned long>(controlTimeouts), ownedChannels,
        unsigned(neutralRequired), diagnosticSteer, diagnosticDrive,
        lastStopReason, static_cast<unsigned long>(lastStopAtMs),
        static_cast<unsigned long>(lastStopGapMs), static_cast<unsigned long>(maxControlGapMs),
        static_cast<unsigned long>(neutralRejects), static_cast<unsigned long>(uartShortWrites));
      usbLength = n > 0 && n < int(sizeof(usbDiagnostic)) ? size_t(n) : 0;
      usbOffset = 0;
    }
  }
  serviceUsbDiagnostic();
  delay(1);
}
