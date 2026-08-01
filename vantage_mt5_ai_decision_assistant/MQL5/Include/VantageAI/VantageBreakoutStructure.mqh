//+------------------------------------------------------------------+
//| VantageBreakoutStructure.mqh                                     |
//| Breakout Structure Intelligence Engine — facade + engine           |
//| Advisory-only — never opens, modifies, or closes trades          |
//+------------------------------------------------------------------+
#ifndef VANTAGE_BREAKOUT_STRUCTURE_MQH
#define VANTAGE_BREAKOUT_STRUCTURE_MQH

#include "VantageTypes.mqh"
#include "VantageBreakoutStructureTypes.mqh"
#include "VantageGoldSMCValidator.mqh"

#define BOS_OBJ_PREFIX "VAI_BOS_"

class CVantageBreakoutStructure
  {
private:
   string                      m_symbol;
   VantageBosConfig            m_cfg;
   VantageBosResult            m_last;
   CVantageGoldSymbolValidator m_validator;
   VantageBosSwing             m_swings[BOS_MAX_SWINGS];
   int                         m_swing_count;
   VantageBosTrendline         m_tl_bull;
   VantageBosTrendline         m_tl_bear;
   datetime                    m_last_m5_bar;
   datetime                    m_last_alert_time;
   string                      m_last_alert_key;
   int                         m_h_atr_h4, m_h_atr_h1, m_h_atr_m15, m_h_atr_m5;
   int                         m_h_rsi_m5, m_h_adx_h1;
   int                         m_h_ema20_h1, m_h_ema50_h1, m_h_ema200_h1;
   bool                        m_inited;

   void Rel(int &h) { if(h != INVALID_HANDLE) { IndicatorRelease(h); h = INVALID_HANDLE; } }

   void Debug(const string msg) const
     {
      if(!m_cfg.debug_log) return;
      Print("[BreakoutStructure] ", msg);
     }

   double ClampD(const double v, const double lo, const double hi) const
     {
      if(v < lo) return lo;
      if(v > hi) return hi;
      return v;
     }

   void ResetResult(VantageBosResult &r)
     {
      ZeroMemory(r);
      r.valid = false;
      r.symbol = m_symbol;
      r.engine_phase = 2;
      r.grade_label = "Reject";
      r.breakout_label = "Waiting";
      r.retest_label = "Waiting";
      r.sbr_label = "Waiting";
      r.rbs_label = "Waiting";
      r.breakout_type = "Waiting";
      r.breakout_lifecycle = "Waiting";
      r.retest_lifecycle = "Waiting";
      r.rbs_flip_lifecycle = "Waiting";
      r.sbr_flip_lifecycle = "Waiting";
      r.current_structure = "Range";
      r.structure_strength = "Weak";
      r.recommendation = "WAIT — monitoring breakout structure";
     }

   bool CopyRatesClosed(const ENUM_TIMEFRAMES tf, const int count, MqlRates &rates[])
     {
      ArraySetAsSeries(rates, true);
      return (CopyRates(m_symbol, tf, 1, count, rates) > 0);
     }

   double GetBuf(const int h, const int shift = 1)
     {
      if(h == INVALID_HANDLE) return 0.0;
      double b[];
      if(CopyBuffer(h, 0, shift, 1, b) != 1) return 0.0;
      return b[0];
     }

   double GetAtrTf(const ENUM_TIMEFRAMES tf)
     {
      int h = INVALID_HANDLE;
      if(tf == PERIOD_H4) h = m_h_atr_h4;
      else if(tf == PERIOD_H1) h = m_h_atr_h1;
      else if(tf == PERIOD_M15) h = m_h_atr_m15;
      else h = m_h_atr_m5;
      double a = GetBuf(h);
      if(a > 0) return a;
      int tmp = iATR(m_symbol, tf, m_cfg.atr_period);
      if(tmp == INVALID_HANDLE) return 0;
      double v = GetBuf(tmp);
      IndicatorRelease(tmp);
      return v;
     }

   bool IsSwingHigh(const MqlRates &rates[], const int i, const int left, const int right)
     {
      if(i < right || i + left >= ArraySize(rates)) return false;
      double h = rates[i].high;
      for(int k = 1; k <= left; k++) if(rates[i+k].high >= h) return false;
      for(int k = 1; k <= right; k++) if(rates[i-k].high >= h) return false;
      return true;
     }

   bool IsSwingLow(const MqlRates &rates[], const int i, const int left, const int right)
     {
      if(i < right || i + left >= ArraySize(rates)) return false;
      double l = rates[i].low;
      for(int k = 1; k <= left; k++) if(rates[i+k].low <= l) return false;
      for(int k = 1; k <= right; k++) if(rates[i-k].low >= l) return false;
      return true;
     }

   void CollectSwings(MqlRates &rates[], const int n, const double atr)
     {
      m_swing_count = 0;
      const int L = m_cfg.swing_left, R = m_cfg.swing_right;
      for(int i = R; i < MathMin(n - L, 80) && m_swing_count < BOS_MAX_SWINGS; i++)
        {
         if(IsSwingHigh(rates, i, L, R))
           {
            VantageBosSwing s;
            s.price = rates[i].high;
            s.time = rates[i].time;
            s.bar_index = i;
            s.atr = atr;
            s.is_high = true;
            double rng = rates[i].high - rates[i].low;
            s.strength = ClampD((rng / MathMax(atr, _Point)) * 25.0, 0, 100);
            s.label = "SH";
            m_swings[m_swing_count++] = s;
           }
         if(IsSwingLow(rates, i, L, R) && m_swing_count < BOS_MAX_SWINGS)
           {
            VantageBosSwing s;
            s.price = rates[i].low;
            s.time = rates[i].time;
            s.bar_index = i;
            s.atr = atr;
            s.is_high = false;
            double rng = rates[i].high - rates[i].low;
            s.strength = ClampD((rng / MathMax(atr, _Point)) * 25.0, 0, 100);
            s.label = "SL";
            m_swings[m_swing_count++] = s;
           }
        }
      // Classify HH HL LH LL on recent pairs
      double last_hi = 0, prev_hi = 0, last_lo = 0, prev_lo = 0;
      for(int i = 0; i < m_swing_count; i++)
        {
         if(m_swings[i].is_high)
           {
            prev_hi = last_hi; last_hi = m_swings[i].price;
            if(prev_hi > 0)
               m_swings[i].label = (last_hi > prev_hi) ? "HH" : "LH";
           }
         else
           {
            prev_lo = last_lo; last_lo = m_swings[i].price;
            if(prev_lo > 0)
               m_swings[i].label = (last_lo > prev_lo) ? "HL" : "LL";
           }
        }
     }

   ENUM_BOS_STRUCTURE StructureFromSwings(void)
     {
      bool hh = false, hl = false, lh = false, ll = false;
      for(int i = 0; i < m_swing_count; i++)
        {
         if(m_swings[i].label == "HH") hh = true;
         if(m_swings[i].label == "HL") hl = true;
         if(m_swings[i].label == "LH") lh = true;
         if(m_swings[i].label == "LL") ll = true;
        }
      if(hh && hl) return BOS_STRUCT_BULLISH;
      if(lh && ll) return BOS_STRUCT_BEARISH;
      if((hh||hl) && (lh||ll)) return BOS_STRUCT_CONFLICTING;
      if(hh || hl) return BOS_STRUCT_BULLISH;
      if(lh || ll) return BOS_STRUCT_BEARISH;
      return BOS_STRUCT_NEUTRAL;
     }

   double TlPriceAt(const VantageBosTrendline &tl, const datetime t) const
     {
      if(tl.time1 == tl.time2) return tl.price1;
      double dt = (double)(t - tl.time1);
      return tl.price1 + tl.slope * dt;
     }

   int CountTouches(MqlRates &rates[], const int n, const VantageBosTrendline &tl, const double atr)
     {
      if(tl.type == BOS_TL_NONE || n < 5) return 0;
      double tol = atr * m_cfg.tl_touch_atr;
      int touches = 0;
      for(int i = 2; i < MathMin(n, 60); i++)
        {
         double lp = TlPriceAt(tl, rates[i].time);
         if(tl.type == BOS_TL_BULLISH)
           {
            if(MathAbs(rates[i].low - lp) <= tol) touches++;
           }
         else if(tl.type == BOS_TL_BEARISH)
           {
            if(MathAbs(rates[i].high - lp) <= tol) touches++;
           }
        }
      return touches;
     }

   void BuildTrendline(MqlRates &rates[], const int n, const double atr, const bool bullish)
     {
      VantageBosTrendline tl;
      ZeroMemory(tl);
      tl.type = bullish ? BOS_TL_BULLISH : BOS_TL_BEARISH;
      // find two most recent valid pivots of correct type
      double p1 = 0, p2 = 0;
      datetime t1 = 0, t2 = 0;
      int found = 0;
      for(int i = 0; i < m_swing_count && found < 2; i++)
        {
         if(bullish && !m_swings[i].is_high && (m_swings[i].label == "HL" || m_swings[i].label == "SL"))
           {
            if(found == 0) { p1 = m_swings[i].price; t1 = m_swings[i].time; found++; }
            else { p2 = m_swings[i].price; t2 = m_swings[i].time; found++; }
           }
         if(!bullish && m_swings[i].is_high && (m_swings[i].label == "LH" || m_swings[i].label == "SH"))
           {
            if(found == 0) { p1 = m_swings[i].price; t1 = m_swings[i].time; found++; }
            else { p2 = m_swings[i].price; t2 = m_swings[i].time; found++; }
           }
        }
      if(found < 2 || t1 == t2) return;
      tl.price1 = p1; tl.price2 = p2; tl.time1 = t1; tl.time2 = t2;
      tl.slope = (p2 - p1) / (double)(t2 - t1);
      tl.angle_deg = MathAbs(MathArctan(tl.slope * 86400.0)) * 180.0 / 3.141592653589793;
      tl.touches = CountTouches(rates, n, tl, atr);
      tl.active = (tl.touches >= m_cfg.min_tl_touches);
      tl.strength = ClampD(tl.touches * 20.0 + tl.angle_deg * 0.5, 0, 100);
      if(bullish) m_tl_bull = tl; else m_tl_bear = tl;
     }

   bool ValidBodyBreak(const MqlRates &bar, const double level, const bool bullish, const double atr)
     {
      double pen = m_cfg.min_break_atr * atr;
      double body = MathAbs(bar.close - bar.open);
      double rng = bar.high - bar.low;
      if(rng <= 0) return false;
      double body_pct = body / rng;
      if(body_pct < m_cfg.min_body_break_pct) return false;
      if(bullish)
        {
         if(bar.close <= level) return false;
         if(bar.close - level < pen) return false;
         if(bar.high > level && bar.close <= level) return false; // wick only
         return (bar.close > bar.open);
        }
      if(bar.close >= level) return false;
      if(level - bar.close < pen) return false;
      if(bar.low < level && bar.close >= level) return false;
      return (bar.close < bar.open);
     }

   ENUM_BOS_BOS_CLASS DetectBos(MqlRates &rates[], const int n, const double atr, string &ev)
     {
      ev = "";
      if(n < 10 || m_swing_count < 2) return BOS_BOS_NONE;
      double sh = 0, sl = 0;
      for(int i = 0; i < m_swing_count; i++)
        {
         if(m_swings[i].is_high && sh == 0) sh = m_swings[i].price;
         if(!m_swings[i].is_high && sl == 0) sl = m_swings[i].price;
        }
      MqlRates bar = rates[0];
      double body = MathAbs(bar.close - bar.open);
      double body_pct = body / MathMax(bar.high - bar.low, _Point);
      if(sh > 0 && ValidBodyBreak(bar, sh, true, atr))
        {
         if(body_pct >= m_cfg.min_body_pct && (bar.close - sh) >= m_cfg.min_bos_atr * atr)
           { ev = "Bullish BOS above " + DoubleToString(sh, _Digits); return BOS_BOS_BULLISH; }
         ev = "Weak bullish BOS";
         return BOS_BOS_WEAK;
        }
      if(sl > 0 && ValidBodyBreak(bar, sl, false, atr))
        {
         if(body_pct >= m_cfg.min_body_pct && (sl - bar.close) >= m_cfg.min_bos_atr * atr)
           { ev = "Bearish BOS below " + DoubleToString(sl, _Digits); return BOS_BOS_BEARISH; }
         ev = "Weak bearish BOS";
         return BOS_BOS_WEAK;
        }
      if((sh > 0 && bar.high > sh && bar.close <= sh) || (sl > 0 && bar.low < sl && bar.close >= sl))
        { ev = "Wick beyond level — invalid BOS"; return BOS_BOS_INVALID; }
      return BOS_BOS_NONE;
     }

   ENUM_BOS_CHOCH_CLASS DetectChoch(const ENUM_BOS_STRUCTURE prior, const ENUM_BOS_BOS_CLASS bos)
     {
      if(bos == BOS_BOS_BULLISH && (prior == BOS_STRUCT_BEARISH || prior == BOS_STRUCT_CONFLICTING))
         return BOS_CHOCH_BULLISH;
      if(bos == BOS_BOS_BEARISH && (prior == BOS_STRUCT_BULLISH || prior == BOS_STRUCT_CONFLICTING))
         return BOS_CHOCH_BEARISH;
      return BOS_CHOCH_NONE;
     }

   ENUM_BOS_BREAK_CLASS DetectTrendlineBreak(MqlRates &rates[], const int n, const double atr,
                                               const VantageBosTrendline &tl, const double rsi)
     {
      if(!tl.active || n < 3) return BOS_BREAK_NONE;
      MqlRates bar = rates[0];
      double lp = TlPriceAt(tl, bar.time);
      bool bull_break = (tl.type == BOS_TL_BEARISH && bar.close > lp);
      bool bear_break = (tl.type == BOS_TL_BULLISH && bar.close < lp);
      if(!bull_break && !bear_break) return BOS_BREAK_NONE;

      if(!ValidBodyBreak(bar, lp, bull_break, atr)) return BOS_BREAK_FAKE;

      double body = MathAbs(bar.close - bar.open);
      double disp = body / MathMax(atr, _Point);
      bool rsi_ok = bull_break ? (rsi > 50) : (rsi < 50);

      // fake: next bar returns inside (check bar[1] if recent break)
      if(n >= 2)
        {
         double lp1 = TlPriceAt(tl, rates[1].time);
         if(bull_break && rates[1].close > lp1 && bar.close < lp) return BOS_BREAK_FAKE;
         if(bear_break && rates[1].close < lp1 && bar.close > lp) return BOS_BREAK_FAKE;
        }

      if(disp >= 0.75 && rsi_ok && tl.strength >= 60) return BOS_BREAK_INSTITUTIONAL;
      if(disp >= 0.45 && rsi_ok) return BOS_BREAK_STRONG;
      return BOS_BREAK_WEAK;
     }

   ENUM_BOS_RETEST_STATUS DetectRetest(MqlRates &rates[], const int n, const double atr,
                                        const VantageBosTrendline &tl, const ENUM_BOS_BREAK_CLASS brk)
     {
      if(brk == BOS_BREAK_NONE || brk == BOS_BREAK_FAKE || !tl.active || n < 5)
         return BOS_RETEST_NONE;
      double tol = atr * m_cfg.retest_tolerance_atr;
      bool bull_break = (tl.type == BOS_TL_BEARISH);
      for(int i = 0; i < MathMin(m_cfg.retest_max_bars, n - 1); i++)
        {
         double lp = TlPriceAt(tl, rates[i].time);
         if(bull_break)
           {
            if(MathAbs(rates[i].low - lp) <= tol && rates[i].close > lp)
               return (i == 0 ? BOS_RETEST_SUCCESS : BOS_RETEST_PENDING);
            if(i > 0 && rates[i].close < lp && rates[i-1].close > lp)
               return BOS_RETEST_FAILED;
           }
         else
           {
            if(MathAbs(rates[i].high - lp) <= tol && rates[i].close < lp)
               return (i == 0 ? BOS_RETEST_SUCCESS : BOS_RETEST_PENDING);
            if(i > 0 && rates[i].close > lp && rates[i-1].close < lp)
               return BOS_RETEST_FAILED;
           }
        }
      return BOS_RETEST_PENDING;
     }

   ENUM_BOS_FLIP_STATUS DetectFlip(MqlRates &rates[], const int n, const double level,
                                    const bool support_to_resistance, const double atr)
     {
      if(level <= 0 || n < 5) return BOS_FLIP_NONE;
      MqlRates bar = rates[0];
      double tol = atr * 0.15;
      if(support_to_resistance)
        {
         bool broke = false;
         for(int i = 2; i < MathMin(8, n); i++)
            if(rates[i].close < level - m_cfg.min_break_atr * atr) { broke = true; break; }
         if(!broke) return BOS_FLIP_NONE;
         if(MathAbs(bar.high - level) <= tol && bar.close < level && bar.close < bar.open)
            return BOS_FLIP_VALID;
         if(MathAbs(bar.high - level) <= tol) return BOS_FLIP_WEAK;
         if(bar.close > level) return BOS_FLIP_FAILED;
        }
      else
        {
         bool broke = false;
         for(int i = 2; i < MathMin(8, n); i++)
            if(rates[i].close > level + m_cfg.min_break_atr * atr) { broke = true; break; }
         if(!broke) return BOS_FLIP_NONE;
         if(MathAbs(bar.low - level) <= tol && bar.close > level && bar.close > bar.open)
            return BOS_FLIP_VALID;
         if(MathAbs(bar.low - level) <= tol) return BOS_FLIP_WEAK;
         if(bar.close < level) return BOS_FLIP_FAILED;
        }
      return BOS_FLIP_NONE;
     }

   string DominantStructure(const VantageBosResult &r) const
     {
      int bull = 0, bear = 0;
      if(r.market_structure_h4 == BOS_STRUCT_BULLISH) bull++;
      else if(r.market_structure_h4 == BOS_STRUCT_BEARISH) bear++;
      if(r.market_structure_h1 == BOS_STRUCT_BULLISH) bull++;
      else if(r.market_structure_h1 == BOS_STRUCT_BEARISH) bear++;
      if(r.market_structure_m15 == BOS_STRUCT_BULLISH) bull++;
      else if(r.market_structure_m15 == BOS_STRUCT_BEARISH) bear++;
      if(bull >= 2 && bull > bear) return "Bullish (HH-HL)";
      if(bear >= 2 && bear > bull) return "Bearish (LH-LL)";
      if(bull == bear && bull > 0) return "Range";
      if(bull > bear) return "Bullish (HH-HL)";
      if(bear > bull) return "Bearish (LH-LL)";
      return "Range";
     }

   string StructureStrengthLabel(const VantageBosResult &r, const double adx) const
     {
      double pts = 0;
      if(r.htf_aligned) pts += 35;
      if(r.market_structure_h1 != BOS_STRUCT_NEUTRAL) pts += 25;
      if(r.trendline_touches >= m_cfg.min_tl_touches) pts += 20;
      pts += ClampD(adx / 50.0, 0, 1) * 20;
      if(pts >= 65) return "Strong";
      if(pts >= 35) return "Moderate";
      return "Weak";
     }

   bool HorizontalBreakActive(MqlRates &m5[], const int n, const double pdh, const double pdl,
                               const double atr, double &level, string &dir) const
     {
      if(n < 1 || atr <= 0) return false;
      MqlRates bar = m5[0];
      if(pdh > 0 && bar.close > pdh && (bar.close - pdh) >= m_cfg.min_break_atr * atr)
        { level = pdh; dir = "bull"; return true; }
      if(pdl > 0 && bar.close < pdl && (pdl - bar.close) >= m_cfg.min_break_atr * atr)
        { level = pdl; dir = "bear"; return true; }
      if(pdh > 0 && bar.high > pdh && bar.close <= pdh) { level = pdh; dir = "bull"; return false; }
      if(pdl > 0 && bar.low < pdl && bar.close >= pdl) { level = pdl; dir = "bear"; return false; }
      return false;
     }

   bool MaBreakActive(MqlRates &m5[], const double ema50, const double atr, double &level, string &dir) const
     {
      if(ArraySize(m5) < 1 || ema50 <= 0) return false;
      MqlRates bar = m5[0];
      if(bar.close > ema50 && (bar.close - ema50) >= m_cfg.min_break_atr * atr)
        { level = ema50; dir = "bull"; return true; }
      if(bar.close < ema50 && (ema50 - bar.close) >= m_cfg.min_break_atr * atr)
        { level = ema50; dir = "bear"; return true; }
      return false;
     }

   void BuildModuleView(VantageBosResult &r, MqlRates &m5[], const int n,
                         const double pdh, const double pdl, const double atr_m5,
                         const double rsi, const double adx, const double ema50,
                         const VantageBosTrendline &active_tl)
     {
      r.current_structure = DominantStructure(r);
      r.structure_strength = StructureStrengthLabel(r, adx);
      r.current_price = (n > 0 ? m5[0].close : SymbolInfoDouble(m_symbol, SYMBOL_BID));

      double h_level = 0; string h_dir = "";
      bool h_conf = HorizontalBreakActive(m5, n, pdh, pdl, atr_m5, h_level, h_dir);
      bool h_pot = (h_level > 0 && !h_conf);

      ENUM_BOS_BREAK_CLASS tl_brk = r.breakout_status;
      bool tl_conf = (tl_brk == BOS_BREAK_STRONG || tl_brk == BOS_BREAK_INSTITUTIONAL);
      bool tl_pot = (tl_brk == BOS_BREAK_WEAK);

      double ma_level = 0; string ma_dir = "";
      bool ma_conf = MaBreakActive(m5, ema50, atr_m5, ma_level, ma_dir);

      bool channel_pot = (adx < 22 && r.structure_strength != "Strong");

      if(h_conf) { r.breakout_type = "Horizontal"; r.breakout_level = h_level; }
      else if(tl_conf || tl_pot) { r.breakout_type = "Trendline"; r.breakout_level = (active_tl.type != BOS_TL_NONE ? TlPriceAt(active_tl, m5[0].time) : 0); }
      else if(ma_conf) { r.breakout_type = "Moving Average"; r.breakout_level = ma_level; }
      else if(channel_pot) { r.breakout_type = "Channel"; r.breakout_level = (pdh > 0 && pdl > 0 ? (pdh + pdl) / 2.0 : 0); }
      else if(h_pot) { r.breakout_type = "Horizontal"; r.breakout_level = h_level; }
      else { r.breakout_type = "Waiting"; r.breakout_level = (pdh > 0 ? pdh : (pdl > 0 ? pdl : 0)); }

      r.lifecycle_failed = (tl_brk == BOS_BREAK_FAKE || r.retest_status == BOS_RETEST_FAILED);
      if(r.lifecycle_failed)
        {
         r.breakout_lifecycle = "Failed";
         r.lifecycle_stage = 5;
         r.lifecycle_failed = true;
        }
      else if(tl_conf || h_conf || ma_conf)
        {
         if(r.retest_status == BOS_RETEST_SUCCESS && r.ml.expected_follow_through >= 55)
           { r.breakout_lifecycle = "Completed"; r.lifecycle_stage = 5; }
         else if(r.retest_status == BOS_RETEST_SUCCESS)
           { r.breakout_lifecycle = "Continuation"; r.lifecycle_stage = 4; }
         else if(r.retest_status == BOS_RETEST_PENDING || r.retest_status == BOS_RETEST_SUCCESS)
           { r.breakout_lifecycle = "Retesting"; r.lifecycle_stage = 3; }
         else
           { r.breakout_lifecycle = "Confirmed Close"; r.lifecycle_stage = 2; }
        }
      else if(tl_pot || h_pot || tl_brk == BOS_BREAK_WEAK)
        { r.breakout_lifecycle = "Potential Break"; r.lifecycle_stage = 1; }
      else
        { r.breakout_lifecycle = "Waiting"; r.lifecycle_stage = 0; }

      r.breakout_confidence = ClampD(r.ml.prob_success, 0, 100);
      if(r.breakout_lifecycle == "Confirmed Close") r.breakout_confidence = MathMax(r.breakout_confidence, 70);
      if(r.breakout_lifecycle == "Potential Break") r.breakout_confidence = MathMax(r.breakout_confidence, 45);

      MqlRates bar;
      if(n > 0) bar = m5[0];
      else { ZeroMemory(bar); bar.close = SymbolInfoDouble(m_symbol, SYMBOL_BID); bar.open = bar.close; bar.high = bar.close; bar.low = bar.close; }
      double body = MathAbs(bar.close - bar.open);
      double rng = MathMax(bar.high - bar.low, _Point);
      double body_pct = body / rng;
      r.val_strong_close = (body_pct >= m_cfg.min_body_break_pct);
      r.val_closed_beyond_swing = (r.bos_class == BOS_BOS_BULLISH || r.bos_class == BOS_BOS_BEARISH);
      r.val_atr_expansion = (r.breakout_level > 0 && MathAbs(bar.close - r.breakout_level) >= m_cfg.min_bos_atr * atr_m5);
      r.val_momentum = ((r.bos_class == BOS_BOS_BULLISH && rsi > 50) || (r.bos_class == BOS_BOS_BEARISH && rsi < 50) || (rsi >= 45 && rsi <= 55 && adx > 20));
      r.val_retest_done = (r.retest_status == BOS_RETEST_SUCCESS);
      r.val_follow_through = (r.ml.expected_follow_through >= 60);

      int val_n = 0, val_done = 0;
      if(r.val_strong_close) val_done++; val_n++;
      if(r.val_closed_beyond_swing) val_done++; val_n++;
      if(r.val_atr_expansion) val_done++; val_n++;
      if(r.val_momentum) val_done++; val_n++;
      if(r.val_retest_done) val_done++; val_n++;
      if(r.val_follow_through) val_done++; val_n++;
      r.validation_progress = (val_n > 0 ? (double)val_done / val_n * 100.0 : 0);

      if(r.breakout_level > 0)
        {
         r.distance_from_breakout = MathAbs(r.current_price - r.breakout_level);
         r.atr_distance_ratio = (atr_m5 > 0 ? r.distance_from_breakout / atr_m5 : 0);
        }
      else
        {
         r.distance_from_breakout = 0;
         r.atr_distance_ratio = 0;
        }

      if(r.lifecycle_failed) r.risk_zone = "Invalidation zone — breakout failed";
      else if(r.breakout_lifecycle == "Retesting") r.risk_zone = "Retest tolerance band";
      else if(r.breakout_lifecycle == "Confirmed Close" || r.breakout_lifecycle == "Continuation")
         r.risk_zone = "Above breakout — continuation zone";
      else r.risk_zone = "Pre-breakout monitoring zone";

      r.retest_max_distance = atr_m5 * m_cfg.retest_tolerance_atr * 2.0;
      r.retest_max_candles = m_cfg.retest_max_bars;
      r.retest_candles_elapsed = 0;
      if(r.breakout_level > 0)
         r.retest_distance = MathAbs(r.current_price - r.breakout_level);
      else
         r.retest_distance = 0;

      if(r.retest_status == BOS_RETEST_FAILED) r.retest_lifecycle = "Failed";
      else if(r.retest_status == BOS_RETEST_SUCCESS) r.retest_lifecycle = "Confirmed";
      else if(r.retest_status == BOS_RETEST_PENDING)
        {
         if(r.retest_distance <= r.retest_max_distance * 0.5) r.retest_lifecycle = "Retesting";
         else if(r.retest_distance <= r.retest_max_distance) r.retest_lifecycle = "Approaching";
         else r.retest_lifecycle = "Waiting";
        }
      else if(r.breakout_lifecycle == "Confirmed Close" || r.breakout_lifecycle == "Potential Break")
         r.retest_lifecycle = (r.retest_distance <= r.retest_max_distance ? "Approaching" : "Waiting");
      else
         r.retest_lifecycle = "Waiting";

      r.rbs_flip_lifecycle = FlipLifecycleLabel(r.rbs_status, pdh, r.breakout_level, true);
      r.sbr_flip_lifecycle = FlipLifecycleLabel(r.sbr_status, pdl, r.breakout_level, false);

      r.breakout_valid = (!r.lifecycle_failed &&
                          (r.breakout_lifecycle == "Confirmed Close" || r.breakout_lifecycle == "Retesting" ||
                           r.breakout_lifecycle == "Continuation" || r.breakout_lifecycle == "Completed"));

      BuildEventsAndReasoning(r, pdh, pdl);

      r.breakout_label = r.breakout_lifecycle;
      r.retest_label = r.retest_lifecycle;
      r.rbs_label = r.rbs_flip_lifecycle;
      r.sbr_label = r.sbr_flip_lifecycle;
     }

   string FlipLifecycleLabel(const ENUM_BOS_FLIP_STATUS st, const double level,
                              const double brk_level, const bool is_rbs) const
     {
      if(st == BOS_FLIP_VALID) return "Confirmed";
      if(st == BOS_FLIP_FAILED) return "Failed";
      if(st == BOS_FLIP_WEAK) return "Retesting";
      if(level > 0 && brk_level > 0 && MathAbs(brk_level - level) < _Point * 10)
         return "Broken";
      if(st == BOS_FLIP_NONE && level > 0) return "Waiting Retest";
      return "Waiting";
     }

   void BuildEventsAndReasoning(VantageBosResult &r, const double pdh, const double pdl)
     {
      string miss = "";
      if(!r.val_strong_close) miss += "Strong candle close; ";
      if(!r.val_closed_beyond_swing) miss += "Close beyond swing; ";
      if(!r.val_atr_expansion) miss += "ATR expansion; ";
      if(!r.val_momentum) miss += "Momentum; ";
      if(!r.val_retest_done) miss += "Retest completion; ";
      if(!r.val_follow_through) miss += "Follow-through; ";
      r.missing_confirmations = (miss == "" ? "All primary confirmations complete" : miss);

      if(r.lifecycle_failed)
        {
         r.current_event = "Failed Breakout";
         r.expected_next_event = "Breakout invalid if price closes beyond invalidation level";
        }
      else if(r.retest_lifecycle == "Retesting" || r.retest_lifecycle == "Approaching")
        {
         r.current_event = "Retest In Progress";
         r.expected_next_event = "Waiting for Retest Confirmation";
        }
      else if(r.breakout_lifecycle == "Confirmed Close" && r.breakout_type == "Horizontal")
        {
         r.current_event = "Horizontal Breakout Detected";
         r.expected_next_event = "Waiting for Retest";
        }
      else if(r.bos_class == BOS_BOS_BULLISH || r.bos_class == BOS_BOS_BEARISH)
        {
         r.current_event = (r.bos_class == BOS_BOS_BULLISH ? "Bullish BOS Confirmed" : "Bearish BOS Confirmed");
         r.expected_next_event = "Waiting for Follow Through";
        }
      else if(r.breakout_lifecycle == "Continuation" || r.breakout_lifecycle == "Completed")
        {
         r.current_event = "Continuation Confirmed";
         r.expected_next_event = "Monitor for Resistance to Become Support";
        }
      else if(r.breakout_lifecycle == "Potential Break")
        {
         r.current_event = "Potential " + r.breakout_type + " Break";
         r.expected_next_event = "Waiting for Confirmed Close";
        }
      else
        {
         r.current_event = "Monitoring Breakout Structure";
         r.expected_next_event = "Waiting for Valid Breakout Setup";
        }

      if(r.rbs_flip_lifecycle == "Waiting Retest" && r.breakout_valid)
         r.expected_next_event = "Waiting for Resistance to Become Support";
      if(r.sbr_flip_lifecycle == "Waiting Retest" && r.breakout_valid)
         r.expected_next_event = "Waiting for Support to Become Resistance";

      string nar = "";
      nar += r.current_structure + " structure (" + r.structure_strength + " strength). ";
      if(r.bos_class == BOS_BOS_BULLISH || r.bos_class == BOS_BOS_BEARISH)
         nar += "Price has closed beyond the prior swing level. ";
      else
         nar += "No confirmed BOS on the execution timeframe yet. ";
      nar += r.breakout_type + " breakout is ";
      string lc = r.breakout_lifecycle;
      StringToLower(lc);
      nar += lc + ". ";
      if(r.breakout_type != "Trendline" && r.trendline_type != BOS_TL_NONE)
         nar += "Trendline breakout has not yet occurred. ";
      if(!r.val_retest_done)
         nar += "Retest has not yet been completed. ";
      if(r.rbs_flip_lifecycle == "Waiting Retest" || r.rbs_flip_lifecycle == "Waiting")
         nar += "Resistance has not yet become support. ";
      if(r.breakout_valid)
         nar += "The breakout remains valid, but confirmation is still pending.";
      else if(r.lifecycle_failed)
         nar += "The breakout has failed — treat as invalid until structure resets.";
      else
         nar += "No active confirmed breakout — continue monitoring.";
      r.ai_reasoning = nar;
     }

   void ComputeMl(VantageBosResult &r, const double atr, const double rsi, const double adx,
                  const double spread_pts)
     {
      // Explainable weighted logistic — not opaque ML; feature-normalized
      double f = 0.0;
      f += (r.market_structure_h1 == BOS_STRUCT_BULLISH || r.market_structure_h1 == BOS_STRUCT_BEARISH) ? 0.12 : 0.0;
      f += ClampD(r.trendline_strength / 100.0, 0, 1) * 0.15;
      if(r.breakout_status == BOS_BREAK_INSTITUTIONAL) f += 0.18;
      else if(r.breakout_status == BOS_BREAK_STRONG) f += 0.12;
      else if(r.breakout_status == BOS_BREAK_FAKE) f -= 0.15;
      if(r.retest_status == BOS_RETEST_SUCCESS) f += 0.14;
      if(r.sbr_status == BOS_FLIP_VALID || r.rbs_status == BOS_FLIP_VALID) f += 0.10;
      f += ClampD(rsi / 100.0, 0, 1) * 0.05;
      f += ClampD(adx / 50.0, 0, 1) * 0.08;
      if(r.htf_aligned) f += 0.08;
      if(spread_pts > 80) f -= 0.10;
      f = ClampD(f, 0.05, 0.95);
      r.ml.prob_success = f * 100.0;
      r.ml.prob_failure = (1.0 - f) * 100.0;
      r.ml.confidence = r.ml.prob_success;
      r.ml.expected_follow_through = ClampD(f * 1.2, 0, 1) * 100.0;
      r.ml.feature_summary = "struct+tl+break+retest+htf+rsi+adx";
      r.institutional_probability = (r.breakout_status == BOS_BREAK_INSTITUTIONAL ? r.ml.prob_success : r.ml.prob_success * 0.85);
     }

   void ScoreSetup(VantageBosResult &r)
     {
      double s = 0.0;
      string br = "";
      // Market structure 20
      double ms = 0;
      if(r.market_structure_h4 == r.market_structure_h1 && r.market_structure_h1 != BOS_STRUCT_NEUTRAL) ms = 20;
      else if(r.market_structure_h1 != BOS_STRUCT_NEUTRAL) ms = 14;
      else ms = 6;
      s += ms; br += "Structure " + DoubleToString(ms, 0) + "; ";

      // Trendline 15
      double tl = ClampD(r.trendline_strength / 100.0, 0, 1) * m_cfg.w_trendline;
      s += tl; br += "TL " + DoubleToString(tl, 0) + "; ";

      // Breakout 15
      double bk = 0;
      if(r.breakout_status == BOS_BREAK_INSTITUTIONAL) bk = m_cfg.w_breakout;
      else if(r.breakout_status == BOS_BREAK_STRONG) bk = m_cfg.w_breakout * 0.85;
      else if(r.breakout_status == BOS_BREAK_WEAK) bk = m_cfg.w_breakout * 0.45;
      else if(r.breakout_status == BOS_BREAK_FAKE) bk = 0;
      s += bk; br += "Break " + DoubleToString(bk, 0) + "; ";

      // Retest 15
      double rt = 0;
      if(r.retest_status == BOS_RETEST_SUCCESS) rt = m_cfg.w_retest;
      else if(r.retest_status == BOS_RETEST_PENDING) rt = m_cfg.w_retest * 0.4;
      s += rt; br += "Retest " + DoubleToString(rt, 0) + "; ";

      // Flip 10
      double fl = 0;
      if(r.sbr_status == BOS_FLIP_VALID || r.rbs_status == BOS_FLIP_VALID) fl = m_cfg.w_flip;
      else if(r.sbr_status == BOS_FLIP_WEAK || r.rbs_status == BOS_FLIP_WEAK) fl = m_cfg.w_flip * 0.5;
      s += fl; br += "Flip " + DoubleToString(fl, 0) + "; ";

      // Confluence placeholders (liquidity/FVG/OB) — heuristic from BOS quality
      double lq = (r.bos_class == BOS_BOS_BULLISH || r.bos_class == BOS_BOS_BEARISH) ? m_cfg.w_liquidity * 0.6 : 0;
      s += lq; br += "Liq " + DoubleToString(lq, 0) + "; ";

      double htf = r.htf_aligned ? m_cfg.w_htf : m_cfg.w_htf * 0.3;
      s += htf; br += "HTF " + DoubleToString(htf, 0) + "; ";

      double sess = 3.0; // session placeholder
      s += sess;

      r.confidence_score = ClampD(s, 0, 100);
      r.score_breakdown = br;
      r.score_structure_pts = ms;
      r.score_breakout_pts = bk;
      r.score_trendline_pts = tl;
      r.score_retest_pts = rt;
      r.score_flip_pts = fl;
      r.score_momentum_pts = htf + sess;

      if(r.confidence_score >= 95) r.signal_grade = BOS_GRADE_INSTITUTIONAL;
      else if(r.confidence_score >= 90) r.signal_grade = BOS_GRADE_A_PLUS;
      else if(r.confidence_score >= 85) r.signal_grade = BOS_GRADE_A;
      else if(r.confidence_score >= 80) r.signal_grade = BOS_GRADE_B_PLUS;
      else if(r.confidence_score >= 75) r.signal_grade = BOS_GRADE_B;
      else r.signal_grade = BOS_GRADE_REJECT;
      r.grade_label = BosGradeToString(r.signal_grade);
     }

   void DrawObjects(const VantageBosResult &r)
     {
      if(!m_cfg.show_chart) return;
      if(!m_cfg.show_hlines)
        {
         if(ObjectFind(0, BOS_OBJ_PREFIX + "TL_BULL") >= 0) ObjectDelete(0, BOS_OBJ_PREFIX + "TL_BULL");
         if(ObjectFind(0, BOS_OBJ_PREFIX + "TL_BEAR") >= 0) ObjectDelete(0, BOS_OBJ_PREFIX + "TL_BEAR");
        }
      else
        {
         if(m_tl_bull.active)
           {
            string id = BOS_OBJ_PREFIX + "TL_BULL";
            if(ObjectFind(0, id) < 0) ObjectCreate(0, id, OBJ_TREND, 0, m_tl_bull.time2, m_tl_bull.price2, m_tl_bull.time1, m_tl_bull.price1);
            ObjectMove(0, id, 0, m_tl_bull.time2, m_tl_bull.price2);
            ObjectMove(0, id, 1, m_tl_bull.time1, m_tl_bull.price1);
            ObjectSetInteger(0, id, OBJPROP_COLOR, clrDodgerBlue);
            ObjectSetInteger(0, id, OBJPROP_RAY_RIGHT, true);
           }
         if(m_tl_bear.active)
           {
            string id = BOS_OBJ_PREFIX + "TL_BEAR";
            if(ObjectFind(0, id) < 0) ObjectCreate(0, id, OBJ_TREND, 0, m_tl_bear.time2, m_tl_bear.price2, m_tl_bear.time1, m_tl_bear.price1);
            ObjectMove(0, id, 0, m_tl_bear.time2, m_tl_bear.price2);
            ObjectMove(0, id, 1, m_tl_bear.time1, m_tl_bear.price1);
            ObjectSetInteger(0, id, OBJPROP_COLOR, clrOrangeRed);
            ObjectSetInteger(0, id, OBJPROP_RAY_RIGHT, true);
           }
        }
      datetime t0 = iTime(m_symbol, PERIOD_M5, 0);
      string lbl = BOS_OBJ_PREFIX + "LBL";
      if(ObjectFind(0, lbl) < 0) ObjectCreate(0, lbl, OBJ_TEXT, 0, t0, SymbolInfoDouble(m_symbol, SYMBOL_BID));
      ObjectSetString(0, lbl, OBJPROP_TEXT, r.grade_label + " " + DoubleToString(r.confidence_score, 0));
     }

   void ClearObjects(void)
     {
      int total = ObjectsTotal(0, 0, -1);
      for(int i = total - 1; i >= 0; i--)
        {
         string name = ObjectName(0, i, 0, -1);
         if(StringFind(name, BOS_OBJ_PREFIX) == 0) ObjectDelete(0, name);
        }
     }

public:
   CVantageBreakoutStructure(void) : m_inited(false), m_swing_count(0), m_last_m5_bar(0),
      m_h_atr_h4(INVALID_HANDLE), m_h_atr_h1(INVALID_HANDLE), m_h_atr_m15(INVALID_HANDLE),
      m_h_atr_m5(INVALID_HANDLE), m_h_rsi_m5(INVALID_HANDLE), m_h_adx_h1(INVALID_HANDLE),
      m_h_ema20_h1(INVALID_HANDLE), m_h_ema50_h1(INVALID_HANDLE), m_h_ema200_h1(INVALID_HANDLE)
     { ZeroMemory(m_tl_bull); ZeroMemory(m_tl_bear); }

   bool Init(const string symbol, const VantageBosConfig &cfg)
     {
      m_symbol = symbol;
      m_cfg = cfg;
      m_validator.Configure(cfg.approved_aliases, cfg.allow_broker_suffix, cfg.allow_broker_prefix);
      Rel(m_h_atr_h4); Rel(m_h_atr_h1); Rel(m_h_atr_m15); Rel(m_h_atr_m5);
      m_h_atr_h4 = iATR(m_symbol, PERIOD_H4, m_cfg.atr_period);
      m_h_atr_h1 = iATR(m_symbol, PERIOD_H1, m_cfg.atr_period);
      m_h_atr_m15 = iATR(m_symbol, PERIOD_M15, m_cfg.atr_period);
      m_h_atr_m5 = iATR(m_symbol, PERIOD_M5, m_cfg.atr_period);
      m_h_rsi_m5 = iRSI(m_symbol, PERIOD_M5, 14, PRICE_CLOSE);
      m_h_adx_h1 = iADX(m_symbol, PERIOD_H1, 14);
      m_h_ema20_h1 = iMA(m_symbol, PERIOD_H1, 20, 0, MODE_EMA, PRICE_CLOSE);
      m_h_ema50_h1 = iMA(m_symbol, PERIOD_H1, 50, 0, MODE_EMA, PRICE_CLOSE);
      m_h_ema200_h1 = iMA(m_symbol, PERIOD_H1, 200, 0, MODE_EMA, PRICE_CLOSE);
      if(m_h_atr_h1 == INVALID_HANDLE) return false;
      m_inited = true;
      ResetResult(m_last);
      return true;
     }

   void Release(void) { ClearObjects(); Rel(m_h_atr_h4); Rel(m_h_atr_h1); Rel(m_h_atr_m15); Rel(m_h_atr_m5);
      Rel(m_h_rsi_m5); Rel(m_h_adx_h1); Rel(m_h_ema20_h1); Rel(m_h_ema50_h1); Rel(m_h_ema200_h1); m_inited = false; }

   bool Evaluate(const bool force, VantageBosResult &out)
     {
      ResetResult(out);
      out.engine_enabled = m_cfg.enable;
      out.symbol = m_symbol;

      if(!m_cfg.enable)
        {
         out.valid = true;
         out.disable_reason = "Breakout Structure Engine disabled in inputs";
         out.status_line = "Disabled";
         return true;
        }

      string base = "";
      bool gold_ok = m_validator.IsApprovedGoldSymbol(m_symbol, base);
      out.gold_symbol_valid = gold_ok;
      out.base_symbol = base;
      if(m_cfg.gold_only && !gold_ok)
        {
         out.valid = true;
         out.disable_reason = VANTAGE_BOS_DISABLE_MSG;
         out.status_line = "Wrong symbol";
         return true;
        }
      if(!m_inited) return false;

      MqlRates m5[];
      if(!CopyRatesClosed(PERIOD_M5, 120, m5)) return false;
      datetime bar_time = m5[0].time;
      if(!force && bar_time == m_last_m5_bar) { out = m_last; return true; }

      MqlRates h1[], h4[], m15[];
      CopyRatesClosed(PERIOD_H1, 120, h1);
      CopyRatesClosed(PERIOD_H4, 80, h4);
      CopyRatesClosed(PERIOD_M15, 100, m15);

      double atr_h1 = GetAtrTf(PERIOD_H1);
      double atr_m5 = GetAtrTf(PERIOD_M5);
      double rsi = GetBuf(m_h_rsi_m5);
      double adx = GetBuf(m_h_adx_h1);
      double ema50 = GetBuf(m_h_ema50_h1);
      double spread = (double)SymbolInfoInteger(m_symbol, SYMBOL_SPREAD);

      CollectSwings(h1, ArraySize(h1), atr_h1);
      out.market_structure_h1 = StructureFromSwings();
      m_swing_count = 0;
      CollectSwings(h4, ArraySize(h4), GetAtrTf(PERIOD_H4));
      out.market_structure_h4 = StructureFromSwings();
      m_swing_count = 0;
      CollectSwings(m15, ArraySize(m15), GetAtrTf(PERIOD_M15));
      out.market_structure_m15 = StructureFromSwings();
      m_swing_count = 0;
      CollectSwings(h1, ArraySize(h1), atr_h1);

      out.market_structure_label = "H4 " + BosStructureToString(out.market_structure_h4) +
         " | H1 " + BosStructureToString(out.market_structure_h1) +
         " | M15 " + BosStructureToString(out.market_structure_m15);

      ZeroMemory(m_tl_bull); ZeroMemory(m_tl_bear);
      BuildTrendline(h1, ArraySize(h1), atr_h1, true);
      BuildTrendline(h1, ArraySize(h1), atr_h1, false);

      VantageBosTrendline active_tl = m_tl_bull.active ? m_tl_bull : m_tl_bear;
      if(!m_tl_bull.active && m_tl_bear.active) active_tl = m_tl_bear;
      else if(m_tl_bull.active && m_tl_bear.active)
         active_tl = (m_tl_bull.strength >= m_tl_bear.strength) ? m_tl_bull : m_tl_bear;

      out.trendline_type = active_tl.type;
      out.trendline_strength = active_tl.strength;
      out.trendline_slope = active_tl.slope;
      out.trendline_angle = active_tl.angle_deg;
      out.trendline_touches = active_tl.touches;

      string bos_ev = "";
      out.bos_class = DetectBos(h1, ArraySize(h1), atr_h1, bos_ev);
      out.latest_bos_event = bos_ev;
      out.choch_class = DetectChoch(out.market_structure_h1, out.bos_class);
      if(out.choch_class == BOS_CHOCH_BULLISH) out.latest_choch_event = "CHoCH Bullish";
      else if(out.choch_class == BOS_CHOCH_BEARISH) out.latest_choch_event = "CHoCH Bearish";

      out.breakout_status = DetectTrendlineBreak(m5, ArraySize(m5), atr_m5, active_tl, rsi);
      out.breakout_label = BosBreakClassToString(out.breakout_status);
      out.retest_status = DetectRetest(m5, ArraySize(m5), atr_m5, active_tl, out.breakout_status);
      out.retest_label = BosRetestToString(out.retest_status);

      double pdh = 0, pdl = 0;
      MqlRates d1[];
      if(CopyRatesClosed(PERIOD_D1, 3, d1) >= 2) { pdh = d1[1].high; pdl = d1[1].low; }

      out.sbr_status = DetectFlip(m5, ArraySize(m5), pdl, true, atr_m5);
      out.sbr_label = BosFlipToString(out.sbr_status);
      out.rbs_status = DetectFlip(m5, ArraySize(m5), pdh, false, atr_m5);
      out.rbs_label = BosFlipToString(out.rbs_status);

      out.htf_aligned = (out.market_structure_h4 == out.market_structure_h1 &&
                         out.market_structure_h1 != BOS_STRUCT_NEUTRAL &&
                         out.market_structure_h1 != BOS_STRUCT_CONFLICTING);

      ComputeMl(out, atr_m5, rsi, adx, spread);
      ScoreSetup(out);

      BuildModuleView(out, m5, ArraySize(m5), pdh, pdl, atr_m5, rsi, adx, ema50, active_tl);

      out.valid = true;
      out.analysis_active = true;
      out.eval_bar_m5 = bar_time;
      out.chart_objects_active = m_cfg.show_chart;
      out.status_line = out.grade_label + " | Score " + DoubleToString(out.confidence_score, 0);
      out.nearest_support = pdl;
      out.nearest_resistance = pdh;
      if(out.signal_grade >= BOS_GRADE_B)
         out.recommendation = "Structural breakout conditions developing — monitor retest";
      else
         out.recommendation = "WAIT — score below threshold";
      out.technical_narrative = out.market_structure_label + " | " + out.breakout_label + " | " + out.retest_label;

      if(m_cfg.show_chart) DrawObjects(out);
      m_last_m5_bar = bar_time;
      m_last = out;
      out = m_last;
      return true;
     }

   string ToJson(const VantageBosResult &r) const
     {
      string j = "{";
      j += "\"module\":\"breakout_structure\",";
      j += "\"version\":\"" + VANTAGE_BOS_VERSION + "\",";
      j += "\"valid\":" + (r.valid ? "true" : "false") + ",";
      j += "\"gold_symbol_valid\":" + (r.gold_symbol_valid ? "true" : "false") + ",";
      j += "\"engine_enabled\":" + (r.engine_enabled ? "true" : "false") + ",";
      j += "\"analysis_active\":" + (r.analysis_active ? "true" : "false") + ",";
      j += "\"symbol\":\"" + JsonEscape(r.symbol) + "\",";
      j += "\"base_symbol\":\"" + JsonEscape(r.base_symbol) + "\",";
      j += "\"status_line\":\"" + JsonEscape(r.status_line) + "\",";
      j += "\"disable_reason\":\"" + JsonEscape(r.disable_reason) + "\",";
      j += "\"market_structure\":\"" + JsonEscape(r.market_structure_label) + "\",";
      j += "\"market_structure_h4\":\"" + JsonEscape(BosStructureToString(r.market_structure_h4)) + "\",";
      j += "\"market_structure_h1\":\"" + JsonEscape(BosStructureToString(r.market_structure_h1)) + "\",";
      j += "\"market_structure_m15\":\"" + JsonEscape(BosStructureToString(r.market_structure_m15)) + "\",";
      j += "\"bos_class\":\"" + JsonEscape(BosBosClassToString(r.bos_class)) + "\",";
      j += "\"latest_bos_event\":\"" + JsonEscape(r.latest_bos_event) + "\",";
      j += "\"latest_choch_event\":\"" + JsonEscape(r.latest_choch_event) + "\",";
      j += "\"trendline_type\":\"" + (r.trendline_type == BOS_TL_BULLISH ? "Bullish (HL)" : (r.trendline_type == BOS_TL_BEARISH ? "Bearish (LH)" : "None")) + "\",";
      j += "\"trendline_strength\":" + DoubleToString(r.trendline_strength, 1) + ",";
      j += "\"trendline_touches\":" + IntegerToString(r.trendline_touches) + ",";
      j += "\"trendline_angle\":" + DoubleToString(r.trendline_angle, 2) + ",";
      j += "\"breakout_status\":\"" + JsonEscape(r.breakout_label) + "\",";
      j += "\"retest_status\":\"" + JsonEscape(r.retest_label) + "\",";
      j += "\"sbr_status\":\"" + JsonEscape(r.sbr_label) + "\",";
      j += "\"rbs_status\":\"" + JsonEscape(r.rbs_label) + "\",";
      j += "\"confidence_score\":" + DoubleToString(r.confidence_score, 1) + ",";
      j += "\"signal_grade\":\"" + JsonEscape(r.grade_label) + "\",";
      j += "\"institutional_probability\":" + DoubleToString(r.institutional_probability, 1) + ",";
      j += "\"ml_prob_success\":" + DoubleToString(r.ml.prob_success, 1) + ",";
      j += "\"ml_prob_failure\":" + DoubleToString(r.ml.prob_failure, 1) + ",";
      j += "\"ml_confidence\":" + DoubleToString(r.ml.confidence, 1) + ",";
      j += "\"ml_expected_follow_through\":" + DoubleToString(r.ml.expected_follow_through, 1) + ",";
      j += "\"ml_feature_summary\":\"" + JsonEscape(r.ml.feature_summary) + "\",";
      j += "\"score_breakdown\":\"" + JsonEscape(r.score_breakdown) + "\",";
      j += "\"recommendation\":\"" + JsonEscape(r.recommendation) + "\",";
      j += "\"technical_narrative\":\"" + JsonEscape(r.technical_narrative) + "\",";
      j += "\"htf_aligned\":" + (r.htf_aligned ? "true" : "false") + ",";
      j += "\"nearest_support\":" + DoubleToString(r.nearest_support, _Digits) + ",";
      j += "\"nearest_resistance\":" + DoubleToString(r.nearest_resistance, _Digits) + ",";
      j += "\"eval_bar_m5\":" + IntegerToString((int)r.eval_bar_m5) + ",";
      j += "\"chart_objects_active\":" + (r.chart_objects_active ? "true" : "false") + ",";
      j += "\"engine_phase\":" + IntegerToString(r.engine_phase) + ",";
      j += "\"current_structure\":\"" + JsonEscape(r.current_structure) + "\",";
      j += "\"structure_strength\":\"" + JsonEscape(r.structure_strength) + "\",";
      j += "\"breakout_type\":\"" + JsonEscape(r.breakout_type) + "\",";
      j += "\"breakout_lifecycle\":\"" + JsonEscape(r.breakout_lifecycle) + "\",";
      j += "\"breakout_confidence\":" + DoubleToString(r.breakout_confidence, 1) + ",";
      j += "\"lifecycle_stage\":" + IntegerToString(r.lifecycle_stage) + ",";
      j += "\"lifecycle_failed\":" + (r.lifecycle_failed ? "true" : "false") + ",";
      j += "\"val_strong_close\":" + (r.val_strong_close ? "true" : "false") + ",";
      j += "\"val_closed_beyond_swing\":" + (r.val_closed_beyond_swing ? "true" : "false") + ",";
      j += "\"val_atr_expansion\":" + (r.val_atr_expansion ? "true" : "false") + ",";
      j += "\"val_momentum\":" + (r.val_momentum ? "true" : "false") + ",";
      j += "\"val_retest_done\":" + (r.val_retest_done ? "true" : "false") + ",";
      j += "\"val_follow_through\":" + (r.val_follow_through ? "true" : "false") + ",";
      j += "\"validation_progress\":" + DoubleToString(r.validation_progress, 1) + ",";
      j += "\"breakout_level\":" + DoubleToString(r.breakout_level, _Digits) + ",";
      j += "\"current_price\":" + DoubleToString(r.current_price, _Digits) + ",";
      j += "\"distance_from_breakout\":" + DoubleToString(r.distance_from_breakout, _Digits) + ",";
      j += "\"atr_distance_ratio\":" + DoubleToString(r.atr_distance_ratio, 2) + ",";
      j += "\"risk_zone\":\"" + JsonEscape(r.risk_zone) + "\",";
      j += "\"retest_lifecycle\":\"" + JsonEscape(r.retest_lifecycle) + "\",";
      j += "\"retest_distance\":" + DoubleToString(r.retest_distance, _Digits) + ",";
      j += "\"retest_max_distance\":" + DoubleToString(r.retest_max_distance, _Digits) + ",";
      j += "\"retest_max_candles\":" + IntegerToString(r.retest_max_candles) + ",";
      j += "\"retest_candles_elapsed\":" + IntegerToString(r.retest_candles_elapsed) + ",";
      j += "\"rbs_flip_lifecycle\":\"" + JsonEscape(r.rbs_flip_lifecycle) + "\",";
      j += "\"sbr_flip_lifecycle\":\"" + JsonEscape(r.sbr_flip_lifecycle) + "\",";
      j += "\"current_event\":\"" + JsonEscape(r.current_event) + "\",";
      j += "\"expected_next_event\":\"" + JsonEscape(r.expected_next_event) + "\",";
      j += "\"ai_reasoning\":\"" + JsonEscape(r.ai_reasoning) + "\",";
      j += "\"missing_confirmations\":\"" + JsonEscape(r.missing_confirmations) + "\",";
      j += "\"breakout_valid\":" + (r.breakout_valid ? "true" : "false") + ",";
      j += "\"score_structure_pts\":" + DoubleToString(r.score_structure_pts, 1) + ",";
      j += "\"score_breakout_pts\":" + DoubleToString(r.score_breakout_pts, 1) + ",";
      j += "\"score_trendline_pts\":" + DoubleToString(r.score_trendline_pts, 1) + ",";
      j += "\"score_retest_pts\":" + DoubleToString(r.score_retest_pts, 1) + ",";
      j += "\"score_flip_pts\":" + DoubleToString(r.score_flip_pts, 1) + ",";
      j += "\"score_momentum_pts\":" + DoubleToString(r.score_momentum_pts, 1);
      j += "}";
      return j;
     }
  };

#endif
