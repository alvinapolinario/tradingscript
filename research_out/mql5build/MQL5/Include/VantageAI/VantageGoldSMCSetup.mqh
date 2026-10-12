//+------------------------------------------------------------------+
//| VantageGoldSMCSetup.mqh                                          |
//| Phase 6 — Confluence scoring, setup state, targets, narrative    |
//| Advisory-only — never opens, modifies, or closes trades          |
//+------------------------------------------------------------------+
#ifndef VANTAGE_GOLD_SMC_SETUP_MQH
#define VANTAGE_GOLD_SMC_SETUP_MQH

#include "VantageGoldSMCTypes.mqh"

class CVantageGoldSMCSetup
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

   double NormWeight(const double w)
     {
      return (w < 0.0) ? 0.0 : w;
     }

   ENUM_SMC_DIRECTION ResolveBias(const VantageGoldSMCResult &r)
     {
      if(r.h1_bias == SMC_DIR_BULLISH || r.h1_bias == SMC_DIR_BEARISH)
         return r.h1_bias;
      if(r.h4_bias == SMC_DIR_BULLISH || r.h4_bias == SMC_DIR_BEARISH)
         return r.h4_bias;
      if(r.macro_bias == SMC_DIR_BULLISH || r.macro_bias == SMC_DIR_BEARISH)
         return r.macro_bias;
      return SMC_DIR_NEUTRAL;
     }

   bool HasSweep(const VantageGoldSMCResult &r)
     {
      return (StringFind(r.sweep_class, "sweep") >= 0 ||
              StringFind(r.sweep_class, "Sweep") >= 0 ||
              StringFind(r.latest_liquidity_event, "swept") >= 0 ||
              StringFind(r.latest_liquidity_event, "Swept") >= 0);
     }

   bool StrongDisp(const VantageGoldSMCResult &r)
     {
      return (StringFind(r.displacement_status, "Strong") >= 0 ||
              StringFind(r.displacement_status, "Exceptional") >= 0 ||
              StringFind(r.displacement_status, "Moderate") >= 0);
     }

   bool PoiValid(const VantageGoldSMCResult &r)
     {
      return (r.primary_poi_type != "" && r.primary_poi_type != "None" &&
              StringFind(r.primary_poi_status, "Invalid") < 0 &&
              StringFind(r.primary_poi_status, "Fully") < 0);
     }

   bool PoiBull(const VantageGoldSMCResult &r)
     {
      return (r.primary_poi_dir == "Bullish");
     }

   bool PoiBear(const VantageGoldSMCResult &r)
     {
      return (r.primary_poi_dir == "Bearish");
     }

   //--- component scores 0..1 -------------------------------------------------
   double ScoreHtf(const VantageGoldSMCResult &r, const ENUM_SMC_DIRECTION dir, string &note)
     {
      if(r.h4_bias == SMC_DIR_CONFLICTING ||
         (r.h4_bias != SMC_DIR_NEUTRAL && r.h1_bias != SMC_DIR_NEUTRAL && r.h4_bias != r.h1_bias))
        {
         note = "H4/H1 conflict";
         return 0.25;
        }
      if(dir == SMC_DIR_NEUTRAL)
        {
         note = "No clear HTF bias";
         return 0.20;
        }
      if(r.h4_bias == dir && r.h1_bias == dir)
        {
         note = "H4+H1 aligned";
         return 1.0;
        }
      if(r.h1_bias == dir)
        {
         note = "H1 aligned";
         return 0.75;
        }
      if(r.h4_bias == dir)
        {
         note = "H4 aligned";
         return 0.65;
        }
      note = "Countertrend vs HTF";
      return 0.15;
     }

   double ScoreLiq(const VantageGoldSMCResult &r, const ENUM_SMC_DIRECTION dir, string &note)
     {
      bool swept = HasSweep(r);
      bool strong = (StringFind(r.sweep_class, "Strong") >= 0 ||
                     StringFind(r.sweep_class, "MSS") >= 0 ||
                     StringFind(r.sweep_class, "displacement") >= 0);
      bool weak = (StringFind(r.sweep_class, "Weak") >= 0 ||
                   StringFind(r.sweep_class, "No confirm") >= 0 ||
                   StringFind(r.sweep_class, "no confirm") >= 0);
      bool breakout = (StringFind(r.sweep_class, "true breakout") >= 0 ||
                       StringFind(r.sweep_class, "True breakout") >= 0);
      if(breakout)
        {
         note = "True breakout (not reversal)";
         return 0.20;
        }
      if(swept && strong)
        {
         note = "Strong liquidity sweep";
         return 1.0;
        }
      if(swept && !weak)
        {
         note = "Valid liquidity sweep";
         return 0.80;
        }
      if(swept && weak)
        {
         note = "Weak / unconfirmed sweep";
         return 0.40;
        }
      if(r.distance_bsl_atr > 0 && r.distance_bsl_atr <= m_cfg.approach_atr)
        {
         note = "BSL approaching";
         return 0.45;
        }
      if(r.distance_ssl_atr > 0 && r.distance_ssl_atr <= m_cfg.approach_atr)
        {
         note = "SSL approaching";
         return 0.45;
        }
      if(r.liquidity_draw != "")
        {
         note = "Liquidity draw mapped";
         return 0.35;
        }
      note = "No liquidity event";
      return 0.10;
     }

   double ScoreDisp(const VantageGoldSMCResult &r, string &note)
     {
      if(StringFind(r.displacement_status, "Exceptional") >= 0)
        { note = "Exceptional displacement"; return 1.0; }
      if(StringFind(r.displacement_status, "Strong") >= 0)
        { note = "Strong displacement"; return 0.90; }
      if(StringFind(r.displacement_status, "Moderate") >= 0)
        { note = "Moderate displacement"; return 0.65; }
      if(StringFind(r.displacement_status, "Weak") >= 0)
        { note = "Weak displacement"; return 0.35; }
      note = "No displacement";
      return 0.10;
     }

   double ScoreStruct(const VantageGoldSMCResult &r, const ENUM_SMC_DIRECTION dir, string &note)
     {
      string ev = r.latest_structure_event;
      bool mss = (StringFind(ev, "MSS") >= 0);
      bool choch = (StringFind(ev, "CHoCH") >= 0);
      bool bos = (StringFind(ev, "BOS") >= 0);
      bool bull_ev = (StringFind(ev, "Bull") >= 0);
      bool bear_ev = (StringFind(ev, "Bear") >= 0);
      bool align = ((dir == SMC_DIR_BULLISH && bull_ev) || (dir == SMC_DIR_BEARISH && bear_ev));
      bool against = ((dir == SMC_DIR_BULLISH && bear_ev) || (dir == SMC_DIR_BEARISH && bull_ev));

      if(StringFind(ev, "Wick") >= 0)
        { note = "Wick-only — not BOS"; return 0.20; }
      if(mss && align)
        { note = "MSS with bias"; return 1.0; }
      if(bos && align && StringFind(ev, "External") >= 0)
        { note = "External BOS with bias"; return 0.90; }
      if(bos && align)
        { note = "BOS with bias"; return 0.80; }
      if(choch && align)
        { note = "CHoCH early warning"; return 0.55; }
      if(choch && against)
        { note = "CHoCH against bias"; return 0.30; }
      if(StringFind(r.m5_context, "does not override") >= 0)
        { note = "LTF correction only"; return 0.45; }
      if(dir != SMC_DIR_NEUTRAL)
        { note = "HTF structure present"; return 0.50; }
      note = "No structure confirmation";
      return 0.15;
     }

   double ScoreOb(const VantageGoldSMCResult &r, const ENUM_SMC_DIRECTION dir, string &note)
     {
      if(!r.has_valid_ob && !r.has_breaker)
        { note = "No valid OB"; return 0.05; }
      bool dir_ok = ((dir == SMC_DIR_BULLISH && PoiBull(r)) ||
                     (dir == SMC_DIR_BEARISH && PoiBear(r)) ||
                     dir == SMC_DIR_NEUTRAL);
      double q = Clamp(r.poi_quality / 100.0, 0.0, 1.0);
      double mit = Clamp(r.poi_mitigation_pct / 100.0, 0.0, 1.0);
      double base = r.has_breaker ? 0.85 : 0.75;
      if(StringFind(r.primary_poi_type, "Order Block") < 0 &&
         StringFind(r.primary_poi_type, "Breaker") < 0 &&
         StringFind(r.primary_poi_type, "Mitigation") < 0)
        {
         if(r.has_valid_ob) { note = "OB present (not primary)"; return 0.45 * q; }
         note = "No OB primary";
         return 0.10;
        }
      if(!dir_ok) { note = "OB against bias"; return 0.25 * q; }
      if(mit >= 0.85) { note = "OB heavily mitigated"; return 0.20; }
      note = r.has_breaker ? "Breaker aligned" : "Valid OB";
      return Clamp(base * (0.5 + 0.5 * q) * (1.0 - 0.5 * mit), 0.0, 1.0);
     }

   double ScoreFvg(const VantageGoldSMCResult &r, const ENUM_SMC_DIRECTION dir, string &note)
     {
      if(!r.has_fresh_fvg && !r.has_inverse_fvg)
        { note = "No fresh FVG"; return 0.05; }
      bool primary_fvg = (StringFind(r.primary_poi_type, "FVG") >= 0 ||
                          StringFind(r.primary_poi_type, "Fair Value") >= 0);
      bool dir_ok = ((dir == SMC_DIR_BULLISH && PoiBull(r)) ||
                     (dir == SMC_DIR_BEARISH && PoiBear(r)) ||
                     dir == SMC_DIR_NEUTRAL);
      double q = Clamp(r.poi_quality / 100.0, 0.0, 1.0);
      if(r.has_inverse_fvg && primary_fvg)
        { note = "Inverse FVG"; return dir_ok ? 0.85 * q : 0.30; }
      if(primary_fvg && dir_ok)
        { note = "Aligned FVG"; return Clamp(0.70 + 0.30 * q, 0, 1); }
      if(r.has_fresh_fvg)
        { note = "Fresh FVG present"; return 0.50; }
      note = "FVG weak";
      return 0.20;
     }

   double ScorePd(const VantageGoldSMCResult &r, const ENUM_SMC_DIRECTION dir, string &note)
     {
      if(dir == SMC_DIR_BULLISH)
        {
         if(r.premium_discount == "Deep Discount") { note = "Deep discount"; return 1.0; }
         if(r.premium_discount == "Discount") { note = "Discount"; return 0.85; }
         if(r.premium_discount == "Equilibrium") { note = "Equilibrium"; return 0.40; }
         if(r.in_premium) { note = "Bullish in premium"; return 0.20; }
        }
      else if(dir == SMC_DIR_BEARISH)
        {
         if(r.premium_discount == "Deep Premium") { note = "Deep premium"; return 1.0; }
         if(r.premium_discount == "Premium") { note = "Premium"; return 0.85; }
         if(r.premium_discount == "Equilibrium") { note = "Equilibrium"; return 0.40; }
         if(r.in_discount) { note = "Bearish in discount"; return 0.20; }
        }
      note = "PD neutral";
      return 0.35;
     }

   double ScoreSession(const VantageGoldSMCResult &r, string &note)
     {
      string s = r.session_name;
      if(StringFind(s, "Overlap") >= 0) { note = "London–NY overlap"; return 1.0; }
      if(StringFind(s, "London") >= 0) { note = "London session"; return 0.85; }
      if(StringFind(s, "New York") >= 0) { note = "New York session"; return 0.80; }
      if(StringFind(s, "Asian") >= 0) { note = "Asian session"; return 0.45; }
      note = "Off-session";
      return 0.25;
     }

   double ScorePdWeek(const VantageGoldSMCResult &r, const ENUM_SMC_DIRECTION dir, string &note)
     {
      bool near_pd = (StringFind(r.nearest_bsl_label, "PDH") >= 0 ||
                      StringFind(r.nearest_ssl_label, "PDL") >= 0 ||
                      StringFind(r.latest_liquidity_event, "PDH") >= 0 ||
                      StringFind(r.latest_liquidity_event, "PDL") >= 0);
      bool near_pw = (StringFind(r.nearest_bsl_label, "PWH") >= 0 ||
                      StringFind(r.nearest_ssl_label, "PWL") >= 0);
      bool asian = (StringFind(r.nearest_bsl_label, "Asian") >= 0 ||
                    StringFind(r.nearest_ssl_label, "Asian") >= 0);
      if(HasSweep(r) && near_pd) { note = "PDH/PDL sweep confluence"; return 1.0; }
      if(near_pd) { note = "Near previous-day level"; return 0.70; }
      if(near_pw) { note = "Near previous-week level"; return 0.60; }
      if(asian) { note = "Near Asian range"; return 0.55; }
      note = "No PD/PW confluence";
      return 0.20;
     }

   double ScoreOte(const VantageGoldSMCResult &r, string &note)
     {
      if(!r.ote_enabled_hit) { note = "OTE off"; return 0.30; }
      if(r.poi_overlaps_ote && r.price_in_ote) { note = "Price+POI in OTE"; return 1.0; }
      if(r.poi_overlaps_ote) { note = "POI overlaps OTE"; return 0.85; }
      if(r.price_in_ote) { note = "Price in OTE"; return 0.70; }
      note = "Outside OTE";
      return 0.15;
     }

   double ScoreLtf(const VantageGoldSMCResult &r, const ENUM_SMC_DIRECTION dir, string &note)
     {
      // M5 should support, not override
      if(StringFind(r.m5_context, "does not override") >= 0)
        {
         // Internal correction into HTF POI is good for continuation
         if(PoiValid(r))
           { note = "LTF retracement into HTF POI"; return 0.80; }
         note = "LTF correction (non-override)";
         return 0.55;
        }
      if(dir == SMC_DIR_BULLISH && r.m5_bias == SMC_DIR_BULLISH && r.m15_bias == SMC_DIR_BULLISH)
        { note = "M15/M5 aligned bullish"; return 0.90; }
      if(dir == SMC_DIR_BEARISH && r.m5_bias == SMC_DIR_BEARISH && r.m15_bias == SMC_DIR_BEARISH)
        { note = "M15/M5 aligned bearish"; return 0.90; }
      if((dir == SMC_DIR_BULLISH && r.m15_bias == SMC_DIR_BULLISH) ||
         (dir == SMC_DIR_BEARISH && r.m15_bias == SMC_DIR_BEARISH))
        { note = "M15 aligned"; return 0.70; }
      if(r.m5_bias != SMC_DIR_NEUTRAL && r.m5_bias != dir && dir != SMC_DIR_NEUTRAL)
        { note = "M5 opposing (not override)"; return 0.35; }
      note = "LTF neutral";
      return 0.40;
     }

   double ScoreVolSpread(string &note)
     {
      double ask = SymbolInfoDouble(m_symbol, SYMBOL_ASK);
      double bid = SymbolInfoDouble(m_symbol, SYMBOL_BID);
      double point = SymbolInfoDouble(m_symbol, SYMBOL_POINT);
      if(ask <= 0 || bid <= 0 || point <= 0)
        { note = "Spread n/a"; return 0.50; }
      double spread_pts = (ask - bid) / point;
      // Gold typical: tens of points depending on digits
      if(spread_pts <= 30) { note = "Tight spread"; return 1.0; }
      if(spread_pts <= 60) { note = "Normal spread"; return 0.75; }
      if(spread_pts <= 120) { note = "Elevated spread"; return 0.40; }
      note = "Wide spread — reduce confidence";
      return 0.15;
     }

   ENUM_SMC_DIRECTION InferSetupDir(const VantageGoldSMCResult &r)
     {
      ENUM_SMC_DIRECTION bias = ResolveBias(r);
      if(PoiBull(r) && (bias != SMC_DIR_BEARISH || r.in_discount))
         return SMC_DIR_BULLISH;
      if(PoiBear(r) && (bias != SMC_DIR_BULLISH || r.in_premium))
         return SMC_DIR_BEARISH;
      if(r.po3_bias == "Bullish") return SMC_DIR_BULLISH;
      if(r.po3_bias == "Bearish") return SMC_DIR_BEARISH;
      if(bias == SMC_DIR_BULLISH && r.in_discount) return SMC_DIR_BULLISH;
      if(bias == SMC_DIR_BEARISH && r.in_premium) return SMC_DIR_BEARISH;
      return bias;
     }

   string ClassifyType(const VantageGoldSMCResult &r, const ENUM_SMC_DIRECTION dir)
     {
      bool swept = HasSweep(r);
      bool pdh = (StringFind(r.latest_liquidity_event, "PDH") >= 0 ||
                  (r.nearest_bsl_label == "PDH" && swept));
      bool pdl = (StringFind(r.latest_liquidity_event, "PDL") >= 0 ||
                  (r.nearest_ssl_label == "PDL" && swept));
      bool asian = (StringFind(r.nearest_bsl_label, "Asian") >= 0 ||
                    StringFind(r.nearest_ssl_label, "Asian") >= 0 ||
                    StringFind(r.latest_liquidity_event, "Asian") >= 0);
      bool ob_fvg = (r.has_valid_ob && r.has_fresh_fvg);
      bool primary_ob = (StringFind(r.primary_poi_type, "Order Block") >= 0 ||
                         StringFind(r.primary_poi_type, "Mitigation") >= 0);
      bool primary_brk = (StringFind(r.primary_poi_type, "Breaker") >= 0);
      bool primary_fvg = (StringFind(r.primary_poi_type, "Fair Value") >= 0);
      bool primary_ifvg = (StringFind(r.primary_poi_type, "Inverse") >= 0);
      bool mss = (StringFind(r.latest_structure_event, "MSS") >= 0);
      bool choch = (StringFind(r.latest_structure_event, "CHoCH") >= 0);
      bool bos = (StringFind(r.latest_structure_event, "BOS") >= 0);
      bool po3 = (StringFind(r.po3_status, "Manipulation") >= 0 ||
                  StringFind(r.po3_status, "Distribution") >= 0 ||
                  StringFind(r.po3_status, "PO3 completed") >= 0);
      bool session_london = (StringFind(r.session_name, "London") >= 0);
      bool session_ny = (StringFind(r.session_name, "New York") >= 0);

      // Priority: specific confluence first
      if(ob_fvg && PoiValid(r)) return "Order Block and FVG Confluence";
      if(r.poi_overlaps_ote && PoiValid(r)) return "OTE Confluence Setup";
      if(po3 && PoiValid(r)) return "Power of Three Setup";
      if(po3) return "Session Manipulation Setup";
      if(pdh && swept) return "Previous-Day High Sweep";
      if(pdl && swept) return "Previous-Day Low Sweep";
      if(asian && swept) return "Asian-Range Sweep";
      if(primary_brk) return "Breaker Block Retest";
      if(primary_ifvg) return "Inverse FVG Retest";
      if(swept && mss) return "MSS Confirmation Setup";
      if(swept && StrongDisp(r) && PoiValid(r))
        {
         // Sweep + POI aligned with bias → continuation; against → reversal watch
         if((dir == SMC_DIR_BULLISH && PoiBull(r)) || (dir == SMC_DIR_BEARISH && PoiBear(r)))
            return "Liquidity Sweep Continuation";
         return "Liquidity Sweep Reversal";
        }
      if(swept && PoiValid(r)) return "Liquidity Sweep Reversal";
      if(mss) return "MSS Confirmation Setup";
      if(choch) return "CHoCH Reversal Watch";
      if(bos && PoiValid(r)) return "BOS Continuation";
      if(primary_ob) return "Order Block Mitigation";
      if(primary_fvg) return "FVG Retracement";
      if(dir == SMC_DIR_BEARISH && r.in_premium) return "Premium Sell Setup";
      if(dir == SMC_DIR_BULLISH && r.in_discount) return "Discount Buy Setup";
      if(session_ny && swept) return "New York Reversal";
      if(session_ny && bos) return "New York Continuation";
      if(session_london && bos) return "London Continuation";
      if(PoiValid(r) || swept || StrongDisp(r)) return "Context Forming Watch";
      return "No Valid SMC Setup";
     }

   ENUM_SMC_SETUP_PHASE ClassifyPhase(const VantageGoldSMCResult &r,
                                      const double score,
                                      const double price,
                                      const bool inside,
                                      const bool approaching)
     {
      if(r.poi_mitigation_pct >= 95.0 && PoiValid(r) == false)
         return SMC_PHASE_SETUP_MISSED;
      if(StringFind(r.primary_poi_status, "Invalid") >= 0)
         return SMC_PHASE_SETUP_INVALIDATED;

      if(score >= 75.0 && inside && StrongDisp(r) && HasSweep(r) && PoiValid(r))
         return SMC_PHASE_SETUP_CONFIRMED;
      if(inside)
         return SMC_PHASE_INSIDE_ENTRY;
      if(approaching && PoiValid(r))
         return SMC_PHASE_RETRACE_IN_PROGRESS;
      if(PoiValid(r) && score >= 50.0)
         return SMC_PHASE_LTF_AWAITED;
      if(PoiValid(r))
         return SMC_PHASE_POI_IDENTIFIED;
      if(HasSweep(r) && !StrongDisp(r))
         return SMC_PHASE_DISP_AWAITED;
      if(HasSweep(r))
         return SMC_PHASE_STRUCT_AWAITED;
      if((r.distance_bsl_atr > 0 && r.distance_bsl_atr <= m_cfg.approach_atr) ||
         (r.distance_ssl_atr > 0 && r.distance_ssl_atr <= m_cfg.approach_atr))
         return SMC_PHASE_LIQ_APPROACHING;
      if(StringFind(r.latest_liquidity_event, "swept") >= 0 ||
         StringFind(r.latest_liquidity_event, "Swept") >= 0)
         return SMC_PHASE_LIQ_SWEPT;
      return SMC_PHASE_CONTEXT_FORMING;
     }

   void BuildEntry(VantageGoldSMCResult &r, const ENUM_SMC_DIRECTION dir, const double price)
     {
      r.entry_low = 0; r.entry_high = 0; r.preferred_entry = 0;
      r.entry_status = "Far";
      r.zone_source = "";

      if(PoiValid(r) && r.poi_upper > r.poi_lower)
        {
         r.entry_low = r.poi_lower;
         r.entry_high = r.poi_upper;
         r.zone_source = r.primary_poi_type;
         if(r.poi_ce > r.poi_lower && r.poi_ce < r.poi_upper)
            r.preferred_entry = r.poi_ce;
         else
            r.preferred_entry = 0.5 * (r.poi_lower + r.poi_upper);

         // Refine with OTE overlap
         if(r.poi_overlaps_ote && r.ote_high > r.ote_low)
           {
            r.entry_low = MathMax(r.entry_low, r.ote_low);
            r.entry_high = MathMin(r.entry_high, r.ote_high);
            if(r.entry_high > r.entry_low)
              {
               r.zone_source += " + OTE";
               r.preferred_entry = Clamp(r.ote_mid, r.entry_low, r.entry_high);
              }
            else
              {
               // restore POI if OTE intersection empty
               r.entry_low = r.poi_lower;
               r.entry_high = r.poi_upper;
              }
           }
        }
      else if(r.price_in_ote && r.ote_high > r.ote_low)
        {
         r.entry_low = r.ote_low;
         r.entry_high = r.ote_high;
         r.preferred_entry = r.ote_mid;
         r.zone_source = "OTE (confluence only — not standalone)";
        }

      if(r.entry_high > r.entry_low)
        {
         r.entry_zone = DoubleToString(r.entry_low, _Digits) + "-" + DoubleToString(r.entry_high, _Digits);
         double mid = 0.5 * (r.entry_low + r.entry_high);
         double half = 0.5 * (r.entry_high - r.entry_low);
         double dist = MathAbs(price - mid);
         double atr_proxy = (r.dealing_high > r.dealing_low)
                            ? (r.dealing_high - r.dealing_low) * 0.08
                            : half * 2.0;
         if(atr_proxy <= 0) atr_proxy = half > 0 ? half : 1.0;

         if(price >= r.entry_low && price <= r.entry_high)
            r.entry_status = "Inside";
         else if(dist <= atr_proxy * MathMax(0.35, m_cfg.approach_atr))
            r.entry_status = "Approaching";
         else if(dir == SMC_DIR_BULLISH && price < r.entry_low - atr_proxy)
            r.entry_status = "Missed";
         else if(dir == SMC_DIR_BEARISH && price > r.entry_high + atr_proxy)
            r.entry_status = "Missed";
         else
            r.entry_status = "Far";

         if(StringFind(r.primary_poi_status, "Invalid") >= 0 ||
            r.poi_mitigation_pct >= 95.0)
            r.entry_status = "Invalidated";
        }
      else
        {
         r.entry_zone = "";
         r.entry_status = "Far";
        }
     }

   void BuildInvalidation(VantageGoldSMCResult &r, const ENUM_SMC_DIRECTION dir)
     {
      r.invalidation_price = 0;
      if(r.entry_high > r.entry_low)
        {
         if(dir == SMC_DIR_BULLISH)
           {
            r.invalidation_price = r.entry_low;
            r.invalidation = "M15 close below " + DoubleToString(r.entry_low, _Digits) +
                             " (entry-zone / POI extreme)";
           }
         else if(dir == SMC_DIR_BEARISH)
           {
            r.invalidation_price = r.entry_high;
            r.invalidation = "M15 close above " + DoubleToString(r.entry_high, _Digits) +
                             " (entry-zone / POI extreme)";
           }
        }
      if(r.invalidation == "" && r.dealing_high > r.dealing_low)
        {
         if(dir == SMC_DIR_BULLISH)
           {
            r.invalidation_price = r.dealing_low;
            r.invalidation = "Close below dealing-range low " + DoubleToString(r.dealing_low, _Digits);
           }
         else if(dir == SMC_DIR_BEARISH)
           {
            r.invalidation_price = r.dealing_high;
            r.invalidation = "Close above dealing-range high " + DoubleToString(r.dealing_high, _Digits);
           }
        }
      if(r.invalidation == "")
         r.invalidation = "No structural invalidation — incomplete setup";
     }

   void BuildTargets(VantageGoldSMCResult &r, const ENUM_SMC_DIRECTION dir)
     {
      r.target_1 = 0; r.target_2 = 0; r.target_3 = 0;
      r.estimated_rr = 0;
      r.targets = "";

      if(dir == SMC_DIR_NEUTRAL)
         return;

      // Collect opposing liquidity
      double t_internal = 0, t_draw = 0, t_external = 0;
      if(dir == SMC_DIR_BULLISH)
        {
         // Upside targets: nearest BSL, PDH, dealing high
         t_internal = (r.nearest_bsl > 0) ? r.nearest_bsl : r.london_high;
         if(t_internal <= 0) t_internal = r.asian_high;
         t_draw = (r.pdh > 0) ? r.pdh : r.nearest_bsl;
         if(StringFind(r.liquidity_draw, "Buy") >= 0 && r.nearest_bsl > 0)
            t_draw = r.nearest_bsl;
         t_external = (r.dealing_high > 0) ? r.dealing_high : r.pwh;
         if(t_external <= 0) t_external = r.ny_high;
        }
      else
        {
         t_internal = (r.nearest_ssl > 0) ? r.nearest_ssl : r.london_low;
         if(t_internal <= 0) t_internal = r.asian_low;
         t_draw = (r.pdl > 0) ? r.pdl : r.nearest_ssl;
         if(StringFind(r.liquidity_draw, "Sell") >= 0 && r.nearest_ssl > 0)
            t_draw = r.nearest_ssl;
         t_external = (r.dealing_low > 0) ? r.dealing_low : r.pwl;
         if(t_external <= 0) t_external = r.ny_low;
        }

      // Order by distance from preferred entry in trade direction
      double entry = (r.preferred_entry > 0) ? r.preferred_entry :
                     (r.entry_low > 0 ? 0.5 * (r.entry_low + r.entry_high) : 0);
      if(entry <= 0) return;

      double cands[3];
      cands[0] = t_internal; cands[1] = t_draw; cands[2] = t_external;
      // Filter invalid / wrong side
      for(int i = 0; i < 3; i++)
        {
         if(cands[i] <= 0) continue;
         if(dir == SMC_DIR_BULLISH && cands[i] <= entry) cands[i] = 0;
         if(dir == SMC_DIR_BEARISH && cands[i] >= entry) cands[i] = 0;
        }
      // Sort by proximity for T1, then farther
      for(int a = 0; a < 2; a++)
         for(int b = a + 1; b < 3; b++)
           {
            double da = (cands[a] > 0) ? MathAbs(cands[a] - entry) : 1e99;
            double db = (cands[b] > 0) ? MathAbs(cands[b] - entry) : 1e99;
            if(db < da)
              {
               double tmp = cands[a]; cands[a] = cands[b]; cands[b] = tmp;
              }
           }
      r.target_1 = cands[0];
      r.target_2 = cands[1];
      r.target_3 = cands[2];
      // Ensure uniqueness / progression
      if(r.target_2 == r.target_1) r.target_2 = cands[2];
      if(r.target_3 == r.target_2 || r.target_3 == r.target_1)
         r.target_3 = (dir == SMC_DIR_BULLISH) ? r.dealing_high : r.dealing_low;

      r.targets = "";
      if(r.target_1 > 0) r.targets += "T1 " + DoubleToString(r.target_1, _Digits);
      if(r.target_2 > 0) r.targets += (r.targets != "" ? " | " : "") + "T2 " + DoubleToString(r.target_2, _Digits);
      if(r.target_3 > 0) r.targets += (r.targets != "" ? " | " : "") + "T3 " + DoubleToString(r.target_3, _Digits);

      if(r.invalidation_price > 0 && r.target_1 > 0)
        {
         double risk = MathAbs(entry - r.invalidation_price);
         double reward = MathAbs(r.target_1 - entry);
         if(risk > 0)
            r.estimated_rr = reward / risk;
         // Cap fantasy RR
         if(r.estimated_rr > 12.0) r.estimated_rr = 12.0;
        }
     }

   ENUM_SMC_SETUP_PHASE RefinePhaseWithTargets(const ENUM_SMC_SETUP_PHASE phase,
                                               const VantageGoldSMCResult &r,
                                               const double price)
     {
      if(phase == SMC_PHASE_SETUP_INVALIDATED || phase == SMC_PHASE_SETUP_MISSED)
         return phase;
      bool bull = (r.setup_direction == "Bullish");
      bool bear = (r.setup_direction == "Bearish");
      if(r.target_3 > 0 && ((bull && price >= r.target_3) || (bear && price <= r.target_3)))
         return SMC_PHASE_SETUP_COMPLETED;
      if(r.target_2 > 0 && ((bull && price >= r.target_2) || (bear && price <= r.target_2)))
         return SMC_PHASE_T2_REACHED;
      if(r.target_1 > 0 && ((bull && price >= r.target_1) || (bear && price <= r.target_1)))
         return SMC_PHASE_T1_REACHED;
      return phase;
     }

public:
   CVantageGoldSMCSetup(void) : m_symbol("")
     {
      ZeroMemory(m_cfg);
     }

   bool Init(const string symbol, const VantageGoldSMCConfig &cfg)
     {
      m_symbol = symbol;
      m_cfg = cfg;
      return true;
     }

   void Release(void) { m_symbol = ""; }

   bool Analyze(VantageGoldSMCResult &r)
     {
      double price = SymbolInfoDouble(m_symbol, SYMBOL_BID);
      if(price <= 0.0) price = r.preferred_entry > 0 ? r.preferred_entry : r.external_equilibrium;

      ENUM_SMC_DIRECTION dir = InferSetupDir(r);
      r.setup_direction = SmcDirectionToString(dir);

      // Weights (defaults if all unset / ZeroMemory)
      double w_htf = NormWeight(m_cfg.w_htf_align);
      double w_liq = NormWeight(m_cfg.w_liquidity);
      double w_disp = NormWeight(m_cfg.w_displacement);
      double w_str = NormWeight(m_cfg.w_structure);
      double w_ob = NormWeight(m_cfg.w_order_block);
      double w_fvg = NormWeight(m_cfg.w_fvg);
      double w_pd = NormWeight(m_cfg.w_premium_discount);
      double w_sess = NormWeight(m_cfg.w_session);
      double w_pdw = NormWeight(m_cfg.w_pd_week);
      double w_ote = NormWeight(m_cfg.w_ote);
      double w_ltf = NormWeight(m_cfg.w_ltf);
      double w_vol = NormWeight(m_cfg.w_vol_spread);
      double wsum = w_htf + w_liq + w_disp + w_str + w_ob + w_fvg + w_pd + w_sess + w_pdw + w_ote + w_ltf + w_vol;
      if(wsum <= 0.0)
        {
         w_htf = 15; w_liq = 12; w_disp = 12; w_str = 14; w_ob = 10; w_fvg = 8;
         w_pd = 7; w_sess = 5; w_pdw = 4; w_ote = 4; w_ltf = 6; w_vol = 3;
         wsum = 100.0;
        }

      string n1, n2, n3, n4, n5, n6, n7, n8, n9, n10, n11, n12;
      double s_htf = ScoreHtf(r, dir, n1);
      double s_liq = ScoreLiq(r, dir, n2);
      double s_disp = ScoreDisp(r, n3);
      double s_str = ScoreStruct(r, dir, n4);
      double s_ob = ScoreOb(r, dir, n5);
      double s_fvg = ScoreFvg(r, dir, n6);
      double s_pd = ScorePd(r, dir, n7);
      double s_sess = ScoreSession(r, n8);
      double s_pdw = ScorePdWeek(r, dir, n9);
      double s_ote = ScoreOte(r, n10);
      double s_ltf = ScoreLtf(r, dir, n11);
      double s_vol = ScoreVolSpread(n12);

      // Countertrend penalty
      ENUM_SMC_DIRECTION bias = ResolveBias(r);
      if(bias != SMC_DIR_NEUTRAL && dir != SMC_DIR_NEUTRAL && bias != dir)
        {
         s_htf *= 0.5;
         s_str *= 0.7;
         n1 += " (countertrend penalty)";
        }

      double score = 100.0 * (
         w_htf * s_htf + w_liq * s_liq + w_disp * s_disp + w_str * s_str +
         w_ob * s_ob + w_fvg * s_fvg + w_pd * s_pd + w_sess * s_sess +
         w_pdw * s_pdw + w_ote * s_ote + w_ltf * s_ltf + w_vol * s_vol
      ) / wsum;

      // Hard caps: incomplete ingredients cannot be A-grade
      if(!PoiValid(r) && !HasSweep(r))
         score = MathMin(score, 35.0);
      if(!PoiValid(r))
         score = MathMin(score, 55.0);
      if(dir == SMC_DIR_NEUTRAL)
         score = MathMin(score, 40.0);
      if(r.premium_discount == "Equilibrium" && !r.poi_overlaps_ote)
         score = MathMin(score, 60.0);

      score = Clamp(score, 0.0, 100.0);
      r.confidence_score = score;
      r.quality_grade = SmcGradeFromScore(score);
      r.confidence_band = SmcConfidenceBand(score);

      r.score_breakdown =
         "HTF " + DoubleToString(s_htf * 100, 0) + " (" + n1 + "); " +
         "Liq " + DoubleToString(s_liq * 100, 0) + " (" + n2 + "); " +
         "Disp " + DoubleToString(s_disp * 100, 0) + " (" + n3 + "); " +
         "Struct " + DoubleToString(s_str * 100, 0) + " (" + n4 + "); " +
         "OB " + DoubleToString(s_ob * 100, 0) + " (" + n5 + "); " +
         "FVG " + DoubleToString(s_fvg * 100, 0) + " (" + n6 + "); " +
         "PD " + DoubleToString(s_pd * 100, 0) + " (" + n7 + "); " +
         "Sess " + DoubleToString(s_sess * 100, 0) + " (" + n8 + "); " +
         "PDW " + DoubleToString(s_pdw * 100, 0) + " (" + n9 + "); " +
         "OTE " + DoubleToString(s_ote * 100, 0) + " (" + n10 + "); " +
         "LTF " + DoubleToString(s_ltf * 100, 0) + " (" + n11 + "); " +
         "Vol " + DoubleToString(s_vol * 100, 0) + " (" + n12 + ")";

      string candidate = ClassifyType(r, dir);
      r.setup_candidate = candidate;
      double min_sc = (m_cfg.min_setup_score > 0.0) ? m_cfg.min_setup_score : 45.0;
      if(score < min_sc || candidate == "No Valid SMC Setup" || candidate == "Context Forming Watch")
         r.setup_type = "No Valid SMC Setup";
      else
         r.setup_type = candidate;

      BuildEntry(r, dir, price);
      BuildInvalidation(r, dir);
      BuildTargets(r, dir);

      bool inside = (r.entry_status == "Inside");
      bool approaching = (r.entry_status == "Approaching");
      ENUM_SMC_SETUP_PHASE phase = ClassifyPhase(r, score, price, inside, approaching);
      phase = RefinePhaseWithTargets(phase, r, price);
      if(r.entry_status == "Missed" && score >= min_sc)
         phase = SMC_PHASE_SETUP_MISSED;
      if(r.entry_status == "Invalidated")
         phase = SMC_PHASE_SETUP_INVALIDATED;
      r.setup_phase = SmcPhaseToString(phase);

      // Reasons
      r.reasons_for = "Approved Gold symbol;";
      r.reasons_against = "";
      if(s_htf >= 0.7) r.reasons_for += "HTF alignment;";
      if(s_liq >= 0.7) r.reasons_for += "Liquidity event;";
      if(s_disp >= 0.65) r.reasons_for += "Displacement;";
      if(s_ob >= 0.6) r.reasons_for += "Valid OB;";
      if(s_fvg >= 0.6) r.reasons_for += "Valid FVG;";
      if(s_pd >= 0.8) r.reasons_for += "Favorable premium/discount;";
      if(s_ote >= 0.7) r.reasons_for += "OTE confluence;";
      if(StringFind(r.inducement_status, "Confirmed") >= 0) r.reasons_for += "Inducement sweep;";
      if(StringFind(r.po3_status, "Distribution") >= 0 ||
         StringFind(r.po3_status, "Manipulation confirmed") >= 0)
         r.reasons_for += "PO3 context;";

      if(score < min_sc) r.reasons_against += "Score below setup gate;";
      if(!PoiValid(r)) r.reasons_against += "No qualifying POI;";
      if(bias != SMC_DIR_NEUTRAL && dir != bias) r.reasons_against += "Countertrend vs HTF;";
      if(r.premium_discount == "Equilibrium") r.reasons_against += "At equilibrium;";
      if(s_vol < 0.4) r.reasons_against += "Spread/volatility drag;";
      if(StringFind(r.sweep_class, "true breakout") >= 0)
         r.reasons_against += "True breakout — not treated as reversal;";
      if(r.setup_type == "No Valid SMC Setup")
         r.reasons_against += "Incomplete confluence;";

      // Narrative
      string narr = "Gold SMC score " + DoubleToString(score, 0) + "/100 (" + r.quality_grade +
                    ", " + r.confidence_band + "). Direction: " + r.setup_direction + ".";
      if(r.setup_type != "No Valid SMC Setup")
         narr += " Setup: " + r.setup_type + " — phase " + r.setup_phase + ".";
      else
         narr += " No Valid SMC Setup" +
                 (r.setup_candidate != "" && r.setup_candidate != "No Valid SMC Setup"
                  ? (" (candidate: " + r.setup_candidate + ")") : "") +
                 ". Phase: " + r.setup_phase + ".";
      if(r.entry_zone != "")
         narr += " Entry " + r.entry_zone + " [" + r.entry_status + "]" +
                 (r.zone_source != "" ? (" via " + r.zone_source) : "") + ".";
      if(r.invalidation != "")
         narr += " Invalidation: " + r.invalidation + ".";
      if(r.targets != "")
         narr += " Targets: " + r.targets +
                 (r.estimated_rr > 0 ? (" (est. R:R to T1 " + DoubleToString(r.estimated_rr, 1) + ")") : "") + ".";
      narr += " Advisory only — no orders are placed.";
      r.technical_narrative = narr;

      // Recommendation
      if(r.setup_type == "No Valid SMC Setup")
        {
         r.recommendation = "WAIT — " + r.confidence_band +
                            " confluence (" + DoubleToString(score, 0) +
                            "). " + (r.reasons_against != "" ? r.reasons_against : "Conditions incomplete.");
        }
      else if(phase == SMC_PHASE_SETUP_CONFIRMED)
        {
         r.recommendation = "WATCH — " + r.setup_direction + " " + r.setup_type +
                            " confirmed analytically at " + r.entry_zone +
                            ". Manage risk to invalidation; not an order instruction.";
        }
      else if(inside)
        {
         r.recommendation = "WATCH — price inside entry zone (" + r.entry_zone +
                            "). Await LTF reaction; score " + DoubleToString(score, 0) +
                            " (" + r.quality_grade + ").";
        }
      else if(approaching)
        {
         r.recommendation = "WAIT — approaching " + r.setup_direction + " zone " + r.entry_zone +
                            ". Score " + DoubleToString(score, 0) + " (" + r.quality_grade + ").";
        }
      else
        {
         r.recommendation = "WAIT — " + r.setup_type + " developing (" + r.setup_phase +
                            "). Score " + DoubleToString(score, 0) + " (" + r.quality_grade + ").";
        }

      r.engine_phase = 8;
      r.status_line = "ACTIVE – GOLD ONLY (Phase 8)";
      r.analysis_active = true;

      Print("[GoldSMC][SETUP] score=", DoubleToString(score, 0),
            " grade=", r.quality_grade,
            " type=", r.setup_type,
            " dir=", r.setup_direction,
            " phase=", r.setup_phase,
            " rr=", DoubleToString(r.estimated_rr, 1));
      return true;
     }
  };

#endif
//+------------------------------------------------------------------+
