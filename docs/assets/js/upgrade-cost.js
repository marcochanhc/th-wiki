/* Top Heroes Wiki — static upgrade-cost calculator. Vanilla JS only; no network. */
(function (root) {
  "use strict";

  function num(value) {
    var n = Number(value);
    return isFinite(n) ? n : 0;
  }

  function fmtQty(value) {
    var n = num(value);
    var sign = n < 0 ? "-" : "";
    var bits = String(Math.abs(Math.trunc(n))).split("");
    var out = [];
    for (var i = bits.length - 1, c = 0; i >= 0; i--, c++) {
      if (c && c % 3 === 0) out.push(",");
      out.push(bits[i]);
    }
    return sign + out.reverse().join("");
  }

  function resourceKey(typ, mid) {
    return String(typ) + ":" + String(mid);
  }

  function segmentLabel(typ, mid, qty, resources) {
    var key = resourceKey(typ, mid);
    var name = resources && Object.prototype.hasOwnProperty.call(resources, key) ? resources[key] : null;
    if (name) return name + " ×" + fmtQty(qty);
    return "類型 " + typ + "、第 " + mid + " 段、數量 " + fmtQty(qty);
  }

  function addCost(acc, typ, mid, qty) {
    var key = resourceKey(typ, mid);
    if (!acc[key]) acc[key] = { typ: typ, mid: mid, qty: 0 };
    acc[key].qty += num(qty);
  }

  function costList(acc, resources) {
    var keys = Object.keys(acc);
    keys.sort(function (a, b) {
      var aa = acc[a];
      var bb = acc[b];
      if (aa.typ !== bb.typ) return aa.typ - bb.typ;
      return aa.mid - bb.mid;
    });
    var out = [];
    for (var i = 0; i < keys.length; i++) {
      var it = acc[keys[i]];
      if (it.qty === 0) continue;
      out.push(segmentLabel(it.typ, it.mid, it.qty, resources));
    }
    return out;
  }

  function curveMax(curve) {
    return curve.min + curve.t.length - 1;
  }

  function sumCityRange(curve, fromLv, toLv, resources) {
    if (!curve || !curve.t || !curve.c) {
      return { ok: false, reason: "該來源沒有這座建築的升級列。" };
    }
    fromLv = num(fromLv);
    toLv = num(toLv);
    if (fromLv >= toLv) {
      return { ok: false, reason: "目前等級需小於目標等級。" };
    }
    var min = curve.min;
    var max = curveMax(curve);
    if (fromLv < min || toLv > max) {
      return {
        ok: false,
        reason: "這張表的等級範圍是 " + min + "–" + max + " 級，無法加總從 " + fromLv + " 級升到 " + toLv + " 級。",
      };
    }
    var acc = {};
    var time = 0;
    var used = 0;
    var emptyRows = 0;
    for (var lv = fromLv; lv < toLv; lv++) {
      var i = lv - min;
      time += num(curve.t[i]);
      var segs = curve.c[i] || [];
      used += 1;
      if (!segs.length) emptyRows += 1;
      for (var s = 0; s < segs.length; s++) {
        var seg = segs[s];
        addCost(acc, num(seg[0]), num(seg[1]), num(seg[2]));
      }
    }
    var leftover = null;
    if (toLv === max) {
      var ti = toLv - min;
      var tSegs = curve.c[ti] || [];
      var tTime = num(curve.t[ti]);
      if (tSegs.length) {
        leftover = {
          time: tTime,
          costs: (function () {
            var a = {};
            for (var j = 0; j < tSegs.length; j++) {
              addCost(a, num(tSegs[j][0]), num(tSegs[j][1]), num(tSegs[j][2]));
            }
            return costList(a, resources);
          })(),
        };
      }
    }
    return {
      ok: true,
      fromLv: fromLv,
      toLv: toLv,
      rows: used,
      emptyRows: emptyRows,
      time: time,
      costs: costList(acc, resources),
      leftover: leftover,
      range: min + "–" + max,
    };
  }

  function sumBeastLevels(data, fromLv, toLv) {
    var levels = data.levels;
    fromLv = num(fromLv);
    toLv = num(toLv);
    if (fromLv >= toLv) {
      return { ok: false, reason: "目前等級需小於目標等級。" };
    }
    if (fromLv < 0 || toLv > levels.max || toLv < levels.min) {
      return {
        ok: false,
        reason: "升級表是 1–" + levels.max + " 級。尚未升級請把目前等級填 0。",
      };
    }
    var start = Math.max(fromLv + 1, levels.min);
    var crystal = 0;
    var core = 0;
    var coreLevels = [];
    for (var lv = start; lv <= toLv; lv++) {
      crystal += num(levels.crystal[lv - levels.min]);
      var c = levels.core[String(lv)];
      if (c) {
        core += num(c);
        coreLevels.push(lv);
      }
    }
    return {
      ok: true,
      fromLv: fromLv,
      toLv: toLv,
      crystal: crystal,
      core: core,
      coreLevels: coreLevels,
    };
  }

  function starIndex(stars, star, sub) {
    for (var i = 0; i < stars.length; i++) {
      if (stars[i].star === star && stars[i].sub === sub) return i;
    }
    return -1;
  }

  function sumBeastStars(data, fromStar, fromSub, toStar, toSub, includeStart) {
    var stars = data.stars;
    var fromI;
    var toI = starIndex(stars, num(toStar), num(toSub));
    if (includeStart) {
      fromI = -1;
    } else {
      fromI = starIndex(stars, num(fromStar), num(fromSub));
      if (fromI < 0) return { ok: false, reason: "目前星級或子階不在升星表裡。" };
    }
    if (toI < 0) return { ok: false, reason: "目標星級或子階不在升星表裡。" };
    var startI = fromI + 1;
    if (startI > toI) {
      return { ok: false, reason: "目前星級需在目標之前。" };
    }
    var contract = 0;
    var other = 0;
    var stone = 0;
    var used = 0;
    var otherDiffers = false;
    for (var i = startI; i <= toI; i++) {
      var row = stars[i];
      used += 1;
      if (row.stone) {
        stone += num(row.stone);
      } else {
        contract += num(row.contract);
      }
      var o = row.other;
      if (row.stone) {
        if (num(o) !== 0 && num(o) !== num(row.stone)) otherDiffers = true;
        other += num(o || row.stone);
      } else {
        if (num(o) !== num(row.contract)) otherDiffers = true;
        other += num(o);
      }
    }
    return {
      ok: true,
      used: used,
      contract: contract,
      other: other,
      stone: stone,
      otherDiffers: otherDiffers,
      fromI: fromI,
      toI: toI,
    };
  }

  function el(html) {
    return html;
  }

  function escapeText(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function p(text) {
    return "<p>" + escapeText(text) + "</p>";
  }

  function renderCityResult(data, item, fromLv, toLv) {
    var bits = [];
    var tableNames = data.tables;
    var anyOk = false;
    bits.push("<h3>加總結果</h3>");
    bits.push(p("建築：「" + item.label + "」。從 " + fromLv + " 級升到 " + toLv + " 級。兩張表分開加總，不以其中一張覆寫另一張。"));
    if (item.hint) bits.push(p(item.hint));
    for (var i = 0; i < tableNames.length; i++) {
      var tname = tableNames[i];
      var key = item.tables[tname];
      bits.push("<h4>" + escapeText(tname) + "</h4>");
      if (!key || !data.curves[key]) {
        bits.push(p("這張表沒有這座建築的升級列，不能加總。"));
        continue;
      }
      var sum = sumCityRange(data.curves[key], fromLv, toLv, data.resources);
      if (!sum.ok) {
        bits.push(p(sum.reason));
        continue;
      }
      anyOk = true;
      if (!sum.costs.length) {
        bits.push(p("這段範圍在該表沒有消耗。時間（表上原值，無單位）合計 " + fmtQty(sum.time) + "。"));
      } else {
        bits.push("<p>消耗合計：" + escapeText(sum.costs.join("、")) + "。</p>");
        bits.push(p("時間（表上原值，無單位）合計 " + fmtQty(sum.time) + "。"));
      }
      bits.push(p("加總了 " + sum.rows + " 列（" + fromLv + " 級到 " + (toLv - 1) + " 級）。"));
      if (sum.leftover) {
        var extra = sum.leftover.costs.length ? sum.leftover.costs.join("、") : "沒有消耗";
        bits.push(
          p(
            "目標等級那一列在表上還寫了：" +
              extra +
              "，時間（表上原值，無單位）" +
              fmtQty(sum.leftover.time) +
              "。依本頁規則，從目前等級升到目標等級只加總到目標前一級；這一列不加進上列合計，只照錄原值。"
          )
        );
      }
    }
    if (!anyOk && bits.length <= 3) {
      /* still return the per-table reasons already added */
    }
    return bits.join("");
  }

  function renderBeastLevelResult(data, beast, fromLv, toLv) {
    var sum = sumBeastLevels(data, fromLv, toLv);
    if (!sum.ok) return "<h3>加總結果</h3>" + p(sum.reason);
    var bits = ["<h3>加總結果</h3>"];
    bits.push(p("守護魔獸：「" + beast.name + "」。從 " + fromLv + " 級升到 " + toLv + " 級（加總 " + (fromLv + 1) + " 級到 " + toLv + " 級各列）。"));
    var parts = [];
    if (sum.crystal) parts.push(beast.crystal + " ×" + fmtQty(sum.crystal));
    if (sum.core) parts.push(data.coreName + " ×" + fmtQty(sum.core));
    if (!parts.length) {
      bits.push(p("這段範圍在升級表沒有消耗。"));
    } else {
      bits.push("<p>消耗合計：" + escapeText(parts.join("、")) + "。</p>");
    }
    if (sum.coreLevels.length) {
      bits.push(
        p(
          data.coreName +
            "出現在這段範圍裡的 " +
            sum.coreLevels.join("、") +
            " 級。魔核是在 20、30 直到 170 級這些等級出現，不是只在其中某一級。"
        )
      );
    }
    return bits.join("");
  }

  function starLabel(row) {
    return row.star + " 星 " + row.sub + " 子階";
  }

  function renderBeastStarResult(data, beast, fromSel, toSel) {
    var includeStart = fromSel === "none";
    var fromStar = 0;
    var fromSub = 0;
    if (!includeStart) {
      var fp = fromSel.split(",");
      fromStar = num(fp[0]);
      fromSub = num(fp[1]);
    }
    var tp = toSel.split(",");
    var toStar = num(tp[0]);
    var toSub = num(tp[1]);
    var sum = sumBeastStars(data, fromStar, fromSub, toStar, toSub, includeStart);
    var bits = ["<h3>加總結果</h3>"];
    if (!sum.ok) return bits.join("") + p(sum.reason);
    var fromText = includeStart ? "尚未升星" : starLabel({ star: fromStar, sub: fromSub });
    var toText = starLabel({ star: toStar, sub: toSub });
    bits.push(p("守護魔獸：「" + beast.name + "」。從「" + fromText + "」升到「" + toText + "」，加總目前之後到目標（含）的各列。"));
    var main = [];
    if (sum.contract) main.push(beast.contract + " ×" + fmtQty(sum.contract));
    if (sum.stone) main.push(data.stoneName + " ×" + fmtQty(sum.stone));
    if (!main.length) {
      bits.push(p("這段範圍在升星表的主項沒有消耗。"));
    } else {
      bits.push("<p>主項消耗合計：" + escapeText(main.join("、")) + "。</p>");
    }
    if (sum.otherDiffers) {
      var otherParts = [];
      if (sum.other) otherParts.push("數量合計 " + fmtQty(sum.other));
      bits.push(
        p(
          "表上另有一欄消耗，只照錄原值，不對成賽季編號，也不寫成臨時擁有或臨時使用。" +
            (otherParts.length ? "該欄合計：" + otherParts.join("、") + "。" : "")
        )
      );
    }
    return bits.join("");
  }

  function fillStarSelect(sel, stars, withNone, noneLabel) {
    sel.innerHTML = "";
    if (withNone) {
      var o = document.createElement("option");
      o.value = "none";
      o.textContent = noneLabel;
      sel.appendChild(o);
    }
    for (var i = 0; i < stars.length; i++) {
      var opt = document.createElement("option");
      opt.value = stars[i].star + "," + stars[i].sub;
      opt.textContent = starLabel(stars[i]);
      sel.appendChild(opt);
    }
  }

  function bindCity(box, data) {
    var itemSel = box.querySelector("[data-uc-item]");
    var fromIn = box.querySelector("[data-uc-from]");
    var toIn = box.querySelector("[data-uc-to]");
    var btn = box.querySelector("[data-uc-run]");
    var out = box.querySelector("[data-uc-result]");
    if (!itemSel || !fromIn || !toIn || !btn || !out) return;

    data.items.forEach(function (item, idx) {
      var opt = document.createElement("option");
      opt.value = String(idx);
      opt.textContent = item.label;
      itemSel.appendChild(opt);
    });

    function currentItem() {
      return data.items[num(itemSel.value)] || data.items[0];
    }

    function bounds() {
      var item = currentItem();
      var min = null;
      var max = null;
      data.tables.forEach(function (tname) {
        var key = item.tables[tname];
        var curve = key && data.curves[key];
        if (!curve) return;
        var cmin = curve.min;
        var cmax = curveMax(curve);
        min = min === null ? cmin : Math.min(min, cmin);
        max = max === null ? cmax : Math.max(max, cmax);
      });
      return { min: min == null ? 0 : min, max: max == null ? 0 : max };
    }

    function syncBounds() {
      var b = bounds();
      fromIn.min = b.min;
      fromIn.max = Math.max(b.min, b.max - 1);
      toIn.min = b.min + 1;
      toIn.max = b.max;
      if (fromIn.value === "" || num(fromIn.value) < b.min) fromIn.value = b.min;
      if (toIn.value === "" || num(toIn.value) > b.max) toIn.value = b.max;
      if (num(toIn.value) <= num(fromIn.value)) toIn.value = Math.min(b.max, num(fromIn.value) + 1);
    }

    function run() {
      var item = currentItem();
      out.innerHTML = renderCityResult(data, item, num(fromIn.value), num(toIn.value));
      out.hidden = false;
    }

    itemSel.addEventListener("change", syncBounds);
    btn.addEventListener("click", run);
    box.addEventListener("submit", function (ev) {
      ev.preventDefault();
      run();
    });
    syncBounds();
  }

  function bindBeast(box, data) {
    var beastSel = box.querySelector("[data-uc-beast]");
    var modeSel = box.querySelector("[data-uc-mode]");
    var levelWraps = box.querySelectorAll("[data-uc-level-fields]");
    var starWraps = box.querySelectorAll("[data-uc-star-fields]");
    var fromLv = box.querySelector("[data-uc-from-lv]");
    var toLv = box.querySelector("[data-uc-to-lv]");
    var fromStar = box.querySelector("[data-uc-from-star]");
    var toStar = box.querySelector("[data-uc-to-star]");
    var btn = box.querySelector("[data-uc-run]");
    var out = box.querySelector("[data-uc-result]");
    if (!beastSel || !btn || !out) return;

    data.beasts.forEach(function (b, idx) {
      var opt = document.createElement("option");
      opt.value = String(idx);
      opt.textContent = b.name;
      beastSel.appendChild(opt);
    });
    if (fromStar) fillStarSelect(fromStar, data.stars, true, "尚未升星");
    if (toStar) {
      fillStarSelect(toStar, data.stars, false);
      toStar.value = data.stars[data.stars.length - 1].star + "," + data.stars[data.stars.length - 1].sub;
    }
    if (fromLv) {
      fromLv.min = 0;
      fromLv.max = data.levels.max - 1;
      fromLv.value = 0;
    }
    if (toLv) {
      toLv.min = 1;
      toLv.max = data.levels.max;
      toLv.value = data.levels.max;
    }

    function syncMode() {
      var starMode = modeSel && modeSel.value === "star";
      for (var i = 0; i < levelWraps.length; i++) levelWraps[i].hidden = !!starMode;
      for (var j = 0; j < starWraps.length; j++) starWraps[j].hidden = !starMode;
    }

    function run() {
      var beast = data.beasts[num(beastSel.value)] || data.beasts[0];
      if (modeSel && modeSel.value === "star") {
        out.innerHTML = renderBeastStarResult(data, beast, fromStar.value, toStar.value);
      } else {
        out.innerHTML = renderBeastLevelResult(data, beast, num(fromLv.value), num(toLv.value));
      }
      out.hidden = false;
    }

    if (modeSel) modeSel.addEventListener("change", syncMode);
    btn.addEventListener("click", run);
    box.addEventListener("submit", function (ev) {
      ev.preventDefault();
      run();
    });
    syncMode();
  }

  function init(scope) {
    var rootEl = scope || document;
    if (!rootEl || !rootEl.querySelectorAll) return;
    rootEl.querySelectorAll("[data-upgrade-cost]").forEach(function (box) {
      var id = box.getAttribute("data-upgrade-source");
      var data = root.TH_UPGRADE_COST;
      if (id && root[id]) data = root[id];
      if (!data) return;
      if (data.kind === "city") bindCity(box, data);
      else if (data.kind === "holybeast") bindBeast(box, data);
    });
  }

  var api = {
    init: init,
    sumCityRange: sumCityRange,
    sumBeastLevels: sumBeastLevels,
    sumBeastStars: sumBeastStars,
    fmtQty: fmtQty,
    segmentLabel: segmentLabel,
  };
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.THUpgradeCost = api;
    if (root.document) {
      if (root.document.readyState === "loading") {
        root.document.addEventListener("DOMContentLoaded", function () {
          init(root.document);
        });
      } else {
        init(root.document);
      }
    }
  }
})(typeof window !== "undefined" ? window : this);
