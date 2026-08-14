//+------------------------------------------------------------------+
//| VantageIctFeed.mqh — closed multi-TF candle export for Python ICT |
//+------------------------------------------------------------------+
#ifndef VANTAGE_ICT_FEED_MQH
#define VANTAGE_ICT_FEED_MQH

#include "VantageTypes.mqh"

class CVantageIctFeed
  {
private:
   string m_symbol;
   int    m_d1_bars;
   int    m_h4_bars;
   int    m_h1_bars;
   int    m_m15_bars;
   int    m_m5_bars;

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
   CVantageIctFeed(void) : m_d1_bars(30), m_h4_bars(60), m_h1_bars(80), m_m15_bars(120), m_m5_bars(150) {}

   void Configure(const string symbol,
                  const int d1_bars,
                  const int h4_bars,
                  const int h1_bars,
                  const int m15_bars,
                  const int m5_bars)
     {
      m_symbol = symbol;
      m_d1_bars = MathMax(10, d1_bars);
      m_h4_bars = MathMax(20, h4_bars);
      m_h1_bars = MathMax(30, h1_bars);
      m_m15_bars = MathMax(60, m15_bars);
      m_m5_bars = MathMax(60, m5_bars);
     }

   string BuildCandlesJson(const int digits)
     {
      MqlRates d1[], h4[], h1[], m15[], m5[];
      if(!CopyClosed(PERIOD_D1, m_d1_bars, d1))
         return "";
      if(!CopyClosed(PERIOD_H4, m_h4_bars, h4))
         return "";
      if(!CopyClosed(PERIOD_H1, m_h1_bars, h1))
         return "";
      if(!CopyClosed(PERIOD_M15, m_m15_bars, m15))
         return "";
      if(!CopyClosed(PERIOD_M5, m_m5_bars, m5))
         return "";
      string j = "{";
      j += "\"D1\":" + RatesToJsonArray(d1, ArraySize(d1), digits) + ",";
      j += "\"H4\":" + RatesToJsonArray(h4, ArraySize(h4), digits) + ",";
      j += "\"H1\":" + RatesToJsonArray(h1, ArraySize(h1), digits) + ",";
      j += "\"M15\":" + RatesToJsonArray(m15, ArraySize(m15), digits) + ",";
      j += "\"M5\":" + RatesToJsonArray(m5, ArraySize(m5), digits);
      j += "}";
      return j;
     }
  };

#endif
