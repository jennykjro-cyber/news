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

# [오류 수정 핵심] 엑셀 변환 함수
def to_excel(df: pd.DataFrame):
    output = BytesIO()
    df_safe = df.copy()
    
    # 엑셀 수식 오류의 주범인 큰따옴표(")를 제거하거나 치환
    df_safe["제목_클린"] = df_safe["제목"].str.replace('"', "'")
    
    # 하이퍼링크 수식 적용
    df_safe["기사제목(링크)"] = df_safe.apply(
        lambda x: f'=HYPERLINK("{x["링크"]}", "{x["제목_클린"]}")', axis=1
    )
    
    # 최종 파일에 포함할 컬럼만 선택
    export_df = df_safe[["검색키워드", "출처", "기사일자", "기사제목(링크)"]]

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="뉴스스크랩")
        # 컬럼 너비 조절 (선택사항)
        worksheet = writer.sheets['뉴스스크랩']
        worksheet.column_dimensions['D'].width = 80 
        
    return output.getvalue()

# =================================================
# 3. UI 화면 구성
# =================================================
st.set_page_config(page_title="식품 뉴스 스크랩", layout="wide")
st.title("📰 식품/육가공 뉴스 스크랩 자동화")

start_date, end_date = get_date_range()
st.info(f"📅 현재 수집 설정 기간: **{start_date} ~ {end_date}** (지난주 토요일 ~ 이번주 목요일)")

# 사이드바 설정
with st.sidebar:
    st.header("🔍 검색 설정")
    keyword = st.text_input("검색어 입력 (예: 소시지 마케팅)")
    min_score = st.slider("연관도 필터 (키워드 포함 개수)", 0, 5, 1)
    
    if st.button("뉴스 수집 시작", use_container_width=True):
        if keyword:
            with st.spinner('구글 뉴스를 긁어오는 중...'):
                results = collect_news(keyword, start_date, end_date)
                st.session_state.news_results = [r for r in results if r['연관도점수'] >= min_score]
                if not st.session_state.news_results:
                    st.warning("검색 결과가 없습니다.")
        else:
            st.warning("키워드를 입력하세요.")

# 메인화면: 검색 결과
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📌 검색 결과")
    if st.session_state.news_results:
        selected_items = []
        for idx, item in enumerate(st.session_state.news_results):
            # 체크박스를 통해 기사 선택
            is_selected = st.checkbox(
                f"{item['기사일자']} | {item['출처']} | {item['제목']}", 
                key=f"item_{idx}"
            )
            if is_selected:
                selected_items.append(item)
        
        # 선택된 항목을 세션 카트에 저장
        st.session_state.cart = pd.DataFrame(selected_items)
    else:
        st.write("왼쪽에서 검색을 시작해주세요.")

with col2:
    st.subheader("🛒 선택된 기사 (엑셀 저장 목록)")
    if not st.session_state.cart.empty:
        # 화면 표시용 (수식 없는 버전)
        st.dataframe(
            st.session_state.cart[["출처", "기사일자", "제목"]], 
            use_container_width=True,
            hide_index=True
        )
        
        # 엑셀 다운로드 버튼
        excel_data = to_excel(st.session_state.cart)
        st.download_button(
            label="📥 선택 기사 엑셀 다운로드",
            data=excel_data,
            file_name=f"News_Scrap_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
        if st.button("목록 초기화"):
            st.session_state.cart = pd.DataFrame()
            st.rerun()
    else:
        st.info("선택된 기사가 없습니다.")
