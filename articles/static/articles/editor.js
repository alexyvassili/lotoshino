(() => {
    "use strict";

    class UploadAdapter {
        constructor(loader, textarea) {
            this.loader = loader;
            this.textarea = textarea;
            this.controller = new AbortController();
        }

        async upload() {
            const file = await this.loader.file;
            const limit = Number(document.querySelector('meta[name="site-upload-limit-mb"]')?.content);
            if (limit > 0 && file.size > limit * 1024 * 1024) {
                throw new Error(`Максимальный размер файла для загрузки — ${limit} МБ. Выберите файл меньшего размера.`);
            }
            const data = new FormData();
            data.append("upload", file);
            const response = await fetch(this.textarea.dataset.uploadUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json",
                    "X-CSRFToken": this.textarea.form.querySelector('[name="csrfmiddlewaretoken"]').value,
                },
                body: data,
                signal: this.controller.signal,
            });
            const result = await response.json().catch(() => ({}));
            if (!response.ok || !result.url) {
                throw new Error(result.error?.message || "Не удалось загрузить изображение. Проверьте права доступа и повторите попытку.");
            }
            return { urls: { default: result.url }, fullUrl: result.full_url };
        }

        abort() {
            this.controller.abort();
        }
    }

    function openLibrary(editor, textarea) {
        const dialog = document.createElement("dialog");
        dialog.className = "article-image-library";
        dialog.setAttribute("aria-label", "Библиотека изображений");
        const heading = document.createElement("h2");
        heading.textContent = "Библиотека изображений";
        const close = document.createElement("button");
        close.type = "button";
        close.textContent = "Закрыть";
        close.addEventListener("click", () => dialog.close());
        const searchForm = document.createElement("form");
        const search = document.createElement("input");
        search.type = "search";
        search.placeholder = "Название изображения";
        search.setAttribute("aria-label", "Поиск изображений");
        const searchButton = document.createElement("button");
        searchButton.type = "submit";
        searchButton.textContent = "Найти";
        searchForm.append(search, searchButton);
        const status = document.createElement("p");
        status.setAttribute("role", "status");
        const grid = document.createElement("div");
        grid.className = "article-image-grid";
        const navigation = document.createElement("div");
        const previous = document.createElement("button");
        const next = document.createElement("button");
        previous.type = next.type = "button";
        previous.textContent = "Назад";
        next.textContent = "Далее";
        navigation.append(previous, next);
        dialog.append(heading, close, searchForm, status, grid, navigation);
        document.body.append(dialog);
        let currentPage = 1;
        let request;
        let preparing = false;
        const preparation = new AbortController();

        async function load(page) {
            request?.abort();
            request = new AbortController();
            grid.replaceChildren();
            previous.disabled = next.disabled = true;
            status.textContent = "Загрузка…";
            const url = new URL(textarea.dataset.libraryUrl, window.location.origin);
            url.searchParams.set("q", search.value);
            url.searchParams.set("page", page);
            try {
                const response = await fetch(url, { signal: request.signal, credentials: "same-origin" });
                if (!response.ok) throw new Error("Нет доступа к библиотеке или произошла ошибка загрузки.");
                const result = await response.json();
                currentPage = result.page;
                status.textContent = result.images.length ? `Страница ${result.page} из ${result.pages}` : "Изображений нет. Загрузите новое изображение через панель редактора.";
                for (const item of result.images) {
                    const button = document.createElement("button");
                    button.type = "button";
                    const image = document.createElement("img");
                    image.src = item.url;
                    image.alt = item.alt;
                    image.loading = "lazy";
                    const label = document.createElement("span");
                    label.textContent = item.title;
                    button.append(image, label);
                    button.addEventListener("click", async () => {
                        if (preparing) return;
                        preparing = true;
                        status.textContent = "Подготовка размеров для статьи…";
                        const pending = editor.plugins.get("PendingActions");
                        const action = pending.add("Подготовка изображения для статьи");
                        try {
                            const response = await fetch(item.prepare_url, {
                                method: "POST",
                                credentials: "same-origin",
                                headers: {
                                    "Accept": "application/json",
                                    "X-CSRFToken": textarea.form.querySelector('[name="csrfmiddlewaretoken"]').value,
                                },
                                signal: preparation.signal,
                            });
                            const result = await response.json().catch(() => ({}));
                            if (!response.ok || !result.url || !result.full_url) {
                                throw new Error(result.error?.message || "Не удалось подготовить изображение.");
                            }
                            if (!dialog.open) return;
                            editor.execute("insertImage", { source: [{
                                src: result.url, alt: result.alt, linkHref: result.full_url,
                                width: result.width, height: result.height,
                            }] });
                            dialog.close();
                        } catch (error) {
                            if (error.name !== "AbortError") status.textContent = error.message;
                        } finally {
                            preparing = false;
                            pending.remove(action);
                        }
                    });
                    grid.append(button);
                }
                previous.disabled = result.page <= 1;
                next.disabled = result.page >= result.pages;
            } catch (error) {
                if (error.name !== "AbortError") status.textContent = error.message;
            }
        }

        searchForm.addEventListener("submit", (event) => { event.preventDefault(); load(1); });
        previous.addEventListener("click", () => load(currentPage - 1));
        next.addEventListener("click", () => load(currentPage + 1));
        dialog.addEventListener("close", () => {
            request?.abort();
            preparation.abort();
            dialog.remove();
            editor.editing.view.focus();
        }, { once: true });
        dialog.showModal();
        load(1);
    }

    async function initialize(textarea) {
        const status = textarea.closest(".article-editor-wrapper").querySelector(".article-editor-status");
        try {
            const CK = window.CKEDITOR;
            function ArticleImages(editor) {
                editor.plugins.get("FileRepository").createUploadAdapter = (loader) => new UploadAdapter(loader, textarea);
                editor.plugins.get("ImageUploadEditing").on("uploadComplete", (event, { imageElement, data }) => {
                    if (data.fullUrl) {
                        editor.model.change((writer) => writer.setAttribute("linkHref", data.fullUrl, imageElement));
                    }
                });
                editor.ui.componentFactory.add("imageLibrary", (locale) => {
                    const button = new CK.ButtonView(locale);
                    button.set({ label: "Библиотека изображений", withText: true, tooltip: true });
                    button.bind("isEnabled").to(editor.commands.get("insertImage"), "isEnabled");
                    button.on("execute", () => openLibrary(editor, textarea));
                    return button;
                });
            }
            const editor = await CK.ClassicEditor.create(textarea, {
                licenseKey: "GPL",
                language: "ru",
                plugins: [
                    CK.Essentials, CK.Paragraph, CK.Heading, CK.Bold, CK.Italic,
                    CK.Link, CK.LinkImage, CK.List, CK.BlockQuote, CK.ImageBlock, CK.ImageCaption,
                    CK.ImageStyle, CK.ImageToolbar, CK.ImageUpload, CK.ImageResize,
                    CK.PendingActions,
                ],
                extraPlugins: [ArticleImages],
                toolbar: {
                    items: ["undo", "redo", "|", "heading", "|", "bold", "italic", "link", "bulletedList", "numberedList", "blockQuote", "|", "uploadImage", "imageLibrary"],
                    shouldNotGroupWhenFull: true,
                },
                heading: { options: [
                    { model: "paragraph", title: "Абзац", class: "ck-heading_paragraph" },
                    { model: "heading2", view: "h2", title: "Заголовок 2", class: "ck-heading_heading2" },
                    { model: "heading3", view: "h3", title: "Заголовок 3", class: "ck-heading_heading3" },
                ] },
                image: {
                    upload: { types: ["jpeg", "png", "webp"] },
                    styles: { options: ["alignLeft", "block", "alignRight"] },
                    toolbar: ["imageStyle:alignLeft", "imageStyle:block", "imageStyle:alignRight", "|", "resizeImage", "toggleImageCaption", "imageTextAlternative"],
                    resizeUnit: "%",
                    resizeOptions: [
                        { name: "resizeImage:original", value: null, label: "Исходный размер" },
                        { name: "resizeImage:25", value: "25", label: "25%" },
                        { name: "resizeImage:50", value: "50", label: "50%" },
                        { name: "resizeImage:75", value: "75", label: "75%" },
                    ],
                },
            });
            textarea.required = false;
            textarea.form.addEventListener("submit", (event) => {
                if (editor.plugins.get("PendingActions").hasAny) {
                    event.preventDefault();
                    status.textContent = "Дождитесь загрузки изображений и нажмите «Сохранить» ещё раз.";
                }
                editor.updateSourceElement();
            });
            editor.model.document.on("change:data", () => { editor.updateSourceElement(); status.textContent = ""; });
        } catch (error) {
            console.error("CKEditor initialization failed", error);
            status.textContent = "Визуальный редактор не загрузился. Текст сохранён в поле ниже; обновите страницу, чтобы повторить попытку.";
        }
    }

    const start = () => document.querySelectorAll("textarea[data-article-editor]").forEach(initialize);
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
    else start();
})();
