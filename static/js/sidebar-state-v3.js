(function () {
    "use strict";

    var root = document.documentElement;
    var storageKey = "zarya.sidebar.collapsed.v1";
    var stateClass = "sidebar-is-collapsed";
    var stateAttribute = "data-sidebar-collapsed";
    var desktopQuery = window.matchMedia(
        "(min-width: 981px)"
    );

    function readStoredState() {
        try {
            return (
                window.localStorage.getItem(
                    storageKey
                ) === "1"
            );
        } catch (error) {
            return false;
        }
    }

    function writeStoredState(collapsed) {
        try {
            window.localStorage.setItem(
                storageKey,
                collapsed ? "1" : "0"
            );
        } catch (error) {
            return;
        }
    }

    function applyRootState(collapsed) {
        var shouldCollapse = (
            desktopQuery.matches
            && collapsed
        );

        root.classList.toggle(
            stateClass,
            shouldCollapse
        );

        root.setAttribute(
            stateAttribute,
            shouldCollapse ? "true" : "false"
        );

        return shouldCollapse;
    }

    applyRootState(
        readStoredState()
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

        var toggle = document.getElementById(
            "sidebar-desktop-toggle"
        );

        if (!sidebar || !toggle) {
            return;
        }

        var collapseLabel = (
            toggle.getAttribute(
                "data-collapse-label"
            )
            || "Свернуть меню"
        );

        var expandLabel = (
            toggle.getAttribute(
                "data-expand-label"
            )
            || "Развернуть меню"
        );

        function labelSidebarLinks() {
            var links = sidebar.querySelectorAll(
                [
                    "a.nav-link",
                    "a.sidebar-user-action"
                ].join(",")
            );

            Array.prototype.forEach.call(
                links,
                function (link) {
                    var labelNode = (
                        link.querySelector(
                            ".nav-label"
                        )
                        || link.querySelector(
                            "span:last-child"
                        )
                    );

                    if (!labelNode) {
                        return;
                    }

                    var label = (
                        labelNode.textContent
                        || ""
                    ).trim();

                    if (!label) {
                        return;
                    }

                    link.setAttribute(
                        "data-sidebar-label",
                        label
                    );

                    if (
                        !link.hasAttribute(
                            "title"
                        )
                    ) {
                        link.setAttribute(
                            "title",
                            label
                        );
                    }

                    if (
                        link.classList.contains(
                            "is-active"
                        )
                        || link.classList.contains(
                            "active"
                        )
                    ) {
                        link.setAttribute(
                            "aria-current",
                            "page"
                        );
                    }
                }
            );
        }

        function requestLayoutRefresh() {
            window.requestAnimationFrame(
                function () {
                    window.dispatchEvent(
                        new Event("resize")
                    );
                }
            );
        }

        function updateControls(collapsed) {
            var label = (
                collapsed
                ? expandLabel
                : collapseLabel
            );

            sidebar.setAttribute(
                stateAttribute,
                collapsed ? "true" : "false"
            );

            toggle.setAttribute(
                "aria-expanded",
                collapsed ? "false" : "true"
            );

            toggle.setAttribute(
                "aria-label",
                label
            );

            toggle.setAttribute(
                "title",
                label
            );
        }

        function setCollapsed(
            collapsed,
            persist
        ) {
            var applied = applyRootState(
                collapsed
            );

            updateControls(
                applied
            );

            if (
                persist
                && desktopQuery.matches
            ) {
                writeStoredState(
                    applied
                );
            }

            requestLayoutRefresh();
        }

        labelSidebarLinks();

        sidebar.setAttribute(
            "data-sidebar-ready",
            "v3"
        );

        setCollapsed(
            readStoredState(),
            false
        );

        toggle.addEventListener(
            "click",
            function () {
                setCollapsed(
                    !root.classList.contains(
                        stateClass
                    ),
                    true
                );
            }
        );

        function handleDesktopChange() {
            setCollapsed(
                readStoredState(),
                false
            );
        }

        if (
            typeof desktopQuery.addEventListener
            === "function"
        ) {
            desktopQuery.addEventListener(
                "change",
                handleDesktopChange
            );
        } else if (
            typeof desktopQuery.addListener
            === "function"
        ) {
            desktopQuery.addListener(
                handleDesktopChange
            );
        }

        window.addEventListener(
            "storage",
            function (event) {
                if (
                    event.key !== storageKey
                ) {
                    return;
                }

                setCollapsed(
                    event.newValue === "1",
                    false
                );
            }
        );
    });
})();
