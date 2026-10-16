(() => {
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
