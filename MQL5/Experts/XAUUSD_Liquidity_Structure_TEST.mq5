//+------------------------------------------------------------------+
//| XAUUSD_Liquidity_Structure_TEST.mq5                              |
//| Research/backtest EA - live trading intentionally disabled.      |
//| Logic: H1 structure -> M5 liquidity sweep -> displacement/BOS    |
//| -> volume/flat filters -> liquidity-aware target.                |
//+------------------------------------------------------------------+
#property strict
#property version   "2.0"
#property description "XAUUSD M5 liquidity/structure backtest EA"

#include <Trade/Trade.mqh>

CTrade trade;

input ENUM_TIMEFRAMES InpEntryTF = PERIOD_M5;
input ENUM_TIMEFRAMES InpBiasTF  = PERIOD_H1;

input int    InpSwingLookback       = 3;
input int    InpLiquidityBars       = 36;
input int    InpATRPeriod           = 14;
input double InpMinATRImpulse       = 1.40;
input double InpMinBodyPct          = 0.65;
input double InpMinRR               = 2.00;
input double InpRiskPct             = 0.50;
input int    InpMaxBarsAfterSweep   = 4;
input int    InpCooldownBars        = 8;
input int    InpMaxSpreadPoints     = 80;

input bool   InpUseSessionFilter    = true;
input int    InpStartHourUTC        = 7;
input int    InpEndHourUTC          = 20;

input bool   InpUseVolumeFilter     = true;
input int    InpVolumeLookback      = 20;
input double InpVolumeFactor        = 1.10;

input bool   InpUseFlatFilter       = true;
input int    InpFlatBars            = 24;
input double InpFlatRangeATR        = 2.20;

input bool   InpUseLiquidityTarget  = true;
input double InpSL_ATR_Buffer       = 0.20;
input double InpMaxTargetRR         = 5.00;

input bool   InpDrawSignals         = true;
input bool   InpVerboseLog          = false;

int      g_atr = INVALID_HANDLE;
datetime g_lastBar = 0;
datetime g_lastEntryBar = 0;

struct SweepSignal
{
   bool     valid;
   bool     bullish;
   double   level;
   datetime sweepTime;
   int      shift;
};

double PointValue()
{
   return SymbolInfoDouble(_Symbol,SYMBOL_POINT);
}

bool IsTesterOnly()
{
   return (bool)MQLInfoInteger(MQL_TESTER);
}

bool NewBar()
{
   datetime t=iTime(_Symbol,InpEntryTF,0);
   if(t==0 || t==g_lastBar) return false;
   g_lastBar=t;
   return true;
}

double ATR(int shift)
{
   if(g_atr==INVALID_HANDLE) return 0.0;
   double b[];
   ArraySetAsSeries(b,true);
   if(CopyBuffer(g_atr,0,shift,1,b)!=1) return 0.0;
   return b[0];
}

bool GetOHLC(int shift,double &o,double &h,double &l,double &c)
{
   o=iOpen(_Symbol,InpEntryTF,shift);
   h=iHigh(_Symbol,InpEntryTF,shift);
   l=iLow(_Symbol,InpEntryTF,shift);
   c=iClose(_Symbol,InpEntryTF,shift);
   return o!=0.0 && h!=0.0 && l!=0.0 && c!=0.0;
}

bool InSession()
{
   if(!InpUseSessionFilter) return true;

   // Use the historical bar timestamp so the filter is deterministic
   // in Strategy Tester and does not depend on the local PC clock.
   datetime t=iTime(_Symbol,InpEntryTF,1);
   if(t==0) return false;

   MqlDateTime dt;
   TimeToStruct(t,dt);

   if(InpStartHourUTC<=InpEndHourUTC)
      return dt.hour>=InpStartHourUTC && dt.hour<InpEndHourUTC;

   return dt.hour>=InpStartHourUTC || dt.hour<InpEndHourUTC;
}

double AverageTickVolume(int startShift,int count)
{
   if(count<=0) return 0.0;

   double sum=0.0;
   int n=0;

   for(int i=startShift;i<startShift+count;i++)
   {
      long v=iVolume(_Symbol,InpEntryTF,i);
      if(v>0)
      {
         sum+=(double)v;
         n++;
      }
   }

   return n>0 ? sum/n : 0.0;
}

bool VolumeConfirmed(int shift)
{
   if(!InpUseVolumeFilter) return true;

   double base=AverageTickVolume(shift+1,InpVolumeLookback);
   double cur=(double)iVolume(_Symbol,InpEntryTF,shift);

   return base>0.0 && cur>=base*InpVolumeFactor;
}

double HighestHigh(int start,int count)
{
   double x=-DBL_MAX;

   for(int i=start;i<start+count;i++)
      x=MathMax(x,iHigh(_Symbol,InpEntryTF,i));

   return x;
}

double LowestLow(int start,int count)
{
   double x=DBL_MAX;

   for(int i=start;i<start+count;i++)
      x=MathMin(x,iLow(_Symbol,InpEntryTF,i));

   return x;
}

bool IsFlat()
{
   if(!InpUseFlatFilter) return false;

   double a=ATR(1);
   if(a<=0.0) return true;

   double hi=-DBL_MAX;
   double lo= DBL_MAX;

   for(int i=1;i<=InpFlatBars;i++)
   {
      hi=MathMax(hi,iHigh(_Symbol,InpEntryTF,i));
      lo=MathMin(lo,iLow(_Symbol,InpEntryTF,i));
   }

   return (hi-lo)<a*InpFlatRangeATR;
}

bool BullishBias()
{
   double h1=iHigh(_Symbol,InpBiasTF,1);
   double h2=iHigh(_Symbol,InpBiasTF,2);
   double l1=iLow(_Symbol,InpBiasTF,1);
   double l2=iLow(_Symbol,InpBiasTF,2);
   double c=iClose(_Symbol,InpBiasTF,1);

   return c>h2 && l1>=l2 && h1>=h2;
}

bool BearishBias()
{
   double h1=iHigh(_Symbol,InpBiasTF,1);
   double h2=iHigh(_Symbol,InpBiasTF,2);
   double l1=iLow(_Symbol,InpBiasTF,1);
   double l2=iLow(_Symbol,InpBiasTF,2);
   double c=iClose(_Symbol,InpBiasTF,1);

   return c<l2 && h1<=h2 && l1<=l2;
}

bool DetectSweepAtShift(int shift,SweepSignal &s)
{
   s.valid=false;
   s.shift=shift;

   double o,h,l,c;
   if(!GetOHLC(shift,o,h,l,c)) return false;

   double sellSide=HighestHigh(shift+1,InpLiquidityBars);
   double buySide =LowestLow(shift+1,InpLiquidityBars);

   // Sell-side sweep -> bullish setup.
   if(l<buySide && c>buySide)
   {
      s.valid=true;
      s.bullish=true;
      s.level=buySide;
      s.sweepTime=iTime(_Symbol,InpEntryTF,shift);
      return true;
   }

   // Buy-side sweep -> bearish setup.
   if(h>sellSide && c<sellSide)
   {
      s.valid=true;
      s.bullish=false;
      s.level=sellSide;
      s.sweepTime=iTime(_Symbol,InpEntryTF,shift);
      return true;
   }

   return false;
}

bool FindRecentSweep(SweepSignal &s)
{
   // Search the last N closed bars. The displacement bar must be
   // later than the sweep bar, preventing same-candle hindsight.
   for(int shift=2;shift<=InpMaxBarsAfterSweep+1;shift++)
   {
      if(DetectSweepAtShift(shift,s))
         return true;
   }

   return false;
}

bool DisplacementConfirmed(bool bullish,int shift)
{
   double o,h,l,c;
   if(!GetOHLC(shift,o,h,l,c)) return false;

   double range=h-l;
   if(range<=0.0) return false;

   double body=MathAbs(c-o);

   if(body/range<InpMinBodyPct)
      return false;

   double a=ATR(shift);
   if(a<=0.0 || range<a*InpMinATRImpulse)
      return false;

   if(bullish && c<=o) return false;
   if(!bullish && c>=o) return false;

   if(bullish)
      return c>HighestHigh(shift+1,InpSwingLookback);

   return c<LowestLow(shift+1,InpSwingLookback);
}

bool CooldownOK()
{
   if(g_lastEntryBar==0) return true;

   int shift=iBarShift(_Symbol,InpEntryTF,g_lastEntryBar,false);

   return shift<0 || shift>=InpCooldownBars;
}

bool HasOpenPosition()
{
   return PositionSelect(_Symbol);
}

double NormalizeVolume(double lots)
{
   double minLot=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maxLot=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);

   if(step<=0.0) return 0.0;

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

   if(tickSize<=0.0 || tickValue<=0.0 || distance<=0.0)
      return 0.0;

   double moneyPerLot=(distance/tickSize)*tickValue;

   if(moneyPerLot<=0.0)
      return 0.0;

   return NormalizeVolume(riskMoney/moneyPerLot);
}

bool SpreadOK()
{
   MqlTick t;

   if(!SymbolInfoTick(_Symbol,t))
      return false;

   double point=PointValue();

   if(point<=0.0)
      return false;

   double spread=(t.ask-t.bid)/point;

   return spread<=InpMaxSpreadPoints;
}

double TargetFromLiquidity(bool bullish,double entry,double risk)
{
   if(!InpUseLiquidityTarget)
      return bullish ? entry+risk*InpMinRR : entry-risk*InpMinRR;

   double liquidity=bullish
                    ? HighestHigh(2,InpLiquidityBars)
                    : LowestLow(2,InpLiquidityBars);

   double minTarget=bullish ? entry+risk*InpMinRR
                            : entry-risk*InpMinRR;

   double maxTarget=bullish ? entry+risk*InpMaxTargetRR
                            : entry-risk*InpMaxTargetRR;

   if(bullish)
   {
      if(liquidity<minTarget) return minTarget;
      return MathMin(liquidity,maxTarget);
   }

   if(liquidity>minTarget) return minTarget;
   return MathMax(liquidity,maxTarget);
}

void DrawMarker(string prefix,datetime t,double price,bool bullish)
{
   if(!InpDrawSignals) return;

   string name=prefix+"_"+IntegerToString((long)t);

   if(ObjectFind(0,name)>=0)
      return;

   ObjectCreate(0,name,OBJ_ARROW,0,t,price);
   ObjectSetInteger(0,name,OBJPROP_ARROWCODE,bullish ? 233 : 234);
   ObjectSetInteger(0,name,OBJPROP_WIDTH,1);
}

void DrawLevel(string prefix,datetime t,double price)
{
   if(!InpDrawSignals) return;

   string name=prefix+"_"+IntegerToString((long)t);

   if(ObjectFind(0,name)>=0)
      return;

   ObjectCreate(0,name,OBJ_HLINE,0,0,price);
   ObjectSetInteger(0,name,OBJPROP_WIDTH,1);
}

void TryEntry()
{
   // Explicit research boundary: no live trading path.
   if(!IsTesterOnly())
      return;

   if(!InSession() || !SpreadOK() || !CooldownOK())
      return;

   if(IsFlat() || HasOpenPosition())
      return;

   SweepSignal s;

   if(!FindRecentSweep(s))
      return;

   // The current closed bar is the confirmation bar.
   if(!VolumeConfirmed(1))
      return;

   bool bias=s.bullish ? BullishBias() : BearishBias();

   if(!bias)
      return;

   if(!DisplacementConfirmed(s.bullish,1))
      return;

   MqlTick tick;

   if(!SymbolInfoTick(_Symbol,tick))
      return;

   double entry=s.bullish ? tick.ask : tick.bid;
   double a=ATR(1);

   if(a<=0.0)
      return;

   double sl=s.bullish
             ? s.level-a*InpSL_ATR_Buffer
             : s.level+a*InpSL_ATR_Buffer;

   double risk=MathAbs(entry-sl);

   if(risk<=0.0)
      return;

   double tp=TargetFromLiquidity(s.bullish,entry,risk);

   double rr=MathAbs(tp-entry)/risk;

   if(rr<InpMinRR)
      return;

   double lots=LotsForRisk(entry,sl);

   if(lots<=0.0)
      return;

   bool ok=false;

   if(s.bullish)
      ok=trade.Buy(lots,_Symbol,entry,sl,tp,"LQ_SWEEP_BOS_BUY");
   else
      ok=trade.Sell(lots,_Symbol,entry,sl,tp,"LQ_SWEEP_BOS_SELL");

   if(ok)
   {
      g_lastEntryBar=iTime(_Symbol,InpEntryTF,1);

      DrawMarker("ENTRY",g_lastEntryBar,entry,s.bullish);
      DrawLevel("SL",g_lastEntryBar,sl);
      DrawLevel("TP",g_lastEntryBar,tp);

      if(InpVerboseLog)
      {
         PrintFormat(
            "ENTRY %s lots=%.2f entry=%.2f sl=%.2f tp=%.2f RR=%.2f sweepShift=%d",
            s.bullish ? "BUY" : "SELL",
            lots,entry,sl,tp,rr,s.shift
         );
      }
   }
   else if(InpVerboseLog)
   {
      PrintFormat(
         "ENTRY FAILED retcode=%u %s",
         trade.ResultRetcode(),
         trade.ResultRetcodeDescription()
      );
   }
}

int OnInit()
{
   if(_Symbol=="")
      return INIT_FAILED;

   g_atr=iATR(_Symbol,InpEntryTF,InpATRPeriod);

   if(g_atr==INVALID_HANDLE)
      return INIT_FAILED;

   trade.SetAsyncMode(false);

   if(!IsTesterOnly())
   {
      Print(
         "XAUUSD_Liquidity_Structure_TEST v2.0: "
         "live trading disabled; Strategy Tester only."
      );
   }

   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_atr!=INVALID_HANDLE)
      IndicatorRelease(g_atr);
}

void OnTick()
{
   if(!NewBar())
      return;

   TryEntry();
}
//+------------------------------------------------------------------+
