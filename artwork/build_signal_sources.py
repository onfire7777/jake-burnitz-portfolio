"""Build the native Craft projects and render inputs for Signal Path.

Run with the matching SolidCraft, EffectCraft and FilmCraft MCP helpers
registered in Codex. Pass a dedicated output directory as the only argument.
"""

import argparse
import asyncio
import json
import math
import tomllib
from contextlib import asynccontextmanager
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("destination", type=Path)
parser.add_argument(
    "--patchbay-only", action="store_true", help="Build the closing patch panel"
)
parser.add_argument(
    "--contact-print",
    action="store_true",
    help="Cut and finish the page-wide contact printer artwork",
)
parser.add_argument(
    "--studio-identity",
    action="store_true",
    help="Draw the monogram and project meters",
)
options = parser.parse_args()
out = options.destination.expanduser().resolve()
out.mkdir(parents=True, exist_ok=True)
assets = Path(__file__).resolve().parents[1] / "site" / "assets"


class Craft:
    """Request/response client for Craft's newline-delimited stdio transport."""

    def __init__(self, process):
        self.process = process
        self.sequence = 0

    async def send(self, message):
        self.process.stdin.write(
            (json.dumps({"jsonrpc": "2.0", **message}) + "\n").encode()
        )
        await self.process.stdin.drain()

    async def request(self, method, params):
        self.sequence += 1
        await self.send({"id": self.sequence, "method": method, "params": params})
        async with asyncio.timeout(90):
            while line := await self.process.stdout.readline():
                reply = json.loads(line)
                if reply.get("id") == self.sequence:
                    if "error" in reply:
                        raise RuntimeError(reply["error"])
                    return reply["result"]
        raise RuntimeError("Craft closed the connection")

    async def initmcp(self):
        await self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "signal-path", "version": "1"},
                "capabilities": {},
            },
        )
        await self.send({"method": "notifications/initialized"})


@asynccontextmanager
async def session(name):
    config = tomllib.loads((Path.home() / ".codex/config.toml").read_text())[
        "mcp_servers"
    ][name]
    args = (
        ["mcp", "--headless", "--allow-path", str(out)]
        if name == "solidcraft"
        else ["mcp"]
    )
    process = await asyncio.create_subprocess_exec(
        config["command"],
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        limit=8 * 1024 * 1024,
    )
    try:
        yield Craft(process)
    finally:
        process.stdin.close()
        try:
            await asyncio.wait_for(process.wait(), 3)
        except TimeoutError:
            process.kill()
            await process.wait()


async def call(c, tool, args):
    result = await c.request("tools/call", {"name": tool, "arguments": args})
    text = result.get("content", [{}])[0].get("text", "")
    if result.get("isError"):
        raise RuntimeError(f"{tool}: {text}")
    try:
        return json.loads(text)
    except ValueError:
        return text


async def solid(kind):
    async with session("solidcraft") as c:
        await c.initmcp()

        async def command(id, **p):
            return await call(c, "execute", {"command": id, "params": p})

        await call(c, "new_design", {})
        await command("sketch.create", plane="XY")

        async def circle(x, y, r):
            await command("sketch.circle.center", center=[x, y], radius=r)

        async def rect(x, y, w, h):
            await command(
                "sketch.rectangle.center", center=[x, y], corner=[x + w / 2, y + h / 2]
            )

        if kind == "spool":
            await circle(0, 0, 50)
            await circle(0, 0, 5)
            for i in range(5):
                a = math.tau * i / 5
                await circle(27.5 * math.cos(a), 27.5 * math.sin(a), 13.9)
            h = 3
        elif kind == "memory":
            await rect(0, 0, 82, 60)
            for x in [-34, 34]:
                for y in [-23, 23]:
                    await circle(x, y, 1.9)
            for x in range(-21, 24, 7):
                await rect(x, 0, 2.4, 29)
            h = 3
        elif kind == "patchbay":
            await rect(0, 0, 80, 50)
            for x, y in [
                (-24, 8),
                (-8, 8),
                (8, 8),
                (24, 8),
                (-16, -10),
                (0, -10),
                (16, -10),
            ]:
                await circle(x, y, 4)
            for x in [-35, 35]:
                for y in [-20, 20]:
                    await circle(x, y, 1.5)
            h = 2.6
        else:
            await rect(0, 0, 84, 64)
            await rect(0, 0, 56, 34)
            for x in [-35, 35]:
                for y in range(-20, 21, 10):
                    await rect(x, y, 3, 5)
            h = 4
        await command("sketch.finish")
        await command("solid.extrude", distance=h)
        await call(c, "save", {"path": str(out / (kind + ".sc"))})
        await call(c, "export", {"path": str(out / (kind + ".stl")), "format": "stl"})
        print("SolidCraft", kind, (out / (kind + ".stl")).stat().st_size, flush=True)


async def traces():
    async with session("effectcraft") as c:
        await c.initmcp()

        async def cmd(i, **p):
            return await call(c, "command_run", {"id": i, "params": p})

        for i, kind in enumerate(["voice", "memory", "frame"]):
            await cmd("comp.new", name=kind, width=720, height=96, duration=1)

            async def line(name, points, color, weight):
                await cmd("layer.newShape", kind="none", name=name)
                await cmd(
                    "shape.newPath",
                    name=name,
                    vertices=points,
                    space="comp",
                    closed=False,
                    fill=False,
                    stroke=color,
                    strokeWidth=weight,
                )

            await line("Zero line", [[4, 48], [716, 48]], "#a59e92", 1)
            if i == 0:
                pts = [
                    [
                        x,
                        48
                        + 32
                        * math.sin(x * 0.088)
                        * (0.12 + 0.88 * abs(math.sin(x * 0.009)) ** 4)
                        * math.cos(x * 0.027),
                    ]
                    for x in range(4, 717, 2)
                ]
            elif i == 1:
                pts = [[4, 61]]
                x = 5
                for j in range(24):
                    w = 14 + ((j * 17) % 23)
                    height = 19 + (j * 11) % 37
                    pts.extend(
                        [
                            [x, 61],
                            [x, 61 - height],
                            [x + w * 0.68, 61 - height],
                            [x + w * 0.68, 61],
                            [x + w, 61],
                        ]
                    )
                    x += w
            else:
                pts = [[4, 62]]
                for j in range(12):
                    x = 10 + 58 * j
                    pts.extend(
                        [[x, 62], [x + 5, 26], [x + 38, 26], [x + 42, 62], [x + 54, 62]]
                    )
            await line("Signal", pts, "#ac441f", 3)
            await call(
                c,
                "render_frame",
                {
                    "comp": kind,
                    "path": str(out / (kind + "-trace.png")),
                    "inline": False,
                    "transparent": True,
                },
            )
        await call(c, "save_project", {"path": str(out / "Signal traces.ecproj")})
        print("EffectCraft traces rendered", flush=True)


async def film():
    async with session("filmcraft") as c:
        await c.initmcp()

        async def cmd(i, **p):
            return await call(c, "command_run", {"id": i, "params": p})

        await cmd("file.newProject", name="Signal Path — film gate")
        paths = [
            assets / "ben-lang-luigi.jpg",
            assets / "redeemed-zoomer.jpg",
            assets / "burnos-demo.jpg",
        ]
        res = await call(c, "media_import", {"paths": list(map(str, paths))})
        ids = res["items"]
        await cmd(
            "file.newSequence",
            name="Gate exposures",
            width=640,
            height=360,
            fps=24,
            fromItems=ids,
        )
        for j, item in enumerate(ids):
            await cmd(
                "file.exportFrame",
                target="source",
                item=item,
                path=str(out / ("exposure-" + str(j) + ".png")),
                format="png",
            )
        await cmd("file.saveAs", path=str(out / "Gate exposures.fcproj"))


async def contact_print():
    """Make a three-shot FilmCraft edit and the printable EffectCraft exposures."""
    folder = out / "Contact printer"
    folder.mkdir(exist_ok=True)
    movie = folder / "Three inserts.mp4"
    async with session("filmcraft") as editor:
        await editor.initmcp()

        async def edit(command, **params):
            return await call(editor, "command_run", {"id": command, "params": params})

        await edit("file.newProject", name="Contact printer")
        media = await call(
            editor, "media_import", {"paths": [str(out / "Gemini Signal Path.mp4")]}
        )
        shots = []
        for name, first, last in [
            ("Spindle", 17, 43),
            ("Plates", 91, 119),
            ("Aperture", 172, 202),
        ]:
            clip = await edit(
                "clip.makeSubclip",
                item=media["items"][0],
                name=name,
                startFrame=first,
                endFrame=last,
            )
            shots.append(clip["item"])
        await edit(
            "file.newSequence",
            name="Contact printer inserts",
            width=1280,
            height=720,
            fps=24,
            fromItems=shots,
        )
        timeline = await call(editor, "sequence_inspect", {})
        for track in timeline["video"]:
            for clip in track["items"]:
                # Subclips inherit a 1920x1080 anchor. Centre the source footage
                # on its actual 1280x720 frame before handing it to EffectCraft.
                await edit(
                    "effects.setParam",
                    clip=clip["clip"],
                    effect="motion",
                    param="anchor",
                    value=[640, 360],
                )
        await edit("file.saveAs", path=str(folder / "Contact printer.fcproj"))
        result = await edit(
            "file.exportMedia",
            path=str(movie),
            format="h264",
            width=1280,
            height=720,
            fps=24,
            audio=False,
            crf=17,
            bitrateMode="crf",
            wait=True,
        )
        duration = result["result"]["frames"] / 24
        print(
            "FilmCraft edited three inserts and exported",
            result["result"]["frames"],
            "frames",
            flush=True,
        )
    async with session("effectcraft") as artist:
        await artist.initmcp()

        async def effect(command, **params):
            return await call(artist, "command_run", {"id": command, "params": params})

        await effect("file.import", paths=[str(movie)])
        await effect(
            "comp.new",
            name="Silver print",
            width=640,
            height=360,
            frameRate=24,
            duration=duration,
        )
        await effect("layer.addItem", item=movie.name)
        await effect(
            "layer.setTransform", layers=[movie.name], prop="scale", value=[50, 50]
        )
        await effect(
            "layer.setTransform", layers=[movie.name], prop="position", value=[320, 180]
        )
        await effect(
            "layer.newShape",
            kind="rect",
            name="Warm emulsion",
            position=[320, 180],
            size=[640, 360],
            fill="#cfa873",
            stroke=False,
        )
        await effect("layer.setBlendMode", layers=["Warm emulsion"], mode="Multiply")
        await effect(
            "layer.setTransform", layers=["Warm emulsion"], prop="opacity", value=18
        )
        await effect(
            "layer.newShape",
            kind="rect",
            name="Passing light",
            position=[-80, 180],
            size=[72, 400],
            fill="#ffdead",
            stroke=False,
        )
        await effect("layer.setBlendMode", layers=["Passing light"], mode="Screen")
        await effect(
            "layer.setTransform", layers=["Passing light"], prop="opacity", value=14
        )
        await call(
            artist,
            "add_keyframe",
            {
                "layer": "Passing light",
                "path": "transform/position",
                "keys": [
                    {"time": 0, "value": [-60, 180]},
                    {"time": duration - 0.08, "value": [700, 180]},
                ],
            },
        )
        for x, y, dx, dy in [
            (19, 18, 1, 1),
            (621, 18, -1, 1),
            (19, 342, 1, -1),
            (621, 342, -1, -1),
        ]:
            name = f"Registration {x} {y}"
            await effect("layer.newShape", kind="none", name=name)
            await effect(
                "shape.newPath",
                layer=name,
                vertices=[[x + 18 * dx, y], [x, y], [x, y + 12 * dy]],
                closed=False,
                space="comp",
                fill=False,
                stroke="#f6ddac",
                strokeWidth=2,
            )
        for i in range(8):
            await call(
                artist,
                "render_frame",
                {
                    "comp": "Silver print",
                    "time": (duration - 1 / 24) * i / 7,
                    "inline": False,
                    "path": str(folder / f"print-{i}.png"),
                },
            )
        await effect(
            "renderQueue.add",
            comp="Silver print",
            output=str(folder / "Silver print.mp4"),
            format="h264",
            audio="off",
            bitrate=3000,
            frameRate=24,
        )
        result = await effect("renderQueue.render", wait=True)
        if result.get("failed"):
            raise RuntimeError(result)
        await effect(
            "comp.new", name="Tape edge", width=32, height=320, frameRate=24, duration=1
        )
        for name, position, size, color in [
            ("Back edge", [10, 160], [3, 322], "#895638"),
            ("Copper", [12, 160], [4, 322], "#c67e4d"),
            ("Edge light", [14, 160], [1.5, 322], "#e1b586"),
            ("Splice", [12, 153], [7, 20], "#9e482c"),
        ]:
            await effect(
                "layer.newShape",
                kind="rect",
                name=name,
                position=position,
                size=size,
                fill=color,
                stroke=False,
            )
        for idx in range(10):
            await effect(
                "layer.newShape",
                kind="rect",
                name=f"Index notch {idx}",
                position=[19 if idx % 5 else 21, 16 + 32 * idx],
                size=[6 if idx % 5 else 11, 2],
                fill="#af9e85",
                stroke=False,
            )
        await call(
            artist,
            "render_frame",
            {
                "comp": "Tape edge",
                "time": 0,
                "transparent": True,
                "inline": False,
                "path": str(folder / "Tape edge.png"),
            },
        )
        await call(
            artist, "save_project", {"path": str(folder / "Silver print.ecproj")}
        )
        print(
            "EffectCraft rendered eight print exposures, a finished master, and the tape edge",
            flush=True,
        )


async def studio_identity():
    """Draw the JB tape mark and lay out the three printed meter faces."""
    folder = out / "Studio graphics"
    folder.mkdir(exist_ok=True)
    async with session("vectorcraft") as vector:
        await vector.initmcp()
        await call(
            vector,
            "command_run",
            {
                "id": "file.new",
                "params": {
                    "name": "JB — tape mark",
                    "width": 64,
                    "height": 64,
                    "units": "Pixels",
                    "colorMode": "RGB",
                },
            },
        )
        await call(
            vector,
            "draw_path",
            {
                "name": "Vermilion plate",
                "d": "M9 0H55Q64 0 64 9V55Q64 64 55 64H9Q0 64 0 55V9Q0 0 9 0Z",
                "fill": "#ee693c",
                "stroke": "none",
            },
        )
        for label, path in [
            ("Return bend", "M24 16V37C24 45 20 48 15 48C11 48 8 45 8 40"),
            (
                "Double loop",
                "M34 48V16H42C48 16 52 18 52 24C52 29 48 32 42 32H34M42 32C50 32 55 34 55 40C55 46 50 48 43 48H34",
            ),
        ]:
            await call(
                vector,
                "draw_path",
                {
                    "name": label,
                    "d": path,
                    "fill": "none",
                    "stroke": "#282824",
                    "strokeWidth": 5.7,
                    "cap": "round",
                    "join": "round",
                },
            )
        await call(
            vector, "save_file", {"path": str(folder / "JB tape mark.vectorcraft")}
        )
        await call(
            vector,
            "export",
            {"path": str(folder / "JB tape mark.svg"), "format": "svg"},
        )
        print("VectorCraft saved the editable monogram and SVG", flush=True)
    async with session("designcraft") as design:
        await design.initmcp()
        await call(
            design,
            "new_document",
            {
                "title": "Project meters",
                "intent": "web",
                "width": 360,
                "height": 82,
                "pages": 3,
                "margins": 0,
                "facingPages": False,
            },
        )

        async def cmd(command, **params):
            return await call(design, "execute", {"command": command, "params": params})

        for name, color in [
            ("Stock", "#f3ecdc"),
            ("Edge", "#a69b80"),
            ("Rule", "#b4a991"),
            ("Locator", "#ad481f"),
        ]:
            await cmd("swatch.create", name=name, color=color)
        for page, source in enumerate(["voice", "memory", "frame"]):

            async def shape(rect, swatch, spread=page):
                await cmd(
                    "frame.create", spread=spread, rect=rect, content="unassigned"
                )
                await cmd("object.fill", swatch=swatch)
                await cmd("object.stroke", weight=0)

            await shape([0, 0, 360, 82], "Edge")
            await shape([3, 3, 357, 79], "Stock")
            await call(
                design,
                "place_image",
                {
                    "path": str(out / f"{source}-trace.png"),
                    "spread": page,
                    "x": 20,
                    "y": 12,
                    "width": 320,
                },
            )
            await shape([16, 57, 344, 59], "Rule")
            for tick in range(17):
                x = 17 + tick * 20
                await shape(
                    [x, 59, x + 2, 70 if tick % 4 == 0 else 64],
                    "Locator" if tick == page * 6 + 2 else "Rule",
                )
            await call(
                design,
                "export_png",
                {"page": page, "scale": 1, "path": str(folder / f"meter-{source}.png")},
            )
        result = await call(
            design,
            "save_document",
            {"path": str(folder / "Project meters.designcraft")},
        )
        print("DesignCraft saved all three meter pages", result, flush=True)


async def main():
    if options.studio_identity:
        await studio_identity()
        return
    if options.contact_print:
        await contact_print()
        return
    if options.patchbay_only:
        await solid("patchbay")
        return
    await asyncio.gather(
        *(solid(x) for x in ["spool", "memory", "gate", "patchbay"]), traces(), film()
    )


if __name__ == "__main__":
    asyncio.run(main())
