#property strict
#property indicator_chart_window
#property indicator_plots 0

input ENUM_TIMEFRAMES InpTF=PERIOD_M5;
input int InpATRPeriod=14;
input double InpImpulseATR=1.40;
input double InpMinBodyRatio=0.65;
input double InpMinEfficiency=0.35;

int atrHandle=INVALID_HANDLE;

double ATR(int shift)
{
   double b[];
   ArraySetAsSeries(b,true);
   if(CopyBuffer(atrHandle,0,shift,1,b)!=1) return 0.0;
   return b[0];
}

double Efficiency(int bars)
{
   double first=iClose(_Symbol,InpTF,bars);
   double last=iClose(_Symbol,InpTF,1);
   double path=0.0;
   for(int i=1;i<=bars;i++)
      path+=iHigh(_Symbol,InpTF,i)-iLow(_Symbol,InpTF,i);
   if(path<=0.0) return 0.0;
   return MathAbs(last-first)/path;
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
   if(rates_total<30) return prev_calculated;

   double a=ATR(1);
   double range=iHigh(_Symbol,InpTF,1)-iLow(_Symbol,InpTF,1);
   double body=MathAbs(iClose(_Symbol,InpTF,1)-iOpen(_Symbol,InpTF,1));
   double eff=Efficiency(8);

   string state="NO TRADE";
   string reason="";

   if(a<=0.0) reason="ATR unavailable";
   else if(a < (ATR(2)+ATR(3)+ATR(4)+ATR(5))/4.0) reason="volatility below recent average";
   else if(eff < InpMinEfficiency) reason="flat / low directional efficiency";
   else if(range < a*InpImpulseATR) reason="no confirmed impulse";
   else if(body/range < InpMinBodyRatio) reason="weak candle body";
   else state="IMPULSE CANDIDATE";

   Comment("XAUUSD SETUP SCREENER\n",
           "TF: ",EnumToString(InpTF),"\n",
           "STATE: ",state,"\n",
           "ATR: ",DoubleToString(a,_Digits),"\n",
           "Efficiency: ",DoubleToString(eff,2),"\n",
           "Reason: ",reason);

   return rates_total;
}
