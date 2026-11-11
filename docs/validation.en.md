# GPU validation record

[简体中文](validation.zh-CN.md) · [Back to project overview](../README.en.md)

As of **2026-11-11**, candidate 23 booted on the RedmiBook Pro 14 2022 and passed basic compute, rendering, and large-texture sample checks. The user reported less severe stutter, but Safari stutter has not been accepted as fixed. Desktop FPS was not measured.

This repository contains the current candidate source, its upstream patch, build scripts, and standalone Metal tools. Historical real-device records are available as [sanitized JSON](../evidence/README.en.md). The public tools' Apple M4 control run is recorded separately from the RedmiBook results.

## Tested environment

| Area | Environment |
|---|---|
| Device | RedmiBook Pro 14 2022, Ryzen 7 6800H / Radeon 680M |
| OS | Initial Sequoia 15.8.1 / 24H32; current Tahoe 26.7.2 / 25G332 |
| SMBIOS | MacPro7,1 |
| VRAM | 512 MiB fixed VRAM, 256 MiB CPU-visible aperture; Metal reports `hasUnifiedMemory=false` |
| Internal display | 2560 × 1600, 1280 × 800 HiDPI, 120 Hz |
| Candidate 23 | `-rmballoclow` and `-rmballocboth` enabled; render command staging retained; hardware video disabled |

120 Hz describes the display mode, not a steady desktop rate of 120 FPS. Both ranges belong to the same fixed VRAM space. The ordinary-free and fixed-free ledgers also cover the same addresses and cannot be added as extra VRAM.

In the initial Sequoia run, device ID spoofing was active, but Apple's Navi 23 support table rejected revision `02`, and native initialization returned 1. Mapping `02 → c7` in PCI configuration reads while preserving the other bits allowed initialization to return 0 and the graphics stack to take over the internal display. Tahoe uses a separate local GPU port and matching patches. It booted and passed basic Metal checks on the listed build; other machines and older systems were not regression-tested.

## Candidate 23 correctness checks

These results followed one real reboot into candidate 23. See [candidate23-20261111.json](../evidence/candidate23-20261111.json).

| Check | Real-device result |
|---|---|
| Metal compute | 1,024 correct values |
| Metal rendering | All 1,024 pixels of a 32 × 32 image checked successfully |
| Render command writer | Full 1,294 bytes matched the validated replacement |
| Large private textures | 1 / 3 / 6 private 2182 × 1394 RGBA16Float textures; three readback cycles per stage; 480 correct pixel samples |
| Window operations | 15 five-application activations and 6 Finder / Safari activations; foreground and main-window visibility checked |
| GPU recovery count | 0 during texture and window checks |

The texture check sampled pixels rather than checking every texel, and did not reproduce all WindowServer allocation flags. The historical tool used an in-process allocation observer; its binding and page permissions were restored on exit. The public tools retain only compute, rendering, and texture-pattern readback. See the [tool instructions](../tools/README.en.md).

## Why combine the ranges

Successful native allocations keep their result. Retry occurs only after native failure with the existing `-rmballoclow` gate enabled. Candidate 23 adds `-rmballocboth` to select native type 2 across the full range. Removing the new flag retains candidate 22's type 0 lower-range retry. Both paths use native block size, alignment, descriptors, and fragment parsing.

The device produced 102 throttled retry records, all type 2. Nine were from WindowServer, including four successful retries. One request had these byte counts:

| Original request | Block-rounded | Lower usable | Upper usable | Combined usable | Final return |
|---:|---:|---:|---:|---:|---|
| 790,528 | 851,968 | 720,896 | 131,072 | 851,968 | 1, success |

Neither range was sufficient alone; the sum was exactly sufficient, and the real allocation returned success. The request was not linked to its later pixels resource by resource. The 480 texture samples are a separate check. This run captured no final retry sample for a WindowServer request of at least 16 MiB.

Throttled records cannot establish an overall success rate. Native `large-fail` / `AMD ERROR` messages precede retry and do not directly establish a final rendering failure.

## Window operations and user feedback

| Round | Candidate | Duration, seconds | WindowServer CPU increase, seconds | Cumulative whole-GPU reclaim wait, milliseconds |
|---|---:|---:|---:|---:|
| Five applications, 15 activations | 22 | 27.176 | 16.06 | 136.022 |
| Five applications, 15 activations | 23 | 27.533 | 15.62 | 131.693 |
| Finder / Safari, 6 activations | 22 | 13.071 | 7.04 | 264.221 |
| Finder / Safari, 6 activations | 23 | 13.225 | 7.34 | 68.067 |

These are cumulative phase counters, not frame times. Warm-up, pages, and checks differed between boots. Candidate 22's five-application round checked only foreground state; candidate 23 added main-window checks. The runs were not a strict A/B test and establish no FPS or percentage improvement. Candidate 23 used `CLOCK_UPTIME_RAW`, checked against `mach_absolute_time`.

The user described it as seemingly smoother, with less severe stutter. This is uncertain, partial subjective improvement. Allocation has not been established as the only cause of remaining stutter.

## Render command staging

The replacement generates the original commands in ordinary stack memory, then copies them with AVX. Its code remains 1,294 bytes long and adds 4,104 temporary stack bytes. Two hardware feature states and viewport and clip counts from 0–16 produced 578 equivalence cases. Return offsets, the entire destination, and the trailing canary matched.

| Single-function writes to the same unsubmitted command resource | Mean time |
|---|---:|
| Original, before replacement | 33.107 µs |
| Replacement | 9.389 µs |
| Original, restored | 33.097 µs |

The microbenchmark submitted no GPU commands. A separate real-device offscreen original—replacement—restored-original check used three phases and three workloads per phase, each with 24 measured and 4 warm-up frames. All 2,304 pixel samples passed, with a GPU recovery count of 0. Encoding timings improved; GPU execution showed no consistent proportional improvement. Batch and render data are in [render-command-staging-20261110.json](../evidence/render-command-staging-20261110.json).

The user reported no Stage Manager improvement. These results do not establish a desktop stutter fix. Candidate 23 retains this replacement, but later subjective changes cannot be attributed to it alone.

## Hardware video failure and withdrawal

After login, candidate 18 passed a 320 × 240 single-frame HEVC hardware encode/decode check. Its first H.264 1080p encode did not complete. GPU recovery reports pointed to `VCN0EncLLQ`, and the user confirmed a frozen desktop. HEVC 1080p was not run. The candidate was withdrawn; hardware video remains disabled. See [vcn-withdrawn-20261110.json](../evidence/vcn-withdrawn-20261110.json).

Code analysis confirmed video cleanup holding the accelerator lock while waiting for an unfinished queue, with WindowServer resource creation waiting for the same lock. This explains the path that blocked the desktop. The final encoding failure cause remains unknown, and a cyclic deadlock has not been established.

## Build, focused checks, and remaining validation

| Scope | Result |
|---|---|
| Independent public candidate 23 build | `scripts/build_rembrandt.py` compiled and linked x86_64; the executable has the same SHA-256 as the original candidate 23 |
| Current source export checks | All 28 files match `source-lock.json`; the complete generated header matches candidate 23; the existing 214-register remapper test passed under ASan / UBSan |
| Historical focused checks and offline replay | Native symbols, production ABI, synthetic allocation, and release passed; 6,512 page fragments checked; oversized failure rolled back |
| Public Metal tools | arm64 / x86_64 compilation passed; the arm64 run on Apple M4 checked 1,024 compute values, 1,024 rendered pixels, and 480 texture samples; the x86_64 slice was not executed |
| Upstream full suite / complete machine acceptance | Not run |
| Candidate 23 sustained workload, sleep/wake, external display | Not tested |
| Real candidate 23 → 22 restoration | Not executed this run; candidate 22 materials, manifests, and entry points checked |

The independently built executable's SHA-256 is `5f7513e9893cfb5c60a4c91b400eb7d7f359ab4c1d8c2b670bca2eb9951cdb1c`. Firmware and original Metal function bytes are supplied locally. See [source-lock.json](../source-lock.json) for the source manifest and [check_export.py](../tests/check_export.py) for the focused checks. Preparing this publication did not install this build or perform a new RedmiBook boot or real-device test.

Offline replay uses native machine code and synthetic free-space layouts. It does not prove real GPU page tables or WindowServer rendering. Apple M4 establishes only tool compilation and correctness on the control machine; it does not extend RedmiBook acceptance. See [tool-control-20261111.json](../evidence/tool-control-20261111.json).

Original Apple function bytes, full code pages, firmware, and VBIOS are excluded from repository uploads. The published content is source, patches, build entry points, and sanitized results. Run `python3 evidence/verify.py` to check public totals and source hashes.
