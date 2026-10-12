#include "motion_tracker_metadata.h"
#include <cassert>

int main() {
    using nlohmann::json;
    auto packet = json::parse(R"({"timeStampNs":100,"joints":[
        {"sn":"tracker-A","confidence":1,"timeStampNs":101},
        {"sn":"tracker-B","confidence":3}]})");
    auto result = parseMotionTrackerMetadata(packet);
    assert(result.size() == 2);
    assert(result[0].deviceId == "tracker-A" && result[0].confidence == 1);
    assert(result[0].timestampNs == 101);
    assert(result[1].deviceId == "tracker-B" && result[1].confidence == 3);
    assert(result[1].timestampNs == 100);

    // Reordering and legacy senders cannot reuse the previous slot's confidence.
    packet["joints"] = json::parse(R"([{"sn":"tracker-B"},{"sn":"tracker-A","confidence":0}])");
    result = parseMotionTrackerMetadata(packet);
    assert(result[0].deviceId == "tracker-B" && !result[0].confidence);
    assert(result[1].deviceId == "tracker-A" && result[1].confidence == 0);

    packet["joints"] = json::parse(R"([{}, {"confidence":null}, {"confidence":"1"}, {"confidence":1}])");
    result = parseMotionTrackerMetadata(packet);
    assert(result.size() == 3);
    for (const auto& item : result) {
        assert(item.deviceId.empty() && !item.confidence);
    }
    packet["joints"] = json::parse(R"([{"confidence":-1},{"confidence":4294967295},{"confidence":1.5}])");
    for (const auto& item : parseMotionTrackerMetadata(packet)) {
        assert(!item.confidence);
    }
    packet["joints"] = json::array();
    assert(parseMotionTrackerMetadata(packet).empty());
    assert(parseMotionTrackerMetadata(json::object()).empty());
    result = parseMotionTrackerMetadata(json::parse(R"({"joints":[{"sn":"tracker-C","confidence":2}]})"));
    assert(result[0].confidence == 2 && result[0].timestampNs == 0);
}
