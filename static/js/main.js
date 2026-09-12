// TechMobi custom JavaScript
// 1. Live cart total recalculation (visual feedback before the page reloads)
// 2. Bootstrap client-side form validation for the checkout form
// 3. Auto-dismiss alerts after a few seconds

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
                row.querySelector('.cart-line-total').textContent = 'Tk ' + lineTotal.toFixed(2);
                grandTotal += lineTotal;
            });
            if (grandTotalEl) {
                grandTotalEl.textContent = 'Tk ' + grandTotal.toFixed(2);
            }
        }

        // Purely visual pre-update; the actual source of truth is the server,
        // which recalculates on submit via the increase/decrease/remove buttons.
        recalcTotals();
    }

    // ---- Simple product search UX: submit on Enter already works natively ----
});
