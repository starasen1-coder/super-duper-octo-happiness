//+------------------------------------------------------------------+
//| XAUUSD_Liquidity_Diagnostic_v1.mq5                               |
//| Educational chart diagnostics only. NO order submission.         |
//| Structure -> liquidity sweep -> impulse -> OB -> retest.         |
//+------------------------------------------------------------------+
#property strict
#property version   "1.00"
#property description "Diagnostic-only SMC/price-action analyzer. Never sends trade requests."

input group "Timeframes"
input ENUM_TIMEFRAMES InpEntryTF      = PERIOD_M5;
input ENUM_TIMEFRAMES InpStructureTF  = PERIOD_H1;

input group "Structure"
input int    InpSwingLookback         = 120;
input int    InpPivotStrength         = 2;
input double InpMinSwingGapPoints     = 30;

input group "Impulse / volatility"
input int    InpATRPeriod              = 14;
input double InpImpulseATR             = 1.40;
input double InpMinBodyRatio           = 0.65;
input double InpCloseExtreme           = 0.20;
input double InpMinEfficiency          = 0.35;
input double InpMinATRRatio            = 0.90;
input int    InpEfficiencyBars         = 8;

input group "Liquidity / OB"
input int    InpSweepLookback          = 12;
input double InpSweepBufferATR         = 0.05;
input int    InpOBSearchBars           = 5;
input double InpRetestToleranceATR     = 0.20;
input int    InpSetupExpiryBars        = 12;

input group "Display"
input bool   InpDrawObjects            = true;
input bool   InpLogEveryRejection      = true;
input int    InpPanelCorner            = 0;

int      g_atrHandle = INVALID_HANDLE;
datetime g_lastEntryBar = 0;
datetime g_lastStructureBar = 0;
datetime g_setupBar = 0;
int      g_bias = 0;
int      g_previousBias = 0;
int      g_setupDirection = 0;
int      g_setupAge = 0;
bool     g_setupActive = false;
double   g_obHigh = 0.0;
double   g_obLow = 0.0;
double   g_sweepExtreme = 0.0;
string   g_status = "INITIALIZING";
string   g_prefix = "XAU_DIAG_";

//+------------------------------------------------------------------+
int OnInit()
{
   g_atrHandle = iATR(_Symbol, InpEntryTF, InpATRPeriod);
   if(g_atrHandle == INVALID_HANDLE)
   {
      PrintFormat("INIT FAILED: ATR handle error=%d", GetLastError());
      return INIT_FAILED;
   }

   if(InpPivotStrength < 1 || InpSwingLookback < 20 ||
      InpEfficiencyBars < 2 || InpOBSearchBars < 2)
   {
      Print("INIT FAILED: invalid diagnostic parameters.");
      return INIT_PARAMETERS_INCORRECT;
   }

   g_lastEntryBar = iTime(_Symbol, InpEntryTF, 0);
   g_lastStructureBar = iTime(_Symbol, InpStructureTF, 0);
   g_status = "WAITING FOR CLOSED BARS";
   UpdatePanel();
   Print("DIAGNOSTIC STARTED: chart analysis only; no trade functions are present.");
   return INIT_SUCCEEDED;
}
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_atrHandle != INVALID_HANDLE)
      IndicatorRelease(g_atrHandle);
   ObjectsDeleteAll(0, g_prefix);
   Comment("");
}
//+------------------------------------------------------------------+
double GetATR(const int shift)
{
   double values[];
   ArraySetAsSeries(values, true);
   if(CopyBuffer(g_atrHandle, 0, shift, 1, values) != 1)
      return 0.0;
   return values[0];
}
//+------------------------------------------------------------------+
double BarRange(const ENUM_TIMEFRAMES tf, const int shift)
{
   return iHigh(_Symbol, tf, shift) - iLow(_Symbol, tf, shift);
}
//+------------------------------------------------------------------+
double BodyRatio(const ENUM_TIMEFRAMES tf, const int shift)
{
   double range = BarRange(tf, shift);
   if(range <= 0.0) return 0.0;
   return MathAbs(iClose(_Symbol, tf, shift) - iOpen(_Symbol, tf, shift)) / range;
}
//+------------------------------------------------------------------+
//| Find a confirmed pivot. Shift starts at strength+1 to avoid      |
//| using the still-forming candle and unconfirmed right-side bars.   |
//+------------------------------------------------------------------+
bool FindPivot(const ENUM_TIMEFRAMES tf, const bool wantHigh,
               const int startShift, const int lookback,
               const int occurrence, double &price, datetime &stamp)
{
   int found = 0;
   int strength = MathMax(1, InpPivotStrength);
   int lastShift = MathMin(startShift + lookback, Bars(_Symbol, tf) - strength - 1);

   for(int s = MathMax(startShift, strength + 1); s <= lastShift; s++)
   {
      double candidate = wantHigh ? iHigh(_Symbol, tf, s) : iLow(_Symbol, tf, s);
      bool pivot = true;

      for(int k = 1; k <= strength; k++)
      {
         if(wantHigh)
         {
            if(candidate <= iHigh(_Symbol, tf, s-k) ||
               candidate <= iHigh(_Symbol, tf, s+k)) { pivot = false; break; }
         }
         else
         {
            if(candidate >= iLow(_Symbol, tf, s-k) ||
               candidate >= iLow(_Symbol, tf, s+k)) { pivot = false; break; }
         }
      }

      if(pivot)
      {
         found++;
         if(found == occurrence)
         {
            price = candidate;
            stamp = iTime(_Symbol, tf, s);
            return true;
         }
      }
   }
   return false;
}
//+------------------------------------------------------------------+
int ReadStructureBias(double &lastHigh, double &lastLow)
{
   double h1=0,h2=0,l1=0,l2=0;
   datetime th1=0,th2=0,tl1=0,tl2=0;
   if(!FindPivot(InpStructureTF,true,InpPivotStrength+1,InpSwingLookback,1,h1,th1) ||
      !FindPivot(InpStructureTF,true,InpPivotStrength+1,InpSwingLookback,2,h2,th2) ||
      !FindPivot(InpStructureTF,false,InpPivotStrength+1,InpSwingLookback,1,l1,tl1) ||
      !FindPivot(InpStructureTF,false,InpPivotStrength+1,InpSwingLookback,2,l2,tl2))
      return 0;

   lastHigh = h1;
   lastLow = l1;
   double gap = InpMinSwingGapPoints * _Point;

   if(h1 > h2 + gap && l1 > l2 + gap) return 1;
   if(h1 < h2 - gap && l1 < l2 - gap) return -1;
   return 0;
}
//+------------------------------------------------------------------+
double Efficiency(const int bars)
{
   double first = iClose(_Symbol, InpEntryTF, bars);
   double last = iClose(_Symbol, InpEntryTF, 1);
   double path = 0.0;
   for(int s=1; s<=bars; s++) path += BarRange(InpEntryTF,s);
   if(path <= 0.0) return 0.0;
   return MathAbs(last-first)/path;
}
//+------------------------------------------------------------------+
bool IsFlatMarket(string &reason)
{
   double atrNow = GetATR(1);
   double sum = 0.0;
   int count = 0;
   for(int s=2; s<=21; s++)
   {
      double a = GetATR(s);
      if(a > 0.0) { sum += a; count++; }
   }
   if(atrNow <= 0.0 || count < 10)
   {
      reason = "NO DATA: ATR/history not ready";
      return true;
   }
   double average = sum/count;
   if(atrNow < average*InpMinATRRatio)
   {
      reason = StringFormat("FLAT: ATR %.5f below average %.5f x %.2f",
                            atrNow,average,InpMinATRRatio);
      return true;
   }
   double efficiency = Efficiency(InpEfficiencyBars);
   if(efficiency < InpMinEfficiency)
   {
      reason = StringFormat("FLAT: efficiency %.3f below %.3f",
                            efficiency,InpMinEfficiency);
      return true;
   }
   reason = "VOLATILITY + EFFICIENCY PASSED";
   return false;
}
//+------------------------------------------------------------------+
int DetectSweep(double &extreme, string &reason)
{
   double atr = GetATR(1);
   if(atr <= 0.0) { reason="NO SWEEP: ATR unavailable"; return 0; }

   int hi = iHighest(_Symbol,InpEntryTF,MODE_HIGH,InpSweepLookback,2);
   int lo = iLowest(_Symbol,InpEntryTF,MODE_LOW,InpSweepLookback,2);
   if(hi < 0 || lo < 0) { reason="NO SWEEP: insufficient bars"; return 0; }

   double oldHigh = iHigh(_Symbol,InpEntryTF,hi);
   double oldLow = iLow(_Symbol,InpEntryTF,lo);
   double high = iHigh(_Symbol,InpEntryTF,1);
   double low = iLow(_Symbol,InpEntryTF,1);
   double close = iClose(_Symbol,InpEntryTF,1);
   double buffer = atr*InpSweepBufferATR;

   if(high > oldHigh+buffer && close < oldHigh)
   {
      extreme=high; reason=StringFormat("BEARISH LIQUIDITY SWEEP %.3f",high);
      return -1;
   }
   if(low < oldLow-buffer && close > oldLow)
   {
      extreme=low; reason=StringFormat("BULLISH LIQUIDITY SWEEP %.3f",low);
      return 1;
   }
   reason="NO TRADE: no confirmed liquidity sweep";
   return 0;
}
//+------------------------------------------------------------------+
bool ConfirmImpulse(const int direction, string &reason)
{
   double atr=GetATR(1);
   double range=BarRange(InpEntryTF,1);
   if(atr<=0.0 || range < atr*InpImpulseATR)
   {
      reason=StringFormat("REJECT: impulse range %.3f < ATR x %.2f",
                          range,InpImpulseATR);
      return false;
   }
   double body=BodyRatio(InpEntryTF,1);
   if(body < InpMinBodyRatio)
   {
      reason=StringFormat("REJECT: body ratio %.2f < %.2f",body,InpMinBodyRatio);
      return false;
   }

   double o=iOpen(_Symbol,InpEntryTF,1);
   double h=iHigh(_Symbol,InpEntryTF,1);
   double l=iLow(_Symbol,InpEntryTF,1);
   double c=iClose(_Symbol,InpEntryTF,1);
   bool valid=false;
   if(direction>0)
      valid=(c>o && c>=h-range*InpCloseExtreme);
   else
      valid=(c<o && c<=l+range*InpCloseExtreme);

   reason=valid ? "CONFIRMED IMPULSE" : "REJECT: candle direction/close location failed";
   return valid;
}
//+------------------------------------------------------------------+
bool FindOrderBlock(const int direction, double &zoneHigh, double &zoneLow)
{
   for(int s=2; s<=InpOBSearchBars+1; s++)
   {
      double o=iOpen(_Symbol,InpEntryTF,s);
      double c=iClose(_Symbol,InpEntryTF,s);
      if((direction>0 && c<o) || (direction<0 && c>o))
      {
         zoneHigh=iHigh(_Symbol,InpEntryTF,s);
         zoneLow=iLow(_Symbol,InpEntryTF,s);
         return (zoneHigh>zoneLow);
      }
   }
   return false;
}
//+------------------------------------------------------------------+
void DrawHLine(const string name,const double price,const color clr,
               const ENUM_LINE_STYLE style=STYLE_DASH)
{
   if(!InpDrawObjects) return;
   string id=g_prefix+name;
   if(ObjectFind(0,id)<0) ObjectCreate(0,id,OBJ_HLINE,0,0,price);
   ObjectSetDouble(0,id,OBJPROP_PRICE,price);
   ObjectSetInteger(0,id,OBJPROP_COLOR,clr);
   ObjectSetInteger(0,id,OBJPROP_STYLE,style);
   ObjectSetInteger(0,id,OBJPROP_WIDTH,1);
}
//+------------------------------------------------------------------+
void DrawText(const string name,const datetime t,const double price,
              const string label,const color clr)
{
   if(!InpDrawObjects) return;
   string id=g_prefix+name+"_"+IntegerToString((long)t);
   if(ObjectFind(0,id)>=0) return;
   if(ObjectCreate(0,id,OBJ_TEXT,0,t,price))
   {
      ObjectSetString(0,id,OBJPROP_TEXT,label);
      ObjectSetInteger(0,id,OBJPROP_COLOR,clr);
      ObjectSetInteger(0,id,OBJPROP_FONTSIZE,8);
   }
}
//+------------------------------------------------------------------+
void DrawOB()
{
   if(!InpDrawObjects || !g_setupActive) return;
   string id=g_prefix+"OB_"+IntegerToString((long)g_setupBar);
   datetime right=iTime(_Symbol,InpEntryTF,0)+PeriodSeconds(InpEntryTF)*InpSetupExpiryBars;
   if(ObjectFind(0,id)<0)
      ObjectCreate(0,id,OBJ_RECTANGLE,0,g_setupBar,g_obHigh,right,g_obLow);
   ObjectMove(0,id,0,g_setupBar,g_obHigh);
   ObjectMove(0,id,1,right,g_obLow);
   ObjectSetInteger(0,id,OBJPROP_COLOR,g_setupDirection>0?clrDodgerBlue:clrTomato);
   ObjectSetInteger(0,id,OBJPROP_STYLE,STYLE_DOT);
   ObjectSetInteger(0,id,OBJPROP_BACK,true);
   ObjectSetInteger(0,id,OBJPROP_FILL,false);
}
//+------------------------------------------------------------------+
void UpdatePanel()
{
   string biasText = g_bias>0 ? "BULLISH" : (g_bias<0 ? "BEARISH" : "NEUTRAL");
   string setupText = g_setupActive ? (g_setupDirection>0?"BUY SETUP":"SELL SETUP") : "NONE";
   string panel = "XAUUSD PRICE-ACTION DIAGNOSTIC\n";
   panel += "Structure H1: "+biasText+"\n";
   panel += "Setup: "+setupText+" | age: "+IntegerToString(g_setupAge)+"\n";
   panel += "Status: "+g_status+"\n";
   panel += "Orders: DISABLED (diagnostic only)";
   Comment(panel);
}
//+------------------------------------------------------------------+
void Reject(const string reason)
{
   g_status=reason;
   if(InpLogEveryRejection)
      PrintFormat("NO TRADE | %s | %s %s",reason,_Symbol,EnumToString(InpEntryTF));
   UpdatePanel();
}
//+------------------------------------------------------------------+
void ProcessStructureBar()
{
   datetime bar=iTime(_Symbol,InpStructureTF,0);
   if(bar==0 || bar==g_lastStructureBar) return;
   g_lastStructureBar=bar;

   double swingHigh=0,swingLow=0;
   int newBias=ReadStructureBias(swingHigh,swingLow);
   double close=iClose(_Symbol,InpStructureTF,1);
   double priorClose=iClose(_Symbol,InpStructureTF,2);

   if(swingHigh>0 && priorClose<=swingHigh && close>swingHigh)
   {
      DrawText("BOS_UP",iTime(_Symbol,InpStructureTF,1),close,"BOS UP",clrDodgerBlue);
      PrintFormat("STRUCTURE EVENT | BOS UP | close %.3f > swing %.3f",close,swingHigh);
   }
   if(swingLow>0 && priorClose>=swingLow && close<swingLow)
   {
      DrawText("BOS_DN",iTime(_Symbol,InpStructureTF,1),close,"BOS DOWN",clrTomato);
      PrintFormat("STRUCTURE EVENT | BOS DOWN | close %.3f < swing %.3f",close,swingLow);
   }

   g_previousBias=g_bias;
   g_bias=newBias;
   if(g_previousBias!=0 && g_bias!=0 && g_previousBias!=g_bias)
   {
      DrawText("CHOCH",iTime(_Symbol,InpStructureTF,1),close,
               g_bias>0?"CHoCH UP":"CHoCH DOWN",clrGold);
      PrintFormat("STRUCTURE EVENT | CHoCH | bias %d -> %d",g_previousBias,g_bias);
   }
   g_status="H1 structure updated";
   UpdatePanel();
}
//+------------------------------------------------------------------+
void ClearSetup(const string why)
{
   if(g_setupActive) PrintFormat("SETUP CLOSED | %s",why);
   g_setupActive=false;
   g_setupDirection=0;
   g_setupAge=0;
   g_setupBar=0;
   g_obHigh=0;
   g_obLow=0;
   g_sweepExtreme=0;
}
//+------------------------------------------------------------------+
void DetectNewSetup()
{
   string reason="";
   if(IsFlatMarket(reason)) { Reject(reason); return; }

   double extreme=0;
   int sweepDirection=DetectSweep(extreme,reason);
   if(sweepDirection==0) { Reject(reason); return; }

   if(g_bias==0)
   {
      Reject("NO TRADE: H1 structure is neutral / not confirmed");
      return;
   }
   if(sweepDirection!=g_bias)
   {
      Reject(StringFormat("NO TRADE: sweep direction %d conflicts with H1 bias %d",
                          sweepDirection,g_bias));
      return;
   }

   if(!ConfirmImpulse(sweepDirection,reason)) { Reject(reason); return; }

   double zoneHigh=0,zoneLow=0;
   if(!FindOrderBlock(sweepDirection,zoneHigh,zoneLow))
   {
      Reject("NO TRADE: no opposite candle found for OB");
      return;
   }

   g_setupActive=true;
   g_setupDirection=sweepDirection;
   g_setupBar=iTime(_Symbol,InpEntryTF,1);
   g_setupAge=0;
   g_obHigh=zoneHigh;
   g_obLow=zoneLow;
   g_sweepExtreme=extreme;
   DrawOB();
   DrawHLine("SWEEP_LEVEL",extreme,clrGold);
   DrawText("SWEEP",g_setupBar,extreme,
            sweepDirection>0?"LIQUIDITY SWEEP +":"LIQUIDITY SWEEP -",clrGold);
   g_status="SETUP CONFIRMED; WAITING FOR OB RETEST";
   PrintFormat("SETUP CONFIRMED | %s | OB %.3f-%.3f | sweep %.3f",
               sweepDirection>0?"BULLISH":"BEARISH",zoneLow,zoneHigh,extreme);
   UpdatePanel();
}
//+------------------------------------------------------------------+
void ManageRetest()
{
   if(!g_setupActive) return;

   datetime currentBar=iTime(_Symbol,InpEntryTF,0);
   static datetime lastAgeBar=0;
   if(currentBar>0 && currentBar!=lastAgeBar)
   {
      if(lastAgeBar!=0) g_setupAge++;
      lastAgeBar=currentBar;
   }

   if(g_setupAge>InpSetupExpiryBars)
   {
      ClearSetup("expired without OB retest");
      g_status="NO TRADE: setup expired";
      UpdatePanel();
      return;
   }

   double close=iClose(_Symbol,InpEntryTF,1);
   if((g_setupDirection>0 && close<g_sweepExtreme) ||
      (g_setupDirection<0 && close>g_sweepExtreme))
   {
      ClearSetup("sweep extreme invalidated");
      g_status="NO TRADE: sweep invalidated";
      UpdatePanel();
      return;
   }

   double atr=GetATR(1);
   if(atr<=0.0) return;
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick)) return;
   double price=g_setupDirection>0?tick.bid:tick.ask;
   double tolerance=atr*InpRetestToleranceATR;

   if(price>=g_obLow-tolerance && price<=g_obHigh+tolerance)
   {
      g_status="OB RETEST OBSERVED (NO ORDER)";
      DrawText("RETEST",TimeCurrent(),price,"OB RETEST",clrAqua);
      PrintFormat("RETEST OBSERVED | %s | price %.3f | zone %.3f-%.3f | diagnostic only",
                  g_setupDirection>0?"BULLISH":"BEARISH",price,g_obLow,g_obHigh);
      ClearSetup("retest observed; diagnostic event recorded");
      UpdatePanel();
   }
}
//+------------------------------------------------------------------+
void OnTick()
{
   if(Bars(_Symbol,InpEntryTF)<100 || Bars(_Symbol,InpStructureTF)<100)
   {
      Reject("WAIT: insufficient history");
      return;
   }

   ProcessStructureBar();
   ManageRetest();

   datetime bar=iTime(_Symbol,InpEntryTF,0);
   if(bar==0 || bar==g_lastEntryBar) return;
   g_lastEntryBar=bar;

   if(!g_setupActive)
      DetectNewSetup();
   else
   {
      g_status="SETUP ACTIVE; WAITING FOR RETEST";
      UpdatePanel();
   }
}
//+------------------------------------------------------------------+
