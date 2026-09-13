// Named beep sequences for SoundPlayer. See sound.h for why these are
// procedural tones rather than recorded WAV playback.
#pragma once

#include "sound.h"

constexpr ToneStep kSoundReady[] = {{880, 80}};
constexpr ToneStep kSoundPress[] = {{1200, 25}};
constexpr ToneStep kSoundFeed[] = {{660, 70}, {880, 70}, {1320, 110}};
constexpr ToneStep kSoundCelebrate[] = {{660, 80}, {880, 80}, {990, 80}, {1320, 140}};

// A cheerful rising arpeggio (C5-E5-G5-C6) for the moment a focus session
// completes -- fired when the laptop navigates to break_offer, not by a
// dedicated animation cue (the protocol only defines "feed"/"celebrate", and
// break_offer already gets its own "celebrate" cue for the pet's pose; this
// is purely a sound layered on top of that same moment). See firmware.ino's
// screen-transition detection in dispatch().
constexpr ToneStep kSoundPomodoroComplete[] = {
    {523, 110},  // C5
    {659, 110},  // E5
    {784, 110},  // G5
    {1047, 220}, // C6
};

// A gentle descending three-note chime (G5-E5-C5) for the moment a break
// ends and focus resumes -- fired when the laptop navigates away from the
// break screen. Calmer than the completion fanfare on purpose: this is
// "back to it", not a celebration.
constexpr ToneStep kSoundBreakEnd[] = {
    {784, 120},  // G5
    {659, 120},  // E5
    {523, 220},  // C5
};

// Chiptune arrangement inspired by "Littleroot Town" (Pokemon Ruby/Sapphire/
// Emerald, composed by Junichi Masuda). This is NOT a verified note-for-note
// transcription -- the sources checked for it (piano letter-notes, kalimba
// tabs, virtual-piano sheets) disagree with each other on exact pitches, and
// some use an ambiguous shorthand this couldn't be safely decoded from. It's
// an ear/reference approximation: phrase one is the opening rising motif (C
// F G A / C G A G), extended here with a variation and a descending answer
// phrase so it loops as a longer, more song-like background line rather than
// a single repeated fragment. Frequencies are equal-temperament (A4=440Hz),
// played as a monophonic square-wave line on the DAC; see firmware.ino for
// where this is started as a looping background track via playBackground().
constexpr ToneStep kSoundLittlerootTown[] = {
    // Phrase A -- opening motif
    {262, 220},  // C4
    {349, 220},  // F4
    {392, 220},  // G4
    {440, 220},  // A4
    {523, 320},  // C5
    {392, 220},  // G4
    {440, 220},  // A4
    {392, 380},  // G4
    // Phrase A' -- same shape, reaches a step higher before resolving
    {262, 220},  // C4
    {349, 220},  // F4
    {392, 220},  // G4
    {440, 220},  // A4
    {523, 320},  // C5
    {587, 220},  // D5
    {523, 220},  // C5
    {440, 380},  // A4
    // Phrase B -- descending answer, resolves back to the top of the loop
    {392, 220},  // G4
    {330, 220},  // E4
    {349, 220},  // F4
    {294, 220},  // D4
    {330, 220},  // E4
    {262, 220},  // C4
    {294, 220},  // D4
    {262, 460},  // C4
};
