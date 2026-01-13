/**
 * Compare.js - Music Taste Comparison UI
 * Handles 1:1 comparison, group comparison, and profile creation
 */

// Parse URL to determine mode
const path = window.location.pathname;
const pathParts = path.split('/').filter(p => p);

let mode = 'create'; // Default: show create profile
let targetProfileId = null;
let groupId = null;
let myProfileId = localStorage.getItem('myProfileId');

// Determine mode from URL
if (pathParts[0] === 'compare' && pathParts[1]) {
    targetProfileId = pathParts[1];
    mode = 'compare';
} else if (pathParts[0] === 'group' && pathParts[1]) {
    groupId = pathParts[1];
    mode = pathParts[2] === 'join' ? 'group-join' : 'group';
}

// Initialize page
document.addEventListener('DOMContentLoaded', init);

async function init() {
    const loading = document.getElementById('loading');
    const result = document.getElementById('comparison-result');
    const createSection = document.getElementById('create-profile-section');

    if (mode === 'compare') {
        // Compare with a specific profile
        if (myProfileId) {
            // We have our profile, show comparison
            await loadComparison(myProfileId, targetProfileId);
        } else {
            // Try to compare with current user's local music data
            await loadComparisonWithCurrent(targetProfileId);
        }
    } else if (mode === 'group' || mode === 'group-join') {
        // Group comparison
        await loadGroupView(groupId);
    } else {
        // Default: create profile page
        loading.style.display = 'none';
        createSection.style.display = 'block';
    }
}

async function loadComparisonWithCurrent(targetProfileId) {
    const loading = document.getElementById('loading');
    const result = document.getElementById('comparison-result');
    const createSection = document.getElementById('create-profile-section');

    try {
        const response = await fetch(`/api/compare/with-current/${targetProfileId}`);
        const data = await response.json();

        if (data.error) {
            // No local data, show create profile prompt
            loading.style.display = 'none';
            createSection.style.display = 'block';
            createSection.innerHTML = `
                <div class="compatibility-hero">
                    <h2>Compare Your Music Taste</h2>
                    <p style="color: #888; margin-top: 10px;">Create your profile to compare with this person</p>
                    <div class="action-buttons">
                        <button class="btn btn-primary" onclick="showCreateModal()">Create My Profile</button>
                    </div>
                </div>
            `;
            return;
        }

        loading.style.display = 'none';
        result.style.display = 'block';
        result.innerHTML = renderComparison(data);

    } catch (error) {
        loading.innerHTML = `
            <p style="color: #e74c3c;">Error: ${error.message}</p>
            <div class="action-buttons">
                <button class="btn btn-secondary" onclick="showCreateModal()">Create Profile</button>
                <a href="/" class="btn btn-primary">Back to Map</a>
            </div>
        `;
    }
}

async function loadComparison(profile1Id, profile2Id) {
    const loading = document.getElementById('loading');
    const result = document.getElementById('comparison-result');

    try {
        let endpoint = `/api/compare/${profile1Id}/${profile2Id}`;

        // If comparing with current user's local data
        if (profile1Id === 'current') {
            endpoint = `/api/compare/with-current/${profile2Id}`;
        }

        const response = await fetch(endpoint);
        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        loading.style.display = 'none';
        result.style.display = 'block';
        result.innerHTML = renderComparison(data);

    } catch (error) {
        loading.innerHTML = `
            <p style="color: #e74c3c;">Error: ${error.message}</p>
            <div class="action-buttons">
                <button class="btn btn-secondary" onclick="showCreateModal()">Create Profile</button>
                <a href="/" class="btn btn-primary">Back to Map</a>
            </div>
        `;
    }
}

function renderComparison(data) {
    const compatibilityClass = data.overall >= 70 ? 'high' : data.overall >= 40 ? 'medium' : 'low';

    return `
        <div class="compatibility-hero">
            <div class="compatibility-score">${Math.round(data.overall)}%</div>
            <div class="compatibility-label">Music Compatibility</div>

            <div class="profiles-row">
                <div class="profile-card">
                    <div class="profile-avatar">${getInitials(data.profile1.name)}</div>
                    <div class="profile-name">${data.profile1.name}</div>
                    <div class="profile-stats">${data.profile1_artist_count} artists</div>
                </div>
                <div class="vs-badge">VS</div>
                <div class="profile-card">
                    <div class="profile-avatar" style="background: linear-gradient(135deg, #48dbfb, #0abde3);">
                        ${getInitials(data.profile2.name)}
                    </div>
                    <div class="profile-name">${data.profile2.name}</div>
                    <div class="profile-stats">${data.profile2_artist_count} artists</div>
                </div>
            </div>
        </div>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value">${data.shared_count}</div>
                <div class="metric-label">Shared Artists</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${data.artist_overlap}%</div>
                <div class="metric-label">Artist Overlap</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${data.genre_match}%</div>
                <div class="metric-label">Genre Match</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${data.weighted_overlap}%</div>
                <div class="metric-label">Listening Similarity</div>
            </div>
        </div>

        ${data.shared_artists.length > 0 ? `
        <div class="section">
            <h3 class="section-title">Artists You Both Love</h3>
            <div class="artists-grid" id="sharedArtistsGrid">
                ${data.shared_artists.slice(0, 20).map(artist => `
                    <div class="artist-chip shared" data-artist="${escapeHtml(artist)}" onclick="highlightArtist(this, 'shared')">
                        <span class="artist-icon">&#9829;</span>
                        <span>${escapeHtml(artist)}</span>
                    </div>
                `).join('')}
            </div>
        </div>
        ` : ''}

        <div class="section">
            <h3 class="section-title">Genre Comparison</h3>
            <div class="genre-comparison">
                <div class="genre-column">
                    <h4>${data.profile1.name}'s Taste</h4>
                    ${renderGenreBars(data.genre_breakdown.profile1, '#ff6b6b')}
                </div>
                <div class="genre-column">
                    <h4>${data.profile2.name}'s Taste</h4>
                    ${renderGenreBars(data.genre_breakdown.profile2, '#48dbfb')}
                </div>
            </div>
        </div>

        <div class="section">
            <h3 class="section-title">Unique to ${escapeHtml(data.profile1.name)}</h3>
            <div class="artists-grid" id="unique1Grid">
                ${data.unique_to_profile1.slice(0, 15).map(artist => `
                    <div class="artist-chip unique-1" data-artist="${escapeHtml(artist)}" onclick="highlightArtist(this, 'unique-1')">
                        <span>${escapeHtml(artist)}</span>
                    </div>
                `).join('')}
            </div>
        </div>

        <div class="section">
            <h3 class="section-title">Unique to ${escapeHtml(data.profile2.name)}</h3>
            <div class="artists-grid" id="unique2Grid">
                ${data.unique_to_profile2.slice(0, 15).map(artist => `
                    <div class="artist-chip unique-2" data-artist="${escapeHtml(artist)}" onclick="highlightArtist(this, 'unique-2')">
                        <span>${escapeHtml(artist)}</span>
                    </div>
                `).join('')}
            </div>
        </div>

        <div class="action-buttons">
            <button class="btn btn-secondary" onclick="shareComparison()">Share Result</button>
            <a href="/leaderboard" class="btn btn-secondary">Find More People</a>
            <a href="/" class="btn btn-primary">Back to Map</a>
        </div>
    `;
}

function renderGenreBars(genreData, color) {
    const sorted = Object.entries(genreData)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 8);

    return sorted.map(([genre, weight]) => `
        <div class="genre-bar">
            <span class="genre-bar-label">${genre}</span>
            <div class="genre-bar-track">
                <div class="genre-bar-fill" style="width: ${weight * 100}%; background: ${color};"></div>
            </div>
            <span class="genre-bar-value">${Math.round(weight * 100)}%</span>
        </div>
    `).join('');
}

async function loadGroupView(groupId) {
    const loading = document.getElementById('loading');
    const result = document.getElementById('comparison-result');

    try {
        // Get group info
        const groupResponse = await fetch(`/api/group/${groupId}`);
        const group = await groupResponse.json();

        if (group.error) {
            throw new Error(group.error);
        }

        // If joining, show join UI
        if (mode === 'group-join' && !myProfileId) {
            loading.style.display = 'none';
            result.style.display = 'block';
            result.innerHTML = `
                <div class="compatibility-hero">
                    <h2>Join "${group.name}"</h2>
                    <p style="color: #888; margin-top: 10px;">${group.member_count} members so far</p>
                    <div class="action-buttons">
                        <button class="btn btn-primary" onclick="showCreateModal()">Create Profile & Join</button>
                    </div>
                </div>
            `;
            return;
        }

        // Get comparison results if enough members
        if (group.member_count >= 2) {
            const resultsResponse = await fetch(`/api/group/${groupId}/results`);
            const results = await resultsResponse.json();

            loading.style.display = 'none';
            result.style.display = 'block';
            result.innerHTML = renderGroupComparison(group, results);
        } else {
            loading.style.display = 'none';
            result.style.display = 'block';
            result.innerHTML = `
                <div class="compatibility-hero">
                    <h2>${group.name}</h2>
                    <p style="color: #888; margin-top: 10px;">Waiting for more members (${group.member_count}/2 minimum)</p>
                    <p style="margin-top: 20px;">Share this link to invite others:</p>
                    <div class="share-link" style="max-width: 400px; margin: 20px auto;">
                        <input type="text" value="${window.location.origin}/group/${groupId}/join" readonly id="groupLink">
                        <button class="btn btn-secondary" onclick="copyGroupLink()">Copy</button>
                    </div>
                </div>
                ${renderGroupMembers(group.members)}
            `;
        }

    } catch (error) {
        loading.innerHTML = `<p style="color: #e74c3c;">Error: ${error.message}</p>`;
    }
}

function renderGroupComparison(group, results) {
    return `
        <div class="compatibility-hero">
            <h2>${group.name}</h2>
            <div class="compatibility-score">${results.group_avg}%</div>
            <div class="compatibility-label">Group Compatibility</div>
        </div>

        <div class="section">
            <h3 class="section-title">Compatibility Matrix</h3>
            <div class="group-matrix">
                <table class="matrix-table">
                    <tr>
                        <th></th>
                        ${results.profile_names.map(name => `<th>${name}</th>`).join('')}
                    </tr>
                    ${results.matrix.map((row, i) => `
                        <tr>
                            <th>${results.profile_names[i]}</th>
                            ${row.map((val, j) => `
                                <td class="matrix-cell ${val >= 70 ? 'high' : val >= 40 ? 'medium' : 'low'}">
                                    ${i === j ? '-' : Math.round(val) + '%'}
                                </td>
                            `).join('')}
                        </tr>
                    `).join('')}
                </table>
            </div>
        </div>

        ${results.consensus_artists.length > 0 ? `
        <div class="section">
            <h3 class="section-title">Everyone Loves These Artists</h3>
            <div class="artists-grid">
                ${results.consensus_artists.map(artist => `
                    <div class="artist-chip" style="background: rgba(46, 204, 113, 0.2); border: 1px solid #2ecc71;">
                        <span>${artist}</span>
                    </div>
                `).join('')}
            </div>
        </div>
        ` : ''}

        ${results.bridge_artists.length > 0 ? `
        <div class="section">
            <h3 class="section-title">Bridge Artists (Connect Different Tastes)</h3>
            <div class="artists-grid">
                ${results.bridge_artists.slice(0, 15).map(a => `
                    <div class="artist-chip">
                        <span>${a.name}</span>
                        <small style="color: #888;">(${a.in_profiles} people)</small>
                    </div>
                `).join('')}
            </div>
        </div>
        ` : ''}

        <div class="section">
            <h3 class="section-title">Member Rankings</h3>
            <div class="artists-grid">
                ${results.avg_compatibility.sort((a, b) => b.avg_compatibility - a.avg_compatibility).map((member, i) => `
                    <div class="metric-card" style="padding: 15px;">
                        <div style="font-size: 1.5rem; font-weight: bold;">#${i + 1}</div>
                        <div style="font-size: 1.1rem; margin-top: 5px;">${member.name}</div>
                        <div style="color: #48dbfb; font-size: 1.2rem;">${member.avg_compatibility}%</div>
                        <div style="color: #888; font-size: 0.8rem;">avg compatibility</div>
                    </div>
                `).join('')}
            </div>
        </div>

        <div class="action-buttons">
            <button class="btn btn-secondary" onclick="copyGroupLink()">Invite More</button>
            <a href="/" class="btn btn-primary">Back to Map</a>
        </div>

        <div class="share-link" style="max-width: 400px; margin: 20px auto; display: none;" id="groupLinkContainer">
            <input type="text" value="${window.location.origin}/group/${groupId}/join" readonly id="groupLink">
        </div>
    `;
}

function renderGroupMembers(members) {
    return `
        <div class="section">
            <h3 class="section-title">Current Members</h3>
            <div class="artists-grid">
                ${members.map(m => `
                    <div class="profile-card">
                        <div class="profile-avatar">${getInitials(m.name)}</div>
                        <div class="profile-name">${m.name}</div>
                        <div class="profile-stats">${m.stats.song_count || 0} songs</div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

// Profile creation
function showCreateModal() {
    document.getElementById('createModal').classList.add('active');
}

function closeModal() {
    document.getElementById('createModal').classList.remove('active');
}

async function createProfile() {
    const name = document.getElementById('profileName').value.trim();

    try {
        const response = await fetch('/api/profile/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, public: true })
        });

        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        // Save profile ID
        myProfileId = data.id;
        localStorage.setItem('myProfileId', data.id);

        // Show share link
        const resultDiv = document.getElementById('profileResult');
        const shareUrl = document.getElementById('shareUrl');
        shareUrl.value = window.location.origin + data.share_url;
        resultDiv.style.display = 'block';

        // If we were comparing, reload to show comparison
        if (targetProfileId) {
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        }

        // If joining a group, join it
        if (groupId) {
            await fetch(`/api/group/${groupId}/join`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ profile_id: data.id })
            });
            setTimeout(() => {
                window.location.href = `/group/${groupId}`;
            }, 2000);
        }

    } catch (error) {
        alert('Error creating profile: ' + error.message);
    }
}

function copyShareLink() {
    const input = document.getElementById('shareUrl');
    input.select();
    document.execCommand('copy');
    alert('Link copied!');
}

function copyGroupLink() {
    const input = document.getElementById('groupLink');
    if (input) {
        input.select();
        document.execCommand('copy');
        alert('Link copied!');
    }
}

function shareComparison() {
    const url = window.location.href;
    if (navigator.share) {
        navigator.share({
            title: 'Music Taste Comparison',
            url: url
        });
    } else {
        navigator.clipboard.writeText(url);
        alert('Link copied!');
    }
}

function getInitials(name) {
    return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Artist highlighting in comparison view
let selectedArtist = null;

function highlightArtist(element, type) {
    const artistName = element.dataset.artist;

    // Toggle selection
    if (selectedArtist === artistName) {
        // Deselect
        clearHighlights();
        selectedArtist = null;
        return;
    }

    selectedArtist = artistName;

    // Clear previous highlights
    clearHighlights();

    // Add selected class to clicked element
    element.classList.add('selected');

    // Fade all other artists
    document.querySelectorAll('.artist-chip').forEach(chip => {
        if (chip !== element) {
            chip.classList.add('faded');
        }
    });

    // Show toast with artist info
    showArtistToast(artistName, type);
}

function clearHighlights() {
    document.querySelectorAll('.artist-chip').forEach(chip => {
        chip.classList.remove('selected', 'faded');
    });
    hideArtistToast();
}

function showArtistToast(artistName, type) {
    let toast = document.getElementById('artistToast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'artistToast';
        toast.className = 'artist-toast';
        document.body.appendChild(toast);
    }

    let typeLabel = '';
    let typeColor = '';

    if (type === 'shared') {
        typeLabel = 'Both of you love this artist!';
        typeColor = '#9b59b6';
    } else if (type === 'unique-1') {
        typeLabel = 'Only in your library';
        typeColor = '#ff6b6b';
    } else if (type === 'unique-2') {
        typeLabel = 'Only in their library - check them out!';
        typeColor = '#48dbfb';
    }

    toast.innerHTML = `
        <div class="toast-content" style="border-left: 4px solid ${typeColor};">
            <div class="toast-artist">${artistName}</div>
            <div class="toast-type" style="color: ${typeColor};">${typeLabel}</div>
        </div>
    `;
    toast.classList.add('visible');
}

function hideArtistToast() {
    const toast = document.getElementById('artistToast');
    if (toast) {
        toast.classList.remove('visible');
    }
}

// Click outside to clear highlights
document.addEventListener('click', (e) => {
    if (!e.target.closest('.artist-chip') && selectedArtist) {
        clearHighlights();
        selectedArtist = null;
    }
});
