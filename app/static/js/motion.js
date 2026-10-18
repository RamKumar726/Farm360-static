(() => {
  document.querySelectorAll("[data-quote-calculator]").forEach((calculator) => {
    const base = calculator.querySelector('[name="base_price"]');
    const discount = calculator.querySelector('[name="discount_amount"]');
    const total = calculator.querySelector("[data-quote-total]");
    if (!base || !discount || !total) return;

    const currency = new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 2,
    });
    const update = () => {
      const quoted = Number.parseFloat(base.value) || 0;
      const reduction = Number.parseFloat(discount.value) || 0;
      total.textContent = reduction > quoted
        ? "Discount exceeds quote"
        : currency.format(quoted - reduction);
    };
    base.addEventListener("input", update);
    discount.addEventListener("input", update);
    update();
  });

  document.querySelectorAll("[data-carousel]").forEach((carousel) => {
    const track = carousel.querySelector(".carousel-track");
    const previous = carousel.querySelector("[data-carousel-prev]");
    const next = carousel.querySelector("[data-carousel-next]");
    if (!track || !previous || !next) return;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "auto"
      : "smooth";

    const stepSize = () => {
      const card = track.querySelector(":scope > *");
      if (!card) return track.clientWidth;
      const gap = Number.parseFloat(getComputedStyle(track).columnGap) || 0;
      return card.getBoundingClientRect().width + gap;
    };

    previous.addEventListener("click", () => {
      track.scrollBy({ left: -stepSize(), behavior: motion });
    });
    next.addEventListener("click", () => {
      track.scrollBy({ left: stepSize(), behavior: motion });
    });
    track.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      track.scrollBy({
        left: (event.key === "ArrowRight" ? 1 : -1) * stepSize(),
        behavior: motion,
      });
    });
  });

  document.querySelectorAll("[data-image-carousel]").forEach((carousel) => {
    const slides = Array.from(carousel.querySelectorAll(".image-carousel-slide"));
    const currentLabel = carousel.querySelector("[data-image-current]");
    if (slides.length < 2) return;

    let activeIndex = Math.max(0, slides.findIndex((slide) => slide.classList.contains("is-active")));
    let timer = null;
    let inView = false;
    let paused = false;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const showSlide = (index) => {
      activeIndex = (index + slides.length) % slides.length;
      slides.forEach((slide, slideIndex) => {
        const active = slideIndex === activeIndex;
        slide.classList.toggle("is-active", active);
        slide.setAttribute("aria-hidden", String(!active));
      });
      if (currentLabel) currentLabel.textContent = String(activeIndex + 1).padStart(2, "0");
    };
    const stop = () => {
      if (timer) window.clearInterval(timer);
      timer = null;
    };
    const start = () => {
      if (reducedMotion || !inView || paused || document.hidden || timer) return;
      timer = window.setInterval(() => showSlide(activeIndex + 1), 1000);
    };

    carousel.addEventListener("pointerenter", () => { paused = true; stop(); });
    carousel.addEventListener("pointerleave", () => { paused = false; start(); });
    carousel.addEventListener("focusin", () => { paused = true; stop(); });
    carousel.addEventListener("focusout", (event) => {
      if (carousel.contains(event.relatedTarget)) return;
      paused = false;
      start();
    });
    document.addEventListener("visibilitychange", () => document.hidden ? stop() : start());

    if ("IntersectionObserver" in window) {
      const observer = new IntersectionObserver((entries) => {
        inView = entries[0].isIntersecting;
        if (inView) start(); else stop();
      }, { threshold: 0.15 });
      observer.observe(carousel);
    } else {
      inView = true;
      start();
    }
  });

  const targets = document.querySelectorAll(
    "[data-reveal], .section-heading, .about-copy, .about-image, .process-step, .portfolio-card",
  );

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  if (!("IntersectionObserver" in window)) return;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    },
    { threshold: 0.12, rootMargin: "0px 0px -32px 0px" },
  );

  targets.forEach((target) => {
    target.classList.add("reveal");
    observer.observe(target);
  });
})();
