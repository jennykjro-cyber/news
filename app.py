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

# 세션 상태 초기 설정 (오류 방지)
if "keyword_mapping" not in st.session_state:
    st.session_state.keyword_mapping = load_keywords()
if "reset_key" not in st.session_state:
    st.session_state.reset_key = 0
if "news_results" not in st.session_state:
    st.session_state.news_results = []
if "cart" not in st.session_state:
    st.session_state.cart = pd.DataFrame()

# =================================================
# 2. 핵심 기능 함수 (날짜, 수집, 점수)
# =================================================
def get_fixed_date_range():
    """지난주 금요일 ~ 이번주 목요일 범위 계산"""
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
    """제목 가중치 2점, 본문 1점 부여 로직"""
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
    google_news = GNews(language="ko", country="KR", max_results=12)
    all_rows = []
    # 검색용 전체 키워드 평탄화
    all_search_kws = [kw for sublist in mapping.values() for kw in sublist]
    
    progress_bar = st.progress(0)
    groups = list(mapping.items())
    
    for i, (group, sub_kws) in enumerate(groups):
        for kw in sub_kws:
            articles = google_news.get_news(kw)
            for a in articles:
                article_date = parse_news_date(a.get("published date", ""))
                if not article_date or not (start_date <= article_date <= end_date):
                    continue
                
                title = a.get("title", "")
                desc = a.get("description", "")
                score = get_relevance_score(title, desc, all_search_kws)
                
                # KeyError 방지를 위해 모든 필드를 명확히 생성
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
            # 엑셀 복구 오류 방지: write_url 사용
            worksheet.write_url(row_num + 1, 3, row['링크'], link_format, row['제목'])
        worksheet.set_column('A:C', 15)
        worksheet.set_column('D:D', 80)
    return output.getvalue()

# =================================================
# 3. UI 화면 구성
# =================================================
st.set_page_config(page_title="주간 뉴스 클리핑", layout="wide")

# --- 키워드 관리 섹션 ---
with st.expander("🛠️ 뉴스클리핑 키워드 관리 (클릭하여 열기)", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        new_g = st.text_input("새 대분류 추가")
        if st.button("대분류 추가"):
            if new_g and new_g not in st.session_state.keyword_mapping:
                st.session_state.keyword_mapping[new_g] = []
                save_keywords(st.session_state.keyword_mapping)
                st.rerun()
    with c2:
        keys = list(st.session_state.keyword_mapping.keys())
        if keys:
            sel_g = st.selectbox("소분류 추가할 그룹 선택", options=keys)
            new_s = st.text_input(f"'{sel_g}'에 추가할 소분류 키워드")
            if st.button("소분류 추가"):
                if new_s and new_s not in st.session_state.keyword_mapping[sel_g]:
                    st.session_state.keyword_mapping[sel_g].append(new_s)
                    save_keywords(st.session_state.keyword_mapping)
                    st.rerun()
    
    st.write("---")
    for g, subs in list(st.session_state.keyword_mapping.items()):
        col_g, col_s = st.columns([1, 4])
        with col_g:
            if st.button(f"🗑️ {g} 삭제", key=f"del_{g}"):
                del st.session_state.keyword_mapping[g]
                save_keywords(st.session_state.keyword_mapping)
                st.rerun()
        with col_s:
            st.write(f"**{g}**: {', '.join(subs)}")

# --- 메인 본문 ---
st.title("🚀 주간 뉴스 클리핑 시스템")
start_d, end_d = get_fixed_date_range()
st.success(f"📅 대상 기간: {start_d} (금) ~ {end_d} (목)")

with st.sidebar:
    st.header("⚙️ 검색 필터")
    min_score = st.slider("업무 연관도 필터 (최소 점수)", 0, 10, 3)
    if st.button("🌟 뉴스 수집 시작", type="primary", use_container_width=True):
        st.session_state.news_results = collect_news_enhanced(st.session_state.keyword_mapping, start_d, end_d)
        st.session_state.cart = pd.DataFrame()
        st.rerun()

col_list, col_cart = st.columns([1.2, 0.8])

with col_list:
    st.subheader("📌 뉴스 리스트")
    res = [r for r in st.session_state.news_results if r.get('연관도점수', 0) >= min_score]
    if res:
        st.write(f"검색 결과: {len(res)}건")
        temp_selected = []
        for idx, item in enumerate(res):
            cb_key = f"news_{idx}_v{st.session_state.reset_key}"
            # KeyError 방지: item.get('그룹') 사용
            label = f"[{item.get('그룹', '기타')} | 점수:{item['연관도점수']}] {item['제목']}"
            if st.checkbox(label, key=cb_key):
                temp_selected.append(item)
        st.session_state.cart = pd.DataFrame(temp_selected)
    elif st.session_state.news_results:
        st.warning(f"{min_score}점 이상인 기사가 없습니다.")
    else:
        st.info("사이드바 버튼을 눌러 수집을 시작하세요.")

with col_cart:
    st.subheader("🛒 추출 바구니")
    if not st.session_state.cart.empty:
        st.dataframe(st.session_state.cart[["그룹", "출처", "제목"]], use_container_width=True, hide_index=True)
        excel_data = to_excel(st.session_state.cart)
        st.download_button(
            label="📥 엑셀 다운로드",
            data=excel_data,
            file_name=f"News_Scrap_{end_d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        if st.button("🔄 선택 전체 해제", use_container_width=True):
            st.session_state.reset_key += 1
            st.session_state.cart = pd.DataFrame()
            st.rerun()
    else:
        st.write("선택된 기사가 없습니다.")
