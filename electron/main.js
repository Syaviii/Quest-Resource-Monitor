/**
 * VR System Monitor - Electron Main
 * bootstraps the window and python backend.
 */

const { app, BrowserWindow, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow = null;
let backendProcess = null;

// Configuration
const BACKEND_PORT = 5000;
const FRONTEND_PATH = path.join(__dirname, '..', 'frontend', 'index.html');
const BACKEND_PATH = path.join(__dirname, '..', 'backend', 'app.py');

/**
 * Create the main application window
 */
function createWindow() {
  // make the window
  const mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#0a0a0a',
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      backgroundThrottling: false // keep running in background
    },
    titleBarStyle: 'default',
    show: false // Don't show until ready
  });

    // Remove menu bar (optional)
    mainWindow.setMenuBarVisibility(false);

    // Load the frontend
    mainWindow.loadFile(FRONTEND_PATH);

    // Show window when ready
    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
    });

    // Open external links in default browser
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        shell.openExternal(url);
        return { action: 'deny' };
    });

    // Handle window close
    mainWindow.on('closed', () => {
        mainWindow = null;
    });

    // Open DevTools in development
    if (process.argv.includes('--dev')) {
        mainWindow.webContents.openDevTools();
    }
}

/**
 * Start the Python backend process
 */
function startBackend() {
    return new Promise((resolve, reject) => {
        console.log('starting backend...');
        
        // Determine Python command (python3 on macOS/Linux, python on Windows)
        const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
        
        // Check if running from venv
        const pythonPath = path.join(path.dirname(BACKEND_PATH), 'venv', 'Scripts', 'python.exe');
        const actualPython = require('fs').existsSync(pythonPath) ? pythonPath : pythonCmd;
        
        console.log(`Using Python: ${actualPython}`);
        
        backendProcess = spawn(actualPython, [BACKEND_PATH], {
            cwd: path.dirname(BACKEND_PATH),
            stdio: ['pipe', 'pipe', 'pipe'],
            env: { ...process.env, PYTHONUNBUFFERED: '1' } // Ensure output isn't buffered
        });

        let startupTimeout = setTimeout(() => {
            console.log('Backend startup timeout reached, checking health...');
            resolve(); // Continue anyway, waitForBackend will verify
        }, 8000); // Give Flask 8 seconds to start

        backendProcess.stdout.on('data', (data) => {
            console.log(`backend: ${data}`);
            // Check if server is ready
            if (data.toString().includes('Running on') || data.toString().includes('Server ready')) {
                clearTimeout(startupTimeout);
                resolve();
            }
        });

        backendProcess.stderr.on('data', (data) => {
            console.error(`backend error: ${data}`);
            // Flask often logs to stderr, check for ready signal there too
            if (data.toString().includes('Running on') || data.toString().includes('Server ready')) {
                clearTimeout(startupTimeout);
                resolve();
            }
        });

        backendProcess.on('error', (error) => {
            console.error('Failed to start backend:', error);
            clearTimeout(startupTimeout);
            reject(error);
        });

        backendProcess.on('close', (code) => {
            console.log(`backend died with code ${code}`);
            clearTimeout(startupTimeout);
            if (code !== 0 && code !== null) {
                reject(new Error(`Backend exited with code ${code}`));
            }
            backendProcess = null;
        });
    });
}

/**
 * Stop the backend process
 */
function stopBackend() {
    if (backendProcess) {
        console.log('Stopping backend...');
        backendProcess.kill('SIGTERM');
        backendProcess = null;
    }
}

/**
 * Wait for backend to be ready
 */
async function waitForBackend(maxAttempts = 60) {
    const http = require('http');
    
    console.log('Waiting for backend to be ready...');
    
    for (let i = 0; i < maxAttempts; i++) {
        try {
            await new Promise((resolve, reject) => {
                const req = http.get(`http://localhost:${BACKEND_PORT}/health`, (res) => {
                    if (res.statusCode === 200) {
                        resolve();
                    } else {
                        reject(new Error(`Status ${res.statusCode}`));
                    }
                });
                req.on('error', reject);
                req.setTimeout(2000, () => {
                    req.destroy();
                    reject(new Error('Timeout'));
                });
            });
            console.log(`Backend ready after ${i + 1} attempts`);
            return true;
        } catch (e) {
            if (i % 10 === 0) {
                console.log(`Waiting for backend... (attempt ${i + 1}/${maxAttempts})`);
            }
            await new Promise(r => setTimeout(r, 500)); // Check every 500ms
        }
    }
    console.error('Backend failed to start after max attempts');
    return false;
}

// App lifecycle
app.whenReady().then(async () => {
    try {
        // Start backend first
        await startBackend();
        
        // Wait for backend to be ready
        const ready = await waitForBackend();
        if (!ready) {
            console.error('Backend failed to start');
        }
        
        // Create window
        createWindow();
    } catch (error) {
        console.error('Startup error:', error);
        app.quit();
    }
});

app.on('window-all-closed', () => {
    stopBackend();
    // quit when all windows are closed, except on mac
    if (process.platform !== 'darwin') app.quit()
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});

app.on('before-quit', () => {
    stopBackend();
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
    console.error('Uncaught exception:', error);
    stopBackend();
});
