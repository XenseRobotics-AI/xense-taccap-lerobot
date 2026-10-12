#pragma once

#include <algorithm>
#include <cstdint>
#include <optional>
#include <string>
#include <utility>
#include <vector>
#include <nlohmann/json.hpp>

// One packet's metadata. Never inherit identity or confidence from an older slot.
struct MotionTrackerMetadata {
    std::string deviceId;  // Tracker serial number, not the headset ID.
    std::optional<int> confidence;
    int64_t timestampNs = 0;
};

inline std::vector<MotionTrackerMetadata> parseMotionTrackerMetadata(const nlohmann::json& motion) {
    std::vector<MotionTrackerMetadata> result;
    if (!motion.contains("joints") || !motion["joints"].is_array()) {
        return result;
    }
    const auto& joints = motion["joints"];
    const auto count = std::min<size_t>(joints.size(), 3);
    for (size_t i = 0; i < count; ++i) {
        const auto& joint = joints[i];
        MotionTrackerMetadata item;
        if (joint.contains("sn") && joint["sn"].is_string()) {
            item.deviceId = joint["sn"].get<std::string>();
        }
        // Preserve the raw PICO integer enum; absent/invalid is unknown.
        if (joint.contains("confidence") && joint["confidence"].is_number_integer()) {
            const auto& confidence = joint["confidence"];
            if (confidence >= 0 && confidence <= INT32_MAX) {
                item.confidence = confidence.get<int>();
            }
        }
        const auto& timestamp = joint.contains("timeStampNs") ? joint : motion;
        if (timestamp.contains("timeStampNs") && timestamp["timeStampNs"].is_number_integer()) {
            item.timestampNs = timestamp["timeStampNs"].get<int64_t>();
        }
        result.push_back(std::move(item));
    }
    return result;
}
