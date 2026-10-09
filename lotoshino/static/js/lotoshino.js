// The calendar widget inserts links without a target into the page.
document.querySelectorAll('a[href]').forEach((link) => {
    const url = new URL(link.href, document.baseURI);
    if (['http:', 'https:'].includes(url.protocol) && url.origin !== window.location.origin) {
        link.target = '_blank';
        link.relList.add('noopener', 'noreferrer');
    }
});
