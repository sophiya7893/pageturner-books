/* =========================================================
   PageTurner Books

   Main JavaScript
   File: static/app.js
   ========================================================= */


/* =========================================================
   1. BASIC HELPERS
   ========================================================= */

function showMessage(message, type = "info") {

    const container =
        document.querySelector(".flash-container");

    if (!container) {
        alert(message);
        return;
    }

    const messageBox =
        document.createElement("div");

    messageBox.className =
        `flash-message flash-${type}`;

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

    const badge =
        document.getElementById("cart-count");

    if (!badge) {
        return;
    }

    badge.textContent = count;
}


/* =========================================================
   3. API BOOK SEARCH
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

        const books =
            await response.json();

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
   4. DISPLAY SEARCH RESULTS
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


        /* ---------------------------------------------
           Cover image
           --------------------------------------------- */

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
                    <div
                        class="book-cover placeholder-cover"
                    >
                        📖
                    </div>
                  `;


        /* ---------------------------------------------
           Stock display
           --------------------------------------------- */

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


        /* ---------------------------------------------
           Book card HTML
           --------------------------------------------- */

        card.innerHTML = `

            ${image}

            <div class="book-card-body">

                <span class="book-category">
                    ${escapeHTML(
                        book.category || ""
                    )}
                </span>

                <h3>
                    <a href="/book/${book.id}">
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

        resultsContainer.appendChild(
            card
        );
    });
}


/* =========================================================
   5. HTML ESCAPING
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
   6. LIVE SEARCH
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
   7. QUANTITY VALIDATION
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
   8. CONFIRM DELETE
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
   9. AUTO-HIDE FLASH MESSAGES
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
   10. MOBILE MENU
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
   11. FORM DOUBLE-SUBMIT PROTECTION
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
                 * Wait a few milliseconds before
                 * disabling the button.
                 *
                 * This allows the browser to perform
                 * the normal form submission first.
                 *
                 * The form will therefore submit:
                 *
                 *     _csrf_token
                 *     quantity
                 *     and other form fields
                 */

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
   12. INITIALIZE
   ========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    function() {

        setupLiveSearch();

        setupQuantityValidation();

        setupDeleteConfirmation();

        setupFlashMessages();

        setupMobileMenu();

        setupFormProtection();
    }
);
// Step 68: accessible live-search suggestions using the read-only books API.
(() => {
  const input = document.querySelector('input[name="q"]');
  if (!input) return;
  let wrapper = input.parentElement;
  if (!wrapper.classList.contains('search-input-wrap')) {
    wrapper = document.createElement('div');
    wrapper.className = 'search-input-wrap';
    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);
  }
  const list = document.createElement('div');
  list.className = 'search-suggestions';
  list.setAttribute('role', 'listbox');
  list.hidden = true;
  wrapper.appendChild(list);
  let timer;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    const term = input.value.trim();
    if (term.length < 2) { list.replaceChildren(); list.hidden = true; return; }
    timer = setTimeout(async () => {
      try {
        const response = await fetch(`/api/books?q=${encodeURIComponent(term)}`, { headers: { Accept: 'application/json' } });
        if (!response.ok) throw new Error('Search unavailable');
        const books = await response.json();
        list.replaceChildren();
        books.slice(0, 5).forEach(book => {
          const link = document.createElement('a');
          link.href = `/book/${book.id}`;
          link.textContent = `${book.title} — ${book.author}`;
          link.setAttribute('role', 'option');
          list.appendChild(link);
        });
        list.hidden = list.childElementCount === 0;
      } catch (_) { list.replaceChildren(); list.hidden = true; }
    }, 220);
  });
  document.addEventListener('click', event => { if (!wrapper.contains(event.target)) list.hidden = true; });
})();
