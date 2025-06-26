// 전역 변수 및 초기화
let allTickets = [];
let platformColors = {};
const ticketsContainer = document.getElementById('tickets-container');
const loadingSpinner = document.getElementById('loading-spinner');
const noResults = document.getElementById('no-results');
const platformFilter = document.getElementById('platform-filter');
const genreFilter = document.getElementById('genre-filter');
const dateFilter = document.getElementById('date-filter');
const sortFilter = document.getElementById('sort-filter');
const searchInput = document.getElementById('search-input');
const gridViewBtn = document.getElementById('grid-view-btn');
const listViewBtn = document.getElementById('list-view-btn');
const lastUpdateSpan = document.getElementById('last-update-time');
const autoRefreshInfo = document.getElementById('auto-refresh-info');
const refreshBtn = document.getElementById('refresh-btn');

// 날짜 정보 업데이트
document.getElementById('today-date').textContent = getFormattedDate(0);
document.getElementById('tomorrow-date').textContent = getFormattedDate(1);

// 이벤트 리스너
document.addEventListener('DOMContentLoaded', () => {
    loadTicketData();
    startAutoRefresh();
    setView('grid'); // 초기 뷰 설정
});

[platformFilter, genreFilter, dateFilter, sortFilter].forEach(filter => {
    filter.addEventListener('change', applyFiltersAndSort);
});

searchInput.addEventListener('input', debounce(applyFiltersAndSort, 300));

gridViewBtn.addEventListener('click', () => setView('grid'));
listViewBtn.addEventListener('click', () => setView('list'));
refreshBtn.addEventListener('click', refreshData);


// 데이터 로딩 및 처리
async function loadTicketData() {
    showLoading();
    try {
        const response = await fetch('/api/tickets');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        allTickets = data.tickets;
        platformColors = data.platform_colors;
        updateStats(data.stats);
        populateFilters(data.stats);
        applyFiltersAndSort();
        updateLastUpdateTime(data.last_update);
    } catch (error) {
        console.error("티켓 데이터 로딩 실패:", error);
        ticketsContainer.innerHTML = '<div class="no-results"><i class="fas fa-exclamation-circle"></i><p>티켓 정보를 불러오는 데 실패했습니다.</p></div>';
    } finally {
        hideLoading();
    }
}

function updateStats(stats) {
    document.getElementById('today-count').textContent = stats.today_count;
    document.getElementById('tomorrow-count').textContent = stats.tomorrow_count;
    document.getElementById('this-week-count').textContent = stats.this_week_count;
    document.getElementById('total-count').textContent = stats.total_count;
}

function populateFilters(stats) {
    // 플랫폼 필터 채우기
    const platformFragment = document.createDocumentFragment();
    for (const platform in stats.platform_counts) {
        const option = document.createElement('option');
        option.value = platform;
        option.textContent = `${platform}`;
        platformFragment.appendChild(option);
    }
    platformFilter.appendChild(platformFragment);

    // 장르 필터 채우기
    const genreFragment = document.createDocumentFragment();
    for (const genre in stats.genre_counts) {
        if (stats.genre_counts[genre] > 0) {
            const option = document.createElement('option');
            option.value = genre;
            option.textContent = `${genre}`;
            genreFragment.appendChild(option);
        }
    }
    genreFilter.appendChild(genreFragment);
}

function applyFiltersAndSort() {
    let filteredTickets = [...allTickets];

    // 필터링
    const platform = platformFilter.value;
    if (platform !== 'all') {
        filteredTickets = filteredTickets.filter(t => t.source === platform);
    }

    const genre = genreFilter.value;
    if (genre !== 'all') {
        // 백엔드에서 제공하는 genre 필드를 직접 사용하여 필터링
        filteredTickets = filteredTickets.filter(t => t.genre === genre);
    }

    const date = dateFilter.value;
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    if (date === 'today') {
        filteredTickets = filteredTickets.filter(t => new Date(t.open_date).toDateString() === today.toDateString());
    } else if (date === 'tomorrow') {
        const tomorrow = new Date(today);
        tomorrow.setDate(today.getDate() + 1);
        filteredTickets = filteredTickets.filter(t => new Date(t.open_date).toDateString() === tomorrow.toDateString());
    } else if (date === 'this-week') {
        const endOfWeek = new Date(today);
        endOfWeek.setDate(today.getDate() + (6 - today.getDay()));
        filteredTickets = filteredTickets.filter(t => {
            const openDate = new Date(t.open_date);
            return openDate >= today && openDate <= endOfWeek;
        });
    }

    const searchTerm = searchInput.value.toLowerCase();
    if (searchTerm) {
        filteredTickets = filteredTickets.filter(t => 
            t.title.toLowerCase().includes(searchTerm) || 
            t.place.toLowerCase().includes(searchTerm)
        );
    }

    // 정렬
    const sort = sortFilter.value;
    filteredTickets.sort((a, b) => {
        if (sort === 'open-date-asc') {
            return new Date(a.open_date) - new Date(b.open_date);
        } else if (sort === 'open-date-desc') {
            return new Date(b.open_date) - new Date(a.open_date);
        } else if (sort === 'title-asc') {
            return a.title.localeCompare(b.title);
        }
        return 0;
    });

    displayTickets(filteredTickets);
}

function displayTickets(tickets) {
    ticketsContainer.innerHTML = '';
    if (tickets.length === 0) {
        noResults.style.display = 'flex';
        return;
    }
    noResults.style.display = 'none';

    const fragment = document.createDocumentFragment();
    tickets.forEach(ticket => {
        const card = createTicketCard(ticket);
        fragment.appendChild(card);
    });
    ticketsContainer.appendChild(fragment);
}

function createTicketCard(ticket) {
    const card = document.createElement('div');
    card.className = 'ticket-card';

    const openDate = new Date(ticket.open_date);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const diffDays = Math.ceil((openDate - today) / (1000 * 60 * 60 * 24));

    let dDay = '';
    let dDayClass = '';
    if (diffDays === 0) {
        dDay = 'D-DAY';
        dDayClass = 'today';
    } else if (diffDays > 0) {
        dDay = `D-${diffDays}`;
    }

    const ticketGenre = ticket.genre || '기타';
    const openDateFormatted = ticket.open_date && ticket.open_date !== '미정' ? 
        new Date(ticket.open_date).toLocaleString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : 
        ticket.open_date || '미정';

    card.innerHTML = `
        <div class="ticket-image-container">
            <img src="${ticket.image_url || 'https://via.placeholder.com/300x420.png?text=No+Image'}" alt="${ticket.title}" class="ticket-image" loading="lazy" onerror="this.onerror=null;this.src='https://via.placeholder.com/300x420.png?text=No+Image';">
            <div class="platform-badge" style="background-color: ${platformColors[ticket.source] || 'var(--color-gray-600)'}">${ticket.source}</div>
            ${dDay ? `<div class="d-day ${dDayClass}">${dDay}</div>` : ''}
        </div>
        <div class="ticket-content">
            <h3 class="ticket-title">${ticket.title}</h3>
            <div class="ticket-info">
                <p><i class="fas fa-palette"></i> <span>${ticketGenre}</span></p>
                <p><i class="fas fa-map-marker-alt"></i> <span>${ticket.place || '장소 미정'}</span></p>
                <p><i class="fas fa-calendar-alt"></i> <span>${ticket.perf_date || '공연일 미정'}</span></p>
                <p><i class="fas fa-clock"></i> <span class="open-date">${openDateFormatted}</span></p>
            </div>
        </div>
        <div class="ticket-actions">
             <a href="${ticket.url}" target="_blank" class="btn btn-primary">
                <i class="fas fa-ticket-alt"></i> 예매하기
            </a>
        </div>
    `;
    return card;
}

// 뷰 전환
function setView(view) {
    if (view === 'grid') {
        ticketsContainer.classList.remove('list-view');
        ticketsContainer.classList.add('grid-view');
        gridViewBtn.classList.add('active');
        listViewBtn.classList.remove('active');
    } else {
        ticketsContainer.classList.remove('grid-view');
        ticketsContainer.classList.add('list-view');
        listViewBtn.classList.add('active');
        gridViewBtn.classList.remove('active');
    }
}

// 유틸리티 함수
function showLoading() {
    loadingSpinner.style.display = 'flex';
    ticketsContainer.style.display = 'none';
    noResults.style.display = 'none';
}

function hideLoading() {
    loadingSpinner.style.display = 'none';
    ticketsContainer.style.display = '';
}

function debounce(func, delay) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), delay);
    };
}

function getFormattedDate(dayOffset) {
    const date = new Date();
    date.setDate(date.getDate() + dayOffset);
    return `${date.getMonth() + 1}/${date.getDate()}`;
}

function updateLastUpdateTime(timeStr) {
    if (!timeStr) return;
    const date = new Date(timeStr);
    const formattedTime = date.toLocaleString('ko-KR');
    lastUpdateSpan.textContent = formattedTime;
    document.getElementById('footer-last-update').textContent = formattedTime;
}

// 자동 새로고침
let autoRefreshInterval;
function startAutoRefresh() {
    let remaining = 300;
    autoRefreshInfo.textContent = `다음 업데이트까지 5분 00초`;
    autoRefreshInterval = setInterval(() => {
        remaining--;
        const minutes = Math.floor(remaining / 60);
        const seconds = remaining % 60;
        autoRefreshInfo.textContent = `다음 업데이트까지 ${minutes}분 ${seconds.toString().padStart(2, '0')}초`;
        if (remaining <= 0) {
            refreshData();
            remaining = 300;
        }
    }, 1000);
}

async function refreshData() {
    clearInterval(autoRefreshInterval);
    const refreshIcon = refreshBtn.querySelector('i');
    refreshIcon.classList.add('fa-spin');
    refreshBtn.disabled = true;
    
    await loadTicketData();
    
    startAutoRefresh();
    refreshIcon.classList.remove('fa-spin');
    refreshBtn.disabled = false;
}