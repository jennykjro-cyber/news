import streamlit as st
import pandas as pd
from gnews import GNews
from datetime import datetime, timedelta
from io import BytesIO
import json
import os

# =================================================
# 1. 시스템 초기 설정 및 데이터 로드
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

# 세션 상태 초기화 (오류 방지 핵심)
if "keyword_mapping" not in st.session_state:
    st.session_state.keyword_mapping = load_keywords()
if "news_results" not in st.session_state:
    st.session_state.news_results = []
if "cart_list" not in st.session_state: # DataFrame 대신 리스트로 관리하여 TypeError 방지
    st.session_state.cart_list = []
if "reset_key" not in st.session_state:
    st.session_state.reset_key = 0

# =================================================
# 2. 핵심 로직 함수
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
    text = f"{title} {desc}".replace(" ", "").lower()
    title_only = title.replace(" ", "").lower()
    for kw in all_keywords:
        target = kw.replace(" ", "").lower()
        if target in title_only: score += 2
        elif target in text: score += 1
    return score

def collect_news_final(mapping, start_date, end_date):
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
                title = a.get("title", "제목 없음")
                if any(ex in title for ex in exclude_keywords): continue
                
                article_date = parse_news_date(a.get("published date", ""))
                if not article_date or not (start_date <= article_date <= end_date): continue
                
                desc = a.get("description", "")
                score = get_relevance_score(title, desc, all_search_kws)
                all_rows.append({
                    "그룹": group,
                    "출처": a.get("publisher", {}).get("title", "출처 미상"),
                    "기사일자": article_date.strftime("%Y-%m-%d"),
                    "제목": title,
                    "링크": a.get("url", ""),
                    "연관도점수": score
                })
        progress_bar.progress((i + 1) / len(groups))
    
    # 중복 제거
    unique_rows = {r['링크']: r for r in all_rows}.values()
    return list(unique_rows)

def to_excel(data_list):
    df = pd.DataFrame(data_list)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df[["그룹", "출처", "기사일자", "제목"]].to_excel(writer, index=False, sheet_name="뉴스클리핑")
        workbook = writer.book
        worksheet = writer.sheets["뉴스클리핑"]
        link_format = workbook.add_format({'font_color': 'blue', 'underline': 1})
        for row_num, link in enumerate(df['링크']):
            worksheet.write_url(row_num + 1, 3, link, link_format, df.iloc[row_num]['제목'])
        worksheet.set_column('A:C', 15)
        worksheet.set_column('D:D', 80)
    return output.getvalue()

# =================================================
# 3. 화면 UI 구성 (레이아웃 최적화)
# =================================================
st.set_page_config(page_title="진주햄 뉴스 클리핑", layout="wide")

# 타이틀 및 기간 설정 영역 (왼쪽 정렬 중심)
st.title("🗞️ 주간 뉴스 클리핑 시스템")
start_d, end_d = get_fixed_date_range()
st.markdown(f"🗓️ **수집 대상 기간:** `{start_d}` ~ `{end_d}`")

# 설정 및 실행 영역
st.divider()
col_setup1, col_setup2 = st.columns([1.5, 3])

with col_setup1:
    st.subheader("🔍 수집 및 필터")
    min_score = st.number_input("업무 연관도 최소 점수 (0~10)", min_value=0, max_value=10, value=3)
    if st.button("🌟 뉴스 수집 시작", type="primary", use_container_width=True):
        with st.spinner('뉴스를 수집하고 있습니다...'):
            st.session_state.news_results = collect_news_final(st.session_state.keyword_mapping, start_d, end_d)
            st.session_state.cart_list = []
            st.rerun()

with col_setup2:
    # 키워드 관리 (항상 접혀있음)
    with st.expander("🛠️ 뉴스클리핑 키워드 관리 (클릭하여 열기)", expanded=False):
        mg_c1, mg_c2 = st.columns(2)
        with mg_c1:
            new_g = st.text_input("새 대분류 추가")
            if st.button("대분류 추가"):
                if new_g and new_g not in st.session_state.keyword_mapping:
                    st.session_state.keyword_mapping[new_g] = []
                    save_keywords(st.session_state.keyword_mapping)
                    st.rerun()
        with mg_c2:
            keys = list(st.session_state.keyword_mapping.keys())
            if keys:
                sel_g = st.selectbox("대분류 선택", options=keys)
                new_s = st.text_input(f"'{sel_g}'에 소분류 키워드 추가")
                if st.button("소분류 추가"):
                    if new_s and new_s not in st.session_state.keyword_mapping[sel_g]:
                        st.session_state.keyword_mapping[sel_g].append(new_s)
                        save_keywords(st.session_state.keyword_mapping)
                        st.rerun()
        st.write("---")
        for g, subs in list(st.session_state.keyword_mapping.items()):
            cg, cs = st.columns([1, 4])
            if cg.button(f"🗑️ {g}", key=f"del_{g}"):
                del st.session_state.keyword_mapping[g]
                save_keywords(st.session_state.keyword_mapping)
                st.rerun()
            cs.write(f"**{g}**: {', '.join(subs)}")

st.divider()

# 결과 출력 영역
col_list, col_cart = st.columns([1.2, 0.8])

with col_list:
    st.subheader("📌 수집된 뉴스 리스트")
    filtered_res = [r for r in st.session_state.news_results if r.get('연관도점수', 0) >= min_score]
    
    if filtered_res:
        st.caption(f"총 {len(filtered_res)}건의 기사가 검색되었습니다.")
        for idx, item in enumerate(filtered_res):
            cb_key = f"news_{idx}_v{st.session_state.reset_key}"
            # 체크박스 선택 시 리스트에 추가
            if st.checkbox(f"[{item.get('그룹')}] {item['제목']} (점수:{item['연관도점수']})", key=cb_key):
                if item not in st.session_state.cart_list:
                    st.session_state.cart_list.append(item)
    elif st.session_state.news_results:
        st.warning(f"점수 {min_score}점 이상인 기사가 없습니다.")
    else:
        st.info("왼쪽 '뉴스 수집 시작' 버튼을 눌러주세요.")

with col_cart:
    st.subheader("🛒 추출 바구니")
    if st.session_state.cart_list:
        cart_df = pd.DataFrame(st.session_state.cart_list)
        st.dataframe(cart_df[["그룹", "출처", "제목"]], use_container_width=True, hide_index=True)
        
        file_name = f"진주햄 뉴스클리핑 ({end_d.strftime('%Y%m%d')}).xlsx"
        st.download_button(
            label="📥 엑셀 다운로드",
            data=to_excel(st.session_state.cart_list),
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
        if st.button("🔄 선택 전체 해제", use_container_width=True):
            st.session_state.reset_key += 1
            st.session_state.cart_list = []
            st.rerun()
    else:
        st.write("선택된 기사가 없습니다.")
