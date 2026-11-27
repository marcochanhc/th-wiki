/* Top Heroes Wiki — site-wide search. Vanilla JS only; no network, no third-party library. */
(function () {
  var form = document.querySelector("[data-site-search]");
  if (!form) return;

  var input = form.querySelector("#site-search-q");
  var panel = form.querySelector("[data-site-search-results]");
  var index = window.TH_WIKI_SEARCH_INDEX;
  if (!input || !panel || !index || !index.length) return;

  form.hidden = false;

  function norm(s) {
    return String(s || "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  function siteRoot() {
    var attr = form.getAttribute("data-root");
    if (attr !== null && attr !== undefined) return attr;
    var scripts = document.getElementsByTagName("script");
    for (var i = 0; i < scripts.length; i++) {
      var src = scripts[i].getAttribute("src") || "";
      var m = src.match(/^(.*)assets\/js\/search(?:-index)?\.js$/);
      if (m) return m[1];
    }
    return "";
  }

  var root = siteRoot();

  function score(item, q) {
    var title = norm(item.title);
    var text = norm(item.text);
    if (title === q) return 100;
    if (title.indexOf(q) === 0) return 80;
    if (title.indexOf(q) !== -1) return 60;
    if (text.indexOf(q) !== -1) return 20;
    return 0;
  }

  function hide() {
    panel.hidden = true;
    panel.innerHTML = "";
    input.setAttribute("aria-expanded", "false");
  }

  function render() {
    var q = norm(input.value);
    if (!q) {
      hide();
      return;
    }
    var hits = [];
    for (var i = 0; i < index.length; i++) {
      var s = score(index[i], q);
      if (s) hits.push({ s: s, item: index[i] });
    }
    hits.sort(function (a, b) {
      if (b.s !== a.s) return b.s - a.s;
      return a.item.title.localeCompare(b.item.title, "zh-Hant");
    });

    panel.innerHTML = "";
    if (!hits.length) {
      var empty = document.createElement("p");
      empty.className = "site-search-empty";
      empty.textContent = "沒有符合的項目";
      panel.appendChild(empty);
      panel.hidden = false;
      input.setAttribute("aria-expanded", "true");
      return;
    }

    var ul = document.createElement("ul");
    var limit = Math.min(hits.length, 20);
    for (var j = 0; j < limit; j++) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = root + hits[j].item.url;
      a.textContent = hits[j].item.title;
      li.appendChild(a);
      ul.appendChild(li);
    }
    panel.appendChild(ul);
    panel.hidden = false;
    input.setAttribute("aria-expanded", "true");
  }

  input.addEventListener("input", render);
  input.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") {
      input.value = "";
      hide();
      return;
    }
    if (ev.key === "Enter") {
      ev.preventDefault();
      var first = panel.querySelector("a");
      if (first) {
        window.location.href = first.getAttribute("href");
      }
    }
  });
  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    var first = panel.querySelector("a");
    if (first) {
      window.location.href = first.getAttribute("href");
    } else {
      render();
    }
  });
  document.addEventListener("click", function (ev) {
    if (!form.contains(ev.target)) hide();
  });
})();
