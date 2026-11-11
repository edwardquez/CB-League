/* CB League figure motion.
   Runs once in the page (page.py puts it there). Three jobs:
   1. Scroll: every figure block (.cb) waits, frozen on its first frame, until it scrolls into view, then plays.
   2. Replay: when a filter, tab, mode or map changes what a figure shows, that figure plays again from the start.
   3. Charts: Plotly charts draw in the way the design did (lines draw left to right, dots pop, bars grow,
      the radar unfolds), again only once on screen and again whenever their data changes.
   With "reduce motion" switched on in the device settings, none of this runs and everything shows at once. */
(function () {
  if (window.__cbMotion) return;
  window.__cbMotion = true;
  var D = document, R = D.documentElement;
  if (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  if (!("IntersectionObserver" in window) || !("MutationObserver" in window)) return;
  R.classList.add("cbm-js");

  var ANIM = ".cu,.cb-grow,.cb-rise,.cb-gx,.cb-gxc,.cb-gy,.cb-gyd,.cb-cellin,.cb-pop,.cb-dslide,.cb-pslide,.cb-fadein,.cb-bal,.cb-tnst,.cb-tnwin,.cb-strip";

  /* ---------- 1 + 2: HTML figures ---------- */
  var seen = new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      if (!e.isIntersecting) return;
      seen.unobserve(e.target);
      e.target.classList.add("cbm-on");
    });
  }, { rootMargin: "0px 0px -6% 0px", threshold: 0 });

  function arm(b) {                      // freeze on the first frame, restart, and wait to be seen
    if (!b.querySelector(ANIM)) { b.classList.add("cbm-on"); return; }
    b.classList.remove("cbm-on");
    b.classList.add("cbm-reset");
    void b.offsetWidth;                  // let the browser drop the old animations
    b.classList.remove("cbm-reset");
    seen.unobserve(b);
    seen.observe(b);
  }

  /* ---------- 3: Plotly charts ---------- */
  var plotSeen = new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      var gd = e.target;
      gd.__cbmVisible = e.isIntersecting;
      if (e.isIntersecting && gd.getAttribute("data-cbm") === "wait") playPlot(gd);
    });
  }, { rootMargin: "0px 0px -6% 0px", threshold: 0 });

  function sig(gd) {
    try {
      var s = JSON.stringify((gd.data || []).map(function (t) {
        return [t.type, t.x, t.y, t.r, t.theta, t.z, t.visible];
      }));
      var h = 0;
      for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
      return s.length + ":" + h;
    } catch (err) { return String(Math.random()); }
  }

  function onPlot(gd) {
    var k = sig(gd);
    if (k === gd.__cbmSig) return;       // same data (a resize or a theme repaint): leave it alone
    gd.__cbmSig = k;
    gd.setAttribute("data-cbm", "wait");
    if (gd.__cbmVisible) requestAnimationFrame(function () { playPlot(gd); });
  }

  function anim(el, frames, opts) {
    try { return el.animate(frames, Object.assign({ fill: "backwards" }, opts)); } catch (err) { return null; }
  }

  function playPlot(gd) {
    gd.removeAttribute("data-cbm");
    var ease = "cubic-bezier(.16,.8,.2,1)";
    // lines draw in, left to right
    gd.querySelectorAll(".scatterlayer .trace path.js-line").forEach(function (p, i) {
      var len = 0;
      try { len = p.getTotalLength(); } catch (err) {}
      if (!len) return;
      var dash = getComputedStyle(p).strokeDasharray;
      if (dash && dash !== "none") {     // dashed lines keep their dashes and fade in instead
        anim(p, [{ opacity: 0 }, { opacity: 1 }], { duration: 900, delay: 150 + i * 60, easing: "ease" });
        return;
      }
      anim(p, [{ strokeDasharray: len + " " + len, strokeDashoffset: len },
               { strokeDasharray: len + " " + len, strokeDashoffset: 0 }],
           { duration: 1800, delay: i * 60, easing: "cubic-bezier(.3,.6,.2,1)" });
    });
    // filled areas fade in under their lines
    gd.querySelectorAll(".scatterlayer .trace path.js-fill").forEach(function (p) {
      anim(p, [{ opacity: 0 }, { opacity: 1 }], { duration: 900, delay: 400, easing: "ease" });
    });
    // dots pop in, one after another
    var pts = gd.querySelectorAll(".cartesianlayer .scatterlayer .trace .points path");
    var n = pts.length;
    // Plotly places each dot with its own translate(x,y). An animated transform replaces that, so the move is kept in
    // every frame; without it the dots start in the chart's top-left corner and jump into place.
    function placed(el) {
      var m = /translate\(\s*([-\d.e]+)[ ,]+([-\d.e]+)\s*\)/.exec(el.getAttribute("transform") || "");
      return m ? "translate(" + m[1] + "px," + m[2] + "px) " : "";
    }
    pts.forEach(function (p, i) {
      var at = placed(p);
      p.style.transformBox = "fill-box"; p.style.transformOrigin = "center";   // each dot is drawn around its own 0,0
      anim(p, [{ transform: at + "scale(0)", opacity: 0 }, { transform: at + "scale(1)", opacity: 1 }],
           { duration: 700, delay: 200 + Math.min(1000 * i / Math.max(n, 1), 1000), easing: "cubic-bezier(.2,1.4,.4,1)" });
    });
    // the initials written on the dots fade in once their dot has landed
    gd.querySelectorAll(".cartesianlayer .scatterlayer .trace .text text").forEach(function (t, i, all) {
      anim(t, [{ opacity: 0 }, { opacity: 1 }],
           { duration: 400, delay: 500 + Math.min(1000 * i / Math.max(all.length, 1), 1000), easing: "ease" });
    });
    // bars grow from the zero line
    var horiz = {};
    (gd._fullData || []).forEach(function (t) { if (t.type === "bar") horiz[t.index] = t.orientation === "h"; });
    gd.querySelectorAll(".barlayer .trace").forEach(function (tr, ti) {
      var h = false;
      try { h = !!horiz[tr.__data__[0].trace.index]; } catch (err) {}
      tr.querySelectorAll(".point path").forEach(function (p, i) {
        var neg = false;
        try { neg = (p.parentNode.__data__ || p.__data__).s < 0; } catch (err) {}
        p.style.transformBox = "fill-box";
        p.style.transformOrigin = h ? (neg ? "right center" : "left center") : (neg ? "center top" : "center bottom");
        anim(p, [{ transform: h ? "scaleX(0)" : "scaleY(0)" }, { transform: "none" }],
             { duration: 1200, delay: Math.min(i * 40, 800), easing: ease });
      });
    });
    // radar shapes unfold from the middle
    gd.querySelectorAll(".polarlayer .polar").forEach(function (pl) {
      var bg = pl.querySelector(".bglayer path, .bg path") || pl;
      var svg = gd.querySelector("svg.main-svg");
      if (!svg) return;
      var a = bg.getBoundingClientRect(), o = svg.getBoundingClientRect();
      var cx = a.left - o.left + a.width / 2, cy = a.top - o.top + a.height / 2;
      gd.querySelectorAll(".polarlayer .trace").forEach(function (tr) {
        tr.style.transformBox = "view-box"; tr.style.transformOrigin = cx + "px " + cy + "px";
        anim(tr, [{ transform: "scale(0) rotate(-25deg)", opacity: 0 }, { transform: "none", opacity: 1 }],
             { duration: 1300, delay: 200, easing: ease });
      });
    });
    // heat grids and shaded bands fade in
    gd.querySelectorAll(".heatmaplayer, .shapelayer").forEach(function (el) {
      anim(el, [{ opacity: 0 }, { opacity: 1 }], { duration: 1000, easing: "ease" });
    });
    // anything else drawn as a trace (box plots and such) fades in
    gd.querySelectorAll(".boxlayer .trace, .violinlayer .trace").forEach(function (el) {
      anim(el, [{ opacity: 0 }, { opacity: 1 }], { duration: 900, easing: "ease" });
    });
  }

  function hook(gd) {
    if (gd.__cbmHooked) return;
    if (typeof gd.on !== "function" || !gd._fullLayout) return;   // not drawn yet; the next scan picks it up
    gd.__cbmHooked = true;
    plotSeen.observe(gd);
    gd.on("plotly_afterplot", function () { onPlot(gd); });
    onPlot(gd);
  }

  /* ---------- watching the page ---------- */
  var pending = new Set(), queued = false;
  function flush() {
    queued = false;
    pending.forEach(arm);
    pending.clear();
    D.querySelectorAll(".js-plotly-plot").forEach(hook);
  }
  function queue(b) { if (b) pending.add(b); if (!queued) { queued = true; requestAnimationFrame(flush); } }

  new MutationObserver(function (recs) {
    recs.forEach(function (r) {
      var t = r.target.nodeType === 1 ? r.target : r.target.parentElement;
      if (!t) return;
      if (r.type === "attributes" && t.classList && t.classList.contains("cb")) return;   // our own class changes
      if (t.closest && t.closest(".js-plotly-plot")) { queue(null); return; }
      if (r.type === "childList") {
        r.addedNodes.forEach(function (nd) {
          if (nd.nodeType !== 1) return;
          if (nd.classList.contains("cb")) queue(nd);
          nd.querySelectorAll && nd.querySelectorAll(".cb").forEach(queue);
          if (nd.querySelector && nd.querySelector(".js-plotly-plot")) queue(null);
        });
      }
      var b = t.closest && t.closest(".cb");
      if (b && !(r.type === "attributes" && t.closest(".cb-tip"))) queue(b);
    });
  }).observe(D.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ["style", "class"] });

  D.querySelectorAll(".cb").forEach(queue);
  setInterval(function () { D.querySelectorAll(".js-plotly-plot").forEach(hook); }, 1200);
})();