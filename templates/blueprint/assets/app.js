/* 4+2R Evidence Appraisal — app logic
   - loads modular chapter fragments (fetch → fallback to window.__CHAPTERS__ bundle for file://)
   - builds TOC, renders AMA references, wires citation jump + hovercards
   - version toggle (專業人員版 / 民眾版), scroll-spy, mobile nav
*/
(function () {
  "use strict";

  // chapter id -> fragment file. Provided by the renderer via __CHAPTER_LIST__;
  // falls back to the original 4+2R chapter set.
  var CHAPTERS = window.__CHAPTER_LIST__ || [
    { id: "ch0", file: "chapters/00-summary.html" },
    { id: "ch1", file: "chapters/01-method.html" },
    { id: "ch2", file: "chapters/02-microbiome.html" },
    { id: "ch3", file: "chapters/03-protein.html" },
    { id: "ch4", file: "chapters/04-meal-order.html" },
    { id: "ch5", file: "chapters/05-setpoint.html" },
    { id: "ch6", file: "chapters/06-safety.html" },
    { id: "ch7", file: "chapters/07-comparison.html" },
    { id: "ch8", file: "chapters/08-verdict.html" }
  ];

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var report = $("#report");
  var refsAnchor = $("#references");
  var bundle = window.__CHAPTERS__ || {};

  function loadFragment(ch) {
    // Try network fetch first (works under http server). Fall back to inlined bundle (file://).
    return fetch(ch.file, { cache: "no-cache" })
      .then(function (r) { if (!r.ok) throw new Error(String(r.status)); return r.text(); })
      .then(function (html) { return html && html.trim() ? html : bundleOrThrow(ch); })
      .catch(function () { return bundleOrThrow(ch); });
  }
  function bundleOrThrow(ch) {
    if (bundle[ch.id]) return bundle[ch.id];
    throw new Error("missing:" + ch.id);
  }

  function buildChapters() {
    var status = $("#loadStatus");
    return Promise.all(CHAPTERS.map(function (ch) {
      return loadFragment(ch).then(
        function (html) { return { id: ch.id, html: html, ok: true }; },
        function () { return { id: ch.id, html: "", ok: false }; }
      );
    })).then(function (results) {
      var missing = [];
      results.forEach(function (res) {
        if (!res.ok) { missing.push(res.id); return; }
        var tmp = document.createElement("div");
        tmp.innerHTML = res.html.trim();
        var sec = tmp.querySelector("section.chapter") || tmp.firstElementChild;
        if (sec) report.insertBefore(sec, refsAnchor);
      });
      if (status) {
        if (missing.length) {
          status.textContent = "下列章節尚未生成或無法載入：" + missing.join(", ") +
            "（若以 file:// 開啟且無 chapters.js，請改用本機伺服器：python3 -m http.server）";
          status.classList.add("err");
        } else { status.remove(); }
      }
    });
  }

  /* ---------- references ---------- */
  function renderReferences() {
    var refs = window.__REFS__ || [];
    var ol = $("#refList");
    var frag = document.createDocumentFragment();
    refs.forEach(function (r) {
      var li = document.createElement("li");
      li.id = "ref-" + r.n;
      var html = '<div class="ref-body">' + r.ama;
      if (r.doi) {
        html += ' <span class="doi"><a href="https://doi.org/' + r.doi +
          '" target="_blank" rel="noopener">doi:' + r.doi + "</a></span>";
      }
      html += '<span class="ref-back" data-back="' + r.n + '"></span></div>';
      li.innerHTML = html;
      frag.appendChild(li);
    });
    ol.appendChild(frag);
    var c = $("#refCount"); if (c) c.textContent = String(refs.length);
  }

  function refByN(n) {
    var refs = window.__REFS__ || [];
    for (var i = 0; i < refs.length; i++) if (String(refs[i].n) === String(n)) return refs[i];
    return null;
  }

  /* ---------- wire <cite class="ref" data-ref="N"> → links ---------- */
  function wireCitations() {
    var cites = report.querySelectorAll("cite.ref[data-ref]");
    var usage = {}; // n -> [citeIds] for back-links
    Array.prototype.forEach.call(cites, function (cite, idx) {
      var n = cite.getAttribute("data-ref");
      var ref = refByN(n);
      var a = document.createElement("a");
      a.className = "cite";
      a.href = "#ref-" + n;
      a.textContent = n;
      a.id = "cite-" + n + "-" + idx;
      a.setAttribute("data-ref", n);
      a.setAttribute("aria-label", "參考文獻 " + n);
      if (ref) a.setAttribute("data-ama", ref.ama);
      cite.parentNode.replaceChild(a, cite);
      (usage[n] = usage[n] || []).push(a.id);

      a.addEventListener("click", function (e) {
        e.preventDefault();
        jumpToRef(n);
      });
      a.addEventListener("mouseenter", function () { showCitePop(a, n); });
      a.addEventListener("mouseleave", hideCitePop);
      a.addEventListener("focus", function () { showCitePop(a, n); });
      a.addEventListener("blur", hideCitePop);
    });
    // back-links on each reference
    Object.keys(usage).forEach(function (n) {
      var span = report.querySelector('.ref-back[data-back="' + n + '"]');
      if (!span) return;
      var first = usage[n][0];
      span.innerHTML = '↩ <a href="#' + first + '" data-firstcite="' + first + '">回到內文</a>';
      span.querySelector("a").addEventListener("click", function (e) {
        e.preventDefault();
        var el = document.getElementById(first);
        if (el) { el.scrollIntoView({ behavior: "smooth", block: "center" });
          el.style.background = "var(--vc-weak-bg)";
          setTimeout(function () { el.style.background = ""; }, 1400); }
      });
    });
  }

  function jumpToRef(n) {
    var li = document.getElementById("ref-" + n);
    if (!li) return;
    li.scrollIntoView({ behavior: "smooth", block: "center" });
    li.classList.remove("flash"); void li.offsetWidth; li.classList.add("flash");
    if (history.replaceState) history.replaceState(null, "", "#ref-" + n);
  }

  /* ---------- citation hovercard ---------- */
  var pop = $("#citePop"), popTimer;
  function showCitePop(anchor, n) {
    clearTimeout(popTimer);
    var ref = refByN(n);
    if (!ref) return;
    pop.innerHTML = '<span class="cp-n">[' + n + "]</span>" + ref.ama +
      (ref.doi ? ' <a href="https://doi.org/' + ref.doi + '" target="_blank" rel="noopener">doi:' + ref.doi + "</a>" : "");
    pop.hidden = false;
    var r = anchor.getBoundingClientRect();
    var top = window.scrollY + r.bottom + 8;
    var left = Math.min(window.scrollX + r.left, window.scrollX + document.documentElement.clientWidth - pop.offsetWidth - 14);
    pop.style.top = top + "px";
    pop.style.left = Math.max(10, left) + "px";
  }
  function hideCitePop() { popTimer = setTimeout(function () { pop.hidden = true; }, 180); }
  if (pop) {
    pop.addEventListener("mouseenter", function () { clearTimeout(popTimer); });
    pop.addEventListener("mouseleave", hideCitePop);
  }

  /* ---------- TOC + scroll-spy ---------- */
  function buildTOC() {
    var toc = $("#toc");
    var secs = report.querySelectorAll("section.chapter");
    var n = 0;
    Array.prototype.forEach.call(secs, function (sec) {
      var title = sec.getAttribute("data-title") || (sec.querySelector(".ch-title") || {}).textContent || sec.id;
      var a = document.createElement("a");
      a.href = "#" + sec.id;
      var isRef = sec.id === "references";
      var label = isRef ? "§" : String(n);
      a.innerHTML = '<span class="tnum">' + label + "</span><span class=\"ttxt\">" + title + "</span>";
      a.addEventListener("click", function (e) {
        e.preventDefault();
        sec.scrollIntoView({ behavior: "smooth", block: "start" });
        document.body.classList.remove("nav-open");
        history.replaceState && history.replaceState(null, "", "#" + sec.id);
      });
      toc.appendChild(a);
      if (!isRef) n++;
    });
    spy();
  }

  var spyTicking = false;
  function spy() {
    if (spyTicking) return; spyTicking = true;
    requestAnimationFrame(function () {
      var secs = report.querySelectorAll("section.chapter");
      var pos = window.scrollY + 120, current = null;
      Array.prototype.forEach.call(secs, function (sec) {
        if (sec.offsetTop <= pos) current = sec.id;
      });
      var links = document.querySelectorAll("#toc a");
      Array.prototype.forEach.call(links, function (l) {
        l.classList.toggle("active", l.getAttribute("href") === "#" + current);
      });
      spyTicking = false;
    });
  }

  /* ---------- version toggle ---------- */
  function setMode(mode) {
    document.body.classList.remove("mode-pro", "mode-public");
    document.body.classList.add("mode-" + mode);
    document.querySelectorAll(".mode-btn").forEach(function (b) {
      var on = b.getAttribute("data-mode") === mode;
      b.classList.toggle("is-active", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
    try { localStorage.setItem("r42_mode", mode); } catch (e) {}
  }
  function initMode() {
    var saved;
    try { saved = localStorage.getItem("r42_mode"); } catch (e) {}
    setMode(saved === "public" ? "public" : "pro");
    document.querySelectorAll(".mode-btn").forEach(function (b) {
      b.addEventListener("click", function () { setMode(b.getAttribute("data-mode")); });
    });
  }

  /* ---------- misc UI ---------- */
  function initChrome() {
    var nt = $("#navToggle");
    if (nt) nt.addEventListener("click", function () {
      var open = document.body.classList.toggle("nav-open");
      nt.setAttribute("aria-expanded", open ? "true" : "false");
    });
    var toTop = $("#toTop");
    window.addEventListener("scroll", function () {
      spy();
      if (toTop) toTop.hidden = window.scrollY < 600;
    }, { passive: true });
    if (toTop) toTop.addEventListener("click", function () { window.scrollTo({ top: 0, behavior: "smooth" }); });
  }

  /* ---------- boot ---------- */
  initMode();
  renderReferences();
  buildChapters().then(function () {
    wireCitations();
    buildTOC();
    initChrome();
    // deep-link to a ref/section if hash present
    if (location.hash) {
      var el = document.querySelector(location.hash);
      if (el) setTimeout(function () { el.scrollIntoView({ block: "center" }); }, 60);
    }
  });
})();
