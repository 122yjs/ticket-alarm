# **티켓링크 상품 목록 API 설계 명세서 (v1.1)**

## 1. 개요

티켓링크 웹사이트에서 '공연' 또는 '스포츠' 카테고리의 상품 목록 데이터를 가져오기 위한 내부 API의 명세입니다. 이 명세는 웹 스크래핑 방식의 한계를 극복하고, 안정적이고 효율적인 데이터 수집을 목표로 합니다.

*   **API 엔드포인트 URL:** `https://www.ticketlink.co.kr/api/product/v1/search` (가설)
*   **HTTP 메서드:** `POST`

## 2. 요청 (Request)

### 2.1. 요청 헤더 (Headers)

| Key | Value | 설명 |
| :--- | :--- | :--- |
| `User-Agent` | `Mozilla/5.0 ...` | 서버가 정상적인 브라우저 요청으로 인식하도록 하는 필수 헤더입니다. |
| `Referer` | `https://www.ticketlink.co.kr/` | 요청의 출처를 명시하여 일부 보안 검사를 우회하기 위한 헤더입니다. |
| `Content-Type`| `application/json` | 요청 본문(Body)이 JSON 형식임을 명시합니다. |

### 2.2. 요청 파라미터 (Request Body)

요청 본문은 다음 필드를 포함하는 JSON 객체입니다.

| 파라미터 명 | 타입 | 필수 | 설명 | 예시 값 |
| :--- | :--- | :--- | :--- | :--- |
| `categoryId` | String | O | 조회할 상품의 카테고리 ID입니다. '공연', '스포츠' 등을 구분합니다. | `"P0001"` (공연) |
| `page` | Integer | O | 조회할 페이지 번호입니다. | `1` |
| `size` | Integer | O | 한 페이지에 가져올 상품의 개수입니다. | `20` |
| `sort` | String | X | 상품 정렬 기준입니다. (기본값: 추천순) | `"RECENT"` (최신순) |

## 3. 응답 (Response)

### 3.1. 성공 응답 (200 OK)

요청이 성공하면, 상품 목록을 포함한 JSON 객체를 반환합니다.

```json
{
  "code": "0000",
  "message": "성공",
  "result": {
    "totalCount": 150,
    "page": 1,
    "size": 20,
    "products": [
      {
        "productId": 12345,
        "productName": "[서울] 뮤지컬 〈시카고〉",
        "categoryName": "뮤지컬",
        "genreName": "뮤지컬",
        "salesStartDate": "2025-07-15T14:00:00",
        "placeName": "블루스퀘어 신한카드홀",
        "productUrl": "/product/12345",
        "posterUrl": "https://.../poster_12345.jpg"
      }
    ]
  }
}
```

### 3.2. 실패 응답 (4xx/5xx)

요청이 실패하면, 오류 코드와 메시지를 포함한 JSON 객체를 반환합니다.

```json
{
  "code": "E4001",
  "message": "잘못된 요청 파라미터입니다.",
  "result": null
}
```

## 4. 데이터 매핑

API 응답 데이터를 우리가 최종적으로 수집할 데이터 형식으로 변환하는 규칙입니다.

| 수집할 정보 | API 응답 필드 | 데이터 타입 | **필수** | 설명 |
| :--- | :--- | :--- | :--- | :--- |
| `공연명` | `productName` | String | O | 상품의 전체 이름입니다. |
| `장르` | `genreName` | String | O | 상품의 세부 장르입니다. |
| `공연날짜` | `salesStartDate`| String (ISO) | O | 예매 시작 일시 또는 공연 시작일입니다. |
| `공연장소` | `placeName` | String | O | 공연이 열리는 장소의 이름입니다. |
| `예매링크` | `productUrl` | String | O | `https://www.ticketlink.co.kr` 뒤에 붙여 완성합니다. |
| `포스터 이미지`| `posterUrl` | String | **X** | 상품 포스터 이미지의 전체 URL입니다. **(선택 사항)** |