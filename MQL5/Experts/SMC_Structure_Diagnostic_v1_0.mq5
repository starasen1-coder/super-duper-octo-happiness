//+------------------------------------------------------------------+
//| SMC_Structure_Diagnostic_v1_0.mq5                                |
//| Closed-bar H4 structure + M5 liquidity sweep/displacement        |
//| Diagnostic research prototype; not a profitability claim.        |
//+------------------------------------------------------------------+
#property strict
#property version   "1.00"
#property description "No-MA SMC prototype with closed-bar signals and setup-funnel diagnostics."

#include <Trade/Trade.mqh>

input double InpRiskPercent            = 0.25;
input double InpMaxDailyLossPercent     = 2.00;
input int    InpMaxSpreadPoints         = 100;
input int    InpLiquidityLookback       = 12;
input int    InpSwingDepth              = 2;
input int    InpH4StructureLookback     = 160;
input int    InpATRPeriod               = 14;
input double InpMinDisplacementATR      = 0.60;
input double InpStopBufferATR           = 0.15;
input double InpRiskReward              = 2.00;
input ulong  InpMagic                   = 27102701;
input int    InpDeviationPoints         = 20;
input bool   InpShowDiagnostics         = true;

CTrade   g_trade;
int      g_atrHandle = INVALID_HANDLE;
datetime g_lastM5Bar = 0;
datetime g_dayStart = 0;
double   g_dayStartEquity = 0.0;

long g_barsSeen = 0;
long g_biasPass = 0;
long g_sweepPass = 0;
long g_displacementPass = 0;
long g_entryAttempts = 0;
long g_entryAccepted = 0;
long g_entryRejected = 0;

struct SweepSetup
{
   bool   valid;
   bool   isBuy;
   double extreme;
   double atr;
};

//+------------------------------------------------------------------+
double TickSize()
{
   double size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(size <= 0.0)
      size = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   return size;
}
//+------------------------------------------------------------------+
double RoundDownToTick(const double price)
{
   double step = TickSize();
   return NormalizeDouble(MathFloor(price / step + 1e-8) * step, _Digits);
}
//+------------------------------------------------------------------+
double RoundUpToTick(const double price)
{
   double step = TickSize();
   return NormalizeDouble(MathCeil(price / step - 1e-8) * step, _Digits);
}
//+------------------------------------------------------------------+
bool ReadATR(double &atr)
{
   double buf[1];
   if(g_atrHandle == INVALID_HANDLE || CopyBuffer(g_atrHandle, 0, 1, 1, buf) != 1)
      return false;
   atr = buf[0];
   return (MathIsValidNumber(atr) && atr > 0.0);
}
//+------------------------------------------------------------------+
bool IsNewM5Bar()
{
   datetime t = iTime(_Symbol, PERIOD_M5, 0);
   if(t <= 0 || t == g_lastM5Bar)
      return false;
   g_lastM5Bar = t;
   return true;
}
//+------------------------------------------------------------------+
bool IsSwingHigh(const ENUM_TIMEFRAMES tf, const int shift, const int depth)
{
   double value = iHigh(_Symbol, tf, shift);
   if(value <= 0.0)
      return false;
   for(int k=1; k<=depth; ++k)
   {
      if(iHigh(_Symbol, tf, shift-k) >= value ||
         iHigh(_Symbol, tf, shift+k) > value)
         return false;
   }
   return true;
}
//+------------------------------------------------------------------+
bool IsSwingLow(const ENUM_TIMEFRAMES tf, const int shift, const int depth)
{
   double value = iLow(_Symbol, tf, shift);
   if(value <= 0.0)
      return false;
   for(int k=1; k<=depth; ++k)
   {
      if(iLow(_Symbol, tf, shift-k) <= value ||
         iLow(_Symbol, tf, shift+k) < value)
         return false;
   }
   return true;
}
//+------------------------------------------------------------------+
//| H4 direction from confirmed swing structure; no moving averages. |
//| Returns +1 bullish, -1 bearish, 0 unclear.                        |
//+------------------------------------------------------------------+
int GetH4Bias()
{
   double high1=0.0, high2=0.0, low1=0.0, low2=0.0;
   int foundHighs=0, foundLows=0;
   const int bars = Bars(_Symbol, PERIOD_H4);
   if(bars < InpSwingDepth*2 + 20)
      return 0;

   int maxShift = MathMin(InpH4StructureLookback, bars-InpSwingDepth-1);
   for(int shift=InpSwingDepth+1; shift<=maxShift; ++shift)
   {
      if(foundHighs < 2 && IsSwingHigh(PERIOD_H4, shift, InpSwingDepth))
      {
         if(foundHighs==0) high1=iHigh(_Symbol,PERIOD_H4,shift);
         else              high2=iHigh(_Symbol,PERIOD_H4,shift);
         foundHighs++;
      }
      if(foundLows < 2 && IsSwingLow(PERIOD_H4, shift, InpSwingDepth))
      {
         if(foundLows==0) low1=iLow(_Symbol,PERIOD_H4,shift);
         else             low2=iLow(_Symbol,PERIOD_H4,shift);
         foundLows++;
      }
      if(foundHighs>=2 && foundLows>=2)
         break;
   }
   if(foundHighs<2 || foundLows<2)
      return 0;

   const double lastClose = iClose(_Symbol, PERIOD_H4, 1);
   if(lastClose > high1)
      return 1;
   if(lastClose < low1)
      return -1;

   // The newest confirmed swing is at shift lower than the previous one.
   if(high1 > high2 && low1 > low2)
      return 1;
   if(high1 < high2 && low1 < low2)
      return -1;
   return 0;
}
//+------------------------------------------------------------------+
bool FindRecentLiquidityLevels(double &priorHigh, double &priorLow)
{
   priorHigh = -DBL_MAX;
   priorLow  = DBL_MAX;
   if(Bars(_Symbol, PERIOD_M5) < InpLiquidityLookback + 5)
      return false;

   // Exclude the sweep candle (shift 2) and the confirmation candle (shift 1).
   for(int shift=3; shift<3+InpLiquidityLookback; ++shift)
   {
      const double h=iHigh(_Symbol,PERIOD_M5,shift);
      const double l=iLow(_Symbol,PERIOD_M5,shift);
      if(h<=0.0 || l<=0.0)
         return false;
      if(h>priorHigh) priorHigh=h;
      if(l<priorLow)  priorLow=l;
   }
   return (priorHigh>priorLow && priorLow>0.0);
}
//+------------------------------------------------------------------+
//| Two-candle sequence: sweep on shift 2, displacement on shift 1.  |
//+------------------------------------------------------------------+
SweepSetup DetectSetup(const int bias)
{
   SweepSetup s;
   s.valid=false; s.isBuy=false; s.extreme=0.0; s.atr=0.0;

   double atr=0.0, priorHigh=0.0, priorLow=0.0;
   if(bias==0 || !ReadATR(atr) || !FindRecentLiquidityLevels(priorHigh,priorLow))
      return s;

   const double sweepHigh=iHigh(_Symbol,PERIOD_M5,2);
   const double sweepLow=iLow(_Symbol,PERIOD_M5,2);
   const double sweepClose=iClose(_Symbol,PERIOD_M5,2);
   const double dispOpen=iOpen(_Symbol,PERIOD_M5,1);
   const double dispClose=iClose(_Symbol,PERIOD_M5,1);
   const double dispHigh=iHigh(_Symbol,PERIOD_M5,1);
   const double dispLow=iLow(_Symbol,PERIOD_M5,1);
   if(sweepHigh<=0 || sweepLow<=0 || sweepClose<=0 ||
      dispOpen<=0 || dispClose<=0 || dispHigh<=0 || dispLow<=0)
      return s;

   const bool bullishSweep = (sweepLow < priorLow && sweepClose > priorLow);
   const bool bearishSweep = (sweepHigh > priorHigh && sweepClose < priorHigh);
   if((bias>0 && bullishSweep) || (bias<0 && bearishSweep))
   {
      g_sweepPass++;
      const double body=MathAbs(dispClose-dispOpen);
      const double range=dispHigh-dispLow;
      if(bias>0 && bullishSweep && dispClose>dispOpen &&
         dispClose>sweepHigh && body>=atr*InpMinDisplacementATR &&
         range>0.0 && (dispHigh-dispClose)/range<=0.30)
      {
         s.valid=true; s.isBuy=true; s.extreme=sweepLow; s.atr=atr;
         g_displacementPass++;
      }
      else if(bias<0 && bearishSweep && dispClose<dispOpen &&
              dispClose<sweepLow && body>=atr*InpMinDisplacementATR &&
              range>0.0 && (dispClose-dispLow)/range<=0.30)
      {
         s.valid=true; s.isBuy=false; s.extreme=sweepHigh; s.atr=atr;
         g_displacementPass++;
      }
   }
   return s;
}
//+------------------------------------------------------------------+
bool HasOurPosition()
{
   for(int i=PositionsTotal()-1; i>=0; --i)
   {
      const ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket))
         continue;
      if(PositionGetString(POSITION_SYMBOL)==_Symbol &&
         (ulong)PositionGetInteger(POSITION_MAGIC)==InpMagic)
         return true;
   }
   return false;
}
//+------------------------------------------------------------------+
double NormalizeVolume(const double requested)
{
   const double minVol=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   const double maxVol=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   const double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(step<=0.0 || minVol<=0.0 || maxVol<minVol || requested<minVol-1e-8)
      return 0.0;

   double v=MathFloor(MathMin(requested,maxVol)/step+1e-8)*step;
   int digits=0;
   double p=step;
   while(digits<8 && MathAbs(p-MathRound(p))>1e-8) { p*=10.0; digits++; }
   v=NormalizeDouble(v,digits);
   if(v<minVol || v>maxVol) return 0.0;
   return v;
}
//+------------------------------------------------------------------+
double VolumeByRisk(const bool isBuy, const double entry, const double sl)
{
   if(InpRiskPercent<=0.0) return 0.0;
   double pnl=0.0;
   const ENUM_ORDER_TYPE type=isBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   ResetLastError();
   if(!OrderCalcProfit(type,_Symbol,1.0,entry,sl,pnl))
   {
      Print("OrderCalcProfit failed; error=",GetLastError());
      return 0.0;
   }
   const double lossPerLot=MathAbs(pnl);
   if(lossPerLot<=0.0) return 0.0;
   const double riskCash=AccountInfoDouble(ACCOUNT_EQUITY)*InpRiskPercent/100.0;
   return NormalizeVolume(riskCash/lossPerLot);
}
//+------------------------------------------------------------------+
bool DailyRiskAllowed()
{
   if(InpMaxDailyLossPercent<=0.0 || g_dayStartEquity<=0.0)
      return true;
   const double change=AccountInfoDouble(ACCOUNT_EQUITY)-g_dayStartEquity;
   const double limit=g_dayStartEquity*InpMaxDailyLossPercent/100.0;
   if(change<=-limit)
   {
      PrintFormat("Daily equity guard: %.2f <= -%.2f; new entries blocked.",change,limit);
      return false;
   }
   return true;
}
//+------------------------------------------------------------------+
bool OpenSetup(const SweepSetup &s)
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick))
      return false;

   const double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   const double entry=s.isBuy ? tick.ask : tick.bid;
   const double buffer=s.atr*InpStopBufferATR;
   const double minStop=(double)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)*point;
   double sl=0.0, tp=0.0;
   if(s.isBuy)
   {
      sl=RoundDownToTick(MathMin(s.extreme-buffer,entry-MathMax(minStop,TickSize())));
      const double risk=entry-sl;
      if(risk<=0.0) return false;
      tp=RoundUpToTick(entry+risk*InpRiskReward);
   }
   else
   {
      sl=RoundUpToTick(MathMax(s.extreme+buffer,entry+MathMax(minStop,TickSize())));
      const double risk=sl-entry;
      if(risk<=0.0) return false;
      tp=RoundDownToTick(entry-risk*InpRiskReward);
   }

   const double volume=VolumeByRisk(s.isBuy,entry,sl);
   if(volume<=0.0)
   {
      Print("Setup skipped: risk-sized volume below broker minimum or invalid.");
      return false;
   }

   g_entryAttempts++;
   ResetLastError();
   bool sent=s.isBuy
      ? g_trade.Buy(volume,_Symbol,0.0,sl,tp,"SMC_Sweep_Displacement_BUY")
      : g_trade.Sell(volume,_Symbol,0.0,sl,tp,"SMC_Sweep_Displacement_SELL");
   const uint rc=g_trade.ResultRetcode();
   if(!sent || (rc!=TRADE_RETCODE_DONE && rc!=TRADE_RETCODE_DONE_PARTIAL && rc!=TRADE_RETCODE_PLACED))
   {
      g_entryRejected++;
      PrintFormat("Order rejected: %s vol=%.3f retcode=%u %s err=%d",
         s.isBuy?"BUY":"SELL",volume,rc,g_trade.ResultRetcodeDescription(),GetLastError());
      return false;
   }

   g_entryAccepted++;
   PrintFormat("Accepted %s vol=%.3f entry~%.*f SL=%.*f TP=%.*f",
      s.isBuy?"BUY":"SELL",volume,_Digits,entry,_Digits,sl,_Digits,tp);
   return true;
}
//+------------------------------------------------------------------+
void DrawDiagnostics(const int bias, const bool spreadOK)
{
   if(!InpShowDiagnostics) return;
   string biasText=(bias>0 ? "BUY bias" : (bias<0 ? "SELL bias" : "NO CLEAR BIAS"));
   Comment("SMC Structure Diagnostic v1.00\n",
           "Symbol: ",_Symbol," | TF entry: M5 | H4: ",biasText,"\n",
           "Spread: ",(spreadOK?"OK":"BLOCKED")," (",SymbolInfoInteger(_Symbol,SYMBOL_SPREAD)," pts)\n",
           "Bars evaluated: ",g_barsSeen,"\n",
           "H4 bias passed: ",g_biasPass,"\n",
           "Liquidity sweep passed: ",g_sweepPass,"\n",
           "Displacement passed: ",g_displacementPass,"\n",
           "Order attempts / accepted / rejected: ",g_entryAttempts," / ",g_entryAccepted," / ",g_entryRejected,"\n",
           "Daily equity change: ",DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY)-g_dayStartEquity,2),
           " | Risk/trade: ",DoubleToString(InpRiskPercent,2),"%");
}
//+------------------------------------------------------------------+
int OnInit()
{
   if(InpRiskPercent<=0.0 || InpRiskPercent>2.0 ||
      InpMaxDailyLossPercent<0.0 || InpMaxDailyLossPercent>100.0 ||
      InpMaxSpreadPoints<0 || InpLiquidityLookback<3 ||
      InpSwingDepth<1 || InpH4StructureLookback<20 ||
      InpATRPeriod<2 || InpMinDisplacementATR<=0.0 ||
      InpStopBufferATR<0.0 || InpRiskReward<=0.0)
   {
      Print("Invalid inputs. Review risk, lookbacks, ATR and RR.");
      return INIT_PARAMETERS_INCORRECT;
   }

   g_atrHandle=iATR(_Symbol,PERIOD_M5,InpATRPeriod);
   if(g_atrHandle==INVALID_HANDLE)
   {
      Print("Failed to create M5 ATR handle. Error=",GetLastError());
      return INIT_FAILED;
   }

   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(InpDeviationPoints);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   g_lastM5Bar=iTime(_Symbol,PERIOD_M5,0);
   g_dayStart=StringToTime(TimeToString(TimeCurrent(),TIME_DATE));
   g_dayStartEquity=AccountInfoDouble(ACCOUNT_EQUITY);

   Print("SMC Structure Diagnostic initialized. No MA signals. Entry: H4 structure + M5 sweep + displacement. Fixed RR exits; no trailing/BE.");
   return INIT_SUCCEEDED;
}
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Comment("");
   if(g_atrHandle!=INVALID_HANDLE) IndicatorRelease(g_atrHandle);
}
//+------------------------------------------------------------------+
void OnTick()
{
   const datetime now=TimeCurrent();
   const datetime today=StringToTime(TimeToString(now,TIME_DATE));
   if(today!=g_dayStart)
   {
      g_dayStart=today;
      g_dayStartEquity=AccountInfoDouble(ACCOUNT_EQUITY);
   }

   if(!IsNewM5Bar())
      return;

   g_barsSeen++;
   const long spread=SymbolInfoInteger(_Symbol,SYMBOL_SPREAD);
   const bool spreadOK=(spread>=0 && spread<=InpMaxSpreadPoints);
   const int bias=GetH4Bias();
   if(bias!=0) g_biasPass++;

   DrawDiagnostics(bias,spreadOK);
   if(!spreadOK || HasOurPosition() || !DailyRiskAllowed())
      return;

   const SweepSetup setup=DetectSetup(bias);
   if(!setup.valid)
   {
      DrawDiagnostics(bias,spreadOK);
      return;
   }

   OpenSetup(setup);
   DrawDiagnostics(bias,spreadOK);
}
//+------------------------------------------------------------------+
