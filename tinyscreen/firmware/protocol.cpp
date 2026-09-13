#include "protocol.h"

#include <ArduinoJson.h>

namespace {

// These must match docs/serial_protocol.md exactly. A value missing from these
// lists invalidates the whole view, which blanks the screen -- so the mood list
// in particular has to track the laptop's catalog (features/emotions.py), not
// just the moods this firmware happens to have artwork for.
const char* kScreens[] = {"home", "feed",        "setup", "focus",
                          "break_offer", "break", "settings"};
constexpr int kScreenCount = 7;

const char* kMoods[] = {"idle",           "happy",      "sad",      "hungry",
                        "working_neutral", "working_sad", "sleeping", "party"};
constexpr int kMoodCount = 8;

const char* kFeedbackValues[] = {"unavailable", "storage_error"};
const char* kAnimationNames[] = {"feed", "celebrate", "pet"};

bool oneOf(const String& value, const char* const* options, int count) {
  for (int i = 0; i < count; i++) {
    if (value == options[i]) return true;
  }
  return false;
}

bool isPrintableAscii(const char* value, size_t minLen, size_t maxLen) {
  if (value == nullptr) return false;
  size_t len = strlen(value);
  if (len < minLen || len > maxLen) return false;
  for (size_t i = 0; i < len; i++) {
    unsigned char ch = static_cast<unsigned char>(value[i]);
    if (ch < 32 || ch > 126) return false;
  }
  return true;
}

bool isClockText(const char* value) {
  if (value == nullptr || strlen(value) != 5 || value[2] != ':') return false;
  if (!isDigit(value[0]) || !isDigit(value[1]) || !isDigit(value[3]) || !isDigit(value[4])) {
    return false;
  }
  int hh = (value[0] - '0') * 10 + (value[1] - '0');
  int mm = (value[3] - '0') * 10 + (value[4] - '0');
  return hh >= 0 && hh <= 23 && mm >= 0 && mm <= 59;
}

bool validateButtons(JsonVariantConst buttons, const std::vector<int>& advertised,
                      std::vector<ButtonAdvert>* out) {
  if (!buttons.is<JsonArrayConst>()) return false;
  JsonArrayConst arr = buttons.as<JsonArrayConst>();
  if (static_cast<size_t>(arr.size()) != advertised.size()) return false;

  size_t index = 0;
  for (JsonVariantConst entry : arr) {
    if (!entry.is<JsonObjectConst>()) return false;
    JsonObjectConst obj = entry.as<JsonObjectConst>();
    JsonVariantConst buttonId = obj["button"];
    if (!buttonId.is<int>() || buttonId.as<int>() != advertised[index]) return false;
    JsonVariantConst label = obj["label"];
    if (!label.is<const char*>() || !isPrintableAscii(label.as<const char*>(), 1, 12)) {
      return false;
    }
    JsonVariantConst enabled = obj["enabled"];
    if (!enabled.is<bool>()) return false;

    if (out != nullptr) {
      ButtonAdvert advert;
      advert.id = buttonId.as<int>();
      advert.label = label.as<const char*>();
      advert.enabled = enabled.as<bool>();
      out->push_back(advert);
    }
    index++;
  }
  return true;
}

bool validateView(JsonVariantConst viewVar, const std::vector<int>& advertised, View* out) {
  if (!viewVar.is<JsonObjectConst>()) return false;
  JsonObjectConst obj = viewVar.as<JsonObjectConst>();

  JsonVariantConst screen = obj["screen"];
  if (!screen.is<const char*>() || !oneOf(screen.as<const char*>(), kScreens, kScreenCount)) return false;

  JsonVariantConst epoch = obj["control_epoch"];
  if (!epoch.is<long>() || epoch.as<long>() <= 0) return false;

  JsonVariantConst mood = obj["mood"];
  if (!mood.is<const char*>() || !oneOf(mood.as<const char*>(), kMoods, kMoodCount)) return false;

  JsonVariantConst clockText = obj["clock_text"];
  if (!clockText.isNull() && !isClockText(clockText.as<const char*>())) return false;

  JsonVariantConst timerSeconds = obj["timer_seconds"];
  if (!timerSeconds.isNull()) {
    if (!timerSeconds.is<long>()) return false;
    long v = timerSeconds.as<long>();
    if (v < 0 || v > 3600) return false;
  }

  JsonVariantConst paused = obj["paused"];
  if (!paused.is<bool>()) return false;

  JsonVariantConst focusMinutes = obj["focus_minutes"];
  if (!focusMinutes.isNull()) {
    if (!focusMinutes.is<long>()) return false;
    long v = focusMinutes.as<long>();
    // 0 is reserved for the fixed-length debug session below the shortest
    // configured duration -- see the laptop's DEBUG_FOCUS_MINUTES.
    if (v != 0 && (v < 5 || v > 60 || v % 5 != 0)) return false;
  }

  JsonVariantConst breakMinutes = obj["break_minutes"];
  if (!breakMinutes.isNull()) {
    if (!breakMinutes.is<long>()) return false;
    long v = breakMinutes.as<long>();
    if (v < 1 || v > 60) return false;
  }

  JsonVariantConst feedback = obj["feedback"];
  if (!feedback.isNull() && !oneOf(feedback.as<const char*>(), kFeedbackValues, 2)) return false;

  // Null except on Home/Feed; see docs/serial_protocol.md's progression
  // contract. Physical UI draws only level/yarn, but all four fields are
  // required together when the object is present.
  JsonVariantConst progression = obj["progression"];
  int level = 0, xpIntoLevel = 0, xpForNextLevel = 0, yarnBalance = 0;
  if (!progression.isNull()) {
    if (!progression.is<JsonObjectConst>()) return false;
    JsonObjectConst prog = progression.as<JsonObjectConst>();
    JsonVariantConst levelVar = prog["level"];
    JsonVariantConst xpIntoVar = prog["xp_into_level"];
    JsonVariantConst xpForNextVar = prog["xp_for_next_level"];
    JsonVariantConst yarnVar = prog["yarn_balance"];
    if (!levelVar.is<long>() || levelVar.as<long>() < 1) return false;
    if (!xpIntoVar.is<long>() || xpIntoVar.as<long>() < 0) return false;
    if (!xpForNextVar.is<long>() || xpForNextVar.as<long>() <= 0) return false;
    if (!yarnVar.is<long>() || yarnVar.as<long>() < 0) return false;
    level = levelVar.as<int>();
    xpIntoLevel = xpIntoVar.as<int>();
    xpForNextLevel = xpForNextVar.as<int>();
    yarnBalance = yarnVar.as<int>();
  }

  // Present only on break_offer; both fields are required together when the
  // object is present.
  JsonVariantConst rewards = obj["earned_rewards"];
  int earnedXp = 0, earnedYarn = 0;
  if (!rewards.isNull()) {
    if (!rewards.is<JsonObjectConst>()) return false;
    JsonObjectConst r = rewards.as<JsonObjectConst>();
    JsonVariantConst xpVar = r["xp"];
    JsonVariantConst yarnVar = r["yarn"];
    if (!xpVar.is<long>() || xpVar.as<long>() < 0) return false;
    if (!yarnVar.is<long>() || yarnVar.as<long>() < 0) return false;
    earnedXp = xpVar.as<int>();
    earnedYarn = yarnVar.as<int>();
  }

  // Present only on the settings screen.
  JsonVariantConst settings = obj["settings"];
  int settingsSelectedRow = 0;
  bool settingsKeyboardEnabled = false, settingsKeyboardAvailable = false;
  bool settingsCameraEnabled = false, settingsCameraAvailable = false;
  bool settingsSoundEnabled = true;
  if (!settings.isNull()) {
    if (!settings.is<JsonObjectConst>()) return false;
    JsonObjectConst s = settings.as<JsonObjectConst>();
    JsonVariantConst selectedRowVar = s["selected_row"];
    JsonVariantConst keyboardEnabledVar = s["keyboard_enabled"];
    JsonVariantConst keyboardAvailableVar = s["keyboard_available"];
    JsonVariantConst cameraEnabledVar = s["camera_enabled"];
    JsonVariantConst cameraAvailableVar = s["camera_available"];
    JsonVariantConst soundEnabledVar = s["sound_enabled"];
    if (!selectedRowVar.is<long>() || selectedRowVar.as<long>() < 0) return false;
    if (!keyboardEnabledVar.is<bool>() || !keyboardAvailableVar.is<bool>()) return false;
    if (!cameraEnabledVar.is<bool>() || !cameraAvailableVar.is<bool>()) return false;
    if (!soundEnabledVar.is<bool>()) return false;
    settingsSelectedRow = selectedRowVar.as<int>();
    settingsKeyboardEnabled = keyboardEnabledVar.as<bool>();
    settingsKeyboardAvailable = keyboardAvailableVar.as<bool>();
    settingsCameraEnabled = cameraEnabledVar.as<bool>();
    settingsCameraAvailable = cameraAvailableVar.as<bool>();
    settingsSoundEnabled = soundEnabledVar.as<bool>();
  }

  if (out == nullptr) {
    return validateButtons(obj["buttons"], advertised, nullptr);
  }

  out->screen = screen.as<const char*>();
  out->controlEpoch = epoch.as<long>();
  out->mood = mood.as<const char*>();
  out->hasClockText = !clockText.isNull();
  if (out->hasClockText) out->clockText = clockText.as<const char*>();
  out->hasTimerSeconds = !timerSeconds.isNull();
  if (out->hasTimerSeconds) out->timerSeconds = timerSeconds.as<int>();
  out->paused = paused.as<bool>();
  out->hasFocusMinutes = !focusMinutes.isNull();
  if (out->hasFocusMinutes) out->focusMinutes = focusMinutes.as<int>();
  out->hasBreakMinutes = !breakMinutes.isNull();
  if (out->hasBreakMinutes) out->breakMinutes = breakMinutes.as<int>();
  out->hasFeedback = !feedback.isNull();
  if (out->hasFeedback) out->feedback = feedback.as<const char*>();

  out->hasProgression = !progression.isNull();
  out->level = level;
  out->xpIntoLevel = xpIntoLevel;
  out->xpForNextLevel = xpForNextLevel;
  out->yarnBalance = yarnBalance;

  out->hasEarnedRewards = !rewards.isNull();
  out->earnedXp = earnedXp;
  out->earnedYarn = earnedYarn;

  out->hasSettings = !settings.isNull();
  out->settingsSelectedRow = settingsSelectedRow;
  out->settingsKeyboardEnabled = settingsKeyboardEnabled;
  out->settingsKeyboardAvailable = settingsKeyboardAvailable;
  out->settingsCameraEnabled = settingsCameraEnabled;
  out->settingsCameraAvailable = settingsCameraAvailable;
  out->settingsSoundEnabled = settingsSoundEnabled;

  return validateButtons(obj["buttons"], advertised, &out->buttons);
}

}  // namespace

Protocol::Protocol(String bootId, const int* advertisedButtons, int advertisedCount)
    : bootId_(std::move(bootId)) {
  for (int i = 0; i < advertisedCount; i++) advertised_.push_back(advertisedButtons[i]);
}

bool Protocol::parseLine(const String& line, ParsedMessage& out) const {
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, line);
  if (err) return false;
  if (!doc.is<JsonObject>()) return false;

  JsonVariantConst v = doc["v"];
  if (!v.is<int>() || v.as<int>() != PROTOCOL_VERSION) return false;

  JsonVariantConst type = doc["type"];
  if (!type.is<const char*>()) return false;
  String msgType = type.as<const char*>();

  JsonVariantConst connectionId = doc["connection_id"];
  if (!connectionId.is<const char*>() ||
      !isPrintableAscii(connectionId.as<const char*>(), 1, 64)) {
    return false;
  }

  if (msgType == "hello") {
    out.type = MsgType::Hello;
    out.connectionId = connectionId.as<const char*>();
    return true;
  }

  if (msgType == "ping") {
    JsonVariantConst nonce = doc["nonce"];
    if (!nonce.is<long>() || nonce.as<long>() < 0) return false;
    out.type = MsgType::Ping;
    out.connectionId = connectionId.as<const char*>();
    out.nonce = nonce.as<long>();
    return true;
  }

  if (msgType == "render") {
    JsonVariantConst revision = doc["revision"];
    if (!revision.is<long>() || revision.as<long>() <= 0) return false;
    View view;
    if (!validateView(doc["view"], advertised_, &view)) return false;
    out.type = MsgType::Render;
    out.connectionId = connectionId.as<const char*>();
    out.revision = revision.as<long>();
    out.view = std::move(view);
    return true;
  }

  if (msgType == "animate") {
    JsonVariantConst animationId = doc["animation_id"];
    if (!animationId.is<const char*>() ||
        !isPrintableAscii(animationId.as<const char*>(), 1, 96)) {
      return false;
    }
    JsonVariantConst afterRevision = doc["after_revision"];
    if (!afterRevision.is<long>() || afterRevision.as<long>() <= 0) return false;
    JsonVariantConst name = doc["name"];
    if (!name.is<const char*>() || !oneOf(name.as<const char*>(), kAnimationNames, 3)) {
      return false;
    }
    String nameStr = name.as<const char*>();
    JsonVariantConst foodSprite = doc["food_sprite"];
    bool hasFoodSprite = !foodSprite.isNull();
    if (nameStr == "feed") {
      // Any configured item's sprite_id (e.g. "jollof_rice", "espresso") is
      // valid here -- firmware doesn't assign meaning to which item it is,
      // only that a feed animation always names one.
      if (!hasFoodSprite || !foodSprite.is<const char*>() ||
          !isPrintableAscii(foodSprite.as<const char*>(), 1, 64)) {
        return false;
      }
    } else {
      if (hasFoodSprite) return false;
    }

    out.type = MsgType::Animate;
    out.connectionId = connectionId.as<const char*>();
    out.animationId = animationId.as<const char*>();
    out.afterRevision = afterRevision.as<long>();
    out.name = nameStr;
    out.hasFoodSprite = hasFoodSprite;
    if (hasFoodSprite) out.foodSprite = foodSprite.as<const char*>();
    return true;
  }

  return false;
}

void Protocol::feed(const uint8_t* data, size_t len, std::vector<ParsedMessage>& outMessages) {
  for (size_t i = 0; i < len; i++) {
    char c = static_cast<char>(data[i]);
    if (c == '\n') {
      String line = buffer_;
      buffer_ = "";
      bool wasDiscarding = discarding_;
      discarding_ = false;
      if (wasDiscarding) continue;
      if (line.endsWith("\r")) line.remove(line.length() - 1);
      ParsedMessage message;
      if (parseLine(line, message)) outMessages.push_back(std::move(message));
      continue;
    }
    if (!discarding_) {
      buffer_ += c;
      if (buffer_.length() >= MAX_LINE_BYTES) {
        buffer_ = "";
        discarding_ = true;
      }
    }
  }
}

bool Protocol::accept(const ParsedMessage& message, unsigned long nowMs, DeviceAction& outAction) {
  if (message.type == MsgType::Hello) {
    connectionId = message.connectionId;
    hasConnectionId = true;
    lastRevision_ = 0;
    controlEpoch = 0;
    connected = true;
    hasValidView = false;
    lastTrafficMs_ = nowMs;
    hasLastTraffic_ = true;
    outAction.kind = ActionKind::ResetConnection;
    return true;
  }

  if (!hasConnectionId || message.connectionId != connectionId) return false;
  lastTrafficMs_ = nowMs;
  hasLastTraffic_ = true;

  if (message.type == MsgType::Ping) {
    outAction.kind = ActionKind::Pong;
    outAction.nonce = message.nonce;
    return true;
  }

  if (message.type == MsgType::Render) {
    if (message.revision <= lastRevision_) return false;
    if (message.view.controlEpoch < controlEpoch) return false;
    lastRevision_ = message.revision;
    controlEpoch = message.view.controlEpoch;
    hasValidView = true;
    outAction.kind = ActionKind::SetView;
    outAction.view = message.view;
    outAction.revision = message.revision;
    return true;
  }

  if (message.type == MsgType::Animate) {
    if (message.afterRevision > lastRevision_) return false;
    outAction.kind = ActionKind::EnqueueAnimation;
    outAction.animationId = message.animationId;
    outAction.name = message.name;
    outAction.hasFoodSprite = message.hasFoodSprite;
    outAction.foodSprite = message.foodSprite;
    return true;
  }

  return false;
}

bool Protocol::isTimedOut(unsigned long nowMs, unsigned long timeoutMs) const {
  if (!hasLastTraffic_) return false;
  return (unsigned long)(nowMs - lastTrafficMs_) >= timeoutMs;
}

String Protocol::encodeReady() const {
  JsonDocument doc;
  doc["v"] = PROTOCOL_VERSION;
  doc["type"] = "ready";
  if (hasConnectionId) {
    doc["connection_id"] = connectionId;
  } else {
    doc["connection_id"] = nullptr;
  }
  doc["boot_id"] = bootId_;
  JsonArray buttons = doc["buttons"].to<JsonArray>();
  for (int id : advertised_) buttons.add(id);
  doc["ui"] = UI_ID;
  String out;
  serializeJson(doc, out);
  out += '\n';
  return out;
}

String Protocol::encodeButton(unsigned long seq, long controlEpochArg, int button,
                               const char* action) const {
  JsonDocument doc;
  doc["v"] = PROTOCOL_VERSION;
  doc["type"] = "button";
  doc["connection_id"] = connectionId;
  doc["boot_id"] = bootId_;
  doc["seq"] = seq;
  doc["control_epoch"] = controlEpochArg;
  doc["button"] = button;
  doc["action"] = action;
  String out;
  serializeJson(doc, out);
  out += '\n';
  return out;
}

String Protocol::encodePong(long nonce) const {
  JsonDocument doc;
  doc["v"] = PROTOCOL_VERSION;
  doc["type"] = "pong";
  doc["connection_id"] = connectionId;
  doc["nonce"] = nonce;
  String out;
  serializeJson(doc, out);
  out += '\n';
  return out;
}
