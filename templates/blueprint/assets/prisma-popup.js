// Make PRISMA-strip counts clickable -> modal listing the actual included studies
// for that chapter. Data is window.__PICO_STUDIES__ = { "<chapterId>": [study,...] },
// emitted by the build. The "檢索命中" (found) step is left static — the raw
// search list is not persisted, only the Q1 + CrossRef-verified included set.
(function () {
  "use strict";
  var DATA = window.__PICO_STUDIES__ || {};
  var SEARCH = window.__PICO_SEARCH__ || {};

  function chapterIdOf(el) {
    var sec = el.closest && el.closest("section.chapter");
    return sec ? sec.id : null;
  }
  function isFound(step) {
    return ((step.querySelector(".ps-l") || {}).textContent || "").indexOf("檢索命中") !== -1;
  }
  // 檢索命中 -> show the query; other steps -> show the included-study list.
  function isClickable(step) {
    var id = chapterIdOf(step);
    if (!id) return false;
    return isFound(step) ? !!SEARCH[id] : !!(DATA[id] && DATA[id].length);
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

  // Shared modal shell. Returns { back } (not yet appended); wires its own close.
  function makeModal(title, bodyHtml) {
    var back = document.createElement("div");
    back.className = "lit-modal-backdrop";
    back.innerHTML =
      '<div class="lit-modal" role="dialog" aria-modal="true">' +
      '<div class="lm-head"><strong>' + title + "</strong>" +
      '<button class="lm-close" aria-label="關閉">×</button></div>' + bodyHtml + "</div>";
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
    return { back: back, close: close };
  }

  function openModal(chapterId) {
    var studies = DATA[chapterId] || [];
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
    var m = makeModal(
      "納入文獻（" + studies.length + " 篇 · Q1 · ≥2016 · CrossRef 驗證）",
      '<ol class="lm-list">' + rows + "</ol>"
    );
    document.body.appendChild(m.back);
  }

  function openSearchModal(chapterId) {
    var s = SEARCH[chapterId] || {};
    var chips = (s.terms || []).map(function (t) { return '<span class="q-chip">' + t + "</span>"; }).join("");
    var mesh = (s.mesh || []).length
      ? '<p class="lm-meta">MeSH：' + s.mesh.join("、") + "</p>" : "";
    var modal = makeModal(
      "檢索策略（命中 " + (s.found || "?") + " 篇）",
      '<div class="q-body">' +
      '<p class="lm-meta">資料庫：' + (s.databases || []).join(" · ") + "　·　年限：≥ " + (s.date_from || 2016) + "</p>" +
      '<div class="q-chips">' + chips + "</div>" +
      "<p class=\"lm-meta\">布林查詢式（送至各庫，實際語法依庫而異）：</p>" +
      '<pre class="q-code">' + (s.query || "") + "</pre>" + mesh +
      '<p class="lm-meta">命中後依序套用：去重 → 僅 Q1 期刊 → ≥2016 → doi.org 解析 → CrossRef 驗證 → 納入。</p>' +
      "</div>"
    );
    document.body.appendChild(modal.back);
  }

  function dispatch(step) {
    var id = chapterIdOf(step);
    if (isFound(step)) openSearchModal(id); else openModal(id);
  }
  document.addEventListener("click", function (e) {
    var step = e.target.closest && e.target.closest(".prisma-step.clickable");
    if (step) dispatch(step);
  });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Enter" && e.key !== " ") return;
    var step = e.target.closest && e.target.closest(".prisma-step.clickable");
    if (step) { e.preventDefault(); dispatch(step); }
  });

  // chapters load asynchronously; mark affordances now and shortly after.
  markAffordances();
  setTimeout(markAffordances, 400);
  setTimeout(markAffordances, 1200);
})();
