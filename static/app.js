document.addEventListener("DOMContentLoaded", function () {

    /*
     * Automatically hide flash messages.
     */
    const flashes = document.querySelectorAll(".flash");

    flashes.forEach(function (flash) {

        setTimeout(function () {

            flash.style.transition = "opacity 0.4s";
            flash.style.opacity = "0";

            setTimeout(function () {
                flash.remove();
            }, 400);

        }, 4500);

    });


    /*
     * Confirm admin deletion.
     */
    window.confirmDelete = function () {

        return confirm(
            "Are you sure you want to delete this book?"
        );

    };


    /*
     * Prevent quantities larger than the stock
     * on the book detail page.
     */
    const quantityInput =
        document.getElementById("quantity");

    if (quantityInput) {

        quantityInput.addEventListener(
            "input",
            function () {

                const max =
                    parseInt(
                        quantityInput.max
                    );

                const value =
                    parseInt(
                        quantityInput.value
                    );

                if (value > max) {
                    quantityInput.value = max;
                }

                if (value < 1) {
                    quantityInput.value = 1;
                }

            }
        );

    }


    /*
     * Simple keyboard shortcut:
     * "/" focuses the search box.
     */
    const searchInput =
        document.getElementById("liveSearch");

    document.addEventListener(
        "keydown",
        function (event) {

            if (
                event.key === "/" &&
                document.activeElement.tagName !== "INPUT" &&
                document.activeElement.tagName !== "TEXTAREA"
            ) {

                event.preventDefault();

                if (searchInput) {
                    searchInput.focus();
                }

            }

        }
    );

});