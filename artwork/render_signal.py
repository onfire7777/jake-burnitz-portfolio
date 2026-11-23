"""Light the three SolidCraft models and export the independent scroll layers.

Usage: python artwork/render_signal.py CRAFT_PROJECT_DIR WEB_ASSET_DIR [--draft]
The project directory contains spool/memory/gate STL exports, three EffectCraft
trace PNGs, and FilmCraft exposure-0/1/2 PNGs. Requires bpy 4.5 and Pillow.
"""

import argparse
import math
import tempfile
from pathlib import Path

import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from PIL import Image, ImageOps

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", type=Path)
parser.add_argument("output", type=Path)
parser.add_argument("--draft", action="store_true")
options = parser.parse_args()
options.output.mkdir(parents=True, exist_ok=True)
radians = math.radians


def material(name, color, metal=0.0, rough=0.4):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    values = [int(color[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    bsdf.inputs["Base Color"].default_value = (*[v**2.2 for v in values], 1)
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Roughness"].default_value = rough
    return mat


def finish(obj, name, mat, parent=None, bevel=0):
    obj.name = name
    obj.data.materials.append(mat)
    if parent:
        obj.parent = parent
    if bevel:
        mod = obj.modifiers.new("Machined edge", "BEVEL")
        mod.width, mod.segments = bevel, 3
        obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    return obj


def pivot(name, xyz, angle=(0, 0, 0)):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.location, obj.rotation_euler = xyz, tuple(map(radians, angle))
    return obj


def component(kind, parent, mat, z, scale=0.038):
    bpy.ops.wm.stl_import(filepath=str(options.source / (kind + ".stl")))
    obj = bpy.context.object
    obj.scale = (scale,) * 3
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.location = (0, 0, z)
    return finish(obj, kind, mat, parent, 0.018)


def cylinder(name, xyz, radius, height, mat, parent=None):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=100, radius=radius, depth=height, location=xyz
    )
    obj = bpy.context.object
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return finish(obj, name, mat, parent, min(0.025, height * 0.22))


def ring(parent, r, z, mat, gauge=0.014):
    bpy.ops.mesh.primitive_torus_add(
        major_segments=100,
        minor_segments=8,
        major_radius=r,
        minor_radius=gauge,
        location=(0, 0, z),
    )
    obj = bpy.context.object
    for face in obj.data.polygons:
        face.use_smooth = True
    return finish(obj, "Lathed groove", mat, parent)


def block(name, xyz, size, mat, parent=None, bevel=0.04):
    bpy.ops.mesh.primitive_cube_add(size=1, location=xyz)
    obj = bpy.context.object
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, name, mat, parent, bevel)


def ribbon(points, width, front, back, name="Oxide ribbon"):
    # The local width twists along a continuous path, giving each fold two faces.
    verts, faces = [], []
    for pos, across in points:
        axis = Vector(across).normalized() * width / 2
        pos = Vector(pos)
        verts.extend([pos - axis, pos + axis])
        k = len(verts) - 2
        if k:
            faces.append((k - 2, k, k + 1, k - 1))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    mesh.materials.append(front)
    mesh.materials.append(back)
    for face in mesh.polygons:
        face.use_smooth = True
    edge = obj.modifiers.new("Foil gauge", "SOLIDIFY")
    edge.thickness, edge.material_offset = 0.018, 1
    return obj


def path_ribbon(coords, width, mat, reverse):
    # A Catmull–Rom interpolant keeps the tangent continuous at the guide rollers.
    pts = [Vector(p) for p in coords]
    seq = [pts[0], *pts, pts[-1]]
    samples = []
    for i in range(len(seq) - 3):
        a, b, c, d = seq[i : i + 4]
        for j in range(21):
            u = j / 20
            if i and not j:
                continue
            pos = 0.5 * (
                2 * b
                + (-a + c) * u
                + (2 * a - 5 * b + 4 * c - d) * u * u
                + (-a + 3 * b - 3 * c + d) * u**3
            )
            twist = 0.65 * math.sin((i + u) * 1.15)
            samples.append((pos, (0.06, math.sin(twist), math.cos(twist))))
    return ribbon(samples, width, mat, reverse)


def stamp(parent, text, x, y, z, size, mat):
    font = bpy.data.curves.new(text, "FONT")
    font.body, font.size, font.align_x = text, size, "CENTER"
    obj = bpy.data.objects.new(text, font)
    bpy.context.collection.objects.link(obj)
    obj.location = (x, y, z)
    return finish(obj, text, mat, parent)


def light(xyz, color, power, size, target=(0, 0, 1)):
    bpy.ops.object.light_add(type="AREA", location=xyz)
    obj = bpy.context.object
    obj.data.energy, obj.data.shape, obj.data.size = power, "DISK", size
    obj.data.color = color
    obj.rotation_euler = (
        (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
    )


def generate(kind, tmp):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.samples, s.cycles.use_denoising = (5 if options.draft else 24), True
    s.cycles.max_bounces = 5
    s.render.threads_mode, s.render.threads = "FIXED", 6
    s.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("Softbox fill")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.86, 0.88, 0.92, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
    s.world = world
    silver = material("Milled nickel", "c7c8c2", 0.83, 0.27)
    pale = material("Pale bead blast", "deded5", 0.58, 0.29)
    steel = material("Blued steel", "474b4b", 0.73, 0.3)
    ferrite = material("Ferrite", "2f201a", 0.44, 0.32)
    copper = material("Vermilion enamel", "fa5424", 0.36, 0.23)
    bronze = material("Copper reverse", "b85b34", 0.73, 0.23)
    green = material("Oxidized nickel", "798979", 0.66, 0.3)
    paper = material("Studio sweep", "ded5c4", 0.03, 0.58)
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
    finish(bpy.context.object, "Cyclorama", paper)
    separate = []
    strip = []
    if kind == "voice":
        axis = pivot("Tape transport", (-0.68, 0.2, 1.75), (56, -16, -16))
        component("spool", axis, steel, -0.18)
        cylinder("Winding", (0, 0, 0.035), 1.68, 0.33, ferrite, axis)
        for i in range(25):
            ring(axis, 0.35 + i * 0.054, 0.205, bronze if i % 7 == 0 else steel, 0.006)
        path_ribbon(
            [
                (-2.15, 0.48, 1.1),
                (-2.05, -0.63, 0.57),
                (-0.77, -1.22, 0.49),
                (0.8, -1.17, 0.85),
                (1.71, -0.47, 1.72),
                (2.28, 0.23, 1.74),
                (2.65, 0.35, 1.11),
                (2.40, -0.32, 0.40),
                (3.2, -1, 0.2),
                (4.8, -1.1, 0.32),
            ],
            0.34,
            copper,
            bronze,
        )
        separate.append(component("spool", axis, silver, 0.227))
        separate.extend(
            [ring(axis, 1.84, 0.35, pale), ring(axis, 1.74, 0.35, steel, 0.008)]
        )
        separate.extend(
            [
                cylinder("Index collar", (0, 0, 0.38), 0.37, 0.11, steel, axis),
                cylinder("Index button", (0, 0, 0.471), 0.20, 0.083, copper, axis),
                stamp(axis, "SIGNAL   /   A", 0, -1.49, 0.351, 0.125, steel),
            ]
        )
    elif kind == "memory":
        axis = pivot("Memory core", (-0.15, 0.13, 0.60), (7, -7, -18))
        for i in range(8):
            z = i * 0.265
            mat = [steel, green, pale, green, steel, copper, green, pale][i]
            layer = component("memory", axis, mat, z, 0.040)
            layer.rotation_euler.z = radians(i * 3 - 8)
            if i >= 6:
                separate.append(layer)
            if i < 7:
                for x in [-1.12, 1.12]:
                    for y in [-0.85, 0.85]:
                        obj = cylinder(
                            "Stand-off", (x, y, z + 0.18), 0.095, 0.20, bronze, axis
                        )
                        if i >= 6:
                            separate.append(obj)
        separate.append(stamp(axis, "M E M O R Y", 0, -0.82, 1.98, 0.115, steel))
        path_ribbon(
            [
                (-4.8, -1.12, 0.32),
                (-2.42, -0.81, 0.38),
                (-2.11, 0.28, 1.12),
                (-1.84, 1.32, 1.67),
                (-0.35, 1.72, 1.83),
                (1.9, 0.89, 1.55),
                (2.23, -0.43, 0.47),
                (2.72, -1.09, 0.25),
                (4.8, -1.10, 0.32),
            ],
            0.35,
            copper,
            bronze,
        )
    else:
        axis = pivot("Film carriage", (0, 0.12, 1.78), (67, -9, -16))
        component("gate", axis, steel, -0.14, 0.045)
        # Three real exposures sit on one continuous photographic strip.
        for j in range(-1, 2):
            texture_path = options.source / f"exposure-{j + 1}.png"
            im = Image.open(texture_path).convert("RGB")
            im = ImageOps.colorize(ImageOps.grayscale(im), "#231d1b", "#ffe6c5")
            tex_path = tmp / f"print-{j}.png"
            im.save(tex_path)
            mat = material("Photographic emulsion", "ffffff", 0.05, 0.29)
            texture = mat.node_tree.nodes.new("ShaderNodeTexImage")
            texture.image = bpy.data.images.load(str(tex_path))
            mat.node_tree.links.new(
                texture.outputs["Color"],
                mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"],
            )
            offset = j * 2.69
            strip.append(
                block(
                    "Film base",
                    (offset, 0, 0.115),
                    (2.69, 1.98, 0.028),
                    ferrite,
                    axis,
                    0,
                )
            )
            bpy.ops.mesh.primitive_plane_add(size=1, location=(offset, 0, 0.135))
            still = bpy.context.object
            still.scale = (2.45, 1.39, 1)
            strip.append(finish(still, "Exposed frame", mat, axis))
            for k in range(8):
                x = offset - 1.18 + k * 0.337
                for y in [-0.849, 0.849]:
                    strip.append(
                        block(
                            "Film perforation",
                            (x, y, 0.136),
                            (0.156, 0.102, 0.008),
                            paper,
                            axis,
                            0.012,
                        )
                    )
            strip.append(
                stamp(
                    axis,
                    f"JB    {j + 8:02d}    ▸",
                    offset - 1.02,
                    -0.743,
                    0.145,
                    0.07,
                    copper,
                )
            )
        separate.append(component("gate", axis, silver, 0.20, 0.045))
        for x in [-1.6, 1.6]:
            for y in [-1.17, 1.17]:
                separate.append(
                    cylinder("Gate screw", (x, y, 0.41), 0.11, 0.08, steel, axis)
                )
        separate.append(stamp(axis, "F I L M    G A T E", 0, -1.12, 0.385, 0.14, steel))
        path_ribbon(
            [
                (-4.8, -1.1, 0.32),
                (-3.31, -1.33, 0.30),
                (-2.5, -1.16, 0.58),
                (-2.06, 0.25, 0.86),
                (-1.61, 1.31, 1.22),
                (0.61, 2.0, 0.92),
                (3.2, 1.1, 0.33),
            ],
            0.28,
            copper,
            bronze,
        )
    light((-4, -4, 8), (1, 0.86, 0.73), 1000, 5)
    light((4, -0.2, 6), (0.75, 0.87, 1), 900, 4)
    light((0, 5, 6), (1, 0.83, 0.65), 1000, 3)
    bpy.ops.object.camera_add(location=(3.0, -11.4, 7.25))
    cam = bpy.context.object
    cam.rotation_euler = (
        (Vector((0, 0, 1.38)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    )
    cam.data.type, cam.data.ortho_scale = "ORTHO", 8.6
    s.camera = cam
    s.render.resolution_x, s.render.resolution_y = (
        (660, 430) if options.draft else (1360, 880)
    )
    s.render.resolution_percentage = 100
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_mode = "RGBA"
    geometry = [obj for obj in s.objects if obj.type in ("MESH", "FONT", "CURVE")]
    if kind == "voice":
        bpy.context.view_layer.update()

        def project(local):
            q = world_to_camera_view(s, cam, axis.matrix_world @ Vector(local))
            return Vector((q.x, 1 - q.y))

        center = project((0, 0, 0.34))
        x = project((1, 0, 0.34)) - center
        y = project((0, 1, 0.34)) - center
        aspect = s.render.resolution_y / s.render.resolution_x
        factor = 1 / x.length
        print(
            "REEL PROJECTION",
            list(center),
            [x.x * factor, x.y * aspect * factor, y.x * factor, y.y * aspect * factor],
            flush=True,
        )
    layers = [
        ("bench", set(geometry) - set(separate) - set(strip)),
        ("part", set(separate)),
    ]
    if strip:
        layers.append(("strip", set(strip)))
    for layer, visible in layers:
        for obj in geometry:
            obj.hide_render = obj not in visible
        s.render.film_transparent = layer != "bench"
        s.render.filepath = str(tmp / (kind + "-" + layer + ".png"))
        bpy.ops.render.render(write_still=True)
        im = Image.open(s.render.filepath).convert(
            "RGBA" if layer != "bench" else "RGB"
        )
        for small in [False, True]:
            dest = options.output / (
                kind + "-" + layer + ("-small" if small else "") + ".webp"
            )
            result = im.resize((680, 440), Image.Resampling.LANCZOS) if small else im
            result.save(dest, quality=85, method=6, exact=True)
    trace = Image.open(options.source / (kind + "-trace.png")).convert("RGBA")
    trace.save(options.output / (kind + "-trace.webp"), lossless=True, method=6)


with tempfile.TemporaryDirectory() as folder:
    for chapter in ("voice", "memory", "frame"):
        generate(chapter, Path(folder))
