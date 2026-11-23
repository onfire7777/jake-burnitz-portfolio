"""Draw the four copper joins as editable VectorCraft documents and web SVGs.

Run with Python 3.11+ and the configured VectorCraft MCP helper:
python artwork/build_splices.py "/path/to/Signal Path/Splices"
"""

import asyncio
from pathlib import Path
from xml.etree import ElementTree

from build_signal_sources import call, out, session
from export_splice_models import SWEEPS, foil_samples

WEB = Path(__file__).resolve().parents[1] / "site" / "assets" / "splices"


def face(samples, start, stop, drop=0):
    points = [
        (x + normal_x * start, y + normal_y * start + drop)
        for x, y, normal_x, normal_y in samples
    ]
    points += [
        (x + normal_x * stop, y + normal_y * stop + drop)
        for x, y, normal_x, normal_y in reversed(samples)
    ]
    return "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in points) + " Z"


async def draw():
    WEB.mkdir(parents=True, exist_ok=True)
    async with session("vectorcraft") as vector:
        await vector.initmcp()
        for name, curves in SWEEPS.items():
            await call(
                vector,
                "command_run",
                {
                    "id": "file.new",
                    "params": {
                        "name": name.title(),
                        "width": 1280,
                        "height": 144,
                        "units": "Pixels",
                        "colorMode": "RGB",
                    },
                },
            )
            samples = foil_samples(curves)
            for label, low, high, drop, color, opacity in [
                ("Contact shadow", -1, 1, 2.2, "#72654f", 23),
                ("Oxide back", -1, 1, 0, "#a85e37", 100),
                ("Burnished face", -0.88, 0.55, 0, "#cb8050", 100),
                ("Grazing light", -0.87, -0.57, 0, "#e6af76", 100),
            ]:
                await call(
                    vector,
                    "draw_path",
                    {
                        "name": label,
                        "d": face(samples, low, high, drop),
                        "fill": color,
                        "stroke": "none",
                        "opacity": opacity,
                    },
                )
            await call(vector, "save_file", {"path": str(out / f"{name}.vectorcraft")})
            dest = WEB / f"{name}.svg"
            await call(vector, "export", {"format": "svg", "path": str(dest)})
            # The bounding box is the physical join. Adapt its aspect ratio with
            # the layout so neither endpoint drifts into a letterbox margin.
            data = dest.read_text().replace(
                'viewBox="0 0 1280 144"',
                'viewBox="0 0 1280 144" preserveAspectRatio="none"',
            )
            root = ElementTree.fromstring(data)
            assert (
                root.get("preserveAspectRatio") == "none"
                and len(root.findall(".//{*}polygon")) == 4
            )
            dest.write_text(data)
            print(f"{name}: {dest.stat().st_size} bytes", flush=True)


if __name__ == "__main__":
    asyncio.run(draw())
