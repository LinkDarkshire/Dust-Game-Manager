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
        // Fixed: Correct path to Python main script
        const pythonScript = path.join(__dirname, 'backend', 'scripts', 'main.py');
        
        console.log(`Starting Python backend at: ${pythonScript}`);
        
        // Check if Python script exists
        if (!fs.existsSync(pythonScript)) {
            console.error(`Python script not found at: ${pythonScript}`);
            return false;
        }
        
        // Try to start Python backend
        pythonProcess = spawn('python', [
            pythonScript,
            '--host', '127.0.0.1',
            '--port', BACKEND_PORT.toString()
        ], {
            stdio: ['ignore', 'pipe', 'pipe'],
            cwd: __dirname // Set working directory to project root
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
                // Show error dialog to user
                const { dialog } = require('electron');
                if (mainWindow) {
                    dialog.showErrorBox(
                        'Backend Error',
                        `Python backend crashed with exit code ${code}. Please check the console for details.`
                    );
                }
            }
        });

        pythonProcess.on('error', (error) => {
            console.error('Failed to start Python backend:', error);
            // Show error dialog to user
            const { dialog } = require('electron');
            dialog.showErrorBox(
                'Backend Error',
                'Failed to start Python backend. Please ensure Python is installed and all dependencies are available.\n\n' +
                'Error: ' + error.message
            );
        });

        console.log('Python backend process started successfully');
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
    
    console.log('Waiting for Python backend to be ready...');
    
    for (let i = 0; i < maxAttempts; i++) {
        try {
            const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/status`, {
                timeout: 2000 // 2 second timeout per request
            });
            if (response.ok) {
                console.log('Python backend is ready');
                const data = await response.json();
                console.log('Backend status:', data);
                return true;
            }
        } catch (error) {
            // Backend not ready yet, wait and retry
            console.log(`Backend not ready yet (attempt ${i + 1}/${maxAttempts}), retrying...`);
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
    console.log('Creating main application window...');
    
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        minWidth: 800,
        minHeight: 600,
        icon: path.join(__dirname, 'assets', 'icon.png'),
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
            enableRemoteModule: true
        },
        show: false, // Don't show until backend is ready
        titleBarStyle: 'default'
    });

    // Load the app
    mainWindow.loadFile('index.html');

    // Show window when ready
    mainWindow.once('ready-to-show', () => {
        console.log('Main window ready, showing...');
        mainWindow.show();
    });

    // Handle window closed
    mainWindow.on('closed', () => {
        console.log('Main window closed');
        mainWindow = null;
    });

    // Development tools in debug mode
    if (process.argv.includes('--debug')) {
        console.log('Debug mode enabled, opening DevTools...');
        mainWindow.webContents.openDevTools();
    }
    
    // Log when page is loaded
    mainWindow.webContents.on('did-finish-load', () => {
        console.log('Main window content loaded');
    });
}

/**
 * App event handlers
 */
app.whenReady().then(async () => {
    console.log('Electron app is ready, starting initialization...');
    
    // Start Python backend
    const backendStarted = startPythonBackend();
    if (!backendStarted) {
        console.error('Failed to start Python backend, exiting...');
        app.quit();
        return;
    }
    
    // Wait for backend to be ready
    const backendReady = await waitForBackend();
    if (!backendReady) {
        console.error('Backend startup timeout, exiting...');
        const { dialog } = require('electron');
        dialog.showErrorBox(
            'Backend Startup Failed',
            'The Python backend failed to start within the timeout period. Please check that Python and all dependencies are properly installed.'
        );
        app.quit();
        return;
    }
    
    // Create main window
    createWindow();
    
    console.log('Application initialization complete');
    
    // macOS specific behavior
    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    console.log('All windows closed');
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('before-quit', () => {
    console.log('Application quitting, cleaning up...');
    
    // Terminate Python backend
    if (pythonProcess && !pythonProcess.killed) {
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
    const url = `http://127.0.0.1:${BACKEND_PORT}`;
    console.log(`Providing backend URL to renderer: ${url}`);
    return url;
});

ipcMain.handle('backend-status', async () => {
    try {
        const fetch = require('node-fetch');
        const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/api/status`, {
            timeout: 2000
        });
        const isReady = response.ok;
        console.log(`Backend status check: ${isReady ? 'Ready' : 'Not ready'}`);
        return isReady;
    } catch (error) {
        console.log(`Backend status check failed: ${error.message}`);
        return false;
    }
});

// Additional IPC handlers for debugging
ipcMain.handle('get-app-info', () => {
    return {
        version: app.getVersion(),
        name: app.getName(),
        backendPort: BACKEND_PORT,
        debug: process.argv.includes('--debug')
    };
});

// Export for use in other modules
module.exports = {
    getMainWindow: () => mainWindow,
    getBackendPort: () => BACKEND_PORT
};