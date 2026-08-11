const profileId = window.location.pathname.split('/').pop();

const el = id => document.getElementById(id);
const pct = v => `${Math.round(v * 100)}%`;

// Artist/track names originate from a user's imported library and this page
// is served at a public share link, so anything derived from them must be
// escaped before it lands in innerHTML.
function esc(s) {
    return String(s).replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
}

function bars(entries, total) {
    return entries.map(([label, value]) => `
        <div class="bar-row">
            <span class="bar-label">${esc(label)}</span>
            <span class="bar-track"><span class="bar-fill" style="width:${(value / total) * 100}%"></span></span>
            <span class="bar-value">${pct(value / total)}</span>
        </div>`).join('');
}

function section(node, title, html) {
    node.innerHTML = `<h2>${title}</h2>${html}`;
    node.hidden = false;
}

async function load() {
    const response = await fetch(`/api/profile/${profileId}/stats`);
    if (!response.ok) {
        el('archetypeName').textContent = 'Profile not found';
        return;
    }
    const { profile, stats, archetype, badges, peer_percentile } = await response.json();

    el('archetypeName').textContent = archetype.name;
    el('archetypeTagline').textContent = archetype.tagline;
    el('profileName').textContent = profile.name;
    el('badges').innerHTML = badges
        .map(b => `<span class="badge">${esc(b.label)}</span>`).join('');

    el('headlineStats').innerHTML = `
        <div class="stat-tile"><span>${stats.artist_count}</span><label>Artists</label></div>
        <div class="stat-tile"><span>${stats.song_count}</span><label>Songs</label></div>
        <div class="stat-tile"><span>${Math.round(stats.diversity * 100)}<small>/100</small></span><label>Diversity</label></div>`;

    // stats carries three song populations that legitimately disagree
    // (song_count, the year_coverage denominator, and artist-song
    // appearances — see build_profile_stats.__doc__), so each figure below
    // is labelled with the population it actually describes.
    if (stats.obscurity !== null) {
        let html = `<p class="big-number">${stats.obscurity.toFixed(1)}<small>/100</small></p>
                    <p class="muted">0 means everyone knows them. 100 means nobody does.</p>`;
        if (peer_percentile !== null) {
            html += `<p>More obscure than <strong>${peer_percentile}%</strong> of profiles here.</p>`;
        }
        if (stats.scene_obscurity !== null) {
            html += `<p>That score is dragged up by a few very famous names. Judged only
                     against other artists in the <em>same genres</em> — not all of music —
                     you sit at the <strong>${stats.scene_obscurity.toFixed(0)}th</strong>
                     obscurity percentile within your own scenes.</p>`;
        }
        section(el('obscuritySection'), 'Obscurity', html);
    }

    // "Other" is artists whose genre could not be resolved — the absence of
    // a genre, not a genre itself — so it must not be ranked among the real
    // ones. Dropping it silently would leave the shown bars summing to less
    // than 100%, which is its own kind of misleading, so its share is
    // reported separately instead.
    const all = Object.entries(stats.genres).sort((a, b) => b[1] - a[1]);
    const genres = all.filter(([name]) => name !== 'Other');
    const unresolved = stats.genres['Other'] || 0;
    if (genres.length) {
        let html = bars(genres.slice(0, 10), 1);
        if (unresolved > 0.01) {
            html += `<p class="muted">${pct(unresolved)} of your library could not be
                     matched to a genre and is not shown above.</p>`;
        }
        section(el('genreSection'), 'Genres', html);
    }

    if (stats.clusters.length) {
        section(el('clusterSection'), 'Your musical worlds', stats.clusters.slice(0, 6).map(c => `
            <div class="cluster">
                <strong>${esc(c.genre)}</strong>
                <span class="muted">${c.size} artists</span>
                <div class="muted">${c.members.slice(0, 4).map(esc).join(', ')}</div>
            </div>`).join(''));
    }

    if (stats.decades) {
        const decades = Object.entries(stats.decades).sort((a, b) => a[0] - b[0]);
        const total = decades.reduce((sum, [, n]) => sum + n, 0);
        section(el('eraSection'), 'Eras',
            bars(decades.map(([d, n]) => [`${d}s`, n]), total) +
            `<p class="muted">Median release year ${stats.median_year}.
             Year data covers ${pct(stats.year_coverage)} of your tracks.</p>`);
    }

    const moods = Object.entries(stats.moods).sort((a, b) => b[1] - a[1]);
    if (moods.length) {
        section(el('moodSection'), 'Moods',
            bars(moods, 1) + `<p class="muted">Derived from Last.fm tags, not audio analysis.</p>`);
    }

    if (stats.top_artists.length) {
        section(el('topArtistSection'), 'Most played', `<ol class="top-artists">${
            stats.top_artists.slice(0, 20)
                .map(([name, n]) => `<li><span>${esc(name)}</span><span class="muted">${n}</span></li>`)
                .join('')}</ol>`);
    }
}

el('copyLink').addEventListener('click', () => {
    navigator.clipboard.writeText(window.location.href);
    el('copyLink').textContent = 'Copied';
});

el('deleteProfile').addEventListener('click', async () => {
    if (!confirm('Delete this profile permanently? The share link will stop working.')) return;
    await fetch(`/api/profile/${profileId}`, { method: 'DELETE' });
    if (localStorage.getItem('myProfileId') === profileId) {
        localStorage.removeItem('myProfileId');
    }
    window.location.href = '/';
});

load();
