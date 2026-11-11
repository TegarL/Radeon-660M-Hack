# Metal 验证工具

[English](README.en.md) · [实机验证记录](../docs/validation.zh-CN.md)

在 macOS 上安装 Xcode Command Line Tools，并准备 Python 3。以下命令在仓库根目录运行：

```sh
python3 tools/build.py
./build/tools/metal-probe
./build/tools/texture-residency-probe --pattern
```

默认构建当前架构。`--arch x86_64` 适用于这台 AMD 笔记本；`--arch arm64` 可在 Apple Silicon 控制端运行；`--arch universal` 同时构建两个架构。用 `--output <目录>` 更改输出目录。构建清单记录工具源文件的 SHA-256。

| 工具 | 实际执行的检查 | 成功输出 |
|---|---|---|
| `metal-probe` | GPU 计算 `i * 7 + 3`，核对 1,024 项结果；绘制 32 × 32 图像，再读回核对全部 1,024 个像素 | 单个 JSON，`passed: true`、`compute_values_checked: 1024`、`render_pixels_checked: 1024` |
| `texture-residency-probe` | 保留 1／3／6 张 2182 × 1394 RGBA16Float Private 纹理，用 GPU 写入随坐标和纹理序号变化的图案；每阶段三轮回读，每张每轮取 16 个样本 | JSON Lines，三个阶段分别核对 48／144／288 个像素样本，最后 `passed: true` |

两个工具成功时退出 0，失败时返回非零。纹理工具总共核对 480 个样本，20 秒未结束会退出 124。纹理分配的实际字节数由 Metal 返回，可能随 GPU 不同而变化。

公开版复用实机实验的计算、绘图与纹理图案代码，去掉原来依赖特定框架页面的分配观察器。运行不需要管理员权限，也不修改 EFI、切换窗口或启用硬件视频。它能检查当前设备的基础 GPU 正确性；它不测桌面 FPS，也不复现 WindowServer 的全部分配标志。

本目录源代码按仓库的 [GPL-2.0 许可证](../LICENSE) 发布。来源与整理过程见[证据说明](../evidence/README.md)。
