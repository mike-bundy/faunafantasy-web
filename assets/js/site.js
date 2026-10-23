// Shared site behaviour: header, menus, reveals, lightbox, readable toggle.
(function () {
  "use strict";

  var bar = document.querySelector(".topbar");
  if (bar) {
    var burger = bar.querySelector(".burger");
    if (burger) {
      burger.addEventListener("click", function () {
        bar.classList.toggle("open");
      });
    }
    var onScroll = function () {
      bar.classList.toggle("solid", window.scrollY > 24);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  // Reveal-on-scroll (skipped entirely for reduced motion).
  if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches &&
      "IntersectionObserver" in window) {
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) {
            e.target.classList.add("in");
            io.unobserve(e.target);
          }
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.05 }
    );
    document.querySelectorAll(".reveal").forEach(function (el) {
      io.observe(el);
    });
  } else {
    document.querySelectorAll(".reveal").forEach(function (el) {
      el.classList.add("in");
    });
  }

  // Play videos only while on screen (battery + thermals).
  if ("IntersectionObserver" in window) {
    var vio = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (e) {
          var v = e.target;
          if (e.isIntersecting) {
            var p = v.play();
            if (p && p.catch) p.catch(function () {});
          } else {
            v.pause();
          }
        });
      },
      { threshold: 0.25 }
    );
    document.querySelectorAll("video[data-onscreen]").forEach(function (v) {
      vio.observe(v);
    });
  }

  // Lightbox for [data-lb] images and videos.
  var lb = document.createElement("div");
  lb.className = "lightbox";
  lb.setAttribute("role", "dialog");
  lb.setAttribute("aria-label", "Media viewer");
  document.body.appendChild(lb);
  var kill = function () {
    lb.classList.remove("on");
    lb.innerHTML = "";
  };
  lb.addEventListener("click", kill);
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      kill();
      var m = document.querySelector(".modal.on");
      if (m) m.classList.remove("on");
    }
  });
  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-lb]");
    if (!t) return;
    e.preventDefault();
    lb.innerHTML = "";
    var src = t.getAttribute("data-lb") || t.getAttribute("href") ||
      (t.tagName === "IMG" ? t.src : null);
    if (!src) return;
    var el;
    if (/\.(mp4|webm)(\?|$)/i.test(src)) {
      el = document.createElement("video");
      el.src = src;
      el.controls = true;
      el.autoplay = true;
      el.loop = true;
    } else {
      el = document.createElement("img");
      el.src = src;
    }
    lb.appendChild(el);
    lb.classList.add("on");
  });

  // Lock page scroll while any modal is open.
  if ("MutationObserver" in window) {
    var mo = new MutationObserver(function () {
      document.body.classList.toggle("lock",
        !!document.querySelector(".modal.on"));
    });
    document.querySelectorAll(".modal").forEach(function (m) {
      mo.observe(m, { attributes: true, attributeFilter: ["class"] });
    });
  }

  // Readable-font toggle (mirrors the game's own setting).
  var toggle = document.getElementById("readableToggle");
  if (toggle) {
    var apply = function (on) {
      document.body.classList.toggle("readable", on);
      try { localStorage.setItem("ff-readable", on ? "1" : "0"); } catch (e) {}
    };
    var saved = null;
    try { saved = localStorage.getItem("ff-readable"); } catch (e) {}
    if (saved === "1") apply(true);
    toggle.addEventListener("change", function () {
      apply(toggle.checked);
    });
  }
})();
