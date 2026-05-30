const path = require("path");
const { app, BrowserWindow } = require("electron");

const DEV_SERVER_URL = "http://localhost:5173";
const isDev = !app.isPackaged;

function loadDevServer(win, attempt = 0) {
  const maxAttempts = 30;
  win.loadURL(DEV_SERVER_URL).catch(() => {
    if (attempt >= maxAttempts) {
      console.error(
        `Could not reach Vite dev server at ${DEV_SERVER_URL} after ${maxAttempts} attempts.`
      );
      return;
    }
    setTimeout(() => loadDevServer(win, attempt + 1), 1000);
  });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    // alwaysOnTop: true,
    // frame: false,
    transparent: false,
    // skipTaskbar: true,
  });

  win.setContentProtection(true);

  if (isDev) {
    // Retry on load failures too (e.g. dev server restart).
    win.webContents.on("did-fail-load", () => loadDevServer(win));
    loadDevServer(win);
  } else {
    win.loadFile(path.join(__dirname, "..", "react-app", "dist", "index.html"));
  }
}

app.whenReady().then(createWindow);
