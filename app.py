import streamlit as st
import pandas as pd
from gnews import GNews
from datetime import datetime, timedelta
from io import BytesIO

# =================================================
# 설정 및 초기화
# =================================================
BUSINESS_KEYWORDS = [
    "육가공", "햄", "소시지", "식품", "원가", "가격", "가격인상",
    "마케팅", "브랜드", "유통", "편의점", "대체육", "시장", "매출"
]

# 세션 상태 초기화
if "news_results" not in st.session_state:
    st.session_state.news_results = [] # 검색 결과 저장
if "cart" not in st.session_state:
    st.session_state.cart = pd.DataFrame() # 최종 바구니

google_news = GNews(language="ko", country="KR", max_results=50)

# =================================================
# 함수부 (기존 로직 유지)
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
    score = sum(1 for kw in BUSINESS_KEYWORDS if kw in text)
    return score

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

def to_excel(df: pd.DataFrame):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# =================================================
# Streamlit UI
# =================================================
st.title("📰 식품/육가공 뉴스 스크랩")

start_date, end_date = get_date_range()
st.info(f"📅 수집 기간: {start_date} ~ {end_date}")

with st.sidebar:
    st.header("🔍 검색 설정")
    keyword = st.text_input("검색어 입력")
    min_score = st.slider("연관도 필터", 0, 5, 1)
    
    if st.button("뉴스 수집 시작"):
        if keyword:
            with st.spinner('뉴스를 불러오는 중...'):
                results = collect_news(keyword, start_date, end_date)
                # 필터링 적용하여 세션에 저장
                st.session_state.news_results = [r for r in results if r['연관도점수'] >= min_score]
        else:
            st.warning("키워드를 입력하세요.")

# --- 메인 영역: 수집 결과 출력 ---
if st.session_state.news_results:
    st.subheader(f"📌 검색 결과 ({len(st.session_state.news_results)}건)")
    st.write("메일로 보낼 기사를 선택하세요.")
    
    selected_indices = []
    for idx, item in enumerate(st.session_state.news_results):
        # 핵심: 체크박스의 상태를 기반으로 리스트를 만듦
        is_selected = st.checkbox(
            f"[{item['출처']}] {item['제목']}", 
            key=f"item_{idx}"
        )
        if is_selected:
            selected_indices.append(item)

    # 선택된 데이터프레임 업데이트
    if selected_indices:
        st.session_state.cart = pd.DataFrame(selected_indices)
    else:
        st.session_state.cart = pd.DataFrame()

# --- 하단 영역: 장바구니 및 엑셀 출력 ---
st.divider()
st.subheader("🛒 최종 선택 리스트")

if not st.session_state.cart.empty:
    # 엑셀용 하이퍼링크 포맷 적용
    final_df = st.session_state.cart.copy()
    final_df["제목"] = final_df.apply(
        lambda x: f'=HYPERLINK("{x["링크"]}", "{x["제목"]}")', axis=1
    )
    
    # 출력용 컬럼 정리
    export_df = final_df[["검색키워드", "출처", "기사일자", "제목"]]
    
    st.dataframe(export_df, use_container_width=True)
    
    excel_data = to_excel(export_df)
    st.download_button(
        label="📥 엑셀로 내보내기 (메일 발송용)",
        data=excel_data,
        file_name=f"news_scrap_{datetime.now().strftime('%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.write("선택된 기사가 없습니다.")
