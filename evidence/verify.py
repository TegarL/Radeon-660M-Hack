#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Check arithmetic and published source hashes in the evidence summaries."""

import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def read(name: str) -> dict:
    return json.loads((ROOT / name).read_text())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> None:
    candidate = read("candidate23-20261111.json")
    texture = candidate["texture_pattern"]
    total = 0
    for stage in texture["stages"]:
        expected = (stage["texture_count"] * texture["cycles_per_stage"]
                    * texture["samples_per_texture_per_cycle"])
        require(stage["readback_pixels_checked"] == expected, "Texture stage sample count differs")
        total += expected
    require(total == texture["total_readback_pixel_samples"], "Texture total differs")
    request = candidate["allocation_retry"]["both_ranges_necessary_request"]
    require(request["lowUsable"] + request["highUsable"] == request["combined_usable_bytes"],
            "Combined usable allocation size differs")
    require(request["lowUsable"] < request["rounded"] and request["highUsable"] < request["rounded"]
            and request["combined_usable_bytes"] >= request["rounded"], "Both-range example differs")
    activations = sum(item["activations"] for item in candidate["window_operations"]["rounds"]
                      if item["candidate"] == candidate["candidate"])
    require(activations == candidate["window_operations"]["candidate23_activations"],
            "Window operation total differs")

    staging = read("render-command-staging-20261110.json")
    equivalence = staging["equivalence"]
    require(equivalence["cases"] == equivalence["feature_bit_variants"] * 17 * 17,
            "Equivalence case count differs")
    for measurement in staging["single_function_benchmark"]["measurements"].values():
        mean = sum(measurement["batch_us_per_call"]) / len(measurement["batch_us_per_call"])
        require(math.isclose(mean, measurement["mean_us_per_call"], rel_tol=1e-12),
                "Benchmark batch mean differs")
    samples = sum(case["readback_pixels_checked"] for phase in staging["offscreen_render"]["phases"]
                  for case in phase["cases"])
    require(samples == staging["offscreen_render"]["total_pixel_samples"],
            "Offscreen render sample total differs")

    provenance = read("tool-source-provenance.json")
    control = read("tool-control-20261111.json")
    for name, source in provenance["tools"].items():
        digest = hashlib.sha256((ROOT.parent / "tools" / name).read_bytes()).hexdigest()
        require(digest == source["published_source_sha256"], f"Published source changed: {name}")
        require(digest == control["build"]["sources_sha256"][name], f"Control build source changed: {name}")
    control_samples = sum(item.get("readback_pixels_checked", 0)
                          for item in control["texture_residency_probe"]["records"])
    require(control_samples == total, "Control texture sample count differs")
    print("Evidence arithmetic and published tool source hashes match.")


if __name__ == "__main__":
    main()
