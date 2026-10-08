from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

app = FastAPI(title="せどりリサーチBot", version="3.0.0")

RAKUTEN_APP_ID = os.getenv("RAKUTEN_APP_ID", "").strip()
RAKUTEN_ACCESS_KEY = os.getenv("RAKUTEN_ACCESS_KEY", "").strip()
YAHOO_APP_ID = os.getenv("YAHOO_APP_ID", "").strip()


def calc(purchase: float, sale: float, fee_rate: float, shipping: float) -> dict[str, Any]:
    fee = sale * fee_rate / 100
    profit = sale - purchase - fee - shipping
    margin = profit / purchase * 100 if purchase > 0 else 0
    return {"fee": round(fee), "profit": round(profit), "margin": round(margin, 1)}


async def rakuten(keyword: str, hits: int = 30) -> list[dict[str, Any]]:
    if not RAKUTEN_APP_ID:
        raise RuntimeError("RAKUTEN_APP_ID が設定されていません")
    if not RAKUTEN_ACCESS_KEY:
        raise RuntimeError("RAKUTEN_ACCESS_KEY が設定されていません")

    url = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
    params = {
        "applicationId": RAKUTEN_APP_ID,
        "accessKey": RAKUTEN_ACCESS_KEY,
        "keyword": keyword,
        "hits": min(hits, 30),
        "page": 1,
        "formatVersion": 2,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    results = []
    for item in data.get("Items", []):
        if isinstance(item, dict) and "Item" in item:
            item = item["Item"]
        if not isinstance(item, dict):
            continue

        try:
            price = float(item.get("itemPrice") or 0)
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue

        image = ""
        images = item.get("mediumImageUrls") or []
        if images:
            first = images[0]
            if isinstance(first, dict):
                image = first.get("imageUrl") or first.get("url") or ""
            elif isinstance(first, str):
                image = first

        results.append({
            "name": item.get("itemName", ""),
            "price": price,
            "url": item.get("itemUrl", ""),
            "image": image,
            "source": "楽天市場",
        })

    return results


async def yahoo(keyword: str, hits: int = 30) -> list[dict[str, Any]]:
    if not YAHOO_APP_ID:
        raise RuntimeError("YAHOO_APP_ID が設定されていません")

    url = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"
    params = {
        "appid": YAHOO_APP_ID,
        "query": keyword,
        "results": min(hits, 50),
        "start": 1,
        "sort": "-price",
        "condition": "new",
        "image_size": 300,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    results = []
    for item in data.get("hits", []):
        try:
            price = float(item.get("price") or 0)
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue

        image_data = item.get("image") or {}
        image = ""
        if isinstance(image_data, dict):
            image = (
                image_data.get("medium")
                or image_data.get("small")
                or image_data.get("url")
                or ""
            )

        results.append({
            "name": item.get("name", ""),
            "price": price,
            "url": item.get("url", ""),
            "image": image,
            "source": "Yahoo!ショッピング",
        })

    return results


def candidates(
    buys: list[dict[str, Any]],
    sells: list[dict[str, Any]],
    min_profit: float,
    min_margin: float,
    fee_rate: float,
    shipping: float,
) -> list[dict[str, Any]]:
    if not buys or not sells:
        return []

    sell_prices = sorted(x["price"] for x in sells if x.get("price", 0) > 0)
    if not sell_prices:
        return []

    index = min(len(sell_prices) - 1, max(0, int(len(sell_prices) * 0.75)))
    reference_sale_price = sell_prices[index]
    sale_item = min(sells, key=lambda x: abs(x["price"] - reference_sale_price))

    results = []
    for buy in buys:
        purchase_price = buy.get("price", 0)
        if purchase_price <= 0:
            continue

        result = calc(purchase_price, reference_sale_price, fee_rate, shipping)

        if result["profit"] >= min_profit and result["margin"] >= min_margin:
            results.append({
                "name": buy.get("name", ""),
                "purchase_price": purchase_price,
                "sale_price": reference_sale_price,
                "purchase_source": "楽天市場",
                "purchase_url": buy.get("url", ""),
                "sale_source": "Yahoo!ショッピング",
                "sale_url": sale_item.get("url", ""),
                "image": buy.get("image") or sale_item.get("image") or "",
                "fee": result["fee"],
                "profit": result["profit"],
                "margin": result["margin"],
            })

    results.sort(key=lambda x: x["profit"], reverse=True)
    return results


@app.get("/api/search")
async def search(
    keyword: str = Query(...),
    min_profit: float = Query(1000),
    min_margin: float = Query(20),
    fee_rate: float = Query(10),
    shipping: float = Query(750),
):
    keyword = keyword.strip()

    if not keyword:
        return {"mode": "error", "count": 0, "items": [], "error": "キーワードを入力してください"}

    missing = []
    if not RAKUTEN_APP_ID:
        missing.append("RAKUTEN_APP_ID")
    if not RAKUTEN_ACCESS_KEY:
        missing.append("RAKUTEN_ACCESS_KEY")
    if not YAHOO_APP_ID:
        missing.append("YAHOO_APP_ID")

    if missing:
        return {
            "mode": "error",
            "count": 0,
            "items": [],
            "error": "Vercelの環境変数が不足しています: " + ", ".join(missing),
        }

    try:
        buys, sells = await asyncio.gather(rakuten(keyword), yahoo(keyword))
        items = candidates(buys, sells, min_profit, min_margin, fee_rate, shipping)

        return {
            "mode": "live",
            "count": len(items),
            "items": items,
            "sources": {
                "purchase": "楽天市場API",
                "sale_reference": "Yahoo!ショッピングAPI",
            },
        }

    except RuntimeError as e:
        return {"mode": "error", "count": 0, "items": [], "error": str(e)}
    except httpx.HTTPStatusError as e:
        return {
            "mode": "error",
            "count": 0,
            "items": [],
            "error": f"APIエラー: HTTP {e.response.status_code}",
        }
    except httpx.HTTPError:
        return {"mode": "error", "count": 0, "items": [], "error": "APIとの通信に失敗しました"}
    except Exception as e:
        return {
            "mode": "error",
            "count": 0,
            "items": [],
            "error": "検索処理でエラーが発生しました: " + type(e).__name__,
        }


HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>せどりリサーチBot</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#f5f5f5;color:#111;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.container{max-width:1000px;margin:auto;padding:20px}
.header{background:#111;color:white;padding:25px;border-radius:16px;margin-bottom:20px}
.header h1{margin:0 0 8px}.header p{margin:0;opacity:.75}
.search-box{background:white;padding:20px;border-radius:16px;margin-bottom:20px}
input{width:100%;padding:13px;border:1px solid #ddd;border-radius:10px;font-size:16px;margin-bottom:10px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
button{width:100%;border:0;background:#111;color:white;padding:14px;border-radius:10px;font-size:16px;cursor:pointer;margin-top:12px}
.status{margin:15px 0;font-weight:bold}
.card{background:white;border-radius:16px;padding:16px;margin-bottom:15px;display:grid;grid-template-columns:120px 1fr;gap:16px}
.card img{width:120px;height:120px;object-fit:contain;background:#fafafa;border-radius:10px}
.card h3{margin-top:0}.price{font-size:18px;font-weight:bold}.profit{font-size:22px;font-weight:bold}.meta{color:#666;font-size:13px;margin-top:5px}a{color:#111}
@media(max-width:700px){.grid{grid-template-columns:1fr 1fr}.card{grid-template-columns:90px 1fr}.card img{width:90px;height:90px}}
</style>
</head>
<body>
<div class="container">
<div class="header"><h1>せどりリサーチBot</h1><p>楽天市場 × Yahoo!ショッピング</p></div>
<div class="search-box">
<input id="keyword" placeholder="商品名を入力">
<div class="grid">
<input id="min_profit" type="number" value="1000" placeholder="最低利益">
<input id="min_margin" type="number" value="20" placeholder="最低利益率">
<input id="fee_rate" type="number" value="10" placeholder="販売手数料%">
<input id="shipping" type="number" value="750" placeholder="送料">
</div>
<button onclick="searchProducts()">検索する</button>
</div>
<div id="status" class="status"></div>
<div id="results"></div>
</div>
<script>
async function searchProducts(){
 const keyword=document.getElementById("keyword").value.trim();
 if(!keyword){alert("商品名を入力してください");return}
 const status=document.getElementById("status");
 const results=document.getElementById("results");
 status.textContent="楽天＋Yahoo!を検索中...";
 results.innerHTML="";
 const params=new URLSearchParams({
   keyword:keyword,
   min_profit:document.getElementById("min_profit").value,
   min_margin:document.getElementById("min_margin").value,
   fee_rate:document.getElementById("fee_rate").value,
   shipping:document.getElementById("shipping").value
 });
 try{
   const response=await fetch("/api/search?"+params);
   const data=await response.json();
   if(data.mode==="error"){status.textContent=data.error||"エラーが発生しました";return}
   status.textContent=`${data.count}件見つかりました`;
   if(!data.items.length){
     results.innerHTML='<div class="card">条件に合う商品がありませんでした。</div>';
     return;
   }
   results.innerHTML=data.items.map(item=>`
     <div class="card">
       ${item.image?`<img src="${item.image}" alt="">`:`<div></div>`}
       <div>
         <h3>${escapeHtml(item.name)}</h3>
         <div class="price">仕入れ：¥${item.purchase_price.toLocaleString()}</div>
         <div class="price">販売参考：¥${item.sale_price.toLocaleString()}</div>
         <div class="profit">利益：¥${item.profit.toLocaleString()}</div>
         <div>利益率：${item.margin}%</div>
         <div class="meta">仕入れ：<a href="${item.purchase_url}" target="_blank">楽天市場</a></div>
         <div class="meta">販売参考：<a href="${item.sale_url}" target="_blank">Yahoo!ショッピング</a></div>
       </div>
     </div>
   `).join("");
 }catch(error){status.textContent="検索に失敗しました。"}
}
function escapeHtml(text){
 return String(text).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");
}
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML
