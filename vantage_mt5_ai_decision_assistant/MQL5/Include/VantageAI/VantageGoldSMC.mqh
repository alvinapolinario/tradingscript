//+------------------------------------------------------------------+
//| VantageGoldSMC.mqh                                               |
//| Gold SMC Intelligence Engine — facade (Phase 8 polish)           |
//| Advisory-only — never opens, modifies, or closes trades          |
//+------------------------------------------------------------------+
#ifndef VANTAGE_GOLD_SMC_MQH
#define VANTAGE_GOLD_SMC_MQH

#include "VantageTypes.mqh"
#include "VantageGoldSMCTypes.mqh"
#include "VantageGoldSMCValidator.mqh"
#include "VantageGoldSMCCore.mqh"
#include "VantageGoldSMCLiquidity.mqh"
#include "VantageGoldSMCZones.mqh"
#include "VantageGoldSMCContext.mqh"
#include "VantageGoldSMCSetup.mqh"
#include "VantageGoldSMCChart.mqh"
#include "VantageGoldSMCAlert.mqh"

class CVantageGoldSMC
  {
private:
   string                 m_symbol;
   VantageGoldSMCConfig   m_cfg;
   VantageGoldSMCResult   m_last;
   CVantageGoldSymbolValidator m_validator;
   CVantageGoldSMCCore    m_core;
   CVantageGoldSMCLiquidity m_liq;
   CVantageGoldSMCZones   m_zones;
   CVantageGoldSMCContext m_ctx;
   CVantageGoldSMCSetup   m_setup;
   CVantageGoldSMCChart   m_chart;
   CVantageGoldSMCAlert   m_alert;
   bool                   m_inited;
   bool                   m_core_ready;
   bool                   m_liq_ready;
   bool                   m_zones_ready;
   bool                   m_ctx_ready;
   bool                   m_setup_ready;
   datetime               m_last_m5_bar;
   string                 m_obj_prefix;

   void ResetResult(VantageGoldSMCResult &r)
     {
      r.valid = false;
      r.gold_symbol_valid = false;
      r.engine_enabled = false;
      r.analysis_active = false;
      r.symbol = "";
      r.base_symbol = "";
      r.status_line = "";
      r.disable_reason = "";
      r.macro_bias = SMC_DIR_NEUTRAL;
      r.h4_bias = SMC_DIR_NEUTRAL;
      r.h1_bias = SMC_DIR_NEUTRAL;
      r.m15_bias = SMC_DIR_NEUTRAL;
      r.m5_bias = SMC_DIR_NEUTRAL;
      r.structure_status = "";
      r.m5_context = "";
      r.latest_structure_event = "";
      r.external_range_high = 0.0;
      r.external_range_low = 0.0;
      r.external_equilibrium = 0.0;
      r.premium_discount = "";
      r.pdh = 0; r.pdl = 0; r.pd_mid = 0;
      r.pwh = 0; r.pwl = 0; r.pw_mid = 0;
      r.cdh = 0; r.cdl = 0;
      r.asian_high = 0; r.asian_low = 0;
      r.london_high = 0; r.london_low = 0;
      r.ny_high = 0; r.ny_low = 0;
      r.nearest_bsl_label = "";
      r.nearest_ssl_label = "";
      r.distance_bsl_atr = 0;
      r.distance_ssl_atr = 0;
      r.liquidity_draw = "";
      r.draw_distance_atr = 0;
      r.latest_liquidity_event = "";
      r.sweep_class = "";
      r.session_name = "";
      r.equal_highs_note = "";
      r.equal_lows_note = "";
      r.displacement_status = "";
      r.primary_poi_type = "";
      r.primary_poi_dir = "";
      r.primary_poi_status = "";
      r.poi_upper = 0; r.poi_lower = 0; r.poi_mid = 0; r.poi_ce = 0;
      r.poi_mitigation_pct = 0; r.poi_quality = 0;
      r.fvg_summary = "";
      r.order_block_summary = "";
      r.breaker_summary = "";
      r.has_fresh_fvg = false;
      r.has_valid_ob = false;
      r.has_breaker = false;
      r.has_inverse_fvg = false;
      r.dealing_high = 0; r.dealing_low = 0; r.dealing_eq = 0; r.dealing_pct = 0;
      r.in_discount = false; r.in_premium = false;
      r.ote_enabled_hit = false;
      r.ote_low = 0; r.ote_mid = 0; r.ote_high = 0;
      r.price_in_ote = false; r.poi_overlaps_ote = false;
      r.inducement_status = "";
      r.po3_status = "";
      r.po3_bias = "";
      r.setup_direction = "Neutral";
      r.setup_type = "No Valid SMC Setup";
      r.setup_candidate = "";
      r.setup_phase = SmcPhaseToString(SMC_PHASE_NO_SETUP);
      r.confidence_score = 0.0;
      r.confidence_band = "No Valid Setup";
      r.quality_grade = "Invalid";
      r.score_breakdown = "";
      r.entry_zone = "";
      r.entry_low = 0; r.entry_high = 0; r.preferred_entry = 0;
      r.entry_status = "";
      r.zone_source = "";
      r.invalidation = "";
      r.invalidation_price = 0;
      r.target_1 = 0; r.target_2 = 0; r.target_3 = 0;
      r.targets = "";
      r.estimated_rr = 0;
      r.recommendation = "";
      r.technical_narrative = "";
      r.reasons_for = "";
      r.reasons_against = "";
      r.eval_bar_m5 = 0;
      r.engine_phase = 8;
      r.nearest_bsl = 0.0;
      r.nearest_ssl = 0.0;
      r.last_alert = "";
      r.last_alert_time = 0;
      r.chart_objects_active = false;
     }

   void DeleteChartObjects(void)
     {
      m_chart.ClearAll();
     }

   void Debug(const string cat, const string msg) const
     {
      if(!m_cfg.debug_log) return;
      Print("[GoldSMC][", cat, "] ", msg);
     }

   // Lightweight live update between closed M5 bars (entry proximity only)
   void LightRefreshLive(VantageGoldSMCResult &r)
     {
      if(!r.analysis_active || !r.gold_symbol_valid) return;
      double price = SymbolInfoDouble(m_symbol, SYMBOL_BID);
      if(price <= 0.0) return;

      if(r.ote_enabled_hit && r.ote_high > r.ote_low)
         r.price_in_ote = (price >= r.ote_low && price <= r.ote_high);

      if(r.entry_high > r.entry_low)
        {
         double mid = 0.5 * (r.entry_low + r.entry_high);
         double half = 0.5 * (r.entry_high - r.entry_low);
         double atr_proxy = (r.dealing_high > r.dealing_low)
                            ? (r.dealing_high - r.dealing_low) * 0.08
                            : half * 2.0;
         if(atr_proxy <= 0) atr_proxy = (half > 0 ? half : 1.0);
         string prev = r.entry_status;
         if(StringFind(r.primary_poi_status, "Invalid") >= 0 || r.poi_mitigation_pct >= 95.0)
            r.entry_status = "Invalidated";
         else if(price >= r.entry_low && price <= r.entry_high)
            r.entry_status = "Inside";
         else if(MathAbs(price - mid) <= atr_proxy * MathMax(0.35, m_cfg.approach_atr))
            r.entry_status = "Approaching";
         else
            r.entry_status = "Far";

         if(prev != r.entry_status)
           {
            Debug("PERFORMANCE", "LightRefresh entry_status " + prev + " -> " + r.entry_status);
            if(m_cfg.show_chart_objects)
              {
               m_chart.Configure(m_symbol, m_cfg);
               m_chart.Render(r);
              }
            m_alert.Configure(m_symbol, m_cfg);
            m_alert.MaybeAlert(r);
           }
        }
      r.engine_phase = 8;
     }

   void ApplyDisabledState(VantageGoldSMCResult &r, const string symbol, const string base, const bool ok)
     {
      r.symbol = symbol;
      r.base_symbol = base;
      r.engine_enabled = m_cfg.enable;
      r.gold_symbol_valid = ok;
      r.engine_phase = 8;
      r.valid = true;
      r.analysis_active = false;
     }

public:
   CVantageGoldSMC(void)
      : m_symbol(""), m_inited(false), m_core_ready(false), m_liq_ready(false),
        m_zones_ready(false), m_ctx_ready(false), m_setup_ready(false),
        m_last_m5_bar(0), m_obj_prefix("VAI_GSMC_")
     {
      ZeroMemory(m_cfg);
      ResetResult(m_last);
     }

   bool Init(const string symbol, const VantageGoldSMCConfig &cfg)
     {
      Release();
      m_symbol = symbol;
      m_cfg = cfg;
      m_validator.Configure(m_cfg.approved_aliases, m_cfg.allow_broker_suffix, m_cfg.allow_broker_prefix);
      m_chart.Configure(symbol, m_cfg);
      m_alert.Configure(symbol, m_cfg);
      m_alert.Reset();
      m_inited = true;

      VantageGoldSMCResult r;
      ResetResult(r);
      string base = "";
      const bool ok = m_validator.IsApprovedGoldSymbol(symbol, base);
      ApplyDisabledState(r, symbol, base, ok);

      if(!m_cfg.enable)
        {
         r.status_line = "INACTIVE — module disabled by input";
         r.disable_reason = "InpGoldSmcEnable=false";
         r.setup_phase = SmcPhaseToString(SMC_PHASE_NO_SETUP);
         r.recommendation = "Enable Gold SMC inputs to activate (Gold charts only).";
         r.technical_narrative = r.recommendation;
         Print("[GoldSMC][SYMBOL] Module input disabled on ", symbol);
         m_last = r;
         return true;
        }

      if(!ok)
        {
         r.status_line = "DISABLED — GOLD ONLY";
         r.disable_reason = m_validator.DisableMessage();
         r.setup_phase = SmcPhaseToString(SMC_PHASE_DISABLED_SYMBOL);
         r.setup_type = "No Valid SMC Setup";
         r.recommendation = m_validator.DisableMessage();
         r.technical_narrative = m_validator.DisableMessage();
         r.reasons_against = "Symbol failed strict Gold alias validation;";
         DeleteChartObjects();
         Print("[GoldSMC][SYMBOL] REJECTED ", symbol, " — ", m_validator.DisableMessage());
         m_last = r;
         m_alert.MaybeAlert(m_last);
         return true;
        }

      m_core_ready = m_core.Init(symbol, m_cfg);
      m_liq_ready = m_liq.Init(symbol, m_cfg);
      m_zones_ready = m_zones.Init(symbol, m_cfg);
      m_ctx_ready = m_ctx.Init(symbol, m_cfg);
      m_setup_ready = m_setup.Init(symbol, m_cfg);
      if(!m_core_ready)
        {
         r.status_line = "ACTIVE – GOLD ONLY (structure init failed)";
         r.setup_phase = SmcPhaseToString(SMC_PHASE_INSUFFICIENT_DATA);
         r.recommendation = "WAIT — structure engine failed to initialize ATR handles.";
         r.technical_narrative = r.recommendation;
         r.reasons_against = "ATR handle init failed;";
         m_last = r;
         return true;
        }
      if(!m_liq_ready)
         Print("[GoldSMC][LIQUIDITY] init warning — ATR handle failed; liquidity map may be limited");
      if(!m_zones_ready)
         Print("[GoldSMC][ZONES] init warning — ATR handle failed; FVG/OB may be limited");

      r.status_line = "ACTIVE – GOLD ONLY (Phase 8)";
      r.setup_phase = SmcPhaseToString(SMC_PHASE_CONTEXT_FORMING);
      r.recommendation = "Evaluating structure + liquidity + POI + score + visuals…";
      r.technical_narrative = "Gold symbol validated (" + base + "). Running Phase 2–8 map.";
      r.reasons_for = "Approved Gold symbol;";
      Print("[GoldSMC][SYMBOL] ACCEPTED ", symbol, " base=", base, " (Phase 8)");
      m_last = r;
      VantageGoldSMCResult tmp;
      Evaluate(true, tmp);
      return true;
     }

   void Release(void)
     {
      m_core.Release();
      m_liq.Release();
      m_zones.Release();
      m_ctx.Release();
      m_setup.Release();
      m_alert.Reset();
      m_core_ready = false;
      m_liq_ready = false;
      m_zones_ready = false;
      m_ctx_ready = false;
      m_setup_ready = false;
      DeleteChartObjects();
      m_inited = false;
      m_last_m5_bar = 0;
      ResetResult(m_last);
     }

   bool Evaluate(const bool force, VantageGoldSMCResult &out)
     {
      if(!m_inited)
        {
         ResetResult(out);
         out.valid = false;
         out.disable_reason = "Gold SMC not initialized";
         return false;
        }

      string base = "";
      const bool ok = m_validator.IsApprovedGoldSymbol(m_symbol, base);
      if(m_cfg.enable && ok != m_last.gold_symbol_valid)
        {
         Init(m_symbol, m_cfg);
         out = m_last;
         return out.valid;
        }

      if(!m_cfg.enable || !ok || !m_core_ready)
        {
         out = m_last;
         return out.valid;
        }

      datetime m5_bar = 0;
      MqlRates rb[];
      if(CopyRates(m_symbol, m_cfg.tf_exec, 1, 1, rb) == 1)
         m5_bar = rb[0].time;

      if(!force && m5_bar != 0 && m5_bar == m_last_m5_bar && m_last.analysis_active)
        {
         VantageGoldSMCResult live = m_last;
         LightRefreshLive(live);
         m_last = live;
         out = m_last;
         return true;
        }

      datetime t0 = GetTickCount();
      VantageGoldSMCResult r = m_last;
      r.symbol = m_symbol;
      r.base_symbol = base;
      r.gold_symbol_valid = true;
      r.engine_enabled = true;
      r.eval_bar_m5 = m5_bar;
      r.engine_phase = 8;
      r.reasons_for = "Approved Gold symbol;";
      r.reasons_against = "";
      // Carry prior alert display across quiet re-evals
      r.last_alert = m_last.last_alert;
      r.last_alert_time = m_last.last_alert_time;

      if(!m_core.Analyze(r))
        {
         r.valid = true;
         r.engine_phase = 8;
         m_chart.Render(r);
         m_alert.MaybeAlert(r);
         m_last = r;
         m_last_m5_bar = m5_bar;
         out = m_last;
         return true;
        }

      if(m_liq_ready)
         m_liq.Analyze(r);

      if(m_zones_ready)
         m_zones.Analyze(r);

      if(m_ctx_ready)
         m_ctx.Analyze(r);

      if(m_setup_ready)
         m_setup.Analyze(r);
      else if(!m_zones_ready && !m_liq_ready)
        {
         r.engine_phase = 2;
         r.setup_phase = SmcPhaseToString(SMC_PHASE_STRUCTURE_READY);
        }

      r.engine_phase = 8;
      r.status_line = "ACTIVE – GOLD ONLY (Phase 8)";

      m_chart.Configure(m_symbol, m_cfg);
      m_alert.Configure(m_symbol, m_cfg);
      m_chart.Render(r);
      m_alert.MaybeAlert(r);

      uint elapsed = GetTickCount() - t0;
      Debug("PERFORMANCE", "Full eval " + IntegerToString((int)elapsed) + " ms on M5 " +
            TimeToString(m5_bar, TIME_DATE|TIME_MINUTES));

      r.valid = true;
      m_last = r;
      m_last_m5_bar = m5_bar;
      out = m_last;
      return true;
     }

   VantageGoldSMCResult Last(void) const { return m_last; }

   bool IsGoldActive(void) const
     {
      return (m_last.engine_enabled && m_last.gold_symbol_valid);
     }

   string ToJson(const VantageGoldSMCResult &r)
     {
      string j = "{";
      j += "\"version\":\"1.0\",";
      j += "\"engine_phase\":" + IntegerToString(r.engine_phase) + ",";
      j += "\"advisory_only\":true,";
      j += "\"valid\":" + (r.valid ? "true" : "false") + ",";
      j += "\"gold_symbol_valid\":" + (r.gold_symbol_valid ? "true" : "false") + ",";
      j += "\"engine_enabled\":" + (r.engine_enabled ? "true" : "false") + ",";
      j += "\"analysis_active\":" + (r.analysis_active ? "true" : "false") + ",";
      j += "\"symbol\":\"" + JsonEscape(r.symbol) + "\",";
      j += "\"base_symbol\":\"" + JsonEscape(r.base_symbol) + "\",";
      j += "\"status_line\":\"" + JsonEscape(r.status_line) + "\",";
      j += "\"disable_reason\":\"" + JsonEscape(r.disable_reason) + "\",";
      j += "\"macro_bias\":\"" + JsonEscape(SmcDirectionToString(r.macro_bias)) + "\",";
      j += "\"h4_bias\":\"" + JsonEscape(SmcDirectionToString(r.h4_bias)) + "\",";
      j += "\"h1_bias\":\"" + JsonEscape(SmcDirectionToString(r.h1_bias)) + "\",";
      j += "\"m15_bias\":\"" + JsonEscape(SmcDirectionToString(r.m15_bias)) + "\",";
      j += "\"m5_bias\":\"" + JsonEscape(SmcDirectionToString(r.m5_bias)) + "\",";
      j += "\"structure_status\":\"" + JsonEscape(r.structure_status) + "\",";
      j += "\"m5_context\":\"" + JsonEscape(r.m5_context) + "\",";
      j += "\"latest_structure_event\":\"" + JsonEscape(r.latest_structure_event) + "\",";
      j += "\"external_range_high\":" + DoubleToJson(r.external_range_high, 8) + ",";
      j += "\"external_range_low\":" + DoubleToJson(r.external_range_low, 8) + ",";
      j += "\"external_equilibrium\":" + DoubleToJson(r.external_equilibrium, 8) + ",";
      j += "\"premium_discount\":\"" + JsonEscape(r.premium_discount) + "\",";
      j += "\"dealing_high\":" + DoubleToJson(r.dealing_high, 8) + ",";
      j += "\"dealing_low\":" + DoubleToJson(r.dealing_low, 8) + ",";
      j += "\"dealing_eq\":" + DoubleToJson(r.dealing_eq, 8) + ",";
      j += "\"dealing_pct\":" + DoubleToJson(r.dealing_pct, 1) + ",";
      j += "\"in_discount\":" + (r.in_discount ? "true" : "false") + ",";
      j += "\"in_premium\":" + (r.in_premium ? "true" : "false") + ",";
      j += "\"ote_enabled\":" + (r.ote_enabled_hit ? "true" : "false") + ",";
      j += "\"ote_low\":" + DoubleToJson(r.ote_low, 8) + ",";
      j += "\"ote_mid\":" + DoubleToJson(r.ote_mid, 8) + ",";
      j += "\"ote_high\":" + DoubleToJson(r.ote_high, 8) + ",";
      j += "\"price_in_ote\":" + (r.price_in_ote ? "true" : "false") + ",";
      j += "\"poi_overlaps_ote\":" + (r.poi_overlaps_ote ? "true" : "false") + ",";
      j += "\"inducement_status\":\"" + JsonEscape(r.inducement_status) + "\",";
      j += "\"po3_status\":\"" + JsonEscape(r.po3_status) + "\",";
      j += "\"po3_bias\":\"" + JsonEscape(r.po3_bias) + "\",";
      j += "\"setup_direction\":\"" + JsonEscape(r.setup_direction) + "\",";
      j += "\"setup_candidate\":\"" + JsonEscape(r.setup_candidate) + "\",";
      j += "\"confidence_band\":\"" + JsonEscape(r.confidence_band) + "\",";
      j += "\"score_breakdown\":\"" + JsonEscape(r.score_breakdown) + "\",";
      j += "\"entry_low\":" + DoubleToJson(r.entry_low, 8) + ",";
      j += "\"entry_high\":" + DoubleToJson(r.entry_high, 8) + ",";
      j += "\"preferred_entry\":" + DoubleToJson(r.preferred_entry, 8) + ",";
      j += "\"entry_status\":\"" + JsonEscape(r.entry_status) + "\",";
      j += "\"zone_source\":\"" + JsonEscape(r.zone_source) + "\",";
      j += "\"invalidation_price\":" + DoubleToJson(r.invalidation_price, 8) + ",";
      j += "\"target_1\":" + DoubleToJson(r.target_1, 8) + ",";
      j += "\"target_2\":" + DoubleToJson(r.target_2, 8) + ",";
      j += "\"target_3\":" + DoubleToJson(r.target_3, 8) + ",";
      j += "\"estimated_rr\":" + DoubleToJson(r.estimated_rr, 2) + ",";
      j += "\"pdh\":" + DoubleToJson(r.pdh, 8) + ",";
      j += "\"pdl\":" + DoubleToJson(r.pdl, 8) + ",";
      j += "\"pd_mid\":" + DoubleToJson(r.pd_mid, 8) + ",";
      j += "\"pwh\":" + DoubleToJson(r.pwh, 8) + ",";
      j += "\"pwl\":" + DoubleToJson(r.pwl, 8) + ",";
      j += "\"pw_mid\":" + DoubleToJson(r.pw_mid, 8) + ",";
      j += "\"cdh\":" + DoubleToJson(r.cdh, 8) + ",";
      j += "\"cdl\":" + DoubleToJson(r.cdl, 8) + ",";
      j += "\"asian_high\":" + DoubleToJson(r.asian_high, 8) + ",";
      j += "\"asian_low\":" + DoubleToJson(r.asian_low, 8) + ",";
      j += "\"london_high\":" + DoubleToJson(r.london_high, 8) + ",";
      j += "\"london_low\":" + DoubleToJson(r.london_low, 8) + ",";
      j += "\"ny_high\":" + DoubleToJson(r.ny_high, 8) + ",";
      j += "\"ny_low\":" + DoubleToJson(r.ny_low, 8) + ",";
      j += "\"nearest_bsl\":" + DoubleToJson(r.nearest_bsl, 8) + ",";
      j += "\"nearest_ssl\":" + DoubleToJson(r.nearest_ssl, 8) + ",";
      j += "\"nearest_bsl_label\":\"" + JsonEscape(r.nearest_bsl_label) + "\",";
      j += "\"nearest_ssl_label\":\"" + JsonEscape(r.nearest_ssl_label) + "\",";
      j += "\"distance_bsl_atr\":" + DoubleToJson(r.distance_bsl_atr, 3) + ",";
      j += "\"distance_ssl_atr\":" + DoubleToJson(r.distance_ssl_atr, 3) + ",";
      j += "\"liquidity_draw\":\"" + JsonEscape(r.liquidity_draw) + "\",";
      j += "\"draw_distance_atr\":" + DoubleToJson(r.draw_distance_atr, 3) + ",";
      j += "\"latest_liquidity_event\":\"" + JsonEscape(r.latest_liquidity_event) + "\",";
      j += "\"sweep_class\":\"" + JsonEscape(r.sweep_class) + "\",";
      j += "\"session_name\":\"" + JsonEscape(r.session_name) + "\",";
      j += "\"equal_highs_note\":\"" + JsonEscape(r.equal_highs_note) + "\",";
      j += "\"equal_lows_note\":\"" + JsonEscape(r.equal_lows_note) + "\",";
      j += "\"displacement_status\":\"" + JsonEscape(r.displacement_status) + "\",";
      j += "\"primary_poi_type\":\"" + JsonEscape(r.primary_poi_type) + "\",";
      j += "\"primary_poi_dir\":\"" + JsonEscape(r.primary_poi_dir) + "\",";
      j += "\"primary_poi_status\":\"" + JsonEscape(r.primary_poi_status) + "\",";
      j += "\"poi_upper\":" + DoubleToJson(r.poi_upper, 8) + ",";
      j += "\"poi_lower\":" + DoubleToJson(r.poi_lower, 8) + ",";
      j += "\"poi_mid\":" + DoubleToJson(r.poi_mid, 8) + ",";
      j += "\"poi_ce\":" + DoubleToJson(r.poi_ce, 8) + ",";
      j += "\"poi_mitigation_pct\":" + DoubleToJson(r.poi_mitigation_pct, 1) + ",";
      j += "\"poi_quality\":" + DoubleToJson(r.poi_quality, 1) + ",";
      j += "\"fvg_summary\":\"" + JsonEscape(r.fvg_summary) + "\",";
      j += "\"order_block_summary\":\"" + JsonEscape(r.order_block_summary) + "\",";
      j += "\"breaker_summary\":\"" + JsonEscape(r.breaker_summary) + "\",";
      j += "\"has_fresh_fvg\":" + (r.has_fresh_fvg ? "true" : "false") + ",";
      j += "\"has_valid_ob\":" + (r.has_valid_ob ? "true" : "false") + ",";
      j += "\"has_breaker\":" + (r.has_breaker ? "true" : "false") + ",";
      j += "\"has_inverse_fvg\":" + (r.has_inverse_fvg ? "true" : "false") + ",";
      j += "\"setup_type\":\"" + JsonEscape(r.setup_type) + "\",";
      j += "\"setup_phase\":\"" + JsonEscape(r.setup_phase) + "\",";
      j += "\"confidence_score\":" + DoubleToJson(r.confidence_score, 1) + ",";
      j += "\"quality_grade\":\"" + JsonEscape(r.quality_grade) + "\",";
      j += "\"entry_zone\":\"" + JsonEscape(r.entry_zone) + "\",";
      j += "\"invalidation\":\"" + JsonEscape(r.invalidation) + "\",";
      j += "\"targets\":\"" + JsonEscape(r.targets) + "\",";
      j += "\"recommendation\":\"" + JsonEscape(r.recommendation) + "\",";
      j += "\"technical_narrative\":\"" + JsonEscape(r.technical_narrative) + "\",";
      j += "\"reasons_for\":\"" + JsonEscape(r.reasons_for) + "\",";
      j += "\"reasons_against\":\"" + JsonEscape(r.reasons_against) + "\",";
      j += "\"last_alert\":\"" + JsonEscape(r.last_alert) + "\",";
      j += "\"last_alert_time\":" + IntegerToString((long)r.last_alert_time) + ",";
      j += "\"chart_objects_active\":" + (r.chart_objects_active ? "true" : "false") + ",";
      j += "\"eval_bar_m5\":" + IntegerToString((long)r.eval_bar_m5);
      j += "}";
      return j;
     }
  };

#endif
//+------------------------------------------------------------------+
