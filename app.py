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

if "keyword_mapping" not in st.session_state:
    st.session_state.keyword_mapping = load_keywords()
if "news_results" not in st.session_state:
    st.session_state.news_results = []
if "cart_list" not in st.session_state:
    st.session_state.cart_list = []
if "reset_key" not in st.session_state:
    st.session_state.reset_key = 0

# =================================================
# 2. 핵심 로직 (검색 및 엑셀 생성)
# =================================================
def get_fixed_date_range():
    today = datetime.today()
    days_since_friday = (today.weekday() - 4) % 7
    last_friday = today - timedelta(days=days_since_friday)
    return last_friday.date(), today.date()

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
    google_news = GNews(language="ko", country="KR", max_results=25)
    all_rows = []
    all_search_kws = [kw for sublist in mapping.values() for kw in sublist]
    exclude_keywords = ["출시", "런칭", "신제품", "이벤트", "증정", "할인행사", "포토존", "팝업스토어", "증시", "주가", "상한가"]
    
    progress_bar = st.progress(0)
    groups = list(mapping.items())
    
    for i, (group, sub_kws) in enumerate(groups):
        if not sub_kws: continue
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
                "키워드": group,
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
        export_df = df[["키워드", "출처", "기사일자", "제목"]]
        export_df.to_excel(writer, index=False, sheet_name="뉴스클리핑")
        
        workbook = writer.book
        worksheet = writer.sheets["뉴스클리핑"]
        link_format = workbook.add_format({'font_color': 'blue', 'underline': 1})
        
        for row_num, link in enumerate(df['링크']):
            worksheet.write_url(row_num + 1, 3, link, link_format, df.iloc[row_num]['제목'])
            
        worksheet.set_column('A:C', 15)
        worksheet.set_column('D:D', 80)
    return output.getvalue()

# =================================================
# 3. UI/UX 구성 (사이드바 + 메인 탭 구조)
# =================================================
st.set_page_config(page_title="진주햄 뉴스 클리핑 시스템", layout="wide")

def add_group():
    new_g = st.session_state.new_group_input.strip()
    if new_g and new_g not in st.session_state.keyword_mapping:
        st.session_state.keyword_mapping[new_g] = []
        save_keywords(st.session_state.keyword_mapping)
    st.session_state.new_group_input = ""

def add_sub(group_name):
    new_s = st.session_state.new_sub_input.strip()
    if new_s and new_s not in st.session_state.keyword_mapping[group_name]:
        st.session_state.keyword_mapping[group_name].append(new_s)
        save_keywords(st.session_state.keyword_mapping)
    st.session_state.new_sub_input = ""

with st.sidebar:
    st.header("⚙️ 검색 설정")
    start_d, end_d = get_fixed_date_range()
    st.caption(f"수집 대상: {start_d} ~ {end_d}")
    
    min_score = st.slider("🎯 연관도 필터 점수", 0, 5, 2)
    
    if st.button("🌟 뉴스 수집 시작", type="primary", use_container_width=True):
        with st.spinner('뉴스를 검색 중입니다...'):
            st.session_state.news_results = collect_news_final(st.session_state.keyword_mapping, start_d, end_d)
            st.session_state.cart_list = []
            st.rerun()

    st.divider()
    
    with st.expander("🛠️ 키워드 관리", expanded=True):
        st.text_input("새 대분류 추가 (엔터)", key="new_group_input", on_change=add_group)
        
        keys = list(st.session_state.keyword_mapping.keys())
        if keys:
            sel_g = st.selectbox("대분류 선택", options=keys)
            st.text_input(f"'{sel_g}'에 키워드 추가 (엔터)", key="new_sub_input", on_change=add_sub, args=(sel_g,))
            
            st.write("---")
            # [수정] 키워드 리스트를 스크롤 가능한 컨테이너에 배치하여 공간 효율화
            st.write("📋 현재 등록된 리스트")
            with st.container(height=300, border=False):
                for g, subs in list(st.session_state.keyword_mapping.items()):
                    col_del, col_name = st.columns([0.2, 0.8])
                    if col_del.button("🗑️", key=f"del_{g}"):
                        del st.session_state.keyword_mapping[g]
                        save_keywords(st.session_state.keyword_mapping)
                        st.rerun()
                    col_name.markdown(f"**{g}**")
                    st.caption(f"{', '.join(subs)}")
                    st.divider()

# 메인 영역
st.title("🗞️ 주간 뉴스 클리핑 시스템")

col_main, col_cart = st.columns([1.3, 0.7])

with col_main:
    st.subheader("📌 뉴스 검색 결과")
    
    all_categories = ["전체"] + list(st.session_state.keyword_mapping.keys())
    tabs = st.tabs(all_categories)
    
    for i, tab in enumerate(tabs):
        with tab:
            current_cat = all_categories[i]
            filtered_res = [r for r in st.session_state.news_results if r.get('연관도점수', 0) >= min_score]
            if current_cat != "전체":
                filtered_res = [r for r in filtered_res if r['키워드'] == current_cat]
            
            if filtered_res:
                st.caption(f"검색 결과: {len(filtered_res)}건")
                for idx, item in enumerate(filtered_res):
                    cb_key = f"news_{current_cat}_{idx}_v{st.session_state.reset_key}"
                    col_check, col_content = st.columns([0.05, 0.95])
                    with col_check:
                        is_checked = st.checkbox("", key=cb_key, value=item in st.session_state.cart_list)
                        if is_checked and item not in st.session_state.cart_list:
                            st.session_state.cart_list.append(item)
                        elif not is_checked and item in st.session_state.cart_list:
                            st.session_state.cart_list.remove(item)
                    with col_content:
                        st.markdown(f"**[{item['키워드']}]** {item['제목']}")
                        st.caption(f"{item['출처']} | {item['기사일자']} | 연관도: {item['연관도점수']}점 | [원문보기]({item['링크']})")
                    st.write("")
            else:
                st.info(f"'{current_cat}' 탭에 표시할 뉴스가 없습니다.")

with col_cart:
    st.subheader("🛒 추출 바구니")
    if st.session_state.cart_list:
        cart_df = pd.DataFrame(st.session_state.cart_list)
        st.dataframe(cart_df[["키워드", "출처", "제목"]], use_container_width=True, hide_index=True)
        st.write(f"현재 **{len(st.session_state.cart_list)}**개 기사 선택됨")
        
        file_name = f"진주햄_뉴스클리핑_{end_d.strftime('%Y%m%d')}.xlsx"
        st.download_button(
            label="📥 엑셀 파일 다운로드",
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
        st.info("리스트에서 체크박스를 선택하면 여기에 담깁니다.")
