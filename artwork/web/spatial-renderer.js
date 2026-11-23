import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { loadStudioLight, reflectStudio, lightSculpture } from "./studio-lighting.js";
import { createMotion } from "./spatial-motion.js";

const MAX_FRAME_RATE = 30;
const clamp = value => Math.max(0, Math.min(1, value));

// One drawing buffer supplies every visible sculpture. Each element keeps its
// own display canvas so the browser clips and transforms it with the page.
function makeEngine(photograph, onLost, onRestored) {
  const options = { antialias: true, alpha: true, powerPreference: "low-power" };
  let renderer;
  if (typeof OffscreenCanvas !== "undefined" && OffscreenCanvas.prototype.transferToImageBitmap) {
    try {
      renderer = new THREE.WebGLRenderer({ ...options, canvas: new OffscreenCanvas(1, 1) });
    } catch { /* Some browsers only expose WebGL2 on a document canvas. */ }
  }
  renderer ??= new THREE.WebGLRenderer(options);
  renderer.setClearColor(0x000000, 0);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.VSMShadowMap;

  const source = renderer.domElement;
  let environment;
  try {
    environment = reflectStudio(renderer, photograph);
  } catch (error) {
    renderer.dispose();
    renderer.forceContextLoss();
    throw error;
  }
  let lost = false;
  function lose(event) {
    event.preventDefault();
    lost = true;
    onLost();
  }
  function restore() {
    environment.dispose();
    environment = reflectStudio(renderer, photograph);
    lost = false;
    onRestored();
  }
  source.addEventListener("webglcontextlost", lose);
  source.addEventListener("webglcontextrestored", restore);

  return {
    renderer, source,
    get lost() { return lost; },
    get environment() { return environment.texture; },
    dispose() {
      source.removeEventListener("webglcontextlost", lose);
      source.removeEventListener("webglcontextrestored", restore);
      environment.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
    },
  };
}

export function startSpatialRenderer() {
  const mounts = [...document.querySelectorAll("[data-model]")];
  if (!mounts.length) return;
  if (!("IntersectionObserver" in window) || !("ResizeObserver" in window)) {
    document.dispatchEvent(new Event("studio-image-fallback"));
    return;
  }
  const toggle = document.querySelector("[data-motion-toggle]");
  const label = toggle?.querySelector("[data-motion-label]");
  const recorder = document.querySelector("#recorder-stage");
  const preference = matchMedia("(prefers-reduced-motion: reduce)");
  const connection = navigator.connection;
  const loader = new GLTFLoader();
  const states = new Map(mounts.map(mount => [mount, {
    mount, name: mount.dataset.model, visible: false, dirty: true, time: 0, scroll: 0,
    lastDraw: 0, width: 0, height: 0, top: 0, travelHeight: 0, failed: false,
  }]));
  const recorderState = [...states.values()].find(state => state.name === "recorder");
  const patchState = [...states.values()].find(state => state.name === "patch");
  let engine, frame, unsupported = false, explicitMotion = null, recorderTouched = false;
  let lightLoad, photograph, lightReady = false;
  let viewportHeight = window.innerHeight, angle = 0, exploded = false, port = -1;
  let lastScroll = window.scrollY, scrollingUntil = 0;

  const constrained = () => preference.matches || connection?.saveData === true;
  let systemConstrained = constrained();
  const moving = () => explicitMotion ?? !constrained();
  const permitted = state => !constrained() || explicitMotion === true || (state === recorderState && recorderTouched);

  function showPreference() {
    if (!toggle) return;
    toggle.hidden = unsupported;
    toggle.setAttribute("aria-pressed", String(!moving()));
    const text = moving() ? "Pause 3D motion" : "Resume 3D motion";
    toggle.setAttribute("aria-label", text);
    if (label) label.textContent = text;
  }

  function schedule() {
    if (frame || document.hidden || unsupported || engine?.lost) return;
    frame = requestAnimationFrame(draw);
  }

  function readRecorder() {
    if (!recorder) return;
    angle = Number(recorder.getAttribute("aria-valuenow")) || 0;
    exploded = document.querySelector(".assembly-toggle")?.getAttribute("aria-pressed") === "true";
  }

  function prepare(state) {
    if (unsupported || state.scene || state.loading || state.failed || document.hidden || !permitted(state)) return;
    state.loading = true;
    if (!lightLoad) {
      lightLoad = loadStudioLight().then(texture => { photograph = texture; })
        .catch(() => { /* The procedural studio still lights the geometry offline. */ })
        .finally(() => { lightReady = true; schedule(); });
    }
    loader.loadAsync(`/assets/models/${encodeURIComponent(state.name)}.glb`).then(({ scene: root }) => {
      state.motion = createMotion(state.name, root);
      Object.assign(state, lightSculpture(root, state.name));
      state.camera = new THREE.OrthographicCamera(-1, 1, 1, -1, .01, 250);
      state.camera.position.fromArray(state.motion.camera.eye);
      state.camera.lookAt(...state.motion.camera.target);
      if (state === recorderState) readRecorder();
      state.dirty = true;
      schedule();
    }).catch(() => {
      state.failed = true;
      release(state, true);
      state.mount.dispatchEvent(new Event("studio-image-fallback", { bubbles: true }));
    }).finally(() => { state.loading = false; });
  }

  function measure(state) {
    const box = state.mount.getBoundingClientRect();
    const travel = state.mount.closest(".signal-track")?.getBoundingClientRect() ?? box;
    state.width = state.mount.clientWidth;
    state.height = state.mount.clientHeight;
    state.top = travel.top + window.scrollY;
    state.travelHeight = travel.height;
    state.dirty = true;
  }

  function release(state, restoreRecorder = false) {
    const wasLive = state.mount.classList.contains("has-live-model");
    state.mount.classList.remove("has-live-model");
    state.canvas?.remove();
    state.canvas = state.context = null;
    state.lastDraw = 0;
    state.lastShadow = 0;
    if (state === recorderState && recorder) {
      recorder.classList.remove("has-live-model");
      if (wasLive && restoreRecorder) recorder.dispatchEvent(new Event("recorder-fallback"));
    }
  }

  function makeSurface(state) {
    const canvas = document.createElement("canvas");
    canvas.className = "model-canvas";
    canvas.setAttribute("aria-hidden", "true");
    const bitmap = engine.source.transferToImageBitmap && canvas.getContext("bitmaprenderer");
    state.context = bitmap || canvas.getContext("2d", { alpha: true });
    if (!state.context) throw new Error("No presentation canvas");
    state.bitmap = Boolean(bitmap);
    state.canvas = canvas;
  }

  function paint(state, timestamp, crowded, scrolling) {
    if (!state.canvas) makeSurface(state);
    const { source, renderer } = engine;
    const { camera, motion } = state;
    const delta = moving() && state.lastDraw ? Math.min((timestamp - state.lastDraw) / 1000, .1) : 0;
    state.time += delta;
    if (moving() || !state.lastDraw) {
      state.scroll = clamp((window.scrollY + viewportHeight - state.top) / (viewportHeight + state.travelHeight));
    }
    if (moving()) state.hasAnimatedPose = true;
    const reduced = !moving() && constrained() && !state.hasAnimatedPose;
    motion.update({ time: state.time, scroll: state.scroll, delta, angle, exploded, port, reduced, instant: !moving() });
    camera.lookAt(...motion.camera.target);
    const width = motion.camera.width;
    const height = motion.camera.height ?? width * state.height / state.width;
    camera.left = -width / 2;
    camera.right = width / 2;
    camera.top = height / 2;
    camera.bottom = -height / 2;
    camera.updateProjectionMatrix();
    if (state.shadow) {
      if (!state.shadow.map) {
        const size = state.width >= 470 || state.name === "recorder" ? 1024 : 512;
        state.shadow.mapSize.set(size, size);
        state.shadow.radius = size === 1024 ? 11 : 5.5;
        state.shadow.blurSamples = 9;
      }
      // The camera can redraw without repeating every depth pass. Keep shadows
      // closer to a hand-driven turn or patch change than a slow idle gesture.
      const interval = state.manualUntil > timestamp ? 1000 / 24 : (scrolling ? 190 : (crowded ? 125 : 85));
      if (state.dirty || !state.lastShadow || timestamp - state.lastShadow >= interval) {
        state.shadow.needsUpdate = true;
        state.lastShadow = timestamp;
      }
    }
    state.scene.environment = engine.environment;
    renderer.render(state.scene, camera);
    if (engine.lost) return;
    const canvas = state.canvas;
    if (canvas.width !== source.width || canvas.height !== source.height) {
      canvas.width = source.width;
      canvas.height = source.height;
    }
    if (state.bitmap) {
      state.context.transferFromImageBitmap(source.transferToImageBitmap());
    } else {
      state.context.globalCompositeOperation = "copy";
      state.context.drawImage(source, 0, 0);
    }
    if (!canvas.isConnected) {
      state.mount.append(canvas);
      state.mount.classList.add("has-live-model");
      if (state === recorderState) recorder?.classList.add("has-live-model");
    }
    state.lastDraw = timestamp;
    state.dirty = false;
  }

  function draw(timestamp) {
    frame = 0;
    const visible = [...states.values()].filter(state =>
      state.visible && state.scene && !state.failed && state.width && state.height && permitted(state));
    if (!visible.length || !lightReady || document.hidden || unsupported || engine?.lost) return;
    if (!engine) {
      try {
        engine = makeEngine(
          photograph,
          () => states.forEach(state => release(state, true)),
          () => { states.forEach(state => { state.dirty = true; }); schedule(); },
        );
      } catch {
        unsupported = true;
        showPreference();
        document.dispatchEvent(new Event("studio-image-fallback"));
        return;
      }
    }
    // A hero or large gallery object gets Retina detail. A row of small
    // instruments shares a lighter buffer. A long, narrow tape crossing does
    // not force its adjacent sculpture or every project card to render at 4K.
    const physical = visible.filter(s => s.shadow);
    const subjects = physical.length ? physical : visible;
    const crowded = physical.length > 1;
    const hero = !crowded && physical.some(s => s.width >= 460);
    const density = Math.min(devicePixelRatio || 1, hero ? 2 : (crowded ? 1.35 : 1.6));
    const size = (dimension, limit) => Math.ceil(Math.min(limit, Math.max(...subjects.map(s => s[dimension])) * density) / 64) * 64;
    const width = size("width", hero ? 1408 : (crowded ? 896 : 1280));
    const height = size("height", hero ? 960 : (crowded ? 640 : 704));
    if (engine.source.width !== width || engine.source.height !== height) engine.renderer.setSize(width, height, false);
    const position = window.scrollY;
    if (Math.abs(position - lastScroll) > 1) scrollingUntil = timestamp + 145;
    lastScroll = position;
    const scrolling = timestamp < scrollingUntil;
    const interval = 1000 / (scrolling ? 24 : MAX_FRAME_RATE) - 1;
    // Distribute expensive instruments across display frames as a gallery
    // row enters view. The newest explicitly manipulated pose takes priority.
    let renderedInstrument = false;
    visible.sort((a, b) => Number(b.manualUntil > timestamp) - Number(a.manualUntil > timestamp) || a.lastDraw - b.lastDraw);
    for (const state of visible) {
      if (!state.dirty && (!moving() || timestamp - state.lastDraw < interval)) continue;
      if (scrolling && crowded && state.shadow && renderedInstrument && moving()) continue;
      if (state.shadow) renderedInstrument = true;
      try { paint(state, timestamp, crowded, scrolling); } catch {
        if (engine?.lost) return;
        state.failed = true;
        release(state, true);
        state.mount.dispatchEvent(new Event("studio-image-fallback", { bubbles: true }));
      }
    }
    if (moving() && visible.some(state => !state.failed)) schedule();
  }

  const visibility = new IntersectionObserver(entries => {
    for (const entry of entries) {
      const state = states.get(entry.target);
      state.visible = entry.isIntersecting && entry.intersectionRatio >= .01;
      if (!state.visible) { release(state); continue; }
      measure(state);
      prepare(state);
    }
    schedule();
  }, { threshold: [0, .01] });
  const resize = new ResizeObserver(entries => {
    viewportHeight = window.innerHeight;
    for (const entry of entries) measure(states.get(entry.target));
    schedule();
  });
  for (const mount of mounts) { resize.observe(mount); visibility.observe(mount); }
  window.addEventListener("resize", () => {
    viewportHeight = window.innerHeight;
    for (const state of states.values()) if (state.visible) measure(state);
    schedule();
  });

  function applyPreference() {
    showPreference();
    for (const state of states.values()) {
      if (!permitted(state)) { release(state, true); continue; }
      state.dirty = true;
      if (state.visible) prepare(state);
    }
    schedule();
  }
  toggle?.addEventListener("click", () => { explicitMotion = !moving(); applyPreference(); });
  function systemPreferenceChanged() {
    const next = constrained();
    if (next === systemConstrained) return;
    systemConstrained = next;
    explicitMotion = null;
    recorderTouched = false;
    states.forEach(state => { state.hasAnimatedPose = false; });
    applyPreference();
  }
  preference.addEventListener("change", systemPreferenceChanged);
  connection?.addEventListener("change", systemPreferenceChanged);

  recorder?.addEventListener("recorder-view", ({ detail }) => {
    if (!recorderState) return;
    angle = detail.angle;
    exploded = detail.exploded;
    recorderTouched = true;
    recorderState.dirty = true;
    recorderState.manualUntil = performance.now() + 540;
    if (recorderState.visible) prepare(recorderState);
    schedule();
  });

  const grid = document.querySelector(".link-grid");
  if (grid && patchState) {
    const links = [...grid.querySelectorAll(".profile-link")];
    const index = element => links.indexOf(element?.closest?.(".profile-link"));
    let hover = -1, focus = -1;
    function highlight() {
      port = focus >= 0 ? focus : hover;
      patchState.dirty = true;
      patchState.manualUntil = performance.now() + 540;
      schedule();
    }
    grid.addEventListener("pointerover", e => { hover = index(e.target); highlight(); });
    grid.addEventListener("pointerout", e => { hover = index(e.relatedTarget); highlight(); });
    grid.addEventListener("focusin", e => { focus = index(e.target); highlight(); });
    grid.addEventListener("focusout", e => { focus = index(e.relatedTarget); highlight(); });
  }

  function sleep() {
    cancelAnimationFrame(frame);
    frame = 0;
    states.forEach(state => release(state));
    engine?.dispose();
    engine = null;
  }
  function wake() {
    for (const state of states.values()) if (state.visible) {
      measure(state);
      prepare(state);
    }
    schedule();
  }
  document.addEventListener("visibilitychange", () => { if (document.hidden) sleep(); else wake(); });
  window.addEventListener("pagehide", sleep);
  window.addEventListener("pageshow", wake);
  showPreference();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", startSpatialRenderer, { once: true });
} else {
  startSpatialRenderer();
}
