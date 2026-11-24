// Resolves once the YouTube IFrame API has loaded; each game creates its own player.
const youtubeReady = new Promise((resolve) => {
  window.onYouTubeIframeAPIReady = resolve;
});
