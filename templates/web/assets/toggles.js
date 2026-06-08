// Dual toggles: audience (pro/lay) x language (zh/en).
// All four writeup variants live in the DOM; we show only the active pair.
(function () {
  "use strict";
  var root = document.documentElement;
  var state = { audience: "pro", lang: "zh" };

  function readHash() {
    var m = (location.hash || "").replace("#", "").split("/");
    if (m.length === 2) {
      if (m[0] === "pro" || m[0] === "lay") state.audience = m[0];
      if (m[1] === "zh" || m[1] === "en") state.lang = m[1];
    }
  }
  function load() {
    try {
      var s = JSON.parse(localStorage.getItem("verdict-toggles") || "null");
      if (s && s.audience) state.audience = s.audience;
      if (s && s.lang) state.lang = s.lang;
    } catch (e) { /* ignore */ }
    readHash();
  }
  function persist() {
    try { localStorage.setItem("verdict-toggles", JSON.stringify(state)); } catch (e) { /* ignore */ }
    if (history.replaceState) history.replaceState(null, "", "#" + state.audience + "/" + state.lang);
  }

  function applyWriteups() {
    var blocks = document.querySelectorAll(".writeup");
    blocks.forEach(function (b) {
      var match = b.getAttribute("data-audience") === state.audience &&
                  b.getAttribute("data-lang") === state.lang;
      b.hidden = !match;
    });
  }
  function applyButtons() {
    document.querySelectorAll("[data-set-audience]").forEach(function (btn) {
      btn.classList.toggle("active", btn.getAttribute("data-set-audience") === state.audience);
    });
    document.querySelectorAll("[data-set-lang]").forEach(function (btn) {
      btn.classList.toggle("active", btn.getAttribute("data-set-lang") === state.lang);
    });
  }
  function apply() {
    root.setAttribute("data-audience-active", state.audience);
    root.setAttribute("data-lang-active", state.lang);
    root.setAttribute("lang", state.lang === "zh" ? "zh-Hant" : "en");
    applyWriteups();
    applyButtons();
  }

  document.addEventListener("click", function (e) {
    var a = e.target.closest("[data-set-audience]");
    var l = e.target.closest("[data-set-lang]");
    if (a) { state.audience = a.getAttribute("data-set-audience"); persist(); apply(); }
    if (l) { state.lang = l.getAttribute("data-set-lang"); persist(); apply(); }
  });

  load();
  apply();
})();
