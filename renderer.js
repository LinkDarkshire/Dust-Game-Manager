const { ipcRenderer } = require('electron');

/**
 * Dust Game Manager - Frontend Application
 * Updated to work with Python backend via HTTP API
 */
class DustApp {
    constructor() {
        this.apiUrl = null;
        this.games = [];
        this.filteredGames = [];
        this.currentView = 'grid';
        this.selectedGame = null;
        this.isLoading = false;

        this.init();
    }

    /**
     * Initialize the application
     */
    async init() {
        console.log('Initializing Dust Game Manager...');
        
        try {
            // Get backend URL from main process
            this.apiUrl = await ipcRenderer.invoke('get-backend-url');
            console.log(`Backend URL: ${this.apiUrl}`);
            
            // Check backend status
            const backendReady = await ipcRenderer.invoke('backend-status');
            if (!backendReady) {
                this.showError('Backend is not ready. Please restart the application.');
                return;
            }
            
            // Initialize UI
            this.initEventListeners();
            this.initUI();
            
            // Load games
            await this.loadGames();
            
            console.log('Dust Game Manager initialized successfully');
            
        } catch (error) {
            console.error('Error initializing Dust App:', error);
            this.showError('Failed to initialize application');
        }
    }

    /**
     * Initialize event listeners
     */
    initEventListeners() {
        // Game grid/list toggle
        const viewToggle = document.getElementById('view-toggle');
        if (viewToggle) {
            viewToggle.addEventListener('change', (e) => {
                this.currentView = e.target.checked ? 'list' : 'grid';
                this.renderGames();
            });
        }

        // Search functionality
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.filterGames(e.target.value);
            });
        }

        // Add game button
        const addGameBtn = document.getElementById('add-game-btn');
        if (addGameBtn) {
            addGameBtn.addEventListener('click', () => {
                this.showAddGameDialog();
            });
        }

        // Scan games button
        const scanGamesBtn = document.getElementById('scan-games-btn');
        if (scanGamesBtn) {
            scanGamesBtn.addEventListener('click', () => {
                this.scanGames();
            });
        }

        // Refresh button
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadGames();
            });
        }

        // Close details panel
        const closeDetailsBtn = document.getElementById('close-details');
        if (closeDetailsBtn) {
            closeDetailsBtn.addEventListener('click', () => {
                this.hideGameDetails();
            });
        }
    }

    /**
     * Initialize UI components
     */
    initUI() {
        // Set initial view
        this.renderGames();
        
        // Show loading indicator
        this.setLoading(false);
    }

    /**
     * Make API request to Python backend
     */
    async apiRequest(endpoint, options = {}) {
        try {
            const url = `${this.apiUrl}${endpoint}`;
            const defaultOptions = {
                headers: {
                    'Content-Type': 'application/json'
                }
            };
            
            const requestOptions = { ...defaultOptions, ...options };
            
            console.log(`API Request: ${requestOptions.method || 'GET'} ${url}`);
            
            const response = await fetch(url, requestOptions);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            return data;
            
        } catch (error) {
            console.error('API Request failed:', error);
            throw error;
        }
    }

    /**
     * Load games from backend
     */
    async loadGames() {
        try {
            this.setLoading(true);
            console.log('Loading games from backend...');
            
            const response = await this.apiRequest('/api/games');
            
            if (response.success) {
                this.games = response.games || [];
                this.filteredGames = [...this.games];
                this.renderGames();
                
                console.log(`Loaded ${this.games.length} games`);
                this.showNotification(`Loaded ${this.games.length} games`, 'success');
            } else {
                throw new Error(response.message || 'Failed to load games');
            }
            
        } catch (error) {
            console.error('Error loading games:', error);
            this.showError('Failed to load games: ' + error.message);
        } finally {
            this.setLoading(false);
        }
    }

    /**
     * Scan for games
     */
    async scanGames() {
        try {
            this.setLoading(true);
            console.log('Scanning for games...');
            
            const response = await this.apiRequest('/api/games/scan', {
                method: 'POST'
            });
            
            if (response.success) {
                this.showNotification(response.message, 'success');
                // Reload games after scan
                await this.loadGames();
            } else {
                throw new Error(response.message || 'Scan failed');
            }
            
        } catch (error) {
            console.error('Error scanning games:', error);
            this.showError('Failed to scan games: ' + error.message);
        } finally {
            this.setLoading(false);
        }
    }

    /**
     * Launch a game
     */
    async launchGame(gameId) {
        try {
            console.log(`Launching game ID: ${gameId}`);
            
            const response = await this.apiRequest(`/api/games/${gameId}/launch`, {
                method: 'POST'
            });
            
            if (response.success) {
                this.showNotification(response.message, 'success');
            } else {
                throw new Error(response.message || 'Failed to launch game');
            }
            
        } catch (error) {
            console.error('Error launching game:', error);
            this.showError('Failed to launch game: ' + error.message);
        }
    }

    /**
     * Show game details
     */
    async showGameDetails(gameId) {
        try {
            const game = this.games.find(g => g.id === gameId);
            if (!game) {
                this.showError('Game not found');
                return;
            }
            
            this.selectedGame = game;
            
            // Update details panel
            const detailsPanel = document.getElementById('game-details-panel');
            const detailsContent = document.getElementById('game-details-content');
            
            if (detailsPanel && detailsContent) {
                detailsContent.innerHTML = this.generateGameDetailsHTML(game);
                detailsPanel.classList.add('active');
                
                // Setup details panel event listeners
                this.setupDetailsEventListeners(game);
            }
            
        } catch (error) {
            console.error('Error showing game details:', error);
            this.showError('Failed to show game details');
        }
    }

    /**
     * Generate HTML for game details
     */
    generateGameDetailsHTML(game) {
        const coverImage = game.coverImage || 'assets/default-cover.jpg';
        const tags = game.tags || [];
        const screenshots = game.screenshots || [];
        
        return `
            <div class="game-details-header">
                <img src="${coverImage}" alt="${game.title}" class="game-cover-large" 
                     onerror="this.src='assets/default-cover.jpg'">
                <div class="game-info">
                    <h2 class="game-title">${game.title}</h2>
                    <p class="game-developer">by ${game.developer || 'Unknown'}</p>
                    <p class="game-source">Source: ${game.source || 'Local'}</p>
                    <div class="game-actions">
                        <button class="btn btn-primary" id="launch-game-btn">
                            <i class="fas fa-play"></i> Launch Game
                        </button>
                        <button class="btn btn-secondary" id="edit-game-btn">
                            <i class="fas fa-edit"></i> Edit
                        </button>
                    </div>
                </div>
            </div>
            
            <div class="game-details-body">
                <div class="detail-section">
                    <h3>Description</h3>
                    <p>${game.description || 'No description available.'}</p>
                </div>
                
                <div class="detail-section">
                    <h3>Information</h3>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <span class="label">Genre:</span>
                            <span class="value">${game.genre || 'Unknown'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">Release Date:</span>
                            <span class="value">${game.releaseDate || 'Unknown'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">Version:</span>
                            <span class="value">${game.version || '1.0'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">Play Time:</span>
                            <span class="value">${this.formatPlayTime(game.playTime || 0)}</span>
                        </div>
                        <div class="detail-item">
                            <span class="label">Last Played:</span>
                            <span class="value">${this.formatDate(game.lastPlayed)}</span>
                        </div>
                    </div>
                </div>
                
                ${tags.length > 0 ? `
                <div class="detail-section">
                    <h3>Tags</h3>
                    <div class="tags-container">
                        ${tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
                    </div>
                </div>
                ` : ''}
                
                ${game.voiceActors && game.voiceActors.length > 0 ? `
                <div class="detail-section">
                    <h3>Voice Actors</h3>
                    <ul class="credits-list">
                        ${game.voiceActors.map(actor => `<li>${actor}</li>`).join('')}
                    </ul>
                </div>
                ` : ''}
                
                ${screenshots.length > 0 ? `
                <div class="detail-section">
                    <h3>Screenshots</h3>
                    <div class="screenshots-grid">
                        ${screenshots.map(screenshot => `
                            <img src="${screenshot}" alt="Screenshot" class="screenshot-thumb"
                                 onclick="this.classList.toggle('enlarged')">
                        `).join('')}
                    </div>
                </div>
                ` : ''}
            </div>
        `;
    }

    /**
     * Setup event listeners for details panel
     */
    setupDetailsEventListeners(game) {
        const launchBtn = document.getElementById('launch-game-btn');
        if (launchBtn) {
            launchBtn.addEventListener('click', () => {
                this.launchGame(game.id);
            });
        }
        
        const editBtn = document.getElementById('edit-game-btn');
        if (editBtn) {
            editBtn.addEventListener('click', () => {
                this.showEditGameDialog(game);
            });
        }
    }

    /**
     * Hide game details panel
     */
    hideGameDetails() {
        const detailsPanel = document.getElementById('game-details-panel');
        if (detailsPanel) {
            detailsPanel.classList.remove('active');
        }
        this.selectedGame = null;
    }

    /**
     * Filter games based on search query
     */
    filterGames(query) {
        const searchTerm = query.toLowerCase().trim();
        
        if (!searchTerm) {
            this.filteredGames = [...this.games];
        } else {
            this.filteredGames = this.games.filter(game => {
                return (
                    game.title.toLowerCase().includes(searchTerm) ||
                    (game.developer && game.developer.toLowerCase().includes(searchTerm)) ||
                    (game.genre && game.genre.toLowerCase().includes(searchTerm)) ||
                    (game.tags && game.tags.some(tag => tag.toLowerCase().includes(searchTerm)))
                );
            });
        }
        
        this.renderGames();
    }

    /**
     * Render games in the current view
     */
    renderGames() {
        const gamesList = document.getElementById('games-list');
        if (!gamesList) return;
        
        if (this.filteredGames.length === 0) {
            gamesList.innerHTML = `
                <div class="no-games-message">
                    <i class="fas fa-gamepad"></i>
                    <h3>No games found</h3>
                    <p>Add some games to get started!</p>
                    <button class="btn btn-primary" onclick="dustApp.showAddGameDialog()">
                        <i class="fas fa-plus"></i> Add Game
                    </button>
                </div>
            `;
            return;
        }
        
        const gamesHTML = this.filteredGames.map(game => {
            if (this.currentView === 'grid') {
                return this.generateGameCardHTML(game);
            } else {
                return this.generateGameListItemHTML(game);
            }
        }).join('');
        
        gamesList.className = `games-${this.currentView}`;
        gamesList.innerHTML = gamesHTML;
        
        // Add click listeners to game cards
        this.addGameClickListeners();
    }

    /**
     * Generate HTML for game card (grid view)
     */
    generateGameCardHTML(game) {
        const coverImage = game.coverImage || 'assets/default-cover.jpg';
        const lastPlayed = game.lastPlayed ? this.formatDate(game.lastPlayed) : 'Never';
        
        return `
            <div class="game-card" data-game-id="${game.id}">
                <div class="game-cover-container">
                    <img src="${coverImage}" alt="${game.title}" class="game-cover"
                         onerror="this.src='assets/default-cover.jpg'">
                    <div class="game-overlay">
                        <button class="play-btn" data-action="launch" data-game-id="${game.id}">
                            <i class="fas fa-play"></i>
                        </button>
                    </div>
                </div>
                <div class="game-info">
                    <h3 class="game-title" title="${game.title}">${game.title}</h3>
                    <p class="game-developer">${game.developer || 'Unknown'}</p>
                    <p class="game-last-played">Last played: ${lastPlayed}</p>
                </div>
            </div>
        `;
    }

    /**
     * Generate HTML for game list item (list view)
     */
    generateGameListItemHTML(game) {
        const coverImage = game.coverImage || 'assets/default-cover.jpg';
        const lastPlayed = game.lastPlayed ? this.formatDate(game.lastPlayed) : 'Never';
        const playTime = this.formatPlayTime(game.playTime || 0);
        
        return `
            <div class="game-list-item" data-game-id="${game.id}">
                <img src="${coverImage}" alt="${game.title}" class="game-cover-small"
                     onerror="this.src='assets/default-cover.jpg'">
                <div class="game-info">
                    <h3 class="game-title">${game.title}</h3>
                    <p class="game-developer">${game.developer || 'Unknown'}</p>
                    <p class="game-genre">${game.genre || 'Unknown'}</p>
                </div>
                <div class="game-stats">
                    <span class="stat">Play Time: ${playTime}</span>
                    <span class="stat">Last Played: ${lastPlayed}</span>
                </div>
                <div class="game-actions">
                    <button class="btn btn-small btn-primary" data-action="launch" data-game-id="${game.id}">
                        <i class="fas fa-play"></i> Launch
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Add click listeners to game elements
     */
    addGameClickListeners() {
        // Game card/item clicks (for details)
        document.querySelectorAll('.game-card, .game-list-item').forEach(element => {
            element.addEventListener('click', (e) => {
                // Don't trigger if clicking on action buttons
                if (e.target.closest('[data-action]')) return;
                
                const gameId = parseInt(element.dataset.gameId);
                this.showGameDetails(gameId);
            });
        });
        
        // Action button clicks
        document.querySelectorAll('[data-action]').forEach(button => {
            button.addEventListener('click', (e) => {
                e.stopPropagation();
                
                const action = button.dataset.action;
                const gameId = parseInt(button.dataset.gameId);
                
                if (action === 'launch') {
                    this.launchGame(gameId);
                }
            });
        });
    }

    /**
     * Show add game dialog
     */
    showAddGameDialog() {
        // This would open a dialog for adding games
        // For now, just show a notification
        this.showNotification('Add game functionality coming soon!', 'info');
    }

    /**
     * Show edit game dialog
     */
    showEditGameDialog(game) {
        // This would open a dialog for editing game information
        this.showNotification('Edit game functionality coming soon!', 'info');
    }

    /**
     * Set loading state
     */
    setLoading(loading) {
        this.isLoading = loading;
        const loadingIndicator = document.getElementById('loading-indicator');
        const mainContent = document.getElementById('main-content');
        
        if (loadingIndicator && mainContent) {
            if (loading) {
                loadingIndicator.style.display = 'flex';
                mainContent.style.opacity = '0.5';
            } else {
                loadingIndicator.style.display = 'none';
                mainContent.style.opacity = '1';
            }
        }
    }

    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        console.log(`Notification [${type}]: ${message}`);
        
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <i class="fas fa-${this.getNotificationIcon(type)}"></i>
            <span>${message}</span>
            <button class="notification-close">&times;</button>
        `;
        
        // Add to page
        document.body.appendChild(notification);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 5000);
        
        // Close button functionality
        notification.querySelector('.notification-close').addEventListener('click', () => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        });
    }

    /**
     * Show error message
     */
    showError(message) {
        this.showNotification(message, 'error');
    }

    /**
     * Get notification icon based on type
     */
    getNotificationIcon(type) {
        const icons = {
            'success': 'check-circle',
            'error': 'exclamation-circle',
            'warning': 'exclamation-triangle',
            'info': 'info-circle'
        };
        return icons[type] || 'info-circle';
    }

    /**
     * Format play time in minutes to readable format
     */
    formatPlayTime(minutes) {
        if (minutes < 60) {
            return `${minutes} min`;
        } else if (minutes < 1440) {
            const hours = Math.floor(minutes / 60);
            const mins = minutes % 60;
            return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
        } else {
            const days = Math.floor(minutes / 1440);
            const hours = Math.floor((minutes % 1440) / 60);
            return hours > 0 ? `${days}d ${hours}h` : `${days}d`;
        }
    }

    /**
     * Format date string to readable format
     */
    formatDate(dateString) {
        if (!dateString) return 'Never';
        
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        } catch (error) {
            return 'Invalid date';
        }
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.dustApp = new DustApp();
});