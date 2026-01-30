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
    try:
        return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z").date()
    except:
        return None

def get_relevance_score(title, desc, all_keywords):
    score = 0
    text = f"{title} {desc}".replace(" ", "").lower()
    title_only = title.replace(" ", "").lower()
    for kw in all_keywords:
        t = kw.replace(" ", "").lower()
        if t in title_only: score += 2
        elif t in text: score += 1
    return score

def collect_news_final(mapping, start_date, end_date):
    google_news = GNews(language="ko", country="KR", max_results=25)
    rows = []
    all_kws = [kw for subs in mapping.values() for kw in subs]
    exclude = ["출시", "런칭", "신제품", "이벤트", "증정", "할인행사", "증시", "주가"]

    for g, subs in mapping.items():
        if not subs:
            continue
        q = f"{g} ({' OR '.join(subs)})"
        for a in google_news.get_news(q):
            title = a.get("title", "")
            if any(e in title for e in exclude):
                continue
            d = parse_news_date(a.get("published date", ""))
            if not d or not (start_date <= d <= end_date):
                continue
            rows.append({
                "키워드": g,
                "출처": a.get("publisher", {}).get("title", ""),
                "기사일자": d.strftime("%Y-%m-%d"),
                "제목": title,
                "링크": a.get("url", ""),
                "연관도점수": get_relevance_score(title, a.get("description", ""), all_kws)
            })
    uniq = {r["링크"]: r for r in rows}.values()
    return sorted(uniq, key=lambda x: x["연관도점수"], reverse=True)

def to_excel(data):
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df[["키워드", "출처", "기사일자", "제목"]].to_excel(writer, index=False)
    return output.getvalue()

# =================================================
# 3. UI
# =================================================
st.set_page_config(page_title="진주햄 뉴스 클리핑", layout="wide")

def toggle_cart_item(item, key):
    checked = st.session_state[key]
    links = [c["링크"] for c in st.session_state.cart_list]
    if checked and item["링크"] not in links:
        st.session_state.cart_list.append(item)
    if not checked:
        st.session_state.cart_list = [c for c in st.session_state.cart_list if c["링크"] != item["링크"]]

def add_group():
    g = st.session_state.new_group_input.strip()
    if g and g not in st.session_state.keyword_mapping:
        st.session_state.keyword_mapping[g] = []
        save_keywords(st.session_state.keyword_mapping)
    st.session_state.new_group_input = ""

def add_sub(group):
    s = st.session_state.new_sub_input.strip()
    if s and s not in st.session_state.keyword_mapping[group]:
        st.session_state.keyword_mapping[group].append(s)
        save_keywords(st.session_state.keyword_mapping)
    st.session_state.new_sub_input = ""

with st.sidebar:
    st.title("진주햄 뉴스봇")
    start_d, end_d = get_fixed_date_range()
    min_score = st.slider("연관도", 0, 5, 2)

    if st.button("뉴스 수집", use_container_width=True):
        st.session_state.news_results = collect_news_final(st.session_state.keyword_mapping, start_d, end_d)
        st.session_state.cart_list = []
        st.rerun()

    st.divider()
    st.subheader("키워드 관리")

    c1, c2 = st.columns(2)
    with c1:
        st.text_input("대분류 추가", key="new_group_input", on_change=add_group)
    with c2:
        groups = list(st.session_state.keyword_mapping.keys())
        sel_g = st.selectbox("선택", groups) if groups else None

    if sel_g:
        st.text_input("하위 키워드 추가", key="new_sub_input", on_change=add_sub, args=(sel_g,))

    st.markdown("### 등록된 키워드")
    for g, subs in list(st.session_state.keyword_mapping.items()):
        with st.expander(f"{g} ({len(subs)})", expanded=True):
            c_del, _ = st.columns([0.15, 0.85])
            if c_del.button("🗑️ 대분류 삭제", key=f"del_group_{g}"):
                del st.session_state.keyword_mapping[g]
                save_keywords(st.session_state.keyword_mapping)
                st.rerun()

            if not subs:
                st.caption("하위 키워드 없음")
            else:
                cols = st.columns(4)
                for i, s in enumerate(list(subs)):
                    if cols[i % 4].button(s, key=f"del_{g}_{s}", use_container_width=True):
                        st.session_state.keyword_mapping[g].remove(s)
                        save_keywords(st.session_state.keyword_mapping)
                        st.rerun()

st.title("Weekly News Clipping")
col_main, col_cart = st.columns([1.3, 0.7])

with col_main:
    tabs = ["전체"] + list(st.session_state.keyword_mapping.keys())
    tab_objs = st.tabs(tabs)

    cart_links = [c["링크"] for c in st.session_state.cart_list]

    for i, tab in enumerate(tab_objs):
        with tab:
            cat = tabs[i]
            res = [r for r in st.session_state.news_results if r["연관도점수"] >= min_score]
            if cat != "전체":
                res = [r for r in res if r["키워드"] == cat]

            with st.container(height=500):
                for idx, item in enumerate(res):
                    k = f"cb_{cat}_{idx}"
                    c1, c2 = st.columns([0.05, 0.95])
                    with c1:
                        st.checkbox("", key=k, value=item["링크"] in cart_links,
                                    on_change=toggle_cart_item, args=(item, k))
                    with c2:
                        st.markdown(f"**[{item['키워드']}] {item['제목']}**")
                        st.caption(f"{item['출처']} | {item['기사일자']} | {item['연관도점수']}점")

with col_cart:
    st.subheader("쓸만한 뉴스 장바구니")
    if st.session_state.cart_list:
        df = pd.DataFrame(st.session_state.cart_list)
        st.dataframe(df[["키워드", "출처", "기사일자", "제목"]],
                     use_container_width=True, hide_index=True, height=300)
        st.download_button(
            "엑셀 다운로드",
            to_excel(st.session_state.cart_list),
            file_name=f"진주햄_뉴스클리핑_{end_d.strftime('%Y%m%d')}.xlsx",
            use_container_width=True
        )
    else:
        st.info("선택된 뉴스가 없습니다.")
