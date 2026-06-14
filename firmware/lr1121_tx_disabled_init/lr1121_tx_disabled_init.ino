/*
 * lr1121_tx_disabled_init
 * -----------------------
 * Safe bring-up firmware for LEO-DTF H0/H0.5 on a Nucleo-64 (NUCLEO_L476RG)
 * host carrying an LR1121 radio.
 *
 * SAFETY CONTRACT (do not weaken):
 *   - TX is DISABLED by default and at all times in this build.
 *   - No automatic transmission in setup() or loop().
 *   - Only READ-ONLY LR1121 SPI commands are issued (GetVersion / GetStatus).
 *   - No LR1121 radio TX/send API is invoked anywhere in this build.
 *   - The `tx` serial command is intentionally BLOCKED.
 *   - This firmware does NOT prove HIL/OTA/hardware validation.
 *
 * H0.5 adds a read-only SPI probe (LR1121 GetVersion) over raw SPI, with no
 * vendor library dependency, so the build cannot transmit.
 */

#include <SPI.h>

// ---- Build identity ---------------------------------------------------------
static const char *FW_NAME    = "lr1121_tx_disabled_init";
static const char *FW_VERSION = "0.2.0";
static const char *BOARD_TGT  = "STMicroelectronics:stm32:Nucleo_64:pnum=NUCLEO_L476RG";
static const long  SERIAL_BAUD = 115200;

// ---- Safety flags (compile-time constants; not runtime-togglable) -----------
static const bool RF_TRANSMISSION_ENABLED      = false;
static const bool PACKET_TRANSMISSION_EXECUTED = false;
static const bool HIL_VALIDATION_COMPLETE      = false;
static const bool TX_DEFAULT_DISABLED          = true;

// ---- LR1121 pin map (configurable; verify against actual shield wiring) ------
// Likely wiring for an Arduino-header LR1121 shield on Nucleo-L476RG.
// SPI MOSI/MISO/SCK use the board default SPI1 (D11/D12/D13).
#ifndef PIN_LR_NSS
#define PIN_LR_NSS   D10   // SPI chip select / NSS
#endif
#ifndef PIN_LR_BUSY
#define PIN_LR_BUSY  D8    // BUSY
#endif
#ifndef PIN_LR_RESET
#define PIN_LR_RESET D9    // NRESET
#endif
#ifndef PIN_LR_DIO
#define PIN_LR_DIO   D3    // DIO/IRQ
#endif
static const int PIN_MOSI = D11;  // informational (SPI default)
static const int PIN_MISO = D12;  // informational (SPI default)
static const int PIN_SCK  = D13;  // informational (SPI default)

// LR11xx read-only opcodes.
static const uint16_t LR_CMD_GET_VERSION = 0x0101;  // returns hw,type,fw_major,fw_minor

static bool g_spi_ready = false;
static bool g_probe_attempted = false;
static const char *g_probe_result = "not_attempted";
static uint8_t g_version_raw[5] = {0, 0, 0, 0, 0};  // stat + 4 bytes
static SPISettings g_spi_settings(8000000, MSBFIRST, SPI_MODE0);

static bool waitBusyLow(uint32_t timeout_ms) {
  uint32_t t0 = millis();
  while (digitalRead(PIN_LR_BUSY) == HIGH) {
    if (millis() - t0 > timeout_ms) return false;
  }
  return true;
}

static void lrReset() {
  pinMode(PIN_LR_RESET, OUTPUT);
  digitalWrite(PIN_LR_RESET, LOW);
  delay(2);
  digitalWrite(PIN_LR_RESET, HIGH);
  delay(5);
}

static void spiInit() {
  pinMode(PIN_LR_NSS, OUTPUT);
  digitalWrite(PIN_LR_NSS, HIGH);   // deselect
  pinMode(PIN_LR_BUSY, INPUT);
  pinMode(PIN_LR_DIO, INPUT);
  SPI.begin();
  g_spi_ready = true;
  Serial.print(F("SPI_INIT_STATUS="));
  Serial.println(g_spi_ready ? "ok" : "fail");
}

// READ-ONLY probe: LR1121 GetVersion. Issues no TX command.
static void lrGetVersionProbe() {
  g_probe_attempted = true;
  lrReset();

  if (!waitBusyLow(100)) {
    g_probe_result = "fail_busy_timeout_after_reset";
  } else {
    SPI.beginTransaction(g_spi_settings);
    // Send GetVersion opcode.
    digitalWrite(PIN_LR_NSS, LOW);
    SPI.transfer((uint8_t)(LR_CMD_GET_VERSION >> 8));
    SPI.transfer((uint8_t)(LR_CMD_GET_VERSION & 0xFF));
    digitalWrite(PIN_LR_NSS, HIGH);
    SPI.endTransaction();

    bool ready = waitBusyLow(100);

    // Read response: stat byte + 4 version bytes.
    SPI.beginTransaction(g_spi_settings);
    digitalWrite(PIN_LR_NSS, LOW);
    for (int i = 0; i < 5; i++) {
      g_version_raw[i] = SPI.transfer(0x00);
    }
    digitalWrite(PIN_LR_NSS, HIGH);
    SPI.endTransaction();

    bool all_zero = true, all_ff = true;
    for (int i = 1; i < 5; i++) {
      if (g_version_raw[i] != 0x00) all_zero = false;
      if (g_version_raw[i] != 0xFF) all_ff = false;
    }
    if (!ready) {
      g_probe_result = "fail_busy_timeout_after_cmd";
    } else if (all_zero || all_ff) {
      g_probe_result = "fail_no_plausible_response";
    } else {
      g_probe_result = "ok";
    }
  }

  Serial.print(F("LR1121_SPI_PROBE_ATTEMPTED="));
  Serial.println(g_probe_attempted ? "true" : "false");
  Serial.print(F("LR1121_SPI_PROBE_RESULT="));
  Serial.println(g_probe_result);
  Serial.print(F("LR1121_VERSION_RAW="));
  for (int i = 0; i < 5; i++) {
    if (g_version_raw[i] < 0x10) Serial.print('0');
    Serial.print(g_version_raw[i], HEX);
    if (i < 4) Serial.print(' ');
  }
  Serial.println();
}

static void printPinMap() {
  Serial.println(F("---- pin map (configurable) ----"));
  Serial.print(F("LR1121_NSS="));   Serial.println(PIN_LR_NSS);
  Serial.print(F("LR1121_BUSY="));  Serial.println(PIN_LR_BUSY);
  Serial.print(F("LR1121_RESET=")); Serial.println(PIN_LR_RESET);
  Serial.print(F("LR1121_DIO="));   Serial.println(PIN_LR_DIO);
  Serial.print(F("SPI_MOSI="));     Serial.println(PIN_MOSI);
  Serial.print(F("SPI_MISO="));     Serial.println(PIN_MISO);
  Serial.print(F("SPI_SCK="));      Serial.println(PIN_SCK);
}

static void printBanner() {
  Serial.println();
  Serial.println(F("==== LEO-DTF H0.5 firmware ===="));
  Serial.print(F("firmware_name="));    Serial.println(FW_NAME);
  Serial.print(F("firmware_version=")); Serial.println(FW_VERSION);
  Serial.print(F("board_target="));     Serial.println(BOARD_TGT);
  Serial.print(F("serial_baud="));      Serial.println(SERIAL_BAUD);
  printPinMap();
  Serial.println(F("---- safety flags ----"));
  Serial.print(F("TX_DEFAULT_DISABLED="));          Serial.println(TX_DEFAULT_DISABLED ? "true" : "false");
  Serial.print(F("RF_TRANSMISSION_ENABLED="));      Serial.println(RF_TRANSMISSION_ENABLED ? "true" : "false");
  Serial.print(F("PACKET_TRANSMISSION_EXECUTED=")); Serial.println(PACKET_TRANSMISSION_EXECUTED ? "true" : "false");
  Serial.print(F("HIL_VALIDATION_COMPLETE="));      Serial.println(HIL_VALIDATION_COMPLETE ? "true" : "false");
}

static void printStatus() {
  Serial.println(F("---- status ----"));
  Serial.print(F("spi_ready="));               Serial.println(g_spi_ready ? "true" : "false");
  Serial.print(F("lr1121_spi_probe_attempted=")); Serial.println(g_probe_attempted ? "true" : "false");
  Serial.print(F("lr1121_spi_probe_result="));    Serial.println(g_probe_result);
  Serial.print(F("RF_TRANSMISSION_ENABLED=")); Serial.println(RF_TRANSMISSION_ENABLED ? "true" : "false");
  Serial.println(F("READY"));
}

static void handleCommand(const String &cmd) {
  if (cmd == "status") {
    printStatus();
  } else if (cmd == "spi") {
    spiInit();
  } else if (cmd == "init") {
    spiInit();
    lrGetVersionProbe();
  } else if (cmd == "version") {
    lrGetVersionProbe();
  } else if (cmd == "tx") {
    Serial.println(F("TX command blocked in this firmware build"));
  } else if (cmd.length() > 0) {
    Serial.print(F("unknown command: "));
    Serial.println(cmd);
  }
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  unsigned long t0 = millis();
  while (!Serial && (millis() - t0) < 3000) { /* wait up to 3s for USB serial */ }

  printBanner();
  spiInit();
  lrGetVersionProbe();   // READ-ONLY probe only
  printStatus();
  Serial.println(F("commands: status | spi | version | init | tx(blocked)"));
  // NOTE: no transmission is performed here. TX stays disabled.
}

void loop() {
  // No automatic transmission. Only respond to safe serial commands.
  static String line;
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      line.trim();
      if (line.length() > 0) {
        handleCommand(line);
      }
      line = "";
    } else {
      line += c;
    }
  }
}
