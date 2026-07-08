const links = Array.from(document.querySelectorAll(".toc a"));
const sections = links
  .map((link) => document.querySelector(link.getAttribute("href")))
  .filter(Boolean);

const observer = new IntersectionObserver(
  (entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      links.forEach((link) => {
        link.classList.toggle("active", link.getAttribute("href") === `#${entry.target.id}`);
      });
    }
  },
  { rootMargin: "-20% 0px -70% 0px" }
);

sections.forEach((section) => observer.observe(section));
