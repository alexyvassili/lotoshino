(() => {
    'use strict';
    const create = (tag, text, className) => {
        const node = document.createElement(tag);
        if (text) node.textContent = text;
        if (className) node.className = className;
        return node;
    };
    const start = () => {
        const group = document.querySelector('#items-group');
        if (!group) return;
        const list = create('ol', '', 'menu-order-list');
        const nav = create('nav', '', 'menu-order');
        nav.setAttribute('aria-label', 'Порядок пунктов меню');
        nav.append(list);
        group.querySelector('h2').after(nav);
        const entries = new WeakMap();
        const rows = () => [...group.querySelectorAll('.inline-related:not(.empty-form)')]
            .filter(row => row.querySelector('[name$="-title"]') && !row.querySelector('[name$="-DELETE"]')?.checked);
        const refresh = () => {
            const items = rows();
            list.replaceChildren(...items.map((row, index) => {
                const entry = entries.get(row);
                row.querySelector('[name$="-position"]').value = index;
                const link = entry.querySelector('a');
                link.textContent = row.querySelector('[name$="-title"]').value.trim() || 'Новый пункт';
                link.href = `#${row.id}`;
                entry.classList.toggle('menu-item-hidden', !row.querySelector('[name$="-is_visible"]').checked);
                entry.querySelector('.menu-move-up').disabled = index === 0;
                entry.querySelector('.menu-move-down').disabled = index === items.length - 1;
                return entry;
            }));
            if (!items.length) list.append(create('li', 'Добавьте пункты меню.', 'menu-order-empty'));
        };
        const initialize = row => {
            if (row.classList.contains('empty-form') || entries.has(row)) return;
            const title = row.querySelector('[name$="-title"]');
            if (!title) return;
            const entry = create('li');
            const link = create('a');
            const heading = row.querySelector('h3');
            heading.tabIndex = -1;
            link.addEventListener('click', event => {
                event.preventDefault();
                row.scrollIntoView({block: 'start'});
                heading.focus({preventScroll: true});
            });
            entry.append(link);
            const controls = create('span', '', 'menu-order-controls');
            for (const [direction, label] of [['up', '↑ Выше'], ['down', '↓ Ниже']]) {
                const button = create('button', label, `menu-move-${direction}`);
                button.type = 'button';
                button.addEventListener('click', () => {
                    const items = rows();
                    const other = items[items.indexOf(row) + (direction === 'up' ? -1 : 1)];
                    if (!other) return;
                    if (direction === 'up') other.before(row);
                    else other.after(row);
                    refresh();
                    (button.disabled ? controls.querySelector('button:not(:disabled)') : button)?.focus({preventScroll:true});
                });
                controls.append(button);
            }
            entry.append(controls);
            entries.set(row, entry);
            const page = row.querySelector('[name$="-page"]');
            let automaticTitle = page.selectedOptions[0]?.dataset.title || '';
            page.addEventListener('change', () => {
                const nextTitle = page.selectedOptions[0]?.dataset.title || '';
                if (nextTitle && (!title.value.trim() || title.value === automaticTitle)) {
                    title.value = nextTitle;
                    link.textContent = nextTitle;
                }
                automaticTitle = nextTitle;
            });
            title.addEventListener('input', () => { link.textContent = title.value.trim() || 'Новый пункт'; });
        };
        group.querySelectorAll('.inline-related').forEach(initialize);
        refresh();
        group.addEventListener('formset:added', event => { initialize(event.target); refresh(); });
        document.addEventListener('formset:removed', event => {
            if (event.detail.formsetName === 'items') queueMicrotask(refresh);
        });
        group.addEventListener('change', event => {
            if (event.target.name?.endsWith('-DELETE') || event.target.name?.endsWith('-is_visible')) refresh();
        });
        group.closest('form').addEventListener('submit', refresh);
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
    else start();
})();
