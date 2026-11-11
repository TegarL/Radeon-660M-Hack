# 验证数据

[English](README.en.md) · [验证记录](../docs/validation.zh-CN.md)

| 文件 | 来源与内容 |
|---|---|
| [candidate23-20261111.json](candidate23-20261111.json) | 红米实机候选 23：设备与系统、两个实验开关、Metal 结果、纹理样本、窗口操作和两区合用请求 |
| [render-command-staging-20261110.json](render-command-staging-20261110.json) | 实机单函数批次耗时、578 组等价检查及三阶段离屏绘图数据 |
| [vcn-withdrawn-20261110.json](vcn-withdrawn-20261110.json) | 候选 18 的 HEVC 小图成功、H.264 1080p 编码失败和撤回结果 |
| [tool-control-20261111.json](tool-control-20261111.json) | 公开工具双架构编译后，在 Apple M4 控制端的实际输出 |
| [tool-source-provenance.json](tool-source-provenance.json) | 公开工具与原实验源码的内容 hash，以及独立化时做的改动 |

历史 JSON 是从保留的本地实验记录中逐项选取字段后的汇总，保留原输入的 SHA-256。原始日志、机器标识、私人路径、框架原始代码页和二进制未上传。原输入 hash 用于追溯同一份记录，不能单独证明实机行为。

以下命令核对公开数据的加总、批次平均值及工具源码 hash，不运行 GPU 测试：

```sh
python3 evidence/verify.py
```

可以从 JSON 重算 480 个纹理样本、21 次窗口操作、851,968 字节两区可用总量、578 组等价检查、2,304 个离屏像素样本和三组单函数平均耗时。重跑当前 GPU 检查见[工具说明](../tools/README.md)。
