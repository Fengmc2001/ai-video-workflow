"use strict";
const video = document.querySelector("#film-video");
const status = document.querySelector("#player-status");
const qualityButtons = document.querySelectorAll("[data-quality]");
const sources = {
  full: "media/traffic-safety-fengmc-1080p60.mp4",
  preview: "assets/demo-preview.mp4"
};
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function playerStatus(text) { status.textContent = text; }
function playVideo() {
  const attempt = video.play();
  if (attempt) attempt.catch(() => playerStatus("Press play · 点击播放"));
}
qualityButtons.forEach(button => {
  button.addEventListener("click", () => {
    if (button.getAttribute("aria-pressed") === "true") return;
    const time = video.currentTime || 0;
    const wasPlaying = !video.paused;
    qualityButtons.forEach(item => item.setAttribute("aria-pressed", String(item === button)));
    playerStatus("Loading · 正在载入");
    video.addEventListener("loadedmetadata", () => {
      video.currentTime = Math.min(time, Math.max(0, video.duration - 0.05));
      if (wasPlaying) playVideo();
      else playerStatus("Ready to play · 点击播放");
    }, { once: true });
    video.src = sources[button.dataset.quality];
    video.load();
  });
});
video.addEventListener("play", () => playerStatus("Playing · 正在播放"));
video.addEventListener("pause", () => playerStatus("Paused · 已暂停"));
video.addEventListener("ended", () => playerStatus("Replay · 再看一次"));
video.addEventListener("error", () => playerStatus("Try 540p or reload · 可切换540p或刷新"));

document.querySelectorAll("[data-time]").forEach(button => {
  button.addEventListener("click", () => {
    const seek = () => {
      video.currentTime = Math.min(Number(button.dataset.time), video.duration - 0.05);
      playVideo();
    };
    document.querySelector("#film").scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth" });
    if (video.readyState >= 1) seek();
    else {
      video.addEventListener("loadedmetadata", seek, { once: true });
      video.load();
    }
  });
});

const comparison = document.querySelector("#compare-image");
const range = document.querySelector("#compare-range");
const before = document.querySelector("#compare-before");
const after = document.querySelector("#compare-after");
function updateSplit() {
  comparison.style.setProperty("--split", range.value + "%");
  range.setAttribute("aria-valuetext", range.value + "% before · 超分前");
}
range.addEventListener("input", updateSplit);
updateSplit();
document.querySelectorAll("[data-view]").forEach(button => {
  button.addEventListener("click", () => {
    const view = button.dataset.view;
    document.querySelectorAll("[data-view]").forEach(item => {
      item.setAttribute("aria-pressed", String(item === button));
    });
    before.src = "assets/showcase/sr-before-" + view + ".jpg";
    after.src = "assets/showcase/sr-after-" + view + ".jpg";
    comparison.classList.toggle("detail", view === "detail");
    before.width = after.width = view === "detail" ? 640 : 1920;
    before.height = after.height = view === "detail" ? 640 : 1080;
  });
});

const requestedTime = Number(new URLSearchParams(window.location.search).get("t"));
if (requestedTime > 0 && Number.isFinite(requestedTime)) {
  const setStart = () => { video.currentTime = Math.min(requestedTime, video.duration - 0.05); };
  if (video.readyState >= 1) setStart();
  else video.addEventListener("loadedmetadata", setStart, { once: true });
}
