(() => {
    "use strict";

    const SELECTOR_FOCUSABLE = [
        "a[href]",
        "button:not([disabled])",
        "input:not([disabled]):not([type='hidden'])",
        "select:not([disabled])",
        "textarea:not([disabled])",
        "[tabindex]:not([tabindex='-1'])",
    ].join(",");

    const modalOpeners = new WeakMap();
    const drawerOpeners = new WeakMap();

    function byId(id) {
        return id ? document.getElementById(id) : null;
    }

    function visibleFocusable(container) {
        return Array.from(container.querySelectorAll(SELECTOR_FOCUSABLE)).filter(
            (element) => !element.hidden && element.getAttribute("aria-hidden") !== "true"
        );
    }

    function focusFirst(container) {
        const first = visibleFocusable(container)[0];
        if (first) {
            window.requestAnimationFrame(() => first.focus());
        }
    }

    function overlayIsOpen() {
        return Boolean(
            document.querySelector("[data-modal][open], [data-drawer].is-open")
        );
    }

    function syncBodyLock() {
        document.body.classList.toggle("has-interaction-overlay", overlayIsOpen());
    }

    function closePopover(popover) {
        if (!popover || popover.hidden) {
            return;
        }
        popover.hidden = true;
        const trigger = document.querySelector(
            `[data-popover-toggle="${popover.id}"]`
        );
        if (trigger) {
            trigger.setAttribute("aria-expanded", "false");
        }
    }

    function closeAllPopovers(except = null) {
        document.querySelectorAll("[data-popover]").forEach((popover) => {
            if (popover !== except) {
                closePopover(popover);
            }
        });
    }

    function openPopover(popover, trigger) {
        const isOpen = !popover.hidden;
        closeAllPopovers(popover);
        if (isOpen) {
            closePopover(popover);
            return;
        }
        popover.hidden = false;
        trigger.setAttribute("aria-expanded", "true");
    }

    function closeDrawer(drawer, restoreFocus = true) {
        if (!drawer || !drawer.classList.contains("is-open")) {
            return;
        }
        drawer.classList.remove("is-open");
        drawer.setAttribute("aria-hidden", "true");
        drawer.hidden = true;
        document.querySelectorAll(`[data-drawer-open="${drawer.id}"]`).forEach(
            (trigger) => trigger.setAttribute("aria-expanded", "false")
        );
        syncBodyLock();
        if (restoreFocus) {
            const opener = drawerOpeners.get(drawer);
            if (opener && document.contains(opener)) {
                opener.focus();
            }
        }
    }

    function openDrawer(drawer, trigger) {
        closeAllPopovers();
        document.querySelectorAll("[data-drawer].is-open").forEach((current) => {
            if (current !== drawer) {
                closeDrawer(current, false);
            }
        });
        drawerOpeners.set(drawer, trigger);
        drawer.hidden = false;
        drawer.setAttribute("aria-hidden", "false");
        drawer.classList.add("is-open");
        trigger.setAttribute("aria-expanded", "true");
        syncBodyLock();
        focusFirst(drawer.querySelector(".z-drawer-panel") || drawer);
    }

    function closeModal(modal, restoreFocus = true) {
        if (!modal || !modal.hasAttribute("open")) {
            return;
        }
        if (typeof modal.close === "function") {
            modal.close();
        } else {
            modal.removeAttribute("open");
        }
        modal.setAttribute("aria-hidden", "true");
        syncBodyLock();
        if (restoreFocus) {
            const opener = modalOpeners.get(modal);
            if (opener && document.contains(opener)) {
                opener.focus();
            }
        }
    }

    function openModal(modal, trigger) {
        closeAllPopovers();
        if (trigger.hasAttribute("data-close-parent-drawer")) {
            const drawer = trigger.closest("[data-drawer]");
            closeDrawer(drawer, false);
        }
        modalOpeners.set(modal, trigger);
        modal.setAttribute("aria-hidden", "false");
        if (typeof modal.showModal === "function") {
            if (!modal.open) {
                modal.showModal();
            }
        } else {
            modal.setAttribute("open", "");
        }
        syncBodyLock();
        focusFirst(modal);
    }

    function trapDrawerFocus(event, drawer) {
        if (event.key !== "Tab") {
            return;
        }
        const focusable = visibleFocusable(drawer);
        if (!focusable.length) {
            event.preventDefault();
            return;
        }
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    }

    function dismissToast(toast) {
        if (!toast || toast.classList.contains("is-leaving")) {
            return;
        }
        toast.classList.add("is-leaving");
        window.setTimeout(() => toast.remove(), 180);
    }

    function initToasts() {
        document.querySelectorAll("[data-toast]").forEach((toast) => {
            const timeout = Number.parseInt(toast.dataset.toastTimeout || "7000", 10);
            if (Number.isFinite(timeout) && timeout > 0) {
                window.setTimeout(() => dismissToast(toast), timeout);
            }
        });
    }

    document.addEventListener("click", (event) => {
        const modalTrigger = event.target.closest("[data-modal-open]");
        if (modalTrigger) {
            const modal = byId(modalTrigger.dataset.modalOpen);
            if (modal) {
                event.preventDefault();
                openModal(modal, modalTrigger);
            }
            return;
        }

        const modalClose = event.target.closest("[data-modal-close]");
        if (modalClose) {
            event.preventDefault();
            closeModal(modalClose.closest("[data-modal]"));
            return;
        }

        const drawerTrigger = event.target.closest("[data-drawer-open]");
        if (drawerTrigger) {
            const drawer = byId(drawerTrigger.dataset.drawerOpen);
            if (drawer) {
                event.preventDefault();
                openDrawer(drawer, drawerTrigger);
            }
            return;
        }

        const drawerClose = event.target.closest("[data-drawer-close]");
        if (drawerClose) {
            event.preventDefault();
            closeDrawer(drawerClose.closest("[data-drawer]"));
            return;
        }

        const popoverTrigger = event.target.closest("[data-popover-toggle]");
        if (popoverTrigger) {
            const popover = byId(popoverTrigger.dataset.popoverToggle);
            if (popover) {
                event.preventDefault();
                event.stopPropagation();
                openPopover(popover, popoverTrigger);
            }
            return;
        }

        const valueTrigger = event.target.closest("[data-field-value-use]");
        if (valueTrigger) {
            const input = byId(valueTrigger.dataset.fieldValueTarget);
            if (input) {
                input.value = valueTrigger.dataset.fieldValue || "";
                input.dispatchEvent(new Event("input", { bubbles: true }));
                input.focus();
            }
            return;
        }

        const toastClose = event.target.closest("[data-toast-close]");
        if (toastClose) {
            dismissToast(toastClose.closest("[data-toast]"));
            return;
        }

        if (!event.target.closest("[data-popover]")) {
            closeAllPopovers();
        }
    });

    document.addEventListener("keydown", (event) => {
        const openDrawerElement = document.querySelector("[data-drawer].is-open");
        if (openDrawerElement) {
            if (event.key === "Escape") {
                event.preventDefault();
                closeDrawer(openDrawerElement);
                return;
            }
            trapDrawerFocus(event, openDrawerElement);
        }

        if (event.key === "Escape") {
            const openPopoverElement = Array.from(
                document.querySelectorAll("[data-popover]")
            ).find((popover) => !popover.hidden);
            if (openPopoverElement) {
                event.preventDefault();
                closePopover(openPopoverElement);
            }
        }
    });

    document.querySelectorAll("[data-modal]").forEach((modal) => {
        modal.setAttribute("aria-hidden", modal.open ? "false" : "true");
        modal.addEventListener("cancel", (event) => {
            event.preventDefault();
            closeModal(modal);
        });
        modal.addEventListener("click", (event) => {
            if (event.target === modal) {
                closeModal(modal);
            }
        });
        modal.addEventListener("close", syncBodyLock);
    });

    initToasts();
})();
