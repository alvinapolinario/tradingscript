//+------------------------------------------------------------------+
//| VantageMarketStateManager.mqh                                    |
//| Institutional Market State Engine v2 — centralized orchestrator   |
//| Advisory-only — never opens, modifies, or closes trades          |
//+------------------------------------------------------------------+
#ifndef VANTAGE_MARKET_STATE_MANAGER_MQH
#define VANTAGE_MARKET_STATE_MANAGER_MQH

#include "VantageTypes.mqh"
#include "VantageMarketStateTypes.mqh"
#include "VantageGoldSMCValidator.mqh"

#define MSE_OBJ_PREFIX "VAI_MSE_"

// Shared bar cache for all engines (no duplicate CopyRates)
struct VantageMseBarCache
  {
   MqlRates h4[];
   MqlRates h1[];
   MqlRates m15[];
   MqlRates m5[];
   int      n_h4, n_h1, n_m15, n_m5;
   double   atr_h4, atr_h1, atr_m15, atr_m5;
   double   rsi_m5, adx_h1, ema20, ema50, ema200;
   double   spread_pts;
  };

// Event bus — modules publish, manager consumes
struct VantageMseEventBus
  {
   bool   bos_bull_confirmed;
   bool   bos_bear_confirmed;
   bool   choch_bull;
   bool   choch_bear;
   bool   tl_bull_active;
   bool   tl_bear_active;
   bool   tl_bull_broken;
   bool   tl_bear_broken;
   double horizontal_res;
   double horizontal_sup;
   ENUM_MSE_CONTEXT context;
   ENUM_MSE_LIFECYCLE horizontal_brk;
   ENUM_MSE_LIFECYCLE trendline_brk;
   ENUM_MSE_LIFECYCLE retest;
   ENUM_MSE_FLIP_STATE sbr;
   ENUM_MSE_FLIP_STATE rbs;
   ENUM_MSE_LIQ_STATE  liquidity;
   string reasons[16];
   int    reason_count;
  };

class CMarketStateManager
  {
private:
   string                      m_symbol;
   VantageMseConfig            m_cfg;
   VantageMseResult            m_last;
   CVantageGoldSymbolValidator m_validator;
   VantageMseBarCache          m_cache;
   VantageMseEventBus          m_bus;
   VantageMseSwing             m_swings[MSE_MAX_SWINGS];
   int                         m_swing_n;
   VantageMseTimelineEntry     m_timeline[MSE_MAX_TIMELINE];
   int                         m_timeline_n;
   datetime                    m_last_m5_bar;
   int                         m_h_atr_h4, m_h_atr_h1, m_h_atr_m15, m_h_atr_m5;
   int                         m_h_rsi, m_h_adx, m_h_ema20, m_h_ema50, m_h_ema200;
   bool                        m_inited;
   double                      m_progressive_score;

   void Rel(int &h) { if(h != INVALID_HANDLE) { IndicatorRelease(h); h = INVALID_HANDLE; } }

   void Debug(const string msg) const
     {
      if(!m_cfg.debug_log) return;
      Print("[MarketState] ", msg);
     }

   double ClampD(const double v, const double lo, const double hi)
     {
      if(v < lo) return lo;
      if(v > hi) return hi;
      return v;
     }

   void ResetBus(void)
     {
      ZeroMemory(m_bus);
      m_bus.context = MSE_CTX_UNKNOWN;
      m_bus.horizontal_brk = MSE_LC_WAITING;
      m_bus.trendline_brk = MSE_LC_WAITING;
      m_bus.retest = MSE_LC_WAITING;
      m_bus.sbr = MSE_FLIP_WAITING;
      m_bus.rbs = MSE_FLIP_WAITING;
      m_bus.liquidity = MSE_LIQ_WAITING;
     }

   void AddReason(const string r)
     {
      if(m_bus.reason_count >= 16) return;
      m_bus.reasons[m_bus.reason_count++] = r;
     }

   void AddTimeline(const datetime t, const string ev, const string det = "")
     {
      if(m_timeline_n >= MSE_MAX_TIMELINE) return;
      m_timeline[m_timeline_n].time = t;
      m_timeline[m_timeline_n].event = ev;
      m_timeline[m_timeline_n].detail = det;
      m_timeline_n++;
     }

   bool LoadCache(void)
     {
      m_cache.n_h4 = CopyRates(m_symbol, PERIOD_H4, 1, 100, m_cache.h4);
      m_cache.n_h1 = CopyRates(m_symbol, PERIOD_H1, 1, 120, m_cache.h1);
      m_cache.n_m15 = CopyRates(m_symbol, PERIOD_M15, 1, 100, m_cache.m15);
      m_cache.n_m5 = CopyRates(m_symbol, PERIOD_M5, 1, 120, m_cache.m5);
      ArraySetAsSeries(m_cache.h4, true);
      ArraySetAsSeries(m_cache.h1, true);
      ArraySetAsSeries(m_cache.m15, true);
      ArraySetAsSeries(m_cache.m5, true);
      if(m_cache.n_m5 < 30) return false;
      m_cache.atr_h4 = GetAtr(PERIOD_H4);
      m_cache.atr_h1 = GetAtr(PERIOD_H1);
      m_cache.atr_m15 = GetAtr(PERIOD_M15);
      m_cache.atr_m5 = GetAtr(PERIOD_M5);
      m_cache.rsi_m5 = GetBuf(m_h_rsi);
      m_cache.adx_h1 = GetBuf(m_h_adx);
      m_cache.ema20 = GetBuf(m_h_ema20);
      m_cache.ema50 = GetBuf(m_h_ema50);
      m_cache.ema200 = GetBuf(m_h_ema200);
      m_cache.spread_pts = (double)SymbolInfoInteger(m_symbol, SYMBOL_SPREAD);
      return true;
     }

   double GetBuf(const int h, const int sh = 1)
     {
      if(h == INVALID_HANDLE) return 0;
      double b[]; if(CopyBuffer(h, 0, sh, 1, b) != 1) return 0; return b[0];
     }

   double GetAtr(const ENUM_TIMEFRAMES tf)
     {
      int h = m_h_atr_m5;
      if(tf == PERIOD_H4) h = m_h_atr_h4;
      else if(tf == PERIOD_H1) h = m_h_atr_h1;
      else if(tf == PERIOD_M15) h = m_h_atr_m15;
      return GetBuf(h);
     }

   bool IsSwingHigh(const MqlRates &r[], const int i, const int L, const int R)
     {
      if(i < R || i + L >= ArraySize(r)) return false;
      double h = r[i].high;
      for(int k = 1; k <= L; k++) if(r[i+k].high >= h) return false;
      for(int k = 1; k <= R; k++) if(r[i-k].high >= h) return false;
      return true;
     }

   bool IsSwingLow(const MqlRates &r[], const int i, const int L, const int R)
     {
      if(i < R || i + L >= ArraySize(r)) return false;
      double l = r[i].low;
      for(int k = 1; k <= L; k++) if(r[i+k].low <= l) return false;
      for(int k = 1; k <= R; k++) if(r[i-k].low >= l) return false;
      return true;
     }

   // --- SwingEngine ---
   void RunSwingEngine(void)
     {
      m_swing_n = 0;
      const int L = m_cfg.swing_left, R = m_cfg.swing_right;
      int n = m_cache.n_h1;
      double atr = m_cache.atr_h1;
      for(int i = R; i < MathMin(n - L, 60) && m_swing_n < MSE_MAX_SWINGS; i++)
        {
         double rng = m_cache.h1[i].high - m_cache.h1[i].low;
         if(rng < m_cfg.min_swing_atr * atr) continue;
         if(IsSwingHigh(m_cache.h1, i, L, R))
           {
            VantageMseSwing s; s.price = m_cache.h1[i].high; s.time = m_cache.h1[i].time; s.bar_index = i;
            s.atr = atr; s.is_high = true;
            s.strength = ClampD(rng / atr * 30, 0, 100);
            s.confidence = s.strength;
            s.label = MSE_SWING_UNKNOWN;
            m_swings[m_swing_n++] = s;
           }
         if(IsSwingLow(m_cache.h1, i, L, R) && m_swing_n < MSE_MAX_SWINGS)
           {
            VantageMseSwing s; s.price = m_cache.h1[i].low; s.time = m_cache.h1[i].time; s.bar_index = i;
            s.atr = atr; s.is_high = false;
            s.strength = ClampD(rng / atr * 30, 0, 100);
            s.confidence = s.strength;
            s.label = MSE_SWING_UNKNOWN;
            m_swings[m_swing_n++] = s;
           }
        }
      double ph = 0, pl = 0;
      for(int i = m_swing_n - 1; i >= 0; i--)
        {
         if(m_swings[i].is_high)
           {
            if(ph > 0) m_swings[i].label = (m_swings[i].price > ph) ? MSE_SWING_HH : MSE_SWING_LH;
            ph = m_swings[i].price;
           }
         else
           {
            if(pl > 0) m_swings[i].label = (m_swings[i].price > pl) ? MSE_SWING_HL : MSE_SWING_LL;
            pl = m_swings[i].price;
           }
        }
      Debug("SwingEngine: " + IntegerToString(m_swing_n) + " swings");
     }

   string StructureLabel(const ENUM_TIMEFRAMES tf)
     {
      bool hh=false, hl=false, lh=false, ll=false;
      for(int i = 0; i < m_swing_n; i++)
        {
         if(m_swings[i].label == MSE_SWING_HH) hh = true;
         if(m_swings[i].label == MSE_SWING_HL) hl = true;
         if(m_swings[i].label == MSE_SWING_LH) lh = true;
         if(m_swings[i].label == MSE_SWING_LL) ll = true;
        }
      if(hh && hl) return "Bullish HH/HL";
      if(lh && ll) return "Bearish LH/LL";
      if(hh || hl) return "Bullish bias";
      if(lh || ll) return "Bearish bias";
      return "Neutral";
     }

   // --- MarketStructureEngine (BOS/CHoCH state machine) ---
   void RunStructureEngine(VantageMseResult &r)
     {
      r.structure_h4 = StructureLabel(PERIOD_H4);
      r.structure_h1 = StructureLabel(PERIOD_H1);
      r.structure_m15 = StructureLabel(PERIOD_M15);
      r.bos_state = MSE_BOS_WAITING;
      r.choch_state = MSE_CHOCH_WAITING;
      r.bos_label = "Waiting";
      r.choch_label = "Waiting";

      double sh = 0, sl = 0;
      for(int i = 0; i < m_swing_n; i++)
        {
         if(m_swings[i].is_high && sh == 0) sh = m_swings[i].price;
         if(!m_swings[i].is_high && sl == 0) sl = m_swings[i].price;
        }
      double atr = m_cache.atr_h1;
      double body = MathAbs(m_cache.h1[0].close - m_cache.h1[0].open);
      double body_pct = body / MathMax(m_cache.h1[0].high - m_cache.h1[0].low, _Point);

      if(sh > 0 && m_cache.h1[0].close > sh && body_pct >= m_cfg.min_body_pct)
        {
         if(m_cache.h1[0].close - sh >= m_cfg.min_bos_atr * atr)
           {
            r.bos_state = MSE_BOS_CONFIRMED;
            r.bos_label = "Confirmed Bullish BOS";
            r.bos_reason = "Close above swing high with body " + DoubleToString(body_pct*100,0) + "%";
            m_bus.bos_bull_confirmed = true;
            AddTimeline(m_cache.h1[0].time, "Bullish BOS Confirmed", r.bos_reason);
            AddReason(r.bos_reason);
           }
         else
           {
            r.bos_state = MSE_BOS_POTENTIAL;
            r.bos_label = "Potential Bullish BOS";
            r.bos_reason = "Close above level — awaiting ATR penetration";
           }
        }
      else if(sl > 0 && m_cache.h1[0].close < sl && body_pct >= m_cfg.min_body_pct)
        {
         if(sl - m_cache.h1[0].close >= m_cfg.min_bos_atr * atr)
           {
            r.bos_state = MSE_BOS_CONFIRMED;
            r.bos_label = "Confirmed Bearish BOS";
            r.bos_reason = "Close below swing low with expansion";
            m_bus.bos_bear_confirmed = true;
            AddTimeline(m_cache.h1[0].time, "Bearish BOS Confirmed", r.bos_reason);
            AddReason(r.bos_reason);
           }
         else
           {
            r.bos_state = MSE_BOS_POTENTIAL;
            r.bos_label = "Potential Bearish BOS";
           }
        }

      if(m_bus.bos_bull_confirmed && StringFind(r.structure_h1, "Bearish") >= 0)
        {
         r.choch_state = MSE_CHOCH_CONFIRMED;
         r.choch_label = "Confirmed Bullish CHoCH";
         r.choch_reason = "BOS against prior bearish structure";
         m_bus.choch_bull = true;
         AddTimeline(m_cache.h1[0].time, "Bullish CHoCH", r.choch_reason);
        }
      else if(m_bus.bos_bear_confirmed && StringFind(r.structure_h1, "Bullish") >= 0)
        {
         r.choch_state = MSE_CHOCH_CONFIRMED;
         r.choch_label = "Confirmed Bearish CHoCH";
         m_bus.choch_bear = true;
         AddTimeline(m_cache.h1[0].time, "Bearish CHoCH", r.choch_reason);
        }
     }

   // --- TrendlineEngine ---
   void RunTrendlineEngine(VantageMseResult &r)
     {
      r.tl_bull_state = MSE_TL_BUILDING;
      r.tl_bear_state = MSE_TL_BUILDING;
      r.tl_bull_label = "Building";
      r.tl_bear_label = "Building";
      r.tl_strength = 0;
      r.tl_touches = 0;

      if(m_bus.bos_bull_confirmed) { r.tl_bear_state = MSE_TL_DEACTIVATED; r.tl_bear_label = "Deactivated (bullish BOS)"; }
      if(m_bus.bos_bear_confirmed) { r.tl_bull_state = MSE_TL_DEACTIVATED; r.tl_bull_label = "Deactivated (bearish BOS)"; }

      int hl = 0, lh = 0;
      for(int i = 0; i < m_swing_n; i++)
        {
         if(m_swings[i].label == MSE_SWING_HL) hl++;
         if(m_swings[i].label == MSE_SWING_LH) lh++;
        }
      if(hl >= m_cfg.min_tl_touches && r.tl_bull_state != MSE_TL_DEACTIVATED)
        {
         r.tl_bull_state = MSE_TL_VALID;
         r.tl_bull_label = "Valid (HL trendline)";
         r.tl_touches = hl;
         r.tl_strength = ClampD(hl * 25, 0, 100);
         m_bus.tl_bull_active = true;
        }
      if(lh >= m_cfg.min_tl_touches && r.tl_bear_state != MSE_TL_DEACTIVATED)
        {
         r.tl_bear_state = MSE_TL_VALID;
         r.tl_bear_label = "Valid (LH trendline)";
         r.tl_touches = MathMax(r.tl_touches, lh);
         r.tl_strength = MathMax(r.tl_strength, ClampD(lh * 25, 0, 100));
         m_bus.tl_bear_active = true;
        }
      r.tl_reason = "Touches " + IntegerToString(r.tl_touches) + " min " + IntegerToString(m_cfg.min_tl_touches);
     }

   // --- BreakoutEngine (separate tracks) ---
   void RunBreakoutEngine(VantageMseResult &r)
     {
      double atr = m_cache.atr_m5;
      MqlRates d1[];
      if(CopyRates(m_symbol, PERIOD_D1, 1, 2, d1) >= 2)
        {
         ArraySetAsSeries(d1, true);
         m_bus.horizontal_res = d1[1].high;
         m_bus.horizontal_sup = d1[1].low;
        }

      r.horizontal_breakout = "Waiting";
      r.trendline_breakout = "Waiting";
      r.channel_breakout = "Waiting";
      r.ma_breakout = "Waiting";

      if(m_bus.horizontal_res > 0 && m_cache.m5[0].close > m_bus.horizontal_res)
        {
         double pen = m_cache.m5[0].close - m_bus.horizontal_res;
         if(pen >= m_cfg.min_bos_atr * atr)
           {
            r.horizontal_breakout = "Confirmed";
            r.horizontal_reason = "PDH close breakout +" + DoubleToString(pen, _Digits);
            m_bus.horizontal_brk = MSE_LC_CONFIRMED;
            AddTimeline(m_cache.m5[0].time, "Horizontal Breakout", "PDH");
           }
         else { r.horizontal_breakout = "Potential"; m_bus.horizontal_brk = MSE_LC_POTENTIAL; }
        }
      else if(m_bus.horizontal_sup > 0 && m_cache.m5[0].close < m_bus.horizontal_sup)
        {
         if(m_bus.horizontal_sup - m_cache.m5[0].close >= m_cfg.min_bos_atr * atr)
           {
            r.horizontal_breakout = "Confirmed";
            r.horizontal_reason = "PDL close breakout";
            m_bus.horizontal_brk = MSE_LC_CONFIRMED;
           }
         else r.horizontal_breakout = "Potential";
        }

      if(m_bus.tl_bear_active && m_cache.m5[0].close > m_cache.ema20)
        {
         r.trendline_breakout = "Potential";
         r.trendline_brk_reason = "Price testing bearish TL zone";
         m_bus.trendline_brk = MSE_LC_POTENTIAL;
        }
      else if(m_bus.tl_bull_active && m_cache.m5[0].close < m_cache.ema20)
        {
         r.trendline_breakout = "Retesting";
         r.trendline_brk_reason = "Pullback to bullish TL area";
         m_bus.trendline_brk = MSE_LC_RETESTING;
         AddTimeline(m_cache.m5[0].time, "Trendline Broken/Retest", r.trendline_brk_reason);
        }
      else if(m_bus.bos_bull_confirmed)
        {
         r.trendline_breakout = "Continuation";
         m_bus.trendline_brk = MSE_LC_CONTINUATION;
        }

      if(m_cache.adx_h1 > 25) r.channel_breakout = "Waiting";
      else r.channel_breakout = "Potential";

      if(m_cache.m5[0].close > m_cache.ema50 && m_cache.ema20 > m_cache.ema50)
         r.ma_breakout = "Confirmed";
      else if(m_cache.m5[0].close < m_cache.ema50 && m_cache.ema20 < m_cache.ema50)
         r.ma_breakout = "Confirmed";
      else
         r.ma_breakout = "Waiting";
     }

   // --- SupportResistanceEngine (SBR/RBS) ---
   void RunSREngine(VantageMseResult &r)
     {
      double atr = m_cache.atr_m5;
      double tol = atr * m_cfg.retest_tol_atr;

      r.sbr_status = "Waiting";
      r.rbs_status = "Waiting";

      if(m_bus.horizontal_sup > 0)
        {
         if(m_cache.m5[0].close < m_bus.horizontal_sup - m_cfg.min_bos_atr * atr)
           {
            m_bus.sbr = MSE_FLIP_BROKEN;
            r.sbr_status = "Broken";
            if(MathAbs(m_cache.m5[0].high - m_bus.horizontal_sup) <= tol)
              {
               m_bus.sbr = MSE_FLIP_RETESTING;
               r.sbr_status = "Retesting";
               r.sbr_reason = "Support break — retest from below";
              }
           }
         else if(m_cache.m5[1].close < m_bus.horizontal_sup && m_cache.m5[0].close >= m_bus.horizontal_sup)
           {
            m_bus.sbr = MSE_FLIP_WAITING_RETEST;
            r.sbr_status = "Waiting Retest";
           }
        }

      if(m_bus.horizontal_res > 0)
        {
         if(m_cache.m5[0].close > m_bus.horizontal_res + m_cfg.min_bos_atr * atr)
           {
            m_bus.rbs = MSE_FLIP_BROKEN;
            r.rbs_status = "Broken";
            if(MathAbs(m_cache.m5[0].low - m_bus.horizontal_res) <= tol)
              {
               m_bus.rbs = MSE_FLIP_RETESTING;
               r.rbs_status = "Retesting";
               r.rbs_reason = "Resistance break — retest as support";
               AddTimeline(m_cache.m5[0].time, "Resistance became Support", r.rbs_reason);
              }
           }
         else
            r.rbs_status = "Waiting Retest";
        }
     }

   // --- RetestEngine ---
   void RunRetestEngine(VantageMseResult &r)
     {
      if(m_bus.trendline_brk == MSE_LC_RETESTING || m_bus.sbr == MSE_FLIP_RETESTING || m_bus.rbs == MSE_FLIP_RETESTING)
        {
         r.retest_status = "Retesting";
         r.retest_reason = "Price within ATR tolerance of broken level";
         m_bus.retest = MSE_LC_RETESTING;
        }
      else if(m_bus.horizontal_brk == MSE_LC_CONFIRMED)
        {
         double dist = MathAbs(m_cache.m5[0].close - m_bus.horizontal_res);
         if(dist <= m_cache.atr_m5 * m_cfg.retest_tol_atr * 2)
           {
            r.retest_status = "Approaching";
            r.retest_reason = "Distance " + DoubleToString(dist, _Digits) + " from level";
            m_bus.retest = MSE_LC_APPROACHING;
           }
         else r.retest_status = "Waiting";
        }
      else
        {
         r.retest_status = "Waiting";
         r.retest_reason = "No active breakout to retest";
        }
     }

   // --- LiquidityEngine ---
   void RunLiquidityEngine(VantageMseResult &r)
     {
      if(m_bus.horizontal_res > 0 && m_cache.m5[0].high > m_bus.horizontal_res && m_cache.m5[0].close < m_bus.horizontal_res)
        {
         r.liquidity_status = "Potential Sweep";
         r.liquidity_reason = "Buy-side sweep above PDH with close back inside";
         m_bus.liquidity = MSE_LIQ_POTENTIAL_SWEEP;
         AddTimeline(m_cache.m5[0].time, "Potential Liquidity Sweep", r.liquidity_reason);
        }
      else if(m_bus.horizontal_sup > 0 && m_cache.m5[0].low < m_bus.horizontal_sup && m_cache.m5[0].close > m_bus.horizontal_sup)
        {
         r.liquidity_status = "Potential Sweep";
         r.liquidity_reason = "Sell-side sweep below PDL";
         m_bus.liquidity = MSE_LIQ_POTENTIAL_SWEEP;
        }
      else
        {
         r.liquidity_status = "Waiting";
         r.liquidity_reason = "No sweep pattern on closed M5 bar";
        }
     }

   // --- MarketContextEngine ---
   void RunContextEngine(VantageMseResult &r)
     {
      double atr = m_cache.atr_h1;
      double range20 = 0;
      for(int i = 0; i < 20 && i < m_cache.n_h1; i++)
         range20 += m_cache.h1[i].high - m_cache.h1[i].low;
      range20 /= 20.0;
      if(m_cache.adx_h1 >= 25)
        {
         m_bus.context = MSE_CTX_TRENDING;
         r.context_reason = "ADX " + DoubleToString(m_cache.adx_h1, 1) + " — trend environment";
        }
      else if(range20 < atr * 0.8)
        {
         m_bus.context = MSE_CTX_COMPRESSION;
         r.context_reason = "Compressed range vs ATR";
        }
      else if(range20 > atr * 2.5)
        {
         m_bus.context = MSE_CTX_EXPANSION;
         r.context_reason = "Wide recent range — expansion";
        }
      else
        {
         m_bus.context = MSE_CTX_RANGING;
         r.context_reason = "Low ADX — range conditions";
        }
      r.market_context = MseContextToString(m_bus.context);
     }

   // --- MachineLearningEngine (probabilities, not buy/sell) ---
   void RunMLEngine(VantageMseResult &r)
     {
      double cont = 0.35, fail = 0.25, pull = 0.20, ret = 0.10, liq = 0.05, fake = 0.05;
      if(m_bus.context == MSE_CTX_TRENDING) cont += 0.15;
      if(m_bus.context == MSE_CTX_RANGING) fake += 0.15;
      if(m_bus.bos_bull_confirmed || m_bus.bos_bear_confirmed) cont += 0.12;
      if(m_bus.retest == MSE_LC_RETESTING) ret += 0.12;
      if(m_bus.liquidity == MSE_LIQ_POTENTIAL_SWEEP) liq += 0.10;
      if(m_bus.horizontal_brk == MSE_LC_FAILED) fail += 0.15;
      double sum = cont + fail + pull + ret + liq + fake;
      r.ml.trend_continuation_pct = cont / sum * 100;
      r.ml.failed_breakout_pct = fail / sum * 100;
      r.ml.deep_pullback_pct = pull / sum * 100;
      r.ml.retest_success_pct = ret / sum * 100;
      r.ml.liquidity_sweep_pct = liq / sum * 100;
      r.ml.false_breakout_pct = fake / sum * 100;
      r.ml.distribution_summary = "Continuation " + DoubleToString(r.ml.trend_continuation_pct, 0) + "% | Failed BO " +
         DoubleToString(r.ml.failed_breakout_pct, 0) + "% | Pullback " + DoubleToString(r.ml.deep_pullback_pct, 0) + "%";
      r.institutional_probability = ClampD(r.ml.trend_continuation_pct * 0.6 + r.ml.retest_success_pct * 0.4, 0, 100);
     }

   // --- ScoreEngine (progressive) ---
   void RunScoreEngine(VantageMseResult &r)
     {
      m_progressive_score = 0;
      string br = "";

      if(r.bos_state == MSE_BOS_POTENTIAL) { m_progressive_score += 10; br += "BOS detected +10; "; }
      if(r.bos_state == MSE_BOS_CONFIRMED) { m_progressive_score += 20; br += "BOS confirmed +20; "; }
      if(r.bos_state == MSE_BOS_CONTINUATION) { m_progressive_score += 25; br += "BOS continuation +25; "; }
      if(r.tl_bull_state == MSE_TL_VALID || r.tl_bear_state == MSE_TL_VALID) { m_progressive_score += 5; br += "TL valid +5; "; }
      if(r.tl_bull_state == MSE_TL_BROKEN || r.tl_bear_state == MSE_TL_BROKEN) { m_progressive_score += 10; br += "TL broken +10; "; }
      if(m_bus.trendline_brk == MSE_LC_RETESTING) { m_progressive_score += 15; br += "TL retesting +15; "; }
      if(r.horizontal_breakout == "Confirmed") { m_progressive_score += 15; br += "Horizontal BO +15; "; }
      if(r.retest_status == "Approaching") { m_progressive_score += 8; br += "Retest approaching +8; "; }
      if(r.retest_status == "Retesting") { m_progressive_score += 15; br += "Retest active +15; "; }
      if(r.rbs_status == "Retesting") { m_progressive_score += 8; br += "RBS retesting +8; "; }
      if(m_bus.context == MSE_CTX_TRENDING) { m_progressive_score += 5; br += "Trend context +5; "; }

      r.confidence_score = ClampD(m_progressive_score, 0, 100);
      r.score_breakdown = br;
      if(m_bus.retest == MSE_LC_RETESTING) r.signal_lifecycle = "Retesting";
      else if(r.bos_state == MSE_BOS_CONFIRMED) r.signal_lifecycle = "BOS Confirmed";
      else if(r.horizontal_breakout == "Confirmed") r.signal_lifecycle = "Breakout Confirmed";
      else r.signal_lifecycle = "Waiting";
      r.lifecycle_reason = "Progressive score from event chain";
     }

   void BuildNarrative(VantageMseResult &r)
     {
      r.what_happened = r.bos_label;
      if(r.choch_label != "Waiting") r.what_happened += " | " + r.choch_label;
      r.what_is_happening = r.signal_lifecycle + " — " + r.retest_status + " retest, " + r.liquidity_status + " liquidity";
      r.what_is_next = (r.retest_status == "Waiting") ? "Watch for retest of broken level" : "Monitor retest confirmation";
      r.missing_confirmations = "";
      if(r.bos_state != MSE_BOS_CONFIRMED) r.missing_confirmations += "Confirmed BOS; ";
      if(r.retest_status == "Waiting") r.missing_confirmations += "Successful retest; ";
      if(r.liquidity_status == "Waiting") r.missing_confirmations += "Liquidity event optional; ";
      if(r.missing_confirmations == "") r.missing_confirmations = "Core sequence progressing";
      r.recommendation = (r.confidence_score >= 75) ? "Structural intelligence — high progression" : "WAIT — confirmations incomplete";
     }

   string BuildTimelineJson(void)
     {
      string j = "";
      for(int i = 0; i < m_timeline_n; i++)
        {
         if(i > 0) j += "|";
         MqlDateTime dt; TimeToStruct(m_timeline[i].time, dt);
         j += StringFormat("%02d:%02d %s", dt.hour, dt.min, m_timeline[i].event);
         if(m_timeline[i].detail != "") j += " — " + m_timeline[i].detail;
        }
      return j;
     }

   void DrawChart(void)
     {
      if(!m_cfg.show_chart) return;
      if(m_bus.horizontal_res > 0)
        {
         string id = MSE_OBJ_PREFIX + "RES";
         if(ObjectFind(0, id) < 0) ObjectCreate(0, id, OBJ_HLINE, 0, 0, m_bus.horizontal_res);
         ObjectSetDouble(0, id, OBJPROP_PRICE, m_bus.horizontal_res);
         ObjectSetInteger(0, id, OBJPROP_COLOR, clrOrangeRed);
        }
      if(m_bus.horizontal_sup > 0)
        {
         string id = MSE_OBJ_PREFIX + "SUP";
         if(ObjectFind(0, id) < 0) ObjectCreate(0, id, OBJ_HLINE, 0, 0, m_bus.horizontal_sup);
         ObjectSetDouble(0, id, OBJPROP_PRICE, m_bus.horizontal_sup);
         ObjectSetInteger(0, id, OBJPROP_COLOR, clrDodgerBlue);
        }
     }

   void ClearChart(void)
     {
      for(int i = ObjectsTotal(0,0,-1)-1; i >= 0; i--)
        {
         string n = ObjectName(0, i, 0, -1);
         if(StringFind(n, MSE_OBJ_PREFIX) == 0) ObjectDelete(0, n);
        }
     }

public:
   CMarketStateManager(void) : m_inited(false), m_swing_n(0), m_timeline_n(0), m_last_m5_bar(0), m_progressive_score(0),
      m_h_atr_h4(INVALID_HANDLE), m_h_atr_h1(INVALID_HANDLE), m_h_atr_m15(INVALID_HANDLE), m_h_atr_m5(INVALID_HANDLE),
      m_h_rsi(INVALID_HANDLE), m_h_adx(INVALID_HANDLE), m_h_ema20(INVALID_HANDLE), m_h_ema50(INVALID_HANDLE), m_h_ema200(INVALID_HANDLE) {}

   bool Init(const string symbol, const VantageMseConfig &cfg)
     {
      m_symbol = symbol; m_cfg = cfg;
      m_validator.Configure(cfg.approved_aliases, cfg.allow_suffix, cfg.allow_prefix);
      m_h_atr_h4 = iATR(m_symbol, PERIOD_H4, cfg.atr_period);
      m_h_atr_h1 = iATR(m_symbol, PERIOD_H1, cfg.atr_period);
      m_h_atr_m15 = iATR(m_symbol, PERIOD_M15, cfg.atr_period);
      m_h_atr_m5 = iATR(m_symbol, PERIOD_M5, cfg.atr_period);
      m_h_rsi = iRSI(m_symbol, PERIOD_M5, 14, PRICE_CLOSE);
      m_h_adx = iADX(m_symbol, PERIOD_H1, 14);
      m_h_ema20 = iMA(m_symbol, PERIOD_H1, 20, 0, MODE_EMA, PRICE_CLOSE);
      m_h_ema50 = iMA(m_symbol, PERIOD_H1, 50, 0, MODE_EMA, PRICE_CLOSE);
      m_h_ema200 = iMA(m_symbol, PERIOD_H1, 200, 0, MODE_EMA, PRICE_CLOSE);
      m_inited = (m_h_atr_h1 != INVALID_HANDLE);
      return m_inited;
     }

   void Release(void) { ClearChart(); Rel(m_h_atr_h4); Rel(m_h_atr_h1); Rel(m_h_atr_m15); Rel(m_h_atr_m5);
      Rel(m_h_rsi); Rel(m_h_adx); Rel(m_h_ema20); Rel(m_h_ema50); Rel(m_h_ema200); m_inited = false; }

   bool Evaluate(const bool force, VantageMseResult &out)
     {
      ZeroMemory(out);
      out.symbol = m_symbol;
      out.engine_enabled = m_cfg.enable;
      out.engine_phase = 2;
      out.horizontal_breakout = "Waiting";
      out.trendline_breakout = "Waiting";
      out.retest_status = "Waiting";
      out.liquidity_status = "Waiting";
      out.sbr_status = "Waiting";
      out.rbs_status = "Waiting";
      out.bos_label = "Waiting";
      out.choch_label = "Waiting";

      if(!m_cfg.enable) { out.valid = true; out.disable_reason = "Market State Engine disabled"; return true; }
      string base = "";
      out.gold_symbol_valid = m_validator.IsApprovedGoldSymbol(m_symbol, base);
      out.base_symbol = base;
      if(m_cfg.gold_only && !out.gold_symbol_valid)
        { out.valid = true; out.disable_reason = VANTAGE_MSE_DISABLE_MSG; return true; }
      if(!m_inited || !LoadCache()) return false;

      datetime bar_t = m_cache.m5[0].time;
      if(!force && bar_t == m_last_m5_bar) { out = m_last; return true; }

      ResetBus();
      m_timeline_n = 0;
      m_progressive_score = 0;

      RunSwingEngine();
      RunStructureEngine(out);
      RunTrendlineEngine(out);
      RunBreakoutEngine(out);
      RunSREngine(out);
      RunRetestEngine(out);
      RunLiquidityEngine(out);
      RunContextEngine(out);
      RunMLEngine(out);
      RunScoreEngine(out);
      BuildNarrative(out);

      out.timeline_json = BuildTimelineJson();
      out.valid = true;
      out.analysis_active = true;
      out.eval_bar_m5 = bar_t;
      out.status_line = out.signal_lifecycle + " | Score " + DoubleToString(out.confidence_score, 0);
      out.chart_objects_active = m_cfg.show_chart;
      if(m_cfg.show_chart) DrawChart();

      m_last_m5_bar = bar_t;
      m_last = out;
      out = m_last;
      return true;
     }

   string ToJson(const VantageMseResult &r) const
     {
      string j = "{";
      j += "\"module\":\"market_state\",";
      j += "\"version\":\"" + VANTAGE_MSE_VERSION + "\",";
      j += "\"valid\":" + (r.valid ? "true" : "false") + ",";
      j += "\"gold_symbol_valid\":" + (r.gold_symbol_valid ? "true" : "false") + ",";
      j += "\"symbol\":\"" + JsonEscape(r.symbol) + "\",";
      j += "\"status_line\":\"" + JsonEscape(r.status_line) + "\",";
      j += "\"market_context\":\"" + JsonEscape(r.market_context) + "\",";
      j += "\"context_reason\":\"" + JsonEscape(r.context_reason) + "\",";
      j += "\"structure_h4\":\"" + JsonEscape(r.structure_h4) + "\",";
      j += "\"structure_h1\":\"" + JsonEscape(r.structure_h1) + "\",";
      j += "\"structure_m15\":\"" + JsonEscape(r.structure_m15) + "\",";
      j += "\"bos_label\":\"" + JsonEscape(r.bos_label) + "\",";
      j += "\"bos_reason\":\"" + JsonEscape(r.bos_reason) + "\",";
      j += "\"choch_label\":\"" + JsonEscape(r.choch_label) + "\",";
      j += "\"tl_bull_label\":\"" + JsonEscape(r.tl_bull_label) + "\",";
      j += "\"tl_bear_label\":\"" + JsonEscape(r.tl_bear_label) + "\",";
      j += "\"horizontal_breakout\":\"" + JsonEscape(r.horizontal_breakout) + "\",";
      j += "\"trendline_breakout\":\"" + JsonEscape(r.trendline_breakout) + "\",";
      j += "\"channel_breakout\":\"" + JsonEscape(r.channel_breakout) + "\",";
      j += "\"ma_breakout\":\"" + JsonEscape(r.ma_breakout) + "\",";
      j += "\"retest_status\":\"" + JsonEscape(r.retest_status) + "\",";
      j += "\"retest_reason\":\"" + JsonEscape(r.retest_reason) + "\",";
      j += "\"sbr_status\":\"" + JsonEscape(r.sbr_status) + "\",";
      j += "\"rbs_status\":\"" + JsonEscape(r.rbs_status) + "\",";
      j += "\"liquidity_status\":\"" + JsonEscape(r.liquidity_status) + "\",";
      j += "\"liquidity_reason\":\"" + JsonEscape(r.liquidity_reason) + "\",";
      j += "\"confidence_score\":" + DoubleToString(r.confidence_score, 1) + ",";
      j += "\"institutional_probability\":" + DoubleToString(r.institutional_probability, 1) + ",";
      j += "\"ml_trend_continuation\":" + DoubleToString(r.ml.trend_continuation_pct, 1) + ",";
      j += "\"ml_failed_breakout\":" + DoubleToString(r.ml.failed_breakout_pct, 1) + ",";
      j += "\"ml_deep_pullback\":" + DoubleToString(r.ml.deep_pullback_pct, 1) + ",";
      j += "\"ml_distribution\":\"" + JsonEscape(r.ml.distribution_summary) + "\",";
      j += "\"signal_lifecycle\":\"" + JsonEscape(r.signal_lifecycle) + "\",";
      j += "\"score_breakdown\":\"" + JsonEscape(r.score_breakdown) + "\",";
      j += "\"timeline\":\"" + JsonEscape(r.timeline_json) + "\",";
      j += "\"what_happened\":\"" + JsonEscape(r.what_happened) + "\",";
      j += "\"what_is_happening\":\"" + JsonEscape(r.what_is_happening) + "\",";
      j += "\"what_is_next\":\"" + JsonEscape(r.what_is_next) + "\",";
      j += "\"missing_confirmations\":\"" + JsonEscape(r.missing_confirmations) + "\",";
      j += "\"recommendation\":\"" + JsonEscape(r.recommendation) + "\",";
      j += "\"eval_bar_m5\":" + IntegerToString((int)r.eval_bar_m5) + ",";
      j += "\"engine_phase\":" + IntegerToString(r.engine_phase);
      j += "}";
      return j;
     }
  };

#endif
