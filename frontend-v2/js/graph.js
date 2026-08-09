/**
 * Music Mapper V2 - "Vinyl Noir" Theme
 * D3.js Force-Directed Graph Visualization
 */

class MusicGraph {
    constructor() {
        // DOM Elements
        this.svg = d3.select('#graph-svg');
        this.container = this.svg.append('g').attr('class', 'graph-group');

        // State
        this.data = { nodes: [], links: [] };
        this.simulation = null;
        this.selectedNode = null;
        this.showLabels = true;
        this.showRelated = false;

        // Settings
        this.nodeSize = 20;
        this.linkStrength = 80;

        // Genre Colors
        this.genreColors = {
            'Electronic': '#00d4aa',
            'Dance': '#00d4aa',
            'House': '#00d4aa',
            'Techno': '#00d4aa',
            'Trance': '#00d4aa',
            'EDM': '#00d4aa',
            'Rock': '#ff6b6b',
            'Alternative': '#ff6b6b',
            'Indie Rock': '#ff6b6b',
            'Hip-Hop': '#ffd93d',
            'Rap': '#ffd93d',
            'Hip Hop': '#ffd93d',
            'Pop': '#ff8fab',
            'Synth-pop': '#ff8fab',
            'Jazz': '#6c5ce7',
            'Classical': '#a29bfe',
            'R&B': '#fd79a8',
            'Soul': '#e056fd',
            'Metal': '#636e72',
            'Folk': '#81ecec',
            'Country': '#fab1a0',
            'Latin': '#e17055',
            'Indie': '#74b9ff',
            'Punk': '#00b894',
            'Blues': '#0984e3',
            'Reggae': '#55a630',
            'default': '#d4a574'
        };

        this.init();
    }

    init() {
        this.setupSVG();
        this.setupZoom();
        this.setupEventListeners();
        this.setupDragDrop();
        this.updateDimensions();

        window.addEventListener('resize', () => this.updateDimensions());
    }

    setupDragDrop() {
        const container = document.querySelector('.graph-container');
        if (!container) return;

        // Prevent default drag behaviors
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            container.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
        });

        // Add visual feedback
        ['dragenter', 'dragover'].forEach(eventName => {
            container.addEventListener(eventName, () => {
                container.classList.add('drag-over');
            });
        });

        ['dragleave', 'drop'].forEach(eventName => {
            container.addEventListener(eventName, () => {
                container.classList.remove('drag-over');
            });
        });

        // Handle file drop
        container.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.handleDroppedFile(files[0]);
            }
        });
    }

    handleDroppedFile(file) {
        if (!file.name.match(/\.(json|csv|zip)$/i)) {
            alert('Please drop a JSON, CSV, or ZIP file.');
            return;
        }

        this.showLoading(true);

        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const data = JSON.parse(e.target.result);
                this.loadData(data);
            } catch (error) {
                console.error('Error parsing file:', error);
                alert('Could not parse file. Please upload a valid JSON file.');
            }
            this.showLoading(false);
        };
        reader.readAsText(file);
    }

    setupSVG() {
        const defs = this.svg.append('defs');

        // Glow filter for selected nodes
        const glowFilter = defs.append('filter')
            .attr('id', 'glow')
            .attr('x', '-50%')
            .attr('y', '-50%')
            .attr('width', '200%')
            .attr('height', '200%');

        glowFilter.append('feGaussianBlur')
            .attr('stdDeviation', '3')
            .attr('result', 'coloredBlur');

        const feMerge = glowFilter.append('feMerge');
        feMerge.append('feMergeNode').attr('in', 'coloredBlur');
        feMerge.append('feMergeNode').attr('in', 'SourceGraphic');

        // Link layers
        this.linkGroup = this.container.append('g').attr('class', 'links');
        this.nodeGroup = this.container.append('g').attr('class', 'nodes');
        this.labelGroup = this.container.append('g').attr('class', 'labels');
    }

    setupZoom() {
        const zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on('zoom', (event) => {
                this.container.attr('transform', event.transform);
            });

        this.svg.call(zoom);

        // Reset zoom on double-click
        this.svg.on('dblclick.zoom', null);
    }

    setupEventListeners() {
        // Load buttons
        document.getElementById('btn-demo')?.addEventListener('click', () => this.loadDemo());
        document.getElementById('btn-get-started')?.addEventListener('click', () => this.loadDemo());
        document.getElementById('btn-upload')?.addEventListener('click', () => {
            document.getElementById('file-input')?.click();
        });
        document.getElementById('file-input')?.addEventListener('change', (e) => this.handleFileUpload(e));

        // Controls
        document.getElementById('node-size')?.addEventListener('input', (e) => {
            this.nodeSize = parseInt(e.target.value);
            this.updateNodeSizes();
        });

        document.getElementById('link-strength')?.addEventListener('input', (e) => {
            this.linkStrength = parseInt(e.target.value);
            this.updateSimulation();
        });

        document.getElementById('show-labels')?.addEventListener('change', (e) => {
            this.showLabels = e.target.checked;
            this.updateLabels();
        });

        document.getElementById('show-related')?.addEventListener('change', (e) => {
            this.showRelated = e.target.checked;
            this.render();
        });

        // Search
        const searchInput = document.getElementById('search-input');
        const searchResults = document.getElementById('search-results');

        searchInput?.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            if (query.length < 2) {
                searchResults.classList.remove('active');
                return;
            }

            const matches = this.data.nodes
                .filter(n => n.name.toLowerCase().includes(query))
                .slice(0, 8);

            if (matches.length > 0) {
                searchResults.innerHTML = matches.map(n => `
                    <div class="search-result-item" data-id="${n.id}">
                        ${n.name}
                    </div>
                `).join('');
                searchResults.classList.add('active');

                searchResults.querySelectorAll('.search-result-item').forEach(item => {
                    item.addEventListener('click', () => {
                        const node = this.data.nodes.find(n => n.id === item.dataset.id);
                        if (node) this.selectNode(node);
                        searchResults.classList.remove('active');
                        searchInput.value = '';
                    });
                });
            } else {
                searchResults.classList.remove('active');
            }
        });

        // Panel close
        document.getElementById('panel-close')?.addEventListener('click', () => {
            this.deselectNode();
        });

        // Genre filter
        document.getElementById('genre-filter')?.addEventListener('click', (e) => {
            if (e.target.classList.contains('genre-chip')) {
                document.querySelectorAll('.genre-chip').forEach(c => c.classList.remove('active'));
                e.target.classList.add('active');
                this.filterByGenre(e.target.dataset.genre);
            }
        });
    }

    updateDimensions() {
        const container = document.querySelector('.graph-container');
        if (!container) return;

        const rect = container.getBoundingClientRect();
        this.width = rect.width;
        this.height = rect.height;

        this.svg
            .attr('width', this.width)
            .attr('height', this.height);

        if (this.simulation) {
            this.simulation.force('center', d3.forceCenter(this.width / 2, this.height / 2));
            this.simulation.alpha(0.3).restart();
        }
    }

    async loadDemo() {
        this.showLoading(true);

        try {
            // Load graph data
            const response = await fetch('graph_data.json');
            if (response.ok) {
                const data = await response.json();
                this.loadData(data);
            } else {
                // Generate sample data
                this.loadData(this.generateSampleData());
            }
        } catch (error) {
            console.error('Error loading demo:', error);
            this.loadData(this.generateSampleData());
        }

        this.showLoading(false);
    }

    generateSampleData() {
        const genres = ['Electronic', 'Rock', 'Hip-Hop', 'Pop', 'Jazz', 'R&B', 'Indie', 'Metal'];
        const nodes = [];
        const links = [];

        // Generate sample artists
        for (let i = 0; i < 40; i++) {
            nodes.push({
                id: `artist-${i}`,
                name: `Artist ${i + 1}`,
                genre: genres[Math.floor(Math.random() * genres.length)],
                song_count: Math.floor(Math.random() * 20) + 1,
                in_library: Math.random() > 0.3,
                songs: Array.from({ length: Math.floor(Math.random() * 5) + 1 }, (_, j) => ({
                    title: `Song ${j + 1}`,
                    album: `Album ${Math.floor(Math.random() * 3) + 1}`
                }))
            });
        }

        // Generate connections
        for (let i = 0; i < 60; i++) {
            const source = nodes[Math.floor(Math.random() * nodes.length)].id;
            let target = nodes[Math.floor(Math.random() * nodes.length)].id;
            while (target === source) {
                target = nodes[Math.floor(Math.random() * nodes.length)].id;
            }

            if (!links.find(l => (l.source === source && l.target === target) || (l.source === target && l.target === source))) {
                links.push({
                    source,
                    target,
                    type: Math.random() > 0.5 ? 'collaboration' : 'similar'
                });
            }
        }

        return { nodes, links };
    }

    handleFileUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        this.showLoading(true);

        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const data = JSON.parse(e.target.result);
                this.loadData(data);
            } catch (error) {
                console.error('Error parsing file:', error);
                alert('Could not parse file. Please upload a valid JSON file.');
            }
            this.showLoading(false);
        };
        reader.readAsText(file);
    }

    loadData(data) {
        this.data = data;

        // Filter nodes if not showing related
        let nodes = this.showRelated
            ? data.nodes
            : data.nodes.filter(n => n.in_library !== false);

        let nodeIds = new Set(nodes.map(n => n.id));
        let links = data.links.filter(l => {
            const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
            const targetId = typeof l.target === 'object' ? l.target.id : l.target;
            return nodeIds.has(sourceId) && nodeIds.has(targetId);
        });

        this.displayData = { nodes, links };

        this.updateStats();
        this.updateGenreFilter();
        this.updateLegend();
        this.render();

        document.getElementById('empty-state')?.classList.add('hidden');
    }

    updateStats() {
        const nodes = this.displayData.nodes;
        const songs = nodes.reduce((sum, n) => sum + (n.song_count || n.songs?.length || 0), 0);
        const genres = [...new Set(nodes.map(n => n.genre).filter(Boolean))];

        // Animate stat updates
        this.animateStat('stat-artists', nodes.length);
        this.animateStat('stat-connections', this.displayData.links.length);
        this.animateStat('stat-songs', songs);
        this.animateStat('stat-genres', genres.length);
    }

    animateStat(elementId, targetValue) {
        const element = document.getElementById(elementId);
        if (!element) return;

        const currentValue = parseInt(element.textContent) || 0;

        if (currentValue === targetValue) return;

        // Add animation class
        element.classList.add('updating');

        // Animate counting
        const duration = 600;
        const startTime = performance.now();

        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Easing function (ease-out cubic)
            const eased = 1 - Math.pow(1 - progress, 3);

            const value = Math.round(currentValue + (targetValue - currentValue) * eased);
            element.textContent = value;

            if (progress < 1) {
                requestAnimationFrame(animate);
            } else {
                element.classList.remove('updating');
            }
        };

        requestAnimationFrame(animate);
    }

    updateGenreFilter() {
        const genres = [...new Set(this.data.nodes.map(n => n.genre).filter(Boolean))].sort();
        const container = document.getElementById('genre-filter');
        if (!container) return;

        container.innerHTML = `
            <button class="genre-chip active" data-genre="all">All</button>
            ${genres.map(g => `
                <button class="genre-chip" data-genre="${g}">${g}</button>
            `).join('')}
        `;
    }

    updateLegend() {
        const genres = [...new Set(this.displayData.nodes.map(n => n.genre).filter(Boolean))].sort();
        const container = document.getElementById('legend-items');
        if (!container) return;

        container.innerHTML = genres.map(g => `
            <div class="legend-item">
                <span class="legend-color" style="background: ${this.getGenreColor(g)}"></span>
                <span>${g}</span>
            </div>
        `).join('');
    }

    getGenreColor(genre) {
        if (!genre) return this.genreColors.default;

        // Check exact match first
        if (this.genreColors[genre]) return this.genreColors[genre];

        // Check partial matches
        const genreLower = genre.toLowerCase();
        for (const [key, color] of Object.entries(this.genreColors)) {
            if (genreLower.includes(key.toLowerCase()) || key.toLowerCase().includes(genreLower)) {
                return color;
            }
        }

        return this.genreColors.default;
    }

    filterByGenre(genre) {
        if (genre === 'all') {
            this.loadData(this.data);
        } else {
            const nodes = this.data.nodes.filter(n => n.genre === genre);
            const nodeIds = new Set(nodes.map(n => n.id));
            const links = this.data.links.filter(l => {
                const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
                const targetId = typeof l.target === 'object' ? l.target.id : l.target;
                return nodeIds.has(sourceId) && nodeIds.has(targetId);
            });

            this.displayData = { nodes, links };
            this.updateStats();
            this.render();
        }
    }

    render() {
        const { nodes, links } = this.displayData;

        // Create simulation
        this.simulation = d3.forceSimulation(nodes)
            .force('link', d3.forceLink(links)
                .id(d => d.id)
                .distance(this.linkStrength))
            .force('charge', d3.forceManyBody()
                .strength(-200))
            .force('center', d3.forceCenter(this.width / 2, this.height / 2))
            .force('collision', d3.forceCollide()
                .radius(d => this.getNodeRadius(d) + 5));

        // Render links
        this.linkGroup.selectAll('.link').remove();
        const link = this.linkGroup.selectAll('.link')
            .data(links)
            .enter()
            .append('line')
            .attr('class', d => `link ${d.type || 'similar'}`)
            .attr('stroke-width', 1.5);

        // Render nodes
        this.nodeGroup.selectAll('.node').remove();
        const node = this.nodeGroup.selectAll('.node')
            .data(nodes)
            .enter()
            .append('g')
            .attr('class', 'node')
            .style('animation-delay', (d, i) => `${i * 20}ms`)
            .call(d3.drag()
                .on('start', (event, d) => this.dragStarted(event, d))
                .on('drag', (event, d) => this.dragged(event, d))
                .on('end', (event, d) => this.dragEnded(event, d)));

        node.append('circle')
            .attr('class', 'node-circle')
            .attr('r', d => this.getNodeRadius(d))
            .attr('fill', d => this.getGenreColor(d.genre));

        // Node events
        node.on('click', (event, d) => this.selectNode(d))
            .on('mouseenter', (event, d) => this.showTooltip(event, d))
            .on('mouseleave', () => this.hideTooltip());

        // Render labels
        this.renderLabels(nodes);

        // Update positions on tick
        this.simulation.on('tick', () => {
            link
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            node.attr('transform', d => `translate(${d.x}, ${d.y})`);

            this.labelGroup.selectAll('.node-label')
                .attr('x', d => d.x)
                .attr('y', d => d.y + this.getNodeRadius(d) + 12);
        });
    }

    renderLabels(nodes) {
        this.labelGroup.selectAll('.node-label').remove();

        if (!this.showLabels) return;

        this.labelGroup.selectAll('.node-label')
            .data(nodes)
            .enter()
            .append('text')
            .attr('class', 'node-label')
            .text(d => d.name.length > 15 ? d.name.substring(0, 15) + '...' : d.name)
            .attr('x', d => d.x)
            .attr('y', d => d.y + this.getNodeRadius(d) + 12);
    }

    getNodeRadius(d) {
        const count = d.song_count || d.songs?.length || 1;
        const baseSize = this.nodeSize;
        return Math.max(baseSize * 0.5, Math.min(baseSize * 1.5, baseSize * Math.sqrt(count / 5)));
    }

    updateNodeSizes() {
        this.nodeGroup.selectAll('.node-circle')
            .attr('r', d => this.getNodeRadius(d));

        if (this.simulation) {
            this.simulation.force('collision', d3.forceCollide()
                .radius(d => this.getNodeRadius(d) + 5));
            this.simulation.alpha(0.3).restart();
        }
    }

    updateSimulation() {
        if (this.simulation) {
            this.simulation.force('link').distance(this.linkStrength);
            this.simulation.alpha(0.3).restart();
        }
    }

    updateLabels() {
        if (this.showLabels) {
            this.renderLabels(this.displayData.nodes);
        } else {
            this.labelGroup.selectAll('.node-label').remove();
        }
    }

    selectNode(node) {
        // Deselect previous
        this.nodeGroup.selectAll('.node').classed('selected', false);

        // Select new
        this.selectedNode = node;
        this.nodeGroup.selectAll('.node')
            .filter(d => d.id === node.id)
            .classed('selected', true);

        // Show panel
        this.showArtistPanel(node);

        // Highlight connections
        this.highlightConnections(node);
    }

    deselectNode() {
        this.selectedNode = null;
        this.nodeGroup.selectAll('.node').classed('selected', false);
        this.linkGroup.selectAll('.link').classed('highlighted', false);

        document.getElementById('artist-panel')?.classList.remove('open');
    }

    showArtistPanel(node) {
        const panel = document.getElementById('artist-panel');
        if (!panel) return;

        // Update panel content
        document.getElementById('artist-image').src = node.thumbnail || 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"%3E%3Ccircle cx="50" cy="50" r="40" fill="%23d4a574"/%3E%3C/svg%3E';
        document.getElementById('artist-name').textContent = node.name;
        document.getElementById('artist-genre').textContent = node.genre || 'Unknown';
        document.getElementById('artist-genre').style.background = this.getGenreColor(node.genre);
        document.getElementById('artist-genre').style.color = '#0a0908';

        const songCount = node.song_count || node.songs?.length || 0;
        document.getElementById('artist-songs').textContent = songCount;

        // Get connections
        const connections = this.displayData.links.filter(l => {
            const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
            const targetId = typeof l.target === 'object' ? l.target.id : l.target;
            return sourceId === node.id || targetId === node.id;
        });
        document.getElementById('artist-connections').textContent = connections.length;

        // Songs list
        const songList = document.getElementById('song-list');
        if (node.songs && node.songs.length > 0) {
            songList.innerHTML = node.songs.map(s => `
                <li class="song-item">
                    <span class="song-title">${s.title}</span>
                    ${s.album ? `<span class="song-album">${s.album}</span>` : ''}
                </li>
            `).join('');
        } else {
            songList.innerHTML = '<li class="song-item"><span class="song-title">No songs loaded</span></li>';
        }

        // Connected artists
        const connectedArtists = document.getElementById('connected-artists');
        const connectedNodes = connections.map(l => {
            const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
            const targetId = typeof l.target === 'object' ? l.target.id : l.target;
            const connectedId = sourceId === node.id ? targetId : sourceId;
            return this.displayData.nodes.find(n => n.id === connectedId);
        }).filter(Boolean);

        connectedArtists.innerHTML = connectedNodes.slice(0, 10).map(n => `
            <span class="artist-tag" data-id="${n.id}">${n.name}</span>
        `).join('');

        connectedArtists.querySelectorAll('.artist-tag').forEach(tag => {
            tag.addEventListener('click', () => {
                const targetNode = this.displayData.nodes.find(n => n.id === tag.dataset.id);
                if (targetNode) this.selectNode(targetNode);
            });
        });

        // Similar artists (placeholder - would need API)
        document.getElementById('similar-artists').innerHTML = '<span class="artist-tag">Coming soon...</span>';

        panel.classList.add('open');
    }

    highlightConnections(node) {
        this.linkGroup.selectAll('.link')
            .classed('highlighted', l => {
                const sourceId = typeof l.source === 'object' ? l.source.id : l.source;
                const targetId = typeof l.target === 'object' ? l.target.id : l.target;
                return sourceId === node.id || targetId === node.id;
            });
    }

    showTooltip(event, d) {
        const tooltip = document.getElementById('tooltip');
        if (!tooltip) return;

        tooltip.querySelector('.tooltip-name').textContent = d.name;
        tooltip.querySelector('.tooltip-detail').textContent = `${d.genre || 'Unknown'} · ${d.song_count || d.songs?.length || 0} songs`;

        tooltip.style.left = `${event.pageX + 10}px`;
        tooltip.style.top = `${event.pageY - 10}px`;
        tooltip.classList.add('visible');
    }

    hideTooltip() {
        document.getElementById('tooltip')?.classList.remove('visible');
    }

    showLoading(show) {
        const loading = document.getElementById('loading-state');
        if (loading) {
            loading.classList.toggle('active', show);
        }
    }

    // Drag handlers
    dragStarted(event, d) {
        if (!event.active) this.simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }

    dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }

    dragEnded(event, d) {
        if (!event.active) this.simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.musicGraph = new MusicGraph();
});
