"""Build the site's 512 x 256 linear RGBE environment from Poly Haven's source.

Requires Python 3.11+, NumPy, FFmpeg, and curl when downloading the original.
Run with --source to reuse the verified 1K HDR file from an earlier build.
"""

import argparse
import hashlib
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

SOURCE_URL = (
    "https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/1k/studio_small_09_1k.hdr"
)
SOURCE_SHA256 = "e7cfda5f4e98e623db12b8bfd0184e048488e4855d9c83e2751fb44a32e80c45"
OUTPUT = Path(__file__).resolve().parents[1] / "site/assets/engine/studio-light.hdr"


def build(source, output):
    if hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError(
            "The source does not match the original 1K Studio Small 09 capture."
        )
    raw = subprocess.check_output(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(source),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gbrpf32le",
            "-",
        ]
    )
    radiance = (
        np.frombuffer(raw, dtype="<f4").reshape(3, 256, 2, 512, 2).mean(axis=(2, 4))
    )
    # Area-average actual linear radiance. Conventional image scalers can clamp
    # these values to 1, destroying the power in the two octabox reflections.
    vertical = np.pad(radiance, ((0, 0), (1, 1), (0, 0)), mode="edge")
    soft = (vertical[:, :-2] + 2 * vertical[:, 1:-1] + vertical[:, 2:]) * 0.25
    soft = (np.roll(soft, 1, axis=2) + 2 * soft + np.roll(soft, -1, axis=2)) * 0.25
    peak = radiance.max(axis=0)
    blend = 0.5 * np.clip((2 - peak) / 1.5, 0, 1)
    filtered = radiance * (1 - blend) + soft * blend
    # Preserve the capture's full emitter range and a fine highlight mantissa.
    # Smooth low-energy areas use fewer mantissa bits for Radiance's scanline RLE.
    mantissa_bits = np.where(peak > 2, 6, 4)
    step = np.ldexp(1.0, np.frexp(filtered.max(axis=0))[1] - mantissa_bits)
    packed = (np.rint(filtered / step) * step).astype("<f4")
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "rawvideo",
            "-s",
            "512x256",
            "-pix_fmt",
            "gbrpf32le",
            "-i",
            "-",
            "-vf",
            "setsar=1",
            "-frames:v",
            "1",
            "-y",
            str(output),
        ],
        input=packed.tobytes(),
        check=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    with TemporaryDirectory() as folder:
        source = args.source or Path(folder) / "studio_small_09_1k.hdr"
        if not args.source:
            subprocess.run(
                [
                    "curl",
                    "--fail",
                    "--silent",
                    "--show-error",
                    "--location",
                    "--output",
                    str(source),
                    SOURCE_URL,
                ],
                check=True,
            )
        build(source, args.output)
    print(args.output, args.output.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
