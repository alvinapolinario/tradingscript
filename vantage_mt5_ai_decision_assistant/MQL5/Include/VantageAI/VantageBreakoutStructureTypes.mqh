//+------------------------------------------------------------------+
//| VantageBreakoutStructureTypes.mqh                                |
//| Breakout Structure Intelligence Engine — shared types (Gold)     |
//| Advisory-only — never opens, modifies, or closes trades          |
//+------------------------------------------------------------------+
#ifndef VANTAGE_BREAKOUT_STRUCTURE_TYPES_MQH
#define VANTAGE_BREAKOUT_STRUCTURE_TYPES_MQH

#define VANTAGE_BOS_VERSION "1.0"
#define VANTAGE_BOS_DISABLE_MSG \
  "Breakout Structure Engine is disabled. This module supports XAUUSD/Gold only."
#define BOS_MAX_SWINGS 32
#define BOS_MAX_TL 4

enum ENUM_BOS_STRUCTURE
  {
   BOS_STRUCT_NEUTRAL = 0,
   BOS_STRUCT_BULLISH,      // HH + HL
   BOS_STRUCT_BEARISH,      // LH + LL
   BOS_STRUCT_CONFLICTING
  };

enum ENUM_BOS_BOS_CLASS
  {
   BOS_BOS_NONE = 0,
   BOS_BOS_BULLISH,
   BOS_BOS_BEARISH,
   BOS_BOS_WEAK,
   BOS_BOS_INVALID
  };

enum ENUM_BOS_CHOCH_CLASS
  {
   BOS_CHOCH_NONE = 0,
   BOS_CHOCH_BULLISH,
   BOS_CHOCH_BEARISH
  };

enum ENUM_BOS_TL_TYPE
  {
   BOS_TL_NONE = 0,
   BOS_TL_BULLISH,           // connects higher lows
   BOS_TL_BEARISH            // connects lower highs
  };

enum ENUM_BOS_BREAK_CLASS
  {
   BOS_BREAK_NONE = 0,
   BOS_BREAK_WEAK,
   BOS_BREAK_STRONG,
   BOS_BREAK_FAKE,
   BOS_BREAK_INSTITUTIONAL
  };

enum ENUM_BOS_RETEST_STATUS
  {
   BOS_RETEST_NONE = 0,
   BOS_RETEST_PENDING,
   BOS_RETEST_SUCCESS,
   BOS_RETEST_FAILED
  };

enum ENUM_BOS_FLIP_STATUS
  {
   BOS_FLIP_NONE = 0,
   BOS_FLIP_VALID,
   BOS_FLIP_WEAK,
   BOS_FLIP_FAILED
  };

enum ENUM_BOS_GRADE
  {
   BOS_GRADE_REJECT = 0,
   BOS_GRADE_B,
   BOS_GRADE_B_PLUS,
   BOS_GRADE_A,
   BOS_GRADE_A_PLUS,
   BOS_GRADE_INSTITUTIONAL
  };

struct VantageBosSwing
  {
   double   price;
   datetime time;
   int      bar_index;
   double   atr;
   double   strength;        // 0-100
   bool     is_high;
   string   label;           // HH HL LH LL
  };

struct VantageBosTrendline
  {
   ENUM_BOS_TL_TYPE type;
   double   price1;
   double   price2;
   datetime time1;
   datetime time2;
   double   slope;           // price per second
   double   angle_deg;
   int      touches;
   double   avg_distance;
   double   strength;        // 0-100
   bool     active;
  };

struct VantageBosConfig
  {
   bool   enable;
   bool   gold_only;
   string approved_aliases;
   bool   allow_broker_suffix;
   bool   allow_broker_prefix;
   ENUM_TIMEFRAMES tf_primary_h4;
   ENUM_TIMEFRAMES tf_primary_h1;
   ENUM_TIMEFRAMES tf_primary_m15;
   ENUM_TIMEFRAMES tf_entry_m5;
   ENUM_TIMEFRAMES tf_entry_m1;
   int    swing_left;
   int    swing_right;
   double min_swing_strength;
   int    atr_period;
   double min_bos_atr;
   double min_body_pct;
   double min_break_atr;
   double min_body_break_pct;
   int    min_tl_touches;
   double tl_touch_atr;
   double min_tl_strength;
   int    retest_max_bars;
   double retest_tolerance_atr;
   double w_structure;
   double w_trendline;
   double w_breakout;
   double w_retest;
   double w_flip;
   double w_liquidity;
   double w_fvg;
   double w_ob;
   double w_htf;
   double w_session;
   double reject_threshold;
   bool   show_chart;
   bool   show_dashboard;
   bool   alert_enable;
   int    alert_cooldown_sec;
   bool   debug_log;
  };

struct VantageBosMlOutput
  {
   double prob_success;
   double prob_failure;
   double confidence;
   double expected_follow_through;
   string feature_summary;
  };

struct VantageBosResult
  {
   bool   valid;
   bool   gold_symbol_valid;
   bool   engine_enabled;
   bool   analysis_active;
   string symbol;
   string base_symbol;
   string status_line;
   string disable_reason;
   ENUM_BOS_STRUCTURE market_structure_h4;
   ENUM_BOS_STRUCTURE market_structure_h1;
   ENUM_BOS_STRUCTURE market_structure_m15;
   string market_structure_label;
   ENUM_BOS_BOS_CLASS bos_class;
   ENUM_BOS_CHOCH_CLASS choch_class;
   string latest_bos_event;
   string latest_choch_event;
   ENUM_BOS_TL_TYPE trendline_type;
   double trendline_strength;
   double trendline_slope;
   double trendline_angle;
   int    trendline_touches;
   ENUM_BOS_BREAK_CLASS breakout_status;
   string breakout_label;
   ENUM_BOS_RETEST_STATUS retest_status;
   string retest_label;
   ENUM_BOS_FLIP_STATUS sbr_status;
   ENUM_BOS_FLIP_STATUS rbs_status;
   string sbr_label;
   string rbs_label;
   double confidence_score;
   ENUM_BOS_GRADE signal_grade;
   string grade_label;
   double institutional_probability;
   VantageBosMlOutput ml;
   string score_breakdown;
   string recommendation;
   string technical_narrative;
   double invalidation_price;
   double nearest_support;
   double nearest_resistance;
   string session_name;
   bool   htf_aligned;
   datetime eval_bar_m5;
   string last_alert;
   datetime last_alert_time;
   bool   chart_objects_active;
   int    engine_phase;
  };

string BosStructureToString(const ENUM_BOS_STRUCTURE s)
  {
   if(s == BOS_STRUCT_BULLISH) return "Bullish (HH/HL)";
   if(s == BOS_STRUCT_BEARISH) return "Bearish (LH/LL)";
   if(s == BOS_STRUCT_CONFLICTING) return "Conflicting";
   return "Neutral";
  }

string BosBosClassToString(const ENUM_BOS_BOS_CLASS c)
  {
   if(c == BOS_BOS_BULLISH) return "Bullish BOS";
   if(c == BOS_BOS_BEARISH) return "Bearish BOS";
   if(c == BOS_BOS_WEAK) return "Weak BOS";
   if(c == BOS_BOS_INVALID) return "Invalid BOS";
   return "None";
  }

string BosBreakClassToString(const ENUM_BOS_BREAK_CLASS c)
  {
   if(c == BOS_BREAK_WEAK) return "Weak Breakout";
   if(c == BOS_BREAK_STRONG) return "Strong Breakout";
   if(c == BOS_BREAK_FAKE) return "Fake Breakout";
   if(c == BOS_BREAK_INSTITUTIONAL) return "Institutional Breakout";
   return "None";
  }

string BosRetestToString(const ENUM_BOS_RETEST_STATUS s)
  {
   if(s == BOS_RETEST_PENDING) return "Retest Pending";
   if(s == BOS_RETEST_SUCCESS) return "Retest Confirmed";
   if(s == BOS_RETEST_FAILED) return "Retest Failed";
   return "No Retest";
  }

string BosFlipToString(const ENUM_BOS_FLIP_STATUS s)
  {
   if(s == BOS_FLIP_VALID) return "Valid";
   if(s == BOS_FLIP_WEAK) return "Weak";
   if(s == BOS_FLIP_FAILED) return "Failed";
   return "None";
  }

string BosGradeToString(const ENUM_BOS_GRADE g)
  {
   if(g == BOS_GRADE_INSTITUTIONAL) return "Institutional Grade";
   if(g == BOS_GRADE_A_PLUS) return "A+";
   if(g == BOS_GRADE_A) return "A";
   if(g == BOS_GRADE_B_PLUS) return "B+";
   if(g == BOS_GRADE_B) return "B";
   return "Reject";
  }

#endif
