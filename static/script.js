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
const mockTickets = [
    {
        id: '1', title: '아이유 콘서트', artist: '아이유', open_date: '2024-08-01T10:00:00', open_date_str: '2024.08.01 10:00',
        date: '2024.09.21 - 2024.09.22', place: 'KSPO DOME', genre: '콘서트', platform: '멜론티켓', 
        image_url: 'https://via.placeholder.com/300x200/4f46e5/ffffff?text=IU', d_day: 'D-10', created_at: '2024-07-20T10:00:00', views: 1200
    },
    {
        id: '2', title: '뮤지컬 <헤드윅>', artist: '조정석', open_date: '2024-07-25T14:00:00', open_date_str: '2024.07.25 14:00',
        date: '2024.08.10 - 2024.10.27', place: '샤롯데씨어터', genre: '뮤지컬', platform: '인터파크', 
        image_url: 'https://via.placeholder.com/300x200/d946ef/ffffff?text=Hedwig', d_day: 'D-3', created_at: '2024-07-18T10:00:00', views: 850
    },
    {
        id: '3', title: '싸이 흠뻑쇼', artist: '싸이', open_date: '2024-06-10T20:00:00', open_date_str: '2024.06.10 20:00',
        date: '2024.07.27 - 2024.08.25', place: '전국', genre: '콘서트', platform: 'YES24', 
        image_url: 'https://via.placeholder.com/300x200/22c55e/ffffff?text=PSY', d_day: null, created_at: '2024-06-01T10:00:00', views: 2500
    }
];

document.addEventListener('DOMContentLoaded', function() {
    initializeElements();
    initializeEventListeners();
    loadWishlist();
    loadInitialTheme();
    
    // Use mock data for now
    currentTickets = mockTickets;
    filteredTickets = [...mockTickets];
    renderTickets();
});

/**
 * DOM 요소 초기화
 */
function initializeElements() {
    elements.ticketsContainer = document.querySelector('.grid'); // Updated selector
    elements.loadingSpinner = document.getElementById('loadingSpinner'); // Assuming you have this element
    elements.noResults = document.getElementById('noResults'); // Assuming you have this element
    elements.searchInput = document.querySelector('input[type="text"][placeholder*="검색"]');
    
    // Filters
    elements.platformFilters = document.querySelectorAll('aside input[type="checkbox"][name="platform"]');
    elements.genreFilters = document.querySelectorAll('aside input[type="checkbox"][name="genre"]');
    elements.dateFilterButtons = document.querySelectorAll('aside button[data-range]');
    elements.dateStartInput = document.querySelector('aside input[type="date"]:first-of-type');
    elements.dateEndInput = document.querySelector('aside input[type="date"]:last-of-type');

    // Sorting and View
    elements.sortSelect = document.querySelector('main select');
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
    document.querySelectorAll('aside button[data-range]').forEach(btn => {
        btn.addEventListener('click', () => {
            // Date range logic here
            applyFiltersAndSort();
        });
    });
    [elements.dateStartInput, elements.dateEndInput].forEach(input => {
        input.addEventListener('change', applyFiltersAndSort);
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
    const startDate = elements.dateStartInput.valueAsDate;
    const endDate = elements.dateEndInput.valueAsDate;
    if (startDate) {
        tempTickets = tempTickets.filter(ticket => new Date(ticket.open_date) >= startDate);
    }
    if (endDate) {
        tempTickets = tempTickets.filter(ticket => new Date(ticket.open_date) <= endDate);
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
 * 드롭다운 초기화
 */
function initializeDropdowns() {
    // This function might be removed or refactored if no longer needed
    const dropdowns = document.querySelectorAll('.dropdown');
    
    dropdowns.forEach(dropdown => {
        const button = dropdown.querySelector('.dropdown-button');
        const menu = dropdown.querySelector('.dropdown-menu');
        const options = dropdown.querySelectorAll('.dropdown-option');
        
        if (!button || !menu) return;
        
        // 드롭다운 버튼 클릭
        button.addEventListener('click', function(e) {
            e.stopPropagation();
            
            // 다른 드롭다운 닫기
            dropdowns.forEach(otherDropdown => {
                if (otherDropdown !== dropdown) {
                    otherDropdown.classList.remove('active');
                }
            });
            
            // 현재 드롭다운 토글
            dropdown.classList.toggle('active');
        });
        
        // 옵션 선택
        options.forEach(option => {
            option.addEventListener('click', function(e) {
                e.stopPropagation();
                
                const value = this.dataset.value;
                const text = this.textContent;
                
                // 버튼 텍스트 업데이트
                const buttonText = button.querySelector('.dropdown-text');
                if (buttonText) {
                    buttonText.textContent = text;
                }
                
                // 선택된 옵션 표시
                options.forEach(opt => opt.classList.remove('selected'));
                this.classList.add('selected');
                
                // 드롭다운 닫기
                dropdown.classList.remove('active');
                
                // 해당 필터 업데이트
                updateFilterFromDropdown(dropdown, value);
            });
        });
    });
    
    // 외부 클릭 시 모든 드롭다운 닫기
    document.addEventListener('click', function() {
        dropdowns.forEach(dropdown => {
            dropdown.classList.remove('active');
        });
    });
}

/**
 * 드롭다운에서 필터 업데이트
 */
function updateFilterFromDropdown(dropdown, value) {
    const filterId = dropdown.dataset.filter;
    
    switch (filterId) {
        case 'platform':
            if (elements.platformFilter) {
                elements.platformFilter.value = value;
                applyFilters();
            }
            break;
        case 'genre':
            if (elements.genreFilter) {
                elements.genreFilter.value = value;
                applyFilters();
            }
            break;
        case 'date':
            if (elements.dateFilter) {
                elements.dateFilter.value = value;
                applyFilters();
            }
            break;
        case 'sort':
            if (elements.sortFilter) {
                elements.sortFilter.value = value;
                applySorting();
            }
            break;
    }
}

/**
 * 티켓 데이터 로드
 */
async function loadTickets() {
    if (isLoading) return;
    
    showLoading(true);
    
    try {
        const response = await fetch('/api/tickets?limit=100');
        const data = await response.json();
        
        currentTickets = data.tickets || [];
        applyFilters(); // 필터와 정렬 모두 적용
        
    } catch (error) {
        console.error('티켓 데이터 로드 실패:', error);
        showError('티켓 데이터를 불러오는데 실패했습니다.');
    } finally {
        showLoading(false);
    }
}

/**
 * 데이터 새로고침 (관리자 전용)
 */
async function refreshData() {
    if (isLoading || !isAdmin) return;
    
    const originalText = elements.refreshBtn.innerHTML;
    elements.refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 새로고침 중...';
    elements.refreshBtn.disabled = true;
    
    try {
        // 관리자 권한으로 수동 새로고침 요청
        const response = await fetch('/api/refresh?user=admin', {
            method: 'POST'
        });
        
        if (response.status === 403) {
            showNotification('관리자 권한이 필요합니다.', 'error');
            return;
        }
        
        const data = await response.json();
        
        if (data.status === 'success') {
            await loadTickets();
            lastUpdateTime = new Date(data.last_update);
            updateLastUpdateDisplay();
            showNotification('데이터가 성공적으로 새로고침되었습니다.', 'success');
            
            // 자동 갱신 타이머 재시작
            startAutoRefresh();
        }
    } catch (error) {
        console.error('데이터 새로고침 실패:', error);
        showNotification('데이터 새로고침에 실패했습니다.', 'error');
    } finally {
        elements.refreshBtn.innerHTML = originalText;
        elements.refreshBtn.disabled = false;
    }
}

/**
 * 자동 갱신 시작
 */
function startAutoRefresh() {
    // 기존 타이머 정리
    if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
    }
    
    // 새 타이머 시작 (1시간마다)
    autoRefreshTimer = setInterval(async () => {
        try {
            await autoRefreshData();
            console.log('자동 갱신 완료');
        } catch (error) {
            console.error('자동 갱신 실패:', error);
        }
    }, autoRefreshInterval);
    
    console.log(`자동 갱신 타이머 시작: ${autoRefreshInterval / 1000}초마다`);
}

/**
 * 자동 데이터 갱신 (백그라운드)
 */
async function autoRefreshData() {
    try {
        // 업데이트 정보만 가져와서 데이터 영역만 갱신
        const response = await fetch('/api/update-info');
        const updateInfo = await response.json();
        
        // 새로운 데이터가 있는지 확인
        if (updateInfo.last_update) {
            const serverUpdateTime = new Date(updateInfo.last_update);
            
            // 서버의 업데이트 시간이 클라이언트보다 최신인 경우에만 갱신
            if (!lastUpdateTime || serverUpdateTime > lastUpdateTime) {
                await loadTickets();
                lastUpdateTime = serverUpdateTime;
                updateLastUpdateDisplay();
                
                // 조용한 알림 (사용자가 페이지를 보고 있을 때만)
                if (document.visibilityState === 'visible') {
                    showNotification('새로운 티켓 정보가 업데이트되었습니다.', 'info');
                }
            }
        }
    } catch (error) {
        console.error('자동 갱신 실패:', error);
    }
}

/**
 * 필터 적용
 */
async function applyFilters() {
    if (isLoading) return;
    
    showLoading(true);
    
    try {
        const params = new URLSearchParams();
        
        const platform = elements.platformFilter?.value || '전체';
        const genre = elements.genreFilter?.value || '전체';
        const dateFilter = elements.dateFilter?.value || '전체';
        const search = elements.searchInput?.value?.trim() || '';
        
        if (platform && platform !== '전체') params.append('platform', platform);
        if (genre && genre !== '전체') params.append('genre', genre);
        if (dateFilter && dateFilter !== '전체') params.append('date_filter', dateFilter);
        if (search) params.append('search', search);
        
        params.append('limit', '100');
        
        const response = await fetch(`/api/tickets?${params.toString()}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        filteredTickets = data.tickets || [];
        applySorting(); // 필터 적용 후 정렬도 함께 적용
        
        // 필터 결과 통계 업데이트
        updateFilterStats(data.total || filteredTickets.length);
        
    } catch (error) {
        console.error('필터 적용 실패:', error);
        showError('필터 적용에 실패했습니다.');
        filteredTickets = currentTickets; // 원본 데이터로 복원
        applySorting();
    } finally {
        showLoading(false);
    }
}

/**
 * 필터 결과 통계 업데이트
 */
function updateFilterStats(totalCount) {
    const statsElement = document.querySelector('.filter-stats');
    if (statsElement) {
        statsElement.textContent = `총 ${totalCount}개의 티켓`;
    }
}

/**
 * 티켓 목록 렌더링
 */
function renderTickets(tickets) {
    if (!tickets || tickets.length === 0) {
        showNoResults(true);
        return;
    }
    
    showNoResults(false);
    
    const container = elements.ticketsContainer;
    container.innerHTML = '';
    
    tickets.forEach(ticket => {
        const ticketElement = createTicketElement(ticket);
        container.appendChild(ticketElement);
    });

    // 찜하기 UI 업데이트
    updateWishlistUI();
}

/**
 * 티켓 카드 요소 생성
 */
function createTicketElement(ticket) {
    const div = document.createElement('div');
    div.className = 'ticket-card';
    
    const openDate = ticket.open_date || '미정';
    const dateClass = getDateClass(openDate);
    const platform = ticket.source || '알 수 없음';
    const title = ticket.title || '제목 없음';
    const place = ticket.place || '장소 미정';
    const link = ticket.link || '#';
    
    div.innerHTML = `
        <div class="ticket-header">
            <span class="platform-tag ${getPlatformClass(platform)}">${escapeHtml(platform)}</span>
            <span class="ticket-date ${dateClass}">${escapeHtml(openDate)}</span>
        </div>
        
        <h3 class="ticket-title">${escapeHtml(title)}</h3>
        
        <div class="ticket-info">
            <div class="ticket-info-item">
                <i class="fas fa-map-marker-alt"></i>
                <span>${escapeHtml(place)}</span>
            </div>
            <div class="ticket-info-item">
                <i class="fas fa-clock"></i>
                <span>수집 시간: ${formatCollectedTime(ticket.collected_at)}</span>
            </div>
        </div>
        
        <div class="ticket-actions">
            <a href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer" class="ticket-link">
                <i class="fas fa-external-link-alt"></i>
                티켓 보기
            </a>
        </div>
    `;
    
    // 클릭 이벤트 추가
    div.addEventListener('click', function(e) {
        if (e.target.tagName !== 'A') {
            window.open(link, '_blank', 'noopener,noreferrer');
        }
    });
    
    return div;
}

/**
 * 날짜에 따른 CSS 클래스 반환
 */
function getDateClass(dateStr) {
    if (!dateStr || dateStr === '미정') return '';
    
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    
    try {
        // 다양한 날짜 형식 파싱
        let ticketDate;
        
        if (dateStr.includes('.')) {
            const parts = dateStr.split('.');
            if (parts.length === 2) {
                // MM.DD 형식
                ticketDate = new Date(today.getFullYear(), parseInt(parts[0]) - 1, parseInt(parts[1]));
            } else if (parts.length === 3) {
                // YYYY.MM.DD 형식
                ticketDate = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
            }
        } else if (dateStr.includes('/')) {
            const parts = dateStr.split('/');
            if (parts.length === 2) {
                // MM/DD 형식
                ticketDate = new Date(today.getFullYear(), parseInt(parts[0]) - 1, parseInt(parts[1]));
            }
        }
        
        if (ticketDate) {
            const todayStr = today.toDateString();
            const tomorrowStr = tomorrow.toDateString();
            const ticketStr = ticketDate.toDateString();
            
            if (ticketStr === todayStr) {
                return 'urgent';
            } else if (ticketStr === tomorrowStr) {
                return 'soon';
            }
        }
    } catch (error) {
        console.warn('날짜 파싱 실패:', dateStr, error);
    }
    
    return '';
}

/**
 * 수집 시간 포맷팅
 */
function formatCollectedTime(timestamp) {
    if (!timestamp) return '알 수 없음';
    
    try {
        const date = new Date(timestamp);
        return date.toLocaleString('ko-KR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (error) {
        return '알 수 없음';
    }
}

/**
 * HTML 이스케이프
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * 뷰 변경
 */
function changeView(view) {
    currentView = view;
    
    // 버튼 상태 업데이트
    elements.viewBtns.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === view);
    });
    
    // 컨테이너 클래스 변경
    const container = elements.ticketsContainer;
    container.className = view === 'grid' ? 'tickets-grid' : 'tickets-list';
}

/**
 * 로딩 상태 표시
 */
function showLoading(show) {
    isLoading = show;
    elements.loadingSpinner.style.display = show ? 'block' : 'none';
    elements.ticketsContainer.style.display = show ? 'none' : '';
    elements.noResults.style.display = 'none';
}

/**
 * 결과 없음 상태 표시
 */
function showNoResults(show) {
    elements.noResults.style.display = show ? 'block' : 'none';
    elements.ticketsContainer.style.display = show ? 'none' : '';
}

/**
 * 에러 표시
 */
function showError(message) {
    elements.ticketsContainer.innerHTML = `
        <div class="error-message">
            <i class="fas fa-exclamation-triangle"></i>
            <h3>오류가 발생했습니다</h3>
            <p>${escapeHtml(message)}</p>
            <button onclick="location.reload()" class="btn btn-primary">
                <i class="fas fa-refresh"></i>
                페이지 새로고침
            </button>
        </div>
    `;
}

/**
 * 알림 표시
 */
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas ${type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle'}"></i>
            <span>${escapeHtml(message)}</span>
        </div>
        <button class="notification-close">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    // 스타일 추가
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? 'var(--success-color)' : type === 'error' ? 'var(--danger-color)' : 'var(--primary-color)'};
        color: white;
        padding: 1rem 1.5rem;
        border-radius: var(--border-radius);
        box-shadow: var(--shadow-lg);
        z-index: 1000;
        display: flex;
        align-items: center;
        gap: 1rem;
        max-width: 400px;
        animation: slideIn 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    // 닫기 버튼 이벤트
    notification.querySelector('.notification-close').addEventListener('click', () => {
        notification.remove();
    });
    
    // 자동 제거
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

/**
 * 마지막 업데이트 시간 표시 갱신
 */
function updateLastUpdateDisplay() {
    if (!lastUpdateTime) return;
    
    const timeString = lastUpdateTime.toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
    
    if (elements.lastUpdate) {
        elements.lastUpdate.textContent = timeString;
    }
    if (elements.footerLastUpdate) {
        elements.footerLastUpdate.textContent = timeString;
    }
}

/**
 * 페이지 언로드 시 타이머 정리
 */
window.addEventListener('beforeunload', function() {
    if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
    }
});

// CSS 애니메이션 추가
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    .notification {
        animation: slideIn 0.3s ease;
    }
    
    .notification-content {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        flex: 1;
    }
    
    .notification-close {
        background: none;
        border: none;
        color: white;
        cursor: pointer;
        padding: 0.25rem;
        border-radius: 50%;
        transition: background-color 0.2s ease;
    }
    
    .notification-close:hover {
        background-color: rgba(255, 255, 255, 0.2);
    }
    
    .error-message {
        text-align: center;
        padding: 3rem;
        color: var(--text-secondary);
    }
    
    .error-message i {
        font-size: 3rem;
        margin-bottom: 1rem;
        color: var(--danger-color);
    }
    
    .error-message h3 {
        font-size: 1.25rem;
        margin-bottom: 0.5rem;
        color: var(--text-primary);
    }
    
    .error-message p {
        margin-bottom: 1.5rem;
    }
`;
document.head.appendChild(style);

/**
 * 정렬 적용
 */
function applySorting() {
    if (filteredTickets.length === 0) {
        renderTickets([]);
        return;
    }
    
    const sortValue = elements.sortFilter?.value || 'open_date_asc';
    const sortedTickets = [...filteredTickets];
    
    switch (sortValue) {
        case 'open_date_desc':
            sortedTickets.sort((a, b) => {
                const dateA = parseTicketDate(a.open_date);
                const dateB = parseTicketDate(b.open_date);
                return dateB - dateA;
            });
            break;
            
        case 'open_date_asc':
        default:
            sortedTickets.sort((a, b) => {
                const dateA = parseTicketDate(a.open_date);
                const dateB = parseTicketDate(b.open_date);
                return dateA - dateB;
            });
            break;
            
        case 'performance_date_asc':
            sortedTickets.sort((a, b) => {
                const dateA = parseTicketDate(a.performance_date || a.open_date);
                const dateB = parseTicketDate(b.performance_date || b.open_date);
                return dateA - dateB;
            });
            break;
            
        case 'title_asc':
            sortedTickets.sort((a, b) => {
                const titleA = (a.title || '').toLowerCase();
                const titleB = (b.title || '').toLowerCase();
                return titleA.localeCompare(titleB, 'ko');
            });
            break;
            
        case 'artist_asc':
            sortedTickets.sort((a, b) => {
                const artistA = extractArtistName(a.title || '').toLowerCase();
                const artistB = extractArtistName(b.title || '').toLowerCase();
                return artistA.localeCompare(artistB, 'ko');
            });
            break;
            
        case 'popularity_desc':
            // 인기순은 수집 시간이 최근인 것을 우선으로 정렬
            sortedTickets.sort((a, b) => {
                const timeA = new Date(a.collected_at || 0);
                const timeB = new Date(b.collected_at || 0);
                return timeB - timeA;
            });
            break;
    }
    
    renderTickets(sortedTickets);
}

/**
 * 아티스트 이름 추출 (제목에서)
 */
function extractArtistName(title) {
    // 간단한 아티스트 이름 추출 로직
    // 예: "아이유 콘서트" -> "아이유"
    const patterns = [
        /^([가-힣a-zA-Z0-9\s]+)\s+(콘서트|공연|투어|리사이틀)/,
        /^([가-힣a-zA-Z0-9\s]+)\s+/,
        /([가-힣a-zA-Z0-9]+)/
    ];
    
    for (const pattern of patterns) {
        const match = title.match(pattern);
        if (match && match[1]) {
            return match[1].trim();
        }
    }
    
    return title;
}

/**
 * 티켓 날짜 파싱
 */
function parseTicketDate(dateStr) {
    if (!dateStr || dateStr === '미정') {
        return new Date(0); // 미정인 경우 가장 오래된 날짜로 처리
    }
    
    const today = new Date();
    
    try {
        if (dateStr.includes('.')) {
            const parts = dateStr.split('.');
            if (parts.length === 2) {
                // MM.DD 형식
                return new Date(today.getFullYear(), parseInt(parts[0]) - 1, parseInt(parts[1]));
            } else if (parts.length === 3) {
                // YYYY.MM.DD 형식
                return new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
            }
        } else if (dateStr.includes('/')) {
            const parts = dateStr.split('/');
            if (parts.length === 2) {
                // MM/DD 형식
                return new Date(today.getFullYear(), parseInt(parts[0]) - 1, parseInt(parts[1]));
            }
        }
        
        // ISO 형식 시도
        const parsed = new Date(dateStr);
        if (!isNaN(parsed.getTime())) {
            return parsed;
        }
    } catch (error) {
        console.warn('날짜 파싱 실패:', dateStr, error);
    }
    
    return new Date(0);
}

/**
 * 플랫폼별 CSS 클래스 반환
 */
function getPlatformClass(platform) {
    if (!platform) return 'default';
    
    const platformLower = platform.toLowerCase();
    
    if (platformLower.includes('interpark') || platformLower.includes('인터파크')) {
        return 'interpark';
    } else if (platformLower.includes('melon') || platformLower.includes('멜론')) {
        return 'melon';
    } else if (platformLower.includes('yes24')) {
        return 'yes24';
    } else {
        return 'default';
    }
}