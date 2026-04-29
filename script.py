from pathlib import Path
import textwrap, json, os

backend = Path('output/macro-gold-app/backend.py')
backend.write_text(textwrap.dedent('''
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import os, httpx

app = FastAPI(title="Macro Gold Proxy")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GOLDAPI_KEY = os.getenv("GOLDAPI_KEY", "")
FRED_KEY = os.getenv("FRED_KEY", "")

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/api/market")
async def market():
    headers = {"x-access-token": GOLDAPI_KEY, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=15) as client:
        xau = await client.get("https://www.goldapi.io/api/XAU/USD", headers=headers)
        xag = await client.get("https://www.goldapi.io/api/XAG/USD", headers=headers)
        xpt = await client.get("https://www.goldapi.io/api/XPT/USD", headers=headers)
    return {
        "xau": xau.json(),
        "silver": xag.json(),
        "platinum": xpt.json(),
    }

@app.get("/api/macro")
async def macro():
    async with httpx.AsyncClient(timeout=15) as client:
        dgs10 = await client.get(f"https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&api_key={FRED_KEY}&file_type=json&sort_order=desc&limit=1")
        fedfunds = await client.get(f"https://api.stlouisfed.org/fred/series/observations?series_id=FEDFUNDS&api_key={FRED_KEY}&file_type=json&sort_order=desc&limit=1")
    return {"dgs10": dgs10.json(), "fedfunds": fedfunds.json()}
'''), encoding='utf-8')

req = Path('output/macro-gold-app/requirements.txt')
req.write_text('fastapi\nuvicorn[standard]\nhttpx\n', encoding='utf-8')

html_path = Path('output/macro-gold-app/macro-gold-production-preconfigured.html')
html = html_path.read_text(encoding='utf-8')
# add backend url input and change fetch logic for proxy usage
html = html.replace('<label><span class="meta">FRED API key</span><input id="fredKey" placeholder="Sua chave FRED" value="9c23f1e44f44094de3cbd76fee2b2179"></label>', '<label><span class="meta">Backend URL</span><input id="backendUrl" placeholder="http://127.0.0.1:8000" value="http://127.0.0.1:8000"></label><label><span class="meta">FRED API key</span><input id="fredKey" placeholder="Sua chave FRED" value="9c23f1e44f44094de3cbd76fee2b2179"></label>')
html = html.replace("const app={provider:'GoldAPI.io',xauApiKey:'goldapi-cca4b104bcd32367752dd0318da79ee6-io',fredKey:'9c23f1e44f44094de3cbd76fee2b2179',customBaseUrl:'',liveRefresh:10000,macroRefresh:60000,customMap:{xau:'price',silver:'silver',platinum:'platinum',copper:'copper',dxy:'dxy',bcom:'bcom'},alerts:[],sourceState:{xau:'demo fallback',fred:'demo fallback'},assets:{XAUUSD:{price:3428.6,prevClose:3384.0,history:[]},DXY:{price:101.78,prevClose:102.41,history:[]},US10Y:{price:4.181,prevClose:4.259,history:[]},BCOM:{price:109.4,prevClose:108.0,history:[]},Silver:{price:35.10,prevClose:34.31,history:[]},Copper:{price:4.70,prevClose:4.58,history:[]},Platinum:{price:1011.8,prevClose:1005.7,history:[]},Fed:{price:4.625,prevClose:4.75,history:[]}}};", "const app={provider:'GoldAPI.io',xauApiKey:'goldapi-cca4b104bcd32367752dd0318da79ee6-io',fredKey:'9c23f1e44f44094de3cbd76fee2b2179',backendUrl:'http://127.0.0.1:8000',customBaseUrl:'',liveRefresh:10000,macroRefresh:60000,customMap:{xau:'price',silver:'silver',platinum:'platinum',copper:'copper',dxy:'dxy',bcom:'bcom'},alerts:[],sourceState:{xau:'demo fallback',fred:'demo fallback'},assets:{XAUUSD:{price:3428.6,prevClose:3384.0,history:[]},DXY:{price:101.78,prevClose:102.41,history:[]},US10Y:{price:4.181,prevClose:4.259,history:[]},BCOM:{price:109.4,prevClose:108.0,history:[]},Silver:{price:35.10,prevClose:34.31,history:[]},Copper:{price:4.70,prevClose:4.58,history:[]},Platinum:{price:1011.8,prevClose:1005.7,history:[]},Fed:{price:4.625,prevClose:4.75,history:[]}}};")
html = html.replace("async function fetchJson(url,options={}){const res=await fetch(url,options);if(!res.ok)throw new Error(`HTTP ${res.status}`);return res.json()}", "async function fetchJson(url,options={}){const res=await fetch(url,options);if(!res.ok)throw new Error(`HTTP ${res.status}`);return res.json()}\n  async function fetchViaBackend(path){return fetchJson(`${app.backendUrl}${path}`)}")
# replace refreshMarketReal body with backend calls
start = html.find("async function refreshMarketReal(){")
end = html.find("async function refreshMacroReal(){")
new_fn = '''async function refreshMarketReal(){\n    try{\n      const data=await fetchViaBackend('/api/market');\n      if(Number.isFinite(Number(data?.xau?.price)))app.assets.XAUUSD.price=Number(data.xau.price);\n      if(Number.isFinite(Number(data?.silver?.price)))app.assets.Silver.price=Number(data.silver.price);\n      if(Number.isFinite(Number(data?.platinum?.price)))app.assets.Platinum.price=Number(data.platinum.price);\n      app.sourceState.xau='backend live';\n      Object.values(app.assets).forEach(v=>pushHistory(v,v.price));\n    }catch(e){app.sourceState.xau='demo fallback'}\n  }\n\n  '''
html = html[:start] + new_fn + html[end:]
# replace refreshMacroReal with backend calls
start = html.find("async function refreshMacroReal(){")
end = html.find("function computeState(){")
new_fn2 = '''async function refreshMacroReal(){\n    try{\n      const data=await fetchViaBackend('/api/macro');\n      const yv=Number(data?.dgs10?.observations?.[0]?.value),fv=Number(data?.fedfunds?.observations?.[0]?.value);\n      if(!Number.isNaN(yv))app.assets.US10Y.price=yv;\n      if(!Number.isNaN(fv))app.assets.Fed.price=fv;\n      app.sourceState.fred='backend live';\n    }catch(e){app.sourceState.fred='demo fallback'}\n  }\n\n  '''
html = html[:start] + new_fn2 + html[end:]
# wire backendUrl field in applyConnectors
html = html.replace("app.customBaseUrl=document.getElementById('customBaseUrl').value.trim();", "app.customBaseUrl=document.getElementById('customBaseUrl').value.trim();app.backendUrl=document.getElementById('backendUrl').value.trim()||app.backendUrl;")
html_path.write_text(html, encoding='utf-8')
print(backend, req, html_path)