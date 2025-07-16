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

            // Check backend status with retry logic
            let backendReady = false;
            let retries = 0;
            const maxRetries = 10;

            while (!backendReady && retries < maxRetries) {
                try {
                    backendReady = await ipcRenderer.invoke('backend-status');
                    if (backendReady) break;

                    console.log(`Backend not ready, retrying... (${retries + 1}/${maxRetries})`);
                    await new Promise(resolve => setTimeout(resolve, 1000));
                    retries++;
                } catch (error) {
                    console.log(`Backend connection error: ${error.message}`);
                    retries++;
                    await new Promise(resolve => setTimeout(resolve, 1000));
                }
            }

            if (!backendReady) {
                this.showError('Backend ist nicht bereit. Bitte starte die Anwendung neu.');
                return;
            }

            // Initialize UI components
            this.initEventListeners();
            this.initUINavigation();
            this.initMissingEventListeners();
            this.initUI();

            // Load games
            await this.loadGames();

            // VPN initialisieren
            await this.initVPN();

            console.log('Dust Game Manager erfolgreich initialisiert');
            this.showNotification('Dust Game Manager gestartet', 'success');

        } catch (error) {
            console.error('Error initializing Dust App:', error);
            this.showError('Fehler beim Initialisieren der Anwendung: ' + error.message);
        }
    }

    /**
     * Initialize UI navigation
     */
    initUINavigation() {
        const navButtons = document.querySelectorAll('.nav-button');
        const pages = document.querySelectorAll('.page');

        navButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const targetPage = button.getAttribute('data-page');

                // Remove active class from all nav buttons and pages
                navButtons.forEach(btn => btn.classList.remove('active'));
                pages.forEach(page => page.classList.remove('active'));

                // Add active class to clicked button and target page
                button.classList.add('active');
                const targetPageElement = document.getElementById(targetPage);
                if (targetPageElement) {
                    targetPageElement.classList.add('active');
                }

                console.log(`Navigated to: ${targetPage}`);
            });
        });
    }

    /**
     * Initialize missing event listeners
     */
    initMissingEventListeners() {
        // Search functionality
        const searchBar = document.querySelector('.search-bar');
        if (searchBar) {
            searchBar.addEventListener('input', (e) => {
                this.filterGames(e.target.value);
            });
        }

        // Filter dropdowns
        const genreFilter = document.getElementById('genre-filter');
        const sourceFilter = document.getElementById('source-filter');

        if (genreFilter) {
            genreFilter.addEventListener('change', (e) => {
                this.applyFilters();
            });
        }

        if (sourceFilter) {
            sourceFilter.addEventListener('change', (e) => {
                this.applyFilters();
            });
        }

        // View toggle button
        const viewToggle = document.getElementById('view-toggle');
        if (viewToggle) {
            viewToggle.addEventListener('click', (e) => {
                this.toggleView();
            });
        }

        // Add missing buttons to the toolbar if they don't exist
        this.ensureToolbarButtons();
    }

    /**
     * Ensure toolbar buttons exist
     */
    ensureToolbarButtons() {
        const filterContainer = document.querySelector('.filter-container');
        if (!filterContainer) return;

        // Check if add game button exists
        if (!document.getElementById('add-game-btn')) {
            const addGameBtn = document.createElement('button');
            addGameBtn.id = 'add-game-btn';
            addGameBtn.className = 'primary-button';
            addGameBtn.innerHTML = '<i class="fas fa-plus"></i> Spiel hinzufügen';
            addGameBtn.addEventListener('click', () => this.showAddGameDialog());
            filterContainer.appendChild(addGameBtn);
        }

        // Check if scan games button exists
        if (!document.getElementById('scan-games-btn')) {
            const scanGamesBtn = document.createElement('button');
            scanGamesBtn.id = 'scan-games-btn';
            scanGamesBtn.className = 'secondary-button';
            scanGamesBtn.innerHTML = '<i class="fas fa-search"></i> Scannen';
            scanGamesBtn.addEventListener('click', () => this.scanGames());
            filterContainer.appendChild(scanGamesBtn);
        }

        // Check if refresh button exists
        if (!document.getElementById('refresh-btn')) {
            const refreshBtn = document.createElement('button');
            refreshBtn.id = 'refresh-btn';
            refreshBtn.className = 'icon-button';
            refreshBtn.innerHTML = '<i class="fas fa-sync"></i>';
            refreshBtn.title = 'Aktualisieren';
            refreshBtn.addEventListener('click', () => this.loadGames());
            filterContainer.appendChild(refreshBtn);
        }
    }

    /**
     * Apply combined filters
     */
    applyFilters() {
        const searchTerm = document.querySelector('.search-bar')?.value?.toLowerCase().trim() || '';
        const genreFilter = document.getElementById('genre-filter')?.value || 'all';
        const sourceFilter = document.getElementById('source-filter')?.value || 'all';

        this.filteredGames = this.games.filter(game => {
            // Search filter
            const matchesSearch = !searchTerm ||
                game.title.toLowerCase().includes(searchTerm) ||
                (game.developer && game.developer.toLowerCase().includes(searchTerm)) ||
                (game.genre && game.genre.toLowerCase().includes(searchTerm)) ||
                (game.tags && game.tags.some(tag => tag.toLowerCase().includes(searchTerm)));

            // Genre filter
            const matchesGenre = genreFilter === 'all' ||
                (game.genre && game.genre.toLowerCase() === genreFilter.toLowerCase());

            // Source filter
            const matchesSource = sourceFilter === 'all' ||
                (game.source && game.source.toLowerCase() === sourceFilter.toLowerCase());

            return matchesSearch && matchesGenre && matchesSource;
        });

        this.renderGames();
    }

    /**
     * Toggle between grid and list view
     */
    toggleView() {
        const gameContainer = document.querySelector('.game-grid');
        const viewToggleBtn = document.getElementById('view-toggle');
        const viewToggleIcon = viewToggleBtn?.querySelector('i');

        if (this.currentView === 'grid') {
            this.currentView = 'list';
            if (gameContainer) gameContainer.className = 'game-list';
            if (viewToggleIcon) {
                viewToggleIcon.className = 'fas fa-th';
                viewToggleBtn.title = 'Grid-Ansicht';
            }
        } else {
            this.currentView = 'grid';
            if (gameContainer) gameContainer.className = 'game-grid';
            if (viewToggleIcon) {
                viewToggleIcon.className = 'fas fa-list';
                viewToggleBtn.title = 'Listen-Ansicht';
            }
        }

        this.renderGames();
    }

    /**
     * Update filter options based on available games
     */
    updateFilterOptions() {
        const genreFilter = document.getElementById('genre-filter');
        const sourceFilter = document.getElementById('source-filter');

        if (genreFilter && this.games.length > 0) {
            // Get unique genres
            const genres = [...new Set(this.games.map(game => game.genre).filter(Boolean))];

            // Clear existing options except "All"
            genreFilter.innerHTML = '<option value="all">Alle Genres</option>';

            // Add genre options
            genres.sort().forEach(genre => {
                const option = document.createElement('option');
                option.value = genre;
                option.textContent = genre;
                genreFilter.appendChild(option);
            });
        }

        if (sourceFilter && this.games.length > 0) {
            // Get unique sources
            const sources = [...new Set(this.games.map(game => game.source).filter(Boolean))];

            // Clear existing options except "All"
            sourceFilter.innerHTML = '<option value="all">Alle Quellen</option>';

            // Add source options
            sources.sort().forEach(source => {
                const option = document.createElement('option');
                option.value = source;
                option.textContent = source;
                sourceFilter.appendChild(option);
            });
        }
    }

    /**
     * Enhanced render games function
     */
    renderGames() {
        const gameContainer = document.querySelector('.game-grid') || this.createGameContainer();

        if (!gameContainer) {
            console.error('Game container not found and could not be created');
            return;
        }

        // Update container class
        gameContainer.className = this.currentView === 'grid' ? 'game-grid' : 'game-list';

        if (this.filteredGames.length === 0) {
            this.renderEmptyState(gameContainer);
            return;
        }

        const gamesHTML = this.filteredGames.map(game => {
            return this.currentView === 'grid' ?
                this.generateGameCardHTML(game) :
                this.generateGameListItemHTML(game);
        }).join('');

        gameContainer.innerHTML = gamesHTML;

        // Re-attach event listeners
        this.addGameClickListeners();

        // Update filter options
        this.updateFilterOptions();

        console.log(`Rendered ${this.filteredGames.length} games in ${this.currentView} view`);
    }

    /**
     * Create game container if it doesn't exist
     */
    createGameContainer() {
        const libraryPage = document.getElementById('library');
        if (!libraryPage) return null;

        let gameContainer = libraryPage.querySelector('.game-grid');
        if (!gameContainer) {
            gameContainer = document.createElement('div');
            gameContainer.className = 'game-grid';
            libraryPage.appendChild(gameContainer);
        }

        return gameContainer;
    }

    /**
     * Render empty state
     */
    renderEmptyState(container) {
        container.innerHTML = `
        <div class="empty-library">
            <i class="fas fa-gamepad placeholder-icon"></i>
            <h3>Keine Spiele gefunden</h3>
            <p>Füge Spiele hinzu oder scanne deine Spieleverzeichnisse.</p>
            <div style="margin-top: 20px;">
                <button class="primary-button" onclick="dustApp.showAddGameDialog()" style="margin-right: 10px;">
                    <i class="fas fa-plus"></i> Spiel hinzufügen
                </button>
                <button class="secondary-button" onclick="dustApp.scanGames()">
                    <i class="fas fa-search"></i> Spiele scannen
                </button>
            </div>
        </div>
    `;
    }

    /**
     * Enhanced setLoading function
     */
    setLoading(loading) {
        this.isLoading = loading;

        // Remove existing loading indicator
        const existingIndicator = document.getElementById('loading-indicator');
        if (existingIndicator) {
            existingIndicator.remove();
        }

        if (loading) {
            // Create loading indicator
            const loadingIndicator = document.createElement('div');
            loadingIndicator.id = 'loading-indicator';
            loadingIndicator.className = 'loading-indicator';
            loadingIndicator.innerHTML = `
            <div>
                <div class="loading-spinner"></div>
                <div class="loading-text">Laden...</div>
            </div>
        `;
            document.body.appendChild(loadingIndicator);
        }
    }

    /**
     * Enhanced error handling
     */
    showError(message) {
        console.error('Error:', message);
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
     * Enhanced filterGames function (for backward compatibility)
     */
    filterGames(query) {
        // Update search input if it exists
        const searchInput = document.querySelector('.search-bar');
        if (searchInput && searchInput.value !== query) {
            searchInput.value = query;
        }

        // Apply all filters
        this.applyFilters();
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
            const game = this.games.find(g => g.id === gameId);
            if (game) {
                await this.autoConnectVPNForDLSite(game);
            }
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
     * Show platform selection dialog first
     */
    showAddGameDialog() {
        const modal = this.createModal('Spiel hinzufügen - Plattform wählen', `
        <div class="platform-selection-container">
            <p class="platform-instruction">
                Wählen Sie die Plattform des Spiels aus:
            </p>
            
            <div class="platform-grid-icons">
                <div class="platform-card-icon" data-platform="dlsite" title="DLSite - Automatische Metadaten aus RJ/RE-Nummer">
                    <div class="platform-icon-container">
                        <img src="backend/data/covers/platforms/dlsite.png" alt="DLSite" class="platform-icon-large" 
                             onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" />
                        <div class="platform-icon-fallback dlsite-fallback" style="display: none;">
                            <span>DL</span>
                        </div>
                    </div>
                    <span class="platform-label">DLSite</span>
                </div>
                
                <div class="platform-card-icon" data-platform="steam" title="Steam - Steam-Bibliothek Integration">
                    <div class="platform-icon-container">
                        <img src="backend/data/covers/platforms/steam.png" alt="Steam" class="platform-icon-large"
                             onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" />
                        <div class="platform-icon-fallback steam-fallback" style="display: none;">
                            <i class="fas fa-gamepad"></i>
                        </div>
                    </div>
                    <span class="platform-label">Steam</span>
                </div>
                
                <div class="platform-card-icon" data-platform="itchio" title="Itch.io - Indie Games Platform">
                    <div class="platform-icon-container">
                        <img src="backend/data/covers/platforms/itchio.png" alt="Itch.io" class="platform-icon-large"
                             onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" />
                        <div class="platform-icon-fallback itchio-fallback" style="display: none;">
                            <i class="fas fa-paint-brush"></i>
                        </div>
                    </div>
                    <span class="platform-label">Itch.io</span>
                </div>
                
                <div class="platform-card-icon" data-platform="manual" title="Manuell - Lokale Spiele ohne Platform">
                    <div class="platform-icon-container">
                        <img src="backend/data/covers/platforms/other.png" alt="Manual" class="platform-icon-large"
                             onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" />
                        <div class="platform-icon-fallback manual-fallback" style="display: none;">
                            <i class="fas fa-cog"></i>
                        </div>
                    </div>
                    <span class="platform-label">Manuell</span>
                </div>
            </div>
            
            <div class="platform-actions">
                <button type="button" class="secondary-button" onclick="dustApp.closeModal()">
                    Abbrechen
                </button>
            </div>
        </div>
    `);

        // Add click handlers for platform cards
        const platformCards = document.querySelectorAll('.platform-card-icon');
        platformCards.forEach(card => {
            card.addEventListener('click', () => {
                const platform = card.dataset.platform;
                this.closeModal();
                this.showPlatformSpecificDialog(platform);
            });
        });
    }

    /**
     * Show platform-specific dialog based on selection
     */
    showPlatformSpecificDialog(platform) {
        switch (platform) {
            case 'dlsite':
                this.showDLSiteGameDialog();
                break;
            case 'steam':
                this.showSteamGameDialog();
                break;
            case 'itchio':
                this.showItchioGameDialog();
                break;
            case 'manual':
                this.showManualGameDialog();
                break;
            default:
                console.error('Unknown platform:', platform);
        }
    }

    /**
 * DLSite-specific game addition dialog
 */
    showDLSiteGameDialog() {
        const modal = this.createModal('DLSite Spiel hinzufügen', `
        <div class="dlsite-game-form">
            <div class="dlsite-header">
                <img src="backend/data/covers/platforms/dlsite.png" alt="DLSite" class="platform-icon-small"
                     onerror="this.style.display='none'">
                <div class="dlsite-info">
                    <h3>DLSite Spiel hinzufügen</h3>
                    <p>Wählen Sie die .exe Datei des DLSite-Spiels aus. Die RJ/RE-Nummer wird automatisch erkannt.</p>
                </div>
            </div>
            
            <form id="dlsite-game-form">
                <div class="form-group">
                    <label for="dlsite-executable-path">Spiel-Executable (.exe) auswählen *</label>
                    <div class="file-selector">
                        <input type="text" id="dlsite-executable-path" name="executableFullPath" required readonly
                               placeholder="Klicken Sie auf 'Durchsuchen' um die .exe Datei auszuwählen">
                        <button type="button" id="browse-dlsite-executable" class="primary-button">
                            <i class="fas fa-folder-open"></i> Durchsuchen
                        </button>
                    </div>
                    <small class="info-text">Nur .exe Dateien werden unterstützt</small>
                </div>
                
                <div id="dlsite-detection-result" class="detection-result" style="display: none;">
                    <!-- Results will be shown here -->
                </div>
                
                <div id="dlsite-manual-id" class="form-group" style="display: none;">
                    <label for="manual-dlsite-id">DLSite ID manuell eingeben</label>
                    <input type="text" id="manual-dlsite-id" name="dlsiteId" 
                           placeholder="z.B. RJ123456 oder RE654321" pattern="[A-Z]{2}\\d+">
                    <small class="info-text">Format: RJ123456 oder RE654321</small>
                </div>
                
                <div class="form-actions">
                    <button type="button" class="secondary-button" onclick="dustApp.closeModal()">
                        Abbrechen
                    </button>
                    <button type="button" id="dlsite-detect-btn" class="primary-button" disabled>
                        <i class="fas fa-search"></i> RJ/RE Nummer erkennen
                    </button>
                </div>
            </form>
        </div>
    `);

        // Setup event handlers
        this.setupDLSiteFormHandlers();
    }

    /**
     * Setup event handlers for DLSite form (simplified)
     */
    setupDLSiteFormHandlers() {
        const browseBtn = document.getElementById('browse-dlsite-executable');
        const executableInput = document.getElementById('dlsite-executable-path');
        const detectBtn = document.getElementById('dlsite-detect-btn');
        const manualIdInput = document.getElementById('manual-dlsite-id');

        // Browse for executable - direct file dialog
        browseBtn.addEventListener('click', async () => {
            await this.browseDLSiteExecutable();
        });

        // Detect RJ/RE number when button is clicked
        detectBtn.addEventListener('click', async () => {
            await this.detectDLSiteId();
        });

        // Manual ID input handler
        if (manualIdInput) {
            manualIdInput.addEventListener('input', (e) => {
                const value = e.target.value.toUpperCase();
                e.target.value = value;

                if (this.validateDLSiteId(value)) {
                    this.fetchDLSiteInfoAndProceed(value, executableInput.value);
                }
            });
        }

        // Auto-detect when path changes
        executableInput.addEventListener('change', async () => {
            if (executableInput.value) {
                detectBtn.disabled = false;
            }
        });
    }

    /**
     * Validate DLSite ID format (fixed)
     */
    validateDLSiteId(id) {
        if (!id) return false;

        // Accept RJ123456, RE123456 format
        const pattern = /^(RJ|RE)\d{6,}$/i;
        return pattern.test(id.toUpperCase());
    }

    /**
     * Parse executable path into directory and filename (enhanced)
     */
    parseExecutablePath(fullPath) {
        if (!fullPath) {
            return {
                directory: '',
                executable: ''
            };
        }

        // Normalize path separators to forward slashes
        const normalizedPath = fullPath.replace(/\\/g, '/');
        const lastSlash = normalizedPath.lastIndexOf('/');

        if (lastSlash === -1) {
            // No path separator found, assume current directory
            return {
                directory: '.',
                executable: fullPath
            };
        }

        const directory = normalizedPath.substring(0, lastSlash).replace(/\//g, '\\'); // Convert back to Windows format
        const executable = normalizedPath.substring(lastSlash + 1);

        return {
            directory: directory,
            executable: executable
        };
    }

    /**
     * Browse for DLSite executable
     */
    async browseDLSiteExecutable() {
        try {
            // Request file dialog from main process
            const result = await ipcRenderer.invoke('show-open-dialog', {
                title: 'DLSite Spiel-Executable auswählen',
                buttonLabel: 'Auswählen',
                filters: [
                    { name: 'Executable Dateien', extensions: ['exe'] },
                    { name: 'Alle Dateien', extensions: ['*'] }
                ],
                properties: ['openFile']
            });

            if (result.canceled || !result.filePaths || result.filePaths.length === 0) {
                console.log('File selection canceled');
                return;
            }

            const selectedPath = result.filePaths[0];
            console.log('Selected executable:', selectedPath);

            // Validate the selected file
            if (!selectedPath.toLowerCase().endsWith('.exe')) {
                this.showError('Bitte wählen Sie eine .exe Datei aus.');
                return;
            }

            // Set the path in the input field
            const executableInput = document.getElementById('dlsite-executable-path');
            if (executableInput) {
                executableInput.value = selectedPath;

                // Enable the detect button
                const detectBtn = document.getElementById('dlsite-detect-btn');
                if (detectBtn) {
                    detectBtn.disabled = false;
                }

                // Auto-trigger RJ/RE detection
                await this.detectDLSiteId();
            }

        } catch (error) {
            console.error('Error opening file dialog:', error);
            this.showError('Fehler beim Öffnen des Datei-Dialogs: ' + error.message);
        }
    }


    /**
     * Setup handlers for the file browser dialog
     */
    setupFileBrowserHandlers() {
        const pathInput = document.getElementById('executable-path-input');
        const validateBtn = document.getElementById('validate-path-btn');
        const confirmBtn = document.getElementById('confirm-path-btn');
        const validationDiv = document.getElementById('path-validation');

        // Auto-validate as user types
        pathInput.addEventListener('input', () => {
            this.debounce(() => this.validateExecutablePath(pathInput.value), 500)();
        });

        // Validate button
        validateBtn.addEventListener('click', () => {
            this.validateExecutablePath(pathInput.value);
        });

        // Confirm button
        confirmBtn.addEventListener('click', () => {
            const path = pathInput.value.trim();
            if (this.isValidExecutablePath(path)) {
                document.getElementById('dlsite-executable-path').value = path;
                document.getElementById('dlsite-detect-btn').disabled = false;
                this.closeModal();
                // Auto-trigger detection
                this.detectDLSiteId();
            }
        });

        // Quick browse buttons
        const quickBrowseButtons = document.querySelectorAll('.quick-browse-btn');
        quickBrowseButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const basePath = btn.dataset.path;
                this.showDirectoryHint(basePath);
            });
        });

        // Handle paste events
        pathInput.addEventListener('paste', (e) => {
            setTimeout(() => {
                // Clean up pasted path
                const cleanPath = this.cleanPathInput(pathInput.value);
                pathInput.value = cleanPath;
                this.validateExecutablePath(cleanPath);
            }, 10);
        });
    }

    /**
     * Validate executable path
     */
    validateExecutablePath(path) {
        const validationDiv = document.getElementById('path-validation');
        const confirmBtn = document.getElementById('confirm-path-btn');

        validationDiv.style.display = 'block';

        if (!path || path.trim().length === 0) {
            validationDiv.innerHTML = `
            <div class="validation-neutral">
                <i class="fas fa-info-circle"></i>
                <span>Geben Sie den Pfad zur Executable-Datei ein</span>
            </div>
        `;
            confirmBtn.disabled = true;
            return false;
        }

        const cleanPath = this.cleanPathInput(path);
        const validation = this.isValidExecutablePath(cleanPath);

        if (validation.isValid) {
            validationDiv.innerHTML = `
            <div class="validation-success">
                <i class="fas fa-check-circle"></i>
                <span>Gültiger Pfad erkannt!</span>
            </div>
        `;
            confirmBtn.disabled = false;

            // Show additional info if RJ/RE detected
            const rjMatch = cleanPath.match(/[RJ|RE]\d{6,}/gi);
            if (rjMatch) {
                validationDiv.innerHTML += `
                <div class="validation-info">
                    <i class="fas fa-star"></i>
                    <span>DLSite ID erkannt: ${rjMatch[0].toUpperCase()}</span>
                </div>
            `;
            }

            return true;
        } else {
            validationDiv.innerHTML = `
            <div class="validation-error">
                <i class="fas fa-exclamation-triangle"></i>
                <span>${validation.error}</span>
            </div>
        `;

            if (validation.suggestions.length > 0) {
                validationDiv.innerHTML += `
                <div class="validation-suggestions">
                    <strong>Vorschläge:</strong>
                    <ul>
                        ${validation.suggestions.map(s => `<li>${s}</li>`).join('')}
                    </ul>
                </div>
            `;
            }

            confirmBtn.disabled = true;
            return false;
        }
    }

    /**
     * Check if path is a valid executable
     */
    isValidExecutablePath(path) {
        const suggestions = [];

        if (!path || path.trim().length === 0) {
            return {
                isValid: false,
                error: 'Pfad ist leer',
                suggestions: ['Geben Sie den vollständigen Pfad zur .exe Datei ein']
            };
        }

        // Clean path
        const cleanPath = path.trim().replace(/^["']|["']$/g, '');

        // Check if it looks like a valid Windows path
        if (!/^[A-Za-z]:\\/.test(cleanPath) && !/^\\\\/.test(cleanPath)) {
            suggestions.push('Pfad sollte mit Laufwerksbuchstaben beginnen (z.B. C:\\)');
            return {
                isValid: false,
                error: 'Ungültiges Pfad-Format',
                suggestions: suggestions
            };
        }

        // Check file extension
        const validExtensions = ['.exe', '.bat', '.cmd', '.jar', '.py'];
        const hasValidExtension = validExtensions.some(ext =>
            cleanPath.toLowerCase().endsWith(ext)
        );

        if (!hasValidExtension) {
            suggestions.push('Datei sollte eine ausführbare Erweiterung haben (.exe, .bat, .cmd)');
            return {
                isValid: false,
                error: 'Keine gültige Executable-Datei',
                suggestions: suggestions
            };
        }

        // Check for common invalid characters
        const invalidChars = ['<', '>', '|', '?', '*'];
        const hasInvalidChars = invalidChars.some(char => cleanPath.includes(char));

        if (hasInvalidChars) {
            return {
                isValid: false,
                error: 'Pfad enthält ungültige Zeichen',
                suggestions: ['Entfernen Sie Zeichen wie < > | ? *']
            };
        }

        return {
            isValid: true,
            error: null,
            suggestions: []
        };
    }

    /**
     * Clean up path input
     */
    cleanPathInput(path) {
        if (!path) return '';

        let cleaned = path.trim();

        // Remove surrounding quotes
        cleaned = cleaned.replace(/^["']|["']$/g, '');

        // Fix common path issues
        cleaned = cleaned.replace(/\//g, '\\'); // Convert forward slashes
        cleaned = cleaned.replace(/\\\\/g, '\\'); // Remove double backslashes

        return cleaned;
    }

    /**
     * Get user downloads path
     */
    getUserDownloadsPath() {
        // Return common downloads paths
        return `${process.env.USERPROFILE || 'C:\\Users\\User'}\\Downloads`;
    }

    /**
     * Show directory hint for quick browse
     */
    showDirectoryHint(basePath) {
        const pathInput = document.getElementById('executable-path-input');
        const placeholder = `${basePath}\\GameFolder\\game.exe`;

        pathInput.placeholder = `z.B. ${placeholder}`;
        pathInput.focus();

        this.showNotification(`Beispiel-Pfad: ${placeholder}`, 'info');
    }

    /**
     * Debounce function for input validation
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    /**
     * Enhanced createModal with custom class support
     */
    createModal(title, content, customClass = '') {
        // Remove existing modal if any
        this.closeModal();

        const modal = document.createElement('div');
        modal.className = `modal ${customClass}`;
        modal.id = 'dust-modal';

        modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h2>${title}</h2>
                <button class="close-modal" onclick="dustApp.closeModal()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                ${content}
            </div>
        </div>
    `;

        document.body.appendChild(modal);

        // Close modal when clicking outside
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeModal();
            }
        });

        // Close modal with Escape key
        const escapeHandler = (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
                document.removeEventListener('keydown', escapeHandler);
            }
        };
        document.addEventListener('keydown', escapeHandler);

        return modal;
    }

    /**
     * Detect DLSite ID from executable path
     */
    async detectDLSiteId() {
        const executablePath = document.getElementById('dlsite-executable-path').value;
        const resultDiv = document.getElementById('dlsite-detection-result');
        const manualDiv = document.getElementById('dlsite-manual-id');

        if (!executablePath) {
            this.showNotification('Bitte wählen Sie zuerst eine Executable-Datei aus.', 'warning');
            return;
        }

        // Show detection result area
        resultDiv.style.display = 'block';
        resultDiv.innerHTML = `
        <div class="detection-status">
            <i class="fas fa-spinner fa-spin"></i>
            <span>Suche nach RJ/RE-Nummer im Pfad...</span>
        </div>
    `;

        // Extract RJ/RE number from path (fixed regex)
        const dlsiteIdPattern = /(RJ|RE)\d{6,}/gi;
        const matches = executablePath.match(dlsiteIdPattern);

        if (matches && matches.length > 0) {
            let dlsiteId = matches[0].toUpperCase();

            // Ensure the ID has the R prefix (fix for missing R)
            if (dlsiteId.startsWith('J') && !dlsiteId.startsWith('RJ')) {
                dlsiteId = 'R' + dlsiteId;
            } else if (dlsiteId.startsWith('E') && !dlsiteId.startsWith('RE')) {
                dlsiteId = 'R' + dlsiteId;
            }

            console.log('Detected DLSite ID:', dlsiteId);

            resultDiv.innerHTML = `
            <div class="detection-success">
                <i class="fas fa-check-circle"></i>
                <span>DLSite ID gefunden: <strong>${dlsiteId}</strong></span>
            </div>
        `;

            // Fetch DLSite info and proceed
            await this.fetchDLSiteInfoAndProceed(dlsiteId, executablePath);

        } else {
            // No ID found, show manual input
            resultDiv.innerHTML = `
            <div class="detection-warning">
                <i class="fas fa-exclamation-triangle"></i>
                <span>Keine RJ/RE-Nummer im Pfad gefunden</span>
            </div>
        `;

            manualDiv.style.display = 'block';
            this.showNotification('Keine RJ/RE-Nummer erkannt. Bitte geben Sie die ID manuell ein.', 'warning');
        }
    }

    /**
     * Fetch DLSite info and proceed with game creation
     */
    async fetchDLSiteInfoAndProceed(dlsiteId, executablePath) {
        try {
            this.setLoading(true);

            // Validate DLSite ID format
            if (!this.validateDLSiteId(dlsiteId)) {
                this.showError('Ungültige DLSite ID. Format: RJ123456 oder RE123456');
                return;
            }

            console.log(`Fetching DLSite info for: ${dlsiteId}`);
            this.showNotification(`Lade DLSite-Informationen für ${dlsiteId}...`, 'info');

            // Fetch from DLSite API
            const result = await this.apiRequest(`/api/dlsite/info/${dlsiteId}`);

            console.log('DLSite API result:', result);

            if (result.success && result.gameInfo) {
                const gameInfo = result.gameInfo;

                // Parse paths
                const pathInfo = this.parseExecutablePath(executablePath);

                // Prepare final game data
                const finalGameData = {
                    ...gameInfo,
                    executable: pathInfo.executable,
                    executablePath: pathInfo.directory,
                    source: 'DLSite',
                    dlsiteId: dlsiteId
                };

                console.log('Final game data:', finalGameData);

                this.closeModal();
                this.showDLSiteConfirmationDialog(finalGameData);

            } else {
                console.warn('DLSite API returned no data:', result);
                this.showError(result.message || `Keine DLSite-Informationen für ${dlsiteId} gefunden`);

                // Show manual input as fallback
                const manualDiv = document.getElementById('dlsite-manual-id');
                if (manualDiv) {
                    manualDiv.style.display = 'block';
                }
            }

        } catch (error) {
            console.error('Error fetching DLSite info:', error);
            this.showError('Fehler beim Laden der DLSite-Informationen: ' + error.message);

            // Show manual input as fallback
            const manualDiv = document.getElementById('dlsite-manual-id');
            if (manualDiv) {
                manualDiv.style.display = 'block';
            }
        } finally {
            this.setLoading(false);
        }
    }

    /**
     * Show DLSite confirmation dialog with fetched info
     */
    showDLSiteConfirmationDialog(gameData) {
        const modal = this.createModal(`DLSite Spiel bestätigen: ${gameData.title}`, `
        <div class="dlsite-confirmation">
            <div class="confirmation-header">
                <div class="game-preview">
                    <img src="${gameData.workImageUrl || 'assets/default-cover.jpg'}" 
                         alt="${gameData.title}" class="game-cover-preview"
                         onerror="this.src='assets/default-cover.jpg'">
                    <div class="game-info-preview">
                        <h3>${gameData.title}</h3>
                        <p><strong>Entwickler:</strong> ${gameData.developer}</p>
                        <p><strong>DLSite ID:</strong> ${gameData.dlsiteId}</p>
                        <p><strong>Genre:</strong> ${gameData.genre || 'Unbekannt'}</p>
                    </div>
                </div>
            </div>
            
            <div class="confirmation-details">
                <h4>Spiel-Details:</h4>
                <div class="detail-grid">
                    <div class="detail-item">
                        <strong>Executable:</strong> ${gameData.executable}
                    </div>
                    <div class="detail-item">
                        <strong>Pfad:</strong> ${gameData.executablePath}
                    </div>
                    <div class="detail-item">
                        <strong>Beschreibung:</strong> ${gameData.description ? gameData.description.substring(0, 100) + '...' : 'Keine Beschreibung'}
                    </div>
                </div>
                
                ${gameData.tags && gameData.tags.length > 0 ? `
                <div class="tags-preview">
                    <strong>Tags:</strong>
                    ${gameData.tags.slice(0, 5).map(tag => `<span class="tag-preview">${tag}</span>`).join('')}
                    ${gameData.tags.length > 5 ? `<span class="tag-more">+${gameData.tags.length - 5} weitere</span>` : ''}
                </div>
                ` : ''}
            </div>
            
            <div class="confirmation-actions">
                <button type="button" class="secondary-button" onclick="dustApp.closeModal()">
                    Abbrechen
                </button>
                <button type="button" class="secondary-button" onclick="dustApp.editDLSiteGameData(${JSON.stringify(gameData).replace(/"/g, '&quot;')})">
                    <i class="fas fa-edit"></i> Bearbeiten
                </button>
                <button type="button" class="primary-button" onclick="dustApp.confirmAddDLSiteGame(${JSON.stringify(gameData).replace(/"/g, '&quot;')})">
                    <i class="fas fa-plus"></i> Spiel hinzufügen
                </button>
            </div>
        </div>
    `);
    }

    /**
     * Parse executable path into directory and filename
     */
    parseExecutablePath(fullPath) {
        const path = fullPath.replace(/\\/g, '/'); // Normalize path separators
        const lastSlash = path.lastIndexOf('/');

        if (lastSlash === -1) {
            return {
                directory: '.',
                executable: fullPath
            };
        }

        return {
            directory: path.substring(0, lastSlash),
            executable: path.substring(lastSlash + 1)
        };
    }

    /**
     * Validate DLSite ID format
     */
    validateDLSiteId(id) {
        if (!id) return false;
        const pattern = /^[A-Z]{2}\d{6,}$/;
        return pattern.test(id.toUpperCase());
    }

    /**
     * Confirm and add DLSite game
     */
    async confirmAddDLSiteGame(gameData) {
        try {
            this.setLoading(true);
            this.closeModal();

            const result = await this.apiRequest('/api/games/add', {
                method: 'POST',
                body: JSON.stringify({
                    gameInfo: gameData,
                    gameFolder: gameData.executablePath,
                    executablePath: gameData.executable
                })
            });

            if (result.success) {
                this.showNotification(`DLSite-Spiel "${gameData.title}" erfolgreich hinzugefügt!`, 'success');
                await this.loadGames(); // Refresh the game library
            } else {
                this.showError(result.message || 'Fehler beim Hinzufügen des Spiels');
            }

        } catch (error) {
            console.error('Error adding DLSite game:', error);
            this.showError('Fehler beim Hinzufügen des Spiels: ' + error.message);
        } finally {
            this.setLoading(false);
        }
    }

    /**
     * Edit DLSite game data before adding
     */
    editDLSiteGameData(gameData) {
        this.closeModal();
        // Show the manual form pre-filled with DLSite data
        this.showManualGameDialog(gameData);
    }

    /**
     * Manual game dialog (original implementation, now as fallback)
     */
    showManualGameDialog(prefillData = null) {
        const data = prefillData || {};

        const modal = this.createModal('Spiel manuell hinzufügen', `
        <form id="manual-game-form">
            <div class="form-group">
                <label for="game-title">Spieltitel *</label>
                <input type="text" id="game-title" name="title" required 
                       value="${data.title || ''}" placeholder="z.B. Final Fantasy VII">
            </div>
            
            <div class="form-group">
                <label for="game-folder">Spieleordner *</label>
                <div class="executable-path">
                    <input type="text" id="game-folder" name="gameFolder" required 
                           value="${data.executablePath || ''}" placeholder="C:\\Games\\MeinSpiel">
                    <button type="button" id="browse-folder-btn" class="secondary-button">
                        <i class="fas fa-folder"></i> Durchsuchen
                    </button>
                </div>
            </div>
            
            <div class="form-group">
                <label for="game-executable">Executable-Datei *</label>
                <input type="text" id="game-executable" name="executable" required 
                       value="${data.executable || ''}" placeholder="game.exe">
            </div>
            
            <div class="form-group">
                <label for="game-developer">Entwickler</label>
                <input type="text" id="game-developer" name="developer" 
                       value="${data.developer || ''}" placeholder="Square Enix">
            </div>
            
            <div class="form-group">
                <label for="game-genre">Genre</label>
                <select id="game-genre" name="genre">
                    <option value="">Genre auswählen</option>
                    <option value="Action" ${data.genre === 'Action' ? 'selected' : ''}>Action</option>
                    <option value="Adventure" ${data.genre === 'Adventure' ? 'selected' : ''}>Adventure</option>
                    <option value="RPG" ${data.genre === 'RPG' ? 'selected' : ''}>RPG</option>
                    <option value="Strategy" ${data.genre === 'Strategy' ? 'selected' : ''}>Strategy</option>
                    <option value="Simulation" ${data.genre === 'Simulation' ? 'selected' : ''}>Simulation</option>
                    <option value="Visual Novel" ${data.genre === 'Visual Novel' ? 'selected' : ''}>Visual Novel</option>
                    <option value="Puzzle" ${data.genre === 'Puzzle' ? 'selected' : ''}>Puzzle</option>
                    <option value="Other" ${data.genre === 'Other' ? 'selected' : ''}>Sonstiges</option>
                </select>
            </div>
            
            <div class="form-group">
                <label for="game-source">Plattform</label>
                <select id="game-source" name="source">
                    <option value="Local" ${data.source === 'Local' ? 'selected' : ''}>Lokal</option>
                    <option value="Steam" ${data.source === 'Steam' ? 'selected' : ''}>Steam</option>
                    <option value="DLSite" ${data.source === 'DLSite' ? 'selected' : ''}>DLSite</option>
                    <option value="Itch.io" ${data.source === 'Itch.io' ? 'selected' : ''}>Itch.io</option>
                    <option value="Other" ${data.source === 'Other' ? 'selected' : ''}>Sonstiges</option>
                </select>
            </div>
            
            ${data.dlsiteId ? `
            <div class="form-group">
                <label for="dlsite-id">DLSite ID</label>
                <input type="text" id="dlsite-id" name="dlsiteId" readonly
                       value="${data.dlsiteId}" style="background-color: #f0f0f0;">
            </div>
            ` : ''}
            
            <div class="form-group full-width">
                <label for="game-description">Beschreibung</label>
                <textarea id="game-description" name="description" rows="3">${data.description || ''}</textarea>
            </div>
            
            <div class="form-actions">
                <button type="button" class="secondary-button" onclick="dustApp.closeModal()">
                    Abbrechen
                </button>
                <button type="submit" class="primary-button">
                    <i class="fas fa-plus"></i> Spiel hinzufügen
                </button>
            </div>
        </form>
    `);

        // Setup form handler
        const form = document.getElementById('manual-game-form');
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.handleAddGameSubmit(form);
        });

        // Browse folder handler
        const browseFolderBtn = document.getElementById('browse-folder-btn');
        browseFolderBtn.addEventListener('click', () => {
            const path = prompt('Geben Sie den Pfad zum Spieleordner ein:');
            if (path) {
                document.getElementById('game-folder').value = path.trim().replace(/^["']|["']$/g, '');
            }
        });
    }

    /**
     * Placeholder functions for other platforms
     */
    showSteamGameDialog() {
        this.showNotification('Steam-Integration kommt in Version 0.3.0', 'info');
        this.showManualGameDialog({ source: 'Steam' });
    }

    showItchioGameDialog() {
        this.showNotification('Itch.io-Integration kommt in Version 0.4.0', 'info');
        this.showManualGameDialog({ source: 'Itch.io' });
    }

    /**
     * Handle add game form submission
     */
    async handleAddGameSubmit(form) {
        try {
            this.setLoading(true);

            const formData = new FormData(form);
            const gameInfo = Object.fromEntries(formData.entries());

            // Validate required fields
            if (!gameInfo.title || !gameInfo.gameFolder || !gameInfo.executable) {
                this.showError('Bitte füllen Sie alle Pflichtfelder aus.');
                return;
            }

            // Validate executable path
            let executablePath = gameInfo.executable;
            if (executablePath.includes('/') || executablePath.includes('\\')) {
                // If it contains path separators, treat as relative to game folder
                executablePath = executablePath.replace(/^[/\\]+/, ''); // Remove leading slashes
            }

            // Validate game folder path
            const gameFolder = gameInfo.gameFolder.trim();
            if (!gameFolder) {
                this.showError('Spieleordner darf nicht leer sein.');
                return;
            }

            // Prepare game data with enhanced metadata
            const enhancedGameInfo = {
                ...gameInfo,
                // Ensure all fields are properly formatted
                title: gameInfo.title.trim(),
                developer: gameInfo.developer?.trim() || 'Unknown',
                genre: gameInfo.genre || 'Unknown',
                source: gameInfo.source || 'Local',
                description: gameInfo.description?.trim() || '',
                // Add timestamp
                addedDate: new Date().toISOString(),
                // Convert tags if they exist
                tags: gameInfo.tags ? (Array.isArray(gameInfo.tags) ? gameInfo.tags : gameInfo.tags.split(',').map(t => t.trim())) : []
            };

            console.log('Adding game with enhanced info:', enhancedGameInfo);

            // Submit to backend
            const result = await this.apiRequest('/api/games/add', {
                method: 'POST',
                body: JSON.stringify({
                    gameInfo: enhancedGameInfo,
                    gameFolder: gameFolder,
                    executablePath: executablePath
                })
            });

            if (result.success) {
                this.showNotification(`Spiel "${enhancedGameInfo.title}" erfolgreich hinzugefügt!`, 'success');
                this.closeModal();
                await this.loadGames(); // Refresh the game library

                // Optional: Show game details of newly added game
                if (result.gameId) {
                    setTimeout(() => {
                        this.showGameDetails(result.gameId);
                    }, 1000);
                }
            } else {
                this.showError(result.message || 'Fehler beim Hinzufügen des Spiels');
            }

        } catch (error) {
            console.error('Error adding game:', error);
            this.showError('Fehler beim Hinzufügen des Spiels: ' + error.message);
        } finally {
            this.setLoading(false);
        }
    }
    /**
     * Enhanced notification system for game operations
     */
    showGameOperationNotification(operation, gameTitle, success, message = '') {
        const operations = {
            'added': { icon: 'plus-circle', successMsg: 'hinzugefügt', errorMsg: 'Fehler beim Hinzufügen' },
            'updated': { icon: 'edit', successMsg: 'aktualisiert', errorMsg: 'Fehler beim Aktualisieren' },
            'deleted': { icon: 'trash', successMsg: 'entfernt', errorMsg: 'Fehler beim Entfernen' },
            'launched': { icon: 'play', successMsg: 'gestartet', errorMsg: 'Fehler beim Starten' }
        };

        const op = operations[operation];
        if (!op) return;

        if (success) {
            this.showNotification(`${gameTitle} wurde erfolgreich ${op.successMsg}!`, 'success');
        } else {
            this.showNotification(`${op.errorMsg}: ${gameTitle}. ${message}`, 'error');
        }
    }

    /**
     * Validate game data before submission
     */
    validateGameData(gameInfo) {
        const errors = [];

        // Required fields
        if (!gameInfo.title?.trim()) {
            errors.push('Spieltitel ist erforderlich');
        }

        if (!gameInfo.gameFolder?.trim()) {
            errors.push('Spieleordner ist erforderlich');
        }

        if (!gameInfo.executable?.trim()) {
            errors.push('Executable-Datei ist erforderlich');
        }

        // Validate DLSite ID format if provided
        if (gameInfo.dlsiteId && !this.validateDLSiteId(gameInfo.dlsiteId)) {
            errors.push('DLSite ID hat ein ungültiges Format (erwarte RJ/RE + Nummer)');
        }

        // Validate file extensions
        if (gameInfo.executable) {
            const validExtensions = ['.exe', '.bat', '.cmd', '.jar', '.py', '.sh', '.run', '.app'];
            const hasValidExtension = validExtensions.some(ext =>
                gameInfo.executable.toLowerCase().endsWith(ext)
            );

            if (!hasValidExtension) {
                errors.push('Executable-Datei sollte eine gültige Erweiterung haben (.exe, .bat, .jar, etc.)');
            }
        }

        return {
            isValid: errors.length === 0,
            errors: errors
        };
    }

    /**
     * Enhanced file path handling
     */
    normalizeFilePath(path) {
        if (!path) return '';

        // Normalize path separators
        let normalized = path.replace(/\\/g, '/');

        // Remove quotes if present
        normalized = normalized.replace(/^["']|["']$/g, '');

        // Remove trailing slashes
        normalized = normalized.replace(/\/+$/, '');

        return normalized.trim();
    }

    /**
     * Check if game already exists (duplicate detection)
     */
    async checkGameExists(gameInfo) {
        try {
            // Simple check based on title and executable path
            const existingGames = this.games || [];

            const duplicates = existingGames.filter(game => {
                const sameTitle = game.title.toLowerCase() === gameInfo.title.toLowerCase();
                const samePath = game.executablePath && gameInfo.gameFolder &&
                    this.normalizeFilePath(game.executablePath) === this.normalizeFilePath(gameInfo.gameFolder);
                const sameExecutable = game.executable === gameInfo.executable;

                return sameTitle && (samePath || sameExecutable);
            });

            return duplicates.length > 0 ? duplicates[0] : null;

        } catch (error) {
            console.warn('Error checking for duplicates:', error);
            return null;
        }
    }

    /**
     * Show duplicate game warning
     */
    async showDuplicateWarning(existingGame, newGameInfo) {
        return new Promise((resolve) => {
            const modal = this.createModal('Spiel bereits vorhanden', `
            <div class="duplicate-warning">
                <div class="warning-icon">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
                
                <h3>Mögliches Duplikat erkannt</h3>
                
                <p>Ein Spiel mit ähnlichen Daten ist bereits in der Bibliothek:</p>
                
                <div class="game-comparison">
                    <div class="existing-game">
                        <h4>Vorhandenes Spiel:</h4>
                        <p><strong>Titel:</strong> ${existingGame.title}</p>
                        <p><strong>Pfad:</strong> ${existingGame.executablePath}</p>
                        <p><strong>Executable:</strong> ${existingGame.executable}</p>
                    </div>
                    
                    <div class="new-game">
                        <h4>Neues Spiel:</h4>
                        <p><strong>Titel:</strong> ${newGameInfo.title}</p>
                        <p><strong>Pfad:</strong> ${newGameInfo.gameFolder}</p>
                        <p><strong>Executable:</strong> ${newGameInfo.executable}</p>
                    </div>
                </div>
                
                <p>Möchten Sie trotzdem fortfahren?</p>
                
                <div class="form-actions">
                    <button type="button" class="secondary-button" onclick="dustApp.resolveDuplicate(false)">
                        Abbrechen
                    </button>
                    <button type="button" class="secondary-button" onclick="dustApp.resolveDuplicate('update')">
                        Vorhandenes aktualisieren
                    </button>
                    <button type="button" class="primary-button" onclick="dustApp.resolveDuplicate(true)">
                        Trotzdem hinzufügen
                    </button>
                </div>
            </div>
        `);

            // Store resolver function
            this._duplicateResolver = resolve;
        });
    }

    /**
     * Resolve duplicate game decision
     */
    resolveDuplicate(decision) {
        if (this._duplicateResolver) {
            this._duplicateResolver(decision);
            this._duplicateResolver = null;
        }
        this.closeModal();
    }

    /**
     * Enhanced handleAddGameSubmit with duplicate checking
     */
    async handleAddGameSubmitWithDuplicateCheck(form) {
        try {
            this.setLoading(true);

            const formData = new FormData(form);
            const gameInfo = Object.fromEntries(formData.entries());

            // Validate game data
            const validation = this.validateGameData(gameInfo);
            if (!validation.isValid) {
                this.showError('Validierungsfehler:\n' + validation.errors.join('\n'));
                return;
            }

            // Check for duplicates
            const existingGame = await this.checkGameExists(gameInfo);
            if (existingGame) {
                const decision = await this.showDuplicateWarning(existingGame, gameInfo);

                if (decision === false) {
                    // User cancelled
                    return;
                } else if (decision === 'update') {
                    // Update existing game
                    await this.updateExistingGameWithNewData(existingGame.id, gameInfo);
                    return;
                }
                // If decision === true, continue with adding new game
            }

            // Proceed with adding the game
            await this.handleAddGameSubmit(form);

        } catch (error) {
            console.error('Error in enhanced add game:', error);
            this.showError('Fehler beim Hinzufügen des Spiels: ' + error.message);
        } finally {
            this.setLoading(false);
        }
    }

    /**
     * Update existing game with new data
     */
    async updateExistingGameWithNewData(gameId, newGameInfo) {
        try {
            const result = await this.apiRequest(`/api/games/${gameId}/update`, {
                method: 'PUT',
                body: JSON.stringify({ updates: newGameInfo })
            });

            if (result.success) {
                this.showNotification('Vorhandenes Spiel wurde aktualisiert!', 'success');
                this.closeModal();
                await this.loadGames();
            } else {
                this.showError(result.message || 'Fehler beim Aktualisieren des Spiels');
            }

        } catch (error) {
            console.error('Error updating existing game:', error);
            this.showError('Fehler beim Aktualisieren: ' + error.message);
        }
    }

    /**
     * Show edit game dialog
     */
    showEditGameDialog(game) {
        const modal = this.createModal(`Spiel bearbeiten: ${game.title}`, `
        <form id="edit-game-form">
            <input type="hidden" name="gameId" value="${game.id}">
            
            <div class="form-group">
                <label for="edit-game-title">Spieltitel *</label>
                <input type="text" id="edit-game-title" name="title" required 
                       value="${game.title || ''}">
            </div>
            
            <div class="form-group">
                <label for="edit-game-folder">Spieleordner *</label>
                <input type="text" id="edit-game-folder" name="executablePath" required 
                       value="${game.executablePath || ''}">
            </div>
            
            <div class="form-group">
                <label for="edit-game-executable">Executable *</label>
                <input type="text" id="edit-game-executable" name="executable" required 
                       value="${game.executable || ''}">
            </div>
            
            <div class="form-group">
                <label for="edit-game-developer">Entwickler</label>
                <input type="text" id="edit-game-developer" name="developer" 
                       value="${game.developer || ''}">
            </div>
            
            <div class="form-group">
                <label for="edit-game-genre">Genre</label>
                <select id="edit-game-genre" name="genre">
                    <option value="">Genre auswählen</option>
                    <option value="Action" ${game.genre === 'Action' ? 'selected' : ''}>Action</option>
                    <option value="Adventure" ${game.genre === 'Adventure' ? 'selected' : ''}>Adventure</option>
                    <option value="RPG" ${game.genre === 'RPG' ? 'selected' : ''}>RPG</option>
                    <option value="Strategy" ${game.genre === 'Strategy' ? 'selected' : ''}>Strategy</option>
                    <option value="Simulation" ${game.genre === 'Simulation' ? 'selected' : ''}>Simulation</option>
                    <option value="Sports" ${game.genre === 'Sports' ? 'selected' : ''}>Sports</option>
                    <option value="Racing" ${game.genre === 'Racing' ? 'selected' : ''}>Racing</option>
                    <option value="Visual Novel" ${game.genre === 'Visual Novel' ? 'selected' : ''}>Visual Novel</option>
                    <option value="Puzzle" ${game.genre === 'Puzzle' ? 'selected' : ''}>Puzzle</option>
                    <option value="Indie" ${game.genre === 'Indie' ? 'selected' : ''}>Indie</option>
                    <option value="Other" ${game.genre === 'Other' ? 'selected' : ''}>Sonstiges</option>
                </select>
            </div>
            
            <div class="form-group">
                <label for="edit-game-source">Plattform</label>
                <select id="edit-game-source" name="source">
                    <option value="Local" ${game.source === 'Local' ? 'selected' : ''}>Lokal</option>
                    <option value="Steam" ${game.source === 'Steam' ? 'selected' : ''}>Steam</option>
                    <option value="DLSite" ${game.source === 'DLSite' ? 'selected' : ''}>DLSite</option>
                    <option value="Itch.io" ${game.source === 'Itch.io' ? 'selected' : ''}>Itch.io</option>
                    <option value="Other" ${game.source === 'Other' ? 'selected' : ''}>Sonstiges</option>
                </select>
            </div>
            
            <div class="form-group full-width">
                <label for="edit-game-description">Beschreibung</label>
                <textarea id="edit-game-description" name="description" rows="3">${game.description || ''}</textarea>
            </div>
            
            <div class="form-actions">
                <button type="button" class="danger-button" onclick="dustApp.confirmDeleteGame(${game.id})">
                    <i class="fas fa-trash"></i> Löschen
                </button>
                <button type="button" class="secondary-button" onclick="dustApp.closeModal()">
                    Abbrechen
                </button>
                <button type="submit" class="primary-button">
                    <i class="fas fa-save"></i> Speichern
                </button>
            </div>
        </form>
    `);

        // Handle form submission
        const form = document.getElementById('edit-game-form');
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.handleEditGameSubmit(form);
        });
    }

    /**
     * Handle edit game form submission
     */
    async handleEditGameSubmit(form) {
        try {
            this.setLoading(true);

            const formData = new FormData(form);
            const updates = Object.fromEntries(formData.entries());
            const gameId = parseInt(updates.gameId);
            delete updates.gameId;

            console.log('Updating game:', gameId, updates);

            const result = await this.apiRequest(`/api/games/${gameId}/update`, {
                method: 'PUT',
                body: JSON.stringify({ updates })
            });

            if (result.success) {
                this.showNotification('Spiel erfolgreich aktualisiert!', 'success');
                this.closeModal();
                await this.loadGames(); // Refresh the game library
            } else {
                this.showError(result.message || 'Fehler beim Aktualisieren des Spiels');
            }

        } catch (error) {
            console.error('Error updating game:', error);
            this.showError('Fehler beim Aktualisieren des Spiels: ' + error.message);
        } finally {
            this.setLoading(false);
        }
    }

    /**
     * Confirm game deletion
     */
    confirmDeleteGame(gameId) {
        const game = this.games.find(g => g.id === gameId);
        if (!game) return;

        const confirmModal = this.createModal('Spiel löschen', `
        <div class="confirm-modal">
            <p>Möchten Sie das Spiel <strong>"${game.title}"</strong> wirklich aus der Bibliothek entfernen?</p>
            <p><small>Die Spieldateien werden nicht gelöscht, nur der Eintrag in der Dust-Bibliothek.</small></p>
            
            <div class="form-actions">
                <button type="button" class="secondary-button" onclick="dustApp.closeModal()">
                    Abbrechen
                </button>
                <button type="button" class="danger-button" onclick="dustApp.deleteGame(${gameId})">
                    <i class="fas fa-trash"></i> Entfernen
                </button>
            </div>
        </div>
    `);
    }

    /**
     * Delete a game
     */
    async deleteGame(gameId) {
        try {
            this.setLoading(true);

            const result = await this.apiRequest(`/api/games/${gameId}/delete`, {
                method: 'DELETE'
            });

            if (result.success) {
                this.showNotification('Spiel aus der Bibliothek entfernt', 'success');
                this.closeModal();
                await this.loadGames(); // Refresh the game library
            } else {
                this.showError(result.message || 'Fehler beim Löschen des Spiels');
            }

        } catch (error) {
            console.error('Error deleting game:', error);
            this.showError('Fehler beim Löschen des Spiels: ' + error.message);
        } finally {
            this.setLoading(false);
        }
    }

    /**
     * Create a modal dialog
     */
    createModal(title, content) {
        // Remove existing modal if any
        this.closeModal();

        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.id = 'dust-modal';

        modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h2>${title}</h2>
                <button class="close-modal" onclick="dustApp.closeModal()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                ${content}
            </div>
        </div>
    `;

        document.body.appendChild(modal);

        // Close modal when clicking outside
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeModal();
            }
        });

        // Close modal with Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
            }
        });

        return modal;
    }

    /**
     * Close the current modal
     */
    closeModal() {
        const modal = document.getElementById('dust-modal');
        if (modal) {
            modal.remove();
        }
    }

    /**
     * Enhanced notification system
     */
    showNotification(message, type = 'info') {
        console.log(`Notification [${type}]: ${message}`);

        // Remove existing notifications
        const existingNotifications = document.querySelectorAll('.notification');
        existingNotifications.forEach(n => n.remove());

        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;

        const icon = this.getNotificationIcon(type);

        notification.innerHTML = `
        <div class="notification-content">
            <i class="fas fa-${icon}"></i>
            <span>${message}</span>
            <button class="close-notification" onclick="this.parentElement.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;

        // Add to page
        document.body.appendChild(notification);

        // Show with animation
        setTimeout(() => notification.classList.add('show'), 10);

        // Auto remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.classList.remove('show');
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.remove();
                    }
                }, 300);
            }
        }, 5000);

        return notification;
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
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } catch (error) {
            return 'Invalid date';
        }
    }
    /**
 * Initialize UI navigation and missing event listeners
 */
    initUINavigation() {
        // Navigation between pages
        const navButtons = document.querySelectorAll('.nav-button');
        const pages = document.querySelectorAll('.page');

        navButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const targetPage = button.getAttribute('data-page');

                // Remove active class from all nav buttons and pages
                navButtons.forEach(btn => btn.classList.remove('active'));
                pages.forEach(page => page.classList.remove('active'));

                // Add active class to clicked button and target page
                button.classList.add('active');
                const targetPageElement = document.getElementById(targetPage);
                if (targetPageElement) {
                    targetPageElement.classList.add('active');
                }

                console.log(`Navigated to: ${targetPage}`);
            });
        });
    }

    /**
     * Initialize missing UI event listeners
     */
    initMissingEventListeners() {
        // Search functionality
        const searchBar = document.querySelector('.search-bar');
        if (searchBar) {
            searchBar.addEventListener('input', (e) => {
                this.filterGames(e.target.value);
            });
        }

        // Filter dropdowns
        const genreFilter = document.getElementById('genre-filter');
        const sourceFilter = document.getElementById('source-filter');

        if (genreFilter) {
            genreFilter.addEventListener('change', (e) => {
                this.applyFilters();
            });
        }

        if (sourceFilter) {
            sourceFilter.addEventListener('change', (e) => {
                this.applyFilters();
            });
        }

        // View toggle button
        const viewToggle = document.getElementById('view-toggle');
        if (viewToggle) {
            viewToggle.addEventListener('click', (e) => {
                this.toggleView();
            });
        }

        // Refresh and scan buttons
        const refreshBtn = document.getElementById('refresh-btn');
        const scanBtn = document.getElementById('scan-games-btn');

        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadGames();
            });
        }

        if (scanBtn) {
            scanBtn.addEventListener('click', () => {
                this.scanGames();
            });
        }
    }

    /**
     * Toggle between grid and list view
     */
    toggleView() {
        const gameContainer = document.querySelector('.game-grid');
        const viewToggleBtn = document.getElementById('view-toggle');
        const viewToggleIcon = viewToggleBtn.querySelector('i');

        if (this.currentView === 'grid') {
            this.currentView = 'list';
            gameContainer.className = 'game-list';
            viewToggleIcon.className = 'fas fa-th';
            viewToggleBtn.title = 'Grid-Ansicht';
        } else {
            this.currentView = 'grid';
            gameContainer.className = 'game-grid';
            viewToggleIcon.className = 'fas fa-list';
            viewToggleBtn.title = 'Listen-Ansicht';
        }

        this.renderGames();
    }

    /**
     * Apply combined filters
     */
    applyFilters() {
        const searchTerm = document.querySelector('.search-bar')?.value?.toLowerCase().trim() || '';
        const genreFilter = document.getElementById('genre-filter')?.value || 'all';
        const sourceFilter = document.getElementById('source-filter')?.value || 'all';

        this.filteredGames = this.games.filter(game => {
            // Search filter
            const matchesSearch = !searchTerm ||
                game.title.toLowerCase().includes(searchTerm) ||
                (game.developer && game.developer.toLowerCase().includes(searchTerm)) ||
                (game.genre && game.genre.toLowerCase().includes(searchTerm)) ||
                (game.tags && game.tags.some(tag => tag.toLowerCase().includes(searchTerm)));

            // Genre filter
            const matchesGenre = genreFilter === 'all' ||
                (game.genre && game.genre.toLowerCase() === genreFilter.toLowerCase());

            // Source filter
            const matchesSource = sourceFilter === 'all' ||
                (game.source && game.source.toLowerCase() === sourceFilter.toLowerCase());

            return matchesSearch && matchesGenre && matchesSource;
        });

        this.renderGames();
    }

    /**
     * Update filter options based on available games
     */
    updateFilterOptions() {
        const genreFilter = document.getElementById('genre-filter');
        const sourceFilter = document.getElementById('source-filter');

        if (genreFilter && this.games.length > 0) {
            // Get unique genres
            const genres = [...new Set(this.games.map(game => game.genre).filter(Boolean))];

            // Clear existing options except "All"
            genreFilter.innerHTML = '<option value="all">Alle Genres</option>';

            // Add genre options
            genres.sort().forEach(genre => {
                const option = document.createElement('option');
                option.value = genre;
                option.textContent = genre;
                genreFilter.appendChild(option);
            });
        }

        if (sourceFilter && this.games.length > 0) {
            // Get unique sources
            const sources = [...new Set(this.games.map(game => game.source).filter(Boolean))];

            // Clear existing options except "All"
            sourceFilter.innerHTML = '<option value="all">Alle Quellen</option>';

            // Add source options
            sources.sort().forEach(source => {
                const option = document.createElement('option');
                option.value = source;
                option.textContent = source;
                sourceFilter.appendChild(option);
            });
        }
    }

    /**
     * Enhanced game card generation for better UI
     */
    generateGameCardHTML(game) {
        const coverImage = game.coverImage || 'assets/default-cover.jpg';
        const lastPlayed = game.lastPlayed ? this.formatDate(game.lastPlayed) : 'Nie gespielt';
        const playTime = this.formatPlayTime(game.playTime || 0);

        return `
        <div class="game-card" data-game-id="${game.id}">
            <div class="game-image" style="background-image: url('${coverImage}');">
                <div class="game-actions">
                    <button class="play-btn" data-action="launch" data-game-id="${game.id}" title="Spiel starten">
                        <i class="fas fa-play"></i>
                    </button>
                    <button class="info-btn" data-action="info" data-game-id="${game.id}" title="Details anzeigen">
                        <i class="fas fa-info"></i>
                    </button>
                </div>
            </div>
            <div class="game-info">
                <h3 class="game-title" title="${game.title}">${game.title}</h3>
                <div class="game-meta">
                    <span class="game-developer">${game.developer || 'Unbekannt'}</span>
                    <span class="game-source">${game.source || 'Lokal'}</span>
                </div>
                <div class="game-details">
                    <span>Gespielt: ${playTime}</span>
                    <span>Zuletzt: ${lastPlayed}</span>
                </div>
            </div>
        </div>
    `;
    }

    /**
     * Enhanced game list item generation
     */
    generateGameListItemHTML(game) {
        const coverImage = game.coverImage || 'assets/default-cover.jpg';
        const lastPlayed = game.lastPlayed ? this.formatDate(game.lastPlayed) : 'Nie gespielt';
        const playTime = this.formatPlayTime(game.playTime || 0);

        return `
        <div class="game-card list-view" data-game-id="${game.id}">
            <div class="game-image" style="background-image: url('${coverImage}');"></div>
            <div class="game-info">
                <h3 class="game-title">${game.title}</h3>
                <div class="game-meta">
                    <span><strong>Entwickler:</strong> ${game.developer || 'Unbekannt'}</span>
                    <span><strong>Genre:</strong> ${game.genre || 'Unbekannt'}</span>
                    <span><strong>Quelle:</strong> ${game.source || 'Lokal'}</span>
                </div>
                <div class="game-details">
                    <span><strong>Spielzeit:</strong> ${playTime}</span>
                    <span><strong>Zuletzt gespielt:</strong> ${lastPlayed}</span>
                </div>
            </div>
            <div class="game-actions">
                <button class="primary-button" data-action="launch" data-game-id="${game.id}">
                    <i class="fas fa-play"></i> Starten
                </button>
                <button class="secondary-button" data-action="info" data-game-id="${game.id}">
                    <i class="fas fa-info"></i> Details
                </button>
            </div>
        </div>
    `;
    }

    /**
     * Handle "no games" state
     */
    renderEmptyState() {
        const gameContainer = this.currentView === 'grid' ?
            document.querySelector('.game-grid') :
            document.querySelector('.game-list') || document.querySelector('.game-grid');

        if (!gameContainer) return;

        gameContainer.innerHTML = `
        <div class="empty-library">
            <i class="fas fa-gamepad placeholder-icon"></i>
            <h3>Keine Spiele gefunden</h3>
            <p>Füge Spiele hinzu oder scanne deine Spieleverzeichnisse.</p>
            <button class="primary-button" onclick="dustApp.showAddGameDialog()">
                <i class="fas fa-plus"></i> Spiel hinzufügen
            </button>
            <button class="secondary-button" onclick="dustApp.scanGames()" style="margin-top: 10px;">
                <i class="fas fa-search"></i> Spiele scannen
            </button>
        </div>
    `;
    }

    /**
     * Enhanced render games function
     */
    renderGames() {
        const gameContainer = this.currentView === 'grid' ?
            document.querySelector('.game-grid') :
            document.querySelector('.game-list') || document.querySelector('.game-grid');

        if (!gameContainer) {
            console.error('Game container not found');
            return;
        }

        // Update container class
        gameContainer.className = this.currentView === 'grid' ? 'game-grid' : 'game-list';

        if (this.filteredGames.length === 0) {
            this.renderEmptyState();
            return;
        }

        const gamesHTML = this.filteredGames.map(game => {
            return this.currentView === 'grid' ?
                this.generateGameCardHTML(game) :
                this.generateGameListItemHTML(game);
        }).join('');

        gameContainer.innerHTML = gamesHTML;

        // Re-attach event listeners
        this.addGameClickListeners();

        // Update filter options
        this.updateFilterOptions();

        console.log(`Rendered ${this.filteredGames.length} games in ${this.currentView} view`);
    }

    /**
     * Initialize everything when DOM is ready
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
                this.showError('Backend ist nicht bereit. Bitte starte die Anwendung neu.');
                return;
            }

            // Initialize UI components
            this.initEventListeners();
            this.initUINavigation();
            this.initMissingEventListeners();
            this.initUI();

            // Load games
            await this.loadGames();

            console.log('Dust Game Manager erfolgreich initialisiert');
            this.showNotification('Dust Game Manager gestartet', 'success');

        } catch (error) {
            console.error('Error initializing Dust App:', error);
            this.showError('Fehler beim Initialisieren der Anwendung');
        }
    }
    // Fügen Sie diese Methoden in Ihre bestehende DustApp Klasse ein:

    /**
     * Initialize VPN functionality
     */
    async initVPN() {
        console.log('Initializing VPN functionality...');

        // Get VPN UI elements
        this.vpnToggleBtn = document.getElementById('vpn-toggle-btn');
        this.vpnConfigBtn = document.getElementById('vpn-config-btn');
        this.vpnStatusLight = document.getElementById('vpn-status-light');
        this.vpnStatusText = document.getElementById('vpn-status-text');

        if (!this.vpnToggleBtn || !this.vpnStatusLight || !this.vpnStatusText) {
            console.error('VPN UI elements not found');
            return;
        }

        // Setup event listeners
        this.setupVPNEventListeners();

        // Initialize VPN status
        await this.updateVPNStatus();

        // Start monitoring
        this.startVPNMonitoring();

        console.log('VPN functionality initialized');
    }

    /**
     * Setup VPN event listeners
     */
    setupVPNEventListeners() {
        if (this.vpnToggleBtn) {
            this.vpnToggleBtn.addEventListener('click', async () => {
                await this.toggleVPN();
            });
        }

        if (this.vpnConfigBtn) {
            this.vpnConfigBtn.addEventListener('click', async () => {
                await this.showVPNConfigDialog();
            });
        }
    }

    /**
     * Toggle VPN connection
     */
    async toggleVPN() {
        try {
            this.setVPNLoading(true);

            const response = await this.apiRequest('/api/vpn/toggle', {
                method: 'POST'
            });

            if (response.success) {
                this.showNotification(response.message, 'success');
                await this.updateVPNStatus();
            } else {
                this.showError(response.message || 'VPN toggle failed');
            }

        } catch (error) {
            console.error('VPN toggle error:', error);
            this.showError('VPN error: ' + error.message);
        } finally {
            this.setVPNLoading(false);
        }
    }

    /**
     * Update VPN status display
     */
    async updateVPNStatus() {
        try {
            const response = await this.apiRequest('/api/vpn/status');

            if (response.success) {
                this.updateVPNUI(response.status);
                this.vpnStatus = response.status;
            } else {
                this.updateVPNUI({ connected: false });
            }

        } catch (error) {
            console.error('VPN status error:', error);
            this.updateVPNUI({ connected: false });
        }
    }

    /**
     * Update VPN UI elements
     */
    updateVPNUI(status) {
        const isConnected = status.connected;

        // Update status light
        if (this.vpnStatusLight) {
            this.vpnStatusLight.className = isConnected ?
                'status-light connected' : 'status-light disconnected';
        }

        // Update status text  
        if (this.vpnStatusText) {
            this.vpnStatusText.textContent = isConnected ? 'Connected' : 'Disconnected';
        }

        // Update toggle button
        if (this.vpnToggleBtn) {
            const span = this.vpnToggleBtn.querySelector('span');
            if (span) {
                span.textContent = isConnected ? 'Disconnect VPN' : 'Connect VPN';
            }

            this.vpnToggleBtn.className = isConnected ?
                'vpn-toggle-btn connected' : 'vpn-toggle-btn disconnected';

            this.vpnToggleBtn.disabled = false;
        }
    }

    /**
     * Set VPN loading state
     */
    setVPNLoading(loading) {
        if (!this.vpnToggleBtn) return;

        if (loading) {
            this.vpnToggleBtn.disabled = true;
            const icon = this.vpnToggleBtn.querySelector('i');
            if (icon) icon.className = 'fas fa-spinner fa-spin';
            const span = this.vpnToggleBtn.querySelector('span');
            if (span) span.textContent = 'Processing...';
        } else {
            this.vpnToggleBtn.disabled = false;
            const icon = this.vpnToggleBtn.querySelector('i');
            if (icon) icon.className = 'fas fa-power-off';
        }
    }

    /**
     * Show VPN configuration dialog
     */
    async showVPNConfigDialog() {
        try {
            const [configs, settings] = await Promise.all([
                this.getVPNConfigs(),
                this.getVPNSettings()
            ]);

            const modal = this.createModal('VPN Configuration', `
            <div class="vpn-config-dialog">
                <div class="vpn-config-section">
                    <h3>VPN Settings</h3>
                    
                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="auto-connect-dlsite" 
                                   ${settings?.auto_connect_dlsite ? 'checked' : ''}>
                            Activate VPN when adding DLSite Game
                        </label>
                    </div>
                    
                    <div class="form-group">
                        <label for="default-vpn-config">Standard VPN Konfiguration:</label>
                        <select id="default-vpn-config">
                            <option value="">Konfiguration auswählen...</option>
                            ${configs.map(config => `
                                <option value="${config.path}" 
                                        ${config.path === settings?.current_config_file ? 'selected' : ''}>
                                    ${config.name}
                                </option>
                            `).join('')}
                        </select>
                    </div>
                </div>
                
                <div class="vpn-config-section">
                    <h3>Verfügbare VPN Konfigurationen</h3>
                    
                    ${configs.length === 0 ? `
                        <div class="no-configs-message">
                            <p>Keine VPN-Konfigurationsdateien gefunden.</p>
                            <p>Bitte .ovpn Dateien in das <code>./vpn/</code> Verzeichnis kopieren.</p>
                        </div>
                    ` : `
                        <div class="vpn-configs-list">
                            ${configs.map(config => `
                                <div class="vpn-config-item">
                                    <div class="config-info">
                                        <strong>${config.name}</strong>
                                        <small>${config.server || 'Unbekannt'}:${config.port || '?'}</small>
                                    </div>
                                    <div class="config-actions">
                                        <button class="secondary-button" onclick="dustApp.useVPNConfig('${config.path}')">
                                            Verwenden
                                        </button>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    `}
                </div>
                
                <div class="form-actions">
                    <button type="button" class="secondary-button" onclick="dustApp.closeModal()">
                        Abbrechen
                    </button>
                    <button type="button" class="primary-button" onclick="dustApp.saveVPNSettings()">
                        Speichern
                    </button>
                </div>
            </div>
        `);

        } catch (error) {
            console.error('VPN config dialog error:', error);
            this.showError('Fehler beim Laden der VPN-Konfiguration');
        }
    }

    /**
     * Get VPN configurations
     */
    async getVPNConfigs() {
        try {
            const response = await this.apiRequest('/api/vpn/configs');
            return response.success ? response.configs : [];
        } catch (error) {
            console.error('Error getting VPN configs:', error);
            return [];
        }
    }

    /**
     * Get VPN settings
     */
    async getVPNSettings() {
        try {
            const response = await this.apiRequest('/api/vpn/settings');
            return response.success ? response.settings : {};
        } catch (error) {
            console.error('Error getting VPN settings:', error);
            return {};
        }
    }

    /**
     * Save VPN settings
     */
    async saveVPNSettings() {
        try {
            const autoConnect = document.getElementById('auto-connect-dlsite')?.checked || false;
            const defaultConfig = document.getElementById('default-vpn-config')?.value || null;

            const settings = { auto_connect_dlsite: autoConnect };
            if (defaultConfig) {
                settings.default_config_file = defaultConfig;
            }

            const response = await this.apiRequest('/api/vpn/settings', {
                method: 'POST',
                body: JSON.stringify(settings)
            });

            if (response.success) {
                this.showNotification('VPN-Einstellungen gespeichert', 'success');
                this.closeModal();
            } else {
                this.showError('Fehler beim Speichern der VPN-Einstellungen');
            }

        } catch (error) {
            console.error('Error saving VPN settings:', error);
            this.showError('Fehler beim Speichern der VPN-Einstellungen');
        }
    }

    /**
     * Use specific VPN config
     */
    async useVPNConfig(configPath) {
        try {
            this.setVPNLoading(true);

            const response = await this.apiRequest('/api/vpn/connect', {
                method: 'POST',
                body: JSON.stringify({
                    configFile: configPath,
                    forceReconnect: true
                })
            });

            if (response.success) {
                this.showNotification('VPN verbunden', 'success');
                this.closeModal();
                await this.updateVPNStatus();
            } else {
                this.showError('VPN-Verbindung fehlgeschlagen');
            }

        } catch (error) {
            console.error('Error using VPN config:', error);
            this.showError('VPN-Fehler');
        } finally {
            this.setVPNLoading(false);
        }
    }

    /**
     * Auto-connect VPN for DLSite games
     */
    async autoConnectVPNForDLSite(game) {
        // Check if VPN is needed for this game
        if (!game || !(game.source === 'DLSite' || game.dlsiteId)) {
            return true;
        }

        // Check if already connected
        if (this.vpnStatus && this.vpnStatus.connected) {
            return true;
        }

        // Check auto-connect setting
        const settings = await this.getVPNSettings();
        if (!settings.auto_connect_dlsite) {
            return true; // Continue without VPN
        }

        // Auto-connect
        this.showNotification('VPN wird für DLSite-Spiel aktiviert...', 'info');

        try {
            const response = await this.apiRequest('/api/vpn/connect', {
                method: 'POST'
            });

            if (response.success) {
                await this.updateVPNStatus();
                return true;
            } else {
                this.showError('VPN-Auto-Verbindung fehlgeschlagen');
                return false;
            }
        } catch (error) {
            console.error('VPN auto-connect error:', error);
            return false;
        }
    }

    /**
     * Start VPN monitoring
     */
    startVPNMonitoring() {
        // Update every 10 seconds
        this.vpnMonitoringInterval = setInterval(async () => {
            await this.updateVPNStatus();
        }, 10000);
    }

    /**
     * Stop VPN monitoring  
     */
    stopVPNMonitoring() {
        if (this.vpnMonitoringInterval) {
            clearInterval(this.vpnMonitoringInterval);
            this.vpnMonitoringInterval = null;
        }
    }

    /**
     * Cleanup VPN functionality
     */
    cleanupVPN() {
        this.stopVPNMonitoring();
    }
}

// =============================================================================
// VPN INTEGRATION - Fügen Sie diesen Code am Ende Ihrer renderer.js hinzu
// =============================================================================

// VPN functionality extension for DustApp
Object.assign(DustApp.prototype, {
    
    /**
     * Initialize VPN functionality
     */
    async initVPN() {
        console.log('Initializing VPN functionality...');
        
        // Get VPN UI elements from the existing sidebar
        this.vpnToggleBtn = document.getElementById('vpn-toggle-btn');
        this.vpnConfigBtn = document.getElementById('vpn-config-btn');
        this.vpnStatusLight = document.getElementById('vpn-status-light');
        this.vpnStatusText = document.getElementById('vpn-status-text');
        
        if (!this.vpnToggleBtn || !this.vpnStatusLight || !this.vpnStatusText) {
            console.error('VPN UI elements not found in sidebar');
            return;
        }
        
        // Setup event listeners for VPN controls
        this.setupVPNEventListeners();
        
        // Initialize VPN status
        await this.updateVPNStatus();
        
        // Start status monitoring
        this.startVPNMonitoring();
        
        console.log('VPN functionality initialized successfully');
    },
    
    /**
     * Setup VPN event listeners
     */
    setupVPNEventListeners() {
        // VPN Toggle Button (Power button)
        if (this.vpnToggleBtn) {
            this.vpnToggleBtn.addEventListener('click', async () => {
                await this.toggleVPN();
            });
        }
        
        // VPN Config Button (Gear button)
        if (this.vpnConfigBtn) {
            this.vpnConfigBtn.addEventListener('click', async () => {
                await this.showVPNConfigDialog();
            });
        }
        
        console.log('VPN event listeners attached');
    },
    
    /**
     * Toggle VPN connection
     */
    async toggleVPN() {
        try {
            console.log('Toggling VPN connection...');
            this.setVPNLoading(true);
            
            const response = await this.apiRequest('/api/vpn/toggle', {
                method: 'POST'
            });
            
            if (response.success) {
                this.showNotification(response.message, 'success');
                await this.updateVPNStatus();
            } else {
                this.showError(response.message || 'VPN toggle failed');
            }
            
        } catch (error) {
            console.error('VPN toggle error:', error);
            this.showError('VPN error: ' + error.message);
        } finally {
            this.setVPNLoading(false);
        }
    },
    
    /**
     * Update VPN status display
     */
    async updateVPNStatus() {
        try {
            const response = await this.apiRequest('/api/vpn/status');
            
            if (response.success) {
                this.updateVPNUI(response.status);
                this.vpnStatus = response.status;
            } else {
                this.updateVPNUI({ connected: false });
            }
            
        } catch (error) {
            console.error('VPN status error:', error);
            this.updateVPNUI({ connected: false });
        }
    },
    
    /**
     * Update VPN UI elements
     */
    updateVPNUI(status) {
        const isConnected = status.connected;
        
        // Update status light (red/green indicator)
        if (this.vpnStatusLight) {
            this.vpnStatusLight.className = isConnected ? 
                'status-light connected' : 'status-light disconnected';
        }
        
        // Update status text  
        if (this.vpnStatusText) {
            this.vpnStatusText.textContent = isConnected ? 'Connected' : 'Disconnected';
        }
        
        // Update toggle button
        if (this.vpnToggleBtn) {
            const span = this.vpnToggleBtn.querySelector('span');
            if (span) {
                span.textContent = isConnected ? 'Disconnect VPN' : 'Connect VPN';
            }
            
            // Update button styling
            this.vpnToggleBtn.className = isConnected ? 
                'vpn-toggle-btn connected' : 'vpn-toggle-btn disconnected';
                
            // Enable the button (it starts disabled in HTML)
            this.vpnToggleBtn.disabled = false;
        }
        
        console.log(`VPN UI updated: ${isConnected ? 'Connected' : 'Disconnected'}`);
    },
    
    /**
     * Set VPN loading state
     */
    setVPNLoading(loading) {
        if (!this.vpnToggleBtn) return;
        
        if (loading) {
            this.vpnToggleBtn.disabled = true;
            const icon = this.vpnToggleBtn.querySelector('i');
            if (icon) icon.className = 'fas fa-spinner fa-spin';
            const span = this.vpnToggleBtn.querySelector('span');
            if (span) span.textContent = 'Processing...';
        } else {
            this.vpnToggleBtn.disabled = false;
            const icon = this.vpnToggleBtn.querySelector('i');
            if (icon) icon.className = 'fas fa-power-off';
        }
    },
    
    /**
     * Show VPN configuration dialog
     */
    async showVPNConfigDialog() {
        try {
            console.log('Opening VPN configuration dialog...');
            
            const [configs, settings] = await Promise.all([
                this.getVPNConfigs(),
                this.getVPNSettings()
            ]);
            
            const modal = this.createModal('VPN Konfiguration', `
                <div class="vpn-config-dialog">
                    <div class="vpn-config-section">
                        <h3>VPN Einstellungen</h3>
                        
                        <div class="form-group">
                            <label>
                                <input type="checkbox" id="auto-connect-dlsite" 
                                       ${settings?.auto_connect_dlsite ? 'checked' : ''}>
                                VPN automatisch für DLSite Spiele aktivieren
                            </label>
                        </div>
                        
                        <div class="form-group">
                            <label for="default-vpn-config">Standard VPN Konfiguration:</label>
                            <select id="default-vpn-config">
                                <option value="">Konfiguration auswählen...</option>
                                ${configs.map(config => `
                                    <option value="${config.path}" 
                                            ${config.path === settings?.current_config_file ? 'selected' : ''}>
                                        ${config.name}
                                    </option>
                                `).join('')}
                            </select>
                        </div>
                    </div>
                    
                    <div class="vpn-config-section">
                        <h3>Verfügbare VPN Konfigurationen</h3>
                        
                        ${configs.length === 0 ? `
                            <div class="no-configs-message">
                                <p>❌ Keine VPN-Konfigurationsdateien gefunden.</p>
                                <p>Bitte .ovpn Dateien in das <code>./vpn/</code> Verzeichnis kopieren und die Anwendung neu starten.</p>
                                <p><strong>Aktuelle VPN-Verzeichnis:</strong> <code>${settings?.config_dir || './vpn/'}</code></p>
                            </div>
                        ` : `
                            <div class="vpn-configs-list">
                                ${configs.map(config => `
                                    <div class="vpn-config-item">
                                        <div class="config-info">
                                            <strong>${config.name}</strong>
                                            <small>${config.server || 'Unbekannt'}:${config.port || '?'} (${config.protocol || 'UDP'})</small>
                                        </div>
                                        <div class="config-actions">
                                            <button class="secondary-button" onclick="dustApp.useVPNConfig('${config.path}')">
                                                Jetzt verwenden
                                            </button>
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        `}
                    </div>
                    
                    <div class="form-actions">
                        <button type="button" class="secondary-button" onclick="dustApp.closeModal()">
                            Abbrechen
                        </button>
                        <button type="button" class="primary-button" onclick="dustApp.saveVPNSettings()">
                            Einstellungen speichern
                        </button>
                    </div>
                </div>
            `);
            
        } catch (error) {
            console.error('VPN config dialog error:', error);
            this.showError('Fehler beim Laden der VPN-Konfiguration');
        }
    },
    
    /**
     * Get VPN configurations
     */
    async getVPNConfigs() {
        try {
            const response = await this.apiRequest('/api/vpn/configs');
            return response.success ? response.configs : [];
        } catch (error) {
            console.error('Error getting VPN configs:', error);
            return [];
        }
    },
    
    /**
     * Get VPN settings
     */
    async getVPNSettings() {
        try {
            const response = await this.apiRequest('/api/vpn/settings');
            return response.success ? response.settings : {};
        } catch (error) {
            console.error('Error getting VPN settings:', error);
            return {};
        }
    },
    
    /**
     * Save VPN settings
     */
    async saveVPNSettings() {
        try {
            const autoConnect = document.getElementById('auto-connect-dlsite')?.checked || false;
            const defaultConfig = document.getElementById('default-vpn-config')?.value || null;
            
            const settings = { auto_connect_dlsite: autoConnect };
            if (defaultConfig) {
                settings.default_config_file = defaultConfig;
            }
            
            const response = await this.apiRequest('/api/vpn/settings', {
                method: 'POST',
                body: JSON.stringify(settings)
            });
            
            if (response.success) {
                this.showNotification('VPN-Einstellungen gespeichert', 'success');
                this.closeModal();
            } else {
                this.showError('Fehler beim Speichern der VPN-Einstellungen');
            }
            
        } catch (error) {
            console.error('Error saving VPN settings:', error);
            this.showError('Fehler beim Speichern der VPN-Einstellungen');
        }
    },
    
    /**
     * Use specific VPN config
     */
    async useVPNConfig(configPath) {
        try {
            this.setVPNLoading(true);
            
            const response = await this.apiRequest('/api/vpn/connect', {
                method: 'POST',
                body: JSON.stringify({
                    configFile: configPath,
                    forceReconnect: true
                })
            });
            
            if (response.success) {
                this.showNotification('VPN verbunden', 'success');
                this.closeModal();
                await this.updateVPNStatus();
            } else {
                this.showError('VPN-Verbindung fehlgeschlagen: ' + response.message);
            }
            
        } catch (error) {
            console.error('Error using VPN config:', error);
            this.showError('VPN-Fehler');
        } finally {
            this.setVPNLoading(false);
        }
    },
    
    /**
     * Auto-connect VPN for DLSite games
     */
    async autoConnectVPNForDLSite(game) {
        // Check if VPN is needed for this game
        if (!game || !(game.source === 'DLSite' || game.dlsiteId)) {
            return true;
        }
        
        // Check if already connected
        if (this.vpnStatus && this.vpnStatus.connected) {
            return true;
        }
        
        // Check auto-connect setting
        const settings = await this.getVPNSettings();
        if (!settings.auto_connect_dlsite) {
            return true; // Continue without VPN
        }
        
        // Auto-connect
        this.showNotification('VPN wird für DLSite-Spiel aktiviert...', 'info');
        
        try {
            const response = await this.apiRequest('/api/vpn/connect', {
                method: 'POST'
            });
            
            if (response.success) {
                this.showNotification('VPN für DLSite aktiviert', 'success');
                await this.updateVPNStatus();
                return true;
            } else {
                this.showError('VPN-Auto-Verbindung fehlgeschlagen');
                return false;
            }
        } catch (error) {
            console.error('VPN auto-connect error:', error);
            return false;
        }
    },
    
    /**
     * Start VPN monitoring
     */
    startVPNMonitoring() {
        // Update every 10 seconds
        this.vpnMonitoringInterval = setInterval(async () => {
            await this.updateVPNStatus();
        }, 10000);
        
        console.log('VPN status monitoring started');
    },
    
    /**
     * Stop VPN monitoring  
     */
    stopVPNMonitoring() {
        if (this.vpnMonitoringInterval) {
            clearInterval(this.vpnMonitoringInterval);
            this.vpnMonitoringInterval = null;
        }
    },
    
    /**
     * Cleanup VPN functionality
     */
    cleanupVPN() {
        this.stopVPNMonitoring();
        console.log('VPN functionality cleaned up');
    }
});

// Override the original init method to include VPN initialization
const originalDustAppInit = DustApp.prototype.init;
DustApp.prototype.init = async function() {
    // Call original init first
    await originalDustAppInit.call(this);
    
    // Then initialize VPN
    await this.initVPN();
};

// Override game launching to include VPN check for DLSite games
const originalLaunchGame = DustApp.prototype.launchGame;
DustApp.prototype.launchGame = async function(gameId) {
    const game = this.games.find(g => g.id === gameId);
    if (game) {
        // Check if VPN should be auto-connected for DLSite games
        await this.autoConnectVPNForDLSite(game);
    }
    
    // Call original launch method
    return await originalLaunchGame.call(this, gameId);
};

// Override DLSite info fetching to include VPN check
const originalFetchDLSiteInfo = DustApp.prototype.fetchDLSiteInfoAndProceed;
DustApp.prototype.fetchDLSiteInfoAndProceed = async function(dlsiteId, executablePath) {
    // Auto-connect VPN for DLSite info fetching
    await this.autoConnectVPNForDLSite({ source: 'DLSite' });
    
    // Call original method
    return await originalFetchDLSiteInfo.call(this, dlsiteId, executablePath);
};

console.log('VPN Frontend Integration loaded');
// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.dustApp = new DustApp();
});