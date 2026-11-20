import React, { createContext, useContext, useState, useLayoutEffect } from "react";

const ThemeContext = createContext({
  theme: "light",
  toggleTheme: () => {},
  setTheme: () => {},
});

const THEME_STORAGE_KEY = "smm_theme";

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(() => {
    try {
      const saved = localStorage.getItem(THEME_STORAGE_KEY) || localStorage.getItem("color-theme");
      if (saved === "dark" || saved === "light") return saved;
      if (typeof window !== "undefined" && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
        return "dark";
      }
      return "light";
    } catch {
      return "light";
    }
  });

  const applyTheme = (t) => {
    const root = document.documentElement;
    root.setAttribute("data-theme", t);
    root.style.colorScheme = t;
    if (t === "dark") {
      root.classList.add("dark");
      if (typeof document !== "undefined" && document.body) {
        document.body.classList.add("dark");
      }
    } else {
      root.classList.remove("dark");
      if (typeof document !== "undefined" && document.body) {
        document.body.classList.remove("dark");
      }
    }
    try {
      localStorage.setItem(THEME_STORAGE_KEY, t);
      localStorage.setItem("color-theme", t);
    } catch {
      // Ignore localStorage failure
    }
  };

  useLayoutEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const toggleTheme = () => {
    setThemeState((prev) => (prev === "dark" ? "light" : "dark"));
  };

  const setTheme = (newTheme) => {
    if (newTheme === "dark" || newTheme === "light") {
      setThemeState(newTheme);
    }
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
