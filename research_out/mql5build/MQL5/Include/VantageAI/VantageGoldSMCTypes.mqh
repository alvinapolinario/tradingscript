//+------------------------------------------------------------------+
//| VantageGoldSMCTypes.mqh                                          |
//| Gold SMC Intelligence — shared enums and result structs          |
//| Advisory-only — never opens, modifies, or closes trades          |
//+------------------------------------------------------------------+
#ifndef VANTAGE_GOLD_SMC_TYPES_MQH
#define VANTAGE_GOLD_SMC_TYPES_MQH

enum ENUM_SMC_DIRECTION
  {
   SMC_DIR_BULLISH = 1,
   SMC_DIR_BEARISH = -1,
   SMC_DIR_NEUTRAL = 0,
   SMC_DIR_CONFLICTING = 2
  };

enum ENUM_SMC_SETUP_PHASE
  {
   SMC_PHASE_NO_SETUP = 0,
   SMC_PHASE_CONTEXT_FORMING,
   SMC_PHASE_DISABLED_SYMBOL,
   SMC_PHASE_INSUFFICIENT_DATA,
   SMC_PHASE_ENGINE_STUB,
   SMC_PHASE_STRUCTURE_READY,
   SMC_PHASE_LIQUIDITY_MAPPED,      // Phase 3
   SMC_PHASE_POI_MAPPED,            // Phase 4 FVG/OB
   SMC_PHASE_CONTEXT_MAPPED,        // Phase 5 PD / OTE / PO3
   // Phase 6 progressive setup states
   SMC_PHASE_LIQ_APPROACHING,
   SMC_PHASE_LIQ_SWEPT,
   SMC_PHASE_DISP_AWAITED,
   SMC_PHASE_STRUCT_AWAITED,
   SMC_PHASE_POI_IDENTIFIED,
   SMC_PHASE_RETRACE_IN_PROGRESS,
   SMC_PHASE_INSIDE_ENTRY,
   SMC_PHASE_LTF_AWAITED,
   SMC_PHASE_SETUP_CONFIRMED,
   SMC_PHASE_SETUP_MISSED,
   SMC_PHASE_SETUP_INVALIDATED,
   SMC_PHASE_T1_REACHED,
   SMC_PHASE_T2_REACHED,
   SMC_PHASE_T3_REACHED,
   SMC_PHASE_SETUP_COMPLETED
  };

enum ENUM_SMC_PO3_STATE
  {
   SMC_PO3_NONE = 0,
   SMC_PO3_ACCUMULATION,
   SMC_PO3_POSSIBLE_MANIPULATION,
   SMC_PO3_MANIPULATION_CONFIRMED,
   SMC_PO3_DISTRIBUTION,
   SMC_PO3_COMPLETED,
   SMC_PO3_INVALIDATED
  };

enum ENUM_SMC_INDUCEMENT
  {
   SMC_IND_NONE = 0,
   SMC_IND_POSSIBLE,
   SMC_IND_CONFIRMED_SWEEP,
   SMC_IND_UNRESOLVED,
   SMC_IND_INVALID
  };

enum ENUM_SMC_ZONE_STATUS
  {
   SMC_ZONE_FRESH = 0,
   SMC_ZONE_TOUCHED,
   SMC_ZONE_PARTIALLY_MITIGATED,
   SMC_ZONE_FULLY_MITIGATED,
   SMC_ZONE_INVALIDATED,
   SMC_ZONE_FLIPPED
  };

enum ENUM_SMC_LIQ_STATUS
  {
   SMC_LIQ_ACTIVE = 0,
   SMC_LIQ_APPROACHING,
   SMC_LIQ_TESTED,
   SMC_LIQ_PARTIALLY_SWEPT,
   SMC_LIQ_SWEPT,
   SMC_LIQ_INVALIDATED
  };

enum ENUM_SMC_SWEEP_CLASS
  {
   SMC_SWEEP_NONE = 0,
   SMC_SWEEP_WEAK,
   SMC_SWEEP_VALID,
   SMC_SWEEP_STRONG,
   SMC_SWEEP_NO_CONFIRM,
   SMC_SWEEP_WITH_MSS,
   SMC_SWEEP_WITH_DISP,
   SMC_SWEEP_FAILED,
   SMC_SWEEP_TRUE_BREAKOUT
  };

enum ENUM_SMC_STRUCTURE_EVENT
  {
   SMC_EVT_NONE = 0,
   SMC_EVT_INTERNAL_BOS_BULL,
   SMC_EVT_INTERNAL_BOS_BEAR,
   SMC_EVT_EXTERNAL_BOS_BULL,
   SMC_EVT_EXTERNAL_BOS_BEAR,
   SMC_EVT_CHOCH_BULL,
   SMC_EVT_CHOCH_BEAR,
   SMC_EVT_MSS_BULL,
   SMC_EVT_MSS_BEAR,
   SMC_EVT_LIQUIDITY_SWEEP_ONLY,
   SMC_EVT_FAILED_BREAK,
   SMC_EVT_WICK_SWEEP_NO_BOS
  };

enum ENUM_SMC_BREAK_MODE
  {
   SMC_BREAK_WICK = 0,
   SMC_BREAK_BODY_CLOSE = 1,
   SMC_BREAK_BODY_PENETRATION = 2,
   SMC_BREAK_BODY_DISPLACEMENT = 3   // default
  };

struct VantageGoldSMCSwing
  {
   datetime time;
   int      bar_index;     // series index at detection (0=newest closed in copy)
   double   price;
   bool     is_high;
   bool     confirmed;
   bool     external_level;
  };

struct VantageGoldSMCTfStructure
  {
   ENUM_TIMEFRAMES timeframe;
   bool   valid;
   datetime bar_time;
   double close_px;
   double atr;
   // External
   ENUM_SMC_DIRECTION external_bias;
   double ext_swing_high;
   double ext_swing_low;
   double ext_range_high;
   double ext_range_low;
   bool   ext_hh;
   bool   ext_hl;
   bool   ext_lh;
   bool   ext_ll;
   // Internal
   ENUM_SMC_DIRECTION internal_bias;
   double int_swing_high;
   double int_swing_low;
   bool   int_hh;
   bool   int_hl;
   bool   int_lh;
   bool   int_ll;
   // Events (latest confirmed on closed bar)
   ENUM_SMC_STRUCTURE_EVENT last_event;
   bool   bos_bull;
   bool   bos_bear;
   bool   choch_bull;
   bool   choch_bear;
   bool   mss_bull;
   bool   mss_bear;
   bool   wick_sweep_only;
   double displacement_score;   // 0-100
   double broken_level;
   string label;                // human summary
  };

// Compact analysis result for HUD / heartbeat
struct VantageGoldSMCResult
  {
   bool   valid;
   bool   gold_symbol_valid;
   bool   engine_enabled;
   bool   analysis_active;
   string symbol;
   string base_symbol;
   string status_line;
   string disable_reason;
   ENUM_SMC_DIRECTION macro_bias;   // D1
   ENUM_SMC_DIRECTION h4_bias;
   ENUM_SMC_DIRECTION h1_bias;
   ENUM_SMC_DIRECTION m15_bias;
   ENUM_SMC_DIRECTION m5_bias;
   string structure_status;
   string m5_context;               // e.g. Internal bullish correction inside bearish H1
   string latest_structure_event;
   double external_range_high;
   double external_range_low;
   double external_equilibrium;
   string premium_discount;
   // Phase 3 liquidity
   double pdh;
   double pdl;
   double pd_mid;
   double pwh;
   double pwl;
   double pw_mid;
   double cdh;
   double cdl;
   double asian_high;
   double asian_low;
   double london_high;
   double london_low;
   double ny_high;
   double ny_low;
   string nearest_bsl_label;
   string nearest_ssl_label;
   double distance_bsl_atr;
   double distance_ssl_atr;
   string liquidity_draw;
   double draw_distance_atr;
   string latest_liquidity_event;
   string sweep_class;
   string session_name;
   string equal_highs_note;
   string equal_lows_note;
   string displacement_status;
   // Phase 4 POI
   string primary_poi_type;         // FVG / Order Block / Breaker / Mitigation / Inverse FVG
   string primary_poi_dir;          // Bullish / Bearish
   string primary_poi_status;
   double poi_upper;
   double poi_lower;
   double poi_mid;
   double poi_ce;                   // consequent encroachment
   double poi_mitigation_pct;
   double poi_quality;
   string fvg_summary;
   string order_block_summary;
   string breaker_summary;
   bool   has_fresh_fvg;
   bool   has_valid_ob;
   bool   has_breaker;
   bool   has_inverse_fvg;
   // Phase 5 context (premium_discount string reused above)
   double dealing_high;
   double dealing_low;
   double dealing_eq;
   double dealing_pct;              // 0=low .. 100=high
   bool   in_discount;
   bool   in_premium;
   bool   ote_enabled_hit;
   double ote_low;
   double ote_mid;
   double ote_high;
   bool   price_in_ote;
   bool   poi_overlaps_ote;
   string inducement_status;
   string po3_status;
   string po3_bias;                 // Bullish / Bearish / None
   // Phase 6 setup / score
   string setup_direction;          // Bullish / Bearish / Neutral
   string setup_type;
   string setup_candidate;          // classified type even when score below gate
   string setup_phase;
   double confidence_score;
   string confidence_band;          // No Valid / Weak / Developing / …
   string quality_grade;
   string score_breakdown;
   string entry_zone;
   double entry_low;
   double entry_high;
   double preferred_entry;
   string entry_status;             // Far / Approaching / Inside / …
   string zone_source;
   string invalidation;
   double invalidation_price;
   double target_1;
   double target_2;
   double target_3;
   string targets;
   double estimated_rr;
   string recommendation;
   string technical_narrative;
   string reasons_for;
   string reasons_against;
   datetime eval_bar_m5;
   int    engine_phase;             // 8 = polish complete
   double nearest_bsl;
   double nearest_ssl;
   // Phase 7 visual / alerts
   string last_alert;
   datetime last_alert_time;
   bool   chart_objects_active;
  };

struct VantageGoldSMCConfig
  {
   bool   enable;
   string approved_aliases;
   bool   allow_broker_suffix;
   bool   allow_broker_prefix;
   bool   show_nongold_warning;
   bool   show_dashboard;
   bool   show_chart_objects;
   ENUM_TIMEFRAMES tf_macro;
   ENUM_TIMEFRAMES tf_major;
   ENUM_TIMEFRAMES tf_bias;
   ENUM_TIMEFRAMES tf_confirm;
   ENUM_TIMEFRAMES tf_exec;
   ENUM_TIMEFRAMES tf_precision;
   // Phase 2 structure
   int    swing_left_ext;
   int    swing_right_ext;
   int    swing_left_int;
   int    swing_right_int;
   int    structure_lookback;
   int    atr_period;
   ENUM_SMC_BREAK_MODE break_mode;
   double min_close_penetration_atr;  // body must clear level by this * ATR
   double min_displacement_atr;       // body size / ATR for displacement
   double min_displacement_score;     // 0-100 gate for BOS/MSS
   // Phase 3 liquidity / sessions
   int    server_utc_offset_hours;
   int    asian_start_hour_utc;
   int    asian_end_hour_utc;
   int    london_start_hour_utc;
   int    london_end_hour_utc;
   int    ny_start_hour_utc;
   int    ny_end_hour_utc;
   bool   show_session_liquidity;
   bool   show_prev_day_liquidity;
   bool   show_prev_week_liquidity;
   double equal_tol_atr;              // equal H/L tolerance in ATR
   double approach_atr;               // "approaching" distance
   // Phase 4 FVG / OB
   double min_fvg_atr;                // min FVG size vs ATR
   int    max_fvgs;
   int    max_obs;
   bool   fvg_require_displacement;
   bool   ob_require_displacement;
   bool   ob_prefer_sweep_origin;
   bool   enable_inverse_fvg;
   bool   enable_breaker;
   int    ob_refinement_mode;         // 0=full 1=body 2=CE
   // Phase 5 context
   bool   enable_ote;
   double ote_low_pct;                // 0.618
   double ote_mid_pct;                // 0.705
   double ote_high_pct;               // 0.790
   bool   enable_inducement;
   bool   enable_po3;
   double deep_premium_pct;           // e.g. 0.85
   double deep_discount_pct;          // e.g. 0.15
   // Phase 6 scoring (weights as percent; normalized at runtime)
   double min_setup_score;            // below → No Valid SMC Setup
   double w_htf_align;                // 15
   double w_liquidity;                // 12
   double w_displacement;             // 12
   double w_structure;                // 14
   double w_order_block;              // 10
   double w_fvg;                      // 8
   double w_premium_discount;         // 7
   double w_session;                  // 5
   double w_pd_week;                  // 4
   double w_ote;                      // 4
   double w_ltf;                      // 6
   double w_vol_spread;               // 3
   // Phase 7 chart / alerts
   bool   chart_show_range;           // dealing + EQ + PD bands
   bool   chart_show_liquidity;       // BSL/SSL / PDH/PDL / PWH/PWL
   bool   chart_show_sessions;        // Asian/London/NY
   bool   chart_show_poi;             // primary POI rectangle
   bool   chart_show_ote;             // OTE zone
   bool   chart_show_setup;           // entry / invalidation / targets
   bool   chart_show_hlines;          // PDH/BSL/TP/invalidation H-lines (rectangles unaffected)
   int    chart_lookback_bars;        // rectangle horizontal span
   bool   alert_enable;
   bool   alert_popup;
   bool   alert_push;
   bool   alert_sound;
   int    alert_cooldown_sec;
   double alert_min_score;            // score-threshold alert
   double alert_spread_points;        // wide-spread alert (points)
   // Phase 8 polish
   bool   debug_log;                  // verbose [GoldSMC] category logs
  };

string SmcDirectionToString(const ENUM_SMC_DIRECTION d)
  {
   if(d == SMC_DIR_BULLISH) return "Bullish";
   if(d == SMC_DIR_BEARISH) return "Bearish";
   if(d == SMC_DIR_CONFLICTING) return "Conflicting";
   return "Neutral";
  }

string SmcPhaseToString(const ENUM_SMC_SETUP_PHASE p)
  {
   if(p == SMC_PHASE_NO_SETUP) return "No Setup";
   if(p == SMC_PHASE_CONTEXT_FORMING) return "Context Forming";
   if(p == SMC_PHASE_DISABLED_SYMBOL) return "Disabled — Gold Only";
   if(p == SMC_PHASE_INSUFFICIENT_DATA) return "Insufficient Data";
   if(p == SMC_PHASE_ENGINE_STUB) return "Engine Scaffold (Phase 1)";
   if(p == SMC_PHASE_STRUCTURE_READY) return "Structure Mapped — No Full Setup Yet";
   if(p == SMC_PHASE_LIQUIDITY_MAPPED) return "Liquidity Mapped — No Full Setup Yet";
   if(p == SMC_PHASE_POI_MAPPED) return "POI Mapped — Awaiting Setup Confirmation";
   if(p == SMC_PHASE_CONTEXT_MAPPED) return "Context Mapped — Awaiting Setup Score";
   if(p == SMC_PHASE_LIQ_APPROACHING) return "Liquidity Approaching";
   if(p == SMC_PHASE_LIQ_SWEPT) return "Liquidity Swept";
   if(p == SMC_PHASE_DISP_AWAITED) return "Displacement Awaited";
   if(p == SMC_PHASE_STRUCT_AWAITED) return "Structure Confirmation Awaited";
   if(p == SMC_PHASE_POI_IDENTIFIED) return "Point of Interest Identified";
   if(p == SMC_PHASE_RETRACE_IN_PROGRESS) return "Retracement in Progress";
   if(p == SMC_PHASE_INSIDE_ENTRY) return "Price Inside Entry Zone";
   if(p == SMC_PHASE_LTF_AWAITED) return "Lower-Timeframe Confirmation Awaited";
   if(p == SMC_PHASE_SETUP_CONFIRMED) return "Setup Confirmed";
   if(p == SMC_PHASE_SETUP_MISSED) return "Setup Missed";
   if(p == SMC_PHASE_SETUP_INVALIDATED) return "Setup Invalidated";
   if(p == SMC_PHASE_T1_REACHED) return "Target 1 Reached";
   if(p == SMC_PHASE_T2_REACHED) return "Target 2 Reached";
   if(p == SMC_PHASE_T3_REACHED) return "Target 3 Reached";
   if(p == SMC_PHASE_SETUP_COMPLETED) return "Setup Completed";
   return "Unknown";
  }

string SmcGradeFromScore(const double score)
  {
   if(score >= 90.0) return "A+";
   if(score >= 80.0) return "A";
   if(score >= 70.0) return "B";
   if(score >= 60.0) return "C";
   if(score >= 45.0) return "D";
   return "Invalid";
  }

string SmcConfidenceBand(const double score)
  {
   if(score < 30.0) return "No Valid Setup";
   if(score < 50.0) return "Weak";
   if(score < 65.0) return "Developing";
   if(score < 75.0) return "Moderate";
   if(score < 85.0) return "Strong";
   return "Exceptional";
  }

string SmcPo3ToString(const ENUM_SMC_PO3_STATE s)
  {
   if(s == SMC_PO3_ACCUMULATION) return "Accumulation forming";
   if(s == SMC_PO3_POSSIBLE_MANIPULATION) return "Possible manipulation";
   if(s == SMC_PO3_MANIPULATION_CONFIRMED) return "Manipulation confirmed";
   if(s == SMC_PO3_DISTRIBUTION) return "Distribution active";
   if(s == SMC_PO3_COMPLETED) return "PO3 completed";
   if(s == SMC_PO3_INVALIDATED) return "PO3 invalidated";
   return "No valid PO3";
  }

string SmcInducementToString(const ENUM_SMC_INDUCEMENT s)
  {
   if(s == SMC_IND_POSSIBLE) return "Possible inducement";
   if(s == SMC_IND_CONFIRMED_SWEEP) return "Confirmed inducement sweep";
   if(s == SMC_IND_UNRESOLVED) return "Unresolved inducement";
   if(s == SMC_IND_INVALID) return "Invalid inducement hypothesis";
   return "None";
  }

string SmcZoneStatusToString(const ENUM_SMC_ZONE_STATUS z)
  {
   if(z == SMC_ZONE_FRESH) return "Fresh";
   if(z == SMC_ZONE_TOUCHED) return "Touched";
   if(z == SMC_ZONE_PARTIALLY_MITIGATED) return "Partially mitigated";
   if(z == SMC_ZONE_FULLY_MITIGATED) return "Fully mitigated";
   if(z == SMC_ZONE_INVALIDATED) return "Invalidated";
   if(z == SMC_ZONE_FLIPPED) return "Flipped / Inverse";
   return "Unknown";
  }

string SmcSweepClassToString(const ENUM_SMC_SWEEP_CLASS c)
  {
   if(c == SMC_SWEEP_WEAK) return "Weak sweep";
   if(c == SMC_SWEEP_VALID) return "Valid sweep";
   if(c == SMC_SWEEP_STRONG) return "Strong sweep";
   if(c == SMC_SWEEP_NO_CONFIRM) return "Sweep without confirmation";
   if(c == SMC_SWEEP_WITH_MSS) return "Sweep followed by MSS";
   if(c == SMC_SWEEP_WITH_DISP) return "Sweep followed by displacement";
   if(c == SMC_SWEEP_FAILED) return "Failed sweep";
   if(c == SMC_SWEEP_TRUE_BREAKOUT) return "True breakout rather than sweep";
   return "None";
  }

string SmcEventToString(const ENUM_SMC_STRUCTURE_EVENT e)
  {
   if(e == SMC_EVT_INTERNAL_BOS_BULL) return "Internal BOS Bullish";
   if(e == SMC_EVT_INTERNAL_BOS_BEAR) return "Internal BOS Bearish";
   if(e == SMC_EVT_EXTERNAL_BOS_BULL) return "External BOS Bullish";
   if(e == SMC_EVT_EXTERNAL_BOS_BEAR) return "External BOS Bearish";
   if(e == SMC_EVT_CHOCH_BULL) return "CHoCH Bullish";
   if(e == SMC_EVT_CHOCH_BEAR) return "CHoCH Bearish";
   if(e == SMC_EVT_MSS_BULL) return "MSS Bullish";
   if(e == SMC_EVT_MSS_BEAR) return "MSS Bearish";
   if(e == SMC_EVT_WICK_SWEEP_NO_BOS) return "Wick Sweep (not BOS)";
   if(e == SMC_EVT_FAILED_BREAK) return "Failed Break";
   if(e == SMC_EVT_LIQUIDITY_SWEEP_ONLY) return "Liquidity Sweep Only";
   return "None";
  }

#endif
//+------------------------------------------------------------------+
