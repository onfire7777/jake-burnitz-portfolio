"""Light the three SolidCraft models and export the independent scroll layers.

Usage: python artwork/render_signal.py CRAFT_PROJECT_DIR WEB_ASSET_DIR [--draft]
The project directory contains spool/memory/gate STL exports, three EffectCraft
trace PNGs, and FilmCraft exposure-0/1/2 PNGs. Requires bpy 4.5 and Pillow.
"""

import argparse
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector
from PIL import Image, ImageDraw, ImageOps

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", type=Path)
parser.add_argument("output", type=Path)
parser.add_argument("--draft", action="store_true")
parser.add_argument(
    "--models", action="store_true", help="Export articulated browser models"
)
parser.add_argument(
    "--print-only",
    action="store_true",
    help="Rebuild the contact print and the tape edge from EffectCraft exposures",
)
parser.add_argument(
    "--installation",
    action="store_true",
    help="Render the page-spanning ribbon, contact print and patch panel",
)
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
        mod.width, mod.segments = bevel, 1 if options.models else 3
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
    return finish(
        obj, kind, mat, parent, 0 if options.models and kind == "spool" else 0.018
    )


def cylinder(name, xyz, radius, height, mat, parent=None):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=32 if options.models else 100,
        radius=radius,
        depth=height,
        location=xyz,
    )
    obj = bpy.context.object
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return finish(obj, name, mat, parent, min(0.025, height * 0.22))


def ring(parent, r, z, mat, gauge=0.014):
    bpy.ops.mesh.primitive_torus_add(
        major_segments=42 if options.models else 100,
        minor_segments=6 if options.models else 8,
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


def export_model(name, groups):
    """Bake modifiers into meshes, preserving each assembly's hinge or axle."""
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    built = []
    for label, origin, pieces in groups:
        if not pieces:
            continue
        joined = []
        local = origin.inverted()
        for piece in pieces:
            evaluated = piece.evaluated_get(deps)
            mesh = bpy.data.meshes.new_from_object(evaluated, depsgraph=deps)
            mesh.transform(local @ evaluated.matrix_world)
            obj = bpy.data.objects.new("Baked part", mesh)
            bpy.context.collection.objects.link(obj)
            joined.append(obj)
        bpy.ops.object.select_all(action="DESELECT")
        for obj in joined:
            obj.select_set(True)
        obj = joined[0]
        bpy.context.view_layer.objects.active = obj
        if len(joined) > 1:
            bpy.ops.object.join()
        obj.name = label
        obj.matrix_world = origin.copy()
        built.append(obj)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in built:
        obj.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=str(options.output / (name + ".glb")),
        export_format="GLB",
        use_selection=True,
        export_animations=False,
        export_cameras=False,
        export_lights=False,
        export_yup=True,
    )
    packer = Path(__file__).resolve().parents[1] / "node_modules" / ".bin" / "gltfpack"
    model = options.output / (name + ".glb")
    packed = options.output / (name + ".packed.glb")
    subprocess.run(
        [
            str(packer),
            "-i",
            str(model),
            "-o",
            str(packed),
            "-kn",
            "-km",
            "-si",
            "0.55" if name != "contact" else "1",
            "-se",
            "0.002",
        ],
        check=True,
    )
    packed.replace(model)
    print("Exported", name, [ob.name for ob in built])


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
        for i in range(0, 25, 4 if options.models else 1):
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
            layer.rotation_euler.z = 0 if options.models else radians(i * 3 - 8)
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
            tex_path = tmp / (f"print-{j}.jpg" if options.models else f"print-{j}.png")
            if options.models:
                im.thumbnail((384, 216))
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
    if options.models:
        # Ground the working assemblies on the same low tabletop fixtures.
        # The arms are behind the moving parts and the memory guides go
        # through the existing holes in the native SolidCraft plates.
        if kind in {"voice", "frame"}:
            x = -0.68 if kind == "voice" else 0
            block("Cast base", (x, 0.83, 0.14), (2.30, 1.52, 0.23), steel, bevel=0.08)
            block(
                "Fixture facing", (x, 0.8, 0.27), (2.15, 1.39, 0.07), pale, bevel=0.037
            )
            block(
                "Bearing support",
                (x, 0.90, 0.92),
                (0.43, 0.52, 1.36),
                silver,
                bevel=0.085,
            )
            block(
                "Bearing seat", (x, 0.85, 1.52), (0.63, 0.72, 0.40), steel, bevel=0.075
            )
            cylinder("Rear axle", (0, 0, -0.32), 0.28, 0.43, bronze, axis)
            for bx in (-0.81, 0.81):
                cylinder("Fixture bolt", (x + bx, 0.46, 0.327), 0.077, 0.053, steel)
                block(
                    "Bolt slot",
                    (x + bx, 0.46, 0.355),
                    (0.074, 0.013, 0.009),
                    pale,
                    bevel=0.002,
                )
            if kind == "voice":
                # A rolled machined edge catches reflections evenly around each
                # opening; the original SolidCraft face stays perfectly planar.
                for index in range(5):
                    angle = math.tau * index / 5
                    collar = ring(axis, 13.9 * 0.038, 0.341, silver, 0.015)
                    collar.location.x = 27.5 * 0.038 * math.cos(angle)
                    collar.location.y = 27.5 * 0.038 * math.sin(angle)
                cylinder("Axle lock", (0, 0, 0.525), 0.085, 0.027, bronze, axis)
                block(
                    "Axle key",
                    (0, 0, 0.541),
                    (0.095, 0.019, 0.008),
                    steel,
                    axis,
                    bevel=0.003,
                )
            else:
                for side in (-1, 1):
                    cylinder(
                        "Film guide",
                        (side * 1.86, 0.82, 0.19),
                        0.093,
                        0.18,
                        bronze,
                        axis,
                    )
                    cylinder(
                        "Guide cap",
                        (side * 1.86, 0.82, 0.292),
                        0.06,
                        0.025,
                        steel,
                        axis,
                    )
        else:
            block("Foot", (0, 0.14, 0.12), (3.18, 2.52, 0.19), steel, bevel=0.065)
            for x in (-1.36, 1.36):
                for y in (-0.92, 0.92):
                    cylinder("Guide rod", (x, y, 1.20), 0.050, 3.36, pale, axis)
                    cylinder("Guide head", (x, y, 2.89), 0.072, 0.050, steel, axis)
        bpy.context.view_layer.update()
        items = [
            ob
            for ob in s.objects
            if ob.type in {"MESH", "CURVE", "FONT"} and ob.name != "Cyclorama"
        ]
        basis = axis.matrix_world.copy()
        if kind == "voice":
            groups = [
                (
                    "Reel",
                    basis,
                    [
                        ob
                        for ob in items
                        if ob.parent == axis and not ob.name.startswith("Rear axle")
                    ],
                )
            ]
            name = "spool"
        elif kind == "memory":
            groups = []
            for i in range(8):
                z = i * 0.265
                pieces = [
                    ob
                    for ob in items
                    if ob.parent == axis
                    and not ob.name.startswith("Guide")
                    and z - 0.001 <= ob.location.z < z + 0.264
                ]
                groups.append(
                    (f"Layer{i}", basis @ Matrix.Translation((0, 0, z)), pieces)
                )
            name = "plates"
        else:
            groups = [("FilmAdvance", basis, strip)]
            name = "gate"
        moved = {ob for _, _, pieces in groups for ob in pieces}
        groups.append(
            ("Bed", Matrix.Identity(4), [ob for ob in items if ob not in moved])
        )
        export_model(name, groups)
        return
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


def render_installation(kind, tmp):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 26 if not options.draft else 6
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 5
    scene.render.threads_mode, scene.render.threads = "FIXED", 6
    scene.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("Cream studio")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.83, 0.85, 0.9, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
    scene.world = world
    light((-4, -4, 7), (1, 0.81, 0.61), 900, 5)
    light((4, 1, 5), (0.79, 0.89, 1), 820, 4)
    light((0, 4, 6), (1, 0.93, 0.83), 950, 3)
    copper = material("Vermilion lacquer", "f05729", 0.44, 0.25)
    bronze = material("Oxide reverse", "944a26", 0.72, 0.25)
    steel = material("Machined nickel", "c5c8c0", 0.84, 0.26)
    dark = material("Bakelite", "39352d", 0.36, 0.34)
    brass = material("Jack ferrule", "c29248", 0.78, 0.23)
    separate = []
    wide = kind != "patchbay"
    dimensions = (1550, 350) if wide else (900, 720)
    scale = 13 if wide else 5.9
    focus = Vector((0, 0, 0.45 if wide else 0.68))
    bpy.ops.object.camera_add(
        location=focus + Vector((0, -7, 8) if wide else (3, -7, 8))
    )
    camera = bpy.context.object
    camera.rotation_euler = (
        (focus - camera.location).to_track_quat("-Z", "Y").to_euler()
    )
    camera.data.type, camera.data.ortho_scale = "ORTHO", scale
    scene.camera = camera
    if kind == "ribbon":
        path_ribbon(
            [
                (-8, -1, 0.15),
                (-6, -0.7, 0.25),
                (-3.8, 0.15, 0.38),
                (-1.6, 0.42, 0.83),
                (-0.4, 0.33, 1.36),
                (0.46, -0.48, 1.3),
                (0.1, -0.78, 0.55),
                (-0.68, -0.12, 0.32),
                (0.26, 0.39, 0.25),
                (1.7, 0.4, 0.22),
                (3.8, -0.15, 0.28),
                (7, -0.5, 0.55),
            ],
            0.47,
            copper,
            bronze,
        )
    elif kind == "contact":
        # A perforated emulsion strip with the actual FilmCraft exposures.
        width, height = 1460, 242
        frame = Image.new("RGBA", (width, height), (48, 37, 30, 255))
        ink = ImageDraw.Draw(frame)
        for i in range(3):
            source = Image.open(options.source / f"exposure-{i}.png").convert("RGB")
            photo = ImageOps.fit(source, (450, 182))
            photo = Image.blend(
                photo, ImageOps.colorize(photo.convert("L"), "#281c16", "#f2e4cd"), 0.55
            )
            left = 18 + i * 486
            frame.paste(photo, (left, 30))
            for j in range(9):
                x = left + j * 53
                for y in [7, 218]:
                    ink.rounded_rectangle((x, y, x + 21, y + 15), 3, fill=(0, 0, 0, 0))
        image_path = tmp / "contact.png"
        frame.save(image_path)
        mat = material("Exposed negative", "ffffff", 0.06, 0.39)
        nodes = mat.node_tree.nodes
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(str(image_path))
        bsdf = nodes.get("Principled BSDF")
        mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        mat.node_tree.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
        verts = []
        faces = []
        steps = 120
        for i in range(steps + 1):
            t = i / steps
            x = (t - 0.5) * 14.4
            center = Vector(
                (
                    x,
                    0.38 * math.sin(t * math.tau - 0.6),
                    0.44 + 0.41 * math.cos(t * math.tau * 1.4),
                )
            )
            twist = 0.23 + 0.43 * math.sin(t * math.tau * 1.55)
            across = Vector((0, math.cos(twist), math.sin(twist)))
            verts.extend([center - across * 1.13, center + across * 1.13])
            if i:
                faces.append((i * 2 - 2, i * 2, i * 2 + 1, i * 2 - 1))
        mesh = bpy.data.meshes.new("Waved contact print")
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        model = bpy.data.objects.new("Contact print", mesh)
        bpy.context.collection.objects.link(model)
        finish(model, "Contact print", mat)
        uv = mesh.uv_layers.new()
        for poly in mesh.polygons:
            poly.use_smooth = True
            for loop in poly.loop_indices:
                vertex = mesh.loops[loop].vertex_index
                uv.data[loop].uv = ((vertex // 2) / steps, float(vertex % 2))
    else:
        panel = pivot("Patch panel", (0, 0.08, 0.22), (0, 0, -11))
        block("Enclosure", (0, 0, 0), (3.98, 2.48, 0.40), dark, panel, 0.14)
        component("patchbay", panel, steel, 0.20, 0.05)
        for x, y in [
            (-1.2, 0.4),
            (-0.4, 0.4),
            (0.4, 0.4),
            (1.2, 0.4),
            (-0.8, -0.5),
            (0, -0.5),
            (0.8, -0.5),
        ]:
            socket = pivot("Socket axis", (x, y, 0.31))
            socket.parent = panel
            cylinder("Jack bore", (0, 0, -0.035), 0.19, 0.06, dark, socket)
            ring(socket, 0.216, 0.035, brass, 0.036)
            ring(socket, 0.18, 0.007, dark, 0.018)
        for x in [-1.75, 1.75]:
            for y in [-1, 1]:
                cylinder("Screw", (x, y, 0.34), 0.073, 0.025, steel, panel)
                block(
                    "Driver slot",
                    (x, y, 0.355),
                    (0.091, 0.017, 0.009),
                    dark,
                    panel,
                    0.002,
                )
        stamp(panel, "J.  B U R N I T Z", 0, 0.9, 0.34, 0.15, dark)
        stamp(panel, "P A T C H    O U T", 0, -1.01, 0.34, 0.105, dark)
        plug = pivot("Patch lead", (0, -0.5, 0.31))
        plug.parent = panel
        for label, radius, z, length, mat in [
            ("Tip", 0.085, 0.02, 0.28, brass),
            ("Insulator", 0.10, 0.2, 0.08, dark),
            ("Sleeve", 0.105, 0.32, 0.19, brass),
            ("Grip", 0.17, 0.6, 0.40, copper),
            ("Collar", 0.182, 0.395, 0.09, steel),
            ("Strain relief", 0.115, 0.87, 0.19, dark),
        ]:
            separate.append(cylinder(label, (0, 0, z), radius, length, mat, plug))
        for i in range(6):
            separate.append(ring(plug, 0.167, 0.47 + i * 0.049, bronze, 0.012))
        coords = [
            (0, 0, 0.95),
            (-0.09, -0.05, 1.33),
            (-0.52, -0.24, 1.64),
            (-1.25, -0.62, 1.28),
            (-1.91, -0.80, 0.54),
            (-2.25, -1.5, 0.31),
            (-1.6, -2.35, 0.29),
            (-2.15, -3.28, 0.20),
            (-3.8, -3.55, 0.18),
        ]
        curve = bpy.data.curves.new("Flexible line", "CURVE")
        curve.dimensions = "3D"
        curve.resolution_u = 22
        curve.bevel_depth = 0.073
        curve.bevel_resolution = 6
        spline = curve.splines.new("BEZIER")
        spline.bezier_points.add(len(coords) - 1)
        for point, xyz in zip(spline.bezier_points, coords):
            point.co = xyz
            point.handle_left_type = point.handle_right_type = "AUTO"
        cord = bpy.data.objects.new("Patch cable", curve)
        bpy.context.collection.objects.link(cord)
        separate.append(finish(cord, "Patch cable", copper, plug))
    if options.models:
        bpy.context.view_layer.update()
        items = [ob for ob in scene.objects if ob.type in {"MESH", "CURVE", "FONT"}]
        if kind == "patchbay":
            sockets = [ob for ob in scene.objects if ob.name.startswith("Socket axis")]
            groups = [("Lead", plug.matrix_world.copy(), separate)]
            for i, socket in enumerate(sockets):
                groups.append(
                    (f"Port{i}", socket.matrix_world.copy(), list(socket.children))
                )
            grouped = {ob for _, _, pieces in groups for ob in pieces}
            groups.append(
                ("Panel", Matrix.Identity(4), [ob for ob in items if ob not in grouped])
            )
            export_model("patch", groups)
        elif kind == "contact":
            # Conform the moving emulsion to the same bent strip as its backing.
            atlas = Image.new("RGB", (8 * 256, 104))
            for i in range(8):
                exposure = Image.open(
                    options.source / "Contact printer" / f"print-{i}.png"
                )
                atlas.paste(
                    ImageOps.fit(exposure.convert("RGB"), (256, 104)), (i * 256, 0)
                )
            atlas_path = tmp / "Contact emulsion.jpg"
            atlas.save(atlas_path, quality=85)
            inlay = material("Moving emulsion", "ffffff", 0.02, 0.45)
            image = inlay.node_tree.nodes.new("ShaderNodeTexImage")
            image.image = bpy.data.images.load(str(atlas_path))
            inlay.node_tree.links.new(
                image.outputs["Color"],
                inlay.node_tree.nodes["Principled BSDF"].inputs["Base Color"],
            )
            overlay = mesh.copy()
            overlay.name = "Exposure mesh"
            overlay.materials.clear()
            overlay.materials.append(inlay)
            # Sample the original surface's printed central photo, with a very
            # small lift to avoid z fighting at shallow camera angles.
            for k in range(steps + 1):
                u = k / steps
                t = (504 + 450 * u) / width
                center = Vector(
                    (
                        (t - 0.5) * 14.4,
                        0.38 * math.sin(t * math.tau - 0.6),
                        0.44 + 0.41 * math.cos(t * math.tau * 1.4) + 0.008,
                    )
                )
                twist = 0.23 + 0.43 * math.sin(t * math.tau * 1.55)
                across = (
                    Vector((0, math.cos(twist), math.sin(twist))) * 1.13 * (182 / 242)
                )
                overlay.vertices[2 * k].co = center - across
                overlay.vertices[2 * k + 1].co = center + across
            cover = bpy.data.objects.new("Emulsion overlay", overlay)
            bpy.context.collection.objects.link(cover)
            export_model(
                "contact",
                [
                    ("Negative", Matrix.Identity(4), [model]),
                    ("Emulsion", Matrix.Identity(4), [cover]),
                ],
            )
        return
    scene.render.film_transparent = True
    scene.render.resolution_x, scene.render.resolution_y = dimensions
    scene.render.resolution_percentage = 65 if options.draft else 100
    scene.render.image_settings.color_mode = "RGBA"
    geometry = [ob for ob in scene.objects if ob.type in {"MESH", "FONT", "CURVE"}]
    layers = [(kind, set(geometry) - set(separate))]
    if separate:
        layers.append(("patch-lead", set(separate)))
    for name, visible in layers:
        for obj in geometry:
            obj.hide_render = obj not in visible
        scene.render.filepath = str(tmp / (name + ".png"))
        bpy.ops.render.render(write_still=True)
        im = Image.open(scene.render.filepath).convert("RGBA")
        im.save(options.output / (name + ".webp"), quality=88, method=6)

    if kind == "contact":
        # Reproject the actual EffectCraft exposures onto the central bend. The
        # transparent margins encode the same camera and curvature as the still.
        printer = options.source / "Contact printer"
        atlas = Image.new("RGBA", (930, 210 * 8))
        scene.render.resolution_x, scene.render.resolution_y = 930, 210
        scene.render.resolution_percentage = 100
        for index in range(8):
            layer = Image.new("RGBA", frame.size)
            photo = ImageOps.fit(
                Image.open(printer / f"print-{index}.png").convert("RGBA"), (450, 182)
            )
            layer.paste(photo, (504, 30))
            texture_path = tmp / f"exposure-{index}.png"
            layer.save(texture_path)
            tex.image = bpy.data.images.load(str(texture_path))
            scene.render.filepath = str(tmp / f"insert-{index}.png")
            bpy.ops.render.render(write_still=True)
            atlas.paste(
                Image.open(scene.render.filepath).convert("RGBA"), (0, index * 210)
            )
        atlas.save(options.output / "contact-exposures.webp", quality=88, method=6)
        Image.open(printer / "Tape edge.png").save(
            options.output / "tape-edge.webp", lossless=True
        )


with tempfile.TemporaryDirectory() as folder:
    if options.models:
        for kind in ("voice", "memory", "frame"):
            generate(kind, Path(folder))
        for kind in ("patchbay", "contact"):
            render_installation(kind, Path(folder))
    elif options.print_only:
        render_installation("contact", Path(folder))
    elif options.installation:
        graphics = options.source / "Studio graphics"
        shutil.copyfile(graphics / "JB tape mark.svg", options.output / "jb-tape.svg")
        for meter in ("voice", "memory", "frame"):
            Image.open(graphics / f"meter-{meter}.png").save(
                options.output / f"meter-{meter}.webp", lossless=True
            )
        for item in ("ribbon", "contact", "patchbay"):
            render_installation(item, Path(folder))
    else:
        for chapter in ("voice", "memory", "frame"):
            generate(chapter, Path(folder))
