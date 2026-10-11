import PhotoViewer from '../js/photo_viewer.js';

const content = document.querySelector('.article-content[data-image-base]');
if (content) {
    const downloads = JSON.parse(document.getElementById('article-image-downloads')?.textContent || '{}');
    const imageBase = new URL(content.dataset.imageBase, window.location.href).href;
    const libraryImage = (value) => {
        if (!value) return false;
        try {
            const url = new URL(value, window.location.href).href;
            return url.startsWith(imageBase) && /^[a-f0-9]{32}(?:_[A-Za-z0-9]{7})?(?:_[1-9]\d{0,4}x[1-9]\d{0,4}(?:_[A-Za-z0-9]{7})?)?\.(jpg|png|webp)$/.test(url.slice(imageBase.length));
        } catch { return false; }
    };
    for (const link of content.querySelectorAll('a[data-illustration="true"]')) {
        const href = link.getAttribute('href');
        try {
            if (!/^\/(?!\/)[^\s\\]*$/.test(decodeURIComponent(href)) ||
                new URL(href, window.location.href).origin !== window.location.origin) continue;
        } catch { continue; }
        link.classList.add('article-photo-viewer');
        link.dataset.localImage = 'true';
        link.dataset.caption = link.textContent.trim();
        if (libraryImage(downloads[href])) link.dataset.downloadUrl = downloads[href];
        link.setAttribute('aria-haspopup', 'dialog');
    }
    for (const image of content.querySelectorAll('img')) {
        let link = image.closest('a');
        if (link?.dataset.illustration === 'true') continue;
        const href = link?.getAttribute('href');
        if (image.dataset.viewer === 'false') {
            if (link && libraryImage(href)) link.replaceWith(...link.childNodes);
            continue;
        }
        // Preserve explicitly authored links to other pages.
        if (link && !libraryImage(href)) continue;
        const fullSize = image.dataset.fullSize || href || image.getAttribute('src');
        if (!libraryImage(fullSize)) continue;
        if (!link) {
            link = document.createElement('a');
            image.before(link);
            link.append(image);
        }
        link.href = fullSize;
        const download = downloads[image.getAttribute('src')];
        if (libraryImage(download)) link.dataset.downloadUrl = download;
        link.classList.add('article-photo-viewer');
        link.dataset.caption = image.closest('figure')?.querySelector('figcaption')?.textContent.trim() || image.alt;
        link.setAttribute('aria-label', image.alt ? `Открыть изображение: ${image.alt}` : 'Открыть изображение в полном размере');
        link.setAttribute('aria-haspopup', 'dialog');
    }
    if (content.querySelector('.article-photo-viewer')) {
        new PhotoViewer(content, { itemSelector: '.article-photo-viewer', overlay: true, navigation: false });
    }
}
