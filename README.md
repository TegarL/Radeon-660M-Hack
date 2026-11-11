# Radeon 680M Hackintosh

中文 | [English](README.en.md)

Radeon 680M 的 RembrandtGfx 源码、兼容补丁和测试工具。目前在 RedmiBook Pro 14 2022（Ryzen 7 6800H、680M revision `02`）上运行 macOS Tahoe **26.7.2 / 25G332**，使用固定 512 MiB 显存。

这里发布的是本机候选 23 的源码快照，可以从源码构建。驱动基于 [GPD Win Max 2 项目的 RembrandtGfx](https://github.com/caoshiyuan0211-blip/winmax2-2022-6800u-hackintosh/tree/a114bdef1d48ecf7a4672d29097af3d91eb3ff80)，保留原作者声明。其他 680M 机器尚未测试。

## 怎么用

- **想在红米本上使用**：先看 [RedmiBook 机型仓库](https://github.com/wzh4869/RedmiBook-Pro14-2022-Ryzen-Hackintosh)，EFI 配置和整机装配步骤在那边。
- **想构建或修改显卡驱动**：看 [源码构建步骤](docs/build.zh-CN.md)。需要自己的 25G332 系统文件和匹配的 AMD 固件；构建脚本会下载固定版本的 SDK 和 Lilu。
- **想检查当前 Metal 是否正常**：看 [测试工具](tools/README.md)。可以单独运行，不需要先构建驱动。

## 这次补了什么

| 改动 | 本机结果 |
|---|---|
| PCI revision `02 → c7` 兼容 | 修复 GPU 初始化失败，Metal 计算和绘图通过 |
| Tahoe 图形入口适配 | 25G332 已进入加速桌面，内屏 2560 × 1600、120 Hz |
| 绘图命令暂存 | 单函数和离屏编码耗时下降；没有测到对应的桌面动画改善 |
| 显存两区合用 | 已记录一次“两区分别不足、合计够用”的真实分配成功；Safari 窗口切换卡顿仍在 |

基础实机检查通过 1,024 项计算、1,024 个绘图像素和 480 个大纹理像素样本。构建、专项检查与实机结果分别列在 [验证记录](docs/validation.zh-CN.md)，实验数据在 [evidence](evidence/README.md)。这些检查不代表所有应用或长期负载已通过。

**视频硬件编解码仍关闭。** 源码保留 VCN 实验代码：曾通过 320 × 240 HEVC 单帧，但 H.264 1080p 编码引发 GPU 恢复和桌面冻结，已撤回。不要添加 `-rmbvcn`。睡眠、外接显示和其他机型尚未验收。

## 文件在哪里

| 路径 | 内容 |
|---|---|
| [src/RembrandtGfx](src/RembrandtGfx) | 当前驱动源码，版本保持 0.1.0 |
| [patches](patches) | 相对固定上游提交的补丁 |
| [scripts](scripts) | 本机输入提取、补丁生成和构建 |
| [source-lock.json](source-lock.json) | 上游、依赖、源码与输入哈希 |
| [tools](tools/README.md) | Metal 计算、绘图和大纹理回读工具 |

构建输出留在本地 `build/`。仓库不包含 Apple 原函数、生成代码页、固件、VBIOS 或预编译 kext。

## 许可证

本项目按 [GPL-2.0](LICENSE) 发布；派生源码保留上游许可和版权声明。SDK、Lilu、固件及其他第三方材料遵守各自许可证。
