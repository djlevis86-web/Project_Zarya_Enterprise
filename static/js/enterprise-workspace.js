(function () {
    "use strict";

    const fallbackPalette = [
        "#39b96a",
        "#5f9fe8",
        "#e3b341",
        "#78c442",
        "#e86767",
        "#94a49a",
    ];

    function parseSource(id) {
        const node = document.getElementById(id);

        if (!node) return null;

        try {
            return JSON.parse(node.textContent);
        } catch (error) {
            return null;
        }
    }

    function sizeCanvas(canvas) {
        const ratio = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        const width = Math.max(Math.floor(rect.width), 280);
        const height = Math.max(Math.floor(rect.height), 200);

        canvas.width = Math.floor(width * ratio);
        canvas.height = Math.floor(height * ratio);

        const context = canvas.getContext("2d");

        context.setTransform(ratio, 0, 0, ratio, 0, 0);

        return {
            context,
            width,
            height,
        };
    }

    function cssColor(styles, token, fallback) {
        return styles.getPropertyValue(token).trim() || fallback;
    }

    function drawDonut(canvas, payload) {
        const data = (
            payload.status_distribution || []
        ).filter(item => Number(item.count) > 0);
        const total = data.reduce(
            (sum, item) => sum + Number(item.count),
            0,
        );
        const sized = sizeCanvas(canvas);
        const ctx = sized.context;
        const cx = sized.width / 2;
        const cy = sized.height / 2;
        const radius = Math.min(
            sized.width,
            sized.height,
        ) * 0.34;
        let angle = -Math.PI / 2;

        ctx.clearRect(
            0,
            0,
            sized.width,
            sized.height,
        );

        data.forEach((item, index) => {
            const slice = total
                ? (
                    Number(item.count)
                    / total
                ) * Math.PI * 2
                : 0;

            ctx.beginPath();
            ctx.strokeStyle = (
                fallbackPalette[
                    index % fallbackPalette.length
                ]
            );
            ctx.lineWidth = Math.max(
                radius * 0.28,
                18,
            );
            ctx.arc(
                cx,
                cy,
                radius,
                angle,
                angle + slice,
            );
            ctx.stroke();
            angle += slice;
        });

        const styles = getComputedStyle(document.body);

        ctx.fillStyle = cssColor(
            styles,
            "--zds-color-text",
            "#f7faf5",
        );
        ctx.textAlign = "center";
        ctx.font = "700 28px system-ui";
        ctx.fillText(
            String(total),
            cx,
            cy + 4,
        );

        ctx.fillStyle = cssColor(
            styles,
            "--zds-color-text-muted",
            "#94a49a",
        );
        ctx.font = "12px system-ui";
        ctx.fillText(
            "Всего",
            cx,
            cy + 26,
        );
    }

    function formatAxisValue(value) {
        return new Intl.NumberFormat(
            "ru-RU",
            {
                notation: "compact",
                maximumFractionDigits: 1,
            },
        ).format(value);
    }

    function resolveLabelEvery(
        dataLength,
        width,
    ) {
        if (dataLength <= 1) return 1;

        const visibleLabels = Math.max(
            Math.floor(width / 72),
            2,
        );

        return Math.max(
            Math.ceil(
                dataLength / visibleLabels,
            ),
            1,
        );
    }

    function resolveBarTone(
        item,
        todayKey,
        styles,
    ) {
        const dayKey = String(
            item.day || "",
        ).slice(0, 10);

        if (
            todayKey
            && dayKey
            && dayKey < todayKey
        ) {
            return cssColor(
                styles,
                "--zds-color-danger",
                "#e86767",
            );
        }

        if (
            todayKey
            && dayKey === todayKey
        ) {
            return cssColor(
                styles,
                "--zds-color-warning",
                "#e3b341",
            );
        }

        return cssColor(
            styles,
            "--zds-color-success",
            "#39b96a",
        );
    }

    function drawRoundedBar(
        ctx,
        x,
        y,
        width,
        height,
        radius,
    ) {
        const safeHeight = Math.max(
            height,
            2,
        );
        const safeRadius = Math.min(
            radius,
            width / 2,
            safeHeight / 2,
        );

        ctx.beginPath();
        ctx.moveTo(
            x,
            y + safeRadius,
        );
        ctx.quadraticCurveTo(
            x,
            y,
            x + safeRadius,
            y,
        );
        ctx.lineTo(
            x + width - safeRadius,
            y,
        );
        ctx.quadraticCurveTo(
            x + width,
            y,
            x + width,
            y + safeRadius,
        );
        ctx.lineTo(
            x + width,
            y + safeHeight,
        );
        ctx.lineTo(
            x,
            y + safeHeight,
        );
        ctx.closePath();
        ctx.fill();
    }

    function drawTrendLine(
        ctx,
        points,
        color,
    ) {
        if (points.length < 2) return;

        ctx.save();
        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.25;
        ctx.setLineDash([5, 4]);
        ctx.lineJoin = "round";
        ctx.lineCap = "round";

        points.forEach((point, index) => {
            if (index === 0) {
                ctx.moveTo(
                    point.x,
                    point.y,
                );
            } else {
                ctx.lineTo(
                    point.x,
                    point.y,
                );
            }
        });

        ctx.stroke();
        ctx.restore();
    }

    function drawBarValue(
        ctx,
        value,
        x,
        y,
        color,
    ) {
        if (value <= 0) return;

        ctx.save();
        ctx.fillStyle = color;
        ctx.font = "10px system-ui";
        ctx.textAlign = "center";
        ctx.fillText(
            formatAxisValue(value),
            x,
            Math.max(
                y - 7,
                12,
            ),
        );
        ctx.restore();
    }

    function drawBars(
        canvas,
        payload,
    ) {
        const data = payload.payment_series || [];
        const sized = sizeCanvas(canvas);
        const ctx = sized.context;
        const padding = {
            left: 58,
            right: 18,
            top: 22,
            bottom: 38,
        };
        const width = Math.max(
            sized.width
            - padding.left
            - padding.right,
            1,
        );
        const height = Math.max(
            sized.height
            - padding.top
            - padding.bottom,
            1,
        );
        const values = data.map(
            item => Number(
                item.amount || 0,
            ),
        );
        const max = Math.max(
            ...values,
            1,
        );
        const cumulativeValues = [];
        let cumulativeTotal = 0;

        values.forEach(value => {
            cumulativeTotal += value;
            cumulativeValues.push(
                cumulativeTotal,
            );
        });

        const cumulativeMax = Math.max(
            cumulativeTotal,
            1,
        );
        const nonZeroCount = values.filter(
            value => value > 0,
        ).length;
        const styles = getComputedStyle(
            document.body,
        );
        const gridColor = cssColor(
            styles,
            "--zds-color-border",
            "#42564a",
        );
        const mutedColor = cssColor(
            styles,
            "--zds-color-text-muted",
            "#94a49a",
        );
        const trendColor = cssColor(
            styles,
            "--zds-color-text-soft",
            "#c4cec7",
        );
        const todayKey = (
            canvas.dataset.today || ""
        );
        const slotWidth = (
            width
            / Math.max(
                data.length,
                1,
            )
        );
        const barWidth = Math.max(
            Math.min(
                slotWidth * 0.58,
                34,
            ),
            3,
        );
        const labelEvery = resolveLabelEvery(
            data.length,
            width,
        );
        const trendPoints = [];

        ctx.clearRect(
            0,
            0,
            sized.width,
            sized.height,
        );
        ctx.strokeStyle = gridColor;
        ctx.fillStyle = mutedColor;
        ctx.font = "11px system-ui";
        ctx.textAlign = "left";

        for (
            let line = 0;
            line <= 4;
            line += 1
        ) {
            const y = (
                padding.top
                + (
                    height / 4
                ) * line
            );

            ctx.beginPath();
            ctx.moveTo(
                padding.left,
                y,
            );
            ctx.lineTo(
                padding.left + width,
                y,
            );
            ctx.stroke();

            const label = (
                max
                * (
                    1 - line / 4
                )
            );

            ctx.fillText(
                formatAxisValue(label),
                4,
                y + 4,
            );
        }

        data.forEach(
            (item, index) => {
                const value = Number(
                    item.amount || 0,
                );
                const rawHeight = (
                    value / max
                ) * height;
                const barHeight = Math.max(
                    rawHeight,
                    value > 0 ? 3 : 0,
                );
                const x = (
                    padding.left
                    + index * slotWidth
                    + (
                        slotWidth
                        - barWidth
                    ) / 2
                );
                const y = (
                    padding.top
                    + height
                    - barHeight
                );

                ctx.fillStyle = resolveBarTone(
                    item,
                    todayKey,
                    styles,
                );

                if (value > 0) {
                    drawRoundedBar(
                        ctx,
                        x,
                        y,
                        barWidth,
                        barHeight,
                        Math.min(
                            barWidth * 0.34,
                            5,
                        ),
                    );

                    if (
                        nonZeroCount <= 6
                        || slotWidth >= 70
                    ) {
                        drawBarValue(
                            ctx,
                            value,
                            x + barWidth / 2,
                            y,
                            mutedColor,
                        );
                    }
                }

                trendPoints.push(
                    {
                        x: x + barWidth / 2,
                        y: (
                            padding.top
                            + height
                            - (
                                cumulativeValues[index]
                                / cumulativeMax
                            ) * height
                        ),
                    },
                );

                const isLast = (
                    index
                    === data.length - 1
                );
                const showLabel = (
                    index % labelEvery === 0
                    || isLast
                );

                if (showLabel) {
                    ctx.fillStyle = mutedColor;
                    ctx.textAlign = "center";
                    ctx.fillText(
                        item.label || "",
                        x + barWidth / 2,
                        padding.top
                        + height
                        + 23,
                    );
                }
            },
        );

        drawTrendLine(
            ctx,
            trendPoints,
            trendColor,
        );
    }

    function renderCharts() {
        document
            .querySelectorAll(
                "[data-enterprise-chart]",
            )
            .forEach(canvas => {
                const payload = parseSource(
                    canvas.dataset.source,
                );

                if (!payload) return;

                if (
                    canvas.dataset.enterpriseChart
                    === "donut"
                ) {
                    drawDonut(
                        canvas,
                        payload,
                    );
                }

                if (
                    canvas.dataset.enterpriseChart
                    === "bars"
                ) {
                    drawBars(
                        canvas,
                        payload,
                    );
                }
            });
    }

    function registryToastIcon(tone) {
        if (tone === "success") {
            return (
                '<svg viewBox="0 0 24 24" focusable="false">'
                + '<path d="M5 12.5 9.2 17 19 7"></path>'
                + "</svg>"
            );
        }

        return (
            '<svg viewBox="0 0 24 24" focusable="false">'
            + '<circle cx="12" cy="12" r="9"></circle>'
            + '<path d="M12 7V13"></path>'
            + '<path d="M12 16.5H12.01"></path>'
            + "</svg>"
        );
    }

    function ensureRegistryToastRegion() {
        let region = document.querySelector(
            "[data-toast-region]",
        );

        if (region) {
            return region;
        }

        region = document.createElement("div");
        region.className = "messages z-toast-region";
        region.dataset.toastRegion = "";
        region.setAttribute("aria-live", "polite");
        region.setAttribute("aria-atomic", "false");
        region.setAttribute(
            "aria-label",
            "Системные уведомления",
        );
        document.body.appendChild(region);

        return region;
    }

    function pushRegistryToast(message, tone) {
        const region = ensureRegistryToastRegion();
        const toast = document.createElement("div");
        const normalizedTone = tone || "info";

        toast.className = (
            "z-toast tone-"
            + normalizedTone
        );
        toast.dataset.toast = "";
        toast.dataset.toastTimeout = (
            normalizedTone === "error"
            ? "0"
            : "7000"
        );
        toast.setAttribute(
            "role",
            normalizedTone === "error"
            ? "alert"
            : "status",
        );

        const icon = document.createElement("span");
        icon.className = "z-toast-icon";
        icon.setAttribute("aria-hidden", "true");
        icon.innerHTML = registryToastIcon(
            normalizedTone,
        );

        const copy = document.createElement("span");
        copy.className = "z-toast-message";
        copy.textContent = message;

        const close = document.createElement("button");
        close.type = "button";
        close.className = "z-toast-close";
        close.dataset.toastClose = "";
        close.setAttribute(
            "aria-label",
            "Закрыть уведомление",
        );
        close.setAttribute("title", "Закрыть");
        close.innerHTML = (
            '<svg viewBox="0 0 24 24" '
            + 'aria-hidden="true" focusable="false">'
            + '<path d="M7 7 17 17"></path>'
            + '<path d="M17 7 7 17"></path>'
            + "</svg>"
        );

        toast.append(icon, copy, close);
        region.appendChild(toast);

        close.addEventListener(
            "click",
            () => toast.remove(),
        );

        if (normalizedTone !== "error") {
            window.setTimeout(
                () => {
                    toast.classList.add("is-leaving");
                    window.setTimeout(
                        () => toast.remove(),
                        180,
                    );
                },
                7000,
            );
        }
    }

    function exportFilename(response, fallback) {
        const disposition = (
            response.headers.get(
                "Content-Disposition",
            )
            || ""
        );
        const utfMatch = disposition.match(
            /filename\*=UTF-8''([^;]+)/i,
        );

        if (utfMatch) {
            return decodeURIComponent(
                utfMatch[1],
            );
        }

        const plainMatch = disposition.match(
            /filename="?([^";]+)"?/i,
        );

        return plainMatch
            ? plainMatch[1]
            : fallback;
    }

    function triggerRegistryDownload(blob, filename) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");

        link.href = url;
        link.download = filename;
        link.hidden = true;
        document.body.appendChild(link);
        link.click();
        link.remove();

        window.setTimeout(
            () => URL.revokeObjectURL(url),
            1000,
        );
    }

    function setRegistryExportPending(form, pending) {
        const button = form.querySelector(
            "[data-registry-export-submit]",
        );

        form.dataset.exportPending = (
            pending
            ? "true"
            : "false"
        );

        if (!button) {
            return;
        }

        if (!button.dataset.originalLabel) {
            button.dataset.originalLabel = (
                button.textContent.trim()
            );
        }

        button.disabled = pending;
        button.setAttribute(
            "aria-busy",
            pending
            ? "true"
            : "false",
        );

        const modal = form.closest(
            "[data-modal]",
        );

        if (modal) {
            modal
                .querySelectorAll(
                    "[data-modal-close]",
                )
                .forEach(control => {
                    control.disabled = pending;
                });
        }

        button.textContent = (
            pending
            ? (
                button.dataset.loadingLabel
                || "Формируем файл…"
            )
            : button.dataset.originalLabel
        );
    }

    async function submitRegistryExport(form) {
        if (
            form.dataset.exportPending
            === "true"
        ) {
            return;
        }

        setRegistryExportPending(form, true);

        const format = (
            form.dataset.exportFormat
            || "файл"
        );
        const registryId = (
            form.dataset.exportRegistry
            || ""
        );

        try {
            const response = await fetch(
                form.action,
                {
                    method: "POST",
                    body: new FormData(form),
                    credentials: "same-origin",
                    headers: {
                        "X-Requested-With":
                            "XMLHttpRequest",
                    },
                },
            );

            if (response.redirected) {
                window.location.assign(
                    response.url,
                );
                return;
            }

            const contentType = (
                response.headers.get(
                    "Content-Type",
                )
                || ""
            );

            if (
                !response.ok
                || contentType.includes(
                    "text/html",
                )
            ) {
                throw new Error(
                    "Сервер не сформировал файл.",
                );
            }

            const blob = await response.blob();
            const extension = (
                format === "Excel"
                ? "xlsx"
                : "txt"
            );
            const fallback = (
                "payment_registry_"
                + registryId
                + "."
                + extension
            );
            const filename = exportFilename(
                response,
                fallback,
            );

            triggerRegistryDownload(
                blob,
                filename,
            );

            setRegistryExportPending(
                form,
                false,
            );

            const modal = form.closest(
                "[data-modal]",
            );
            const closer = modal
                ? modal.querySelector(
                    "[data-modal-close]",
                )
                : null;

            if (closer) {
                closer.click();
            }

            pushRegistryToast(
                (
                    "Файл "
                    + format
                    + " сформирован. "
                    + "Обновляем состояние реестра…"
                ),
                "success",
            );

            window.setTimeout(
                () => window.location.reload(),
                900,
            );
        } catch (error) {
            setRegistryExportPending(
                form,
                false,
            );
            pushRegistryToast(
                (
                    error instanceof Error
                    ? error.message
                    : "Не удалось сформировать файл."
                ),
                "error",
            );
        }
    }

    function initRegistryExportForms() {
        document
            .querySelectorAll(
                "[data-registry-export-form]",
            )
            .forEach(form => {
                form.addEventListener(
                    "submit",
                    event => {
                        event.preventDefault();
                        submitRegistryExport(form);
                    },
                );
            });
    }

    document
        .querySelectorAll(
            "[data-submit-lock]",
        )
        .forEach(form => {
            form.addEventListener(
                "submit",
                event => {
                    if (
                        form.dataset.submitted
                        === "true"
                    ) {
                        event.preventDefault();
                        return;
                    }

                    form.dataset.submitted = "true";

                    const button = form.querySelector(
                        "[data-submit-button]",
                    );

                    if (button) {
                        button.disabled = true;
                        button.textContent = (
                            button.dataset.loadingLabel
                            || "Отправка..."
                        );
                    }
                },
            );
        });

    let resizeTimer = null;

    window.addEventListener(
        "resize",
        () => {
            window.clearTimeout(
                resizeTimer,
            );
            resizeTimer = window.setTimeout(
                renderCharts,
                120,
            );
        },
    );

    document.addEventListener(
        "DOMContentLoaded",
        () => {
            renderCharts();
            initRegistryExportForms();
        },
    );
})();
