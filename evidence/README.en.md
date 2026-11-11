# Validation data

[简体中文](README.md) · [Validation record](../docs/validation.en.md)

| File | Origin and contents |
|---|---|
| [candidate23-20261111.json](candidate23-20261111.json) | Candidate 23 on the RedmiBook: device and OS, two experiment gates, Metal results, texture samples, window operations, and the combined-range request |
| [render-command-staging-20261110.json](render-command-staging-20261110.json) | Real-device single-function batch timings, 578 equivalence cases, and three-phase offscreen rendering data |
| [vcn-withdrawn-20261110.json](vcn-withdrawn-20261110.json) | Candidate 18's small HEVC success, H.264 1080p encoding failure, and withdrawal |
| [tool-control-20261111.json](tool-control-20261111.json) | Actual output from the public tools on an Apple M4 control machine after compilation for both architectures |
| [tool-source-provenance.json](tool-source-provenance.json) | Content hashes of the public and original experimental tool sources, with the standalone adaptations |

Historical JSON summaries select fields from retained local experiment records and include SHA-256 hashes of those inputs. Raw logs, machine identifiers, private paths, original framework code pages, and binaries are excluded. An input hash identifies the same retained record; it does not independently prove real-device behavior.

This command checks public totals, batch means, and tool source hashes. It does not run GPU tests:

```sh
python3 evidence/verify.py
```

The JSON permits recalculation of 480 texture samples, 21 window operations, 851,968 combined usable bytes, 578 equivalence cases, 2,304 offscreen pixel samples, and the three single-function means. See the [tool instructions](../tools/README.en.md) to rerun the current GPU checks.
