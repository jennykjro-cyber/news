import streamlit as st
import pandas as pd
from gnews import GNews
from datetime import datetime, timedelta
from io import BytesIO

# =================================================
# 설정
# =================================================
BUSINESS_KEYWORDS = [
    "육가공", "햄", "소시지", "식품",
    "원가", "가격", "가격인상",
    "마케팅", "브랜드", "유통",
    "편의점", "대체육", "시장", "매출"
]

google_news = GNews(
    language="ko",
    country="KR",
    max_results=50
)

# =================================================
# 날짜 관련 함수
# =================================================
def get_date_range():
    """
    전주 토요일 ~ 이번주 목요일
    """
    today = datetime.today()

    # 이번주 목요일 (weekday: 월0 ~ 일6, 목요일=3)
    this_thursday = today - timedelta(days=(today.weekday() - 3) % 7)

    # 전주 토요일
    last_saturday = this_thursday - timedelta(days=5)

    return last_saturday.date(), this_thursday.date()


def parse_news_date(date_str):
    """
    Google News 기사 날짜 문자열 → date
    """
    try:
        return datetime.strptime(
            date_str, "%a, %d %b %Y %H:%M:%S %Z"
        ).date()
    except:
        return None

# =================================================
# 연관도 계산
# =================================================
def relevance_score(text: str) -> int:
    score = 0
    for kw in BUSINESS_KEYWORDS:
        if kw in text:
            score += 1
    return score

# =================================================
# 뉴스 수집
# =================================================
def collect_news(keyword: str, start_date, end_date):
    articles = google_news.get_news(keyword)
    rows = []

    for a in articles:
        raw_date = a.get("published date", "")
        article_date = parse_news_date(raw_date)

        # 날짜 파싱 실패 시 제외
        if article_date is None:
            continue

        # 기간 필터
        if not (start_date <= article_date <= end_date):
            continue

        title = a.get("title", "")
        description = a.get("description", "")
        content = f"{title} {description}"

        score = relevance_score(content)

        rows.append({
            "검색키워드": keyword,
            "출처": a.get("publisher", {}).get("title", ""),
            "기사일자": article_date.strftime("%Y-%m-%d"),
            "제목": title,
            "링크": a.get("url", ""),
            "연관도점수": score
        })

    return pd.DataFrame(rows)

# =================================================
# 엑셀 변환
# =================================================
def to_excel(df: pd.DataFrame):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# =================================================
# Streamlit UI
# =================================================
st.title("📰 식품/육가공 뉴스 스크랩 자동화")

start_date, end_date = get_date_range()
st.caption(f"📅 기사 수집 기간: {start_date} ~ {end_date}")

keyword = st.text_input("🔎 검색 키워드 입력")

min_score = st.slider(
    "업무 연관도 필터 (점수 이상만 표시)",
    min_value=0,
    max_value=5,
    value=2
)

if "cart" not in st.session_state:
    st.session_state.cart = pd.DataFrame()

if st.button("기사 수집"):
    if not keyword:
        st.warning("키워드를 입력하세요.")
    else:
        df = collect_news(keyword, start_date, end_date)
        df = df[df["연관도점수"] >= min_score]

        if df.empty:
            st.info("조건에 맞는 기사가 없습니다.")
        else:
            st.subheader("📌 수집된 기사")

            for idx, row in df.iterrows():
                checked = st.checkbox(
                    f"[{row['출처']}] {row['제목']} ({row['기사일자']})",
                    key=f"chk_{idx}"
                )

                if checked:
                    st.session_state.cart = pd.concat(
                        [st.session_state.cart, pd.DataFrame([row])],
                        ignore_index=True
                    )

# =================================================
# 장바구니 영역
# =================================================
st.subheader("🛒 선택한 기사")

if not st.session_state.cart.empty:
    display_df = st.session_state.cart.drop_duplicates(
        subset=["제목", "링크"]
    ).copy()

    display_df["제목(하이퍼링크)"] = display_df.apply(
        lambda x: f'=HYPERLINK("{x["링크"]}", "{x["제목"]}")',
        axis=1
    )

    final_df = display_df[
        ["검색키워드", "출처", "기사일자", "제목(하이퍼링크)"]
    ]

    st.dataframe(final_df, use_container_width=True)

    excel_data = to_excel(final_df)

    st.download_button(
        label="📥 엑셀 다운로드",
        data=excel_data,
        file_name="news_scrap.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("선택한 기사가 없습니다.")
