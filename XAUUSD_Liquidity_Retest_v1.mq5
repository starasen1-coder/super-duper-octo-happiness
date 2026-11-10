//+------------------------------------------------------------------+
//| XAUUSD_Liquidity_Retest_v1.mq5                                  |
//| Structure + liquidity sweep + confirmed impulse + OB retest      |
//| No moving averages. Designed for XAUUSD M5 research/backtesting. |
//+------------------------------------------------------------------+
#property strict
#include <Trade\Trade.mqh>

input group "Основные"
input ENUM_TIMEFRAMES InpEntryTF = PERIOD_M5;
input long   InpMagic = 26111001;
input bool   InpOnlyGold = true;
input bool   InpOnePosition = true;
input int    InpSetupExpiryBars = 12;

input group "Структура"
input ENUM_TIMEFRAMES InpStructureTF = PERIOD_H1;
input int    InpStructureLookback = 20;
input int    InpMinStructureGapPoints = 50;

input group "Импульс"
input int    InpATRPeriod = 14;
input double InpImpulseATR = 1.40;
input double InpMinBodyRatio = 0.65;
input double InpCloseExtreme = 0.20;
input double InpMinEfficiency = 0.35;
input double InpMinATRRatio = 1.05;

input group "Ликвидность"
input int    InpSweepLookback = 12;
input double InpSweepBufferATR = 0.05;

input group "OB / вход"
input double InpRetestToleranceATR = 0.20;
input double InpSLBufferATR = 0.10;
input double InpMinRR = 2.0;
input bool   InpUseLimitOrder = false;

input group "Риск"
input double InpRiskPercent = 0.50;
input double InpFixedLot = 0.0;
input double InpMaxLot = 1.0;

CTrade trade;
int atrHandle = INVALID_HANDLE;
datetime lastBar = 0;

struct SetupState
{
   bool active;
   int direction;          // +1 buy, -1 sell
   datetime created;
   int ageBars;
   double obHigh;
   double obLow;
   double sweepPrice;
   double target;
};

SetupState setup = {false,0,0,0,0,0,0,0};

//+------------------------------------------------------------------+
int OnInit()
{
   if(InpOnlyGold && StringFind(_Symbol,"XAU") < 0)
      Print("Внимание: советник рассчитан на XAUUSD.");

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(20);
   trade.SetTypeFillingBySymbol(_Symbol);

   atrHandle = iATR(_Symbol, InpEntryTF, InpATRPeriod);
   if(atrHandle == INVALID_HANDLE)
      return INIT_FAILED;

   return INIT_SUCCEEDED;
}
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(atrHandle != INVALID_HANDLE)
      IndicatorRelease(atrHandle);
}
//+------------------------------------------------------------------+
double ATR(int shift)
{
   double b[];
   ArraySetAsSeries(b,true);
   if(CopyBuffer(atrHandle,0,shift,1,b) != 1)
      return 0.0;
   return b[0];
}
//+------------------------------------------------------------------+
double CandleRange(int shift)
{
   return iHigh(_Symbol,InpEntryTF,shift)-iLow(_Symbol,InpEntryTF,shift);
}
//+------------------------------------------------------------------+
double BodyRatio(int shift)
{
   double r=CandleRange(shift);
   if(r<=0) return 0.0;
   return MathAbs(iClose(_Symbol,InpEntryTF,shift)-iOpen(_Symbol,InpEntryTF,shift))/r;
}
//+------------------------------------------------------------------+
double AverageATR(int startShift,int count)
{
   double sum=0;
   int n=0;
   for(int i=startShift;i<startShift+count;i++)
   {
      double a=ATR(i);
      if(a>0){sum+=a;n++;}
   }
   return n>0 ? sum/n : 0;
}
//+------------------------------------------------------------------+
double Efficiency(int bars)
{
   if(bars<2) return 0;
   double first=iClose(_Symbol,InpEntryTF,bars);
   double last=iClose(_Symbol,InpEntryTF,1);
   double path=0;
   for(int i=1;i<=bars;i++)
      path+=CandleRange(i);
   if(path<=0) return 0;
   return MathAbs(last-first)/path;
}
//+------------------------------------------------------------------+
bool IsFlat()
{
   double a=ATR(1);
   double avg=AverageATR(2,20);
   if(a<=0 || avg<=0) return true;
   if(a < avg*InpMinATRRatio) return true;
   if(Efficiency(8) < InpMinEfficiency) return true;
   return false;
}
//+------------------------------------------------------------------+
//| Простая без-MA структура H1: последние экстремумы должны         |
//| последовательно двигаться в сторону направления.                 |
//+------------------------------------------------------------------+
int StructureBias()
{
   int n=InpStructureLookback;
   if(n<10) n=10;

   int hi1=iHighest(_Symbol,InpStructureTF,MODE_HIGH,n,1);
   int lo1=iLowest(_Symbol,InpStructureTF,MODE_LOW,n,1);
   int hi2=iHighest(_Symbol,InpStructureTF,MODE_HIGH,n, n+1);
   int lo2=iLowest(_Symbol,InpStructureTF,MODE_LOW,n, n+1);
   if(hi1<0 || lo1<0 || hi2<0 || lo2<0) return 0;

   double h1=iHigh(_Symbol,InpStructureTF,hi1);
   double h2=iHigh(_Symbol,InpStructureTF,hi2);
   double l1=iLow(_Symbol,InpStructureTF,lo1);
   double l2=iLow(_Symbol,InpStructureTF,lo2);

   double gap=InpMinStructureGapPoints*_Point;
   if(h1>h2+gap && l1>l2+gap) return 1;
   if(h1<h2-gap && l1<l2-gap) return -1;
   return 0;
}
//+------------------------------------------------------------------+
double HighestBefore(int shift,int count)
{
   int idx=iHighest(_Symbol,InpEntryTF,MODE_HIGH,count,shift);
   return idx>=0 ? iHigh(_Symbol,InpEntryTF,idx) : 0;
}
//+------------------------------------------------------------------+
double LowestBefore(int shift,int count)
{
   int idx=iLowest(_Symbol,InpEntryTF,MODE_LOW,count,shift);
   return idx>=0 ? iLow(_Symbol,InpEntryTF,idx) : 0;
}
//+------------------------------------------------------------------+
//| +1 = bullish sweep, -1 = bearish sweep.                          |
//+------------------------------------------------------------------+
int DetectSweep(double &sweepPrice)
{
   double a=ATR(1);
   if(a<=0) return 0;

   double prevHigh=HighestBefore(2,InpSweepLookback);
   double prevLow =LowestBefore(2,InpSweepLookback);
   double h=iHigh(_Symbol,InpEntryTF,1);
   double l=iLow(_Symbol,InpEntryTF,1);
   double c=iClose(_Symbol,InpEntryTF,1);

   if(h>prevHigh+a*InpSweepBufferATR && c<prevHigh)
   {
      sweepPrice=h;
      return -1;
   }
   if(l<prevLow-a*InpSweepBufferATR && c>prevLow)
   {
      sweepPrice=l;
      return 1;
   }
   return 0;
}
//+------------------------------------------------------------------+
bool ConfirmImpulse(int direction)
{
   double a=ATR(1);
   double r=CandleRange(1);
   if(a<=0 || r<a*InpImpulseATR) return false;
   if(BodyRatio(1)<InpMinBodyRatio) return false;

   double o=iOpen(_Symbol,InpEntryTF,1);
   double h=iHigh(_Symbol,InpEntryTF,1);
   double l=iLow(_Symbol,InpEntryTF,1);
   double c=iClose(_Symbol,InpEntryTF,1);

   if(direction<0)
      return c <= l+r*InpCloseExtreme && c<o;
   return c >= h-r*InpCloseExtreme && c>o;
}
//+------------------------------------------------------------------+
//| OB = последняя противоположная свеча перед импульсом.             |
//+------------------------------------------------------------------+
bool BuildOB(int direction,double &obHigh,double &obLow)
{
   int s=2;
   double o=iOpen(_Symbol,InpEntryTF,s);
   double c=iClose(_Symbol,InpEntryTF,s);
   double h=iHigh(_Symbol,InpEntryTF,s);
   double l=iLow(_Symbol,InpEntryTF,s);

   if(direction<0 && c>o)
   {
      obHigh=h; obLow=l; return true;
   }
   if(direction>0 && c<o)
   {
      obHigh=h; obLow=l; return true;
   }

   // Ищем до 3 свечей назад, чтобы не принимать пустой/неподходящий OB.
   for(s=3;s<=5;s++)
   {
      o=iOpen(_Symbol,InpEntryTF,s);
      c=iClose(_Symbol,InpEntryTF,s);
      h=iHigh(_Symbol,InpEntryTF,s);
      l=iLow(_Symbol,InpEntryTF,s);

      if(direction<0 && c>o)
      {
         obHigh=h; obLow=l; return true;
      }
      if(direction>0 && c<o)
      {
         obHigh=h; obLow=l; return true;
      }
   }
   return false;
}
//+------------------------------------------------------------------+
double NearestLiquidity(int direction,double entry)
{
   int n=30;
   if(direction<0)
   {
      int idx=iLowest(_Symbol,InpEntryTF,MODE_LOW,n,2);
      double p=idx>=0?iLow(_Symbol,InpEntryTF,idx):0;
      return (p>0 && p<entry) ? p : entry-ATR(1)*InpMinRR;
   }
   int idx=iHighest(_Symbol,InpEntryTF,MODE_HIGH,n,2);
   double p=idx>=0?iHigh(_Symbol,InpEntryTF,idx):0;
   return (p>entry) ? p : entry+ATR(1)*InpMinRR;
}
//+------------------------------------------------------------------+
bool PriceInsideOB(double price,double high,double low,double tolerance)
{
   return price>=low-tolerance && price<=high+tolerance;
}
//+------------------------------------------------------------------+
double NormalizeVolume(double volume)
{
   double minv=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maxv=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(step<=0) return 0;
   volume=MathMax(minv,MathMin(maxv,MathMin(InpMaxLot,volume)));
   volume=MathFloor(volume/step)*step;
   return NormalizeDouble(volume,2);
}
//+------------------------------------------------------------------+
double RiskVolume(ENUM_ORDER_TYPE type,double entry,double sl)
{
   if(InpFixedLot>0) return NormalizeVolume(InpFixedLot);

   double riskMoney=AccountInfoDouble(ACCOUNT_BALANCE)*InpRiskPercent/100.0;
   if(riskMoney<=0) return 0;

   double oneLotLoss=0;
   if(!OrderCalcProfit(type,_Symbol,1.0,entry,sl,oneLotLoss))
      return 0;
   oneLotLoss=MathAbs(oneLotLoss);
   if(oneLotLoss<=0) return 0;

   return NormalizeVolume(riskMoney/oneLotLoss);
}
//+------------------------------------------------------------------+
bool OpenTrade(int direction,double obHigh,double obLow,double sweepPrice)
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick)) return false;

   double a=ATR(1);
   if(a<=0) return false;

   double entry=(direction<0?tick.bid:tick.ask);
   double sl,tp;

   if(direction<0)
   {
      sl=MathMax(obHigh,sweepPrice)+a*InpSLBufferATR;
      tp=NearestLiquidity(-1,entry);
      if(tp>=entry || (entry-tp)<=0) return false;
      if((entry-tp)/(sl-entry)<InpMinRR) return false;

      double lot=RiskVolume(ORDER_TYPE_SELL,entry,sl);
      if(lot<=0) return false;
      bool ok=trade.Sell(lot,_Symbol,entry,NormalizeDouble(sl,_Digits),
                         NormalizeDouble(tp,_Digits),"LIQ-OB SELL");
      if(!ok)
         PrintFormat("SELL failed: retcode=%d %s",trade.ResultRetcode(),trade.ResultRetcodeDescription());
      return ok;
   }

   sl=MathMin(obLow,sweepPrice)-a*InpSLBufferATR;
   tp=NearestLiquidity(1,entry);
   if(tp<=entry || (tp-entry)<=0) return false;
   if((tp-entry)/(entry-sl)<InpMinRR) return false;

   double lot=RiskVolume(ORDER_TYPE_BUY,entry,sl);
   if(lot<=0) return false;
   bool ok=trade.Buy(lot,_Symbol,entry,NormalizeDouble(sl,_Digits),
                     NormalizeDouble(tp,_Digits),"LIQ-OB BUY");
   if(!ok)
      PrintFormat("BUY failed: retcode=%d %s",trade.ResultRetcode(),trade.ResultRetcodeDescription());
   return ok;
}
//+------------------------------------------------------------------+
void DrawSetup()
{
   string pfx="LIQOB_"+IntegerToString((long)setup.created);
   ObjectCreate(0,pfx+"_OB",OBJ_RECTANGLE,0,setup.created,setup.obHigh,
                TimeCurrent()+PeriodSeconds(InpEntryTF)*InpSetupExpiryBars,setup.obLow);
   ObjectSetInteger(0,pfx+"_OB",OBJPROP_BACK,true);
   ObjectSetInteger(0,pfx+"_OB",OBJPROP_FILL,true);

   ObjectCreate(0,pfx+"_SWEEP",OBJ_HLINE,0,0,setup.sweepPrice);
   ObjectSetInteger(0,pfx+"_SWEEP",OBJPROP_STYLE,STYLE_DASH);
}
//+------------------------------------------------------------------+
void ClearSetup()
{
   setup.active=false;
   setup.direction=0;
   setup.ageBars=0;
   setup.created=0;
   setup.obHigh=0;
   setup.obLow=0;
   setup.sweepPrice=0;
   setup.target=0;
}
//+------------------------------------------------------------------+
void DetectNewSetup()
{
   if(IsFlat()) return;

   int bias=StructureBias();
   if(bias==0) return;

   double sweep=0;
   int sweepDir=DetectSweep(sweep);
   if(sweepDir==0 || sweepDir!=bias) return;

   if(!ConfirmImpulse(sweepDir)) return;

   double obH=0,obL=0;
   if(!BuildOB(sweepDir,obH,obL)) return;

   setup.active=true;
   setup.direction=sweepDir;
   setup.created=iTime(_Symbol,InpEntryTF,1);
   setup.ageBars=0;
   setup.obHigh=obH;
   setup.obLow=obL;
   setup.sweepPrice=sweep;
   setup.target=0;

   DrawSetup();
   PrintFormat("NEW SETUP %s OB %.3f-%.3f sweep %.3f",
               sweepDir>0?"BUY":"SELL",obL,obH,sweep);
}
//+------------------------------------------------------------------+
void ManageSetup()
{
   if(!setup.active) return;

   setup.ageBars++;
   if(setup.ageBars>InpSetupExpiryBars)
   {
      ClearSetup();
      return;
   }

   double a=ATR(1);
   if(a<=0) return;

   // Слом сценария: цена закрылась за sweep.
   double c=iClose(_Symbol,InpEntryTF,1);
   if((setup.direction<0 && c>setup.sweepPrice) ||
      (setup.direction>0 && c<setup.sweepPrice))
   {
      ClearSetup();
      return;
   }

   if(InpOnePosition && PositionSelect(_Symbol))
      return;

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick)) return;

   double price=(setup.direction<0?tick.bid:tick.ask);
   double tol=a*InpRetestToleranceATR;

   if(PriceInsideOB(price,setup.obHigh,setup.obLow,tol))
   {
      if(OpenTrade(setup.direction,setup.obHigh,setup.obLow,setup.sweepPrice))
         ClearSetup();
   }
}
//+------------------------------------------------------------------+
void OnTick()
{
   if(InpOnlyGold && StringFind(_Symbol,"XAU")<0) return;

   datetime bar=iTime(_Symbol,InpEntryTF,0);
   if(bar==0) return;

   // Управление ретестом происходит на каждом тике.
   ManageSetup();

   if(bar==lastBar) return;
   lastBar=bar;

   if(InpOnePosition && PositionSelect(_Symbol))
      return;

   // Новый setup ищем только на новой свече.
   if(!setup.active)
      DetectNewSetup();
}
//+------------------------------------------------------------------+
