import streamlit as st
import pandas as pd
from gnews import GNews
from datetime import datetime, timedelta
from io import BytesIO

# =================================================
# 1. 설정 및 세션 초기화
# =================================================
BUSINESS_KEYWORDS = [
    "육가공", "햄", "소시지", "식품", "원가", "가격", "가격인상",
    "마케팅", "브랜드", "유통", "편의점", "대체육", "시장", "매출"
]

if "news_results" not in st.session_state:
    st.session_state.news_results = [] 
if "cart" not in st.session_state:
    st.session_state.cart = pd.DataFrame()

google_news = GNews(language="ko", country="KR", max_results=50)

# =================================================
# 2. 기능 함수 (날짜, 검색, 점수)
# =================================================
def get_date_range():
    today = datetime.today()
    this_thursday = today - timedelta(days=(today.weekday() - 3) % 7)
    last_saturday = this_thursday - timedelta(days=5)
    return last_saturday.date(), this_thursday.date()

def parse_news_date(date_str):
    try:
        return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z").date()
    except:
        return None

def relevance_score(text: str) -> int:
    return sum(1 for kw in BUSINESS_KEYWORDS if kw in text)

def collect_news(keyword: str, start_date, end_date):
    articles = google_news.get_news(keyword)
    rows = []
    for a in articles:
        article_date = parse_news_date(a.get("published date", ""))
        if article_date is None or not (start_date <= article_date <= end_date):
            continue
        
        title = a.get("title", "")
        score = relevance_score(f"{title} {a.get('description', '')}")
        
        rows.append({
            "검색키워드": keyword,
            "출처": a.get("publisher", {}).get("title", ""),
            "기사일자": article_date.strftime("%Y-%m-%d"),
            "제목": title,
            "링크": a.get("url", ""),
            "연관도점수": score
        })
    return rows

# [핵심 수정] xlsxwriter를 사용하여 직접 링크를 심는 함수
def to_excel(df: pd.DataFrame):
    output = BytesIO()
    
    # xlsxwriter 엔진 사용
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        # 데이터프레임에서 필요한 열만 선택하여 엑셀에 먼저 씀
        export_df = df[["검색키워드", "출처", "기사일자", "제목"]]
        export_df.to_excel(writer, index=False, sheet_name="뉴스스크랩")
        
        workbook  = writer.book
        worksheet = writer.sheets["뉴스스크랩"]
        
        # 링크용 스타일 설정 (파란색 + 밑줄)
        link_format = workbook.add_format({'font_color': 'blue', 'underline': 1})
        # 헤더용 서식 (선택 사항)
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})

        # 제목 열(D열)에 하이퍼링크 직접 삽입
        # D열은 인덱스 번호 3 (A=0, B=1, C=2, D=3)
        for row_num, (index, row) in enumerate(df.iterrows()):
            link_url = row['링크']
            display_text = row['제목']
            # write_url(row, col, url, string, format)
            # row_num + 1을 하는 이유는 0번째 줄이 헤더이기 때문입니다.
            worksheet.write_url(row_num + 1, 3, link_url, link_format, display_text)
            
        # 열 너비 설정 (D열을 넓게)
        worksheet.set_column('A:C', 15)
        worksheet.set_column('D:D', 70)
        
    return output.getvalue()

# =================================================
# 3. UI 화면 구성 (Streamlit)
# =================================================
st.set_page_config(page_title="식품 뉴스 스크랩", layout="wide")
st.title("📰 식품/육가공 뉴스 스크랩 자동화")

start_date, end_date = get_date_range()
st.info(f"📅 현재 수집 기간: **{start_date} ~ {end_date}**")

# 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    keyword = st.text_input("검색어 입력")
    min_score = st.slider("연관도 필터 (키워드 포함 개수)", 0, 5, 1)
    
    if st.button("뉴스 수집 시작", use_container_width=True):
        if keyword:
            with st.spinner('구글 뉴스를 수집 중...'):
                results = collect_news(keyword, start_date, end_date)
                st.session_state.news_results = [r for r in results if r['연관도점수'] >= min_score]
        else:
            st.warning("키워드를 입력하세요.")

# 메인화면 레이아웃
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📌 검색 결과")
    if st.session_state.news_results:
        selected_items = []
        for idx, item in enumerate(st.session_state.news_results):
            # 체크박스 선택
            is_selected = st.checkbox(
                f"[{item['출처']}] {item['제목']} ({item['기사일자']})", 
                key=f"news_{idx}"
            )
            if is_selected:
                selected_items.append(item)
        
        # 선택된 데이터를 실시간으로 카트에 담기
        st.session_state.cart = pd.DataFrame(selected_items)
    else:
        st.write("왼쪽 사이드바에서 키워드를 입력하고 검색하세요.")

with col2:
    st.subheader("🛒 선택된 기사 목록")
    if not st.session_state.cart.empty:
        # 화면 출력용 (링크 컬럼 제외)
        st.dataframe(
            st.session_state.cart[["출처", "기사일자", "제목"]], 
            use_container_width=True,
            hide_index=True
        )
        
        # 엑셀 다운로드 (xlsxwriter 적용 버전)
        excel_data = to_excel(st.session_state.cart)
        st.download_button(
            label="📥 오류 없는 엑셀 다운로드",
            data=excel_data,
            file_name=f"News_Scrap_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
        if st.button("전체 초기화"):
            st.session_state.cart = pd.DataFrame()
            st.session_state.news_results = []
            st.rerun()
    else:
        st.info("선택된 기사가 없습니다.")
