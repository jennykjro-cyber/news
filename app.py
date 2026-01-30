import streamlit as st
import pandas as pd
from gnews import GNews
from datetime import datetime, timedelta
from io import BytesIO

# =================================================
# 1. 설정 및 세션 초기화
# =================================================
# 그룹별 세분화 키워드 설정 (원하시는 대로 수정 가능)
KEYWORD_MAPPING = {
    "유통": ["홈플러스", "이마트", "롯데마트"] 
    "편의점": ["GS25", "CU"]
    "육가공": ["육가공", "햄", "소시지", "비엔나"]
    "HMR": ["HMR","밀키트"]
    "대체육": ["대체육", "식물성"]
    "시장동향": ["가격인상", "원가", "물가", "식품 매출"]
}

# 검색용 평탄화 리스트 생성
SEARCH_KEYWORDS = [kw for sublist in KEYWORD_MAPPING.values() for kw in sublist]

# 세션 상태 초기화
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

def relevance_score(text: str):
    # 등록된 모든 세부 키워드 중 텍스트에 포함된 개수를 점수로 환산
    score = 0
    clean_text = text.replace(" ", "")
    for kw in SEARCH_KEYWORDS:
        if kw.replace(" ", "") in clean_text:
            score += 1
    return score

def collect_all_news(start_date, end_date):
    all_rows = []
    progress_bar = st.progress(0)
    
    total_kws = len(SEARCH_KEYWORDS)
    for i, kw in enumerate(SEARCH_KEYWORDS):
        articles = google_news.get_news(kw)
        group_name = get_group_name(kw)
        
        for a in articles:
            article_date = parse_news_date(a.get("published date", ""))
            if article_date is None or not (start_date <= article_date <= end_date):
                continue
            
            title = a.get("title", "")
            description = a.get("description", "")
            # 연관도 점수 계산 (제목 + 본문 요약 기준)
            score = relevance_score(f"{title} {description}")
            
            all_rows.append({
                "그룹": group_name,
                "세부키워드": kw,
                "출처": a.get("publisher", {}).get("title", ""),
                "기사일자": article_date.strftime("%Y-%m-%d"),
                "제목": title,
                "링크": a.get("url", ""),
                "연관도점수": score
            })
        progress_bar.progress((i + 1) / total_kws)
    
    df = pd.DataFrame(all_rows).drop_duplicates(subset=["링크"])
    return df.to_dict('records')

def to_excel(df: pd.DataFrame):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        export_df = df[["그룹", "출처", "기사일자", "제목"]]
        export_df.to_excel(writer, index=False, sheet_name="뉴스클리핑")
        
        workbook  = writer.book
        worksheet = writer.sheets["뉴스클리핑"]
        link_format = workbook.add_format({'font_color': 'blue', 'underline': 1})

        for row_num, (index, row) in enumerate(df.iterrows()):
            # 엑셀 복구 오류 방지를 위해 하이퍼링크 직접 삽입
            worksheet.write_url(row_num + 1, 3, row['링크'], link_format, row['제목'])
            
        worksheet.set_column('A:C', 15)
        worksheet.set_column('D:D', 80)
    return output.getvalue()

# =================================================
# 3. UI 화면 구성
# =================================================
st.set_page_config(page_title="주간 뉴스 클리핑", layout="wide")
st.title("🚀 주간 뉴스 클리핑 자동화 (그룹화 & 필터 복구)")

start_date, end_date = get_fixed_date_range()
st.success(f"📅 수집 기준일: **{start_date} (금) ~ {end_date} (목)**")

with st.sidebar:
    st.header("⚙️ 검색 및 필터 설정")
    # [복구] 업무 연관도 점수 필터
    min_score = st.slider("업무 연관도 필터 (최소 매칭 점수)", 0, 10, 1)
    st.caption("기사 내에 관련 키워드가 많이 포함될수록 점수가 높습니다.")
    
    st.divider()
    
    if st.button("🌟 뉴스클리핑 시작", use_container_width=True, type="primary"):
        with st.spinner('뉴스를 수집하고 연관도를 분석 중입니다...'):
            st.session_state.news_results = collect_all_news(start_date, end_date)
            st.session_state.cart = pd.DataFrame()
            st.rerun()

# 메인 레이아웃
col1, col2 = st.columns([1.2, 0.8])

with col1:
    st.subheader("📌 수집된 뉴스 리스트")
    # 설정한 연관도 점수 이상인 기사만 필터링하여 표시
    filtered_results = [r for r in st.session_state.news_results if r['연관도점수'] >= min_score]
    
    if filtered_results:
        st.write(f"현재 필터 조건에 맞는 기사: {len(filtered_results)}건")
        temp_selected = []
        for idx, item in enumerate(filtered_results):
            # 위젯 충돌 방지를 위한 고유 키 생성
            cb_key = f"news_{idx}_v{st.session_state.reset_key}"
            label = f"[{item['그룹']} | {item['출처']}] {item['제목']} (점수: {item['연관도점수']})"
            
            if st.checkbox(label, key=cb_key):
                temp_selected.append(item)
        st.session_state.cart = pd.DataFrame(temp_selected)
    elif st.session_state.news_results:
        st.warning(f"연관도 점수 {min_score}점 이상인 기사가 없습니다. 필터를 조절해 보세요.")
    else:
        st.write("사이드바의 버튼을 눌러 수집을 시작하세요.")

with col2:
    st.subheader("🛒 장바구니 (추출 목록)")
    if not st.session_state.cart.empty:
        st.dataframe(
            st.session_state.cart[["그룹", "출처", "제목"]], 
            use_container_width=True, 
            hide_index=True
        )
        
        excel_data = to_excel(st.session_state.cart)
        st.download_button(
            label="📥 선택 기사 엑셀 다운로드",
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
