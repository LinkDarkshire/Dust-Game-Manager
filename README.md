# 🎮 Dust Game Manager

A universal game management application with Python backend and Electron frontend for organizing, launching, and managing games across multiple platforms including DLSite, Steam, and Itch.io.

![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)
![Node.js](https://img.shields.io/badge/node.js-18%2B-green.svg)

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

##