//+------------------------------------------------------------------+
//| VantageAnalysis.mqh                                              |
//| Local technical engine (EMA/BB/RSI/ATR/structure)                |
//| Confirmed closed candles only for signals                        |
//+------------------------------------------------------------------+
#ifndef VANTAGE_ANALYSIS_MQH
#define VANTAGE_ANALYSIS_MQH

#include "VantageTypes.mqh"

struct VantageLevelConfig
  {
   double upper_resist;   // 4143
   double sec_resist;     // 4133
   double daily_pivot;    // 4124.29
   double imm_resist;     // 4112 bullish confirmation
   double imm_sup_hi;     // 4105 recovery 2
   double imm_sup_lo;     // 4100 recovery 1
   double maj_buy_hi;     // 4090 immediate support hi
   double maj_buy_lo;     // 4088 immediate support lo
   double sec_support;    // 4085
   double oversized_range_atr;
   double oversized_body_atr;
   double retest_tol;
   double rsi_exhaust;
   int    pivot_left;
   int    pivot_right;
   int    trend_need;
   int    bias_lookback;   // closed candles for bullish/bearish %
  };

// Chart-relative levels from mid price + ATR (for BTCUSD and any non-fixed map).
bool VantageFillAutoLevels(const double mid,
                           const double atr,
                           const int digits,
                           const double oversized_range_atr,
                           const double oversized_body_atr,
                           const double rsi_exhaust,
                           const int trend_need,
                           const int bias_lookback,
                           VantageLevelConfig &lvl,
                           double &out_imm_lo,
                           double &out_imm_hi,
                           double &out_rec1,
                           double &out_rec2,
                           double &out_bull)
  {
   if(mid <= 0.0 || atr <= 0.0)
      return false;
   const double a = atr;
   out_imm_lo = NormalizeDouble(mid - 1.00 * a, digits);
   out_imm_hi = NormalizeDouble(mid - 0.50 * a, digits);
   out_rec1   = NormalizeDouble(mid + 0.50 * a, digits);
   out_rec2   = NormalizeDouble(mid + 1.00 * a, digits);
   out_bull   = NormalizeDouble(mid + 1.50 * a, digits);

   ZeroMemory(lvl);
   lvl.daily_pivot = NormalizeDouble(mid, digits);
   lvl.maj_buy_lo = out_imm_lo;
   lvl.maj_buy_hi = out_imm_hi;
   lvl.imm_sup_lo = out_rec1;   // recovery 1 (same mapping as manual OnInit)
   lvl.imm_sup_hi = out_rec2;   // recovery 2
   lvl.imm_resist = out_bull;   // bullish confirmation
   lvl.sec_support = NormalizeDouble(mid - 1.50 * a, digits);
   lvl.sec_resist = NormalizeDouble(mid + 2.00 * a, digits);
   lvl.upper_resist = NormalizeDouble(mid + 2.50 * a, digits);
   lvl.oversized_range_atr = oversized_range_atr;
   lvl.oversized_body_atr = oversized_body_atr;
   lvl.retest_tol = MathMax(NormalizeDouble(0.25 * a, digits), _Point * 10);
   lvl.rsi_exhaust = rsi_exhaust;
   lvl.pivot_left = 3;
   lvl.pivot_right = 3;
   lvl.trend_need = trend_need;
   lvl.bias_lookback = bias_lookback;
   return true;
  }

class CVantageAnalysis
  {
private:
   string m_symbol;
   ENUM_TIMEFRAMES m_tf;
   int m_hEma20;
   int m_hEma50;
   int m_hEma200;
   int m_hBB;
   int m_hRsi;
   int m_hAtr;
   VantageLevelConfig m_lvl;
   bool m_retest_pending;
   double m_last_broken;

   bool Copy1(const int handle, const int buffer, const int shift, double &out_v)
     {
      double a[];
      if(CopyBuffer(handle, buffer, shift, 1, a) != 1)
         return false;
      out_v = a[0];
      return MathIsValidNumber(out_v);
     }

   double NearestBelow(const double px)
     {
      double levels[6];
      levels[0] = m_lvl.imm_resist;
      levels[1] = m_lvl.imm_sup_hi;
      levels[2] = m_lvl.imm_sup_lo;
      levels[3] = m_lvl.maj_buy_hi;
      levels[4] = m_lvl.maj_buy_lo;
      levels[5] = m_lvl.sec_support;
      double best = 0.0;
      double gap = 1e100;
      for(int i = 0; i < 6; i++)
        {
         if(levels[i] <= px)
           {
            double g = px - levels[i];
            if(g < gap)
              {
               gap = g;
               best = levels[i];
              }
           }
        }
      return best;
     }

   double NearestAbove(const double px)
     {
      double levels[4];
      levels[0] = m_lvl.imm_resist;
      levels[1] = m_lvl.daily_pivot;
      levels[2] = m_lvl.sec_resist;
      levels[3] = m_lvl.upper_resist;
      double best = 0.0;
      double gap = 1e100;
      for(int i = 0; i < 4; i++)
        {
         if(levels[i] >= px)
           {
            double g = levels[i] - px;
            if(g < gap)
              {
               gap = g;
               best = levels[i];
              }
           }
        }
      return best;
     }

public:
   CVantageAnalysis(void)
     {
      m_hEma20 = m_hEma50 = m_hEma200 = m_hBB = m_hRsi = m_hAtr = INVALID_HANDLE;
      m_retest_pending = false;
      m_last_broken = 0.0;
      ZeroMemory(m_lvl);
     }

   void SetLevels(const VantageLevelConfig &cfg) { m_lvl = cfg; }

   bool Init(const string symbol, const ENUM_TIMEFRAMES tf)
     {
      Release();
      m_symbol = symbol;
      m_tf = tf;
      m_hEma20  = iMA(symbol, tf, 20, 0, MODE_EMA, PRICE_CLOSE);
      m_hEma50  = iMA(symbol, tf, 50, 0, MODE_EMA, PRICE_CLOSE);
      m_hEma200 = iMA(symbol, tf, 200, 0, MODE_EMA, PRICE_CLOSE);
      m_hBB     = iBands(symbol, tf, 20, 0, 2.0, PRICE_CLOSE);
      m_hRsi    = iRSI(symbol, tf, 14, PRICE_CLOSE);
      m_hAtr    = iATR(symbol, tf, 14);
      if(m_hEma20 == INVALID_HANDLE || m_hEma50 == INVALID_HANDLE || m_hEma200 == INVALID_HANDLE ||
         m_hBB == INVALID_HANDLE || m_hRsi == INVALID_HANDLE || m_hAtr == INVALID_HANDLE)
        {
         Print("[VantageAI] Indicator handle init failed err=", GetLastError());
         return false;
        }
      return true;
     }

   void Release(void)
     {
      if(m_hEma20  != INVALID_HANDLE) IndicatorRelease(m_hEma20);
      if(m_hEma50  != INVALID_HANDLE) IndicatorRelease(m_hEma50);
      if(m_hEma200 != INVALID_HANDLE) IndicatorRelease(m_hEma200);
      if(m_hBB     != INVALID_HANDLE) IndicatorRelease(m_hBB);
      if(m_hRsi    != INVALID_HANDLE) IndicatorRelease(m_hRsi);
      if(m_hAtr    != INVALID_HANDLE) IndicatorRelease(m_hAtr);
      m_hEma20 = m_hEma50 = m_hEma200 = m_hBB = m_hRsi = m_hAtr = INVALID_HANDLE;
     }

   bool HasEnoughHistory(const int need = 220)
     {
      return (Bars(m_symbol, m_tf) >= need);
     }

   // shift=1 => last CLOSED candle (never shift 0 for confirmed signals)
   bool BuildSnapshot(VantageTechnicalSnap &snap)
     {
      return BuildSnapshotAtShift(snap, 1);
     }

   // Strategy Tester replay: snapshot for a specific closed M30 bar time
   bool BuildSnapshotAt(VantageTechnicalSnap &snap, const datetime bar_time)
     {
      const int sh = iBarShift(m_symbol, m_tf, bar_time, true);
      if(sh < 1)
         return false;
      return BuildSnapshotAtShift(snap, sh);
     }

private:
   bool BuildSnapshotAtShift(VantageTechnicalSnap &snap, const int sh)
     {
      ZeroMemory(snap);
      if(sh < 1)
         return false;
      MqlRates rates[];
      if(CopyRates(m_symbol, m_tf, sh, 3, rates) < 3)
         return false;
      // rates[0] is oldest of the 3 when ArraySetAsSeries false by default... CopyRates returns oldest-first
      // With start_pos=1 count=3: index 0 = bar shift 3? Actually CopyRates(symbol,tf,start,count)
      // start_pos is the index from present: 0=current. So start=1,count=3 => bars 1,2,3 oldest-first: rates[0]=bar3, rates[2]=bar1
      ArraySetAsSeries(rates, true);
      // After series: rates[0] = shift 1 (last closed)

      snap.open  = rates[0].open;
      snap.high  = rates[0].high;
      snap.low   = rates[0].low;
      snap.close = rates[0].close;
      snap.volume = (double)rates[0].tick_volume;
      snap.candle_time = rates[0].time;

      if(!Copy1(m_hEma20, 0, sh, snap.ema20)) return false;
      if(!Copy1(m_hEma50, 0, sh, snap.ema50)) return false;
      if(!Copy1(m_hEma200, 0, sh, snap.ema200)) return false;
      if(!Copy1(m_hBB, 1, sh, snap.bb_upper)) return false;   // 1=upper in iBands
      if(!Copy1(m_hBB, 0, sh, snap.bb_middle)) return false;  // 0=base
      if(!Copy1(m_hBB, 2, sh, snap.bb_lower)) return false;   // 2=lower
      if(!Copy1(m_hRsi, 0, sh, snap.rsi14)) return false;
      if(!Copy1(m_hAtr, 0, sh, snap.atr14)) return false;

      // Volume SMA of closed bars
      long vols[];
      if(CopyTickVolume(m_symbol, m_tf, sh, 20, vols) == 20)
        {
         double s = 0.0;
         for(int i = 0; i < 20; i++) s += (double)vols[i];
         snap.volume_sma = s / 20.0;
        }

      double range = snap.high - snap.low;
      double body  = MathAbs(snap.close - snap.open);
      snap.oversized_candle = (snap.atr14 > 0.0) &&
                              ((range > snap.atr14 * m_lvl.oversized_range_atr) ||
                               (body  > snap.atr14 * m_lvl.oversized_body_atr));

      // Support breaks across configured ladder (closed candle)
      double ladder[6];
      ladder[0] = m_lvl.imm_resist;
      ladder[1] = m_lvl.imm_sup_hi;
      ladder[2] = m_lvl.imm_sup_lo;
      ladder[3] = m_lvl.maj_buy_hi;
      ladder[4] = m_lvl.maj_buy_lo;
      ladder[5] = m_lvl.sec_support;
      int broken = 0;
      double lowest_broken = 0.0;
      for(int i = 0; i < 6; i++)
        {
         if(snap.open >= ladder[i] && snap.close < ladder[i])
           {
            broken++;
            if(lowest_broken == 0.0 || ladder[i] < lowest_broken)
               lowest_broken = ladder[i];
           }
        }
      snap.support_break = (broken >= 1);
      if(snap.support_break)
        {
         m_last_broken = lowest_broken;
         m_retest_pending = true;
         if(snap.oversized_candle || broken > 1)
            snap.structure_note = (broken > 1) ? "MULTI_LEVEL_BEARISH_IMPULSE" : "BEARISH_IMPULSE_WAIT_RETEST";
         else
            snap.structure_note = "SUPPORT_BREAK";
        }
      if(m_last_broken > 0.0 && snap.close > m_last_broken + m_lvl.retest_tol)
        {
         m_retest_pending = false;
         m_last_broken = 0.0;
        }
      snap.retest_pending = m_retest_pending;

      // Rejection patterns on closed candle
      double upper_wick = snap.high - MathMax(snap.open, snap.close);
      double lower_wick = MathMin(snap.open, snap.close) - snap.low;
      snap.bear_reject = (upper_wick > body && snap.close < snap.open);
      snap.bull_reject = (lower_wick > body && snap.close > snap.open);

      // Trend score + indicator bias %
      int bull = 0, bear = 0;
      if(snap.close > snap.ema20) bull++; else bear++;
      if(snap.ema20 > snap.ema50) bull++; else bear++;
      if(snap.close > snap.bb_middle) bull++; else bear++;
      if(snap.rsi14 > 50.0) bull++; else bear++;
      if(snap.close > snap.ema200) bull++; else bear++;
      const int votes = bull + bear;
      snap.indicator_bullish_pct = (votes > 0) ? (100.0 * bull / votes) : 50.0;
      snap.indicator_bearish_pct = (votes > 0) ? (100.0 * bear / votes) : 50.0;
      if(bull >= m_lvl.trend_need && bull > bear) snap.trend = VTREND_BULLISH;
      else if(bear >= m_lvl.trend_need && bear > bull) snap.trend = VTREND_BEARISH;
      else snap.trend = VTREND_NEUTRAL;

      // Chart candle bias % over lookback closed bars (shift 1+)
      int lookback = m_lvl.bias_lookback;
      if(lookback < 5) lookback = 20;
      if(lookback > 200) lookback = 200;
      snap.bias_lookback = lookback;
      MqlRates hist[];
      int got = CopyRates(m_symbol, m_tf, sh, lookback, hist);
      int bull_c = 0, bear_c = 0, flat_c = 0;
      if(got > 0)
        {
         for(int i = 0; i < got; i++)
           {
            if(hist[i].close > hist[i].open) bull_c++;
            else if(hist[i].close < hist[i].open) bear_c++;
            else flat_c++;
           }
         double denom = (double)got;
         snap.bullish_pct = 100.0 * bull_c / denom;
         snap.bearish_pct = 100.0 * bear_c / denom;
         snap.neutral_pct = 100.0 * flat_c / denom;
         snap.bias_lookback = got;
        }
      else
        {
         snap.bullish_pct = snap.indicator_bullish_pct;
         snap.bearish_pct = snap.indicator_bearish_pct;
         snap.neutral_pct = 0.0;
        }

      snap.nearest_support_price = NearestBelow(snap.close);
      snap.nearest_resistance_price = NearestAbove(snap.close);
      int digs = (int)SymbolInfoInteger(m_symbol, SYMBOL_DIGITS);
      snap.nearest_support = (snap.nearest_support_price > 0.0) ? DoubleToString(snap.nearest_support_price, digs) : "n/a";
      snap.nearest_resistance = (snap.nearest_resistance_price > 0.0) ? DoubleToString(snap.nearest_resistance_price, digs) : "n/a";

      if(snap.structure_note == "" && snap.retest_pending)
         snap.structure_note = "WAIT_FOR_RETEST";
      if(snap.structure_note == "" && snap.rsi14 <= m_lvl.rsi_exhaust && snap.trend == VTREND_BEARISH)
         snap.structure_note = "BEARISH_WAIT_PULLBACK";
      return true;
     }

public:
   string TrendName(const ENUM_VANTAGE_TREND t) const
     {
      if(t == VTREND_BULLISH) return "BULLISH";
      if(t == VTREND_BEARISH) return "BEARISH";
      return "NEUTRAL";
     }
  };

#endif
//+------------------------------------------------------------------+
