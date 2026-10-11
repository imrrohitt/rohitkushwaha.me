(function () {
  var root = document.documentElement;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------------------------------------------------------------- theme */
  var themeBtn = document.getElementById("theme-toggle");
  var systemDark = window.matchMedia("(prefers-color-scheme: dark)");

  function storedTheme() {
    try { return localStorage.getItem("theme"); } catch (e) { return null; }
  }

  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var next = root.dataset.theme === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      try { localStorage.setItem("theme", next); } catch (e) {}
    });
  }
  // Follow the OS until the visitor makes a choice.
  systemDark.addEventListener("change", function (e) {
    if (!storedTheme()) root.dataset.theme = e.matches ? "dark" : "light";
  });

  /* ---------------------------------------------------------- mobile menu */
  var menuBtn = document.getElementById("menu-toggle");
  var nav = document.getElementById("site-nav");

  function setMenu(open) {
    nav.classList.toggle("open", open);
    menuBtn.setAttribute("aria-expanded", String(open));
    menuBtn.setAttribute("aria-label", open ? "Close menu" : "Open menu");
  }

  if (menuBtn && nav) {
    menuBtn.addEventListener("click", function () { setMenu(!nav.classList.contains("open")); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && nav.classList.contains("open")) { setMenu(false); menuBtn.focus(); }
    });
    document.addEventListener("click", function (e) {
      if (nav.classList.contains("open") && !nav.contains(e.target) && !menuBtn.contains(e.target)) setMenu(false);
    });
  }

  /* ------------------------------------------- header hairline + progress */
  var header = document.getElementById("site-header");
  var bar = document.getElementById("progress-bar");
  var article = document.querySelector(".post .prose");
  var ticking = false;

  function onScroll() {
    var y = window.scrollY;
    if (header) header.classList.toggle("scrolled", y > 8);
    if (bar && article) {
      var rect = article.getBoundingClientRect();
      var total = rect.height - window.innerHeight * 0.6;
      var done = Math.min(1, Math.max(0, -rect.top / Math.max(total, 1)));
      bar.style.transform = "scaleX(" + done + ")";
    }
    ticking = false;
  }
  window.addEventListener("scroll", function () {
    if (!ticking) { ticking = true; requestAnimationFrame(onScroll); }
  }, { passive: true });
  onScroll();

  /* -------------------------------------------------------- scroll reveal */
  var revealables = document.querySelectorAll("[data-reveal]");

  function settle(el) {
    // Once revealed, drop the reveal styles so the card's own hover transitions take over.
    el.addEventListener("transitionend", function done(e) {
      if (e.target !== el || e.propertyName !== "transform") return;
      el.removeEventListener("transitionend", done);
      el.removeAttribute("data-reveal");
      el.classList.remove("in");
    });
  }

  function reveal(el) {
    el.classList.add("in");
    settle(el);
  }

  if ("IntersectionObserver" in window && !reduceMotion) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { reveal(entry.target); io.unobserve(entry.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    revealables.forEach(function (el) { io.observe(el); });
  } else {
    revealables.forEach(function (el) { el.classList.add("in"); el.removeAttribute("data-reveal"); });
  }

  /* -------------------------------------------- cursor spotlight on cards */
  if (window.matchMedia("(hover: hover)").matches) {
    document.addEventListener("pointermove", function (e) {
      var card = e.target.closest && e.target.closest(".card");
      if (!card) return;
      var r = card.getBoundingClientRect();
      card.style.setProperty("--mx", (e.clientX - r.left) + "px");
      card.style.setProperty("--my", (e.clientY - r.top) + "px");
    }, { passive: true });
  }

  /* --------------------------------------------------- local time (Pune) */
  var clocks = document.querySelectorAll("[data-clock]");
  if (clocks.length && window.Intl) {
    var fmt = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone: "Asia/Kolkata" });
    var tick = function () {
      var text = fmt.format(new Date()) + " IST";
      clocks.forEach(function (c) { c.textContent = text; });
    };
    tick();
    setInterval(tick, 30000);
  }
})();
