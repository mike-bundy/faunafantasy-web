// Heroes page: the four starters and their detail modal. Everyone else stays in the packs.
(function () {
  "use strict";
  if (!window.HEROES) return;
  var H = window.HEROES;

  // What each starter does for your party, in a line (the game's own hooks wait in the modal).
  var INTRO = {
    rowan_ashford: "The front line. Rowan stands in front so the other three don't have to.",
    hazel_acornshot: "The archer. Hazel picks enemies off from a distance, and hits harder from higher ground.",
    ember_pike: "The fire mage. Ember's spells hit hard from the back row, so keep him there.",
    clover_softpaw: "The healer. Clover keeps the others on their feet, and hops toward trouble, not away from it."
  };

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
    var poster = "assets/img/heroes/f/" + h.id + ".avif";
    // One piece of art: the moving card when there is one (its poster is the still), else the still.
    // Both at once sat side by side and pushed over the text.
    mArt.innerHTML = h.alive
      ? '<video src="assets/vid/alive/' + h.alive + '" poster="' + poster + '" loop autoplay muted playsinline ' +
        'aria-label="' + esc(h.name) + "'s card, moving\"></video>"
      : '<img src="' + poster + '" alt="Card art of ' + esc(h.name) + '">';
    mTxt.innerHTML =
      "<h3>" + esc(h.name) + "</h3>" +
      '<div class="chips" style="margin-bottom:14px">' +
        '<span class="chip"><b>' + esc(h.jobName) + "</b></span>" +
        '<span class="chip"><b>' + esc(h.el) + "</b></span>" +
      "</div>" +
      "<p>" + esc(INTRO[h.id] || h.hook) + "</p>" +
      (h.sig ? '<p class="small muted"><b style="color:var(--cream)">On the card:</b> ' + esc(h.sig) + ".</p>" : "") +
      (h.flav ? "<blockquote class='quote'>" + esc(h.flav) + "</blockquote>" : "");
    modal.classList.add("on");
  }

  function close() {
    modal.classList.remove("on");
    mArt.innerHTML = "";
  }
  modal.addEventListener("click", function (e) {
    if (e.target === modal) close();
  });
  modal.querySelector(".x").addEventListener("click", close);

  var st = document.getElementById("starters");
  H.filter(function (h) { return h.starter; }).forEach(function (h) {
    var b = el("button", "scard r-" + h.rarity + " el-" + h.el);
    b.innerHTML =
      '<img src="assets/img/heroes/f/' + h.id + '.avif" alt="Card art of ' + esc(h.name) + '" loading="lazy">' +
      '<span class="nm"><b>' + esc(h.name) + "</b><span>" + esc(h.jobName) + " · " + esc(h.el) + "</span></span>" +
      '<span class="hook">' + esc(INTRO[h.id] || h.hook) + "</span>";
    b.addEventListener("click", function () { openHero(h); });
    st.appendChild(b);
  });
})();
