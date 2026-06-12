# 🛡️ Talos Tactical Sentinel

A lightweight, local stealth background application designed to dynamically monitor system states, process logs, and terminal anomalies via low-overhead window tracking. 

Talos runs silently in the system tray, utilizing an optimized, single-file compiled structure that completely eliminates open local network ports or heavy background web service architectures, maintaining near 0% CPU footprint.

---

## 🎯 Key Features

* **Zero-Overhead Active Tracking:** Rebuilt engine that strips out continuous database polling loops, keeping memory and CPU consumption virtually at zero.
* **Smart Keyword Isolation:** Automated screenshot capture triggered exclusively by specified terminal or process window title alterations.
* **Native Desktop Shell:** Compiled via an explicit custom container layout that does not require background Python interpreters or command windows to remain visible.
* **Clean Session State:** Local configuration files and execution build artifacts are entirely ignored to ensure a clean deployment every single run.

---

## 📂 Project Architecture

```text
talos-sentinel/
├── requirements.txt      # Required Python modules
├── talos_app.py          # Main application source code
├── install.bat           # Automated local setup script
└── .gitignore            # Development cache filters
