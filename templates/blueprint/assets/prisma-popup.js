// Make PRISMA-strip counts clickable -> modal listing the actual included studies
// for that chapter. Data is window.__PICO_STUDIES__ = { "<chapterId>": [study,...] },
// emitted by the build. The "檢索命中" (found) step is left static — the raw
// search list is not persisted, only the Q1 + CrossRef-verified included set.
(function () {
  "use strict";
  var DATA = window.__PICO_STUDIES__ || {};

  function chapterIdOf(el) {
    var sec = el.closest && el.closest("section.chapter");
    return sec ? sec.id : null;
  }
  // A step is clickable if it is NOT the first ("檢索命中") and the chapter has data.
  function isClickable(step) {
    var label = (step.querySelector(".ps-l") || {}).textContent || "";
    if (label.indexOf("檢索命中") !== -1) return false;
    var id = chapterIdOf(step);
    return id && DATA[id] && DATA[id].length;
  }

  function markAffordances() {
    document.querySelectorAll(".prisma-step").forEach(function (step) {
      if (isClickable(step)) {
        step.classList.add("clickable");
        step.setAttribute("role", "button");
        step.setAttribute("tabindex", "0");
        step.setAttribute("aria-label", "點擊查看納入文獻清單");
      }
    });
  }

  function badge(cls, text) { return '<span class="ver-badge ' + cls + '">' + text + "</span>"; }

  function openModal(chapterId) {
    var studies = DATA[chapterId] || [];
    var back = document.createElement("div");
    back.className = "lit-modal-backdrop";
    var rows = studies.map(function (s, i) {
      var meta = [s.journal, s.year, s.quartile].filter(Boolean).join(" · ");
      var badges =
        (s.crossref_verified ? badge("vb-crossref", "CrossRef ✓") : "") +
        (s.pmid ? badge("vb-pubmed", "PubMed " + s.pmid) : "");
      var title = s.doi
        ? '<a href="https://doi.org/' + s.doi + '" target="_blank" rel="noopener">' + s.title + "</a>"
        : s.title;
      return (
        '<li><span class="lm-n">' + (i + 1) + ".</span><div>" +
        '<div class="lm-title">' + title + "</div>" +
        '<div class="lm-meta">' + meta + " " + badges + "</div></div></li>"
      );
    }).join("");
    back.innerHTML =
      '<div class="lit-modal" role="dialog" aria-modal="true">' +
      '<div class="lm-head"><strong>納入文獻（' + studies.length + " 篇 · Q1 · ≥2016 · CrossRef 驗證）</strong>" +
      '<button class="lm-close" aria-label="關閉">×</button></div>' +
      '<ol class="lm-list">' + rows + "</ol></div>";
    document.body.appendChild(back);
    document.body.style.overflow = "hidden";

    function close() {
      back.remove();
      document.body.style.overflow = "";
      document.removeEventListener("keydown", onKey);
    }
    function onKey(e) { if (e.key === "Escape") close(); }
    back.addEventListener("click", function (e) {
      if (e.target === back || e.target.classList.contains("lm-close")) close();
    });
    document.addEventListener("keydown", onKey);
  }

  document.addEventListener("click", function (e) {
    var step = e.target.closest && e.target.closest(".prisma-step.clickable");
    if (step) openModal(chapterIdOf(step));
  });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Enter" && e.key !== " ") return;
    var step = e.target.closest && e.target.closest(".prisma-step.clickable");
    if (step) { e.preventDefault(); openModal(chapterIdOf(step)); }
  });

  // chapters load asynchronously; mark affordances now and shortly after.
  markAffordances();
  setTimeout(markAffordances, 400);
  setTimeout(markAffordances, 1200);
})();
