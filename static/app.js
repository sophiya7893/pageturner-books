document.addEventListener("DOMContentLoaded", () => {
    /*
     * Live search by title or author.
     */
    const searchInput = document.querySelector("#liveSearch");
    const cards = [
        ...document.querySelectorAll(".book-card")
    ];

    const noResults = document.querySelector("#noResults");
    const bookCount = document.querySelector("#bookCount");

    if (searchInput) {
        searchInput.addEventListener("input", () => {
            const searchText = searchInput.value
                .trim()
                .toLowerCase();

            let visibleBooks = 0;

            cards.forEach((card) => {
                const title = card.dataset.title;
                const author = card.dataset.author;

                const matches =
                    title.includes(searchText) ||
                    author.includes(searchText);

                card.classList.toggle(
                    "hidden",
                    !matches
                );

                if (matches) {
                    visibleBooks++;
                }
            });

            if (noResults) {
                noResults.classList.toggle(
                    "hidden",
                    visibleBooks !== 0
                );
            }

            if (bookCount) {
                bookCount.textContent =
                    `${visibleBooks} books`;
            }
        });
    }

    /*
     * Ask for confirmation before removing a book.
     */
    document.querySelectorAll(".remove-form")
        .forEach((form) => {
            form.addEventListener("submit", (event) => {
                const confirmed = window.confirm(
                    "Remove this book?"
                );

                if (!confirmed) {
                    event.preventDefault();
                }
            });
        });

    /*
     * Validate exactly 10 phone digits.
     */
    const checkoutForm =
        document.querySelector("#checkoutForm");

    const phoneInput =
        document.querySelector("#phone");

    const phoneError =
        document.querySelector("#phoneError");

    if (checkoutForm && phoneInput) {
        checkoutForm.addEventListener(
            "submit",
            (event) => {
                const validPhone =
                    /^\d{10}$/.test(
                        phoneInput.value.trim()
                    );

                if (!validPhone) {
                    event.preventDefault();

                    phoneError.textContent =
                        "Phone must contain exactly 10 digits.";

                    phoneInput.focus();
                } else {
                    phoneError.textContent = "";
                }
            }
        );
    }

    /*
     * Hide flash messages after 3 seconds.
     */
    document.querySelectorAll(".flash")
        .forEach((message) => {
            setTimeout(() => {
                message.classList.add("hide");
            }, 3000);
        });
});