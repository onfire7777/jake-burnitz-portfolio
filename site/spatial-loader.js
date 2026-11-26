// Keep the page and the recorder poster usable while the studio engine loads.
const toggle = document.querySelector("[data-motion-toggle]");
const recorder = document.querySelector("#recorder-stage");
const reduced = matchMedia("(prefers-reduced-motion: reduce)");
const limited = () => reduced.matches || navigator.connection?.saveData === true;
let loading;
let intent;

function restoreImageLayers(root) {
  for (const template of root.querySelectorAll("template[data-fallback-art]")) {
    template.parentElement.querySelector(".studio-still")?.remove();
    template.replaceWith(template.content);
  }
}
document.addEventListener("studio-image-fallback", event => restoreImageLayers(event.target));

function loadRenderer() {
  if (location.protocol !== "file:") return import("./assets/engine/spatial.js");
  // Browsers can load a classic sibling script from disk. The file build
  // includes the same meshes and studio photograph, without cross-file fetches.
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "file-preview/spatial.js";
    script.onload = resolve;
    script.onerror = reject;
    document.head.append(script);
  });
}

function activate() {
  if (loading) return loading;
  loading = loadRenderer().then(() => {
    toggle?.removeEventListener("click", optIn);
    recorder?.removeEventListener("recorder-view", useRecorder);
    reduced.removeEventListener("change", onPreference);
    if (intent === "opt-in" && toggle?.getAttribute("aria-pressed") === "true") toggle.click();
    if (intent === "recorder") recorder.dispatchEvent(new CustomEvent("recorder-view", {
      detail: {
        angle: Number(recorder.getAttribute("aria-valuenow")) || 0,
        exploded: document.querySelector(".assembly-toggle")?.getAttribute("aria-pressed") === "true",
      },
    }));
  }).catch(() => {
    if (toggle) toggle.hidden = true;
    restoreImageLayers(document);
  });
  return loading;
}
function optIn() { intent = "opt-in"; activate(); }
function useRecorder() { intent = "recorder"; activate(); }
function onPreference() { if (!limited()) activate(); }
if (toggle && limited()) {
  toggle.hidden = false;
  toggle.setAttribute("aria-pressed", "true");
  toggle.setAttribute("aria-label", "Resume 3D motion");
  toggle.querySelector("[data-motion-label]").textContent = "Resume 3D motion";
  toggle.addEventListener("click", optIn);
  recorder?.addEventListener("recorder-view", useRecorder);
  reduced.addEventListener("change", onPreference);
  // The illustrated patch panel can highlight sockets even on a still page.
  const links = document.querySelector(".link-grid");
  function useIllustratedPatch() {
    const patch = document.querySelector(".patch-art");
    if (limited() && patch && !patch.classList.contains("has-live-model")) restoreImageLayers(patch);
  }
  links?.addEventListener("pointerover", useIllustratedPatch, { once: true });
  links?.addEventListener("focusin", useIllustratedPatch, { once: true });
} else if ("requestIdleCallback" in window) {
  requestIdleCallback(activate, { timeout: 850 });
} else {
  setTimeout(activate, 150);
}
