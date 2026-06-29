
(function () {
    "use strict";

    function ready(fn) {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", fn);
        } else {
            fn();
        }
    }

    function isValidLink(link) {
        if (!link) return false;

        var href = link.getAttribute("href");

        if (!href) return false;
        if (href.charAt(0) === "#") return false;
        if (href.indexOf("javascript:") === 0) return false;

        return true;
    }

    function moveIndicator(nav, indicator, link) {
        if (!nav || !indicator || !link) return;

        var navRect = nav.getBoundingClientRect();
        var linkRect = link.getBoundingClientRect();

        var top = linkRect.top - navRect.top;
        var height = linkRect.height;

        indicator.style.height = height + "px";
        indicator.style.transform = "translate3d(0, " + top + "px, 0)";
    }

    function initSidebarNav(nav) {
        if (!nav || nav.dataset.movingHighlightReady === "1") return;

        var links = Array.prototype.slice
            .call(nav.querySelectorAll("a.nav-link"))
            .filter(isValidLink);

        if (!links.length) return;

        var active =
            nav.querySelector("a.nav-link.is-active") ||
            nav.querySelector("a.nav-link.active") ||
            links[0];

        var indicator = nav.querySelector(".sidebar-moving-highlight");

        if (!indicator) {
            indicator = document.createElement("span");
            indicator.className = "sidebar-moving-highlight";
            indicator.setAttribute("aria-hidden", "true");
            nav.insertBefore(indicator, nav.firstChild);
        }

        nav.dataset.movingHighlightReady = "1";
        nav.classList.add("sidebar-nav-highlight-ready");

        requestAnimationFrame(function () {
            moveIndicator(nav, indicator, active);
        });

        links.forEach(function (link) {
            link.addEventListener("mouseenter", function () {
                moveIndicator(nav, indicator, link);
            });

            link.addEventListener("focus", function () {
                moveIndicator(nav, indicator, link);
            });
        });

        nav.addEventListener("mouseleave", function () {
            moveIndicator(nav, indicator, active);
        });

        window.addEventListener("resize", function () {
            moveIndicator(nav, indicator, active);
        });

        var sidebarTop = nav.closest(".sidebar-top");

        if (sidebarTop) {
            sidebarTop.addEventListener("scroll", function () {
                moveIndicator(nav, indicator, active);
            }, { passive: true });
        }
    }

    ready(function () {
        document.querySelectorAll(".sidebar-nav").forEach(initSidebarNav);
    });
})();
