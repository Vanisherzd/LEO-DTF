/*
 * lr1121_controlled_packet_source
 * -------------------------------
 * Gated conducted packet-source firmware for LEO-DTF H1B/H1C on a
 * Nucleo-64 (NUCLEO_L476RG) carrying an LR1121.
 *
 * SAFETY CONTRACT (do not weaken):
 *   - Boots with TX DISABLED (RF_TRANSMISSION_ENABLED=false).
 *   - NEVER auto-transmits in setup() or loop().
 *   - send_test_packet REFUSES unless arm_tx was confirmed in this session.
 *   - arm_tx requires a second confirmation token: "arm_tx CONFIRM_CONDUCTED_TEST".
 *   - The actual RF emission path is additionally gated behind a compile-time
 *     macro ENABLE_REAL_TX (default 0). With ENABLE_REAL_TX==0, even an armed
 *     send_test_packet performs NO RF and logs TX_EXECUTED=false.
 *   - Default packet count = 1. Conservative power placeholder; never max power.
 *   - Conducted/shielded use only. No antenna. No OTA.
 *   - This firmware does NOT prove HIL/OTA/hardware validation.
 *
 * Triple gate before any RF can leave this board:
 *   (1) compile with -DENABLE_REAL_TX=1  (default 0 => no RF code path)
 *   (2) arm_tx CONFIRM_CONDUCTED_TEST    (runtime arm)
 *   (3) send_test_packet                 (explicit single command)
 */

#include <SPI.h>

#ifndef ENABLE_REAL_TX
#define ENABLE_REAL_TX 0   // default: NO real RF emission compiled in
#endif

static const char *FW_NAME    = "lr1121_controlled_packet_source";
static const char *FW_VERSION = "0.1.0";
static const char *BOARD_TGT  = "STMicroelectronics:stm32:Nucleo_64:pnum=NUCLEO_L476RG";
static const long  SERIAL_BAUD = 115200;

// Boot-time safety flags.
static const bool HIL_VALIDATION_COMPLETE      = false;
static const bool OTA_VALIDATION_COMPLETE      = false;
static const bool HARDWARE_VALIDATION_COMPLETE = false;

// Locked LR1121 pin map (confirmed in H0.5C).
static const int PIN_LR_NSS   = D7;
static const int PIN_LR_BUSY  = D3;
static const int PIN_LR_RESET = D9;
static const int PIN_LR_DIO   = D5;

// Conservative defaults.
static const uint32_t CENTER_FREQUENCY_HZ = 915000000UL;
static const uint16_t PACKET_DURATION_MS_PLACEHOLDER = 0;  // unknown until measured
static const char *MODULATION_CONFIG = "placeholder_conservative";
static const int DEFAULT_PACKET_COUNT = 1;

static const uint16_t LR_CMD_GET_VERSION = 0x0101;
static const uint8_t  LR_DEVICE_LR1121   = 0x03;
static SPISettings g_spi(2000000, MSBFIRST, SPI_MODE0);

// Runtime state.
static bool g_rf_transmission_enabled = false;  // never set true unless real TX is compiled AND armed AND executed
static bool g_armed = false;
static bool g_tx_executed = false;
static int  g_packet_index = 0;
static bool g_init_verified = false;
static uint8_t g_raw[5] = {0};

static bool waitBusyLow(uint32_t timeout_ms) {
  uint32_t t0 = millis();
  while (digitalRead(PIN_LR_BUSY) == HIGH) {
    if (millis() - t0 > timeout_ms) return false;
  }
  return true;
}

static void pinsInit() {
  pinMode(PIN_LR_NSS, OUTPUT); digitalWrite(PIN_LR_NSS, HIGH);
  pinMode(PIN_LR_RESET, OUTPUT); digitalWrite(PIN_LR_RESET, HIGH);
  pinMode(PIN_LR_BUSY, INPUT);
  pinMode(PIN_LR_DIO, INPUT);
  SPI.begin();
}

static void lrReset() {
  digitalWrite(PIN_LR_RESET, LOW); delay(2);
  digitalWrite(PIN_LR_RESET, HIGH); delay(5);
}

// READ-ONLY GetVersion (vendor-confirmed framing). No RF.
static void getVersion() {
  lrReset();
  waitBusyLow(50);
  SPI.beginTransaction(g_spi);
  digitalWrite(PIN_LR_NSS, LOW);
  SPI.transfer((uint8_t)(LR_CMD_GET_VERSION >> 8));
  SPI.transfer((uint8_t)(LR_CMD_GET_VERSION & 0xFF));
  digitalWrite(PIN_LR_NSS, HIGH);
  SPI.endTransaction();
  waitBusyLow(50);
  SPI.beginTransaction(g_spi);
  digitalWrite(PIN_LR_NSS, LOW);
  for (int i = 0; i < 5; i++) g_raw[i] = SPI.transfer(0x00);
  digitalWrite(PIN_LR_NSS, HIGH);
  SPI.endTransaction();
  g_init_verified = (g_raw[2] == LR_DEVICE_LR1121);
  Serial.print(F("LR1121_GETVERSION_RAW="));
  for (int i = 0; i < 5; i++) { if (g_raw[i] < 0x10) Serial.print('0'); Serial.print(g_raw[i], HEX); if (i < 4) Serial.print(' '); }
  Serial.println();
  Serial.print(F("lr1121_init_verified=")); Serial.println(g_init_verified ? "true" : "false");
}

static void printConfig() {
  Serial.println(F("---- config ----"));
  Serial.print(F("center_frequency_hz=")); Serial.println(CENTER_FREQUENCY_HZ);
  Serial.print(F("packet_duration_ms=")); Serial.println(PACKET_DURATION_MS_PLACEHOLDER);
  Serial.print(F("modulation=")); Serial.println(MODULATION_CONFIG);
  Serial.print(F("default_packet_count=")); Serial.println(DEFAULT_PACKET_COUNT);
  Serial.print(F("ENABLE_REAL_TX=")); Serial.println(ENABLE_REAL_TX ? "1" : "0");
  Serial.print(F("pin_map: NSS=")); Serial.print(PIN_LR_NSS);
  Serial.print(F(" BUSY=")); Serial.print(PIN_LR_BUSY);
  Serial.print(F(" RESET=")); Serial.print(PIN_LR_RESET);
  Serial.print(F(" DIO=")); Serial.println(PIN_LR_DIO);
}

static void printStatus() {
  Serial.println(F("---- status ----"));
  Serial.print(F("RF_TRANSMISSION_ENABLED=")); Serial.println(g_rf_transmission_enabled ? "true" : "false");
  Serial.print(F("armed=")); Serial.println(g_armed ? "true" : "false");
  Serial.print(F("PACKET_TRANSMISSION_EXECUTED=")); Serial.println(g_tx_executed ? "true" : "false");
  Serial.print(F("HIL_VALIDATION_COMPLETE=")); Serial.println(HIL_VALIDATION_COMPLETE ? "true" : "false");
  Serial.print(F("OTA_VALIDATION_COMPLETE=")); Serial.println(OTA_VALIDATION_COMPLETE ? "true" : "false");
  Serial.print(F("HARDWARE_VALIDATION_COMPLETE=")); Serial.println(HARDWARE_VALIDATION_COMPLETE ? "true" : "false");
  Serial.println(F("READY"));
}

static void armTx(const String &arg) {
  if (arg == "CONFIRM_CONDUCTED_TEST") {
    g_armed = true;
    Serial.println(F("WARNING: TX ARMED for a CONDUCTED/SHIELDED test only."));
    Serial.println(F("WARNING: ensure attenuator/dummy-load, NO antenna, NO OTA."));
    Serial.println(F("armed=true"));
  } else {
    Serial.println(F("arm_tx refused: missing confirm token. Use: arm_tx CONFIRM_CONDUCTED_TEST"));
  }
}

static void disarmTx() {
  g_armed = false;
  g_rf_transmission_enabled = false;
  Serial.println(F("armed=false"));
}

// Gated single-packet test. Performs NO RF unless ENABLE_REAL_TX is compiled in
// AND the board is armed. With ENABLE_REAL_TX==0 (default), this never emits RF.
static void sendTestPacket() {
  if (!g_armed) {
    Serial.println(F("send_test_packet refused: not armed. Use arm_tx CONFIRM_CONDUCTED_TEST first."));
    return;
  }
#if ENABLE_REAL_TX
  // INTENTIONAL REVIEWED TODO: the real LR1121 conducted TX opcode sequence
  // (SetPacketType / SetRfFrequency / SetPaConfig / conservative SetTxParams /
  // SetModulationParams / SetPacketParams / WriteBuffer / single send) must be
  // implemented and bench-reviewed before first use. Left unimplemented so no
  // unverified RF sequence ships. Keeps TX_EXECUTED=false.
  Serial.println(F("TX_PATH_REVIEW_REQUIRED: real TX sequence not yet implemented"));
  g_tx_executed = false;
#else
  Serial.println(F("TX_PATH_DISABLED_AT_COMPILE_TIME: rebuild with -DENABLE_REAL_TX=1 to enable"));
  g_tx_executed = false;
#endif
  g_packet_index++;
  Serial.print(F("packet_index=")); Serial.println(g_packet_index);
  Serial.print(F("timestamp_ms=")); Serial.println(millis());
  Serial.print(F("center_frequency_hz=")); Serial.println(CENTER_FREQUENCY_HZ);
  Serial.print(F("packet_duration_ms=")); Serial.println(PACKET_DURATION_MS_PLACEHOLDER);
  Serial.print(F("modulation=")); Serial.println(MODULATION_CONFIG);
  Serial.print(F("TX_EXECUTED=")); Serial.println(g_tx_executed ? "true" : "false");
}

static void printHelp() {
  Serial.println(F("commands: status | getversion | config | arm_tx CONFIRM_CONDUCTED_TEST | disarm_tx | send_test_packet"));
}

static void printBanner() {
  Serial.println();
  Serial.println(F("==== LEO-DTF H1B/H1C controlled packet source ===="));
  Serial.print(F("firmware_name=")); Serial.println(FW_NAME);
  Serial.print(F("firmware_version=")); Serial.println(FW_VERSION);
  Serial.print(F("board_target=")); Serial.println(BOARD_TGT);
  Serial.print(F("RF_TRANSMISSION_ENABLED=")); Serial.println(g_rf_transmission_enabled ? "true" : "false");
  Serial.print(F("PACKET_TRANSMISSION_EXECUTED=")); Serial.println(g_tx_executed ? "true" : "false");
  Serial.print(F("HIL_VALIDATION_COMPLETE=")); Serial.println(HIL_VALIDATION_COMPLETE ? "true" : "false");
}

static void handleCommand(const String &line) {
  int sp = line.indexOf(' ');
  String cmd = (sp < 0) ? line : line.substring(0, sp);
  String arg = (sp < 0) ? "" : line.substring(sp + 1);
  arg.trim();

  if (cmd == "status") {
    printStatus();
  } else if (cmd == "getversion") {
    getVersion();
  } else if (cmd == "config") {
    printConfig();
  } else if (cmd == "arm_tx") {
    armTx(arg);
  } else if (cmd == "disarm_tx") {
    disarmTx();
  } else if (cmd == "send_test_packet") {
    sendTestPacket();
  } else if (cmd == "help") {
    printHelp();
  } else if (cmd.length() > 0) {
    Serial.print(F("unknown command: ")); Serial.println(cmd);
  }
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  unsigned long t0 = millis();
  while (!Serial && (millis() - t0) < 3000) { /* wait up to 3s for USB serial */ }

  pinsInit();
  printBanner();
  getVersion();
  printConfig();
  printStatus();
  printHelp();
  // NOTE: TX disabled, not armed, no transmission performed.
}

void loop() {
  // NEVER auto-transmits. Only responds to gated serial commands.
  static String line;
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      line.trim();
      if (line.length() > 0) handleCommand(line);
      line = "";
    } else {
      line += c;
    }
  }
}
