// Keep the page and the recorder poster usable while the studio engine loads.
const toggle = document.querySelector("[data-motion-toggle]");
const recorder = document.querySelector("#recorder-stage");
const reduced = matchMedia("(prefers-reduced-motion: reduce)");
const limited = () => reduced.matches || navigator.connection?.saveData === true;
let loading;
let intent;

function activate() {
  if (loading) return loading;
  loading = import("./assets/engine/spatial.js").then(() => {
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
  }).catch(() => { if (toggle) toggle.hidden = true; });
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
} else if ("requestIdleCallback" in window) {
  requestIdleCallback(activate, { timeout: 850 });
} else {
  setTimeout(activate, 150);
}
