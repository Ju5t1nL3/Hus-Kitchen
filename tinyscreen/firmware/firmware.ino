// Cooperative firmware loop: USB protocol, buttons and rendering.
//
// Ported from ../../pico/main.py to run on the TinyScreen+ (SAMD21) instead
// of the RP2040 Pico. This is the whole of the firmware's decision-making:
// assemble/validate USB input, track connection/revision/epoch state, scan
// buttons and hand the laptop-selected view to the renderer. It must never
// decide timer outcomes, emotions, rewards or persistence -- see
// ../../docs/system_design.md and ../../docs/serial_protocol.md.
#include <SPI.h>
#include <TinyScreen.h>
#include <Wire.h>

#include "audio_player.h"
#include "buttons.h"
#include "display.h"
#include "hardware_config.h"
#include "protocol.h"
#include "sound.h"
#include "sound_cues.h"

namespace {

constexpr unsigned long kHeartbeatTimeoutMs = 6000;
// SAMD21's factory-programmed 128-bit unique serial number.
constexpr uint32_t kSerialNumberWords[4] = {0x0080A00CUL, 0x0080A040UL, 0x0080A044UL,
                                             0x0080A048UL};

TinyScreen tsDisplay = TinyScreen(TinyScreenPlus);

String makeBootId() {
  uint32_t a = *reinterpret_cast<volatile uint32_t*>(kSerialNumberWords[0]);
  uint32_t b = *reinterpret_cast<volatile uint32_t*>(kSerialNumberWords[1]);
  char buf[40];
  snprintf(buf, sizeof(buf), "boot-%08lx%08lx-%08lx", (unsigned long)a, (unsigned long)b,
           (unsigned long)millis());
  return String(buf);
}

ButtonScanner* scanner = nullptr;
Renderer* renderer = nullptr;
Protocol* protocolPtr = nullptr;
unsigned long seq = 0;
SoundPlayer soundPlayer;
AudioPlayer audioPlayer;

// Tracks the previously rendered screen so a focus-complete/break-end jingle
// plays exactly once, on the transition, rather than on every subsequent
// render of the same screen (e.g. a clock/timer tick). Neither the protocol
// nor firmware assigns any *meaning* to these transitions beyond "make a
// sound" -- the laptop is still the only thing that decided the screen.
String lastScreen;

void dispatch(const DeviceAction& action) {
  switch (action.kind) {
    case ActionKind::ResetConnection:
      scanner->resetUntilRelease();
      seq = 0;
      renderer->setConnected(true);
      SerialUSB.print(protocolPtr->encodeReady());
      if (renderer->soundEnabled()) soundPlayer.playCue(kSoundReady, 1);
      lastScreen = "";
      break;
    case ActionKind::Pong:
      SerialUSB.print(protocolPtr->encodePong(action.nonce));
      break;
    case ActionKind::SetView: {
      const String& newScreen = action.view.screen;
      if (newScreen == "break_offer" && lastScreen != "break_offer") {
        if (renderer->soundEnabled()) soundPlayer.playCue(kSoundPomodoroComplete, 4);
      } else if (lastScreen == "break" && newScreen != "break") {
        if (renderer->soundEnabled()) soundPlayer.playCue(kSoundBreakEnd, 3);
      }
      lastScreen = newScreen;
      renderer->setView(action.view);
      break;
    }
    case ActionKind::EnqueueAnimation:
      renderer->enqueueAnimation(action.animationId, action.name, action.foodSprite);
      // "celebrate" has no sound of its own: it always accompanies entering
      // break_offer, which the SetView case above already gives its own
      // (nicer) jingle. Playing both would just cut one off mid-note, since
      // there's only one DAC voice for foreground cues.
      if (action.name == "feed" && renderer->soundEnabled()) {
        soundPlayer.playCue(kSoundFeed, 3);
      }
      break;
  }
}

}  // namespace

void setup() {
  tsDisplay.begin();
  tsDisplay.setBrightness(11);  // slightly below max (0-15)
  // Board is mounted rotated 180 degrees in its enclosure; setFlip() corrects
  // both the drawn image and getButtons()'s corner mapping together.
  tsDisplay.setFlip(true);

  static int ids[hw::BUTTON_COUNT];
  for (int i = 0; i < hw::BUTTON_COUNT; i++) ids[i] = hw::BUTTONS[i].id;
  static Protocol realProtocol(makeBootId(), ids, hw::BUTTON_COUNT);
  protocolPtr = &realProtocol;

  static ButtonScanner realScanner(tsDisplay, hw::BUTTONS, hw::BUTTON_COUNT, hw::DEBOUNCE_MS,
                                   hw::HOLD_MS);
  scanner = &realScanner;

  static Renderer realRenderer(tsDisplay);
  renderer = &realRenderer;

  soundPlayer.begin();

  audioPlayer.begin();
  // BGM disabled per request -- audioPlayer.play() loops the 14s lake_mono.wav
  // clip (see audio_clip.h); call it here to re-enable.

  SerialUSB.begin(115200);
  SerialUSB.print(protocolPtr->encodeReady());
}

void loop() {
  unsigned long nowMs = millis();

  if (SerialUSB.available()) {
    uint8_t chunk[128];
    size_t len = 0;
    while (SerialUSB.available() && len < sizeof(chunk)) {
      chunk[len++] = static_cast<uint8_t>(SerialUSB.read());
    }
    std::vector<ParsedMessage> messages;
    protocolPtr->feed(chunk, len, messages);
    for (const ParsedMessage& message : messages) {
      DeviceAction action;
      if (protocolPtr->accept(message, nowMs, action)) dispatch(action);
    }
  }

  if (protocolPtr->connected && protocolPtr->isTimedOut(nowMs, kHeartbeatTimeoutMs)) {
    protocolPtr->connected = false;
    protocolPtr->hasValidView = false;
    renderer->setConnected(false);
  }

  std::vector<Gesture> gestures = scanner->poll(nowMs, protocolPtr->controlEpoch);
  if (protocolPtr->connected && protocolPtr->hasValidView) {
    for (const Gesture& gesture : gestures) {
      seq++;
      SerialUSB.print(
          protocolPtr->encodeButton(seq, gesture.controlEpoch, gesture.button, gesture.action));
      if (renderer->soundEnabled()) soundPlayer.playCue(kSoundPress, 1);
    }
  }

  renderer->tick(nowMs);

  unsigned long nowUs = micros();
  soundPlayer.tick(nowUs);
  // Both ultimately drive the same DAC pin; let a short cue (press/feed/
  // ready/celebrate) take priority and yield the background clip otherwise.
  if (!soundPlayer.isCuePlaying()) audioPlayer.tick(nowUs);
}
