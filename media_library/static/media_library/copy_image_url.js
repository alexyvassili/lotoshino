document.addEventListener('click', async (event) => {
    const button = event.target.closest('.copy-image-url');
    if (!button) return;
    const status = button.parentElement.querySelector('.copy-image-status');
    try {
        const url = new URL(button.dataset.copyUrl, window.location.href);
        await navigator.clipboard.writeText(url.pathname);
        status.textContent = 'Адрес скопирован';
    } catch {
        status.textContent = 'Не удалось скопировать адрес. Скопируйте ссылку вручную.';
    }
});
