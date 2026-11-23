import * as THREE from "three";
import { HDRLoader } from "three/addons/loaders/HDRLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

// The photographed softboxes supply highlights to glass, paint and metal. A
// window-side key gives those same forms a single, legible cast shadow.
export const loadStudioLight = () => new HDRLoader().loadAsync("/assets/engine/studio-light.hdr");

export function reflectStudio(renderer, photograph) {
  const generator = new THREE.PMREMGenerator(renderer);
  try {
    if (photograph) return generator.fromEquirectangular(photograph);
    const fallback = new RoomEnvironment();
    try { return generator.fromScene(fallback, .04); }
    finally { fallback.dispose(); }
  } finally { generator.dispose(); }
}

// A broad key lights the paper around elevated parts while the feet still
// leave dark contact. Reuse the depth moments from the key's real shadow
// map. Perturb only the floor lookup; the instrument retains its fine relief.
function paperReceiver() {
  const material = new THREE.ShadowMaterial({ color: 0x3e342a, opacity: .31, depthWrite: false, toneMapped: false });
  material.onBeforeCompile = shader => {
    shader.fragmentShader = shader.fragmentShader.replace("#include <tonemapping_fragment>", `
      #if defined(SHADOWMAP_TYPE_VSM) && NUM_DIR_LIGHT_SHADOWS > 0
        vec3 floorCoord = vDirectionalShadowCoord[0].xyz / vDirectionalShadowCoord[0].w;
        vec2 uv = floorCoord.xy;
        float dz = max(0.0, floorCoord.z - texture2D(directionalShadowMap[0], uv).r);
        // Smooth the widening penumbra around elevated objects. Neighboring
        // comparisons adjust for the floor's tilt relative to the light.
        vec3 dx = dFdx(floorCoord), dy = dFdy(floorCoord);
        float det = dx.x * dy.y - dx.y * dy.x;
        vec2 slope = abs(det) > 1e-10 ? vec2(dy.y * dx.z - dx.y * dy.z, dx.x * dy.z - dy.x * dx.z) / det : vec2(0.0);
        float width = 0.006;
        for (int i = 0; i < 4; ++i) {
          float a = (float(i) + .5) * 1.5707963;
          vec2 offset = vec2(cos(a), sin(a)) * .019;
          float depth = texture2D(directionalShadowMap[0], uv + offset).r;
          dz = max(dz, floorCoord.z + dot(slope, offset) - depth);
        }
        width += min(.046, dz * .39);
        float shade = 0.0;
        for (int i = 0; i < 12; ++i) {
          float ring = (float(i) + .5) / 12.0;
          float a = float(i) * 2.3999632;
          vec2 offset = width * sqrt(ring) * vec2(cos(a), sin(a));
          vec2 moments = texture2D(directionalShadowMap[0], uv + offset).rg;
          float separation = max(0.0, floorCoord.z + dot(slope, offset) - moments.r - .00065);
          float variance = max(.0000001, moments.g * moments.g);
          float visibility = variance / (variance + separation * separation);
          float fill = mix(1.0, .55, smoothstep(.012, .12, separation));
          shade += (1.0 - smoothstep(.22, .98, visibility)) * fill;
        }
        // A floor may extend past the light camera. A clamped edge texel
        // outside that frustum has no physical blocker to project.
        vec3 border = min(floorCoord, 1.0 - floorCoord);
        float coverage = smoothstep(width, width + .014, min(border.x, border.y)) * smoothstep(.004, .018, border.z);
        gl_FragColor.a = coverage * opacity * (shade / 12.0);
      #endif
      #include <tonemapping_fragment>
    `);
  };
  return material;
}

export function lightSculpture(root, name) {
  const scene = new THREE.Scene();
  scene.add(root);
  scene.environmentIntensity = 1.15;
  scene.environmentRotation.y = -.5;
  scene.add(new THREE.HemisphereLight(0xfff1dc, 0x727782, .20));
  const key = new THREE.DirectionalLight(0xffead3, .85);
  key.position.set(-2.4, 8, 3.2);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0xe5edff, .35);
  rim.position.set(4, 3, -3);
  scene.add(rim);

  // The inter-section ribbons and contact print hang in free space.
  if (name.startsWith("splice-") || name === "contact") return { scene, shadow: null };

  // Quantized exports have translated/rotated child nodes. Measuring their
  // actual world vertices once locates the receiver where the lowest foot,
  // plate or spindle touches the table, including new versions of the model.
  const bounds = new THREE.Box3().setFromObject(root, true);
  const center = bounds.getCenter(new THREE.Vector3());
  const size = bounds.getSize(new THREE.Vector3());
  const span = Math.hypot(size.x, size.z);
  const extent = Math.max(span * .60, size.y * .85) + (name === "recorder" ? 1 : .45);
  root.traverse(mesh => {
    if (!mesh.isMesh) return;
    const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    mesh.castShadow = mats.some(mat => !(mat.transparent && mat.alphaTest === 0) && !(mat.transmission > .65));
    mesh.receiveShadow = true;
  });

  key.castShadow = true;
  key.position.normalize().multiplyScalar(extent * 3).add(center);
  key.target.position.copy(center);
  scene.add(key.target);
  const shadow = key.shadow;
  const camera = shadow.camera;
  camera.left = camera.bottom = -extent;
  camera.right = camera.top = extent;
  camera.near = Math.max(.04, extent * .3);
  camera.far = extent * 5;
  camera.updateProjectionMatrix();
  shadow.normalBias = Math.max(.0015, extent * .0008);
  shadow.bias = -.00023;
  shadow.autoUpdate = false;
  shadow.needsUpdate = true;

  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(size.x + size.y * 3 + 2, size.z + size.y * 3 + 2),
    paperReceiver(),
  );
  floor.name = "Studio shadow receiver";
  floor.rotateX(-Math.PI / 2);
  floor.position.set(center.x, bounds.min.y - extent * .00035, center.z);
  floor.receiveShadow = true;
  scene.add(floor);
  return { scene, shadow };
}
