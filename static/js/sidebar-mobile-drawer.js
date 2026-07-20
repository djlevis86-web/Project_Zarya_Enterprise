(function () {
    "use strict";

    function ready(callback) {
        if (document.readyState === "loading") {
            document.addEventListener(
                "DOMContentLoaded",
                callback
            );
        } else {
            callback();
        }
    }

    ready(function () {
        var body = document.body;
        var sidebar = document.getElementById(
            "app-sidebar"
        );
        var toggle = document.getElementById(
            "sidebar-mobile-toggle"
        );
        var closeControls = document.querySelectorAll(
            "[data-sidebar-close]"
        );
        var mobileQuery = window.matchMedia(
            "(max-width: 980px)"
        );
        var previousFocus = null;

        if (!body || !sidebar || !toggle) {
            return;
        }

        function isOpen() {
            return body.classList.contains(
                "sidebar-mobile-open"
            );
        }

        function setExpanded(expanded) {
            toggle.setAttribute(
                "aria-expanded",
                expanded ? "true" : "false"
            );
        }

        function getFocusableElements() {
            return Array.prototype.slice.call(
                sidebar.querySelectorAll(
                    [
                        "a[href]",
                        "button:not([disabled])",
                        "input:not([disabled])",
                        "select:not([disabled])",
                        "textarea:not([disabled])",
                        '[tabindex]:not([tabindex="-1"])'
                    ].join(",")
                )
            );
        }

        function openSidebar() {
            if (!mobileQuery.matches) {
                return;
            }

            previousFocus = document.activeElement;

            body.classList.add(
                "sidebar-mobile-open"
            );

            sidebar.setAttribute(
                "aria-hidden",
                "false"
            );

            setExpanded(
                true
            );

            var closeButton = sidebar.querySelector(
                "[data-sidebar-close]"
            );

            if (closeButton) {
                window.requestAnimationFrame(
                    function () {
                        closeButton.focus();
                    }
                );
            }
        }

        function closeSidebar(restoreFocus) {
            body.classList.remove(
                "sidebar-mobile-open"
            );

            setExpanded(
                false
            );

            if (mobileQuery.matches) {
                sidebar.setAttribute(
                    "aria-hidden",
                    "true"
                );
            } else {
                sidebar.removeAttribute(
                    "aria-hidden"
                );
            }

            if (
                restoreFocus !== false
                && previousFocus
                && typeof previousFocus.focus === "function"
            ) {
                previousFocus.focus();
            }

            previousFocus = null;
        }

        function syncLayout() {
            if (mobileQuery.matches) {
                if (!isOpen()) {
                    sidebar.setAttribute(
                        "aria-hidden",
                        "true"
                    );
                }

                setExpanded(
                    isOpen()
                );

                return;
            }

            closeSidebar(
                false
            );

            sidebar.removeAttribute(
                "aria-hidden"
            );
        }

        function trapFocus(event) {
            if (
                event.key !== "Tab"
                || !mobileQuery.matches
                || !isOpen()
            ) {
                return;
            }

            var focusable = getFocusableElements();

            if (!focusable.length) {
                event.preventDefault();
                sidebar.focus();
                return;
            }

            var first = focusable[0];
            var last = focusable[
                focusable.length - 1
            ];

            if (
                event.shiftKey
                && document.activeElement === first
            ) {
                event.preventDefault();
                last.focus();
                return;
            }

            if (
                !event.shiftKey
                && document.activeElement === last
            ) {
                event.preventDefault();
                first.focus();
            }
        }

        toggle.addEventListener(
            "click",
            function () {
                if (isOpen()) {
                    closeSidebar(
                        true
                    );
                } else {
                    openSidebar();
                }
            }
        );

        closeControls.forEach(
            function (control) {
                control.addEventListener(
                    "click",
                    function () {
                        closeSidebar(
                            true
                        );
                    }
                );
            }
        );

        sidebar.querySelectorAll(
            "a.nav-link"
        ).forEach(
            function (link) {
                link.addEventListener(
                    "click",
                    function () {
                        if (mobileQuery.matches) {
                            closeSidebar(
                                false
                            );
                        }
                    }
                );
            }
        );

        document.addEventListener(
            "keydown",
            function (event) {
                if (
                    event.key === "Escape"
                    && isOpen()
                ) {
                    event.preventDefault();

                    closeSidebar(
                        true
                    );

                    return;
                }

                trapFocus(
                    event
                );
            }
        );

        if (
            typeof mobileQuery.addEventListener
            === "function"
        ) {
            mobileQuery.addEventListener(
                "change",
                syncLayout
            );
        } else {
            mobileQuery.addListener(
                syncLayout
            );
        }

        syncLayout();
    });
})();
