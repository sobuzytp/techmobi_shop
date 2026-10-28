// TechMobi custom JavaScript
// 1. Live cart total recalculation (visual feedback before the page reloads)
// 2. Bootstrap client-side form validation for the checkout form
// 3. Auto-dismiss alerts after a few seconds

// 5499 -> "5,499", 1234567 -> "12,34,567", 3399.15 -> "3,399.15" (same as the server-side `taka` filter)
window.formatTaka = function (value) {
    var n = Math.abs(Number(value) || 0);
    var parts = n.toFixed(2).split('.');
    var whole = parts[0], head = whole.slice(0, -3), tail = whole.slice(-3), groups = [];
    while (head.length > 2) { groups.unshift(head.slice(-2)); head = head.slice(0, -2); }
    if (head) groups.unshift(head);
    var text = groups.length ? groups.join(',') + ',' + tail : whole;
    return (value < 0 ? '-' : '') + text + (parts[1] !== '00' ? '.' + parts[1] : '');
};

document.addEventListener('DOMContentLoaded', function () {

    // ---- Bootstrap checkout form validation ----
    const checkoutForm = document.querySelector('.needs-validation');
    if (checkoutForm) {
        checkoutForm.addEventListener('submit', function (event) {
            if (!checkoutForm.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            checkoutForm.classList.add('was-validated');
        }, false);
    }

    // ---- Auto dismiss alerts ----
    document.querySelectorAll('.alert').forEach(function (alertEl) {
        setTimeout(function () {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alertEl);
            if (bsAlert) bsAlert.close();
        }, 4000);
    });

    // ---- Live cart total preview ----
    // Recomputes the grand total instantly on the cart page when a user
    // changes a quantity input (before the form submit hits the server).
    const cartTable = document.getElementById('cart-table');
    if (cartTable) {
        const grandTotalEl = document.getElementById('cart-grand-total');

        function recalcTotals() {
            let grandTotal = 0;
            document.querySelectorAll('.cart-row').forEach(function (row) {
                const price = parseFloat(row.dataset.price);
                const qty = parseInt(row.querySelector('.cart-qty-value').textContent, 10);
                const lineTotal = price * qty;
                row.querySelector('.cart-line-total').textContent = 'Tk ' + window.formatTaka(lineTotal);
                grandTotal += lineTotal;
            });
            if (grandTotalEl) {
                grandTotalEl.textContent = 'Tk ' + window.formatTaka(grandTotal);
            }
        }

        // Purely visual pre-update; the actual source of truth is the server,
        // which recalculates on submit via the increase/decrease/remove buttons.
        recalcTotals();
    }

    // ---- Simple product search UX: submit on Enter already works natively ----
});
