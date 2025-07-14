const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

let mainWindow;
let pythonProcess;
const BACKEND_PORT = 5000;

/**
 * Start the Python backend server
 */
function startPythonBackend() {
    console.log('Starting Python backend server...');
    
    try {
        // Try to start Python backend
        pythonProcess = spawn('python', [
            path.join(__dirname, 'backend', 'main.py'),
            '--host', '127.0.0.1',
            '--port', BACKEND_PORT.toString()
        ], {
            stdio: ['ignore', 'pipe', 'pipe']
        });

        pythonProcess.stdout.on('data', (data) => {
            console.log(`Python Backend: ${data.toString()}`);
        });

        pythonProcess.stderr.on('data', (data) => {
            console.error(`Python Backend Error: ${data.toString()}`);
        });

        pythonProcess.on('close', (code) => {
            console.log(`Python backend process exited with code ${code}`);
            if (code !== 0) {
                console.error('Python backend crashed');
                // Optionally restart or show error to user
            }
        });

        pythonProcess.on('error', (error) => {
            console.error('Failed to start Python backend:', error);
            // Show error dialog to user
            const { dialog } = require('electron');
            dialog.showErrorBox(
                'Backend Error',
                'Failed to start Python backend. Please ensure Python is installed and dependencies are available.'
            );
        });

        return true;
    } catch (error) {
        console.error('Error starting Python backend:', error);
        return false;
    }
}

/**
 * Check if backend is ready
 */
async function waitForBackend(maxAttempts = 30) {
    const fetch = require('node-fetch');
    
    for (let i = 0; i < maxAttempts; i++) {
        try {
            const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/status`);
            if (response.ok) {
                console.log('Python backend is ready');
                return true;
            }
        } catch (error) {
            // Backend not ready yet, wait and retry
            await new Promise(resolve => setTimeout(resolve, 1000));
        }
    }
    
    console.error('Backend failed to start within timeout');
    return false;
}

/**
 * Create the main application window
 */
function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        icon: path.join(__dirname, 'assets', 'icon.png'),
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
            enableRemoteModule: true
        },
        show: false // Don't show until backend is ready
    });

    // Load the app
    mainWindow.loadFile('index.html');

    // Show window when ready
    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
    });

    // Handle window closed
    mainWindow.on('closed', () => {
        mainWindow = null;
    });

    // Development tools in debug mode
    if (process.argv.includes('--debug')) {
        mainWindow.webContents.openDevTools();
    }
}

/**
 * App event handlers
 */
app.whenReady().then(async () => {
    console.log('Electron app is ready, starting initialization...');
    
    // Start Python backend
    const backendStarted = startPythonBackend();
    if (!backendStarted) {
        app.quit();
        return;
    }
    
    // Wait for backend to be ready
    const backendReady = await waitForBackend();
    if (!backendReady) {
        console.error('Backend startup timeout, exiting...');
        app.quit();
        return;
    }
    
    // Create main window
    createWindow();
    
    // macOS specific behavior
    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('before-quit', () => {
    // Terminate Python backend
    if (pythonProcess) {
        console.log('Terminating Python backend...');
        pythonProcess.kill('SIGTERM');
        
        // Force kill after 5 seconds if it doesn't terminate gracefully
        setTimeout(() => {
            if (pythonProcess && !pythonProcess.killed) {
                console.log('Force killing Python backend...');
                pythonProcess.kill('SIGKILL');
            }
        }, 5000);
    }
});

/**
 * IPC handlers for communication with renderer process
 */
ipcMain.handle('get-backend-url', () => {
    return `http://127.0.0.1:${BACKEND_PORT}`;
});

ipcMain.handle('backend-status', async () => {
    try {
        const fetch = require('node-fetch');
        const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/status`);
        return response.ok;
    } catch (error) {
        return false;
    }
});

// Export for use in other modules
module.exports = {
    getMainWindow: () => mainWindow
};