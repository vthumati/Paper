import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./auth";
import PromptHost from "./components/Prompt";
import ToastHost from "./components/Toast";
import "./styles.css";

// Apply the saved theme (or the OS preference) before first paint.
const savedTheme = localStorage.getItem("paper_theme");
document.documentElement.dataset.theme =
  savedTheme || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
        <PromptHost />
        <ToastHost />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);
