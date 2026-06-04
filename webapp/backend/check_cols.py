from dotenv import load_dotenv
load_dotenv()

from db.database import engine
from sqlalchemy import text

with engine.begin() as conn:
    result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='listings' ORDER BY ordinal_position"))
    cols = [r[0] for r in result]
    print("현재 listings 컬럼:", cols)

    missing = []
    if "variants_json" not in cols:
        missing.append("variants_json")
        conn.execute(text("ALTER TABLE listings ADD COLUMN variants_json TEXT"))
        print("variants_json 컬럼 추가 완료")
    if "details_json" not in cols:
        missing.append("details_json")
        conn.execute(text("ALTER TABLE listings ADD COLUMN details_json TEXT"))
        print("details_json 컬럼 추가 완료")
    if "guide_json" not in cols:
        missing.append("guide_json")
        conn.execute(text("ALTER TABLE listings ADD COLUMN guide_json TEXT"))
        print("guide_json 컬럼 추가 완료")

    if not missing:
        print("모든 컬럼이 이미 존재합니다.")
    else:
        print("추가된 컬럼:", missing)
