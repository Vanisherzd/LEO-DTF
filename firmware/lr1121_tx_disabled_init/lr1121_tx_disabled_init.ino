/*
 * lr1121_tx_disabled_init
 * -----------------------
 * Safe bring-up firmware for LEO-DTF H0 on a Nucleo-64 (NUCLEO_L476RG) host
 * carrying an LR1121 radio.
 *
 * SAFETY CONTRACT (do not weaken):
 *   - TX is DISABLED by default and at all times in this build.
 *   - No automatic transmission in setup() or loop().
 *   - No LR1121 radio TX/send API is invoked anywhere in this build.
 *   - The `tx` serial command is intentionally BLOCKED.
 *   - This firmware does NOT prove HIL/OTA/hardware validation.
 *
 * It only: prints a banner, initializes SPI, prints an LR1121 pin map, and
 * reports status over serial. LR1121 register access is a read-only placeholder.
 */

#include <SPI.h>

// ---- Build identity ---------------------------------------------------------
static const char *FW_NAME    = "lr1121_tx_disabled_init";
static const char *FW_VERSION = "0.1.0";
static const char *BOARD_TGT  = "STMicroelectronics:stm32:Nucleo_64:pnum=NUCLEO_L476RG";
static const long  SERIAL_BAUD = 115200;

// ---- Safety flags (compile-time constants; not runtime-togglable) -----------
static const bool RF_TRANSMISSION_ENABLED    = false;
static const bool PACKET_TRANSMISSION_EXECUTED = false;
static const bool HIL_VALIDATION_COMPLETE     = false;
static const bool TX_DEFAULT_DISABLED         = true;

// ---- LR1121 pin map PLACEHOLDERS (verify against actual wiring) --------------
// These are placeholders for an Arduino-header LR1121 shield. Confirm before use.
static const int PIN_LR_NSS   = D7;   // SPI chip select (placeholder)
static const int PIN_LR_RESET = A0;   // reset (placeholder)
static const int PIN_LR_BUSY  = D3;   // busy (placeholder)
static const int PIN_LR_DIO9  = D5;   // IRQ/DIO (placeholder)
// SCK/MISO/MOSI use the board default SPI pins.

static bool g_spi_ready = false;
static bool g_lr1121_init_attempted = false;
static bool g_lr1121_init_ok = false;

static void printBanner() {
  Serial.println();
  Serial.println(F("==== LEO-DTF H0 firmware ===="));
  Serial.print(F("firmware_name="));    Serial.println(FW_NAME);
  Serial.print(F("firmware_version=")); Serial.println(FW_VERSION);
  Serial.print(F("board_target="));     Serial.println(BOARD_TGT);
  Serial.print(F("serial_baud="));      Serial.println(SERIAL_BAUD);
  Serial.println(F("---- pin map (placeholders) ----"));
  Serial.print(F("LR1121_NSS="));   Serial.println(PIN_LR_NSS);
  Serial.print(F("LR1121_RESET=")); Serial.println(PIN_LR_RESET);
  Serial.print(F("LR1121_BUSY="));  Serial.println(PIN_LR_BUSY);
  Serial.print(F("LR1121_DIO9="));  Serial.println(PIN_LR_DIO9);
  Serial.println(F("---- safety flags ----"));
  Serial.print(F("TX_DEFAULT_DISABLED="));          Serial.println(TX_DEFAULT_DISABLED ? "true" : "false");
  Serial.print(F("RF_TRANSMISSION_ENABLED="));      Serial.println(RF_TRANSMISSION_ENABLED ? "true" : "false");
  Serial.print(F("PACKET_TRANSMISSION_EXECUTED=")); Serial.println(PACKET_TRANSMISSION_EXECUTED ? "true" : "false");
  Serial.print(F("HIL_VALIDATION_COMPLETE="));      Serial.println(HIL_VALIDATION_COMPLETE ? "true" : "false");
}

static void spiInit() {
  pinMode(PIN_LR_NSS, OUTPUT);
  digitalWrite(PIN_LR_NSS, HIGH);   // deselect
  pinMode(PIN_LR_RESET, OUTPUT);
  digitalWrite(PIN_LR_RESET, HIGH); // hold out of reset (placeholder)
  pinMode(PIN_LR_BUSY, INPUT);
  pinMode(PIN_LR_DIO9, INPUT);
  SPI.begin();
  g_spi_ready = true;
  Serial.print(F("SPI_INIT_STATUS="));
  Serial.println(g_spi_ready ? "ok" : "fail");
}

static void lr1121InitPlaceholder() {
  // Read-only placeholder. No transmit, no config-for-tx. Real LR1121 GetVersion
  // would be implemented with the vendor library later; kept as a stub so this
  // build cannot transmit and has no external library dependency.
  g_lr1121_init_attempted = true;
  g_lr1121_init_ok = false;  // not implemented in this safe build
  Serial.print(F("LR1121_INIT_ATTEMPTED="));
  Serial.println(g_lr1121_init_attempted ? "true" : "false");
  Serial.print(F("LR1121_INIT_RESULT="));
  Serial.println(g_lr1121_init_ok ? "ok" : "not_implemented_safe_build");
}

static void printStatus() {
  Serial.println(F("---- status ----"));
  Serial.print(F("spi_ready="));               Serial.println(g_spi_ready ? "true" : "false");
  Serial.print(F("lr1121_init_attempted="));   Serial.println(g_lr1121_init_attempted ? "true" : "false");
  Serial.print(F("lr1121_init_ok="));          Serial.println(g_lr1121_init_ok ? "true" : "false");
  Serial.print(F("RF_TRANSMISSION_ENABLED=")); Serial.println(RF_TRANSMISSION_ENABLED ? "true" : "false");
  Serial.println(F("READY"));
}

static void handleCommand(const String &cmd) {
  if (cmd == "status") {
    printStatus();
  } else if (cmd == "init") {
    spiInit();
    lr1121InitPlaceholder();
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
  lr1121InitPlaceholder();
  printStatus();
  Serial.println(F("commands: status | init | tx(blocked)"));
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
