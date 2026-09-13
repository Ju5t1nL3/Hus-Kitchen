// Minimal desktop stand-ins for the Arduino APIs that protocol.cpp uses, so
// the firmware's wire validator can be compiled and tested on a host machine
// against the shared contract fixtures. This is a TEST shim only: it is never
// compiled into the firmware, which uses the real Arduino core.
//
// Keep this surface as small as the firmware actually needs. If protocol.cpp
// starts using another Arduino API, add it here deliberately rather than
// pulling in a full Arduino emulation layer.
#pragma once

#include <cstddef>
#include <cstring>
#include <string>

inline bool isDigit(char c) {
  return c >= '0' && c <= '9';
}

// Arduino's String, reduced to the operations the validator performs.
class String {
 public:
  String() = default;
  String(const char* value) : value_(value == nullptr ? "" : value) {}
  String(const std::string& value) : value_(value) {}
  explicit String(int value) : value_(std::to_string(value)) {}
  explicit String(long value) : value_(std::to_string(value)) {}
  explicit String(unsigned long value) : value_(std::to_string(value)) {}

  const char* c_str() const { return value_.c_str(); }
  size_t length() const { return value_.size(); }

  bool endsWith(const String& suffix) const {
    if (suffix.value_.size() > value_.size()) return false;
    return value_.compare(value_.size() - suffix.value_.size(), suffix.value_.size(),
                          suffix.value_) == 0;
  }

  void remove(size_t index) {
    if (index < value_.size()) value_.erase(index);
  }

  String& operator+=(char c) {
    value_.push_back(c);
    return *this;
  }
  String& operator+=(const String& other) {
    value_ += other.value_;
    return *this;
  }

  // ArduinoJson writes into an Arduino String through concat().
  void concat(char c) { value_.push_back(c); }
  void concat(const char* s) { value_ += s; }

  friend bool operator==(const String& a, const String& b) { return a.value_ == b.value_; }
  friend bool operator!=(const String& a, const String& b) { return a.value_ != b.value_; }
  friend bool operator==(const String& a, const char* b) { return a.value_ == b; }
  friend bool operator!=(const String& a, const char* b) { return a.value_ != b; }

  friend String operator+(const String& a, const String& b) { return String(a.value_ + b.value_); }

 private:
  std::string value_;
};
