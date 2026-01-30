import streamlit as st
import pandas as pd
from gnews import GNews
from datetime import datetime, timedelta
from io import BytesIO

# =================================================
# 1. 설정 및 세션 초기화
# =================================================
# [수정] 검색 키워드 세분화 및 그룹 매핑 설정
KEYWORD_MAPPING = {
    "유통": ["홈플러스", "이마트", "롯데마트", "편의점", "GS25", "CU"],
    "육가공/식품": ["육가공", "햄", "소시지", "냉동식품", "HMR", "밀키트"],
    "시장동향": ["가격인상", "원가", "물가", "식품 매출", "대체육"]
}

# 검색을 위한 전체 리스트 생성
SEARCH_KEYWORDS = [kw for sublist in KEYWORD_MAPPING.values() for kw in sublist]

if "reset_key" not in st.session_state:
    st.session_state.reset_key = 0
if "news_results" not in st.session_state:
    st.session_state.news_results = [] 
if "cart" not in st.session_state:
    st.session_state.cart = pd.DataFrame()

google_news = GNews(language="ko", country="KR", max_results=15)

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

# [추가] 세부 키워드가 어느 그룹에 속하는지 찾는 함수
def get_group_name(detail_kw):
    for group, details in KEYWORD_MAPPING.items():
        if detail_kw in details:
            return group
    return "기타"

def collect_all_news(start_date, end_date):
    all_rows = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 세분화된 모든 키워드를 순회하며 검색
    total_kws = len(SEARCH_KEYWORDS)
    for i, kw in enumerate(SEARCH_KEYWORDS):
        status_text.text(f"🔍 '{kw}' 뉴스 수집 중... ({i+1}/{total_kws})")
        articles = google_news.get_news(kw)
        
        group_name = get_group_name(kw) # 해당 키워드의 그룹명 가져오기
        
        for a in articles:
            article_date = parse_news_date(a.get("published date", ""))
            if article_date is None or not (start_date <= article_date <= end_date):
                continue
            
            all_rows.append({
                "그룹": group_name,        # 엑셀에 표기될 그룹명
                "세부키워드": kw,          # 실제 검색된 키워드
                "출처": a.get("publisher", {}).get("title", ""),
                "기사일자": article_date.strftime("%Y-%m-%d"),
                "제목": a.get("title", ""),
                "링크": a.get("url", "")
            })
        progress_bar.progress((i + 1) / total_kws)
    
    status_text.text("✅ 수집 완료!")
    df = pd.DataFrame(all_rows).drop_duplicates(subset=["링크"])
    return df.to_dict('records')

def to_excel(df: pd.DataFrame):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        # [수정] 엑셀 상단에 '그룹' 항목이 먼저 나오도록 배치
        export_df = df[["그룹", "출처", "기사일자", "제목"]]
        export_df.to_excel(writer, index=False, sheet_name="뉴스클리핑")
        
        workbook  = writer.book
        worksheet = writer.sheets["뉴스클리핑"]
        link_format = workbook.add_format({'font_color': 'blue', 'underline': 1})

        for row_num, (index, row) in enumerate(df.iterrows()):
            # 제목 컬럼(D열, 인덱스 3)에 링크 삽입
            worksheet.write_url(row_num + 1, 3, row['링크'], link_format, row['제목'])
            
        worksheet.set_column('A:C', 15)
        worksheet.set_column('D:D', 80)
    return output.getvalue()

# =================================================
# 3. UI 화면 구성
# =================================================
st.set_page_config(page_title="주간 뉴스 클리핑", layout="wide")
st.title("🚀 그룹화된 뉴스 클리핑 자동화")

start_date, end_date = get_fixed_date_range()
st.success(f"📅 수집 기준일: **{start_date} (금) ~ {end_date} (목)**")

with st.sidebar:
    st.header("⚙️ 설정 확인")
    for group, details in KEYWORD_MAPPING.items():
        st.write(f"**{group}**: {', '.join(details)}")
    
    if st.button("🌟 뉴스클리핑 시작", use_container_width=True, type="primary"):
        results = collect_all_news(start_date, end_date)
        st.session_state.news_results = results
        st.session_state.cart = pd.DataFrame()

col1, col2 = st.columns([1.2, 0.8])

with col1:
    st.subheader("📌 수집된 뉴스 리스트")
    if st.session_state.news_results:
        temp_selected = []
        for idx, item in enumerate(st.session_state.news_results):
            cb_key = f"news_{idx}_v{st.session_state.reset_key}"
            # 체크박스 라벨에 그룹명을 함께 표시해줍니다.
            if st.checkbox(f"[{item['그룹']} | {item['출처']}] {item['제목']}", key=cb_key):
                temp_selected.append(item)
        st.session_state.cart = pd.DataFrame(temp_selected)
    else:
        st.write("사이드바의 버튼을 눌러주세요.")

with col2:
    st.subheader("🛒 장바구니 (추출 목록)")
    if not st.session_state.cart.empty:
        # 화면에는 어떤 그룹으로 묶였는지 보여줌
        st.dataframe(st.session_state.cart[["그룹", "출처", "제목"]], use_container_width=True, hide_index=True)
        
        excel_data = to_excel(st.session_state.cart)
        st.download_button(
            label="📥 그룹별 엑셀 다운로드",
            data=excel_data,
            file_name=f"뉴스클리핑_{end_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
        if st.button("🔄 선택 전체 해제", use_container_width=True):
            st.session_state.reset_key += 1
            st.session_state.cart = pd.DataFrame()
            st.rerun()
    else:
        st.info("선택된 기사가 없습니다.")
