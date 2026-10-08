/* =========================================================
   PageTurner Books
   Main JavaScript
   File: static/app.js
   ========================================================= */


/* =========================================================
   1. BASIC HELPERS
   ========================================================= */

function showMessage(message, type = "info") {
    const container = document.querySelector(".flash-container");

    if (!container) {
        alert(message);
        return;
    }

    const messageBox = document.createElement("div");

    messageBox.className = `flash-message flash-${type}`;

    messageBox.textContent = message;

    container.appendChild(messageBox);

    setTimeout(() => {
        messageBox.remove();
    }, 4000);
}


/* =========================================================
   2. CART BADGE
   ========================================================= */

function updateCartBadge(count) {
    const badge = document.getElementById("cart-count");

    if (!badge) {
        return;
    }

    badge.textContent = count;
}


/* =========================================================
   3. ADD TO CART USING FETCH
   ========================================================= */

async function addToCartAjax(bookId, quantity = 1) {

    try {

        const response = await fetch(
            `/api/cart/add/${bookId}`,
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    quantity: quantity
                })
            }
        );


        const data = await response.json();


        if (!response.ok) {

            showMessage(
                data.message || "Could not add book to cart.",
                "error"
            );

            return;
        }


        if (data.cart_count !== undefined) {
            updateCartBadge(data.cart_count);
        }


        showMessage(
            data.message || "Book added to cart.",
            "success"
        );


    } catch (error) {

        console.error("Add to cart error:", error);

        showMessage(
            "Something went wrong. Please try again.",
            "error"
        );
    }
}


/* =========================================================
   4. AJAX ADD-TO-CART BUTTONS
   ========================================================= */

function setupAjaxCartButtons() {

    const forms = document.querySelectorAll(
        ".ajax-cart-form"
    );


    forms.forEach(form => {

        form.addEventListener(
            "submit",
            async function(event) {

                event.preventDefault();


                const bookId =
                    this.dataset.bookId;

                const quantityInput =
                    this.querySelector(
                        'input[name="quantity"]'
                    );


                let quantity = 1;


                if (quantityInput) {

                    quantity =
                        parseInt(
                            quantityInput.value,
                            10
                        );

                }


                if (
                    !Number.isInteger(quantity) ||
                    quantity < 1
                ) {

                    showMessage(
                        "Quantity must be at least 1.",
                        "error"
                    );

                    return;
                }


                await addToCartAjax(
                    bookId,
                    quantity
                );

            }
        );

    });
}


/* =========================================================
   5. API BOOK SEARCH
   ========================================================= */

async function searchBooksAPI(query) {

    try {

        const response = await fetch(
            `/api/books?q=${encodeURIComponent(query)}`
        );


        if (!response.ok) {
            throw new Error(
                "Book search failed"
            );
        }


        const books = await response.json();


        displayBookSearchResults(books);


    } catch (error) {

        console.error(
            "Search error:",
            error
        );

        showMessage(
            "Unable to search books.",
            "error"
        );
    }
}


/* =========================================================
   6. DISPLAY SEARCH RESULTS
   ========================================================= */

function displayBookSearchResults(books) {

    const resultsContainer =
        document.getElementById(
            "api-book-results"
        );


    if (!resultsContainer) {
        return;
    }


    resultsContainer.innerHTML = "";


    if (!books || books.length === 0) {

        resultsContainer.innerHTML = `
            <div class="empty-state">
                <h2>No books found</h2>
                <p>
                    Try another title or author.
                </p>
            </div>
        `;

        return;
    }


    books.forEach(book => {

        const card =
            document.createElement("article");


        card.className = "book-card";


        const image =
            book.cover_image
                ? `
                    <img
                        src="/static/images/${escapeHTML(
                            book.cover_image
                        )}"
                        alt="${escapeHTML(
                            book.title
                        )}"
                        class="book-cover"
                    >
                  `
                : `
                    <div class="book-cover placeholder-cover">
                        📖
                    </div>
                  `;


        const stock =
            Number(book.stock) > 0
                ? `
                    <span class="stock available">
                        ${book.stock} available
                    </span>
                  `
                : `
                    <span class="stock sold-out">
                        Sold Out
                    </span>
                  `;


        card.innerHTML = `

            ${image}

            <div class="book-card-body">

                <span class="book-category">
                    ${escapeHTML(
                        book.category || ""
                    )}
                </span>


                <h3>
                    <a
                        href="/book/${book.id}"
                    >
                        ${escapeHTML(
                            book.title
                        )}
                    </a>
                </h3>


                <p class="book-author">
                    ${escapeHTML(
                        book.author || ""
                    )}
                </p>


                <div class="book-price-row">

                    <strong class="book-price">
                        ₹${Number(
                            book.price
                        ).toFixed(2)}
                    </strong>

                    ${stock}

                </div>


                <div class="book-actions">

                    <a
                        href="/book/${book.id}"
                        class="btn btn-secondary"
                    >
                        View
                    </a>

                </div>

            </div>
        `;


        resultsContainer.appendChild(card);

    });
}


/* =========================================================
   7. HTML ESCAPING
   ========================================================= */

function escapeHTML(value) {

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


/* =========================================================
   8. LIVE SEARCH
   ========================================================= */

function setupLiveSearch() {

    const searchInput =
        document.getElementById(
            "live-search"
        );


    if (!searchInput) {
        return;
    }


    let timer;


    searchInput.addEventListener(
        "input",
        function() {

            const query =
                this.value.trim();


            clearTimeout(timer);


            if (query.length === 0) {

                const results =
                    document.getElementById(
                        "api-book-results"
                    );

                if (results) {
                    results.innerHTML = "";
                }

                return;
            }


            timer = setTimeout(
                () => {

                    searchBooksAPI(
                        query
                    );

                },
                300
            );

        }
    );
}


/* =========================================================
   9. QUANTITY VALIDATION
   ========================================================= */

function setupQuantityValidation() {

    const quantityInputs =
        document.querySelectorAll(
            'input[type="number"]'
        );


    quantityInputs.forEach(input => {

        input.addEventListener(
            "change",
            function() {

                const min =
                    parseInt(
                        this.min || "0",
                        10
                    );


                const max =
                    parseInt(
                        this.max || "999999",
                        10
                    );


                let value =
                    parseInt(
                        this.value,
                        10
                    );


                if (Number.isNaN(value)) {
                    value = min;
                }


                if (value < min) {
                    value = min;
                }


                if (value > max) {
                    value = max;
                }


                this.value = value;

            }
        );

    });
}


/* =========================================================
   10. CONFIRM DELETE
   ========================================================= */

function setupDeleteConfirmation() {

    const deleteForms =
        document.querySelectorAll(
            ".delete-form"
        );


    deleteForms.forEach(form => {

        form.addEventListener(
            "submit",
            function(event) {

                const confirmed =
                    confirm(
                        "Are you sure you want to delete this item?"
                    );


                if (!confirmed) {
                    event.preventDefault();
                }

            }
        );

    });
}


/* =========================================================
   11. AUTO-HIDE FLASH MESSAGES
   ========================================================= */

function setupFlashMessages() {

    const messages =
        document.querySelectorAll(
            ".flash-message"
        );


    messages.forEach(message => {

        setTimeout(
            () => {

                message.style.transition =
                    "opacity 0.4s ease";

                message.style.opacity = "0";


                setTimeout(
                    () => {
                        message.remove();
                    },
                    400
                );

            },
            5000
        );

    });
}


/* =========================================================
   12. MOBILE MENU
   ========================================================= */

function setupMobileMenu() {

    const button =
        document.getElementById(
            "mobile-menu-button"
        );


    const menu =
        document.querySelector(
            ".main-nav"
        );


    if (!button || !menu) {
        return;
    }


    button.addEventListener(
        "click",
        function() {

            menu.classList.toggle(
                "mobile-open"
            );

        }
    );
}


/* =========================================================
   13. FORM DOUBLE-SUBMIT PROTECTION
   ========================================================= */

function setupFormProtection() {

    const forms =
        document.querySelectorAll(
            "form"
        );


    forms.forEach(form => {

        form.addEventListener(
            "submit",
            function() {

                const submitButton =
                    this.querySelector(
                        'button[type="submit"]'
                    );


                if (!submitButton) {
                    return;
                }


                /*
                 * Do not disable buttons for AJAX
                 * forms because JavaScript handles them.
                 */

                if (
                    this.classList.contains(
                        "ajax-cart-form"
                    )
                ) {
                    return;
                }


                setTimeout(
                    () => {

                        submitButton.disabled =
                            true;

                        submitButton.dataset.originalText =
                            submitButton.textContent;

                        submitButton.textContent =
                            "Processing...";

                    },
                    10
                );

            }
        );

    });
}


/* =========================================================
   14. INITIALIZE
   ========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    function() {

        setupAjaxCartButtons();

        setupLiveSearch();

        setupQuantityValidation();

        setupDeleteConfirmation();

        setupFlashMessages();

        setupMobileMenu();

        setupFormProtection();

    }
);