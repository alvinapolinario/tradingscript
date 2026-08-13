//+------------------------------------------------------------------+
//| VantagePullbackV2.mqh                                            |
//| Pullback Probability Desk V2 — experimental independent scores   |
//| Advisory-only — never opens, modifies, or closes trades          |
//| Milestone 1: structure, extension, horizon metadata, no Normalize4|
//| Milestone 2: displacement, RSI state, premium/discount, entry location|
//| Milestone 3: liquidity integration (Liquidity Grab + structural fallback)|
//| Milestone 4: FVG / OB integration + POI ranking (Gold SMC + fallback)  |
//| Milestone 5: expected pullback depth, OTE, continuation-after-PB    |
//| Milestone 6: CSV historical logging + calibration metadata           |
//| Milestone 7: calibration bucket report metadata (offline Python)     |
//+------------------------------------------------------------------+
#ifndef VANTAGE_PULLBACK_V2_MQH
#define VANTAGE_PULLBACK_V2_MQH

#include "VantageTypes.mqh"
#include "VantageLiquidityGrabTypes.mqh"
#include "VantageGoldSMCTypes.mqh"

enum PbV2StructureState
  {
   PBV2_STRUCTURE_UNKNOWN = 0,
   PBV2_BULL_CONTINUATION,
   PBV2_BEAR_CONTINUATION,
   PBV2_BULL_PULLBACK,
   PBV2_BEAR_PULLBACK,
   PBV2_BULL_CHOCH,
   PBV2_BEAR_CHOCH,
   PBV2_RANGE
  };

enum PbV2MomentumState
  {
   PBV2_MOM_NEUTRAL = 0,
   PBV2_MOM_CONTINUATION,
   PBV2_MOM_STRONG,
   PBV2_MOM_EXTENDED,
   PBV2_MOM_ROLLOVER,
   PBV2_MOM_DIVERGENCE
  };

enum PbV2LiquidityState
  {
   PBV2_LIQ_NONE = 0,
   PBV2_LIQ_APPROACHING,
   PBV2_LIQ_TOUCHED,
   PBV2_LIQ_SWEPT,
   PBV2_LIQ_REJECTED,
   PBV2_LIQ_ACCEPTED_BEYOND
  };

struct PbV2DisplacementSnap
  {
   double score;
   double body;
   double range;
   double persistence;
   double close_quality;
   double ema_accel;
   double bos;
   double fvg;
  };

struct PbV2DealingRangeSnap
  {
   bool   valid;
   double range_low;
   double range_high;
   double equilibrium;
   double position_pct;
   string location;
   double pd_pressure_score;
  };

struct PbV2MomentumSnap
  {
   PbV2MomentumState state;
   string state_label;
   double rsi_level;
   double rsi_slope;
   double rollover_score;
   double continuation_score;
  };

struct PbV2LiquiditySnap
  {
   bool   valid;
   string draw;
   PbV2LiquidityState state;
   string state_label;
   double target_price;
   string target_label;
   double distance_atr;
   double pullback_pressure;
   double continuation_boost;
   bool   from_liquidity_grab;
  };

struct PbV2PoiCandidate
  {
   bool   valid;
   string type_label;
   string dir_label;
   bool   bullish;
   datetime created;
   double upper;
   double lower;
   double mid;
   double ce;
   double quality;
   double mitigation_pct;
   string status_label;
   ENUM_TIMEFRAMES tf;
   bool   with_fvg;
  };

struct PbV2PoiSnap
  {
   bool   valid;
   string primary_type;
   string primary_dir;
   string status;
   double upper;
   double lower;
   double mid;
   double ce;
   double quality;
   double mitigation_pct;
   double distance_atr;
   double pullback_target_score;
   double confluence_score;
   int    fvg_count;
   int    ob_count;
   bool   from_gold_smc;
   bool   price_inside;
   bool   price_approaching;
  };

struct PbV2OteSnap
  {
   bool   valid;
   double ote_low;
   double ote_mid;
   double ote_high;
   bool   price_in_ote;
   bool   poi_overlaps_ote;
   double alignment_score;
   bool   from_gold_smc;
  };

struct PbV2DepthSnap
  {
   bool   valid;
   double target_low;
   double target_mid;
   double target_high;
   double expected_pullback_atr;
   double fib_retrace_pct;
   string expected_depth;
   string source;
  };

struct VantagePullbackV2Config
  {
   ENUM_TIMEFRAMES tf_h1;
   ENUM_TIMEFRAMES tf_m15;
   ENUM_TIMEFRAMES tf_m5;
   ENUM_TIMEFRAMES horizon_tf;
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
   double pullback_atr_threshold;
   int    prediction_bars;
   double min_mss_displacement;
   double deep_discount_pct;
   double deep_premium_pct;
   double liquidity_approach_atr;
   double liquidity_touch_atr;
   bool   prefer_liquidity_grab;
   bool   prefer_gold_smc_poi;
   double min_fvg_atr;
   int    max_poi_scan;
   double poi_approach_atr;
   bool   enable_ote;
   bool   prefer_gold_smc_ote;
   double ote_low_pct;
   double ote_mid_pct;
   double ote_high_pct;
   bool   csv_log_enable;
   bool   csv_log_v1_shadow;
   string csv_log_prefix;
   bool   show_dashboard;
  };

struct PbV2StructureSnap
  {
   bool   valid;
   bool   hh;
   bool   hl;
   bool   lh;
   bool   ll;
   bool   bullish_bos;
   bool   bearish_bos;
   bool   bullish_choch;
   bool   bearish_choch;
   bool   bullish_mss;
   bool   bearish_mss;
   double swing_high;
   double swing_low;
   double prev_swing_high;
   double prev_swing_low;
   double protected_high;
   double protected_low;
   PbV2StructureState state;
   string state_label;
  };

struct PbV2TfSnap
  {
   ENUM_TIMEFRAMES timeframe;
   bool   valid;
   double close_px;
   datetime bar_time;
   double ema_fast;
   double ema_slow;
   double ema_long;
   double ema_fast_prev;
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
   double extension;
   int    trend_dir;
   string trend_label;
   double trend_strength;
   bool   bb_outside_then_in;
   bool   candle_reject_bull;
   bool   candle_reject_bear;
   bool   rsi_div_bull;
   bool   rsi_div_bear;
   PbV2StructureSnap structure;
  };

struct VantagePullbackV2Snapshot
  {
   bool   valid;
   bool   insufficient_data;
   string symbol;
   datetime evaluated_at;
   int    dominant_dir;
   string dominant_trend;
   double trend_strength;
   double extension_score;
   double displacement_score;
   double entry_location_score;
   double pullback_score;
   double immediate_continuation_score;
   double continuation_after_pullback_score;
   double reversal_risk_score;
   double expected_pullback_atr;
   string expected_depth;
   string market_state;
   string explanation;
   string short_reason;
   string reasons_pos;
   string reasons_neg;
   datetime eval_bar_m5;
   // Horizon / event definition (metadata for calibration; no future bars in live eval)
   ENUM_TIMEFRAMES horizon_tf;
   int    horizon_bars;
   int    horizon_minutes;
   double pullback_threshold_atr;
   string pullback_event_definition;
   // Per-TF structure summary
   string h1_structure;
   string m15_structure;
   string m5_structure;
   bool   bullish_bos;
   bool   bearish_bos;
   bool   bullish_choch;
   bool   bearish_choch;
   bool   bullish_mss;
   bool   bearish_mss;
   double protected_high;
   double protected_low;
   // Milestone 2 — displacement components
   double disp_body;
   double disp_range;
   double disp_persistence;
   double disp_close_quality;
   double disp_ema;
   double disp_bos;
   double disp_fvg;
   // Milestone 2 — momentum
   string momentum_state;
   double rsi_level;
   double rsi_slope;
   // Milestone 2 — premium / discount
   double dealing_range_low;
   double dealing_range_high;
   double range_position_pct;
   string premium_discount_location;
   // Milestone 3 — liquidity
   string liquidity_draw;
   string liquidity_state;
   double liquidity_target_price;
   string liquidity_target_label;
   double liquidity_distance_atr;
   bool   liquidity_from_grab_module;
   // Milestone 4 — POI / FVG / OB
   string poi_primary_type;
   string poi_primary_dir;
   string poi_status;
   double poi_upper;
   double poi_lower;
   double poi_mid;
   double poi_quality;
   double poi_mitigation_pct;
   double poi_distance_atr;
   double poi_pullback_target_score;
   double poi_confluence_score;
   int    poi_fvg_count;
   int    poi_ob_count;
   bool   poi_from_gold_smc;
   bool   poi_price_inside;
   bool   poi_price_approaching;
   // Milestone 5 — OTE / depth
   double ote_low;
   double ote_mid;
   double ote_high;
   bool   ote_valid;
   bool   price_in_ote;
   bool   poi_overlaps_ote;
   double ote_alignment_score;
   bool   ote_from_gold_smc;
   double depth_target_low;
   double depth_target_mid;
   double depth_target_high;
   double depth_fib_retrace_pct;
   string depth_source;
   // Milestone 6 — calibration metadata
   double reference_close;
   double atr_m15;
   bool   csv_logging_enabled;
  };

class CVantagePullbackV2
  {
private:
   string                  m_symbol;
   VantagePullbackV2Config m_cfg;
   VantagePullbackV2Snapshot m_last;
   datetime                m_last_m5_bar;

   int m_hEmaF[3], m_hEmaS[3], m_hEmaL[3];
   int m_hRsi[3], m_hAtr[3], m_hBb[3], m_hAdx[3];

   void Rel(int &h)
     {
      if(h != INVALID_HANDLE) { IndicatorRelease(h); h = INVALID_HANDLE; }
     }

   double Clamp(const double v, const double lo, const double hi)
     {
      if(v < lo) return lo;
      if(v > hi) return hi;
      return v;
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

   int TfMinutes(const ENUM_TIMEFRAMES tf)
     {
      return PeriodSeconds(tf) / 60;
     }

   bool ClosedBar(const ENUM_TIMEFRAMES tf, MqlRates &out_r)
     {
      MqlRates r[];
      if(CopyRates(m_symbol, tf, 1, 1, r) != 1) return false;
      out_r = r[0];
      return (out_r.close > 0.0);
     }

   string StructureStateToString(const PbV2StructureState st)
     {
      switch(st)
        {
         case PBV2_BULL_CONTINUATION: return "Bullish Continuation";
         case PBV2_BEAR_CONTINUATION: return "Bearish Continuation";
         case PBV2_BULL_PULLBACK:     return "Bullish Pullback";
         case PBV2_BEAR_PULLBACK:     return "Bearish Pullback";
         case PBV2_BULL_CHOCH:        return "Bullish CHoCH";
         case PBV2_BEAR_CHOCH:        return "Bearish CHoCH";
         case PBV2_RANGE:             return "Range";
         default:                     return "Unknown";
        }
     }

   void AnalyzeStructureV2(const ENUM_TIMEFRAMES tf, PbV2StructureSnap &out)
     {
      ZeroMemory(out);
      out.state = PBV2_STRUCTURE_UNKNOWN;
      out.state_label = "Unknown";

      const int need = m_cfg.swing_left + m_cfg.swing_right + 30;
      MqlRates rates[];
      int n = CopyRates(m_symbol, tf, 1, need, rates);
      if(n < m_cfg.swing_left + m_cfg.swing_right + 5)
         return;

      ArraySetAsSeries(rates, true);

      double sh[4], sl[4];
      int nh = 0, nl = 0;
      for(int i = m_cfg.swing_right; i < n - m_cfg.swing_left && (nh < 4 || nl < 4); i++)
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
         if(is_hi && nh < 4) sh[nh++] = rates[i].high;
         if(is_lo && nl < 4) sl[nl++] = rates[i].low;
        }

      if(nh < 2 || nl < 2)
         return;

      out.swing_high = sh[0];
      out.swing_low = sl[0];
      out.prev_swing_high = sh[1];
      out.prev_swing_low = sl[1];
      out.hh = (sh[0] > sh[1]);
      out.hl = (sl[0] > sl[1]);
      out.lh = (sh[0] < sh[1]);
      out.ll = (sl[0] < sl[1]);

      const double close_px = rates[0].close;
      const bool bull_seq = (out.hh && out.hl);
      const bool bear_seq = (out.lh && out.ll);

      if(bull_seq)
        {
         out.protected_low = sl[0];
         if(close_px > sh[1])
            out.bullish_bos = true;
         if(out.protected_low > 0 && close_px < out.protected_low)
           {
            out.bearish_choch = true;
            out.bearish_mss = true; // M1: MSS identical to CHoCH; displacement gate in M2
           }
         if(out.bearish_choch)
            out.state = PBV2_BEAR_CHOCH;
         else if(out.bullish_bos)
            out.state = PBV2_BULL_CONTINUATION;
         else if(close_px < sh[0] && close_px > out.protected_low)
            out.state = PBV2_BULL_PULLBACK;
         else
            out.state = PBV2_BULL_CONTINUATION;
        }
      else if(bear_seq)
        {
         out.protected_high = sh[0];
         if(close_px < sl[1])
            out.bearish_bos = true;
         if(out.protected_high > 0 && close_px > out.protected_high)
           {
            out.bullish_choch = true;
            out.bullish_mss = true;
           }
         if(out.bullish_choch)
            out.state = PBV2_BULL_CHOCH;
         else if(out.bearish_bos)
            out.state = PBV2_BEAR_CONTINUATION;
         else if(close_px > sl[0] && close_px < out.protected_high)
            out.state = PBV2_BEAR_PULLBACK;
         else
            out.state = PBV2_BEAR_CONTINUATION;
        }
      else
        {
         out.state = PBV2_RANGE;
        }

      out.state_label = StructureStateToString(out.state);
      out.valid = true;
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
      double lower_wick = MathMin(r[0].open, r[0].close) - r[0].low;
      double upper_wick = r[0].high - MathMax(r[0].open, r[0].close);
      if(lower_wick >= body * 1.5 && lower_wick >= range * 0.45)
         bull = true;
      if(upper_wick >= body * 1.5 && upper_wick >= range * 0.45)
         bear = true;
      if(r[0].close > r[0].open && r[0].close >= r[1].high && r[0].open <= r[1].close)
         bull = true;
      if(r[0].close < r[0].open && r[0].close <= r[1].low && r[0].open >= r[1].close)
         bear = true;
     }

   void DetectRsiDiv(const ENUM_TIMEFRAMES tf, const int h_rsi, bool &bull_div, bool &bear_div)
     {
      bull_div = false; bear_div = false;
      MqlRates rates[];
      double rsi[];
      int n = 40;
      if(CopyRates(m_symbol, tf, 1, n, rates) < n) return;
      if(CopyBuffer(h_rsi, 0, 1, n, rsi) < n) return;
      ArraySetAsSeries(rates, true);
      ArraySetAsSeries(rsi, true);
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

   string MomentumStateToString(const PbV2MomentumState st)
     {
      switch(st)
        {
         case PBV2_MOM_CONTINUATION: return "CONTINUATION";
         case PBV2_MOM_STRONG:       return "STRONG";
         case PBV2_MOM_EXTENDED:     return "EXTENDED";
         case PBV2_MOM_ROLLOVER:     return "ROLLOVER";
         case PBV2_MOM_DIVERGENCE:   return "DIVERGENCE";
         default:                    return "NEUTRAL";
        }
     }

   bool DetectRecentFvg(const ENUM_TIMEFRAMES tf, const int trend_dir)
     {
      MqlRates rates[];
      if(CopyRates(m_symbol, tf, 1, 4, rates) < 3) return false;
      ArraySetAsSeries(rates, true);
      if(trend_dir > 0)
        {
         if(rates[2].high < rates[0].low) return true;
         if(rates[1].high < rates[0].low) return true;
        }
      else if(trend_dir < 0)
        {
         if(rates[2].low > rates[0].high) return true;
         if(rates[1].low > rates[0].high) return true;
        }
      return false;
     }

   int CountDirectionalBars(const ENUM_TIMEFRAMES tf, const int dir, const int lookback)
     {
      MqlRates hist[];
      if(CopyRates(m_symbol, tf, 1, lookback, hist) < 2) return 0;
      ArraySetAsSeries(hist, true);
      int c = 0;
      for(int i = 0; i < lookback; i++)
        {
         int d = (hist[i].close > hist[i].open) ? 1 : ((hist[i].close < hist[i].open) ? -1 : 0);
         if(d == dir && d != 0) c++; else break;
        }
      return c;
     }

   PbV2DisplacementSnap CalcDisplacement(const int dom, const PbV2TfSnap &m15, const PbV2TfSnap &m5s)
     {
      PbV2DisplacementSnap d;
      ZeroMemory(d);
      if(m15.atr <= 0) return d;

      MqlRates bar;
      if(!ClosedBar(m15.timeframe, bar)) return d;

      const double range = bar.high - bar.low;
      const double body = MathAbs(bar.close - bar.open);
      const double body_atr = body / m15.atr;
      const double range_atr = (range > 0) ? range / m15.atr : 0;
      d.body = Clamp(body_atr / 1.0, 0, 1) * 100;

      d.range = Clamp(range_atr / 1.5, 0, 1) * 100;

      int dir = (dom != 0) ? dom : m15.trend_dir;
      int persist = CountDirectionalBars(m5s.timeframe, dir, 6);
      d.persistence = Clamp(persist / 4.0, 0, 1) * 100;

      if(range > 0)
        {
         if(bar.close >= bar.open)
            d.close_quality = Clamp((bar.close - bar.low) / range, 0, 1) * 100;
         else
            d.close_quality = Clamp((bar.high - bar.close) / range, 0, 1) * 100;
        }

      double ema_slope_atr = (m15.ema_fast - m15.ema_fast_prev) / m15.atr;
      if(dom < 0) ema_slope_atr = -ema_slope_atr;
      d.ema_accel = Clamp(MathAbs(ema_slope_atr) / 0.35, 0, 1) * 100;

      if((dom > 0 && m15.structure.bullish_bos) || (dom < 0 && m15.structure.bearish_bos))
         d.bos = 100;
      else if(m5s.structure.bullish_bos || m5s.structure.bearish_bos)
         d.bos = 60;
      else
         d.bos = 20;

      d.fvg = DetectRecentFvg(m15.timeframe, dir) ? 100 : (DetectRecentFvg(m5s.timeframe, dir) ? 75 : 0);

      d.score = Clamp(
         d.body * 0.25 +
         d.range * 0.20 +
         d.persistence * 0.15 +
         d.close_quality * 0.10 +
         d.ema_accel * 0.10 +
         d.bos * 0.10 +
         d.fvg * 0.10, 0, 100);
      return d;
     }

   PbV2MomentumSnap ClassifyMomentum(const int dom, const PbV2TfSnap &m15, const PbV2TfSnap &m5s)
     {
      PbV2MomentumSnap m;
      ZeroMemory(m);
      m.rsi_level = m15.rsi;
      m.rsi_slope = m15.rsi - m15.rsi_prev;
      m.state = PBV2_MOM_NEUTRAL;
      m.state_label = "NEUTRAL";
      m.rollover_score = 0;
      m.continuation_score = 40;

      if(m15.rsi_div_bull || m15.rsi_div_bear || m5s.rsi_div_bull || m5s.rsi_div_bear)
        {
         m.state = PBV2_MOM_DIVERGENCE;
         m.state_label = "DIVERGENCE";
         m.rollover_score = 80;
         m.continuation_score = 30;
         return m;
        }

      if(dom > 0)
        {
         if(m15.rsi >= 68 && m.rsi_slope < 0)
           {
            m.state = PBV2_MOM_ROLLOVER;
            m.state_label = "ROLLOVER";
            m.rollover_score = 90;
            m.continuation_score = 35;
           }
         else if(m15.rsi >= 68 && m.rsi_slope >= 0)
           {
            m.state = PBV2_MOM_EXTENDED;
            m.state_label = "EXTENDED";
            m.rollover_score = 55;
            m.continuation_score = 55;
           }
         else if(m15.rsi >= 50 && m15.rsi <= 68 && m.rsi_slope >= 0)
           {
            m.state = PBV2_MOM_CONTINUATION;
            m.state_label = "CONTINUATION";
            m.rollover_score = 20;
            m.continuation_score = 85;
           }
         else if(m15.rsi >= 50 && m.rsi_slope > 0)
           {
            m.state = PBV2_MOM_STRONG;
            m.state_label = "STRONG";
            m.rollover_score = 30;
            m.continuation_score = 75;
           }
        }
      else if(dom < 0)
        {
         if(m15.rsi <= 32 && m.rsi_slope > 0)
           {
            m.state = PBV2_MOM_ROLLOVER;
            m.state_label = "ROLLOVER";
            m.rollover_score = 90;
            m.continuation_score = 35;
           }
         else if(m15.rsi <= 32 && m.rsi_slope <= 0)
           {
            m.state = PBV2_MOM_EXTENDED;
            m.state_label = "EXTENDED";
            m.rollover_score = 55;
            m.continuation_score = 55;
           }
         else if(m15.rsi <= 50 && m15.rsi >= 32 && m.rsi_slope <= 0)
           {
            m.state = PBV2_MOM_CONTINUATION;
            m.state_label = "CONTINUATION";
            m.rollover_score = 20;
            m.continuation_score = 85;
           }
         else if(m15.rsi <= 50 && m.rsi_slope < 0)
           {
            m.state = PBV2_MOM_STRONG;
            m.state_label = "STRONG";
            m.rollover_score = 30;
            m.continuation_score = 75;
           }
        }
      return m;
     }

   PbV2DealingRangeSnap CalcDealingRange(const int dom, const PbV2TfSnap &m15)
     {
      PbV2DealingRangeSnap dr;
      ZeroMemory(dr);
      dr.location = "Unknown";

      if(dom > 0)
        {
         dr.range_low = (m15.structure.protected_low > 0) ? m15.structure.protected_low : m15.structure.swing_low;
         dr.range_high = (m15.structure.swing_high > 0) ? m15.structure.swing_high : m15.close_px;
         if(dr.range_high < m15.close_px) dr.range_high = m15.close_px;
        }
      else if(dom < 0)
        {
         dr.range_high = (m15.structure.protected_high > 0) ? m15.structure.protected_high : m15.structure.swing_high;
         dr.range_low = (m15.structure.swing_low > 0) ? m15.structure.swing_low : m15.close_px;
         if(dr.range_low > m15.close_px) dr.range_low = m15.close_px;
        }
      else
         return dr;

      if(dr.range_high <= dr.range_low || dr.range_low <= 0)
         return dr;

      dr.valid = true;
      dr.equilibrium = (dr.range_low + dr.range_high) * 0.5;
      double span = dr.range_high - dr.range_low;
      dr.position_pct = Clamp((m15.close_px - dr.range_low) / span * 100.0, 0, 100);

      double deep_d = Clamp(m_cfg.deep_discount_pct, 0.05, 0.45) * 100.0;
      double deep_p = Clamp(m_cfg.deep_premium_pct, 0.55, 0.95) * 100.0;
      if(deep_p <= deep_d + 10) { deep_d = 25; deep_p = 75; }

      if(dr.position_pct <= deep_d)
         dr.location = "Deep Discount";
      else if(dr.position_pct < 50)
         dr.location = "Discount";
      else if(dr.position_pct <= 55)
         dr.location = "Equilibrium";
      else if(dr.position_pct < deep_p)
         dr.location = "Premium";
      else
         dr.location = "Deep Premium";

      if(dom > 0)
        {
         if(dr.location == "Deep Discount") dr.pd_pressure_score = 15;
         else if(dr.location == "Discount") dr.pd_pressure_score = 30;
         else if(dr.location == "Equilibrium") dr.pd_pressure_score = 45;
         else if(dr.location == "Premium") dr.pd_pressure_score = 70;
         else dr.pd_pressure_score = 85;
        }
      else
        {
         if(dr.location == "Deep Premium") dr.pd_pressure_score = 15;
         else if(dr.location == "Premium") dr.pd_pressure_score = 30;
         else if(dr.location == "Equilibrium") dr.pd_pressure_score = 45;
         else if(dr.location == "Discount") dr.pd_pressure_score = 70;
         else dr.pd_pressure_score = 85;
        }
      return dr;
     }

   double CalcPdEntryFavorability(const int dom, const PbV2DealingRangeSnap &dr)
     {
      if(!dr.valid) return 50;
      if(dom > 0)
        {
         if(dr.location == "Deep Discount") return 95;
         if(dr.location == "Discount") return 80;
         if(dr.location == "Equilibrium") return 55;
         if(dr.location == "Premium") return 35;
         return 15;
        }
      if(dom < 0)
        {
         if(dr.location == "Deep Premium") return 95;
         if(dr.location == "Premium") return 80;
         if(dr.location == "Equilibrium") return 55;
         if(dr.location == "Discount") return 35;
         return 15;
        }
      return 50;
     }

   double CalcDisplacementExhaustion(const PbV2DisplacementSnap &disp, const double extension_score)
     {
      if(disp.score >= 65 && extension_score >= 60)
         return Clamp(disp.score * 0.55 + extension_score * 0.45, 0, 100);
      if(extension_score >= 70)
         return extension_score * 0.75;
      return disp.score * 0.35;
     }

   double CalcRejectionScore(const PbV2TfSnap &m15, const PbV2TfSnap &m5s, const int dom)
     {
      double s = 0;
      if(m15.bb_outside_then_in || m5s.bb_outside_then_in) s += 60;
      if(dom > 0 && m5s.candle_reject_bear) s += 40;
      if(dom < 0 && m5s.candle_reject_bull) s += 40;
      return Clamp(s, 0, 100);
     }

   double CalcEntryLocationScore(const int dom, const double extension_score,
                                 const double reversal_risk, const double protected_intact,
                                 const PbV2DealingRangeSnap &dr, const PbV2DisplacementSnap &disp)
     {
      const double pd_fav = CalcPdEntryFavorability(dom, dr);
      return Clamp(
         pd_fav * 0.40 +
         (100.0 - extension_score) * 0.30 +
         protected_intact * 0.20 +
         (100.0 - reversal_risk) * 0.10, 0, 100);
     }

   string EntryLocationLabel(const double score)
     {
      if(score >= 80) return "Excellent";
      if(score >= 65) return "Good";
      if(score >= 50) return "Acceptable";
      if(score >= 35) return "Weak";
      return "Poor / chase";
     }

   void ApplyMssDisplacementGate(PbV2StructureSnap &st, const double displacement_score)
     {
      if(st.bullish_choch && displacement_score < m_cfg.min_mss_displacement)
        {
         st.bullish_mss = false;
         if(st.state == PBV2_BULL_CHOCH) st.state_label = StructureStateToString(st.state);
        }
      if(st.bearish_choch && displacement_score < m_cfg.min_mss_displacement)
        {
         st.bearish_mss = false;
         if(st.state == PBV2_BEAR_CHOCH) st.state_label = StructureStateToString(st.state);
        }
      if(st.bullish_choch && displacement_score >= m_cfg.min_mss_displacement)
         st.bullish_mss = true;
      if(st.bearish_choch && displacement_score >= m_cfg.min_mss_displacement)
         st.bearish_mss = true;
     }

   string LiquidityStateToString(const PbV2LiquidityState st)
     {
      switch(st)
        {
         case PBV2_LIQ_APPROACHING:      return "approaching";
         case PBV2_LIQ_TOUCHED:           return "touched";
         case PBV2_LIQ_SWEPT:            return "swept";
         case PBV2_LIQ_REJECTED:         return "rejected";
         case PBV2_LIQ_ACCEPTED_BEYOND:  return "accepted_beyond";
         default:                        return "none";
        }
     }

   void ScoreLiquidityState(const int dom, const PbV2LiquidityState st,
                            double &pullback_pressure, double &continuation_boost)
     {
      pullback_pressure = 35;
      continuation_boost = 40;
      if(dom > 0)
        {
         switch(st)
           {
            case PBV2_LIQ_APPROACHING:     pullback_pressure = 25; continuation_boost = 70; break;
            case PBV2_LIQ_TOUCHED:         pullback_pressure = 40; continuation_boost = 60; break;
            case PBV2_LIQ_SWEPT:          pullback_pressure = 55; continuation_boost = 45; break;
            case PBV2_LIQ_REJECTED:       pullback_pressure = 85; continuation_boost = 25; break;
            case PBV2_LIQ_ACCEPTED_BEYOND: pullback_pressure = 20; continuation_boost = 85; break;
            default: break;
           }
        }
      else if(dom < 0)
        {
         switch(st)
           {
            case PBV2_LIQ_APPROACHING:     pullback_pressure = 25; continuation_boost = 70; break;
            case PBV2_LIQ_TOUCHED:         pullback_pressure = 40; continuation_boost = 60; break;
            case PBV2_LIQ_SWEPT:          pullback_pressure = 55; continuation_boost = 45; break;
            case PBV2_LIQ_REJECTED:       pullback_pressure = 85; continuation_boost = 25; break;
            case PBV2_LIQ_ACCEPTED_BEYOND: pullback_pressure = 20; continuation_boost = 85; break;
            default: break;
           }
        }
     }

   PbV2LiquiditySnap CalcLiquidityFallback(const int dom, const PbV2TfSnap &m15, const PbV2TfSnap &m5s)
     {
      PbV2LiquiditySnap liq;
      ZeroMemory(liq);
      liq.state = PBV2_LIQ_NONE;
      liq.state_label = "none";
      liq.draw = "none";
      if(dom == 0 || m15.atr <= 0) return liq;

      if(dom > 0)
        {
         liq.draw = "buy_side";
         liq.target_price = (m15.structure.swing_high > 0 ? m15.structure.swing_high : m15.bb_upper);
         liq.target_label = "M15 swing high / BSL proxy";
        }
      else
        {
         liq.draw = "sell_side";
         liq.target_price = (m15.structure.swing_low > 0 ? m15.structure.swing_low : m15.bb_lower);
         liq.target_label = "M15 swing low / SSL proxy";
        }

      if(liq.target_price <= 0) return liq;

      liq.valid = true;
      liq.distance_atr = MathAbs(liq.target_price - m15.close_px) / m15.atr;

      MqlRates m5bar;
      if(ClosedBar(m5s.timeframe, m5bar))
        {
         const double tol = m15.atr * 0.08;
         if(dom > 0)
           {
            if(m5bar.high >= liq.target_price - tol && m5bar.close < liq.target_price)
              liq.state = PBV2_LIQ_REJECTED;
            else if(m5bar.high > liq.target_price + tol && m5bar.close >= liq.target_price)
              liq.state = PBV2_LIQ_ACCEPTED_BEYOND;
            else if(m5bar.high >= liq.target_price - tol)
              liq.state = PBV2_LIQ_SWEPT;
            else if(m5bar.high >= liq.target_price - m15.atr * m_cfg.liquidity_touch_atr)
              liq.state = PBV2_LIQ_TOUCHED;
            else if(liq.distance_atr <= m_cfg.liquidity_approach_atr)
              liq.state = PBV2_LIQ_APPROACHING;
           }
         else
           {
            if(m5bar.low <= liq.target_price + tol && m5bar.close > liq.target_price)
              liq.state = PBV2_LIQ_REJECTED;
            else if(m5bar.low < liq.target_price - tol && m5bar.close <= liq.target_price)
              liq.state = PBV2_LIQ_ACCEPTED_BEYOND;
            else if(m5bar.low <= liq.target_price + tol)
              liq.state = PBV2_LIQ_SWEPT;
            else if(m5bar.low <= liq.target_price + m15.atr * m_cfg.liquidity_touch_atr)
              liq.state = PBV2_LIQ_TOUCHED;
            else if(liq.distance_atr <= m_cfg.liquidity_approach_atr)
              liq.state = PBV2_LIQ_APPROACHING;
           }
        }
      else if(liq.distance_atr <= m_cfg.liquidity_approach_atr)
         liq.state = PBV2_LIQ_APPROACHING;

      liq.state_label = LiquidityStateToString(liq.state);
      ScoreLiquidityState(dom, liq.state, liq.pullback_pressure, liq.continuation_boost);
      liq.from_liquidity_grab = false;
      return liq;
     }

   PbV2LiquiditySnap MapLiquidityGrab(const int dom, const PbV2TfSnap &m15,
                                      const VantageLiquidityGrabResult &lg)
     {
      PbV2LiquiditySnap liq;
      ZeroMemory(liq);
      liq.state = PBV2_LIQ_NONE;
      liq.state_label = "none";
      liq.draw = "none";
      liq.valid = true;
      liq.from_liquidity_grab = true;
      liq.target_price = lg.liquidity_level_price;
      liq.target_label = (lg.liquidity_level_type != "" ? lg.liquidity_level_type : lg.liquidity_level_id);
      liq.distance_atr = (m15.atr > 0 ? MathAbs(liq.target_price - m15.close_px) / m15.atr : lg.sweep_distance_atr);

      if(lg.direction == LG_DIR_BUY_SIDE_GRAB_BEARISH)
         liq.draw = "buy_side";
      else if(lg.direction == LG_DIR_SELL_SIDE_GRAB_BULLISH)
         liq.draw = "sell_side";
      else if(liq.target_price > m15.close_px)
         liq.draw = "buy_side";
      else if(liq.target_price < m15.close_px)
         liq.draw = "sell_side";

      switch(lg.machine_state)
        {
         case LG_STATE_APPROACHING:
            liq.state = PBV2_LIQ_APPROACHING;
            break;
         case LG_STATE_SWEPT:
            liq.state = PBV2_LIQ_SWEPT;
            break;
         case LG_STATE_REJECTED:
         case LG_STATE_DISPLACEMENT:
         case LG_STATE_MSS:
         case LG_STATE_CONFIRMED:
            if(lg.status == LG_STATUS_GENUINE_BREAKOUT || lg.machine_state == LG_STATE_BREAKOUT)
               liq.state = PBV2_LIQ_ACCEPTED_BEYOND;
            else
               liq.state = PBV2_LIQ_REJECTED;
            break;
         case LG_STATE_BREAKOUT:
            liq.state = PBV2_LIQ_ACCEPTED_BEYOND;
            break;
         case LG_STATE_FAILED:
            liq.state = PBV2_LIQ_SWEPT;
            break;
         default:
            if(lg.status == LG_STATUS_APPROACH)
               liq.state = PBV2_LIQ_APPROACHING;
            else if(lg.status == LG_STATUS_TEST)
               liq.state = PBV2_LIQ_TOUCHED;
            else if(lg.status == LG_STATUS_SWEEP_UNCONFIRMED)
               liq.state = PBV2_LIQ_SWEPT;
            else if(lg.status == LG_STATUS_GENUINE_BREAKOUT)
               liq.state = PBV2_LIQ_ACCEPTED_BEYOND;
            else if(lg.sweep_price > 0 && lg.rejection_close_price > 0)
               liq.state = PBV2_LIQ_REJECTED;
            else if(liq.distance_atr <= m_cfg.liquidity_approach_atr)
               liq.state = PBV2_LIQ_APPROACHING;
            break;
        }

      if(lg.status == LG_STATUS_TEST && liq.state == PBV2_LIQ_NONE)
         liq.state = PBV2_LIQ_TOUCHED;
      if(lg.status == LG_STATUS_GENUINE_BREAKOUT)
         liq.state = PBV2_LIQ_ACCEPTED_BEYOND;

      liq.state_label = LiquidityStateToString(liq.state);
      ScoreLiquidityState(dom, liq.state, liq.pullback_pressure, liq.continuation_boost);

      // Counter-trend grab against dominant direction increases pullback / reversal nuance
      if(dom > 0 && lg.direction == LG_DIR_BUY_SIDE_GRAB_BEARISH && liq.state == PBV2_LIQ_REJECTED)
        {
         liq.pullback_pressure = MathMax(liq.pullback_pressure, 88);
         liq.continuation_boost = MathMin(liq.continuation_boost, 22);
        }
      if(dom < 0 && lg.direction == LG_DIR_SELL_SIDE_GRAB_BULLISH && liq.state == PBV2_LIQ_REJECTED)
        {
         liq.pullback_pressure = MathMax(liq.pullback_pressure, 88);
         liq.continuation_boost = MathMin(liq.continuation_boost, 22);
        }
      if(dom > 0 && liq.state == PBV2_LIQ_ACCEPTED_BEYOND)
        {
         liq.pullback_pressure = MathMin(liq.pullback_pressure, 25);
         liq.continuation_boost = MathMax(liq.continuation_boost, 82);
        }
      if(dom < 0 && liq.state == PBV2_LIQ_ACCEPTED_BEYOND)
        {
         liq.pullback_pressure = MathMin(liq.pullback_pressure, 25);
         liq.continuation_boost = MathMax(liq.continuation_boost, 82);
        }

      return liq;
     }

   PbV2LiquiditySnap ResolveLiquidity(const int dom, const PbV2TfSnap &m15, const PbV2TfSnap &m5s,
                                      const bool lg_active, const VantageLiquidityGrabResult &lg)
     {
      if(m_cfg.prefer_liquidity_grab && lg_active && lg.valid && lg.analysis_active &&
         lg.liquidity_level_price > 0)
         return MapLiquidityGrab(dom, m15, lg);
      return CalcLiquidityFallback(dom, m15, m5s);
     }

   double PbV2DispScore(const MqlRates &bar, const double atr)
     {
      if(atr <= 0) return 0;
      const double range = bar.high - bar.low;
      if(range <= 0) return 0;
      const double body = MathAbs(bar.close - bar.open);
      const double body_atr = body / atr;
      const double range_atr = range / atr;
      const double close_pos = (bar.close >= bar.open)
                             ? (bar.close - bar.low) / range
                             : (bar.high - bar.close) / range;
      return Clamp(body_atr * 35.0 + range_atr * 20.0 + close_pos * 20.0, 0, 100);
     }

   void PbV2UpdateFvgMitigation(PbV2PoiCandidate &c, MqlRates &rates[], const int n)
     {
      if(c.status_label == "invalidated") return;
      const double span = c.upper - c.lower;
      if(span <= 0) return;
      double worst = 0;
      for(int i = 0; i < n; i++)
        {
         if(rates[i].time <= c.created) break;
         if(c.bullish)
           {
            if(rates[i].low < c.upper)
              {
               const double fill = (c.upper - MathMax(rates[i].low, c.lower)) / span;
               if(fill > worst) worst = fill;
              }
            if(rates[i].close < c.lower) { c.status_label = "invalidated"; c.mitigation_pct = 100; return; }
           }
         else
           {
            if(rates[i].high > c.lower)
              {
               const double fill = (MathMin(rates[i].high, c.upper) - c.lower) / span;
               if(fill > worst) worst = fill;
              }
            if(rates[i].close > c.upper) { c.status_label = "invalidated"; c.mitigation_pct = 100; return; }
           }
        }
      c.mitigation_pct = Clamp(worst * 100.0, 0, 100);
      if(c.mitigation_pct >= 99) c.status_label = "fully_mitigated";
      else if(c.mitigation_pct >= 50) c.status_label = "partially_mitigated";
      else if(c.mitigation_pct > 0) c.status_label = "touched";
      else c.status_label = "fresh";
     }

   void FinalizePoiSnap(const int dom, const PbV2TfSnap &m15, const PbV2DealingRangeSnap &dr,
                        PbV2PoiSnap &poi)
     {
      if(!poi.valid || m15.atr <= 0 || poi.upper <= poi.lower) return;
      const double px = m15.close_px;
      poi.price_inside = (px <= poi.upper && px >= poi.lower);
      const double dist = poi.price_inside ? 0 :
                          (px > poi.upper ? px - poi.upper : poi.lower - px);
      poi.distance_atr = dist / m15.atr;
      poi.price_approaching = (poi.distance_atr <= m_cfg.poi_approach_atr);

      const bool poi_bull = (StringFind(poi.primary_dir, "Bull") >= 0);
      poi.pullback_target_score = 35;
      poi.confluence_score = Clamp(poi.quality * 0.55 + 15, 0, 100);

      if(dom > 0 && poi_bull)
        {
         if(px > poi.upper)
           {
            poi.pullback_target_score = 58 + Clamp(poi.quality * 0.30, 0, 30);
            if(dr.valid && dr.position_pct >= 55) poi.pullback_target_score += 8;
            if(poi.status == "fresh" || poi.status == "touched") poi.pullback_target_score += 8;
            if(poi.distance_atr >= 0.25 && poi.distance_atr <= 1.75) poi.pullback_target_score += 7;
           }
         else if(poi.price_inside)
            poi.pullback_target_score = 82;
         poi.confluence_score += 12;
        }
      else if(dom < 0 && !poi_bull)
        {
         if(px < poi.lower)
           {
            poi.pullback_target_score = 58 + Clamp(poi.quality * 0.30, 0, 30);
            if(dr.valid && dr.position_pct <= 45) poi.pullback_target_score += 8;
            if(poi.status == "fresh" || poi.status == "touched") poi.pullback_target_score += 8;
            if(poi.distance_atr >= 0.25 && poi.distance_atr <= 1.75) poi.pullback_target_score += 7;
           }
         else if(poi.price_inside)
            poi.pullback_target_score = 82;
         poi.confluence_score += 12;
        }
      else
         poi.confluence_score *= 0.65;

      if(StringFind(poi.primary_type, "Breaker") >= 0) poi.confluence_score += 6;
      if(StringFind(poi.primary_type, "Inverse") >= 0) poi.confluence_score += 5;
      if(poi.from_gold_smc) poi.confluence_score += 8;
      if(poi.mitigation_pct >= 75) poi.pullback_target_score = MathMin(poi.pullback_target_score, 45);

      poi.pullback_target_score = Clamp(poi.pullback_target_score, 0, 100);
      poi.confluence_score = Clamp(poi.confluence_score, 0, 100);
     }

   PbV2PoiSnap MapGoldSmcPoi(const int dom, const PbV2TfSnap &m15, const PbV2DealingRangeSnap &dr,
                             const VantageGoldSMCResult &gsm)
     {
      PbV2PoiSnap poi;
      ZeroMemory(poi);
      if(gsm.primary_poi_type == "" || gsm.primary_poi_type == "None") return poi;
      if(gsm.poi_upper <= gsm.poi_lower) return poi;

      poi.valid = true;
      poi.from_gold_smc = true;
      poi.primary_type = gsm.primary_poi_type;
      poi.primary_dir = gsm.primary_poi_dir;
      poi.status = gsm.primary_poi_status;
      if(poi.status == "") poi.status = "fresh";
      poi.upper = gsm.poi_upper;
      poi.lower = gsm.poi_lower;
      poi.mid = gsm.poi_mid;
      poi.ce = gsm.poi_ce;
      poi.quality = gsm.poi_quality;
      poi.mitigation_pct = gsm.poi_mitigation_pct;
      poi.fvg_count = gsm.has_fresh_fvg ? 1 : 0;
      poi.ob_count = gsm.has_valid_ob ? 1 : 0;
      if(gsm.has_inverse_fvg) poi.fvg_count++;
      if(gsm.has_breaker) poi.ob_count++;
      FinalizePoiSnap(dom, m15, dr, poi);
      return poi;
     }

   double RankPoiCandidate(const int dom, const PbV2TfSnap &m15, const PbV2DealingRangeSnap &dr,
                           const PbV2PoiCandidate &c)
     {
      if(!c.valid || c.status_label == "invalidated" || c.status_label == "fully_mitigated") return -1;
      const double px = m15.close_px;
      const bool aligned = (dom > 0 && c.bullish) || (dom < 0 && !c.bullish);
      if(!aligned && dom != 0) return -1;

      double score = c.quality;
      if(c.with_fvg) score += 10;
      if(c.status_label == "fresh") score += 8;
      else if(c.status_label == "touched") score += 5;

      if(dom > 0 && c.bullish && px > c.upper)
        {
         const double dist_atr = (px - c.upper) / m15.atr;
         if(dist_atr <= 2.5) score += 12;
         if(dr.valid && c.mid <= dr.equilibrium) score += 8;
        }
      else if(dom < 0 && !c.bullish && px < c.lower)
        {
         const double dist_atr = (c.lower - px) / m15.atr;
         if(dist_atr <= 2.5) score += 12;
         if(dr.valid && c.mid >= dr.equilibrium) score += 8;
        }
      else if(px <= c.upper && px >= c.lower)
         score += 18;

      if(c.mitigation_pct >= 60) score -= 15;
      return score;
     }

   PbV2PoiSnap CalcPoiFallback(const int dom, const PbV2TfSnap &m15, const PbV2DealingRangeSnap &dr)
     {
      PbV2PoiSnap poi;
      ZeroMemory(poi);
      if(m15.atr <= 0 || dom == 0) return poi;

      MqlRates rates[];
      const int max_bars = MathMax(20, m_cfg.max_poi_scan);
      int n = CopyRates(m_symbol, m15.timeframe, 1, max_bars, rates);
      if(n < 8) return poi;
      ArraySetAsSeries(rates, true);

      PbV2PoiCandidate cands[];
      int nc = 0;
      const double min_gap = m_cfg.min_fvg_atr * m15.atr;

      for(int i = 0; i < n - 3 && nc < 12; i++)
        {
         if(rates[i].low > rates[i + 2].high)
           {
            const double gap = rates[i].low - rates[i + 2].high;
            if(gap >= min_gap)
              {
               PbV2PoiCandidate c;
               ZeroMemory(c);
               c.valid = true;
               c.type_label = "Fair Value Gap";
               c.dir_label = "Bullish";
               c.bullish = true;
               c.lower = rates[i + 2].high;
               c.upper = rates[i].low;
               c.mid = 0.5 * (c.upper + c.lower);
               c.ce = c.lower + 0.5 * (c.upper - c.lower);
               c.created = rates[i + 1].time;
               c.tf = m15.timeframe;
               c.quality = Clamp(42 + PbV2DispScore(rates[i + 1], m15.atr) * 0.35 + gap / m15.atr * 8, 0, 100);
               c.status_label = "fresh";
               PbV2UpdateFvgMitigation(c, rates, n);
               ArrayResize(cands, nc + 1);
               cands[nc++] = c;
               poi.fvg_count++;
              }
           }
         if(rates[i].high < rates[i + 2].low)
           {
            const double gap = rates[i + 2].low - rates[i].high;
            if(gap >= min_gap)
              {
               PbV2PoiCandidate c;
               ZeroMemory(c);
               c.valid = true;
               c.type_label = "Fair Value Gap";
               c.dir_label = "Bearish";
               c.bullish = false;
               c.upper = rates[i + 2].low;
               c.lower = rates[i].high;
               c.mid = 0.5 * (c.upper + c.lower);
               c.ce = c.upper - 0.5 * (c.upper - c.lower);
               c.created = rates[i + 1].time;
               c.tf = m15.timeframe;
               c.quality = Clamp(42 + PbV2DispScore(rates[i + 1], m15.atr) * 0.35 + gap / m15.atr * 8, 0, 100);
               c.status_label = "fresh";
               PbV2UpdateFvgMitigation(c, rates, n);
               ArrayResize(cands, nc + 1);
               cands[nc++] = c;
               poi.fvg_count++;
              }
           }
        }

      for(int i = 1; i < n - 3 && nc < 16; i++)
        {
         const double ds = PbV2DispScore(rates[i], m15.atr);
         if(ds < 45) continue;
         if(rates[i].close > rates[i].open && rates[i + 1].close < rates[i + 1].open)
           {
            PbV2PoiCandidate c;
            ZeroMemory(c);
            c.valid = true;
            c.type_label = "Order Block";
            c.dir_label = "Bullish";
            c.bullish = true;
            c.upper = rates[i + 1].high;
            c.lower = rates[i + 1].low;
            c.mid = 0.5 * (c.upper + c.lower);
            c.ce = c.mid;
            c.created = rates[i + 1].time;
            c.tf = m15.timeframe;
            c.quality = Clamp(40 + ds * 0.45, 0, 100);
            c.status_label = "fresh";
            if(rates[i].close > rates[i + 2].high) c.quality += 8;
            ArrayResize(cands, nc + 1);
            cands[nc++] = c;
            poi.ob_count++;
           }
         if(rates[i].close < rates[i].open && rates[i + 1].close > rates[i + 1].open)
           {
            PbV2PoiCandidate c;
            ZeroMemory(c);
            c.valid = true;
            c.type_label = "Order Block";
            c.dir_label = "Bearish";
            c.bullish = false;
            c.upper = rates[i + 1].high;
            c.lower = rates[i + 1].low;
            c.mid = 0.5 * (c.upper + c.lower);
            c.ce = c.mid;
            c.created = rates[i + 1].time;
            c.tf = m15.timeframe;
            c.quality = Clamp(40 + ds * 0.45, 0, 100);
            c.status_label = "fresh";
            if(rates[i].close < rates[i + 2].low) c.quality += 8;
            ArrayResize(cands, nc + 1);
            cands[nc++] = c;
            poi.ob_count++;
           }
        }

      int best = -1;
      double best_q = -1;
      for(int i = 0; i < nc; i++)
        {
         const double q = RankPoiCandidate(dom, m15, dr, cands[i]);
         if(q > best_q) { best_q = q; best = i; }
        }
      if(best < 0) return poi;

      PbV2PoiCandidate win = cands[best];
      poi.valid = true;
      poi.from_gold_smc = false;
      poi.primary_type = win.type_label;
      poi.primary_dir = win.dir_label;
      poi.status = win.status_label;
      poi.upper = win.upper;
      poi.lower = win.lower;
      poi.mid = win.mid;
      poi.ce = win.ce;
      poi.quality = win.quality;
      poi.mitigation_pct = win.mitigation_pct;
      FinalizePoiSnap(dom, m15, dr, poi);
      return poi;
     }

   PbV2PoiSnap ResolvePoi(const int dom, const PbV2TfSnap &m15, const PbV2DealingRangeSnap &dr,
                          const bool gsm_active, const VantageGoldSMCResult &gsm)
     {
      if(m_cfg.prefer_gold_smc_poi && gsm_active && gsm.valid && gsm.analysis_active &&
         gsm.gold_symbol_valid && gsm.primary_poi_type != "" && gsm.primary_poi_type != "None")
         return MapGoldSmcPoi(dom, m15, dr, gsm);
      return CalcPoiFallback(dom, m15, dr);
     }

   bool PbV2Overlap(const double a_lo, const double a_hi, const double b_lo, const double b_hi)
     {
      return (a_lo <= b_hi && a_hi >= b_lo);
     }

   PbV2OteSnap MapGoldSmcOte(const PbV2PoiSnap &poi, const VantageGoldSMCResult &gsm)
     {
      PbV2OteSnap ote;
      ZeroMemory(ote);
      if(!gsm.ote_enabled_hit || gsm.ote_high <= gsm.ote_low) return ote;
      ote.valid = true;
      ote.from_gold_smc = true;
      ote.ote_low = gsm.ote_low;
      ote.ote_mid = gsm.ote_mid;
      ote.ote_high = gsm.ote_high;
      ote.price_in_ote = gsm.price_in_ote;
      ote.poi_overlaps_ote = gsm.poi_overlaps_ote;
      if(!ote.poi_overlaps_ote && poi.valid && poi.upper > poi.lower)
         ote.poi_overlaps_ote = PbV2Overlap(poi.lower, poi.upper, ote.ote_low, ote.ote_high);
      return ote;
     }

   PbV2OteSnap CalcOteFallback(const int dom, const PbV2TfSnap &m15, const PbV2DealingRangeSnap &dr,
                               const PbV2PoiSnap &poi)
     {
      PbV2OteSnap ote;
      ZeroMemory(ote);
      if(!m_cfg.enable_ote || !dr.valid || dr.range_high <= dr.range_low) return ote;

      double lo_pct = Clamp(m_cfg.ote_low_pct, 0.50, 0.75);
      double mid_pct = Clamp(m_cfg.ote_mid_pct, lo_pct, 0.80);
      double hi_pct = Clamp(m_cfg.ote_high_pct, mid_pct, 0.90);
      const double span = dr.range_high - dr.range_low;

      if(dom > 0)
        {
         ote.ote_high = dr.range_high - span * lo_pct;
         ote.ote_mid  = dr.range_high - span * mid_pct;
         ote.ote_low  = dr.range_high - span * hi_pct;
        }
      else if(dom < 0)
        {
         ote.ote_low  = dr.range_low + span * lo_pct;
         ote.ote_mid  = dr.range_low + span * mid_pct;
         ote.ote_high = dr.range_low + span * hi_pct;
        }
      else
         return ote;

      if(ote.ote_high < ote.ote_low)
        {
         const double tmp = ote.ote_high;
         ote.ote_high = ote.ote_low;
         ote.ote_low = tmp;
        }

      ote.valid = true;
      ote.from_gold_smc = false;
      ote.price_in_ote = (m15.close_px >= ote.ote_low && m15.close_px <= ote.ote_high);
      if(poi.valid && poi.upper > poi.lower)
         ote.poi_overlaps_ote = PbV2Overlap(poi.lower, poi.upper, ote.ote_low, ote.ote_high);
      return ote;
     }

   double ScoreOteAlignment(const int dom, const PbV2OteSnap &ote, const PbV2PoiSnap &poi,
                            const PbV2DealingRangeSnap &dr)
     {
      if(!ote.valid) return 40;
      double s = 45;
      if(ote.price_in_ote) s = 78;
      if(ote.poi_overlaps_ote) s = 88;
      if(poi.valid && poi.price_inside && ote.poi_overlaps_ote) s = 92;
      if(dr.valid)
        {
         if(dom > 0 && dr.position_pct >= 55) s += 5;
         if(dom < 0 && dr.position_pct <= 45) s += 5;
        }
      return Clamp(s, 0, 100);
     }

   PbV2OteSnap ResolveOte(const int dom, const PbV2TfSnap &m15, const PbV2DealingRangeSnap &dr,
                          const PbV2PoiSnap &poi, const bool gsm_active, const VantageGoldSMCResult &gsm)
     {
      PbV2OteSnap ote;
      if(m_cfg.prefer_gold_smc_ote && gsm_active && gsm.valid && gsm.analysis_active &&
         gsm.gold_symbol_valid && gsm.ote_enabled_hit && gsm.ote_high > gsm.ote_low)
         ote = MapGoldSmcOte(poi, gsm);
      else
         ote = CalcOteFallback(dom, m15, dr, poi);
      ote.alignment_score = ScoreOteAlignment(dom, ote, poi, dr);
      return ote;
     }

   PbV2DepthSnap CalcExpectedDepth(const int dom, const PbV2TfSnap &m15, const PbV2DealingRangeSnap &dr,
                                   const PbV2OteSnap &ote, const PbV2PoiSnap &poi,
                                   const double pullback_score, const double threshold_atr)
     {
      PbV2DepthSnap depth;
      ZeroMemory(depth);
      if(m15.atr <= 0 || dom == 0) return depth;

      depth.valid = true;
      const double px = m15.close_px;
      double ote_target = 0, poi_target = 0, fib382 = 0, fib50 = 0, fib618 = 0;
      double weight_sum = 0, target_mid = 0;

      if(dr.valid && dr.range_high > dr.range_low)
        {
         const double span = dr.range_high - dr.range_low;
         if(dom > 0)
           {
            fib382 = dr.range_high - span * 0.382;
            fib50 = dr.range_high - span * 0.50;
            fib618 = dr.range_high - span * 0.618;
            if(ote.valid && ote.ote_mid > 0 && ote.ote_mid < px) ote_target = ote.ote_mid;
            if(poi.valid && poi.mid > 0 && poi.mid < px) poi_target = poi.mid;
           }
         else
           {
            fib382 = dr.range_low + span * 0.382;
            fib50 = dr.range_low + span * 0.50;
            fib618 = dr.range_low + span * 0.618;
            if(ote.valid && ote.ote_mid > 0 && ote.ote_mid > px) ote_target = ote.ote_mid;
            if(poi.valid && poi.mid > 0 && poi.mid > px) poi_target = poi.mid;
           }
        }

      if(ote_target > 0) { target_mid += ote_target * 0.40; weight_sum += 0.40; }
      if(poi_target > 0) { target_mid += poi_target * 0.35; weight_sum += 0.35; }
      if(fib618 > 0)     { target_mid += fib618 * 0.25; weight_sum += 0.25; }

      const double heuristic_dist = Clamp(pullback_score / 100.0 * threshold_atr * 1.7, 0.15, 2.5) * m15.atr;
      const double heuristic = px + (dom > 0 ? -1 : 1) * heuristic_dist;

      if(weight_sum > 0)
         target_mid = target_mid / weight_sum * 0.85 + heuristic * 0.15;
      else
         target_mid = heuristic;

      if(dom > 0)
        {
         depth.target_high = (ote.valid ? ote.ote_high : fib382);
         depth.target_mid = target_mid;
         depth.target_low = (ote.valid ? ote.ote_low : fib618);
         if(poi.valid && poi.lower > 0) depth.target_low = MathMin(depth.target_low, poi.lower);
        }
      else
        {
         depth.target_low = (ote.valid ? ote.ote_low : fib382);
         depth.target_mid = target_mid;
         depth.target_high = (ote.valid ? ote.ote_high : fib618);
         if(poi.valid && poi.upper > 0) depth.target_high = MathMax(depth.target_high, poi.upper);
        }

      depth.expected_pullback_atr = MathAbs(px - target_mid) / m15.atr;

      if(dr.valid && dr.range_high > dr.range_low)
        {
         const double span = dr.range_high - dr.range_low;
         if(dom > 0)
            depth.fib_retrace_pct = Clamp((dr.range_high - target_mid) / span * 100.0, 0, 100);
         else
            depth.fib_retrace_pct = Clamp((target_mid - dr.range_low) / span * 100.0, 0, 100);
        }

      if(ote.valid && poi.valid) depth.source = "ote+poi";
      else if(ote.valid) depth.source = "ote";
      else if(poi.valid) depth.source = "poi";
      else depth.source = "heuristic";

      if(depth.expected_pullback_atr < 0.5)
         depth.expected_depth = "SHALLOW";
      else if(depth.expected_pullback_atr < 1.0)
         depth.expected_depth = "MODERATE";
      else if(depth.expected_pullback_atr < 1.75)
         depth.expected_depth = "DEEP";
      else
         depth.expected_depth = "STRUCTURAL_FAILURE";

      return depth;
     }

   double CalcContinuationAfterPullback(const int dom, const double trend_strength, const double align,
                                        const double protected_intact, const double reversal_risk,
                                        const PbV2OteSnap &ote, const PbV2PoiSnap &poi,
                                        const PbV2LiquiditySnap &liq, const PbV2DisplacementSnap &disp)
     {
      double score = Clamp(
         trend_strength * 0.28 +
         protected_intact * 0.22 +
         align * 0.15 +
         ote.alignment_score * 0.12 +
         (poi.valid ? poi.confluence_score : 40) * 0.10 +
         (100.0 - reversal_risk) * 0.08 +
         disp.score * 0.05, 0, 100);

      if(ote.poi_overlaps_ote) score = Clamp(score + 8, 0, 100);
      if(ote.price_in_ote && protected_intact >= 80) score = Clamp(score + 5, 0, 100);
      if(poi.valid && poi.price_inside && poi.pullback_target_score >= 70) score = Clamp(score + 6, 0, 100);
      if(liq.valid && liq.state == PBV2_LIQ_REJECTED &&
         ((dom > 0 && liq.draw == "buy_side") || (dom < 0 && liq.draw == "sell_side")))
         score = Clamp(score - 15, 0, 100);
      if(poi.valid && poi.mitigation_pct >= 75) score = Clamp(score - 8, 0, 100);
      return score;
     }

   double CalcExtension(const PbV2TfSnap &s)
     {
      if(s.atr <= 0) return 0;
      double d20 = MathAbs(s.close_px - s.ema_fast) / s.atr;
      double d50 = MathAbs(s.close_px - s.ema_slow) / s.atr;
      double dbb = MathAbs(s.close_px - s.bb_middle) / s.atr;
      double ext_raw = (d20 * 0.45 + d50 * 0.25 + dbb * 0.30) * 28.0;
      if(s.close_px <= s.bb_lower || s.close_px >= s.bb_upper)
         ext_raw += 12.0;
      return Clamp(ext_raw, 0, 100);
     }

   double CalcRsiRolloverScore(const int dom, const PbV2TfSnap &m15, const PbV2TfSnap &m5s)
     {
      double score = 0;
      if(dom > 0)
        {
         if(m15.rsi >= 68 && m15.rsi < m15.rsi_prev)
            score = 85;
         else if(m15.rsi >= m_cfg.rsi_ob)
            score = 55;
         else if(m5s.rsi >= m_cfg.rsi_ob && m5s.rsi < m5s.rsi_prev)
            score = 70;
        }
      else if(dom < 0)
        {
         if(m15.rsi <= 32 && m15.rsi > m15.rsi_prev)
            score = 85;
         else if(m15.rsi <= m_cfg.rsi_os)
            score = 55;
         else if(m5s.rsi <= m_cfg.rsi_os && m5s.rsi > m5s.rsi_prev)
            score = 70;
        }
      return Clamp(score, 0, 100);
     }

   double CalcBbReclaimScore(const PbV2TfSnap &m15, const PbV2TfSnap &m5s)
     {
      if(m15.bb_outside_then_in || m5s.bb_outside_then_in)
         return 100;
      return 0;
     }

   double CalcLtfPullbackScore(const int dom, const PbV2StructureSnap &m5s, const PbV2StructureSnap &m15s)
     {
      if(dom > 0)
        {
         if(m5s.state == PBV2_BULL_PULLBACK) return 90;
         if(m5s.bearish_choch && !m15s.bearish_choch) return 60;
        }
      else if(dom < 0)
        {
         if(m5s.state == PBV2_BEAR_PULLBACK) return 90;
         if(m5s.bullish_choch && !m15s.bullish_choch) return 60;
        }
      return 0;
     }

   double CalcTrendAlignScore(const int dom, const PbV2TfSnap &h1, const PbV2TfSnap &m15, const PbV2TfSnap &m5s)
     {
      if(dom == 0) return 40;
      int match = 0;
      if(h1.trend_dir == dom) match++;
      if(m15.trend_dir == dom) match++;
      if(m5s.trend_dir == dom) match++;
      if(h1.trend_dir != 0 && m15.trend_dir != 0 && h1.trend_dir != m15.trend_dir)
         return 20;
      if(match == 3) return 100;
      if(match == 2) return 75;
      if(match == 1) return 45;
      return 30;
     }

   double CalcAdxContinuationScore(const PbV2TfSnap &m15)
     {
      if(m15.adx >= 25 && m15.adx >= m15.adx_prev)
         return 100;
      if(m15.adx >= m_cfg.adx_min && m15.adx >= m15.adx_prev)
         return 70;
      if(m15.adx < m_cfg.adx_min)
         return 20;
      return 40;
     }

   double CalcBosContinuationScore(const int dom, const PbV2StructureSnap &m15s, const PbV2StructureSnap &h1s)
     {
      if(dom > 0 && (m15s.bullish_bos || h1s.bullish_bos) && !m15s.bearish_choch && !h1s.bearish_choch)
         return 100;
      if(dom < 0 && (m15s.bearish_bos || h1s.bearish_bos) && !m15s.bullish_choch && !h1s.bullish_choch)
         return 100;
      return 30;
     }

   double CalcRsiHealthyScore(const int dom, const PbV2TfSnap &m15)
     {
      if(dom > 0 && m15.rsi >= 50 && m15.rsi <= 68 && m15.rsi >= m15.rsi_prev)
         return 100;
      if(dom < 0 && m15.rsi <= 50 && m15.rsi >= 32 && m15.rsi <= m15.rsi_prev)
         return 100;
      return 35;
     }

   double CalcProtectedIntactScore(const int dom, const PbV2StructureSnap &m15s, const PbV2StructureSnap &h1s)
     {
      if(dom > 0)
        {
         if(h1s.bearish_choch) return 0;
         if(m15s.bearish_choch) return 25;
         if(m15s.protected_low > 0) return 100;
         return 60;
        }
      if(dom < 0)
        {
         if(h1s.bullish_choch) return 0;
         if(m15s.bullish_choch) return 25;
         if(m15s.protected_high > 0) return 100;
         return 60;
        }
      return 50;
     }

   double CalcReversalRiskScore(const int dom, const PbV2TfSnap &h1, const PbV2TfSnap &m15, const PbV2TfSnap &m5s)
     {
      double risk = 0;
      if(dom > 0)
        {
         if(h1.structure.bearish_choch) risk += 45;
         else if(m15.structure.bearish_choch) risk += 30;
         else if(m5s.structure.bearish_choch) risk += 12;
         if(m15.rsi_div_bear || m5s.rsi_div_bear) risk += 10;
        }
      else if(dom < 0)
        {
         if(h1.structure.bullish_choch) risk += 45;
         else if(m15.structure.bullish_choch) risk += 30;
         else if(m5s.structure.bullish_choch) risk += 12;
         if(m15.rsi_div_bull || m5s.rsi_div_bull) risk += 10;
        }
      return Clamp(risk, 0, 100);
     }

   string MapStateV2(const VantagePullbackV2Snapshot &r, const bool conflict)
     {
      if(r.insufficient_data) return "INSUFFICIENT DATA";
      if(conflict) return "CONFLICTING TIMEFRAMES";
      if(r.reversal_risk_score >= 65) return "STRUCTURAL REVERSAL RISK";
      if(r.reversal_risk_score >= 45) return "POSSIBLE REVERSAL — UNCONFIRMED";
      if(r.poi_price_inside && r.poi_pullback_target_score >= 70 && r.pullback_score >= 50)
         return "INSIDE POI — PULLBACK REACTION ZONE";
      if(r.poi_price_approaching && r.poi_pullback_target_score >= 65 && r.pullback_score >= 52)
         return "POI RETRACE APPROACHING — WATCH REACTION";
      if(r.price_in_ote && r.ote_valid && r.poi_overlaps_ote && r.pullback_score >= 50)
         return "OTE + POI CONFLUENCE — PULLBACK TARGET";
      if(r.price_in_ote && r.ote_valid && r.pullback_score >= 48)
         return "PRICE IN OTE — WATCH PULLBACK REACTION";
      if(r.continuation_after_pullback_score >= 78 &&
         (r.price_in_ote || r.poi_price_inside) && r.reversal_risk_score < 35)
         return "POST-PULLBACK RESUMPTION LIKELY";
      if(r.liquidity_state == "swept" && r.immediate_continuation_score < 50)
         return "LIQUIDITY SWEEP — WAIT FOR CONFIRMATION";
      if(r.liquidity_state == "rejected" && r.pullback_score >= 55)
         return "LIQUIDITY REJECTION — PULLBACK PRESSURE";
      if(r.entry_location_score <= 34 && r.trend_strength >= 60)
         return "NO TRADE — POOR ENTRY LOCATION";
      if(r.extension_score >= 75 && r.entry_location_score <= 45)
         return "TREND STRONG — WAIT FOR PULLBACK";
      if(r.extension_score >= 75 && r.immediate_continuation_score < 55)
         return "TREND STRONG — MARKET EXTENDED";
      if(r.displacement_score >= 70 && r.extension_score >= 65 && r.pullback_score >= 55)
         return "IMPULSE STRONG — WAIT FOR RETRACEMENT";
      if(r.pullback_score >= 60 && r.immediate_continuation_score < 45)
         return "PULLBACK DEVELOPING";
      if(r.pullback_score >= 55 && r.extension_score >= 50)
         return "WAIT FOR PULLBACK";
      if(r.immediate_continuation_score >= 65 && r.extension_score < 50 && r.entry_location_score >= 50)
         return "STRONG TREND — CONTINUATION FAVORED";
      if(r.continuation_after_pullback_score >= 70 && r.pullback_score >= 45)
         return "TREND RESUMPTION SETUP";
      if(r.immediate_continuation_score < 35 && r.pullback_score < 40)
         return "RANGE / CONSOLIDATION";
      return "NO TRADE / WAIT";
     }

   bool FillTf(const int idx, PbV2TfSnap &s)
     {
      ZeroMemory(s);
      s.timeframe = TfAt(idx);
      MqlRates bar;
      if(!ClosedBar(s.timeframe, bar)) return false;
      s.close_px = bar.close;
      s.bar_time = bar.time;
      if(!Copy1(m_hEmaF[idx], 0, 1, s.ema_fast)) return false;
      if(!Copy1(m_hEmaS[idx], 0, 1, s.ema_slow)) return false;
      if(!Copy1(m_hEmaL[idx], 0, 1, s.ema_long)) return false;
      Copy1(m_hEmaF[idx], 0, 2, s.ema_fast_prev);
      if(!Copy1(m_hRsi[idx], 0, 1, s.rsi)) return false;
      Copy1(m_hRsi[idx], 0, 2, s.rsi_prev);
      if(!Copy1(m_hAtr[idx], 0, 1, s.atr) || s.atr <= 0) return false;
      if(!Copy1(m_hBb[idx], 0, 1, s.bb_upper)) return false;
      if(!Copy1(m_hBb[idx], 1, 1, s.bb_middle)) return false;
      if(!Copy1(m_hBb[idx], 2, 1, s.bb_lower)) return false;
      Copy1(m_hAdx[idx], 0, 1, s.adx);
      Copy1(m_hAdx[idx], 0, 2, s.adx_prev);
      Copy1(m_hAdx[idx], 1, 1, s.plus_di);
      Copy1(m_hAdx[idx], 2, 1, s.minus_di);

      s.extension = CalcExtension(s);

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

      AnalyzeStructureV2(s.timeframe, s.structure);
      DetectCandleReject(s.timeframe, s.candle_reject_bull, s.candle_reject_bear);
      DetectRsiDiv(s.timeframe, m_hRsi[idx], s.rsi_div_bull, s.rsi_div_bear);

      bool stack_bull = (s.ema_fast > s.ema_slow && s.ema_slow > s.ema_long);
      bool stack_bear = (s.ema_fast < s.ema_slow && s.ema_slow < s.ema_long);
      bool slope_bull = (s.ema_fast > s.ema_fast_prev);
      bool slope_bear = (s.ema_fast < s.ema_fast_prev);
      bool px_bull = (s.close_px > s.ema_fast && s.close_px > s.ema_slow);
      bool px_bear = (s.close_px < s.ema_fast && s.close_px < s.ema_slow);
      bool di_bull = (s.plus_di > s.minus_di);
      bool di_bear = (s.minus_di > s.plus_di);
      int score = 0;
      if(stack_bull) score += 2; if(stack_bear) score -= 2;
      if(slope_bull) score += 1; if(slope_bear) score -= 1;
      if(px_bull) score += 1; if(px_bear) score -= 1;
      if(s.structure.state == PBV2_BULL_CONTINUATION || s.structure.bullish_bos) score += 1;
      if(s.structure.state == PBV2_BEAR_CONTINUATION || s.structure.bearish_bos) score -= 1;
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

public:
   CVantagePullbackV2(void) { ZeroMemory(m_last); m_last_m5_bar = 0; }

   bool Init(const string symbol, const VantagePullbackV2Config &cfg)
     {
      m_symbol = symbol;
      m_cfg = cfg;
      if(m_cfg.min_fvg_atr <= 0) m_cfg.min_fvg_atr = 0.12;
      if(m_cfg.max_poi_scan <= 0) m_cfg.max_poi_scan = 80;
      if(m_cfg.poi_approach_atr <= 0) m_cfg.poi_approach_atr = 0.50;
      if(m_cfg.ote_low_pct <= 0) m_cfg.ote_low_pct = 0.618;
      if(m_cfg.ote_mid_pct <= 0) m_cfg.ote_mid_pct = 0.705;
      if(m_cfg.ote_high_pct <= 0) m_cfg.ote_high_pct = 0.790;
      m_last_m5_bar = 0;
      ZeroMemory(m_last);
      for(int i = 0; i < 3; i++)
        {
         ENUM_TIMEFRAMES tf = TfAt(i);
         m_hEmaF[i] = iMA(m_symbol, tf, m_cfg.ema_fast, 0, MODE_EMA, PRICE_CLOSE);
         m_hEmaS[i] = iMA(m_symbol, tf, m_cfg.ema_slow, 0, MODE_EMA, PRICE_CLOSE);
         m_hEmaL[i] = iMA(m_symbol, tf, m_cfg.ema_long, 0, MODE_EMA, PRICE_CLOSE);
         m_hRsi[i] = iRSI(m_symbol, tf, m_cfg.rsi_period, PRICE_CLOSE);
         m_hAtr[i] = iATR(m_symbol, tf, m_cfg.atr_period);
         m_hBb[i] = iBands(m_symbol, tf, m_cfg.bb_period, 0, m_cfg.bb_dev, PRICE_CLOSE);
         m_hAdx[i] = iADX(m_symbol, tf, m_cfg.adx_period);
         if(m_hEmaF[i] == INVALID_HANDLE || m_hRsi[i] == INVALID_HANDLE || m_hAtr[i] == INVALID_HANDLE)
            return false;
        }
      return true;
     }

   void Release(void)
     {
      for(int i = 0; i < 3; i++)
        {
         Rel(m_hEmaF[i]); Rel(m_hEmaS[i]); Rel(m_hEmaL[i]);
         Rel(m_hRsi[i]); Rel(m_hAtr[i]); Rel(m_hBb[i]); Rel(m_hAdx[i]);
        }
     }

   VantagePullbackV2Snapshot Last(void) const { return m_last; }

   bool Evaluate(const bool force, VantagePullbackV2Snapshot &out,
                 const bool lg_active, const VantageLiquidityGrabResult &lg,
                 const bool gsm_active, const VantageGoldSMCResult &gsm)
     {
      ZeroMemory(out);
      out.valid = false;
      out.symbol = m_symbol;
      out.evaluated_at = TimeCurrent();

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

      PbV2TfSnap h1, m15, m5s;
      if(!FillTf(0, h1) || !FillTf(1, m15) || !FillTf(2, m5s))
        {
         out.insufficient_data = true;
         out.market_state = "INSUFFICIENT DATA";
         out.explanation = "Insufficient multi-timeframe indicator history.";
         m_last = out;
         return false;
        }

      int dom = 0;
      double wsum = h1.trend_dir * 3.0 + m15.trend_dir * 2.0 + m5s.trend_dir * 1.0;
      if(wsum >= 2) dom = 1;
      else if(wsum <= -2) dom = -1;
      else dom = (h1.trend_dir != 0 ? h1.trend_dir : m15.trend_dir);

      bool conflict = (h1.trend_dir != 0 && m15.trend_dir != 0 && h1.trend_dir != m15.trend_dir);

      out.dominant_dir = dom;
      out.dominant_trend = h1.trend_label;
      if(StringFind(out.dominant_trend, "Bull") < 0 && StringFind(out.dominant_trend, "Bear") < 0)
         out.dominant_trend = (dom > 0 ? "Moderate Bullish" : (dom < 0 ? "Moderate Bearish" : "Neutral"));

      out.extension_score = Clamp(m15.extension * 0.55 + m5s.extension * 0.45, 0, 100);
      out.trend_strength = Clamp(h1.trend_strength * 0.5 + m15.trend_strength * 0.35 + m5s.trend_strength * 0.15, 0, 100);

      out.horizon_tf = m_cfg.horizon_tf;
      out.horizon_bars = m_cfg.prediction_bars;
      out.horizon_minutes = TfMinutes(m_cfg.horizon_tf) * m_cfg.prediction_bars;
      out.pullback_threshold_atr = m_cfg.pullback_atr_threshold;
      out.pullback_event_definition =
         "Experimental: within " + IntegerToString(out.horizon_bars) + " " +
         EnumToString(out.horizon_tf) + " bars, price retraces >= " +
         DoubleToString(out.pullback_threshold_atr, 2) + " M15 ATR against reference close without protected-structure invalidation first.";

      out.h1_structure = h1.structure.state_label;
      out.m15_structure = m15.structure.state_label;
      out.m5_structure = m5s.structure.state_label;
      out.bullish_bos = (h1.structure.bullish_bos || m15.structure.bullish_bos || m5s.structure.bullish_bos);
      out.bearish_bos = (h1.structure.bearish_bos || m15.structure.bearish_bos || m5s.structure.bearish_bos);
      out.bullish_choch = (h1.structure.bullish_choch || m15.structure.bullish_choch || m5s.structure.bullish_choch);
      out.bearish_choch = (h1.structure.bearish_choch || m15.structure.bearish_choch || m5s.structure.bearish_choch);
      out.bullish_mss = (h1.structure.bullish_mss || m15.structure.bullish_mss || m5s.structure.bullish_mss);
      out.bearish_mss = (h1.structure.bearish_mss || m15.structure.bearish_mss || m5s.structure.bearish_mss);
      out.protected_high = m15.structure.protected_high;
      out.protected_low = m15.structure.protected_low;

      // --- Milestone 2 engines ---
      PbV2DisplacementSnap disp = CalcDisplacement(dom, m15, m5s);
      ApplyMssDisplacementGate(m15.structure, disp.score);
      ApplyMssDisplacementGate(h1.structure, disp.score * 0.85);
      out.displacement_score = disp.score;
      out.disp_body = disp.body;
      out.disp_range = disp.range;
      out.disp_persistence = disp.persistence;
      out.disp_close_quality = disp.close_quality;
      out.disp_ema = disp.ema_accel;
      out.disp_bos = disp.bos;
      out.disp_fvg = disp.fvg;

      PbV2MomentumSnap mom = ClassifyMomentum(dom, m15, m5s);
      out.momentum_state = mom.state_label;
      out.rsi_level = mom.rsi_level;
      out.rsi_slope = mom.rsi_slope;

      PbV2DealingRangeSnap dr = CalcDealingRange(dom, m15);
      out.dealing_range_low = dr.range_low;
      out.dealing_range_high = dr.range_high;
      out.range_position_pct = dr.position_pct;
      out.premium_discount_location = dr.location;

      // --- Milestone 3 liquidity ---
      PbV2LiquiditySnap liq = ResolveLiquidity(dom, m15, m5s, lg_active, lg);
      out.liquidity_draw = liq.draw;
      out.liquidity_state = liq.state_label;
      out.liquidity_target_price = liq.target_price;
      out.liquidity_target_label = liq.target_label;
      out.liquidity_distance_atr = liq.distance_atr;
      out.liquidity_from_grab_module = liq.from_liquidity_grab;

      // --- Milestone 4 POI / FVG / OB ---
      PbV2PoiSnap poi = ResolvePoi(dom, m15, dr, gsm_active, gsm);
      out.poi_primary_type = poi.primary_type;
      out.poi_primary_dir = poi.primary_dir;
      out.poi_status = poi.status;
      out.poi_upper = poi.upper;
      out.poi_lower = poi.lower;
      out.poi_mid = poi.mid;
      out.poi_quality = poi.quality;
      out.poi_mitigation_pct = poi.mitigation_pct;
      out.poi_distance_atr = poi.distance_atr;
      out.poi_pullback_target_score = poi.pullback_target_score;
      out.poi_confluence_score = poi.confluence_score;
      out.poi_fvg_count = poi.fvg_count;
      out.poi_ob_count = poi.ob_count;
      out.poi_from_gold_smc = poi.from_gold_smc;
      out.poi_price_inside = poi.price_inside;
      out.poi_price_approaching = poi.price_approaching;

      // --- Milestone 5 OTE + expected depth ---
      PbV2OteSnap ote = ResolveOte(dom, m15, dr, poi, gsm_active, gsm);
      out.ote_valid = ote.valid;
      out.ote_low = ote.ote_low;
      out.ote_mid = ote.ote_mid;
      out.ote_high = ote.ote_high;
      out.price_in_ote = ote.price_in_ote;
      out.poi_overlaps_ote = ote.poi_overlaps_ote;
      out.ote_alignment_score = ote.alignment_score;
      out.ote_from_gold_smc = ote.from_gold_smc;

      // Refresh aggregate structure flags after MSS gate
      out.h1_structure = h1.structure.state_label;
      out.m15_structure = m15.structure.state_label;
      out.bullish_mss = (h1.structure.bullish_mss || m15.structure.bullish_mss || m5s.structure.bullish_mss);
      out.bearish_mss = (h1.structure.bearish_mss || m15.structure.bearish_mss || m5s.structure.bearish_mss);

      const double bb_reclaim = CalcBbReclaimScore(m15, m5s);
      const double ltf_pull = CalcLtfPullbackScore(dom, m5s.structure, m15.structure);
      const double reject = CalcRejectionScore(m15, m5s, dom);
      const double disp_exhaust = CalcDisplacementExhaustion(disp, out.extension_score);
      const double pd_pressure = dr.valid ? dr.pd_pressure_score : 45;
      const double liq_pressure = liq.valid ? liq.pullback_pressure : 40;
      const double liq_cont = liq.valid ? liq.continuation_boost : 40;
      const double poi_target = poi.valid ? poi.pullback_target_score : 35;

      // --- Independent scores (Milestone 4 weights) ---
      out.pullback_score = Clamp(
         out.extension_score * 0.16 +
         mom.rollover_score * 0.16 +
         pd_pressure * 0.09 +
         reject * 0.08 +
         ltf_pull * 0.09 +
         bb_reclaim * 0.09 +
         disp_exhaust * 0.13 +
         liq_pressure * 0.11 +
         poi_target * 0.09, 0, 100);

      const double align = CalcTrendAlignScore(dom, h1, m15, m5s);
      const double adx_cont = CalcAdxContinuationScore(m15);
      const double bos_cont = CalcBosContinuationScore(dom, m15.structure, h1.structure);
      const double poi_cont = poi.valid ? poi.confluence_score : 40;

      out.immediate_continuation_score = Clamp(
         align * 0.21 +
         (100.0 - out.extension_score) * 0.17 +
         adx_cont * 0.13 +
         bos_cont * 0.13 +
         mom.continuation_score * 0.13 +
         disp.score * 0.08 +
         liq_cont * 0.09 +
         poi_cont * 0.06, 0, 100);

      const double protected_intact = CalcProtectedIntactScore(dom, m15.structure, h1.structure);

      out.reversal_risk_score = CalcReversalRiskScore(dom, h1, m15, m5s);
      if(liq.valid && liq.state == PBV2_LIQ_REJECTED)
        {
         if((dom > 0 && liq.draw == "buy_side") || (dom < 0 && liq.draw == "sell_side"))
            out.reversal_risk_score = Clamp(out.reversal_risk_score + 12, 0, 100);
        }

      out.continuation_after_pullback_score = CalcContinuationAfterPullback(
         dom, out.trend_strength, align, protected_intact, out.reversal_risk_score,
         ote, poi, liq, disp);

      out.entry_location_score = CalcEntryLocationScore(
         dom, out.extension_score, out.reversal_risk_score, protected_intact, dr, disp);
      if(poi.valid && poi.pullback_target_score >= 65)
         out.entry_location_score = Clamp(out.entry_location_score + 6, 0, 100);
      else if(poi.valid && poi.price_inside && poi.pullback_target_score >= 75)
         out.entry_location_score = Clamp(out.entry_location_score + 10, 0, 100);
      if(ote.valid && ote.poi_overlaps_ote)
         out.entry_location_score = Clamp(out.entry_location_score + 5, 0, 100);

      PbV2DepthSnap depth = CalcExpectedDepth(dom, m15, dr, ote, poi, out.pullback_score,
                                              out.pullback_threshold_atr);
      out.depth_target_low = depth.target_low;
      out.depth_target_mid = depth.target_mid;
      out.depth_target_high = depth.target_high;
      out.depth_fib_retrace_pct = depth.fib_retrace_pct;
      out.depth_source = depth.source;
      out.expected_pullback_atr = depth.expected_pullback_atr;
      out.expected_depth = depth.expected_depth;

      string pos = "", neg = "";
      if(align >= 75) pos += "H1/M15 trend alignment;";
      if(conflict) neg += "H1 vs M15 conflict;";
      if(out.extension_score >= 50) pos += "Market extended (ATR-normalized);";
      if(mom.state == PBV2_MOM_ROLLOVER) pos += "RSI rollover pressure;";
      if(mom.state == PBV2_MOM_DIVERGENCE) pos += "RSI divergence;";
      if(mom.state == PBV2_MOM_CONTINUATION || mom.state == PBV2_MOM_STRONG) pos += "Healthy momentum;";
      if(bb_reclaim >= 50) pos += "Bollinger reclaim;";
      if(reject >= 50) pos += "Rejection candle / BB reclaim;";
      if(disp.score >= 65) pos += "Strong displacement;";
      if(disp_exhaust >= 60) pos += "Displacement exhaustion risk;";
      if(dr.valid) pos += "Dealing range " + dr.location + ";";
      if(liq.valid)
        {
         pos += "Liquidity " + liq.draw + " " + liq.state_label + ";";
         if(liq.from_liquidity_grab) pos += "Liquidity Grab module;";
        }
      if(poi.valid)
        {
         pos += "POI " + poi.primary_dir + " " + poi.primary_type + " Q=" +
                DoubleToString(poi.quality, 0) + ";";
         if(poi.from_gold_smc) pos += "Gold SMC POI;";
         if(poi.price_inside) pos += "Price inside POI;";
         else if(poi.price_approaching) pos += "Approaching POI retrace;";
        }
      if(ote.valid)
        {
         if(ote.price_in_ote) pos += "Price in OTE;";
         if(ote.poi_overlaps_ote) pos += "POI overlaps OTE;";
         if(ote.from_gold_smc) pos += "Gold SMC OTE;";
        }
      if(out.depth_source != "" && out.depth_source != "heuristic")
         pos += "Depth from " + out.depth_source + ";";
      if(out.entry_location_score <= 34) neg += "Poor entry location / chase risk;";
      if(out.entry_location_score >= 65) pos += "Favorable entry location;";
      if(poi.valid && poi.mitigation_pct >= 70) neg += "Primary POI heavily mitigated;";
      if(!poi.valid) neg += "No ranked POI target;";
      if(ote.valid && !ote.price_in_ote && out.extension_score >= 60) neg += "Outside OTE confluence;";
      if(m15.structure.bullish_bos || m15.structure.bearish_bos) pos += "Confirmed BOS on M15;";
      if(m15.structure.bullish_choch || m15.structure.bearish_choch) pos += "M15 CHoCH;";
      if(m15.structure.bullish_mss || m15.structure.bearish_mss) pos += "M15 MSS (displacement confirmed);";
      if(h1.structure.bullish_choch || h1.structure.bearish_choch) pos += "H1 CHoCH;";
      if(m5s.structure.bearish_choch && dom > 0 && !m15.structure.bearish_choch)
         pos += "M5 local pullback only;";
      if(!m15.structure.bullish_choch && !m15.structure.bearish_choch && !h1.structure.bullish_choch && !h1.structure.bearish_choch)
         neg += "No HTF CHoCH confirmation;";

      out.reasons_pos = pos;
      out.reasons_neg = neg;
      out.market_state = MapStateV2(out, conflict);
      out.short_reason = out.market_state;

      out.explanation =
         "Pullback Desk V2 M7 (experimental). Dominant: " + out.dominant_trend +
         ". Extension=" + DoubleToString(out.extension_score, 0) +
         "/100. Displacement=" + DoubleToString(out.displacement_score, 0) +
         "/100. Entry location=" + DoubleToString(out.entry_location_score, 0) + "/100. " +
         "Liquidity " + out.liquidity_draw + " " + out.liquidity_state +
         " @ " + DoubleToString(out.liquidity_distance_atr, 2) + " ATR. " +
         "POI " + (poi.valid ? out.poi_primary_dir + " " + out.poi_primary_type : "none") + ". " +
         "Depth " + out.expected_depth + " (~" + DoubleToString(out.expected_pullback_atr, 2) + " ATR, " +
         out.depth_source + "). " +
         "Cont-after-PB=" + DoubleToString(out.continuation_after_pullback_score, 0) + "/100. " +
         "Pullback score=" + DoubleToString(out.pullback_score, 0) +
         "/100. State: " + out.market_state + ". Advisory only.";

      out.eval_bar_m5 = m5.time;
      out.reference_close = m15.close_px;
      out.atr_m15 = m15.atr;
      out.csv_logging_enabled = m_cfg.csv_log_enable;
      out.valid = true;
      out.insufficient_data = false;
      m_last = out;
      m_last_m5_bar = m5.time;
      return true;
     }

   string ToJson(const VantagePullbackV2Snapshot &r)
     {
      string j = "{";
      j += "\"version\":\"pullback_v2\",";
      j += "\"milestone\":7,";
      j += "\"experimental\":true,";
      j += "\"calibrated\":false,";
      j += "\"valid\":" + (r.valid ? "true" : "false") + ",";
      j += "\"symbol\":\"" + JsonEscape(r.symbol) + "\",";
      j += "\"evaluated_at\":" + IntegerToString((long)r.evaluated_at) + ",";
      j += "\"dominant_direction\":" + IntegerToString(r.dominant_dir) + ",";
      j += "\"dominant_trend\":\"" + JsonEscape(r.dominant_trend) + "\",";
      j += "\"trend_strength\":" + DoubleToJson(r.trend_strength, 1) + ",";
      j += "\"extension_score\":" + DoubleToJson(r.extension_score, 1) + ",";
      j += "\"displacement_score\":" + DoubleToJson(r.displacement_score, 1) + ",";
      j += "\"entry_location_score\":" + DoubleToJson(r.entry_location_score, 1) + ",";
      j += "\"pullback_score\":" + DoubleToJson(r.pullback_score, 1) + ",";
      j += "\"immediate_continuation_score\":" + DoubleToJson(r.immediate_continuation_score, 1) + ",";
      j += "\"continuation_after_pullback_score\":" + DoubleToJson(r.continuation_after_pullback_score, 1) + ",";
      j += "\"reversal_risk_score\":" + DoubleToJson(r.reversal_risk_score, 1) + ",";
      j += "\"expected_pullback_atr\":" + DoubleToJson(r.expected_pullback_atr, 2) + ",";
      j += "\"expected_depth\":\"" + JsonEscape(r.expected_depth) + "\",";
      j += "\"prediction_horizon\":{";
      j += "\"timeframe\":\"" + JsonEscape(EnumToString(r.horizon_tf)) + "\",";
      j += "\"bars\":" + IntegerToString(r.horizon_bars) + ",";
      j += "\"minutes\":" + IntegerToString(r.horizon_minutes) + "},";
      j += "\"pullback_event_definition\":{";
      j += "\"threshold_atr\":" + DoubleToJson(r.pullback_threshold_atr, 2) + ",";
      j += "\"description\":\"" + JsonEscape(r.pullback_event_definition) + "\"},";
      j += "\"market_structure\":{";
      j += "\"h1\":\"" + JsonEscape(r.h1_structure) + "\",";
      j += "\"m15\":\"" + JsonEscape(r.m15_structure) + "\",";
      j += "\"m5\":\"" + JsonEscape(r.m5_structure) + "\",";
      j += "\"bullish_bos\":" + (r.bullish_bos ? "true" : "false") + ",";
      j += "\"bearish_bos\":" + (r.bearish_bos ? "true" : "false") + ",";
      j += "\"bullish_choch\":" + (r.bullish_choch ? "true" : "false") + ",";
      j += "\"bearish_choch\":" + (r.bearish_choch ? "true" : "false") + ",";
      j += "\"bullish_mss\":" + (r.bullish_mss ? "true" : "false") + ",";
      j += "\"bearish_mss\":" + (r.bearish_mss ? "true" : "false") + ",";
      j += "\"protected_high\":" + DoubleToJson(r.protected_high, 8) + ",";
      j += "\"protected_low\":" + DoubleToJson(r.protected_low, 8) + "},";
      j += "\"displacement\":{";
      j += "\"body\":" + DoubleToJson(r.disp_body, 1) + ",";
      j += "\"range\":" + DoubleToJson(r.disp_range, 1) + ",";
      j += "\"persistence\":" + DoubleToJson(r.disp_persistence, 1) + ",";
      j += "\"close_quality\":" + DoubleToJson(r.disp_close_quality, 1) + ",";
      j += "\"ema_accel\":" + DoubleToJson(r.disp_ema, 1) + ",";
      j += "\"bos\":" + DoubleToJson(r.disp_bos, 1) + ",";
      j += "\"fvg\":" + DoubleToJson(r.disp_fvg, 1) + "},";
      j += "\"momentum\":{";
      j += "\"state\":\"" + JsonEscape(r.momentum_state) + "\",";
      j += "\"rsi_level\":" + DoubleToJson(r.rsi_level, 1) + ",";
      j += "\"rsi_slope\":" + DoubleToJson(r.rsi_slope, 2) + "},";
      j += "\"dealing_range\":{";
      j += "\"low\":" + DoubleToJson(r.dealing_range_low, 8) + ",";
      j += "\"high\":" + DoubleToJson(r.dealing_range_high, 8) + ",";
      j += "\"position_pct\":" + DoubleToJson(r.range_position_pct, 1) + ",";
      j += "\"location\":\"" + JsonEscape(r.premium_discount_location) + "\"},";
      j += "\"liquidity\":{";
      j += "\"draw\":\"" + JsonEscape(r.liquidity_draw) + "\",";
      j += "\"state\":\"" + JsonEscape(r.liquidity_state) + "\",";
      j += "\"target_price\":" + DoubleToJson(r.liquidity_target_price, 8) + ",";
      j += "\"target_label\":\"" + JsonEscape(r.liquidity_target_label) + "\",";
      j += "\"distance_atr\":" + DoubleToJson(r.liquidity_distance_atr, 3) + ",";
      j += "\"from_liquidity_grab\":" + (r.liquidity_from_grab_module ? "true" : "false") + "},";
      j += "\"poi\":{";
      j += "\"primary_type\":\"" + JsonEscape(r.poi_primary_type) + "\",";
      j += "\"primary_dir\":\"" + JsonEscape(r.poi_primary_dir) + "\",";
      j += "\"status\":\"" + JsonEscape(r.poi_status) + "\",";
      j += "\"upper\":" + DoubleToJson(r.poi_upper, 8) + ",";
      j += "\"lower\":" + DoubleToJson(r.poi_lower, 8) + ",";
      j += "\"mid\":" + DoubleToJson(r.poi_mid, 8) + ",";
      j += "\"quality\":" + DoubleToJson(r.poi_quality, 1) + ",";
      j += "\"mitigation_pct\":" + DoubleToJson(r.poi_mitigation_pct, 1) + ",";
      j += "\"distance_atr\":" + DoubleToJson(r.poi_distance_atr, 3) + ",";
      j += "\"pullback_target_score\":" + DoubleToJson(r.poi_pullback_target_score, 1) + ",";
      j += "\"confluence_score\":" + DoubleToJson(r.poi_confluence_score, 1) + ",";
      j += "\"fvg_count\":" + IntegerToString(r.poi_fvg_count) + ",";
      j += "\"ob_count\":" + IntegerToString(r.poi_ob_count) + ",";
      j += "\"price_inside\":" + (r.poi_price_inside ? "true" : "false") + ",";
      j += "\"price_approaching\":" + (r.poi_price_approaching ? "true" : "false") + ",";
      j += "\"from_gold_smc\":" + (r.poi_from_gold_smc ? "true" : "false") + "},";
      j += "\"poi_primary_type\":\"" + JsonEscape(r.poi_primary_type) + "\",";
      j += "\"poi_pullback_target_score\":" + DoubleToJson(r.poi_pullback_target_score, 1) + ",";
      j += "\"ote\":{";
      j += "\"valid\":" + (r.ote_valid ? "true" : "false") + ",";
      j += "\"ote_low\":" + DoubleToJson(r.ote_low, 8) + ",";
      j += "\"ote_mid\":" + DoubleToJson(r.ote_mid, 8) + ",";
      j += "\"ote_high\":" + DoubleToJson(r.ote_high, 8) + ",";
      j += "\"price_in_ote\":" + (r.price_in_ote ? "true" : "false") + ",";
      j += "\"poi_overlaps_ote\":" + (r.poi_overlaps_ote ? "true" : "false") + ",";
      j += "\"alignment_score\":" + DoubleToJson(r.ote_alignment_score, 1) + ",";
      j += "\"from_gold_smc\":" + (r.ote_from_gold_smc ? "true" : "false") + "},";
      j += "\"depth\":{";
      j += "\"target_low\":" + DoubleToJson(r.depth_target_low, 8) + ",";
      j += "\"target_mid\":" + DoubleToJson(r.depth_target_mid, 8) + ",";
      j += "\"target_high\":" + DoubleToJson(r.depth_target_high, 8) + ",";
      j += "\"expected_pullback_atr\":" + DoubleToJson(r.expected_pullback_atr, 2) + ",";
      j += "\"expected_depth\":\"" + JsonEscape(r.expected_depth) + "\",";
      j += "\"fib_retrace_pct\":" + DoubleToJson(r.depth_fib_retrace_pct, 1) + ",";
      j += "\"source\":\"" + JsonEscape(r.depth_source) + "\"},";
      j += "\"reference_close\":" + DoubleToJson(r.reference_close, 8) + ",";
      j += "\"atr_m15\":" + DoubleToJson(r.atr_m15, 8) + ",";
      j += "\"calibration\":{";
      j += "\"csv_logging_enabled\":" + (r.csv_logging_enabled ? "true" : "false") + ",";
      j += "\"outcome_labeler\":\"offline_python_only\",";
      j += "\"shadow_compare\":\"v1_vs_v2\",";
      j += "\"bucket_report\":\"offline_python_only\"},";
      j += "\"market_state\":\"" + JsonEscape(r.market_state) + "\",";
      j += "\"explanation\":\"" + JsonEscape(r.explanation) + "\",";
      j += "\"short_reason\":\"" + JsonEscape(r.short_reason) + "\",";
      j += "\"reasons_positive\":\"" + JsonEscape(r.reasons_pos) + "\",";
      j += "\"reasons_negative\":\"" + JsonEscape(r.reasons_neg) + "\"";
      j += "}";
      return j;
     }
  };

#endif
