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
  document.querySelectorAll("[data-brain]").forEach((box) => {
    fetch(box.dataset.brain).then((r) => r.text()).then((svg) => {
      box.innerHTML = svg;
      box.querySelectorAll("path").forEach((p) => {
        p.style.setProperty("--len", Math.ceil(p.getTotalLength()) + 1);
        p.style.setProperty("--delay", (p.dataset.delay || 0) + "s");
        p.style.setProperty("--dur", (p.dataset.dur || 2) + "s");
      });
      box.classList.add("ready");
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

  // Footer year
  const y = document.getElementById("year");
  if (y) y.textContent = new Date().getFullYear();
})();
