"use strict";

(() => {
    const menuSelector = "[data-invoice-detail-action-menu]";
    const triggerSelector = "[data-invoice-detail-action-trigger]";
    const panelSelector = "[data-invoice-detail-action-panel]";
    const itemSelector = '[role="menuitem"]';

    const menus = Array.from(
        document.querySelectorAll(menuSelector)
    );

    if (menus.length === 0) {
        return;
    }

    const getItems = (menu) => {
        const panel = menu.querySelector(panelSelector);

        if (!panel) {
            return [];
        }

        return Array.from(
            panel.querySelectorAll(itemSelector)
        ).filter(
            (item) => (
                !item.disabled
                && item.getAttribute("aria-disabled") !== "true"
            )
        );
    };

    const updateExpandedState = (menu) => {
        const trigger = menu.querySelector(triggerSelector);

        if (!trigger) {
            return;
        }

        trigger.setAttribute(
            "aria-expanded",
            menu.open ? "true" : "false"
        );
    };

    const closeMenu = (menu, restoreFocus = false) => {
        if (!menu.open) {
            return;
        }

        menu.open = false;
        updateExpandedState(menu);

        if (restoreFocus) {
            const trigger = menu.querySelector(triggerSelector);

            if (trigger) {
                trigger.focus();
            }
        }
    };

    const closeOtherMenus = (currentMenu) => {
        for (const menu of menus) {
            if (menu !== currentMenu) {
                closeMenu(menu);
            }
        }
    };

    const openAndFocus = (menu, edge) => {
        closeOtherMenus(menu);
        menu.open = true;
        updateExpandedState(menu);

        const items = getItems(menu);

        if (items.length === 0) {
            return;
        }

        const target = (
            edge === "last"
            ? items[items.length - 1]
            : items[0]
        );

        target.focus();
    };

    for (const menu of menus) {
        const trigger = menu.querySelector(triggerSelector);
        const panel = menu.querySelector(panelSelector);

        if (!trigger || !panel) {
            continue;
        }

        updateExpandedState(menu);

        menu.addEventListener("toggle", () => {
            if (menu.open) {
                closeOtherMenus(menu);
            }

            updateExpandedState(menu);
        });

        trigger.addEventListener("keydown", (event) => {
            if (
                event.key === "ArrowDown"
                || event.key === "Home"
            ) {
                event.preventDefault();
                openAndFocus(menu, "first");
                return;
            }

            if (
                event.key === "ArrowUp"
                || event.key === "End"
            ) {
                event.preventDefault();
                openAndFocus(menu, "last");
            }
        });

        panel.addEventListener("keydown", (event) => {
            const items = getItems(menu);

            if (items.length === 0) {
                return;
            }

            if (event.key === "Escape") {
                event.preventDefault();
                closeMenu(menu, true);
                return;
            }

            if (event.key === "Tab") {
                closeMenu(menu);
                return;
            }

            const currentIndex = items.indexOf(
                document.activeElement
            );

            if (
                event.key === "Home"
                || event.key === "End"
            ) {
                event.preventDefault();

                const target = (
                    event.key === "End"
                    ? items[items.length - 1]
                    : items[0]
                );

                target.focus();
                return;
            }

            if (
                event.key !== "ArrowDown"
                && event.key !== "ArrowUp"
            ) {
                return;
            }

            event.preventDefault();

            const direction = (
                event.key === "ArrowDown"
                ? 1
                : -1
            );

            const fallbackIndex = (
                direction > 0
                ? -1
                : 0
            );

            const nextIndex = (
                currentIndex === -1
                ? fallbackIndex + direction
                : (
                    currentIndex
                    + direction
                    + items.length
                ) % items.length
            );

            items[nextIndex].focus();
        });

        menu.addEventListener("submit", (event) => {
            const form = event.target;

            if (!(form instanceof HTMLFormElement)) {
                return;
            }

            const message = (
                form.dataset.confirmMessage
                || ""
            ).trim();

            if (
                message
                && !window.confirm(message)
            ) {
                event.preventDefault();
            }
        });
    }

    document.addEventListener("pointerdown", (event) => {
        for (const menu of menus) {
            if (
                menu.open
                && !menu.contains(event.target)
            ) {
                closeMenu(menu);
            }
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape") {
            return;
        }

        for (const menu of menus) {
            if (menu.open) {
                closeMenu(menu, true);
            }
        }
    });
})();
