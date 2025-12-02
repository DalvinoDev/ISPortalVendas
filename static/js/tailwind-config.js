// static/js/tailwind-config.js
window.tailwind = window.tailwind || {};
window.tailwind.config = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        primary: "#00C247",
        "background-light": "#FFFFFF",
        "background-dark": "#121212",
        "foreground-light": "#1F2937",
        "foreground-dark": "#F9FAFB",
        "input-light": "#F3F4F6",
        "input-dark": "#374151",
        "button-secondary-light": "#D1D5DB",
        "button-secondary-dark": "#4B5563",
        "button-secondary-text-light": "#1F2937",
        "button-secondary-text-dark": "#F9FAFB"
      },
      fontFamily: { display: ["Inter", "sans-serif"] },
      borderRadius: { DEFAULT: "1.5rem" }
    }
  }
};