(() => {
    "use strict";

    function protectUnsavedChanges(textarea) {
        const form = textarea.form;
        const read = () => Object.fromEntries(
            ["title", "slug", "is_published", "content"].map((name) => {
                const field = form.elements.namedItem(name);
                return [name, field?.type === "checkbox" ? field.checked : field?.value];
            }),
        );
        const initial = read();
        const hasValidationErrors = Boolean(form.querySelector(".errorlist"));
        let submitting = false;
        let pendingActions;
        const resumeProtection = () => { submitting = false; };
        window.addEventListener("pageshow", resumeProtection);
        form.addEventListener("input", resumeProtection);
        form.addEventListener("change", resumeProtection);

        window.addEventListener("beforeunload", (event) => {
            const changed = JSON.stringify(read()) !== JSON.stringify(initial);
            if (!submitting && (changed || hasValidationErrors || pendingActions?.hasAny)) {
                event.preventDefault();
                event.returnValue = "";
            }
        });
        window.addEventListener("submit", (event) => {
            // Bubbling reaches window after the editor's upload check on the form.
            if (event.target === form) {
                submitting = !event.defaultPrevented;
            }
        });
        return (editor) => {
            // CKEditor normalizes HTML on startup; this is not a user edit.
            initial.content = editor.getData();
            editor.updateSourceElement();
            pendingActions = editor.plugins.get("PendingActions");
            editor.model.document.on("change:data", resumeProtection);
        };
    }

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
                                articleFullSize: result.full_url, articleViewer: "true",
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
        const editorReady = protectUnsavedChanges(textarea);
        const status = textarea.closest(".article-editor-wrapper").querySelector(".article-editor-status");
        try {
            const CK = window.CKEDITOR;
            function configureArticleImageViewer(editor) {
                const imageUtils = editor.plugins.get("ImageUtils");
                editor.model.schema.extend("imageBlock", { allowAttributes: ["articleViewer", "articleFullSize"] });
                for (const [model, attribute] of [["articleViewer", "data-viewer"], ["articleFullSize", "data-full-size"]]) {
                    editor.conversion.for("upcast").attributeToAttribute({
                        view: { name: "img", key: attribute }, model,
                    });
                    editor.conversion.for("downcast").add((dispatcher) => {
                        dispatcher.on(`attribute:${model}:imageBlock`, (event, data, api) => {
                            if (!api.consumable.consume(data.item, event.name)) return;
                            const image = imageUtils.findViewImgElement(api.mapper.toViewElement(data.item));
                            if (data.attributeNewValue === null) api.writer.removeAttribute(attribute, image);
                            else api.writer.setAttribute(attribute, data.attributeNewValue, image);
                        });
                    });
                }
                editor.ui.componentFactory.add("articleImageViewer", (locale) => {
                    const toggle = new CK.SwitchButtonView(locale);
                    toggle.set({ label: "Открывать в полном размере", withText: true, tooltip: "Открывать исходное изображение в просмотрщике" });
                    const selectedImage = () => editor.model.document.selection.getSelectedElement();
                    const update = () => {
                        const image = selectedImage();
                        toggle.isEnabled = !editor.isReadOnly && imageUtils.isBlockImage(image);
                        toggle.isOn = toggle.isEnabled && image.getAttribute("articleViewer") !== "false";
                    };
                    editor.model.document.selection.on("change", update);
                    editor.model.document.on("change:data", update);
                    editor.on("change:isReadOnly", update);
                    toggle.on("execute", () => {
                        const image = selectedImage();
                        if (!imageUtils.isBlockImage(image)) return;
                        const enabled = image.getAttribute("articleViewer") === "false";
                        const fullSize = image.getAttribute("articleFullSize") || image.getAttribute("linkHref") || image.getAttribute("src");
                        editor.model.change((writer) => {
                            writer.setAttribute("articleViewer", String(enabled), image);
                            writer.setAttribute("articleFullSize", fullSize, image);
                            if (enabled) writer.setAttribute("linkHref", fullSize, image);
                            else if (image.getAttribute("linkHref") === fullSize) writer.removeAttribute("linkHref", image);
                        });
                        editor.editing.view.focus();
                    });
                    update();
                    return toggle;
                });
            }
            class ArticleImageViewer extends CK.Plugin {
                init() {
                    configureArticleImageViewer(this.editor);
                }
            }
            class ArticleIllustrations extends CK.Plugin {
                afterInit() {
                    const editor = this.editor;
                    const linkUI = editor.plugins.get("LinkUI");
                    const command = editor.commands.get("link");
                    const decorator = command.manualDecorators.get("linkIllustration");
                    const message = "Для иллюстрации укажите относительный адрес на этом сайте. Адрес должен начинаться символом /. Ссылки на внешние сайты использовать нельзя.";
                    const localURL = (value) => {
                        try { return /^\/(?!\/)[^\s\\]*$/.test(decodeURIComponent(value)); }
                        catch { return false; }
                    };
                    // CKEditor 49 creates its link form lazily. Keep the switch in
                    // that form, next to the URL, rather than in a separate panel.
                    const createForm = linkUI._createFormView.bind(linkUI);
                    linkUI._createFormView = () => {
                        const form = createForm();
                        const toggle = new CK.SwitchButtonView(editor.locale);
                        toggle.set({ label: "Иллюстрация", withText: true });
                        toggle.bind("isOn").to(decorator, "value", value => !!value);
                        toggle.on("execute", () => { decorator.value = !toggle.isOn; form.resetFormStatus(); });
                        form.children.add(toggle, 2);
                        form.manualDecoratorsButtonView.isVisible = false;
                        const render = form.render.bind(form);
                        form.render = () => {
                            render();
                            form._focusables.add(toggle);
                            form.focusTracker.add(toggle.element);
                        };
                        form.on("submit", event => {
                            if (toggle.isOn && !localURL(form.url)) {
                                event.stop();
                                form.urlInputView.errorText = message;
                                form.urlInputView.fieldView.focus();
                            }
                        }, { priority: "high" });
                        return form;
                    };
                    command.on("execute", (event, [url, decorators = {}]) => {
                        if ((decorators.linkIllustration ?? decorator.value) && !localURL(url)) {
                            event.stop();
                            status.textContent = message;
                        }
                    }, { priority: "highest" });
                }
            }
            function ArticleImages(editor) {
                editor.plugins.get("FileRepository").createUploadAdapter = (loader) => new UploadAdapter(loader, textarea);
                editor.plugins.get("ImageUploadEditing").on("uploadComplete", (event, { imageElement, data }) => {
                    if (data.fullUrl) {
                        editor.model.change((writer) => {
                            writer.setAttribute("articleFullSize", data.fullUrl, imageElement);
                            if (imageElement.getAttribute("articleViewer") !== "false") {
                                writer.setAttribute("articleViewer", "true", imageElement);
                                writer.setAttribute("linkHref", data.fullUrl, imageElement);
                            }
                        });
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
                extraPlugins: [ArticleImages, ArticleImageViewer, ArticleIllustrations],
                link: {
                    decorators: {
                        illustration: { mode: "manual", label: "Иллюстрация", defaultValue: false,
                            attributes: { "data-illustration": "true" } },
                    },
                    toolbar: ["linkPreview", "|", "editLink", "unlink"],
                },
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
                    upload: { types: textarea.dataset.imageTypes.split(",").filter(Boolean) },
                    styles: { options: ["alignLeft", "block", "alignRight"] },
                    toolbar: ["imageStyle:alignLeft", "imageStyle:block", "imageStyle:alignRight", "|", "resizeImage", "toggleImageCaption", "imageTextAlternative", "|", "articleImageViewer"],
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
            editorReady(editor);
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
