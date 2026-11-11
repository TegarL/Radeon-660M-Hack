#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build the standalone Metal probes with the installed macOS SDK."""

import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path


TOOLS = ("metal-probe", "texture-residency-probe")
ROOT = Path(__file__).resolve().parent


def xcrun(*arguments: str) -> str:
    return subprocess.check_output(["xcrun", *arguments], text=True).strip()


def build(architecture: str, output: Path) -> None:
    architectures = ["arm64", "x86_64"] if architecture == "universal" else [architecture]
    compiler = xcrun("--find", "clang")
    sdk = xcrun("--sdk", "macosx", "--show-sdk-path")
    output.mkdir(parents=True, exist_ok=True)
    for name in TOOLS:
        command = [compiler, "-isysroot", sdk, "-mmacosx-version-min=12.0",
                   "-fobjc-arc", "-O2", "-Wall", "-Wextra"]
        for item in architectures:
            command.extend(["-arch", item])
        command.extend([str(ROOT / f"{name}.m"), "-framework", "Foundation",
                        "-framework", "Metal", "-o", str(output / name)])
        subprocess.run(command, check=True)
        print(f"Built {name} ({', '.join(architectures)})")
    manifest = {
        "architectures": architectures,
        "sources_sha256": {
            f"{name}.m": hashlib.sha256((ROOT / f"{name}.m").read_bytes()).hexdigest()
            for name in TOOLS
        },
    }
    (output / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=("native", "arm64", "x86_64", "universal"),
                        default="native")
    parser.add_argument("--output", type=Path, default=ROOT.parent / "build" / "tools")
    arguments = parser.parse_args()
    architecture = platform.machine() if arguments.arch == "native" else arguments.arch
    if platform.system() != "Darwin" or architecture not in ("arm64", "x86_64", "universal"):
        parser.error("The probes require macOS and an arm64 or x86_64 macOS SDK.")
    build(architecture, arguments.output.resolve())


if __name__ == "__main__":
    main()
