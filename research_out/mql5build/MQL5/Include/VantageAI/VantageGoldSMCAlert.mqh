//+------------------------------------------------------------------+
//| VantageGoldSMCAlert.mqh                                          |
//| Phase 7 — Configurable Gold SMC alerts (deduped / cooldown)      |
//| Advisory-only — never opens, modifies, or closes trades          |
//+------------------------------------------------------------------+
#ifndef VANTAGE_GOLD_SMC_ALERT_MQH
#define VANTAGE_GOLD_SMC_ALERT_MQH

#include "VantageGoldSMCTypes.mqh"

class CVantageGoldSMCAlert
  {
private:
   string               m_symbol;
   VantageGoldSMCConfig m_cfg;
   string               m_last_key;
   datetime             m_last_time;
   string               m_prev_sweep_evt;
   string               m_prev_entry_status;
   string               m_prev_setup_phase;
   string               m_prev_structure_evt;
   bool                 m_reject_alerted;
   bool                 m_inside_alerted;
   bool                 m_confirm_alerted;
   string               m_confirm_setup_id;

   void Fire(VantageGoldSMCResult &r, const string key, const string msg)
     {
      if(!m_cfg.alert_enable) return;
      if(key == "" || key == m_last_key) return;
      int cool = m_cfg.alert_cooldown_sec;
      if(cool < 30) cool = 30;
      if(m_last_time > 0 && (TimeCurrent() - m_last_time) < cool) return;

      m_last_key = key;
      m_last_time = TimeCurrent();
      r.last_alert = msg;
      r.last_alert_time = m_last_time;

      string full = "Gold SMC [" + (r.base_symbol != "" ? r.base_symbol : m_symbol) + "]: " + msg;
      if(m_cfg.alert_popup) Alert(full);
      if(m_cfg.alert_sound) PlaySound("alert.wav");
      if(m_cfg.alert_push)
        {
         if(!SendNotification(full))
            Print("[GoldSMC][ALERT] push failed err=", GetLastError());
        }
      Print("[GoldSMC][ALERT] ", full);
     }

public:
   CVantageGoldSMCAlert(void)
      : m_symbol(""), m_last_key(""), m_last_time(0),
        m_prev_sweep_evt(""), m_prev_entry_status(""), m_prev_setup_phase(""),
        m_prev_structure_evt(""), m_reject_alerted(false),
        m_inside_alerted(false), m_confirm_alerted(false), m_confirm_setup_id("")
     {
      ZeroMemory(m_cfg);
     }

   void Configure(const string symbol, const VantageGoldSMCConfig &cfg)
     {
      m_symbol = symbol;
      m_cfg = cfg;
     }

   void Reset(void)
     {
      m_last_key = "";
      m_last_time = 0;
      m_prev_sweep_evt = "";
      m_prev_entry_status = "";
      m_prev_setup_phase = "";
      m_prev_structure_evt = "";
      m_reject_alerted = false;
      m_inside_alerted = false;
      m_confirm_alerted = false;
      m_confirm_setup_id = "";
     }

   void MaybeAlert(VantageGoldSMCResult &r)
     {
      if(!m_cfg.alert_enable)
         return;

      // Preserve prior alert on quiet ticks
      if(r.last_alert == "" && m_last_key != "")
        {
         // keep displayed last_alert from previous fire via m_last — caller copies result
        }

      if(!r.engine_enabled)
         return;

      // Non-gold rejection (one-shot until accepted again)
      if(!r.gold_symbol_valid)
        {
         if(!m_reject_alerted)
           {
            m_reject_alerted = true;
            Fire(r, "REJECT|" + r.symbol, "Gold-only module disabled on " + r.symbol);
           }
         return;
        }
      m_reject_alerted = false;

      if(!r.analysis_active)
         return;

      string bar = TimeToString(r.eval_bar_m5, TIME_DATE|TIME_MINUTES);

      // Wide spread
      double ask = SymbolInfoDouble(m_symbol, SYMBOL_ASK);
      double bid = SymbolInfoDouble(m_symbol, SYMBOL_BID);
      double point = SymbolInfoDouble(m_symbol, SYMBOL_POINT);
      double spread_thr = (m_cfg.alert_spread_points > 0) ? m_cfg.alert_spread_points : 120.0;
      if(ask > 0 && bid > 0 && point > 0)
        {
         double sp = (ask - bid) / point;
         if(sp >= spread_thr)
            Fire(r, "SPREAD|" + bar, "Spread elevated (" + DoubleToString(sp, 0) + " pts)");
        }

      // Liquidity approaching
      if(r.distance_bsl_atr > 0 && r.distance_bsl_atr <= m_cfg.approach_atr)
         Fire(r, "APPR_BSL|" + bar, "Buy-side liquidity approaching (" +
              r.nearest_bsl_label + " " + DoubleToString(r.nearest_bsl, _Digits) + ")");
      if(r.distance_ssl_atr > 0 && r.distance_ssl_atr <= m_cfg.approach_atr)
         Fire(r, "APPR_SSL|" + bar, "Sell-side liquidity approaching (" +
              r.nearest_ssl_label + " " + DoubleToString(r.nearest_ssl, _Digits) + ")");

      // Sweep edge
      string sweep_evt = r.latest_liquidity_event;
      if(sweep_evt != "" && sweep_evt != m_prev_sweep_evt)
        {
         if(StringFind(sweep_evt, "Buy-Side") >= 0 &&
            (StringFind(sweep_evt, "swept") >= 0 || StringFind(sweep_evt, "Swept") >= 0))
            Fire(r, "SWEEP_BSL|" + bar, "Buy-side liquidity swept — " + r.sweep_class);
         else if(StringFind(sweep_evt, "Sell-Side") >= 0 &&
                 (StringFind(sweep_evt, "swept") >= 0 || StringFind(sweep_evt, "Swept") >= 0))
            Fire(r, "SWEEP_SSL|" + bar, "Sell-side liquidity swept — " + r.sweep_class);
         m_prev_sweep_evt = sweep_evt;
        }

      // Structure MSS / displacement
      string sev = r.latest_structure_event;
      if(sev != "" && sev != m_prev_structure_evt)
        {
         if(StringFind(sev, "MSS Bull") >= 0 || sev == "MSS Bullish")
            Fire(r, "MSS_BULL|" + bar, "Bullish MSS confirmed");
         else if(StringFind(sev, "MSS Bear") >= 0 || sev == "MSS Bearish")
            Fire(r, "MSS_BEAR|" + bar, "Bearish MSS confirmed");
         m_prev_structure_evt = sev;
        }
      if(StringFind(r.displacement_status, "Strong") >= 0 ||
         StringFind(r.displacement_status, "Exceptional") >= 0)
        {
         if(r.setup_direction == "Bullish" || r.primary_poi_dir == "Bullish")
            Fire(r, "DISP_BULL|" + bar, "Bullish displacement — " + r.displacement_status);
         else if(r.setup_direction == "Bearish" || r.primary_poi_dir == "Bearish")
            Fire(r, "DISP_BEAR|" + bar, "Bearish displacement — " + r.displacement_status);
        }

      // Entry zone transitions
      if(r.entry_status == "Inside" && m_prev_entry_status != "Inside")
        {
         string z = (r.zone_source != "" ? r.zone_source : r.primary_poi_type);
         Fire(r, "INSIDE|" + bar + "|" + r.entry_zone,
              "Price inside " + z + " " + r.entry_zone);
         m_inside_alerted = true;
        }
      if(r.entry_status != "Inside")
         m_inside_alerted = false;
      m_prev_entry_status = r.entry_status;

      // CE touch: preferred entry ≈ CE when inside and poi_ce set
      if(r.entry_status == "Inside" && r.poi_ce > 0 && r.preferred_entry > 0)
        {
         double px = SymbolInfoDouble(m_symbol, SYMBOL_BID);
         double tol = (r.entry_high - r.entry_low) * 0.15;
         if(tol <= 0) tol = _Point * 50;
         if(MathAbs(px - r.poi_ce) <= tol)
            Fire(r, "CE|" + bar, "Price at consequent encroachment " +
                 DoubleToString(r.poi_ce, _Digits));
        }

      // Score threshold
      double min_sc = (m_cfg.alert_min_score > 0) ? m_cfg.alert_min_score : 75.0;
      if(r.confidence_score >= min_sc && r.setup_type != "No Valid SMC Setup")
         Fire(r, "SCORE|" + bar + "|" + DoubleToString(r.confidence_score, 0),
              "Setup confidence " + DoubleToString(r.confidence_score, 0) +
              " (" + r.quality_grade + ") — " + r.setup_type);

      // Setup confirmed (one-time per setup id)
      string setup_id = r.setup_type + "|" + r.entry_zone + "|" + r.setup_direction;
      if(r.setup_phase == "Setup Confirmed")
        {
         if(!m_confirm_alerted || m_confirm_setup_id != setup_id)
           {
            m_confirm_alerted = true;
            m_confirm_setup_id = setup_id;
            Fire(r, "CONF|" + setup_id, "Setup confirmed — " + r.setup_direction + " " + r.setup_type);
           }
        }
      else if(r.setup_phase == "Setup Invalidated")
        {
         Fire(r, "INV|" + bar + "|" + setup_id, "Setup invalidated — " + r.invalidation);
         m_confirm_alerted = false;
        }
      else if(r.setup_phase != m_prev_setup_phase)
        {
         if(StringFind(r.setup_phase, "Target 1") >= 0)
            Fire(r, "T1|" + bar, "Target 1 reached " + DoubleToString(r.target_1, _Digits));
         else if(StringFind(r.setup_phase, "Target 2") >= 0)
            Fire(r, "T2|" + bar, "Target 2 reached " + DoubleToString(r.target_2, _Digits));
         else if(StringFind(r.setup_phase, "Target 3") >= 0 ||
                 StringFind(r.setup_phase, "Completed") >= 0)
            Fire(r, "T3|" + bar, "Target / setup completed");
        }
      m_prev_setup_phase = r.setup_phase;

      // Carry last alert into result for HUD/web if we have one
      if(r.last_alert == "" && m_last_key != "" && m_last_time > 0)
        {
         // leave empty on quiet cycles — facade may copy from m_last
        }
     }
  };

#endif
//+------------------------------------------------------------------+
