# 从源码构建

这套命令构建候选 23 的 x86_64 `RembrandtGfx.kext`。需要你自己的 Tahoe **25G332 x86_64h** 系统缓存和匹配的 AMD yellow_carp 固件。脚本不安装或加载驱动。

## 1. 准备仓库和工具

在 macOS 上运行：

```sh
git clone https://github.com/wzh4869/Radeon-680M-Hackintosh.git
cd Radeon-680M-Hackintosh
python3 --version
xcrun --find clang
xcrun --find ld
xcrun --find otool
```

需要 Python 3 和 Xcode Command Line Tools。固件为 `.bin.zst` 时还需要 `zstd`；使用解压后的 `.bin` 不需要它。构建脚本不会安装工具。

## 2. 从自己的 Tahoe 系统提取 Metal 输入

在你自己的 25G332 x86_64h 系统上检查版本，然后提取：

```sh
sw_vers -buildVersion
python3 scripts/extract_metal_input.py
```

第一条应输出 `25G332`。提取脚本读取：

```text
/System/Library/CoreServices/SystemVersion.plist
/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_x86_64h.03
```

它按缓存头里的映射读取 `AMDRadeonX6000MTLDriver` 的不可变 `__TEXT`，不读取进程内存。核对以下内容后才写文件：

| 检查 | 必须匹配 |
| --- | --- |
| 系统 build | `25G332` |
| 缓存架构 | `x86_64h` |
| Metal UUID | `F89F483D-39AC-368D-B9D9-FB689179EFD2` |
| 完整原函数 | 1294 字节，SHA-256 `f49c9d6d8cd0ad91aefefe857554f2d9e1c0e9d2fdbde75110100fc057e141dd` |

输出：

```text
build/private/metal-input/render-writer-original.bin
build/private/metal-input/metal-input.json
```

如果在另一台 Mac 上构建，把自己这套系统的上述缓存文件和 `SystemVersion.plist` 复制到构建仓库的 `build/private/tahoe-cache/`，然后运行：

```sh
python3 scripts/extract_metal_input.py \
  --cache-dir build/private/tahoe-cache \
  --system-version-plist build/private/tahoe-cache/SystemVersion.plist
```

只需要 `.03` 缓存文件；脚本针对已核对的 25G332 布局。使用同一套安装的 plist 和缓存。其他系统、UUID 或函数内容会被拒绝，不能把这个输入换成另一版 Metal 驱动。

加入 `--write-text` 可额外生成本机 `MTLDriver-Tahoe-TEXT.bin`，供构建命令的 `--metal-text` 参数使用。这些 Apple 输入与生成数组留在 `build/`，不要上传到仓库。

## 3. 准备 yellow_carp 固件

匹配这套构建的固件可从 linux-firmware 官方固定提交 [`69e51bb26f3fa3e118dd770f1962a93bed690dc1`](https://gitlab.com/kernel-firmware/linux-firmware/-/commit/69e51bb26f3fa3e118dd770f1962a93bed690dc1) 取得：

```sh
python3 scripts/fetch_firmware.py
```

脚本将 10 个 raw `.bin` 文件下载到 `build/private/amdgpu/`，逐个检查大小和 SHA-256，并生成 `download-manifest.json`。固定文件 URL 和原有哈希见 [source-lock.json](../source-lock.json) 的 `firmware.files`。下载地址格式为：

```text
https://gitlab.com/kernel-firmware/linux-firmware/-/raw/69e51bb26f3fa3e118dd770f1962a93bed690dc1/amdgpu/<文件名>
```

也可使用自己 Linux 安装中匹配的文件，通常位于 `/usr/lib/firmware/amdgpu/` 或 `/lib/firmware/amdgpu/`。本次记录的输入最初来自测试机的 CachyOS Linux 固件目录，以上固定上游的 10 个 raw 文件已下载核验，全部与记录相同。仓库不分发固件；下载产物留在本机 `build/`。

手动准备时，将这些文件复制到构建机器上的 `build/private/amdgpu/`，保留原始文件名：

```text
yellow_carp_ce.bin
yellow_carp_dmcub.bin
yellow_carp_me.bin
yellow_carp_mec.bin
yellow_carp_mec2.bin
yellow_carp_pfp.bin
yellow_carp_rlc.bin
yellow_carp_sdma.bin
yellow_carp_toc.bin
yellow_carp_vcn.bin
```

也接受对应的 `.bin.zst` 文件，且可混用两种格式。读取权限足够即可，不需要修改 Linux 的固件目录。新版本固件若不匹配，脚本会报出文件名并停止；本仓库没有验证它们可替换记录版本。

## 4. 构建

```sh
python3 scripts/build_rembrandt.py \
  --firmware-dir build/private/amdgpu \
  --metal-function build/private/metal-input/render-writer-original.bin
```

第一次运行会从 GitHub 下载锁定提交的 MacKernelSDK 和 Lilu，校验归档 SHA-256 后保存到 `build/dependencies/`。它先在本机生成 `command_staging.hpp`，再编译和链接 x86_64 kext。不会依赖旧候选目录。

输出：

```text
build/RembrandtGfx/RembrandtGfx.kext
build/RembrandtGfx/build-manifest.json
build/RembrandtGfx/generated/command_staging.hpp
build/RembrandtGfx/vcn-firmware.json
```

每个编译、链接和输入处理步骤的日志也在 `build/RembrandtGfx/`。需要另一处输出目录时，可加 `--output-dir build/my-build`。

## 5. 检查

```sh
python3 tests/check_export.py \
  --generated-header build/RembrandtGfx/generated/command_staging.hpp
```

这会核对 28 个公开源码文件和完整生成头文件的哈希，并运行现有 VCN 寄存器映射测试。源码哈希检查用于核对公开的候选 23 快照；修改源码后，这项检查应报告差异。

如需比较已有候选的内核导入，重新构建时加入：

```sh
python3 scripts/build_rembrandt.py \
  --firmware-dir build/private/amdgpu \
  --metal-function build/private/metal-input/render-writer-original.bin \
  --reference-binary /path/to/RembrandtGfx.kext/Contents/MacOS/RembrandtGfx
```

`build-manifest.json` 会记录新增和移除的导入。编译、哈希及映射测试通过，不代表驱动已经在你的机器上运行，也不代表硬件视频解码可用。实机范围见[验证记录](validation.zh-CN.md)。
