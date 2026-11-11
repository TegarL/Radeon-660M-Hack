# Metal validation tools

[简体中文](README.md) · [Real-device validation](../docs/validation.en.md)

Use macOS with Xcode Command Line Tools and Python 3. Run these commands from the repository root:

```sh
python3 tools/build.py
./build/tools/metal-probe
./build/tools/texture-residency-probe --pattern
```

The default builds for the current architecture. Use `--arch x86_64` for the AMD laptop, `--arch arm64` for an Apple Silicon control machine, or `--arch universal` for both. `--output <directory>` changes the output directory. The build manifest records each tool source's SHA-256.

| Tool | Work performed | Successful output |
|---|---|---|
| `metal-probe` | Computes `i * 7 + 3` on the GPU and checks 1,024 values; renders a 32 × 32 image, then reads back and checks all 1,024 pixels | One JSON object with `passed: true`, `compute_values_checked: 1024`, and `render_pixels_checked: 1024` |
| `texture-residency-probe` | Retains 1 / 3 / 6 private 2182 × 1394 RGBA16Float textures; fills coordinate- and texture-dependent patterns on the GPU; performs three readback cycles per stage with 16 samples per texture per cycle | JSON Lines with 48 / 144 / 288 checked pixel samples in the three stages and a final `passed: true` |

Both tools exit 0 on success and return nonzero on failure. The texture probe checks 480 samples in total and exits 124 if it has not finished within 20 seconds. Metal reports the actual allocation size, which can differ between GPUs.

The public tools reuse the real-device experiment's compute, render, and texture-pattern code. The allocation observer that depended on a particular framework page has been removed. No administrator access is required, and these tools do not modify EFI, switch windows, or enable hardware video. They check basic GPU correctness on the current device; they do not measure desktop FPS or reproduce all WindowServer allocation flags.

The sources use the repository's [GPL-2.0 license](../LICENSE). See the [evidence notes](../evidence/README.en.md) for their origin and preparation.
