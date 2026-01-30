import streamlit as st
import pandas as pd
from gnews import GNews
from datetime import datetime, timedelta
from io import BytesIO

# =================================================
# 1. 설정 및 세션 초기화
# =================================================
# 그룹별 세분화 키워드 설정
KEYWORD_MAPPING = {
    "유통": ["홈플러스", "이마트", "롯데마트", "편의점", "GS25", "CU"],
    "육가공/식품": ["육가공", "햄", "소시지", "냉동식품", "HMR", "밀키트"],
    "시장동향": ["가격인상", "원가", "물가", "식품 매출", "대체육"]
}

# 검색용 평탄화 리스트
SEARCH_KEYWORDS = [kw for sublist in KEYWORD_MAPPING.values() for kw in sublist]

# 세션 상태 초기화 (KeyError 및 위젯 충돌 방지)
if "reset_key" not in st.session_state:
    st.session_state.reset_key = 0
if "news_results" not in st.session_state:
    st.session_state.news_results = [] 
if "cart" not in st.session_state:
    st.session_state.cart = pd.DataFrame()

google_news = GNews(language="ko", country="KR", max_results=10)

# =================================================
# 2. 기능 함수
# =================================================
def get_fixed_date_range():
    today = datetime.today()
    this_thursday = today - timedelta(days=(today.weekday() - 3) % 7)
    last_friday = this_thursday - timedelta(days=6)
    return last_friday.date(), this_thursday.date()

def parse_news_date(date_str):
    try:
        return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z").date()
    except:
        return None

def get_group_name(detail_kw):
    for group, details in KEYWORD_MAPPING.items():
        if detail_kw in details:
            return group
    return "기타"

def collect_all_news(start_date, end_date):
    all_rows = []
    progress_bar = st.progress(0)
    
    for i, kw in enumerate(SEARCH_KEYWORDS):
        articles = google_news.get_news(kw)
        group_name = get_group_name(kw)
        
        for a in articles:
            article_date = parse_news_date(a.get("published date", ""))
            if article_date is None or not (start_date <= article_date <= end_date):
                continue
            
            # [해결] KeyError 방지: 모든 데이터 생성 시 '그룹' 키를 명확히 포함
            all_rows.append({
                "그룹": group_name,
                "세부키워드": kw,
                "출처": a.get("publisher", {}).get("title", ""),
                "기사일자": article_date.strftime("%Y-%m-%d"),
                "제목": a.get("title", ""),
                "링크": a.get("url", "")
            })
        progress_bar.progress((i + 1) / len(SEARCH_KEYWORDS))
    
    df = pd.DataFrame(all_rows).drop_duplicates(subset=["링크"])
    return df.to_dict('records')

def to_excel(df: pd.DataFrame):
    output = BytesIO()
    # [해결] 엑셀 복구 오류 방지: xlsxwriter 엔진 사용
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        export_df = df[["그룹", "출처", "기사일자", "제목"]]
        export_df.to_excel(writer, index=False, sheet_name="뉴스클리핑")
        
        workbook  = writer.book
        worksheet = writer.sheets["뉴스클리핑"]
        link_format = workbook.add_format({'font_color': 'blue', 'underline': 1})

        for row_num, (index, row) in enumerate(df.iterrows()):
            # 수식이 아닌 URL 데이터로 직접 기록하여 손상 방지
            worksheet.write_url(row_num + 1, 3, row['링크'], link_format, row['제목'])
            
        worksheet.set_column('A:C', 15)
        worksheet.set_column('D:D', 80)
    return output.getvalue()

# =================================================
# 3. UI 화면 구성
# =================================================
st.set_page_config(page_title="주간 뉴스 클리핑", layout="wide")
st.title("🚀 뉴스 클리핑 자동화 (오류 수정판)")

start_date, end_date = get_fixed_date_range()
st.info(f"📅 수집 기간: {start_date} ~ {end_date}")

with st.sidebar:
    if st.button("🌟 뉴스클리핑 시작", use_container_width=True, type="primary"):
        # 수집 시점에 데이터 구조를 완전히 생성
        st.session_state.news_results = collect_all_news(start_date, end_date)
        st.session_state.cart = pd.DataFrame()
        st.rerun()

col1, col2 = st.columns([1.2, 0.8])

with col1:
    st.subheader("📌 수집된 뉴스 리스트")
    if st.session_state.news_results:
        temp_selected = []
        for idx, item in enumerate(st.session_state.news_results):
            # [해결] StreamlitAPIException 방지: reset_key를 포함한 고유 key 사용
            cb_key = f"news_{idx}_v{st.session_state.reset_key}"
            # [해결] KeyError 방지: item
