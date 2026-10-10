(() => {
    const limit = Number(document.querySelector('meta[name="site-upload-limit-mb"]')?.content);
    if (!Number.isFinite(limit) || limit <= 0) return;

    function validate(input) {
        const oversized = [...input.files].some(file => file.size > limit * 1024 * 1024);
        input.setCustomValidity(oversized
            ? `Максимальный размер файла для загрузки — ${limit} МБ. Выберите файл меньшего размера.`
            : '');
        return !oversized;
    }

    document.addEventListener('change', event => {
        const input = event.target;
        // Editor-owned inputs are checked by their upload adapter.
        if (!input.matches('input[type="file"]') || !input.name) return;
        if (!validate(input) && input.getClientRects().length) input.reportValidity();
    });
    document.addEventListener('submit', event => {
        for (const input of event.target.querySelectorAll('input[type="file"]:enabled')) {
            if (!input.name) continue;
            if (!validate(input)) {
                event.preventDefault();
                input.reportValidity();
                break;
            }
        }
    }, true);
})();
