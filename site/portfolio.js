const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");

function setupReveals() {
  if (reducedMotion.matches || !("IntersectionObserver" in window)) return;

  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      entry.target.classList.replace("pending", "arrived");
      observer.unobserve(entry.target);
    }
  }, { rootMargin: "0px 0px -12px 0px" });

  for (const item of document.querySelectorAll(".reveal")) {
    item.classList.add("pending");
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
  player.allowFullscreen = true;
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
      if (event.data?.type === "playback_started") retry.abort();
      if (event.data?.type === "playback_update" && typeof event.data.payload?.isPaused === "boolean") {
        const playing = !event.data.payload.isPaused;
        soundtrack.classList.toggle("is-playing", playing);
        if (playing) retry.abort();
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

  function setOpen(open, moveFocus = true) {
    soundtrack.hidden = !open;
    trigger.setAttribute("aria-expanded", String(open));
    if (open && !frame) openPlayer();
    if (!open) stopSoundtrack();
    if (moveFocus) (open ? close : trigger).focus({ preventScroll: true });
  }

  trigger.hidden = false;
  setOpen(true, false);
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

function setupOrbit() {
  const canvas = document.getElementById("orbit");
  const context = canvas.getContext("2d");
  if (!context) return;

  const art = canvas.parentElement;
  const tau = 2 * Math.PI;
  const points = [];
  const colors = ["#b08362", "#af6d4b", "#6959a9", "#2b3fa9"];
  let bounds;
  let frame = 0;
  let visible = true;
  let pointerX = 0;
  let pointerY = 0;
  let tiltX = 0;
  let tiltY = 0;
  let elapsed = 0;
  let lastTime = 0;

  for (let ring = 0; ring < 15; ring++) {
    const v = ring / 15 * tau;
    for (let step = 0; step < 80; step++) {
      const u = (step + (ring % 2) * 0.5) / 80 * tau;
      const radius = 1 + 0.34 * Math.cos(v);
      points.push({
        x: radius * Math.cos(u),
        y: radius * Math.sin(u),
        z: 0.34 * Math.sin(v),
        u,
      });
    }
  }

  function render() {
    const { width, height } = bounds;
    const centerX = width * 0.5;
    const centerY = height * 0.5;
    const scale = Math.min(width, height) * 0.315;
    const spin = elapsed * 0.00019;
    const tilt = 0.91 + tiltY + Math.sin(elapsed * 0.00032) * 0.12;
    const slant = -0.48 + tiltX;
    const spinCos = Math.cos(spin);
    const spinSin = Math.sin(spin);
    const tiltCos = Math.cos(tilt);
    const tiltSin = Math.sin(tilt);
    const slantCos = Math.cos(slant);
    const slantSin = Math.sin(slant);

    context.clearRect(0, 0, width, height);
    context.save();
    context.translate(centerX, centerY);
    context.rotate(slant);
    context.strokeStyle = "#2b3fa95d";
    context.setLineDash([2, 6]);
    context.beginPath();
    context.ellipse(0, 0, scale * 1.5, scale * 0.86, 0, 0, tau);
    context.stroke();
    context.restore();

    const buckets = colors.map(() => []);
    for (const point of points) {
      const x = point.x * spinCos - point.y * spinSin;
      const originalY = point.x * spinSin + point.y * spinCos;
      const y = originalY * tiltCos - point.z * tiltSin;
      const z = originalY * tiltSin + point.z * tiltCos;
      const perspective = 3.9 / (3.9 - z);
      const light = (z + 1.4) / 2.8;
      const shimmer = Math.sin(point.u * 3 + spin * 3) * 0.10;
      const tone = Math.max(0, Math.min(colors.length - 1, Math.floor((light + shimmer) * colors.length)));
      buckets[tone].push({
        x: centerX + (x * slantCos - y * slantSin) * scale * perspective,
        y: centerY + (x * slantSin + y * slantCos) * scale * perspective,
        radius: (0.64 + tone * 0.12) * perspective,
      });
    }

    for (let layer = 0; layer < colors.length; layer++) {
      context.fillStyle = colors[layer];
      context.beginPath();
      for (const point of buckets[layer]) {
        context.moveTo(point.x + point.radius, point.y);
        context.arc(point.x, point.y, point.radius, 0, tau);
      }
      context.fill();
    }
  }

  function resize() {
    bounds = art.getBoundingClientRect();
    const ratio = Math.min(devicePixelRatio || 1, 2);
    canvas.width = Math.round(bounds.width * ratio);
    canvas.height = Math.round(bounds.height * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    if (bounds.width > 0 && bounds.height > 0) {
      render();
      art.classList.add("has-orbit");
    }
  }

  function tick(now) {
    elapsed += lastTime ? Math.min(now - lastTime, 35) : 0;
    lastTime = now;
    tiltX += (pointerX - tiltX) * 0.05;
    tiltY += (pointerY - tiltY) * 0.05;
    render();
    frame = requestAnimationFrame(tick);
  }

  function syncAnimation() {
    cancelAnimationFrame(frame);
    lastTime = 0;
    if (visible && !document.hidden && !reducedMotion.matches) {
      frame = requestAnimationFrame(tick);
      return;
    }
    if (reducedMotion.matches) {
      elapsed = tiltX = tiltY = 0;
      render();
    }
  }

  resize();
  if ("ResizeObserver" in window) new ResizeObserver(resize).observe(art);
  else window.addEventListener("resize", resize);

  if ("IntersectionObserver" in window) {
    new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      syncAnimation();
    }).observe(art);
  }

  art.addEventListener("pointermove", (event) => {
    if (event.pointerType === "touch" || reducedMotion.matches) return;
    const box = art.getBoundingClientRect();
    pointerX = ((event.clientX - box.left) / box.width - 0.5) * 0.32;
    pointerY = ((event.clientY - box.top) / box.height - 0.5) * 0.32;
  });
  art.addEventListener("pointerleave", () => {
    pointerX = pointerY = 0;
  });
  document.addEventListener("visibilitychange", syncAnimation);
  reducedMotion.addEventListener("change", syncAnimation);
  syncAnimation();
}

setupMedia();
setupReveals();
setupSectionLinks();
setupOrbit();
