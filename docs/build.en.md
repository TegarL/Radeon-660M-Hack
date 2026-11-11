# Build from source

These commands build candidate 23 as an x86_64 `RembrandtGfx.kext`. You need your own Tahoe **25G332 x86_64h** system cache and matching AMD yellow_carp firmware. The scripts do not install or load the driver.

## 1. Get the repository and check tools

Run on macOS:

```sh
git clone https://github.com/wzh4869/Radeon-680M-Hackintosh.git
cd Radeon-680M-Hackintosh
python3 --version
xcrun --find clang
xcrun --find ld
xcrun --find otool
```

Python 3 and Xcode Command Line Tools are required. Compressed `.bin.zst` firmware also requires `zstd`; uncompressed `.bin` files do not. The build script does not install tools.

## 2. Extract the Metal input from your own Tahoe system

On your own 25G332 x86_64h installation, check the build and extract the input:

```sh
sw_vers -buildVersion
python3 scripts/extract_metal_input.py
```

The first command should print `25G332`. The extractor reads:

```text
/System/Library/CoreServices/SystemVersion.plist
/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_x86_64h.03
```

It uses the cache header mappings to read the immutable `AMDRadeonX6000MTLDriver` `__TEXT` segment. It does not read process memory. It checks these values before writing output:

| Check | Required value |
| --- | --- |
| System build | `25G332` |
| Cache architecture | `x86_64h` |
| Metal UUID | `F89F483D-39AC-368D-B9D9-FB689179EFD2` |
| Complete original function | 1294 bytes, SHA-256 `f49c9d6d8cd0ad91aefefe857554f2d9e1c0e9d2fdbde75110100fc057e141dd` |

Output:

```text
build/private/metal-input/render-writer-original.bin
build/private/metal-input/metal-input.json
```

To build on another Mac, copy that cache file and `SystemVersion.plist` from your own installation into `build/private/tahoe-cache/` in the build repository. Then run:

```sh
python3 scripts/extract_metal_input.py \
  --cache-dir build/private/tahoe-cache \
  --system-version-plist build/private/tahoe-cache/SystemVersion.plist
```

Only the `.03` cache file is needed for the checked 25G332 layout. Use the plist and cache from the same installation. A different system build, UUID or function is rejected; a Metal driver from another release cannot replace this input.

Add `--write-text` to also produce a local `MTLDriver-Tahoe-TEXT.bin` for the build command's `--metal-text` option. Keep Apple inputs and generated arrays in `build/`; do not upload them to this repository.

## 3. Prepare yellow_carp firmware

The matching firmware is available from the official linux-firmware commit [`69e51bb26f3fa3e118dd770f1962a93bed690dc1`](https://gitlab.com/kernel-firmware/linux-firmware/-/commit/69e51bb26f3fa3e118dd770f1962a93bed690dc1):

```sh
python3 scripts/fetch_firmware.py
```

The script downloads 10 raw `.bin` files into `build/private/amdgpu/`, checks each file's size and SHA-256, and writes `download-manifest.json`. Fixed file URLs and the original hashes are recorded under `firmware.files` in [source-lock.json](../source-lock.json). The URL format is:

```text
https://gitlab.com/kernel-firmware/linux-firmware/-/raw/69e51bb26f3fa3e118dd770f1962a93bed690dc1/amdgpu/<filename>
```

You can also use matching files from your own Linux installation, usually in `/usr/lib/firmware/amdgpu/` or `/lib/firmware/amdgpu/`. The recorded inputs originally came from the test machine's CachyOS Linux firmware directory. All 10 raw files from the fixed upstream commit have been downloaded and verified to match. This repository does not redistribute firmware; downloaded files stay under the local `build/` directory.

For manual preparation, copy these files to `build/private/amdgpu/` on the build machine, keeping their names:

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

The corresponding `.bin.zst` files are also accepted, and the directory may contain a mix of both formats. Read access is sufficient; no changes to the Linux firmware directory are needed. If a newer firmware file differs, the build reports its name and stops. Replacement firmware versions have not been validated here.

## 4. Build

```sh
python3 scripts/build_rembrandt.py \
  --firmware-dir build/private/amdgpu \
  --metal-function build/private/metal-input/render-writer-original.bin
```

The first run downloads the pinned MacKernelSDK and Lilu commits from GitHub, checks archive SHA-256 values and saves them under `build/dependencies/`. It generates `command_staging.hpp` locally, then compiles and links the x86_64 kext. No previous candidate directory is required.

Output:

```text
build/RembrandtGfx/RembrandtGfx.kext
build/RembrandtGfx/build-manifest.json
build/RembrandtGfx/generated/command_staging.hpp
build/RembrandtGfx/vcn-firmware.json
```

Compilation, linking and input-processing logs are also in `build/RembrandtGfx/`. Add `--output-dir build/my-build` to choose another output directory.

## 5. Check

```sh
python3 tests/check_export.py \
  --generated-header build/RembrandtGfx/generated/command_staging.hpp
```

This checks the hashes of all 28 exported source files and the complete generated header, then runs the existing VCN register remapper test. The source hash check verifies the published candidate 23 snapshot; it should report differences after source edits.

To compare kernel imports with an existing candidate, rebuild with:

```sh
python3 scripts/build_rembrandt.py \
  --firmware-dir build/private/amdgpu \
  --metal-function build/private/metal-input/render-writer-original.bin \
  --reference-binary /path/to/RembrandtGfx.kext/Contents/MacOS/RembrandtGfx
```

`build-manifest.json` records added and removed imports. Successful compilation, hash checks and remapper tests do not establish runtime behavior on your machine or working hardware video decoding. See the [validation record](validation.en.md) for the hardware checks performed.
