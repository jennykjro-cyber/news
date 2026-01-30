import streamlit as st
import pandas as pd
from gnews import GNews
from datetime import datetime, timedelta
from io import BytesIO

# =================================================
# 1. 설정 및 세션 초기화
# =================================================
BUSINESS_KEYWORDS = [
    "육가공", "햄", "소시지", "식품", "원가", "가격인상",
    "식품 마케팅", "유통", "편의점 신제품", "대체육", "HMR"
]

# 위젯 초기화를 위한 버전 관리 키 추가
if "reset_key" not in st.session_state:
    st.session_state.reset_key = 0
if "news_results" not in st.session_state:
    st.session_state.news_results = [] 
if "cart" not in st.session_state:
    st.session_state.cart = pd.DataFrame()

google_news = GNews(language="ko", country="KR", max_results=20)

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

def relevance_score(text: str) -> int:
    return sum(1 for kw in BUSINESS_KEYWORDS if kw.replace(" ", "") in text.replace(" ", ""))

def collect_all_news(start_date, end_date):
    all_rows = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, kw in enumerate(BUSINESS_KEYWORDS):
        status_text.text(f"🔍 '{kw}' 뉴스 수집 중... ({i+1}/{len(BUSINESS_KEYWORDS)})")
        articles = google_news.get_news(kw)
        for a in articles:
            article_date = parse_news_date(a.get("published date", ""))
            if article_date is None or not (start_date <= article_date <= end_date):
                continue
            title = a.get("title", "")
            all_rows.append({
                "검색키워드": kw,
                "출처": a.get("publisher", {}).get("title", ""),
                "기사일자": article_date.strftime("%Y-%m-%d"),
                "제목": title,
                "링크": a.get("url", ""),
                "연관도점수": relevance_score(f"{title} {a.get('description', '')}")
            })
        progress_bar.progress((i + 1) / len(BUSINESS_KEYWORDS))
    
    status_text.text("✅ 수집 완료!")
    df = pd.DataFrame(all_rows).drop_duplicates(subset=["링크"])
    return df.to_dict('records')

def to_excel(df: pd.DataFrame):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        export_df = df[["검색키워드", "출처", "기사일자", "제목"]]
        export_df.to_excel(writer, index=False, sheet_name="뉴스클리핑")
        workbook  = writer.book
        worksheet = writer.sheets["뉴스클리핑"]
        link_format = workbook.add_format({'font_color': 'blue', 'underline': 1})

        for row_num, (index, row) in enumerate(df.iterrows()):
            # 엑셀 복구 오류 방지를 위해 write_url 직접 사용
            worksheet.write_url(row_num + 1, 3, row['링크'], link_format, row['제목'])
            
        worksheet.set_column('A:C', 15)
        worksheet.set_column('D:D', 80)
    return output.getvalue()

# =================================================
# 3. UI 화면 구성
# =================================================
st.set_page_config(page_title="주간 뉴스 클리핑", layout="wide")
st.title("🚀 주간 뉴스 클리핑 자동화")

start_date, end_date = get_fixed_date_range()
st.success(f"📅 수집 기준일: **{start_date} (금) ~ {end_date} (목)**")

with st.sidebar:
    st.header("⚙️ 필터 설정")
    min_score = st.slider("업무 연관도 필터", 0, 5, 1)
    
    if st.button("🌟 뉴스클리핑 시작", use_container_width=True, type="primary"):
        results = collect_all_news(start_date, end_date)
        st.session_state.news_results = [r for r in results if r['연관도점수'] >= min_score]
        st.session_state.cart = pd.DataFrame() # 새 검색 시 장바구니 초기화

# 메인 레이아웃
col1, col2 = st.columns([1.2, 0.8])

with col1:
    st.subheader("📌 수집된 뉴스 리스트")
    if st.session_state.news_results:
        temp_selected = []
        for idx, item in enumerate(st.session_state.news_results):
            # reset_key를 결합하여 버튼 클릭 시 체크박스를 강제로 다시 그리게 함 (에러 방지 핵심)
            cb_key = f"news_{idx}_v{st.session_state.reset_key}"
            if st.checkbox(f"[{item['출처']}] {item['제목']}", key=cb_key):
                temp_selected.append(item)
        st.session_state.cart = pd.DataFrame(temp_selected)
    else:
        st.write("사이드바의 버튼을 눌러주세요.")

with col2:
    st.subheader("🛒 장바구니 (추출 목록)")
    if not st.session_state.cart.empty:
        st.dataframe(st.session_state.cart[["출처", "제목"]], use_container_width=True, hide_index=True)
        
        excel_data = to_excel(st.session_state.cart)
        st.download_button(
            label="📥 엑셀 파일 다운로드",
            data=excel_data,
            file_name=f"뉴스클리핑_{end_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
        # 전체 해제 기능을 안전하게 구현
        if st.button("🔄 선택 전체 해제", use_container_width=True):
            st.session_state.reset_key += 1 # 키 값을 바꿔서 위젯을 완전히 새로 고침
            st.session_state.cart = pd.DataFrame()
            st.rerun()
    else:
        st.info("선택된 기사가 없습니다.")
