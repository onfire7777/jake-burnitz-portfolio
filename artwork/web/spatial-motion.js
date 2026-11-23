import { Quaternion, Vector3 } from "three";
import { finishSurfaces } from "./surface-finish.js";

// Models share the studio's Y-up coordinate system. Keep the camera still so
// an axle, plate or contact strip is the source of the motion in each shot.
const cameras = {
  recorder: { eye: [4.5, 7.4, 6.5], target: [0, .50, 0], width: 5.94 },
  burnos: { eye: [4, 4.4, 7], target: [0, 1.15, 0], width: 4.55 },
  mnemosyne: { eye: [4, 4.4, 7], target: [0, .84, 0], width: 4.75 },
  mnemetric: { eye: [4, 4.4, 7], target: [0, 1.20, 0], width: 5.2 },
  spool: { eye: [3, 7.25, 11.4], target: [0, 1.38, 0], width: 8.25 },
  plates: { eye: [3, 7.25, 11.4], target: [0, 1.38, 0], width: 8.25 },
  gate: { eye: [3, 7.25, 11.4], target: [0, 1.38, 0], width: 8.25 },
  patch: { eye: [3, 8.68, 7], target: [0, .68, 0], width: 5.9 },
  contact: { eye: [0, 8.45, 7], target: [0, .45, 0], width: 13 },
};
const spliceCamera = { eye: [6.4, 0, 15], target: [6.4, 0, 0], width: 12.8, height: 1.44 };
const yAxis = new Vector3(0, 1, 0);
const xAxis = new Vector3(1, 0, 0);
const radians = Math.PI / 180;
const clamp = n => Math.max(0, Math.min(1, n));
const smooth = n => { const t = clamp(n); return t * t * (3 - 2 * t); };

function joint(root, name) {
  const node = root.getObjectByName(name);
  if (!node) throw new Error("Missing model joint " + name);
  const position = node.position.clone(), rotation = node.quaternion.clone(), scale = node.scale.clone();
  const up = yAxis.clone().applyQuaternion(rotation), along = xAxis.clone().applyQuaternion(rotation);
  const turn = new Quaternion();
  return {
    node, position, up,
    lift(y, x = 0) { node.position.copy(position).addScaledVector(up, y).addScaledVector(along, x); },
    rotate(axis, value) { node.quaternion.copy(rotation).multiply(turn.setFromAxisAngle(axis, value)); },
    stretch(y) { node.scale.copy(scale); node.scale.y *= y; },
  };
}

function recorder(root, camera) {
  const frame = joint(root, "StudioObject");
  const moving = Object.entries({ Seam: .20, Face: .52, Needle: .52, Deck: .85, Tape: 1.2,
    TapeLeft: 1.2, TapeRight: 1.2, ReelLeft: 1.65, ReelRight: 1.65 }).map(([name, height]) => [joint(root, name), height]);
  const reels = ["ReelLeft", "ReelRight", "TapeLeft", "TapeRight"].map(name => joint(root, name));
  const needle = joint(root, "Needle"), left = joint(root, "RailLeft"), right = joint(root, "RailRight");
  let open = 0, turn = 0;
  return ({ time, scroll, delta, angle, exploded, reduced, instant }) => {
    const follow = (reduced || instant) ? 1 : 1 - Math.exp(-Math.max(delta, .016) * 14);
    const target = -angle * radians;
    turn += Math.atan2(Math.sin(target - turn), Math.cos(target - turn)) * follow;
    frame.rotate(yAxis, turn + (reduced ? 0 : (scroll - .45) * .12));
    open += (Number(exploded) - open) * follow;
    moving.forEach(([part, distance]) => part.lift(distance * open));
    left.lift(0, -.22 * open); right.lift(0, .22 * open);
    reels.forEach((part, index) => part.rotate(yAxis, reduced ? 0 : time * (index % 2 ? .92 : .75)));
    needle.rotate(yAxis, reduced ? 0 : .11 * Math.sin(time * 3.5) + .045 * Math.sin(time * 7.1));
    camera.width = 5.94 + open * .75;
    camera.target[1] = .50 + open * .48;
  };
}

function waveform(root) {
  const waves = Array.from({ length: 11 }, (_, i) => joint(root, "Wave" + String(i + 1).padStart(2, "0")));
  return ({ time, scroll, reduced }) => waves.forEach((part, i) => {
    const phase = time * 2.1 - i * .64 + scroll * 2;
    part.stretch(reduced ? 1 : .88 + .14 * Math.sin(phase) + .08 * Math.sin(phase * 1.8));
    part.rotate(xAxis, reduced ? 0 : .055 * Math.cos(phase));
  });
}

function stack(root, studio) {
  const parts = Array.from({ length: studio ? 8 : 5 }, (_, i) =>
    joint(root, studio ? "Layer" + i : "Plate" + String(i + 1).padStart(2, "0")));
  return ({ time, scroll, reduced }) => parts.forEach((part, i) => {
    const f = i / (parts.length - 1);
    const opening = reduced ? 0 : .30 + .43 * smooth(scroll) + .23 * Math.sin(time * .8 - f * 1.2);
    part.lift(f * opening * (studio ? .95 : .64));
    part.rotate(yAxis, studio ? 0 : f * opening * .26);
  });
}

function patchbay(root) {
  const lead = joint(root, "Lead");
  const sockets = Array.from({ length: 7 }, (_, i) => joint(root, "Port" + i));
  const lights = sockets.map(port => {
    const materials = [];
    port.node.traverse(part => {
      if (!part.isMesh) return;
      const tint = material => {
        if (!material.name.includes("ferrule")) return material;
        const copy = material.clone();
        copy.emissive.set(0xc64f23);
        copy.emissiveIntensity = 0;
        materials.push(copy);
        return copy;
      };
      part.material = Array.isArray(part.material) ? part.material.map(tint) : tint(part.material);
    });
    return materials;
  });
  const start = lead.position.clone();
  let last = 5, progress = 1;
  return ({ time, scroll, delta, port, reduced, instant }) => {
    const dest = port >= 0 && port < sockets.length ? port : 5;
    if (dest !== last) { start.copy(lead.node.position); last = dest; progress = 0; }
    progress = (reduced || instant) ? 1 : Math.min(1, progress + delta * 2.8);
    const height = reduced ? 0 : .52 * Math.sin(Math.PI * progress) + .42 * (1 - smooth(scroll * 2));
    lead.node.position.copy(start).lerp(sockets[dest].position, smooth(progress)).addScaledVector(lead.up, height);
    lead.rotate(yAxis, reduced ? 0 : .055 * Math.sin(time * .86));
    lights.forEach((list, i) => list.forEach(mat => { mat.emissiveIntensity = i === port ? .55 : 0; }));
  };
}

function exposureStrip(root) {
  const negative = joint(root, "Negative"), emulsion = joint(root, "Emulsion");
  let atlas;
  emulsion.node.traverse(mesh => {
    const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    for (const mat of mats) if (mat?.map) atlas = mat.map;
  });
  // Print onto the bent film surface itself. Separate nearly coplanar strips
  // crossed at oblique angles and left visible slivers of the original still.
  emulsion.node.visible = false;
  const exposure = { value: 0 };
  negative.node.traverse(mesh => {
    if (!mesh.isMesh || !mesh.material.map || !atlas) return;
    const mat = mesh.material.clone();
    mat.transparent = false;
    mat.alphaTest = .48;
    mat.depthWrite = true;
    mat.roughness = .55;
    mat.envMapIntensity = .5;
    mat.onBeforeCompile = shader => {
      shader.uniforms.printAtlas = { value: atlas };
      shader.uniforms.exposure = exposure;
      shader.fragmentShader = shader.fragmentShader
        .replace("#include <common>", "#include <common>\nuniform sampler2D printAtlas; uniform float exposure;")
        .replace("#include <map_fragment>", `#include <map_fragment>
          vec2 printUV=(vMapUv-vec2(504.0/1460.0,30.0/242.0))/vec2(450.0/1460.0,182.0/242.0);
          if(all(greaterThanEqual(printUV,vec2(0.0))) && all(lessThanEqual(printUV,vec2(1.0)))) {
            vec2 atlasUV=vec2((exposure+clamp(printUV.x,.002,.998))/8.0,clamp(printUV.y,.002,.998));
            diffuseColor.rgb=diffuse*texture2D(printAtlas,atlasUV).rgb;
          }`);
    };
    mat.customProgramCacheKey = () => "contact-printer";
    mesh.material = mat;
  });
  return ({ time, scroll, reduced }) => {
    const tilt = reduced ? 0 : .085 * Math.sin(time * .65 + scroll * 2);
    const advance = reduced ? 0 : .34 * (scroll - .5) + .08 * Math.sin(time * .8);
    for (const part of [negative, emulsion]) {
      part.rotate(xAxis, tilt); part.lift(0, advance);
    }
    const frame = reduced ? 0 : Math.floor(scroll * 7 + time * 1.35) % 8;
    exposure.value = frame;
  };
}

export function createMotion(name, root) {
  const camera = structuredClone(cameras[name] || spliceCamera);
  if (!name.startsWith("splice-")) finishSurfaces(root);
  let update;
  if (name.startsWith("splice-")) {
    const meshes = [];
    root.traverse(part => {
      if (part.morphTargetDictionary?.Flex !== undefined) meshes.push(part);
    });
    update = ({ time, scroll, reduced }) => meshes.forEach(part => {
      part.morphTargetInfluences[part.morphTargetDictionary.Flex] = reduced ? 0 : .45 + .36 * Math.sin(time * .85 + scroll * 3);
    });
  } else if (name === "recorder") update = recorder(root, camera);
  else if (name === "burnos") update = waveform(root);
  else if (name === "plates" || name === "mnemosyne") update = stack(root, name === "plates");
  else if (name === "patch") update = patchbay(root);
  else if (name === "contact") update = exposureStrip(root);
  else if (name === "mnemetric") {
    const gauges = Array.from({ length: 6 }, (_, i) => joint(root, "Gauge" + String(i + 1).padStart(2, "0")));
    update = ({ time, scroll, reduced }) => gauges.forEach((part, i) => {
      part.stretch(reduced ? 1 : .91 + .13 * Math.sin(time * 1.3 - i * .7 + scroll * 2));
    });
  } else if (name === "spool") {
    const reel = joint(root, "Reel");
    update = ({ time, scroll, reduced }) => reel.rotate(yAxis, reduced ? 0 : time * .64 + scroll * 1.35);
  } else if (name === "gate") {
    const film = joint(root, "FilmAdvance");
    update = ({ time, scroll, reduced }) => {
      const beat = time * .56 + scroll * 1.3;
      const cycle = [0, 1, 0, -1];
      const i = Math.floor(beat) % cycle.length;
      const advance = cycle[i] + (cycle[(i + 1) % 4] - cycle[i]) * smooth((beat % 1 - .32) / .55);
      film.lift(0, reduced ? 0 : advance * 2.34);
    };
  } else throw new Error("Unknown sculpture " + name);
  return { camera, update };
}
