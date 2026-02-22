import requests, numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Signal(Enum):
    STRONG_BUY="STRONG_BUY"; BUY="BUY"; WEAK_BUY="WEAK_BUY"
    SELL="SELL"; STRONG_SELL="STRONG_SELL"; WEAK_SELL="WEAK_SELL"; NO_TRADE="NO_TRADE"

@dataclass
class TFData:
    tf: str; signal: Signal; conf: float; rsi: float; adx: float; trend: str; price: float; age: int; max_age: int; weight: float

class ProAnalyzer:
    PAIRS={"EURUSD":"EURUSD=X","GBPUSD":"GBPUSD=X","USDJPY":"USDJPY=X","AUDUSD":"AUDUSD=X","USDCAD":"USDCAD=X","USDCHF":"USDCHF=X","NZDUSD":"NZDUSD=X","EURGBP":"EURGBP=X","EURJPY":"EURJPY=X","GBPJPY":"GBPJPY=X","AUDJPY":"AUDJPY=X","XAUUSD":"GC=F","XAGUSD":"SI=F","BTCUSD":"BTC-USD","ETHUSD":"ETH-USD","USOIL":"CL=F","UKOIL":"BZ=F"}
    TFS={"15m":{"i":"15m","r":"10d","w":1.5,"max_age":20},"1h":{"i":"1h","r":"30d","w":2.5,"max_age":90},"4h":{"i":"4h","r":"90d","w":3,"max_age":300}}
    
    def __init__(self):
        self.sess=requests.Session()
        self.sess.headers.update({"User-Agent":"Mozilla/5.0"})
    
    def get_live_price(self,pair):
        """Get real-time price from alternative source"""
        try:
            # Try CoinGecko for crypto (real-time)
            if "BTC" in pair or "ETH" in pair:
                cg_map={"BTCUSD":"bitcoin","ETHUSD":"ethereum"}
                if pair in cg_map:
                    r=requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={cg_map[pair]}&vs_currencies=usd",timeout=5)
                    if r.status_code==200:
                        return r.json()[cg_map[pair]]["usd"]
        except: pass
        return None
    
    def fetch(self,pair,tf):
        try:
            sym=self.PAIRS.get(pair,f"{pair}=X")
            cfg=self.TFS[tf]
            url=f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={cfg['i']}&range={cfg['r']}"
            r=self.sess.get(url,timeout=10)
            if r.status_code!=200: return None
            data=r.json()
            if not data.get("chart",{}).get("result"): return None
            
            res=data["chart"]["result"][0]
            qt=res["indicators"]["quote"][0]
            meta=res["meta"]
            ts=res["timestamp"]
            
            # Get price from multiple sources
            yahoo_live=meta.get("regularMarketPrice") or meta.get("postMarketPrice")
            alt_live=self.get_live_price(pair)
            
            clean=[{"t":ts[i],"o":qt["open"][i],"h":qt["high"][i],"l":qt["low"][i],"c":qt["close"][i],"v":qt["volume"][i] or 0} 
                   for i in range(len(ts)) if all(qt[k][i] is not None for k in ["close","high","low","open"])]
            
            if len(clean)<20: return None
            
            c=[d["c"] for d in clean]
            h=[d["h"] for d in clean]
            l=[d["l"] for d in clean]
            v=[d["v"] for d in clean]
            
            last_c=c[-1]
            # PRIORITY: Alternative live > Yahoo live > Last close
            curr=alt_live if alt_live else (yahoo_live if yahoo_live else last_c)
            
            last_t=datetime.fromtimestamp(clean[-1]["t"])
            age=int((datetime.now()-last_t).total_seconds()/60)
            
            # STRICT: Reject if too stale
            if age>cfg["max_age"]*3:
                logger.warning(f"{pair} {tf} TOO STALE: {age}min")
                return None
            
            is_live=curr!=last_c or age<5
            
            return{"c":c,"h":h,"l":l,"v":v,"price":curr,"last_c":last_c,"age":age,"max_age":cfg["max_age"],"is_live":is_live,"source":"alt" if alt_live else "yahoo"}
        except Exception as e:
            logger.error(f"Error {pair} {tf}: {e}")
            return None
    
    def ema(self,d,p):
        if len(d)<p: return [d[-1]]*len(d)
        m=2/(p+1); e=[sum(d[:p])/p]
        for x in d[p:]: e.append((x-e[-1])*m+e[-1])
        return [e[0]]*(p-1)+e
    
    def rsi(self,c,p=14):
        if len(c)<p+1: return 50
        d=np.diff(c); g=np.where(d>0,d,0); l=np.where(d<0,-d,0)
        ag,al=np.mean(g[:p]),np.mean(l[:p])
        for i in range(p,len(g)): ag=(ag*(p-1)+g[i])/p; al=(al*(p-1)+l[i])/p
        return 100-(100/(1+ag/al)) if al>0 else 100
    
    def macd(self,c):
        e12,e26=self.ema(c,12),self.ema(c,26)
        ml=[a-b for a,b in zip(e12[-len(e26):],e26)]
        sl=self.ema(ml,9)
        h=ml[-1]-sl[-1]; ph=(ml[-2]-sl[-2]) if len(ml)>1 else h
        st="bullish_expanding" if h>0 and h>ph else "bullish_contracting" if h>0 else "bearish_expanding" if h<0 and h<ph else "bearish_contracting"
        return h,st
    
    def adx(self,h,l,c,p=14):
        if len(h)<p+1: return 0
        tr,pdm,mdm=[],[],[]
        for i in range(1,len(h)):
            tr.append(max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1])))
            um,dm=h[i]-h[i-1],l[i-1]-l[i]
            pdm.append(um if um>dm and um>0 else 0)
            mdm.append(dm if dm>um and dm>0 else 0)
        atr=sum(tr[-p:])/p
        pdi=100*sum(pdm[-p:])/p/atr if atr>0 else 0
        mdi=100*sum(mdm[-p:])/p/atr if atr>0 else 0
        return 100*abs(pdi-mdi)/(pdi+mdi) if (pdi+mdi)>0 else 0
    
    def atr(self,h,l,c,p=14):
        if len(h)<p+1: return 0
        return sum([max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1])) for i in range(1,len(h))][-p:])/p
    
    def structure(self,h,l):
        if len(h)<20: return "undefined",0
        sh=[(i,h[i]) for i in range(2,len(h)-2) if h[i]>max(h[i-2:i]) and h[i]>max(h[i+1:i+3])]
        sl=[(i,l[i]) for i in range(2,len(l)-2) if l[i]<min(l[i-2:i]) and l[i]<min(l[i+1:i+3])]
        if len(sh)<2 or len(sl)<2: return "undefined",0
        hh,hl=(1 if sh[-1][1]>sh[-2][1] else -1),(1 if sl[-1][1]>sl[-2][1] else -1)
        if hh==1 and hl==1: return "bullish_structure",3
        elif hh==1 or hl==1: return "bullish_bias",1.5
        elif hh==-1 and hl==-1: return "bearish_structure",-3
        elif hh==-1 or hl==-1: return "bearish_bias",-1.5
        return "choppy",0
    
    def analyze_tf(self,d,tf):
        c,h,l,v=d["c"],d["h"],d["l"],d["v"]
        price=d["price"]
        
        ema9,ema21,ema50=self.ema(c,9)[-1],self.ema(c,21)[-1],self.ema(c,50)[-1] if len(c)>=50 else self.ema(c,21)[-1]
        rsi=self.rsi(c)
        macd_hist,macd_st=self.macd(c)
        adx=self.adx(h,l,c)
        struct,sstr=self.structure(h,l)
        atr=self.atr(h,l,c)
        
        # Trend
        if price>ema9>ema21>ema50: trend,esc="strong_uptrend",3
        elif price>ema9>ema21: trend,esc="uptrend",2
        elif price>ema9: trend,esc="weak_uptrend",1
        elif price<ema9<ema21<ema50: trend,esc="strong_downtrend",-3
        elif price<ema9<ema21: trend,esc="downtrend",-2
        elif price<ema9: trend,esc="weak_downtrend",-1
        else: trend,esc="ranging",0
        
        # Score
        score=0; reasons=[]
        
        # RSI with trend context
        if rsi<30:
            if "downtrend" in trend: score+=3; reasons.append(f"RSI oversold {rsi:.1f} in downtrend=potential bounce")
            else: score+=1; reasons.append(f"RSI oversold {rsi:.1f}")
        elif rsi<40: score+=0.5; reasons.append(f"RSI low {rsi:.1f}")
        elif rsi>70:
            if "uptrend" in trend: score-=3; reasons.append(f"RSI overbought {rsi:.1f} in uptrend=potential pullback")
            else: score-=1; reasons.append(f"RSI overbought {rsi:.1f}")
        elif rsi>60: score-=0.5; reasons.append(f"RSI high {rsi:.1f}")
        else: reasons.append(f"RSI {rsi:.1f}")
        
        # MACD
        if macd_hist>0 and "bullish" in macd_st:
            score+=2 if "expanding" in macd_st else 1
            reasons.append("MACD bullish"+(" expanding" if "expanding" in macd_st else ""))
        elif macd_hist<0 and "bearish" in macd_st:
            score-=2 if "expanding" in macd_st else 1
            reasons.append("MACD bearish"+(" expanding" if "expanding" in macd_st else ""))
        
        score+=esc; reasons.append(f"Trend: {trend}")
        score+=sstr; reasons.append(f"Structure: {struct}")
        reasons.append(f"ADX: {adx:.1f}")
        
        # Volatility check
        recent_vol=np.mean(v[-5:]) if len(v)>=5 else np.mean(v)
        avg_vol=np.mean(v[-20:]) if len(v)>=20 else np.mean(v)
        if avg_vol>0 and recent_vol/avg_vol>2: reasons.append("⚠ High volatility"); score*=0.8
        
        # Signal determination
        if score>=6 and adx>30: sig,conf=Signal.STRONG_BUY,min(85+score,98)
        elif score>=4: sig,conf=Signal.BUY,min(75+score,90)
        elif score>1 and adx>25: sig,conf=Signal.WEAK_BUY,60+score*3
        elif score<=-6 and adx>30: sig,conf=Signal.STRONG_SELL,min(85+abs(score),98)
        elif score<=-4: sig,conf=Signal.SELL,min(75+abs(score),90)
        elif score<-1 and adx>25: sig,conf=Signal.WEAK_SELL,60+abs(score)*3
        else: sig,conf=Signal.NO_TRADE,35+abs(score)*2
        
        if not d["is_live"]: conf*=0.85
        if d["age"]>d["max_age"]: conf*=0.7
        
        return TFData(tf,sig,conf,rsi,adx,trend,price,d["age"],d["max_age"],self.TFS[tf]["w"]),reasons,atr
    
    def aggregate(self,tf_results):
        if not tf_results: return Signal.NO_TRADE,0,{},["No data"]
        
        # Check HTF conflict
        htf=[t for t,r,a in tf_results if t.tf in ["4h","1d"]]
        if len(htf)>=2:
            bulls=sum(1 for t in htf if t.signal in [Signal.STRONG_BUY,Signal.BUY])
            bears=sum(1 for t in htf if t.signal in [Signal.STRONG_SELL,Signal.SELL])
            if bulls>0 and bears>0: return Signal.NO_TRADE,25,{"conflict":"HTF mismatch"},["⚠ Higher TFs conflict"]
        
        wbull=wbear=0; prices=[]; all_reas=[]
        for td,reas,atr in tf_results:
            prices.append(td.price)
            w=td.weight*(td.conf/100)
            all_reas.extend([f"[{td.tf}] {r}" for r in reas])
            if td.signal in [Signal.STRONG_BUY,Signal.BUY]: wbull+=w*(2 if td.signal==Signal.STRONG_BUY else 1)
            elif td.signal==Signal.WEAK_BUY: wbull+=w*0.5
            elif td.signal in [Signal.STRONG_SELL,Signal.SELL]: wbear+=w*(2 if td.signal==Signal.STRONG_SELL else 1)
            elif td.signal==Signal.WEAK_SELL: wbear+=w*0.5
        
        avg_price=sum(prices)/len(prices)
        net=wbull-wbear
        
        if wbull>wbear*1.5 and net>2:
            fs=Signal.STRONG_BUY if net>4 else Signal.BUY if net>2 else Signal.WEAK_BUY
            fc=min(85+net,98) if fs==Signal.STRONG_BUY else min(75+net,90)
        elif wbear>wbull*1.5 and net<-2:
            fs=Signal.STRONG_SELL if net<-4 else Signal.SELL if net<-2 else Signal.WEAK_SELL
            fc=min(85+abs(net),98) if fs==Signal.STRONG_SELL else min(75+abs(net),90)
        else: fs,fc=Signal.NO_TRADE,30+abs(net)*3
        
        # Price divergence check
        div=(max(prices)-min(prices))/avg_price*100 if avg_price>0 else 0
        if div>1.5: all_reas.append(f"⚠ Price divergence {div:.1f}%"); fc*=0.75
        
        return fs,min(fc,98),{"net":net,"div":div,"tfs":len(tf_results)},all_reas
    
    def levels(self,price,sig,atr,pair):
        dec=2 if price>10000 else 3 if price>1000 else 4 if price>100 else 5
        mult,rr=(2.0,2.5) if "BTC" in pair or "ETH" in pair else ((1.5,2.0) if "XAU" in pair or "XAG" in pair else (1.0,1.5))
        sl_dist=max(atr*mult,price*0.005)
        
        if sig in [Signal.STRONG_BUY,Signal.BUY,Signal.WEAK_BUY]:
            return{"entry":round(price,dec),"sl":round(price-sl_dist,dec),"tp":round(price+(sl_dist*rr),dec),"trail":round(price+(sl_dist*0.5),dec),"rr":rr,"atr":round(atr,dec)}
        elif sig in [Signal.STRONG_SELL,Signal.SELL,Signal.WEAK_SELL]:
            return{"entry":round(price,dec),"sl":round(price+sl_dist,dec),"tp":round(price-(sl_dist*rr),dec),"trail":round(price-(sl_dist*0.5),dec),"rr":rr,"atr":round(atr,dec)}
        return{"entry":round(price,dec),"sl":None,"tp":None,"trail":None,"rr":0,"atr":round(atr,dec)}
    
    def analyze(self,pair,tfs=None,primary="1h"):
        if tfs is None: tfs=["15m","1h","4h"]
        
        tf_results=[]
        for tf in tfs:
            d=self.fetch(pair,tf)
            if d:
                td,reas,atr=self.analyze_tf(d,tf)
                tf_results.append((td,reas,atr))
                logger.info(f"{pair} {tf}: {td.signal.value} RSI:{td.rsi:.1f} Price:{td.price:.2f} Age:{td.age}m Live:{d['is_live']}")
        
        if not tf_results:
            return{"signal":"NO_TRADE","confidence":0,"error":"No fresh data","pair":pair,"reasoning":["⚠ No valid market data"]}
        
        fs,conf,meta,reasons=self.aggregate(tf_results)
        
        prim=next((t for t,r,a in tf_results if t.tf==primary),tf_results[0][0])
        prim_atr=next((a for t,r,a in tf_results if t.tf==primary),tf_results[0][2])
        
        lv=self.levels(prim.price,fs,prim_atr,pair)
        
        if prim.age>prim.max_age*2:
            return{"signal":"NO_TRADE","confidence":0,"error":"Data too stale","pair":pair,"reasoning":["⚠ Data too old - try again later"]}
        
        return{
            "signal":fs.value,
            "confidence":round(conf,1),
            "pair":pair,
            "current_price":round(prim.price,2 if prim.price>10000 else 3),
            "entry_price":lv["entry"],
            "stop_loss":lv.get("sl"),
            "take_profit":lv.get("tp"),
            "trailing_activation":lv.get("trail"),
            "risk_reward":lv["rr"],
            "timestamp":datetime.now().strftime("%H:%M:%S"),
            "data":{"age_min":prim.age,"max_age":prim.max_age,"is_live":prim.age<10,"source":next((d.get('source','yahoo') for t,r,a in tf_results if t.tf==primary),'yahoo')},
            "indicators":{"rsi":round(prim.rsi,1),"adx":round(prim.adx,1),"atr":lv["atr"],"trend":prim.trend},
            "multi_tf":meta,
            "reasoning":reasons[:6]
        }

analyzer=ProAnalyzer()
