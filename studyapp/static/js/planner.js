// ===== Planner Page Scripts =====
document.addEventListener('DOMContentLoaded', function() {
    const plannerContainer = document.querySelector('.planner-container');
    if (!plannerContainer) return;

    // Add date picker enhancement (if using HTML5 date input).
    const dateInputs = document.querySelectorAll('input[type="date"]');
    dateInputs.forEach(input => {
        if (!input.value) {
            const today = new Date().toISOString().split('T')[0];
            input.value = today;
        }
    });
});
