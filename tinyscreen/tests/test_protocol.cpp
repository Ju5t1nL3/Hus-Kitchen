// Host-side test for the firmware's wire validator.
//
// The protocol has no render acknowledgement, so a device cannot tell the host
// "I accepted that view". That makes on-device fixture replay unobservable and
// this host test the practical way to prove the firmware agrees with
// docs/serial_protocol.md. It compiles the real protocol.cpp (not a copy)
// against a tiny Arduino shim and replays the shared contract fixtures.
//
// Build and run with tinyscreen/tests/run_tests.sh.

#include <cstdio>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

#include "protocol.h"

namespace {

int failures = 0;

void check(bool condition, const std::string& what) {
  if (condition) {
    std::cout << "  ok   " << what << "\n";
  } else {
    std::cout << "  FAIL " << what << "\n";
    failures++;
  }
}

std::vector<std::string> readLines(const std::string& path) {
  std::vector<std::string> lines;
  std::ifstream file(path);
  if (!file) {
    std::cout << "  FAIL cannot open " << path << "\n";
    failures++;
    return lines;
  }
  std::string line;
  while (std::getline(file, line)) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    if (!line.empty()) lines.push_back(line);
  }
  return lines;
}

// The device advertises four corner buttons; every render fixture must label
// exactly these, in this order.
const int kAdvertised[] = {1, 2, 3, 4};
constexpr int kAdvertisedCount = 4;

Protocol makeProtocol() {
  return Protocol("boot-test", kAdvertised, kAdvertisedCount);
}

// Feed one whole line (plus newline) and return the parsed messages.
std::vector<ParsedMessage> feedLine(Protocol& protocol, const std::string& line) {
  std::vector<ParsedMessage> messages;
  std::string framed = line + "\n";
  protocol.feed(reinterpret_cast<const uint8_t*>(framed.data()), framed.size(), messages);
  return messages;
}

void testSharedFixturesAreAccepted(const std::string& contractsDir) {
  std::cout << "laptop -> device fixtures\n";
  Protocol protocol = makeProtocol();
  unsigned long now = 1000;

  std::vector<std::string> lines = readLines(contractsDir + "/laptop_to_pico.v2.jsonl");
  check(!lines.empty(), "fixture file is non-empty");

  int renders = 0;
  for (size_t i = 0; i < lines.size(); i++) {
    std::vector<ParsedMessage> messages = feedLine(protocol, lines[i]);
    std::string label = "line " + std::to_string(i + 1) + " parses";
    check(messages.size() == 1, label);
    if (messages.size() != 1) continue;

    DeviceAction action;
    bool accepted = protocol.accept(messages[0], now, action);
    check(accepted, "line " + std::to_string(i + 1) + " is accepted");
    if (messages[0].type == MsgType::Render && accepted) {
      renders++;
      check(action.view.buttons.size() == 4,
            "render " + std::to_string(renders) + " labels all four buttons");
    }
    now += 10;
  }
  check(renders == 7, "all seven screen fixtures round-trip");
}

void testEveryDocumentedMoodIsAccepted() {
  std::cout << "mood vocabulary\n";
  const char* moods[] = {"idle",           "happy",       "sad",      "hungry",
                         "working_neutral", "working_sad", "sleeping", "party"};
  for (const char* mood : moods) {
    Protocol protocol = makeProtocol();
    feedLine(protocol, R"({"v":2,"type":"hello","connection_id":"c1"})");
    std::vector<ParsedMessage> hello;
    DeviceAction action;

    std::string render =
        std::string(R"({"v":2,"type":"render","connection_id":"c1","revision":1,"view":{)") +
        R"("screen":"home","control_epoch":1,"mood":")" + mood +
        R"(","clock_text":"14:32","timer_seconds":null,"paused":false,)"
        R"("focus_minutes":null,"break_minutes":null,"buttons":[)"
        R"({"button":1,"label":"Feed","enabled":true},)"
        R"({"button":2,"label":"Focus","enabled":true},)"
        R"({"button":3,"label":"-","enabled":false},)"
        R"({"button":4,"label":"-","enabled":false}],)"
        R"("feedback":null,"progression":null,"earned_rewards":null}})";
    std::vector<ParsedMessage> messages = feedLine(protocol, render);
    check(messages.size() == 1, std::string("mood ") + mood + " is accepted");
  }

  Protocol protocol = makeProtocol();
  std::vector<ParsedMessage> messages = feedLine(
      protocol,
      R"({"v":2,"type":"render","connection_id":"c1","revision":1,"view":{"screen":"home",)"
      R"("control_epoch":1,"mood":"calm","clock_text":null,"timer_seconds":null,"paused":false,)"
      R"("focus_minutes":null,"break_minutes":null,"buttons":[{"button":1,"label":"Feed","enabled":true},)"
      R"({"button":2,"label":"Focus","enabled":true},{"button":3,"label":"-","enabled":false},)"
      R"({"button":4,"label":"-","enabled":false}],"feedback":null,"progression":null,)"
      R"("earned_rewards":null}})");
  check(messages.empty(), "a retired mood (calm) is rejected");
}

void testButtonCountMustMatchAdvertisement() {
  std::cout << "button advertisement\n";
  Protocol protocol = makeProtocol();
  std::vector<ParsedMessage> messages = feedLine(
      protocol,
      R"({"v":2,"type":"render","connection_id":"c1","revision":1,"view":{"screen":"home",)"
      R"("control_epoch":1,"mood":"idle","clock_text":null,"timer_seconds":null,"paused":false,)"
      R"("focus_minutes":null,"break_minutes":null,"buttons":[{"button":1,"label":"Feed","enabled":true},)"
      R"({"button":2,"label":"Focus","enabled":true},{"button":3,"label":"-","enabled":false}],)"
      R"("feedback":null,"progression":null,"earned_rewards":null}})");
  check(messages.empty(), "a three-button view is rejected by a four-button device");
}

void testOptionalObjectsParse() {
  std::cout << "optional view objects\n";
  Protocol protocol = makeProtocol();
  feedLine(protocol, R"({"v":2,"type":"hello","connection_id":"c1"})");

  std::vector<ParsedMessage> messages = feedLine(
      protocol,
      R"({"v":2,"type":"render","connection_id":"c1","revision":1,"view":{"screen":"break_offer",)"
      R"("control_epoch":1,"mood":"party","clock_text":null,"timer_seconds":null,"paused":false,)"
      R"("focus_minutes":null,"break_minutes":5,"buttons":[{"button":1,"label":"Break","enabled":true},)"
      R"({"button":2,"label":"Again","enabled":true},{"button":3,"label":"Home","enabled":true},)"
      R"({"button":4,"label":"-","enabled":false}],"feedback":null,"progression":null,)"
      R"("earned_rewards":{"xp":75,"yarn":3}}})");
  check(messages.size() == 1, "break_offer with earned_rewards parses");
  if (messages.size() == 1) {
    check(messages[0].view.hasEarnedRewards, "earned_rewards is recorded");
    check(messages[0].view.earnedXp == 75, "earned xp is 75");
    check(messages[0].view.earnedYarn == 3, "earned yarn is 3");
  }
}

void testReadyAdvertisesFourButtons() {
  std::cout << "outbound ready\n";
  Protocol protocol = makeProtocol();
  String ready = protocol.encodeReady();
  std::string text(ready.c_str());
  check(text.find("\"buttons\":[1,2,3,4]") != std::string::npos,
        "ready advertises [1,2,3,4]");
  check(text.find("\"ui\":\"emotions_v1\"") != std::string::npos,
        "ready declares the emotions_v1 UI");
  check(!text.empty() && text.back() == '\n', "ready is newline framed");
}

void testOversizedLineIsDiscarded() {
  std::cout << "framing limits\n";
  Protocol protocol = makeProtocol();
  std::string oversized(MAX_LINE_BYTES + 50, 'x');
  std::vector<ParsedMessage> messages = feedLine(protocol, oversized);
  check(messages.empty(), "an oversized line yields no message");

  // The parser must resynchronise on the next newline.
  messages = feedLine(protocol, R"({"v":2,"type":"hello","connection_id":"c1"})");
  check(messages.size() == 1, "the following line still parses");
}

}  // namespace

int main(int argc, char** argv) {
  std::string contractsDir = argc > 1 ? argv[1] : "../../contracts";

  testSharedFixturesAreAccepted(contractsDir);
  testEveryDocumentedMoodIsAccepted();
  testButtonCountMustMatchAdvertisement();
  testOptionalObjectsParse();
  testReadyAdvertisesFourButtons();
  testOversizedLineIsDiscarded();

  std::cout << "\n" << (failures == 0 ? "PASS" : "FAIL") << " (" << failures
            << " failing checks)\n";
  return failures == 0 ? 0 : 1;
}
