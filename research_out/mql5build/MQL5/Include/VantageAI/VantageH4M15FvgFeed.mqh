//+------------------------------------------------------------------+
//| VantageH4M15FvgFeed.mqh — closed H4/M15 candle export for Python |
//+------------------------------------------------------------------+
#ifndef VANTAGE_H4M15_FVG_FEED_MQH
#define VANTAGE_H4M15_FVG_FEED_MQH

#include "VantageTypes.mqh"

class CVantageH4M15FvgFeed
  {
private:
   string m_symbol;
   int    m_h4_bars;
   int    m_m15_bars;

   bool CopyClosed(const ENUM_TIMEFRAMES tf, const int count, MqlRates &rates[])
     {
      ArraySetAsSeries(rates, true);
      int n = CopyRates(m_symbol, tf, 1, count, rates);
      return (n >= MathMin(count, 20));
     }

   string RatesToJsonArray(const MqlRates &rates[], const int count, const int digits)
     {
      if(count <= 0)
         return "[]";
      string j = "[";
      for(int i = count - 1; i >= 0; i--)
        {
         if(i < count - 1)
            j += ",";
         j += "{";
         j += "\"time\":" + IntegerToString((long)rates[i].time) + ",";
         j += "\"open\":" + DoubleToJson(rates[i].open, digits) + ",";
         j += "\"high\":" + DoubleToJson(rates[i].high, digits) + ",";
         j += "\"low\":" + DoubleToJson(rates[i].low, digits) + ",";
         j += "\"close\":" + DoubleToJson(rates[i].close, digits) + ",";
         j += "\"volume\":" + DoubleToJson((double)rates[i].tick_volume, 0);
         j += "}";
        }
      j += "]";
      return j;
     }

public:
   CVantageH4M15FvgFeed(void) : m_h4_bars(80), m_m15_bars(120) {}

   void Configure(const string symbol, const int h4_bars, const int m15_bars)
     {
      m_symbol = symbol;
      m_h4_bars = MathMax(30, h4_bars);
      m_m15_bars = MathMax(40, m15_bars);
     }

   string BuildCandlesJson(const int digits)
     {
      MqlRates h4[], m15[];
      if(!CopyClosed(PERIOD_H4, m_h4_bars, h4))
         return "";
      if(!CopyClosed(PERIOD_M15, m_m15_bars, m15))
         return "";
      string j = "{";
      j += "\"H4\":" + RatesToJsonArray(h4, ArraySize(h4), digits) + ",";
      j += "\"M15\":" + RatesToJsonArray(m15, ArraySize(m15), digits);
      j += "}";
      return j;
     }
  };

#endif
