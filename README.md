# 電商平台 MVP（可直接啟動）

這次不是只給規劃，而是先幫你把「可運行的後端骨架」架起來，讓你可以直接 demo 核心流程：

- 會員註冊（含 LINE 綁定欄位）
- 賣家申請與保證金繳納
- 訂單流程：下單付款 → 賣家接單 → 出貨 → 物流收件 → 到店 → 買家取貨完成
- 通知中心（LINE/Email/站內通知以事件紀錄模擬）
- 基礎後台查詢（訂單、賣家申請、通知）
- 會員積分與銅銀金等級升級

## 快速啟動

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

啟動後：
- API: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`

## 測試

```bash
pytest -q
```

## 已實作 API（節錄）

- `POST /auth/register`
- `POST /seller/apply`
- `POST /seller/{application_id}/deposit`
- `POST /orders`
- `POST /orders/{order_id}/accept`
- `POST /orders/{order_id}/ship`
- `POST /orders/{order_id}/logistics-receive`
- `POST /orders/{order_id}/arrive`
- `POST /orders/{order_id}/pickup`
- `GET /admin/orders`
- `GET /admin/seller-applications`
- `GET /admin/notifications`

## 下一步建議（正式上線前）

1. 將記憶體資料改成 PostgreSQL + Redis。
2. 串接真實金流（如藍新/綠界/Stripe）與物流商 API。
3. 導入 OAuth（Google/Facebook/Apple）與 JWT。
4. 串接 LINE Official Account Messaging API 做真實通知推播。
5. 建置前端（買家端 / 賣家中心 / 後台）與客服即時聊天。
