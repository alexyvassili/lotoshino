(() => {
    "use strict";
    window.openArticleDocumentLibrary = function (editor, textarea) {
        const dialog = document.createElement("dialog");
        dialog.className = "article-image-library article-document-library";
        dialog.setAttribute("aria-label", "Вставить документ");
        const heading = document.createElement("h2");
        heading.textContent = "Вставить документ";
        const close = document.createElement("button");
        close.type = "button";
        close.textContent = "Закрыть";
        close.addEventListener("click", () => dialog.close());
        const searchForm = document.createElement("form");
        const search = document.createElement("input");
        search.type = "search";
        search.placeholder = "Название или имя файла";
        search.setAttribute("aria-label", "Поиск документов");
        const searchButton = document.createElement("button");
        searchButton.textContent = "Найти";
        searchForm.append(search, searchButton);
        const list = document.createElement("div");
        list.className = "article-document-list";
        const navigation = document.createElement("div");
        const previous = document.createElement("button");
        const next = document.createElement("button");
        previous.type = next.type = "button";
        previous.textContent = "Назад";
        next.textContent = "Далее";
        navigation.append(previous, next);
        const uploadLabel = document.createElement("label");
        uploadLabel.textContent = "Загрузить новый документ";
        const file = document.createElement("input");
        file.type = "file";
        file.accept = textarea.dataset.documentTypes;
        file.setAttribute("aria-label", "Загрузить новый документ");
        uploadLabel.append(file);
        const chosen = document.createElement("p");
        chosen.textContent = "Выберите документ из библиотеки или загрузите новый.";
        const label = document.createElement("label");
        label.textContent = "Текст ссылки";
        const linkText = document.createElement("input");
        linkText.type = "text";
        linkText.setAttribute("aria-label", "Текст ссылки");
        label.append(linkText);
        const insert = document.createElement("button");
        insert.type = "button";
        insert.textContent = "Вставить ссылку";
        insert.disabled = true;
        const status = document.createElement("p");
        status.setAttribute("role", "status");
        dialog.append(heading, close, searchForm, list, navigation, uploadLabel, chosen, label, insert, status);
        document.body.append(dialog);
        let selected = null, currentPage = 1, request = null, busy = false, automaticText = "";
        const select = (item) => {
            selected = item;
            chosen.textContent = `${item.title} (${item.format})`;
            if (!linkText.value.trim() || linkText.value === automaticText) linkText.value = item.title;
            automaticText = item.title;
            insert.disabled = false;
            list.querySelectorAll("button").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.id === String(item.id))));
        };
        const load = async (page) => {
            request?.abort();
            request = new AbortController();
            list.replaceChildren();
            previous.disabled = next.disabled = true;
            status.textContent = "Загрузка…";
            const url = new URL(textarea.dataset.documentLibraryUrl, location.origin);
            url.searchParams.set("q", search.value);
            url.searchParams.set("page", page);
            try {
                const response = await fetch(url, { credentials: "same-origin", signal: request.signal });
                if (!response.ok) throw new Error("Не удалось открыть библиотеку документов. Проверьте права доступа.");
                const data = await response.json();
                if (!dialog.open) return;
                currentPage = data.page;
                for (const item of data.documents) {
                    const button = document.createElement("button");
                    button.type = "button";
                    button.dataset.id = item.id;
                    button.setAttribute("aria-pressed", String(selected?.id === item.id));
                    button.textContent = `${item.title} · ${item.format} · ${item.filename}`;
                    button.addEventListener("click", () => select(item));
                    list.append(button);
                }
                status.textContent = data.documents.length ? `Страница ${data.page} из ${data.pages}` : "Документов не найдено.";
                previous.disabled = data.page <= 1;
                next.disabled = data.page >= data.pages;
            } catch (error) {
                if (error.name !== "AbortError") status.textContent = error.message;
            }
        };
        searchForm.addEventListener("submit", event => { event.preventDefault(); load(1); });
        previous.addEventListener("click", () => load(currentPage - 1));
        next.addEventListener("click", () => load(currentPage + 1));
        file.addEventListener("change", async () => {
            const chosenFile = file.files[0];
            if (!chosenFile || busy) return;
            const limit = Number(document.querySelector('meta[name="site-upload-limit-mb"]')?.content);
            if (limit > 0 && chosenFile.size > limit * 1024 * 1024) {
                status.textContent = `Максимальный размер файла для загрузки — ${limit} МБ.`;
                file.value = "";
                return;
            }
            const pending = editor.plugins.get("PendingActions");
            const action = pending.add("Загрузка документа");
            busy = true;
            file.disabled = insert.disabled = close.disabled = true;
            request?.abort();
            status.textContent = "Загрузка документа…";
            const data = new FormData();
            data.append("file", chosenFile);
            data.append("title", chosenFile.name.replace(/\.[^.]+$/, "").slice(0, 255));
            try {
                const response = await fetch(textarea.dataset.documentUploadUrl, {
                    method: "POST", credentials: "same-origin",
                    headers: { "Accept": "application/json", "X-CSRFToken": textarea.form.querySelector('[name="csrfmiddlewaretoken"]').value },
                    body: data,
                });
                const item = await response.json().catch(() => ({}));
                if (!response.ok || !item.url) throw new Error(item.error?.message || "Не удалось загрузить документ.");
                select(item);
                status.textContent = "Документ загружен. Укажите текст ссылки и нажмите «Вставить ссылку».";
            } catch (error) {
                status.textContent = error.message;
            } finally {
                busy = false;
                file.disabled = close.disabled = false;
                insert.disabled = !selected;
                file.value = "";
                pending.remove(action);
            }
        });
        insert.addEventListener("click", () => {
            if (!selected || busy) return;
            const anchor = document.createElement("a");
            anchor.className = "document-link";
            anchor.dataset.documentFormat = selected.format;
            anchor.href = selected.url;
            anchor.setAttribute("href", selected.url);
            if (selected.format === "PDF") anchor.target = "_blank";
            anchor.textContent = linkText.value.trim() || selected.title;
            const view = editor.data.processor.toView(anchor.outerHTML);
            const model = editor.data.toModel(view);
            editor.model.insertContent(model);
            dialog.close();
            editor.editing.view.focus();
        });
        dialog.addEventListener("cancel", event => { if (busy) event.preventDefault(); });
        dialog.addEventListener("close", () => { request?.abort(); dialog.remove(); });
        dialog.showModal();
        load(1);
    };
})();
