// Shared color constants for icons.h and display.cpp.
#pragma once

#include <stdint.h>
#include <Arduino.h>

// Closest achievable approximation of hex 573336 in this display's 8-bit
// BGR332 format (3-bit blue, 3-bit green, 2-bit red): quantizing R=0x57,
// G=0x33, B=0x36 gives red2=1, green3=1, blue3=1, decoding back to roughly
// RGB(85,36,36) -- a dark maroon-brown, not an exact match (this format's
// weak 2-bit red channel can't reproduce it precisely).
constexpr uint8_t kInkColor = 0x25;
