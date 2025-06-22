/**
 * 티켓 오픈 모니터 웹 인터페이스 JavaScript
 * 
 * 실시간 티켓 정보 표시, 필터링, 검색 기능을 제공합니다.
 */

// 전역 변수
let currentTickets = [];
let filteredTickets = [];
let wishlist = []; // 찜 목록
let currentView = 'grid';
let isLoading = false;
let autoRefreshTimer = null;
let lastUpdateTime = null;
let isAdmin = false;
let autoRefreshInterval = 3600000; // 기본값 1시간 (밀리초)

// DOM 요소
const elements = {
    ticketsContainer: null,
    loadingSpinner: null,
    noResults: null,
    searchInput: null,
    lastUpdate: null,
    footerLastUpdate: null,
    platformFilters: null,
    genreFilters: null,
    dateFilterButtons: null,
    dateStartInput: null,
    dateEndInput: null,
    sortSelect: null,
    cardViewBtn: null,
    gridViewBtn: null,
    themeToggle: null
};

// 초기화
document.addEventListener('DOMContentLoaded', function() {
    initializeElements();
    initializeEventListeners();
    loadWishlist();
    loadInitialTheme();
    loadTickets();
});

/**
 * DOM 요소 초기화
 */
function initializeElements() {
    elements.ticketsContainer = document.getElementById('tickets-container');
    elements.loadingSpinner = document.getElementById('loadingSpinner');
    elements.noResults = document.getElementById('noResults');
    elements.searchInput = document.getElementById('search-input');
    
    // Filters
    elements.platformFilters = document.querySelectorAll('aside input[type="checkbox"][name="platform"]');
    elements.genreFilters = document.querySelectorAll('aside input[type="checkbox"][name="genre"]');
    elements.dateFilterButtons = document.querySelectorAll('aside button[data-range]');
    elements.dateStartInput = document.getElementById('date-start');
    elements.dateEndInput = document.getElementById('date-end');

    // Sorting and View
    elements.sortSelect = document.getElementById('sort-select');
    elements.cardViewBtn = document.getElementById('card-view-btn');
    elements.gridViewBtn = document.getElementById('grid-view-btn');

    // Theme
    elements.themeToggle = document.getElementById('theme-toggle');
}

/**
 * 찜 목록을 로컬 저장소에서 불러옵니다.
 */
function loadWishlist() {
    const storedWishlist = localStorage.getItem('ticketWishlist');
    if (storedWishlist) {
        wishlist = JSON.parse(storedWishlist);
    }
}

/**
 * 찜 목록을 로컬 저장소에 저장합니다.
 */
function saveWishlist() {
    localStorage.setItem('ticketWishlist', JSON.stringify(wishlist));
}

/**
 * 찜 상태를 토글합니다.
 * @param {string} ticketId - 티켓 ID
 */
function toggleWishlist(ticketId) {
    const index = wishlist.indexOf(ticketId);
    if (index > -1) {
        wishlist.splice(index, 1); // 찜 목록에서 제거
    } else {
        wishlist.push(ticketId); // 찜 목록에 추가
    }
    saveWishlist();
    updateWishlistUI();
}

/**
 * 찜 목록 UI를 업데이트합니다.
 */
function updateWishlistUI() {
    document.querySelectorAll('.wishlist-btn').forEach(btn => {
        const ticketId = btn.dataset.id;
        const icon = btn.querySelector('i');
        if (wishlist.includes(ticketId)) {
            icon.classList.remove('ri-heart-line');
            icon.classList.add('ri-heart-fill');
            btn.classList.add('text-primary');
        } else {
            icon.classList.remove('ri-heart-fill');
            icon.classList.add('ri-heart-line');
            btn.classList.remove('text-primary');
        }
    });
}

/**
 * 이벤트 리스너 초기화
 */
function initializeEventListeners() {
    // 검색 입력
    let searchTimeout;
    elements.searchInput.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(applyFiltersAndSort, 300);
    });

    // 필터 변경
    document.querySelectorAll('aside input[type="checkbox"]').forEach(cb => {
        cb.addEventListener('change', applyFiltersAndSort);
    });

    // 날짜 필터 버튼
    elements.dateFilterButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const range = btn.dataset.range;
            const today = new Date();
            let startDate, endDate;

            // 모든 버튼의 활성 상태 초기화
            elements.dateFilterButtons.forEach(b => b.classList.remove('bg-primary', 'text-white'));
            // 클릭된 버튼 활성 상태로 변경
            btn.classList.add('bg-primary', 'text-white');

            switch (range) {
                case 'today':
                    startDate = new Date(today);
                    endDate = new Date(today);
                    break;
                case 'week':
                    const currentDay = today.getDay();
                    startDate = new Date(today);
                    startDate.setDate(today.getDate() - currentDay);
                    endDate = new Date(startDate);
                    endDate.setDate(startDate.getDate() + 6);
                    break;
                case 'month':
                    startDate = new Date(today.getFullYear(), today.getMonth(), 1);
                    endDate = new Date(today.getFullYear(), today.getMonth() + 1, 0);
                    break;
            }

            // yyyy-mm-dd 형식으로 변환
            elements.dateStartInput.value = startDate.toISOString().split('T')[0];
            elements.dateEndInput.value = endDate.toISOString().split('T')[0];

            applyFiltersAndSort();
        });
    });

    // 날짜 직접 선택 시, 날짜 필터 버튼 비활성화
    [elements.dateStartInput, elements.dateEndInput].forEach(input => {
        input.addEventListener('change', () => {
            elements.dateFilterButtons.forEach(b => b.classList.remove('bg-primary', 'text-white'));
            applyFiltersAndSort();
        });
    });


    // 정렬 변경
    elements.sortSelect.addEventListener('change', applyFiltersAndSort);

    // 뷰 변경
    elements.cardViewBtn.addEventListener('click', () => switchView('card'));
    elements.gridViewBtn.addEventListener('click', () => switchView('grid'));

    // 테마 변경
    elements.themeToggle.addEventListener('click', toggleTheme);

    // 찜하기 버튼 이벤트 위임
    elements.ticketsContainer.addEventListener('click', e => {
        const wishlistBtn = e.target.closest('.wishlist-btn');
        if (wishlistBtn) {
            const ticketId = wishlistBtn.dataset.id;
            toggleWishlist(ticketId);
        }
    });

    // 키보드 단축키
    document.addEventListener('keydown', e => {
        if (e.key === '/' && document.activeElement.tagName !== 'INPUT') {
            e.preventDefault();
            elements.searchInput.focus();
        }
    });
}

function applyFiltersAndSort() {
    let tempTickets = [...currentTickets];

    // 1. Search Filter
    const searchTerm = elements.searchInput.value.toLowerCase();
    if (searchTerm) {
        tempTickets = tempTickets.filter(ticket => 
            ticket.title.toLowerCase().includes(searchTerm) || 
            (ticket.artist && ticket.artist.toLowerCase().includes(searchTerm))
        );
    }

    // 2. Platform Filter
    const selectedPlatforms = [...elements.platformFilters].filter(cb => cb.checked).map(cb => cb.dataset.platform);
    if (selectedPlatforms.length > 0) {
        tempTickets = tempTickets.filter(ticket => selectedPlatforms.includes(ticket.platform));
    }

    // 3. Genre Filter
    const selectedGenres = [...elements.genreFilters].filter(cb => cb.checked).map(cb => cb.dataset.genre);
    if (selectedGenres.length > 0) {
        tempTickets = tempTickets.filter(ticket => selectedGenres.includes(ticket.genre));
    }

    // 4. Date Filter
    const startDateValue = elements.dateStartInput.value;
    const endDateValue = elements.dateEndInput.value;

    if (startDateValue) {
        const startDate = new Date(startDateValue);
        startDate.setHours(0, 0, 0, 0); // 시간 부분을 0으로 설정하여 날짜만 비교
        tempTickets = tempTickets.filter(ticket => {
            const openDate = new Date(ticket.open_date);
            openDate.setHours(0, 0, 0, 0);
            return openDate >= startDate;
        });
    }
    if (endDateValue) {
        const endDate = new Date(endDateValue);
        endDate.setHours(23, 59, 59, 999); // 시간 부분을 마지막으로 설정
        tempTickets = tempTickets.filter(ticket => {
            const openDate = new Date(ticket.open_date);
            openDate.setHours(0, 0, 0, 0);
            return openDate <= endDate;
        });
    }

    // 5. Sorting
    const sortValue = elements.sortSelect.value;
    switch (sortValue) {
        case '인기순': // Placeholder for popularity
            tempTickets.sort((a, b) => (b.views || 0) - (a.views || 0));
            break;
        case '마감임박순':
            tempTickets.sort((a, b) => new Date(a.open_date) - new Date(b.open_date));
            break;
        case '최신순':
        default:
            tempTickets.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
            break;
    }

    filteredTickets = tempTickets;
    renderTickets();
}

function switchView(view) {
    currentView = view;
    const container = elements.ticketsContainer;
    if (view === 'grid') {
        container.classList.remove('grid-cols-1');
        container.classList.add('md:grid-cols-2', 'xl:grid-cols-3');
        elements.gridViewBtn.classList.add('bg-white', 'text-primary', 'shadow-sm');
        elements.cardViewBtn.classList.remove('bg-white', 'text-primary', 'shadow-sm');
    } else { // card view
        container.classList.add('grid-cols-1');
        container.classList.remove('md:grid-cols-2', 'xl:grid-cols-3');
        elements.cardViewBtn.classList.add('bg-white', 'text-primary', 'shadow-sm');
        elements.gridViewBtn.classList.remove('bg-white', 'text-primary', 'shadow-sm');
    }
}

function toggleTheme() {
    const html = document.documentElement;
    html.classList.toggle('dark');
    const isDarkMode = html.classList.contains('dark');
    localStorage.setItem('theme', isDarkMode ? 'dark' : 'light');
    updateThemeIcon(isDarkMode);
}

function updateThemeIcon(isDarkMode) {
    const icon = elements.themeToggle.querySelector('i');
    if (isDarkMode) {
        icon.classList.remove('ri-sun-line');
        icon.classList.add('ri-moon-line');
    } else {
        icon.classList.remove('ri-moon-line');
        icon.classList.add('ri-sun-line');
    }
}

function loadInitialTheme() {
    const theme = localStorage.getItem('theme');
    const isDarkMode = theme === 'dark';
    if (isDarkMode) {
        document.documentElement.classList.add('dark');
    }
    updateThemeIcon(isDarkMode);
}

function renderTickets() {
    const container = elements.ticketsContainer;
    if (!container) return;
    container.innerHTML = ''; // Clear existing tickets

    if (filteredTickets.length === 0) {
        // elements.noResults.classList.remove('hidden');
        return;
    }

    // elements.noResults.classList.add('hidden');

    const fragment = document.createDocumentFragment();
    filteredTickets.forEach(ticket => {
        const card = createTicketCard(ticket);
        fragment.appendChild(card);
    });

    container.appendChild(fragment);
    updateWishlistUI();
}

function createTicketCard(ticket) {
    const div = document.createElement('div');
    div.className = 'ticket-card bg-white rounded-lg shadow-sm overflow-hidden border border-gray-100 transition-all duration-300 dark:bg-gray-800 dark:border-gray-700';
    div.dataset.ticketId = ticket.id;

    const dDay = ticket.d_day ? `<div class="absolute bottom-3 left-3 bg-primary text-white text-xs px-2 py-1 rounded-full">${ticket.d_day}</div>` : '';

    div.innerHTML = `
        <div class="relative">
            <img src="${ticket.image_url}" alt="${ticket.title}" class="w-full h-48 object-cover object-top">
            <button class="wishlist-btn absolute top-3 right-3 bg-white rounded-full p-1 shadow-md text-gray-400 hover:text-primary cursor-pointer dark:bg-gray-700 dark:text-gray-400" data-id="${ticket.id}">
                <div class="w-6 h-6 flex items-center justify-center">
                    <i class="ri-heart-line"></i>
                </div>
            </button>
            ${dDay}
        </div>
        <div class="p-4">
            <div class="flex items-center mb-2">
                <div class="w-5 h-5 flex items-center justify-center mr-1">
                    <i class="ri-ticket-line text-primary"></i>
                </div>
                <span class="text-xs text-gray-500 dark:text-gray-400">${ticket.open_date_str} 오픈</span>
            </div>
            <h3 class="font-bold text-gray-800 mb-1 dark:text-gray-200">${ticket.title}</h3>
            <p class="text-sm text-gray-600 mb-3 dark:text-gray-400">${ticket.date} | ${ticket.place}</p>
            <div class="flex items-center justify-between">
                <span class="text-xs px-2 py-1 bg-gray-100 rounded-full dark:bg-gray-700 dark:text-gray-300">${ticket.genre}</span>
                <div class="flex items-center">
                    <div class="w-5 h-5 flex items-center justify-center mr-1 text-blue-500">
                        <i class="ri-melody-fill"></i>
                    </div>
                    <span class="text-xs text-gray-500 dark:text-gray-400">${ticket.platform}</span>
                </div>
            </div>
        </div>
    `;
    return div;
}

/**
 * 티켓 데이터 로드
 */
async function loadTickets() {
    if (isLoading) return;
    // showLoading(true);
    
    try {
        const response = await fetch('/api/tickets');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        
        currentTickets = data.tickets || [];
        applyFiltersAndSort();
        
    } catch (error) {
        console.error('티켓 데이터 로드 실패:', error);
        // showError('티켓 데이터를 불러오는데 실패했습니다.');
    } finally {
        // showLoading(false);
    }
}