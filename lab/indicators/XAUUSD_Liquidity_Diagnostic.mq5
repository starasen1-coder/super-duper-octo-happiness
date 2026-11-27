#property strict
#property indicator_chart_window
#property indicator_plots 0

input ENUM_TIMEFRAMES InpTF=PERIOD_M5;
input int InpLookback=12;
input int InpATRPeriod=14;
input double InpSweepBufferATR=0.05;
input double InpImpulseATR=1.40;
input double InpMinBodyRatio=0.65;

int atrHandle=INVALID_HANDLE;
int seq=0;

double ATR(int shift)
{
   double b[];
   ArraySetAsSeries(b,true);
   if(CopyBuffer(atrHandle,0,shift,1,b)!=1) return 0.0;
   return b[0];
}

double HighestBefore(int shift,int count)
{
   int i=iHighest(_Symbol,InpTF,MODE_HIGH,count,shift);
   return i>=0 ? iHigh(_Symbol,InpTF,i) : 0.0;
}

double LowestBefore(int shift,int count)
{
   int i=iLowest(_Symbol,InpTF,MODE_LOW,count,shift);
   return i>=0 ? iLow(_Symbol,InpTF,i) : 0.0;
}

void Mark(string name,datetime t,double p,color c,int code)
{
   if(ObjectFind(0,name)>=0) ObjectDelete(0,name);
   ObjectCreate(0,name,OBJ_ARROW,0,t,p);
   ObjectSetInteger(0,name,OBJPROP_ARROWCODE,code);
   ObjectSetInteger(0,name,OBJPROP_COLOR,c);
   ObjectSetInteger(0,name,OBJPROP_WIDTH,2);
}

int OnInit()
{
   atrHandle=iATR(_Symbol,InpTF,InpATRPeriod);
   return atrHandle==INVALID_HANDLE ? INIT_FAILED : INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(atrHandle!=INVALID_HANDLE) IndicatorRelease(atrHandle);
   Comment("");
}

int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
{
   static datetime lastBar=0;
   datetime bar=iTime(_Symbol,InpTF,0);
   if(bar==lastBar) return rates_total;
   lastBar=bar;

   double a=ATR(1);
   if(a<=0.0) return rates_total;

   double h=iHigh(_Symbol,InpTF,1);
   double l=iLow(_Symbol,InpTF,1);
   double o=iOpen(_Symbol,InpTF,1);
   double c=iClose(_Symbol,InpTF,1);
   double r=h-l;
   if(r<=0.0) return rates_total;

   double prevH=HighestBefore(2,InpLookback);
   double prevL=LowestBefore(2,InpLookback);

   bool bearishSweep=h>prevH+a*InpSweepBufferATR && c<prevH;
   bool bullishSweep=l<prevL-a*InpSweepBufferATR && c>prevL;
   bool impulse=r>=a*InpImpulseATR && MathAbs(c-o)/r>=InpMinBodyRatio;

   seq++;

   if(bearishSweep)
      Mark("LQD_BEAR_"+IntegerToString(seq),iTime(_Symbol,InpTF,1),h,clrRed,234);
   if(bullishSweep)
      Mark("LQD_BULL_"+IntegerToString(seq),iTime(_Symbol,InpTF,1),l,clrLime,233);
   if(impulse)
      Mark("IMP_"+IntegerToString(seq),iTime(_Symbol,InpTF,1),c,clrYellow,c>o?241:242);

   Comment("XAUUSD LIQUIDITY DIAGNOSTIC\n",
           "Bearish sweep: ",bearishSweep?"YES":"NO","\n",
           "Bullish sweep: ",bullishSweep?"YES":"NO","\n",
           "Impulse: ",impulse?"YES":"NO","\n",
           "ATR: ",DoubleToString(a,_Digits));

   return rates_total;
}
