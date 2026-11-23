"""Export the VectorCraft copper contours as animated, extruded foil meshes.

The 12.8 x 1.44 world-unit board has a Y-up front view along +Z. Its left rail
runs through (0, +.72) and (0, -.72). The Flex target leaves both joins fixed.
Usage: python artwork/export_splice_models.py site/assets/models
"""

import argparse
import itertools
import json
import math
import struct
from pathlib import Path

# Every sweep begins and ends vertically at the rail. The seventh coordinate
# sets the apparent foil width at that knot as the ribbon turns toward the light.
SWEEPS = {
    "take-up": [
        (0, 26, 31, 28, 113, 34, 4),
        (250, 44, 392, 27, 516, 40, 7),
        (594, 48, 659, 81, 720, 78, 12),
        (780, 76, 786, 42, 748, 43, 5),
        (721, 44, 713, 71, 774, 81, 2),
        (858, 94, 918, 67, 1025, 66, 3),
        (1104, 65, 1104, 89, 1001, 95, 8),
        (835, 105, 489, 92, 285, 104, 3),
        (100, 114, 0, 102, 0, 144, 3),
    ],
    "fold": [
        (0, 25, 48, 29, 138, 30, 3),
        (264, 32, 338, 32, 425, 33, 4),
        (482, 34, 512, 33, 548, 54, 10),
        (580, 73, 589, 84, 631, 85, 3),
        (705, 86, 775, 67, 846, 66, 4),
        (894, 65, 914, 79, 870, 87, 8),
        (825, 95, 736, 98, 663, 98, 4),
        (554, 98, 480, 85, 392, 92, 2),
        (218, 105, 0, 90, 0, 144, 3),
    ],
    "aperture": [
        (0, 25, 51, 24, 132, 25, 3),
        (255, 27, 365, 41, 481, 51, 5),
        (612, 63, 661, 64, 760, 50, 6),
        (871, 34, 959, 18, 1042, 36, 12),
        (1107, 50, 1148, 74, 1118, 85, 3),
        (1078, 100, 996, 87, 917, 86, 7),
        (772, 83, 648, 103, 506, 104, 4),
        (281, 106, 0, 88, 0, 144, 3),
    ],
    "return": [
        (0, 28, 42, 31, 125, 31, 3),
        (240, 31, 325, 34, 417, 44, 4),
        (486, 52, 531, 63, 596, 61, 6),
        (676, 59, 700, 29, 755, 34, 11),
        (804, 38, 820, 75, 772, 91, 5),
        (707, 112, 579, 90, 458, 90, 3),
        (248, 90, 0, 87, 0, 144, 3),
    ],
}


def foil_samples(curves):
    x, y, width = 0, 0, 3
    samples = []
    for ax, ay, bx, by, ex, ey, ew in curves:
        for step in range(25):
            if samples and step == 0:
                continue
            t = step / 24
            u = 1 - t
            px = u**3 * x + 3 * u * u * t * ax + 3 * u * t * t * bx + t**3 * ex
            py = u**3 * y + 3 * u * u * t * ay + 3 * u * t * t * by + t**3 * ey
            dx = u * u * (ax - x) + 2 * u * t * (bx - ax) + t * t * (ex - bx)
            dy = u * u * (ay - y) + 2 * u * t * (by - ay) + t * t * (ey - by)
            mag = math.hypot(dx, dy)
            radius = (width + (ew - width) * t * t * (3 - 2 * t)) / 2
            samples.append((px, py, -dy / mag * radius, dx / mag * radius))
        x, y, width = ex, ey, ew
    return samples


# Eight points around the edge and the copper face. Coating and exposed edge
# differ in color as well as actual height; lighting follows the folded surface.
SECTION = [
    (-1.00, -0.18, "#aa643e"),
    (-0.88, 0.71, "#c48152"),
    (-0.58, 1.05, "#e0a16a"),
    (0.45, 0.92, "#cb8050"),
    (0.86, 0.50, "#bd7046"),
    (1.00, -0.22, "#a15a37"),
    (0.82, -0.65, "#985334"),
    (-0.84, -0.65, "#985334"),
]


def linear_color(code):
    def component(hex_pair):
        s = int(hex_pair, 16) / 255
        return round(
            255 * (s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4)
        )

    return tuple(component(code[i : i + 2]) for i in [1, 3, 5]) + (255,)


def positions(samples, phase, flex):
    distances = [0.0]
    for a, b in itertools.pairwise(samples):
        distances.append(distances[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    points = []
    for (px, py, nx, ny), distance in zip(samples, distances, strict=True):
        t = distance / distances[-1]
        free = math.sin(math.pi * t) ** 1.6 * min(1, px / 65) ** 2
        base_turn = free * 0.32 * math.sin(7 * t + phase)
        turn = base_turn + flex * free * 0.78 * math.sin(13 * t + phase)
        rise = free * (6 + 5 * math.sin(9 * t + phase))
        radius = math.hypot(nx, ny)
        drift = flex * free * math.sin(8 * t + phase)
        for span, relief, _ in SECTION:
            xx = px + nx * math.cos(turn) * span + drift * 3
            yy = py + ny * math.cos(turn) * span + drift * 5
            zz = (
                rise
                + flex * free * (9 + 8 * math.sin(11 * t))
                + radius * span * math.sin(turn)
                + relief
            )
            points.append((xx / 100, (72 - yy) / 100, zz / 100))
    return points


def triangle_indices(count):
    ring = len(SECTION)
    triangles = []
    for i in range(count - 1):
        for j in range(ring):
            a = i * ring + j
            b = i * ring + (j + 1) % ring
            triangles.extend([(a, b, b + ring), (a, b + ring, a + ring)])
    last = (count - 1) * ring
    for j in range(1, ring - 1):
        triangles.extend([(0, j + 1, j), (last, last + j, last + j + 1)])
    return triangles


def normals(points, triangles):
    accum = [[0.0, 0.0, 0.0] for p in points]
    for a, b, c in triangles:
        ab = [v - u for v, u in zip(points[b], points[a], strict=True)]
        ac = [v - u for v, u in zip(points[c], points[a], strict=True)]
        n = [
            ab[1] * ac[2] - ab[2] * ac[1],
            ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0],
        ]
        for vertex in (a, b, c):
            for axis in range(3):
                accum[vertex][axis] += n[axis]
    return [tuple(x / math.hypot(*n) for x in n) for n in accum]


def subtract(a, b):
    return [
        tuple(x - y for x, y in zip(v, w, strict=True))
        for v, w in zip(a, b, strict=True)
    ]


def make_glb(name, curves, phase, destination):
    # The screen contour and the mesh follow the same Cubic Bezier samples.
    samples = foil_samples(curves)[::2]
    base = positions(samples, phase, 0)
    bent = positions(samples, phase, 1)
    triangles = triangle_indices(len(samples))
    base_normals = normals(base, triangles)
    bent_normals = normals(bent, triangles)
    binary = bytearray()
    views = []
    accessors = []

    def attribute(rows, fmt, kind, target, normalized=False):
        while len(binary) % 4:
            binary.append(0)
        offset = len(binary)
        layout = struct.Struct("<" + fmt * len(rows[0]))
        for row in rows:
            binary.extend(layout.pack(*row))
        views.append(
            {
                "buffer": 0,
                "byteOffset": offset,
                "byteLength": len(binary) - offset,
                "target": target,
            }
        )
        record = {
            "bufferView": len(views) - 1,
            "componentType": {"f": 5126, "H": 5123, "B": 5121}[fmt],
            "count": len(rows),
            "type": kind,
        }
        if normalized:
            record["normalized"] = True
        if fmt == "f":
            axes = list(zip(*rows, strict=True))
            record.update(min=[min(a) for a in axes], max=[max(a) for a in axes])
        accessors.append(record)
        return len(accessors) - 1

    material = {
        "name": "Burnished copper foil",
        "pbrMetallicRoughness": {
            "baseColorFactor": [1, 1, 1, 1],
            "metallicFactor": 0.34,
            "roughnessFactor": 0.40,
        },
    }
    colors = [linear_color(color) for _ in samples for _, _, color in SECTION]
    attrs = {
        "POSITION": attribute(base, "f", "VEC3", 34962),
        "NORMAL": attribute(base_normals, "f", "VEC3", 34962),
        "COLOR_0": attribute(colors, "B", "VEC4", 34962, True),
    }
    target = {
        "POSITION": attribute(subtract(bent, base), "f", "VEC3", 34962),
        "NORMAL": attribute(subtract(bent_normals, base_normals), "f", "VEC3", 34962),
    }
    index = attribute([(v,) for tri in triangles for v in tri], "H", "SCALAR", 34963)
    gltf = {
        "asset": {
            "version": "2.0",
            "generator": "Jake Burnitz studio / VectorCraft contours",
        },
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"name": "SpliceTape", "mesh": 0}],
        "meshes": [
            {
                "name": "SpliceTape",
                "weights": [0],
                "extras": {"targetNames": ["Flex"]},
                "primitives": [
                    {
                        "attributes": attrs,
                        "indices": index,
                        "material": 0,
                        "targets": [target],
                    }
                ],
            }
        ],
        "materials": [material],
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(binary)}],
    }
    metadata = json.dumps(gltf, separators=(",", ":")).encode()
    metadata += b" " * (-len(metadata) % 4)
    binary.extend(b"\x00" * (-len(binary) % 4))
    total = 28 + len(metadata) + len(binary)
    data = (
        struct.pack("<4sII", b"glTF", 2, total)
        + struct.pack("<I4s", len(metadata), b"JSON")
        + metadata
        + struct.pack("<I4s", len(binary), b"BIN\x00")
        + binary
    )
    (destination / f"splice-{name}.glb").write_bytes(data)
    print(
        name,
        len(data),
        "bytes",
        len(triangles),
        "triangles; inlet/outlet static",
        flush=True,
    )
    assert (
        base[: len(SECTION)] == bent[: len(SECTION)]
        and base[-len(SECTION) :] == bent[-len(SECTION) :]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    dest = parser.parse_args().destination
    dest.mkdir(parents=True, exist_ok=True)
    for i, (name, curve) in enumerate(SWEEPS.items()):
        make_glb(name, curve, i * 0.82, dest)


if __name__ == "__main__":
    main()
