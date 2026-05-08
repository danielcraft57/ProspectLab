/**
 * Client front pour lancer/suivre la génération des landing variants.
 * Exposé en global: window.LandingVariantsClient
 */
(function (window) {
    "use strict";

    function notify(message, type) {
        try {
            if (window.Notifications && typeof window.Notifications.show === "function") {
                window.Notifications.show(message, type || "info");
            }
        } catch (e) {}
    }

    async function start(payload) {
        const res = await fetch("/api/landing-variants/start", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload || {}),
        });
        const data = await res.json().catch(function () { return {}; });
        if (!res.ok || !data.success) {
            throw new Error(data.error || ("HTTP " + res.status));
        }
        return data;
    }

    async function watchTask(taskId, options) {
        const intervalMs = (options && options.intervalMs) || 1500;
        const maxPolls = (options && options.maxPolls) || 4800;
        for (let i = 0; i < maxPolls; i += 1) {
            const res = await fetch("/api/celery-task/" + encodeURIComponent(taskId), {
                credentials: "same-origin",
            });
            const data = await res.json().catch(function () { return {}; });
            if (!res.ok) throw new Error(data.error || ("HTTP " + res.status));
            if (data.state === "SUCCESS") return data.result || {};
            if (data.state === "FAILURE" || data.state === "REVOKED" || data.state === "REJECTED") {
                throw new Error(data.error || "La tâche a échoué.");
            }
            await new Promise(function (r) { return setTimeout(r, intervalMs); });
        }
        throw new Error("Timeout de suivi de tâche dépassé.");
    }

    function bindDefaultNotifications() {
        document.addEventListener("landing_variants:progress", function (ev) {
            const d = (ev && ev.detail) || {};
            if (d && d.message) notify("Landing variants: " + d.message, "info");
        });
        document.addEventListener("landing_variants:complete", function () {
            notify("Landing variants terminés.", "success");
        });
        document.addEventListener("landing_variants:error", function (ev) {
            const d = (ev && ev.detail) || {};
            notify("Landing variants en erreur: " + (d.error || "inconnue"), "error");
        });
        document.addEventListener("landing_variants:usage_limit", function (ev) {
            const d = (ev && ev.detail) || {};
            const msg = d.message || "Usage limit Cursor atteint.";
            notify(msg, "warning");
        });
    }

    window.LandingVariantsClient = {
        start: start,
        watchTask: watchTask,
        bindDefaultNotifications: bindDefaultNotifications,
    };

    // Activé par défaut pour fournir le feedback temps réel partout.
    bindDefaultNotifications();
})(window);

