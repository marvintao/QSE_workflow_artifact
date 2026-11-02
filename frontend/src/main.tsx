// Copyright (c) 2026 QJump.ai
// SPDX-License-Identifier: MIT

/**
 * Application entry point.
 * Mounts the root App component onto the DOM node with id "root" and enables React strict mode.
 */
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { LanguageProvider } from "./i18n/LanguageProvider";
import "./styles/globals.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <LanguageProvider>
      <App />
    </LanguageProvider>
  </React.StrictMode>
);
