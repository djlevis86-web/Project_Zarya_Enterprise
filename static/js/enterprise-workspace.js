(function () {
    "use strict";

    const palette = ["#39b96a", "#5f9fe8", "#e3b341", "#78c442", "#e86767", "#94a49a"];

    function parseSource(id) {
        const node = document.getElementById(id);
        if (!node) return null;
        try { return JSON.parse(node.textContent); } catch (error) { return null; }
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
        return { context, width, height };
    }

    function drawDonut(canvas, payload) {
        const data = (payload.status_distribution || []).filter(item => Number(item.count) > 0);
        const total = data.reduce((sum, item) => sum + Number(item.count), 0);
        const sized = sizeCanvas(canvas);
        const ctx = sized.context;
        const cx = sized.width / 2;
        const cy = sized.height / 2;
        const radius = Math.min(sized.width, sized.height) * 0.34;
        let angle = -Math.PI / 2;
        ctx.clearRect(0, 0, sized.width, sized.height);
        data.forEach((item, index) => {
            const slice = total ? (Number(item.count) / total) * Math.PI * 2 : 0;
            ctx.beginPath(); ctx.strokeStyle = palette[index % palette.length]; ctx.lineWidth = Math.max(radius * 0.28, 18); ctx.arc(cx, cy, radius, angle, angle + slice); ctx.stroke(); angle += slice;
        });
        ctx.fillStyle = getComputedStyle(document.body).getPropertyValue("--zds-color-text").trim() || "#f7faf5";
        ctx.textAlign = "center"; ctx.font = "700 28px system-ui"; ctx.fillText(String(total), cx, cy + 4);
        ctx.fillStyle = getComputedStyle(document.body).getPropertyValue("--zds-color-text-muted").trim() || "#94a49a";
        ctx.font = "12px system-ui"; ctx.fillText("Всего", cx, cy + 26);
    }

    function drawBars(canvas, payload) {
        const data = payload.payment_series || [];
        const sized = sizeCanvas(canvas);
        const ctx = sized.context;
        const padding = { left: 48, right: 16, top: 18, bottom: 34 };
        const width = sized.width - padding.left - padding.right;
        const height = sized.height - padding.top - padding.bottom;
        const values = data.map(item => Number(item.amount || 0));
        const max = Math.max(...values, 1);
        ctx.clearRect(0, 0, sized.width, sized.height);
        ctx.strokeStyle = getComputedStyle(document.body).getPropertyValue("--zds-color-border-strong").trim() || "#42564a";
        ctx.fillStyle = getComputedStyle(document.body).getPropertyValue("--zds-color-text-muted").trim() || "#94a49a";
        ctx.font = "11px system-ui";
        for (let line = 0; line <= 4; line += 1) {
            const y = padding.top + (height / 4) * line;
            ctx.beginPath(); ctx.moveTo(padding.left, y); ctx.lineTo(padding.left + width, y); ctx.stroke();
            const label = Math.round(max * (1 - line / 4));
            ctx.fillText(String(label), 4, y + 4);
        }
        const gap = 10;
        const barWidth = Math.max((width - gap * Math.max(data.length - 1, 0)) / Math.max(data.length, 1), 12);
        data.forEach((item, index) => {
            const value = Number(item.amount || 0);
            const barHeight = (value / max) * height;
            const x = padding.left + index * (barWidth + gap);
            const y = padding.top + height - barHeight;
            const gradient = ctx.createLinearGradient(0, y, 0, padding.top + height);
            gradient.addColorStop(0, palette[0]); gradient.addColorStop(1, palette[1]);
            ctx.fillStyle = gradient; ctx.fillRect(x, y, barWidth, barHeight);
            ctx.fillStyle = getComputedStyle(document.body).getPropertyValue("--zds-color-text-muted").trim() || "#94a49a";
            ctx.textAlign = "center"; ctx.fillText(item.label || "", x + barWidth / 2, padding.top + height + 20);
        });
    }

    function renderCharts() {
        document.querySelectorAll("[data-enterprise-chart]").forEach(canvas => {
            const payload = parseSource(canvas.dataset.source);
            if (!payload) return;
            if (canvas.dataset.enterpriseChart === "donut") drawDonut(canvas, payload);
            if (canvas.dataset.enterpriseChart === "bars") drawBars(canvas, payload);
        });
    }

    document.querySelectorAll("[data-submit-lock]").forEach(form => {
        form.addEventListener("submit", event => {
            if (form.dataset.submitted === "true") { event.preventDefault(); return; }
            form.dataset.submitted = "true";
            const button = form.querySelector("[data-submit-button]");
            if (button) { button.disabled = true; button.textContent = button.dataset.loadingLabel || "Отправка..."; }
        });
    });

    let resizeTimer = null;
    window.addEventListener("resize", () => { window.clearTimeout(resizeTimer); resizeTimer = window.setTimeout(renderCharts, 120); });
    document.addEventListener("DOMContentLoaded", renderCharts);
})();
