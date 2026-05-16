/*
 * Hikari ECharts theme for the CTFd admin panel.
 *
 * Problem: CTFd's /admin/statistics calls echarts.init(el) without a
 * named theme, so charts render with the default Bootstrap-era palette
 * (#5470c6 blue bars, #ee6666 red pies, #91cc75 greens) which clashes
 * with the Hikari dark identity. The axis/legend/title colors are also
 * fixed dark-on-light grey, illegible on our dark surfaces.
 *
 * Approach: monkey-patch echarts.init so every chart created after this
 * script runs gets the 'hikari' theme. This is the smallest surface that
 * survives CTFd updates to statistics.js — we never touch the chart
 * series logic, only colors and text.
 *
 * Loaded via register_admin_plugin_script (CTFd's stylesheet API for JS).
 */
(function () {
    "use strict";

    function applyTheme() {
        if (typeof window.echarts === "undefined") {
            // statistics.js bundles echarts as a module import; the global
            // is not always set. In that case the page-level script wins
            // and our theme will not apply. We still set up the global if
            // it appears later via dynamic import.
            return;
        }
        if (window.echarts.__hikariThemeApplied) return;

        var hk = {
            bg:        "#0f1a2c",
            surface2:  "#142139",
            border:    "#1f2f4a",
            text:      "#edf3f8",
            textMuted: "#9aa7b7",
            primary:   "#10b981",
        };

        // Hikari-tinted palette: ordered for accessibility on dark BG.
        // First color is the brand primary; remainder cycle through
        // analogous teals, ambers and muted purples — no pure red/green
        // (reserved for solve/fail semantics) and no pure cyan/magenta.
        var palette = [
            "#10b981", // primary
            "#22d3ee", // teal
            "#f59e0b", // amber
            "#a78bfa", // muted purple
            "#fb7185", // soft coral
            "#84cc16", // lime
            "#38bdf8", // sky
            "#f472b6", // soft pink
            "#fbbf24", // gold
            "#34d399", // mint
        ];

        var theme = {
            color: palette,
            backgroundColor: "transparent",
            textStyle: { color: hk.text },
            title: {
                textStyle: { color: hk.text, fontWeight: "600" },
                subtextStyle: { color: hk.textMuted },
            },
            legend: {
                textStyle: { color: hk.text },
                inactiveColor: hk.textMuted,
            },
            tooltip: {
                backgroundColor: hk.surface2,
                borderColor: hk.border,
                textStyle: { color: hk.text },
                axisPointer: {
                    lineStyle: { color: hk.primary },
                    crossStyle: { color: hk.primary },
                },
            },
            // Cartesian axes shared style. Applied for every category and
            // value axis on bar / line / scatter charts.
            categoryAxis: axisStyle(),
            valueAxis: axisStyle(),
            logAxis: axisStyle(),
            timeAxis: axisStyle(),
            grid: {
                borderColor: hk.border,
            },
            line: { itemStyle: { borderWidth: 1 }, lineStyle: { width: 2 } },
            bar: { itemStyle: { borderRadius: [3, 3, 0, 0] } },
            pie: { itemStyle: { borderColor: hk.bg, borderWidth: 1 } },
            dataZoom: {
                backgroundColor: "transparent",
                dataBackgroundColor: hk.surface2,
                fillerColor: "rgba(16, 185, 129, 0.18)",
                handleColor: hk.primary,
                handleSize: "100%",
                textStyle: { color: hk.textMuted },
                borderColor: hk.border,
            },
        };

        function axisStyle() {
            return {
                axisLine: { lineStyle: { color: hk.border } },
                axisTick: { lineStyle: { color: hk.border } },
                axisLabel: { color: hk.textMuted, fontSize: 11 },
                splitLine: { lineStyle: { color: hk.border, type: "dashed" } },
                splitArea: { areaStyle: { color: ["transparent", "transparent"] } },
            };
        }

        window.echarts.registerTheme("hikari", theme);

        // Monkey-patch init so call sites that don't pass a theme still
        // get the Hikari palette. Charts already initialized before our
        // script ran will be re-skinned via the postInit pass below.
        var originalInit = window.echarts.init;
        window.echarts.init = function (dom, theme, opts) {
            if (theme === undefined || theme === null) {
                theme = "hikari";
            }
            return originalInit.call(window.echarts, dom, theme, opts);
        };

        // Re-skin any chart that was initialized before the monkey-patch.
        // echarts.getInstanceByDom retrieves the live instance; setOption
        // with merge=true applies our palette without breaking the data.
        if (typeof window.echarts.getInstanceByDom === "function") {
            document.querySelectorAll("[_echarts_instance_]").forEach(function (el) {
                var chart = window.echarts.getInstanceByDom(el);
                if (!chart) return;
                try {
                    chart.setOption({ color: palette }, false);
                } catch (e) {
                    /* charts disposed mid-render — safe to ignore */
                }
            });
        }

        window.echarts.__hikariThemeApplied = true;
    }

    // CTFd's statistics.js bundles echarts as an ES module so the global
    // may appear only after the page's main entrypoint executes. Try at
    // DOMContentLoaded and again after a short delay to cover both
    // bundling strategies.
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", applyTheme);
    } else {
        applyTheme();
    }
    setTimeout(applyTheme, 300);
    setTimeout(applyTheme, 1500);
})();
