import streamlit as st
import pandas as pd
from gnews import GNews
from datetime import datetime, timedelta
from io import BytesIO
import json
import os

# =================================================
# 1. 키워드 DB 관리 (JSON 기반)
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
# 2. 고도화된 연관도 계산 및 수집 로직
# =================================================
def get_relevance_score(title, desc, all_keywords):
    """
    제목에 키워드가 있으면 2점, 본문에 있으면 1점을 부여하여 
    점수가 더 잘 나오도록 가중치를 둡니다.
    """
    score = 0
    full_text = f"{title} {desc}".replace(" ", "").lower()
    title_text = title.replace(" ", "").lower()
    
    for kw in all_keywords:
        target = kw.replace(" ", "").lower()
        if target in title_text:
            score += 2  # 제목 매칭 가중치
        elif target in full_text:
            score += 1
    return score

def collect_news_enhanced(mapping, start_date, end_date):
    google_news = GNews(language="ko", country="KR", max_results=15)
    all_rows = []
    
    # 전체 키워드 리스트 (점수 계산용)
    all_search_kws = [kw for sublist in mapping.values() for kw in sublist]
    
    # 진행 상황 표시
    progress_bar = st.progress(0)
    total_groups = len(mapping)
    
    for i, (group, sub_kws) in enumerate(mapping.items()):
        for kw in sub_kws:
            articles = google_news.get_news(kw)
            for a in articles:
                pub_date = a.get("published date", "")
                article_date = None
                try:
                    article_date = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z").date()
                except: continue
                
                if not (start_date <= article_date <= end_date):
                    continue
                
                title = a.get("title", "")
                desc = a.get("description", "")
                
                # 점수 계산 실행
                score = get_relevance_score(title, desc, all_search_kws)
                
                all_rows.append({
                    "그룹": group,
                    "출처": a.get("publisher", {}).get("title", ""),
                    "기사일자": article_date.strftime("%Y-%m-%d"),
                    "제목": title,
                    "링크": a.get("url", ""),
                    "연관도점수": score
                })
        progress_bar.progress((i + 1) / total_groups)
    
    df = pd.DataFrame(all_rows).drop_duplicates(subset=["링크"])
    return df.to_dict('records')

# =================================================
# 3. 화면 UI
# =================================================
st.set_page_config(page_title="주간 뉴스 클리핑", layout="wide")

# --- 키워드 관리 섹션 ---
with st.expander("🛠️ 뉴스클리핑 키워드 관리 (클릭하여 열기)", expanded=False):
    st.info("여기서 수정한 키워드는 파일에 저장되어 계속 유지됩니다.")
    
    c1, c2 = st.columns(2)
    with c1:
        new_g = st.text_input("새 대분류")
        if st.button("대분류 추가"):
            if new_g and new_g not in st.session_state.keyword_mapping:
                st.session_state.keyword_mapping[new_g] = []
                save_keywords(st.session_state.keyword_mapping)
                st.rerun()
    with c2:
        sel_g = st.selectbox("소분류 추가할 곳", options=list(st.session_state.keyword_mapping.keys()))
        new_s = st.text_input("새 소분류 키워드")
        if st.button("소분류 추가"):
            if new_s and new_s not in st.session_state.keyword_mapping[sel_g]:
                st.session_state.keyword_mapping[sel_g].append(new_s)
                save_keywords(st.session_state.keyword_mapping)
                st.rerun()
    
    st.write("---")
    # 현재 키워드 삭제 및 보기
    for g, subs in list(st.session_state.keyword_mapping.items()):
        col_g, col_s = st.columns([1, 4])
        with col_g:
            if st.button(f"🗑️ {g} 삭제", key=f"del_{g}"):
                del st.session_state.keyword_mapping[g]
                save_keywords(st.session_state.keyword_mapping)
                st.rerun()
        with col_s:
            st.write(f"**{g}**: {', '.join(subs)}")

# --- 뉴스 수집 섹션 ---
st.title("🚀 주간 뉴스 클리핑 시스템")
start_d, end_d = get_fixed_date_range() # 기존 날짜 함수 사용
st.success(f"📅 대상 기간: {start_d} ~ {end_d}")

with st.sidebar:
    st.header("⚙️ 검색 필터")
    # 점수가 더 잘 나오도록 가중치를 줬으므로 슬라이더 범위를 유지합니다.
    min_score = st.slider("업무 연관도 필터 (점수↑ = 관련성↑)", 0, 10, 3)
    
    if st.button("🌟 뉴스 수집 시작", type="primary", use_container_width=True):
        st.session_state.news_results = collect_news_enhanced(st.session_state.keyword_mapping, start_d, end_d)
        st.session_state.cart = pd.DataFrame()
        st.rerun()

# --- 결과 출력 ---
col_list, col_cart = st.columns([1.2, 0.8])

with col_list:
    st.subheader("📌 뉴스 리스트")
    # 필터링 적용
    res = [r for r in st.session_state.news_results if r['연관도점수'] >= min_score]
    
    if res:
        for idx, item in enumerate(res):
            k = f"chk_{idx}_v{st.session_state.reset_key}"
            if st.checkbox(f"[{item['그룹']} | 점수:{item['연관도점수']}] {item['제목']}", key=k):
                # 장바구니 추가 로직 (기존과 동일)
                if item['링크'] not in st.session_state.cart.values:
                    st.session_state.cart = pd.concat([st.session_state.cart, pd.DataFrame([item])])
    elif st.session_state.news_results:
        st.warning(f"점수 {min_score}점 이상 기사가 없습니다. 필터를 낮추거나 키워드를 점검하세요.")

with col_cart:
    st.subheader("🛒 추출 바구니")
    if not st.session_state.cart.empty:
        st.dataframe(st.session_state.cart[["그룹", "제목", "연관도점수"]], hide_index=True)
        # 엑셀 다운로드 (기존 xlsxwriter 함수 사용)
        if st.button("🔄 전체 해제"):
            st.session_state.reset_key += 1
            st.session_state.cart = pd.DataFrame()
            st.rerun()
