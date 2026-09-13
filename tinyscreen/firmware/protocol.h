// Wire protocol v2: line assembly, validation, connection state and encoding.
//
// Ported from ../../pico/protocol.py (MicroPython/RP2040) to run on the
// TinyScreen+'s SAMD21. Mirrors ../../docs/serial_protocol.md exactly, same
// as the original: firmware validates shape and connection/revision/epoch
// bookkeeping only, and never assigns game meaning to a message. `feed()` is
// pure parsing/validation; `accept()` is the only place that touches
// connection state.
#pragma once

#include <Arduino.h>
// Arduino.h's min/max macros break libstdc++'s templated min/max overloads.
#undef min
#undef max
#include <vector>

constexpr int PROTOCOL_VERSION = 2;
constexpr const char* UI_ID = "emotions_v1";
constexpr size_t MAX_LINE_BYTES = 2048;

struct ButtonAdvert {
  int id = 0;
  String label;
  bool enabled = false;
};

// A decoded `view` object from a `render` message. Optional fields use a
// `has*` flag rather than a sentinel, mirroring Python's `None`.
struct View {
  String screen;
  long controlEpoch = 0;
  String mood;

  bool hasClockText = false;
  String clockText;

  bool hasTimerSeconds = false;
  int timerSeconds = 0;

  bool paused = false;

  bool hasFocusMinutes = false;
  int focusMinutes = 0;

  bool hasBreakMinutes = false;
  int breakMinutes = 0;

  bool hasFeedback = false;
  String feedback;  // "unavailable" | "storage_error"

  std::vector<ButtonAdvert> buttons;

  // Null except on Home/Feed per docs/serial_protocol.md's progression
  // contract. Physical UI draws only level/yarn; xp_into_level/
  // xp_for_next_level exist mainly for dev diagnostics but also drive the
  // XP bar's fill ratio.
  bool hasProgression = false;
  int level = 0;
  int xpIntoLevel = 0;
  int xpForNextLevel = 0;
  int yarnBalance = 0;

  // Present only on break_offer: the XP/yarn just awarded for the completed
  // focus session.
  bool hasEarnedRewards = false;
  int earnedXp = 0;
  int earnedYarn = 0;

  // Present only on the settings screen.
  bool hasSettings = false;
  int settingsSelectedRow = 0;
  bool settingsKeyboardEnabled = false;
  bool settingsKeyboardAvailable = false;
  bool settingsCameraEnabled = false;
  bool settingsCameraAvailable = false;
  // Sound has no "available" status -- it's never unavailable, unlike
  // keyboard/camera which depend on host sensors.
  bool settingsSoundEnabled = true;
};

enum class MsgType { Hello, Ping, Render, Animate };

struct ParsedMessage {
  MsgType type;
  String connectionId;

  long revision = 0;
  View view;

  String animationId;
  long afterRevision = 0;
  String name;
  bool hasFoodSprite = false;
  String foodSprite;

  long nonce = 0;
};

enum class ActionKind { ResetConnection, Pong, SetView, EnqueueAnimation };

struct DeviceAction {
  ActionKind kind;
  long nonce = 0;
  View view;
  long revision = 0;
  String animationId;
  String name;
  bool hasFoodSprite = false;
  String foodSprite;
};

class Protocol {
 public:
  Protocol(String bootId, const int* advertisedButtons, int advertisedCount);

  // Available bytes -> bounded nonblocking line assembly and validation.
  // Appends every successfully parsed message to `outMessages`.
  void feed(const uint8_t* data, size_t len, std::vector<ParsedMessage>& outMessages);

  // Parsed message/time -> DeviceAction or false if it should be dropped.
  // Applies connection/revision/epoch validation on top of the shape
  // validation already done by `feed()`.
  bool accept(const ParsedMessage& message, unsigned long nowMs, DeviceAction& outAction);

  bool isTimedOut(unsigned long nowMs, unsigned long timeoutMs = 6000) const;

  String encodeReady() const;
  String encodeButton(unsigned long seq, long controlEpoch, int button, const char* action) const;
  String encodePong(long nonce) const;

  // Connection state, public like the Python class's public attributes.
  String connectionId;
  bool hasConnectionId = false;
  long controlEpoch = 0;
  bool connected = false;
  bool hasValidView = false;

 private:
  String bootId_;
  std::vector<int> advertised_;
  String buffer_;
  bool discarding_ = false;
  long lastRevision_ = 0;
  bool hasLastTraffic_ = false;
  unsigned long lastTrafficMs_ = 0;

  bool parseLine(const String& line, ParsedMessage& out) const;
};
