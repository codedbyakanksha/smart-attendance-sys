
document.addEventListener("DOMContentLoaded", () => {

    const search = document.getElementById("tableSearch");

    if (search) {

        search.addEventListener("input", () => {

            const query = search.value.toLowerCase();

            document.querySelectorAll(
                "#recordsTable tbody tr"
            ).forEach(row => {

                row.style.display =
                    row.innerText.toLowerCase().includes(query)
                    ? ""
                    : "none";

            });

        });

    }

});
