from __future__ import annotations
import asyncio, os
from typing import Any
import httpx
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

app = FastAPI(title='せどりリサーチBot', version='2.0.0')
RAKUTEN_APP_ID=os.getenv('RAKUTEN_APP_ID','')
RAKUTEN_ACCESS_KEY=os.getenv('RAKUTEN_ACCESS_KEY','')
YAHOO_APP_ID=os.getenv('YAHOO_APP_ID','')

DEMO=[
 {'name':'Nintendo Switch 本体','purchase_price':29800,'sale_price':34980,'source':'デモデータ'},
 {'name':'ワイヤレスイヤホン','purchase_price':4980,'sale_price':7980,'source':'デモデータ'},
 {'name':'フィギュア','purchase_price':6800,'sale_price':10800,'source':'デモデータ'},
]

def calc(purchase,sale,fee_rate,shipping):
 fee=sale*fee_rate/100
 profit=sale-purchase-fee-shipping
 margin=profit/purchase*100 if purchase else 0
 return {'fee':round(fee),'profit':round(profit),'margin':round(margin,1)}

async def rakuten(keyword,hits=30):
 if not (RAKUTEN_APP_ID and RAKUTEN_ACCESS_KEY): return []
 url='https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701'
 params={'applicationId':RAKUTEN_APP_ID,'accessKey':RAKUTEN_ACCESS_KEY,'format':'json','keyword':keyword,'hits':min(hits,30),'sort':'+itemPrice','availability':1,'imageFlag':1}
 async with httpx.AsyncClient(timeout=10) as c:
  r=await c.get(url,params=params); r.raise_for_status(); data=r.json()
 out=[]
 for x in data.get('Items',[]):
  i=x.get('Item',x); imgs=i.get('mediumImageUrls') or []
  out.append({'name':i.get('itemName',''),'price':float(i.get('itemPrice') or 0),'url':i.get('itemUrl',''),'image':imgs[0].get('imageUrl','') if imgs else '','source':'楽天市場'})
 return out

async def yahoo(keyword,hits=30):
 if not YAHOO_APP_ID: return []
 url='https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch'
 params={'appid':YAHOO_APP_ID,'query':keyword,'results':min(hits,50),'sort':'-price','condition':'new','image_size':300}
 async with httpx.AsyncClient(timeout=10) as c:
  r=await c.get(url,params=params); r.raise_for_status(); data=r.json()
 out=[]
 for x in data.get('hits',[]):
  img=x.get('image') or {}
  out.append({'name':x.get('name',''),'price':float(x.get('price') or 0),'url':x.get('url',''),'image':img.get('medium',''),'source':'Yahoo!ショッピング'})
 return out

def candidates(buys,sells,min_profit,min_margin,fee_rate,shipping):
 prices=sorted(x['price'] for x in sells if x['price']>0)
 if not prices:return []
 ref=prices[min(len(prices)-1,max(0,int(len(prices)*.75)))]
 sale=min(sells,key=lambda x:abs(x['price']-ref))
 out=[]
 for b in buys:
  if b['price']<=0:continue
  c=calc(b['price'],ref,fee_rate,shipping)
  if c['profit']>=min_profit and c['margin']>=min_margin:
   out.append({'name':b['name'],'purchase_price':round(b['price']),'sale_price':round(ref),'fee':c['fee'],'shipping':round(shipping),'profit':c['profit'],'margin':c['margin'],'purchase_source':b['source'],'purchase_url':b['url'],'sale_source':sale['source'],'sale_url':sale['url'],'image':b.get('image') or sale.get('image') or '','note':'売価は検索結果から算出した参考値。同一JAN・型番・状態を確認してください。'})
 return sorted(out,key=lambda x:x['profit'],reverse=True)[:50]

@app.get('/',response_class=HTMLResponse)
async def home(): return HTML

@app.get('/api/search')
async def search(keyword:str=Query(...,min_length=1,max_length=80),min_profit:float=2000,min_margin:float=20,fee_rate:float=10,shipping:float=750):
 if not (RAKUTEN_APP_ID and YAHOO_APP_ID):
  items=[]
  for x in DEMO:
   c=calc(x['purchase_price'],x['sale_price'],fee_rate,shipping)
   if c['profit']>=min_profit and c['margin']>=min_margin:
    items.append({'name':x['name'],'purchase_price':x['purchase_price'],'sale_price':x['sale_price'],'fee':c['fee'],'shipping':shipping,'profit':c['profit'],'margin':c['margin'],'purchase_source':x['source'],'purchase_url':'https://www.rakuten.co.jp/','sale_source':x['source'],'sale_url':'https://www.rakuten.co.jp/','image':'','note':'現在はデモモード。APIキーを設定すると楽天/Yahooの検索結果を使います。'})
  return {'mode':'demo','count':len(items),'items':items}
 try:
  buys,sells=await asyncio.gather(rakuten(keyword),yahoo(keyword))
  items=candidates(buys,sells,min_profit,min_margin,fee_rate,shipping)
  return {'mode':'live','count':len(items),'items':items,'sources':{'purchase':'楽天市場API','sale_reference':'Yahoo!ショッピングAPI'}}
 except httpx.HTTPError as e:
  return {'mode':'error','count':0,'items':[],'error':f'API通信エラー: {type(e).__name__}'}

HTML=r'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#111"><title>せどりリサーチBot</title><style>*{box-sizing:border-box}body{margin:0;background:#f5f5f7;color:#111;font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,sans-serif}.wrap{max-width:760px;margin:auto;padding:22px 16px calc(40px + env(safe-area-inset-bottom))}h1{font-size:31px;margin:0 0 4px;font-weight:800}.sub{color:#777;margin:0 0 18px}.panel,.card{background:#fff;border:1px solid #ddd;border-radius:22px;padding:16px;box-shadow:0 3px 15px rgba(0,0,0,.05)}label{display:block;font-weight:700;font-size:14px;margin:2px 0 7px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}input{width:100%;font-size:18px;padding:16px;border:1px solid #d6d6d6;border-radius:15px;background:#fff}button{width:100%;border:0;border-radius:16px;background:#111;color:#fff;font-size:18px;font-weight:800;padding:17px;margin-top:14px}.status{color:#777;margin:18px 4px}.card{border-radius:19px;margin:12px 0}.card h3{font-size:17px;line-height:1.4;margin:0 0 12px}.numbers{display:grid;grid-template-columns:1fr 1fr;gap:8px}.num{background:#f7f7f8;border-radius:13px;padding:10px}.num small{display:block;color:#777;font-size:12px}.num b{font-size:18px}.profit{font-size:25px;font-weight:900;margin:12px 0 2px}.green{color:#087f3f}.muted{font-size:12px;color:#777;line-height:1.5}.links{display:flex;gap:8px;margin-top:12px}.links a{flex:1;text-align:center;text-decoration:none;background:#111;color:#fff;padding:11px;border-radius:12px;font-weight:700;font-size:13px}.badge{display:inline-block;background:#eee;padding:5px 8px;border-radius:999px;font-size:11px;margin-bottom:8px}@media(max-width:430px){h1{font-size:28px}.grid{gap:9px}}</style></head><body><div class="wrap"><h1>せどりリサーチBot</h1><p class="sub">iPhoneで利益商品をすばやくチェック</p><div class="panel"><label>キーワード</label><input id="keyword" placeholder="例：ゲーム、イヤホン、フィギュア"><div class="grid" style="margin-top:12px"><div><label>最低利益</label><input id="min_profit" type="number" value="2000"></div><div><label>最低利益率</label><input id="min_margin" type="number" value="20"></div></div><div class="grid" style="margin-top:12px"><div><label>販売手数料(%)</label><input id="fee_rate" type="number" value="10"></div><div><label>送料(円)</label><input id="shipping" type="number" value="750"></div></div><button onclick="searchProducts()">🔎 利益商品を探す</button></div><div id="status" class="status">条件を設定して検索してください</div><div id="results"></div></div><script>async function searchProducts(){const kw=document.getElementById('keyword').value.trim();if(!kw){alert('キーワードを入力してください');return}const s=document.getElementById('status'),r=document.getElementById('results');s.textContent='検索中…';r.innerHTML='';const q=new URLSearchParams({keyword:kw,min_profit:document.getElementById('min_profit').value,min_margin:document.getElementById('min_margin').value,fee_rate:document.getElementById('fee_rate').value,shipping:document.getElementById('shipping').value});try{const res=await fetch('/api/search?'+q);const d=await res.json();if(d.mode==='error'){s.textContent=d.error;return}s.textContent=`${d.count}件見つかりました（${d.mode==='live'?'実データ':'デモ'}）`;if(!d.items.length){r.innerHTML='<div class="card">条件に合う商品がありませんでした。</div>';return}r.innerHTML=d.items.map(x=>`<div class="card"><span class="badge">${esc(x.purchase_source)} → ${esc(x.sale_source)}</span><h3>${esc(x.name)}</h3><div class="numbers"><div class="num"><small>仕入れ価格</small><b>¥${num(x.purchase_price)}</b></div><div class="num"><small>参考売価</small><b>¥${num(x.sale_price)}</b></div><div class="num"><small>手数料</small><b>¥${num(x.fee)}</b></div><div class="num"><small>送料</small><b>¥${num(x.shipping)}</b></div></div><div class="profit green">利益 ¥${num(x.profit)}</div><div class="muted">利益率 ${x.margin}%</div><div class="links"><a href="${x.purchase_url}" target="_blank" rel="noopener">仕入れ先</a><a href="${x.sale_url}" target="_blank" rel="noopener">売価確認</a></div><p class="muted">${esc(x.note||'')}</p></div>`).join('')}catch(e){s.textContent='検索に失敗しました。時間を置いて再試行してください。'}}function num(v){return Number(v||0).toLocaleString('ja-JP')}function esc(s){return String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}</script></body></html>'''
