# 🎮 Dust Game Manager

A universal game management application with Python backend and Electron frontend for organizing, launching, and managing games across multiple platforms including DLSite, Steam, and Itch.io.

![Version](https://img.shields.io/badge/version-0.2.1--dev-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)
![Node.js](https://img.shields.io/badge/node.js-16%2B-green.svg)

**Current Version:** v0.2.1-dev (Build 20250715)  
**Author:** Link Darkshire  
**License:** MIT

## 🌟 Features

### ✅ Core Features (v0.2.0)
- **Unified Game Library**: Manage games from multiple platforms in one place
- **DLSite Integration**: Complete integration using dlsite-async library
- **Centralized Data Management**: All data stored in unified `data/` directory
- **Genre/WorkType Mapping**: Proper separation of game genres and content categories
- **SQLite Database**: Robust local database storage with automatic schema management
- **dustgrain.json Support**: Maintains compatibility with existing game metadata
- **Game Launching**: Direct game execution from the interface
- **Automatic Scanning**: Detect and import games automatically
- **Cover Art Download**: Automatic cover image fetching and caching from DLSite
- **Unified Version Management**: Centralized version control across all components

### 🎯 Platform Support
- ✅ **DLSite** (Complete - Maniax, Home, Books, etc.)
  - Automatic metadata fetching
  - Cover image downloading
  - RJ/RE number detection
  - Genre and tag extraction
- 🔄 **Steam** (Planned for v0.3.0)
- 🔄 **Itch.io** (Planned for v0.4.0)
- ✅ **Local Games** (Any executable)

### 🛠️ Technical Features
- **Python Backend**: Modular backend with async DLSite integration
- **Electron Frontend**: Cross-platform desktop application
- **Centralized Configuration**: Unified path and version management
- **Comprehensive Logging**: Full operation tracking with centralized logs
- **Tag System**: Organize games with custom tags and metadata
- **Play Time Tracking**: Monitor gaming habits (planned)
- **Error Handling**: Robust error handling with fallback systems
- **Cross-Platform**: Windows, macOS, and Linux support

## 📋 System Requirements

### Minimum Requirements
- **OS**: Windows 10/11, macOS 10.15+, or Linux (major distributions)
- **Python**: 3.9 or higher
- **Node.js**: 16.0 or higher
- **RAM**: 4 GB
- **Storage**: 500 MB + space for game metadata and cover images
- **Internet**: Required for DLSite integration and cover downloads

### Recommended
- **Python**: 3.11+
- **Node.js**: 18.0+
- **RAM**: 8 GB
- **SSD Storage**: For better performance

## 🚀 Installation & Setup

### Prerequisites
1. Install [Python 3.9+](https://www.python.org/downloads/)
2. Install [Node.js 16+](https://nodejs.org/)
3. Install [Git](https://git-scm.com/) (for cloning the repository)

### Installation Steps
```bash
# 1. Clone the repository
git clone https://github.com/LinkDarkshire/Dust-Game-Manager.git
cd Dust-Game-Manager

# 2. Install Node.js dependencies
npm install

# 3. Install Python dependencies
cd backend
pip install -r requirements.txt
cd ..

# 4. Run setup (optional)
npm run setup
```

## 🎮 Usage

### Starting the Application
```bash
# Development mode (with debug console)
npm run dev

# Production mode
npm start

# Backend testing
npm run test-backend
```

### First Time Setup
1. Launch the application
2. Configure your game directories in Settings
3. Run an initial game scan to detect existing games
4. Add games manually or import from DLSite

### Managing Versions
```bash
# Update version across all files
npm run update-version

# Check current version
python update_version.py
```

## 📁 Project Structure

```
Dust-Game-Manager/
├── data/                           # 📊 All application data
│   ├── dust_games.db              # SQLite database
│   ├── covers/                    # Game cover images
│   ├── logs/                      # Application logs
│   └── screenshots/               # Game screenshots
├── backend/                       # 🐍 Python backend
│   ├── src/modules/              # Core modules
│   ├── src/platforms/            # Platform integrations
│   ├── config/                   # Configuration
│   └── scripts/                  # Backend scripts
├── assets/                       # 🎨 Application assets
├── update_version.py             # 🔧 Version management
├── main.js                       # ⚡ Electron main process
├── renderer.js                  # 🖥️ Frontend logic
├── index.html                   # 📄 Main UI
└── package.json                 # 📦 Dependencies
```

## 🗺️ Development Roadmap

### Version 0.2.0 - DLSite Integration (Current)
- [x] Complete DLSite platform support
- [x] Enhanced metadata display
- [x] Improved game detection
- [x] Centralized data management
- [x] Genre/WorkType field mapping
- [x] Unified version management
- [ ] UI refinements
- [ ] Performance optimizations

### Version 0.3.0 - Steam Integration (Planned)
- [ ] Steam platform integration
- [ ] Steam library detection
- [ ] Steam metadata fetching
- [ ] Unified game view across DLSite and Steam
- [ ] Enhanced filtering capabilities

### Version 0.4.0 - Itch.io Support (Planned)
- [ ] Itch.io platform integration
- [ ] Indie game support
- [ ] Browser-playable games handling
- [ ] Metadata enrichment from multiple sources

### Version 1.0.0 - Stable Release (Future)
- [ ] All core features complete
- [ ] Advanced game organization
- [ ] Cloud sync capabilities
- [ ] Community features

## 🤝 Contributing

We welcome contributions! Please read our contributing guidelines and feel free to submit pull requests.

### Development Setup
```bash
# Install development dependencies
npm install

# Run in development mode
npm run dev

# Run backend tests
npm run test-backend

# Build for production
npm run build
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- **Repository**: [GitHub](https://github.com/LinkDarkshire/Dust-Game-Manager)
- **Issues**: [Bug Reports & Feature Requests](https://github.com/LinkDarkshire/Dust-Game-Manager/issues)
- **Releases**: [Download Latest](https://github.com/LinkDarkshire/Dust-Game-Manager/releases)

## 🙏 Acknowledgments

- **dlsite-async**: For DLSite API integration
- **Electron**: For cross-platform desktop application framework
- **SQLite**: For reliable local database storage

---

**Version:** v0.2.0-dev | **Build Date:** 20250715 | **Author:** Link Darkshire