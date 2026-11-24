const SONG_LANGUAGE_KEY = "songs:language";

const songEls = {
  languages: document.getElementById("song-languages"),
  era: document.getElementById("song-era"),
  stage: document.getElementById("song-stage"),
  play: document.getElementById("song-play"),
  clock: document.getElementById("song-clock"),
  status: document.getElementById("song-status"),
  restart: document.getElementById("song-restart"),
  skip: document.getElementById("song-skip"),
  sound: document.getElementById("song-sound"),
  answer: document.getElementById("song-answer"),
  title: document.getElementById("song-title"),
  film: document.getElementById("song-film"),
  music: document.getElementById("song-music"),
  singers: document.getElementById("song-singers"),
  meta: document.getElementById("song-meta"),
  reveal: document.getElementById("song-reveal"),
  next: document.getElementById("song-next"),
};

let songCatalog = [];
let songLanguage = localStorage.getItem(SONG_LANGUAGE_KEY) || "bollywood";
let songsStarted = false;

function songSeenKey() {
  return `songs:seen:${songLanguage}`;
}

function loadSongSeen() {
  try {
    return JSON.parse(localStorage.getItem(songSeenKey())) || [];
  } catch {
    return [];
  }
}

function saveSongSeen(seen) {
  localStorage.setItem(songSeenKey(), JSON.stringify(seen));
}

function songLanguageLabel() {
  return songCatalog.find((item) => item.id === songLanguage)?.label || "";
}

function renderSongLanguages() {
  songEls.languages.replaceChildren(
    ...songCatalog.map((item) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "seg";
      btn.textContent = item.label;
      btn.dataset.language = item.id;
      btn.setAttribute("aria-pressed", String(item.id === songLanguage));
      btn.addEventListener("click", () => selectSongLanguage(item.id));
      return btn;
    }),
  );
}

function updateSongEraOptions() {
  const years = songCatalog.find((item) => item.id === songLanguage)?.years || [];
  for (const option of songEls.era.options) {
    if (option.value === "all") continue;
    const [min, max] = option.value.split("-").map(Number);
    option.disabled = !years.some((year) => year >= min && year <= max);
  }
  if (songEls.era.selectedOptions[0]?.disabled) songEls.era.value = "all";
}

function selectSongLanguage(id) {
  if (id === songLanguage) return;
  songLanguage = id;
  localStorage.setItem(SONG_LANGUAGE_KEY, id);
  for (const btn of songEls.languages.children) {
    btn.setAttribute("aria-pressed", String(btn.dataset.language === id));
  }
  updateSongEraOptions();
  nextSong();
}

function setSongRevealed(revealed) {
  songEls.stage.classList.toggle("covered", !revealed);
  songEls.answer.hidden = !revealed;
  songEls.reveal.textContent = revealed ? "Hide answer" : "Reveal answer";
}

// YouTube player
let songPlayer = null;
let songPlayerReady = false;
let pendingSong = null;
let songAutoplayCheck = null;
let songError = null;
let clockTimer = null;

youtubeReady.then(() => {
  songPlayer = new YT.Player("song-player", {
    host: "https://www.youtube-nocookie.com",
    playerVars: { playsinline: 1, rel: 0, modestbranding: 1 },
    events: {
      onReady: () => {
        songPlayerReady = true;
        if (pendingSong) loadSong(pendingSong.id, pendingSong.autoplay);
        renderPlayback();
      },
      onStateChange: renderPlayback,
      onError: () => {
        songError = "This song won't play here. Tap Play next song.";
        renderPlayback();
      },
    },
  });
});

function formatClock(seconds) {
  const s = Math.floor(seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function statusText(state, muted) {
  switch (state) {
    case YT.PlayerState.PLAYING:
      return muted ? "Playing without sound" : "Playing";
    case YT.PlayerState.BUFFERING:
      return "Loading...";
    case YT.PlayerState.PAUSED:
      return "Paused";
    case YT.PlayerState.ENDED:
      return "Song finished";
    default:
      return "Tap play to start the song";
  }
}

function renderPlayback() {
  if (!songPlayerReady) return;
  const state = songPlayer.getPlayerState();
  const playing = state === YT.PlayerState.PLAYING || state === YT.PlayerState.BUFFERING;
  const muted = songPlayer.isMuted();
  songEls.play.classList.toggle("playing", playing);
  songEls.play.setAttribute("aria-label", playing ? "Pause song" : "Play song");
  songEls.clock.textContent = formatClock(songPlayer.getCurrentTime() || 0);
  songEls.status.textContent = songError || statusText(state, muted);
  songEls.sound.hidden = !(playing && muted);
}

// Mobile browsers often block autoplay with sound; fall back to muted playback
// and offer a button that restarts the song with sound.
function checkAutoplay() {
  clearTimeout(songAutoplayCheck);
  songAutoplayCheck = setTimeout(() => {
    const state = songPlayer.getPlayerState();
    if (state !== YT.PlayerState.PLAYING && state !== YT.PlayerState.BUFFERING) {
      songPlayer.mute();
      songPlayer.playVideo();
    }
  }, 1500);
}

function startPlayback() {
  songPlayer.playVideo();
  checkAutoplay();
}

function loadSong(videoId, autoplay) {
  if (!songPlayerReady) {
    pendingSong = { id: videoId, autoplay };
    return;
  }
  pendingSong = null;
  songError = null;
  clearTimeout(songAutoplayCheck);
  songPlayer.unMute();
  if (autoplay) {
    songPlayer.loadVideoById(videoId);
    checkAutoplay();
  } else {
    songPlayer.cueVideoById(videoId);
  }
  renderPlayback();
}

// Songs
let queuedSong = null;

function songFilterKey() {
  return `${songLanguage}|${songEls.era.value}`;
}

async function fetchSong() {
  const params = new URLSearchParams({ language: songLanguage, exclude: loadSongSeen().join(",") });
  if (songEls.era.value !== "all") {
    const [minYear, maxYear] = songEls.era.value.split("-");
    params.set("minYear", minYear);
    params.set("maxYear", maxYear);
  }
  const res = await fetch(`/api/song/random?${params}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function showSong(song, autoplay) {
  const seen = loadSongSeen();
  saveSongSeen(song.exhausted ? [song.videoId] : [...seen, song.videoId]);

  songEls.title.textContent = song.title;
  songEls.film.textContent = `${song.film} · ${song.year}`;
  songEls.music.textContent = song.music;
  songEls.singers.textContent = song.singers.join(", ");
  songEls.meta.textContent = song.exhausted
    ? "You've heard them all - starting over!"
    : `${song.remaining} more ${songLanguageLabel()} songs left`;
  setSongRevealed(false);
  loadSong(song.videoId, autoplay);
}

// The next song is prefetched so a tap can start it synchronously,
// which browsers require before they allow playback with sound.
function takeQueuedSong() {
  const q = queuedSong;
  queuedSong = null;
  if (!q || q.filter !== songFilterKey() || loadSongSeen().includes(q.song.videoId)) return null;
  return q.song;
}

async function prefetchSong() {
  const filter = songFilterKey();
  try {
    queuedSong = { filter, song: await fetchSong() };
  } catch {
    queuedSong = null;
  }
}

async function nextSong({ autoplay = true } = {}) {
  songEls.next.disabled = true;
  try {
    showSong(takeQueuedSong() || (await fetchSong()), autoplay);
  } catch (err) {
    songError = "Couldn't load a song. Check your connection and try again.";
    songEls.status.textContent = songError;
    console.error(err);
    return;
  } finally {
    songEls.next.disabled = false;
  }
  prefetchSong();
}

async function startSongs() {
  songsStarted = true;
  try {
    const res = await fetch("/api/songs/catalog");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    songCatalog = (await res.json()).languages;
    if (!songCatalog.length) throw new Error("No songs in the catalog");
  } catch (err) {
    songsStarted = false;
    songEls.status.textContent = "Couldn't load songs. Check your connection and refresh the page.";
    console.error(err);
    return;
  }
  if (!songCatalog.some((item) => item.id === songLanguage)) songLanguage = songCatalog[0].id;
  renderSongLanguages();
  updateSongEraOptions();
  nextSong({ autoplay: false });
}

songEls.play.addEventListener("click", () => {
  if (!songPlayerReady) return;
  const state = songPlayer.getPlayerState();
  if (state === YT.PlayerState.PLAYING || state === YT.PlayerState.BUFFERING) {
    clearTimeout(songAutoplayCheck);
    songPlayer.pauseVideo();
  } else {
    if (state === YT.PlayerState.ENDED) songPlayer.seekTo(0, true);
    startPlayback();
  }
  renderPlayback();
});
songEls.restart.addEventListener("click", () => {
  if (!songPlayerReady) return;
  songPlayer.seekTo(0, true);
  startPlayback();
});
songEls.skip.addEventListener("click", () => {
  if (!songPlayerReady) return;
  songPlayer.seekTo((songPlayer.getCurrentTime() || 0) + 10, true);
  renderPlayback();
});
songEls.sound.addEventListener("click", () => {
  songPlayer.unMute();
  songPlayer.seekTo(0, true);
  songPlayer.playVideo();
  renderPlayback();
});
songEls.reveal.addEventListener("click", () => setSongRevealed(songEls.answer.hidden));
songEls.next.addEventListener("click", () => nextSong());
songEls.era.addEventListener("change", () => nextSong());

document.addEventListener("gamechange", (event) => {
  clearInterval(clockTimer);
  if (event.detail === "songs") {
    if (!songsStarted) startSongs();
    clockTimer = setInterval(renderPlayback, 250);
  } else if (songPlayerReady) {
    clearTimeout(songAutoplayCheck);
    songPlayer.pauseVideo();
  }
});
