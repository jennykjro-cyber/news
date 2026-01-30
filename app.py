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
        if t in title_only:
            score += 2
        elif t in text:
            score += 1
    return score

def collect_news_final(mapping, start_date, end_date):
    google_news = GNews(language="ko", country="KR", max_results=25)
    all_rows = []
    all_search_kws = [kw for subs in mapping.values() for kw in subs]
    exclude_keywords = ["출시", "런칭", "신제품", "이벤트", "증정", "할인행사", "포토존", "팝업스토어", "증시", "주가", "상한가"]

    progress = st.progress(0)
    groups = list(mapping.items())

    for i, (group, subs) in enumerate(groups):
        if not subs:
            continue
        query = f"{group} ({' OR '.join(subs)})"
        articles = google_news.get_news(query)

        for a in articles:
            title = a.get("title", "")
            if any(ex in title for ex in exclude_keywords):
                continue

            ad = parse_news_date(a.get("published date", ""))
            if not ad or not (start_date <= ad <= end_date):
                continue

            score = get_relevance_score(title, a.get("description", ""), all_search_kws)

            all_rows.append({
                "키워드": group,
                "출처": a.get("publisher", {}).get("title", ""),
                "기사일자": ad.strftime("%Y-%m-%d"),
                "제목": title,
                "링크": a.get("url", ""),
                "연관도점수": score
            })

        progress.progress((i + 1) / len(groups))

    uniq = {r["링크"]: r for r in all_rows}
    return sorted(uniq.values(), key=lambda x: x["연관도점수"], reverse=True)

def to_excel(data):
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df[["키워드", "출처", "기사일자", "제목"]].to_excel(
            writer, index=False, sheet_name="뉴스클리핑"
        )
    return output.getvalue()

# =================================================
# 3. UI
# =================================================
st.set_page_config(page_title="진주햄 뉴스 클리핑", page_icon="🥓", layout="wide")

def toggle_cart_item(item, key):
    checked = st.session_state[key]
    links = [c["링크"] for c in st.session_state.cart_list]
    if checked and item["링크"] not in links:
        st.session_state.cart_list.append(item)
    if not checked:
        st.session_state.cart_list = [c for c in st.session_state.cart_list if c["링크"] != item["링크"]]

with st.sidebar:
    st.title("🥓 진주햄 뉴스봇")

    start_d, end_d = get_fixed_date_range()
    st.info(f"📅 {start_d.strftime('%m.%d')} (금) ~ {end_d.strftime('%m.%d')} (오늘)")

    min_score = st.slider("연관도 필터", 0, 5, 2)

    if st.button("🗂 이번 주 어쩔 수 없는 뉴스 수집", use_container_width=True):
        with st.spinner("🕵️‍♀️ 불가피하게 뉴스를 수집 중입니다"):
            st.session_state.news_results = collect_news_final(
                st.session_state.keyword_mapping, start_d, end_d
            )
            st.session_state.cart_list = []
            st.rerun()

    st.divider()
    st.subheader("📝 키워드 관리")

    col1, col2 = st.columns(2)
    with col1:
        new_group = st.text_input("대분류 입력")
    with col2:
        groups = list(st.session_state.keyword_mapping.keys())
        sel_g = st.selectbox("대분류 선택", groups) if groups else None

    if new_group and new_group not in st.session_state.keyword_mapping:
        st.session_state.keyword_mapping[new_group] = []
        save_keywords(st.session_state.keyword_mapping)
        st.rerun()

    if sel_g:
        new_sub = st.text_input("소분류 입력")
        if new_sub and new_sub not in st.session_state.keyword_mapping[sel_g]:
            st.session_state.keyword_mapping[sel_g].append(new_sub)
            save_keywords(st.session_state.keyword_mapping)
            st.rerun()

    with st.expander("📋 등록된 키워드 (접힘)", expanded=False):
        for g, subs in st.session_state.keyword_mapping.items():
            c1, c2 = st.columns([0.9, 0.1])
            c1.markdown(f"**{g}**")
            if c2.button("삭제", key=f"delg_{g}"):
                del st.session_state.keyword_mapping[g]
                save_keywords(st.session_state.keyword_mapping)
                st.rerun()

            if subs:
                clicked = st.multiselect(
                    "",
                    subs,
                    default=subs,
                    key=f"ms_{g}"
                )
                if set(clicked) != set(subs):
                    st.session_state.keyword_mapping[g] = clicked
                    save_keywords(st.session_state.keyword_mapping)
                    st.rerun()

# =================================================
# 메인
# =================================================
col_main, col_cart = st.columns([1.3, 0.7])

with col_main:
    st.subheader("🔍 검색 결과")

    with st.container(height=550):
        for i, item in enumerate(st.session_state.news_results):
            if item["연관도점수"] < min_score:
                continue
            key = f"cb_{i}_{item['링크']}"
            st.checkbox(
                f"[{item['키워드']}] {item['제목']}",
                key=key,
                value=item["링크"] in [c["링크"] for c in st.session_state.cart_list],
                on_change=toggle_cart_item,
                args=(item, key)
            )

with col_cart:
    st.subheader("🛒 쓸만한 뉴스 장바구니")

    if st.session_state.cart_list:
        df = pd.DataFrame(st.session_state.cart_list)
        st.dataframe(
            df[["키워드", "출처", "기사일자", "제목"]],
            use_container_width=True,
            hide_index=True
        )

        st.download_button(
            "📥 엑셀 다운로드",
            data=to_excel(st.session_state.cart_list),
            file_name=f"진주햄_뉴스클리핑_{end_d.strftime('%Y%m%d')}.xlsx"
        )
