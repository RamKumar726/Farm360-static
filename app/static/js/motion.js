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
