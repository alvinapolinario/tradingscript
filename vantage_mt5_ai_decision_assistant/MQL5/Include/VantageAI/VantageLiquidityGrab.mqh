//+------------------------------------------------------------------+
//| VantageLiquidityGrab.mqh                                         |
//| Liquidity Grab Detection — state machine, scoring, alerts        |
//| Advisory-only — never opens, modifies, or closes trades          |
//+------------------------------------------------------------------+
#ifndef VANTAGE_LIQUIDITY_GRAB_MQH
#define VANTAGE_LIQUIDITY_GRAB_MQH

#include "VantageTypes.mqh"
#include "VantageLiquidityGrabTypes.mqh"
#include "VantageGoldSMCValidator.mqh"

#define LG_OBJ_PREFIX "VAI_LG_"

class CVantageLiquidityGrab
  {
private:
   string                      m_symbol;
   VantageLiquidityGrabConfig  m_cfg;
   VantageLiquidityGrabResult  m_last;
   CVantageGoldSymbolValidator m_validator;
   VantageLiquidityGrabLevel   m_levels[LG_MAX_LEVELS];
   int                         m_level_count;
   VantageLiquidityGrabCandidate m_candidates[LG_MAX_CANDIDATES];
   int                         m_candidate_count;
   int                         m_active_idx;       // best candidate index (-1 none)
   datetime                    m_last_m5_bar;
   datetime                    m_last_alert_time;
   string                      m_last_alert_key;
   int                         m_h_atr;
   int                         m_h_ema20_h1, m_h_ema50_h1, m_h_ema200_h1;
   int                         m_h_ema20_h4, m_h_ema50_h4, m_h_ema200_h4;
   int                         m_candidate_serial;
   bool                        m_inited;

   void Rel(int &h) { if(h != INVALID_HANDLE) { IndicatorRelease(h); h = INVALID_HANDLE; } }

   void Debug(const string msg) const
     {
      if(!m_cfg.debug_log) return;
      Print("[LiquidityGrab] ", msg);
     }

   void ResetResult(VantageLiquidityGrabResult &r)
     {
      r.valid = false;
      r.gold_symbol_valid = false;
      r.engine_enabled = false;
      r.analysis_active = false;
      r.symbol = m_symbol;
      r.base_symbol = "";
      r.status_line = "";
      r.disable_reason = "";
      r.detection_tf = m_cfg.tf_detect;
      r.confirmation_tf = m_cfg.tf_confirm;
      r.higher_tf = m_cfg.tf_context;
      r.direction = LG_DIR_NONE;
      r.status = LG_STATUS_NO_VALID_SETUP;
      r.machine_state = LG_STATE_IDLE;
      r.confidence_score = 0.0;
      r.liquidity_level_id = "";
      r.liquidity_level_type = "";
      r.liquidity_level_price = 0.0;
      r.sweep_price = 0.0;
      r.sweep_distance = 0.0;
      r.sweep_distance_atr = 0.0;
      r.rejection_close_price = 0.0;
      r.wick_ratio = 0.0;
      r.displacement_detected = false;
      r.displacement_strength = 0.0;
      r.mss_detected = false;
      r.mss_type = "NONE";
      r.mss_level = 0.0;
      r.fvg_detected = false;
      r.volume_ratio = 1.0;
      r.session_name = "";
      r.higher_timeframe_bias = "NEUTRAL";
      r.ema_alignment = "Mixed";
      r.is_countertrend = false;
      r.news_restricted = false;
      r.spread_at_detection = 0.0;
      r.candidate_start_time = 0;
      r.confirmation_time = 0;
      r.expiry_time = 0;
      r.invalidation_reason = "";
      r.evidence_json = "";
      r.warnings_json = "";
      r.nearest_opposing_liquidity = 0.0;
      r.nearest_opposing_label = "";
      r.invalidation_level = 0.0;
      r.recommendation = "WAIT";
      r.technical_narrative = "";
      r.action_guidance = "NO VALID SETUP";
      r.setup_age_bars = 0;
      r.confirmation_countdown = 0;
      r.last_alert = "";
      r.last_alert_time = 0;
      r.chart_objects_active = false;
      r.eval_bar_m5 = 0;
      r.engine_phase = 1;
     }

   datetime ToUtcApprox(const datetime server_t) const
     {
      return server_t - (datetime)(m_cfg.server_utc_offset_hours * 3600);
     }

   int HourUtc(const datetime server_t) const
     {
      MqlDateTime dt;
      TimeToStruct(ToUtcApprox(server_t), dt);
      return dt.hour;
     }

   bool InHourRange(const int hour, const int start_h, const int end_h) const
     {
      if(start_h == end_h) return false;
      if(start_h < end_h) return (hour >= start_h && hour < end_h);
      return (hour >= start_h || hour < end_h);
     }

   string CurrentSessionName(const datetime server_t) const
     {
      int h = HourUtc(server_t);
      bool asian = InHourRange(h, m_cfg.asian_start_utc, m_cfg.asian_end_utc);
      bool london = InHourRange(h, m_cfg.london_start_utc, m_cfg.london_end_utc);
      bool ny = InHourRange(h, m_cfg.ny_start_utc, m_cfg.ny_end_utc);
      if(london && ny) return "London–New York Overlap";
      if(ny) return "New York";
      if(london) return "London";
      if(asian) return "Asian";
      return "Off-session";
     }

   bool SameUtcDay(const datetime a, const datetime b) const
     {
      MqlDateTime d1, d2;
      TimeToStruct(ToUtcApprox(a), d1);
      TimeToStruct(ToUtcApprox(b), d2);
      return (d1.year == d2.year && d1.mon == d2.mon && d1.day == d2.day);
     }

   bool GetClosedBar(const ENUM_TIMEFRAMES tf, MqlRates &bar)
     {
      MqlRates rates[];
      if(CopyRates(m_symbol, tf, 1, 1, rates) != 1) return false;
      bar = rates[0];
      return true;
     }

   bool CopyRatesClosed(const ENUM_TIMEFRAMES tf, const int count, MqlRates &rates[])
     {
      ArraySetAsSeries(rates, true);
      return (CopyRates(m_symbol, tf, 1, count, rates) > 0);
     }

   double GetAtr(const ENUM_TIMEFRAMES tf, const int shift = 1)
     {
      if(tf == m_cfg.tf_detect && m_h_atr != INVALID_HANDLE)
        {
         double a[];
         if(CopyBuffer(m_h_atr, 0, shift, 1, a) == 1) return a[0];
        }
      int h = iATR(m_symbol, tf, m_cfg.atr_period);
      if(h == INVALID_HANDLE) return 0.0;
      double a[];
      if(CopyBuffer(h, 0, shift, 1, a) != 1) { IndicatorRelease(h); return 0.0; }
      IndicatorRelease(h);
      return a[0];
     }

   double GetEma(const int handle, const int shift = 1)
     {
      if(handle == INVALID_HANDLE) return 0.0;
      double e[];
      if(CopyBuffer(handle, 0, shift, 1, e) != 1) return 0.0;
      return e[0];
     }

   void ClearLevels(void)
     {
      m_level_count = 0;
     }

   void AddLevel(const ENUM_LG_LEVEL_TYPE type, const double price, const bool is_bsl,
                 const ENUM_TIMEFRAMES src_tf, const double strength, const string session = "")
     {
      if(price <= 0.0 || !MathIsValidNumber(price)) return;
      if(m_level_count >= LG_MAX_LEVELS) return;
      double min_dist = _Point * 3;
      for(int i = 0; i < m_level_count; i++)
        {
         if(m_levels[i].type == type && MathAbs(m_levels[i].price - price) < min_dist)
           {
            if(strength > m_levels[i].strength)
              {
               m_levels[i].price = price;
               m_levels[i].strength = strength;
              }
            return;
           }
        }
      VantageLiquidityGrabLevel lv;
      lv.id = "LG-" + LgLevelTypeToString(type) + "-" + DoubleToString(price, _Digits);
      lv.type = type;
      lv.type_label = LgLevelTypeToString(type);
      lv.price = price;
      lv.is_bsl = is_bsl;
      lv.source_tf = src_tf;
      lv.created = TimeCurrent();
      lv.last_test = 0;
      lv.touch_count = 0;
      lv.swept = false;
      lv.active = true;
      lv.strength = strength;
      lv.session_tag = session;
      lv.expires = 0;
      m_levels[m_level_count++] = lv;
     }

   bool IsSwingHigh(const MqlRates &rates[], const int i, const int left, const int right)
     {
      if(i < right || i + left >= ArraySize(rates)) return false;
      double h = rates[i].high;
      for(int k = 1; k <= left; k++)
         if(rates[i + k].high >= h) return false;
      for(int k = 1; k <= right; k++)
         if(rates[i - k].high >= h) return false;
      return true;
     }

   bool IsSwingLow(const MqlRates &rates[], const int i, const int left, const int right)
     {
      if(i < right || i + left >= ArraySize(rates)) return false;
      double l = rates[i].low;
      for(int k = 1; k <= left; k++)
         if(rates[i + k].low <= l) return false;
      for(int k = 1; k <= right; k++)
         if(rates[i - k].low <= l) return false;
      return true;
     }

   void BuildSessionAndPdLevels(MqlRates &m15[], const int n, const datetime now)
     {
      if(m_cfg.enable_session && n > 10)
        {
         double a_hi = 0, a_lo = 0, l_hi = 0, l_lo = 0, n_hi = 0, n_lo = 0;
         bool fa = false, fl = false, fn = false;
         for(int i = 0; i < n; i++)
           {
            if(!SameUtcDay(m15[i].time, now)) continue;
            int h = HourUtc(m15[i].time);
            if(InHourRange(h, m_cfg.asian_start_utc, m_cfg.asian_end_utc))
              {
               if(!fa) { a_hi = m15[i].high; a_lo = m15[i].low; fa = true; }
               else { if(m15[i].high > a_hi) a_hi = m15[i].high; if(m15[i].low < a_lo) a_lo = m15[i].low; }
              }
            if(InHourRange(h, m_cfg.london_start_utc, m_cfg.london_end_utc))
              {
               if(!fl) { l_hi = m15[i].high; l_lo = m15[i].low; fl = true; }
               else { if(m15[i].high > l_hi) l_hi = m15[i].high; if(m15[i].low < l_lo) l_lo = m15[i].low; }
              }
            if(InHourRange(h, m_cfg.ny_start_utc, m_cfg.ny_end_utc))
              {
               if(!fn) { n_hi = m15[i].high; n_lo = m15[i].low; fn = true; }
               else { if(m15[i].high > n_hi) n_hi = m15[i].high; if(m15[i].low < n_lo) n_lo = m15[i].low; }
              }
           }
         if(fa) { AddLevel(LG_LVL_ASIAN_HIGH, a_hi, true, PERIOD_M15, 10.0, "Asian"); AddLevel(LG_LVL_ASIAN_LOW, a_lo, false, PERIOD_M15, 10.0, "Asian"); }
         if(fl) { AddLevel(LG_LVL_LONDON_HIGH, l_hi, true, PERIOD_M15, 10.0, "London"); AddLevel(LG_LVL_LONDON_LOW, l_lo, false, PERIOD_M15, 10.0, "London"); }
         if(fn) { AddLevel(LG_LVL_NY_HIGH, n_hi, true, PERIOD_M15, 10.0, "New York"); AddLevel(LG_LVL_NY_LOW, n_lo, false, PERIOD_M15, 10.0, "New York"); }
        }

      if(m_cfg.enable_pdh_pdl)
        {
         MqlRates d1[];
         if(CopyRatesClosed(PERIOD_D1, 3, d1) >= 2)
           {
            AddLevel(LG_LVL_PDH, d1[1].high, true, PERIOD_D1, 12.0);
            AddLevel(LG_LVL_PDL, d1[1].low, false, PERIOD_D1, 12.0);
            AddLevel(LG_LVL_CDH, d1[0].high, true, PERIOD_D1, 8.0);
            AddLevel(LG_LVL_CDL, d1[0].low, false, PERIOD_D1, 8.0);
           }
        }
      if(m_cfg.enable_pwh_pwl)
        {
         MqlRates w1[];
         if(CopyRatesClosed(PERIOD_W1, 3, w1) >= 2)
           {
            AddLevel(LG_LVL_PWH, w1[1].high, true, PERIOD_W1, 12.0);
            AddLevel(LG_LVL_PWL, w1[1].low, false, PERIOD_W1, 12.0);
           }
        }
     }

   void BuildSwingAndEqualLevels(MqlRates &rates[], const int n, const double atr)
     {
      if(!m_cfg.enable_swing && !m_cfg.enable_equal) return;
      const int L = m_cfg.swing_left;
      const int R = m_cfg.swing_right;
      double tol = MathMax(_Point * 10, atr * m_cfg.equal_level_atr_mult);

      double swing_hi[16]; int shi = 0;
      double swing_lo[16]; int slo = 0;
      for(int i = R; i < MathMin(n - L, 80); i++)
        {
         if(m_cfg.enable_swing && IsSwingHigh(rates, i, L, R))
           {
            AddLevel(LG_LVL_SWING_HIGH, rates[i].high, true, m_cfg.tf_detect, 8.0);
            if(shi < 16) swing_hi[shi++] = rates[i].high;
           }
         if(m_cfg.enable_swing && IsSwingLow(rates, i, L, R))
           {
            AddLevel(LG_LVL_SWING_LOW, rates[i].low, false, m_cfg.tf_detect, 8.0);
            if(slo < 16) swing_lo[slo++] = rates[i].low;
           }
        }

      if(m_cfg.enable_equal && tol > 0)
        {
         for(int a = 0; a < shi; a++)
           {
            int matches = 0;
            for(int b = 0; b < shi; b++)
               if(MathAbs(swing_hi[a] - swing_hi[b]) <= tol) matches++;
            if(matches >= 2)
               AddLevel(LG_LVL_EQUAL_HIGH, swing_hi[a], true, m_cfg.tf_detect, 10.0);
           }
         for(int a = 0; a < slo; a++)
           {
            int matches = 0;
            for(int b = 0; b < slo; b++)
               if(MathAbs(swing_lo[a] - swing_lo[b]) <= tol) matches++;
            if(matches >= 2)
               AddLevel(LG_LVL_EQUAL_LOW, swing_lo[a], false, m_cfg.tf_detect, 10.0);
           }
        }

      if(n >= 20)
        {
         double r_hi = rates[0].high, r_lo = rates[0].low;
         for(int i = 1; i < 20; i++)
           {
            if(rates[i].high > r_hi) r_hi = rates[i].high;
            if(rates[i].low < r_lo) r_lo = rates[i].low;
           }
         AddLevel(LG_LVL_RANGE_HIGH, r_hi, true, m_cfg.tf_detect, 6.0);
         AddLevel(LG_LVL_RANGE_LOW, r_lo, false, m_cfg.tf_detect, 6.0);
        }
     }

   void BuildEmaLevels(void)
     {
      double e20 = GetEma(m_h_ema20_h1);
      double e50 = GetEma(m_h_ema50_h1);
      double e200 = GetEma(m_h_ema200_h1);
      if(e20 > 0) AddLevel(LG_LVL_EMA20, e20, true, PERIOD_H1, 5.0);
      if(e50 > 0) AddLevel(LG_LVL_EMA50, e50, true, PERIOD_H1, 5.0);
      if(e200 > 0) AddLevel(LG_LVL_EMA200, e200, true, PERIOD_H1, 5.0);
     }

   ENUM_LG_HTF_BIAS EvalHtfBias(void)
     {
      MqlRates h1[], h4[];
      if(CopyRatesClosed(PERIOD_H1, 30, h1) < 20 || CopyRatesClosed(PERIOD_H4, 20, h4) < 10)
         return LG_HTF_NEUTRAL;

      double e20 = GetEma(m_h_ema20_h1);
      double e50 = GetEma(m_h_ema50_h1);
      double e200 = GetEma(m_h_ema200_h1);
      double px = h1[0].close;
      int bull = 0, bear = 0;

      if(e20 > e50 && e50 > e200) bull += 2;
      else if(e20 < e50 && e50 < e200) bear += 2;
      if(px > e20) bull++; else bear++;
      if(px > e50) bull++; else bear++;
      if(px > e200) bull++; else bear++;

      // structure: recent HH/HL vs LH/LL on H1
      double sh = h1[5].high, sl = h1[5].low;
      for(int i = 6; i < 15; i++)
        {
         if(h1[i].high > sh) { bull++; sh = h1[i].high; }
         if(h1[i].low < sl) { bear++; sl = h1[i].low; }
        }

      if(bull >= bear + 3) return LG_HTF_STRONGLY_BULLISH;
      if(bull >= bear + 1) return LG_HTF_BULLISH;
      if(bear >= bull + 3) return LG_HTF_STRONGLY_BEARISH;
      if(bear >= bull + 1) return LG_HTF_BEARISH;
      if(bull > 0 && bear > 0) return LG_HTF_CONFLICTING;
      return LG_HTF_NEUTRAL;
     }

   string EvalEmaAlignment(void)
     {
      double e20 = GetEma(m_h_ema20_h1);
      double e50 = GetEma(m_h_ema50_h1);
      double e200 = GetEma(m_h_ema200_h1);
      if(e20 > e50 && e50 > e200) return "Bullish stack";
      if(e20 < e50 && e50 < e200) return "Bearish stack";
      return "Mixed";
     }

   bool EvalNewsRestricted(bool &available)
     {
      available = false;
      datetime now = TimeTradeServer();
      if(now <= 0) now = TimeCurrent();
      const datetime from = now - (datetime)(m_cfg.news_after_min * 60);
      const datetime to   = now + (datetime)(m_cfg.news_before_min * 60) + 3600;
      MqlCalendarValue values[];
      ResetLastError();
      int n = CalendarValueHistory(values, from, to, NULL, "USD");
      if(n < 0) return false;
      available = true;
      for(int i = 0; i < n; i++)
        {
         MqlCalendarEvent ev;
         if(!CalendarEventById(values[i].event_id, ev)) continue;
         if(ev.importance < CALENDAR_IMPORTANCE_HIGH) continue;
         datetime evt = values[i].time;
         if(now >= evt - m_cfg.news_before_min * 60 && now <= evt + m_cfg.news_after_min * 60)
            return true;
        }
      return false;
     }

   double WickRatioUpper(const MqlRates &c)
     {
      double body_top = MathMax(c.open, c.close);
      double uw = c.high - body_top;
      double rng = c.high - c.low;
      if(rng < _Point) return 0.0;
      return uw / rng;
     }

   double WickRatioLower(const MqlRates &c)
     {
      double body_bot = MathMin(c.open, c.close);
      double lw = body_bot - c.low;
      double rng = c.high - c.low;
      if(rng < _Point) return 0.0;
      return lw / rng;
     }

   bool ValidSweepDistance(const double penetration, const double atr, const double spread_pts)
     {
      double spread_px = spread_pts * _Point;
      double min_dist = MathMax(spread_px * m_cfg.spread_mult, atr * m_cfg.min_sweep_atr);
      min_dist = MathMax(min_dist, _Point * 2);
      double max_dist = atr * m_cfg.max_sweep_atr;
      if(max_dist <= 0) max_dist = atr * 0.5;
      return (penetration >= min_dist && penetration <= max_dist);
     }

   int FindLevelIndex(const string id)
     {
      for(int i = 0; i < m_level_count; i++)
         if(m_levels[i].id == id) return i;
      return -1;
     }

   string NewCandidateId(void)
     {
      m_candidate_serial++;
      MqlDateTime dt;
      TimeToStruct(TimeCurrent(), dt);
      return StringFormat("LG-%04d%02d%02d-%03d", dt.year, dt.mon, dt.day, m_candidate_serial);
     }

   void AddEvidence(VantageLiquidityGrabCandidate &c, const string line)
     {
      if(c.evidence_count >= LG_MAX_EVIDENCE) return;
      c.evidence[c.evidence_count++] = line;
     }

   void AddWarning(VantageLiquidityGrabCandidate &c, const string line)
     {
      if(c.warning_count >= 8) return;
      c.warnings[c.warning_count++] = line;
     }

   bool DetectDisplacement(const MqlRates &rates[], const int max_bars, const bool bearish,
                           const double atr, double &strength)
     {
      strength = 0.0;
      for(int i = 0; i < max_bars && i < ArraySize(rates); i++)
        {
         double body = MathAbs(rates[i].close - rates[i].open);
         if(body < atr * m_cfg.disp_body_atr * 0.5) continue;
         bool ok = bearish ? (rates[i].close < rates[i].open) : (rates[i].close > rates[i].open);
         if(!ok) continue;
         double opp_wick = bearish ? WickRatioLower(rates[i]) : WickRatioUpper(rates[i]);
         if(opp_wick > 0.30) continue;
         strength = body / atr;
         if(body >= atr * m_cfg.disp_body_atr) return true;
        }
      return false;
     }

   bool DetectMSS(MqlRates &rates[], const int n, const bool bearish,
                  double &mss_level, ENUM_LG_MSS_TYPE &mss_type)
     {
      mss_type = LG_MSS_NONE;
      mss_level = 0.0;
      if(n < 10) return false;
      const int L = m_cfg.swing_left;
      const int R = m_cfg.swing_right;
      double pivot = 0.0;
      for(int i = R + 1; i < MathMin(n - L, 40); i++)
        {
         if(bearish && IsSwingLow(rates, i, L, R))
            pivot = rates[i].low;
         if(!bearish && IsSwingHigh(rates, i, L, R))
            pivot = rates[i].high;
        }
      if(pivot <= 0.0) return false;
      double close0 = rates[0].close;
      if(m_cfg.require_close_mss)
        {
         if(bearish && close0 < pivot) { mss_level = pivot; mss_type = LG_MSS_INTERNAL; return true; }
         if(!bearish && close0 > pivot) { mss_level = pivot; mss_type = LG_MSS_INTERNAL; return true; }
         return false;
        }
      if(bearish && rates[0].low < pivot) { mss_level = pivot; mss_type = LG_MSS_INTERNAL; return true; }
      if(!bearish && rates[0].high > pivot) { mss_level = pivot; mss_type = LG_MSS_INTERNAL; return true; }
      return false;
     }

   bool DetectFVG(MqlRates &rates[], const int n, const bool bearish)
     {
      if(n < 4) return false;
      // ICT indexing: candle 1 (older) vs candle 3 (newer) with middle displacement
      if(bearish)
         return (rates[2].low > rates[0].high);
      return (rates[2].high < rates[0].low);
     }

   bool IsGenuineBreakout(const MqlRates &rates[], const int n, const VantageLiquidityGrabCandidate &c)
     {
      if(n < 3) return false;
      bool bsl = (c.direction == LG_DIR_BUY_SIDE_GRAB_BEARISH);
      double lvl = c.level_price;
      int beyond = 0;
      for(int i = 0; i < MathMin(3, n); i++)
        {
         if(bsl && rates[i].close > lvl) beyond++;
         if(!bsl && rates[i].close < lvl) beyond++;
        }
      if(beyond >= 2) return true;
      double body = MathAbs(rates[0].close - rates[0].open);
      double atr = GetAtr(m_cfg.tf_detect);
      if(bsl && rates[0].close > lvl && body >= atr * m_cfg.strong_disp_atr) return true;
      if(!bsl && rates[0].close < lvl && body >= atr * m_cfg.strong_disp_atr) return true;
      return false;
     }

   double ScoreCandidate(VantageLiquidityGrabCandidate &c, const ENUM_LG_HTF_BIAS htf,
                         const bool session_boost, const bool news_restricted)
     {
      double score = 0.0;
      // Level quality
      if(c.level_type == LG_LVL_PDH || c.level_type == LG_LVL_PDL ||
         c.level_type == LG_LVL_PWH || c.level_type == LG_LVL_PWL) score += 12;
      else if(c.level_type == LG_LVL_ASIAN_HIGH || c.level_type == LG_LVL_ASIAN_LOW ||
              c.level_type == LG_LVL_LONDON_HIGH || c.level_type == LG_LVL_LONDON_LOW ||
              c.level_type == LG_LVL_NY_HIGH || c.level_type == LG_LVL_NY_LOW) score += 10;
      else if(c.level_type == LG_LVL_EQUAL_HIGH || c.level_type == LG_LVL_EQUAL_LOW) score += 10;
      else if(c.level_type == LG_LVL_SWING_HIGH || c.level_type == LG_LVL_SWING_LOW) score += 8;

      if(c.sweep_distance_atr > 0 && c.sweep_distance_atr < m_cfg.max_sweep_atr) score += 8;
      if(c.close_back_inside) score += 12;
      else score -= 12;
      if(c.wick_ratio >= m_cfg.min_wick_ratio) score += 6;
      if(c.displacement_detected) score += 12;
      if(c.mss_detected)
        {
         score += 16;
         if(c.mss_type == LG_MSS_EXTERNAL) score += 8;
        }
      if(c.fvg_detected) score += 5;
      if(c.volume_ratio >= m_cfg.elevated_volume_ratio) score += 4;

      bool aligned = false;
      if(c.direction == LG_DIR_BUY_SIDE_GRAB_BEARISH &&
         (htf == LG_HTF_BEARISH || htf == LG_HTF_STRONGLY_BEARISH)) aligned = true;
      if(c.direction == LG_DIR_SELL_SIDE_GRAB_BULLISH &&
         (htf == LG_HTF_BULLISH || htf == LG_HTF_STRONGLY_BULLISH)) aligned = true;
      if(aligned) score += 8;
      else if(htf != LG_HTF_NEUTRAL && htf != LG_HTF_CONFLICTING)
        {
         score -= m_cfg.countertrend_penalty;
         AddWarning(c, "Countertrend vs higher-timeframe bias");
        }
      if(session_boost && m_cfg.session_confluence) score += 5;
      if(news_restricted) score -= m_cfg.news_penalty;

      if(m_cfg.require_mss && !c.mss_detected)
         score = MathMin(score, 69.0);

      if(score < 0) score = 0;
      if(score > 100) score = 100;
      c.score = score;
      return score;
     }

   ENUM_LG_STATUS StatusFromScore(const double score, const ENUM_LG_STATE st) const
     {
      if(st == LG_STATE_BREAKOUT) return LG_STATUS_GENUINE_BREAKOUT;
      if(st == LG_STATE_FAILED) return LG_STATUS_FAILED_SWEEP;
      if(st == LG_STATE_APPROACHING) return LG_STATUS_APPROACH;
      if(st == LG_STATE_SWEPT && score < 40) return LG_STATUS_TEST;
      if(score >= m_cfg.high_conf_threshold && st >= LG_STATE_MSS) return LG_STATUS_HIGH_CONFIDENCE;
      if(score >= m_cfg.confirmed_threshold && st >= LG_STATE_MSS) return LG_STATUS_GRAB_CONFIRMED;
      if(st >= LG_STATE_SWEPT || score >= 55) return LG_STATUS_SWEEP_UNCONFIRMED;
      if(score >= 40) return LG_STATUS_TEST;
      return LG_STATUS_NO_VALID_SETUP;
     }

   void TransitionState(VantageLiquidityGrabCandidate &c, const ENUM_LG_STATE ns)
     {
      if(c.state == ns) return;
      Debug("Candidate " + c.id + " " + LgStateToString(c.state) + " -> " + LgStateToString(ns));
      c.state = ns;
      c.bars_in_state = 0;
     }

   void ProcessCandidateOnBar(VantageLiquidityGrabCandidate &c, MqlRates &rates[], const int n,
                               const double atr, const double spread_pts,
                               const ENUM_LG_HTF_BIAS htf, const bool session_boost,
                               const bool news_restricted)
     {
      if(c.state == LG_STATE_FAILED || c.state == LG_STATE_BREAKOUT || c.state == LG_STATE_CONFIRMED)
         return;

      c.bars_in_state++;
      c.confirmation_bars_left = MathMax(0, m_cfg.confirm_window_bars - c.bars_in_state);

      MqlRates sweep_bar = rates[0];
      bool bsl = (c.direction == LG_DIR_BUY_SIDE_GRAB_BEARISH);

      if(c.state == LG_STATE_SWEPT)
        {
         bool rejected = false;
         if(bsl)
           {
            c.wick_ratio = WickRatioUpper(sweep_bar);
            c.rejection_close = sweep_bar.close;
            c.close_back_inside = (sweep_bar.close < c.level_price);
            rejected = c.close_back_inside || c.wick_ratio >= m_cfg.min_wick_ratio;
           }
         else
           {
            c.wick_ratio = WickRatioLower(sweep_bar);
            c.rejection_close = sweep_bar.close;
            c.close_back_inside = (sweep_bar.close > c.level_price);
            rejected = c.close_back_inside || c.wick_ratio >= m_cfg.min_wick_ratio;
           }
         if(rejected)
           {
            TransitionState(c, LG_STATE_REJECTED);
            AddEvidence(c, "Rejection detected on closed bar");
           }
        }

      if(c.state == LG_STATE_REJECTED)
        {
         double ds = 0;
         if(DetectDisplacement(rates, 3, bsl, atr, ds))
           {
            c.displacement_detected = true;
            c.displacement_strength = ds;
            TransitionState(c, LG_STATE_DISPLACEMENT);
            AddEvidence(c, "Opposite displacement confirmed");
           }
        }

      if(c.state == LG_STATE_DISPLACEMENT || c.state == LG_STATE_REJECTED)
        {
         double mss_lvl = 0;
         ENUM_LG_MSS_TYPE mt = LG_MSS_NONE;
         if(DetectMSS(rates, n, bsl, mss_lvl, mt))
           {
            c.mss_detected = true;
            c.mss_type = mt;
            c.mss_level = mss_lvl;
            TransitionState(c, LG_STATE_MSS);
            AddEvidence(c, "MSS break at " + DoubleToString(mss_lvl, _Digits));
           }
        }

      if(c.state >= LG_STATE_REJECTED)
         c.fvg_detected = DetectFVG(rates, n, bsl);

      if(IsGenuineBreakout(rates, n, c))
        {
         TransitionState(c, LG_STATE_BREAKOUT);
         c.invalidation_reason = "Price held beyond level — breakout more likely";
         AddWarning(c, "GENUINE_BREAKOUT conditions met");
         return;
        }

      if(c.bars_in_state > m_cfg.confirm_window_bars && c.state < LG_STATE_MSS)
        {
         TransitionState(c, LG_STATE_FAILED);
         c.invalidation_reason = "Confirmation window expired";
         return;
        }

      ScoreCandidate(c, htf, session_boost, news_restricted);
      c.status = StatusFromScore(c.score, c.state);

      if(c.score >= m_cfg.confirmed_threshold && c.state >= LG_STATE_MSS &&
         (!m_cfg.require_mss || c.mss_detected))
        {
         TransitionState(c, LG_STATE_CONFIRMED);
         c.confirm_time = rates[0].time;
         c.status = StatusFromScore(c.score, c.state);
        }
     }

   void ScanNewSweeps(MqlRates &rates[], const int n, const double atr, const double spread_pts)
     {
      if(n < 5) return;
      MqlRates bar = rates[0];
      for(int i = 0; i < m_level_count; i++)
        {
         if(!m_levels[i].active || m_levels[i].swept) continue;
         if(m_levels[i].strength < m_cfg.min_level_strength) continue;

         bool swept = false;
         double penetration = 0;
         ENUM_LG_DIRECTION dir = LG_DIR_NONE;

         if(m_levels[i].is_bsl && bar.high > m_levels[i].price)
           {
            penetration = bar.high - m_levels[i].price;
            if(ValidSweepDistance(penetration, atr, spread_pts))
              {
               swept = true;
               dir = LG_DIR_BUY_SIDE_GRAB_BEARISH;
              }
           }
         else if(!m_levels[i].is_bsl && bar.low < m_levels[i].price)
           {
            penetration = m_levels[i].price - bar.low;
            if(ValidSweepDistance(penetration, atr, spread_pts))
              {
               swept = true;
               dir = LG_DIR_SELL_SIDE_GRAB_BULLISH;
              }
           }

         if(!swept) continue;

         // dedupe active candidate on same level
         bool exists = false;
         for(int c = 0; c < m_candidate_count; c++)
           {
            if(m_candidates[c].level_id == m_levels[i].id && m_candidates[c].state < LG_STATE_FAILED)
              { exists = true; break; }
           }
         if(exists) continue;

         if(m_candidate_count >= LG_MAX_CANDIDATES)
           {
            // expire oldest failed first
            int drop = -1;
            for(int c = 0; c < m_candidate_count; c++)
               if(m_candidates[c].state == LG_STATE_FAILED) { drop = c; break; }
            if(drop >= 0)
              {
               for(int k = drop; k < m_candidate_count - 1; k++)
                  m_candidates[k] = m_candidates[k + 1];
               m_candidate_count--;
              }
            else continue;
           }

         VantageLiquidityGrabCandidate cand;
         ZeroMemory(cand);
         cand.id = NewCandidateId();
         cand.state = LG_STATE_SWEPT;
         cand.status = LG_STATUS_SWEEP_UNCONFIRMED;
         cand.direction = dir;
         cand.level_id = m_levels[i].id;
         cand.level_type = m_levels[i].type;
         cand.level_price = m_levels[i].price;
         cand.sweep_price = dir == LG_DIR_BUY_SIDE_GRAB_BEARISH ? bar.high : bar.low;
         cand.sweep_distance = penetration;
         cand.sweep_distance_atr = (atr > 0 ? penetration / atr : 0);
         cand.start_time = bar.time;
         cand.expiry_time = bar.time + (datetime)(m_cfg.confirm_window_bars * PeriodSeconds(m_cfg.tf_detect));
         cand.confirmation_bars_left = m_cfg.confirm_window_bars;
         AddEvidence(cand, "Sweep " + DoubleToString(penetration, _Digits) + " beyond " + m_levels[i].type_label);
         m_candidates[m_candidate_count++] = cand;
         m_levels[i].swept = true;
         m_levels[i].last_test = bar.time;
         Debug("New sweep on " + m_levels[i].type_label + " @ " + DoubleToString(m_levels[i].price, _Digits));
        }
     }

   void ScanApproach(const double price, const double atr)
     {
      if(atr <= 0) return;
      double dist_thresh = atr * m_cfg.approach_atr;
      for(int i = 0; i < m_level_count; i++)
        {
         if(!m_levels[i].active || m_levels[i].swept) continue;
         if(MathAbs(price - m_levels[i].price) <= dist_thresh)
            m_levels[i].touch_count++;
        }
     }

   int PickBestCandidate(void)
     {
      int best = -1;
      double best_score = -1;
      for(int i = 0; i < m_candidate_count; i++)
        {
         if(m_candidates[i].state == LG_STATE_FAILED) continue;
         if(m_candidates[i].score > best_score)
           {
            best_score = m_candidates[i].score;
            best = i;
           }
        }
      return best;
     }

   void FillResultFromCandidate(VantageLiquidityGrabResult &r, const VantageLiquidityGrabCandidate &c,
                                 const ENUM_LG_HTF_BIAS htf, const string session,
                                 const bool news_restricted, const double spread_pts)
     {
      r.direction = c.direction;
      r.status = c.status;
      r.machine_state = c.state;
      r.confidence_score = c.score;
      r.liquidity_level_id = c.level_id;
      r.liquidity_level_type = LgLevelTypeToString(c.level_type);
      r.liquidity_level_price = c.level_price;
      r.sweep_price = c.sweep_price;
      r.sweep_distance = c.sweep_distance;
      r.sweep_distance_atr = c.sweep_distance_atr;
      r.rejection_close_price = c.rejection_close;
      r.wick_ratio = c.wick_ratio;
      r.displacement_detected = c.displacement_detected;
      r.displacement_strength = c.displacement_strength;
      r.mss_detected = c.mss_detected;
      r.mss_type = (c.mss_type == LG_MSS_EXTERNAL ? "EXTERNAL" : (c.mss_detected ? "INTERNAL" : "NONE"));
      r.mss_level = c.mss_level;
      r.fvg_detected = c.fvg_detected;
      r.volume_ratio = c.volume_ratio;
      r.session_name = session;
      r.higher_timeframe_bias = LgHtfBiasToString(htf);
      r.ema_alignment = EvalEmaAlignment();
      r.news_restricted = news_restricted;
      r.spread_at_detection = spread_pts;
      r.candidate_start_time = c.start_time;
      r.confirmation_time = c.confirm_time;
      r.expiry_time = c.expiry_time;
      r.invalidation_reason = c.invalidation_reason;
      r.setup_age_bars = c.bars_in_state;
      r.confirmation_countdown = c.confirmation_bars_left;

      string ev = "";
      for(int i = 0; i < c.evidence_count; i++)
        {
         if(i > 0) ev += ";";
         ev += c.evidence[i];
        }
      r.evidence_json = ev;
      string wn = "";
      for(int i = 0; i < c.warning_count; i++)
        {
         if(i > 0) wn += ";";
         wn += c.warnings[i];
        }
      r.warnings_json = wn;
      r.is_countertrend = (StringFind(wn, "Countertrend") >= 0);

      r.invalidation_level = c.mss_level;
      if(r.status == LG_STATUS_GRAB_CONFIRMED || r.status == LG_STATUS_HIGH_CONFIDENCE)
        {
         r.recommendation = "CONFIRMED STRUCTURAL EVENT";
         r.action_guidance = "Conditions met — monitor invalidation level";
        }
      else if(r.status == LG_STATUS_SWEEP_UNCONFIRMED)
        {
         r.recommendation = "DEVELOPING";
         r.action_guidance = "WAIT FOR CONFIRMATION";
        }
      else if(r.status == LG_STATUS_GENUINE_BREAKOUT)
        {
         r.recommendation = "BREAKOUT MORE LIKELY";
         r.action_guidance = "Liquidity grab thesis cancelled";
        }
      else if(r.status == LG_STATUS_FAILED_SWEEP)
        {
         r.recommendation = "WAIT";
         r.action_guidance = "REVERSAL CONDITIONS NOT COMPLETE";
        }
      else
        {
         r.recommendation = "WAIT";
         r.action_guidance = "NO VALID SETUP";
        }

      r.technical_narrative = "Status " + LgStatusToString(r.status) + " | " +
         LgDirectionToString(r.direction) + " | Score " + DoubleToString(r.confidence_score, 0);
      if(news_restricted)
         r.technical_narrative += " | NEWS_RESTRICTED";
      r.status_line = LgStatusToString(r.status);
     }

   void FindNearestOpposing(const double price, VantageLiquidityGrabResult &r)
     {
      double best = 0;
      string lbl = "";
      for(int i = 0; i < m_level_count; i++)
        {
         if(!m_levels[i].active) continue;
         if(r.direction == LG_DIR_BUY_SIDE_GRAB_BEARISH && !m_levels[i].is_bsl && m_levels[i].price < price)
           {
            if(best == 0 || m_levels[i].price > best) { best = m_levels[i].price; lbl = m_levels[i].type_label; }
           }
         if(r.direction == LG_DIR_SELL_SIDE_GRAB_BULLISH && m_levels[i].is_bsl && m_levels[i].price > price)
           {
            if(best == 0 || m_levels[i].price < best) { best = m_levels[i].price; lbl = m_levels[i].type_label; }
           }
        }
      r.nearest_opposing_liquidity = best;
      r.nearest_opposing_label = lbl;
     }

   void DrawChartObjects(const VantageLiquidityGrabResult &r)
     {
      if(!m_cfg.show_chart_objects) return;
      datetime t0 = iTime(m_symbol, m_cfg.tf_detect, 0);
      datetime t1 = t0 + PeriodSeconds(m_cfg.tf_detect) * 3;

      // Active best level line
      if(r.liquidity_level_price > 0)
        {
         string lid = LG_OBJ_PREFIX + "LVL";
         if(ObjectFind(0, lid) < 0) ObjectCreate(0, lid, OBJ_HLINE, 0, 0, r.liquidity_level_price);
         ObjectSetDouble(0, lid, OBJPROP_PRICE, r.liquidity_level_price);
         ObjectSetInteger(0, lid, OBJPROP_COLOR, r.direction == LG_DIR_BUY_SIDE_GRAB_BEARISH ? clrOrangeRed : clrDodgerBlue);
         ObjectSetString(0, lid, OBJPROP_TEXT, r.liquidity_level_type);
        }

      if(r.sweep_price > 0)
        {
         string sid = LG_OBJ_PREFIX + "SWP";
         if(ObjectFind(0, sid) < 0) ObjectCreate(0, sid, OBJ_ARROW, 0, t0, r.sweep_price);
         ObjectSetInteger(0, sid, OBJPROP_ARROWCODE, r.direction == LG_DIR_BUY_SIDE_GRAB_BEARISH ? 234 : 233);
         ObjectSetInteger(0, sid, OBJPROP_COLOR, clrYellow);
        }

      if(r.mss_detected && r.mss_level > 0)
        {
         string mid = LG_OBJ_PREFIX + "MSS";
         if(ObjectFind(0, mid) < 0) ObjectCreate(0, mid, OBJ_HLINE, 0, 0, r.mss_level);
         ObjectSetDouble(0, mid, OBJPROP_PRICE, r.mss_level);
         ObjectSetInteger(0, mid, OBJPROP_STYLE, STYLE_DASH);
         ObjectSetInteger(0, mid, OBJPROP_COLOR, clrMagenta);
        }

      string lbl = LG_OBJ_PREFIX + "LBL";
      if(ObjectFind(0, lbl) < 0) ObjectCreate(0, lbl, OBJ_TEXT, 0, t1, r.sweep_price > 0 ? r.sweep_price : r.liquidity_level_price);
      ObjectSetString(0, lbl, OBJPROP_TEXT, r.status_line + " " + DoubleToString(r.confidence_score, 0));
      ObjectSetInteger(0, lbl, OBJPROP_COLOR, clrWhite);
     }

   void ClearChartObjects(void)
     {
      int total = ObjectsTotal(0, 0, -1);
      for(int i = total - 1; i >= 0; i--)
        {
         string name = ObjectName(0, i, 0, -1);
         if(StringFind(name, LG_OBJ_PREFIX) == 0)
            ObjectDelete(0, name);
        }
     }

   void MaybeAlert(const VantageLiquidityGrabResult &r)
     {
      if(!m_cfg.alert_enable) return;
      string key = LgStatusToString(r.status) + "|" + r.liquidity_level_id;
      if(key == m_last_alert_key && (TimeCurrent() - m_last_alert_time) < m_cfg.alert_cooldown_sec)
         return;
      if(r.status != LG_STATUS_GRAB_CONFIRMED && r.status != LG_STATUS_HIGH_CONFIDENCE &&
         r.status != LG_STATUS_SWEEP_UNCONFIRMED)
         return;

      string msg = m_symbol + " " + EnumToString(m_cfg.tf_detect) + " " +
                   LgStatusToString(r.status) + " Level " + r.liquidity_level_type +
                   " " + DoubleToString(r.liquidity_level_price, _Digits) +
                   " Score " + DoubleToString(r.confidence_score, 0);
      if(m_cfg.alert_popup) Alert(msg);
      if(m_cfg.alert_push) SendNotification(msg);
      if(m_cfg.alert_sound) PlaySound("alert.wav");
      m_last_alert_key = key;
      m_last_alert_time = TimeCurrent();
      m_last.last_alert = msg;
      m_last.last_alert_time = m_last_alert_time;
     }

   double TickVolumeRatio(MqlRates &rates[], const int n)
     {
      if(!m_cfg.enable_tick_volume || n < m_cfg.volume_avg_period + 1) return 1.0;
      long cur = rates[0].tick_volume;
      double sum = 0;
      for(int i = 1; i <= m_cfg.volume_avg_period; i++)
         sum += (double)rates[i].tick_volume;
      double avg = sum / m_cfg.volume_avg_period;
      if(avg <= 0) return 1.0;
      return (double)cur / avg;
     }

public:
   CVantageLiquidityGrab(void) : m_inited(false), m_level_count(0), m_candidate_count(0),
      m_active_idx(-1), m_last_m5_bar(0), m_last_alert_time(0), m_candidate_serial(0),
      m_h_atr(INVALID_HANDLE), m_h_ema20_h1(INVALID_HANDLE), m_h_ema50_h1(INVALID_HANDLE),
      m_h_ema200_h1(INVALID_HANDLE), m_h_ema20_h4(INVALID_HANDLE), m_h_ema50_h4(INVALID_HANDLE),
      m_h_ema200_h4(INVALID_HANDLE) {}

   bool Init(const string symbol, const VantageLiquidityGrabConfig &cfg)
     {
      m_symbol = symbol;
      m_cfg = cfg;
      m_validator.Configure(cfg.approved_aliases, cfg.allow_broker_suffix, cfg.allow_broker_prefix);
      Rel(m_h_atr);
      m_h_atr = iATR(m_symbol, m_cfg.tf_detect, m_cfg.atr_period);
      m_h_ema20_h1 = iMA(m_symbol, PERIOD_H1, 20, 0, MODE_EMA, PRICE_CLOSE);
      m_h_ema50_h1 = iMA(m_symbol, PERIOD_H1, 50, 0, MODE_EMA, PRICE_CLOSE);
      m_h_ema200_h1 = iMA(m_symbol, PERIOD_H1, 200, 0, MODE_EMA, PRICE_CLOSE);
      m_h_ema20_h4 = iMA(m_symbol, PERIOD_H4, 20, 0, MODE_EMA, PRICE_CLOSE);
      m_h_ema50_h4 = iMA(m_symbol, PERIOD_H4, 50, 0, MODE_EMA, PRICE_CLOSE);
      m_h_ema200_h4 = iMA(m_symbol, PERIOD_H4, 200, 0, MODE_EMA, PRICE_CLOSE);
      if(m_h_atr == INVALID_HANDLE) return false;
      m_inited = true;
      ResetResult(m_last);
      return true;
     }

   void Release(void)
     {
      Rel(m_h_atr);
      Rel(m_h_ema20_h1); Rel(m_h_ema50_h1); Rel(m_h_ema200_h1);
      Rel(m_h_ema20_h4); Rel(m_h_ema50_h4); Rel(m_h_ema200_h4);
      ClearChartObjects();
      m_inited = false;
     }

   bool Evaluate(const bool force, VantageLiquidityGrabResult &out)
     {
      ResetResult(out);
      out.symbol = m_symbol;
      out.engine_enabled = m_cfg.enable;
      out.engine_phase = 1;

      if(!m_cfg.enable)
        {
         out.valid = true;
         out.disable_reason = "Liquidity Grab Monitor disabled in inputs";
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
         out.disable_reason = VANTAGE_LIQGRAB_DISABLE_MSG;
         out.status_line = "Wrong symbol";
         return true;
        }

      if(!m_inited) return false;

      MqlRates m5[];
      if(!CopyRatesClosed(m_cfg.tf_detect, 120, m5)) return false;
      datetime bar_time = m5[0].time;
      bool new_bar = (bar_time != m_last_m5_bar);
      if(!new_bar && !force)
        {
         out = m_last;
         return true;
        }

      double atr = GetAtr(m_cfg.tf_detect);
      double spread_pts = (double)SymbolInfoInteger(m_symbol, SYMBOL_SPREAD);
      out.spread_at_detection = spread_pts;
      datetime now = TimeCurrent();
      string session = CurrentSessionName(now);
      bool session_boost = (session == "London" || session == "New York" || session == "London–New York Overlap");

      bool news_avail = false;
      bool news_restricted = EvalNewsRestricted(news_avail);

      ENUM_LG_HTF_BIAS htf = EvalHtfBias();

      ClearLevels();
      MqlRates m15[];
      CopyRatesClosed(PERIOD_M15, 200, m15);
      BuildSessionAndPdLevels(m15, ArraySize(m15), now);
      BuildSwingAndEqualLevels(m5, ArraySize(m5), atr);
      BuildEmaLevels();

      double bid = SymbolInfoDouble(m_symbol, SYMBOL_BID);
      ScanApproach(bid, atr);

      if(new_bar || force)
        {
         ScanNewSweeps(m5, ArraySize(m5), atr, spread_pts);
         double vol_ratio = TickVolumeRatio(m5, ArraySize(m5));
         for(int i = 0; i < m_candidate_count; i++)
           {
            m_candidates[i].volume_ratio = vol_ratio;
            ProcessCandidateOnBar(m_candidates[i], m5, ArraySize(m5), atr, spread_pts, htf, session_boost, news_restricted);
           }
         m_last_m5_bar = bar_time;
        }

      m_active_idx = PickBestCandidate();
      out.valid = true;
      out.analysis_active = true;
      out.eval_bar_m5 = bar_time;
      out.session_name = session;
      out.news_restricted = news_restricted;
      out.chart_objects_active = m_cfg.show_chart_objects;

      if(m_active_idx >= 0)
         FillResultFromCandidate(out, m_candidates[m_active_idx], htf, session, news_restricted, spread_pts);
      else
        {
         out.status = LG_STATUS_NO_VALID_SETUP;
         out.status_line = "NO_VALID_SETUP";
         out.action_guidance = "NO VALID SETUP";
         out.recommendation = "WAIT";
         out.higher_timeframe_bias = LgHtfBiasToString(htf);
         out.ema_alignment = EvalEmaAlignment();
        }

      FindNearestOpposing(bid, out);
      if(m_cfg.show_chart_objects) DrawChartObjects(out);
      MaybeAlert(out);
      m_last = out;
      return true;
     }

   string ToJson(const VantageLiquidityGrabResult &r) const
     {
      string j = "{";
      j += "\"module\":\"liquidity_grab\",";
      j += "\"version\":\"" + VANTAGE_LIQGRAB_VERSION + "\",";
      j += "\"valid\":" + (r.valid ? "true" : "false") + ",";
      j += "\"gold_symbol_valid\":" + (r.gold_symbol_valid ? "true" : "false") + ",";
      j += "\"engine_enabled\":" + (r.engine_enabled ? "true" : "false") + ",";
      j += "\"analysis_active\":" + (r.analysis_active ? "true" : "false") + ",";
      j += "\"symbol\":\"" + JsonEscape(r.symbol) + "\",";
      j += "\"base_symbol\":\"" + JsonEscape(r.base_symbol) + "\",";
      j += "\"status_line\":\"" + JsonEscape(r.status_line) + "\",";
      j += "\"disable_reason\":\"" + JsonEscape(r.disable_reason) + "\",";
      j += "\"detection_tf\":\"" + JsonEscape(EnumToString(r.detection_tf)) + "\",";
      j += "\"confirmation_tf\":\"" + JsonEscape(EnumToString(r.confirmation_tf)) + "\",";
      j += "\"higher_tf\":\"" + JsonEscape(EnumToString(r.higher_tf)) + "\",";
      j += "\"direction\":\"" + JsonEscape(LgDirectionToString(r.direction)) + "\",";
      j += "\"status\":\"" + JsonEscape(LgStatusToString(r.status)) + "\",";
      j += "\"machine_state\":\"" + JsonEscape(LgStateToString(r.machine_state)) + "\",";
      j += "\"confidence_score\":" + DoubleToString(r.confidence_score, 1) + ",";
      j += "\"liquidity_level_id\":\"" + JsonEscape(r.liquidity_level_id) + "\",";
      j += "\"liquidity_level_type\":\"" + JsonEscape(r.liquidity_level_type) + "\",";
      j += "\"liquidity_level_price\":" + DoubleToString(r.liquidity_level_price, _Digits) + ",";
      j += "\"sweep_price\":" + DoubleToString(r.sweep_price, _Digits) + ",";
      j += "\"sweep_distance\":" + DoubleToString(r.sweep_distance, _Digits) + ",";
      j += "\"sweep_distance_atr\":" + DoubleToString(r.sweep_distance_atr, 3) + ",";
      j += "\"rejection_close_price\":" + DoubleToString(r.rejection_close_price, _Digits) + ",";
      j += "\"wick_ratio\":" + DoubleToString(r.wick_ratio, 3) + ",";
      j += "\"displacement_detected\":" + (r.displacement_detected ? "true" : "false") + ",";
      j += "\"displacement_strength\":" + DoubleToString(r.displacement_strength, 3) + ",";
      j += "\"mss_detected\":" + (r.mss_detected ? "true" : "false") + ",";
      j += "\"mss_type\":\"" + JsonEscape(r.mss_type) + "\",";
      j += "\"mss_level\":" + DoubleToString(r.mss_level, _Digits) + ",";
      j += "\"fvg_detected\":" + (r.fvg_detected ? "true" : "false") + ",";
      j += "\"volume_ratio\":" + DoubleToString(r.volume_ratio, 2) + ",";
      j += "\"session_name\":\"" + JsonEscape(r.session_name) + "\",";
      j += "\"higher_timeframe_bias\":\"" + JsonEscape(r.higher_timeframe_bias) + "\",";
      j += "\"ema_alignment\":\"" + JsonEscape(r.ema_alignment) + "\",";
      j += "\"is_countertrend\":" + (r.is_countertrend ? "true" : "false") + ",";
      j += "\"news_restricted\":" + (r.news_restricted ? "true" : "false") + ",";
      j += "\"spread_at_detection\":" + DoubleToString(r.spread_at_detection, 1) + ",";
      j += "\"candidate_start_time\":" + IntegerToString((int)r.candidate_start_time) + ",";
      j += "\"confirmation_time\":" + IntegerToString((int)r.confirmation_time) + ",";
      j += "\"expiry_time\":" + IntegerToString((int)r.expiry_time) + ",";
      j += "\"invalidation_reason\":\"" + JsonEscape(r.invalidation_reason) + "\",";
      j += "\"evidence\":\"" + JsonEscape(r.evidence_json) + "\",";
      j += "\"warnings\":\"" + JsonEscape(r.warnings_json) + "\",";
      j += "\"nearest_opposing_liquidity\":" + DoubleToString(r.nearest_opposing_liquidity, _Digits) + ",";
      j += "\"nearest_opposing_label\":\"" + JsonEscape(r.nearest_opposing_label) + "\",";
      j += "\"invalidation_level\":" + DoubleToString(r.invalidation_level, _Digits) + ",";
      j += "\"recommendation\":\"" + JsonEscape(r.recommendation) + "\",";
      j += "\"technical_narrative\":\"" + JsonEscape(r.technical_narrative) + "\",";
      j += "\"action_guidance\":\"" + JsonEscape(r.action_guidance) + "\",";
      j += "\"setup_age_bars\":" + IntegerToString(r.setup_age_bars) + ",";
      j += "\"confirmation_countdown\":" + IntegerToString(r.confirmation_countdown) + ",";
      j += "\"last_alert\":\"" + JsonEscape(r.last_alert) + "\",";
      j += "\"last_alert_time\":" + IntegerToString((int)r.last_alert_time) + ",";
      j += "\"chart_objects_active\":" + (r.chart_objects_active ? "true" : "false") + ",";
      j += "\"eval_bar_m5\":" + IntegerToString((int)r.eval_bar_m5) + ",";
      j += "\"engine_phase\":" + IntegerToString(r.engine_phase);
      j += "}";
      return j;
     }
  };

#endif
//+------------------------------------------------------------------+
