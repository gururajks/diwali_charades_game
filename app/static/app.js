const INDUSTRY_KEY = "charades:industry";

const els = {
  industries: document.getElementById("industries"),
  name: document.getElementById("movie-name"),
  year: document.getElementById("movie-year"),
  unmute: document.getElementById("unmute"),
  meta: document.getElementById("meta"),
  next: document.getElementById("next"),
  hide: document.getElementById("hide"),
  cover: document.getElementById("cover"),
  reveal: document.getElementById("reveal"),
  era: document.getElementById("era"),
  clock: document.getElementById("clock"),
  duration: document.getElementById("duration"),
  timerToggle: document.getElementById("timer-toggle"),
};

let catalog = [];
let industry = localStorage.getItem(INDUSTRY_KEY) || "bollywood";

function seenKey() {
  return `charades:seen:${industry}`;
}

function loadSeen() {
  try {
    return JSON.parse(localStorage.getItem(seenKey())) || [];
  } catch {
    return [];
  }
}

function saveSeen(seen) {
  localStorage.setItem(seenKey(), JSON.stringify(seen));
}

function industryLabel() {
  return catalog.find((item) => item.id === industry)?.label || "";
}

function renderIndustries() {
  els.industries.replaceChildren(
    ...catalog.map((item) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "seg";
      btn.textContent = item.label;
      btn.dataset.industry = item.id;
      btn.setAttribute("aria-pressed", String(item.id === industry));
      btn.addEventListener("click", () => selectIndustry(item.id));
      return btn;
    }),
  );
}

function updateEraOptions() {
  const years = catalog.find((item) => item.id === industry)?.years || [];
  for (const option of els.era.options) {
    if (option.value === "all") continue;
    const [min, max] = option.value.split("-").map(Number);
    option.disabled = !years.some((year) => year >= min && year <= max);
  }
  if (els.era.selectedOptions[0]?.disabled) els.era.value = "all";
}

function selectIndustry(id) {
  if (id === industry) return;
  industry = id;
  localStorage.setItem(INDUSTRY_KEY, id);
  for (const btn of els.industries.children) {
    btn.setAttribute("aria-pressed", String(btn.dataset.industry === id));
  }
  updateEraOptions();
  nextMovie();
}

function setHidden(hidden) {
  els.cover.hidden = !hidden;
  els.hide.textContent = hidden ? "Show" : "Hide";
}

// YouTube player
let player = null;
let playerReady = false;
let pendingVideo = null;
let autoplayCheck = null;

window.onYouTubeIframeAPIReady = () => {
  player = new YT.Player("player", {
    host: "https://www.youtube-nocookie.com",
    playerVars: { playsinline: 1, rel: 0, modestbranding: 1 },
    events: {
      onReady: () => {
        playerReady = true;
        if (pendingVideo) playVideo(pendingVideo.id, pendingVideo.autoplay);
      },
      onStateChange: (event) => {
        if (event.data === YT.PlayerState.PLAYING) {
          els.unmute.hidden = !player.isMuted();
        }
      },
      onError: () => {
        els.meta.textContent = "This clip won't play here - tap Next movie.";
      },
    },
  });
};

function playVideo(videoId, autoplay) {
  if (!playerReady) {
    pendingVideo = { id: videoId, autoplay };
    return;
  }
  pendingVideo = null;
  clearTimeout(autoplayCheck);
  if (!autoplay) {
    player.cueVideoById(videoId);
    return;
  }
  player.loadVideoById(videoId);
  // Mobile browsers often block autoplay with sound; fall back to muted playback.
  autoplayCheck = setTimeout(() => {
    const state = player.getPlayerState();
    if (state !== YT.PlayerState.PLAYING && state !== YT.PlayerState.BUFFERING) {
      player.mute();
      player.playVideo();
    }
  }, 1500);
}

// Movies
let queued = null;

function filterKey() {
  return `${industry}|${els.era.value}`;
}

async function fetchMovie() {
  const params = new URLSearchParams({ industry, exclude: loadSeen().join(",") });
  if (els.era.value !== "all") {
    const [minYear, maxYear] = els.era.value.split("-");
    params.set("minYear", minYear);
    params.set("maxYear", maxYear);
  }
  const res = await fetch(`/api/movie/random?${params}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function showMovie(movie, autoplay) {
  const seen = loadSeen();
  saveSeen(movie.exhausted ? [movie.videoId] : [...seen, movie.videoId]);

  els.name.textContent = movie.name;
  els.year.textContent = movie.year;
  els.meta.textContent = movie.exhausted
    ? "You've seen them all - starting over!"
    : `${movie.remaining} more ${industryLabel()} movies left`;
  playVideo(movie.videoId, autoplay);
  setHidden(autoplay);
  resetTimer();
}

// The next movie is prefetched so a tap can start the video synchronously,
// which browsers require before they allow playback with sound.
function takeQueued() {
  const q = queued;
  queued = null;
  if (!q || q.filter !== filterKey() || loadSeen().includes(q.movie.videoId)) return null;
  return q.movie;
}

async function prefetch() {
  const filter = filterKey();
  try {
    queued = { filter, movie: await fetchMovie() };
  } catch {
    queued = null;
  }
}

async function nextMovie({ autoplay = true } = {}) {
  els.next.disabled = true;
  try {
    showMovie(takeQueued() || (await fetchMovie()), autoplay);
  } catch (err) {
    els.name.textContent = "Couldn't load a movie";
    els.year.textContent = "";
    els.meta.textContent = "Check your connection and tap Next again.";
    console.error(err);
    return;
  } finally {
    els.next.disabled = false;
  }
  prefetch();
}

// Timer
let timerId = null;
let remaining = 0;
let audioCtx = null;

function formatTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = String(seconds % 60).padStart(2, "0");
  return `${m}:${s}`;
}

function renderClock() {
  els.clock.textContent = formatTime(remaining);
  els.clock.classList.toggle("low", remaining > 0 && remaining <= 10 && timerId !== null);
  els.clock.classList.toggle("done", remaining === 0);
}

function resetTimer() {
  clearInterval(timerId);
  timerId = null;
  remaining = Number(els.duration.value);
  els.timerToggle.textContent = "Start timer";
  renderClock();
}

function beep() {
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    [0, 0.35, 0.7].forEach((offset) => {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.25, audioCtx.currentTime + offset);
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + offset + 0.3);
      osc.connect(gain).connect(audioCtx.destination);
      osc.start(audioCtx.currentTime + offset);
      osc.stop(audioCtx.currentTime + offset + 0.3);
    });
  } catch (err) {
    console.warn("Audio unavailable", err);
  }
}

function timeUp() {
  clearInterval(timerId);
  timerId = null;
  els.timerToggle.textContent = "Restart";
  renderClock();
  beep();
  if (navigator.vibrate) navigator.vibrate([300, 150, 300, 150, 600]);
}

function toggleTimer() {
  if (timerId !== null) {
    clearInterval(timerId);
    timerId = null;
    els.timerToggle.textContent = "Resume";
    renderClock();
    return;
  }
  if (remaining === 0) remaining = Number(els.duration.value);
  // Unlock audio on iOS, which only allows it after a user gesture.
  audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
  timerId = setInterval(() => {
    remaining -= 1;
    if (remaining <= 0) {
      remaining = 0;
      timeUp();
    } else {
      renderClock();
    }
  }, 1000);
  els.timerToggle.textContent = "Pause";
  renderClock();
}

els.next.addEventListener("click", () => nextMovie());
els.hide.addEventListener("click", () => setHidden(els.cover.hidden));
els.reveal.addEventListener("click", () => setHidden(false));
els.era.addEventListener("change", () => nextMovie());
els.duration.addEventListener("change", resetTimer);
els.timerToggle.addEventListener("click", toggleTimer);
els.unmute.addEventListener("click", () => {
  player.unMute();
  els.unmute.hidden = true;
});
document.addEventListener("gamechange", (event) => {
  if (event.detail !== "charades" && playerReady) {
    clearTimeout(autoplayCheck);
    player.pauseVideo();
  }
});

async function init() {
  resetTimer();
  try {
    const res = await fetch("/api/catalog");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    catalog = (await res.json()).industries;
  } catch (err) {
    els.name.textContent = "Couldn't load movies";
    els.meta.textContent = "Check your connection and refresh the page.";
    console.error(err);
    return;
  }
  if (!catalog.some((item) => item.id === industry)) industry = catalog[0].id;
  renderIndustries();
  updateEraOptions();
  nextMovie({ autoplay: false });
}

init();
