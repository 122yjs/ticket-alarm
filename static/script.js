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
    refreshBtn: null,
    platformFilter: null,
    genreFilter: null,
    dateFilter: null,
    sortFilter: null,
    searchInput: null,
    viewBtns: null,
    lastUpdate: null,
    footerLastUpdate: null
};

// 초기화
document.addEventListener('DOMContentLoaded', function() {
    // 서버에서 전달받은 설정값 적용
    if (window.APP_CONFIG) {
        isAdmin = window.APP_CONFIG.isAdmin || false;
        autoRefreshInterval = window.APP_CONFIG.autoRefreshInterval || 3600000;
        if (window.APP_CONFIG.lastUpdateIso) {
            lastUpdateTime = new Date(window.APP_CONFIG.lastUpdateIso);
        }
    }
    
    initializeElements();
    initializeEventListeners();
    initializeDropdowns();
    loadWishlist(); // 찜 목록 로드
    loadTickets();
    
    // 자동 갱신 타이머 시작 (1시간마다)
    startAutoRefresh();
    
    // 업데이트 시간 표시 갱신
    updateLastUpdateDisplay();
});

/**
 * DOM 요소 초기화
 */
function initializeElements() {
    elements.ticketsContainer = document.getElementById('ticketsContainer');
    elements.loadingSpinner = document.getElementById('loadingSpinner');
    elements.noResults = document.getElementById('noResults');
    elements.refreshBtn = document.getElementById('refreshBtn');
    elements.platformFilter = document.getElementById('platformFilter');
    elements.genreFilter = document.getElementById('genreFilter');
    elements.dateFilter = document.getElementById('dateFilter');
    elements.sortFilter = document.getElementById('sortFilter');
    elements.searchInput = document.getElementById('searchInput');
    elements.viewBtns = document.querySelectorAll('.view-btn');
    elements.lastUpdate = document.getElementById('lastUpdate');
    elements.footerLastUpdate = document.getElementById('footerLastUpdate');
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
    // 새로고침 버튼 (관리자만)
    if (elements.refreshBtn && isAdmin) {
        elements.refreshBtn.addEventListener('click', refreshData);
    }
    
    // 필터 변경
    elements.platformFilter.addEventListener('change', applyFilters);
    elements.genreFilter.addEventListener('change', applyFilters);
    elements.dateFilter.addEventListener('change', applyFilters);
    elements.sortFilter.addEventListener('change', applySorting);
    
    // 검색 입력
    let searchTimeout;
    elements.searchInput.addEventListener('input', function() {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(applyFilters, 300);
    });
    
    // 뷰 변경
    elements.viewBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const view = this.dataset.view;
            changeView(view);
        });
    });
    
    // 찜하기 버튼 이벤트 위임
    if (elements.ticketsContainer) {
        elements.ticketsContainer.addEventListener('click', function(e) {
            const wishlistBtn = e.target.closest('.wishlist-btn');
            if (wishlistBtn) {
                const ticketId = wishlistBtn.dataset.id;
                toggleWishlist(ticketId);
            }
        });
    }

    // 키보드 단축키
    document.addEventListener('keydown', function(e) {
        // Ctrl + R: 새로고침 (관리자만)
        if (e.ctrlKey && e.key === 'r' && isAdmin) {
            e.preventDefault();
            refreshData();
        }
        
        // '/': 검색창 포커스
        if (e.key === '/' && !e.ctrlKey && !e.altKey) {
            e.preventDefault();
            elements.searchInput.focus();
        }
    });
}

/**
 * 드롭다운 초기화
 */
function initializeDropdowns() {
    // 모든 드롭다운 요소 찾기
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