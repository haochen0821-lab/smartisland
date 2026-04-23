# Smart Island Hub｜智慧島嶼中心

離島韌性超商系統：把船班物流 × 中央氣象署資料 × 庫存 整合成「物資燈號」，
讓島民出門前就知道貨架狀態；註冊顧客可建立常買組合，一鍵下單 + QR 取貨。

## Project Info
- Port: 6200
- Domain: https://smartisland.dayspringmatsu.com
- 書籤名稱：Smart Island Hub｜智慧島嶼中心
- Docker container: smartisland
- Database: SQLite (instance/smartisland.db)
- Repo: https://github.com/haochen0821-lab/smartisland
- 範例店面：南竿介壽智慧島嶼超商（對應福澳港 / 台馬之星 + 合富快輪）

## Architecture
- Flask 3 + SQLAlchemy + Flask-Login + Flask-WTF + Pillow + qrcode
- 三個介面：
  - **顧客 PWA `/`**：天氣 + 船班 + 物資燈號 + 我的常買組合 + QR 取貨
  - **店內看板 `/board`**：全螢幕無登入，平板/電視顯示
  - **店家後台 `/admin`**：商品/庫存、船班、天氣、訂單、顧客、店家資訊、PWA 圖示
- 雙身份登入（Flask-Login user_id 用 `admin:N` / `customer:N` 區分）
- 燈號邏輯（`app/utils/signal.py`）：庫存 × 今日船班是否補給 × 是否天候警示
- 氣象資料：CWA 「鄉鎮天氣預報-連江縣 F-D0047-079」，需 `CWA_API_KEY`；無 key 時 fallback 模擬資料
- PWA：`/manifest.json` 動態產生，icon 在 `app/static/uploads/pwa/`

## Key Commands
- 啟動：`docker compose up -d --build`
- Logs：`docker logs smartisland -f`
- 進容器：`docker exec -it smartisland sh`

## Auto Git Workflow
完成任何變更後，自動執行：
```bash
git add -A
git commit -m "<簡潔訊息>"
git push origin main
```
GitHub Actions 會自動部署到 VPS（secrets: VPS_HOST / VPS_USER / VPS_SSH_KEY）。

## 開發注意事項
- **絕對不能刪除 `instance/smartisland.db`**；schema 變更用 migration / `ALTER TABLE`
- `.env` 不進版控
- 商品圖示用 emoji（不需要圖片）
- 顧客的 password_hash 與管理員分表（`customers` vs `admin_users`）
- 訂單 QR 內容格式：`SIH:{order_no}:{qr_token}`，店家後台改成「已取貨」會自動扣庫存
- service worker 不快取 `/admin`、`/api`、`/auth`、`/orders`

## PWA Icon 規則（硬性）
- 正方形、解析度至少 512x512、PNG
- 後台 `/admin/settings` 上傳，會自動產出 192/512/180/32 並 bump 版本號破快取

## 後台預設帳號
- 管理員：`admin / smartisland2026`（.env: `ADMIN_USERNAME` / `ADMIN_PASSWORD`）
- Demo 顧客：`chen / demo1234`（民宿主人，已備好「民宿早餐 6 人組」與一筆歷史訂單）
- 其他 demo 顧客：`aling / demo1234`（在地居民）、`mike / demo1234`（背包客）

## CWA API Key 設定
1. 到 https://opendata.cwa.gov.tw 註冊（免費）
2. 取得 API Key
3. 寫入 `/opt/smartisland/.env` 的 `CWA_API_KEY=...`
4. `docker compose up -d` 重啟容器
5. 後台「天氣」→「立刻更新」即可拉取
