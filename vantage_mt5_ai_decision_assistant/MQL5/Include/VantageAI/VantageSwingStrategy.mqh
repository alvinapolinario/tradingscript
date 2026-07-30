//+------------------------------------------------------------------+
//| VantageSwingStrategy.mqh                                         |
//| Swing Strategy Engine — multi-TF SMC swing validation (Gold only)  |
//| Advisory-only — never opens, modifies, or closes trades          |
//+------------------------------------------------------------------+
#ifndef VANTAGE_SWING_STRATEGY_MQH
#define VANTAGE_SWING_STRATEGY_MQH

#include "VantageTypes.mqh"
#include "VantageSwingStrategyTypes.mqh"
#include "VantageGoldSMCValidator.mqh"

#define SWING_STRAT_OBJ_PREFIX "VAI_SSWING_"

class CVantageSwingStrategy
  {
private:
   string                      m_symbol;
   VantageSwingStratConfig     m_cfg;
   VantageSwingStratResult     m_last;
   CVantageGoldSymbolValidator m_validator;
   VantageSwingStratSwing      m_swings[SWING_STRAT_MAX_SWINGS];
   int                         m_swing_n;
   datetime                    m_last_m5_bar;
   int                         m_h_atr_d1, m_h_atr_h4, m_h_atr_h1, m_h_atr_m15, m_h_atr_m5;
   int                         m_h_rsi_h1, m_h_macd_m15, m_h_adx_h4;
   bool                        m_inited;

   void Rel(int &h) { if(h != INVALID_HANDLE) { IndicatorRelease(h); h = INVALID_HANDLE; } }

   void Debug(const string msg) const
     {
      if(!m_cfg.debug_log) return;
      Print("[SwingStrategy] ", msg);
     }

   double ClampD(const double v, const double lo, const double hi) const
     {
      if(v < lo) return lo;
      if(v > hi) return hi;
      return v;
     }

   bool CopyClosed(const ENUM_TIMEFRAMES tf, const int count, MqlRates &rates[])
     {
      ArraySetAsSeries(rates, true);
      return (CopyRates(m_symbol, tf, 1, count, rates) > 0);
     }

   double GetBuf(const int h, const int sh = 1) const
     {
      if(h == INVALID_HANDLE) return 0;
      double b[];
      if(CopyBuffer(h, 0, sh, 1, b) != 1) return 0;
      return b[0];
     }

   double GetAtrTf(const ENUM_TIMEFRAMES tf) const
     {
      int h = m_h_atr_m5;
      if(tf == PERIOD_D1) h = m_h_atr_d1;
      else if(tf == PERIOD_H4) h = m_h_atr_h4;
      else if(tf == PERIOD_H1) h = m_h_atr_h1;
      else if(tf == PERIOD_M15) h = m_h_atr_m15;
      return GetBuf(h);
     }

   bool IsSwingHigh(const MqlRates &r[], const int i, const int L, const int R) const
     {
      if(i < R || i + L >= ArraySize(r)) return false;
      double h = r[i].high;
      for(int k = 1; k <= L; k++) if(r[i+k].high >= h) return false;
      for(int k = 1; k <= R; k++) if(r[i-k].high >= h) return false;
      return true;
     }

   bool IsSwingLow(const MqlRates &r[], const int i, const int L, const int R) const
     {
      if(i < R || i + L >= ArraySize(r)) return false;
      double l = r[i].low;
      for(int k = 1; k <= L; k++) if(r[i+k].low <= l) return false;
      for(int k = 1; k <= R; k++) if(r[i-k].low <= l) return false;
      return true;
     }

   void CollectSwings(MqlRates &rates[], const int n, const double atr, const bool external_only)
     {
      const int L = m_cfg.swing_left, R = m_cfg.swing_right;
      for(int i = R; i < MathMin(n - L, 70) && m_swing_n < SWING_STRAT_MAX_SWINGS; i++)
        {
         double rng = rates[i].high - rates[i].low;
         if(rng < m_cfg.min_swing_atr * atr) continue;
         if(IsSwingHigh(rates, i, L, R))
           {
            VantageSwingStratSwing s;
            s.price = rates[i].high; s.time = rates[i].time; s.bar_index = i;
            s.atr = atr; s.is_high = true; s.external = external_only;
            s.strength = ClampD(rng / MathMax(atr, _Point) * 25, 0, 100);
            s.label = SWING_LBL_UNKNOWN;
            m_swings[m_swing_n++] = s;
           }
         if(IsSwingLow(rates, i, L, R) && m_swing_n < SWING_STRAT_MAX_SWINGS)
           {
            VantageSwingStratSwing s;
            s.price = rates[i].low; s.time = rates[i].time; s.bar_index = i;
            s.atr = atr; s.is_high = false; s.external = external_only;
            s.strength = ClampD(rng / MathMax(atr, _Point) * 25, 0, 100);
            s.label = SWING_LBL_UNKNOWN;
            m_swings[m_swing_n++] = s;
           }
        }
      double ph = 0, pl = 0;
      for(int j = m_swing_n - 1; j >= 0; j--)
        {
         if(m_swings[j].is_high)
           {
            if(ph > 0) m_swings[j].label = (m_swings[j].price > ph) ? SWING_LBL_HH : SWING_LBL_LH;
            ph = m_swings[j].price;
           }
         else
           {
            if(pl > 0) m_swings[j].label = (m_swings[j].price > pl) ? SWING_LBL_HL : SWING_LBL_LL;
            pl = m_swings[j].price;
           }
        }
     }

   string StructureFromSwings(void) const
     {
      bool hh=false, hl=false, lh=false, ll=false;
      for(int i = 0; i < m_swing_n; i++)
        {
         if(m_swings[i].label == SWING_LBL_HH) hh = true;
         if(m_swings[i].label == SWING_LBL_HL) hl = true;
         if(m_swings[i].label == SWING_LBL_LH) lh = true;
         if(m_swings[i].label == SWING_LBL_LL) ll = true;
        }
      if(hh && hl) return "HH-HL";
      if(lh && ll) return "LH-LL";
      if(hh || hl) return "Bullish Bias";
      if(lh || ll) return "Bearish Bias";
      return "Range";
     }

   void RunPipeline(VantageSwingStratResult &r,
                    MqlRates &d1[], MqlRates &h4[], MqlRates &h1[], MqlRates &m15[], MqlRates &m5[],
                    const int n_d1, const int n_h4, const int n_h1, const int n_m15, const int n_m5)
     {
      double atr_d1 = GetAtrTf(PERIOD_D1);
      double atr_h4 = GetAtrTf(PERIOD_H4);
      double atr_h1 = GetAtrTf(PERIOD_H1);
      double atr_m15 = GetAtrTf(PERIOD_M15);
      double atr_m5 = GetAtrTf(PERIOD_M5);
      r.atr_h4 = atr_h4;

      // Step 1 — structure on H4
      m_swing_n = 0;
      CollectSwings(h4, n_h4, atr_h4, true);
      r.market_structure = StructureFromSwings();
      r.external_structure = r.market_structure;

      m_swing_n = 0;
      CollectSwings(h1, n_h1, atr_h1, false);
      r.internal_structure = StructureFromSwings();

      double range_h4 = 0;
      for(int i = 0; i < MathMin(20, n_h4); i++) range_h4 += h4[i].high - h4[i].low;
      range_h4 /= MathMax(1, MathMin(20, n_h4));
      if(atr_h4 > 0 && range_h4 / atr_h4 > 1.35) r.structure_regime = "Expansion";
      else if(atr_h4 > 0 && range_h4 / atr_h4 < 0.75) r.structure_regime = "Compression";
      else r.structure_regime = "Trend";

      // Step 2 — trend
      int bull_pts = 0, bear_pts = 0;
      if(StringFind(r.market_structure, "HH") >= 0 || StringFind(r.market_structure, "Bullish") >= 0) bull_pts += 40;
      if(StringFind(r.market_structure, "LH") >= 0 || StringFind(r.market_structure, "Bearish") >= 0) bear_pts += 40;
      if(n_d1 >= 2 && d1[0].close > d1[1].close) bull_pts += 15; else bear_pts += 15;
      if(n_h4 >= 2 && h4[0].close > h4[0].open) bull_pts += 10; else bear_pts += 10;
      double adx = GetBuf(m_h_adx_h4);
      r.trend_strength = ClampD(adx, 0, 100);
      bull_pts += (int)ClampD(adx * 0.35, 0, 35);
      bear_pts += (int)ClampD(adx * 0.35, 0, 35);

      int net = bull_pts - bear_pts;
      r.trend_score = ClampD(50 + net * 0.5, 0, 100);
      if(net >= 45) { r.trend_class = SWING_TREND_STRONG_BULL; r.trend = "Strong Bullish"; }
      else if(net >= 25) { r.trend_class = SWING_TREND_BULLISH; r.trend = "Bullish"; }
      else if(net >= 10) { r.trend_class = SWING_TREND_WEAK_BULL; r.trend = "Weak Bullish"; }
      else if(net <= -45) { r.trend_class = SWING_TREND_STRONG_BEAR; r.trend = "Strong Bearish"; }
      else if(net <= -25) { r.trend_class = SWING_TREND_BEARISH; r.trend = "Bearish"; }
      else if(net <= -10) { r.trend_class = SWING_TREND_WEAK_BEAR; r.trend = "Weak Bearish"; }
      else { r.trend_class = SWING_TREND_SIDEWAYS; r.trend = "Sideways"; r.trend_score = 50; }

      // Step 3 — swings (H4 external)
      m_swing_n = 0;
      CollectSwings(h4, n_h4, atr_h4, true);
      double sh = 0, sl = 0, psh = 0, psl = 0;
      for(int i = 0; i < m_swing_n; i++)
        {
         if(m_swings[i].is_high) { psh = sh; sh = m_swings[i].price; if(r.current_swing_time == 0) { r.current_swing_price = sh; r.current_swing_time = m_swings[i].time; } }
         else { psl = sl; sl = m_swings[i].price; if(r.previous_swing_time == 0 && sl > 0) { r.previous_swing_price = sl; r.previous_swing_time = m_swings[i].time; } }
        }
      if(psh > 0) { r.previous_swing_price = psh; r.previous_swing_time = m_swings[1].time; }
      if(psl > 0 && r.previous_swing_price == 0) r.previous_swing_price = psl;
      r.swing_score = ClampD((m_swing_n > 2 ? 55 : 35) + r.trend_strength * 0.3, 0, 100);

      bool bullish_bias = (r.trend_class <= SWING_TREND_WEAK_BULL);
      bool bearish_bias = (r.trend_class >= SWING_TREND_WEAK_BEAR);
      r.swing_direction = bullish_bias ? "Bullish" : (bearish_bias ? "Bearish" : "Neutral");

      // Step 4 — SMC
      r.rsi_h1 = GetBuf(m_h_rsi_h1);
      double macd_main[], macd_sig[];
      ArraySetAsSeries(macd_main, true);
      ArraySetAsSeries(macd_sig, true);
      if(CopyBuffer(m_h_macd_m15, 0, 1, 3, macd_main) >= 2 && CopyBuffer(m_h_macd_m15, 1, 1, 3, macd_sig) >= 2)
         r.macd_hist_m15 = macd_main[0] - macd_sig[0];

      if(sh > 0 && h4[0].close > sh && (h4[0].close - sh) >= m_cfg.bos_min_atr * atr_h4)
        { r.bos_detected = true; r.smc_score += 20; }
      if(sl > 0 && h4[0].close < sl && (sl - h4[0].close) >= m_cfg.bos_min_atr * atr_h4)
        { r.bos_detected = true; r.smc_score += 20; }

      if(bullish_bias && sl > 0 && m5[0].low < sl && m5[0].close > sl)
        { r.liquidity_grab = true; r.liquidity_score += 25; }
      if(bearish_bias && sh > 0 && m5[0].high > sh && m5[0].close < sh)
        { r.liquidity_grab = true; r.liquidity_score += 25; }

      double eq_tol = atr_h4 * 0.08;
      for(int i = 1; i < MathMin(m_swing_n, 12); i++)
        {
         if(m_swings[i].is_high && MathAbs(m_swings[i].price - sh) <= eq_tol) r.equal_high = true;
         if(!m_swings[i].is_high && MathAbs(m_swings[i].price - sl) <= eq_tol) r.equal_low = true;
        }

      if(n_m15 >= 3)
        {
         if(m15[1].close < m15[1].open && m15[0].close > m15[0].open && m15[0].close > m15[1].high)
            r.order_block = true;
         if(m15[2].high < m15[0].low || m15[2].low > m15[0].high)
            r.fvg = true;
        }

      double d1_mid = (n_d1 > 0 ? (d1[0].high + d1[0].low) / 2.0 : 0);
      double px = m5[0].close;
      if(d1_mid > 0)
        {
         r.in_premium = (px > d1_mid);
         r.in_discount = (px < d1_mid);
        }

      if(r.bos_detected) r.smc_score += 15;
      if(r.order_block) r.smc_score += 12;
      if(r.fvg) r.smc_score += 8;
      if(r.in_discount && bullish_bias) r.smc_score += 10;
      if(r.in_premium && bearish_bias) r.smc_score += 10;
      r.smc_score = ClampD(r.smc_score, 0, 100);
      r.smc_summary = (r.bos_detected ? "BOS " : "") + (r.liquidity_grab ? "LiqGrab " : "") +
                      (r.order_block ? "OB " : "") + (r.fvg ? "FVG " : "");

      // Step 5 — pullback
      double swing_rng = MathAbs(sh - sl);
      if(swing_rng > 0 && bullish_bias)
         r.pullback_pct = ClampD((sh - px) / swing_rng * 100, 0, 100);
      else if(swing_rng > 0 && bearish_bias)
         r.pullback_pct = ClampD((px - sl) / swing_rng * 100, 0, 100);

      r.pullback_healthy = (r.pullback_pct >= 25 && r.pullback_pct <= m_cfg.max_pullback_pct);
      if(r.pullback_pct > m_cfg.max_pullback_pct) r.pullback_quality = "Deep — rejected";
      else if(r.pullback_pct >= 35 && r.pullback_pct <= 62) r.pullback_quality = "Healthy";
      else if(r.pullback_pct > 0) r.pullback_quality = "Shallow";
      else r.pullback_quality = "None";

      if(r.pullback_pct >= 30 && r.pullback_pct <= 65) r.phase = SWING_PHASE_PULLBACK;
      else if(r.bos_detected) r.phase = SWING_PHASE_CONTINUATION;
      else if(r.structure_regime == "Compression") r.phase = SWING_PHASE_COMPRESSION;
      else if(r.structure_regime == "Expansion") r.phase = SWING_PHASE_EXPANSION;
      else if(r.trend_class == SWING_TREND_SIDEWAYS) r.phase = SWING_PHASE_RANGE;
      else r.phase = SWING_PHASE_IMPULSE;
      r.current_phase = SwingStratPhaseToString(r.phase);

      // Step 6 — momentum
      double body = MathAbs(h1[0].close - h1[0].open);
      double body_pct = body / MathMax(h1[0].high - h1[0].low, _Point);
      double mom = 0;
      if(bullish_bias && r.rsi_h1 > m_cfg.rsi_bull) mom += 25;
      if(bearish_bias && r.rsi_h1 < m_cfg.rsi_bear) mom += 25;
      if(bullish_bias && r.macd_hist_m15 > m_cfg.macd_min_hist) mom += 20;
      if(bearish_bias && r.macd_hist_m15 < -m_cfg.macd_min_hist) mom += 20;
      if(body_pct >= m_cfg.min_body_pct) mom += 15;
      if(n_m5 >= 5)
        {
         double vol_now = (double)m5[0].tick_volume;
         double vol_avg = 0;
         for(int v = 1; v <= 5; v++) vol_avg += (double)m5[v].tick_volume;
         vol_avg /= 5.0;
         if(vol_avg > 0 && vol_now / vol_avg >= m_cfg.min_volume_ratio) mom += 15;
        }
      if(n_h4 >= 2 && atr_h4 > 0)
        {
         double prev_atr = GetBuf(m_h_atr_h4, 2);
         if(prev_atr > 0) { r.atr_expansion = atr_h4 / prev_atr; if(r.atr_expansion >= 1.05) mom += 10; }
        }
      r.momentum_score = ClampD(mom, 0, 100);
      r.momentum_summary = "RSI " + DoubleToString(r.rsi_h1, 1) + " MACD " + DoubleToString(r.macd_hist_m15, 2);

      // Step 7 — breakout
      bool body_break = false;
      if(bullish_bias && sh > 0 && h1[0].close > sh && body_pct >= m_cfg.min_body_pct) body_break = true;
      if(bearish_bias && sl > 0 && h1[0].close < sl && body_pct >= m_cfg.min_body_pct) body_break = true;
      bool no_reject = !(bullish_bias && sh > 0 && h1[0].high > sh && h1[0].close <= sh);
      r.breakout_valid = (body_break && no_reject && r.atr_expansion >= 0.95);
      r.breakout_score = ClampD((body_break ? 40 : 10) + (no_reject ? 25 : 0) + (r.atr_expansion >= 1.05 ? 20 : 5), 0, 100);
      r.breakout_summary = r.breakout_valid ? "Validated body close breakout" : "Breakout not confirmed";

      // Step 8 — confidence
      r.liquidity_score = ClampD(r.liquidity_score + (r.liquidity_grab ? 20 : 5), 0, 100);
      r.confidence = ClampD(r.trend_score * 0.22 + r.swing_score * 0.18 + r.momentum_score * 0.18 +
                            r.smc_score * 0.22 + r.liquidity_score * 0.10 + r.breakout_score * 0.10, 0, 100);

      // Step 9 — entry quality
      if(r.confidence >= 88 && r.pullback_healthy && r.breakout_valid)
        { r.entry_quality = SWING_EQ_EXCELLENT; }
      else if(r.confidence >= 78 && r.pullback_healthy)
        { r.entry_quality = SWING_EQ_GOOD; }
      else if(r.confidence >= 65)
        { r.entry_quality = SWING_EQ_AVERAGE; }
      else if(r.confidence >= 50)
        { r.entry_quality = SWING_EQ_WEAK; }
      else
        { r.entry_quality = SWING_EQ_AVOID; }
      r.entry_quality_label = SwingStratEntryQualityToString(r.entry_quality);
      r.entry_explanation = r.entry_quality_label + " — confidence " + DoubleToString(r.confidence, 0) +
                            "% with " + r.pullback_quality + " pullback";

      // Step 10 — risk
      double bid = px;
      if(bullish_bias)
        {
         r.invalidation = (sl > 0 ? sl - atr_m5 * m_cfg.atr_multiplier : bid - atr_h4 * 2);
         r.stop_loss = r.invalidation;
         r.entry_zone_lo = bid - atr_m5 * 0.35;
         r.entry_zone_hi = bid + atr_m5 * 0.15;
         r.tp1 = bid + atr_h4 * 1.5;
         r.tp2 = bid + atr_h4 * 2.5;
         r.tp3 = bid + atr_h4 * 4.0;
         r.max_risk_zone = r.invalidation;
         r.max_risk_zone_label = "Below swing low / demand invalidation";
        }
      else if(bearish_bias)
        {
         r.invalidation = (sh > 0 ? sh + atr_m5 * m_cfg.atr_multiplier : bid + atr_h4 * 2);
         r.stop_loss = r.invalidation;
         r.entry_zone_hi = bid + atr_m5 * 0.35;
         r.entry_zone_lo = bid - atr_m5 * 0.15;
         r.tp1 = bid - atr_h4 * 1.5;
         r.tp2 = bid - atr_h4 * 2.5;
         r.tp3 = bid - atr_h4 * 4.0;
         r.max_risk_zone = r.invalidation;
         r.max_risk_zone_label = "Above swing high / supply invalidation";
        }
      else
        {
         r.entry_zone_lo = bid - atr_m5 * 0.2;
         r.entry_zone_hi = bid + atr_m5 * 0.2;
         r.stop_loss = 0; r.tp1 = 0; r.tp2 = 0; r.tp3 = 0;
        }
      double risk = MathAbs(bid - r.stop_loss);
      double reward = MathAbs(r.tp1 - bid);
      r.risk_reward = (risk > 0 ? reward / risk : 0);
      r.risk_reward_label = "1:" + DoubleToString(r.risk_reward, 1);

      // Step 11 — decision (rules from spec)
      r.signal_class = SWING_SIG_NO_TRADE;
      r.signal = "NO TRADE";
      r.trade_bias = "Neutral";

      bool can_buy = bullish_bias && r.trend_class <= SWING_TREND_WEAK_BULL &&
                     r.momentum_score >= 45 && r.confidence >= m_cfg.min_confidence &&
                     !lifecycle_failed_buy(r);
      bool can_sell = bearish_bias && r.trend_class >= SWING_TREND_WEAK_BEAR &&
                      r.momentum_score >= 45 && r.confidence >= m_cfg.min_confidence;

      if(can_buy && r.risk_reward >= m_cfg.min_rr && r.entry_quality >= SWING_EQ_GOOD)
        {
         r.signal_class = (r.confidence >= 85 ? SWING_SIG_STRONG_SWING_BUY : SWING_SIG_SWING_BUY);
         r.trade_bias = "Bullish Swing";
        }
      else if(can_buy && r.confidence >= m_cfg.min_confidence - 5)
        {
         r.signal_class = SWING_SIG_WAIT;
         r.trade_bias = "Bullish — awaiting confirmation";
        }
      else if(can_sell && r.risk_reward >= m_cfg.min_rr && r.entry_quality >= SWING_EQ_GOOD)
        {
         r.signal_class = (r.confidence >= 85 ? SWING_SIG_STRONG_SWING_SELL : SWING_SIG_SWING_SELL);
         r.trade_bias = "Bearish Swing";
        }
      else if(can_sell)
        {
         r.signal_class = SWING_SIG_WAIT;
         r.trade_bias = "Bearish — awaiting confirmation";
        }
      else if(r.confidence >= 55)
        {
         r.signal_class = SWING_SIG_WAIT;
         r.trade_bias = "Monitor — insufficient confirmations";
        }

      r.signal = SwingStratSignalToString(r.signal_class);

      // Step 12 — explanation
      BuildExplanation(r, h4, n_h4, atr_h4);
      r.status_line = r.signal + " | " + DoubleToString(r.confidence, 0) + "% | " + r.trend;
     }

   bool lifecycle_failed_buy(const VantageSwingStratResult &r) const
     {
      return (!r.bos_detected && r.trend_class >= SWING_TREND_SIDEWAYS);
     }

   void BuildExplanation(VantageSwingStratResult &r, MqlRates &h4[], const int n_h4, const double atr_h4)
     {
      string ex = "";
      ex += "The H4 trend remains " + StringToLowerCopy(r.trend) + " with structure " + r.market_structure + ". ";
      if(r.bos_detected) ex += "A recent Break of Structure has been detected. ";
      if(r.liquidity_grab) ex += "Liquidity was swept beyond the prior swing before rejection. ";
      if(r.in_discount && r.swing_direction == "Bullish")
         ex += "Price trades in a discount zone relative to the D1 range. ";
      if(r.in_premium && r.swing_direction == "Bearish")
         ex += "Price trades in a premium zone relative to the D1 range. ";
      ex += "Current phase is " + r.current_phase + " with " + r.pullback_quality + " retracement (" +
            DoubleToString(r.pullback_pct, 0) + "%). ";
      ex += "Momentum on H1/M15 " + (r.momentum_score >= 55 ? "supports" : "does not yet fully support") +
            " the swing thesis. ";
      if(r.confidence >= m_cfg.min_confidence)
         ex += "Overall confidence is elevated at " + DoubleToString(r.confidence, 0) + "%.";
      else
         ex += "Confidence remains below the configured threshold — stand aside.";
      r.market_explanation = ex;

      r.reason = "";
      if(r.bos_detected) r.reason += "BOS confirmed. ";
      if(r.liquidity_grab) r.reason += "Liquidity sweep. ";
      if(r.pullback_healthy) r.reason += "Healthy pullback. ";
      if(r.breakout_valid) r.reason += "Breakout validated. ";
      if(r.reason == "") r.reason = "Insufficient multi-factor confirmation for swing entry.";
     }

   string StringToLowerCopy(string s) const
     {
      StringToLower(s);
      return s;
     }

   void ClearChart(void)
     {
      int total = ObjectsTotal(0, 0, -1);
      for(int i = total - 1; i >= 0; i--)
        {
         string n = ObjectName(0, i, 0, -1);
         if(StringFind(n, SWING_STRAT_OBJ_PREFIX) == 0) ObjectDelete(0, n);
        }
     }

   void DrawChart(const VantageSwingStratResult &r)
     {
      if(!m_cfg.show_chart) return;
      if(r.invalidation > 0)
        {
         string id = SWING_STRAT_OBJ_PREFIX + "INV";
         if(ObjectFind(0, id) < 0) ObjectCreate(0, id, OBJ_HLINE, 0, 0, r.invalidation);
         ObjectSetDouble(0, id, OBJPROP_PRICE, r.invalidation);
         ObjectSetInteger(0, id, OBJPROP_COLOR, clrOrangeRed);
        }
      if(r.entry_zone_lo > 0 && r.entry_zone_hi > 0)
        {
         string id = SWING_STRAT_OBJ_PREFIX + "ZONE";
         datetime t0 = iTime(m_symbol, PERIOD_M5, 0);
         datetime t1 = t0 + PeriodSeconds(PERIOD_M5) * 8;
         if(ObjectFind(0, id) < 0) ObjectCreate(0, id, OBJ_RECTANGLE, 0, t0, r.entry_zone_hi, t1, r.entry_zone_lo);
         ObjectMove(0, id, 0, t0, r.entry_zone_hi);
         ObjectMove(0, id, 1, t1, r.entry_zone_lo);
         ObjectSetInteger(0, id, OBJPROP_COLOR, clrDodgerBlue);
         ObjectSetInteger(0, id, OBJPROP_FILL, true);
         ObjectSetInteger(0, id, OBJPROP_BACK, true);
        }
     }

public:
   CVantageSwingStrategy(void) : m_inited(false), m_swing_n(0), m_last_m5_bar(0),
      m_h_atr_d1(INVALID_HANDLE), m_h_atr_h4(INVALID_HANDLE), m_h_atr_h1(INVALID_HANDLE),
      m_h_atr_m15(INVALID_HANDLE), m_h_atr_m5(INVALID_HANDLE),
      m_h_rsi_h1(INVALID_HANDLE), m_h_macd_m15(INVALID_HANDLE), m_h_adx_h4(INVALID_HANDLE) {}

   bool Init(const string symbol, const VantageSwingStratConfig &cfg)
     {
      m_symbol = symbol;
      m_cfg = cfg;
      m_validator.Configure(cfg.approved_aliases, cfg.allow_suffix, cfg.allow_prefix);
      m_h_atr_d1 = iATR(m_symbol, PERIOD_D1, cfg.atr_period);
      m_h_atr_h4 = iATR(m_symbol, PERIOD_H4, cfg.atr_period);
      m_h_atr_h1 = iATR(m_symbol, PERIOD_H1, cfg.atr_period);
      m_h_atr_m15 = iATR(m_symbol, PERIOD_M15, cfg.atr_period);
      m_h_atr_m5 = iATR(m_symbol, PERIOD_M5, cfg.atr_period);
      m_h_rsi_h1 = iRSI(m_symbol, PERIOD_H1, 14, PRICE_CLOSE);
      m_h_macd_m15 = iMACD(m_symbol, PERIOD_M15, 12, 26, 9, PRICE_CLOSE);
      m_h_adx_h4 = iADX(m_symbol, PERIOD_H4, 14);
      m_inited = (m_h_atr_h4 != INVALID_HANDLE);
      return m_inited;
     }

   void Release(void)
     {
      ClearChart();
      Rel(m_h_atr_d1); Rel(m_h_atr_h4); Rel(m_h_atr_h1); Rel(m_h_atr_m15); Rel(m_h_atr_m5);
      Rel(m_h_rsi_h1); Rel(m_h_macd_m15); Rel(m_h_adx_h4);
      m_inited = false;
     }

   bool Evaluate(const bool force, VantageSwingStratResult &out)
     {
      ZeroMemory(out);
      out.symbol = m_symbol;
      out.engine_enabled = m_cfg.enable;
      out.engine_phase = 1;
      out.signal = "NO TRADE";
      out.trend = "Sideways";
      out.market_structure = "Range";
      out.current_phase = "Unknown";

      if(!m_cfg.enable)
        {
         out.valid = true;
         out.disable_reason = "Swing Strategy Engine disabled";
         return true;
        }
      string base = "";
      out.gold_symbol_valid = m_validator.IsApprovedGoldSymbol(m_symbol, base);
      out.base_symbol = base;
      if(m_cfg.gold_only && !out.gold_symbol_valid)
        {
         out.valid = true;
         out.disable_reason = VANTAGE_SWING_STRAT_DISABLE_MSG;
         return true;
        }
      if(!m_inited) return false;

      MqlRates m5[];
      if(!CopyClosed(PERIOD_M5, 120, m5)) return false;
      datetime bar_t = m5[0].time;
      if(!force && bar_t == m_last_m5_bar) { out = m_last; return true; }

      MqlRates d1[], h4[], h1[], m15[];
      CopyClosed(PERIOD_D1, 60, d1);
      CopyClosed(PERIOD_H4, 100, h4);
      CopyClosed(PERIOD_H1, 120, h1);
      CopyClosed(PERIOD_M15, 100, m15);

      RunPipeline(out, d1, h4, h1, m15, m5,
                  ArraySize(d1), ArraySize(h4), ArraySize(h1), ArraySize(m15), ArraySize(m5));

      out.valid = true;
      out.analysis_active = true;
      out.eval_bar_m5 = bar_t;
      out.chart_objects_active = m_cfg.show_chart;
      if(m_cfg.show_chart) DrawChart(out);

      m_last_m5_bar = bar_t;
      m_last = out;
      out = m_last;
      return true;
     }

   string ToJson(const VantageSwingStratResult &r) const
     {
      string j = "{";
      j += "\"module\":\"swing_strategy\",";
      j += "\"version\":\"" + VANTAGE_SWING_STRAT_VERSION + "\",";
      j += "\"valid\":" + (r.valid ? "true" : "false") + ",";
      j += "\"gold_symbol_valid\":" + (r.gold_symbol_valid ? "true" : "false") + ",";
      j += "\"symbol\":\"" + JsonEscape(r.symbol) + "\",";
      j += "\"trend\":\"" + JsonEscape(r.trend) + "\",";
      j += "\"market_structure\":\"" + JsonEscape(r.market_structure) + "\",";
      j += "\"internal_structure\":\"" + JsonEscape(r.internal_structure) + "\",";
      j += "\"external_structure\":\"" + JsonEscape(r.external_structure) + "\",";
      j += "\"structure_regime\":\"" + JsonEscape(r.structure_regime) + "\",";
      j += "\"current_phase\":\"" + JsonEscape(r.current_phase) + "\",";
      j += "\"swing_direction\":\"" + JsonEscape(r.swing_direction) + "\",";
      j += "\"trend_score\":" + DoubleToString(r.trend_score, 1) + ",";
      j += "\"swing_score\":" + DoubleToString(r.swing_score, 1) + ",";
      j += "\"momentum_score\":" + DoubleToString(r.momentum_score, 1) + ",";
      j += "\"smc_score\":" + DoubleToString(r.smc_score, 1) + ",";
      j += "\"liquidity_score\":" + DoubleToString(r.liquidity_score, 1) + ",";
      j += "\"breakout_score\":" + DoubleToString(r.breakout_score, 1) + ",";
      j += "\"confidence\":" + DoubleToString(r.confidence, 1) + ",";
      j += "\"signal\":\"" + JsonEscape(r.signal) + "\",";
      j += "\"entry_quality\":\"" + JsonEscape(r.entry_quality_label) + "\",";
      j += "\"entry_zone\":[" + DoubleToString(r.entry_zone_lo, _Digits) + "," + DoubleToString(r.entry_zone_hi, _Digits) + "],";
      j += "\"stop_loss\":" + DoubleToString(r.stop_loss, _Digits) + ",";
      j += "\"invalidation\":" + DoubleToString(r.invalidation, _Digits) + ",";
      j += "\"tp1\":" + DoubleToString(r.tp1, _Digits) + ",";
      j += "\"tp2\":" + DoubleToString(r.tp2, _Digits) + ",";
      j += "\"tp3\":" + DoubleToString(r.tp3, _Digits) + ",";
      j += "\"risk_reward\":\"" + JsonEscape(r.risk_reward_label) + "\",";
      j += "\"risk_reward_ratio\":" + DoubleToString(r.risk_reward, 2) + ",";
      j += "\"reason\":\"" + JsonEscape(r.reason) + "\",";
      j += "\"market_explanation\":\"" + JsonEscape(r.market_explanation) + "\",";
      j += "\"trade_bias\":\"" + JsonEscape(r.trade_bias) + "\",";
      j += "\"pullback_pct\":" + DoubleToString(r.pullback_pct, 1) + ",";
      j += "\"pullback_quality\":\"" + JsonEscape(r.pullback_quality) + "\",";
      j += "\"atr_h4\":" + DoubleToString(r.atr_h4, _Digits) + ",";
      j += "\"current_swing_price\":" + DoubleToString(r.current_swing_price, _Digits) + ",";
      j += "\"previous_swing_price\":" + DoubleToString(r.previous_swing_price, _Digits) + ",";
      j += "\"smc_summary\":\"" + JsonEscape(r.smc_summary) + "\",";
      j += "\"momentum_summary\":\"" + JsonEscape(r.momentum_summary) + "\",";
      j += "\"breakout_summary\":\"" + JsonEscape(r.breakout_summary) + "\",";
      j += "\"max_risk_zone\":" + DoubleToString(r.max_risk_zone, _Digits) + ",";
      j += "\"status_line\":\"" + JsonEscape(r.status_line) + "\",";
      j += "\"eval_bar_m5\":" + IntegerToString((int)r.eval_bar_m5) + ",";
      j += "\"engine_phase\":" + IntegerToString(r.engine_phase);
      j += "}";
      return j;
     }
  };

#endif
