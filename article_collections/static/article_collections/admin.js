(() => {
    "use strict";
    const element = (tag, text, className) => {
        const node = document.createElement(tag);
        if (text) node.textContent = text;
        if (className) node.className = className;
        return node;
    };
    const button = (text, className) => {
        const node = element("button", text, className);
        node.type = "button";
        return node;
    };
    const rows = () => [...document.querySelectorAll('#items-group .inline-related:not(.empty-form)')]
        .filter(row => row.querySelector('[name$="-article"]') && !row.querySelector('[name$="-DELETE"]')?.checked);
    const summaries = new WeakMap();
    let contents;
    function itemTitle(row) {
        const article = row.querySelector('[name$="-article"]');
        return row.querySelector('[name$="-title"]').value.trim()
            || (article.value && article.selectedOptions[0]?.textContent.trim())
            || 'Новая статья';
    }
    function numberRows() {
        const items = rows();
        const entries = items.map((row, index) => {
            row.querySelector('[name$="-position"]').value = index;
            const entry = summaries.get(row);
            entry.querySelector('.collection-move-up').disabled = index === 0;
            entry.querySelector('.collection-move-down').disabled = index === items.length - 1;
            const link = entry.querySelector('a');
            link.textContent = itemTitle(row);
            link.href = `#${row.id}`;
            return entry;
        });
        contents?.replaceChildren(...entries);
        if (!entries.length) contents?.append(element('li', 'Добавьте статьи в подборку.', 'collection-contents-empty'));
    }
    function initializeRow(row) {
        if (row.classList.contains('empty-form') || row.dataset.collectionReady) return;
        const article = row.querySelector('[name$="-article"]');
        if (!article) return;
        row.dataset.collectionReady = 'true';
        // Keep the collection editor open and use the full article admin page.
        const articleWidget = article.closest('.related-widget-wrapper');
        articleWidget.querySelectorAll('.change-related, .view-related').forEach(link => {
            link.target = '_blank';
            link.rel = 'noopener';
            link.removeAttribute('data-popup');
            link.dataset.hrefTemplate = link.dataset.hrefTemplate.split('?')[0];
            if (link.hasAttribute('href')) link.href = link.href.split('?')[0];
        });
        const title = row.querySelector('[name$="-title"]');
        let automaticTitle = article.selectedOptions[0]?.textContent.trim() || '';
        const updateTitle = () => {
            const nextTitle = article.value ? article.selectedOptions[0].textContent.trim() : '';
            if (!title.value.trim() || title.value === automaticTitle) title.value = nextTitle;
            automaticTitle = nextTitle;
            numberRows();
        };
        // Django's autocomplete emits a jQuery change event.
        window.django.jQuery(article).on('change', updateTitle);
        title.addEventListener('input', () => {
            summaries.get(row).querySelector('a').textContent = itemTitle(row);
        });
        const entry = element('li', '', 'collection-contents-item');
        const link = element('a', itemTitle(row));
        link.addEventListener('click', event => {
            event.preventDefault();
            row.scrollIntoView({block: 'start'});
            row.querySelector('h3').focus({preventScroll: true});
        });
        entry.append(link);
        summaries.set(row, entry);
        row.querySelector('h3').tabIndex = -1;
        const controls = element('span', '', 'collection-order-controls');
        for (const [direction, text] of [['up', '↑ Выше'], ['down', '↓ Ниже']]) {
            const control = button(text, `collection-move-${direction}`);
            control.addEventListener('click', () => {
                const items = rows();
                const index = items.indexOf(row);
                const other = items[index + (direction === 'up' ? -1 : 1)];
                if (other) {
                    if (direction === 'up') other.before(row);
                    else other.after(row);
                    numberRows();
                    const focusTarget = control.disabled ? controls.querySelector('button:not(:disabled)') : control;
                    focusTarget?.focus({preventScroll: true});
                }
            });
            controls.append(control);
        }
        entry.append(controls);
    }

    function openPicker(widget) {
        const row = widget.closest('.inline-related');
        const articleId = row.querySelector('[name$="-article"]').value;
        const dialog = element('dialog', '', 'collection-picker-dialog');
        dialog.setAttribute('aria-label', 'Выбор изображения для анонса');
        const header = element('header');
        const close = button('Закрыть');
        header.append(element('h2', 'Изображение анонса'), close);
        const tools = element('div', '', 'collection-picker-tools');
        const scope = element('select');
        scope.setAttribute('aria-label', 'Источник изображений');
        for (const [value, label] of [['article', 'Изображения статьи'], ['all', 'Все изображения']]) {
            const option = element('option', label);
            option.value = value;
            option.disabled = value === 'article' && !articleId;
            scope.append(option);
        }
        scope.value = articleId ? 'article' : 'all';
        const search = element('input');
        search.type = 'search'; search.placeholder = 'Название или описание';
        search.setAttribute('aria-label', 'Поиск изображений');
        const find = button('Найти');
        const uploadButton = button('Загрузить своё');
        const file = element('input');
        file.type = 'file'; file.accept = widget.dataset.imageTypes; file.hidden = true;
        tools.append(scope, search, find, uploadButton, file);
        const status = element('p'); status.setAttribute('role', 'status');
        const grid = element('div', '', 'collection-picker-grid');
        const pages = element('div', '', 'collection-picker-pagination');
        const previous = button('← Назад'), next = button('Далее →'), pageLabel = element('span');
        pages.append(previous, pageLabel, next);
        dialog.append(header, tools, status, grid, pages);
        document.body.append(dialog);
        let currentPage = 1, request, busy = false;
        const csrf = () => widget.closest('form').querySelector('[name=csrfmiddlewaretoken]').value;
        const error = message => { status.textContent = message; status.className = 'collection-picker-error'; };
        const select = (data, title) => {
            widget.querySelector('input').value = data.id;
            widget.querySelector('input').dispatchEvent(new Event('change', {bubbles: true}));
            const preview = widget.querySelector('.collection-image-preview');
            preview.src = data.url; preview.alt = title; preview.hidden = false;
            widget.querySelector('.collection-image-title').textContent = title;
            widget.querySelector('.collection-image-clear').hidden = false;
            dialog.close();
        };
        const post = async (url, data) => {
            const response = await fetch(url, {method:'POST', credentials:'same-origin', headers:{'X-CSRFToken':csrf()}, body:data});
            if (response.status === 413) throw new Error('Файл превышает разрешённый размер загрузки.');
            if (response.status === 403) throw new Error('Недостаточно прав для работы с изображениями.');
            const result = await response.json();
            if (!response.ok) throw new Error(result.error?.message || 'Не удалось подготовить изображение.');
            return result;
        };
        const prepare = async image => {
            if (busy) return;
            busy = true; status.textContent = 'Подготовка изображения…';
            try { select(await post(widget.dataset.prepareUrl.replace('/0/', `/${image.id}/`)), image.title); }
            catch (exception) { error(exception.message); }
            finally { busy = false; }
        };
        const load = async (page = 1) => {
            request?.abort(); request = new AbortController();
            status.className = ''; status.textContent = 'Загрузка…'; grid.replaceChildren();
            previous.disabled = next.disabled = true;
            const url = new URL(widget.dataset.pickerUrl, location.origin);
            url.search = new URLSearchParams({scope:scope.value, article:articleId, q:search.value, page});
            try {
                const response = await fetch(url, {signal:request.signal, credentials:'same-origin'});
                if (!response.ok) throw new Error('Не удалось получить список изображений. Проверьте права доступа.');
                const data = await response.json();
                if (!dialog.open) return;
                currentPage = data.page;
                for (const image of data.images) {
                    const choice = button('');
                    const picture = element('img'); picture.src = image.url; picture.alt = image.title;
                    choice.append(picture, element('span', image.title));
                    choice.addEventListener('click', () => prepare(image));
                    grid.append(choice);
                }
                status.textContent = data.images.length ? '' : 'Изображений нет. Выберите «Все изображения» или загрузите своё.';
                pageLabel.textContent = `${data.page} / ${data.pages}`;
                previous.disabled = data.page <= 1; next.disabled = data.page >= data.pages;
            } catch (exception) { if (exception.name !== 'AbortError') error(exception.message); }
        };
        close.addEventListener('click', () => { if (!busy) dialog.close(); });
        dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
        dialog.addEventListener('close', () => { request?.abort(); dialog.remove(); widget.querySelector('.collection-image-choose').focus(); }, {once:true});
        find.addEventListener('click', () => load());
        search.addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); load(); } });
        scope.addEventListener('change', () => load());
        previous.addEventListener('click', () => load(currentPage - 1));
        next.addEventListener('click', () => load(currentPage + 1));
        uploadButton.addEventListener('click', () => { if (!busy) file.click(); });
        file.addEventListener('change', async () => {
            const selected = file.files[0]; if (!selected || busy) return;
            const limit = Number(document.querySelector('meta[name="site-upload-limit-mb"]')?.content);
            if (limit > 0 && selected.size > limit * 1024 * 1024) { error(`Максимальный размер файла — ${limit} МБ.`); file.value = ''; return; }
            busy = true; status.className = ''; status.textContent = 'Загрузка изображения…';
            const data = new FormData(); data.append('upload', selected);
            try { select(await post(widget.dataset.uploadUrl, data), selected.name); }
            catch (exception) { error(exception.message); }
            finally { busy = false; file.value = ''; }
        });
        dialog.showModal(); load();
    }

    const start = () => {
        const template = document.querySelector('#id_template_name');
        if (template) {
            const updateLayout = () => {
                const textOnly = template.value === 'article_collections/layouts/azbuka-pravoslaviya.html';
                for (const node of document.querySelectorAll('.field-closing_text, #items-group')) node.hidden = textOnly;
                const label = document.querySelector('label[for="id_introduction"]');
                if (label) label.textContent = textOnly ? 'Содержимое:' : 'Вступительный текст:';
            };
            template.addEventListener('change', updateLayout);
            updateLayout();
        }
        const heading = document.querySelector('#items-heading');
        if (!heading) return;
        const navigation = element('nav', '', 'collection-contents');
        navigation.setAttribute('aria-label', 'Статьи подборки: порядок и переход к редактированию');
        contents = element('ol');
        navigation.append(contents);
        heading.after(navigation);
        document.querySelectorAll('#items-group .inline-related').forEach(initializeRow);
        numberRows();
        document.addEventListener('formset:added', event => { initializeRow(event.target); numberRows(); });
        // Django renumbers inline IDs after dispatching this event.
        document.addEventListener('formset:removed', () => queueMicrotask(numberRows));
        document.addEventListener('change', event => { if (event.target.name?.endsWith('-DELETE')) numberRows(); });
        document.addEventListener('click', event => {
            const choose = event.target.closest('.collection-image-choose');
            if (choose) openPicker(choose.closest('.collection-image-picker'));
            const clear = event.target.closest('.collection-image-clear');
            if (clear) {
                const widget = clear.closest('.collection-image-picker');
                const input = widget.querySelector('input'); input.value = ''; input.dispatchEvent(new Event('change', {bubbles:true}));
                const preview = widget.querySelector('.collection-image-preview'); preview.hidden = true; preview.removeAttribute('src');
                widget.querySelector('.collection-image-title').textContent = 'Изображение не выбрано'; clear.hidden = true;
            }
        });
        document.querySelector('#collection_form')?.addEventListener('submit', numberRows);
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
    else start();
})();
