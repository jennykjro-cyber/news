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

# =================================================
# 2. 핵심 로직
# =================================================
def get_fixed_date_range():
    today = datetime.today()
    days_since_friday = (today.weekday() - 4) % 7
    last_friday = today - timedelta(days=days_since_friday)
    return last_friday.date(), today.date()

def parse_news_date(date_str):
    try: return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z").date()
    except: return None

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
        articles = google_news.get_news(f"{group} ({' OR '.join(sub_kws)})")
        for a in articles:
            title = a.get("title", "제목 없음")
            if any(ex in title for ex in exclude_keywords): continue
            article_date = parse_news_date(a.get("published date", ""))
            if not article_date or not (start_date <= article_date <= end_date): continue
            score = get_relevance_score(title, a.get("description", ""), all_search_kws)
            all_rows.append({"키워드": group, "출처": a.get("publisher", {}).get("title", "출처 미상"), "기사일자": article_date.strftime("%Y-%m-%d"), "제목": title, "링크": a.get("url", ""), "연관도점수": score})
        progress_bar.progress((i + 1) / len(groups))
    unique_rows = {r['링크']: r for r in all_rows}.values()
    return sorted(list(unique_rows), key=lambda x: x['연관도점수'], reverse=True)

def to_excel(data_list):
    df = pd.DataFrame(data_list)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df[["키워드", "출처", "기사일자", "제목"]].to_excel(writer, index=False, sheet_name="뉴스클리핑")
        workbook, worksheet = writer.book, writer.sheets["뉴스클리핑"]
        link_format = workbook.add_format({'font_color': 'blue', 'underline': 1})
        for row_num, link in enumerate(df['링크']):
            worksheet.write_url(row_num + 1, 3, link, link_format, df.iloc[row_num]['제목'])
        worksheet.set_column('A:C', 15); worksheet.set_column('D:D', 80)
    return output.getvalue()

# =================================================
# 3. UI/UX
# =================================================
st.set_page_config(page_title="진주햄 뉴스 클리핑", page_icon="🥓", layout="wide")

def toggle_cart_item(item, key):
    if st.session_state[key]:
        if item['링크'] not in [c['링크'] for c in st.session_state.cart_list]:
            st.session_state.cart_list.append(item)
    else:
        st.session_state.cart_list = [c for c in st.session_state.cart_list if c['링크'] != item['링크']]

def add_group():
    new_g = st.session_state.new_group_input.strip()
    if new_g and new_g not in st.session_state.keyword_mapping:
        st.session_state.keyword_mapping[new_g] = []; save_keywords(st.session_state.keyword_mapping)
    st.session_state.new_group_input = ""

def add_sub(group_name):
    new_s = st.session_state.new_sub_input.strip()
    if new_s and new_s not in st.session_state.keyword_mapping[group_name]:
        st.session_state.keyword_mapping[group_name].append(new_s); save_keywords(st.session_state.keyword_mapping)
    st.session_state.new_sub_input = ""

with st.sidebar:
    st.title("🥓 진주햄 뉴스봇")
    st.write("---")
    st.subheader("⚙️ 검색 설정")
    start_d, end_d = get_fixed_date_range()
    st.info(f"📅 {start_d.strftime('%m.%d')} ~ {end_d.strftime('%m.%d')}")
    min_score = st.slider("🎯 연관도 필터", 0, 5, 2)
    if st.button("🗂 뉴스 수집 시작", type="primary", use_container_width=True):
        st.session_state.news_results = collect_news_final(st.session_state.keyword_mapping, start_d, end_d)
        st.session_state.cart_list = []; st.rerun()

    st.divider()
    # [수정] 키워드 관리실: expanded=False 로 설정하여 기본적으로 접어둠
    with st.expander("📝 키워드 관리실 (클릭하여 열기)", expanded=False):
        col1, col2 = st.columns(2)
        with col1: st.text_input("대분류", key="new_group_input", on_change=add_group, placeholder="분류명")
        with col2:
            keys = list(st.session_state.keyword_mapping.keys())
            sel_g = st.selectbox("선택", options=keys) if keys else st.selectbox("없음", ["-"])
        if keys:
            st.text_input(f"➕ '{sel_g}'에 추가", key="new_sub_input", on_change=add_sub, args=(sel_g,))
        
        st.markdown("---")
        with st.container(height=300, border=False):
            for g, subs in list(st.session_state.keyword_mapping.items()):
                c_t, c_d = st.columns([0.8, 0.2])
                c_t.markdown(f"**{g}**")
                if c_d.button("🗑️", key=f"del_g_{g}"):
                    del st.session_state.keyword_mapping[g]; save_keywords(st.session_state.keyword_mapping); st.rerun()
                
                kw_cols = st.columns(2)
                for idx, s in enumerate(subs):
                    with kw_cols[idx % 2]:
                        if st.button(f"{s} ×", key=f"del_kw_{g}_{s}", use_container_width=True):
                            st.session_state.keyword_mapping[g].remove(s); save_keywords(st.session_state.keyword_mapping); st.rerun()

# 메인 화면
st.title("📰 Weekly News Clipping")
col_main, col_cart = st.columns([1.3, 0.7])

with col_main:
    st.subheader("🔍 검색 결과")
    all_categories = ["전체"] + list(st.session_state.keyword_mapping.keys())
    tabs = st.tabs([f" {cat} " for cat in all_categories])
    cart_links = [item['링크'] for item in st.session_state.cart_list]
    
    for i, tab in enumerate(tabs):
        with tab:
            current_cat = all_categories[i]
            filtered_res = [r for r in st.session_state.news_results if r.get('연관도점수', 0) >= min_score]
            if current_cat != "전체": filtered_res = [r for r in filtered_res if r['키워드'] == current_cat]
            
            if filtered_res:
                st.success(f"총 {len(filtered_res)}건 발견")
                # [수정] 뉴스 리스트 스크롤: height=500 설정으로 5개 내외 유지
                with st.container(height=550):
                    for idx, item in enumerate(filtered_res):
                        u_key = f"cb_{current_cat}_{idx}_{item['링크']}"
                        with st.container(border=True):
                            c_ch, c_tx = st.columns([0.05, 0.95])
                            c_ch.checkbox("", key=u_key, value=(item['링크'] in cart_links), on_change=toggle_cart_item, args=(item, u_key))
                            c_tx.markdown(f"**[{item['키워드']}] {item['제목']}**")
                            c_tx.caption(f"🗞 {item['출처']} | 🗓 {item['기사일자']} | ⭐ {item['연관도점수']}점")
                            c_tx.markdown(f"[🔗 기사 원문]({item['링크']})")
            else: st.info("뉴스가 없습니다.")

with col_cart:
    st.subheader("🛒 장바구니")
    if st.session_state.cart_list:
        with st.container(border=True):
            st.dataframe(pd.DataFrame(st.session_state.cart_list)[["키워드", "제목"]], use_container_width=True, hide_index=True, height=300)
            st.download_button(label="📥 엑셀 다운로드", data=to_excel(st.session_state.cart_list), file_name=f"뉴스클리핑_{datetime.now().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, type="primary")
            if st.button("🔄 초기화", use_container_width=True):
                st.session_state.cart_list = []; st.rerun()
    else: st.info("기사를 담아주세요.")
