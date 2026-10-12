//+------------------------------------------------------------------+
//| VantagePullback.mqh                                              |
//| Pullback Probability Analyzer — H1 / M15 / M5                    |
//| Advisory-only — never opens, modifies, or closes trades          |
//+------------------------------------------------------------------+
#ifndef VANTAGE_PULLBACK_MQH
#define VANTAGE_PULLBACK_MQH

#include "VantageTypes.mqh"

struct VantagePullbackConfig
  {
   ENUM_TIMEFRAMES tf_h1;
   ENUM_TIMEFRAMES tf_m15;
   ENUM_TIMEFRAMES tf_m5;
   int    ema_fast;
   int    ema_slow;
   int    ema_long;
   int    rsi_period;
   double rsi_ob;
   double rsi_os;
   int    atr_period;
   int    bb_period;
   double bb_dev;
   int    adx_period;
   double adx_min;
   int    swing_left;
   int    swing_right;
   // Weights (sum ~100 for pullback factors; used as relative)
   double w_rsi_extreme;
   double w_rsi_recovery;
   double w_extension;
   double w_bb;
   double w_ema_dist;
   double w_candle;
   double w_divergence;
   double w_sr;
   double w_structure;
   double w_adx_fall;
   double w_mtf;
   // Alerts
   bool   alert_popup;
   bool   alert_push;
   bool   alert_sound;
   double thr_pullback;
   double thr_continuation;
   double thr_reversal;
   double thr_extension;
   int    alert_cooldown_sec;
   int    server_utc_offset_hours;
   bool   show_chart_objects;
   bool   show_hlines;
   bool   show_dashboard;
  };

struct VantagePullbackTfSnap
  {
   ENUM_TIMEFRAMES timeframe;
   bool   valid;
   double close_px;
   datetime bar_time;
   double ema_fast;
   double ema_slow;
   double ema_long;
   double ema_fast_prev;
   double ema_slow_prev;
   double rsi;
   double rsi_prev;
   double adx;
   double adx_prev;
   double plus_di;
   double minus_di;
   double atr;
   double bb_upper;
   double bb_middle;
   double bb_lower;
   double bb_width;
   double extension;      // 0-100
   int    trend_dir;      // 1 bull, -1 bear, 0 neutral
   string trend_label;    // Strong Bullish ... Strong Bearish / Neutral
   double trend_strength; // 0-100
   bool   bullish_structure;
   bool   bearish_structure;
   bool   bos;
   bool   choch;
   double swing_high;
   double swing_low;
   bool   rsi_div_bull;
   bool   rsi_div_bear;
   bool   candle_reject_bull;
   bool   candle_reject_bear;
   bool   bb_outside_then_in;
   int    consec_dir;
  };

struct VantagePullbackResult
  {
   bool   valid;
   bool   insufficient_data;
   int    dominant_dir;          // 1 / -1 / 0
   string dominant_trend;        // Strong Bearish etc.
   double pullback_prob;
   double continuation_prob;
   double consolidation_prob;
   double reversal_prob;
   double extension_score;
   double pullback_quality;
   double trend_strength_score;
   string market_state;
   string explanation;
   string short_reason;
   double nearest_support;
   double nearest_resistance;
   double pullback_target_lo;
   double pullback_target_hi;
   double invalidation;
   string reasons_pos;           // semicolon-separated
   string reasons_neg;
   datetime eval_bar_m5;
   string session_note;
  };

class CVantagePullback
  {
private:
   string               m_symbol;
   VantagePullbackConfig m_cfg;
   VantagePullbackResult m_last;
   datetime             m_last_m5_bar;
   datetime             m_last_alert_time;
   string               m_last_alert_key;
   string               m_obj_prefix;

   // Handles: [0]=H1 [1]=M15 [2]=M5
   int m_hEmaF[3], m_hEmaS[3], m_hEmaL[3];
   int m_hRsi[3], m_hAtr[3], m_hBb[3], m_hAdx[3];

   void Rel(int &h)
     {
      if(h != INVALID_HANDLE) { IndicatorRelease(h); h = INVALID_HANDLE; }
     }

   bool Copy1(const int handle, const int buf, const int shift, double &out_v)
     {
      out_v = 0.0;
      if(handle == INVALID_HANDLE) return false;
      double a[];
      if(CopyBuffer(handle, buf, shift, 1, a) != 1) return false;
      out_v = a[0];
      return MathIsValidNumber(out_v);
     }

   ENUM_TIMEFRAMES TfAt(const int idx)
     {
      if(idx == 0) return m_cfg.tf_h1;
      if(idx == 1) return m_cfg.tf_m15;
      return m_cfg.tf_m5;
     }

   bool ClosedBar(const ENUM_TIMEFRAMES tf, MqlRates &out_r)
     {
      MqlRates r[];
      if(CopyRates(m_symbol, tf, 1, 1, r) != 1) return false;
      out_r = r[0];
      return (out_r.close > 0.0);
     }

   double Clamp(const double v, const double lo, const double hi)
     {
      if(v < lo) return lo;
      if(v > hi) return hi;
      return v;
     }

   int DetectSwings(const ENUM_TIMEFRAMES tf, double &out_hi, double &out_lo,
                    bool &bull_struct, bool &bear_struct, bool &bos, bool &choch)
     {
      out_hi = 0; out_lo = 0;
      bull_struct = false; bear_struct = false; bos = false; choch = false;
      const int need = m_cfg.swing_left + m_cfg.swing_right + 30;
      MqlRates rates[];
      int n = CopyRates(m_symbol, tf, 1, need, rates);
      if(n < m_cfg.swing_left + m_cfg.swing_right + 5)
         return 0;
      // rates[0] = oldest when copied ascending? CopyRates with start_pos=1 returns newest-first by default
      // Force series as time ascending for swing scan: reverse index mentally — ArraySetAsSeries
      ArraySetAsSeries(rates, true); // index 0 = newest closed (shift 1)

      double sh[8], sl[8];
      int nh = 0, nl = 0;
      // series: index 0 = newest; left(older)=+k, right(newer)=-k
      for(int i = m_cfg.swing_right; i < n - m_cfg.swing_left && (nh < 8 || nl < 8); i++)
        {
         bool is_hi = true, is_lo = true;
         for(int k = 1; k <= m_cfg.swing_left; k++)
           {
            if(rates[i].high < rates[i + k].high) is_hi = false;
            if(rates[i].low > rates[i + k].low) is_lo = false;
           }
         for(int k = 1; k <= m_cfg.swing_right; k++)
           {
            if(rates[i].high <= rates[i - k].high) is_hi = false;
            if(rates[i].low >= rates[i - k].low) is_lo = false;
           }
         if(is_hi && nh < 8) sh[nh++] = rates[i].high;
         if(is_lo && nl < 8) sl[nl++] = rates[i].low;
        }
      if(nh >= 1) out_hi = sh[0];
      if(nl >= 1) out_lo = sl[0];
      if(nh >= 2 && nl >= 2)
        {
         // series: [0]=most recent swing
         bool hh = sh[0] > sh[1];
         bool hl = sl[0] > sl[1];
         bool lh = sh[0] < sh[1];
         bool ll = sl[0] < sl[1];
         bull_struct = (hh && hl);
         bear_struct = (lh && ll);
         // BOS/CHoCH vs last structure
         double c = rates[0].close;
         if(bear_struct && c > sh[0]) { bos = true; choch = true; }
         if(bull_struct && c < sl[0]) { bos = true; choch = true; }
        }
      return nh + nl;
     }

   void DetectCandleReject(const ENUM_TIMEFRAMES tf, bool &bull, bool &bear)
     {
      bull = false; bear = false;
      MqlRates r[];
      if(CopyRates(m_symbol, tf, 1, 2, r) < 1) return;
      ArraySetAsSeries(r, true);
      double range = r[0].high - r[0].low;
      if(range <= 0) return;
      double body = MathAbs(r[0].close - r[0].open);
      double upper = r[0].high - MathMax(r[0].open, r[0].close);
      double lower = MathMin(r[0].open, r[0].close) - r[0].low;
      // Pin / long wick
      if(lower >= range * 0.55 && body <= range * 0.35) bull = true;
      if(upper >= range * 0.55 && body <= range * 0.35) bear = true;
      // Engulfing vs previous
      if(ArraySize(r) >= 2)
        {
         bool prev_bear = r[1].close < r[1].open;
         bool prev_bull = r[1].close > r[1].open;
         if(prev_bear && r[0].close > r[0].open &&
            r[0].close >= r[1].open && r[0].open <= r[1].close)
            bull = true;
         if(prev_bull && r[0].close < r[0].open &&
            r[0].close <= r[1].open && r[0].open >= r[1].close)
            bear = true;
        }
     }

   void DetectRsiDiv(const ENUM_TIMEFRAMES tf, const int h_rsi,
                     bool &bull_div, bool &bear_div)
     {
      bull_div = false; bear_div = false;
      MqlRates rates[];
      double rsi[];
      int n = 40;
      if(CopyRates(m_symbol, tf, 1, n, rates) < n) return;
      if(CopyBuffer(h_rsi, 0, 1, n, rsi) < n) return;
      ArraySetAsSeries(rates, true);
      ArraySetAsSeries(rsi, true);
      // Simple: compare last 15 vs prior 15 extremes
      double p_lo1 = rates[0].low, p_lo2 = rates[15].low;
      double p_hi1 = rates[0].high, p_hi2 = rates[15].high;
      for(int i = 1; i < 15; i++)
        {
         if(rates[i].low < p_lo1) p_lo1 = rates[i].low;
         if(rates[i].high > p_hi1) p_hi1 = rates[i].high;
         if(rates[i + 15].low < p_lo2) p_lo2 = rates[i + 15].low;
         if(rates[i + 15].high > p_hi2) p_hi2 = rates[i + 15].high;
        }
      double r_lo1 = rsi[0], r_lo2 = rsi[15], r_hi1 = rsi[0], r_hi2 = rsi[15];
      for(int i = 1; i < 15; i++)
        {
         if(rsi[i] < r_lo1) r_lo1 = rsi[i];
         if(rsi[i] > r_hi1) r_hi1 = rsi[i];
         if(rsi[i + 15] < r_lo2) r_lo2 = rsi[i + 15];
         if(rsi[i + 15] > r_hi2) r_hi2 = rsi[i + 15];
        }
      if(p_lo1 < p_lo2 && r_lo1 > r_lo2) bull_div = true;
      if(p_hi1 > p_hi2 && r_hi1 < r_hi2) bear_div = true;
     }

   bool FillTf(const int idx, VantagePullbackTfSnap &s)
     {
      ZeroMemory(s);
      s.timeframe = TfAt(idx);
      s.valid = false;
      MqlRates bar;
      if(!ClosedBar(s.timeframe, bar)) return false;
      s.close_px = bar.close;
      s.bar_time = bar.time;
      if(!Copy1(m_hEmaF[idx], 0, 1, s.ema_fast)) return false;
      if(!Copy1(m_hEmaS[idx], 0, 1, s.ema_slow)) return false;
      if(!Copy1(m_hEmaL[idx], 0, 1, s.ema_long)) return false;
      Copy1(m_hEmaF[idx], 0, 2, s.ema_fast_prev);
      Copy1(m_hEmaS[idx], 0, 2, s.ema_slow_prev);
      if(!Copy1(m_hRsi[idx], 0, 1, s.rsi)) return false;
      Copy1(m_hRsi[idx], 0, 2, s.rsi_prev);
      if(!Copy1(m_hAtr[idx], 0, 1, s.atr) || s.atr <= 0) return false;
      // BB: 0 upper, 1 middle, 2 lower
      if(!Copy1(m_hBb[idx], 0, 1, s.bb_upper)) return false;
      if(!Copy1(m_hBb[idx], 1, 1, s.bb_middle)) return false;
      if(!Copy1(m_hBb[idx], 2, 1, s.bb_lower)) return false;
      s.bb_width = (s.bb_middle > 0) ? (s.bb_upper - s.bb_lower) / s.bb_middle : 0;
      // ADX: 0=ADX main, 1=+DI, 2=-DI (iADX)
      Copy1(m_hAdx[idx], 0, 1, s.adx);
      Copy1(m_hAdx[idx], 0, 2, s.adx_prev);
      Copy1(m_hAdx[idx], 1, 1, s.plus_di);
      Copy1(m_hAdx[idx], 2, 1, s.minus_di);

      // Extension ATR-normalized
      double d20 = MathAbs(s.close_px - s.ema_fast) / s.atr;
      double d50 = MathAbs(s.close_px - s.ema_slow) / s.atr;
      double dbb = MathAbs(s.close_px - s.bb_middle) / s.atr;
      double ext_raw = (d20 * 0.45 + d50 * 0.25 + dbb * 0.30) * 28.0;
      if(s.close_px <= s.bb_lower || s.close_px >= s.bb_upper)
         ext_raw += 12.0;
      s.extension = Clamp(ext_raw, 0, 100);

      // Consec directional
      MqlRates hist[];
      s.consec_dir = 0;
      if(CopyRates(m_symbol, s.timeframe, 1, 8, hist) >= 4)
        {
         ArraySetAsSeries(hist, true);
         int dir = (hist[0].close < hist[0].open) ? -1 : 1;
         int c = 0;
         for(int i = 0; i < 8; i++)
           {
            int d = (hist[i].close < hist[i].open) ? -1 : ((hist[i].close > hist[i].open) ? 1 : 0);
            if(d == dir && d != 0) c++; else break;
           }
         s.consec_dir = c * dir;
        }

      // BB outside then in
      MqlRates b2[];
      if(CopyRates(m_symbol, s.timeframe, 1, 2, b2) == 2)
        {
         ArraySetAsSeries(b2, true);
         double bu1, bl1;
         Copy1(m_hBb[idx], 0, 2, bu1);
         Copy1(m_hBb[idx], 2, 2, bl1);
         bool out_prev = (b2[1].close < bl1 || b2[1].close > bu1);
         bool in_now = (b2[0].close >= s.bb_lower && b2[0].close <= s.bb_upper);
         s.bb_outside_then_in = (out_prev && in_now);
        }

      DetectSwings(s.timeframe, s.swing_high, s.swing_low,
                   s.bullish_structure, s.bearish_structure, s.bos, s.choch);
      DetectCandleReject(s.timeframe, s.candle_reject_bull, s.candle_reject_bear);
      DetectRsiDiv(s.timeframe, m_hRsi[idx], s.rsi_div_bull, s.rsi_div_bear);

      // Trend classification
      bool stack_bull = (s.ema_fast > s.ema_slow && s.ema_slow > s.ema_long);
      bool stack_bear = (s.ema_fast < s.ema_slow && s.ema_slow < s.ema_long);
      bool slope_bull = (s.ema_fast > s.ema_fast_prev && s.ema_slow >= s.ema_slow_prev);
      bool slope_bear = (s.ema_fast < s.ema_fast_prev && s.ema_slow <= s.ema_slow_prev);
      bool px_bull = (s.close_px > s.ema_fast && s.close_px > s.ema_slow);
      bool px_bear = (s.close_px < s.ema_fast && s.close_px < s.ema_slow);
      bool di_bull = (s.plus_di > s.minus_di);
      bool di_bear = (s.minus_di > s.plus_di);
      int score = 0;
      if(stack_bull) score += 2; if(stack_bear) score -= 2;
      if(slope_bull) score += 1; if(slope_bear) score -= 1;
      if(px_bull) score += 1; if(px_bear) score -= 1;
      if(s.bullish_structure) score += 1; if(s.bearish_structure) score -= 1;
      if(di_bull) score += 1; if(di_bear) score -= 1;
      if(s.adx >= m_cfg.adx_min) score += (score > 0 ? 1 : (score < 0 ? -1 : 0));

      if(score >= 5) { s.trend_dir = 1; s.trend_label = "Strong Bullish"; }
      else if(score >= 3) { s.trend_dir = 1; s.trend_label = "Moderate Bullish"; }
      else if(score >= 1) { s.trend_dir = 1; s.trend_label = "Weak Bullish"; }
      else if(score <= -5) { s.trend_dir = -1; s.trend_label = "Strong Bearish"; }
      else if(score <= -3) { s.trend_dir = -1; s.trend_label = "Moderate Bearish"; }
      else if(score <= -1) { s.trend_dir = -1; s.trend_label = "Weak Bearish"; }
      else { s.trend_dir = 0; s.trend_label = "Neutral"; }

      s.trend_strength = Clamp(s.adx * 2.0 + MathAbs(score) * 6.0, 0, 100);
      s.valid = true;
      return true;
     }

   string SessionNote(void)
     {
      datetime utc = TimeGMT();
      MqlDateTime dt;
      TimeToStruct(utc, dt);
      int h = dt.hour;
      if(h >= 0 && h < 7) return "Asian session";
      if(h >= 7 && h < 12) return "London session";
      if(h >= 12 && h < 16) return "London-NY overlap";
      if(h >= 16 && h < 21) return "New York session";
      return "Off-peak hours";
     }

   void Normalize4(double &a, double &b, double &c, double &d)
     {
      a = MathMax(0, a); b = MathMax(0, b); c = MathMax(0, c); d = MathMax(0, d);
      double sum = a + b + c + d;
      if(sum <= 0.0001)
        {
         a = 25; b = 25; c = 25; d = 25;
         return;
        }
      a = MathRound(a * 100.0 / sum);
      b = MathRound(b * 100.0 / sum);
      c = MathRound(c * 100.0 / sum);
      d = MathRound(d * 100.0 / sum);
      int tot = (int)(a + b + c + d);
      int rem = 100 - tot;
      if(rem != 0)
        {
         if(a >= b && a >= c && a >= d) a += rem;
         else if(b >= a && b >= c && b >= d) b += rem;
         else if(c >= a && c >= b && c >= d) c += rem;
         else d += rem;
        }
     }

   string MapState(const VantagePullbackResult &r, const bool conflict, const bool chase)
     {
      if(r.insufficient_data) return "INSUFFICIENT DATA";
      if(conflict) return "CONFLICTING TIMEFRAMES";
      if(r.reversal_prob >= 65) return "REVERSAL CONFIRMED";
      if(r.reversal_prob >= m_cfg.thr_reversal) return "POSSIBLE REVERSAL – UNCONFIRMED";
      if(chase || r.extension_score >= m_cfg.thr_extension)
         return "DO NOT CHASE – MARKET EXTENDED";
      if(r.consolidation_prob >= 40) return "CONSOLIDATION";
      if(r.pullback_prob >= 55 && r.pullback_quality >= 50)
         return "PULLBACK DEVELOPING";
      if(r.pullback_prob >= m_cfg.thr_pullback)
         return "TREND ACTIVE – WAIT FOR PULLBACK";
      if(r.continuation_prob >= m_cfg.thr_continuation)
         return "STRONG TREND – CONTINUATION FAVORED";
      if(r.pullback_prob >= 40 && r.continuation_prob >= 35)
         return "TREND RESUMPTION POSSIBLE";
      return "NO TRADE / WAIT";
     }

   void DeleteChartObjects(void)
     {
      int total = ObjectsTotal(0, 0, -1);
      for(int i = total - 1; i >= 0; i--)
        {
         string name = ObjectName(0, i, 0, -1);
         if(StringFind(name, m_obj_prefix) == 0)
            ObjectDelete(0, name);
        }
     }

   void SetHLine(const string key, const double price, const color clr, const string text)
     {
      if(!m_cfg.show_hlines)
        {
         string drop = m_obj_prefix + key;
         if(ObjectFind(0, drop) >= 0) ObjectDelete(0, drop);
         return;
        }
      string id = m_obj_prefix + key;
      if(price <= 0) { if(ObjectFind(0, id) >= 0) ObjectDelete(0, id); return; }
      if(ObjectFind(0, id) < 0)
        {
         ObjectCreate(0, id, OBJ_HLINE, 0, 0, price);
         ObjectSetInteger(0, id, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, id, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, id, OBJPROP_WIDTH, 1);
         ObjectSetInteger(0, id, OBJPROP_STYLE, STYLE_DOT);
        }
      ObjectSetDouble(0, id, OBJPROP_PRICE, price);
      ObjectSetInteger(0, id, OBJPROP_COLOR, clr);
      ObjectSetString(0, id, OBJPROP_TEXT, text);
     }

public:
   CVantagePullback(void) : m_symbol(""), m_last_m5_bar(0), m_last_alert_time(0),
                            m_obj_prefix("VAI_PB_")
     {
      for(int i = 0; i < 3; i++)
        {
         m_hEmaF[i] = m_hEmaS[i] = m_hEmaL[i] = INVALID_HANDLE;
         m_hRsi[i] = m_hAtr[i] = m_hBb[i] = m_hAdx[i] = INVALID_HANDLE;
        }
      ZeroMemory(m_last);
      ZeroMemory(m_cfg);
     }

   void Release(void)
     {
      for(int i = 0; i < 3; i++)
        {
         Rel(m_hEmaF[i]); Rel(m_hEmaS[i]); Rel(m_hEmaL[i]);
         Rel(m_hRsi[i]); Rel(m_hAtr[i]); Rel(m_hBb[i]); Rel(m_hAdx[i]);
        }
      DeleteChartObjects();
     }

   bool Init(const string symbol, const VantagePullbackConfig &cfg)
     {
      Release();
      m_symbol = symbol;
      m_cfg = cfg;
      if(m_cfg.tf_h1 == PERIOD_CURRENT) m_cfg.tf_h1 = PERIOD_H1;
      if(m_cfg.tf_m15 == PERIOD_CURRENT) m_cfg.tf_m15 = PERIOD_M15;
      if(m_cfg.tf_m5 == PERIOD_CURRENT) m_cfg.tf_m5 = PERIOD_M5;

      for(int i = 0; i < 3; i++)
        {
         ENUM_TIMEFRAMES tf = TfAt(i);
         m_hEmaF[i] = iMA(m_symbol, tf, m_cfg.ema_fast, 0, MODE_EMA, PRICE_CLOSE);
         m_hEmaS[i] = iMA(m_symbol, tf, m_cfg.ema_slow, 0, MODE_EMA, PRICE_CLOSE);
         m_hEmaL[i] = iMA(m_symbol, tf, m_cfg.ema_long, 0, MODE_EMA, PRICE_CLOSE);
         m_hRsi[i]  = iRSI(m_symbol, tf, m_cfg.rsi_period, PRICE_CLOSE);
         m_hAtr[i]  = iATR(m_symbol, tf, m_cfg.atr_period);
         m_hBb[i]   = iBands(m_symbol, tf, m_cfg.bb_period, 0, m_cfg.bb_dev, PRICE_CLOSE);
         m_hAdx[i]  = iADX(m_symbol, tf, m_cfg.adx_period);
         if(m_hEmaF[i] == INVALID_HANDLE || m_hEmaS[i] == INVALID_HANDLE ||
            m_hEmaL[i] == INVALID_HANDLE || m_hRsi[i] == INVALID_HANDLE ||
            m_hAtr[i] == INVALID_HANDLE || m_hBb[i] == INVALID_HANDLE ||
            m_hAdx[i] == INVALID_HANDLE)
           {
            Print("[VantageAI] Pullback indicator init failed tf=", EnumToString(tf));
            Release();
            return false;
           }
        }
      Print("[VantageAI] Pullback Probability Analyzer enabled (H1/M15/M5).");
      return true;
     }

   VantagePullbackResult Last(void) const { return m_last; }

   bool Evaluate(const bool force, VantagePullbackResult &out)
     {
      ZeroMemory(out);
      out.valid = false;
      MqlRates m5;
      if(!ClosedBar(m_cfg.tf_m5, m5))
        {
         out.insufficient_data = true;
         out.market_state = "INSUFFICIENT DATA";
         out.explanation = "Waiting for confirmed M5 history.";
         m_last = out;
         return false;
        }
      if(!force && m5.time == m_last_m5_bar && m_last.valid)
        {
         out = m_last;
         return true;
        }

      VantagePullbackTfSnap h1, m15, m5s;
      if(!FillTf(0, h1) || !FillTf(1, m15) || !FillTf(2, m5s))
        {
         out.insufficient_data = true;
         out.market_state = "INSUFFICIENT DATA";
         out.explanation = "Insufficient multi-timeframe indicator history.";
         m_last = out;
         return false;
        }

      // Dominant trend: H1 weighted highest
      int dom = 0;
      double wsum = h1.trend_dir * 3.0 + m15.trend_dir * 2.0 + m5s.trend_dir * 1.0;
      if(wsum >= 2) dom = 1;
      else if(wsum <= -2) dom = -1;
      else dom = h1.trend_dir != 0 ? h1.trend_dir : m15.trend_dir;

      bool conflict = (h1.trend_dir != 0 && m15.trend_dir != 0 && h1.trend_dir != m15.trend_dir);
      out.dominant_dir = dom;
      if(dom > 0) out.dominant_trend = h1.trend_label;
      else if(dom < 0) out.dominant_trend = h1.trend_label;
      else out.dominant_trend = "Neutral";
      if(StringFind(out.dominant_trend, "Bull") < 0 && StringFind(out.dominant_trend, "Bear") < 0)
         out.dominant_trend = (dom > 0 ? "Moderate Bullish" : (dom < 0 ? "Moderate Bearish" : "Neutral"));

      out.extension_score = Clamp(m15.extension * 0.55 + m5s.extension * 0.45, 0, 100);
      out.trend_strength_score = Clamp(h1.trend_strength * 0.5 + m15.trend_strength * 0.35 + m5s.trend_strength * 0.15, 0, 100);

      // --- Raw probability vectors ---
      double pb = 10, cont = 10, cons = 10, rev = 5;
      string pos = "", neg = "";

      // MTF alignment
      bool aligned = (h1.trend_dir == m15.trend_dir && h1.trend_dir != 0);
      if(aligned)
        {
         cont += m_cfg.w_mtf;
         pos += "H1 and M15 trend alignment;";
        }
      else if(conflict)
        {
         cons += m_cfg.w_mtf * 0.6;
         rev += m_cfg.w_mtf * 0.2;
         neg += "H1 vs M15 conflict;";
        }

      // Extension → pullback (do not chase)
      if(out.extension_score >= 50)
        {
         pb += m_cfg.w_extension * (out.extension_score / 100.0);
         pos += "ATR-normalized price extension;";
        }
      else
         cont += m_cfg.w_extension * 0.35;

      // RSI extremes against trend = pullback, not reversal
      bool m15_os = (m15.rsi <= m_cfg.rsi_os);
      bool m15_ob = (m15.rsi >= m_cfg.rsi_ob);
      bool m5_os = (m5s.rsi <= m_cfg.rsi_os);
      bool m5_ob = (m5s.rsi >= m_cfg.rsi_ob);
      if(dom < 0 && (m15_os || m5_os))
        {
         pb += m_cfg.w_rsi_extreme;
         pos += "RSI oversold on lower TF (bearish trend — pullback risk, not auto-buy);";
         if(m15.rsi > m15.rsi_prev) pb += m_cfg.w_rsi_recovery * 0.7;
        }
      else if(dom > 0 && (m15_ob || m5_ob))
        {
         pb += m_cfg.w_rsi_extreme;
         pos += "RSI overbought on lower TF (bullish trend — pullback risk, not auto-sell);";
         if(m15.rsi < m15.rsi_prev) pb += m_cfg.w_rsi_recovery * 0.7;
        }
      else if(m15.rsi > 45 && m15.rsi < 55)
         cons += m_cfg.w_rsi_extreme * 0.5;

      // Momentum on trend side of 50 → continuation
      if(dom < 0 && m15.rsi < 50 && m15.rsi > m_cfg.rsi_os) cont += m_cfg.w_rsi_recovery * 0.5;
      if(dom > 0 && m15.rsi > 50 && m15.rsi < m_cfg.rsi_ob) cont += m_cfg.w_rsi_recovery * 0.5;

      // Bollinger
      if(m15.bb_outside_then_in || m5s.bb_outside_then_in)
        {
         pb += m_cfg.w_bb;
         pos += "Close returned inside Bollinger Band after outside;";
        }
      if(m15.bb_width < 0.01)
        {
         cons += m_cfg.w_bb * 0.8;
         pos += "Bollinger Band squeeze / contraction;";
        }
      // Walking band continuation
      if(dom < 0 && m5s.close_px <= m5s.bb_lower && m15.adx >= m_cfg.adx_min && m15.adx >= m15.adx_prev)
        {
         cont += m_cfg.w_bb * 0.6;
         neg += "Price walking lower band with rising ADX;";
        }
      if(dom > 0 && m5s.close_px >= m5s.bb_upper && m15.adx >= m_cfg.adx_min && m15.adx >= m15.adx_prev)
        {
         cont += m_cfg.w_bb * 0.6;
         neg += "Price walking upper band with rising ADX;";
        }

      // EMA distance
      double ema_dist = MathAbs(m15.close_px - m15.ema_fast) / m15.atr;
      if(ema_dist >= 1.2)
        {
         pb += m_cfg.w_ema_dist;
         pos += "Price extended from EMA20 (>1.2 ATR);";
        }
      else if(ema_dist < 0.4)
         cont += m_cfg.w_ema_dist * 0.4;

      // Candles
      if(dom < 0 && m5s.candle_reject_bull)
        {
         pb += m_cfg.w_candle;
         pos += "Bullish rejection candle on M5;";
        }
      if(dom > 0 && m5s.candle_reject_bear)
        {
         pb += m_cfg.w_candle;
         pos += "Bearish rejection candle on M5;";
        }

      // Divergence — supporting only
      if(dom < 0 && (m15.rsi_div_bull || m5s.rsi_div_bull))
        {
         pb += m_cfg.w_divergence * 0.6;
         rev += m_cfg.w_divergence * 0.4;
         pos += "Bullish RSI divergence (supporting);";
        }
      if(dom > 0 && (m15.rsi_div_bear || m5s.rsi_div_bear))
        {
         pb += m_cfg.w_divergence * 0.6;
         rev += m_cfg.w_divergence * 0.4;
         pos += "Bearish RSI divergence (supporting);";
        }

      // Structure / BOS / CHoCH — reversal needs HTF
      if(m5s.bos && !m15.choch && !h1.choch)
        {
         pb += m_cfg.w_structure * 0.7;
         pos += "M5 structure shift only (treat as pullback, not HTF reversal);";
         neg += "No confirmed M15/H1 structure break;";
        }
      if(m15.choch || h1.choch)
        {
         rev += m_cfg.w_structure;
         pos += "Higher-timeframe Change of Character / BOS;";
        }
      else
         neg += "No confirmed higher-timeframe structure break;";

      if((dom < 0 && m15.bearish_structure) || (dom > 0 && m15.bullish_structure))
         cont += m_cfg.w_structure * 0.4;

      // ADX
      if(m15.adx >= 25 && m15.adx >= m15.adx_prev)
        {
         cont += m_cfg.w_adx_fall;
         neg += "ADX strong and rising;";
        }
      else if(m15.adx >= 20 && m15.adx < m15.adx_prev)
        {
         pb += m_cfg.w_adx_fall * 0.6;
         cons += m_cfg.w_adx_fall * 0.4;
         pos += "ADX high but falling (momentum softening);";
        }
      else if(m15.adx < 20)
        {
         cons += m_cfg.w_adx_fall;
         pos += "Low ADX — ranging / weak trend;";
        }

      // S/R proximity
      out.nearest_resistance = (m15.swing_high > 0 ? m15.swing_high : m15.ema_slow);
      out.nearest_support = (m15.swing_low > 0 ? m15.swing_low : m15.ema_slow);
      if(m15.ema_fast > 0)
        {
         if(dom < 0)
           {
            out.pullback_target_lo = MathMin(m15.ema_fast, m15.bb_middle);
            out.pullback_target_hi = MathMax(m15.ema_fast, m15.bb_middle);
            if(m15.swing_high > 0) out.invalidation = m15.swing_high;
            else out.invalidation = m15.ema_slow;
           }
         else if(dom > 0)
           {
            out.pullback_target_lo = MathMin(m15.ema_fast, m15.bb_middle);
            out.pullback_target_hi = MathMax(m15.ema_fast, m15.bb_middle);
            if(m15.swing_low > 0) out.invalidation = m15.swing_low;
            else out.invalidation = m15.ema_slow;
           }
        }
      double room = 0;
      if(dom < 0 && out.nearest_resistance > m15.close_px)
         room = (out.nearest_resistance - m15.close_px) / m15.atr;
      if(dom > 0 && m15.close_px > out.nearest_support && out.nearest_support > 0)
         room = (m15.close_px - out.nearest_support) / m15.atr;
      if(room >= 0.6)
        {
         pb += m_cfg.w_sr * 0.7;
         pos += "Nearby counter-trend S/R allows pullback room;";
        }
      else
         neg += "Limited room to S/R for pullback;";

      // Cap reversal without HTF confirmation
      if(!m15.choch && !h1.choch)
         rev = MathMin(rev, 28.0);

      Normalize4(pb, cont, cons, rev);
      out.pullback_prob = pb;
      out.continuation_prob = cont;
      out.consolidation_prob = cons;
      out.reversal_prob = rev;

      // Pullback quality
      out.pullback_quality = Clamp(
         (m15_os || m15_ob || m5_os || m5_ob ? 20 : 0) +
         (out.extension_score * 0.25) +
         (m15.bb_outside_then_in || m5s.bb_outside_then_in ? 15 : 0) +
         (m5s.candle_reject_bull || m5s.candle_reject_bear ? 12 : 0) +
         (room >= 0.6 ? 10 : 0) +
         (aligned ? 10 : 0), 0, 100);

      bool chase = (out.extension_score >= m_cfg.thr_extension && out.continuation_prob < 55);
      out.market_state = MapState(out, conflict, chase);
      // refine state when pullback confirmed-ish
      if(out.pullback_prob >= 60 && (m5s.candle_reject_bull || m5s.candle_reject_bear) && out.extension_score >= 40)
         if(StringFind(out.market_state, "REVERSAL") < 0)
            out.market_state = "PULLBACK DEVELOPING";

      out.reasons_pos = pos;
      out.reasons_neg = neg;
      out.session_note = SessionNote();
      out.eval_bar_m5 = m5.time;
      out.short_reason = out.market_state;

      // Explanation
      string dir_word = (dom < 0 ? "bearish" : (dom > 0 ? "bullish" : "neutral"));
      out.explanation =
         "Dominant Trend: " + out.dominant_trend + ". " +
         "H1=" + h1.trend_label + ", M15=" + m15.trend_label + ", M5=" + m5s.trend_label + ". " +
         "ADX M15=" + DoubleToString(m15.adx, 1) +
         (m15.adx >= m15.adx_prev ? " rising" : " falling") + ". " +
         "RSI M15=" + DoubleToString(m15.rsi, 1) + ", M5=" + DoubleToString(m5s.rsi, 1) + ". " +
         "Extension score=" + DoubleToString(out.extension_score, 0) + "/100 (ATR-normalized). " +
         "Session: " + out.session_note + ". " +
         "Pullback " + DoubleToString(out.pullback_prob, 0) + "% vs Continuation " +
         DoubleToString(out.continuation_prob, 0) + "%; Reversal " +
         DoubleToString(out.reversal_prob, 0) + "% remains " +
         (out.reversal_prob < 35 ? "low without HTF structure confirmation. " : "elevated with structure evidence. ") +
         "Status: " + out.market_state + ". Advisory only — never executes trades.";

      out.valid = true;
      out.insufficient_data = false;
      m_last = out;
      m_last_m5_bar = m5.time;

      if(m_cfg.show_chart_objects)
         UpdateChart(out);
      MaybeAlert(out);
      return true;
     }

   void UpdateChart(const VantagePullbackResult &r)
     {
      if(!m_cfg.show_chart_objects) return;
      SetHLine("sup", r.nearest_support, clrDodgerBlue, "PB Support");
      SetHLine("res", r.nearest_resistance, clrOrangeRed, "PB Resistance");
      SetHLine("inv", r.invalidation, clrMagenta, "PB Invalidation");
      SetHLine("tlo", r.pullback_target_lo, clrGold, "PB Target Lo");
      SetHLine("thi", r.pullback_target_hi, clrGold, "PB Target Hi");
      ChartRedraw(0);
     }

   void MaybeAlert(const VantagePullbackResult &r)
     {
      if(!r.valid) return;
      string key = "";
      string msg = "";
      if(r.extension_score >= m_cfg.thr_extension)
        { key = "EXT|" + TimeToString(r.eval_bar_m5); msg = "Market extremely extended (" + DoubleToString(r.extension_score, 0) + ")"; }
      else if(r.pullback_prob >= m_cfg.thr_pullback)
        { key = "PB|" + TimeToString(r.eval_bar_m5); msg = "High pullback probability " + DoubleToString(r.pullback_prob, 0) + "% | " + r.market_state; }
      else if(r.continuation_prob >= m_cfg.thr_continuation)
        { key = "CONT|" + TimeToString(r.eval_bar_m5); msg = "High continuation probability " + DoubleToString(r.continuation_prob, 0) + "%"; }
      else if(r.reversal_prob >= m_cfg.thr_reversal)
        { key = "REV|" + TimeToString(r.eval_bar_m5); msg = "Reversal watch " + DoubleToString(r.reversal_prob, 0) + "% — unconfirmed unless HTF structure holds"; }
      if(key == "" || key == m_last_alert_key) return;
      if((TimeCurrent() - m_last_alert_time) < m_cfg.alert_cooldown_sec) return;
      m_last_alert_key = key;
      m_last_alert_time = TimeCurrent();
      string full = "Vantage Pullback: " + msg;
      if(m_cfg.alert_popup) Alert(full);
      if(m_cfg.alert_sound) PlaySound("alert.wav");
      if(m_cfg.alert_push)
        {
         if(!SendNotification(full))
            Print("[VantageAI] Pullback push failed err=", GetLastError());
        }
      Print("[VantageAI] ", full);
     }

   string ToJson(const VantagePullbackResult &r)
     {
      string j = "{";
      j += "\"version\":\"1.0\",";
      j += "\"advisory_only\":true,";
      j += "\"valid\":" + (r.valid ? "true" : "false") + ",";
      j += "\"dominant_direction\":" + IntegerToString(r.dominant_dir) + ",";
      j += "\"dominant_trend\":\"" + JsonEscape(r.dominant_trend) + "\",";
      j += "\"pullback_probability\":" + DoubleToJson(r.pullback_prob, 1) + ",";
      j += "\"continuation_probability\":" + DoubleToJson(r.continuation_prob, 1) + ",";
      j += "\"consolidation_probability\":" + DoubleToJson(r.consolidation_prob, 1) + ",";
      j += "\"reversal_probability\":" + DoubleToJson(r.reversal_prob, 1) + ",";
      j += "\"extension_score\":" + DoubleToJson(r.extension_score, 1) + ",";
      j += "\"pullback_quality\":" + DoubleToJson(r.pullback_quality, 1) + ",";
      j += "\"trend_strength\":" + DoubleToJson(r.trend_strength_score, 1) + ",";
      j += "\"market_state\":\"" + JsonEscape(r.market_state) + "\",";
      j += "\"explanation\":\"" + JsonEscape(r.explanation) + "\",";
      j += "\"short_reason\":\"" + JsonEscape(r.short_reason) + "\",";
      j += "\"nearest_support\":" + DoubleToJson(r.nearest_support, 8) + ",";
      j += "\"nearest_resistance\":" + DoubleToJson(r.nearest_resistance, 8) + ",";
      j += "\"pullback_target_low\":" + DoubleToJson(r.pullback_target_lo, 8) + ",";
      j += "\"pullback_target_high\":" + DoubleToJson(r.pullback_target_hi, 8) + ",";
      j += "\"invalidation\":" + DoubleToJson(r.invalidation, 8) + ",";
      j += "\"reasons_positive\":\"" + JsonEscape(r.reasons_pos) + "\",";
      j += "\"reasons_negative\":\"" + JsonEscape(r.reasons_neg) + "\",";
      j += "\"session\":\"" + JsonEscape(r.session_note) + "\"";
      j += "}";
      return j;
     }
  };

#endif
//+------------------------------------------------------------------+
