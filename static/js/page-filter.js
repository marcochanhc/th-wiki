/* Top Heroes Wiki — in-page name filter. Vanilla JS only; no network. */
(function () {
  var form = document.querySelector("[data-page-filter]");
  if (!form) return;

  var input = form.querySelector("#page-filter-q");
  var clear = form.querySelector(".page-filter-clear");
  var empty = form.querySelector(".page-filter-empty");
  var root = document.getElementById("main") || document.body;
  if (!input || !root) return;

  form.hidden = false;

  function norm(s) {
    return String(s || "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  function skipped(el) {
    return !!(el.closest && el.closest("#notes, #about, #codex, #cost-calc, .toc, .page-filter, [data-upgrade-cost]"));
  }

  function units() {
    var out = [];
    root.querySelectorAll("#heroes .hero-roster > li, .table-wrap table tbody tr").forEach(function (el) {
      if (!skipped(el)) out.push(el);
    });
    return out;
  }

  function apply() {
    var q = norm(input.value);
    var items = units();
    var shown = 0;
    items.forEach(function (el) {
      var ok = !q || norm(el.textContent).indexOf(q) !== -1;
      el.hidden = !ok;
      if (ok) shown += 1;
    });

    root.querySelectorAll(".table-wrap").forEach(function (wrap) {
      if (skipped(wrap)) return;
      var rows = wrap.querySelectorAll("tbody tr");
      if (!rows.length) return;
      var any = false;
      for (var i = 0; i < rows.length; i++) {
        if (!rows[i].hidden) {
          any = true;
          break;
        }
      }
      wrap.hidden = !!(q && !any);
    });

    root.querySelectorAll("h3, h4").forEach(function (h) {
      if (skipped(h)) return;
      var el = h.nextElementSibling;
      var saw = false;
      var any = false;
      while (el && !/^H[1-4]$/.test(el.tagName) && el.tagName !== "SECTION") {
        if (el.classList && el.classList.contains("table-wrap")) {
          saw = true;
          if (!el.hidden) any = true;
        }
        el = el.nextElementSibling;
      }
      if (saw) h.hidden = !!(q && !any);
    });

    var sections = Array.prototype.slice.call(root.querySelectorAll("section"));
    sections.sort(function (a, b) {
      return b.querySelectorAll("section").length - a.querySelectorAll("section").length;
    });
    sections.forEach(function (sec) {
      var id = sec.id || "";
      if (id === "notes" || id === "about" || id === "codex" || id === "heroes" || id === "cost-calc") {
        sec.hidden = false;
        return;
      }
      if (skipped(sec)) {
        sec.hidden = false;
        return;
      }
      var local = [];
      sec.querySelectorAll("#heroes .hero-roster > li, .table-wrap table tbody tr").forEach(function (el) {
        if (!skipped(el)) local.push(el);
      });
      if (!local.length) {
        sec.hidden = false;
        return;
      }
      var any = false;
      for (var i = 0; i < local.length; i++) {
        if (!local[i].hidden) {
          any = true;
          break;
        }
      }
      sec.hidden = !!(q && !any);
    });

    if (empty) empty.hidden = !(q && shown === 0);
  }

  input.addEventListener("input", apply);
  if (clear) {
    clear.addEventListener("click", function () {
      input.value = "";
      apply();
      input.focus();
    });
  }
  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    apply();
  });
  apply();
})();
