// HTML links provide both routes until the reversible jacket is ready.
const sleeve = document.querySelector("[data-sleeve]");
if (sleeve) {
  const picker = sleeve.querySelector(".sleeve-picker");
  const path = sleeve.querySelector("[data-sleeve-path]");
  const jacket = sleeve.querySelector(".sleeve-jacket");
  const tabs = [...picker.querySelectorAll("[data-side]")];
  const media = matchMedia("(prefers-reduced-motion: reduce)");
  let selected = 0;
  let transition;

  function select(index, animate = false) {
    const forward = index > selected;
    selected = index;
    tabs.forEach((tab, i) => {
      const panel = document.getElementById(tab.getAttribute("aria-controls"));
      panel.hidden = i !== index;
      tab.tabIndex = i === index ? 0 : -1;
      tab.setAttribute("aria-selected", String(i === index));
    });
    path.href = tabs[index].getAttribute("href");
    path.firstChild.textContent = index === 0 ? "Explore software " : "Browse interviews ";
    transition?.cancel();
    const motionPaused = document.querySelector("[data-motion-toggle]")?.getAttribute("aria-pressed") === "true";
    if (animate && !media.matches && !motionPaused && jacket.animate) {
      transition = jacket.animate([
        { transform: "rotateY(" + (forward ? "-8deg" : "8deg") + ") translateY(2px)", opacity: .83 },
        { transform: "rotateY(0) translateY(0)", opacity: 1 },
      ], { duration: 280, easing: "cubic-bezier(.2,.75,.24,1)" });
    }
  }

  picker.setAttribute("role", "tablist");
  tabs.forEach((tab, index) => {
    const panel = document.getElementById("sleeve-face-" + tab.dataset.side);
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-controls", panel.id);
    panel.setAttribute("role", "tabpanel");
    panel.setAttribute("aria-labelledby", tab.id);
    tab.addEventListener("click", event => {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      if (selected !== index) select(index, true);
    });
    tab.addEventListener("keydown", event => {
      const order = { ArrowRight: (index + 1) % tabs.length, ArrowLeft: (index + tabs.length - 1) % tabs.length, Home: 0, End: tabs.length - 1 };
      if (event.key === " ") { event.preventDefault(); select(index, index !== selected); return; }
      if (!(event.key in order)) return;
      event.preventDefault();
      select(order[event.key], order[event.key] !== index);
      tabs[selected].focus();
    });
  });
  select(0);
}
