(function applyStoredResumePilotTheme() {
  try {
    var theme = window.localStorage.getItem("resumepilot-theme");
    if (theme === "dark" || theme === "light") {
      document.documentElement.dataset.theme = theme;
    }
  } catch {
    // System color preference remains the fallback when storage is unavailable.
  }
})();
