//+------------------------------------------------------------------+
//| XAUUSD_Liquidity_Structure_TEST.mq5                              |
//| Research/backtest EA. Trading is hard-disabled outside Strategy  |
//| Tester. No broker/live execution path is implemented.            |
//+------------------------------------------------------------------+
#property strict
#property version   "1.0"
#property description "XAUUSD M5 structure + liquidity sweep + displacement research EA"

#include <Trade/Trade.mqh>

CTrade trade;

input ENUM_TIMEFRAMES InpEntryTF = PERIOD_M5;
input ENUM_TIMEFRAMES InpBiasTF  = PERIOD_H1;

input int    InpSwingLookback = 3;
input int    InpLiquidityBars = 36;
input int    InpATRPeriod = 14;
input double InpMinATRImpulse = 1.40;
input double InpMinBodyPct = 0.65;
input double InpMinRR = 2.0;
input double InpRiskPct = 0.50;
input int    InpMaxBarsAfterSweep = 4;
input int    InpMaxSpreadPoints = 80;
input int    InpCooldownBars = 8;

input bool   InpUseSessionFilter = true;
input int    InpStartHourUTC = 7;
input int    InpEndHourUTC = 20;

input bool   InpUseVolumeFilter = true;
input double InpVolumeFactor = 1.10;

input bool   InpUseFlatFilter = true;
input double InpFlatRangeATR = 2.20;
input int    InpFlatBars = 24;

input bool   InpDrawSignals = true;
input bool   InpVerboseLog = false;

int g_atr = INVALID_HANDLE;
datetime g_lastBar = 0;
datetime g_lastEntryBar = 0;

struct SweepSignal
{
   bool valid;
   bool bullish;
   double level;
   datetime sweepTime;
   int barsAgo;
};

double PointValue()
{
   return SymbolInfoDouble(_Symbol, SYMBOL_POINT);
}

bool IsTesterOnly()
{
   return (bool)MQLInfoInteger(MQL_TESTER);
}

bool NewBar()
{
   datetime t = iTime(_Symbol, InpEntryTF, 0);
   if(t == 0 || t == g_lastBar) return false;
   g_lastBar = t;
   return true;
}

double ATR(int shift)
{
   if(g_atr == INVALID_HANDLE) return 0.0;
   double b[];
   ArraySetAsSeries(b, true);
   if(CopyBuffer(g_atr, 0, shift, 1, b) != 1) return 0.0;
   return b[0];
}

bool GetOHLC(int shift,double &o,double &h,double &l,double &c)
{
   o=iOpen(_Symbol,InpEntryTF,shift);
   h=iHigh(_Symbol,InpEntryTF,shift);
   l=iLow(_Symbol,InpEntryTF,shift);
   c=iClose(_Symbol,InpEntryTF,shift);
   return (o!=0 && h!=0 && l!=0 && c!=0);
}

bool InSession()
{
   if(!InpUseSessionFilter) return true;
   MqlDateTime dt;
   TimeToStruct(TimeGMT(),dt);
   if(InpStartHourUTC <= InpEndHourUTC)
      return dt.hour >= InpStartHourUTC && dt.hour < InpEndHourUTC;
   return dt.hour >= InpStartHourUTC || dt.hour < InpEndHourUTC;
}

double AverageTickVolume(int startShift,int count)
{
   if(count <= 0) return 0;
   long sum=0;
   int n=0;
   for(int i=startShift;i<startShift+count;i++)
   {
      long v=(long)iVolume(_Symbol,InpEntryTF,i);
      if(v>0){sum+=v;n++;}
   }
   return n>0 ? (double)sum/n : 0;
}

bool VolumeConfirmed(int shift)
{
   if(!InpUseVolumeFilter) return true;
   double base=AverageTickVolume(shift+1,20);
   double cur=(double)iVolume(_Symbol,InpEntryTF,shift);
   return base>0 && cur >= base*InpVolumeFactor;
}

bool IsFlat()
{
   if(!InpUseFlatFilter) return false;
   double a=ATR(1);
   if(a<=0) return true;

   double hi=-DBL_MAX, lo=DBL_MAX;
   for(int i=1;i<=InpFlatBars;i++)
   {
      hi=MathMax(hi,iHigh(_Symbol,InpEntryTF,i));
      lo=MathMin(lo,iLow(_Symbol,InpEntryTF,i));
   }
   return (hi-lo) < a*InpFlatRangeATR;
}

bool BullishBias()
{
   double h1h1=iHigh(_Symbol,InpBiasTF,1);
   double h1h2=iHigh(_Symbol,InpBiasTF,2);
   double h1l1=iLow(_Symbol,InpBiasTF,1);
   double h1l2=iLow(_Symbol,InpBiasTF,2);
   double c=iClose(_Symbol,InpBiasTF,1);
   return c>h1h2 && h1l1>=h1l2;
}

bool BearishBias()
{
   double h1h1=iHigh(_Symbol,InpBiasTF,1);
   double h1h2=iHigh(_Symbol,InpBiasTF,2);
   double h1l1=iLow(_Symbol,InpBiasTF,1);
   double h1l2=iLow(_Symbol,InpBiasTF,2);
   double c=iClose(_Symbol,InpBiasTF,1);
   return c<h1l2 && h1h1<=h1h2;
}

double HighestHigh(int start,int count)
{
   double x=-DBL_MAX;
   for(int i=start;i<start+count;i++) x=MathMax(x,iHigh(_Symbol,InpEntryTF,i));
   return x;
}

double LowestLow(int start,int count)
{
   double x=DBL_MAX;
   for(int i=start;i<start+count;i++) x=MathMin(x,iLow(_Symbol,InpEntryTF,i));
   return x;
}

bool DetectSweep(SweepSignal &s)
{
   s.valid=false;
   double o,h,l,c;
   if(!GetOHLC(1,o,h,l,c)) return false;

   double buySide=LowestLow(2,InpLiquidityBars);
   double sellSide=HighestHigh(2,InpLiquidityBars);

   // Bullish liquidity sweep: low takes prior sell-side liquidity,
   // candle closes back above the level.
   if(l < buySide && c > buySide)
   {
      s.valid=true;
      s.bullish=true;
      s.level=buySide;
      s.sweepTime=iTime(_Symbol,InpEntryTF,1);
      s.barsAgo=1;
      return true;
   }

   // Bearish liquidity sweep: high takes prior buy-side liquidity,
   // candle closes back below the level.
   if(h > sellSide && c < sellSide)
   {
      s.valid=true;
      s.bullish=false;
      s.level=sellSide;
      s.sweepTime=iTime(_Symbol,InpEntryTF,1);
      s.barsAgo=1;
      return true;
   }
   return false;
}

bool DisplacementConfirmed(bool bullish)
{
   double o,h,l,c;
   if(!GetOHLC(1,o,h,l,c)) return false;

   double range=h-l;
   if(range<=0) return false;

   double body=MathAbs(c-o);
   if(body/range < InpMinBodyPct) return false;

   double a=ATR(1);
   if(a<=0 || range < a*InpMinATRImpulse) return false;

   if(bullish && c<=o) return false;
   if(!bullish && c>=o) return false;

   // Simple local structure confirmation.
   if(bullish)
      return c > HighestHigh(2,InpSwingLookback);
   return c < LowestLow(2,InpSwingLookback);
}

bool CooldownOK()
{
   if(g_lastEntryBar==0) return true;
   int shift=iBarShift(_Symbol,InpEntryTF,g_lastEntryBar,false);
   return shift >= InpCooldownBars || shift < 0;
}

double NormalizeVolume(double lots)
{
   double minLot=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maxLot=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(step<=0) return 0;
   lots=MathMax(minLot,MathMin(maxLot,lots));
   lots=MathFloor(lots/step)*step;
   return NormalizeDouble(lots,2);
}

double LotsForRisk(double entry,double sl)
{
   double balance=AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney=balance*InpRiskPct/100.0;
   double tickSize=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   double tickValue=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double distance=MathAbs(entry-sl);

   if(tickSize<=0 || tickValue<=0 || distance<=0) return 0;
   double moneyPerLot=(distance/tickSize)*tickValue;
   if(moneyPerLot<=0) return 0;

   return NormalizeVolume(riskMoney/moneyPerLot);
}

bool SpreadOK()
{
   MqlTick t;
   if(!SymbolInfoTick(_Symbol,t)) return false;
   double spread=(t.ask-t.bid)/PointValue();
   return spread <= InpMaxSpreadPoints;
}

void DrawMarker(string prefix,datetime t,double price,bool bullish)
{
   if(!InpDrawSignals) return;
   string name=prefix+"_"+IntegerToString((long)t);
   if(ObjectFind(0,name)>=0) return;
   ObjectCreate(0,name,OBJ_ARROW,0,t,price);
   ObjectSetInteger(0,name,OBJPROP_ARROWCODE,bullish?233:234);
   ObjectSetInteger(0,name,OBJPROP_WIDTH,1);
}

void TryEntry()
{
   // Hard safety boundary: this EA is intentionally backtest-only.
   if(!IsTesterOnly()) return;

   if(!InSession() || !SpreadOK() || !CooldownOK() || IsFlat()) return;

   SweepSignal s;
   if(!DetectSweep(s)) return;
   if(!VolumeConfirmed(1)) return;

   bool bias = s.bullish ? BullishBias() : BearishBias();
   if(!bias) return;

   if(!DisplacementConfirmed(s.bullish)) return;

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick)) return;

   double entry=s.bullish ? tick.ask : tick.bid;
   double a=ATR(1);
   if(a<=0) return;

   // Structural stop beyond sweep with small ATR buffer.
   double sl=s.bullish ? s.level-a*0.20 : s.level+a*0.20;
   double risk=MathAbs(entry-sl);
   if(risk<=0) return;

   double tp=s.bullish ? entry+risk*InpMinRR : entry-risk*InpMinRR;
   double lots=LotsForRisk(entry,sl);
   if(lots<=0) return;

   bool ok=false;
   if(s.bullish)
      ok=trade.Buy(lots,_Symbol,entry,sl,tp,"LQ_SWEEP_BUY");
   else
      ok=trade.Sell(lots,_Symbol,entry,sl,tp,"LQ_SWEEP_SELL");

   if(ok)
   {
      g_lastEntryBar=iTime(_Symbol,InpEntryTF,1);
      DrawMarker("ENTRY",g_lastEntryBar,entry,s.bullish);
      if(InpVerboseLog)
         PrintFormat("ENTRY %s lots=%.2f entry=%.2f sl=%.2f tp=%.2f",
                     s.bullish?"BUY":"SELL",lots,entry,sl,tp);
   }
   else if(InpVerboseLog)
   {
      PrintFormat("ENTRY FAILED retcode=%u %s",
                  trade.ResultRetcode(),trade.ResultRetcodeDescription());
   }
}

int OnInit()
{
   if(_Symbol=="") return INIT_FAILED;
   g_atr=iATR(_Symbol,InpEntryTF,InpATRPeriod);
   if(g_atr==INVALID_HANDLE) return INIT_FAILED;

   if(!IsTesterOnly())
      Print("XAUUSD_Liquidity_Structure_TEST: live trading disabled; use Strategy Tester.");

   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_atr!=INVALID_HANDLE) IndicatorRelease(g_atr);
}

void OnTick()
{
   if(!NewBar()) return;
   TryEntry();
}
//+------------------------------------------------------------------+
