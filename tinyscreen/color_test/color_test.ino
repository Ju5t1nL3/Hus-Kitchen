// Simple color test for the TinyCircuits TinyScreen+ built-in OLED.
// Cycles the whole screen through solid red, green, blue, and white
// to confirm the display and wiring are working before writing any
// game logic against this board.

#include <Wire.h>
#include <SPI.h>
#include <TinyScreen.h>

TinyScreen display = TinyScreen(TinyScreenPlus);

void setup() {
  display.begin();
  display.setBrightness(10);
}

void loop() {
  display.drawRect(0, 0, 96, 64, TSRectangleFilled, TS_8b_Red);
  delay(1000);
  display.drawRect(0, 0, 96, 64, TSRectangleFilled, TS_8b_Green);
  delay(1000);
  display.drawRect(0, 0, 96, 64, TSRectangleFilled, TS_8b_Blue);
  delay(1000);
  display.drawRect(0, 0, 96, 64, TSRectangleFilled, TS_8b_White);
  delay(1000);
}
