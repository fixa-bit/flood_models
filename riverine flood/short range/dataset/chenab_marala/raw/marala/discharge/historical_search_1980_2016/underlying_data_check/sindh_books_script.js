class BookLibraryComponent {
    constructor(hostOrId, opts = {}) {
        this.host = typeof hostOrId === 'string' ? document.getElementById(hostOrId) : hostOrId;
        if (!this.host) throw new Error('Host element not found');

        this.apiUrl = opts.apiUrl || 'https://api.hicsindh.pk/public/ELib/Books';
        this.pageSize = Number(opts.pageSize) || 12;

        this._uid = 'blc_' + Math.random().toString(36).slice(2, 9);

        this.originalBooks = [];
        this.visibleBooks = [];
        this.page = 1;

        this._renderShell();
        this._wireStaticEvents();
    }

    _id(name) { return `${this._uid}__${name}`; }
    _el(name) { return document.getElementById(this._id(name)); }

    _renderShell() {
        const html = `
      <div class="container" data-aos="fade-up" id="${this._id('root')}">
        <div class="section-title">
          <h2>E Books</h2>
          <div class="row align-items-center justify-content-center mb-2">
            <div class="col-md-8">
              <div class="input-group">
                <input id="${this._id('search')}" class="form-control" type="search" placeholder="Search title, author, publisher..." />
                <button id="${this._id('searchBtn')}" class="btn btn-primary" type="button">Search</button>
                <div class="input-group-text ms-2" id="${this._id('count')}">Books: 0</div>
              </div>

              <div class="input-group mt-2">
                <div class="input-group-text">Filters</div>

                <select class="form-control custom-select" style="max-width:250px;" id="${this._id('category')}">
                  <option value="0">All Categories</option>
                </select>

                <select class="form-control custom-select" style="max-width:165px;" id="${this._id('publisher')}">
                  <option value="0">All Publishers</option>
                </select>

                <select class="form-control custom-select" style="max-width:192px;" id="${this._id('year')}">
                  <option value="0">All Years</option>
                </select>

                <select class="form-control custom-select" style="max-width:200px;" id="${this._id('language')}">
                  <option value="0">All Languages</option>
                </select>

                <button class="btn btn-outline-secondary" type="button" id="${this._id('reset')}" title="Reset filters">
                  <i class="bx bx-reset"></i>
                </button>

                <input type="hidden" id="${this._id('sfid')}" value="9">
              </div>
            </div>
          </div>
        </div>

        <div class="clearfix"></div>
        <div class="rows">
          <div class="row content mt-2" id="${this._id('cards')}"></div>
          <div class="row mt-3">
            <div class="col-12 d-flex justify-content-center align-items-center" id="${this._id('pagination')}"></div>
          </div>
        </div>
      </div>
    `;
        this.host.innerHTML = html;
    }

    _wireStaticEvents() {
        const searchInput = this._el('search');
        const searchBtn = this._el('searchBtn');
        const resetBtn = this._el('reset');
        const debounce = (fn, wait = 300) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), wait); }; };

        if (searchInput) {
            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') { e.preventDefault(); this._applyFiltersResetPage(); }
            });
            searchInput.addEventListener('input', debounce(() => this._applyFiltersResetPage(), 350));
        }
        if (searchBtn) searchBtn.addEventListener('click', () => this._applyFiltersResetPage());
        if (resetBtn) resetBtn.addEventListener('click', () => {
            ['category', 'publisher', 'year', 'language'].forEach(id => {
                const el = this._el(id); if (el) el.value = "0";
            });
            const s = this._el('search'); if (s) s.value = '';
            this.visibleBooks = this.originalBooks.slice();
            this.page = 1;
            this._populateFiltersDynamic(this.visibleBooks); // update counts based on visible set
            this._renderPage();
        });
    }

    async load() {
        const cardsEl = this._el('cards');
        if (cardsEl) cardsEl.innerHTML = `<div class="text-center py-4"><span class="spinner-border"></span> Loading books…</div>`;

        if (typeof loadFlow !== 'function') {
            this._showError('cards', 'loadFlow is not available');
            return;
        }

        try {
            const data = await loadFlow(this.apiUrl);
            if (!Array.isArray(data)) throw new Error('Invalid data from loadFlow');
            this.originalBooks = data;
            this.visibleBooks = data.slice();
            this.page = 1;

            // populate selects: options derived from original dataset; counts from current visible set
            this._populateFiltersDynamic(this.visibleBooks);

            this._wireFilterEvents();
            this._renderPage();
        } catch (err) {
            console.error(err);
            this._showError('cards', 'Failed to load books');
        }
    }

    _showError(elName, message) {
        const el = this._el(elName);
        if (el) el.innerHTML = `<div class="alert alert-danger">${message}</div>`;
        else alert(message);
    }

    // counts from an arbitrary set
    _getCounts(items, key) {
        const counts = Object.create(null);
        items.forEach(item => {
            const k = (item[key] ?? '') + '';
            counts[k] = (counts[k] || 0) + 1;
        });
        return counts;
    }

    // unique keys based on ORIGINAL_BOOKS so options never disappear
    _uniqueKeysFromOriginal(key) {
        const map = Object.create(null);
        this.originalBooks.forEach(item => {
            const k = (item[key] ?? '') + '';
            if (k === '') return;
            map[k] = true;
        });
        return Object.keys(map).sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }));
    }

    // populate selects: options come from ORIGINAL_BOOKS, counts from currentSet,
    // and options with count 0 are omitted (except the "All ..." first option)
    _populateFiltersDynamic(currentSet) {
        this._updateSelectDynamic('category', 'category', 'All Categories', currentSet);
        this._updateSelectDynamic('publisher', 'publisher', 'All Publishers', currentSet);
        this._updateSelectDynamic('year', 'yearPublished', 'All Years', currentSet);
        this._updateSelectDynamic('language', 'language', 'All Languages', currentSet);
    }

    _updateSelectDynamic(domName, dataKey, allLabel, currentSet) {
        const select = this._el(domName);
        if (!select) return;
        const previous = select.value;

        const countsForCurrent = this._getCounts(currentSet, dataKey);
        const allKeys = this._uniqueKeysFromOriginal(dataKey);

        select.innerHTML = '';
        const allOpt = document.createElement('option');
        allOpt.value = "0";
        allOpt.textContent = `${allLabel}`; // no count on first option
        select.appendChild(allOpt);

        allKeys.forEach(k => {
            const cnt = countsForCurrent[k] || 0;
            if (cnt === 0) return; // skip options with zero count
            const opt = document.createElement('option');
            opt.value = k;
            opt.textContent = `${k} (${cnt})`;
            select.appendChild(opt);
        });

        // restore previous selection if still present, otherwise reset to 0
        if (previous && Array.from(select.options).some(o => o.value === previous)) {
            select.value = previous;
        } else {
            select.value = "0";
        }
    }

    _wireFilterEvents() {
        ['category', 'publisher', 'year', 'language'].forEach(name => {
            const el = this._el(name);
            if (!el) return;
            el.addEventListener('change', () => this._applyFiltersResetPage());
        });
    }

    _getFilterValues() {
        return {
            category: this._el('category')?.value || "0",
            publisher: this._el('publisher')?.value || "0",
            year: this._el('year')?.value || "0",
            language: this._el('language')?.value || "0",
            search: (this._el('search')?.value || '').trim().toLowerCase()
        };
    }

    _applyFiltersResetPage() {
        this.page = 1;
        this._applyFilters();
    }

    _applyFilters() {
        const f = this._getFilterValues();
        this.visibleBooks = this.originalBooks.filter(book => {
            if (f.category !== "0" && (book.category !== f.category)) return false;
            if (f.publisher !== "0" && (book.publisher !== f.publisher)) return false;
            if (f.year !== "0" && String(book.yearPublished) !== String(f.year)) return false;
            if (f.language !== "0" && (book.language !== f.language)) return false;

            if (f.search) {
                const hay = [book.title, book.author, book.publisher, book.description].filter(Boolean).join(' ').toLowerCase();
                if (!hay.includes(f.search)) return false;
            }
            return true;
        });

        // Update counts (keep all options but omit zero-count options)
        this._populateFiltersDynamic(this.visibleBooks);

        this._renderPage();
    }

    _pageSize() { return this.pageSize; }
    _totalPages() { return Math.max(1, Math.ceil(this.visibleBooks.length / this._pageSize())); }

    _renderPage() {
        const start = (this.page - 1) * this._pageSize();
        const pageItems = this.visibleBooks.slice(start, start + this._pageSize());
        this._renderCards(pageItems);
        this._renderPagination();
    }

    _renderCards(items) {
        const container = this._el('cards');
        if (!container) return;
        container.innerHTML = '';
        const countEl = this._el('count');
        if (countEl) countEl.textContent = `Books: ${this.visibleBooks.length}`;

        if (!items.length) {
            container.innerHTML = `<div class="col-12"><div class="alert alert-secondary">No books found.</div></div>`;
            return;
        }

        const preWeb = 'https://irrigation.sindh.gov.pk/';
        items.forEach(book => {
            const card = document.createElement('div');
            card.className = "col-lg-3 col-md-6 col-sm-12 mb-4";
            const imgUrl = preWeb + (book.getPictureURL || '/files/Books/default.jpg');
            const bookUrl = preWeb + (book.getBookURL || '#');
            const title = book.title || '';
            const pub = book.publisher || '';
            const yr = book.yearPublished || '';

            card.innerHTML = `
        <div class="card card-small card-post card-post--1 h-100">
          <div class="card-post__image" style="background-image: url('${imgUrl}'); min-height:440px; background-size:cover; background-position:center;">
            <a href="${bookUrl}" class="card-post__category badge badge-pill badge-dark">${yr}</a>
            <div class="card-post__author d-flex">
              <a href="${bookUrl}" target="_blank" class="card-post__author-avatar card-post__author-avatar--small" style="background-image: url('/files/download.png');">${this._escape(pub)}</a>
            </div>
          </div>
          <div class="card-body">
            <h5 class="card-title mb-1">
              <a class="text-fiord-blue textex" href="${bookUrl}" data-full="${this._escape(title)}">${this._escape(title)}</a>
            </h5>
            <span class="text-muted textex2">${this._escape(pub)}</span>
          </div>
        </div>
      `;
            container.appendChild(card);
        });

        if (window.innerWidth > 768) {
            this._applyExpanderToggle(40);
        } else {
            container.querySelectorAll('.textex, .textex2').forEach(el => el.style.cursor = '');
        }
    }

    _applyExpanderToggle(slicePoint) {
        const rootEl = this._el('root');
        if (!rootEl) return;
        rootEl.querySelectorAll('.textex, .textex2').forEach(orig => {
            const clone = orig.cloneNode(true);
            orig.parentNode.replaceChild(clone, orig);
        });

        rootEl.querySelectorAll('.textex, .textex2').forEach(el => {
            const full = el.dataset.full ?? el.textContent.trim();
            if (!full) return;
            const shortText = full.length > slicePoint ? full.slice(0, slicePoint) + '...' : full;
            el.textContent = shortText.length < full.length ? shortText : full;
            el.dataset.expanded = 'false';
            if (full.length > slicePoint) {
                el.style.cursor = 'pointer';
                el.addEventListener('click', () => {
                    const expanded = el.dataset.expanded === 'true';
                    if (expanded) {
                        el.textContent = shortText;
                        el.dataset.expanded = 'false';
                    } else {
                        el.textContent = full;
                        el.dataset.expanded = 'true';
                    }
                });
            } else {
                el.style.cursor = '';
            }
        });
    }

    _renderPagination() {
        const container = this._el('pagination');
        if (!container) return;
        container.innerHTML = '';
        const total = this._totalPages();
        if (total <= 1) return;

        const ul = document.createElement('ul');
        ul.className = 'pagination';

        const addItem = (label, page, disabled = false, active = false) => {
            const li = document.createElement('li');
            li.className = 'page-item' + (disabled ? ' disabled' : '') + (active ? ' active' : '');
            const a = document.createElement('a');
            a.className = 'page-link';
            a.href = '#';
            a.textContent = label;
            a.addEventListener('click', (e) => {
                e.preventDefault();
                if (disabled || this.page === page) return;
                this.page = page;
                this._renderPage();
            });
            li.appendChild(a);
            ul.appendChild(li);
        };

        addItem('«', Math.max(1, this.page - 1), this.page === 1);
        for (let p = 1; p <= total; p++) addItem(String(p), p, false, p === this.page);
        addItem('»', Math.min(total, this.page + 1), this.page === total);

        container.appendChild(ul);
    }

    _escape(s) { return String(s || '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;'); }
}
 
class ReportLibraryComponent {
    constructor(hostOrId, opts = {}) {
        this.host = typeof hostOrId === 'string' ? document.getElementById(hostOrId) : hostOrId;
        if (!this.host) throw new Error('Host element not found');

        this.apiUrl = opts.apiUrl || 'https://api.hicsindh.pk/public/ELib/Reports';
        this.pageSize = Number(opts.pageSize) || 12;
        this._uid = 'rlc_' + Math.random().toString(36).slice(2, 9);

        this.originalReports = [];
        this.visibleReports = [];
        this.page = 1;

        this._renderShell();
        this._wireStaticEvents();
    }

    _id(name) { return `${this._uid}__${name}`; }
    _el(name) { return document.getElementById(this._id(name)); }

    _renderShell() {
        const html = `
      <div class="container" data-aos="fade-up" id="${this._id('root')}">
        <div class="section-title">
          <h2>Reports</h2>
          <div class="row align-items-center justify-content-center mb-2">
            <div class="col-md-7">
              <div class="input-group">
                <input id="${this._id('search')}" class="form-control" type="search" placeholder="Search title, description, organization..." />
                <button id="${this._id('searchBtn')}" class="btn btn-primary" type="button">Search</button>
                <div class="input-group-text ms-2" id="${this._id('count')}">Reports: 0</div>
              </div>

              <div class="input-group mt-2">
                <div class="input-group-text">Filters</div>

                <select class="form-control custom-select" style="max-width:250px;" id="${this._id('category')}">
                  <option value="0">All Categories</option>
                </select>

                <select class="form-control custom-select" style="max-width:250px;" id="${this._id('organization')}">
                  <option value="0">All Organizations</option>
                </select>

                <select class="form-control custom-select" style="max-width:180px;" id="${this._id('year')}">
                  <option value="0">All Years</option>
                </select>

                <button class="btn btn-outline-secondary" type="button" id="${this._id('reset')}" title="Reset filters">
                  <i class="bx bx-reset"></i>
                </button>

                <input type="hidden" id="${this._id('sfid')}" value="reports">
              </div>
            </div>
          </div>
        </div>

        <div class="clearfix"></div>
        <div class="rows">
          <div class="row content mt-2" id="${this._id('cards')}"></div>
          <div class="row mt-3">
            <div class="col-12 d-flex justify-content-center align-items-center" id="${this._id('pagination')}"></div>
          </div>
        </div>
      </div>
    `;
        this.host.innerHTML = html;
    }

    _wireStaticEvents() {
        const searchInput = this._el('search');
        const searchBtn = this._el('searchBtn');
        const resetBtn = this._el('reset');
        const debounce = (fn, wait = 300) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), wait); }; };

        if (searchInput) {
            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') { e.preventDefault(); this._applyFiltersResetPage(); }
            });
            searchInput.addEventListener('input', debounce(() => this._applyFiltersResetPage(), 350));
        }
        if (searchBtn) searchBtn.addEventListener('click', () => this._applyFiltersResetPage());
        if (resetBtn) resetBtn.addEventListener('click', () => {
            ['category', 'organization', 'year'].forEach(id => { const el = this._el(id); if (el) el.value = "0"; });
            const s = this._el('search'); if (s) s.value = '';
            this.visibleReports = this.originalReports.slice();
            this.page = 1;
            this._populateFiltersDynamic(this.visibleReports);
            this._renderPage();
        });
    }

    async load() {
        const cardsEl = this._el('cards');
        if (cardsEl) cardsEl.innerHTML = `<div class="text-center py-4"><span class="spinner-border"></span> Loading reports…</div>`;

        if (typeof loadFlow !== 'function') {
            this._showError('cards', 'loadFlow is not available');
            return;
        }

        try {
            const data = await loadFlow(this.apiUrl);
            if (!Array.isArray(data)) throw new Error('Invalid data from loadFlow');
            this.originalReports = data;
            this.visibleReports = data.slice();
            this.page = 1;

            this._populateFiltersDynamic(this.visibleReports);
            this._wireFilterEvents();
            this._renderPage();
        } catch (err) {
            console.error(err);
            this._showError('cards', 'Failed to load reports');
        }
    }

    _showError(elName, message) {
        const el = this._el(elName);
        if (el) el.innerHTML = `<div class="alert alert-danger">${message}</div>`; else alert(message);
    }

    _getYear(value) {
        if (!value) return '';
        const d = new Date(value);
        if (!isNaN(d.getFullYear())) return String(d.getFullYear());
        const s = String(value); return s.length >= 4 ? s.slice(0, 4) : '';
    }

    _getCounts(items, key, transform) {
        const counts = Object.create(null);
        items.forEach(item => {
            let k = transform ? transform(item) : (item[key] ?? '');
            k = (k ?? '') + '';
            counts[k] = (counts[k] || 0) + 1;
        });
        return counts;
    }

    _uniqueKeysFromOriginal(key, transform) {
        const map = Object.create(null);
        this.originalReports.forEach(item => {
            let k = transform ? transform(item) : (item[key] ?? '');
            k = (k ?? '') + '';
            if (k === '') return;
            map[k] = true;
        });
        return Object.keys(map).sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }));
    }

    _populateFiltersDynamic(currentSet) {
        this._updateSelectDynamic('category', 'category', 'All Categories', currentSet);
        this._updateSelectDynamic('organization', 'orgnization', 'All Organizations', currentSet);
        this._updateSelectDynamic('year', 'publicationYear', 'All Years', currentSet, (item) => this._getYear(item.publicationYear));
    }

    _updateSelectDynamic(domName, dataKey, allLabel, currentSet, transform = null) {
        const select = this._el(domName);
        if (!select) return;
        const previous = select.value;

        const countsForCurrent = this._getCounts(currentSet, dataKey, transform);
        const allKeys = this._uniqueKeysFromOriginal(dataKey, transform);

        select.innerHTML = '';
        const allOpt = document.createElement('option');
        allOpt.value = "0";
        allOpt.textContent = `${allLabel}`;
        select.appendChild(allOpt);

        allKeys.forEach(k => {
            const cnt = countsForCurrent[k] || 0;
            if (cnt === 0) return;
            const opt = document.createElement('option');
            opt.value = k;
            opt.textContent = `${k} (${cnt})`;
            select.appendChild(opt);
        });

        if (previous && Array.from(select.options).some(o => o.value === previous)) select.value = previous;
        else select.value = "0";
    }

    _wireFilterEvents() {
        ['category', 'organization', 'year'].forEach(name => {
            const el = this._el(name);
            if (!el) return;
            el.addEventListener('change', () => this._applyFiltersResetPage());
        });
    }

    _getFilterValues() {
        return {
            category: this._el('category')?.value || "0",
            organization: this._el('organization')?.value || "0",
            year: this._el('year')?.value || "0",
            search: (this._el('search')?.value || '').trim().toLowerCase()
        };
    }

    _applyFiltersResetPage() {
        this.page = 1;
        this._applyFilters();
    }

    _applyFilters() {
        const f = this._getFilterValues();
        this.visibleReports = this.originalReports.filter(r => {
            if (f.category !== "0" && (r.category !== f.category)) return false;
            if (f.organization !== "0" && (r.orgnization !== f.organization)) return false;
            if (f.year !== "0") {
                const y = this._getYear(r.publicationYear);
                if (y !== f.year) return false;
            }
            if (f.search) {
                const hay = [r.title, r.description, r.orgnization].filter(Boolean).join(' ').toLowerCase();
                if (!hay.includes(f.search)) return false;
            }
            return true;
        });

        this._populateFiltersDynamic(this.visibleReports);
        this._renderPage();
    }

    _pageSize() { return this.pageSize; }
    _totalPages() { return Math.max(1, Math.ceil(this.visibleReports.length / this._pageSize())); }

    _renderPage() {
        const start = (this.page - 1) * this._pageSize();
        const pageItems = this.visibleReports.slice(start, start + this._pageSize());
        this._renderCards(pageItems);
        this._renderPagination();
    }

    _renderCards(items) {
        const container = this._el('cards');
        if (!container) return;
        container.innerHTML = '';
        const countEl = this._el('count');
        if (countEl) countEl.textContent = `Reports: ${this.visibleReports.length}`;

        if (!items.length) {
            container.innerHTML = `<div class="col-12"><div class="alert alert-secondary">No reports found.</div></div>`;
            return;
        }

        const preWeb = 'https://irrigation.sindh.gov.pk/';
        const sorted = items.slice().sort((a, b) => {
            const ay = parseInt(this._getYear(a.publicationYear) || '0', 10);
            const by = parseInt(this._getYear(b.publicationYear) || '0', 10);
            return by - ay;
        });

        sorted.forEach(rep => {
            const col = document.createElement('div');
            col.className = "col-lg-3 col-md-6 col-sm-12 mb-4";
            const imgUrl = preWeb + (rep.getPictureURL || '/files/Books/reports/default.jpg');
            const fileUrl = preWeb + (rep.getURL || '#');
            const title = rep.title || '';
            const org = rep.orgnization || '';
            const yr = this._getYear(rep.publicationYear) || '';

            col.innerHTML = `
        <div class="card card-small card-post card-post--1 h-100">
          <div class="card-post__image" style="background-image: url('${imgUrl}'); min-height:440px; background-size:cover; background-position:center;">
            <a href="${fileUrl}" class="card-post__category badge badge-pill badge-dark">${yr}</a>
            <div class="card-post__author d-flex">
              <a href="${fileUrl}" target="_blank" class="card-post__author-avatar card-post__author-avatar--small" style="background-image: url('/files/download.png');">${this._escape(org)}</a>
            </div>
          </div>
          <div class="card-body">
            <h5 class="card-title mb-1">
              <a class="text-fiord-blue textex" href="${fileUrl}" data-full="${this._escape(title)}">${this._escape(title)}</a>
            </h5>
            <span class="text-muted textex2">${this._escape(org)}</span>
          </div>
        </div>
      `;
            container.appendChild(col);
        });

        if (window.innerWidth > 768) this._applyExpanderToggle(40);
        else container.querySelectorAll('.textex, .textex2').forEach(el => el.style.cursor = '');
    }

    _applyExpanderToggle(slicePoint) {
        const rootEl = this._el('root');
        if (!rootEl) return;
        rootEl.querySelectorAll('.textex, .textex2').forEach(orig => {
            const clone = orig.cloneNode(true);
            orig.parentNode.replaceChild(clone, orig);
        });
        rootEl.querySelectorAll('.textex, .textex2').forEach(el => {
            const full = el.dataset.full ?? el.textContent.trim();
            if (!full) return;
            const shortText = full.length > slicePoint ? full.slice(0, slicePoint) + '...' : full;
            el.textContent = shortText.length < full.length ? shortText : full;
            el.dataset.expanded = 'false';
            if (full.length > slicePoint) {
                el.style.cursor = 'pointer';
                el.addEventListener('click', () => {
                    const expanded = el.dataset.expanded === 'true';
                    if (expanded) { el.textContent = shortText; el.dataset.expanded = 'false'; }
                    else { el.textContent = full; el.dataset.expanded = 'true'; }
                });
            } else el.style.cursor = '';
        });
    }

    _renderPagination() {
        const container = this._el('pagination');
        if (!container) return;
        container.innerHTML = '';
        const total = this._totalPages();
        if (total <= 1) return;

        const ul = document.createElement('ul'); ul.className = 'pagination';
        const addItem = (label, page, disabled = false, active = false) => {
            const li = document.createElement('li');
            li.className = 'page-item' + (disabled ? ' disabled' : '') + (active ? ' active' : '');
            const a = document.createElement('a'); a.className = 'page-link'; a.href = '#'; a.textContent = label;
            a.addEventListener('click', (e) => { e.preventDefault(); if (disabled || this.page === page) return; this.page = page; this._renderPage(); });
            li.appendChild(a); ul.appendChild(li);
        };

        addItem('«', Math.max(1, this.page - 1), this.page === 1);
        for (let p = 1; p <= total; p++) addItem(String(p), p, false, p === this.page);
        addItem('»', Math.min(total, this.page + 1), this.page === total);

        container.appendChild(ul);
    }

    _escape(s) { return String(s || '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;'); }
}
 
class StaticMapLibraryComponent {
    constructor(hostOrId, opts = {}) {
        this.host = typeof hostOrId === 'string' ? document.getElementById(hostOrId) : hostOrId;
        if (!this.host) throw new Error('Host element not found');

        this.apiUrl = opts.apiUrl || 'https://api.hicsindh.pk/public/ELib/StaticMaps';
        this.pageSize = Number(opts.pageSize) || 12;
        this._uid = 'smlc_' + Math.random().toString(36).slice(2, 9);

        this.originalItems = [];
        this.visibleItems = [];
        this.page = 1;

        this._renderShell();
        this._wireStaticEvents();
    }

    _id(name) { return `${this._uid}__${name}`; }
    _el(name) { return document.getElementById(this._id(name)); }

    _renderShell() {
        const html = `
      <div class="container" data-aos="fade-up" id="${this._id('root')}">
        <div class="section-title">
          <h2>Static Maps</h2>
          <div class="row align-items-center justify-content-center mb-2">
            <div class="col-md-8">
              <div class="input-group">
                <input id="${this._id('search')}" class="form-control" type="search" placeholder="Search title, keywords, category..." />
                <button id="${this._id('searchBtn')}" class="btn btn-primary" type="button">Search</button>
                <div class="input-group-text ms-2" id="${this._id('count')}">Maps: 0</div>
              </div>

              <div class="input-group mt-2">
                <div class="input-group-text">Filters</div>

                <select class="form-control custom-select" style="max-width:250px;" id="${this._id('category')}">
                  <option value="0">All Categories</option>
                </select>

                <select class="form-control custom-select" style="max-width:165px;" id="${this._id('region')}">
                  <option value="0">All Regions</option>
                </select>

                <select class="form-control custom-select" style="max-width:165px;" id="${this._id('circle')}">
                  <option value="0">All Circles</option>
                </select>

                <select class="form-control custom-select" style="max-width:165px;" id="${this._id('division')}">
                  <option value="0">All Divisions</option>
                </select>

                <button class="btn btn-outline-secondary" type="button" id="${this._id('reset')}" title="Reset filters">
                  <i class="bx bx-reset"></i>
                </button>

                <input type="hidden" id="${this._id('sfid')}" value="staticmaps">
              </div>
            </div>
          </div>
        </div>

        <div class="clearfix"></div>
        <div class="rows">
          <div class="row content mt-2" id="${this._id('cards')}"></div>
          <div class="row mt-3">
            <div class="col-12 d-flex justify-content-center align-items-center" id="${this._id('pagination')}"></div>
          </div>
        </div>
      </div>
    `;
        this.host.innerHTML = html;
    }

    _wireStaticEvents() {
        const searchInput = this._el('search');
        const searchBtn = this._el('searchBtn');
        const resetBtn = this._el('reset');
        const debounce = (fn, wait = 300) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), wait); }; };

        if (searchInput) {
            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') { e.preventDefault(); this._applyFiltersResetPage(); }
            });
            searchInput.addEventListener('input', debounce(() => this._applyFiltersResetPage(), 350));
        }
        if (searchBtn) searchBtn.addEventListener('click', () => this._applyFiltersResetPage());
        if (resetBtn) resetBtn.addEventListener('click', () => {
            ['category', 'region', 'circle', 'division'].forEach(id => {
                const el = this._el(id); if (el) el.value = "0";
            });
            const s = this._el('search'); if (s) s.value = '';
            this.visibleItems = this.originalItems.slice();
            this.page = 1;
            this._populateFiltersDynamic(this.visibleItems);
            this._renderPage();
        });
    }

    async load() {
        const cardsEl = this._el('cards');
        if (cardsEl) cardsEl.innerHTML = `<div class="text-center py-4"><span class="spinner-border"></span> Loading maps…</div>`;

        if (typeof loadFlow !== 'function') {
            this._showError('cards', 'loadFlow is not available');
            return;
        }

        try {
            const data = await loadFlow(this.apiUrl);
            if (!Array.isArray(data)) throw new Error('Invalid data from loadFlow');
            this.originalItems = data;
            this.visibleItems = data.slice();
            this.page = 1;

            this._populateFiltersDynamic(this.visibleItems);
            this._wireFilterEvents();
            this._renderPage();
        } catch (err) {
            console.error(err);
            this._showError('cards', 'Failed to load maps');
        }
    }

    _showError(elName, message) {
        const el = this._el(elName);
        if (el) el.innerHTML = `<div class="alert alert-danger">${message}</div>`; else alert(message);
    }

    // counts from arbitrary set
    _getCounts(items, key, transform) {
        const counts = Object.create(null);
        items.forEach(item => {
            let k = transform ? transform(item) : (item[key] ?? '');
            k = (k ?? '') + '';
            counts[k] = (counts[k] || 0) + 1;
        });
        return counts;
    }

    // unique keys from original dataset (options derived from full set)
    _uniqueKeysFromOriginal(key, transform) {
        const map = Object.create(null);
        this.originalItems.forEach(item => {
            let k = transform ? transform(item) : (item[key] ?? '');
            k = (k ?? '') + '';
            if (k === '') return;
            map[k] = true;
        });
        return Object.keys(map).sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }));
    }

    // populate selects: options come from ORIGINAL, counts come from currentSet, hide zero-count options, first option has no count
    _populateFiltersDynamic(currentSet) {
        this._updateSelectDynamic('category', 'category', 'All Categories', currentSet);
        this._updateSelectDynamic('region', 'region', 'All Regions', currentSet);
        this._updateSelectDynamic('circle', 'circle', 'All Circles', currentSet);
        this._updateSelectDynamic('division', 'division', 'All Divisions', currentSet);
    }

    _updateSelectDynamic(domName, dataKey, allLabel, currentSet, transform = null) {
        const select = this._el(domName);
        if (!select) return;
        const previous = select.value;

        const countsForCurrent = this._getCounts(currentSet, dataKey, transform);
        const allKeys = this._uniqueKeysFromOriginal(dataKey, transform);

        select.innerHTML = '';
        const allOpt = document.createElement('option');
        allOpt.value = "0";
        allOpt.textContent = `${allLabel}`;
        select.appendChild(allOpt);

        allKeys.forEach(k => {
            const cnt = countsForCurrent[k] || 0;
            if (cnt === 0) return; // hide zero-count
            const opt = document.createElement('option');
            opt.value = k;
            opt.textContent = `${k} (${cnt})`;
            select.appendChild(opt);
        });

        if (previous && Array.from(select.options).some(o => o.value === previous)) select.value = previous;
        else select.value = "0";
    }

    _wireFilterEvents() {
        ['category', 'region', 'circle', 'division'].forEach(name => {
            const el = this._el(name);
            if (!el) return;
            el.addEventListener('change', () => this._applyFiltersResetPage());
        });
    }

    _getFilterValues() {
        return {
            category: this._el('category')?.value || "0",
            region: this._el('region')?.value || "0",
            circle: this._el('circle')?.value || "0",
            division: this._el('division')?.value || "0",
            search: (this._el('search')?.value || '').trim().toLowerCase()
        };
    }

    _applyFiltersResetPage() {
        this.page = 1;
        this._applyFilters();
    }

    _applyFilters() {
        const f = this._getFilterValues();
        this.visibleItems = this.originalItems.filter(item => {
            if (f.category !== "0" && (item.category !== f.category)) return false;
            if (f.region !== "0" && (item.region !== f.region)) return false;
            if (f.circle !== "0" && (item.circle !== f.circle)) return false;
            if (f.division !== "0" && (item.division !== f.division)) return false;

            if (f.search) {
                const hay = [item.title, item.keywords, item.category].filter(Boolean).join(' ').toLowerCase();
                if (!hay.includes(f.search)) return false;
            }
            return true;
        });

        // Update counts based on current visible set (options still from original)
        this._populateFiltersDynamic(this.visibleItems);

        this._renderPage();
    }

    _pageSize() { return this.pageSize; }
    _totalPages() { return Math.max(1, Math.ceil(this.visibleItems.length / this._pageSize())); }

    _renderPage() {
        const start = (this.page - 1) * this._pageSize();
        const pageItems = this.visibleItems.slice(start, start + this._pageSize());
        this._renderCards(pageItems);
        this._renderPagination();
    }

    _renderCards(items) {
        const container = this._el('cards');
        if (!container) return;
        container.innerHTML = '';
        const countEl = this._el('count');
        if (countEl) countEl.textContent = `Maps: ${this.visibleItems.length}`;

        if (!items.length) {
            container.innerHTML = `<div class="col-12"><div class="alert alert-secondary">No maps found.</div></div>`;
            return;
        }

        const preWeb = 'https://irrigation.sindh.gov.pk/';
        items.forEach(it => {
            const col = document.createElement('div');
            col.className = "col-lg-3 col-md-6 col-sm-12 mb-4";
            const picture = it.getPictureURL || '';
            const url = (it.getURL && it.getURL !== '#') ? it.getURL : it.getPictureURL;
            const imgUrl = preWeb + (picture || '/files/Books/maps/default.jpg');
            const fileUrl = preWeb + (url || '#');
            const title = it.title || '';
            const cat = it.category || '';

            col.innerHTML = `
        <div class="card card-small card-post card-post--1 h-100">
          <div class="card-post__image" style="background-image: url('${imgUrl}'); min-height:340px; background-size:cover; background-position:center;">
            <div class="card-post__author d-flex">
              <a href="${fileUrl}" target="_blank" class="card-post__author-avatar card-post__author-avatar--small" style="background-image: url('/files/download.png');">${this._escape(cat)}</a>
            </div>
          </div>
          <div class="card-body">
            <h5 class="card-title mb-1">
              <a class="text-fiord-blue textex" href="${fileUrl}" data-full="${this._escape(title)}">${this._escape(title)}</a>
            </h5>
            <span class="text-muted textex2">${this._escape(cat)}</span>
          </div>
        </div>
      `;
            container.appendChild(col);
        });

        if (window.innerWidth > 768) this._applyExpanderToggle(40);
        else container.querySelectorAll('.textex, .textex2').forEach(el => el.style.cursor = '');
    }

    _applyExpanderToggle(slicePoint) {
        const rootEl = this._el('root');
        if (!rootEl) return;
        rootEl.querySelectorAll('.textex, .textex2').forEach(orig => {
            const clone = orig.cloneNode(true);
            orig.parentNode.replaceChild(clone, orig);
        });
        rootEl.querySelectorAll('.textex, .textex2').forEach(el => {
            const full = el.dataset.full ?? el.textContent.trim();
            if (!full) return;
            const shortText = full.length > slicePoint ? full.slice(0, slicePoint) + '...' : full;
            el.textContent = shortText.length < full.length ? shortText : full;
            el.dataset.expanded = 'false';
            if (full.length > slicePoint) {
                el.style.cursor = 'pointer';
                el.addEventListener('click', () => {
                    const expanded = el.dataset.expanded === 'true';
                    if (expanded) { el.textContent = shortText; el.dataset.expanded = 'false'; }
                    else { el.textContent = full; el.dataset.expanded = 'true'; }
                });
            } else el.style.cursor = '';
        });
    }

    _renderPagination() {
        const container = this._el('pagination');
        if (!container) return;
        container.innerHTML = '';
        const total = this._totalPages();
        if (total <= 1) return;

        const ul = document.createElement('ul'); ul.className = 'pagination';
        const addItem = (label, page, disabled = false, active = false) => {
            const li = document.createElement('li');
            li.className = 'page-item' + (disabled ? ' disabled' : '') + (active ? ' active' : '');
            const a = document.createElement('a'); a.className = 'page-link'; a.href = '#'; a.textContent = label;
            a.addEventListener('click', (e) => { e.preventDefault(); if (disabled || this.page === page) return; this.page = page; this._renderPage(); });
            li.appendChild(a); ul.appendChild(li);
        };

        addItem('«', Math.max(1, this.page - 1), this.page === 1);
        for (let p = 1; p <= total; p++) addItem(String(p), p, false, p === this.page);
        addItem('»', Math.min(total, this.page + 1), this.page === total);

        container.appendChild(ul);
    }

    _escape(s) { return String(s || '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;'); }
}

class ResearchPublicationsComponent {
    constructor(hostOrId, opts = {}) {
        this.host = typeof hostOrId === 'string' ? document.getElementById(hostOrId) : hostOrId;
        if (!this.host) throw new Error('Host element not found');

        this.apiUrl = opts.apiUrl || 'https://api.hicsindh.pk/public/ELib/ResearchPublications';
        this.pageSize = Number(opts.pageSize) || 25;
        this._uid = 'rpc_' + Math.random().toString(36).slice(2, 9);

        this.originalItems = [];
        this.visibleItems = [];
        this.page = 1;

        this._renderShell();
        this._wireStaticEvents();
    }

    _id(name) { return `${this._uid}__${name}`; }
    _el(name) { return document.getElementById(this._id(name)); }

    _renderShell() {
        const html = `
      <div class="container" data-aos="fade-up" id="${this._id('root')}">
        <div class="section-title">
          <h2>Research / Publications</h2>
        </div>

        <div class="row mb-2">
          <div class="col-md-8">
            <div class="input-group">
              <input id="${this._id('search')}" class="form-control" type="search" placeholder="Search title, author, abstract..." />
              <button id="${this._id('searchBtn')}" class="btn btn-primary" type="button">Search</button>
              <div class="input-group-text ms-2" id="${this._id('count')}">Publications: 0</div>
            </div>
          </div>
          <div class="col-md-4 text-end">
            <label for="${this._id('pageSize')}" class="form-label me-2">Rows</label>
            <select id="${this._id('pageSize')}" class="form-select" style="width:100px; display:inline-block;">
              <option value="10">10</option><option value="25" selected>25</option><option value="50">50</option><option value="100">100</option>
            </select>
          </div>
        </div>

        <div class="table-responsive card-body p-0 pb-3">
          <table class="table table-striped table-bordered" id="${this._id('table')}" style="max-width:100%;">
            <thead class="bg-light">
              <tr>
                <th width="40%">Title</th>
                <th width="20%">Author</th>
                <th>Year</th>
                <th>Pages</th>
                <th>Abstract</th>
                <th></th>
              </tr>
            </thead>
            <tbody id="${this._id('tbody')}"></tbody>
          </table>
        </div>

        <div class="row mt-2">
          <div class="col-12 d-flex justify-content-center" id="${this._id('pagination')}"></div>
        </div>
      </div>
    `;
        this.host.innerHTML = html;
    }

    _wireStaticEvents() {
        const searchInput = this._el('search');
        const searchBtn = this._el('searchBtn');
        const pageSizeEl = this._el('pageSize');
        const debounce = (fn, wait = 300) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), wait); }; };

        if (searchInput) {
            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') { e.preventDefault(); this._applyFiltersResetPage(); }
            });
            searchInput.addEventListener('input', debounce(() => this._applyFiltersResetPage(), 350));
        }
        if (searchBtn) searchBtn.addEventListener('click', () => this._applyFiltersResetPage());
        if (pageSizeEl) pageSizeEl.addEventListener('change', (e) => {
            this.pageSize = Number(e.target.value) || 25;
            this.page = 1;
            this._renderPage();
        });
    }

    async load() {
        const tbody = this._el('tbody');
        if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="text-center py-3"><span class="spinner-border"></span> Loading...</td></tr>`;

        if (typeof loadFlow !== 'function') {
            this._showError('tbody', 'loadFlow is not available');
            return;
        }

        try {
            const data = await loadFlow(this.apiUrl);
            if (!Array.isArray(data)) throw new Error('Invalid data from loadFlow');
            this.originalItems = data;
            this.visibleItems = data.slice();
            this.page = 1;
            this._applyDefaultSort();
            this._renderPage();
        } catch (err) {
            console.error(err);
            this._showError('tbody', 'Failed to load publications');
        }
    }

    _showError(elName, message) {
        const el = this._el(elName);
        if (el) el.innerHTML = `<tr><td colspan="6" class="alert alert-danger">${message}</td></tr>`;
        else alert(message);
    }

    _applyDefaultSort() {
        this.originalItems.sort((a, b) => {
            const ay = this._yearFrom(a.publicationYear);
            const by = this._yearFrom(b.publicationYear);
            return by - ay;
        });
        this.visibleItems = this.originalItems.slice();
    }

    _yearFrom(val) {
        if (!val) return 0;
        const d = new Date(val);
        if (!isNaN(d.getFullYear())) return d.getFullYear();
        const s = String(val);
        return Number(s.slice(0, 4)) || 0;
    }

    _getFilterValues() {
        return {
            search: (this._el('search')?.value || '').trim().toLowerCase()
        };
    }

    _applyFiltersResetPage() {
        this.page = 1;
        this._applyFilters();
    }

    _applyFilters() {
        const f = this._getFilterValues();
        this.visibleItems = this.originalItems.filter(item => {
            if (f.search) {
                const hay = [item.title, item.author, item.abstract].filter(Boolean).join(' ').toLowerCase();
                return hay.includes(f.search);
            }
            return true;
        });
        this._renderPage();
    }

    _pageSize() { return this.pageSize; }
    _totalPages() { return Math.max(1, Math.ceil(this.visibleItems.length / this._pageSize())); }

    _renderPage() {
        const start = (this.page - 1) * this._pageSize();
        const pageItems = this.visibleItems.slice(start, start + this._pageSize());
        this._renderTableRows(pageItems);
        this._renderPagination();
    }

    _renderTableRows(items) {
        const tbody = this._el('tbody');
        if (!tbody) return;
        tbody.innerHTML = '';
        const countEl = this._el('count');
        if (countEl) countEl.textContent = `Publications: ${this.visibleItems.length}`;

        if (!items.length) {
            tbody.innerHTML = `<tr><td colspan="6" class="text-center">No publications found.</td></tr>`;
            return;
        }

        const preWeb = 'https://irrigation.sindh.gov.pk/';
        items.forEach(item => {
            const year = this._yearFrom(item.publicationYear) || '';
            const pages = item.pages || '';
            const title = this._escape(item.title || '');
            const author = this._escape(item.author || '');
            const abstract = this._escape(item.abstract || '');
            const download = preWeb + (item.getURL || '');
            const external = item.link || '';

            const tr = document.createElement('tr');
            tr.innerHTML = `
        <td>${title}</td>
        <td>${author}</td>
        <td>${year}</td>
        <td>${pages}</td>
        <td><span class="textex" data-full="${abstract}">${abstract}</span></td>
        <td>
          ${item.getURL ? `<a href="${download}" target="_blank" title="Download"><span class="bi-cloud-download"></span></a>` : ''}
          ${external ? ` <a href="${external}" target="_blank" title="External link"><span class="bi-link"></span></a>` : ''}
        </td>
      `;
            tbody.appendChild(tr);
        });

        if (window.innerWidth > 768) this._applyExpanderToggle(80);
        else this._removeExpanderCursor();
    }

    _applyExpanderToggle(slicePoint) {
        const rootEl = this._el('root');
        if (!rootEl) return;

        // remove handlers by cloning
        rootEl.querySelectorAll('.textex').forEach(orig => {
            const clone = orig.cloneNode(true);
            orig.parentNode.replaceChild(clone, orig);
        });

        rootEl.querySelectorAll('.textex').forEach(el => {
            const full = el.dataset.full ?? el.textContent.trim();
            if (!full) return;
            const shortText = full.length > slicePoint ? full.slice(0, slicePoint) + '...' : full;
            el.textContent = shortText.length < full.length ? shortText : full;
            el.dataset.expanded = 'false';
            if (full.length > slicePoint) {
                el.style.cursor = 'pointer';
                el.addEventListener('click', () => {
                    const expanded = el.dataset.expanded === 'true';
                    if (expanded) { el.textContent = shortText; el.dataset.expanded = 'false'; }
                    else { el.textContent = full; el.dataset.expanded = 'true'; }
                });
            } else el.style.cursor = '';
        });
    }

    _removeExpanderCursor() {
        const rootEl = this._el('root');
        if (!rootEl) return;
        rootEl.querySelectorAll('.textex').forEach(el => el.style.cursor = '');
    }

    _renderPagination() {
        const container = this._el('pagination');
        if (!container) return;
        container.innerHTML = '';
        const total = this._totalPages();
        if (total <= 1) return;

        const ul = document.createElement('ul');
        ul.className = 'pagination';

        const addItem = (label, page, disabled = false, active = false) => {
            const li = document.createElement('li');
            li.className = 'page-item' + (disabled ? ' disabled' : '') + (active ? ' active' : '');
            const a = document.createElement('a');
            a.className = 'page-link';
            a.href = '#';
            a.textContent = label;
            a.addEventListener('click', (e) => {
                e.preventDefault();
                if (disabled || this.page === page) return;
                this.page = page;
                this._renderPage();
            });
            li.appendChild(a);
            ul.appendChild(li);
        };

        addItem('«', Math.max(1, this.page - 1), this.page === 1);
        const totalPages = this._totalPages();
        // show up to 7 pages centred
        const range = this._pageRange(this.page, totalPages, 7);
        range.forEach(p => addItem(String(p), p, false, p === this.page));
        addItem('»', Math.min(totalPages, this.page + 1), this.page === totalPages);

        container.appendChild(ul);
    }

    _pageRange(current, total, maxLength) {
        const half = Math.floor(maxLength / 2);
        let start = Math.max(1, current - half);
        let end = Math.min(total, current + half);
        if (end - start + 1 < maxLength) {
            start = Math.max(1, end - maxLength + 1);
            end = Math.min(total, start + maxLength - 1);
        }
        const r = [];
        for (let i = start; i <= end; i++) r.push(i);
        return r;
    }

    _escape(s) { return String(s || '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;'); }
}
 

class PressReleaseComponent {
    constructor(hostOrId, opts = {}) {
        this.host = typeof hostOrId === 'string' ? document.getElementById(hostOrId) : hostOrId;
        if (!this.host) throw new Error('Host element not found');

        this.apiUrl = opts.apiUrl || 'https://api.hicsindh.pk/public/ELib/PressRelease';
        this.pageSize = Number(opts.pageSize) || 25;
        this._uid = 'prc_' + Math.random().toString(36).slice(2, 9);

        this.originalItems = [];
        this.visibleItems = [];
        this.page = 1;

        this._renderShell();
        this._wireStaticEvents();
    }

    _id(name) { return `${this._uid}__${name}`; }
    _el(name) { return document.getElementById(this._id(name)); }

    _renderShell() {
        const html = `
      <div class="container" data-aos="fade-up" id="${this._id('root')}">
        <div class="section-title">
          <h2>Press Release / News Articles</h2>
        </div>

        <div class="row mb-2">
          <div class="col-md-8">
            <div class="input-group">
              <input id="${this._id('search')}" class="form-control" type="search" placeholder="Search title or language..." />
              <button id="${this._id('searchBtn')}" class="btn btn-primary" type="button">Search</button>
              <div class="input-group-text ms-2" id="${this._id('count')}">Items: 0</div>
            </div>
          </div>
          <div class="col-md-4 text-end">
            <label for="${this._id('pageSize')}" class="form-label me-2">Rows</label>
            <select id="${this._id('pageSize')}" class="form-select" style="width:100px; display:inline-block;">
              <option value="10">10</option><option value="25" selected>25</option><option value="50">50</option>
            </select>
          </div>
        </div>

        <div class="table-responsive card-body p-0 pb-3">
          <table class="table table-striped table-bordered" id="${this._id('table')}" style="max-width:100%;">
            <thead class="bg-light">
              <tr>
                <th width="60%">Title</th>
                <th width="20%">Language</th>
                <th></th>
              </tr>
            </thead>
            <tbody id="${this._id('tbody')}"></tbody>
          </table>
        </div>

        <div class="row mt-2">
          <div class="col-12 d-flex justify-content-center" id="${this._id('pagination')}"></div>
        </div>
      </div>
    `;
        this.host.innerHTML = html;
    }

    _wireStaticEvents() {
        const searchInput = this._el('search');
        const searchBtn = this._el('searchBtn');
        const pageSizeEl = this._el('pageSize');
        const debounce = (fn, wait = 300) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), wait); }; };

        if (searchInput) {
            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') { e.preventDefault(); this._applyFiltersResetPage(); }
            });
            searchInput.addEventListener('input', debounce(() => this._applyFiltersResetPage(), 300));
        }
        if (searchBtn) searchBtn.addEventListener('click', () => this._applyFiltersResetPage());
        if (pageSizeEl) pageSizeEl.addEventListener('change', (e) => {
            this.pageSize = Number(e.target.value) || 25;
            this.page = 1;
            this._renderPage();
        });
    }

    async load() {
        const tbody = this._el('tbody');
        if (tbody) tbody.innerHTML = `<tr><td colspan="3" class="text-center py-3"><span class="spinner-border"></span> Loading...</td></tr>`;

        if (typeof loadFlow !== 'function') {
            this._showError('tbody', 'loadFlow is not available');
            return;
        }

        try {
            const data = await loadFlow(this.apiUrl);
            if (!Array.isArray(data)) throw new Error('Invalid data from loadFlow');
            this.originalItems = data;
            this._applyDefaultSort();
            this.visibleItems = this.originalItems.slice();
            this.page = 1;
            this._renderPage();
        } catch (err) {
            console.error(err);
            this._showError('tbody', 'Failed to load items');
        }
    }

    _showError(elName, message) {
        const el = this._el(elName);
        if (el) el.innerHTML = `<tr><td colspan="3" class="alert alert-danger">${message}</td></tr>`;
        else alert(message);
    }

    _applyDefaultSort() {
        this.originalItems.sort((a, b) => {
            const ay = this._yearFrom(a.publicationYear);
            const by = this._yearFrom(b.publicationYear);
            return by - ay;
        });
    }

    _yearFrom(val) {
        if (!val) return 0;
        const d = new Date(val);
        if (!isNaN(d.getFullYear())) return d.getFullYear();
        const s = String(val);
        return Number(s.slice(0, 4)) || 0;
    }

    _getFilterValues() {
        return {
            search: (this._el('search')?.value || '').trim().toLowerCase()
        };
    }

    _applyFiltersResetPage() {
        this.page = 1;
        this._applyFilters();
    }

    _applyFilters() {
        const f = this._getFilterValues();
        this.visibleItems = this.originalItems.filter(item => {
            if (f.search) {
                const hay = [item.title, item.language].filter(Boolean).join(' ').toLowerCase();
                return hay.includes(f.search);
            }
            return true;
        });
        this._renderPage();
    }

    _pageSize() { return this.pageSize; }
    _totalPages() { return Math.max(1, Math.ceil(this.visibleItems.length / this._pageSize())); }

    _renderPage() {
        const start = (this.page - 1) * this._pageSize();
        const pageItems = this.visibleItems.slice(start, start + this._pageSize());
        this._renderTableRows(pageItems);
        this._renderPagination();
    }

    _renderTableRows(items) {
        const tbody = this._el('tbody');
        if (!tbody) return;
        tbody.innerHTML = '';
        const countEl = this._el('count');
        if (countEl) countEl.textContent = `Items: ${this.visibleItems.length}`;

        if (!items.length) {
            tbody.innerHTML = `<tr><td colspan="3" class="text-center">No items found.</td></tr>`;
            return;
        }

        items.forEach(item => {
            const title = this._escape(item.title || '');
            const language = this._escape(item.language || '');
            const downloadUrl = item.getURL ? item.getURL : '';

            const tr = document.createElement('tr');
            tr.innerHTML = `
        <td>${title}</td>
        <td>${language}</td>
        <td>
          ${downloadUrl ? `<a href="${downloadUrl}" target="_blank" title="Download"><span class="bi-cloud-download"></span></a>` : ''}
        </td>
      `;
            tbody.appendChild(tr);
        });

        if (window.innerWidth > 768) this._applyExpanderToggle(80);
        else this._removeExpanderCursor();
    }

    _applyExpanderToggle(slicePoint) {
        const rootEl = this._el('root');
        if (!rootEl) return;
        rootEl.querySelectorAll('.textex').forEach(orig => {
            const clone = orig.cloneNode(true);
            orig.parentNode.replaceChild(clone, orig);
        });

        rootEl.querySelectorAll('.textex').forEach(el => {
            const full = el.dataset.full ?? el.textContent.trim();
            if (!full) return;
            const shortText = full.length > slicePoint ? full.slice(0, slicePoint) + '...' : full;
            el.textContent = shortText.length < full.length ? shortText : full;
            el.dataset.expanded = 'false';
            if (full.length > slicePoint) {
                el.style.cursor = 'pointer';
                el.addEventListener('click', () => {
                    const expanded = el.dataset.expanded === 'true';
                    if (expanded) { el.textContent = shortText; el.dataset.expanded = 'false'; }
                    else { el.textContent = full; el.dataset.expanded = 'true'; }
                });
            } else el.style.cursor = '';
        });
    }

    _removeExpanderCursor() {
        const rootEl = this._el('root');
        if (!rootEl) return;
        rootEl.querySelectorAll('.textex').forEach(el => el.style.cursor = '');
    }

    _renderPagination() {
        const container = this._el('pagination');
        if (!container) return;
        container.innerHTML = '';
        const total = this._totalPages();
        if (total <= 1) return;

        const ul = document.createElement('ul');
        ul.className = 'pagination';

        const addItem = (label, page, disabled = false, active = false) => {
            const li = document.createElement('li');
            li.className = 'page-item' + (disabled ? ' disabled' : '') + (active ? ' active' : '');
            const a = document.createElement('a');
            a.className = 'page-link';
            a.href = '#';
            a.textContent = label;
            a.addEventListener('click', (e) => {
                e.preventDefault();
                if (disabled || this.page === page) return;
                this.page = page;
                this._renderPage();
            });
            li.appendChild(a);
            ul.appendChild(li);
        };

        addItem('«', Math.max(1, this.page - 1), this.page === 1);
        const totalPages = this._totalPages();
        const range = this._pageRange(this.page, totalPages, 7);
        range.forEach(p => addItem(String(p), p, false, p === this.page));
        addItem('»', Math.min(totalPages, this.page + 1), this.page === totalPages);

        container.appendChild(ul);
    }

    _pageRange(current, total, maxLength) {
        const half = Math.floor(maxLength / 2);
        let start = Math.max(1, current - half);
        let end = Math.min(total, current + half);
        if (end - start + 1 < maxLength) {
            start = Math.max(1, end - maxLength + 1);
            end = Math.min(total, start + maxLength - 1);
        }
        const r = [];
        for (let i = start; i <= end; i++) r.push(i);
        return r;
    }

    _escape(s) { return String(s || '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;'); }
}