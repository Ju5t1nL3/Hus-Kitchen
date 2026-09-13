"""Protocol-v2 framing, decoding and encoding boundary tests."""

import json
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from deskpet.adapters.wire_codec import (
    MAX_LINE_BYTES,
    AnimateMessage,
    EncodeError,
    HelloMessage,
    LineDecoder,
    PingMessage,
    RenderMessage,
    decode_line,
    encode,
)
from deskpet.core.models import (
    ButtonId,
    ClockReading,
    Feedback,
    Mood,
    Screen,
)
from deskpet.core.views import (
    AnimationCue,
    AnimationName,
    ButtonInput,
    ButtonLabel,
    DeviceReady,
    Invalid,
    Parsed,
    Pong,
    ProgressionView,
    RenderSnapshot,
)

CONTRACTS = Path(__file__).parents[3] / "contracts"
NOW = ClockReading(datetime(2026, 9, 13, 4, 30, tzinfo=UTC), 10_000, False)
BUTTONS = (ButtonId(1), ButtonId(2), ButtonId(3))


def home() -> RenderSnapshot:
    return RenderSnapshot(
        screen=Screen.HOME,
        control_epoch=1,
        mood=Mood.IDLE,
        clock_text="14:32",
        timer_seconds=None,
        paused=False,
        focus_minutes=None,
        break_minutes=None,
        buttons=(
            ButtonLabel(ButtonId(1), "Feed", True),
            ButtonLabel(ButtonId(2), "Focus", True),
            ButtonLabel(ButtonId(3), "-", False),
        ),
        feedback=None,
        progression=ProgressionView(1, 0, 100, 10),
    )


class DecodeTests(unittest.TestCase):
    def test_all_shared_pico_fixtures_decode_to_typed_messages(self) -> None:
        lines = (CONTRACTS / "pico_to_laptop.v2.jsonl").read_bytes().splitlines()

        results = [decode_line(line, NOW, BUTTONS) for line in lines]

        self.assertTrue(all(isinstance(result, Parsed) for result in results))
        messages = [cast(Parsed, result).message for result in results]
        self.assertIsInstance(messages[0], DeviceReady)
        self.assertIsInstance(messages[2], ButtonInput)
        self.assertIsInstance(messages[-1], Pong)
        button = cast(ButtonInput, messages[2])
        self.assertEqual(button.received_at, NOW)

    def test_invalid_encoding_json_version_type_and_integer_shapes_are_rejected(
        self,
    ) -> None:
        cases = {
            b"\xff": "bad_utf8",
            b"{": "bad_json",
            b"[]": "not_object",
            b'{"v":1,"type":"pong"}': "bad_version",
            b'{"v":2,"type":"future"}': "unknown_type",
            b'{"v":2,"type":"pong","connection_id":"c","nonce":true}': "bad_nonce",
            b'{"v":2,"type":"button","connection_id":"c","boot_id":"b","seq":1,"control_epoch":1,"button":1,"action":"tap"}': "bad_action",
        }
        for raw, code in cases.items():
            with self.subTest(code=code):
                self.assertEqual(decode_line(raw, NOW), Invalid(code))

    def test_button_must_be_declared_by_ready_capabilities(self) -> None:
        raw = b'{"v":2,"type":"button","connection_id":"c","boot_id":"b","seq":1,"control_epoch":1,"button":3,"action":"press"}'

        result = decode_line(raw, NOW, (ButtonId(1), ButtonId(2)))

        self.assertEqual(result, Invalid("undeclared_button"))

    def test_direct_line_limit_includes_terminating_newline(self) -> None:
        self.assertEqual(
            decode_line(b" " * MAX_LINE_BYTES, NOW), Invalid("line_too_long")
        )


class FramingTests(unittest.TestCase):
    def test_fragmented_and_combined_crlf_input_is_assembled(self) -> None:
        first = b'{"v":2,"type":"pong","connection_id":"c","nonce":1}\r\n'
        second = b'{"v":2,"type":"pong","connection_id":"c","nonce":2}\n'
        decoder = LineDecoder()

        prefix = decoder.feed(first[:12], NOW)
        results = decoder.feed(first[12:] + second, NOW)

        self.assertEqual(prefix, ())
        self.assertEqual(
            results,
            (
                Parsed(Pong("c", 1)),
                Parsed(Pong("c", 2)),
            ),
        )

    def test_oversized_input_is_discarded_through_newline_then_recovers(self) -> None:
        decoder = LineDecoder()
        valid = b'{"v":2,"type":"pong","connection_id":"c","nonce":2}\n'

        results = decoder.feed(b"x" * (MAX_LINE_BYTES + 50) + b"\n" + valid, NOW)

        self.assertEqual(results[0], Invalid("line_too_long"))
        self.assertEqual(results[1], Parsed(Pong("c", 2)))

    def test_reset_discards_an_incomplete_previous_connection_line(self) -> None:
        decoder = LineDecoder()
        decoder.feed(b'{"v":2', NOW)
        decoder.reset()

        results = decoder.feed(
            b'{"v":2,"type":"pong","connection_id":"c","nonce":2}\n', NOW
        )

        self.assertEqual(results, (Parsed(Pong("c", 2)),))


class EncodeTests(unittest.TestCase):
    def test_shared_hello_ping_and_home_render_encode_exactly(self) -> None:
        fixture_lines = (
            (CONTRACTS / "laptop_to_pico.v2.jsonl")
            .read_bytes()
            .splitlines(keepends=True)
        )

        actual = (
            encode(HelloMessage("link-001")),
            encode(PingMessage("link-001", 7)),
            encode(RenderMessage("link-001", 1, home()), BUTTONS),
        )

        self.assertEqual(actual, tuple(fixture_lines[:3]))
        for encoded in actual:
            self.assertTrue(encoded.endswith(b"\n"))
            self.assertNotIn(b"\n", encoded[:-1])
            self.assertNotIn(b'": ', encoded)

    def test_complete_view_must_match_screen_and_declared_button_order(self) -> None:
        invalid_views = (
            replace(home(), clock_text=None),
            replace(home(), timer_seconds=5),
            replace(home(), paused=True),
            replace(home(), focus_minutes=25),
            replace(home(), break_minutes=5),
            replace(home(), buttons=home().buttons[:2]),
            replace(home(), control_epoch=0),
        )
        for view in invalid_views:
            with self.subTest(view=view), self.assertRaises(EncodeError):
                encode(RenderMessage("c", 1, view), BUTTONS)

    def test_setup_and_timer_ranges_are_validated(self) -> None:
        feed = replace(home(), screen=Screen.FEED, clock_text=None)
        setup = replace(
            home(),
            screen=Screen.SETUP,
            clock_text=None,
            focus_minutes=25,
            break_minutes=5,
            progression=None,
        )
        timer = replace(
            home(),
            screen=Screen.FOCUS,
            clock_text=None,
            timer_seconds=60,
            mood=Mood.FOCUSED,
            progression=None,
        )
        clock_reveal = replace(timer, clock_text="14:32", timer_seconds=None)

        encode(RenderMessage("c", 1, feed), BUTTONS)
        encode(RenderMessage("c", 1, setup), BUTTONS)
        encode(RenderMessage("c", 1, timer), BUTTONS)
        encode(RenderMessage("c", 1, clock_reveal), BUTTONS)
        for view in (
            replace(setup, focus_minutes=7),
            replace(setup, break_minutes=0),
            replace(timer, timer_seconds=3_601),
            replace(clock_reveal, clock_text="25:00"),
            replace(clock_reveal, timer_seconds=60),
        ):
            with self.subTest(view=view), self.assertRaises(EncodeError):
                encode(RenderMessage("c", 1, view), BUTTONS)

    def test_ids_labels_and_animation_fields_require_protocol_ascii_and_shapes(
        self,
    ) -> None:
        with self.assertRaises(EncodeError):
            encode(HelloMessage("pet-🐈"))
        with self.assertRaises(EncodeError):
            encode(
                RenderMessage(
                    "c",
                    1,
                    replace(
                        home(),
                        buttons=(
                            ButtonLabel(ButtonId(1), "🐈", True),
                            *home().buttons[1:],
                        ),
                    ),
                ),
                BUTTONS,
            )
        with self.assertRaises(EncodeError):
            encode(
                AnimateMessage(
                    "c",
                    AnimationCue("id", AnimationName.FEED, 1, None),
                )
            )
        with self.assertRaises(EncodeError):
            encode(
                AnimateMessage(
                    "c",
                    AnimationCue("id", AnimationName.CELEBRATE, 1, "food_basic"),
                )
            )

    def test_overlong_field_is_rejected_before_encoding(self) -> None:
        huge = "x" * 2_000
        view = replace(
            home(),
            feedback=Feedback.STORAGE_ERROR,
            buttons=(
                ButtonLabel(ButtonId(1), "Feed", True),
                ButtonLabel(ButtonId(2), "Focus", True),
                ButtonLabel(ButtonId(3), huge, False),
            ),
        )

        with self.assertRaises(EncodeError):
            encode(RenderMessage("c", 1, view), BUTTONS)

    def test_encoded_json_is_one_complete_object(self) -> None:
        encoded = encode(PingMessage("c", 0))
        parsed = cast(dict[str, object], json.loads(encoded))

        self.assertEqual(parsed["nonce"], 0)


if __name__ == "__main__":
    unittest.main()
