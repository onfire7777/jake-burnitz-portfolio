"""Render the portfolio's original studio objects with bpy 4.5 and Pillow.

Run with --help for scenes and output options. These are offline production
assets. The deployed portfolio does not require Blender or a 3D runtime.
"""

import argparse
import math
from pathlib import Path
from tempfile import TemporaryDirectory

import bpy
from mathutils import Vector
from PIL import Image

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("scene", choices=["recorder", "voice", "memory", "benchmark"])
parser.add_argument("destination", type=Path)
parser.add_argument(
    "--turntable",
    action="store_true",
    help="Render 36 recorder views at ten-degree intervals",
)
parser.add_argument("--draft", action="store_true")
parser.add_argument(
    "--exploded",
    action="store_true",
    help="Separate the recorder housing, deck and reels",
)
args = parser.parse_args()
args.destination.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 6 if args.draft else 16
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 4
scene.render.threads_mode = "FIXED"
scene.render.threads = 6
scene.view_settings.view_transform = "AgX"


def rgb(hex_value):
    values = [int(hex_value[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(
        v / 12.92 if v < 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values
    ) + (1,)


def material(name, color, metal=0, rough=0.35):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgb(color)
    mat.use_nodes = True
    node = mat.node_tree.nodes.get("Principled BSDF")
    for key, val in [
        ("Base Color", rgb(color)),
        ("Metallic", metal),
        ("Roughness", rough),
    ]:
        node.inputs[key].default_value = val
    return mat


aluminum = material("Bead-blasted aluminum", "bdc2bd", 0.83, 0.27)
polished = material("Polished edge", "e0e6e4", 0.94, 0.18)
ink = material("Graphite rubber", "282a28", 0.13, 0.32)
black = material("Anodized graphite", "383d3e", 0.7, 0.28)
reel_steel = material("Reel faces", "dce0db", 0.78, 0.23)
orange = material("Signal enamel", "f04b16", 0.26, 0.27)
tape = material("Magnetic tape", "3d251c", 0.45, 0.28)
cream = material("Meter ivory", "f4eccf", 0.14, 0.28)
teal = material("Oxide green", "647b76", 0.62, 0.3)
objects = bpy.data.objects.new("Turntable", None)
scene.collection.objects.link(objects)


def finish(obj, name, mat, radius=0):
    obj.name = name
    obj.parent = objects
    obj.data.materials.append(mat)
    if radius:
        bevel = obj.modifiers.new("Machined edges", "BEVEL")
        bevel.width = radius
        bevel.segments = 4
        normals = obj.modifiers.new("Face normals", "WEIGHTED_NORMAL")
        normals.keep_sharp = True
    return obj


def box(name, xyz, size, mat, bevel=0.025):
    bpy.ops.mesh.primitive_cube_add(size=1, location=xyz)
    obj = bpy.context.object
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, name, mat, bevel)


def disk(name, xyz, radius, height, mat, angle=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=80, radius=radius, depth=height, location=xyz, rotation=angle
    )
    obj = bpy.context.object
    for p in obj.data.polygons:
        p.use_smooth = len(p.vertices) == 4
    return finish(obj, name, mat, min(height * 0.15, 0.025))


def pipe(name, points, mat, radius, loop=False):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius
    curve.bevel_resolution = 3
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for p, xyz in zip(spline.points, points):
        p.co = (*xyz, 1)
    spline.use_cyclic_u = loop
    obj = bpy.data.objects.new(name, curve)
    scene.collection.objects.link(obj)
    return finish(obj, name, mat)


def ring(name, x, y, z, radius, mat, gauge=0.018):
    points = [
        (
            x + radius * math.cos(i * math.tau / 96),
            y + radius * math.sin(i * math.tau / 96),
            z,
        )
        for i in range(96)
    ]
    return pipe(name, points, mat, gauge, True)


def label(text, x, y, z, size, mat):
    font = bpy.data.curves.new(text, "FONT")
    font.body, font.size, font.align_x = text, size, "CENTER"
    obj = bpy.data.objects.new(text, font)
    scene.collection.objects.link(obj)
    obj.location = (x, y, z)
    return finish(obj, text, mat)


def screw(x, y, z):
    disk("Countersunk screw", (x, y, z), 0.046, 0.015, polished)
    slot = box("Screw slot", (x, y, z + 0.009), (0.057, 0.012, 0.004), ink, 0)
    slot.rotation_euler.z = 0.65


def spool(x, y, fill):
    disk("Lower flange", (x, y, 0.79), 0.748, 0.055, aluminum)
    disk("Wound tape", (x, y, 0.882), fill, 0.16, tape)
    for r in [fill - 0.02, fill - 0.055, fill - 0.09, fill - 0.14, fill - 0.18]:
        ring("Tape winding", x, y, 0.966, r, black, 0.005)
    ring("Aluminum rim", x, y, 1.00, 0.718, reel_steel, 0.038)
    ring("Inner rim", x, y, 1.00, 0.66, aluminum, 0.026)
    for i in range(3):
        a = i * math.tau / 3 + 0.22
        spoke = box(
            "Reel spoke",
            (x + 0.37 * math.cos(a), y + 0.37 * math.sin(a), 0.996),
            (0.69, 0.20, 0.06),
            reel_steel,
            0.026,
        )
        spoke.rotation_euler.z = a
    disk("Reel hub", (x, y, 1.012), 0.222, 0.084, reel_steel)
    disk("Spindle recess", (x, y, 1.067), 0.119, 0.034, black)
    disk("Spindle", (x, y, 1.095), 0.055, 0.045, polished)


def recorder():
    box("Back housing", (0, 0, 0.28), (3.65, 3.32, 0.49), black, 0.15)
    box("Case seam", (0, 0, 0.49), (3.69, 3.36, 0.08), ink, 0.038)
    box("Face casting", (0, 0, 0.56), (3.68, 3.35, 0.22), aluminum, 0.10)
    box("Tape deck", (0, 0.55, 0.688), (3.39, 1.90, 0.09), black, 0.073)
    spool(-0.83, 0.61, 0.64)
    spool(0.83, 0.61, 0.47)
    for x in [-1.08, 1.08]:
        disk("Guide roller", (x, -0.205, 0.794), 0.101, 0.13, polished)
    box("Head block", (0, -0.24, 0.795), (0.73, 0.245, 0.165), aluminum, 0.045)
    pipe(
        "Threaded tape",
        [
            (-1.40, 0.34, 0.84),
            (-1.16, -0.25, 0.84),
            (-1.05, -0.30, 0.84),
            (1.05, -0.30, 0.84),
            (1.16, -0.24, 0.84),
            (1.28, 0.52, 0.84),
        ],
        tape,
        0.021,
    )
    # Analog level meter, with a red end zone and a physical needle.
    box("VU bezel", (-0.82, -0.86, 0.70), (1.18, 0.63, 0.08), ink, 0.05)
    box("VU dial", (-0.82, -0.86, 0.745), (1.06, 0.52, 0.025), cream, 0.026)
    for i in range(17):
        a = math.radians(52 + i * 4.65)
        x, y = -0.82 + 0.71 * math.cos(a), -1.47 + 0.71 * math.sin(a)
        mark = box(
            "Meter graduation",
            (x, y, 0.762),
            (0.014, 0.078 if i % 4 == 0 else 0.043, 0.006),
            orange if i < 5 else ink,
            0,
        )
        mark.rotation_euler.z = a - math.pi / 2
    pipe("Meter needle", [(-0.82, -1.10, 0.77), (-0.70, -0.75, 0.77)], orange, 0.010)
    label("VU", -0.82, -0.96, 0.769, 0.093, ink)
    # Transport keys and model markings are part of the object.
    for i, (x, mat) in enumerate(zip([0.05, 0.45, 0.85], [ink, ink, orange])):
        box("Key well", (x, -0.97, 0.68), (0.35, 0.47, 0.05), black, 0.025)
        box("Transport key", (x, -0.95, 0.76), (0.29, 0.39, 0.14), mat, 0.035)
        if i == 0:
            box("Stop icon", (x, -0.95, 0.835), (0.085, 0.085, 0.004), cream, 0)
        elif i == 1:
            pipe(
                "Play icon",
                [
                    (x - 0.035, -1.00, 0.835),
                    (x + 0.06, -0.95, 0.835),
                    (x - 0.035, -0.90, 0.835),
                ],
                cream,
                0.012,
                True,
            )
        else:
            disk("Record dot", (x, -0.95, 0.835), 0.050, 0.006, cream)
    disk("Level dial", (1.45, -0.86, 0.77), 0.205, 0.22, black)
    for i in range(26):
        a = i * math.tau / 26
        rib = box(
            "Knurl",
            (1.45 + 0.20 * math.cos(a), -0.86 + 0.20 * math.sin(a), 0.77),
            (0.014, 0.026, 0.135),
            ink,
            0.004,
        )
        rib.rotation_euler.z = a
    box("Level index", (1.45, -0.74, 0.884), (0.022, 0.093, 0.005), cream, 0)
    label("J. BURNITZ", -0.89, -1.40, 0.678, 0.145, ink)
    label(
        "S T E R E O    /    F I E L D    R E C O R D E R",
        0.67,
        -1.40,
        0.678,
        0.072,
        black,
    )
    for x in [-1.67, 1.67]:
        for y in [-1.48, 1.46]:
            screw(x, y, 0.674)
    for i in range(13):
        box(
            "Front speaker grille",
            (-1.01 + i * 0.112, -1.66, 0.31),
            (0.057, 0.028, 0.17),
            ink,
            0.011,
        )
    for x in [0.91, 1.37]:
        disk(
            "Jack bezel", (x, -1.666, 0.31), 0.115, 0.043, polished, (math.pi / 2, 0, 0)
        )
        disk("Jack socket", (x, -1.692, 0.31), 0.071, 0.045, ink, (math.pi / 2, 0, 0))
    # The orange side rails are visible all the way around the turntable.
    for x in [-1.828, 1.828]:
        box("Enamel side rail", (x, 0, 0.375), (0.092, 2.88, 0.30), orange, 0.043)
        for y in [-1.24, 1.24]:
            disk(
                "Rail fastener",
                (x + math.copysign(0.052, x), y, 0.38),
                0.055,
                0.012,
                black,
                (0, math.pi / 2, 0),
            )


def voice():
    pipe("Polished support axle", [(-2.33, 0, 1.25), (2.33, 0, 1.25)], polished, 0.056)
    for x in (-1.97, 1.97):
        box("Pedestal", (x, 0.05, 0.60), (0.085, 0.13, 1.20), aluminum)
        box("Foot", (x, 0.05, 0.055), (0.35, 0.65, 0.10), black)
    for i in range(33):
        x = (i - 16) * 0.137
        wave = math.exp(-(((x + 0.42) / 0.79) ** 2)) + 0.61 * math.exp(
            -(((x - 1.12) / 0.44) ** 2)
        )
        height = 0.23 + 2.2 * wave * (0.57 + 0.43 * abs(math.cos(i * 0.65)))
        rod = box(
            "Waveform vane",
            (x, math.sin(i * 0.19) * 0.15, 1.25),
            (0.092, 0.68, height),
            orange if i % 8 else polished,
            0.042,
        )
        rod.rotation_euler.z = -0.17


def memory():
    for i in range(5):
        z = 0.18 + i * 0.31
        plate = box(
            "Memory plate",
            ((i - 2) * 0.09, (i - 2) * 0.05, z),
            (2.65, 2.06, 0.145),
            [black, teal, aluminum, teal, polished][i],
            0.07,
        )
        plate.rotation_euler.z = (i - 2) * 0.115
    for i in range(9):
        pipe(
            "Memory trace",
            [
                (-0.85, -0.42 + i * 0.105, 1.50),
                (-0.25, -0.42 + i * 0.105, 1.50),
                (0.12, -0.70 + i * 0.105, 1.50),
                (0.77, -0.70 + i * 0.105, 1.50),
            ],
            teal,
            0.013,
        )
    disk("Index pin", (0.88, 0.61, 1.51), 0.12, 0.035, orange)


def benchmark():
    for i, h in enumerate([0.42, 0.71, 1.03, 1.43, 1.94, 2.45]):
        x = (i - 2.5) * 0.44
        box(
            "Gauge blade",
            (x, 0, h / 2 + 0.07),
            (0.36, 1.4, h),
            orange if i == 5 else aluminum,
            0.055,
        )
        for j in range(1, int(h / 0.17)):
            box(
                "Calibration tick",
                (x - 0.045, -0.703, 0.10 + j * 0.17),
                (0.16 if j % 3 == 0 else 0.09, 0.008, 0.012),
                ink,
                0,
            )


def aim(obj, point):
    obj.rotation_euler = (
        (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()
    )


def softbox(name, xyz, size, power):
    data = bpy.data.lights.new(name, "AREA")
    data.energy, data.shape, data.size = power, "DISK", size
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = xyz
    aim(obj, (0, 0, 0.4))


builders = {
    "recorder": recorder,
    "voice": voice,
    "memory": memory,
    "benchmark": benchmark,
}
builders[args.scene]()
if args.exploded:
    if args.scene != "recorder" or not args.turntable:
        parser.error("--exploded requires recorder --turntable")
    for obj in objects.children:
        name = obj.name.split(".")[0]
        if name in {
            "Back housing",
            "Front speaker grille",
            "Jack bezel",
            "Jack socket",
        }:
            continue
        if name in {"Enamel side rail", "Rail fastener"}:
            obj.location.x += math.copysign(0.22, obj.location.x)
        elif name in {
            "Aluminum rim",
            "Inner rim",
            "Reel spoke",
            "Reel hub",
            "Spindle recess",
            "Spindle",
        }:
            obj.location.z += 1.65
        elif name in {"Wound tape", "Tape winding", "Lower flange", "Threaded tape"}:
            obj.location.z += 1.20
        elif name in {"Tape deck", "Guide roller", "Head block"}:
            obj.location.z += 0.85
        elif name == "Case seam":
            obj.location.z += 0.20
        else:
            obj.location.z += 0.52
floor_colors = {
    "recorder": "c9c7bf",
    "voice": "edbb9f",
    "memory": "b5c4bc",
    "benchmark": "c4c9d0",
}
bpy.ops.mesh.primitive_plane_add(size=200)
bpy.context.object.data.materials.append(
    material("Studio sweep", floor_colors[args.scene], rough=0.83)
)
world = bpy.data.worlds.new("Studio ambient")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.48
world.node_tree.nodes["Background"].inputs["Color"].default_value = (
    0.82,
    0.85,
    0.90,
    1,
)
scene.world = world
softbox("Broad key", (-3.8, -4.4, 7), 4.5, 580)
softbox("Strip reflection", (2.4, 4.5, 6), 3.4, 720)
softbox("Front bounce", (5, -2, 3.5), 2.8, 150)
bpy.ops.object.camera_add(
    location=(4.5, -6.5, 7.4) if args.scene == "recorder" else (4, -7, 4.4)
)
camera = bpy.context.object
scene.camera = camera
camera.data.type = "ORTHO"
is_recorder = args.scene == "recorder"
aim(
    camera,
    (
        0,
        0,
        (1.25 if args.exploded else 0.50)
        if is_recorder
        else (1.15 if args.scene == "voice" else 0.84),
    ),
)
camera.data.ortho_scale = {
    "recorder": 6.8 if args.exploded else 5.86,
    "voice": 6.4,
    "memory": 4.38,
    "benchmark": 4.54,
}[args.scene]
width, height = (
    (1200, 900)
    if is_recorder
    else ((1040, 530) if args.scene == "voice" else (680, 680))
)
if args.turntable:
    width, height = 660, 495
if args.draft:
    width, height = 600, 450
scene.render.resolution_x, scene.render.resolution_y = width, height
scene.render.resolution_percentage = 100
with TemporaryDirectory() as tmp:
    source = Path(tmp) / "studio.png"
    scene.render.filepath = str(source)
    for n in range(0 if args.exploded else 1, 36) if args.turntable else [0]:
        objects.rotation_euler.z = math.radians(n * 10)
        bpy.ops.render.render(write_still=True)
        dest = args.destination / (
            f"{'open' if args.exploded else 'view'}-{n:02d}.webp"
            if args.turntable
            else f"{args.scene}.webp"
        )
        with Image.open(source) as img:
            picture = img.convert("RGB")
            picture.save(dest, quality=85, method=6)
            if is_recorder and not args.draft and not args.turntable:
                picture.resize((640, 480), Image.Resampling.LANCZOS).save(
                    args.destination / "recorder-small.webp", quality=85, method=6
                )
        print(dest, flush=True)
