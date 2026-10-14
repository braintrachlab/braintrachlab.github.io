// TrachLab — interactions
(function () {
  // Header border on scroll
  const header = document.querySelector(".site-header");
  const onScroll = () => header && header.classList.toggle("scrolled", window.scrollY > 10);
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  // Mobile menu
  const toggle = document.querySelector(".nav-toggle");
  const links = document.querySelector(".nav-links");
  if (toggle && links) {
    toggle.addEventListener("click", () => {
      const open = links.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open);
    });
  }

  // Highlight current page in the menu
  const page = location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".nav-links a").forEach((a) => {
    if (a.getAttribute("href") === page) a.classList.add("active");
  });

  // Hero: inject the brain line drawing and animate each fibre
  // Animation speed: "site.animation_speed" in content/texts.txt (1 = original pace, 0.75 = a bit faster)
  const speedP = fetch("content/texts.txt", { cache: "no-cache" }).then((r) => r.text()).then((t) => {
    const m = t.match(/^\s*site\.animation_speed\s*:\s*([0-9.]+)/m);
    const v = m ? parseFloat(m[1]) : NaN;
    return v > 0.1 && v < 5 ? v : 0.75;
  }).catch(() => 0.75);
  document.querySelectorAll("[data-brain]").forEach((box) => {
    Promise.all([fetch(box.dataset.brain).then((r) => r.text()), speedP]).then(([svg, ANIMATION_SPEED]) => {
      box.innerHTML = svg;
      box.querySelectorAll("path").forEach((p) => {
        p.style.setProperty("--len", Math.ceil(p.getTotalLength()) + 1);
        p.style.setProperty("--delay", (p.dataset.delay || 0) * ANIMATION_SPEED + "s");
        p.style.setProperty("--dur", (p.dataset.dur || 2) * ANIMATION_SPEED + "s");
      });
      box.querySelectorAll("image.plate-tint").forEach((im) => {
        const d = parseFloat(getComputedStyle(im).getPropertyValue("--tint-delay")) || 2;
        im.style.setProperty("--tint-delay", d * ANIMATION_SPEED + "s");
      });
      // start drawing when the figure scrolls into view
      if ("IntersectionObserver" in window) {
        const io = new IntersectionObserver((es) => {
          if (es.some((e) => e.isIntersecting)) { box.classList.add("ready"); io.disconnect(); }
        }, { threshold: 0.25 });
        io.observe(box);
      } else box.classList.add("ready");
    });
  });

  // Reveal elements as they scroll into view
  const reveals = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add("visible");
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.15, rootMargin: "0px 0px -40px 0px" });
    reveals.forEach((el) => io.observe(el));
  } else {
    reveals.forEach((el) => el.classList.add("visible"));
  }

  // Gentle parallax on images marked with data-speed
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const para = document.querySelectorAll("[data-speed]");
  if (!reduce && para.length) {
    const update = () => {
      para.forEach((el) => {
        const r = el.parentElement.getBoundingClientRect();
        const offset = (r.top + r.height / 2 - window.innerHeight / 2) * parseFloat(el.dataset.speed);
        el.style.transform = `translateY(${offset}px) scale(1.15)`;
      });
    };
    window.addEventListener("scroll", () => requestAnimationFrame(update), { passive: true });
    update();
  }

  // Publication filters
  const buttons = document.querySelectorAll(".filters button");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const f = btn.dataset.filter;
      document.querySelectorAll(".pub").forEach((p) => {
        p.classList.toggle("hidden", f !== "all" && !p.dataset.topic.includes(f));
      });
      document.querySelectorAll(".pub-group").forEach((g) => {
        g.style.display = g.querySelector(".pub:not(.hidden)") ? "" : "none";
      });
    });
  });

  // Team member panels
  const panel = document.getElementById("member-panel");
  if (panel) {
    const body = panel.querySelector(".member-body");
    document.querySelectorAll("[data-member]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const tpl = document.getElementById(btn.dataset.member);
        body.innerHTML = tpl ? tpl.innerHTML : "";
        if (panel.showModal) panel.showModal(); else panel.setAttribute("open", "");
      });
    });
    panel.querySelector(".close").addEventListener("click", () => panel.close());
    panel.addEventListener("click", (e) => {
      const r = panel.getBoundingClientRect();
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) panel.close();
    });
  }

  // Footer year
  const y = document.getElementById("year");
  if (y) y.textContent = new Date().getFullYear();
})();
