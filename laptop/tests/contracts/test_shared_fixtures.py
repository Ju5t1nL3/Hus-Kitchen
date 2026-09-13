"""Structural checks for fixtures shared with the Pico runtime."""

import json
import unittest
from pathlib import Path
from typing import cast

type JsonValue = (
    None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
)

CONTRACTS = Path(__file__).parents[3] / "contracts"


def load_objects(filename: str) -> list[dict[str, JsonValue]]:
    objects: list[dict[str, JsonValue]] = []
    for line in (CONTRACTS / filename).read_text(encoding="utf-8").splitlines():
        value = cast(JsonValue, json.loads(line))
        if not isinstance(value, dict):
            raise TypeError("each fixture line must be a JSON object")
        objects.append(value)
    return objects


class ProtocolFixtureTests(unittest.TestCase):
    def test_pico_examples_include_extra_advertised_button(self) -> None:
        messages = load_objects("pico_to_laptop.v2.jsonl")
        ready = next(message for message in messages if message["type"] == "ready")
        buttons = ready["buttons"]

        self.assertEqual(buttons, [1, 2, 3, 4])
        self.assertTrue(
            any(message.get("button") == 3 for message in messages),
            "an advertised extra button needs a matching input example",
        )

    def test_each_render_labels_every_advertised_button(self) -> None:
        messages = load_objects("laptop_to_pico.v2.jsonl")
        renders = [message for message in messages if message["type"] == "render"]

        self.assertGreater(len(renders), 0)
        for render in renders:
            view = cast(dict[str, JsonValue], render["view"])
            labels = cast(list[JsonValue], view["buttons"])
            ids = [cast(dict[str, JsonValue], label)["button"] for label in labels]
            self.assertEqual(ids, [1, 2, 3, 4])


class EventFixtureTests(unittest.TestCase):
    def test_events_are_ordered_schema_v2(self) -> None:
        events = load_objects("events.v2.jsonl")

        self.assertEqual([event["seq"] for event in events], list(range(1, 8)))
        versions = {cast(int, event["schema_version"]) for event in events}
        self.assertEqual(versions, {2})

    def test_active_time_boundary_has_both_expected_outcomes(self) -> None:
        events = load_objects("events.v2.jsonl")
        ended = [event for event in events if event["type"] == "session_ended"]
        outcomes: set[tuple[int, str]] = set()
        for event in ended:
            payload = cast(dict[str, JsonValue], event["payload"])
            outcomes.add(
                (cast(int, payload["active_ms"]), cast(str, payload["reason"]))
            )

        self.assertEqual(
            outcomes,
            {(59_999, "user_grace"), (60_000, "user_early")},
        )


if __name__ == "__main__":
    unittest.main()
