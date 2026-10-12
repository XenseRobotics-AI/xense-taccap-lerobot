# Pico tracker 置信度 SDK 接口

Pico 端发送的 `Motion.joints[]` 中已有 `sn` 和 `confidence`。
本接口复用 TCP → XenseVR-PC-Service → `PXREADeviceStateJson` 的现有链路，
不增加 TCP 端口或协议命令。PC Service 必须转发完整的 `Motion` JSON 字段。

重新构建并安装 `src/lerobot/teleoperators/pico4/xensevr-pc-service-pybind/`
中的 Python 扩展后调用：

```python
import time
import xensevr_pc_service_sdk as xrt

xrt.init()
try:
    while True:
        for status in xrt.get_motion_tracker_status():
            print(status["device_id"], status["confidence"], status["timestamp_ns"])
        # 已知 tracker 序列号时，也可直接查询：
        # status = xrt.get_motion_tracker_status_by_id("PC2310MLJ6050513G")
        time.sleep(0.1)
finally:
    xrt.close()
```

`get_motion_tracker_status() -> list[dict]` 一次返回最新 Motion 数据包中
最多三个 tracker 的一致快照。尚未收到数据或最新包的 tracker 列表为空时返回 `[]`。
`get_motion_tracker_status_by_id(device_id: str) -> dict | None` 按序列号查找，
最新包中没有该设备时返回 `None`。

每个字典包含：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `device_id` | `str` | tracker 的 `sn` 序列号，不是头显 ID；缺失时为空字符串 |
| `confidence` | `int \| None` | Pico 原始非负整数置信度枚举；缺失、类型错误或超出 int32 时为 `None` |
| `timestamp_ns` | `int` | 优先使用 joint 的 `timeStampNs`，否则使用 Motion 包时间戳；未提供时为 0 |

当前本地消费版 Pico 发送端使用 `1` 表示正在跟踪、`3` 表示当前未跟踪。
企业版透传其 SDK 原始值。置信度不是 0～1 的概率，不做归一化或跨版本枚举转换。
时间戳沿用发送端时钟，不能假定是 PC 的 Unix 时间。

设备顺序变化不会沿用上一设备的置信度。旧发送端缺少 `confidence` 时返回
`None`，调用方应将其视为未知，而不是可靠。每个结果是独立副本。
现有位姿、序列号等 SDK 接口保持兼容。

接口读取缓存，不等待新包。链路停止发送时仍可读到最后一包；调用方应观察
时间戳是否继续更新并自行判定超时。`close()` 清除 tracker 状态缓存。

解析回归测试（需 C++17 编译器与 nlohmann/json 头文件）：

```bash
c++ -std=c++17 -Ibindings tests/test_motion_tracker_metadata.cpp -o /tmp/test_tracker_metadata
/tmp/test_tracker_metadata
```
