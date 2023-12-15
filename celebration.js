document.addEventListener('DOMContentLoaded', function () {
    // Funktio ilotulituksen luomiseksi
    function createFireworks() {
        const fireworksContainer = document.createElement('div');
        fireworksContainer.className = 'fireworks-container';

        for (let i = 0; i < 10; i++) {
            const firework = document.createElement('div');
            firework.className = 'firework';
            fireworksContainer.appendChild(firework);
        }

        document.body.appendChild(fireworksContainer);

        setTimeout(() => {
            fireworksContainer.remove();
        }, 5000); // Poista ilotulitus 5 sekunnin kuluttua
    }

    // Kuuntele tekstin päivitystä
    const resultElement = document.querySelector('.error');
    const newGameLink = document.getElementById('uusi-peli-linkki');

    resultElement.addEventListener('DOMSubtreeModified', function () {
        // Tarkista, onko teksti päivittynyt haluttuun viestiin
        if (resultElement.textContent.includes('Arvasit oikein! Oikea maa on: Thailand. Keräsit 1000 pistettä!')) {
            // Kutsu ilotulituksen luomisfunktiota 5 sekunnin viiveellä
            setTimeout(createFireworks, 5000);

            // Näytä "Aloita uusi peli" -linkki
            newGameLink.style.display = 'block';
        }
    });

    // ... (muu koodi) ...
});
