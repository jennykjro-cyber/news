import streamlit as st
import pandas as pd
from gnews import GNews
from datetime import datetime, timedelta
from io import BytesIO
import json
import os

# =================================================
# 1. 시스템 초기 설정 및 데이터 로드 (기존 유지)
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
if "news_results" not in st.session_state:
    st.session_state.news_results = []
if "cart_list" not in st.session_state:
    st.session_state.cart_list = []
if "reset_key" not in st.session_state:
    st.session_state.reset_key = 0

# =================================================
# 2. 핵심 로직 고도화 (검색 쿼리 확장)
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
    # 검색 결과 수를 늘려 더 폭넓게 수집
    google_news = GNews(language="ko", country="KR", max_results=30)
    all_rows = []
    all_search_kws = [kw for sublist in mapping.values() for kw in sublist]
    exclude_keywords = ["출시", "런칭", "신제품", "이벤트", "증정", "할인행사", "포토존", "팝업스토어", "증시", "주가"]
    
    progress_bar = st.progress(0)
    groups = list(mapping.items())
    
    for i, (group, sub_kws) in enumerate(groups):
        if not sub_kws: continue
        
        # [고도화] 단어 하나가 아니라 "그룹명 (키워드1 OR 키워드2)" 형태로 쿼리 조합
        search_query = f"{group} ({' OR '.join(sub_kws)})"
        articles = google_news.get_news(search_query)
        
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
    
    unique_rows = {r['링크']: r for r in all_rows}.values()
    return sorted(list(unique_rows), key=lambda x: x['연관도점수'], reverse=True)

def to_excel(data_list):
    df = pd.DataFrame(data_list)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df[["그룹", "출처", "기사일자", "제목", "링크"]].to_excel(writer, index=False, sheet_name="뉴스클리핑")
        workbook = writer.book
        worksheet = writer.sheets["뉴스클리핑"]
        link_format = workbook.add_format({'font_color': 'blue', 'underline': 1})
        for row_num, link in enumerate(df['링크']):
            worksheet.write_url(row_num + 1, 3, link, link_format, df.iloc[row_num]['제목'])
        worksheet.set_column('A:C', 15)
        worksheet.set_column('D:D', 80)
    return output.getvalue()

# =================================================
# 3. UI/UX 개선 (사이드바 및 탭 구조)
# =================================================
st.set_page_config(page_title="진주햄 뉴스 클리핑", layout="wide")

# 사이드바: 설정 및 키워드 관리
with st.sidebar:
    st.title("⚙️ 시스템 설정")
    start_d, end_d = get_fixed_date_range()
    st.info(f"🗓️ **대상 기간**\n{start_d} ~ {end_d}")
    
    st.divider()
    min_score = st.slider("🎯 업무 연관도 최소 점수", 0, 10, 3)
    
    if st.button("🌟 뉴스 수집 시작", type="primary", use_container_width=True):
        with st.spinner('뉴스를 수집 중...'):
            st.session_state.news_results = collect_news_final(st.session_state.keyword_mapping, start_d, end_d)
            st.session_state.cart_list = []
            st.rerun()
            
    st.divider()
    with st.expander("🛠️ 키워드 관리"):
        new_g = st.text_input("새 대분류 추가")
        if st.button("대분류 추가"):
            if new_g and new_g not in st.session_state.keyword_mapping:
                st.session_state.keyword_mapping[new_g] = []
                save_keywords(st.session_state.keyword_mapping)
                st.rerun()
        
        keys = list(st.session_state.keyword_mapping.keys())
        if keys:
            sel_g = st.selectbox("대분류 선택", options=keys)
            new_s = st.text_input(f"'{sel_g}' 키워드 추가")
            if st.button("소분류 추가"):
                if new_s and new_s not in st.session_state.keyword_mapping[sel_g]:
                    st.session_state.keyword_mapping[sel_g].append(new_s)
                    save_keywords(st.session_state.keyword_mapping)
                    st.rerun()
        
        for g, subs in list(st.session_state.keyword_mapping.items()):
            if st.button(f"🗑️ {g} 삭제", key=f"del_{g}"):
                del st.session_state.keyword_mapping[g]
                save_keywords(st.session_state.keyword_mapping)
                st.rerun()

# 메인 화면 영역
col_main, col_cart = st.columns([1.2, 0.8])

with col_main:
    st.subheader("📌 수집 뉴스 리스트")
    
    # 탭 생성: 전체 + 각 그룹별
    tab_names = ["전체"] + list(st.session_state.keyword_mapping.keys())
    tabs = st.tabs(tab_names)
    
    for i, tab in enumerate(tabs):
        with tab:
            group_filter = tab_names[i]
            filtered_res = [r for r in st.session_state.news_results if r.get('연관도점수', 0) >= min_score]
            if group_filter != "전체":
                filtered_res = [r for r in filtered_res if r['그룹'] == group_filter]
                
            if filtered_res:
                for idx, item in enumerate(filtered_res):
                    cb_key = f"news_{group_filter}_{idx}_v{st.session_state.reset_key}"
                    # 디자인 개선: 제목과 정보를 한눈에
                    col_check, col_txt = st.columns([0.1, 0.9])
                    with col_check:
                        is_checked = st.checkbox("", key=cb_key, value=item in st.session_state.cart_list)
                        if is_checked and item not in st.session_state.cart_list:
                            st.session_state.cart_list.append(item)
                        elif not is_checked and item in st.session_state.cart_list:
                            st.session_state.cart_list.remove(item)
                    with col_txt:
                        st.markdown(f"**{item['제목']}**")
                        st.caption(f"{item['출처']} | {item['기사일자']} | 점수: {item['연관도점수']} | [링크]({item['링크']})")
                    st.divider()
            else:
                st.info("해당하는 뉴스가 없습니다.")

with col_cart:
    st.subheader("🛒 추출 바구니")
    if st.session_state.cart_list:
        cart_df = pd.DataFrame(st.session_state.cart_list)
        st.dataframe(cart_df[["그룹", "출처", "제목"]], use_container_width=True, hide_index=True)
        
        file_name = f"진주햄_뉴스클리핑_{datetime.now().strftime('%Y%m%d')}.xlsx"
        st.download_button(
            label="📥 선택 기사 엑셀 다운로드",
            data=to_excel(st.session_state.cart_list),
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary"
        )
        
        if st.button("🔄 선택 전체 해제", use_container_width=True):
            st.session_state.reset_key += 1
            st.session_state.cart_list = []
            st.rerun()
    else:
        st.write("선택된 기사가 없습니다. 왼쪽 리스트에서 체크해주세요.")
