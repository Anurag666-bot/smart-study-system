// ===== Calendar Page – Simple month view =====
document.addEventListener('DOMContentLoaded', function() {
    const calendarContainer = document.querySelector('.simple-calendar');
    if (!calendarContainer) return;

    // Get current month/year
    const now = new Date();
    const currentMonth = now.getMonth();
    const currentYear = now.getFullYear();

    // Build a simple month grid
    const monthNames = ['January','February','March','April','May','June',
                        'July','August','September','October','November','December'];
    const firstDay = new Date(currentYear, currentMonth, 1).getDay(); // 0=Sun
    const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();

    let html = `<h3>${monthNames[currentMonth]} ${currentYear}</h3>`;
    html += '<table style="width:100%; border-collapse: collapse;">';
    html += '<tr><th>Sun</th><th>Mon</th><th>Tue</th><th>Wed</th><th>Thu</th><th>Fri</th><th>Sat</th></tr><tr>';

    // Empty cells before first day
    for (let i = 0; i < firstDay; i++) {
        html += '<td></td>';
    }

    // Days
    for (let day = 1; day <= daysInMonth; day++) {
        const dayOfWeek = (firstDay + day - 1) % 7;
        if (dayOfWeek === 0 && day > 1) html += '</tr><tr>';
        const today = (day === now.getDate() && currentMonth === now.getMonth() && currentYear === now.getFullYear()) ? ' today' : '';
        html += `<td class="calendar-day${today}">${day}</td>`;
    }

    // Fill remaining cells
    const remaining = (7 - (firstDay + daysInMonth) % 7) % 7;
    for (let i = 0; i < remaining; i++) {
        html += '<td></td>';
    }
    html += '</tr></table>';

    // Append to container
    calendarContainer.innerHTML += html;

    // Add styling for today
    const style = document.createElement('style');
    style.textContent = `
        .calendar-day.today {
            background: #3b82f6;
            color: white;
            border-radius: 50%;
        }
        .calendar-day {
            text-align: center;
            padding: 8px;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
        }
    `;
    document.head.appendChild(style);
});