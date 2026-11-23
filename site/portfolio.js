function setupSectionLinks() {
  if (!("IntersectionObserver" in window)) return;

  const links = [...document.querySelectorAll("nav a")];
  const sections = links.map((link) => document.getElementById(link.hash.slice(1)));
  const visible = new Set();
  let footerVisible = false;
  let active;
  function markCurrent() {
    const section = footerVisible ? sections.at(-1) : sections.findLast(item => visible.has(item));
    if (active === section) return;
    active = section;
    links.forEach((link, index) => {
      if (sections[index] === active) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    });
  }
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) visible.add(entry.target);
      else visible.delete(entry.target);
    }
    markCurrent();
  }, { rootMargin: "-39% 0px -59% 0px" });
  sections.forEach(section => observer.observe(section));
  new IntersectionObserver(([entry]) => {
    footerVisible = entry.isIntersecting;
    markCurrent();
  }).observe(document.querySelector(".site-footer"));
}

function createPlayer({ title, url, allow }) {
  const player = document.createElement("iframe");
  player.title = title;
  player.src = url;
  player.allow = allow;
  player.referrerPolicy = "strict-origin-when-cross-origin";
  return player;
}

function createYouTubePlayer(videoId, title) {
  return createPlayer({
    title,
    url: `https://www.youtube-nocookie.com/embed/${videoId}?autoplay=1&playsinline=1`,
    allow: "autoplay; encrypted-media; picture-in-picture; fullscreen",
  });
}

function setupSoundtrack() {
  const trigger = document.querySelector(".sound-trigger");
  const soundtrack = document.getElementById("soundtrack");
  const close = document.getElementById("close-soundtrack");
  const mount = document.getElementById("soundtrack-player");
  const spotifyOrigin = "https://open.spotify.com";
  let frame;
  let playbackListeners;

  function stopSoundtrack() {
    playbackListeners?.abort();
    mount.replaceChildren();
    frame = undefined;
    soundtrack.classList.remove("is-playing");
  }

  function openPlayer() {
    const playback = new AbortController();
    const retry = new AbortController();
    playbackListeners = playback;
    playback.signal.addEventListener("abort", () => retry.abort(), { once: true });

    const player = createPlayer({
      title: "Spotify player: Lose You by Drake",
      url: `${spotifyOrigin}/embed/track/2Na0z2gfN67Rzf0vp74Wi3?theme=0&utm_source=iframe-api`,
      allow: "autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture",
    });
    let ready = false;
    let autoplayPending = true;

    function play() {
      player.contentWindow?.postMessage({ command: "play" }, spotifyOrigin);
    }

    function tryAutoplay() {
      if (!ready || !autoplayPending || document.hidden) return;
      autoplayPending = false;
      play();
    }

    window.addEventListener("message", (event) => {
      if (event.origin !== spotifyOrigin || event.source !== player.contentWindow) return;

      if (event.data?.type === "ready" && !ready) {
        ready = true;
        event.source.postMessage({ command: "load_complete_ack" }, spotifyOrigin);
        tryAutoplay();
      }
      if (event.data?.type === "playback_update") {
        const state = event.data.payload;
        if (state?.isPaused === true) soundtrack.classList.remove("is-playing");
        if (state?.isPaused === false && !state.isBuffering && state.position > 0 && state.duration > 0) {
          soundtrack.classList.add("is-playing");
          retry.abort();
        }
      }
    }, { signal: playback.signal });
    document.addEventListener("visibilitychange", tryAutoplay, { signal: playback.signal });

    document.addEventListener("click", (event) => {
      if (!event.isTrusted || !ready || document.hidden || !(event.target instanceof Element)) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      if (event.target.closest(".sound-trigger, #soundtrack, [data-video], dialog, a[href]:not([href^='#'])")) return;
      retry.abort();
      play();
    }, { signal: retry.signal });

    mount.append(player);
    frame = player;
  }

  // Give the first screen the network and main thread before starting Spotify.
  // Opening the dock by hand should always load the player immediately.
  const pendingLoad = new AbortController();
  function loadOnArrival() {
    if (document.hidden || pendingLoad.signal.aborted) return;
    pendingLoad.abort();
    openPlayer();
  }

  function schedulePlayer() {
    const signal = pendingLoad.signal;
    function afterLoad() {
      if (signal.aborted) return;
      if ("requestIdleCallback" in window) {
        window.requestIdleCallback(loadOnArrival, { timeout: 300 });
      } else {
        setTimeout(loadOnArrival, 0);
      }
    }
    if (document.readyState === "complete") afterLoad();
    else window.addEventListener("load", afterLoad, { once: true, signal });
    document.addEventListener("visibilitychange", () => {
      if (document.readyState === "complete") loadOnArrival();
    }, { signal });
  }

  function setOpen(open, moveFocus = true) {
    soundtrack.hidden = !open;
    trigger.setAttribute("aria-expanded", String(open));
    pendingLoad.abort();
    if (open && !frame) openPlayer();
    if (!open) stopSoundtrack();
    if (moveFocus) (open ? close : trigger).focus({ preventScroll: true });
  }

  trigger.hidden = false;
  soundtrack.hidden = false;
  trigger.setAttribute("aria-expanded", "true");
  schedulePlayer();
  trigger.addEventListener("click", () => setOpen(soundtrack.hidden));
  close.addEventListener("click", () => setOpen(false));
  soundtrack.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setOpen(false);
  });

  return () => setOpen(false, false);
}

function setupMedia() {
  const stopSoundtrack = setupSoundtrack();
  const videoDialog = document.getElementById("video-dialog");
  const videoPlayer = document.getElementById("video-player");
  const videoTitle = document.getElementById("video-title");
  const videoSource = document.getElementById("video-source");
  let activeVideoLink;

  if (typeof videoDialog.showModal !== "function") return;
  document.getElementById("videos").addEventListener("click", (event) => {
    const link = event.target.closest("a[data-video]");
    if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return;

    event.preventDefault();
    const videoId = new URL(link.href).searchParams.get("v");
    const label = document.getElementById(link.getAttribute("aria-labelledby"));
    activeVideoLink = link;
    videoTitle.textContent = label.textContent;
    videoSource.href = link.href;
    stopSoundtrack();
    videoDialog.showModal();
    videoPlayer.append(createYouTubePlayer(videoId, videoTitle.textContent));
  });
  videoDialog.addEventListener("close", () => {
    videoPlayer.replaceChildren();
    activeVideoLink.focus({ preventScroll: true });
  });
}

function setupRecorder() {
  const stage = document.getElementById("recorder-stage");
  const art = stage.querySelector(".model-art");
  const hint = document.querySelector(".model-hint");
  const controls = document.querySelector(".turn-controls");
  const angle = controls.querySelector(".angle");
  const assembly = controls.querySelector(".assembly-toggle");
  const frames = new Map();
  const viewCount = 36;
  let visibleView = 0;
  let requestedView = 0;
  let visibleExploded = false;
  let exploded = false;
  let visibleImage;
  let loading = false;
  let drag;

  function wrap(view) {
    return (view % viewCount + viewCount) % viewCount;
  }

  function loadView(view, separate) {
    const key = (separate ? "open-" : "view-") + String(view).padStart(2, "0");
    if (frames.has(key)) return frames.get(key);
    const image = new Image(660, 495);
    image.className = "turn-frame";
    image.alt = "";
    image.draggable = false;
    image.src = "assets/studio/recorder/" + key + ".webp";
    const decoded = image.decode().then(() => image).catch((error) => {
      frames.delete(key);
      throw error;
    });
    frames.set(key, decoded);
    if (frames.size > 8) frames.delete(frames.keys().next().value);
    return decoded;
  }

  function display(view, separate, image) {
    const assemblyChanged = separate !== visibleExploded;
    if (visibleImage !== image) {
      visibleImage?.remove();
      if (image) art.append(image);
      visibleImage = image;
    }
    if (assemblyChanged && image && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
      image.animate([{ opacity: .35 }, { opacity: 1 }], { duration: 180, easing: "ease-out" });
    }
    visibleView = view;
    visibleExploded = separate;
    assembly.setAttribute("aria-pressed", String(separate));
    angle.textContent = String(view * 10).padStart(3, "0") + "°";
    stage.setAttribute("aria-valuenow", String(view * 10));
    stage.setAttribute("aria-valuetext", view * 10 + " degrees");
  }

  async function draw() {
    if (loading) return;
    loading = true;
    try {
      while (visibleView !== requestedView || exploded !== visibleExploded) {
        const view = requestedView;
        const separate = exploded;
        const image = !separate && view === 0 ? undefined : await loadView(view, separate);
        if (view === requestedView && separate === exploded) display(view, separate, image);
      }
      // Warm just the adjacent angles after an interaction.
      for (const next of [wrap(visibleView - 1), wrap(visibleView + 1)]) {
        if (next || exploded) loadView(next, exploded).catch(() => {});
      }
    } catch {
      requestedView = visibleView;
      exploded = visibleExploded;
      hint.textContent = "Couldn’t load view. Try again.";
    } finally {
      loading = false;
    }
  }

  function turn(view) {
    requestedView = wrap(view);
    hint.textContent = "Drag to rotate";
    if (requestedView === 0 && !exploded) display(0, false);
    void draw();
  }

  stage.classList.add("is-interactive");
  stage.tabIndex = 0;
  stage.setAttribute("role", "slider");
  stage.setAttribute("aria-label", "Field recorder rotation");
  stage.setAttribute("aria-describedby", "model-hint");
  stage.setAttribute("aria-valuemin", "0");
  stage.setAttribute("aria-valuemax", "350");
  stage.setAttribute("aria-valuenow", "0");
  stage.setAttribute("aria-valuetext", "0 degrees");
  controls.hidden = false;
  hint.hidden = false;

  assembly.addEventListener("click", () => {
    exploded = !exploded;
    turn(requestedView);
  });
  controls.addEventListener("click", (event) => {
    const button = event.target.closest("[data-turn]");
    if (button) turn(requestedView + 3 * Number(button.dataset.turn));
  });
  stage.addEventListener("keydown", (event) => {
    const keys = { ArrowLeft: requestedView - 1, ArrowDown: requestedView - 1,
      ArrowRight: requestedView + 1, ArrowUp: requestedView + 1, Home: 0, End: viewCount - 1 };
    if (!Object.hasOwn(keys, event.key)) return;
    event.preventDefault();
    turn(keys[event.key]);
  });
  stage.addEventListener("pointerdown", (event) => {
    if (!event.isPrimary || event.button !== 0) return;
    drag = { id: event.pointerId, x: event.clientX, y: event.clientY, view: requestedView };
    stage.setPointerCapture(event.pointerId);
  });
  stage.addEventListener("pointermove", (event) => {
    if (event.pointerId !== drag?.id) return;
    const dx = event.clientX - drag.x;
    if (Math.abs(dx) < 6 || Math.abs(dx) < Math.abs(event.clientY - drag.y)) return;
    stage.classList.add("is-dragging");
    const next = wrap(drag.view + Math.round(dx / 12));
    if (next !== requestedView) turn(next);
  });
  stage.addEventListener("lostpointercapture", () => {
    drag = undefined;
    stage.classList.remove("is-dragging");
  });
}

setupMedia();
setupSectionLinks();
setupRecorder();
