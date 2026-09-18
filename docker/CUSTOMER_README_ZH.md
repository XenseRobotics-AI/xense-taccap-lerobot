# TacCap 数据采集安装包（国内网络安装）

把本文件所在的**整个文件夹**复制到新电脑即可。无需克隆 GitHub，也无需拉取国外容器镜像。
镜像已经放在本目录的 `.tar` 文件中；安装 Docker 等宿主机组件时仍需国内网络。

## 1. 新电脑准备

- 推荐 Ubuntu 22.04 / 24.04 桌面版，架构为 amd64（Intel/AMD 64 位）。
- 需要有 sudo 权限的普通用户。不要登录 root 安装，也不要执行 `sudo ./install_cn.sh`。
- 预先安装 NVIDIA 显卡驱动并重启，`nvidia-smi` 必须正常；版本至少为 570.144，且应支持具体显卡型号。
- 建议至少预留 60 GB 空间供安装包和镜像使用，采集数据还需额外空间。
- 新电脑能够访问中科大镜像站。本包不是完全断网安装包，也不包含宿主机显卡驱动。

检查命令（在新电脑的宿主机终端执行）：

```bash
cat /etc/os-release
dpkg --print-architecture
nvidia-smi
df -h "$HOME"
```

安装脚本会配置设备权限并重启 Docker。请先结束新电脑上已有的容器任务。

## 2. 复制整个文件夹

可以通过移动硬盘、U 盘或局域网传输。镜像 tar 超过 4 GB，请使用 ext4、exFAT、NTFS 等
支持大文件的文件系统，不要使用 FAT32。复制时包含隐藏的 `.env`，不要只复制安装脚本。

在文件管理器中打开复制后的文件夹，右键“在终端打开”。确认内容：

```bash
pwd
ls -lah
sha256sum --check SHA256SUMS
```

校验应显示 `OK`。如果失败，重新复制镜像 tar，不要跳过校验。

## 3. 换源与安装

在当前文件夹执行：

```bash
bash ./install_cn.sh
```

按提示输入当前用户的 sudo 密码。脚本自动完成以下操作：

1. 校验本地镜像 tar，校验失败时在安装宿主机组件前停止。
2. 为本次安装生成国内 APT 源：Ubuntu/Debian 系统依赖使用中科大源，Docker CE 使用中科大源，
   NVIDIA Container Toolkit 使用中科大源。NVIDIA 列表里的包下载地址也会替换为国内地址。
3. 安装缺少的 Docker、Compose、NVIDIA Container Toolkit，并配置 GPU 和 USB 设备权限。
4. 执行 `docker load` 导入镜像，再用它运行 CUDA 和图形能力检查。
   CUDA 检查失败会停止安装；图形检查失败会警告，启用显示前需先解决。
   安装完成应出现 `Installation completed successfully`。

**无需手动修改 `/etc/apt/sources.list`。** 国内系统源仅供本次安装使用，不覆盖宿主机原有系统源；
脚本新建的 Docker/NVIDIA 仓库配置会保留国内地址。已有组件会跳过安装。
本模式缺少 tar 或国内源不可达时会报错，不会自动回退到 GHCR 或国外软件源；保留 APT 签名验证。

安装完成后，**注销桌面并重新登录**，让新增的用户组权限生效。
然后重新打开这个交付文件夹中的终端，后续命令都在这里执行。

## 4. 选择数据保存位置

默认数据保存在 Docker 的 `lerobot-data` 卷中，退出容器不会删除。
如果希望直接在新电脑的用户目录查看数据，首次采集前执行：

```bash
mkdir -p "$HOME/taccap-data"
printf '\nLEROBOT_DATA_DIR=%s/taccap-data\n' "$HOME" >> .env
```

这一步只做一次。容器以 root 写入，必要时结束采集后可执行
`sudo chown -R "$(id -u):$(id -g)" "$HOME/taccap-data"`，仅修改这个专用数据目录。

## 5. 启动容器

先查看镜像配置，确认它与 `delivery.env` 中的镜像名称和版本一致：

```bash
cat delivery.env
docker compose config --images
```

镜像名称即使包含 `ghcr.io`，也只是导入镜像的本地名称，以下启动命令不会访问 GHCR。

如果需要 Rerun 等图形窗口，先执行：

```bash
xhost +si:localuser:root
```

启动并进入容器：

```bash
docker compose run --rm --pull never xense-taccap
```

交付包的 `compose.override.yaml` 也设置了 `pull_policy: never`。不要执行 `docker compose pull`
或 `docker compose build`：客户机直接使用导入的镜像，不需要重新下载或构建环境。

## 6. 语音与首次采集

宿主机应登录桌面音频会话，不要从 root 桌面或纯 SSH 会话启动语音采集。
进入容器后，先单独测试：

```bash
timeout 8s spd-say -l en -o espeak-ng --wait 'Recording episode zero'
echo $?
```

应听到英文提示，退出码应为 `0`；`124` 表示超时。容器通过宿主机 PulseAudio/PipeWire
音频接口播放，请检查宿主机是否静音、输出设备是否正确。

连接并上电 TacCap 设备；如启用 Pico4 跟踪或头显相机，先按设备操作流程让头显应用、跟踪器
与 PC 服务连通。首次建议录制短片段，以下示例适用于双夹爪及已连通的 Pico4：

```bash
lerobot-record \
  --robot.type=bi_taccap_gripper \
  --robot.id=0 \
  --robot.enable_tracker=true \
  --robot.enable_head_camera=true \
  --display_data=false \
  --dataset.repo_id=local/taccap-first-test \
  --dataset.num_episodes=1 \
  --dataset.fps=30 \
  --dataset.push_to_hub=false \
  --dataset.episode_time_s=10 \
  --dataset.single_task='Pick up the object'
```

重复测试请换一个新的 `dataset.repo_id`。先让这次短录制自然结束，确认相机正常退出；
语音排查期间可以给命令加 `--play_sounds=false`。正式录制之前，还需检查保存的图像、姿态和夹爪数据。

退出容器执行 `exit`。`--rm` 只删除临时容器，不删除数据卷；在容器里临时修改软件不会写回镜像。

## 7. 常见问题

| 现象                                  | 处理方法                                                                                   |
| ------------------------------------- | ------------------------------------------------------------------------------------------ |
| 校验失败、找不到 tar                  | 确认复制了整个文件夹，重新复制损坏的文件。不要删掉校验文件。                               |
| 国内软件源连接失败                    | 检查新电脑 DNS、时间、网络和镜像站访问情况；恢复后重试安装。此模式不会回退国外源。         |
| `nvidia-smi` 失败或驱动版本过低       | 先在宿主机安装匹配显卡的驱动并重启，之后再运行本包。                                       |
| Docker socket 权限不足                | 安装后注销并重新登录，不要只关闭一个终端。                                                 |
| `No such image`                       | 重新运行安装入口，检查 `.env`、`delivery.env` 和导入镜像是否一致，不要尝试在线拉取。       |
| 启动时找不到 `docker/Dockerfile.user` | 不应运行 build。本包只用于加载和启动已有镜像。                                             |
| 语音无声或超时                        | 检查宿主机桌面音频；容器中查看 `/tmp/xdg-runtime/speech-dispatcher/log/`；可临时关闭语音。 |
| 没有头显、跟踪器或未连通              | 不要直接运行启用了它们的示例；按实际设备配置关闭相应功能。                                 |

## 8. 包内文件

- `README.md`：本中文操作说明。
- `install_cn.sh`：国内网络安装入口。
- `install_customer.sh`：实际安装脚本。
- `compose.yaml`、`compose.override.yaml`：容器启动配置。
- `.env`、`delivery.env`：镜像名称及固定版本。
- `*.tar`：本地容器镜像。
- `SHA256SUMS`：镜像文件校验值。
- 如有 `BUILD_INFO.md` 和 `build/`：该交付镜像的来源、修补说明和构建材料；客户机无需运行。
