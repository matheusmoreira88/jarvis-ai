const languageToggle = document.querySelector("#language-toggle");

function applyLanguage(language) {
  const isEnglish = language === "en";
  document.documentElement.lang = isEnglish ? "en" : "pt-BR";
  document.querySelectorAll("[data-pt][data-en]").forEach((element) => {
    element.textContent = element.dataset[language];
  });
  document.title = isEnglish
    ? "JARVIS AI — Desktop assistant"
    : "JARVIS AI — Assistente desktop";
  languageToggle.textContent = isEnglish ? "PT" : "EN";
  languageToggle.setAttribute(
    "aria-label",
    isEnglish ? "Mudar para português" : "Switch to English",
  );
  localStorage.setItem("jarvis-site-language", language);
}

languageToggle.addEventListener("click", () => {
  applyLanguage(document.documentElement.lang.startsWith("en") ? "pt" : "en");
});

const savedLanguage = localStorage.getItem("jarvis-site-language");
const browserLanguage = navigator.language.toLowerCase().startsWith("pt") ? "pt" : "en";
applyLanguage(savedLanguage === "en" || savedLanguage === "pt" ? savedLanguage : browserLanguage);
