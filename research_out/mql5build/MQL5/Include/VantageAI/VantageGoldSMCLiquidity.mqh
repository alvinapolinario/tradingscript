//+------------------------------------------------------------------+
//| VantageGoldSMCLiquidity.mqh                                      |
//| Phase 3 — Gold liquidity map, sessions, equal H/L, sweeps        |
//| Closed bars only — advisory                                      |
//+------------------------------------------------------------------+
#ifndef VANTAGE_GOLD_SMC_LIQUIDITY_MQH
#define VANTAGE_GOLD_SMC_LIQUIDITY_MQH

#include "VantageGoldSMCTypes.mqh"

#define GSMC_LIQ_MAX 24

struct VantageGoldSMCLiqPool
  {
   string id;
   string kind;          // BSL / SSL
   string source;        // PDH, EQH, Asian High, …
   double price;
   ENUM_SMC_LIQ_STATUS status;
   double quality;
  };

class CVantageGoldSMCLiquidity
  {
private:
   string               m_symbol;
   VantageGoldSMCConfig m_cfg;
   int                  m_h_atr_h1;

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

   datetime ToUtcApprox(const datetime server_t)
     {
      // Treat chart/server time as UTC+offset hours
      return server_t - (datetime)(m_cfg.server_utc_offset_hours * 3600);
     }

   int HourUtc(const datetime server_t)
     {
      datetime utc = ToUtcApprox(server_t);
      MqlDateTime dt;
      TimeToStruct(utc, dt);
      return dt.hour;
     }

   bool InHourRange(const int hour, const int start_h, const int end_h)
     {
      if(start_h == end_h) return false;
      if(start_h < end_h)
         return (hour >= start_h && hour < end_h);
      // wraps midnight
      return (hour >= start_h || hour < end_h);
     }

   string CurrentSessionName(const datetime server_t)
     {
      int h = HourUtc(server_t);
      bool asian = InHourRange(h, m_cfg.asian_start_hour_utc, m_cfg.asian_end_hour_utc);
      bool london = InHourRange(h, m_cfg.london_start_hour_utc, m_cfg.london_end_hour_utc);
      bool ny = InHourRange(h, m_cfg.ny_start_hour_utc, m_cfg.ny_end_hour_utc);
      if(london && ny) return "London–New York Overlap";
      if(ny) return "New York";
      if(london) return "London";
      if(asian) return "Asian";
      return "Off-session / rollover";
     }

   bool DayKey(const datetime t, int &y, int &m, int &d)
     {
      datetime utc = ToUtcApprox(t);
      MqlDateTime dt;
      TimeToStruct(utc, dt);
      y = dt.year; m = dt.mon; d = dt.day;
      return true;
     }

   bool SameUtcDay(const datetime a, const datetime b)
     {
      int y1, m1, d1, y2, m2, d2;
      DayKey(a, y1, m1, d1);
      DayKey(b, y2, m2, d2);
      return (y1 == y2 && m1 == m2 && d1 == d2);
     }

   int IsoWeekKey(const datetime t)
     {
      // Approximate week id: year*100 + week-of-year via day-of-year/7
      datetime utc = ToUtcApprox(t);
      MqlDateTime dt;
      TimeToStruct(utc, dt);
      return dt.year * 100 + (dt.day_of_year / 7);
     }

   double GetAtrH1(void)
     {
      double a[];
      if(m_h_atr_h1 == INVALID_HANDLE) return 0.0;
      if(CopyBuffer(m_h_atr_h1, 0, 1, 1, a) != 1) return 0.0;
      return a[0];
     }

   void AddPool(VantageGoldSMCLiqPool &pools[], int &count,
                const string kind, const string source, const double price, const double quality)
     {
      if(price <= 0.0 || !MathIsValidNumber(price)) return;
      if(count >= GSMC_LIQ_MAX) return;
      // de-dupe near-identical
      for(int i = 0; i < count; i++)
        {
         if(pools[i].kind == kind && MathAbs(pools[i].price - price) < _Point * 5)
           {
            if(quality > pools[i].quality)
              {
               pools[i].source = source;
               pools[i].quality = quality;
              }
            return;
           }
        }
      ArrayResize(pools, count + 1);
      pools[count].id = kind + "|" + source;
      pools[count].kind = kind;
      pools[count].source = source;
      pools[count].price = price;
      pools[count].status = SMC_LIQ_ACTIVE;
      pools[count].quality = quality;
      count++;
     }

   void RangeOfSessionToday(MqlRates &m15[], const int n, const datetime now_server,
                            const int start_h, const int end_h,
                            double &out_hi, double &out_lo, bool &found)
     {
      out_hi = 0; out_lo = 0; found = false;
      for(int i = 0; i < n; i++)
        {
         if(!SameUtcDay(m15[i].time, now_server))
            continue;
         int h = HourUtc(m15[i].time);
         if(!InHourRange(h, start_h, end_h))
            continue;
         if(!found)
           {
            out_hi = m15[i].high;
            out_lo = m15[i].low;
            found = true;
           }
         else
           {
            if(m15[i].high > out_hi) out_hi = m15[i].high;
            if(m15[i].low < out_lo) out_lo = m15[i].low;
           }
        }
     }

   void DetectEqualLevels(MqlRates &rates[], const int n, const double tol,
                          double &eq_hi, double &eq_lo, string &hi_note, string &lo_note)
     {
      eq_hi = 0; eq_lo = 0; hi_note = ""; lo_note = "";
      if(n < 30 || tol <= 0) return;
      // Scan recent swing-ish highs: local peaks
      double clusters_hi[8]; int chi = 0;
      double clusters_lo[8]; int clo = 0;
      for(int i = 2; i < MathMin(n - 2, 60); i++)
        {
         if(rates[i].high >= rates[i - 1].high && rates[i].high >= rates[i - 2].high &&
            rates[i].high >= rates[i + 1].high && rates[i].high >= rates[i + 2].high)
           {
            if(chi < 8) clusters_hi[chi++] = rates[i].high;
           }
         if(rates[i].low <= rates[i - 1].low && rates[i].low <= rates[i - 2].low &&
            rates[i].low <= rates[i + 1].low && rates[i].low <= rates[i + 2].low)
           {
            if(clo < 8) clusters_lo[clo++] = rates[i].low;
           }
        }
      for(int a = 0; a < chi; a++)
        {
         int matches = 0;
         for(int b = 0; b < chi; b++)
            if(MathAbs(clusters_hi[a] - clusters_hi[b]) <= tol) matches++;
         if(matches >= 2)
           {
            eq_hi = clusters_hi[a];
            hi_note = "Equal highs ~ " + DoubleToString(eq_hi, _Digits) + " (" + IntegerToString(matches) + ")";
            break;
           }
        }
      for(int a = 0; a < clo; a++)
        {
         int matches = 0;
         for(int b = 0; b < clo; b++)
            if(MathAbs(clusters_lo[a] - clusters_lo[b]) <= tol) matches++;
         if(matches >= 2)
           {
            eq_lo = clusters_lo[a];
            lo_note = "Equal lows ~ " + DoubleToString(eq_lo, _Digits) + " (" + IntegerToString(matches) + ")";
            break;
           }
        }
     }

   ENUM_SMC_SWEEP_CLASS ClassifySweep(const bool swept, const bool closed_back,
                                      const bool strong_disp, const bool mss_flag,
                                      const bool sustained_beyond)
     {
      if(!swept) return SMC_SWEEP_NONE;
      if(sustained_beyond && !closed_back)
         return SMC_SWEEP_TRUE_BREAKOUT;
      if(!closed_back)
         return SMC_SWEEP_NO_CONFIRM;
      if(mss_flag && strong_disp) return SMC_SWEEP_WITH_MSS;
      if(strong_disp) return SMC_SWEEP_WITH_DISP;
      if(closed_back && strong_disp) return SMC_SWEEP_STRONG;
      if(closed_back) return SMC_SWEEP_VALID;
      return SMC_SWEEP_WEAK;
     }

public:
   CVantageGoldSMCLiquidity(void) : m_symbol(""), m_h_atr_h1(INVALID_HANDLE)
     {
      ZeroMemory(m_cfg);
     }

   bool Init(const string symbol, const VantageGoldSMCConfig &cfg)
     {
      Release();
      m_symbol = symbol;
      m_cfg = cfg;
      if(m_cfg.equal_tol_atr <= 0.0) m_cfg.equal_tol_atr = 0.08;
      if(m_cfg.approach_atr <= 0.0) m_cfg.approach_atr = 0.35;
      if(m_cfg.atr_period <= 0) m_cfg.atr_period = 14;
      // Default Gold session windows (UTC)
      if(m_cfg.asian_end_hour_utc <= 0 && m_cfg.asian_start_hour_utc == 0)
        { m_cfg.asian_start_hour_utc = 0; m_cfg.asian_end_hour_utc = 7; }
      if(m_cfg.london_end_hour_utc <= 0)
        { m_cfg.london_start_hour_utc = 7; m_cfg.london_end_hour_utc = 16; }
      if(m_cfg.ny_end_hour_utc <= 0)
        { m_cfg.ny_start_hour_utc = 12; m_cfg.ny_end_hour_utc = 21; }

      m_h_atr_h1 = iATR(m_symbol, m_cfg.tf_bias, m_cfg.atr_period);
      return (m_h_atr_h1 != INVALID_HANDLE);
     }

   void Release(void)
     {
      Rel(m_h_atr_h1);
     }

   bool Analyze(VantageGoldSMCResult &r)
     {
      double atr = GetAtrH1();
      if(atr <= 0.0)
        {
         // fallback from H1 ranges
         MqlRates tmp[];
         if(CopyRates(m_symbol, m_cfg.tf_bias, 1, 14, tmp) >= 5)
           {
            ArraySetAsSeries(tmp, true);
            double s = 0;
            for(int i = 0; i < 14 && i < ArraySize(tmp); i++)
               s += (tmp[i].high - tmp[i].low);
            atr = s / 14.0;
           }
        }
      if(atr <= 0.0) return false;

      MqlRates d1[];
      int nd1 = CopyRates(m_symbol, PERIOD_D1, 1, 10, d1);
      if(nd1 < 3) return false;
      ArraySetAsSeries(d1, true);

      // Previous day / current day (closed D1[0]=last completed day typically with shift 1)
      // CopyRates start 1: d1[0] = most recently closed daily bar
      r.pdh = d1[0].high;
      r.pdl = d1[0].low;
      r.pd_mid = 0.5 * (r.pdh + r.pdl);

      // Current day from M15 forming session — use today's M15 including incomplete via shift 0 carefully:
      // Prefer closed M15 only for highs/lows of "current day so far"
      MqlRates m15[];
      int nm15 = CopyRates(m_symbol, PERIOD_M15, 1, 200, m15);
      if(nm15 < 20) return false;
      ArraySetAsSeries(m15, true);
      datetime now_bar = m15[0].time;
      r.session_name = CurrentSessionName(now_bar);

      r.cdh = m15[0].high;
      r.cdl = m15[0].low;
      bool have_today = false;
      for(int i = 0; i < nm15; i++)
        {
         if(!SameUtcDay(m15[i].time, now_bar))
            break;
         if(!have_today)
           {
            r.cdh = m15[i].high;
            r.cdl = m15[i].low;
            have_today = true;
           }
         else
           {
            if(m15[i].high > r.cdh) r.cdh = m15[i].high;
            if(m15[i].low < r.cdl) r.cdl = m15[i].low;
           }
        }

      // Previous week from D1
      r.pwh = 0; r.pwl = 0;
      int cur_wk = IsoWeekKey(now_bar);
      int target_wk = -1;
      for(int i = 0; i < nd1; i++)
        {
         int wk = IsoWeekKey(d1[i].time);
         if(wk == cur_wk) continue;
         target_wk = wk;
         break;
        }
      if(target_wk > 0)
        {
         bool first = true;
         for(int i = 0; i < nd1; i++)
           {
            if(IsoWeekKey(d1[i].time) != target_wk) continue;
            if(first) { r.pwh = d1[i].high; r.pwl = d1[i].low; first = false; }
            else
              {
               if(d1[i].high > r.pwh) r.pwh = d1[i].high;
               if(d1[i].low < r.pwl) r.pwl = d1[i].low;
              }
           }
        }
      if(r.pwh > r.pwl) r.pw_mid = 0.5 * (r.pwh + r.pwl);

      bool fA = false, fL = false, fN = false;
      if(m_cfg.show_session_liquidity)
        {
         RangeOfSessionToday(m15, nm15, now_bar,
                             m_cfg.asian_start_hour_utc, m_cfg.asian_end_hour_utc,
                             r.asian_high, r.asian_low, fA);
         RangeOfSessionToday(m15, nm15, now_bar,
                             m_cfg.london_start_hour_utc, m_cfg.london_end_hour_utc,
                             r.london_high, r.london_low, fL);
         RangeOfSessionToday(m15, nm15, now_bar,
                             m_cfg.ny_start_hour_utc, m_cfg.ny_end_hour_utc,
                             r.ny_high, r.ny_low, fN);
        }

      double eq_hi = 0, eq_lo = 0;
      DetectEqualLevels(m15, nm15, m_cfg.equal_tol_atr * atr, eq_hi, eq_lo,
                        r.equal_highs_note, r.equal_lows_note);

      // Build pool list
      VantageGoldSMCLiqPool pools[];
      int pc = 0;
      ArrayResize(pools, 0);
      if(m_cfg.show_prev_day_liquidity)
        {
         AddPool(pools, pc, "BSL", "PDH", r.pdh, 90);
         AddPool(pools, pc, "SSL", "PDL", r.pdl, 90);
        }
      if(m_cfg.show_prev_week_liquidity && r.pwh > r.pwl)
        {
         AddPool(pools, pc, "BSL", "PWH", r.pwh, 85);
         AddPool(pools, pc, "SSL", "PWL", r.pwl, 85);
        }
      AddPool(pools, pc, "BSL", "CDH", r.cdh, 60);
      AddPool(pools, pc, "SSL", "CDL", r.cdl, 60);
      if(fA)
        {
         AddPool(pools, pc, "BSL", "Asian High", r.asian_high, 75);
         AddPool(pools, pc, "SSL", "Asian Low", r.asian_low, 75);
        }
      if(fL)
        {
         AddPool(pools, pc, "BSL", "London High", r.london_high, 70);
         AddPool(pools, pc, "SSL", "London Low", r.london_low, 70);
        }
      if(fN)
        {
         AddPool(pools, pc, "BSL", "NY High", r.ny_high, 70);
         AddPool(pools, pc, "SSL", "NY Low", r.ny_low, 70);
        }
      if(eq_hi > 0) AddPool(pools, pc, "BSL", "Equal Highs", eq_hi, 80);
      if(eq_lo > 0) AddPool(pools, pc, "SSL", "Equal Lows", eq_lo, 80);
      if(r.external_range_high > 0) AddPool(pools, pc, "BSL", "Ext Range High", r.external_range_high, 65);
      if(r.external_range_low > 0) AddPool(pools, pc, "SSL", "Ext Range Low", r.external_range_low, 65);

      double close_px = m15[0].close;
      double nearest_bsl = 0, nearest_ssl = 0;
      string bsl_lab = "", ssl_lab = "";
      double best_bsl_dist = 1e100, best_ssl_dist = 1e100;

      for(int i = 0; i < pc; i++)
        {
         double dist = pools[i].price - close_px;
         if(pools[i].kind == "BSL" && dist > 0)
           {
            if(dist < best_bsl_dist)
              {
               best_bsl_dist = dist;
               nearest_bsl = pools[i].price;
               bsl_lab = pools[i].source;
              }
            if(dist <= m_cfg.approach_atr * atr)
               pools[i].status = SMC_LIQ_APPROACHING;
           }
         if(pools[i].kind == "SSL" && dist < 0)
           {
            double ad = -dist;
            if(ad < best_ssl_dist)
              {
               best_ssl_dist = ad;
               nearest_ssl = pools[i].price;
               ssl_lab = pools[i].source;
              }
            if(ad <= m_cfg.approach_atr * atr)
               pools[i].status = SMC_LIQ_APPROACHING;
           }
        }

      r.nearest_bsl = nearest_bsl;
      r.nearest_ssl = nearest_ssl;
      r.nearest_bsl_label = bsl_lab;
      r.nearest_ssl_label = ssl_lab;
      r.distance_bsl_atr = (nearest_bsl > 0 && atr > 0) ? (nearest_bsl - close_px) / atr : 0;
      r.distance_ssl_atr = (nearest_ssl > 0 && atr > 0) ? (close_px - nearest_ssl) / atr : 0;

      // Liquidity draw: toward nearer unfilled pool by ATR distance, bias-aware
      if(nearest_bsl > 0 && nearest_ssl > 0)
        {
         if(r.distance_bsl_atr < r.distance_ssl_atr)
           {
            r.liquidity_draw = "Buy-Side";
            r.draw_distance_atr = r.distance_bsl_atr;
           }
         else
           {
            r.liquidity_draw = "Sell-Side";
            r.draw_distance_atr = r.distance_ssl_atr;
           }
        }
      else if(nearest_bsl > 0)
        { r.liquidity_draw = "Buy-Side"; r.draw_distance_atr = r.distance_bsl_atr; }
      else if(nearest_ssl > 0)
        { r.liquidity_draw = "Sell-Side"; r.draw_distance_atr = r.distance_ssl_atr; }
      else
        { r.liquidity_draw = "None"; r.draw_distance_atr = 0; }

      // Prefer HTF bias for draw when distances similar
      if(nearest_bsl > 0 && nearest_ssl > 0 &&
         MathAbs(r.distance_bsl_atr - r.distance_ssl_atr) < 0.25)
        {
         if(r.h1_bias == SMC_DIR_BEARISH) { r.liquidity_draw = "Sell-Side"; r.draw_distance_atr = r.distance_ssl_atr; }
         if(r.h1_bias == SMC_DIR_BULLISH) { r.liquidity_draw = "Buy-Side"; r.draw_distance_atr = r.distance_bsl_atr; }
        }

      // Sweep detection on last closed M15 vs key levels (PDH/PDL/Asian/EQ)
      MqlRates bar = m15[0];
      double body = MathAbs(bar.close - bar.open);
      bool strong_disp = (atr > 0 && body >= m_cfg.min_displacement_atr * atr);
      bool mss_bull = (StringFind(r.latest_structure_event, "MSS Bullish") >= 0);
      bool mss_bear = (StringFind(r.latest_structure_event, "MSS Bearish") >= 0);

      ENUM_SMC_SWEEP_CLASS sw = SMC_SWEEP_NONE;
      string sw_evt = "";

      // Sell-side sweep (raid lows) — bullish context candidate
      double ssl_lvl = (r.pdl > 0 ? r.pdl : nearest_ssl);
      if(fA && r.asian_low > 0) ssl_lvl = r.asian_low; // prefer Asian low raid often on Gold
      if(r.pdl > 0) ssl_lvl = r.pdl;
      if(ssl_lvl > 0)
        {
         bool swept = (bar.low < ssl_lvl);
         bool closed_back = (bar.close > ssl_lvl);
         bool sustained = (bar.close < ssl_lvl - 0.1 * atr);
         ENUM_SMC_SWEEP_CLASS c = ClassifySweep(swept, closed_back, strong_disp, mss_bull, sustained);
         if(c != SMC_SWEEP_NONE)
           {
            sw = c;
            sw_evt = "Sell-Side swept (" + DoubleToString(ssl_lvl, _Digits) + ")";
           }
        }
      // Buy-side sweep (raid highs)
      double bsl_lvl = (r.pdh > 0 ? r.pdh : nearest_bsl);
      if(fA && r.asian_high > 0) bsl_lvl = r.asian_high;
      if(r.pdh > 0) bsl_lvl = r.pdh;
      if(bsl_lvl > 0)
        {
         bool swept = (bar.high > bsl_lvl);
         bool closed_back = (bar.close < bsl_lvl);
         bool sustained = (bar.close > bsl_lvl + 0.1 * atr);
         ENUM_SMC_SWEEP_CLASS c = ClassifySweep(swept, closed_back, strong_disp, mss_bear, sustained);
         // Prefer the more recent meaningful sweep; if both, pick stronger class
         if(c != SMC_SWEEP_NONE && (int)c >= (int)sw)
           {
            sw = c;
            sw_evt = "Buy-Side swept (" + DoubleToString(bsl_lvl, _Digits) + ")";
           }
        }

      r.sweep_class = SmcSweepClassToString(sw);
      if(sw_evt != "")
         r.latest_liquidity_event = sw_evt + " — " + r.sweep_class;
      else
         r.latest_liquidity_event = "No confirmed liquidity sweep on last M15";

      // Mark PDH/PDL status lightly
      if(r.cdh > r.pdh && r.pdh > 0)
         r.latest_liquidity_event = "PDH taken / trading above previous day high; " + r.latest_liquidity_event;
      if(r.cdl < r.pdl && r.pdl > 0)
         r.latest_liquidity_event = "PDL taken / trading below previous day low; " + r.latest_liquidity_event;

      r.engine_phase = 3;
      r.setup_phase = SmcPhaseToString(SMC_PHASE_LIQUIDITY_MAPPED);
      r.status_line = "ACTIVE – GOLD ONLY (Phase 3 liquidity)";

      // Enrich narrative
      string narr = r.technical_narrative;
      if(narr != "") narr += " ";
      narr += "Session: " + r.session_name + ".";
      narr += " Nearest BSL: " + (bsl_lab != "" ? bsl_lab + " " : "") +
              (nearest_bsl > 0 ? DoubleToString(nearest_bsl, _Digits) : "n/a") +
              " (" + DoubleToString(r.distance_bsl_atr, 2) + " ATR).";
      narr += " Nearest SSL: " + (ssl_lab != "" ? ssl_lab + " " : "") +
              (nearest_ssl > 0 ? DoubleToString(nearest_ssl, _Digits) : "n/a") +
              " (" + DoubleToString(r.distance_ssl_atr, 2) + " ATR).";
      narr += " Liquidity draw: " + r.liquidity_draw + ".";
      if(sw != SMC_SWEEP_NONE)
         narr += " " + r.latest_liquidity_event + ".";
      narr += " A liquidity sweep is not automatically a reversal. FVG/OB engines land in Phase 4.";
      r.technical_narrative = narr;

      r.reasons_for += "Liquidity map PDH/PDL/session/EQ;";
      if(sw == SMC_SWEEP_VALID || sw == SMC_SWEEP_STRONG || sw == SMC_SWEEP_WITH_DISP || sw == SMC_SWEEP_WITH_MSS)
         r.reasons_for += "Contextual liquidity sweep;";
      r.reasons_against += "No FVG/OB confluence yet;";
      if(sw == SMC_SWEEP_TRUE_BREAKOUT)
         r.reasons_against += "Move looks like breakout not sweep;";
      if(sw == SMC_SWEEP_NO_CONFIRM)
         r.reasons_against += "Sweep lacks close-back confirmation;";

      r.recommendation = "WAIT — track liquidity draw (" + r.liquidity_draw +
                         "). Full SMC setup still requires POI + confirmation (Phase 4–6).";
      r.setup_type = "No Valid SMC Setup";

      Print("[GoldSMC][LIQUIDITY] draw=", r.liquidity_draw,
            " BSL=", DoubleToString(nearest_bsl, _Digits),
            " SSL=", DoubleToString(nearest_ssl, _Digits),
            " sweep=", r.sweep_class,
            " session=", r.session_name);
      return true;
     }
  };

#endif
//+------------------------------------------------------------------+
