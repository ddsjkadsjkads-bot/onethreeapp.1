"""장보기 알림메모 | 실행: streamlit run app.py
GitHub 저장소에 이 파일과 requirements.txt를 올려 Streamlit Community Cloud에 배포하세요.
QR은 배포된 HTTPS 주소를 입력하면 생성됩니다. QR 자체가 서버를 실행하지는 않습니다.
데이터는 접속한 브라우저의 Streamlit 세션에 보관됩니다. 새로고침/연결 종료/재시작에
대비해 상단 도구 메뉴에서 JSON 백업을 내려받으세요. 기기 간 자동 동기화는 없습니다.
"""
from __future__ import annotations

import io
import json
import uuid
from datetime import datetime
from urllib.parse import urlparse

import qrcode
import streamlit as st

CATEGORIES = ["🥬 야채", "🍎 과일", "🥩 육류", "🐟 수산", "🥚 유제품·달걀", "🍚 곡물", "🥫 가공식품", "🧴 생활용품", "🛒 기타"]
PRIORITIES = {1: "1 · 필수", 2: "2 · 적정가면", 3: "3 · 여유 있으면"}


def money(value: int) -> str:
    return f"{value:,}원"


def total_price(cart: list[dict]) -> int:
    return sum(row["unit_price"] * row["quantity"] for row in cart)


def validate_backup(raw: bytes) -> dict:
    """백업 파일은 신뢰하지 않고 모든 필드의 타입/범위를 점검한다."""
    if len(raw) > 2_000_000:
        raise ValueError("백업 파일은 2MB 이하만 지원합니다.")
    obj = json.loads(raw)
    if not isinstance(obj, dict) or obj.get("version") != 1:
        raise ValueError("지원하지 않는 백업 형식입니다.")
    seen = set()
    for group in ("items", "cart"):
        rows = obj.get(group)
        if not isinstance(rows, list) or len(rows) > 2000:
            raise ValueError("잘못된 목록입니다.")
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("잘못된 상품입니다.")
            ident = row.get("id")
            if not isinstance(ident, str) or len(ident) > 80 or not ident or ident in seen:
                raise ValueError("상품 식별자가 올바르지 않습니다.")
            seen.add(ident)
            if not isinstance(row.get("name"), str) or not row["name"].strip() or len(row["name"]) > 60:
                raise ValueError("상품명이 올바르지 않습니다.")
            if row.get("category") not in CATEGORIES:
                raise ValueError("카테고리가 올바르지 않습니다.")
            if type(row.get("priority")) is not int or row["priority"] not in PRIORITIES:
                raise ValueError("중요도가 올바르지 않습니다.")
            if type(row.get("limit")) is not int or not 0 <= row["limit"] <= 100_000_000:
                raise ValueError("기준가가 올바르지 않습니다.")
            if type(row.get("held")) is not bool:
                raise ValueError("보류 상태가 올바르지 않습니다.")
            if group == "cart":
                for field, low, high in (("unit_price", 1, 100_000_000), ("quantity", 1, 9999)):
                    if type(row.get(field)) is not int or not low <= row[field] <= high:
                        raise ValueError("가격 또는 수량이 올바르지 않습니다.")
    return obj


def main() -> None:
    st.set_page_config(page_title="장보기 알림메모", page_icon="🛒", layout="centered", initial_sidebar_state="collapsed")
    st.markdown("""
    <style>
    .stApp { background: #f5f8f6; }
    .block-container { max-width: 540px; padding: .6rem .8rem 1rem; }
    [data-testid="stHeader"] { height: 0; }
    [data-testid="stVerticalBlock"] { gap: .35rem; }
    [data-testid="stForm"] { padding: .45rem .6rem; border-radius: 14px; background: #fff; }
    [data-testid="stHorizontalBlock"] { gap: .4rem; }
    [data-testid="stWidgetLabel"] p { font-size: .8rem; }
    .stButton button, .stFormSubmitButton button { min-height: 2.2rem; border-radius: 10px; }
    .stTextInput input, .stNumberInput input { min-height: 2.2rem; }
    .summary { padding: .65rem .8rem; border-radius: 14px; background: #126448; color: white; display:flex; justify-content:space-between; align-items:center; }
    .summary b { font-size: 1.4rem; }
    .summary small { opacity: .9; }
    .section { font-size: .86rem; font-weight: 750; color: #153c2e; margin-top: .2rem; }
    .hint { color: #496257; font-size: .75rem; margin: 0; }
    @media (max-width: 640px) {
      [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; }
      [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { min-width: 0 !important; width: auto !important; flex: 1 1 0 !important; }
      .block-container { padding-top: .4rem; }
    }
    </style>
    """, unsafe_allow_html=True)
    for key in ("items", "cart"):
        if key not in st.session_state:
            st.session_state[key] = []
    items, cart = st.session_state["items"], st.session_state["cart"]

    title, tools = st.columns([4, 1])
    title.markdown("### 🛒 장보기 알림메모")
    with tools:
        with st.popover("⚙️", help="QR·백업·사용 안내"):
            st.markdown("**QR로 앱 열기**")
            url = st.text_input("배포된 앱의 HTTPS 주소", placeholder="https://your-app.streamlit.app", key="public_url")
            if url:
                parsed = urlparse(url.strip())
                if parsed.scheme == "https" and parsed.netloc and not parsed.username and not parsed.password:
                    qr = qrcode.make(url.strip())
                    image = io.BytesIO()
                    qr.save(image, format="PNG")
                    st.image(image.getvalue(), width=190)
                    st.download_button("QR 이미지 저장", image.getvalue(), "shopping-qr.png", "image/png")
                else:
                    st.warning("유효한 HTTPS 주소를 입력하세요.")
            st.caption("QR은 앱 주소를 엽니다. 다른 휴대폰에 메모가 자동 공유되지는 않습니다.")
            payload = json.dumps({"version": 1, "items": items, "cart": cart}, ensure_ascii=False, indent=2)
            st.download_button("📥 메모·카트 백업", payload, "shopping-backup.json", "application/json")
            uploaded = st.file_uploader("JSON 백업 복원", type=["json"])
            replace = st.checkbox("현재 메모와 카트를 백업 내용으로 교체")
            if st.button("백업 복원", disabled=uploaded is None or not replace):
                try:
                    restored = validate_backup(uploaded.getvalue())
                except (ValueError, TypeError, KeyError) as exc:
                    st.error(f"복원 실패: {exc}")
                else:
                    st.session_state["items"] = restored["items"]
                    st.session_state["cart"] = restored["cart"]
                    st.rerun()
            st.caption("1 필수 / 2 적정가면 / 3 여유 있으면. 기준가는 1개·1봉·1팩당 가격입니다. 0원은 미지정입니다. 담기는 결제 완료가 아닌 카트 예상액 기록입니다.")
            st.caption("서버 푸시 알림은 제공하지 않습니다. 새로고침·연결 종료 시 데이터가 사라질 수 있으니 백업해 주세요. 작은 화면·확대 글꼴·키보드 사용 중에는 스크롤이 생길 수 있습니다.")

    count = sum(row["quantity"] for row in cart)
    st.markdown(f'<div class="summary"><span>현재 카트<br><b>{money(total_price(cart))}</b></span><span><small>담은 수량 {count}개<br>남은 메모 {len(items)}건</small></span></div>', unsafe_allow_html=True)

    st.markdown('<div class="section">＋ 살 것 추가</div>', unsafe_allow_html=True)
    with st.form("add_item", clear_on_submit=True, border=True):
        c1, c2 = st.columns([1, 2])
        category = c1.selectbox("카테고리", CATEGORIES, label_visibility="collapsed")
        name = c2.text_input("상품명", placeholder="상품명 (예: 양파 1망)", max_chars=60, label_visibility="collapsed")
        c1, c2, c3 = st.columns([1, 1, 1])
        priority = c1.selectbox("중요도", list(PRIORITIES), format_func=lambda p: PRIORITIES[p], label_visibility="collapsed")
        limit = c2.number_input("기준 단가(원)", min_value=0, max_value=100_000_000, step=100, value=0, label_visibility="collapsed", help="이 가격보다 비싸면 보류할 기준. 0은 미지정.")
        submitted = c3.form_submit_button("추가", use_container_width=True, type="primary")
        if submitted:
            if not name.strip():
                st.warning("상품명을 입력하세요.")
            else:
                items.append({"id": uuid.uuid4().hex, "name": name.strip(), "category": category, "priority": priority, "limit": int(limit), "held": False})
                st.rerun()

    st.markdown('<div class="section">📝 메모 → 가격 확인 → 카트 담기</div>', unsafe_allow_html=True)
    if items:
        ordered = sorted(items, key=lambda row: (row["held"], row["priority"]))
        by_id = {row["id"]: row for row in ordered}
        def label(ident: str) -> str:
            row = by_id[ident]
            target = f" · 기준 {money(row['limit'])}" if row["limit"] else ""
            hold = "⏸ " if row["held"] else ""
            return f"{hold}{PRIORITIES[row['priority']]} | {row['category']} {row['name']}{target}"
        selected_id = st.selectbox("남은 메모", list(by_id), format_func=label, label_visibility="collapsed")
        item = by_id[selected_id]
        with st.form(f"purchase_{selected_id}"):
            left, right = st.columns(2)
            unit_price = left.number_input("실제 단가(원)", min_value=0, max_value=100_000_000, value=0, step=100)
            quantity = right.number_input("수량(개·팩·봉)", min_value=1, max_value=9999, value=1, step=1)
            over_ok = st.checkbox("기준가를 초과해도 구매", value=False)
            left, right = st.columns(2)
            buy = left.form_submit_button("🛒 담기", type="primary", use_container_width=True)
            hold = right.form_submit_button("↩ 보류 해제" if item["held"] else "⏸ 비싸면 보류", use_container_width=True)
            if buy:
                if unit_price <= 0:
                    st.warning("실제 단가를 입력해야 카트에 담을 수 있어요.")
                elif item["limit"] > 0 and unit_price > item["limit"] and not over_ok:
                    st.warning(f"기준가보다 {money(int(unit_price) - item['limit'])} 비싸요. 보류하거나 ‘초과해도 구매’를 체크하세요.")
                else:
                    cart.append({**item, "unit_price": int(unit_price), "quantity": int(quantity), "added_at": datetime.now().isoformat(timespec="seconds")})
                    st.session_state["items"] = [row for row in items if row["id"] != selected_id]
                    st.rerun()
            elif hold:
                item["held"] = not item["held"]
                st.rerun()
    else:
        st.caption("살 물건을 추가하세요. 담은 물건은 메모에서 빠지고 카트에 기록돼요.")

    st.markdown('<div class="section">🧺 카트 내역</div>', unsafe_allow_html=True)
    if cart:
        by_cart_id = {row["id"]: row for row in cart}
        c1, c2 = st.columns([3, 1])
        selected_cart_id = c1.selectbox("담은 물건", list(by_cart_id), format_func=lambda ident: f"{by_cart_id[ident]['name']} · {money(by_cart_id[ident]['unit_price'])} × {by_cart_id[ident]['quantity']} = {money(by_cart_id[ident]['unit_price'] * by_cart_id[ident]['quantity'])}", label_visibility="collapsed")
        if c2.button("되돌리기", use_container_width=True, help="카트에서 빼고 원래 메모로 복원. 가격·수량을 수정하려면 복원 후 다시 담으세요."):
            old = by_cart_id[selected_cart_id]
            items.append({key: old[key] for key in ("id", "name", "category", "priority", "limit", "held")})
            st.session_state["cart"] = [row for row in cart if row["id"] != selected_cart_id]
            st.rerun()
    else:
        st.caption("아직 카트가 비어 있어요. 가격 × 수량이 총액에 실시간 반영됩니다.")


if __name__ == "__main__":
    main()
