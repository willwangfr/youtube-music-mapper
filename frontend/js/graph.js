/**
 * YouTube Music Mapper - D3.js Force-Directed Graph Visualization
 * Creates an interactive network graph of artists and their relationships
 */

class MusicGraph {
    constructor(containerId) {
        this.container = d3.select(containerId);
        this.svg = null;
        this.simulation = null;
        this.nodes = [];
        this.links = [];
        this.clusters = [];
        this.nodeElements = null;
        this.linkElements = null;
        this.labelElements = null;
        this.genreLabels = null;
        this.zoom = null;
        this.g = null;

        this.settings = {
            nodeSize: 15,
            linkStrength: 80,
            showRelated: true,
            showLabels: false,  // Off by default for performance
            showGenres: true,
            selectedGenre: 'all'
        };

        // Genre color palette
        this.genreColors = {
            'Melodic Bass': '#ff6b9d',
            'Melodic Dubstep': '#ff6b9d',
            'Dubstep/Bass': '#e74c3c',
            'Future Bass': '#9b59b6',
            'Progressive House': '#3498db',
            'Trance': '#00d2d3',
            'Tech House': '#1abc9c',
            'UK House': '#2ecc71',
            'Bass House': '#27ae60',
            'Electro House': '#f39c12',
            'Trap/Bass': '#e67e22',
            'Pop/EDM': '#fd79a8',
            'Pop': '#ff9ff3',
            'Electronic/Indie': '#a29bfe',
            'Electronic': '#74b9ff',
            'Drum & Bass': '#d63031',
            'Midtempo': '#6c5ce7',
            'Midtempo Bass': '#6c5ce7',
            'Electro Soul': '#ffeaa7',
            'Tropical House': '#55efc4',
            'K-Pop': '#ff7675',
            'Hip Hop': '#fdcb6e',
            'Hip-Hop': '#fdcb6e',
            'Rock': '#fab1a0',
            'Cinematic': '#dfe6e9',
            'House': '#2ecc71',
            'Jazz': '#f1c40f',
            'Funk/Electronic': '#ffeaa7',
            'Other': '#81ecec',
            'default': '#81ecec'
        };

        this.init();
        this.setupEventListeners();
    }

    init() {
        const rect = this.container.node().getBoundingClientRect();
        this.width = rect.width;
        this.height = rect.height;

        this.svg = this.container
            .attr('width', this.width)
            .attr('height', this.height);

        // Set up zoom behavior
        this.zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on('zoom', (event) => {
                this.g.attr('transform', event.transform);
            });

        this.svg.call(this.zoom);

        // Create main group for zoom/pan
        this.g = this.svg.append('g');

        // Add gradient definitions for nodes
        const defs = this.svg.append('defs');

        // Gradient for library nodes
        const libraryGradient = defs.append('radialGradient')
            .attr('id', 'libraryGradient');
        libraryGradient.append('stop')
            .attr('offset', '0%')
            .attr('stop-color', '#ff9a9e');
        libraryGradient.append('stop')
            .attr('offset', '100%')
            .attr('stop-color', '#ff6b6b');

        // Gradient for related nodes
        const relatedGradient = defs.append('radialGradient')
            .attr('id', 'relatedGradient');
        relatedGradient.append('stop')
            .attr('offset', '0%')
            .attr('stop-color', '#a8edea');
        relatedGradient.append('stop')
            .attr('offset', '100%')
            .attr('stop-color', '#48dbfb');

        // Initialize force simulation with springy physics
        this.simulation = d3.forceSimulation()
            .force('link', d3.forceLink().id(d => d.id).distance(80).strength(0.3))
            .force('charge', d3.forceManyBody().strength(-150).distanceMax(300))
            .force('center', d3.forceCenter(this.width / 2, this.height / 2).strength(0.05))
            .force('collision', d3.forceCollide().radius(d => this.getNodeRadius(d) + 5).strength(0.8))
            .alphaDecay(0.02)  // Slower decay = longer, floatier animation
            .velocityDecay(0.4);  // Lower = more momentum/drift
    }

    // Force to pull nodes in the same cluster together
    clusterForce(strength) {
        let nodes;

        function force(alpha) {
            if (!nodes || nodes.length === 0) return;

            const clusterCenters = {};
            const clusterCounts = {};

            // Calculate cluster centers
            nodes.forEach(d => {
                if (d.cluster !== undefined && d.x !== undefined && d.y !== undefined) {
                    if (!clusterCenters[d.cluster]) {
                        clusterCenters[d.cluster] = { x: 0, y: 0 };
                        clusterCounts[d.cluster] = 0;
                    }
                    clusterCenters[d.cluster].x += d.x;
                    clusterCenters[d.cluster].y += d.y;
                    clusterCounts[d.cluster]++;
                }
            });

            // Average centers
            Object.keys(clusterCenters).forEach(c => {
                if (clusterCounts[c] > 0) {
                    clusterCenters[c].x /= clusterCounts[c];
                    clusterCenters[c].y /= clusterCounts[c];
                }
            });

            // Pull nodes toward their cluster center
            nodes.forEach(d => {
                if (d.cluster !== undefined && clusterCenters[d.cluster] && d.x !== undefined && d.y !== undefined) {
                    const center = clusterCenters[d.cluster];
                    d.vx = (d.vx || 0) + (center.x - d.x) * strength * alpha;
                    d.vy = (d.vy || 0) + (center.y - d.y) * strength * alpha;
                }
            });
        }

        force.initialize = function(_) { nodes = _; };
        return force;
    }

    // Force to push different clusters apart
    clusterSeparationForce(strength) {
        let nodes;

        function force(alpha) {
            if (!nodes || nodes.length === 0) return;

            const clusterCenters = {};
            const clusterCounts = {};

            // Calculate cluster centers
            nodes.forEach(d => {
                if (d.cluster !== undefined && d.x !== undefined && d.y !== undefined) {
                    if (!clusterCenters[d.cluster]) {
                        clusterCenters[d.cluster] = { x: 0, y: 0, nodes: [] };
                        clusterCounts[d.cluster] = 0;
                    }
                    clusterCenters[d.cluster].x += d.x;
                    clusterCenters[d.cluster].y += d.y;
                    clusterCenters[d.cluster].nodes.push(d);
                    clusterCounts[d.cluster]++;
                }
            });

            // Average centers
            const clusters = Object.keys(clusterCenters);
            clusters.forEach(c => {
                if (clusterCounts[c] > 0) {
                    clusterCenters[c].x /= clusterCounts[c];
                    clusterCenters[c].y /= clusterCounts[c];
                }
            });

            // Push clusters apart from each other
            for (let i = 0; i < clusters.length; i++) {
                for (let j = i + 1; j < clusters.length; j++) {
                    const c1 = clusterCenters[clusters[i]];
                    const c2 = clusterCenters[clusters[j]];

                    if (!c1 || !c2 || !c1.nodes || !c2.nodes) continue;

                    const dx = c2.x - c1.x;
                    const dy = c2.y - c1.y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;

                    // Only separate if clusters are close
                    const minDist = 250;
                    if (dist < minDist) {
                        const pushStrength = (minDist - dist) / dist * strength * alpha;

                        // Push all nodes in each cluster
                        c1.nodes.forEach(d => {
                            d.vx = (d.vx || 0) - dx * pushStrength;
                            d.vy = (d.vy || 0) - dy * pushStrength;
                        });
                        c2.nodes.forEach(d => {
                            d.vx = (d.vx || 0) + dx * pushStrength;
                            d.vy = (d.vy || 0) + dy * pushStrength;
                        });
                    }
                }
            }
        }

        force.initialize = function(_) { nodes = _; };
        return force;
    }

    setupEventListeners() {
        // Control buttons
        document.getElementById('loadDemo').addEventListener('click', () => this.loadDemoData());
        document.getElementById('loadData').addEventListener('click', () => this.loadUserData());
        document.getElementById('refreshLayout').addEventListener('click', () => this.refreshLayout());
        document.getElementById('exportImage').addEventListener('click', () => this.exportAsImage());

        // Sliders
        document.getElementById('nodeSize').addEventListener('input', (e) => {
            this.settings.nodeSize = parseInt(e.target.value);
            this.updateNodeSizes();
        });

        document.getElementById('linkStrength').addEventListener('input', (e) => {
            this.settings.linkStrength = parseInt(e.target.value);
            this.simulation.force('link').distance(this.settings.linkStrength);
            // Don't restart - keep nodes frozen
        });

        // Checkboxes
        document.getElementById('showRelated').addEventListener('change', (e) => {
            this.settings.showRelated = e.target.checked;
            this.filterNodes();
        });

        document.getElementById('showLabels').addEventListener('change', (e) => {
            this.settings.showLabels = e.target.checked;
            this.toggleLabels();
        });

        document.getElementById('showGenres').addEventListener('change', (e) => {
            this.settings.showGenres = e.target.checked;
            this.updateGenreLabels();
        });

        // Search functionality
        const searchInput = document.getElementById('searchInput');
        const searchResults = document.getElementById('searchResults');

        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.trim().toLowerCase();
            if (query.length < 2) {
                searchResults.classList.remove('visible');
                return;
            }
            this.showSearchResults(query);
        });

        searchInput.addEventListener('focus', (e) => {
            if (e.target.value.trim().length >= 2) {
                this.showSearchResults(e.target.value.trim().toLowerCase());
            }
        });

        // Close search results when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.search-container')) {
                searchResults.classList.remove('visible');
            }
        });

        // Genre filter dropdown
        document.getElementById('genreFilter').addEventListener('change', (e) => {
            this.settings.selectedGenre = e.target.value;
            this.filterByGenre();
        });

        // Close panel button
        document.querySelector('.close-btn').addEventListener('click', () => {
            document.getElementById('artist-panel').classList.remove('open');
        });

        // Window resize
        window.addEventListener('resize', () => this.handleResize());
    }

    async loadDemoData() {
        try {
            const response = await fetch('/api/demo/graph');
            const data = await response.json();
            this.renderGraph(data);
        } catch (error) {
            console.error('Error loading demo data:', error);
            // Fallback to local demo data
            this.renderGraph(this.getLocalDemoData());
        }
    }

    async loadUserData() {
        try {
            // Check authentication status
            const statusRes = await fetch('/api/status');
            const status = await statusRes.json();

            if (!status.authenticated) {
                alert('Not authenticated. Please set up YouTube Music authentication first.');
                return;
            }

            // Export data first
            await fetch('/api/export');

            // Get graph data
            const graphRes = await fetch('/api/graph');
            const data = await graphRes.json();
            this.renderGraph(data);
        } catch (error) {
            console.error('Error loading user data:', error);
            alert('Failed to load user data. Make sure the server is running.');
        }
    }

    getLocalDemoData() {
        // Fallback demo data if server is not available
        return {
            nodes: [
                { id: "1", name: "Taylor Swift", song_count: 45, importance: 0.15, in_library: true },
                { id: "2", name: "Ed Sheeran", song_count: 32, importance: 0.12, in_library: true },
                { id: "3", name: "The Weeknd", song_count: 28, importance: 0.11, in_library: true },
                { id: "4", name: "Dua Lipa", song_count: 22, importance: 0.09, in_library: true },
                { id: "5", name: "Post Malone", song_count: 18, importance: 0.08, in_library: true },
                { id: "6", name: "Ariana Grande", song_count: 15, importance: 0.07, in_library: true },
                { id: "7", name: "Drake", song_count: 25, importance: 0.10, in_library: true },
                { id: "8", name: "Billie Eilish", song_count: 20, importance: 0.08, in_library: true },
                { id: "9", name: "Justin Bieber", song_count: 12, importance: 0.06, is_related: true },
                { id: "10", name: "Shawn Mendes", song_count: 8, importance: 0.05, is_related: true },
            ],
            links: [
                { source: "1", target: "2", weight: 3, type: "collaboration" },
                { source: "1", target: "6", weight: 1, type: "similar" },
                { source: "2", target: "9", weight: 2, type: "collaboration" },
                { source: "3", target: "6", weight: 2, type: "collaboration" },
                { source: "3", target: "7", weight: 3, type: "collaboration" },
                { source: "4", target: "3", weight: 1, type: "similar" },
                { source: "5", target: "7", weight: 2, type: "similar" },
                { source: "6", target: "3", weight: 2, type: "collaboration" },
                { source: "8", target: "10", weight: 1, type: "similar" },
                { source: "9", target: "10", weight: 2, type: "similar" },
            ],
            stats: { total_artists: 10, total_connections: 10, library_artists: 8, related_artists: 2 }
        };
    }

    getGenreColor(genre) {
        return this.genreColors[genre] || this.genreColors['default'];
    }

    // Get color with brightness based on song count
    getNodeColor(node) {
        const baseColor = this.getGenreColor(node.genre);

        // Calculate brightness multiplier based on song count
        const maxSongs = Math.max(...this.nodes.map(n => n.song_count || 0), 1);
        const songRatio = (node.song_count || 0) / maxSongs;

        // Convert hex to HSL, adjust lightness, convert back
        const hsl = this.hexToHSL(baseColor);
        // Lightness: 25% (few songs) to 65% (many songs)
        hsl.l = 25 + (songRatio * 40);
        // Saturation: 50% (few songs) to 90% (many songs)
        hsl.s = 50 + (songRatio * 40);

        return this.hslToHex(hsl.h, hsl.s, hsl.l);
    }

    hexToHSL(hex) {
        hex = hex.replace('#', '');
        const r = parseInt(hex.substr(0, 2), 16) / 255;
        const g = parseInt(hex.substr(2, 2), 16) / 255;
        const b = parseInt(hex.substr(4, 2), 16) / 255;

        const max = Math.max(r, g, b), min = Math.min(r, g, b);
        let h, s, l = (max + min) / 2;

        if (max === min) {
            h = s = 0;
        } else {
            const d = max - min;
            s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
            switch (max) {
                case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
                case g: h = ((b - r) / d + 2) / 6; break;
                case b: h = ((r - g) / d + 4) / 6; break;
            }
        }
        return { h: h * 360, s: s * 100, l: l * 100 };
    }

    hslToHex(h, s, l) {
        s /= 100;
        l /= 100;
        const a = s * Math.min(l, 1 - l);
        const f = n => {
            const k = (n + h / 30) % 12;
            const color = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
            return Math.round(255 * color).toString(16).padStart(2, '0');
        };
        return `#${f(0)}${f(8)}${f(4)}`;
    }

    renderGraph(data) {
        // Clear existing elements
        this.g.selectAll('*').remove();

        this.nodes = data.nodes;
        this.links = data.links;
        this.clusters = data.clusters || [];

        // Update stats
        this.updateStats(data.stats);

        // Create link elements
        this.linkElements = this.g.append('g')
            .attr('class', 'links')
            .selectAll('line')
            .data(this.links)
            .enter()
            .append('line')
            .attr('class', d => `link ${d.type}`)
            .attr('stroke-width', d => Math.max(0.5, Math.sqrt(d.weight) * 0.5));

        // Create node groups
        this.nodeElements = this.g.append('g')
            .attr('class', 'nodes')
            .selectAll('g')
            .data(this.nodes)
            .enter()
            .append('g')
            .attr('class', 'node')
            .call(this.drag())
            .on('click', (event, d) => this.showArtistPanel(d))
            .on('mouseover', (event, d) => {
                this.highlightConnections(d, true);
            })
            .on('mouseout', (event, d) => {
                this.highlightConnections(d, false);
            });

        // Add clip paths for circular images
        this.nodeElements.append('clipPath')
            .attr('id', d => `clip-${d.id.replace(/[^a-zA-Z0-9]/g, '_')}`)
            .append('circle')
            .attr('r', d => this.getNodeRadius(d));

        // Add artist images (circular)
        this.nodeElements.append('image')
            .attr('class', 'node-image')
            .attr('xlink:href', d => {
                // Use thumbnail if available, otherwise generate from name
                if (d.thumbnail) return d.thumbnail;
                const name = encodeURIComponent(d.name || 'Artist');
                const color = this.getGenreColor(d.genre || 'Other').replace('#', '');
                return `https://ui-avatars.com/api/?name=${name}&background=${color}&color=fff&size=128&bold=true`;
            })
            .attr('x', d => -this.getNodeRadius(d))
            .attr('y', d => -this.getNodeRadius(d))
            .attr('width', d => this.getNodeRadius(d) * 2)
            .attr('height', d => this.getNodeRadius(d) * 2)
            .attr('clip-path', d => `url(#clip-${d.id.replace(/[^a-zA-Z0-9]/g, '_')})`)
            .attr('preserveAspectRatio', 'xMidYMid slice');

        // Add border circle for genre color
        this.nodeElements.append('circle')
            .attr('class', d => `node-circle ${d.in_library ? 'library' : 'related'}`)
            .attr('r', d => this.getNodeRadius(d))
            .attr('fill', 'none')
            .attr('stroke', d => this.getGenreColor(d.genre || 'Other'))
            .attr('stroke-width', 3);

        // Add labels
        this.labelElements = this.nodeElements.append('text')
            .attr('class', 'node-label')
            .attr('dy', d => this.getNodeRadius(d) + 15)
            .text(d => d.name);

        // Create genre label group
        this.genreLabelGroup = this.g.append('g')
            .attr('class', 'genre-labels');

        // Update simulation
        this.simulation
            .nodes(this.nodes)
            .on('tick', () => this.ticked());

        this.simulation.force('link').links(this.links);

        // Run simulation briefly then freeze all nodes
        this.simulation.alpha(1).restart();

        // Let it settle for 3 seconds then freeze (will unfreeze on drag)
        setTimeout(() => {
            this.freezeGraph();
        }, 3000);

        this.simulation.on('end', () => {
            this.freezeGraph();
        });

        // Apply filters
        this.filterNodes();
        this.toggleLabels();
        this.populateGenreDropdown();
    }

    populateGenreDropdown() {
        const dropdown = document.getElementById('genreFilter');

        // Get unique genres from nodes
        const genres = new Set();
        this.nodes.forEach(node => {
            if (node.genre) {
                genres.add(node.genre);
            }
        });

        // Sort genres alphabetically
        const sortedGenres = Array.from(genres).sort();

        // Reset dropdown
        dropdown.innerHTML = '<option value="all">All Genres</option>';

        // Add genre options with counts
        sortedGenres.forEach(genre => {
            const count = this.nodes.filter(n => n.genre === genre).length;
            const option = document.createElement('option');
            option.value = genre;
            option.textContent = `${genre} (${count})`;
            option.style.color = this.getGenreColor(genre);
            dropdown.appendChild(option);
        });

        // Reset selection
        this.settings.selectedGenre = 'all';
        dropdown.value = 'all';
    }

    filterByGenre() {
        const selectedGenre = this.settings.selectedGenre;

        if (selectedGenre === 'all') {
            // Show all nodes (respect other filters)
            this.nodeElements.style('opacity', 1).style('display', d => {
                if (!this.settings.showRelated && d.is_related) return 'none';
                return 'block';
            });
            this.linkElements.style('opacity', 0.6).style('display', 'block');
        } else {
            // Filter to selected genre
            this.nodeElements.style('display', 'block').style('opacity', d => {
                return d.genre === selectedGenre ? 1 : 0.1;
            });

            // Fade links not connected to filtered genre
            this.linkElements.style('display', 'block').style('opacity', d => {
                const sourceNode = this.nodes.find(n => n.id === (typeof d.source === 'object' ? d.source.id : d.source));
                const targetNode = this.nodes.find(n => n.id === (typeof d.target === 'object' ? d.target.id : d.target));

                const sourceMatch = sourceNode && sourceNode.genre === selectedGenre;
                const targetMatch = targetNode && targetNode.genre === selectedGenre;

                return (sourceMatch || targetMatch) ? 0.6 : 0.05;
            });
        }
    }

    updateGenreLabels() {
        if (!this.genreLabelGroup || !this.clusters.length) return;

        // Calculate cluster centers based on current node positions
        const clusterCenters = {};
        const clusterCounts = {};

        this.nodes.forEach(node => {
            if (node.cluster !== undefined && node.x && node.y) {
                if (!clusterCenters[node.cluster]) {
                    clusterCenters[node.cluster] = { x: 0, y: 0, genre: node.genre };
                    clusterCounts[node.cluster] = 0;
                }
                clusterCenters[node.cluster].x += node.x;
                clusterCenters[node.cluster].y += node.y;
                clusterCounts[node.cluster]++;
            }
        });

        // Average the positions and filter to significant clusters
        const labelData = [];
        const seenGenres = new Set();

        Object.keys(clusterCenters).forEach(clusterId => {
            const count = clusterCounts[clusterId];
            if (count >= 5) { // Only label clusters with 5+ artists
                const center = clusterCenters[clusterId];
                const genre = center.genre || 'Electronic';

                // Avoid duplicate genre labels
                if (!seenGenres.has(genre)) {
                    seenGenres.add(genre);
                    labelData.push({
                        x: center.x / count,
                        y: center.y / count,
                        genre: genre,
                        size: count
                    });
                }
            }
        });

        // Update genre labels
        this.genreLabelGroup.selectAll('.genre-label').remove();

        if (this.settings.showGenres) {
            this.genreLabelGroup.selectAll('.genre-label')
                .data(labelData)
                .enter()
                .append('text')
                .attr('class', 'genre-label')
                .attr('x', d => d.x)
                .attr('y', d => d.y)
                .attr('text-anchor', 'middle')
                .attr('fill', d => this.getGenreColor(d.genre))
                .attr('font-size', d => Math.min(24, 12 + d.size / 5) + 'px')
                .attr('font-weight', 'bold')
                .attr('opacity', 0.8)
                .attr('pointer-events', 'none')
                .style('text-shadow', '0 0 10px rgba(0,0,0,0.8), 0 0 20px rgba(0,0,0,0.6)')
                .text(d => d.genre);
        }
    }

    getNodeRadius(d) {
        const baseSize = this.settings.nodeSize;
        const songCount = d.song_count || 1;
        // Direct proportion: sqrt for better visual scaling (area proportional to count)
        const scale = Math.sqrt(songCount);
        // Min 5px, max 50px
        return Math.max(5, Math.min(50, baseSize * 0.3 * scale));
    }

    ticked() {
        this.linkElements
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);

        this.nodeElements
            .attr('transform', d => `translate(${d.x}, ${d.y})`);

        // Update genre labels periodically (every 10 ticks for performance)
        if (!this.tickCount) this.tickCount = 0;
        this.tickCount++;
        if (this.tickCount % 10 === 0) {
            this.updateGenreLabels();
        }
    }

    drag() {
        const self = this;
        return d3.drag()
            .on('start', function(event, d) {
                d3.select(this).raise(); // Bring to front

                // Unfreeze all nodes for physics
                self.nodes.forEach(n => {
                    n.fx = null;
                    n.fy = null;
                });

                // Fix the dragged node
                d.fx = d.x;
                d.fy = d.y;

                // Wake up simulation
                self.simulation.alphaTarget(0.3).restart();
            })
            .on('drag', function(event, d) {
                // Move the dragged node
                d.fx = event.x;
                d.fy = event.y;
            })
            .on('end', function(event, d) {
                // Let simulation cool down
                self.simulation.alphaTarget(0);

                // Optionally re-freeze after settling (comment out for permanent physics)
                // setTimeout(() => self.freezeGraph(), 2000);
            });
    }

    // Re-enable tick updates for physics
    setupPhysicsTick() {
        this.simulation.on('tick', () => {
            this.linkElements
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            this.nodeElements
                .attr('transform', d => `translate(${d.x}, ${d.y})`);
        });
    }

    freezeGraph() {
        if (this.frozen) return;
        this.frozen = true;

        console.log('Initial layout complete - physics ready for interaction');

        // Stop simulation but keep tick handler for dragging
        this.simulation.stop();

        // Fix all nodes at current positions
        this.nodes.forEach(d => {
            d.fx = d.x;
            d.fy = d.y;
            d.vx = 0;
            d.vy = 0;
        });

        // Do final position update
        this.nodeElements.attr('transform', d => `translate(${d.x}, ${d.y})`);
        this.linkElements
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
    }

    highlightConnections(node, highlight) {
        const connectedIds = new Set();
        const connectionInfo = new Map(); // Store connection details
        connectedIds.add(node.id);

        this.links.forEach(link => {
            const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
            const targetId = typeof link.target === 'object' ? link.target.id : link.target;

            if (sourceId === node.id) {
                connectedIds.add(targetId);
                connectionInfo.set(targetId, {
                    type: link.type || 'collaboration',
                    weight: link.weight || 1,
                    sharedSongs: link.weight || 1
                });
            }
            if (targetId === node.id) {
                connectedIds.add(sourceId);
                connectionInfo.set(sourceId, {
                    type: link.type || 'collaboration',
                    weight: link.weight || 1,
                    sharedSongs: link.weight || 1
                });
            }
        });

        // Get the hovered node's genre color
        const highlightColor = this.getGenreColor(node.genre || 'Other');

        if (highlight) {
            // Animate fade with transition
            this.nodeElements
                .transition()
                .duration(200)
                .style('opacity', d => connectedIds.has(d.id) ? 1 : 0.15);

            // Highlight connected nodes with glow effect using hovered node's color
            this.nodeElements.classed('highlighted-node', d => connectedIds.has(d.id) && d.id !== node.id);
            this.nodeElements.classed('hovered-node', d => d.id === node.id);

            // Set the highlight color on all highlighted nodes
            this.nodeElements.select('.node-circle')
                .style('--highlight-color', d => connectedIds.has(d.id) ? highlightColor : null);

            this.linkElements
                .transition()
                .duration(200)
                .style('stroke-opacity', d => {
                    const sourceId = typeof d.source === 'object' ? d.source.id : d.source;
                    const targetId = typeof d.target === 'object' ? d.target.id : d.target;
                    return (sourceId === node.id || targetId === node.id) ? 0.9 : 0.05;
                })
                .style('stroke-width', d => {
                    const sourceId = typeof d.source === 'object' ? d.source.id : d.source;
                    const targetId = typeof d.target === 'object' ? d.target.id : d.target;
                    if (sourceId === node.id || targetId === node.id) {
                        return Math.max(2, Math.sqrt(d.weight || 1) * 1.5) + 'px';
                    }
                    return Math.sqrt(d.weight || 1) * 0.5 + 'px';
                });

            this.linkElements.classed('highlighted', d => {
                const sourceId = typeof d.source === 'object' ? d.source.id : d.source;
                const targetId = typeof d.target === 'object' ? d.target.id : d.target;
                return sourceId === node.id || targetId === node.id;
            });

            // Set the highlight color on links
            this.linkElements
                .style('--highlight-color', highlightColor)
                .style('stroke', d => {
                    const sourceId = typeof d.source === 'object' ? d.source.id : d.source;
                    const targetId = typeof d.target === 'object' ? d.target.id : d.target;
                    if (sourceId === node.id || targetId === node.id) {
                        return highlightColor;
                    }
                    return null;
                });

            // Show enhanced tooltip with connection info
            this.showEnhancedTooltip(node, connectionInfo);
        } else {
            // Animate back
            this.nodeElements
                .transition()
                .duration(200)
                .style('opacity', 1);

            this.nodeElements.classed('faded', false);
            this.nodeElements.classed('highlighted-node', false);
            this.nodeElements.classed('hovered-node', false);

            // Clear the highlight color
            this.nodeElements.select('.node-circle').style('--highlight-color', null);

            this.linkElements
                .transition()
                .duration(200)
                .style('stroke-opacity', 0.3)
                .style('stroke-width', d => Math.sqrt(d.weight || 1) * 0.5 + 'px');

            // Clear link highlight styles
            this.linkElements
                .style('--highlight-color', null)
                .style('stroke', null);

            this.linkElements.classed('faded', false);
            this.linkElements.classed('highlighted', false);
            this.hideTooltip();
        }
    }

    showTooltip(node) {
        const tooltip = document.getElementById('tooltip');
        const genreColor = node.genre ? this.getGenreColor(node.genre) : '#888';
        tooltip.innerHTML = `
            <h3>${node.name}</h3>
            ${node.genre ? `<p style="color: ${genreColor}; font-weight: bold;">${node.genre}</p>` : ''}
            <p>Songs in library: ${node.song_count || 0}</p>
            <p>Type: ${node.in_library ? 'In Your Library' : 'Related Artist'}</p>
        `;
        tooltip.classList.add('visible');

        // Position tooltip near mouse
        document.addEventListener('mousemove', this.moveTooltip);
    }

    showEnhancedTooltip(node, connectionInfo) {
        const tooltip = document.getElementById('tooltip');
        const genreColor = node.genre ? this.getGenreColor(node.genre) : '#888';

        // Count connection types
        let collabCount = 0;
        let similarCount = 0;
        let totalSharedSongs = 0;

        connectionInfo.forEach((info, artistId) => {
            if (info.type === 'collaboration') {
                collabCount++;
                totalSharedSongs += info.sharedSongs;
            } else {
                similarCount++;
            }
        });

        // Build connections list (top 5)
        const connectedArtists = [];
        connectionInfo.forEach((info, artistId) => {
            const artist = this.nodes.find(n => n.id === artistId);
            if (artist) {
                connectedArtists.push({
                    name: artist.name,
                    type: info.type,
                    sharedSongs: info.sharedSongs
                });
            }
        });

        // Sort by shared songs and take top 5
        connectedArtists.sort((a, b) => b.sharedSongs - a.sharedSongs);
        const topConnections = connectedArtists.slice(0, 5);

        tooltip.innerHTML = `
            <div class="tooltip-header">
                <h3>${node.name}</h3>
                ${node.genre ? `<span class="tooltip-genre" style="background: ${genreColor};">${node.genre}</span>` : ''}
            </div>
            <div class="tooltip-stats">
                <div class="tooltip-stat">
                    <span class="stat-value">${node.song_count || 0}</span>
                    <span class="stat-label">songs</span>
                </div>
                <div class="tooltip-stat">
                    <span class="stat-value">${connectionInfo.size}</span>
                    <span class="stat-label">connections</span>
                </div>
                ${collabCount > 0 ? `
                <div class="tooltip-stat collab">
                    <span class="stat-value">${collabCount}</span>
                    <span class="stat-label">collabs</span>
                </div>` : ''}
                ${similarCount > 0 ? `
                <div class="tooltip-stat similar">
                    <span class="stat-value">${similarCount}</span>
                    <span class="stat-label">similar</span>
                </div>` : ''}
            </div>
            ${topConnections.length > 0 ? `
            <div class="tooltip-connections">
                <div class="connections-title">Connected Artists:</div>
                ${topConnections.map(c => `
                    <div class="connection-item ${c.type}">
                        <span class="connection-name">${c.name}</span>
                        <span class="connection-type">${c.type === 'collaboration' ? `${c.sharedSongs} song${c.sharedSongs > 1 ? 's' : ''}` : 'similar'}</span>
                    </div>
                `).join('')}
                ${connectedArtists.length > 5 ? `<div class="connection-more">+${connectedArtists.length - 5} more</div>` : ''}
            </div>` : ''}
        `;
        tooltip.classList.add('visible', 'enhanced');

        // Position tooltip near mouse
        document.addEventListener('mousemove', this.moveTooltip);
    }

    moveTooltip = (e) => {
        const tooltip = document.getElementById('tooltip');
        tooltip.style.left = (e.pageX + 15) + 'px';
        tooltip.style.top = (e.pageY + 15) + 'px';
    }

    hideTooltip() {
        const tooltip = document.getElementById('tooltip');
        tooltip.classList.remove('visible', 'enhanced');
        document.removeEventListener('mousemove', this.moveTooltip);
    }

    showArtistPanel(artist) {
        const panel = document.getElementById('artist-panel');
        document.getElementById('artistName').textContent = artist.name;

        // Set image (placeholder if none)
        const img = document.getElementById('artistImage');
        img.src = artist.thumbnail || `https://ui-avatars.com/api/?name=${encodeURIComponent(artist.name)}&background=ff6b6b&color=fff&size=150`;

        // Stats
        const genreColor = artist.genre ? this.getGenreColor(artist.genre) : '#888';
        document.getElementById('artistStats').innerHTML = `
            ${artist.genre ? `<p><span>Genre:</span> <span style="color: ${genreColor}; font-weight: bold;">${artist.genre}</span></p>` : ''}
            <p><span>Songs in library:</span> <span>${artist.song_count || 0}</span></p>
            <p><span>Type:</span> <span>${artist.in_library ? 'Library Artist' : 'Related Artist'}</span></p>
            <p><span>Importance:</span> <span>${((artist.importance || 0) * 100).toFixed(1)}%</span></p>
        `;

        // Songs
        const songs = artist.songs || [];
        const formatViews = (v) => {
            if (!v) return '';
            if (v >= 1000000000) return (v / 1000000000).toFixed(1) + 'B';
            if (v >= 1000000) return (v / 1000000).toFixed(1) + 'M';
            if (v >= 1000) return Math.floor(v / 1000) + 'K';
            return v.toString();
        };
        if (songs.length > 0) {
            document.getElementById('artistSongs').innerHTML = `
                <h4>Your Liked Songs (${songs.length}${songs.length >= 20 ? '+' : ''})</h4>
                <ul class="songs-list">
                    ${songs.map(s => `
                        <li>
                            <span class="song-title">${s.title}</span>
                            <span class="song-meta">
                                ${s.year ? `<span class="song-year">${s.year}</span>` : ''}
                                ${s.views ? `<span class="song-views">${formatViews(s.views)}</span>` : ''}
                                ${s.plays ? `<span class="song-plays">${s.plays}x</span>` : ''}
                            </span>
                        </li>
                    `).join('')}
                </ul>
            `;
        } else {
            document.getElementById('artistSongs').innerHTML = '';
        }

        // Connections
        const connections = this.getConnections(artist);
        document.getElementById('artistConnections').innerHTML = `
            <h4>Connected Artists (${connections.length})</h4>
            <ul>
                ${connections.map(c => `<li onclick="graph.focusNode('${c.id}')">${c.name} (${c.type})</li>`).join('')}
            </ul>
        `;

        panel.classList.add('open');
    }

    getConnections(node) {
        const connections = [];
        this.links.forEach(link => {
            const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
            const targetId = typeof link.target === 'object' ? link.target.id : link.target;

            if (sourceId === node.id) {
                const target = this.nodes.find(n => n.id === targetId);
                if (target) connections.push({ ...target, type: link.type });
            }
            if (targetId === node.id) {
                const source = this.nodes.find(n => n.id === sourceId);
                if (source) connections.push({ ...source, type: link.type });
            }
        });
        return connections;
    }

    focusNode(nodeId) {
        const node = this.nodes.find(n => n.id === nodeId);
        if (node && node.x && node.y) {
            const scale = 1.5;
            const x = this.width / 2 - node.x * scale;
            const y = this.height / 2 - node.y * scale;

            this.svg.transition()
                .duration(750)
                .call(
                    this.zoom.transform,
                    d3.zoomIdentity.translate(x, y).scale(scale)
                );

            this.showArtistPanel(node);
            this.highlightSearchedNode(node);
        }
    }

    showSearchResults(query) {
        const searchResults = document.getElementById('searchResults');

        // Find matching artists
        const artistMatches = this.nodes
            .filter(n => n.name && n.name.toLowerCase().includes(query))
            .sort((a, b) => {
                const aName = a.name.toLowerCase();
                const bName = b.name.toLowerCase();
                if (aName.startsWith(query) && !bName.startsWith(query)) return -1;
                if (!aName.startsWith(query) && bName.startsWith(query)) return 1;
                return (b.song_count || 0) - (a.song_count || 0);
            })
            .slice(0, 5);

        // Find matching songs
        const songMatches = [];
        this.nodes.forEach(artist => {
            if (artist.songs && artist.songs.length > 0) {
                artist.songs.forEach(song => {
                    if (song.title && song.title.toLowerCase().includes(query)) {
                        songMatches.push({
                            ...song,
                            artistId: artist.id,
                            artistName: artist.name,
                            artistGenre: artist.genre
                        });
                    }
                });
            }
        });

        // Sort songs by relevance
        songMatches.sort((a, b) => {
            const aTitle = a.title.toLowerCase();
            const bTitle = b.title.toLowerCase();
            if (aTitle.startsWith(query) && !bTitle.startsWith(query)) return -1;
            if (!aTitle.startsWith(query) && bTitle.startsWith(query)) return 1;
            return aTitle.localeCompare(bTitle);
        });

        const topSongs = songMatches.slice(0, 5);

        if (artistMatches.length === 0 && topSongs.length === 0) {
            searchResults.innerHTML = '<div class="search-result-item no-results">No results found</div>';
        } else {
            let html = '';

            // Artist results section
            if (artistMatches.length > 0) {
                html += '<div class="search-section-header">Artists</div>';
                html += artistMatches.map(artist => {
                    const genreColor = artist.genre ? this.getGenreColor(artist.genre) : '#888';
                    return `
                        <div class="search-result-item" data-artist-id="${artist.id}">
                            <div class="artist-name">${this.highlightMatch(artist.name, query)}</div>
                            <div class="artist-genre" style="color: ${genreColor}">${artist.genre || 'Unknown genre'} • ${artist.song_count || 0} songs</div>
                        </div>
                    `;
                }).join('');
            }

            // Song results section
            if (topSongs.length > 0) {
                html += '<div class="search-section-header">Songs</div>';
                html += topSongs.map(song => {
                    const genreColor = song.artistGenre ? this.getGenreColor(song.artistGenre) : '#888';
                    return `
                        <div class="search-result-item song-result" data-artist-id="${song.artistId}">
                            <div class="song-name">${this.highlightMatch(song.title, query)}</div>
                            <div class="song-artist" style="color: ${genreColor}">by ${song.artistName}${song.album ? ` • ${song.album}` : ''}</div>
                        </div>
                    `;
                }).join('');
            }

            searchResults.innerHTML = html;

            // Add click handlers for both artists and songs
            searchResults.querySelectorAll('.search-result-item[data-artist-id]').forEach(item => {
                item.addEventListener('click', () => {
                    const artistId = item.dataset.artistId;
                    this.focusNode(artistId);
                    searchResults.classList.remove('visible');
                    document.getElementById('searchInput').value = '';
                });
            });
        }

        searchResults.classList.add('visible');
    }

    highlightMatch(text, query) {
        const regex = new RegExp(`(${query})`, 'gi');
        return text.replace(regex, '<span style="color: #ff6b6b; font-weight: bold;">$1</span>');
    }

    highlightSearchedNode(node) {
        // Pulse animation for the searched node
        this.nodeElements
            .filter(d => d.id === node.id)
            .select('circle')
            .transition()
            .duration(200)
            .attr('r', d => this.getNodeRadius(d) * 2)
            .attr('stroke', '#fff')
            .attr('stroke-width', 4)
            .transition()
            .duration(200)
            .attr('r', d => this.getNodeRadius(d) * 1.5)
            .transition()
            .duration(200)
            .attr('r', d => this.getNodeRadius(d) * 2)
            .transition()
            .duration(500)
            .attr('r', d => this.getNodeRadius(d))
            .attr('stroke-width', 2);
    }

    updateStats(stats) {
        document.getElementById('totalArtists').textContent = stats.total_artists || 0;
        document.getElementById('totalConnections').textContent = stats.total_connections || 0;
        document.getElementById('libraryArtists').textContent = stats.library_artists || 0;
    }

    updateNodeSizes() {
        if (this.nodeElements) {
            this.nodeElements.select('circle')
                .attr('r', d => this.getNodeRadius(d));

            this.labelElements
                .attr('dy', d => this.getNodeRadius(d) + 15);

            this.simulation.force('collision').radius(d => this.getNodeRadius(d) + 5);
            // Don't restart - keep nodes frozen
        }
    }

    filterNodes() {
        if (this.nodeElements) {
            this.nodeElements.style('display', d => {
                if (!this.settings.showRelated && d.is_related) return 'none';
                return 'block';
            });

            this.linkElements.style('display', d => {
                const sourceId = typeof d.source === 'object' ? d.source.id : d.source;
                const targetId = typeof d.target === 'object' ? d.target.id : d.target;

                if (!this.settings.showRelated) {
                    const sourceNode = this.nodes.find(n => n.id === sourceId);
                    const targetNode = this.nodes.find(n => n.id === targetId);
                    if ((sourceNode && sourceNode.is_related) || (targetNode && targetNode.is_related)) {
                        return 'none';
                    }
                }
                return 'block';
            });
        }
    }

    toggleLabels() {
        if (this.labelElements) {
            this.labelElements.style('display', this.settings.showLabels ? 'block' : 'none');
        }
    }

    refreshLayout() {
        // Disabled - keep nodes frozen
        // this.simulation.alpha(1).restart();
    }

    exportAsImage() {
        // Get SVG element
        const svgElement = document.getElementById('graph');
        const svgData = new XMLSerializer().serializeToString(svgElement);

        // Create canvas
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');

        // Set canvas size (2x for higher resolution)
        const scale = 2;
        canvas.width = this.width * scale;
        canvas.height = this.height * scale;

        // Draw background
        ctx.fillStyle = '#0f0f23';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Create image from SVG
        const img = new Image();
        const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
        const url = URL.createObjectURL(svgBlob);

        img.onload = () => {
            ctx.scale(scale, scale);
            ctx.drawImage(img, 0, 0);
            URL.revokeObjectURL(url);

            // Add watermark
            ctx.fillStyle = 'rgba(255, 255, 255, 0.5)';
            ctx.font = '14px sans-serif';
            ctx.fillText('YouTube Music Mapper', 20, this.height - 20);

            // Download
            const link = document.createElement('a');
            link.download = `music-map-${new Date().toISOString().slice(0, 10)}.png`;
            link.href = canvas.toDataURL('image/png');
            link.click();
        };

        img.src = url;
    }

    handleResize() {
        const rect = this.container.node().getBoundingClientRect();
        this.width = rect.width;
        this.height = rect.height;

        this.svg
            .attr('width', this.width)
            .attr('height', this.height);

        this.simulation.force('center', d3.forceCenter(this.width / 2, this.height / 2));
        // Don't restart - keep nodes frozen
    }
}

// Initialize graph
const graph = new MusicGraph('#graph');

// DJ Set management
graph.djSet = [];

// Toggle DJ Panel
function toggleDJPanel() {
    const content = document.querySelector('.dj-content');
    const toggle = document.querySelector('.dj-toggle');
    content.classList.toggle('collapsed');
    toggle.textContent = content.classList.contains('collapsed') ? '+' : '-';
}

// Utility methods
MusicGraph.prototype.formatViews = function(views) {
    if (!views) return '';
    if (views >= 1000000000) return (views / 1000000000).toFixed(1) + 'B';
    if (views >= 1000000) return (views / 1000000).toFixed(1) + 'M';
    if (views >= 1000) return (views / 1000).toFixed(0) + 'K';
    return views.toString();
};

// Add DJ methods to MusicGraph
MusicGraph.prototype.findMixPath = function() {
    const fromInput = document.getElementById('mixFrom').value.trim().toLowerCase();
    const toInput = document.getElementById('mixTo').value.trim().toLowerCase();
    const results = document.getElementById('mixPathResults');

    if (!fromInput || !toInput) {
        results.innerHTML = '<p class="dj-hint">Enter both artists</p>';
        return;
    }

    // Find matching nodes
    const fromNode = this.nodes.find(n => n.name.toLowerCase().includes(fromInput));
    const toNode = this.nodes.find(n => n.name.toLowerCase().includes(toInput));

    if (!fromNode || !toNode) {
        results.innerHTML = '<p class="dj-hint">Artist not found</p>';
        return;
    }

    // BFS to find shortest path
    const path = this.bfsPath(fromNode.id, toNode.id);

    if (!path) {
        results.innerHTML = '<p class="dj-hint">No connection found between these artists</p>';
        return;
    }

    // Render path
    const pathHtml = path.map((nodeId, i) => {
        const node = this.nodes.find(n => n.id === nodeId);
        const color = this.getGenreColor(node.genre);
        return `<span class="mix-path-node" style="background: ${color}; color: #000;" onclick="graph.focusNode('${nodeId}')">${node.name}</span>`;
    }).join('<span class="mix-path-arrow">→</span>');

    results.innerHTML = `
        <div class="mix-path-visual">${pathHtml}</div>
        <p class="dj-hint" style="margin-top: 8px;">${path.length} artists in transition</p>
    `;

    // Highlight path on graph
    this.highlightPath(path);
};

MusicGraph.prototype.bfsPath = function(startId, endId) {
    // Build adjacency list
    const adj = {};
    this.nodes.forEach(n => adj[n.id] = []);
    this.links.forEach(l => {
        const src = typeof l.source === 'object' ? l.source.id : l.source;
        const tgt = typeof l.target === 'object' ? l.target.id : l.target;
        if (adj[src]) adj[src].push(tgt);
        if (adj[tgt]) adj[tgt].push(src);
    });

    // BFS
    const queue = [[startId]];
    const visited = new Set([startId]);

    while (queue.length > 0) {
        const path = queue.shift();
        const node = path[path.length - 1];

        if (node === endId) return path;

        for (const neighbor of (adj[node] || [])) {
            if (!visited.has(neighbor)) {
                visited.add(neighbor);
                queue.push([...path, neighbor]);
            }
        }
    }

    return null;
};

MusicGraph.prototype.highlightPath = function(path) {
    const pathSet = new Set(path);

    // Fade non-path nodes
    this.nodeElements.classed('faded', d => !pathSet.has(d.id));

    // Highlight path links
    this.linkElements.classed('faded', d => {
        const src = typeof d.source === 'object' ? d.source.id : d.source;
        const tgt = typeof d.target === 'object' ? d.target.id : d.target;
        const srcIdx = path.indexOf(src);
        const tgtIdx = path.indexOf(tgt);
        return !(srcIdx !== -1 && tgtIdx !== -1 && Math.abs(srcIdx - tgtIdx) === 1);
    });

    this.linkElements.classed('highlighted', d => {
        const src = typeof d.source === 'object' ? d.source.id : d.source;
        const tgt = typeof d.target === 'object' ? d.target.id : d.target;
        const srcIdx = path.indexOf(src);
        const tgtIdx = path.indexOf(tgt);
        return srcIdx !== -1 && tgtIdx !== -1 && Math.abs(srcIdx - tgtIdx) === 1;
    });

    // Clear after 5 seconds
    setTimeout(() => {
        this.nodeElements.classed('faded', false);
        this.linkElements.classed('faded', false);
        this.linkElements.classed('highlighted', false);
    }, 5000);
};

MusicGraph.prototype.findBridgeArtists = function() {
    const results = document.getElementById('bridgeResults');

    // Build adjacency with genres
    const bridges = [];

    this.nodes.forEach(node => {
        if (!node.genre || node.genre === 'Other') return;

        // Get connected genres
        const connectedGenres = new Set();
        this.links.forEach(l => {
            const src = typeof l.source === 'object' ? l.source.id : l.source;
            const tgt = typeof l.target === 'object' ? l.target.id : l.target;

            let connectedId = null;
            if (src === node.id) connectedId = tgt;
            else if (tgt === node.id) connectedId = src;

            if (connectedId) {
                const connectedNode = this.nodes.find(n => n.id === connectedId);
                if (connectedNode && connectedNode.genre && connectedNode.genre !== 'Other' && connectedNode.genre !== node.genre) {
                    connectedGenres.add(connectedNode.genre);
                }
            }
        });

        if (connectedGenres.size >= 2) {
            bridges.push({
                node,
                genres: [node.genre, ...connectedGenres],
                score: connectedGenres.size
            });
        }
    });

    // Sort by bridge score
    bridges.sort((a, b) => b.score - a.score);

    if (bridges.length === 0) {
        results.innerHTML = '<p class="dj-hint">No bridge artists found</p>';
        return;
    }

    results.innerHTML = bridges.slice(0, 8).map(b => {
        const genreTags = b.genres.slice(0, 3).map(g =>
            `<span class="genre-tag" style="background: ${this.getGenreColor(g)}; color: #000;">${g}</span>`
        ).join('<span class="bridge-arrow">↔</span>');

        return `
            <div class="bridge-card" onclick="graph.focusNode('${b.node.id}')">
                <div class="bridge-artist">${b.node.name}</div>
                <div class="bridge-genres">${genreTags}</div>
            </div>
        `;
    }).join('');
};

MusicGraph.prototype.buildSet = function() {
    const genre = document.getElementById('setGenre').value;
    const flow = document.querySelector('input[name="setFlow"]:checked').value;
    const results = document.getElementById('setBuilderResults');

    if (!genre) {
        results.innerHTML = '<p class="dj-hint">Select a starting genre</p>';
        return;
    }

    let set = [];
    const genreNodes = this.nodes.filter(n => n.genre === genre && n.song_count > 0)
        .sort((a, b) => (b.song_count || 0) - (a.song_count || 0));

    if (genreNodes.length === 0) {
        results.innerHTML = '<p class="dj-hint">No artists found in this genre</p>';
        return;
    }

    if (flow === 'energy-up') {
        // Start mellow, end heavy
        set = this.buildEnergySet(genre, 'up');
    } else if (flow === 'energy-down') {
        // Start heavy, end mellow
        set = this.buildEnergySet(genre, 'down');
    } else {
        // Genre journey - traverse through connected genres
        set = this.buildGenreJourney(genre);
    }

    // Build HTML with songs for each artist
    let html = '';
    set.forEach((artist, i) => {
        const songs = artist.songs || [];
        const topSongs = songs.slice(0, 3); // Show top 3 songs per artist

        html += `
            <div class="set-artist-block">
                <div class="dj-result-item" onclick="graph.addToSet('${artist.id}')">
                    <span class="artist-dot" style="background: ${this.getGenreColor(artist.genre)};"></span>
                    <div class="artist-info">
                        <div class="artist-name">${i + 1}. ${artist.name}</div>
                        <div class="artist-meta">${artist.genre} • ${artist.song_count || 0} songs</div>
                    </div>
                </div>
                ${topSongs.length > 0 ? `
                    <div class="set-songs">
                        ${topSongs.map(song => `
                            <div class="set-song-item">
                                <span class="play-icon" onclick="event.stopPropagation(); graph.playSong('${artist.name}', '${song.title.replace(/'/g, "\\'")}')">▶</span>
                                <span class="song-title" onclick="graph.addSongToSet('${artist.id}', '${song.title.replace(/'/g, "\\'")}')">${song.title}</span>
                                ${song.year ? `<span class="song-year-badge">${song.year}</span>` : ''}
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
            </div>
        `;
    });

    results.innerHTML = html;
};

MusicGraph.prototype.buildEnergySet = function(startGenre, direction) {
    // Energy ordering for genres (low to high)
    const energyOrder = [
        'Cinematic', 'Classical', 'Electronic/Indie', 'Tropical House',
        'Progressive House', 'Pop', 'Pop/EDM', 'Future Bass', 'UK House',
        'Tech House', 'Trance', 'Melodic Bass', 'Electro House',
        'Trap/Bass', 'Drum & Bass', 'Dubstep/Bass', 'Midtempo Bass'
    ];

    const startIdx = energyOrder.indexOf(startGenre);
    let targetGenres;

    if (direction === 'up') {
        targetGenres = energyOrder.slice(Math.max(0, startIdx - 1));
    } else {
        targetGenres = energyOrder.slice(0, startIdx + 2).reverse();
    }

    // Build set following energy flow
    const set = [];
    const used = new Set();

    targetGenres.forEach(genre => {
        const candidates = this.nodes
            .filter(n => n.genre === genre && !used.has(n.id) && n.song_count > 0)
            .sort((a, b) => (b.song_count || 0) - (a.song_count || 0));

        if (candidates.length > 0) {
            const pick = candidates[0];
            set.push(pick);
            used.add(pick.id);
        }
    });

    return set.slice(0, 10);
};

MusicGraph.prototype.buildGenreJourney = function(startGenre) {
    const set = [];
    const usedGenres = new Set([startGenre]);
    const used = new Set();

    // Start with top artist from starting genre
    const starters = this.nodes
        .filter(n => n.genre === startGenre && n.song_count > 0)
        .sort((a, b) => (b.song_count || 0) - (a.song_count || 0));

    if (starters.length === 0) return [];

    let current = starters[0];
    set.push(current);
    used.add(current.id);

    // Follow connections to new genres
    for (let i = 0; i < 9; i++) {
        // Find connected artists in different genres
        const connections = this.getConnections(current)
            .filter(c => !used.has(c.id) && c.genre && c.genre !== 'Other');

        // Prefer new genres
        const newGenreConns = connections.filter(c => !usedGenres.has(c.genre));
        const candidates = newGenreConns.length > 0 ? newGenreConns : connections;

        if (candidates.length === 0) break;

        // Pick highest song count
        candidates.sort((a, b) => (b.song_count || 0) - (a.song_count || 0));
        current = candidates[0];
        set.push(current);
        used.add(current.id);
        if (current.genre) usedGenres.add(current.genre);
    }

    return set;
};

MusicGraph.prototype.addToSet = function(artistId) {
    const artist = this.nodes.find(n => n.id === artistId);
    if (!artist) return;

    // Add all songs from this artist to the set
    const songs = artist.songs || [];
    songs.forEach(song => {
        this.djSet.push({
            artistId: artist.id,
            artistName: artist.name,
            genre: artist.genre,
            song: song
        });
    });
    this.updateSetDisplay();
};

MusicGraph.prototype.addSongToSet = function(artistId, songTitle) {
    const artist = this.nodes.find(n => n.id === artistId);
    if (!artist) return;

    const song = (artist.songs || []).find(s => s.title === songTitle);
    if (!song) return;

    // Add this specific song to the set (allows duplicates for re-ordering)
    this.djSet.push({
        artistId: artist.id,
        artistName: artist.name,
        genre: artist.genre,
        song: song
    });
    this.updateSetDisplay();
};

MusicGraph.prototype.removeFromSet = function(index) {
    this.djSet.splice(index, 1);
    this.updateSetDisplay();
};

MusicGraph.prototype.clearSet = function() {
    this.djSet = [];
    this.updateSetDisplay();
};

MusicGraph.prototype.updateSetDisplay = function() {
    const container = document.getElementById('djSetList');

    if (this.djSet.length === 0) {
        container.innerHTML = '<p class="dj-hint">Click songs to add to your set</p>';
        return;
    }

    let html = `<div class="set-stats">${this.djSet.length} songs</div>`;

    html += this.djSet.map((item, i) => {
        const song = item.song || {};
        return `
            <div class="dj-set-song-item">
                <span class="set-song-num">${i + 1}.</span>
                <div class="set-song-info">
                    <span class="set-song-title">${song.title || 'Unknown'}</span>
                    <span class="set-song-artist">${item.artistName}</span>
                </div>
                <button class="remove-btn" onclick="event.stopPropagation(); graph.removeFromSet(${i})">×</button>
            </div>
        `;
    }).join('');

    container.innerHTML = html;
};

MusicGraph.prototype.exportSet = function() {
    if (this.djSet.length === 0) {
        alert('Your set is empty!');
        return;
    }

    // Create text export with song-based format
    const text = this.djSet.map((item, i) => {
        const song = item.song || {};
        return `${i + 1}. ${item.artistName} - ${song.title || 'Unknown'} [${item.genre || 'Unknown'}]`;
    }).join('\n');

    // Copy to clipboard
    navigator.clipboard.writeText(text).then(() => {
        alert('Set copied to clipboard!\n\n' + text);
    }).catch(() => {
        // Fallback
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `dj-set-${new Date().toISOString().slice(0, 10)}.txt`;
        a.click();
    });
};

// Nicotine++ Export - exports songs in format for Soulseek searching
MusicGraph.prototype.exportForNicotine = function() {
    if (this.djSet.length === 0) {
        alert('Your set is empty! Add songs to export.');
        return;
    }

    // Build search terms from the flat song list
    const searchTerms = [];
    const artistSet = new Set();

    this.djSet.forEach(item => {
        const song = item.song || {};
        artistSet.add(item.artistName);
        // Format: "Artist - Song Title [Album]" for better Soulseek search results
        let term = `${item.artistName} - ${song.title || 'Unknown'}`;
        if (song.album && song.album.trim()) {
            term += ` [${song.album}]`;
        }
        searchTerms.push(term);
    });

    // Show export modal
    this.showNicotineExportModal(searchTerms, Array.from(artistSet), []);
};

MusicGraph.prototype.showNicotineExportModal = function(searchTerms, artistsWithSongs, artistsWithoutSongs) {
    // Create modal if it doesn't exist
    let modal = document.getElementById('nicotine-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'nicotine-modal';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content" style="max-width: 700px;">
                <button class="modal-close" onclick="document.getElementById('nicotine-modal').classList.remove('open')">&times;</button>
                <h2 style="color: #f39c12;">Nicotine++ Export</h2>
                <div id="nicotine-content"></div>
            </div>
        `;
        document.body.appendChild(modal);

        // Close on background click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.classList.remove('open');
        });
    }

    const content = document.getElementById('nicotine-content');

    if (searchTerms.length === 0) {
        content.innerHTML = `
            <p style="color: #888; text-align: center;">No songs found for the selected artists.</p>
            <p style="color: #888; text-align: center;">Artists in set: ${artistsWithoutSongs.join(', ')}</p>
            <p style="color: #666; text-align: center; margin-top: 15px;">
                Tip: Click on artists to view their songs, then add artists with songs to your set.
            </p>
        `;
    } else {
        content.innerHTML = `
            <div class="nicotine-stats">
                <p><strong>${searchTerms.length}</strong> songs from <strong>${artistsWithSongs.length}</strong> artists</p>
                ${artistsWithoutSongs.length > 0 ? `<p style="color: #888; font-size: 0.85rem;">Skipped (no songs): ${artistsWithoutSongs.join(', ')}</p>` : ''}
            </div>

            <div class="nicotine-section">
                <h4>Search Terms (for Nicotine++ batch search)</h4>
                <textarea id="nicotine-search-terms" readonly rows="10">${searchTerms.join('\n')}</textarea>
                <div class="nicotine-actions">
                    <button class="btn btn-nicotine" onclick="graph.copyNicotineTerms()">Copy to Clipboard</button>
                    <button class="btn btn-secondary" onclick="graph.downloadNicotineFile()">Download .txt</button>
                </div>
            </div>

            <div class="nicotine-section">
                <h4>How to use in Nicotine++</h4>
                <ol class="nicotine-instructions">
                    <li>Copy the search terms above</li>
                    <li>In Nicotine++, go to <strong>Search → Wishlist</strong></li>
                    <li>Click <strong>Add</strong> and paste each search term, or</li>
                    <li>Use the downloaded .txt file with a batch search tool</li>
                    <li>Filter results by quality (FLAC, 320kbps, etc.)</li>
                </ol>
            </div>

            <div class="nicotine-section">
                <h4>Quick Search Format</h4>
                <p style="color: #888; font-size: 0.85rem;">
                    Each line is formatted as "Artist - Song Title [Album]" for optimal Soulseek search results.
                    The album helps find the exact release/version you want.
                </p>
            </div>
        `;
    }

    modal.classList.add('open');
};

MusicGraph.prototype.copyNicotineTerms = function() {
    const textarea = document.getElementById('nicotine-search-terms');
    navigator.clipboard.writeText(textarea.value).then(() => {
        const btn = document.querySelector('#nicotine-modal .btn-nicotine');
        const originalText = btn.textContent;
        btn.textContent = 'Copied!';
        btn.style.background = '#27ae60';
        setTimeout(() => {
            btn.textContent = originalText;
            btn.style.background = '';
        }, 2000);
    });
};

MusicGraph.prototype.downloadNicotineFile = function() {
    const textarea = document.getElementById('nicotine-search-terms');
    const blob = new Blob([textarea.value], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `nicotine-dj-set-${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
};

// Populate genre dropdown for set builder
MusicGraph.prototype.populateSetGenreDropdown = function() {
    const dropdown = document.getElementById('setGenre');
    if (!dropdown) return;

    const genres = new Set();
    this.nodes.forEach(n => {
        if (n.genre && n.genre !== 'Other') genres.add(n.genre);
    });

    dropdown.innerHTML = '<option value="">Select starting genre...</option>';
    Array.from(genres).sort().forEach(g => {
        dropdown.innerHTML += `<option value="${g}">${g}</option>`;
    });
};

// Override renderGraph to also populate DJ dropdowns
const originalRenderGraph = MusicGraph.prototype.renderGraph;
MusicGraph.prototype.renderGraph = function(data) {
    originalRenderGraph.call(this, data);
    this.populateSetGenreDropdown();
};

// Genre Chart functionality
MusicGraph.prototype.showGenreChart = function() {
    const modal = document.getElementById('genre-modal');
    const chartContainer = document.getElementById('genre-chart');
    const listContainer = document.getElementById('genre-list');

    // Count genres
    const genreCounts = {};
    let totalSongs = 0;
    this.nodes.forEach(n => {
        const genre = n.genre || 'Other';
        const count = n.song_count || 0;
        genreCounts[genre] = (genreCounts[genre] || 0) + count;
        totalSongs += count;
    });

    // Sort by count
    const sorted = Object.entries(genreCounts)
        .sort((a, b) => b[1] - a[1])
        .filter(([g, c]) => c > 0);

    const maxCount = sorted[0] ? sorted[0][1] : 1;

    // Build bar chart (top 12)
    chartContainer.innerHTML = sorted.slice(0, 12).map(([genre, count]) => {
        const color = this.getGenreColor(genre);
        const pct = (count / maxCount * 100).toFixed(0);
        const songPct = (count / totalSongs * 100).toFixed(1);
        return `
            <div class="genre-bar" onclick="graph.filterAndClose('${genre}')">
                <div class="genre-bar-label">${genre}</div>
                <div class="genre-bar-track">
                    <div class="genre-bar-fill" style="width: ${pct}%; background: ${color};">
                        ${count} (${songPct}%)
                    </div>
                </div>
            </div>
        `;
    }).join('');

    // Build full list
    listContainer.innerHTML = '<h4 style="margin-bottom: 10px; color: #888;">All Genres</h4>' +
        sorted.map(([genre, count]) => {
            const color = this.getGenreColor(genre);
            const artistCount = this.nodes.filter(n => n.genre === genre).length;
            return `
                <div class="genre-list-item" onclick="graph.filterAndClose('${genre}')">
                    <span class="genre-name">
                        <span class="genre-dot" style="background: ${color};"></span>
                        ${genre}
                    </span>
                    <span style="color: #888;">${artistCount} artists, ${count} songs</span>
                </div>
            `;
        }).join('');

    modal.classList.add('open');
};

MusicGraph.prototype.filterAndClose = function(genre) {
    document.getElementById('genre-modal').classList.remove('open');
    document.getElementById('genreFilter').value = genre;
    this.settings.selectedGenre = genre;
    this.filterByGenre();
};

function closeGenreModal() {
    document.getElementById('genre-modal').classList.remove('open');
}

// Update stats to include genre count
const originalUpdateStats = MusicGraph.prototype.updateStats;
MusicGraph.prototype.updateStats = function(stats) {
    originalUpdateStats.call(this, stats);

    // Count unique genres
    const genres = new Set();
    this.nodes.forEach(n => {
        if (n.genre && n.genre !== 'Other') genres.add(n.genre);
    });
    document.getElementById('totalGenres').textContent = genres.size;
};

// Song preview - update showArtistPanel to include play buttons
const originalShowArtistPanel = MusicGraph.prototype.showArtistPanel;
MusicGraph.prototype.showArtistPanel = function(artist) {
    const panel = document.getElementById('artist-panel');
    document.getElementById('artistName').textContent = artist.name;

    // Set image
    const img = document.getElementById('artistImage');
    img.src = artist.thumbnail || `https://ui-avatars.com/api/?name=${encodeURIComponent(artist.name)}&background=ff6b6b&color=fff&size=150`;

    // Stats
    const genreColor = artist.genre ? this.getGenreColor(artist.genre) : '#888';
    const totalPlays = artist.total_plays || 0;
    document.getElementById('artistStats').innerHTML = `
        ${artist.genre ? `<p><span>Genre:</span> <span style="color: ${genreColor}; font-weight: bold;">${artist.genre}</span></p>` : ''}
        <p><span>Songs in library:</span> <span>${artist.song_count || 0}</span></p>
        ${totalPlays > 0 ? `<p><span>Recent plays:</span> <span style="color: #1db954;">${totalPlays}</span></p>` : ''}
        <p><span>Type:</span> <span>${artist.in_library ? 'Library Artist' : 'Related Artist'}</span></p>
        <p><span style="cursor: pointer; color: #48dbfb;" onclick="graph.addToSet('${artist.id}')">+ Add to DJ Set</span></p>
    `;

    // Songs with play buttons, years, and play counts
    const songs = artist.songs || [];
    if (songs.length > 0) {
        const formatViews = (v) => {
            if (!v) return '';
            if (v >= 1000000000) return (v / 1000000000).toFixed(1) + 'B';
            if (v >= 1000000) return (v / 1000000).toFixed(1) + 'M';
            if (v >= 1000) return Math.floor(v / 1000) + 'K';
            return v.toString();
        };
        document.getElementById('artistSongs').innerHTML = `
            <h4>Your Liked Songs (${songs.length})</h4>
            <ul class="songs-list">
                ${songs.map(s => {
                    const yearStr = s.year ? `<span class="song-year">${s.year}</span>` : '';
                    const viewsStr = s.views ? `<span class="song-views">${formatViews(s.views)}</span>` : '';
                    const playsStr = s.plays > 0 ? `<span class="song-plays">${s.plays}x</span>` : '';
                    return `
                    <li>
                        <button class="play-btn" onclick="graph.playSong('${encodeURIComponent(artist.name)}', '${encodeURIComponent(s.title)}')" title="Search on YouTube">
                            ▶
                        </button>
                        <div class="song-info">
                            <span class="song-title">${s.title}</span>
                            <span class="song-artist">${artist.name}</span>
                            <span class="song-meta">
                                ${yearStr}
                                ${viewsStr}
                                ${playsStr}
                            </span>
                        </div>
                    </li>
                `}).join('')}
            </ul>
        `;
    } else {
        document.getElementById('artistSongs').innerHTML = '';
    }

    // Connections
    const connections = this.getConnections(artist);
    document.getElementById('artistConnections').innerHTML = `
        <h4>Connected Artists (${connections.length})</h4>
        <ul>
            ${connections.map(c => `<li onclick="graph.focusNode('${c.id}')">${c.name} (${c.type})</li>`).join('')}
        </ul>
    `;

    // Similar artists from Last.fm
    document.getElementById('artistSimilar').innerHTML = `
        <h4>Discover Similar</h4>
        <button class="btn btn-discover" onclick="graph.loadSimilarArtists('${artist.name.replace(/'/g, "\\'")}')">
            Find Similar Artists (Last.fm)
        </button>
        <div id="similarList"></div>
    `;

    panel.classList.add('open');
};

// Fetch similar artists from Last.fm API
MusicGraph.prototype.loadSimilarArtists = function(artistName) {
    const container = document.getElementById('similarList');
    container.innerHTML = '<p class="loading">Loading...</p>';

    fetch(`/api/similar/${encodeURIComponent(artistName)}`)
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                container.innerHTML = `<p class="error">${data.error}</p>`;
                return;
            }

            const similar = data.similar || [];
            if (similar.length === 0) {
                container.innerHTML = '<p>No similar artists found</p>';
                return;
            }

            // Check which artists are in our graph
            const inGraph = new Set(this.nodes.map(n => n.name.toLowerCase()));

            container.innerHTML = similar.map(a => {
                const isInGraph = inGraph.has(a.name.toLowerCase());
                const matchPct = Math.round(a.match * 100);
                return `
                    <div class="similar-artist ${isInGraph ? 'in-library' : ''}">
                        <span class="similar-name" ${isInGraph ? `onclick="graph.focusNodeByName('${a.name.replace(/'/g, "\\'")}')"` : ''}>${a.name}</span>
                        <span class="similar-match">${matchPct}%</span>
                        ${isInGraph ? '<span class="in-graph-badge">In Graph</span>' : ''}
                    </div>
                `;
            }).join('');
        })
        .catch(err => {
            container.innerHTML = `<p class="error">Failed to load: ${err.message}</p>`;
        });
};

// Focus on a node by artist name
MusicGraph.prototype.focusNodeByName = function(name) {
    const node = this.nodes.find(n => n.name.toLowerCase() === name.toLowerCase());
    if (node) {
        this.focusNode(node.id);
    }
};

// Play song - opens YouTube Music search
MusicGraph.prototype.playSong = function(artist, title) {
    const query = encodeURIComponent(`${decodeURIComponent(artist)} ${decodeURIComponent(title)}`);
    window.open(`https://music.youtube.com/search?q=${query}`, '_blank');
};

// Recommendation engine
MusicGraph.prototype.getRecommendations = function() {
    // Find artists similar to your top artists but not in your library
    const topArtists = this.nodes
        .filter(n => n.in_library && n.song_count > 0)
        .sort((a, b) => (b.song_count || 0) - (a.song_count || 0))
        .slice(0, 20);

    const recommendations = [];
    const seen = new Set();

    topArtists.forEach(artist => {
        const connections = this.getConnections(artist);
        connections.forEach(conn => {
            if (!conn.in_library && !seen.has(conn.id)) {
                seen.add(conn.id);
                recommendations.push({
                    ...conn,
                    reason: `Similar to ${artist.name}`
                });
            }
        });
    });

    // Sort by number of connections to your library
    recommendations.sort((a, b) => {
        const aConns = this.getConnections(a).filter(c => c.in_library).length;
        const bConns = this.getConnections(b).filter(c => c.in_library).length;
        return bConns - aConns;
    });

    return recommendations.slice(0, 10);
};

// Show recommendations modal
MusicGraph.prototype.showRecommendations = function() {
    const modal = document.getElementById('recs-modal');
    const listContainer = document.getElementById('recs-list');

    const recs = this.getRecommendations();

    if (recs.length === 0) {
        listContainer.innerHTML = '<p style="text-align: center; color: #888;">No recommendations found. Try loading more data!</p>';
    } else {
        listContainer.innerHTML = recs.map(rec => {
            const color = this.getGenreColor(rec.genre);
            return `
                <div class="rec-card" onclick="graph.focusAndCloseRecs('${rec.id}')">
                    <div class="rec-header">
                        <span class="rec-dot" style="background: ${color};"></span>
                        <span class="rec-name">${rec.name}</span>
                    </div>
                    <div class="rec-meta">
                        <span style="color: ${color};">${rec.genre || 'Unknown'}</span>
                        <span class="rec-reason">${rec.reason}</span>
                    </div>
                    <div class="rec-actions">
                        <button class="btn btn-sm btn-dj" onclick="event.stopPropagation(); graph.addToSet('${rec.id}'); this.textContent='Added!';">+ Add to Set</button>
                        <button class="btn btn-sm btn-secondary" onclick="event.stopPropagation(); window.open('https://music.youtube.com/search?q=${encodeURIComponent(rec.name)}', '_blank')">Listen</button>
                    </div>
                </div>
            `;
        }).join('');
    }

    modal.classList.add('open');
};

MusicGraph.prototype.focusAndCloseRecs = function(nodeId) {
    document.getElementById('recs-modal').classList.remove('open');
    this.focusNode(nodeId);
};

function closeRecsModal() {
    document.getElementById('recs-modal').classList.remove('open');
}

// Close modal on escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.getElementById('genre-modal').classList.remove('open');
        document.getElementById('recs-modal').classList.remove('open');
    }
});

// Close modal on background click
document.getElementById('genre-modal')?.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) {
        e.target.classList.remove('open');
    }
});

// Auto-load user data on page load (falls back to demo if no data)
window.addEventListener('load', () => {
    setTimeout(() => graph.loadUserData(), 500);
});

// ============ Social Features ============

async function createAndShareProfile() {
    const name = prompt('Enter your display name (optional):') || '';

    try {
        const response = await fetch('/api/profile/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, public: true })
        });

        const data = await response.json();

        if (data.error) {
            alert('Error: ' + data.error);
            return;
        }

        // Save profile ID locally
        localStorage.setItem('myProfileId', data.id);

        // Show share link
        const shareUrl = window.location.origin + data.share_url;
        const copied = await copyToClipboard(shareUrl);

        if (copied) {
            alert(`Profile created! Share link copied to clipboard:\n\n${shareUrl}`);
        } else {
            prompt('Profile created! Share this link:', shareUrl);
        }

    } catch (error) {
        alert('Error creating profile: ' + error.message);
    }
}

async function createComparisonGroup() {
    const name = prompt('Enter group name (optional):') || '';

    try {
        const response = await fetch('/api/group/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });

        const data = await response.json();

        if (data.error) {
            alert('Error: ' + data.error);
            return;
        }

        // If user has a profile, auto-join the group
        const myProfileId = localStorage.getItem('myProfileId');
        if (myProfileId) {
            await fetch(`/api/group/${data.id}/join`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ profile_id: myProfileId })
            });
        }

        // Show join link
        const joinUrl = window.location.origin + data.join_url;
        const copied = await copyToClipboard(joinUrl);

        if (copied) {
            alert(`Group created! Invite link copied to clipboard:\n\n${joinUrl}`);
        } else {
            prompt('Group created! Share this invite link:', joinUrl);
        }

        // Open group page
        window.location.href = `/group/${data.id}`;

    } catch (error) {
        alert('Error creating group: ' + error.message);
    }
}

async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch {
        return false;
    }
}

// ==================== Upload Functionality ====================

function openUploadModal() {
    document.getElementById('uploadModal').classList.add('active');
}

function closeUploadModal() {
    document.getElementById('uploadModal').classList.remove('active');
    document.getElementById('uploadStatus').className = 'upload-status';
    document.getElementById('uploadStatus').textContent = '';
}

function showPasteModal() {
    closeUploadModal();
    document.getElementById('pasteModal').classList.add('active');
}

function closePasteModal() {
    document.getElementById('pasteModal').classList.remove('active');
    document.getElementById('pasteArea').value = '';
}

function triggerFileUpload() {
    document.getElementById('fileInput').click();
}

function setUploadStatus(status, message) {
    const statusEl = document.getElementById('uploadStatus');
    statusEl.className = 'upload-status ' + status;
    statusEl.textContent = message;
}

// Handle file selection
document.getElementById('fileInput')?.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploadStatus('loading', 'Processing your file...');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.error) {
            setUploadStatus('error', 'Error: ' + data.error);
            return;
        }

        setUploadStatus('success', `Found ${data.song_count} songs from ${data.artist_count} artists!`);

        // Load the graph with the uploaded data
        setTimeout(() => {
            closeUploadModal();
            graph.loadData(data.graph_data);
        }, 1500);

    } catch (error) {
        setUploadStatus('error', 'Error uploading file: ' + error.message);
    }

    // Reset file input
    e.target.value = '';
});

// Process pasted playlist data
async function processPastedData() {
    const pasteArea = document.getElementById('pasteArea');
    const text = pasteArea.value.trim();

    if (!text) {
        alert('Please paste your playlist data first');
        return;
    }

    closePasteModal();
    openUploadModal();
    setUploadStatus('loading', 'Processing your playlist...');

    try {
        const response = await fetch('/api/upload/paste', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ playlist_text: text })
        });

        const data = await response.json();

        if (data.error) {
            setUploadStatus('error', 'Error: ' + data.error);
            return;
        }

        setUploadStatus('success', `Found ${data.song_count} songs from ${data.artist_count} artists!`);

        // Load the graph with the processed data
        setTimeout(() => {
            closeUploadModal();
            graph.loadData(data.graph_data);
        }, 1500);

    } catch (error) {
        setUploadStatus('error', 'Error processing playlist: ' + error.message);
    }
}

// Set up upload button click handler
document.getElementById('uploadData')?.addEventListener('click', openUploadModal);

// Close modals on outside click
window.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) {
        e.target.classList.remove('active');
    }
});
