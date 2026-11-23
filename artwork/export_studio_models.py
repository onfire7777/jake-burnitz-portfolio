"""Export articulated, browser-sized versions of the four portfolio sculptures.

Usage: python artwork/export_studio_models.py site/assets/models
Requires the same bpy 4.5 and Pillow environment as render_studio.py.
Coordinates in the resulting GLBs are Y-up with the control face toward +Z.
"""

import argparse
import math
import runpy
import sys
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory

import bpy
from mathutils import Matrix

SCULPTURES = {
    "recorder": "recorder",
    "burnos": "voice",
    "mnemosyne": "memory",
    "mnemetric": "benchmark",
}
HOUSING = {"Back housing", "Jack socket", "Jack bezel", "Front speaker grille"}
REELS = {
    "Reel spoke",
    "Aluminum rim",
    "Inner rim",
    "Reel hub",
    "Spindle recess",
    "Spindle",
}
WINDINGS = {"Wound tape", "Tape winding", "Lower flange"}


def studio_builders(scratch):
    # The original production script exposes the four modeling functions after
    # its normal preview build. A single small preview initializes its materials.
    path = Path(__file__).with_name("render_studio.py")
    original_args = sys.argv
    try:
        sys.argv = [str(path), "voice", str(scratch), "--draft"]
        module = runpy.run_path(str(path), run_name="studio_preview")
    finally:
        sys.argv = original_args
    api = module["voice"].__globals__
    for obj in list(bpy.context.scene.objects):
        if obj != api["objects"]:
            bpy.data.objects.remove(obj, do_unlink=True)

    def disk(name, xyz, radius, height, mat, angle=(0, 0, 0)):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=24, radius=radius, depth=height, location=xyz, rotation=angle
        )
        obj = bpy.context.object
        for face in obj.data.polygons:
            face.use_smooth = len(face.vertices) == 4
        return api["finish"](obj, name, mat, min(height * 0.15, 0.025))

    def ring(name, x, y, z, radius, mat, gauge=0.018):
        # Two etched concentric rings read as wound tape at card size.
        if (
            name == "Tape winding"
            and min(abs(radius - r) for r in (0.62, 0.50, 0.45, 0.33)) > 0.002
        ):
            return None
        points = [
            (
                x + radius * math.cos(i * math.tau / 40),
                y + radius * math.sin(i * math.tau / 40),
                z,
            )
            for i in range(40)
        ]
        return api["pipe"](name, points, mat, gauge, True)

    api["disk"], api["ring"] = disk, ring
    return api


def pivot_for(sculpture, obj):
    name = obj.name.split(".")[0]
    x, _, z = obj.location
    if sculpture == "recorder":
        side = "Left" if x < 0 else "Right"
        spindle = (-0.83 if x < 0 else 0.83, 0.61, 0.82)
        if name in REELS or name in WINDINGS:
            # Ring curves have their points in deck space and their object at
            # the origin. Recover the reel side from the ring centre.
            if obj.type == "CURVE":
                pts = obj.data.splines[0].points
                x = sum(p.co.x for p in pts) / len(pts)
                side = "Left" if x < 0 else "Right"
                spindle = (-0.83 if x < 0 else 0.83, 0.61, 0.82)
            return ("Reel" if name in REELS else "Tape") + side, spindle
        if name in HOUSING:
            return "Hull", (0, 0, 0)
        if name in {"Enamel side rail", "Rail fastener"}:
            return "Rail" + side, (0, 0, 0)
        if name == "Case seam":
            return "Seam", (0, 0, 0)
        if name in {"Tape deck", "Head block", "Guide roller"}:
            return "Deck", (0, 0, 0)
        if name == "Threaded tape":
            return "Tape", (0, 0, 0)
        if name == "Meter needle":
            return "Needle", (-0.82, -1.10, 0.77)
        return "Face", (0, 0, 0)
    if sculpture == "burnos":
        if name == "Waveform vane":
            group = round(x / 0.137 + 16) // 3
            return f"Wave{group + 1:02}", ((group * 3 + 1 - 16) * 0.137, 0, 1.25)
        return "Stand", (0, 0, 0)
    if sculpture == "mnemosyne":
        index = round((z - 0.18) / 0.31) if name == "Memory plate" else 4
        return f"Plate{index + 1:02}", (
            (index - 2) * 0.09,
            (index - 2) * 0.05,
            0.18 + index * 0.31,
        )
    index = round(x / 0.44 + 2.5)
    return f"Gauge{index + 1:02}", ((index - 2.5) * 0.44, 0, 0.07)


def export(api, sculpture, destination):
    source_root = api["objects"]
    api[SCULPTURES[sculpture]]()
    objects = list(source_root.children)
    for obj in objects:
        if obj.type == "CURVE":
            obj.data.bevel_resolution = 0
        if obj.type == "FONT":
            obj.data.resolution_u = 3
        for mod in obj.modifiers:
            if mod.type == "BEVEL":
                mod.segments = 2 if obj.name in {"Back housing", "Face casting"} else 1
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    groups = defaultdict(list)
    pivots = {}
    for obj in objects:
        group, pivot = pivot_for(sculpture, obj)
        evaluated = obj.evaluated_get(deps)
        mesh = bpy.data.meshes.new_from_object(evaluated, depsgraph=deps)
        mesh.transform(Matrix.Translation(tuple(-n for n in pivot)) @ obj.matrix_world)
        part = bpy.data.objects.new(group + " component", mesh)
        bpy.context.collection.objects.link(part)
        groups[group].append(part)
        pivots[group] = pivot
    for obj in objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    for group, parts in groups.items():
        bpy.ops.object.select_all(action="DESELECT")
        for part in parts:
            part.select_set(True)
        bpy.context.view_layer.objects.active = parts[0]
        if len(parts) > 1:
            bpy.ops.object.join()
        node = bpy.context.view_layer.objects.active
        node.name = group
        node.data.name = group
        node.parent = source_root
        node.location = pivots[group]
    source_root.name = "StudioObject"
    bpy.ops.export_scene.gltf(
        filepath=str(destination / (sculpture + ".glb")),
        export_format="GLB",
        export_yup=True,
        export_texcoords=False,
        export_normals=True,
        export_tangents=False,
        export_animations=False,
        export_all_vertex_colors=False,
        export_materials="EXPORT",
        export_cameras=False,
        export_lights=False,
    )
    for obj in list(source_root.children):
        bpy.data.objects.remove(obj, do_unlink=True)
    print(
        sculpture,
        (destination / (sculpture + ".glb")).stat().st_size,
        "bytes",
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as temp:
        api = studio_builders(Path(temp))
        for sculpture in SCULPTURES:
            export(api, sculpture, args.destination)


if __name__ == "__main__":
    main()
