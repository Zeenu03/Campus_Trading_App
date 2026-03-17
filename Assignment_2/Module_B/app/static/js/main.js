/**
 * Campus Trading — Main JavaScript
 *
 * The web UI uses standard HTML form submissions for all CRUD operations.
 * No AJAX needed for the web UI. The REST /api/* endpoints remain available
 * for Postman / external API testing with Bearer token auth.
 */
'use strict';

// Auto-dismiss flash alerts after 5 seconds
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.alert').forEach(function (el) {
        setTimeout(function () {
            const a = bootstrap.Alert.getOrCreateInstance(el);
            if (a) a.close();
        }, 5000);
    });
});
