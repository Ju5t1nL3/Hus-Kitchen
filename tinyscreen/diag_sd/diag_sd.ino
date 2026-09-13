#include <SPI.h>
#include <SD.h>

constexpr int kSdCs = 10;

bool sdOk = false;

void setup() {
  SerialUSB.begin(115200);
  sdOk = SD.begin(kSdCs);
}

void loop() {
  SerialUSB.println("SD_TEST_BOOT");
  if (sdOk) {
    SerialUSB.println("SD_OK");
    File root = SD.open("/");
    while (true) {
      File entry = root.openNextFile();
      if (!entry) break;
      SerialUSB.print("FILE: ");
      SerialUSB.print(entry.name());
      SerialUSB.print(" ");
      SerialUSB.println(entry.size());
      entry.close();
    }
    root.close();
  } else {
    SerialUSB.println("SD_FAIL");
  }
  delay(2000);
}
