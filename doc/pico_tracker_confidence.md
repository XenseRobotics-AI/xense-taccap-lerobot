# Pico tracker 置信度接口

重新构建安装 `src/lerobot/teleoperators/pico4/xensevr-pc-service-pybind/` 后调用：

```python
import xensevr_pc_service_sdk as xrt

xrt.init()
try:
    print(xrt.get_motion_tracker_status())
    print(xrt.get_motion_tracker_status_by_id("PC2310MLJ6050513G"))
finally:
    xrt.close()
```

返回字段：`device_id` 为 tracker 序列号（`sn`），`confidence` 为 Pico 原始整数枚举，
`timestamp_ns` 优先使用 joint 时间戳，否则使用 Motion 包时间戳，未提供时为 0。
消费版发送端使用 `1` 表示正在跟踪、`3` 表示未跟踪；企业版透传原始值。
缺少或无效的置信度返回 `None`，不是 0～1 的概率。

全部查询返回最新包的一致快照列表，最多三个 tracker，无数据时为 `[]`；
按序列号查询找不到设备时返回 `None`。链路断开后仍可能读到最后一包，调用方应
观察时间戳是否继续更新；时间戳沿用发送端时钟。`close()` 清除状态。

复用现有 TCP → PC Service → `PXREADeviceStateJson` 链路，PC Service 必须转发
`Motion.joints[]` 的 `sn` 和 `confidence`，不新增端口或协议命令。
