// Heroes browser: starter cards, filterable roster, detail modal.
(function () {
  "use strict";
  if (!window.HEROES) return;
  var H = window.HEROES;

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  var modal = document.getElementById("heroModal");
  var mArt = document.getElementById("mArt");
  var mTxt = document.getElementById("mTxt");

  function openHero(h) {
    var art = '<img src="assets/img/heroes/f/' + h.id + '.jpg" alt="Card art of ' +
      esc(h.name) + '">';
    if (h.alive) {
      art += '<video src="assets/vid/alive/' + h.alive + '" controls loop autoplay ' +
        'muted playsinline preload="metadata" aria-label="' + esc(h.name) +
        ' — the card comes alive"></video>';
    }
    mArt.innerHTML = art;
    var pal = (h.palc || []).map(function (c) {
      return '<span class="sw" style="background:' + c + '"></span>';
    }).join("");
    if (h.pal) {
      pal = '<p class="small muted">' + esc(h.pal) + "<br>" + pal + "</p>";
    }
    mTxt.innerHTML =
      "<h3>" + esc(h.name) + (h.title ? " <span class='muted'>— " + esc(h.title) + "</span>" : "") + "</h3>" +
      '<div class="chips" style="margin-bottom:14px">' +
        '<span class="chip"><b>' + esc(h.jobName) + "</b> · " + esc(h.role) + "</span>" +
        '<span class="chip">Element · <b>' + esc(h.el) + "</b></span>" +
        '<span class="chip"><b>' + esc(h.rarity) + "</b></span>" +
        (h.starter ? '<span class="chip">Starter Set</span>' : "") +
      "</div>" +
      (h.hook ? "<p><i>" + esc(h.hook) + "</i></p>" : "") +
      (h.sig ? '<p class="small muted"><b style="color:var(--cream)">Signature:</b> ' + esc(h.sig) + ".</p>" : "") +
      (h.sp ? '<p class="small" style="margin:4px 0 0"><span class="chip">' + esc(h.sp) + "</span></p>" : "") +
      (h.flav ? "<blockquote class='quote'>" + esc(h.flav) + "</blockquote>" : "") +
      pal;
    modal.classList.add("on");
  }

  modal.addEventListener("click", function (e) {
    if (e.target === modal || e.target.classList.contains("x")) {
      modal.classList.remove("on");
      mArt.innerHTML = "";
    }
  });
  document.querySelectorAll(".modal .x").forEach(function (b) {
    b.addEventListener("click", function () {
      modal.classList.remove("on");
      mArt.innerHTML = "";
    });
  });

  // ---- Starter Set ----
  var st = document.getElementById("starters");
  H.filter(function (h) { return h.starter; }).forEach(function (h) {
    var b = el("button", "scard r-" + h.rarity + " el-" + h.el);
    b.innerHTML =
      '<img src="assets/img/heroes/f/' + h.id + '.jpg" alt="Card art of ' + esc(h.name) + '" loading="lazy">' +
      '<span class="nm"><b>' + esc(h.name) + "</b><span>#" + h.n + " · " + esc(h.jobName) +
      " · " + esc(h.el) + "</span></span>" +
      '<span class="hook">' + esc(h.hook) + "</span>";
    b.addEventListener("click", function () { openHero(h); });
    st.appendChild(b);
  });

  // ---- Roster grid + filters ----
  var grid = document.getElementById("grid");
  var more = document.getElementById("more");
  var count = document.getElementById("count");
  var fJob = document.getElementById("fJob");
  var fEl = document.getElementById("fEl");
  var fRar = document.getElementById("fRar");
  var fText = document.getElementById("fText");
  var PAGE = 24;
  var shown = 0;
  var filtered = H;

  // Job dropdown, populated from the data.
  var jobs = {};
  H.forEach(function (h) { jobs[h.jobName] = (jobs[h.jobName] || 0) + 1; });
  Object.keys(jobs).sort().forEach(function (j) {
    var o = document.createElement("option");
    o.value = j; o.textContent = j + " (" + jobs[j] + ")";
    fJob.appendChild(o);
  });

  function apply() {
    var q = fText.value.trim().toLowerCase();
    filtered = H.filter(function (h) {
      if (fJob.value && h.jobName !== fJob.value) return false;
      if (fEl.value && h.el !== fEl.value) return false;
      if (fRar.value && h.rarity !== fRar.value) return false;
      if (q) {
        var hay = (h.name + " " + (h.title || "") + " " + h.sp + " " + h.jobName).toLowerCase();
        if (hay.indexOf(q) === -1) return false;
      }
      return true;
    });
    grid.innerHTML = "";
    shown = 0;
    renderMore();
  }

  function renderMore() {
    var next = filtered.slice(shown, shown + PAGE);
    next.forEach(function (h) {
      var b = el("button", "hcard r-" + h.rarity + " el-" + h.el);
      b.setAttribute("aria-label", h.name + ", " + h.jobName + " " + h.el + " " + h.rarity);
      b.innerHTML =
        '<img src="assets/img/heroes/f/' + h.id + '.jpg" alt="Card art of ' + esc(h.name) + '" loading="lazy">' +
        '<span class="dot"></span><span class="rar">' + esc(h.rarity) + "</span>" +
        '<span class="nm"><b>' + esc(h.name) + "</b><span>#" + h.n + " · " + esc(h.jobName) +
        " · " + esc(h.el) + "</span></span>";
      b.addEventListener("click", function () { openHero(h); });
      grid.appendChild(b);
    });
    shown += next.length;
    more.hidden = shown >= filtered.length;
    count.textContent = filtered.length + " heroes match · " +
      Math.min(shown, filtered.length) + " on page";
  }

  [fJob, fEl, fRar].forEach(function (s) {
    s.addEventListener("change", apply);
  });
  fText.addEventListener("input", apply);
  more.addEventListener("click", renderMore);

  apply();
})();
