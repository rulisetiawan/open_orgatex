import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import { ThemeProvider } from './context/ThemeContext.jsx';
import './styles/tail-admin.css';
import './styles/motion.css';
import './index.css';

// Initialize theme immediately to prevent flashing
try {
  const savedTheme = localStorage.getItem("smm_theme") || localStorage.getItem("color-theme");
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  const initialTheme = savedTheme || (prefersDark ? "dark" : "light");
  document.documentElement.setAttribute("data-theme", initialTheme);
  document.documentElement.style.colorScheme = initialTheme;
  if (initialTheme === "dark") {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }
} catch {
  document.documentElement.setAttribute("data-theme", "light");
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </React.StrictMode>,
);
