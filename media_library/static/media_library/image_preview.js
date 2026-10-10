import PhotoViewer from '../js/photo_viewer.js';

const container = document.querySelector('#result_list') || document.querySelector('#content-main');
if (container?.querySelector('.media-image-preview')) {
    new PhotoViewer(container, {
        itemSelector: '.media-image-preview',
        overlay: true,
    });
}
