const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");

function setupReveals() {
  if (reducedMotion.matches || !("IntersectionObserver" in window)) return;

  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      entry.target.classList.add("arrived");
      observer.unobserve(entry.target);
    }
  }, { rootMargin: "0px 0px -12px 0px" });

  for (const item of document.querySelectorAll(".reveal")) {
    observer.observe(item);
  }
}

function setupSectionLinks() {
  if (!("IntersectionObserver" in window)) return;

  const links = [...document.querySelectorAll("nav a")];
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      const link = links.find((item) => item.hash === "#" + entry.target.id);
      if (!link) continue;
      if (entry.isIntersecting) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    }
  }, { rootMargin: "-22% 0px -52% 0px" });

  for (const link of links) {
    const section = document.getElementById(link.hash.slice(1));
    if (section) observer.observe(section);
  }
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

setupMedia();
setupReveals();
setupSectionLinks();
