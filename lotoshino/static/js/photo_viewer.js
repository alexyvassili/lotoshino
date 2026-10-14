/**
 * Standalone photo viewer. No dependencies and no automatic initialization.
 * Styles and icons are included in this module; existing pages are not changed.
 *
 * Future integration (replace the old viewer, do not initialize both):
 *   import PhotoViewer from '/static/js/photo_viewer.js';
 *   const viewer = new PhotoViewer('#lightgallery', {
 *     triggerSelector: '.news-main-img', // optional extra image opening the album
 *   });
 *   viewer.open(0);
 *   viewer.destroy(); // removes listeners, dialog, styles and added attributes
 *
 * Reads .gallery-item links with href/data-src, child img and optional
 * data-caption or data-sub-html (converted to plain text, never executed).
 * Optional data-download-url points to a larger original; it is not preloaded.
 * Downloads work directly for same-origin images, as in this site's albums.
 * Cross-origin download behavior depends on the remote server/browser.
 */

const ICONS = {
    previous: '<path d="m14 6-6 6 6 6M8 12h13"/>',
    next: '<path d="m10 6 6 6-6 6M3 12h13"/>',
    zoom: '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6M10 7v6M7 10h6"/>',
    unzoom: '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6M7 10h6"/>',
    download: '<path d="M12 3v12m-4-4 4 4 4-4M5 18v3h14v-3"/>',
    close: '<path d="m6 6 12 12M18 6 6 18"/>',
};

let activeViewer = null;

const CSS = `
.lpv, .lpv * { box-sizing: border-box; }
.lpv {
    position: fixed; inset: 0; width: 100vw; max-width: none;
    height: 100vh; height: 100dvh; max-height: none; margin: 0; padding: 0;
    border: 0; color: #f4f1eb; background: #090a0c; overflow: hidden;
    font: 15px/1.4 system-ui, sans-serif; text-align: left;
    overscroll-behavior: contain; color-scheme: dark; touch-action: pan-x pan-y;
}
.lpv[open] { display: flex; flex-direction: column; }
.lpv::backdrop { background: #090a0c; }
.lpv.lpv-overlay {
    width: calc(100vw - 48px); max-width: 1200px;
    height: calc(100vh - 48px); height: calc(100dvh - 48px); max-height: 900px;
    margin: auto; border-radius: 12px; box-shadow: 0 20px 80px #0008;
}
.lpv.lpv-overlay::backdrop { background: rgb(0 0 0 / 75%); }
.lpv button, .lpv a { margin: 0; font: inherit; -webkit-tap-highlight-color: transparent; }
.lpv-button {
    display: inline-flex; align-items: center; justify-content: center;
    flex: 0 0 44px; width: 44px; height: 44px; padding: 10px;
    border: 1px solid transparent; border-radius: 12px; background: transparent;
    color: #d2d2d5; cursor: pointer; text-decoration: none;
    transition: background .15s, color .15s;
}
.lpv-button:hover { background: #ffffff17; color: #fff; }
.lpv-button:disabled { opacity: .25; cursor: default; }
.lpv button:focus-visible, .lpv a:focus-visible {
    outline: 2px solid #edc284; outline-offset: -3px;
}
.lpv-button svg { width: 24px; height: 24px; fill: none; stroke: currentColor;
    stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.lpv-toolbar {
    display: flex; align-items: center; justify-content: flex-end; gap: 4px; flex: 0 0 auto;
    padding: max(8px, env(safe-area-inset-top)) max(14px, env(safe-area-inset-right)) 8px max(22px, env(safe-area-inset-left));
    background: #101114; z-index: 2;
}
.lpv-counter { margin-right: auto; font-variant-numeric: tabular-nums; color: #c5c5ca; }
.lpv-stage { position: relative; flex: 1 1 auto; min-height: 0; overflow: hidden; touch-action: none; }
.lpv-canvas { position: absolute; inset: 8px 64px; display: grid; place-items: center;
    overflow: hidden; touch-action: none; user-select: none; }
.lpv-image { display: block; max-width: none; max-height: none; border: 0;
    margin: 0; padding: 0; object-fit: contain; transform-origin: center;
    user-select: none; -webkit-user-drag: none; }
.lpv-canvas[data-zoomed="true"] { cursor: grab; }
.lpv-canvas[data-dragging="true"] { cursor: grabbing; }
.lpv-nav { position: absolute; top: 50%; transform: translateY(-50%);
    background: #151619c9; z-index: 1; }
.lpv-prev { left: max(10px, env(safe-area-inset-left)); }
.lpv-next { right: max(10px, env(safe-area-inset-right)); }
.lpv-status { position: absolute; inset: 0; display: grid; place-items: center;
    margin: 24px; color: #b6b6bf; text-align: center; pointer-events: none; }
.lpv-footer { flex: 0 0 auto; min-height: 0; background: #101114;
    padding-bottom: max(10px, env(safe-area-inset-bottom)); }
.lpv-caption { margin: 0; padding: 12px 24px 8px; text-align: center;
    font-size: 14px; font-weight: 500; line-height: 1.4; max-height: 5em; overflow-y: auto; }
.lpv-filmstrip { display: flex; align-items: center; gap: 4px; padding: 0 8px; }
.lpv-thumbs { display: flex; flex: 1; min-width: 0; gap: 8px; overflow-x: auto;
    padding: 8px 3px; overscroll-behavior-x: contain; touch-action: pan-x;
    scrollbar-width: thin; scrollbar-color: #595a60 transparent; }
.lpv-thumb { flex: 0 0 96px; width: 96px; height: 68px; padding: 3px;
    border: 2px solid transparent; border-radius: 8px; background: #25262a;
    cursor: pointer; opacity: .65; transition: opacity .15s, border-color .15s; }
.lpv-thumb:first-child { margin-left: auto; }
.lpv-thumb:last-child { margin-right: auto; }
.lpv-thumb:hover { opacity: 1; }
.lpv-thumb[aria-current="true"] { border-color: #edc284; opacity: 1; }
.lpv-thumb img { display: block; width: 100%; height: 100%; object-fit: cover;
    border-radius: 3px; pointer-events: none; }
.lpv [hidden] { display: none !important; }
@media (max-width: 600px) {
    .lpv.lpv-overlay { width: calc(100vw - 16px); height: calc(100dvh - 16px); }
    .lpv-toolbar { padding-left: 14px; padding-right: 8px; }
    .lpv-canvas { inset: 4px 0; }
    .lpv-nav { background: #0009; }
    .lpv-caption { padding: 8px 16px 4px; font-size: 13px; max-height: 4.8em; }
    .lpv-thumb { flex-basis: 76px; width: 76px; height: 56px; }
    .lpv-filmstrip { gap: 0; padding: 0 4px; }
    .lpv-filmstrip > .lpv-button { flex-basis: 32px; width: 32px; padding: 5px; }
}
@media (max-height: 480px) {
    .lpv-toolbar { padding-top: 0; padding-bottom: 0; }
    .lpv-caption { max-height: 2.3em; padding-top: 4px; padding-bottom: 0; }
    .lpv-thumb { height: 42px; flex-basis: 62px; }
    .lpv-footer { padding-bottom: 0; }
}
@media (prefers-reduced-motion: reduce) { .lpv * { transition: none !important; } }
`;

function imageURL(value) {
    if (typeof value !== 'string' || !value.trim()) return null;
    try {
        const url = new URL(value, document.baseURI);
        return ['http:', 'https:', 'blob:'].includes(url.protocol) ? url.href : null;
    } catch { return null; }
}

function icon(name) {
    return `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[name]}</svg>`;
}

export default class PhotoViewer {
    constructor(container, { itemSelector = '.gallery-item', triggerSelector = null, overlay = false, navigation = true } = {}) {
        this.container = typeof container === 'string' ? document.querySelector(container) : container;
        if (!this.container) throw new Error('PhotoViewer: gallery container not found');
        this.items = [...this.container.querySelectorAll(itemSelector)].map(link => {
            const img = link.querySelector('img');
            const src = imageURL(link.dataset.src || link.getAttribute('href'));
            const caption = link.dataset.caption ?? new DOMParser().parseFromString(
                link.dataset.subHtml || '', 'text/html'
            ).body.textContent;
            return { link, src, download: imageURL(link.dataset.downloadUrl) || src,
                localOnly: link.dataset.localImage === 'true',
                thumb: img ? imageURL(img.currentSrc || img.src) : null,
                alt: img?.alt || '', caption: caption.trim() };
        }).filter(item => item.src);
        this.abort = new AbortController();
        this.index = 0;
        this.loadID = 0;
        this.scale = 1;
        this.pan = { x: 0, y: 0 };
        this.pointers = new Map();
        this.extraAttributes = [];
        this.reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
        this.overlay = overlay;
        this.navigation = navigation;
        this.build();
        this.listen(this.container, 'click', event => {
            if (event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            const index = this.items.findIndex(item => item.link.contains(event.target));
            if (index < 0) return;
            event.preventDefault();
            this.open(index, this.items[index].link);
        });
        if (triggerSelector) {
            document.querySelectorAll(triggerSelector).forEach(trigger => this.bindTrigger(trigger));
        }
    }

    listen(target, type, listener, options = {}) {
        target.addEventListener(type, listener, { ...options, signal: this.abort.signal });
    }

    button(label, symbol, className = '') {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `lpv-button ${className}`;
        button.title = label;
        button.setAttribute('aria-label', label);
        button.innerHTML = icon(symbol);
        return button;
    }

    build() {
        this.style = document.createElement('style');
        this.style.textContent = CSS;
        document.head.append(this.style);
        this.dialog = document.createElement('dialog');
        this.dialog.className = 'lpv';
        if (this.overlay) this.dialog.classList.add('lpv-overlay');
        this.dialog.setAttribute('aria-label', 'Просмотр фотографий');
        this.dialog.innerHTML = `
            <div class="lpv-toolbar"><span class="lpv-counter" role="status" aria-live="polite" aria-atomic="true"></span></div>
            <div class="lpv-stage"><div class="lpv-canvas"></div><p class="lpv-status" role="status"></p></div>
            <div class="lpv-footer"><p class="lpv-caption"></p><div class="lpv-filmstrip">
                <div class="lpv-thumbs" role="group" aria-label="Миниатюры фотографий"></div>
            </div></div>`;
        this.counter = this.dialog.querySelector('.lpv-counter');
        this.counter.hidden = !this.navigation;
        this.dialog.querySelector('.lpv-filmstrip').hidden = !this.navigation;
        this.canvas = this.dialog.querySelector('.lpv-canvas');
        this.status = this.dialog.querySelector('.lpv-status');
        this.caption = this.dialog.querySelector('.lpv-caption');
        this.thumbs = this.dialog.querySelector('.lpv-thumbs');
        this.zoomButton = this.button('Увеличить фотографию', 'zoom');
        this.zoomButton.setAttribute('aria-pressed', 'false');
        this.download = document.createElement('a');
        this.download.className = 'lpv-button';
        this.download.title = 'Скачать фотографию';
        this.download.setAttribute('aria-label', 'Скачать фотографию');
        this.download.innerHTML = icon('download');
        this.closeButton = this.button('Закрыть просмотрщик', 'close');
        this.dialog.querySelector('.lpv-toolbar').append(this.zoomButton, this.download, this.closeButton);
        this.previous = this.button('Предыдущая фотография', 'previous', 'lpv-nav lpv-prev');
        this.next = this.button('Следующая фотография', 'next', 'lpv-nav lpv-next');
        this.previous.hidden = this.next.hidden = !this.navigation || this.items.length < 2;
        this.dialog.querySelector('.lpv-stage').append(this.previous, this.next);
        this.stripPrevious = this.button('Прокрутить миниатюры влево', 'previous');
        this.stripNext = this.button('Прокрутить миниатюры вправо', 'next');
        this.thumbs.before(this.stripPrevious);
        this.thumbs.after(this.stripNext);
        this.thumbButtons = (this.navigation ? this.items : []).map((item, index) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'lpv-thumb';
            button.setAttribute('aria-label', `Фотография ${index + 1}${item.alt ? ': ' + item.alt : ''}`);
            if (item.thumb) {
                const image = document.createElement('img');
                image.src = item.thumb;
                image.alt = '';
                image.loading = 'lazy';
                image.draggable = false;
                button.append(image);
            } else button.textContent = String(index + 1);
            this.listen(button, 'click', () => this.show(index));
            this.thumbs.append(button);
            return button;
        });
        document.body.append(this.dialog);
        this.listen(this.closeButton, 'click', () => this.close());
        this.listen(this.dialog, 'cancel', event => { event.preventDefault(); this.close(); });
        this.listen(this.dialog, 'click', event => {
            if (!this.overlay || event.target !== this.dialog) return;
            const rect = this.dialog.getBoundingClientRect();
            if (event.clientX < rect.left || event.clientX > rect.right ||
                event.clientY < rect.top || event.clientY > rect.bottom) this.close();
        });
        this.listen(this.dialog, 'close', () => {
            if (!this.dialog.open) this.restorePage();
        });
        this.listen(this.previous, 'click', () => this.step(-1));
        this.listen(this.next, 'click', () => this.step(1));
        this.listen(this.zoomButton, 'click', () => this.toggleZoom());
        this.listen(this.stripPrevious, 'click', () => this.scrollStrip(-1));
        this.listen(this.stripNext, 'click', () => this.scrollStrip(1));
        this.listen(this.thumbs, 'scroll', () => this.updateStrip(), { passive: true });
        this.listen(this.thumbs, 'wheel', event => {
            if (event.ctrlKey || Math.abs(event.deltaX) >= Math.abs(event.deltaY)) return;
            const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? this.thumbs.clientWidth : 1);
            const before = this.thumbs.scrollLeft;
            this.thumbs.scrollLeft += delta;
            if (this.thumbs.scrollLeft !== before) event.preventDefault();
        }, { passive: false });
        this.listen(document, 'keydown', event => {
            if (this.dialog.open) this.onKey(event);
        });
        this.listen(this.canvas, 'pointerdown', event => this.pointerDown(event));
        this.listen(this.canvas, 'pointermove', event => this.pointerMove(event));
        this.listen(this.canvas, 'pointerup', event => this.pointerUp(event));
        this.listen(this.canvas, 'pointercancel', () => this.cancelGesture());
        this.listen(this.canvas, 'lostpointercapture', event => {
            if (this.pointers.has(event.pointerId)) this.cancelGesture();
        });
        this.listen(this.dialog, 'wheel', event => this.wheelZoom(event), { passive: false });
        // Safari trackpads also expose GestureEvents. Touchscreen pinches use
        // PointerEvents; never apply both streams to the same gesture.
        for (const type of ['gesturestart', 'gesturechange', 'gestureend']) {
            this.listen(this.dialog, type, event => this.nativePinch(event), { passive: false });
        }
        this.listen(this.canvas, 'dblclick', event => {
            if (event.target === this.image) this.toggleZoom();
        });
        this.resize = new ResizeObserver(() => {
            if (this.dialog.open) { this.fit(); this.updateStrip(); }
        });
        this.resize.observe(this.canvas);
        this.resize.observe(this.thumbs);
    }

    bindTrigger(trigger) {
        const index = this.items.findIndex(item => item.src === imageURL(trigger.currentSrc || trigger.src || trigger.href));
        if (index < 0) return;
        const isNative = trigger.matches('a[href], button');
        const attributes = ['role', 'tabindex', 'aria-label'];
        this.extraAttributes.push([trigger, attributes.map(name => [name, trigger.getAttribute(name)])]);
        if (!isNative) {
            trigger.setAttribute('role', 'button');
            trigger.setAttribute('tabindex', '0');
            trigger.setAttribute('aria-label', 'Открыть фотографию в просмотрщике');
            this.listen(trigger, 'keydown', event => {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault(); this.open(index, trigger);
                }
            });
        }
        this.listen(trigger, 'click', event => {
            if (event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            event.preventDefault(); this.open(index, trigger);
        });
    }

    open(index = 0, trigger = document.activeElement) {
        if (this.destroyed || !this.items.length) return;
        if (this.dialog.open) { this.show(index); return; }
        // Only one viewer owns the scroll lock at a time.
        if (activeViewer && activeViewer !== this) activeViewer.close();
        activeViewer = this;
        this.returnFocus = trigger;
        this.savedScroll = { x: window.scrollX, y: window.scrollY };
        this.savedStyles = [
            [document.documentElement, 'overflow'], [document.body, 'overflow'],
            [document.body, 'position'], [document.body, 'top'], [document.body, 'left'], [document.body, 'width'],
        ].map(([element, name]) => [element, name, element.style.getPropertyValue(name), element.style.getPropertyPriority(name)]);
        document.documentElement.style.setProperty('overflow', 'hidden');
        Object.assign(document.body.style, { overflow: 'hidden', position: 'fixed',
            top: `${-this.savedScroll.y}px`, left: `${-this.savedScroll.x}px`, width: '100%' });
        this.dialog.showModal();
        this.show(index, trigger);
        this.closeButton.focus({ preventScroll: true });
        this.animate(this.dialog, [{ opacity: 0 }, { opacity: 1 }], 180);
    }

    close() {
        this.imageRequest?.abort();
        if (!this.dialog.open) return;
        this.loadID++;
        this.dialog.close();
        this.restorePage();
    }

    restorePage() {
        if (!this.savedStyles) return;
        if (activeViewer === this) activeViewer = null;
        this.loadID++;
        this.cancelGesture();
        for (const [element, name, value, priority] of this.savedStyles) {
            if (value) element.style.setProperty(name, value, priority);
            else element.style.removeProperty(name);
        }
        this.savedStyles = null;
        window.scrollTo({ left: this.savedScroll.x, top: this.savedScroll.y, behavior: 'instant' });
        if (this.returnFocus?.isConnected) this.returnFocus.focus({ preventScroll: true });
    }

    show(index, trigger = null) {
        index = Number.isFinite(index) ? Math.trunc(index) : 0;
        const oldIndex = this.index;
        this.index = (index % this.items.length + this.items.length) % this.items.length;
        const item = this.items[this.index];
        const request = ++this.loadID;
        this.imageRequest?.abort();
        this.cancelGesture();
        this.scale = 1;
        this.pan = { x: 0, y: 0 };
        this.canvas.replaceChildren();
        this.image = null;
        this.updateZoom();
        this.zoomButton.disabled = true;
        this.status.hidden = false;
        this.status.textContent = 'Загрузка фотографии…';
        this.counter.textContent = `${this.index + 1} / ${this.items.length}`;
        this.caption.textContent = item.caption || item.alt;
        this.caption.hidden = !this.caption.textContent;
        this.download.href = item.download;
        this.download.hidden = item.localOnly;
        this.download.download = new URL(item.download).pathname.split('/').pop() || `photo-${this.index + 1}.jpg`;
        this.thumbButtons.forEach((button, n) => button.setAttribute('aria-current', String(n === this.index)));
        this.centerThumb();
        const originImage = trigger?.matches?.('img') ? trigger : trigger?.querySelector?.('img');
        const origin = originImage?.getBoundingClientRect();
        const image = new Image();
        image.alt = item.alt || item.caption || `Фотография ${this.index + 1}`;
        image.className = 'lpv-image';
        image.draggable = false;
        image.onload = () => {
            if (request !== this.loadID || !this.dialog.open) return;
            this.download.hidden = false;
            this.image = image;
            this.canvas.replaceChildren(image);
            this.status.hidden = true;
            this.zoomButton.disabled = false;
            this.fit();
            const rect = image.getBoundingClientRect();
            const from = origin?.width && origin.top < window.innerHeight && origin.bottom > 0
                ? { opacity: .3, transform: `translate(${origin.x + origin.width / 2 - rect.x - rect.width / 2}px, ${origin.y + origin.height / 2 - rect.y - rect.height / 2}px) scale(${Math.min(origin.width / rect.width, 1)})` }
                : { opacity: 0, transform: `translateX(${this.index >= oldIndex ? 20 : -20}px) scale(.98)` };
            this.animate(image, [from, { opacity: 1, transform: 'translate(0, 0) scale(1)' }], trigger ? 260 : 180);
        };
        image.onerror = () => {
            if (request !== this.loadID || !this.dialog.open) return;
            this.download.hidden = true;
            this.status.textContent = 'Не удалось открыть иллюстрацию. Возможно, изображение недоступно или ссылка ведёт на другой файл.';
        };
        if (item.localOnly) this.loadLocalImage(image, item.src, request);
        else image.src = item.src;
    }

    async loadLocalImage(image, src, request) {
        const controller = new AbortController();
        this.imageRequest = controller;
        let objectURL;
        try {
            // Refuse redirects as well as external URLs; never request an external
            // image, even if a local link responds with a redirect to another site.
            const response = await fetch(src, {
                mode: 'same-origin', credentials: 'same-origin', redirect: 'error', signal: controller.signal,
            });
            if (!response.ok || !response.headers.get('Content-Type')?.startsWith('image/')) throw new Error('Invalid image');
            const blob = await response.blob();
            if (request !== this.loadID || !this.dialog.open) return;
            objectURL = URL.createObjectURL(blob);
            image.src = objectURL;
            await image.decode();
        } catch (error) {
            if (error.name !== 'AbortError') image.onerror();
        } finally {
            if (objectURL) URL.revokeObjectURL(objectURL);
        }
    }

    step(direction) { if (this.navigation) this.show(this.index + direction); }

    fit() {
        if (!this.image) return;
        const ratio = Math.min(1, this.canvas.clientWidth / this.image.naturalWidth, this.canvas.clientHeight / this.image.naturalHeight);
        this.baseWidth = this.image.naturalWidth * ratio;
        this.baseHeight = this.image.naturalHeight * ratio;
        this.image.style.width = `${this.baseWidth}px`;
        this.image.style.height = `${this.baseHeight}px`;
        this.transform();
    }

    transform() {
        if (!this.image) return;
        const maxX = Math.max(0, (this.baseWidth * this.scale - this.canvas.clientWidth) / 2);
        const maxY = Math.max(0, (this.baseHeight * this.scale - this.canvas.clientHeight) / 2);
        this.pan.x = Math.max(-maxX, Math.min(maxX, this.pan.x));
        this.pan.y = Math.max(-maxY, Math.min(maxY, this.pan.y));
        this.image.style.transform = `translate(${this.pan.x}px, ${this.pan.y}px) scale(${this.scale})`;
    }

    toggleZoom() {
        if (!this.image) return;
        this.image.getAnimations().forEach(animation => animation.cancel());
        const before = this.image.style.transform;
        this.scale = this.scale === 1 ? 2 : 1;
        this.pan = { x: 0, y: 0 };
        this.transform();
        this.updateZoom();
        this.animate(this.image, [{ transform: before }, { transform: this.image.style.transform }], 180);
    }

    zoomAt(scale, point, origin = { scale: this.scale, pan: this.pan, point }) {
        if (!this.image || !Number.isFinite(scale)) return;
        this.image.getAnimations().forEach(animation => animation.cancel());
        this.scale = Math.max(1, Math.min(8, scale));
        const rect = this.canvas.getBoundingClientRect();
        const center = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
        const ratio = this.scale / origin.scale;
        this.pan = {
            x: point.x - center.x - (origin.point.x - center.x - origin.pan.x) * ratio,
            y: point.y - center.y - (origin.point.y - center.y - origin.pan.y) * ratio,
        };
        this.transform();
        this.updateZoom();
    }

    eventPoint(event) {
        const rect = this.canvas.getBoundingClientRect();
        // Gestures over the toolbar/backdrop (or Safari events without a
        // position) zoom around the image's center.
        return event.clientX >= rect.left && event.clientX <= rect.right &&
            event.clientY >= rect.top && event.clientY <= rect.bottom
            ? { x: event.clientX, y: event.clientY }
            : { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
    }

    wheelZoom(event) {
        if (!this.dialog.open || (!event.ctrlKey && !this.canvas.contains(event.target))) return;
        event.preventDefault();
        if (this.nativeGesture || this.pointers.size > 1) return;
        const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? this.canvas.clientHeight : 1;
        const delta = Math.max(-100, Math.min(100, event.deltaY * unit));
        this.zoomAt(this.scale * Math.exp(-delta * (event.ctrlKey ? .01 : .002)), this.eventPoint(event));
        if (this.pointers.size) this.beginGesture();
    }

    nativePinch(event) {
        if (!this.dialog.open) return;
        event.preventDefault();
        if (event.type === 'gestureend') { this.nativeGesture = null; return; }
        if (this.pointers.size > 1) return;
        if (event.type === 'gesturestart') {
            this.nativeGesture = { scale: this.scale, pan: { ...this.pan }, point: this.eventPoint(event) };
        } else if (this.nativeGesture) {
            this.zoomAt(this.nativeGesture.scale * event.scale, this.eventPoint(event), this.nativeGesture);
        }
    }

    updateZoom() {
        const zoomed = this.scale > 1;
        const label = zoomed ? 'Уменьшить фотографию' : 'Увеличить фотографию';
        this.zoomButton.title = label;
        this.zoomButton.setAttribute('aria-label', label);
        this.zoomButton.setAttribute('aria-pressed', String(zoomed));
        this.zoomButton.innerHTML = icon(zoomed ? 'unzoom' : 'zoom');
        this.canvas.dataset.zoomed = String(zoomed);
    }

    centerThumb() {
        if (!this.navigation) return;
        const current = this.thumbButtons[this.index];
        const rect = current.getBoundingClientRect();
        const parent = this.thumbs.getBoundingClientRect();
        this.thumbs.scrollTo({ left: this.thumbs.scrollLeft + rect.left - parent.left - (parent.width - rect.width) / 2,
            behavior: this.reducedMotion.matches ? 'instant' : 'smooth' });
        this.updateStrip();
    }

    scrollStrip(direction) {
        this.thumbs.scrollBy({ left: direction * this.thumbs.clientWidth * .75,
            behavior: this.reducedMotion.matches ? 'instant' : 'smooth' });
    }

    updateStrip() {
        const max = this.thumbs.scrollWidth - this.thumbs.clientWidth;
        this.stripPrevious.disabled = max <= 1 || this.thumbs.scrollLeft <= 1;
        this.stripNext.disabled = max <= 1 || this.thumbs.scrollLeft >= max - 1;
    }

    onKey(event) {
        if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
        // Keep native button/thumbnail Enter and Space behavior intact.
        if (this.navigation && (event.key === 'ArrowLeft' || event.key === 'ArrowRight')) {
            event.preventDefault(); this.step(event.key === 'ArrowLeft' ? -1 : 1);
        } else if (this.navigation && (event.key === 'Home' || event.key === 'End')) {
            event.preventDefault(); this.show(event.key === 'Home' ? 0 : this.items.length - 1);
        } else if (event.key.toLowerCase() === 'z') {
            event.preventDefault(); this.toggleZoom();
        }
    }

    pointerDown(event) {
        if (event.button !== 0 || !this.image) return;
        this.image.getAnimations().forEach(animation => animation.cancel());
        this.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
        this.canvas.setPointerCapture(event.pointerId);
        if (this.pointers.size > 1) this.nativeGesture = null;
        this.beginGesture(this.pointers.size === 1);
    }

    beginGesture(allowSwipe = false) {
        const [first, second] = this.pointers.values();
        this.gesture = first ? {
            point: second ? { x: (first.x + second.x) / 2, y: (first.y + second.y) / 2 } : { ...first },
            distance: second ? Math.max(1, Math.hypot(first.x - second.x, first.y - second.y)) : 0,
            scale: this.scale, pan: { ...this.pan }, allowSwipe,
        } : null;
        this.canvas.dataset.dragging = String(!!first && this.scale > 1);
    }

    pointerMove(event) {
        if (!this.pointers.has(event.pointerId) || !this.gesture) return;
        this.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
        const [first, second] = this.pointers.values();
        if (second) {
            const distance = Math.hypot(first.x - second.x, first.y - second.y);
            const point = { x: (first.x + second.x) / 2, y: (first.y + second.y) / 2 };
            this.zoomAt(this.gesture.scale * distance / this.gesture.distance, point, this.gesture);
        } else if (this.scale > 1) {
            this.pan = { x: this.gesture.pan.x + first.x - this.gesture.point.x,
                y: this.gesture.pan.y + first.y - this.gesture.point.y };
            this.transform();
        }
        this.canvas.dataset.dragging = String(this.scale > 1);
    }

    pointerUp(event) {
        if (!this.pointers.has(event.pointerId) || !this.gesture) return;
        const dx = event.clientX - this.gesture.point.x;
        const dy = event.clientY - this.gesture.point.y;
        const swipe = this.pointers.size === 1 && this.gesture.allowSwipe && this.scale === 1;
        this.pointers.delete(event.pointerId);
        if (this.canvas.hasPointerCapture(event.pointerId)) this.canvas.releasePointerCapture(event.pointerId);
        // Continue dragging with the remaining finger without a jump or a swipe.
        this.beginGesture();
        if (swipe && Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy) * 1.3) this.step(dx < 0 ? 1 : -1);
    }

    cancelGesture() {
        const ids = [...this.pointers.keys()];
        this.pointers.clear();
        this.gesture = null;
        this.nativeGesture = null;
        this.canvas.dataset.dragging = 'false';
        for (const id of ids) {
            if (this.canvas.hasPointerCapture(id)) this.canvas.releasePointerCapture(id);
        }
    }

    animate(element, frames, duration) {
        if (!this.reducedMotion.matches) element.animate(frames, { duration, easing: 'cubic-bezier(.2,.7,.2,1)' });
    }

    destroy() {
        if (this.destroyed) return;
        this.close();
        this.destroyed = true;
        this.loadID++;
        this.abort.abort();
        this.resize.disconnect();
        this.dialog.remove();
        this.style.remove();
        for (const [element, attributes] of this.extraAttributes) {
            for (const [name, value] of attributes) {
                if (value === null) element.removeAttribute(name);
                else element.setAttribute(name, value);
            }
        }
    }
}
