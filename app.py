import streamlit as st
import pandas as pd
from gnews import GNews
from datetime import datetime, timedelta
from io import BytesIO
import json
import os

# =================================================
# 1. 키워드 저장 및 로드 로직 (고정값 유지용)
# =================================================
DB_FILE = "keywords_db.json"

def load_keywords():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # 기본값
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

# 세션 상태 초기화
if "keyword_mapping" not in st.session_state:
    st.session_state.keyword_mapping = load_keywords()
if "reset_key" not in st.session_state:
    st.session_state.reset_key = 0
if "news_results" not in st.session_state:
    st.session_state.news_results = []
if "cart" not in st.session_state:
    st.session_state.cart = pd.DataFrame()

# =================================================
# 2. 기능 함수
# =================================================
google_news = GNews(language="ko", country="KR", max_results=10)

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

def relevance_score(text: str, search_list):
    score = 0
    clean_text = text.replace(" ", "")
    for kw in search_list:
        if kw.replace(" ", "") in clean_text:
            score += 1
    return score

def collect_all_news(mapping, start_date, end_date):
    all_rows = []
    # 검색용 리스트 생성
    search_keywords = [kw for sublist in mapping.values() for kw in sublist]
    progress_bar = st.progress(0)
    
    total_kws = len(search_keywords)
    idx = 0
    for group, details in mapping.items():
        for kw in details:
            articles = google_news.get_news(kw)
            for a in articles:
                article_date = parse_news_date(a.get("published date", ""))
                if article_date is None or not (start_date <= article_date <= end_date):
                    continue
                title = a.get("title", "")
                score = relevance_score(f"{title} {a.get('description', '')}", search_keywords)
                all_rows.append({
                    "그룹": group,
                    "세부키워드": kw,
                    "출처": a.get("publisher", {}).get("title", ""),
                    "기사일자": article_date.strftime("%Y-%m-%d"),
                    "제목": title,
                    "링크": a.get("url", ""),
                    "연관도점수": score
                })
            idx += 1
            progress_bar.progress(idx / total_kws)
    
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
            worksheet.write_url(row_num + 1, 3, row['リンク'], link_format, row['제목'])
        worksheet.set_column('A:C', 15)
        worksheet.set_column('D:D', 80)
    return output.getvalue()

# =================================================
# 3. UI 화면 구성
# =================================================
st.set_page_config(page_title="주간 뉴스 클리핑", layout="wide")

# --- 메인 상단: 키워드 관리 섹션 ---
with st.expander("🛠️ 뉴스클리핑 키워드 관리 (대분류/소분류)", expanded=False):
    st.write("여기서 키워드를 수정하면 파일로 저장되어 다음 접속 시에도 유지됩니다.")
    
    # 1. 키워드 추가/삭제 UI
    col_k1, col_k2 = st.columns(2)
    with col_k1:
        new_group = st.text_input("새 대분류 추가 (예: 경쟁사)")
        if st.button("대분류 추가"):
            if new_group and new_group not in st.session_state.keyword_mapping:
                st.session_state.keyword_mapping[new_group] = []
                save_keywords(st.session_state.keyword_mapping)
                st.rerun()

    with col_k2:
        target_group = st.selectbox("소분류를 추가할 대분류 선택", options=list(st.session_state.keyword_mapping.keys()))
        new_sub_kw = st.text_input(f"'{target_group}'에 추가할 소분류 키워드")
        if st.button("소분류 추가"):
            if new_sub_kw and new_sub_kw not in st.session_state.keyword_mapping[target_group]:
                st.session_state.keyword_mapping[target_group].append(new_sub_kw)
                save_keywords(st.session_state.keyword_mapping)
                st.rerun()

    st.divider()
    
    # 2. 현재 키워드 현황판 (삭제 기능 포함)
    st.write("### 📋 현재 키워드 설정")
    for group, subs in list(st.session_state.keyword_mapping.items()):
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button(f"❌ {group} 삭제", key=f"del_g_{group}"):
                del st.session_state.keyword_mapping[group]
                save_keywords(st.session_state.keyword_mapping)
                st.rerun()
        with c2:
            st.markdown(f"**{group}**: {', '.join(subs)}")
            # 개별 소분류 삭제는 로직상 복잡하므로 여기서는 그룹 단위 관리를 추천합니다.

# --- 메인 타이틀 ---
st.title("🚀 주간 뉴스 클리핑 자동화")

start_date, end_date = get_fixed_date_range()
st.success(f"📅 수집 기준일: **{start_date} (금) ~ {end_date} (목)**")

with st.sidebar:
    st.header("⚙️ 검색 필터")
    min_score = st.slider("업무 연관도 필터 (최소 점수)", 0, 10, 1)
    
    if st.button("🌟 뉴스클리핑 시작", use_container_width=True, type="primary"):
        with st.spinner('뉴스를 수집 중입니다...'):
            st.session_state.news_results = collect_all_news(st.session_state.keyword_mapping, start_date, end_date)
            st.session_state.cart = pd.DataFrame()
            st.rerun()

# --- 메인 결과 레이아웃 ---
col1, col2 = st.columns([1.2, 0.8])

with col1:
    st.subheader("📌 수집된 뉴스 리스트")
    filtered = [r for r in st.session_state.news_results if r['연관도점수'] >= min_score]
    if filtered:
        temp_selected = []
        for idx, item in enumerate(filtered):
            cb_key = f"news_{idx}_v{st.session_state.reset_key}"
            label = f"[{item['그룹']} | {item['출처']}] {item['제목']} (점수: {item['연관도점수']})"
            if st.checkbox(label, key=cb_key):
                temp_selected.append(item)
        st.session_state.cart = pd.DataFrame(temp_selected)
    elif st.session_state.news_results:
        st.warning(f"점수 {min_score}점 이상인 기사가 없습니다.")
    else:
        st.write("상단에서 키워드를 확인하고 수집을 시작하세요.")

with col2:
    st.subheader("🛒 장바구니")
    if not st.session_state.cart.empty:
        st.dataframe(st.session_state.cart[["그룹", "출처", "제목"]], use_container_width=True, hide_index=True)
        excel_data = to_excel(st.session_state.cart)
        st.download_button(
            label="📥 엑셀 다운로드",
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
