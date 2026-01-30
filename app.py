import streamlit as st
import pandas as pd
from gnews import GNews
from datetime import datetime, timedelta
from io import BytesIO
import json
import os

# =================================================
# 1. 키워드 DB 관리 및 초기화
# =================================================
DB_FILE = "keywords_db.json"

def load_keywords():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {
        "유통": ["홈플러스", "이마트", "롯데마트"],
        "편의점": ["GS25", "CU"],
        "육가공": ["육가공", "햄", "소시지", "비엔나"],
        "HMR": ["HMR", "밀키트"],
        "대체육": ["대체육", "식물성"],
        "시장동향": ["가격인상", "원가", "물가", "식품 매출"]
    }

def save_keywords(mapping):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=4)

if "keyword_mapping" not in st.session_state:
    st.session_state.keyword_mapping = load_keywords()
if "reset_key" not in st.session_state:
    st.session_state.reset_key = 0
if "news_results" not in st.session_state:
    st.session_state.news_results = []
if "cart" not in st.session_state:
    st.session_state.cart = pd.DataFrame()

# =================================================
# 2. 핵심 기능 함수
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

def get_relevance_score(title, desc, all_keywords):
    score = 0
    full_text = f"{title} {desc}".replace(" ", "").lower()
    title_text = title.replace(" ", "").lower()
    for kw in all_keywords:
        target = kw.replace(" ", "").lower()
        if target in title_text:
            score += 2
        elif target in full_text:
            score += 1
    return score

def collect_news_enhanced(mapping, start_date, end_date):
    google_news = GNews(language="ko", country="KR", max_results=15)
    all_rows = []
    all_search_kws = [kw for sublist in mapping.values() for kw in sublist]
    exclude_keywords = ["출시", "런칭", "신제품", "이벤트", "증정", "할인행사", "포토존", "팝업스토어"]
    
    progress_bar = st.progress(0)
    groups = list(mapping.items())
    
    for i, (group, sub_kws) in enumerate(groups):
        for kw in sub_kws:
            articles = google_news.get_news(kw)
            for a in articles:
                title = a.get("title", "")
                if any(ex in title for ex in exclude_keywords):
                    continue
                article_date = parse_news_date(a.get("published date", ""))
                if not article_date or not (start_date <= article_date <= end_date):
                    continue
                desc = a.get("description", "")
                score = get_relevance_score(title, desc, all_search_kws)
                all_rows.append({
                    "그룹": group,
                    "출처": a.get("publisher", {}).get("title", ""),
                    "기사일자": article_date.strftime("%Y-%m-%d"),
                    "제목": title,
                    "링크": a.get("url", ""),
                    "연관도점수": score
                })
        progress_bar.progress((i + 1) / len(groups))
    
    df = pd.DataFrame(all_rows)
    if not df.empty:
        df = df.drop_duplicates(subset=["링크"])
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
            worksheet.write_url(row_num + 1, 3, row['링크'], link_format, row['제목'])
        worksheet.set_column('A:C', 15)
        worksheet.set_column('D:D', 80)
    return output.getvalue()

# =================================================
# 3. UI 화면 구성
# =================================================
st.set_page_config(page_title="진주햄 뉴스 클리핑", layout="wide")

# 상단 타이틀 및 날짜 레이아웃
head_col1, head_col2 = st.columns([2, 1])
with head_col1:
    st.title("🗞️ 주간 뉴스 클리핑 시스템")
with head_col2:
    start_d, end_d = get_fixed_date_range()
    st.write("") # 간격 조절
    st.write(f"📅 **수집 기간:** {start_d} ~ {end_d}")

st.divider()

# --- 1. 수집 설정 및 실행 (타이틀 하단 배치) ---
st.subheader("🔍 수집 설정 및 실행")
col_f1, col_f2 = st.columns([3, 1])
with col_f1:
    min_score = st.slider("업무 연관도 필터 (최소 점수)", 0, 10, 3, help="점수가 높을수록 키워드가 많이 포함된 기사입니다.")
with col_f2:
    st.write("") # 간격 조절
    if st.button("🌟 뉴스 수집 시작", type="primary", use_container_width=True):
        with st.spinner('뉴스를 수집 중입니다...'):
            st.session_state.news_results = collect_news_enhanced(st.session_state.keyword_mapping, start_d, end_d)
            st.session_state.cart = pd.DataFrame()
            st.rerun()

# --- 2. 키워드 관리 (항상 접혀있는 상태) ---
with st.expander("🛠️ 뉴스클리핑 키워드 관리", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        new_g = st.text_input("새 대분류 추가", placeholder="예: 경쟁사")
        if st.button("대분류 추가", use_container_width=True):
            if new_g and new_g not in st.session_state.keyword_mapping:
                st.session_state.keyword_mapping[new_g] = []
                save_keywords(st.session_state.keyword_mapping)
                st.rerun()
    with c2:
        keys = list(st.session_state.keyword_mapping.keys())
        if keys:
            sel_g = st.selectbox("소분류 추가할 그룹 선택", options=keys)
            new_s = st.text_input(f"'{sel_g}'에 추가할 소분류 키워드", placeholder="예: 사조대림")
            if st.button("소분류 추가", use_container_width=True):
                if new_s and new_s not in st.session_state.keyword_mapping[sel_g]:
                    st.session_state.keyword_mapping[sel_g].append(new_s)
                    save_keywords(st.session_state.keyword_mapping)
                    st.rerun()
    st.divider()
    for g, subs in list(st.session_state.keyword_mapping.items()):
        col_g, col_s = st.columns([1, 4])
        with col_g:
            if st.button(f"🗑️ {g} 삭제", key=f"del_{g}"):
                del st.session_state.keyword_mapping[g]
                save_keywords(st.session_state.keyword_mapping)
                st.rerun()
        with col_s:
            st.write(f"**{g}**: {', '.join(subs)}")

st.divider()

# --- 3. 결과 출력 영역 ---
col_list, col_cart = st.columns([1.2, 0.8])

with col_list:
    st.subheader("📌 수집된 뉴스 리스트")
    res = [r for r in st.session_state.news_results if r.get('연관도점수', 0) >= min_score]
    if res:
        st.write(f"검색 결과: **{len(res)}**건 (홍보성 기사 자동 제외)")
        for idx, item in enumerate(res):
            cb_key = f"news_{idx}_v{st.session_state.reset_key}"
            label = f"[{item.get('그룹', '기타')} | 점수:{item['연관도점수']}] {item['제목']}"
            if st.checkbox(label, key=cb_key):
                if item['링크'] not in st.session_state.cart.get('링크', pd.Series()).values:
                    st.session_state.cart = pd.concat([st.session_state.cart, pd.DataFrame([item])]).ignore_index=True
    elif st.session_state.news_results:
        st.warning(f"{min_score}점 이상인 기사가 없습니다. 필터를 낮춰보세요.")
    else:
        st.info("수집 시작 버튼을 눌러주세요.")

with col_cart:
    st.subheader("🛒 추출 바구니")
    if not st.session_state.cart.empty:
        st.dataframe(st.session_state.cart[["그룹", "출처", "제목"]], use_container_width=True, hide_index=True)
        file_date = end_d.strftime("%Y%m%d")
        excel_data = to_excel(st.session_state.cart)
        st.download_button(
            label="📥 진주햄 뉴스클리핑 엑셀 다운로드",
            data=excel_data,
            file_name=f"진주햄 뉴스클리핑 ({file_date}).xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        if st.button("🔄 선택 전체 해제", use_container_width=True):
            st.session_state.reset_key += 1
            st.session_state.cart = pd.DataFrame()
            st.rerun()
    else:
        st.write("선택된 기사가 없습니다.")
