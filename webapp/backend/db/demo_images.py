"""검증된 커버 이미지 URL — HEAD 200 확인된 Unsplash만 사용.

전략 (우선순위 순):
1. 시드 데이터의 큐레이션 URL이 살아있으면 그대로 사용 (쌀→쌀 사진).
2. 큐레이션 URL이 깨졌으면 (`_BROKEN_SEED_URLS`) 제목 키워드로 의미 매칭.
3. 키워드 매칭도 실패하면 카테고리 풀에서 결정적 폴백.
"""
from __future__ import annotations

from sqlalchemy import select

from db.models import ListingRow

_S = "?auto=format&fit=crop&w=1600&q=85"


def _u(pid: str) -> str:
    return f"https://images.unsplash.com/photo-{pid}{_S}"


# --- 검증된 사진 URL (HEAD 200 확인) ---
# 곡물·쌀
IMG_RICE = _u("1586201375761-83865001e31c")
IMG_BEANS = _u("1515543904379-3d757afe72e4")
IMG_RICE_CAKE = _u("1591197172062-c718f82aba20")
IMG_NOODLE = _u("1504674900247-0877df9cc836")

# 과일
IMG_APPLE = _u("1568702846914-96b305d2aaeb")
IMG_PERSIMMON = _u("1606851094291-6efae152bb87")
IMG_MANDARIN_TREE = _u("1574226516831-e1dff420e562")
IMG_CITRUS = _u("1547514701-42782101795e")

# 차
IMG_TEA = _u("1576092768241-dec231879fc3")
IMG_TEA_CUP = _u("1597481499750-3e6b22637e12")
IMG_MATCHA = _u("1564890369478-c89ca6d9cde9")

# 해산물
IMG_FISH_DISH = _u("1544025162-d76694265947")
IMG_SEAFOOD = _u("1562967914-608f82629710")
IMG_OCTOPUS = _u("1565299585323-38d6b0865b47")
IMG_DRIED_FISH = _u("1574781330855-d0db8cc6a79c")
IMG_FISH_MARKET = _u("1559339352-11d035aa65de")

# 양념·가공
IMG_SAUCE = _u("1631452180519-c014fe946bc7")
IMG_JUICE = _u("1560806887-1e4cd0b6cbd6")
IMG_SALT = _u("1471193945509-9ad0617afabf")
IMG_SALT_FIELD = _u("1488477181946-6428a0291777")
IMG_GARLIC = _u("1546549032-9571cd6b27df")
IMG_GARLIC_BRAID = _u("1615485290382-441e4d049cb5")

# 고기
IMG_PORK = _u("1546964124-0cce460f38ef")
IMG_MEAT = _u("1558030006-450675393462")

# 공예
IMG_PAPER_LETTER = _u("1455390582262-044cdead277a")
IMG_LAMP = _u("1521478706270-f2e33c203d95")
IMG_FAN = _u("1543589077-47d81606c1bf")
IMG_BAMBOO = _u("1466692476868-aef1dfb1e735")

# 도자기
IMG_POTTERY1 = _u("1610701596007-11502861dcfa")
IMG_POTTERY2 = _u("1565193566173-7a0ee3dbe261")
IMG_POTTERY3 = _u("1493106641515-6b5631de4bb9")
IMG_POTTERY4 = _u("1607349913338-fca6f7fc42d0")

# 체험
IMG_RICE_PADDY = _u("1500382017468-9049fed747ef")
IMG_BAMBOO_FOREST = IMG_BAMBOO
IMG_COASTAL = _u("1500380804539-4e1e8c1e7118")
IMG_SURF = _u("1500916434205-0c77489c6cf7")
IMG_SURF_LESSON = _u("1502680390469-be75c86b636f")
IMG_PADDLE = _u("1530549387789-4c1017266635")
IMG_DIVING = _u("1559827260-dc66d52bef19")
IMG_BEACH = _u("1551776235-dde6d482980b")
IMG_FIELD = _u("1469854523086-cc02fe5d8800")
IMG_HARBOR = _u("1564501049412-61c2a3083791")
IMG_CAMPING = _u("1532339142463-fd0a8979791a")
IMG_FARM = _u("1582719508461-905c673771fd")

# 숙박
IMG_OCEAN_VIEW = _u("1568084680786-a84f91d1153c")
IMG_LIVING = _u("1505691938895-1758d7feb511")
IMG_HANOK = _u("1600585154340-be6161a56a0c")
IMG_TERRACE = _u("1582719478250-c89cae4dc85b")
IMG_CABIN = _u("1520250497591-112f2f40a3f4")
IMG_GLAMPING = _u("1487730116645-74489c95b41b")
IMG_BEACH_CONDO = _u("1564013799919-ab600027ffc6")
IMG_HOTEL = _u("1566073771259-6a8506099945")
IMG_POOLVILLA = _u("1571896349842-33c89424de2d")
IMG_GUESTHOUSE = _u("1611892440504-42a792e24d32")
IMG_ROOFTOP = _u("1568605114967-8130f3a36994")
IMG_PORT = _u("1602002418082-a4443e081dd1")
IMG_BEACH_HOUSE = _u("1551918120-9739cb430c6d")
IMG_SUNSET_STAY = _u("1505873242700-f289a29e1e0f")
IMG_POOL = _u("1571003123894-1f0594d2b5d9")
IMG_MOUNTAIN_LODGE = _u("1547191783-94d5f8f6d8b1")
IMG_MOUNTAIN_CABIN = _u("1502136969935-8d8eef54d77b")
IMG_CAMPERVAN = _u("1523987355523-c7b5b0dd90a7")

# --- 추가 큐레이션 (웹에서 HEAD 200 + 육안 확인) ---
IMG_MACKEREL = _u("1600699899970-b1c9fadd8f9e")      # 구운 고등어 한 접시
IMG_KIMCHI = _u("1708388064278-707e85eaddc0")        # 배추김치
IMG_BAMBOO_BOX = _u("1633878353628-5fc8b983325c")    # 대나무 용기·도시락 세트
IMG_BAMBOO_TRAY = _u("1667060034726-6b4c4c6eb385")   # 대나무 찻잔 받침
IMG_BAMBOO_CRAFT = _u("1556037867-bc64ed32b2af")     # 대나무 식기·공예
IMG_BAMBOO_GROVE = _u("1532920161727-344adb090f7f")  # 대숲(죽순 캐기)
IMG_HANOK2 = _u("1601721826401-c5e789be0be6")        # 한옥 단청 지붕
IMG_SUNSET2 = _u("1609602126473-2941dc2c58bc")       # 노을 스테이


PRODUCT_POOL: list[str] = [
    IMG_RICE, IMG_APPLE, IMG_PERSIMMON, IMG_TEA, IMG_TEA_CUP, IMG_CITRUS,
    IMG_FISH_DISH, IMG_SEAFOOD, IMG_SAUCE, IMG_JUICE, IMG_MATCHA,
    IMG_FISH_MARKET, IMG_NOODLE, IMG_PAPER_LETTER, IMG_LAMP, IMG_FAN,
]

LODGING_POOL: list[str] = [
    IMG_OCEAN_VIEW, IMG_LIVING, IMG_HANOK, IMG_TERRACE, IMG_CABIN,
    IMG_GLAMPING, IMG_BEACH_CONDO, IMG_HOTEL, IMG_POOLVILLA, IMG_FARM,
    IMG_GUESTHOUSE, IMG_ROOFTOP, IMG_PORT, IMG_BEACH_HOUSE, IMG_SUNSET_STAY,
    IMG_POOL,
]

EXPERIENCE_POOL: list[str] = [
    IMG_RICE_PADDY, IMG_BAMBOO_FOREST, IMG_COASTAL, IMG_SURF, IMG_SURF_LESSON,
    IMG_PADDLE, IMG_DIVING, IMG_BEACH, IMG_FIELD, IMG_HARBOR, IMG_CAMPING,
    IMG_FARM,
]


# --- 키워드 → 이미지 매칭 (제목·설명 기반, 우선순위 순서대로) ---
# (키워드 리스트, 이미지 URL)
_PRODUCT_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("천일염", "소금"), IMG_SALT),
    (("마늘",), IMG_GARLIC_BRAID),
    (("흑돼지", "등심", "삼겹", "한우", "갈비"), IMG_PORK),
    (("과메기",), IMG_DRIED_FISH),
    (("멸치",), IMG_FISH_MARKET),
    (("낙지", "오징어", "주꾸미"), IMG_OCTOPUS),
    (("바지락", "조개", "전복", "굴", "꼬막"), IMG_SEAFOOD),
    (("자반 고등어", "자반", "고등어"), IMG_MACKEREL),
    (("갈치", "가자미", "회", "생선"), IMG_FISH_DISH),
    (("멸치액젓", "액젓", "젓갈"), IMG_SAUCE),
    (("감귤", "한라봉", "오렌지", "유자"), IMG_CITRUS),
    (("사과", "배 "), IMG_APPLE),
    (("곶감", "감 "), IMG_PERSIMMON),
    (("녹차", "황차", "찻잎", "다도", "차밭"), IMG_TEA),
    (("녹차 가루", "가루", "분말"), IMG_MATCHA),
    (("쌀", "햅쌀", "도정"), IMG_RICE),
    (("잡곡", "검은콩", "콩 ", "현미", "보리"), IMG_BEANS),
    (("떡국", "떡", "쌀가루"), IMG_RICE_CAKE),
    (("죽순 김치", "김치", "장아찌"), IMG_KIMCHI),  # 채소·발효
    (("청자", "백자", "옹기", "다관", "도자기", "머그", "잔"),
     (IMG_POTTERY1, IMG_POTTERY2, IMG_POTTERY3, IMG_POTTERY4)),
    (("한지", "엽서", "봉투", "부채", "합죽선"), IMG_PAPER_LETTER),
    (("무드등", "등", "조명"), IMG_LAMP),
    (("도시락 통", "대나무 도시락"), IMG_BAMBOO_BOX),
    (("차 받침", "대나무 차"), IMG_BAMBOO_TRAY),
    (("대나무",), IMG_BAMBOO_CRAFT),
    (("사과즙", "주스", "즙"), IMG_JUICE),
]

_EXPERIENCE_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("서핑", "서퍼", "서프"), IMG_SURF_LESSON),
    (("패들보드", "sup", "SUP"), IMG_PADDLE),
    (("해녀", "다이빙", "스노클"), IMG_DIVING),
    (("출조", "어선", "어부", "고기잡이"), IMG_HARBOR),
    (("갯벌", "조개잡이", "보말"), IMG_BEACH),
    (("멸치잡이", "죽방렴"), IMG_HARBOR),
    (("과메기 손질", "과메기"), IMG_DRIED_FISH),
    (("낙지 손질", "낙지", "연포탕"), IMG_OCTOPUS),
    (("모내기", "들녘", "벼", "논"), IMG_RICE_PADDY),
    (("죽순 캐기", "대숲", "대나무 도시락"), IMG_BAMBOO_FOREST),
    (("도자기", "다관 빚기", "옹기 만들기", "백자 잔", "물레"),
     (IMG_POTTERY2, IMG_POTTERY3, IMG_POTTERY4, IMG_POTTERY1)),
    (("한지 무드등", "무드등 만들기"), IMG_LAMP),
    (("한지 합죽선", "합죽선"), IMG_FAN),
    (("바다부채길", "트레킹", "산책", "둘레길"), IMG_COASTAL),
    (("일몰", "노을"), IMG_SUNSET_STAY),
    (("양떼", "양 먹이", "목장"), IMG_FARM),
    (("오름", "한라산", "곶자왈"), IMG_FIELD),
    (("캠핑", "글램핑"), IMG_CAMPING),
    (("떡 만들기", "떡 클래스"), IMG_RICE_CAKE),
    (("두부", "콩 수확"), IMG_BEANS),
    (("사과따기", "사과 수확"), IMG_APPLE),
    (("곶감 매달기",), IMG_PERSIMMON),
    (("감귤 따기", "감귤청"), IMG_CITRUS),
    (("차밭", "다도", "찻잎"), IMG_TEA),
    (("황차 만들기",), IMG_TEA_CUP),
]

_LODGING_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("풀빌라", "수영장", "인피니티"), IMG_POOL),
    (("글램핑", "글램", "텐트"), IMG_GLAMPING),
    (("캠핑카", "트레일러", "캠핑"), IMG_CAMPERVAN),
    (("서핑", "서퍼", "서프"), IMG_BEACH),
    (("게스트하우스", "도미토리"), IMG_GUESTHOUSE),
    (("한옥", "별채", "정자"), IMG_HANOK),
    (("통나무", "산장", "산속", "흥정", "발왕"), IMG_MOUNTAIN_CABIN),
    (("바다", "해변", "오션", "해안", "바닷가"), IMG_OCEAN_VIEW),
    (("일몰", "노을", "선셋"), IMG_SUNSET_STAY),
    (("일출", "정동진"), IMG_HOTEL),
    (("호수", "산책로"), IMG_LIVING),
    (("옥탑", "다락", "루프", "rooftop", "옥상"), IMG_ROOFTOP),
    (("항구", "어부", "어시장"), IMG_PORT),
    (("숲", "곶자왈", "메밀"), IMG_FARM),
    (("케이블카", "스키"), IMG_MOUNTAIN_LODGE),
]


def _hash_key(key: str) -> int:
    h = 0
    for ch in key:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h


def _match_keywords(
    text: str, table: list[tuple[tuple[str, ...], str | tuple[str, ...]]]
) -> str | tuple[str, ...] | None:
    t = (text or "").lower()
    for keys, url in table:
        for k in keys:
            if k.lower() in t:
                return url
    return None


def _resolve(value: str | tuple[str, ...], key: str) -> str:
    """후보가 여러 장이면(예: 도자기 4종) key 해시로 결정적 분산 — 형제 상품이 서로 다른 사진."""
    if isinstance(value, tuple):
        return value[_hash_key(key) % len(value)]
    return value


def cover_image_for(*, category: str, kind: str, key: str, title: str = "") -> str:
    """제목 키워드로 의미 매칭 → 풀 폴백."""
    if kind == "lodging":
        table, pool = _LODGING_KEYWORDS, LODGING_POOL
    elif category == "experience":
        table, pool = _EXPERIENCE_KEYWORDS, EXPERIENCE_POOL
    else:
        table, pool = _PRODUCT_KEYWORDS, PRODUCT_POOL
    match = _match_keywords(title, table)
    if match is not None:
        return _resolve(match, key)
    return pool[_hash_key(key) % len(pool)]


# 시드 데이터의 손수 큐레이션 URL 중 깨진(404) 것들 — 키워드 매칭으로 폴백.
_BROKEN_SEED_URLS: frozenset[str] = frozenset(
    f"https://images.unsplash.com/photo-{pid}{_S}"
    for pid in (
        "1444930694458-01babe71870e",
        "1502780402662-acc01917189e",
        "1504382262782-aa9bc8d4cdb6",
        "1517305274093-1f9b3a8c1c41",
        "1518991669955-9c7e78ec80ae",
        "1547046832-0e76277f4e93",
        "1556228720-da4e85bcfe69",
        "1556909114-44e3e9399a2c",
        "1559489080-7c34de0b6c4c",
        "1559554498-7e4eea52d8b1",
        "1559738062-9f646c0ce833",
        "1561049501-31df1ee4d1e5",
        "1568568879316-92985ed4d11d",
        "1582719476417-b4a18ea4a9b0",
        "1582719478185-d3022aabf2bd",
        "1599909533045-5d3ec1ad8f1f",
        "1607113284917-d5e0b7e3d3ac",
        "1610530460358-dc7a7c4f7a04",
        "1610630440011-e8e83eafa55c",
        "1611080626919-7cf5a9dbab12",
        "1611171711912-b2d2c75dde6e",
        "1612869538502-6f5fa1812bf7",
        "1614075318598-c45f0a98c4cf",
        "1620912189770-0d22ae8c9c1e",
    )
)


def is_broken_seed_url(url: str | None) -> bool:
    if not url:
        return True
    return url in _BROKEN_SEED_URLS


def fix_url_if_broken(
    url: str | None,
    *,
    category: str,
    kind: str,
    key: str,
    title: str = "",
) -> str:
    """URL이 비었거나 깨진 시드 URL이면 키워드/풀로 폴백, 아니면 그대로."""
    if url and url not in _BROKEN_SEED_URLS:
        return url
    return cover_image_for(category=category, kind=kind, key=key, title=title)


def repair_broken_listing_images(session) -> int:
    """알려진 깨진 시드 URL만 키워드 매칭으로 교체."""
    rows = session.scalars(select(ListingRow)).all()
    n = 0
    for row in rows:
        if not row.cover_image_url:
            continue
        if row.cover_image_url not in _BROKEN_SEED_URLS:
            continue
        cat = getattr(row, "category", None) or ("lodging" if row.kind == "lodging" else "rural")
        new_url = cover_image_for(
            category=cat,
            kind=row.kind,
            key=row.id,
            title=row.title or "",
        )
        row.cover_image_url = new_url
        n += 1
    return n
