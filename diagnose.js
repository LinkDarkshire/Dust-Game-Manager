// diagnose.js - Simple diagnostic script for Dust Game Manager
// Run with: node diagnose.js

const { spawn } = require('child_process');
const fetch = require('node-fetch');
const fs = require('fs');
const path = require('path');

console.log('========================================');
console.log('Dust Game Manager - Diagnostic Tool');
console.log('========================================\n');

async function checkDependencies() {
    console.log('1. Checking Dependencies...');
    
    // Check Node.js
    console.log(`   Node.js: ${process.version} ✓`);
    
    // Check Python
    try {
        const pythonResult = await runCommand('python', ['--version']);
        console.log(`   Python: ${pythonResult.trim()} ✓`);
    } catch (error) {
        console.log(`   Python: NOT FOUND ✗`);
        console.log(`   Error: ${error.message}`);
        return false;
    }
    
    // Check if required files exist
    const requiredFiles = [
        'main.js',
        'renderer.js',
        'index.html',
        'package.json',
        'backend/scripts/main.py',
        'backend/requirements.txt'
    ];
    
    console.log('\n2. Checking Required Files...');
    for (const file of requiredFiles) {
        if (fs.existsSync(file)) {
            console.log(`   ${file}: EXISTS ✓`);
        } else {
            console.log(`   ${file}: MISSING ✗`);
        }
    }
    
    return true;
}

async function checkPythonDependencies() {
    console.log('\n3. Checking Python Dependencies...');
    
    const requiredPackages = [
        'flask',
        'flask_cors',
        'dlsite_async',
        'aiohttp',
        'aiofiles'
    ];
    
    for (const pkg of requiredPackages) {
        try {
            await runCommand('python', ['-c', `import ${pkg}; print("${pkg}: OK")`]);
            console.log(`   ${pkg}: INSTALLED ✓`);
        } catch (error) {
            console.log(`   ${pkg}: NOT INSTALLED ✗`);
        }
    }
}

async function testBackendStartup() {
    console.log('\n4. Testing Backend Startup...');
    
    const backendScript = path.join(__dirname, 'backend', 'scripts', 'main.py');
    if (!fs.existsSync(backendScript)) {
        console.log('   Backend script not found ✗');
        return false;
    }
    
    console.log('   Starting Python backend (test mode)...');
    
    const pythonProcess = spawn('python', [backendScript, '--port', '5002'], {
        stdio: ['ignore', 'pipe', 'pipe']
    });
    
    let backendOutput = '';
    let backendErrors = '';
    
    pythonProcess.stdout.on('data', (data) => {
        backendOutput += data.toString();
    });
    
    pythonProcess.stderr.on('data', (data) => {
        backendErrors += data.toString();
    });
    
    // Wait for backend to start
    await new Promise(resolve => setTimeout(resolve, 3000));
    
    // Test backend endpoint
    try {
        const response = await fetch('http://127.0.0.1:5002/api/status', {
            timeout: 2000
        });
        
        if (response.ok) {
            const data = await response.json();
            console.log('   Backend Status: RUNNING ✓');
            console.log(`   Backend Response: ${JSON.stringify(data)}`);
        } else {
            console.log(`   Backend Status: ERROR ✗ (HTTP ${response.status})`);
        }
    } catch (error) {
        console.log('   Backend Status: NOT RESPONDING ✗');
        console.log(`   Error: ${error.message}`);
    }
    
    // Kill test backend
    pythonProcess.kill('SIGTERM');
    
    // Show backend output/errors if any
    if (backendOutput) {
        console.log('\n   Backend Output:');
        console.log('   ' + backendOutput.replace(/\n/g, '\n   '));
    }
    
    if (backendErrors) {
        console.log('\n   Backend Errors:');
        console.log('   ' + backendErrors.replace(/\n/g, '\n   '));
    }
    
    return true;
}

async function checkElectronSetup() {
    console.log('\n5. Checking Electron Setup...');
    
    // Check if electron is installed
    try {
        const electronPath = path.join(__dirname, 'node_modules', '.bin', 'electron');
        if (fs.existsSync(electronPath) || fs.existsSync(electronPath + '.cmd')) {
            console.log('   Electron: INSTALLED ✓');
        } else {
            console.log('   Electron: NOT FOUND ✗');
            console.log('   Run: npm install');
        }
    } catch (error) {
        console.log('   Electron: ERROR ✗');
    }
    
    // Check main.js for correct backend path
    try {
        const mainJsContent = fs.readFileSync('main.js', 'utf8');
        if (mainJsContent.includes('backend/scripts/main.py')) {
            console.log('   Main.js backend path: CORRECT ✓');
        } else if (mainJsContent.includes('backend/main.py')) {
            console.log('   Main.js backend path: INCORRECT ✗');
            console.log('   Path should be: backend/scripts/main.py');
        } else {
            console.log('   Main.js backend path: NOT FOUND ✗');
        }
    } catch (error) {
        console.log('   Main.js: ERROR READING ✗');
    }
}

async function generateRecommendations() {
    console.log('\n========================================');
    console.log('RECOMMENDATIONS:');
    console.log('========================================');
    
    const recommendations = [];
    
    // Check if setup was run
    if (!fs.existsSync('node_modules')) {
        recommendations.push('Run: npm install');
    }
    
    // Check if Python dependencies are installed
    try {
        await runCommand('python', ['-c', 'import flask']);
    } catch (error) {
        recommendations.push('Install Python dependencies: pip install -r backend/requirements.txt');
    }
    
    // Check if main.js is updated
    if (fs.existsSync('main.js')) {
        const mainJsContent = fs.readFileSync('main.js', 'utf8');
        if (!mainJsContent.includes('backend/scripts/main.py')) {
            recommendations.push('Update main.js with correct backend path (see fixed_main_js artifact)');
        }
    }
    
    // Check if index.html is updated
    if (fs.existsSync('index.html')) {
        const htmlContent = fs.readFileSync('index.html', 'utf8');
        if (!htmlContent.includes('search-input')) {
            recommendations.push('Update index.html with correct element IDs (see fixed_index_html artifact)');
        }
    }
    
    if (recommendations.length === 0) {
        console.log('✓ All checks passed! Your setup should work correctly.');
        console.log('\nTry starting the application with:');
        console.log('  npm start');
        console.log('or');
        console.log('  electron .');
    } else {
        console.log('Please fix the following issues:');
        recommendations.forEach((rec, index) => {
            console.log(`${index + 1}. ${rec}`);
        });
    }
    
    console.log('\n========================================');
    console.log('DEBUGGING TIPS:');
    console.log('========================================');
    console.log('1. Run with debug mode: npm run debug');
    console.log('2. Check browser console for frontend errors');
    console.log('3. Check terminal output for backend errors');
    console.log('4. Verify Python path: python --version');
    console.log('5. Test backend manually: python backend/scripts/main.py');
    console.log('6. Check logs folder for detailed error logs');
}

function runCommand(command, args) {
    return new Promise((resolve, reject) => {
        const process = spawn(command, args, { stdio: 'pipe' });
        let output = '';
        let error = '';
        
        process.stdout.on('data', (data) => {
            output += data.toString();
        });
        
        process.stderr.on('data', (data) => {
            error += data.toString();
        });
        
        process.on('close', (code) => {
            if (code === 0) {
                resolve(output);
            } else {
                reject(new Error(error || `Command failed with code ${code}`));
            }
        });
        
        process.on('error', (err) => {
            reject(err);
        });
    });
}

// Main diagnostic function
async function runDiagnostics() {
    try {
        await checkDependencies();
        await checkPythonDependencies();
        await testBackendStartup();
        await checkElectronSetup();
        await generateRecommendations();
    } catch (error) {
        console.error('\nDiagnostic error:', error);
    }
    
    console.log('\nDiagnostics complete!');
}

// Run diagnostics if this file is executed directly
if (require.main === module) {
    runDiagnostics();
}

module.exports = {
    runDiagnostics,
    checkDependencies,
    checkPythonDependencies,
    testBackendStartup,
    checkElectronSetup
};