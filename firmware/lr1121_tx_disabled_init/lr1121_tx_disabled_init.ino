/*
 * lr1121_tx_disabled_init
 * -----------------------
 * Safe read-only LR1121 bring-up + diagnostic firmware for LEO-DTF
 * H0 / H0.5 / H0.5B / H0.5C on a Nucleo-64 (NUCLEO_L476RG).
 *
 * SAFETY CONTRACT (do not weaken):
 *   - TX is DISABLED by default and at all times in this build.
 *   - No automatic transmission in setup() or loop().
 *   - Only READ-ONLY LR1121 SPI commands are issued (GetVersion).
 *   - No LR1121 radio TX/send API is invoked anywhere in this build.
 *   - The tx/send/transmit serial commands are intentionally BLOCKED.
 *   - This firmware does NOT prove HIL/OTA/hardware validation.
 *
 * H0.5C locks the discovered LR1121 pin map and implements a GetVersion parser
 * whose framing is confirmed against the RadioLib LR11x0 driver
 * (RADIOLIB_LR11X0_CMD_GET_VERSION=0x0101; reply bytes hw, device, major, minor;
 * RADIOLIB_LR11X0_DEVICE_LR1121=0x03). No RadioLib code is linked; only the
 * read-only framing is replicated.
 */

#include <SPI.h>

// ---- Build identity ---------------------------------------------------------
static const char *FW_NAME    = "lr1121_tx_disabled_init";
static const char *FW_VERSION = "0.4.0";
static const char *BOARD_TGT  = "STMicroelectronics:stm32:Nucleo_64:pnum=NUCLEO_L476RG";
static const long  SERIAL_BAUD = 115200;

// ---- Safety flags (compile-time constants; not runtime-togglable) -----------
static const bool RF_TRANSMISSION_ENABLED      = false;
static const bool PACKET_TRANSMISSION_EXECUTED = false;
static const bool HIL_VALIDATION_COMPLETE      = false;
static const bool TX_DEFAULT_DISABLED          = true;

// ---- LOCKED LR1121 pin map (discovered in H0.5B) ---------------------------
static const int PIN_LR_NSS   = D7;
static const int PIN_LR_BUSY  = D3;
static const int PIN_LR_RESET = D9;
static const int PIN_LR_DIO   = D5;
static const int PIN_MOSI = D11;  // SPI default (informational)
static const int PIN_MISO = D12;
static const int PIN_SCK  = D13;
static const uint8_t LR_SPI_MODE = 0;

// ---- Vendor-confirmed constants (from RadioLib LR11x0 driver) ----------------
static const uint16_t LR_CMD_GET_VERSION = 0x0101;
static const uint8_t  LR_DEVICE_LR1121   = 0x03;
static SPISettings g_spi_settings(2000000, MSBFIRST, SPI_MODE0);

// ---- Optional diagnostic sweep maps (NOT default) ---------------------------
struct LrPinMap { const char *name; int nss; int busy; int reset; int dio; };
static const LrPinMap SWEEP_CANDIDATES[] = {
  {"map_current",                 D10, D8, D9, D3},
  {"map_alt_shield",              D7,  D3, A0, D5},
  {"map_alt_reset_d9",           D7,  D3, D9, D5},  // locked map
  {"map_alt_busy_d8",            D7,  D8, A0, D5},
  {"map_cs_d10_busy_d3_reset_a0", D10, D3, A0, D5},
};
static const int N_SWEEP = sizeof(SWEEP_CANDIDATES) / sizeof(SWEEP_CANDIDATES[0]);

static bool g_spi_ready = false;
static bool g_probe_plausible = false;
static bool g_init_verified = false;
static const char *g_parser_confidence = "unverified";
static uint8_t g_raw[5] = {0, 0, 0, 0, 0};   // stat1 + hw,device,major,minor

static bool waitBusyLow(int busyPin, uint32_t timeout_ms) {
  uint32_t t0 = millis();
  while (digitalRead(busyPin) == HIGH) {
    if (millis() - t0 > timeout_ms) return false;
  }
  return true;
}

static void lockedPinsInit() {
  pinMode(PIN_LR_NSS, OUTPUT);
  digitalWrite(PIN_LR_NSS, HIGH);
  pinMode(PIN_LR_RESET, OUTPUT);
  digitalWrite(PIN_LR_RESET, HIGH);
  pinMode(PIN_LR_BUSY, INPUT);
  pinMode(PIN_LR_DIO, INPUT);
}

static void lrReset() {
  digitalWrite(PIN_LR_RESET, LOW);
  delay(2);
  digitalWrite(PIN_LR_RESET, HIGH);
  delay(5);
}

static void spiInit() {
  SPI.begin();
  g_spi_ready = true;
  Serial.print(F("SPI_INIT_STATUS="));
  Serial.println(g_spi_ready ? "ok" : "fail");
}

// READ-ONLY GetVersion using vendor-confirmed framing. No TX command issued.
static void getVersionConfirm() {
  lockedPinsInit();
  lrReset();
  waitBusyLow(PIN_LR_BUSY, 50);

  // Send GetVersion opcode (read-only command).
  SPI.beginTransaction(g_spi_settings);
  digitalWrite(PIN_LR_NSS, LOW);
  SPI.transfer((uint8_t)(LR_CMD_GET_VERSION >> 8));
  SPI.transfer((uint8_t)(LR_CMD_GET_VERSION & 0xFF));
  digitalWrite(PIN_LR_NSS, HIGH);
  SPI.endTransaction();

  waitBusyLow(PIN_LR_BUSY, 50);

  // Read reply: Stat1 + {hw, device, major, minor}.
  SPI.beginTransaction(g_spi_settings);
  digitalWrite(PIN_LR_NSS, LOW);
  for (int i = 0; i < 5; i++) g_raw[i] = SPI.transfer(0x00);
  digitalWrite(PIN_LR_NSS, HIGH);
  SPI.endTransaction();

  uint8_t stat1  = g_raw[0];
  uint8_t hw     = g_raw[1];
  uint8_t device = g_raw[2];
  uint8_t major  = g_raw[3];
  uint8_t minor  = g_raw[4];

  bool all_zero = (hw == 0 && device == 0 && major == 0 && minor == 0);
  bool all_ff   = (hw == 0xFF && device == 0xFF && major == 0xFF && minor == 0xFF);
  g_probe_plausible = !all_zero && !all_ff;

  // Framing matches RadioLib LR11x0 driver -> vendor_confirmed.
  g_parser_confidence = "vendor_confirmed";
  // Verified only if vendor framing decodes an LR1121 device id.
  g_init_verified = (strcmp(g_parser_confidence, "vendor_confirmed") == 0) &&
                    g_probe_plausible && (device == LR_DEVICE_LR1121);

  Serial.print(F("SPI_PROBE_PLAUSIBLE="));
  Serial.println(g_probe_plausible ? "true" : "false");
  Serial.print(F("LR1121_GETVERSION_RAW="));
  for (int i = 0; i < 5; i++) {
    if (g_raw[i] < 0x10) Serial.print('0');
    Serial.print(g_raw[i], HEX);
    if (i < 4) Serial.print(' ');
  }
  Serial.println();
  Serial.print(F("LR1121_GETVERSION_DECODED="));
  Serial.print(F("stat1=0x")); Serial.print(stat1, HEX);
  Serial.print(F(",hw=0x"));    Serial.print(hw, HEX);
  Serial.print(F(",device=0x")); Serial.print(device, HEX);
  Serial.print(F(",fw="));       Serial.print(major); Serial.print('.'); Serial.println(minor);
  Serial.print(F("parser_confidence="));
  Serial.println(g_parser_confidence);
  Serial.print(F("LR1121_INIT_VERIFIED="));
  Serial.println(g_init_verified ? "true" : "false");
}

// Optional read-only diagnostic sweep (kept available; not default).
static void runSweep() {
  Serial.println(F("SWEEP_BEGIN"));
  Serial.println(F("LR1121_SPI_PROBE_ATTEMPTED=true"));
  for (int c = 0; c < N_SWEEP; c++) {
    const LrPinMap &m = SWEEP_CANDIDATES[c];
    pinMode(m.nss, OUTPUT); digitalWrite(m.nss, HIGH);
    pinMode(m.reset, OUTPUT); digitalWrite(m.reset, HIGH);
    pinMode(m.busy, INPUT); pinMode(m.dio, INPUT);
    digitalWrite(m.reset, LOW); delay(2); digitalWrite(m.reset, HIGH); delay(5);
    waitBusyLow(m.busy, 50);
    uint8_t r[5] = {0};
    SPI.beginTransaction(g_spi_settings);
    digitalWrite(m.nss, LOW);
    SPI.transfer(0x01); SPI.transfer(0x01);
    digitalWrite(m.nss, HIGH);
    SPI.endTransaction();
    waitBusyLow(m.busy, 50);
    SPI.beginTransaction(g_spi_settings);
    digitalWrite(m.nss, LOW);
    for (int i = 0; i < 5; i++) r[i] = SPI.transfer(0x00);
    digitalWrite(m.nss, HIGH);
    SPI.endTransaction();
    Serial.print(F("SWEEP,")); Serial.print(m.name); Serial.print(',');
    for (int i = 0; i < 5; i++) { if (r[i] < 0x10) Serial.print('0'); Serial.print(r[i], HEX); if (i < 4) Serial.print('-'); }
    Serial.println();
  }
  Serial.println(F("SWEEP_END"));
}

static void printPinMap() {
  Serial.println(F("---- LOCKED pin map ----"));
  Serial.print(F("LR1121_NSS="));   Serial.println(PIN_LR_NSS);
  Serial.print(F("LR1121_BUSY="));  Serial.println(PIN_LR_BUSY);
  Serial.print(F("LR1121_RESET=")); Serial.println(PIN_LR_RESET);
  Serial.print(F("LR1121_DIO="));   Serial.println(PIN_LR_DIO);
  Serial.print(F("SPI_MOSI="));     Serial.print(PIN_MOSI);
  Serial.print(F(" SPI_MISO="));    Serial.print(PIN_MISO);
  Serial.print(F(" SPI_SCK="));     Serial.print(PIN_SCK);
  Serial.print(F(" SPI_MODE="));    Serial.println(LR_SPI_MODE);
}

static void printBanner() {
  Serial.println();
  Serial.println(F("==== LEO-DTF H0.5C firmware ===="));
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
  Serial.print(F("spi_probe_plausible="));     Serial.println(g_probe_plausible ? "true" : "false");
  Serial.print(F("lr1121_init_verified="));    Serial.println(g_init_verified ? "true" : "false");
  Serial.print(F("parser_confidence="));       Serial.println(g_parser_confidence);
  Serial.print(F("RF_TRANSMISSION_ENABLED=")); Serial.println(RF_TRANSMISSION_ENABLED ? "true" : "false");
  Serial.println(F("READY"));
}

static void printHelp() {
  Serial.println(F("commands: help | status | pins | version | sweep | tx(blocked)"));
}

static void handleCommand(const String &cmd) {
  if (cmd == "status") {
    printStatus();
  } else if (cmd == "pins") {
    printPinMap();
  } else if (cmd == "version") {
    getVersionConfirm();
  } else if (cmd == "sweep") {
    runSweep();
  } else if (cmd == "help") {
    printHelp();
  } else if (cmd == "tx" || cmd == "send" || cmd == "transmit") {
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
  getVersionConfirm();   // READ-ONLY GetVersion only
  printStatus();
  printHelp();
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
