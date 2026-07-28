(function () {
    "use strict";

    var root = document.documentElement;
    var desktopQuery = window.matchMedia(
        "(min-width: 981px)"
    );

    function ready(callback) {
        if (
            document.readyState === "loading"
        ) {
            document.addEventListener(
                "DOMContentLoaded",
                callback
            );
            return;
        }

        callback();
    }

    ready(function () {
        var sidebar = document.getElementById(
            "app-sidebar"
        );

        if (!sidebar) {
            return;
        }

        var tooltip = document.createElement(
            "div"
        );

        tooltip.id = "sidebar-tooltip-v3";
        tooltip.className = "sidebar-tooltip-v3";
        tooltip.setAttribute(
            "role",
            "tooltip"
        );
        tooltip.setAttribute(
            "aria-hidden",
            "true"
        );

        document.body.appendChild(
            tooltip
        );

        var activeTarget = null;

        function isCollapsedDesktop() {
            return (
                desktopQuery.matches
                && root.classList.contains(
                    "sidebar-is-collapsed"
                )
            );
        }

        function positionTooltip(target) {
            var targetRect = (
                target.getBoundingClientRect()
            );

            var tooltipRect = (
                tooltip.getBoundingClientRect()
            );

            var top = (
                targetRect.top
                + (
                    targetRect.height
                    - tooltipRect.height
                )
                / 2
            );

            var viewportPadding = 12;

            top = Math.max(
                viewportPadding,
                Math.min(
                    top,
                    window.innerHeight
                    - tooltipRect.height
                    - viewportPadding
                )
            );

            tooltip.style.left = (
                targetRect.right
                + 12
                + "px"
            );

            tooltip.style.top = (
                top
                + "px"
            );
        }

        function hideTooltip() {
            if (activeTarget) {
                activeTarget.removeAttribute(
                    "aria-describedby"
                );
            }

            activeTarget = null;

            tooltip.setAttribute(
                "aria-hidden",
                "true"
            );

            tooltip.removeAttribute(
                "data-visible"
            );
        }

        function showTooltip(target) {
            if (!isCollapsedDesktop()) {
                hideTooltip();
                return;
            }

            var label = (
                target.getAttribute(
                    "data-sidebar-label"
                )
                || target.getAttribute(
                    "aria-label"
                )
                || target.getAttribute(
                    "title"
                )
                || ""
            ).trim();

            if (!label) {
                hideTooltip();
                return;
            }

            activeTarget = target;
            tooltip.textContent = label;

            target.setAttribute(
                "aria-describedby",
                tooltip.id
            );

            tooltip.setAttribute(
                "aria-hidden",
                "false"
            );

            tooltip.setAttribute(
                "data-visible",
                "true"
            );

            window.requestAnimationFrame(
                function () {
                    if (
                        activeTarget
                        !== target
                    ) {
                        return;
                    }

                    positionTooltip(
                        target
                    );
                }
            );
        }

        var targets = sidebar.querySelectorAll(
            [
                "a.nav-link",
                "a.sidebar-user-action",
                "#sidebar-desktop-toggle"
            ].join(",")
        );

        Array.prototype.forEach.call(
            targets,
            function (target) {
                target.addEventListener(
                    "mouseenter",
                    function () {
                        showTooltip(
                            target
                        );
                    }
                );

                target.addEventListener(
                    "mouseleave",
                    hideTooltip
                );

                target.addEventListener(
                    "focus",
                    function () {
                        showTooltip(
                            target
                        );
                    }
                );

                target.addEventListener(
                    "blur",
                    hideTooltip
                );
            }
        );

        sidebar.addEventListener(
            "scroll",
            hideTooltip,
            true
        );

        window.addEventListener(
            "resize",
            hideTooltip
        );

        document.addEventListener(
            "keydown",
            function (event) {
                if (
                    event.key
                    === "Escape"
                ) {
                    hideTooltip();
                }
            }
        );

        var observer = new MutationObserver(
            function () {
                if (!isCollapsedDesktop()) {
                    hideTooltip();
                }
            }
        );

        observer.observe(
            root,
            {
                attributes: true,
                attributeFilter: [
                    "class",
                    "data-sidebar-collapsed"
                ]
            }
        );
    });
})();
