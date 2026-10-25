//+------------------------------------------------------------------+
//| SMC_Trend_Follower_Final_v1_1.mq5                                |
//| Corrected execution, closed-bar signals, per-tick trailing        |
//+------------------------------------------------------------------+
#property strict
#property version   "1.10"
#property description "Corrected trend/pullback EA. Not a full SMC implementation."

#include <Trade/Trade.mqh>

input double InpLot                  = 0.10;
input int    InpFastMAPeriod          = 50;
input int    InpSlowMAPeriod          = 200;
input double InpRiskReward            = 2.0;
input int    InpATRPeriod              = 14;
input double InpATRMultiplierSL       = 2.5;
input int    InpMaxSpreadPoints        = 100;
input ulong  InpMagic                  = 123456;
input int    InpDeviationPoints        = 20;

input bool   InpUseTrailingStop        = true;
input double InpTrailingStartPips      = 50.0;
input double InpTrailingDistancePips   = 25.0;

input bool   InpUseRetraceFilter       = true;
input bool   InpUseH1LevelFilter       = false;
input int    InpH1Lookback             = 20;
input double InpH1MinDistancePips      = 30.0;
input bool   InpUseFVG                 = false;

int      g_fastMA = INVALID_HANDLE;
int      g_slowMA = INVALID_HANDLE;
int      g_atr    = INVALID_HANDLE;
CTrade   g_trade;
datetime g_lastBarTime = 0;

//+------------------------------------------------------------------+
double PipSize()
{
   const double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(_Digits == 3 || _Digits == 5)
      return point * 10.0;
   return point;
}
//+------------------------------------------------------------------+
bool ReadIndicatorValue(const int handle, const int shift, double &value)
{
   double buffer[1];
   if(handle == INVALID_HANDLE || CopyBuffer(handle, 0, shift, 1, buffer) != 1)
      return false;
   value = buffer[0];
   return MathIsValidNumber(value) && value > 0.0;
}
//+------------------------------------------------------------------+
bool IsNewBar()
{
   datetime t = iTime(_Symbol, PERIOD_M15, 0);
   if(t <= 0)
      return false;
   if(t == g_lastBarTime)
      return false;
   g_lastBarTime = t;
   return true;
}
//+------------------------------------------------------------------+
bool HasOurPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         (ulong)PositionGetInteger(POSITION_MAGIC) == InpMagic)
         return true;
   }
   return false;
}
//+------------------------------------------------------------------+
double NormalizeVolume(double requested)
{
   const double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   const double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   const double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0 || vmin <= 0.0 || vmax < vmin)
      return 0.0;

   double volume = MathMax(vmin, MathMin(vmax, requested));
   volume = MathFloor(volume / step + 1e-8) * step;

   int digits = 0;
   double s = step;
   while(digits < 8 && MathAbs(s - MathRound(s)) > 1e-8)
   {
      s *= 10.0;
      digits++;
   }
   volume = NormalizeDouble(volume, digits);
   if(volume < vmin || volume > vmax)
      return 0.0;
   return volume;
}
//+------------------------------------------------------------------+
bool SpreadAllowed()
{
   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   return (spread >= 0 && spread <= InpMaxSpreadPoints);
}
//+------------------------------------------------------------------+
bool BuildStops(const bool isBuy, const double entry, const double atr,
                double &sl, double &tp)
{
   if(atr <= 0.0 || InpATRMultiplierSL <= 0.0 || InpRiskReward <= 0.0)
      return false;

   const double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   const double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   const long stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   const double minDistance = MathMax((double)stopsLevel * point, tickSize);

   double distance = MathMax(atr * InpATRMultiplierSL, minDistance);
   if(isBuy)
   {
      sl = entry - distance;
      tp = entry + distance * InpRiskReward;
   }
   else
   {
      sl = entry + distance;
      tp = entry - distance * InpRiskReward;
   }

   double step = (tickSize > 0.0 ? tickSize : point);
   sl = NormalizeDouble(MathRound(sl / step) * step, _Digits);
   tp = NormalizeDouble(MathRound(tp / step) * step, _Digits);

   if(isBuy && (sl >= entry || tp <= entry))
      return false;
   if(!isBuy && (sl <= entry || tp >= entry))
      return false;
   return true;
}
//+------------------------------------------------------------------+
//| Signal from completed M15 candle (shift 1), not the live candle. |
//|  1 = buy, -1 = sell, 0 = no signal.                               |
//+------------------------------------------------------------------+
int GetSignal()
{
   double fast, slow, atr;
   if(!ReadIndicatorValue(g_fastMA, 1, fast) ||
      !ReadIndicatorValue(g_slowMA, 1, slow) ||
      !ReadIndicatorValue(g_atr, 1, atr))
      return 0;

   const double close1 = iClose(_Symbol, PERIOD_M15, 1);
   if(close1 <= 0.0)
      return 0;

   if(fast > slow)
   {
      if(InpUseRetraceFilter && close1 >= fast)
         return 0;
      return 1;
   }
   if(fast < slow)
   {
      if(InpUseRetraceFilter && close1 <= fast)
         return 0;
      return -1;
   }
   return 0;
}
//+------------------------------------------------------------------+
void ManageTrailingStops()
{
   if(!InpUseTrailingStop)
      return;

   const double pip = PipSize();
   const double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   const double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   const double trailStart = InpTrailingStartPips * pip;
   const double trailDistance = InpTrailingDistancePips * pip;
   if(trailStart <= 0.0 || trailDistance <= 0.0)
      return;

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
      return;

   for(int i = PositionsTotal() - 1; i >= 0; --i)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol ||
         (ulong)PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;

      const bool isBuy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      const double entry = PositionGetDouble(POSITION_PRICE_OPEN);
      const double oldSL = PositionGetDouble(POSITION_SL);
      const double tp = PositionGetDouble(POSITION_TP);
      const double current = isBuy ? tick.bid : tick.ask;
      const double profitDistance = isBuy ? current - entry : entry - current;
      if(profitDistance < trailStart)
         continue;

      double newSL = isBuy ? current - trailDistance : current + trailDistance;
      const long stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
      const double minDistance = MathMax((double)stopsLevel * point, tickSize);
      if(isBuy)
      {
         newSL = MathMin(newSL, tick.bid - minDistance);
         if(oldSL > 0.0 && newSL <= oldSL + tickSize)
            continue;
         if(newSL >= tick.bid)
            continue;
      }
      else
      {
         newSL = MathMax(newSL, tick.ask + minDistance);
         if(oldSL > 0.0 && newSL >= oldSL - tickSize)
            continue;
         if(newSL <= tick.ask)
            continue;
      }

      const double step = (tickSize > 0.0 ? tickSize : point);
      newSL = NormalizeDouble(MathRound(newSL / step) * step, _Digits);
      ResetLastError();
      if(!g_trade.PositionModify(ticket, newSL, tp))
         PrintFormat("Trailing modify failed. ticket=%I64u retcode=%u (%s), error=%d",
                     ticket, g_trade.ResultRetcode(),
                     g_trade.ResultRetcodeDescription(), GetLastError());
   }
}
//+------------------------------------------------------------------+
bool OpenTrade(const int signal)
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
      return false;

   double atr;
   if(!ReadIndicatorValue(g_atr, 1, atr))
   {
      Print("No valid closed-bar ATR; trade skipped.");
      return false;
   }

   const bool isBuy = (signal > 0);
   const double entry = isBuy ? tick.ask : tick.bid;
   double sl = 0.0, tp = 0.0;
   if(!BuildStops(isBuy, entry, atr, sl, tp))
   {
      Print("Could not calculate valid SL/TP; trade skipped.");
      return false;
   }

   const double volume = NormalizeVolume(InpLot);
   if(volume <= 0.0)
   {
      Print("Invalid volume for symbol: ", InpLot);
      return false;
   }

   ResetLastError();
   bool sent = false;
   if(isBuy)
      sent = g_trade.Buy(volume, _Symbol, 0.0, sl, tp, "SMC_TF_Buy");
   else
      sent = g_trade.Sell(volume, _Symbol, 0.0, sl, tp, "SMC_TF_Sell");

   const uint rc = g_trade.ResultRetcode();
   if(!sent || (rc != TRADE_RETCODE_DONE &&
                rc != TRADE_RETCODE_DONE_PARTIAL &&
                rc != TRADE_RETCODE_PLACED))
   {
      PrintFormat("Order failed. side=%s volume=%.4f retcode=%u (%s), error=%d",
                  isBuy ? "BUY" : "SELL", volume, rc,
                  g_trade.ResultRetcodeDescription(), GetLastError());
      return false;
   }

   PrintFormat("%s request accepted. volume=%.4f entry~%.*f SL=%.*f TP=%.*f",
               isBuy ? "BUY" : "SELL", volume, _Digits, entry,
               _Digits, sl, _Digits, tp);
   return true;
}
//+------------------------------------------------------------------+
int OnInit()
{
   if(InpLot <= 0.0 || InpFastMAPeriod <= 0 ||
      InpSlowMAPeriod <= InpFastMAPeriod ||
      InpATRPeriod <= 0 || InpATRMultiplierSL <= 0.0 ||
      InpRiskReward <= 0.0 || InpMaxSpreadPoints < 0)
   {
      Print("Invalid inputs. Check lot, periods, ATR multiplier, RR and spread.");
      return INIT_PARAMETERS_INCORRECT;
   }

   g_fastMA = iMA(_Symbol, PERIOD_M15, InpFastMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   g_slowMA = iMA(_Symbol, PERIOD_M15, InpSlowMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   g_atr = iATR(_Symbol, PERIOD_M15, InpATRPeriod);

   if(g_fastMA == INVALID_HANDLE || g_slowMA == INVALID_HANDLE ||
      g_atr == INVALID_HANDLE)
   {
      Print("Failed to create indicator handles. Error=", GetLastError());
      return INIT_FAILED;
   }

   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(InpDeviationPoints);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   g_lastBarTime = iTime(_Symbol, PERIOD_M15, 0);

   Print("SMC_Trend_Follower_Final_v1_1 initialized on ", _Symbol,
         ". Signals are trend/pullback based; BOS/OB/FVG logic is not implemented.");
   return INIT_SUCCEEDED;
}
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_fastMA != INVALID_HANDLE) IndicatorRelease(g_fastMA);
   if(g_slowMA != INVALID_HANDLE) IndicatorRelease(g_slowMA);
   if(g_atr != INVALID_HANDLE) IndicatorRelease(g_atr);
}
//+------------------------------------------------------------------+
void OnTick()
{
   // Manage existing positions on every tick, independently of new-bar entries.
   ManageTrailingStops();

   // New entries are evaluated only once per new M15 bar.
   if(!IsNewBar())
      return;

   if(!SpreadAllowed())
   {
      Print("Entry skipped: spread exceeds limit. Current=",
            SymbolInfoInteger(_Symbol, SYMBOL_SPREAD),
            " max=", InpMaxSpreadPoints, " points.");
      return;
   }

   if(HasOurPosition())
      return;

   const int signal = GetSignal();
   if(signal == 0)
      return;

   OpenTrade(signal);
}
//+------------------------------------------------------------------+
