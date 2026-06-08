// Lazy-reveal the table of contents and highlight the active section.
(function () {
  "use strict";
  var loading = document.querySelector(".toc-loading");
  var list = document.querySelector(".toc ol");
  if (loading) loading.hidden = true;
  if (list) list.hidden = false;

  var links = Array.prototype.slice.call(document.querySelectorAll(".toc a"));
  var byId = {};
  links.forEach(function (a) {
    var id = a.getAttribute("href").slice(1);
    byId[id] = a;
  });

  if (!("IntersectionObserver" in window)) return;
  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      var link = byId[entry.target.id];
      if (link && entry.isIntersecting) {
        links.forEach(function (l) { l.classList.remove("active"); });
        link.classList.add("active");
      }
    });
  }, { rootMargin: "-40% 0px -55% 0px", threshold: 0 });

  document.querySelectorAll("main section[id]").forEach(function (s) { observer.observe(s); });
})();
