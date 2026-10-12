//+------------------------------------------------------------------+
//| VantageGoldSMCContext.mqh                                        |
//| Phase 5 — Dealing range, premium/discount, OTE, inducement, PO3  |
//| Closed bars only — advisory                                      |
//+------------------------------------------------------------------+
#ifndef VANTAGE_GOLD_SMC_CONTEXT_MQH
#define VANTAGE_GOLD_SMC_CONTEXT_MQH

#include "VantageGoldSMCTypes.mqh"

class CVantageGoldSMCContext
  {
private:
   string               m_symbol;
   VantageGoldSMCConfig m_cfg;

   double Clamp(const double v, const double lo, const double hi)
     {
      if(v < lo) return lo;
      if(v > hi) return hi;
      return v;
     }

   bool Overlap(const double a0, const double a1, const double b0, const double b1)
     {
      double alo = MathMin(a0, a1);
      double ahi = MathMax(a0, a1);
      double blo = MathMin(b0, b1);
      double bhi = MathMax(b0, b1);
      return (alo <= bhi && ahi >= blo);
     }

   datetime ToUtcApprox(const datetime server_t)
     {
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
      return (hour >= start_h || hour < end_h);
     }

   void MapPremiumDiscount(VantageGoldSMCResult &r, const double price)
     {
      r.dealing_high = r.external_range_high;
      r.dealing_low = r.external_range_low;
      r.dealing_eq = r.external_equilibrium;
      r.dealing_pct = 50.0;
      r.in_discount = false;
      r.in_premium = false;
      r.premium_discount = "No dealing range";

      if(r.dealing_high <= r.dealing_low)
         return;

      double span = r.dealing_high - r.dealing_low;
      double pct = Clamp((price - r.dealing_low) / span, 0.0, 1.0);
      r.dealing_pct = pct * 100.0;

      double deep_d = Clamp(m_cfg.deep_discount_pct, 0.05, 0.45);
      double deep_p = Clamp(m_cfg.deep_premium_pct, 0.55, 0.95);
      if(deep_p <= deep_d + 0.1)
        {
         deep_d = 0.15;
         deep_p = 0.85;
        }

      if(pct <= deep_d)
        {
         r.premium_discount = "Deep Discount";
         r.in_discount = true;
        }
      else if(pct < 0.45)
        {
         r.premium_discount = "Discount";
         r.in_discount = true;
        }
      else if(pct <= 0.55)
        {
         r.premium_discount = "Equilibrium";
        }
      else if(pct < deep_p)
        {
         r.premium_discount = "Premium";
         r.in_premium = true;
        }
      else
        {
         r.premium_discount = "Deep Premium";
         r.in_premium = true;
        }
     }

   void MapOte(VantageGoldSMCResult &r, const double price)
     {
      r.ote_enabled_hit = false;
      r.ote_low = 0; r.ote_mid = 0; r.ote_high = 0;
      r.price_in_ote = false;
      r.poi_overlaps_ote = false;

      if(!m_cfg.enable_ote || r.dealing_high <= r.dealing_low)
         return;

      double lo_pct = Clamp(m_cfg.ote_low_pct, 0.50, 0.75);
      double mid_pct = Clamp(m_cfg.ote_mid_pct, lo_pct, 0.80);
      double hi_pct = Clamp(m_cfg.ote_high_pct, mid_pct, 0.90);
      double span = r.dealing_high - r.dealing_low;

      // OTE measured from the swing that defines the dealing range:
      // bullish bias → discount OTE (retracement from high toward low)
      // bearish bias → premium OTE (retracement from low toward high)
      ENUM_SMC_DIRECTION bias = r.h1_bias;
      if(bias == SMC_DIR_NEUTRAL || bias == SMC_DIR_CONFLICTING)
         bias = r.h4_bias;

      if(bias == SMC_DIR_BULLISH)
        {
         r.ote_high = r.dealing_high - span * lo_pct;
         r.ote_mid  = r.dealing_high - span * mid_pct;
         r.ote_low  = r.dealing_high - span * hi_pct;
        }
      else if(bias == SMC_DIR_BEARISH)
        {
         r.ote_low  = r.dealing_low + span * lo_pct;
         r.ote_mid  = r.dealing_low + span * mid_pct;
         r.ote_high = r.dealing_low + span * hi_pct;
        }
      else
        {
         // Neutral: show both sides as centered band around EQ using mid fib
         r.ote_low  = r.dealing_eq - span * (mid_pct - 0.5);
         r.ote_high = r.dealing_eq + span * (mid_pct - 0.5);
         r.ote_mid  = r.dealing_eq;
        }

      if(r.ote_high < r.ote_low)
        {
         double tmp = r.ote_high;
         r.ote_high = r.ote_low;
         r.ote_low = tmp;
        }

      r.ote_enabled_hit = true;
      r.price_in_ote = (price >= r.ote_low && price <= r.ote_high);

      if(r.poi_upper > r.poi_lower)
         r.poi_overlaps_ote = Overlap(r.poi_lower, r.poi_upper, r.ote_low, r.ote_high);
     }

   void MapInducement(VantageGoldSMCResult &r)
     {
      r.inducement_status = SmcInducementToString(SMC_IND_NONE);
      if(!m_cfg.enable_inducement)
         return;

      ENUM_SMC_INDUCEMENT st = SMC_IND_NONE;
      string sweep = r.sweep_class;
      string draw = r.liquidity_draw;
      bool swept = (StringFind(r.latest_liquidity_event, "swept") >= 0 ||
                    StringFind(r.latest_liquidity_event, "Swept") >= 0 ||
                    StringFind(sweep, "sweep") >= 0 ||
                    StringFind(sweep, "Sweep") >= 0);
      bool weak = (StringFind(sweep, "Weak") >= 0 || StringFind(sweep, "no confirm") >= 0 ||
                   StringFind(sweep, "No confirm") >= 0);
      bool strong = (StringFind(sweep, "Strong") >= 0 || StringFind(sweep, "displacement") >= 0 ||
                     StringFind(sweep, "MSS") >= 0);

      // Inducement heuristic: internal liquidity raid opposite the HTF draw,
      // before/near a POI, without confirmed continuation breakout.
      if(swept && r.primary_poi_type != "" && r.primary_poi_type != "None")
        {
         if(strong && StringFind(sweep, "true breakout") < 0 &&
            StringFind(sweep, "True breakout") < 0)
            st = SMC_IND_CONFIRMED_SWEEP;
         else if(weak)
            st = SMC_IND_POSSIBLE;
         else
            st = SMC_IND_UNRESOLVED;
        }
      else if(swept && (draw == "Buy-Side" || draw == "Sell-Side"))
        {
         st = SMC_IND_POSSIBLE;
        }
      else if(StringFind(r.m5_context, "correction") >= 0 ||
              StringFind(r.m5_context, "retracement") >= 0)
        {
         st = SMC_IND_POSSIBLE;
        }

      if(StringFind(sweep, "true breakout") >= 0 || StringFind(sweep, "True breakout") >= 0)
         st = SMC_IND_INVALID;

      r.inducement_status = SmcInducementToString(st);
     }

   void MapPo3(VantageGoldSMCResult &r, const double price)
     {
      r.po3_status = SmcPo3ToString(SMC_PO3_NONE);
      r.po3_bias = "None";
      if(!m_cfg.enable_po3)
         return;

      if(r.asian_high <= r.asian_low)
        {
         r.po3_status = SmcPo3ToString(SMC_PO3_NONE);
         return;
        }

      datetime now_bar = r.eval_bar_m5;
      if(now_bar <= 0)
         now_bar = TimeCurrent();
      int hour = HourUtc(now_bar);
      bool asian = InHourRange(hour, m_cfg.asian_start_hour_utc, m_cfg.asian_end_hour_utc);
      bool london = InHourRange(hour, m_cfg.london_start_hour_utc, m_cfg.london_end_hour_utc);
      bool ny = InHourRange(hour, m_cfg.ny_start_hour_utc, m_cfg.ny_end_hour_utc);
      bool active_session = (london || ny);

      double asian_mid = 0.5 * (r.asian_high + r.asian_low);
      double asian_span = r.asian_high - r.asian_low;
      bool above_asian = (price > r.asian_high);
      bool below_asian = (price < r.asian_low);
      bool inside_asian = (!above_asian && !below_asian);

      bool swept_bsl = (StringFind(r.latest_liquidity_event, "Buy-Side") >= 0 &&
                        (StringFind(r.latest_liquidity_event, "swept") >= 0 ||
                         StringFind(r.latest_liquidity_event, "Swept") >= 0));
      bool swept_ssl = (StringFind(r.latest_liquidity_event, "Sell-Side") >= 0 &&
                        (StringFind(r.latest_liquidity_event, "swept") >= 0 ||
                         StringFind(r.latest_liquidity_event, "Swept") >= 0));
      // Also treat Asian High/Low raid as manipulation candidate
      if(r.nearest_bsl_label == "Asian High" && StringFind(r.sweep_class, "sweep") >= 0)
         swept_bsl = true;
      if(r.nearest_ssl_label == "Asian Low" && StringFind(r.sweep_class, "sweep") >= 0)
         swept_ssl = true;
      if(price > r.asian_high && active_session &&
         (StringFind(r.sweep_class, "sweep") >= 0 || StringFind(r.sweep_class, "Sweep") >= 0))
         swept_bsl = true;
      if(price < r.asian_low && active_session &&
         (StringFind(r.sweep_class, "sweep") >= 0 || StringFind(r.sweep_class, "Sweep") >= 0))
         swept_ssl = true;

      ENUM_SMC_PO3_STATE st = SMC_PO3_NONE;
      string bias = "None";

      if(asian && inside_asian)
        {
         st = SMC_PO3_ACCUMULATION;
        }
      else if(active_session)
        {
         if(swept_bsl && price < asian_mid)
           {
            // Raid highs then reverse lower → bearish PO3
            st = SMC_PO3_MANIPULATION_CONFIRMED;
            bias = "Bearish";
           }
         else if(swept_ssl && price > asian_mid)
           {
            st = SMC_PO3_MANIPULATION_CONFIRMED;
            bias = "Bullish";
           }
         else if(above_asian || below_asian)
           {
            st = SMC_PO3_POSSIBLE_MANIPULATION;
            bias = above_asian ? "Bearish" : "Bullish"; // raid side often opposite continuation
           }
         else if(inside_asian)
           {
            st = SMC_PO3_ACCUMULATION;
           }

         // Distribution: confirmed manipulation + displacement away from asian mid
         if(st == SMC_PO3_MANIPULATION_CONFIRMED)
           {
            bool disp_ok = (StringFind(r.displacement_status, "Strong") >= 0 ||
                            StringFind(r.displacement_status, "Moderate") >= 0 ||
                            StringFind(r.displacement_status, "Exceptional") >= 0);
            double leave = (asian_span > 0.0) ? MathAbs(price - asian_mid) / asian_span : 0.0;
            if(disp_ok && leave >= 0.35)
               st = SMC_PO3_DISTRIBUTION;
            if(disp_ok && leave >= 0.85 &&
               ((bias == "Bullish" && price > r.asian_high) ||
                (bias == "Bearish" && price < r.asian_low)))
               st = SMC_PO3_COMPLETED;
           }

         // Invalidate: true breakout continuation in raid direction without reclaim
         if(StringFind(r.sweep_class, "true breakout") >= 0 ||
            StringFind(r.sweep_class, "True breakout") >= 0)
           {
            if((above_asian && bias != "Bullish") || (below_asian && bias != "Bearish"))
               st = SMC_PO3_INVALIDATED;
           }
        }

      r.po3_status = SmcPo3ToString(st);
      r.po3_bias = bias;
     }

public:
   CVantageGoldSMCContext(void) : m_symbol("")
     {
      ZeroMemory(m_cfg);
     }

   bool Init(const string symbol, const VantageGoldSMCConfig &cfg)
     {
      m_symbol = symbol;
      m_cfg = cfg;
      return true;
     }

   void Release(void)
     {
      m_symbol = "";
     }

   bool Analyze(VantageGoldSMCResult &r)
     {
      double price = SymbolInfoDouble(m_symbol, SYMBOL_BID);
      if(price <= 0.0 && r.poi_mid > 0.0)
         price = r.poi_mid;
      if(price <= 0.0 && r.dealing_eq > 0.0)
         price = r.dealing_eq;
      if(price <= 0.0 && r.external_equilibrium > 0.0)
         price = r.external_equilibrium;

      MapPremiumDiscount(r, price);
      MapOte(r, price);
      MapInducement(r);
      MapPo3(r, price);

      r.engine_phase = 5;
      r.setup_phase = SmcPhaseToString(SMC_PHASE_CONTEXT_MAPPED);
      r.status_line = "ACTIVE – GOLD ONLY (Phase 5 Context)";
      r.setup_type = "No Valid SMC Setup";

      string narr = r.technical_narrative;
      if(narr != "") narr += " ";
      narr += "Dealing range " + DoubleToString(r.dealing_low, _Digits) + "-" +
              DoubleToString(r.dealing_high, _Digits) + " → " + r.premium_discount +
              " (" + DoubleToString(r.dealing_pct, 0) + "%).";
      if(r.ote_enabled_hit)
        {
         narr += " OTE " + DoubleToString(r.ote_low, _Digits) + "-" +
                 DoubleToString(r.ote_high, _Digits);
         if(r.price_in_ote) narr += " (price inside)";
         if(r.poi_overlaps_ote) narr += " (POI overlaps)";
         narr += ".";
        }
      if(r.inducement_status != "" && r.inducement_status != "None")
         narr += " Inducement: " + r.inducement_status + ".";
      if(m_cfg.enable_po3)
         narr += " PO3: " + r.po3_status +
                 (r.po3_bias != "None" ? (" (" + r.po3_bias + ")") : "") + ".";
      narr += " Premium/discount and OTE are confluence filters — not standalone setups (Phase 6 scores).";
      r.technical_narrative = narr;

      if(r.in_discount) r.reasons_for += "Price in discount;";
      if(r.in_premium) r.reasons_for += "Price in premium;";
      if(r.price_in_ote) r.reasons_for += "Price in OTE;";
      if(r.poi_overlaps_ote) r.reasons_for += "POI overlaps OTE;";
      if(StringFind(r.inducement_status, "Confirmed") >= 0)
         r.reasons_for += "Confirmed inducement sweep;";
      if(StringFind(r.po3_status, "Distribution") >= 0 ||
         StringFind(r.po3_status, "Manipulation confirmed") >= 0)
         r.reasons_for += "PO3 context active;";

      if(r.premium_discount == "Equilibrium")
         r.reasons_against += "Equilibrium — wait for clearer PD location;";
      if(r.ote_enabled_hit && !r.price_in_ote && !r.poi_overlaps_ote)
         r.reasons_against += "Outside OTE confluence;";
      r.reasons_against += "Setup score engine not active yet;";

      // Guidance: still WAIT; hint at confluence readiness
      string tip = "";
      if(r.poi_overlaps_ote && (r.in_discount || r.in_premium))
         tip = "POI + OTE + PD confluence forming — wait for Phase 6 score.";
      else if(r.price_in_ote)
         tip = "Price in OTE — monitor POI reaction; no scored setup yet.";
      else if(r.in_discount || r.in_premium)
         tip = "Price in " + r.premium_discount + " — await OTE/POI alignment.";
      else
         tip = "WAIT — map context; no graded SMC setup yet.";

      if(r.primary_poi_type != "" && r.primary_poi_type != "None")
         r.recommendation = "WAIT — " + tip + " Primary POI: " + r.primary_poi_dir + " " +
                            r.primary_poi_type + ".";
      else
         r.recommendation = "WAIT — " + tip;

      Print("[GoldSMC][CONTEXT] pd=", r.premium_discount,
            " pct=", DoubleToString(r.dealing_pct, 0),
            " ote=", (r.price_in_ote ? "in" : "out"),
            " poi_ote=", (r.poi_overlaps_ote ? "yes" : "no"),
            " ind=", r.inducement_status,
            " po3=", r.po3_status, " ", r.po3_bias);
      return true;
     }
  };

#endif
//+------------------------------------------------------------------+
