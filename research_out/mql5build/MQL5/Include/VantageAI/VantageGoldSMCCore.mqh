//+------------------------------------------------------------------+
//| VantageGoldSMCCore.mqh                                           |
//| Phase 2 — swings, external/internal structure, BOS/CHoCH/MSS     |
//| Closed bars only — advisory                                      |
//+------------------------------------------------------------------+
#ifndef VANTAGE_GOLD_SMC_CORE_MQH
#define VANTAGE_GOLD_SMC_CORE_MQH

#include "VantageGoldSMCTypes.mqh"

class CVantageGoldSMCCore
  {
private:
   string               m_symbol;
   VantageGoldSMCConfig m_cfg;
   int                  m_h_atr_d1;
   int                  m_h_atr_h4;
   int                  m_h_atr_h1;
   int                  m_h_atr_m15;
   int                  m_h_atr_m5;

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

   int AtrHandleFor(const ENUM_TIMEFRAMES tf)
     {
      if(tf == m_cfg.tf_macro) return m_h_atr_d1;
      if(tf == m_cfg.tf_major) return m_h_atr_h4;
      if(tf == m_cfg.tf_bias) return m_h_atr_h1;
      if(tf == m_cfg.tf_confirm) return m_h_atr_m15;
      if(tf == m_cfg.tf_exec) return m_h_atr_m5;
      return INVALID_HANDLE;
     }

   bool CopyAtr(const ENUM_TIMEFRAMES tf, double &out_atr)
     {
      out_atr = 0.0;
      int h = AtrHandleFor(tf);
      if(h == INVALID_HANDLE) return false;
      double a[];
      if(CopyBuffer(h, 0, 1, 1, a) != 1) return false;
      out_atr = a[0];
      return (out_atr > 0.0 && MathIsValidNumber(out_atr));
     }

   // Confirmed fractal swings on series rates (index 0 = newest closed)
   // Fills highs/lows newest-first; returns counts
   int CollectSwings(MqlRates &rates[], const int n,
                     const int left, const int right,
                     double &hi_px[], datetime &hi_tm[], int &hi_n,
                     double &lo_px[], datetime &lo_tm[], int &lo_n,
                     const int max_keep)
     {
      hi_n = 0; lo_n = 0;
      ArrayResize(hi_px, max_keep);
      ArrayResize(hi_tm, max_keep);
      ArrayResize(lo_px, max_keep);
      ArrayResize(lo_tm, max_keep);
      if(n < left + right + 3)
         return 0;

      for(int i = right; i < n - left; i++)
        {
         bool is_hi = true, is_lo = true;
         for(int k = 1; k <= left; k++)
           {
            if(rates[i].high < rates[i + k].high) is_hi = false;
            if(rates[i].low > rates[i + k].low) is_lo = false;
           }
         for(int k = 1; k <= right; k++)
           {
            if(rates[i].high <= rates[i - k].high) is_hi = false;
            if(rates[i].low >= rates[i - k].low) is_lo = false;
           }
         if(is_hi && hi_n < max_keep)
           {
            hi_px[hi_n] = rates[i].high;
            hi_tm[hi_n] = rates[i].time;
            hi_n++;
           }
         if(is_lo && lo_n < max_keep)
           {
            lo_px[lo_n] = rates[i].low;
            lo_tm[lo_n] = rates[i].time;
            lo_n++;
           }
         if(hi_n >= max_keep && lo_n >= max_keep)
            break;
        }
      return hi_n + lo_n;
     }

   ENUM_SMC_DIRECTION BiasFromSwings(const bool hh, const bool hl,
                                     const bool lh, const bool ll)
     {
      if(hh && hl) return SMC_DIR_BULLISH;
      if(lh && ll) return SMC_DIR_BEARISH;
      if((hh || hl) && (lh || ll)) return SMC_DIR_CONFLICTING;
      if(hh || hl) return SMC_DIR_BULLISH;
      if(lh || ll) return SMC_DIR_BEARISH;
      return SMC_DIR_NEUTRAL;
     }

   double DisplacementScore(const MqlRates &bar, const double atr)
     {
      if(atr <= 0.0) return 0.0;
      double range = bar.high - bar.low;
      if(range <= 0.0) return 0.0;
      double body = MathAbs(bar.close - bar.open);
      double body_atr = body / atr;
      double range_atr = range / atr;
      double close_pos = (bar.close >= bar.open)
                         ? (bar.close - bar.low) / range
                         : (bar.high - bar.close) / range;
      double score = 0.0;
      score += Clamp(body_atr / MathMax(0.01, m_cfg.min_displacement_atr), 0.0, 1.5) * 45.0;
      score += Clamp(range_atr / 1.2, 0.0, 1.0) * 25.0;
      score += Clamp(close_pos, 0.0, 1.0) * 20.0;
      double wick = range - body;
      if(body >= wick) score += 10.0;
      return Clamp(score, 0.0, 100.0);
     }

   bool BodyClearsLevel(const MqlRates &bar, const double level, const bool bullish_break,
                        const double atr)
     {
      double pen = m_cfg.min_close_penetration_atr * atr;
      if(m_cfg.break_mode == SMC_BREAK_WICK)
        {
         if(bullish_break) return (bar.high > level);
         return (bar.low < level);
        }
      if(bullish_break)
        {
         if(bar.close <= level) return false;
         if(m_cfg.break_mode == SMC_BREAK_BODY_CLOSE) return true;
         return (bar.close >= level + pen);
        }
      if(bar.close >= level) return false;
      if(m_cfg.break_mode == SMC_BREAK_BODY_CLOSE) return true;
      return (bar.close <= level - pen);
     }

   bool WickOnlyBeyond(const MqlRates &bar, const double level, const bool bullish_probe)
     {
      if(bullish_probe)
         return (bar.high > level && bar.close <= level);
      return (bar.low < level && bar.close >= level);
     }

   void AnalyzeTf(const ENUM_TIMEFRAMES tf, VantageGoldSMCTfStructure &out)
     {
      ZeroMemory(out);
      out.timeframe = tf;
      out.external_bias = SMC_DIR_NEUTRAL;
      out.internal_bias = SMC_DIR_NEUTRAL;
      out.last_event = SMC_EVT_NONE;
      out.label = "";

      const int look = MathMax(40, m_cfg.structure_lookback);
      const int need = look + m_cfg.swing_left_ext + m_cfg.swing_right_ext + 5;
      MqlRates rates[];
      int n = CopyRates(m_symbol, tf, 1, need, rates);
      if(n < m_cfg.swing_left_ext + m_cfg.swing_right_ext + 10)
        {
         out.valid = false;
         out.label = "Insufficient history";
         return;
        }
      ArraySetAsSeries(rates, true);
      out.bar_time = rates[0].time;
      out.close_px = rates[0].close;
      if(!CopyAtr(tf, out.atr) || out.atr <= 0.0)
        {
         // fallback: average range of last 14
         double sum = 0.0;
         int cnt = MathMin(14, n);
         for(int i = 0; i < cnt; i++)
            sum += (rates[i].high - rates[i].low);
         out.atr = sum / MathMax(1, cnt);
        }

      double ehi[], elo[], ihi[], ilo[];
      datetime eht[], elt[], iht[], ilt[];
      int ehn = 0, eln = 0, ihn = 0, iln = 0;
      CollectSwings(rates, n, m_cfg.swing_left_ext, m_cfg.swing_right_ext,
                    ehi, eht, ehn, elo, elt, eln, 8);
      CollectSwings(rates, n, m_cfg.swing_left_int, m_cfg.swing_right_int,
                    ihi, iht, ihn, ilo, ilt, iln, 8);

      if(ehn >= 1) out.ext_swing_high = ehi[0];
      if(eln >= 1) out.ext_swing_low = elo[0];
      if(ehn >= 1 && eln >= 1)
        {
         out.ext_range_high = MathMax(ehi[0], (ehn >= 2 ? ehi[1] : ehi[0]));
         out.ext_range_low = MathMin(elo[0], (eln >= 2 ? elo[1] : elo[0]));
         // Prefer last two external pivots as dealing range
         if(ehn >= 1 && eln >= 1)
           {
            out.ext_range_high = ehi[0];
            out.ext_range_low = elo[0];
            if(ehn >= 2 && ehi[1] > out.ext_range_high) out.ext_range_high = ehi[1];
            if(eln >= 2 && elo[1] < out.ext_range_low) out.ext_range_low = elo[1];
           }
        }
      if(ihn >= 1) out.int_swing_high = ihi[0];
      if(iln >= 1) out.int_swing_low = ilo[0];

      if(ehn >= 2 && eln >= 2)
        {
         out.ext_hh = (ehi[0] > ehi[1]);
         out.ext_hl = (elo[0] > elo[1]);
         out.ext_lh = (ehi[0] < ehi[1]);
         out.ext_ll = (elo[0] < elo[1]);
         out.external_bias = BiasFromSwings(out.ext_hh, out.ext_hl, out.ext_lh, out.ext_ll);
        }
      if(ihn >= 2 && iln >= 2)
        {
         out.int_hh = (ihi[0] > ihi[1]);
         out.int_hl = (ilo[0] > ilo[1]);
         out.int_lh = (ihi[0] < ihi[1]);
         out.int_ll = (ilo[0] < ilo[1]);
         out.internal_bias = BiasFromSwings(out.int_hh, out.int_hl, out.int_lh, out.int_ll);
        }

      out.displacement_score = DisplacementScore(rates[0], out.atr);
      const bool disp_ok = (out.displacement_score >= m_cfg.min_displacement_score) ||
                           (m_cfg.break_mode != SMC_BREAK_BODY_DISPLACEMENT);
      const bool strong_disp = (out.displacement_score >= m_cfg.min_displacement_score + 10.0);

      // --- Event detection on newest closed bar ---
      // External BOS (continuation)
      if(out.external_bias == SMC_DIR_BULLISH && ehn >= 1)
        {
         if(BodyClearsLevel(rates[0], ehi[0], true, out.atr) && disp_ok)
           {
            out.bos_bull = true;
            out.last_event = SMC_EVT_EXTERNAL_BOS_BULL;
            out.broken_level = ehi[0];
           }
         else if(WickOnlyBeyond(rates[0], ehi[0], true))
           {
            out.wick_sweep_only = true;
            if(out.last_event == SMC_EVT_NONE)
               out.last_event = SMC_EVT_WICK_SWEEP_NO_BOS;
           }
        }
      if(out.external_bias == SMC_DIR_BEARISH && eln >= 1)
        {
         if(BodyClearsLevel(rates[0], elo[0], false, out.atr) && disp_ok)
           {
            out.bos_bear = true;
            out.last_event = SMC_EVT_EXTERNAL_BOS_BEAR;
            out.broken_level = elo[0];
           }
         else if(WickOnlyBeyond(rates[0], elo[0], false))
           {
            out.wick_sweep_only = true;
            if(out.last_event == SMC_EVT_NONE)
               out.last_event = SMC_EVT_WICK_SWEEP_NO_BOS;
           }
        }

      // Internal BOS
      if(out.internal_bias == SMC_DIR_BULLISH && ihn >= 1)
        {
         if(BodyClearsLevel(rates[0], ihi[0], true, out.atr) && disp_ok)
           {
            out.bos_bull = true;
            if(out.last_event != SMC_EVT_EXTERNAL_BOS_BULL)
               out.last_event = SMC_EVT_INTERNAL_BOS_BULL;
            out.broken_level = ihi[0];
           }
        }
      if(out.internal_bias == SMC_DIR_BEARISH && iln >= 1)
        {
         if(BodyClearsLevel(rates[0], ilo[0], false, out.atr) && disp_ok)
           {
            out.bos_bear = true;
            if(out.last_event != SMC_EVT_EXTERNAL_BOS_BEAR)
               out.last_event = SMC_EVT_INTERNAL_BOS_BEAR;
            out.broken_level = ilo[0];
           }
        }

      // CHoCH — break against established sequence (internal meaningful level)
      if(out.external_bias == SMC_DIR_BEARISH && ihn >= 1)
        {
         // bullish CHoCH: break internal lower-high while bearish external
         if(BodyClearsLevel(rates[0], ihi[0], true, out.atr))
           {
            out.choch_bull = true;
            out.broken_level = ihi[0];
            if(strong_disp && disp_ok)
              {
               out.mss_bull = true;
               out.last_event = SMC_EVT_MSS_BULL;
              }
            else
              {
               out.last_event = SMC_EVT_CHOCH_BULL;
              }
           }
         else if(WickOnlyBeyond(rates[0], ihi[0], true))
           {
            out.wick_sweep_only = true;
            if(out.last_event == SMC_EVT_NONE)
               out.last_event = SMC_EVT_WICK_SWEEP_NO_BOS;
           }
        }
      if(out.external_bias == SMC_DIR_BULLISH && iln >= 1)
        {
         if(BodyClearsLevel(rates[0], ilo[0], false, out.atr))
           {
            out.choch_bear = true;
            out.broken_level = ilo[0];
            if(strong_disp && disp_ok)
              {
               out.mss_bear = true;
               out.last_event = SMC_EVT_MSS_BEAR;
              }
            else
              {
               out.last_event = SMC_EVT_CHOCH_BEAR;
              }
           }
         else if(WickOnlyBeyond(rates[0], ilo[0], false))
           {
            out.wick_sweep_only = true;
            if(out.last_event == SMC_EVT_NONE)
               out.last_event = SMC_EVT_WICK_SWEEP_NO_BOS;
           }
        }

      // Label
      string eb = SmcDirectionToString(out.external_bias);
      string ib = SmcDirectionToString(out.internal_bias);
      out.label = "Ext " + eb + " / Int " + ib;
      if(out.last_event != SMC_EVT_NONE)
         out.label += " | " + SmcEventToString(out.last_event);
      out.valid = true;
     }

   string ClassifyM5VsH1(const VantageGoldSMCTfStructure &h1,
                         const VantageGoldSMCTfStructure &m5)
     {
      if(!h1.valid || !m5.valid)
         return "";
      if(h1.external_bias == SMC_DIR_BEARISH && m5.internal_bias == SMC_DIR_BULLISH)
         return "Bearish retracement — internal bullish correction (M5 does not override H1)";
      if(h1.external_bias == SMC_DIR_BULLISH && m5.internal_bias == SMC_DIR_BEARISH)
         return "Bullish retracement — internal bearish correction (M5 does not override H1)";
      if(h1.external_bias == SMC_DIR_BEARISH && m5.mss_bull)
         return "Possible bullish MSS on M5 — treat as early watch; H1 still bearish until H1 confirms";
      if(h1.external_bias == SMC_DIR_BULLISH && m5.mss_bear)
         return "Possible bearish MSS on M5 — treat as early watch; H1 still bullish until H1 confirms";
      if(h1.external_bias == m5.external_bias && h1.external_bias != SMC_DIR_NEUTRAL)
         return "Aligned with H1 external structure";
      return "Mixed internal / external structure";
     }

   ENUM_SMC_DIRECTION ResolveMacro(const VantageGoldSMCTfStructure &d1,
                                   const VantageGoldSMCTfStructure &h4)
     {
      if(d1.valid && h4.valid)
        {
         if(d1.external_bias == h4.external_bias)
            return d1.external_bias;
         if(d1.external_bias != SMC_DIR_NEUTRAL && h4.external_bias != SMC_DIR_NEUTRAL &&
            d1.external_bias != h4.external_bias)
            return SMC_DIR_CONFLICTING;
         if(d1.external_bias != SMC_DIR_NEUTRAL)
            return d1.external_bias;
         return h4.external_bias;
        }
      if(h4.valid) return h4.external_bias;
      if(d1.valid) return d1.external_bias;
      return SMC_DIR_NEUTRAL;
     }

public:
   CVantageGoldSMCCore(void)
      : m_symbol(""),
        m_h_atr_d1(INVALID_HANDLE), m_h_atr_h4(INVALID_HANDLE),
        m_h_atr_h1(INVALID_HANDLE), m_h_atr_m15(INVALID_HANDLE),
        m_h_atr_m5(INVALID_HANDLE)
     {
      ZeroMemory(m_cfg);
     }

   bool Init(const string symbol, const VantageGoldSMCConfig &cfg)
     {
      Release();
      m_symbol = symbol;
      m_cfg = cfg;
      if(m_cfg.atr_period <= 0) m_cfg.atr_period = 14;
      if(m_cfg.swing_left_ext <= 0) m_cfg.swing_left_ext = 5;
      if(m_cfg.swing_right_ext <= 0) m_cfg.swing_right_ext = 5;
      if(m_cfg.swing_left_int <= 0) m_cfg.swing_left_int = 2;
      if(m_cfg.swing_right_int <= 0) m_cfg.swing_right_int = 2;
      if(m_cfg.structure_lookback < 40) m_cfg.structure_lookback = 80;
      if(m_cfg.min_displacement_atr <= 0.0) m_cfg.min_displacement_atr = 0.45;
      if(m_cfg.min_displacement_score <= 0.0) m_cfg.min_displacement_score = 55.0;
      if(m_cfg.min_close_penetration_atr < 0.0) m_cfg.min_close_penetration_atr = 0.05;

      m_h_atr_d1 = iATR(m_symbol, m_cfg.tf_macro, m_cfg.atr_period);
      m_h_atr_h4 = iATR(m_symbol, m_cfg.tf_major, m_cfg.atr_period);
      m_h_atr_h1 = iATR(m_symbol, m_cfg.tf_bias, m_cfg.atr_period);
      m_h_atr_m15 = iATR(m_symbol, m_cfg.tf_confirm, m_cfg.atr_period);
      m_h_atr_m5 = iATR(m_symbol, m_cfg.tf_exec, m_cfg.atr_period);
      if(m_h_atr_d1 == INVALID_HANDLE || m_h_atr_h4 == INVALID_HANDLE ||
         m_h_atr_h1 == INVALID_HANDLE || m_h_atr_m15 == INVALID_HANDLE ||
         m_h_atr_m5 == INVALID_HANDLE)
        {
         Print("[GoldSMC][STRUCTURE] ATR handle init failed for ", symbol);
         Release();
         return false;
        }
      return true;
     }

   void Release(void)
     {
      Rel(m_h_atr_d1);
      Rel(m_h_atr_h4);
      Rel(m_h_atr_h1);
      Rel(m_h_atr_m15);
      Rel(m_h_atr_m5);
     }

   // Fills structure fields on result; returns false if insufficient data
   bool Analyze(VantageGoldSMCResult &r)
     {
      VantageGoldSMCTfStructure d1, h4, h1, m15, m5;
      AnalyzeTf(m_cfg.tf_macro, d1);
      AnalyzeTf(m_cfg.tf_major, h4);
      AnalyzeTf(m_cfg.tf_bias, h1);
      AnalyzeTf(m_cfg.tf_confirm, m15);
      AnalyzeTf(m_cfg.tf_exec, m5);

      if(!h1.valid && !h4.valid)
        {
         r.analysis_active = false;
         r.setup_phase = SmcPhaseToString(SMC_PHASE_INSUFFICIENT_DATA);
         r.structure_status = "Insufficient structure history";
         r.technical_narrative = "Not enough closed bars to map Gold external/internal structure.";
         r.reasons_against = "Insufficient history on H4/H1;";
         return false;
        }

      r.macro_bias = ResolveMacro(d1, h4);
      r.h4_bias = h4.valid ? h4.external_bias : SMC_DIR_NEUTRAL;
      r.h1_bias = h1.valid ? h1.external_bias : SMC_DIR_NEUTRAL;
      r.m15_bias = m15.valid ? m15.internal_bias : SMC_DIR_NEUTRAL;
      r.m5_bias = m5.valid ? m5.internal_bias : SMC_DIR_NEUTRAL;

      // HTF conflict
      if(r.h4_bias != SMC_DIR_NEUTRAL && r.h1_bias != SMC_DIR_NEUTRAL &&
         r.h4_bias != r.h1_bias && r.h4_bias != SMC_DIR_CONFLICTING &&
         r.h1_bias != SMC_DIR_CONFLICTING)
        {
         // Keep individual biases; flag in status
         r.structure_status = "H4/H1 CONFLICTING — higher-timeframe priority to H4 for bias narrative";
        }
      else
        {
         r.structure_status = "H4 Ext " + SmcDirectionToString(r.h4_bias) +
                              " | H1 Ext " + SmcDirectionToString(r.h1_bias) +
                              " | M15 Int " + SmcDirectionToString(r.m15_bias) +
                              " | M5 Int " + SmcDirectionToString(r.m5_bias);
        }

      r.m5_context = ClassifyM5VsH1(h1, m5);

      // Prefer H1 external range for display; fallback H4
      if(h1.valid && h1.ext_range_high > h1.ext_range_low)
        {
         r.external_range_high = h1.ext_range_high;
         r.external_range_low = h1.ext_range_low;
        }
      else if(h4.valid)
        {
         r.external_range_high = h4.ext_range_high;
         r.external_range_low = h4.ext_range_low;
        }
      if(r.external_range_high > r.external_range_low)
         r.external_equilibrium = 0.5 * (r.external_range_high + r.external_range_low);

      // Latest event: prefer H1, then M15, then M5 (never let M5 event alone rewrite HTF story)
      ENUM_SMC_STRUCTURE_EVENT ev = SMC_EVT_NONE;
      double disp = 0.0;
      if(h1.valid && h1.last_event != SMC_EVT_NONE) { ev = h1.last_event; disp = h1.displacement_score; }
      else if(m15.valid && m15.last_event != SMC_EVT_NONE) { ev = m15.last_event; disp = m15.displacement_score; }
      else if(m5.valid && m5.last_event != SMC_EVT_NONE) { ev = m5.last_event; disp = m5.displacement_score; }
      r.latest_structure_event = SmcEventToString(ev);
      if(disp >= 75.0) r.displacement_status = "Strong (" + DoubleToString(disp, 0) + ")";
      else if(disp >= 55.0) r.displacement_status = "Moderate (" + DoubleToString(disp, 0) + ")";
      else if(disp > 0.0) r.displacement_status = "Weak (" + DoubleToString(disp, 0) + ")";
      else r.displacement_status = "No displacement";

      r.analysis_active = true;
      r.engine_phase = 2;
      r.setup_type = "No Valid SMC Setup";
      r.setup_phase = SmcPhaseToString(SMC_PHASE_STRUCTURE_READY);
      r.confidence_score = 0.0;
      r.quality_grade = "Invalid";

      // Narrative
      string narr = "Gold D1/H4 macro bias: " + SmcDirectionToString(r.macro_bias) +
                    ". H1 external structure is " + SmcDirectionToString(r.h1_bias) + ".";
      if(r.m5_context != "")
         narr += " " + r.m5_context + ".";
      if(ev != SMC_EVT_NONE)
         narr += " Latest structure event: " + SmcEventToString(ev) + ".";
      if(ev == SMC_EVT_WICK_SWEEP_NO_BOS)
         narr += " Wick beyond structure is not treated as BOS.";
      if(ev == SMC_EVT_CHOCH_BULL || ev == SMC_EVT_CHOCH_BEAR)
         narr += " CHoCH is an early warning, not a confirmed reversal.";
      narr += " Liquidity, FVG, and order-block engines are not active yet (Phase 3+).";
      r.technical_narrative = narr;

      r.reasons_for = "Closed-bar swing map on D1/H4/H1/M15/M5;";
      if(h1.valid) r.reasons_for += "H1 external " + SmcDirectionToString(r.h1_bias) + ";";
      r.reasons_against = "No liquidity/FVG/OB confluence yet;";
      if(StringFind(r.structure_status, "CONFLICTING") >= 0)
         r.reasons_against += "H4 vs H1 conflict;";
      if(r.m5_context != "" && StringFind(r.m5_context, "does not override") >= 0)
         r.reasons_against += "LTF correction only;";

      r.recommendation = "WAIT — map structure only. No full SMC setup until liquidity + POI phases.";
      r.status_line = "ACTIVE – GOLD ONLY (Phase 2 structure)";

      Print("[GoldSMC][STRUCTURE][H1] ", h1.label,
            " close=", DoubleToString(h1.close_px, _Digits),
            " disp=", DoubleToString(h1.displacement_score, 0));
      return true;
     }
  };

#endif
//+------------------------------------------------------------------+
