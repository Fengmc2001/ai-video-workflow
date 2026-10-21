"use strict";
const video = document.querySelector("#film-video");
const status = document.querySelector("#player-status");
const qualityButtons = document.querySelectorAll("[data-quality]");
const languageButtons = document.querySelectorAll("[data-language]");
const sources = {
  zh: { full: "media/traffic-safety-fengmc-1080p60.mp4", preview: "assets/demo-preview.mp4" },
  en: { full: "media/traffic-safety-english-fengmc-1080p60.mp4", preview: "assets/demo-english-preview.mp4" }
};
const params = new URLSearchParams(window.location.search);
let language = params.get("lang") === "en" ? "en" : "zh";
let quality = "full";
let sourceChange = 0;
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
function playerStatus(text) { status.textContent = text; }
function playVideo() {
  const attempt = video.play();
  if (attempt) attempt.catch(() => playerStatus("Press play · 点击播放"));
}
function updateButtons() {
  qualityButtons.forEach(button => button.setAttribute("aria-pressed", String(button.dataset.quality === quality)));
  languageButtons.forEach(button => button.setAttribute("aria-pressed", String(button.dataset.language === language)));
}
function loadFilm(time, resume) {
  const change = ++sourceChange;
  updateButtons();
  playerStatus("Loading · 正在载入");
  video.addEventListener("loadedmetadata", () => {
    if (change !== sourceChange) return;
    video.currentTime = Math.max(0, Math.min(time, Math.max(0, video.duration - 0.05)));
    if (resume) playVideo();
    else playerStatus("Ready to play · 点击播放");
  }, {once:true});
  video.src = sources[language][quality];
  video.load();
}
qualityButtons.forEach(button => button.addEventListener("click", () => {
  if (button.dataset.quality === quality) return;
  quality = button.dataset.quality;
  loadFilm(video.currentTime || 0, !video.paused);
}));
languageButtons.forEach(button => button.addEventListener("click", () => {
  if (button.dataset.language === language) return;
  language = button.dataset.language;
  const url = new URL(window.location.href);
  url.searchParams.set("lang", language);
  window.history.replaceState(null, "", url);
  loadFilm(video.currentTime || 0, !video.paused);
}));
video.addEventListener("play", () => playerStatus("Playing · 正在播放"));
video.addEventListener("pause", () => playerStatus("Paused · 已暂停"));
video.addEventListener("ended", () => playerStatus("Replay · 再看一次"));
video.addEventListener("error", () => playerStatus("Try 540p or reload · 可切换540p或刷新"));
document.querySelectorAll("[data-time]").forEach(button => button.addEventListener("click", () => {
  const seek = () => {
    video.currentTime = Math.min(Number(button.dataset.time), video.duration - 0.05);
    playVideo();
  };
  document.querySelector("#film").scrollIntoView({behavior:reducedMotion ? "auto" : "smooth"});
  if (video.readyState >= 1) seek();
  else { video.addEventListener("loadedmetadata", seek, {once:true}); video.load(); }
}));
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
document.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click", () => {
  const view = button.dataset.view;
  document.querySelectorAll("[data-view]").forEach(item => item.setAttribute("aria-pressed", String(item === button)));
  before.src = "assets/showcase/sr-before-" + view + ".jpg";
  after.src = "assets/showcase/sr-after-" + view + ".jpg";
  comparison.classList.toggle("detail", view === "detail");
  before.width = after.width = view === "detail" ? 640 : 1920;
  before.height = after.height = view === "detail" ? 640 : 1080;
}));
const requestedTime = Number(params.get("t")) || 0;
if (language === "en") loadFilm(requestedTime, false);
else if (requestedTime > 0 && Number.isFinite(requestedTime)) {
  const setStart = () => { video.currentTime = Math.min(requestedTime, video.duration - 0.05); };
  if (video.readyState >= 1) setStart();
  else video.addEventListener("loadedmetadata", setStart, {once:true});
}
updateButtons();
