const { app, BrowserWindow } = require("electron");

function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    // alwaysOnTop: true,
    // frame: false,
    transparent: false,
    // skipTaskbar: true,
  });

  win.loadURL("http://localhost:5173");
}

app.whenReady().then(createWindow);
