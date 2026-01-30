import streamlit as st
import pandas as pd
from gnews import GNews
from datetime import datetime, timedelta
from io import BytesIO

# =================================================
# 1. 설정 및 세션 초기화
# =================================================
# 자동으로 검색할 키워드 목록
BUSINESS_KEYWORDS = [
    "육가공", "햄", "소시지", "식품", "원가", "가격인상",
    "식품 마케팅", "유통", "편의점 신제품", "대체육", "HMR"
]

if "news_results" not in st.session_state:
    st.session_state.news_results = [] 
if "cart" not in st.session_state:
    st.session_state.cart = pd.DataFrame()

google_news = GNews(language="ko", country="KR", max_results=20) # 키워드당 결과수 조절

# =================================================
# 2. 기능 함수
# =================================================
def get_fixed_date_range():
    """
    지난주 금요일 ~ 이번주 목요일 자동 계산
    """
    today = datetime.today()
    # 이번주 목요일 계산 (목요일은 weekday 3)
    this_thursday = today - timedelta(days=(today.weekday() - 3) % 7)
    # 지난주 금요일은 이번주 목요일로부터 6일 전
    last_friday = this_thursday - timedelta(days=6)
    
    return last_friday.date(), this_thursday.date()

def parse_news_date(date_str):
    try:
        return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z").date()
    except:
        return None

def relevance_score(text: str) -> int:
    # 수집된 기사 내용 안에 우리 핵심 키워드가 몇 개나 겹치는지 점수화
    return sum(1 for kw in BUSINESS_KEYWORDS if kw.replace(" ", "") in text.replace(" ", ""))

def collect_all_news(start_date, end_date):
    all_rows = []
    # 프로그레스 바 생성
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, kw in enumerate(BUSINESS_KEYWORDS):
        status_text.text(f"🔍 '{kw}' 관련 뉴스 수집 중... ({i+1}/{len(BUSINESS_KEYWORDS)})")
        articles = google_news.get_news(kw)
        
        for a in articles:
            article_date = parse_news_date(a.get("published date", ""))
            if article_date is None or not (start_date <= article_date <= end_date):
                continue
            
            title = a.get("title", "")
            desc = a.get("description", "")
            score = relevance_score(f"{title} {desc}")
            
            all_rows.append({
                "검색키워드": kw,
                "출처": a.get("publisher", {}).get("title", ""),
                "기사일자": article_date.strftime("%Y-%m-%d"),
                "제목": title,
                "링크": a.get("url", ""),
                "연관도점수": score
            })
        progress_bar.progress((i + 1) / len(BUSINESS_KEYWORDS))
    
    status_text.text("✅ 수집 완료!")
    # 중복 기사 제거 (여러 키워드에 걸릴 수 있음)
    df = pd.DataFrame(all_rows).drop_duplicates(subset=["링크"])
    return df.to_dict('records')

def to_excel(df: pd.DataFrame):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        # 엑셀 추출용 컬럼 정리
        export_df = df[["검색키워드", "출처", "기사일자", "제목"]]
        export_df.to_excel(writer, index=False, sheet_name="뉴스클리핑")
        
        workbook  = writer.book
        worksheet = writer.sheets["뉴스클리핑"]
        link_format = workbook.add_format({'font_color': 'blue', 'underline': 1})

        for row_num, (index, row) in enumerate(df.iterrows()):
            worksheet.write_url(row_num + 1, 3, row['링크'], link_format, row['제목'])
            
        worksheet.set_column('A:C', 15)
        worksheet.set_column('D:D', 80)
    return output.getvalue()

# =================================================
# 3. UI 화면 구성
# =================================================
st.set_page_config(page_title="주간 뉴스 클리핑", layout="wide")
st.title("🚀 주간 식품/유통 뉴스 클리핑 자동화")

start_date, end_date = get_fixed_date_range()
st.success(f"📅 수집 기준일: **{start_date} (금) ~ {end_date} (목)**")

with st.sidebar:
    st.header("⚙️ 필터 설정")
    min_score = st.slider("업무 연관도 필터 (점수 이상만 표시)", 0, 5, 1)
    st.info(f"등록된 키워드: {', '.join(BUSINESS_KEYWORDS)}")
    
    if st.button("🌟 뉴스클리핑 시작", use_container_width=True, type="primary"):
        results = collect_all_news(start_date, end_date)
        st.session_state.news_results = [r for r in results if r['연관도점수'] >= min_score]

# 메인화면 레이아웃 (이 부분을 통째로 교체해 보세요)
col1, col2 = st.columns([1.2, 0.8])

with col1:
    st.subheader("📌 수집된 뉴스 리스트")
    if st.session_state.news_results:
        selected_items = []
        for idx, item in enumerate(st.session_state.news_results):
            # 체크박스 상태를 세션에서 관리
            cb_key = f"news_{idx}"
            is_selected = st.checkbox(
                f"[{item['출처']}] {item['제목']} ({item['기사일자']})", 
                key=cb_key,
                value=st.session_state.get(cb_key, False)
            )
            if is_selected:
                selected_items.append(item)
        
        st.session_state.cart = pd.DataFrame(selected_items)
    else:
        st.write("사이드바의 버튼을 눌러 뉴스를 불러오세요.")

with col2:
    st.subheader("🛒 장바구니 (추출 목록)")
    if not st.session_state.cart.empty:
        st.dataframe(
            st.session_state.cart[["출처", "제목"]], 
            use_container_width=True, hide_index=True
        )
        
        excel_data = to_excel(st.session_state.cart)
        st.download_button(
            label="📥 엑셀 파일 다운로드",
            data=excel_data,
            file_name=f"뉴스클리핑_{end_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
        # 추가된 전체 해제 버튼
        if st.button("🔄 선택 전체 해제", use_container_width=True):
            for idx in range(len(st.session_state.news_results)):
                st.session_state[f"news_{idx}"] = False
            st.session_state.cart = pd.DataFrame()
            st.rerun()

        if st.button("🗑️ 장바구니 비우기", use_container_width=True):
            st.session_state.cart = pd.DataFrame()
            st.rerun()
    else:
        st.info("선택된 기사가 없습니다.")
