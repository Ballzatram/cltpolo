const navToggle = document.querySelector(".nav-toggle");
const siteNav = document.querySelector(".site-nav");

if (navToggle && siteNav) {
  navToggle.addEventListener("click", () => {
    siteNav.classList.toggle("open");
  });
}

const contactForm = document.getElementById("contactForm");

if (contactForm) {
  contactForm.addEventListener("submit", (event) => {
    event.preventDefault();

    const name = document.getElementById("name")?.value.trim();
    const email = document.getElementById("email")?.value.trim();
    const interest = document.getElementById("interest")?.value;
    const message = document.getElementById("message")?.value.trim();

    if (!name || !email || !interest || !message) {
      alert("Please complete all required fields.");
      return;
    }

    alert(
      "Thanks — your inquiry form is set up visually. Next step is connecting it to a real form handler."
    );

    contactForm.reset();
  });
}