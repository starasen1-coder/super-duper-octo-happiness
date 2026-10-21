//+------------------------------------------------------------------+
//| LLM_Advisor.mq5 - каркас: базовый сигнал + фильтр через LLM      |
//| Нужно: Сервис-Настройки-Советники-Разрешить WebRequest,          |
//| добавить URL прокси (http://127.0.0.1:8000)                      |
//+------------------------------------------------------------------+
#property strict
#include <Trade\Trade.mqh>

input string InpUrl          = "http://127.0.0.1:8000/decide";
input bool   InpUseLLM       = true;
input double InpMinConf      = 0.6;     // мин. уверенность модели
input bool   InpTradeOnFail  = false;   // торговать, если LLM недоступен
input int    InpTimeoutMs    = 15000;
input double InpLot          = 0.01;
input int    InpSLPoints     = 300;
input int    InpTPPoints     = 600;
input long   InpMagic        = 260101;
input int    InpVPBars       = 100;     // баров для Volume Profile
input int    InpVPBins       = 40;
input int    InpCandlesSent  = 20;

CTrade trade;
datetime lastBar = 0;

int OnInit() { trade.SetExpertMagicNumber(InpMagic); return INIT_SUCCEEDED; }

//--- Volume Profile по тиковому объёму: POC и область стоимости 70%
bool VolumeProfile(double &poc, double &vah, double &val)
{
   int bars = InpVPBars, bins = InpVPBins;
   double hi = iHigh(_Symbol, _Period, iHighest(_Symbol, _Period, MODE_HIGH, bars, 1));
   double lo = iLow(_Symbol, _Period, iLowest(_Symbol, _Period, MODE_LOW, bars, 1));
   if(hi <= lo) return false;
   double step = (hi - lo) / bins;
   double vol[]; ArrayResize(vol, bins); ArrayInitialize(vol, 0);
   for(int i = 1; i <= bars; i++)
   {
      double c = (iHigh(_Symbol,_Period,i) + iLow(_Symbol,_Period,i) + iClose(_Symbol,_Period,i)) / 3.0;
      int b = (int)MathFloor((c - lo) / step);
      if(b >= bins) b = bins - 1;
      if(b < 0) b = 0;
      vol[b] += (double)iTickVolume(_Symbol, _Period, i);
   }
   int pb = 0; double total = 0;
   for(int k = 0; k < bins; k++) { total += vol[k]; if(vol[k] > vol[pb]) pb = k; }
   int l = pb, u = pb; double acc = vol[pb];
   while(acc < 0.7 * total && (l > 0 || u < bins - 1))
   {
      double dn = (l > 0) ? vol[l-1] : -1, up = (u < bins-1) ? vol[u+1] : -1;
      if(up >= dn) { u++; acc += vol[u]; } else { l--; acc += vol[l]; }
   }
   poc = lo + (pb + 0.5) * step;
   val = lo + l * step;
   vah = lo + (u + 1) * step;
   return true;
}

//--- ПРИМЕР базового сигнала (замени своей логикой): возврат к POC от границ value area
// 1 = buy, -1 = sell, 0 = нет
int BaseSignal(double val, double vah)
{
   double c1 = iClose(_Symbol,_Period,1), c2 = iClose(_Symbol,_Period,2);
   if(c2 < val && c1 > val) return 1;
   if(c2 > vah && c1 < vah) return -1;
   return 0;
}

string Session()
{
   MqlDateTime t; TimeToStruct(TimeGMT(), t);
   if(t.hour < 7)  return "asia";
   if(t.hour < 13) return "london";
   if(t.hour < 21) return "newyork";
   return "offhours";
}

string BuildJson(int sig, double poc, double vah, double val)
{
   string s = "{\"symbol\":\"" + _Symbol + "\",\"timeframe\":\"" + EnumToString(_Period) + "\"";
   s += ",\"session\":\"" + Session() + "\"";
   s += ",\"signal\":\"" + (sig > 0 ? "long" : "short") + "\"";
   s += ",\"price\":" + DoubleToString(iClose(_Symbol,_Period,1), _Digits);
   s += ",\"poc\":" + DoubleToString(poc,_Digits) + ",\"vah\":" + DoubleToString(vah,_Digits) + ",\"val\":" + DoubleToString(val,_Digits);
   s += ",\"candles\":[";
   for(int i = InpCandlesSent; i >= 1; i--)
   {
      s += "[" + DoubleToString(iOpen(_Symbol,_Period,i),_Digits) + "," + DoubleToString(iHigh(_Symbol,_Period,i),_Digits)
         + "," + DoubleToString(iLow(_Symbol,_Period,i),_Digits) + "," + DoubleToString(iClose(_Symbol,_Period,i),_Digits)
         + "," + IntegerToString((long)iTickVolume(_Symbol,_Period,i)) + "]";
      if(i > 1) s += ",";
   }
   return s + "]}";
}

string JsonStr(string js, string key)
{
   int p = StringFind(js, "\"" + key + "\""); if(p < 0) return "";
   p = StringFind(js, ":", p);
   int q1 = StringFind(js, "\"", p), q2 = StringFind(js, "\"", q1 + 1);
   if(q1 < 0 || q2 < 0) return "";
   return StringSubstr(js, q1 + 1, q2 - q1 - 1);
}

double JsonNum(string js, string key)
{
   int p = StringFind(js, "\"" + key + "\""); if(p < 0) return 0;
   p = StringFind(js, ":", p);
   return StringToDouble(StringSubstr(js, p + 1, 12));
}

//--- запрос к прокси. true = ответ получен
bool AskLLM(string body, string &bias, double &conf)
{
   char data[], res[]; string rh;
   StringToCharArray(body, data, 0, StringLen(body), CP_UTF8);
   int rc = WebRequest("POST", InpUrl, "Content-Type: application/json\r\n", InpTimeoutMs, data, res, rh);
   if(rc != 200) { PrintFormat("LLM: http=%d err=%d", rc, GetLastError()); return false; }
   string js = CharArrayToString(res, 0, WHOLE_ARRAY, CP_UTF8);
   bias = JsonStr(js, "bias");
   conf = JsonNum(js, "confidence");
   PrintFormat("LLM: bias=%s conf=%.2f reason=%s", bias, conf, JsonStr(js, "reason"));
   return true;
}

void OnTick()
{
   datetime bar = iTime(_Symbol, _Period, 0);
   if(bar == lastBar) return;          // работаем раз на новую свечу
   lastBar = bar;
   if(PositionSelect(_Symbol)) return; // одна позиция

   double poc, vah, val;
   if(!VolumeProfile(poc, vah, val)) return;
   int sig = BaseSignal(val, vah);
   if(sig == 0) return;

   bool allow = true;
   if(InpUseLLM)
   {
      string bias; double conf;
      if(AskLLM(BuildJson(sig, poc, vah, val), bias, conf))
         allow = (bias == (sig > 0 ? "long" : "short") && conf >= InpMinConf);
      else
         allow = InpTradeOnFail;
   }
   if(!allow) return;

   double pt = _Point;
   if(sig > 0)
   { double a = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
     trade.Buy(InpLot, _Symbol, a, a - InpSLPoints*pt, a + InpTPPoints*pt, "LLM"); }
   else
   { double b = SymbolInfoDouble(_Symbol, SYMBOL_BID);
     trade.Sell(InpLot, _Symbol, b, b + InpSLPoints*pt, b - InpTPPoints*pt, "LLM"); }
}
