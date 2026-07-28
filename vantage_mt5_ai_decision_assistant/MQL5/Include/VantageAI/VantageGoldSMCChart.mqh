//+------------------------------------------------------------------+
//| VantageGoldSMCChart.mqh                                          |
//| Phase 7 — Chart objects (VAI_GSMC_*)                             |
//| Advisory-only — never opens, modifies, or closes trades          |
//+------------------------------------------------------------------+
#ifndef VANTAGE_GOLD_SMC_CHART_MQH
#define VANTAGE_GOLD_SMC_CHART_MQH

#include "VantageGoldSMCTypes.mqh"

class CVantageGoldSMCChart
  {
private:
   string               m_symbol;
   VantageGoldSMCConfig m_cfg;
   string               m_prefix;

   datetime LeftTime(void)
     {
      int lb = m_cfg.chart_lookback_bars;
      if(lb < 20) lb = 80;
      if(lb > 500) lb = 500;
      datetime t[];
      if(CopyTime(m_symbol, m_cfg.tf_exec, 0, lb, t) == lb)
         return t[lb - 1];
      return TimeCurrent() - (datetime)(lb * PeriodSeconds(m_cfg.tf_exec));
     }

   datetime RightTime(void)
     {
      return TimeCurrent() + (datetime)(12 * PeriodSeconds(m_cfg.tf_exec));
     }

   void SetHLine(const string key, const double price, const color clr,
                 const ENUM_LINE_STYLE style, const int width, const string text)
     {
      string id = m_prefix + key;
      if(price <= 0.0)
        {
         if(ObjectFind(0, id) >= 0) ObjectDelete(0, id);
         return;
        }
      if(ObjectFind(0, id) < 0)
        {
         ObjectCreate(0, id, OBJ_HLINE, 0, 0, price);
         ObjectSetInteger(0, id, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, id, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, id, OBJPROP_BACK, true);
        }
      ObjectSetDouble(0, id, OBJPROP_PRICE, price);
      ObjectSetInteger(0, id, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, id, OBJPROP_STYLE, style);
      ObjectSetInteger(0, id, OBJPROP_WIDTH, width);
      ObjectSetString(0, id, OBJPROP_TEXT, text);
      ObjectSetString(0, id, OBJPROP_TOOLTIP, text);
     }

   void SetRect(const string key, const double hi, const double lo,
                const color clr, const uchar alpha, const string text)
     {
      string id = m_prefix + key;
      if(hi <= lo || hi <= 0.0 || lo <= 0.0)
        {
         if(ObjectFind(0, id) >= 0) ObjectDelete(0, id);
         return;
        }
      datetime t1 = LeftTime();
      datetime t2 = RightTime();
      if(ObjectFind(0, id) < 0)
        {
         ObjectCreate(0, id, OBJ_RECTANGLE, 0, t1, hi, t2, lo);
         ObjectSetInteger(0, id, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, id, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, id, OBJPROP_BACK, true);
         ObjectSetInteger(0, id, OBJPROP_FILL, true);
        }
      ObjectMove(0, id, 0, t1, hi);
      ObjectMove(0, id, 1, t2, lo);
      color soft = (color)ColorToARGB(clr, alpha);
      ObjectSetInteger(0, id, OBJPROP_COLOR, soft);
      ObjectSetInteger(0, id, OBJPROP_BGCOLOR, soft);
      ObjectSetString(0, id, OBJPROP_TOOLTIP, text);
      ObjectSetString(0, id, OBJPROP_TEXT, text);
     }

   void SetText(const string key, const double price, const string text, const color clr)
     {
      string id = m_prefix + key;
      if(price <= 0.0 || text == "")
        {
         if(ObjectFind(0, id) >= 0) ObjectDelete(0, id);
         return;
        }
      datetime t = RightTime();
      if(ObjectFind(0, id) < 0)
        {
         ObjectCreate(0, id, OBJ_TEXT, 0, t, price);
         ObjectSetInteger(0, id, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, id, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, id, OBJPROP_ANCHOR, ANCHOR_LEFT);
         ObjectSetInteger(0, id, OBJPROP_FONTSIZE, 8);
        }
      ObjectMove(0, id, 0, t, price);
      ObjectSetString(0, id, OBJPROP_TEXT, text);
      ObjectSetInteger(0, id, OBJPROP_COLOR, clr);
     }

   void ClearKey(const string key)
     {
      string id = m_prefix + key;
      if(ObjectFind(0, id) >= 0) ObjectDelete(0, id);
     }

public:
   CVantageGoldSMCChart(void) : m_symbol(""), m_prefix("VAI_GSMC_")
     {
      ZeroMemory(m_cfg);
     }

   void Configure(const string symbol, const VantageGoldSMCConfig &cfg)
     {
      m_symbol = symbol;
      m_cfg = cfg;
     }

   void ClearAll(void)
     {
      int total = ObjectsTotal(0, 0, -1);
      for(int i = total - 1; i >= 0; i--)
        {
         string name = ObjectName(0, i, 0, -1);
         if(StringFind(name, m_prefix) == 0)
            ObjectDelete(0, name);
        }
     }

   void Render(VantageGoldSMCResult &r)
     {
      if(!m_cfg.show_chart_objects || !r.gold_symbol_valid || !r.analysis_active)
        {
         ClearAll();
         r.chart_objects_active = false;
         return;
        }

      // --- Range / PD / EQ ---
      if(m_cfg.chart_show_range)
        {
         SetHLine("rng_hi", r.dealing_high, clrSilver, STYLE_DASH, 1, "GSMC Range High");
         SetHLine("rng_lo", r.dealing_low, clrSilver, STYLE_DASH, 1, "GSMC Range Low");
         SetHLine("rng_eq", r.dealing_eq, clrGold, STYLE_DOT, 1, "GSMC Equilibrium");
         if(r.dealing_high > r.dealing_eq && r.dealing_eq > r.dealing_low)
           {
            SetRect("pd_prem", r.dealing_high, r.dealing_eq, clrMaroon, 40, "Premium");
            SetRect("pd_disc", r.dealing_eq, r.dealing_low, clrDarkGreen, 40, "Discount");
           }
         else
           {
            ClearKey("pd_prem");
            ClearKey("pd_disc");
           }
         SetText("lbl_pd", r.dealing_eq, "EQ / " + r.premium_discount, clrGold);
        }
      else
        {
         ClearKey("rng_hi"); ClearKey("rng_lo"); ClearKey("rng_eq");
         ClearKey("pd_prem"); ClearKey("pd_disc"); ClearKey("lbl_pd");
        }

      // --- Liquidity ---
      if(m_cfg.chart_show_liquidity)
        {
         if(m_cfg.show_prev_day_liquidity)
           {
            SetHLine("pdh", r.pdh, clrDodgerBlue, STYLE_SOLID, 1, "PDH");
            SetHLine("pdl", r.pdl, clrDodgerBlue, STYLE_SOLID, 1, "PDL");
           }
         else { ClearKey("pdh"); ClearKey("pdl"); }
         if(m_cfg.show_prev_week_liquidity)
           {
            SetHLine("pwh", r.pwh, clrMediumPurple, STYLE_DASHDOT, 1, "PWH");
            SetHLine("pwl", r.pwl, clrMediumPurple, STYLE_DASHDOT, 1, "PWL");
           }
         else { ClearKey("pwh"); ClearKey("pwl"); }
         SetHLine("bsl", r.nearest_bsl, clrAqua, STYLE_DASH, 2, "BSL " + r.nearest_bsl_label);
         SetHLine("ssl", r.nearest_ssl, clrOrange, STYLE_DASH, 2, "SSL " + r.nearest_ssl_label);
        }
      else
        {
         ClearKey("pdh"); ClearKey("pdl"); ClearKey("pwh"); ClearKey("pwl");
         ClearKey("bsl"); ClearKey("ssl");
        }

      // --- Sessions ---
      if(m_cfg.chart_show_sessions && m_cfg.show_session_liquidity)
        {
         SetHLine("ash", r.asian_high, clrGray, STYLE_DOT, 1, "Asian High");
         SetHLine("asl", r.asian_low, clrGray, STYLE_DOT, 1, "Asian Low");
         SetHLine("lnh", r.london_high, clrSteelBlue, STYLE_DOT, 1, "London High");
         SetHLine("lnl", r.london_low, clrSteelBlue, STYLE_DOT, 1, "London Low");
         SetHLine("nyh", r.ny_high, clrDarkOrange, STYLE_DOT, 1, "NY High");
         SetHLine("nyl", r.ny_low, clrDarkOrange, STYLE_DOT, 1, "NY Low");
        }
      else
        {
         ClearKey("ash"); ClearKey("asl"); ClearKey("lnh"); ClearKey("lnl");
         ClearKey("nyh"); ClearKey("nyl");
        }

      // --- Primary POI ---
      if(m_cfg.chart_show_poi && r.poi_upper > r.poi_lower)
        {
         color pc = (r.primary_poi_dir == "Bullish") ? clrLime : clrTomato;
         SetRect("poi", r.poi_upper, r.poi_lower, pc, 50,
                 r.primary_poi_dir + " " + r.primary_poi_type);
         SetText("lbl_poi", r.poi_mid > 0 ? r.poi_mid : 0.5 * (r.poi_upper + r.poi_lower),
                 r.primary_poi_type + " [" + r.primary_poi_status + "]", pc);
         if(r.poi_ce > 0)
            SetHLine("poi_ce", r.poi_ce, clrWhite, STYLE_DOT, 1, "CE");
         else
            ClearKey("poi_ce");
        }
      else
        {
         ClearKey("poi"); ClearKey("lbl_poi"); ClearKey("poi_ce");
        }

      // --- OTE ---
      if(m_cfg.chart_show_ote && r.ote_enabled_hit && r.ote_high > r.ote_low)
        {
         SetRect("ote", r.ote_high, r.ote_low, clrDarkSlateBlue, 45, "OTE");
         SetHLine("ote_mid", r.ote_mid, clrBlueViolet, STYLE_DOT, 1, "OTE mid");
         SetText("lbl_ote", r.ote_mid, "OTE", clrBlueViolet);
        }
      else
        {
         ClearKey("ote"); ClearKey("ote_mid"); ClearKey("lbl_ote");
        }

      // --- Setup entry / inv / targets ---
      if(m_cfg.chart_show_setup)
        {
         if(r.entry_high > r.entry_low)
            SetRect("entry", r.entry_high, r.entry_low, clrGoldenrod, 55,
                    "Entry " + r.entry_status);
         else
            ClearKey("entry");
         SetHLine("inv", r.invalidation_price, clrMagenta, STYLE_DASHDOTDOT, 2, "Invalidation");
         SetHLine("t1", r.target_1, clrLimeGreen, STYLE_SOLID, 1, "T1");
         SetHLine("t2", r.target_2, clrYellowGreen, STYLE_SOLID, 1, "T2");
         SetHLine("t3", r.target_3, clrOlive, STYLE_SOLID, 1, "T3");
         if(r.preferred_entry > 0)
            SetHLine("pref", r.preferred_entry, clrWhite, STYLE_DOT, 1, "Preferred entry");
         else
            ClearKey("pref");
         string evt = r.latest_structure_event;
         if(evt != "" && evt != "None")
            SetText("lbl_evt", (r.nearest_bsl > 0 ? r.nearest_bsl : r.dealing_eq), evt, clrAqua);
         else
            ClearKey("lbl_evt");
        }
      else
        {
         ClearKey("entry"); ClearKey("inv"); ClearKey("t1"); ClearKey("t2"); ClearKey("t3");
         ClearKey("pref"); ClearKey("lbl_evt");
        }

      r.chart_objects_active = true;
      ChartRedraw(0);
     }
  };

#endif
//+------------------------------------------------------------------+
