"""Build the native Craft projects and render inputs for Signal Path.

Run with the matching SolidCraft, EffectCraft and FilmCraft MCP helpers
registered in Codex. Pass a dedicated output directory as the only argument.
"""

import argparse
import asyncio
from contextlib import asynccontextmanager
import json
import math
from pathlib import Path
import tomllib

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("destination", type=Path)
out = parser.parse_args().destination.expanduser().resolve()
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


async def main():
    await asyncio.gather(
        *(solid(x) for x in ["spool", "memory", "gate"]), traces(), film()
    )


if __name__ == "__main__":
    asyncio.run(main())
