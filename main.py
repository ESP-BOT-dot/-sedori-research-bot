from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="せどりリサーチBot")

DEMO = [
    {"name":"ワイヤレスイヤホン Pro", "buy":3980, "sell":7980, "source":"Demo", "url":"https://www.amazon.co.jp/"},
    {"name":"人気ゲームソフト", "buy":4500, "sell":8200, "source":"Demo", "url":"https://www.rakuten.co.jp/"},
    {"name":"フィギュア 限定版", "buy":5200, "sell":9800, "source":"Demo", "url":"https://shopping.yahoo.co.jp/"},
]

def calc(x):
    sell=x["sell"]; buy=x["buy"]
    fee=round(sell*0.10); shipping=750
    profit=sell-buy-fee-shipping
    margin=round(profit/sell*100,1) if sell else 0
    return {**x,"fee":fee,"shipping":shipping,"profit":profit,"margin":margin}

@app.get("/", response_class=HTMLResponse)
def home():
    return HTML

@app.get("/api/search")
def search(keyword:str="", min_profit:int=0, min_margin:float=0):
    items=[calc(x) for x in DEMO if not keyword or keyword.lower() in x["name"].lower()]
    items=[x for x in items if x["profit"]>=min_profit and x["margin"]>=min_margin]
    items.sort(key=lambda x:x["profit"], reverse=True)
    return {"items":items}

@app.get("/health")
def health():
    return {"status":"ok"}

HTML = '<!doctype html>\n<html lang="ja">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n<meta name="theme-color" content="#111">\n<title>せどりリサーチBot</title>\n<style>\n*{box-sizing:border-box}body{margin:0;background:#f5f5f7;color:#111;font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,sans-serif}\n.app{max-width:520px;margin:auto;padding:calc(16px + env(safe-area-inset-top)) 14px 25px}\nh1{font-size:25px;margin:0;font-weight:800}.sub{color:#777;font-size:13px;margin:5px 0 15px}\n.card,.item{background:#fff;border:1px solid #e5e5e8;border-radius:18px;padding:15px;margin-bottom:12px}\nlabel{display:block;font-size:12px;font-weight:700;color:#666;margin:0 0 6px}\ninput{width:100%;height:49px;border:1px solid #ddd;border-radius:12px;padding:0 13px;font-size:16px;background:#fff}\n.row{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:10px}\nbutton{width:100%;height:55px;border:0;border-radius:14px;background:#111;color:#fff;font-size:16px;font-weight:800;margin-top:12px}\nbutton:disabled{opacity:.55}.status{font-size:12px;color:#777;margin:10px 2px}\n.item .top{font-size:12px;color:#777}.name{font-size:17px;font-weight:800;line-height:1.35;margin:8px 0 12px}\n.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.metric{background:#f7f7f8;border-radius:12px;padding:10px}\n.metric small{display:block;color:#777;font-size:11px}.metric b{font-size:17px}\n.dark{background:#111;color:#fff}.dark small{color:#bbb}\n.advice{margin-top:10px;padding:11px;background:#f7f7f8;border-radius:12px;font-size:13px;line-height:1.5}\na{display:flex;align-items:center;justify-content:center;text-decoration:none;background:#111;color:#fff;border-radius:12px;height:46px;margin-top:10px;font-size:13px;font-weight:800}\n.empty{text-align:center;color:#777;padding:25px 5px}\n</style>\n</head>\n<body>\n<main class="app">\n<h1>せどりリサーチBot</h1>\n<div class="sub">iPhoneで利益商品をすばやくチェック</div>\n<section class="card">\n<label>キーワード</label>\n<input id="q" placeholder="例：ゲーム、イヤホン、フィギュア" inputmode="search">\n<div class="row">\n<div><label>最低利益</label><input id="p" type="number" value="2000" inputmode="numeric"></div>\n<div><label>最低利益率</label><input id="m" type="number" value="20" inputmode="decimal"></div>\n</div>\n<button id="btn">🔎 利益商品を探す</button>\n</section>\n<div class="status" id="s">条件を設定して検索してください</div>\n<section id="r"></section>\n</main>\n<script>\nconst yen=n=>n==null?"—":"¥"+Number(n).toLocaleString();\nconst esc=s=>String(s).replace(/[&<>"\']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",\'"\':"&quot;","\'":"&#39;"}[c]));\nconst b=document.getElementById("btn"),r=document.getElementById("r"),s=document.getElementById("s");\nasync function go(){\n b.disabled=true;b.textContent="検索中…";r.innerHTML="";s.textContent="商品をチェックしています";\n try{\n  const q=encodeURIComponent(document.getElementById("q").value);\n  const p=document.getElementById("p").value||0,m=document.getElementById("m").value||0;\n  const res=await fetch(`/api/search?keyword=${q}&min_profit=${p}&min_margin=${m}`);\n  const d=await res.json();\n  s.textContent=`候補 ${d.items.length}件`;\n  if(!d.items.length){r.innerHTML=\'<div class="card empty">条件に合う商品がありません。<br>利益条件を少し下げてみてください。</div>\';return}\n  r.innerHTML=d.items.map((x,i)=>`<article class="item">\n   <div class="top">#${i+1}\u3000${esc(x.source)}</div>\n   <div class="name">${esc(x.name)}</div>\n   <div class="grid">\n    <div class="metric"><small>仕入れ価格</small><b>${yen(x.buy)}</b></div>\n    <div class="metric"><small>販売価格</small><b>${yen(x.sell)}</b></div>\n    <div class="metric dark"><small>想定利益</small><b>${yen(x.profit)}</b></div>\n    <div class="metric"><small>利益率</small><b>${x.margin}%</b></div>\n   </div>\n   <div class="advice">💡 <b>販売アドバイス</b><br>${x.profit>=3000?"利益額が大きめ。相場と売れ行きを確認して出品候補に。":"回転率と相場を確認して出品価格を決めるのがおすすめ。"}</div>\n   <a href="${esc(x.url)}" target="_blank" rel="noopener">仕入れページを開く ↗</a>\n  </article>`).join("");\n }catch(e){s.textContent="エラー";r.innerHTML=\'<div class="card empty">サーバーが起動していない可能性があります。</div>\'}\n finally{b.disabled=false;b.textContent="🔎 利益商品を探す"}\n}\nb.onclick=go;document.getElementById("q").onkeydown=e=>{if(e.key==="Enter")go()};\n</script>\n</body>\n</html>'

