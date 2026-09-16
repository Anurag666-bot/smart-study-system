// ===== Charts for Analytics Page =====
// Include Chart.js CDN in the analytics template: 
// <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

document.addEventListener('DOMContentLoaded', function() {
    // If on analytics page, render charts
    const analyticsContainer = document.querySelector('.analytics-cards');
    if (!analyticsContainer) return;

    // Data passed from Django (via context)
    const completedPercent = parseFloat(analyticsContainer.dataset.completedPercent) || 0;
    const attendancePercent = parseFloat(analyticsContainer.dataset.attendancePercent) || 0;

    // Create a canvas for completion chart
    const chartContainer = document.createElement('div');
    chartContainer.style.cssText = 'margin-top: 2rem;';
    chartContainer.innerHTML = `
        <h3>Progress Overview</h3>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2rem;">
            <div><canvas id="completionChart"></canvas></div>
            <div><canvas id="attendanceChart"></canvas></div>
        </div>
    `;
    analyticsContainer.parentNode.insertBefore(chartContainer, analyticsContainer.nextSibling);

    // Completion Doughnut
    const ctx1 = document.getElementById('completionChart').getContext('2d');
    new Chart(ctx1, {
        type: 'doughnut',
        data: {
            labels: ['Completed', 'Pending'],
            datasets: [{
                data: [completedPercent, 100 - completedPercent],
                backgroundColor: ['#10b981', '#e2e8f0'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'bottom' },
                title: { display: true, text: 'Task Completion' }
            }
        }
    });

    // Attendance Doughnut
    const ctx2 = document.getElementById('attendanceChart').getContext('2d');
    new Chart(ctx2, {
        type: 'doughnut',
        data: {
            labels: ['Present', 'Absent'],
            datasets: [{
                data: [attendancePercent, 100 - attendancePercent],
                backgroundColor: ['#3b82f6', '#e2e8f0'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'bottom' },
                title: { display: true, text: 'Attendance' }
            }
        }
    });
});