"""輕量遷移：把舊版本 DB 補上新欄位。在 seed 之前呼叫，失敗（欄位已存在）就略過。"""
from sqlalchemy import text
from app import db


def ensure_columns():
    stmts = [
        # Product 新增 photo
        "ALTER TABLE products ADD COLUMN photo VARCHAR(256) DEFAULT ''",
    ]
    with db.engine.connect() as conn:
        for s in stmts:
            try:
                conn.execute(text(s))
                conn.commit()
            except Exception:
                pass
