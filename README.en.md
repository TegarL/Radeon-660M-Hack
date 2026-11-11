# Radeon 680M Hackintosh

[中文](README.md) | English

RembrandtGfx source, compatibility patches and test tools for Radeon 680M. The current test machine is a RedmiBook Pro 14 2022 with a Ryzen 7 6800H, 680M revision `02` and a fixed 512 MiB VRAM reservation, running macOS Tahoe **26.7.2 / 25G332**.

This repository contains the buildable source snapshot of local candidate 23. It is based on [RembrandtGfx from the GPD Win Max 2 project](https://github.com/caoshiyuan0211-blip/winmax2-2022-6800u-hackintosh/tree/a114bdef1d48ecf7a4672d29097af3d91eb3ff80), with the original attribution retained. Other 680M machines have not been tested.

## Getting started

- **Using it on a RedmiBook**: start with the [RedmiBook repository](https://github.com/wzh4869/RedmiBook-Pro14-2022-Ryzen-Hackintosh). It contains the machine configuration and EFI assembly steps.
- **Building or modifying the driver**: follow the [source build guide](docs/build.en.md). You need files from your own 25G332 installation and matching AMD firmware. The build script downloads pinned SDK and Lilu versions.
- **Checking Metal on your current system**: use the [test tools](tools/README.en.md). They run independently of the driver build.

## Changes in this snapshot

| Change | Result on this machine |
|---|---|
| PCI revision `02 → c7` compatibility | Fixed GPU initialization failure; Metal compute and rendering passed |
| Tahoe graphics entry points | Accelerated desktop on 25G332, internal display at 2560 × 1600 and 120 Hz |
| Render command staging | Lower single-function and offscreen encoding times; no corresponding improvement measured in desktop animation |
| Allocation across both VRAM ranges | One real allocation succeeded when neither range was sufficient alone; Safari window switching still stutters |

Basic hardware checks passed 1,024 compute values, 1,024 rendered pixels and 480 large-texture pixel samples. Build checks, focused tests and hardware results are separated in the [validation record](docs/validation.en.md); experiment data is in [evidence](evidence/README.en.md). These checks do not cover every application or sustained workloads.

**Hardware video encoding and decoding remain disabled.** The source retains the VCN experiment: a single 320 × 240 HEVC frame passed, but H.264 1080p encoding caused GPU recovery and a frozen desktop, so it was withdrawn. Do not add `-rmbvcn`. Sleep, external displays and other machines have not been accepted.

## Repository contents

| Path | Contents |
|---|---|
| [src/RembrandtGfx](src/RembrandtGfx) | Current driver source; version remains 0.1.0 |
| [patches](patches) | Patch against the pinned upstream commit |
| [scripts](scripts) | Local input extraction, patch generation and build |
| [source-lock.json](source-lock.json) | Upstream, dependency, source and input hashes |
| [tools](tools/README.en.md) | Metal compute, render and large-texture readback tools |

Build output stays in local `build/`. Apple functions, generated code pages, firmware, VBIOS and prebuilt kexts are not included.

## License

The project is released under [GPL-2.0](LICENSE). Derived source retains upstream license and copyright notices. SDK, Lilu, firmware and other third-party materials retain their own licenses.
