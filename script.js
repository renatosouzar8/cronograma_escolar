document.addEventListener('DOMContentLoaded', () => {
    loadSchedules();
    setupTabs();
});

function setupTabs() {
    const tabTheo = document.getElementById('tab-theo');
    const tabLiz = document.getElementById('tab-liz');
    const theoContainer = document.getElementById('theo-schedule');
    const lizContainer = document.getElementById('liz-schedule');

    const inactiveClasses = ['text-gray-500', 'border-transparent', 'hover:text-gray-700', 'hover:border-gray-300'];
    const activeTheoClasses = ['text-theo-color', 'border-theo-color'];
    const activeLizClasses = ['text-liz-color', 'border-liz-color'];

    tabTheo.addEventListener('click', () => {
        if (theoContainer.classList.contains('hidden')) {
            theoContainer.classList.remove('hidden');
            lizContainer.classList.add('hidden');

            tabTheo.classList.remove(...inactiveClasses);
            tabTheo.classList.add(...activeTheoClasses);

            tabLiz.classList.remove(...activeLizClasses);
            tabLiz.classList.add(...inactiveClasses);
        }
    });

    tabLiz.addEventListener('click', () => {
        if (lizContainer.classList.contains('hidden')) {
            lizContainer.classList.remove('hidden');
            theoContainer.classList.add('hidden');

            tabLiz.classList.remove(...inactiveClasses);
            tabLiz.classList.add(...activeLizClasses);

            tabTheo.classList.remove(...activeTheoClasses);
            tabTheo.classList.add(...inactiveClasses);
        }
    });
}

async function loadSchedules() {
    try {
        const response = await fetch('./events.json');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const events = await response.json();

        const theoContainer = document.getElementById('theo-schedule');
        const lizContainer = document.getElementById('liz-schedule');

        if (!theoContainer || !lizContainer) {
            console.error("Schedule containers not found in the DOM.");
            return;
        }

        const parseDate = (dateStr) => {
            const [day, month] = dateStr.split('/').map(Number);
            const currentYear = new Date().getFullYear();
            return new Date(currentYear, month - 1, day);
        };

        const theoEvents = events
            .filter(event => event.aluno === 'Theo')
            .sort((a, b) => parseDate(a.data) - parseDate(b.data));

        const lizEvents = events
            .filter(event => event.aluno === 'Liz')
            .sort((a, b) => parseDate(a.data) - parseDate(b.data));
            
        theoContainer.innerHTML = theoEvents.map(event => createEventCard(event, 'theo')).join('');
        lizContainer.innerHTML = lizEvents.map(event => createEventCard(event, 'liz')).join('');

        lucide.createIcons();

    } catch (error) {
        console.error("Failed to load or process schedule data:", error);
        document.getElementById('schedule-content').innerHTML = `<p class="text-center text-red-500 col-span-full">Não foi possível carregar os eventos. Por favor, tente novamente mais tarde.</p>`;
    }
}

function createEventCard(event, studentClass) {
    const studentColorClass = studentClass === 'theo' ? 'theo' : 'liz';

    return `
        <div class="event-card ${studentColorClass}-card">
            <div class="event-card-header ${studentColorClass}-header p-4 flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <i data-lucide="calendar-days" class="w-6 h-6"></i>
                    <div class="font-bold text-lg">${event.data}</div>
                </div>
                <div class="font-medium text-gray-600">${event.dia_semana}</div>
            </div>
            <div class="p-5 space-y-4">
                <div>
                    <h3 class="font-bold text-xl text-gray-800">${event.evento}</h3>
                </div>
                <div class="border-t pt-4">
                    <p class="font-semibold text-gray-600 mb-2 flex items-center gap-2">
                        <i data-lucide="clipboard-list" class="w-5 h-5"></i>
                        Preparação
                    </p>
                    <p class="text-gray-700 leading-relaxed">${event.preparacao}</p>
                </div>
            </div>
        </div>
    `;
}
