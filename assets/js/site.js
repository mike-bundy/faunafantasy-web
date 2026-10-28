// Shared site behaviour: AVIF fallback, header, menus, reveals, lightbox, readable toggle.
(function () {
  "use strict";

  // Stills are AVIF with a JPEG twin beside each (build.py). Browsers that can't
  // decode AVIF (Safari before 16, older Macs) get every .avif reference swapped for
  // its .jpg, including ones added later (hero cards, the modal, the lightbox).
  (function () {
    var AVIF = /\.avif(?=$|[?#])/i;
    var ATTRS = ["src", "poster", "data-lb", "href"];
    function fix(root) {
      if (!root.querySelectorAll) return;
      var list = [root].concat([].slice.call(root.querySelectorAll("img, video, a, [data-lb]")));
      list.forEach(function (el) {
        ATTRS.forEach(function (a) {
          var v = el.getAttribute && el.getAttribute(a);
          if (v && AVIF.test(v)) el.setAttribute(a, v.replace(AVIF, ".jpg"));
        });
      });
    }
    var probe = new Image();
    probe.onload = function () {
      if (probe.width > 0) return;          // decoded: AVIF works
      probe.onerror();
    };
    probe.onerror = function () {
      document.documentElement.classList.add("no-avif");
      fix(document.body);
      if ("MutationObserver" in window) {
        new MutationObserver(function (muts) {
          muts.forEach(function (m) {
            [].forEach.call(m.addedNodes, function (n) { if (n.nodeType === 1) fix(n); });
          });
        }).observe(document.body, { childList: true, subtree: true });
      }
    };
    probe.src = "data:image/avif;base64,AAAAIGZ0eXBhdmlmAAAAAE1pUHJhdmlmbWlhZm1pZjEAAAEhbWV0YQAAAAAAAAAhaGRscgAAAAAAAAAAcGljdAAAAAAAAAAAAAAAAAAAAAAkZGluZgAAABxkcmVmAAAAAAAAAAEAAAAMdXJsIAAAAAEAAAAOcGl0bQAAAAAAAQAAACNpaW5mAAAAAAABAAAAFWluZmUCAAAAAAEAAGF2MDEAAAAAgWlwcnAAAABgaXBjbwAAABNjb2xybmNseAACAAIABoAAAAAMY2xsaQDLAEAAAAAUaXNwZQAAAAAAAAACAAAAAgAAAAlpcm90AAAAABBwaXhpAAAAAAMICAgAAAAMYXYxQ4EADAAAAAAZaXBtYQAAAAAAAAABAAEGgQIDBYaEAAAAHmlsb2MAAAAARAAAAQABAAAAAQAAAVEAAAAmAAAAAW1kYXQAAAAAAAAANhIACgwAAAAABn/8CBAQNCAyFBABkgAIIIIgAGjTBoezviHWCduA";
  })();

  var bar = document.querySelector(".topbar");
  if (bar) {
    var burger = bar.querySelector(".burger");
    if (burger) {
      burger.addEventListener("click", function () {
        var open = bar.classList.toggle("open");
        burger.setAttribute("aria-expanded", open ? "true" : "false");
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

  // Play muted loops only while on screen (battery + thermals). With Reduce
  // Motion or Save-Data on, nothing autoplays: clips keep their poster and get
  // controls, and the hero reel stays a still.
  var calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
    !!(navigator.connection && navigator.connection.saveData);
  if (calm) {
    document.querySelectorAll("video[data-onscreen]").forEach(function (v) {
      v.removeAttribute("autoplay");
      v.pause();
      if (!v.hasAttribute("data-bg")) v.controls = true;
    });
  } else if ("IntersectionObserver" in window) {
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
  lb.addEventListener("click", function (e) {
    if (e.target === lb) kill();   // the backdrop or its close mark, not the media
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      kill();
      var m = document.querySelector(".modal.on");
      if (m) m.classList.remove("on");
    }
  });
  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-lb]");
    if (!t || (calm && e.target.tagName === "VIDEO")) return;
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
      el.muted = /\/vid\/(play\/|reel_)/.test(src);   // gameplay clips have no sound
      el.playsInline = true;
    } else {
      el = document.createElement("img");
      el.src = src;
      var from = t.tagName === "IMG" ? t : t.querySelector("img");
      el.alt = (from && from.getAttribute("alt")) || "";
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
