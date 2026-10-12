//+------------------------------------------------------------------+
//| VantageLiquidityGrabTypes.mqh                                    |
//| Liquidity Grab Detection — shared types (Gold / XAUUSD)         |
//| Advisory-only — never opens, modifies, or closes trades         |
//+------------------------------------------------------------------+
#ifndef VANTAGE_LIQUIDITY_GRAB_TYPES_MQH
#define VANTAGE_LIQUIDITY_GRAB_TYPES_MQH

#define VANTAGE_LIQGRAB_VERSION "1.0"
#define VANTAGE_LIQGRAB_DISABLE_MSG \
  "Liquidity Grab Monitor is disabled. Supported pairs: XAUUSD, EURUSD, USDJPY."
#define LG_MAX_LEVELS 48
#define LG_MAX_CANDIDATES 8
#define LG_MAX_EVIDENCE 16

enum ENUM_LG_STATUS
  {
   LG_STATUS_NO_VALID_SETUP = 0,
   LG_STATUS_APPROACH,
   LG_STATUS_TEST,
   LG_STATUS_SWEEP_UNCONFIRMED,
   LG_STATUS_GRAB_CONFIRMED,
   LG_STATUS_HIGH_CONFIDENCE,
   LG_STATUS_GENUINE_BREAKOUT,
   LG_STATUS_FAILED_SWEEP
  };

enum ENUM_LG_STATE
  {
   LG_STATE_IDLE = 0,
   LG_STATE_APPROACHING,
   LG_STATE_SWEPT,
   LG_STATE_REJECTED,
   LG_STATE_DISPLACEMENT,
   LG_STATE_MSS,
   LG_STATE_CONFIRMED,
   LG_STATE_BREAKOUT,
   LG_STATE_FAILED
  };

enum ENUM_LG_DIRECTION
  {
   LG_DIR_NONE = 0,
   LG_DIR_BUY_SIDE_GRAB_BEARISH,   // swept highs → bearish reversal
   LG_DIR_SELL_SIDE_GRAB_BULLISH   // swept lows → bullish reversal
  };

enum ENUM_LG_LEVEL_TYPE
  {
   LG_LVL_UNKNOWN = 0,
   LG_LVL_ASIAN_HIGH, LG_LVL_ASIAN_LOW,
   LG_LVL_LONDON_HIGH, LG_LVL_LONDON_LOW,
   LG_LVL_NY_HIGH, LG_LVL_NY_LOW,
   LG_LVL_PDH, LG_LVL_PDL, LG_LVL_PWH, LG_LVL_PWL,
   LG_LVL_CDH, LG_LVL_CDL,
   LG_LVL_SWING_HIGH, LG_LVL_SWING_LOW,
   LG_LVL_EQUAL_HIGH, LG_LVL_EQUAL_LOW,
   LG_LVL_RANGE_HIGH, LG_LVL_RANGE_LOW,
   LG_LVL_EMA20, LG_LVL_EMA50, LG_LVL_EMA200
  };

enum ENUM_LG_HTF_BIAS
  {
   LG_HTF_STRONGLY_BULLISH = 0,
   LG_HTF_BULLISH,
   LG_HTF_NEUTRAL,
   LG_HTF_BEARISH,
   LG_HTF_STRONGLY_BEARISH,
   LG_HTF_CONFLICTING
  };

enum ENUM_LG_MSS_TYPE
  {
   LG_MSS_NONE = 0,
   LG_MSS_INTERNAL,
   LG_MSS_EXTERNAL
  };

enum ENUM_LG_VOLUME_CLASS
  {
   LG_VOL_LOW = 0,
   LG_VOL_NORMAL,
   LG_VOL_ELEVATED,
   LG_VOL_SPIKE
  };

struct VantageLiquidityGrabLevel
  {
   string id;
   ENUM_LG_LEVEL_TYPE type;
   string type_label;
   double price;
   bool   is_bsl;              // buy-side liquidity (above)
   ENUM_TIMEFRAMES source_tf;
   datetime created;
   datetime last_test;
   int    touch_count;
   bool   swept;
   bool   active;
   double strength;
   string session_tag;
   datetime expires;
  };

struct VantageLiquidityGrabCandidate
  {
   string id;
   ENUM_LG_STATE state;
   ENUM_LG_STATUS status;
   ENUM_LG_DIRECTION direction;
   string level_id;
   ENUM_LG_LEVEL_TYPE level_type;
   double level_price;
   double sweep_price;
   double sweep_distance;
   double sweep_distance_atr;
   double rejection_close;
   double wick_ratio;
   bool   close_back_inside;
   bool   displacement_detected;
   double displacement_strength;
   bool   mss_detected;
   ENUM_LG_MSS_TYPE mss_type;
   double mss_level;
   bool   fvg_detected;
   double volume_ratio;
   ENUM_LG_VOLUME_CLASS volume_class;
   datetime start_time;
   datetime confirm_time;
   datetime expiry_time;
   int    bars_in_state;
   int    confirmation_bars_left;
   double score;
   string invalidation_reason;
   string evidence[LG_MAX_EVIDENCE];
   int    evidence_count;
   string warnings[8];
   int    warning_count;
  };

struct VantageLiquidityGrabConfig
  {
   bool   enable;
   bool   gold_only;
   string approved_aliases;
   bool   allow_broker_suffix;
   bool   allow_broker_prefix;
   ENUM_TIMEFRAMES tf_detect;       // M5
   ENUM_TIMEFRAMES tf_confirm;      // M5
   ENUM_TIMEFRAMES tf_confirm2;     // M15
   ENUM_TIMEFRAMES tf_context;      // H1
   ENUM_TIMEFRAMES tf_major;        // H4
   int    swing_left;
   int    swing_right;
   int    atr_period;
   double min_sweep_atr;
   double max_sweep_atr;
   double spread_mult;
   double equal_level_atr_mult;
   double min_equal_touches;
   double approach_atr;
   double disp_body_atr;
   double strong_disp_atr;
   double min_wick_ratio;
   double min_wick_body_ratio;
   bool   require_close_back;
   int    rejection_confirm_bars;
   bool   require_mss;
   bool   require_close_mss;
   int    mss_confirm_bars;
   bool   allow_internal_mss;
   double external_mss_bonus;
   bool   enable_pdh_pdl;
   bool   enable_pwh_pwl;
   bool   enable_session;
   bool   enable_swing;
   bool   enable_equal;
   int    level_max_age_bars;
   double min_level_strength;
   int    server_utc_offset_hours;
   int    asian_start_utc, asian_end_utc;
   int    london_start_utc, london_end_utc;
   int    ny_start_utc, ny_end_utc;
   bool   session_confluence;
   bool   enable_tick_volume;
   int    volume_avg_period;
   double elevated_volume_ratio;
   double confirmed_threshold;
   double high_conf_threshold;
   double countertrend_penalty;
   double news_penalty;
   int    news_before_min;
   int    news_after_min;
   int    confirm_window_bars;
   bool   alert_enable;
   bool   alert_popup;
   bool   alert_push;
   bool   alert_sound;
   int    alert_cooldown_sec;
   bool   show_chart_objects;
   bool   show_hlines;              // liquidity/MSS H-lines (labels/arrows unaffected)
   bool   show_dashboard;
   int    chart_retention_bars;
   bool   debug_log;
  };

struct VantageLiquidityGrabResult
  {
   bool   valid;
   bool   gold_symbol_valid;
   bool   engine_enabled;
   bool   analysis_active;
   string symbol;
   string base_symbol;
   string status_line;
   string disable_reason;
   ENUM_TIMEFRAMES detection_tf;
   ENUM_TIMEFRAMES confirmation_tf;
   ENUM_TIMEFRAMES higher_tf;
   ENUM_LG_DIRECTION direction;
   ENUM_LG_STATUS status;
   ENUM_LG_STATE machine_state;
   double confidence_score;
   string liquidity_level_id;
   string liquidity_level_type;
   double liquidity_level_price;
   double sweep_price;
   double sweep_distance;
   double sweep_distance_atr;
   double rejection_close_price;
   double wick_ratio;
   bool   displacement_detected;
   double displacement_strength;
   bool   mss_detected;
   string mss_type;
   double mss_level;
   bool   fvg_detected;
   double volume_ratio;
   string session_name;
   string higher_timeframe_bias;
   string ema_alignment;
   bool   is_countertrend;
   bool   news_restricted;
   double spread_at_detection;
   datetime candidate_start_time;
   datetime confirmation_time;
   datetime expiry_time;
   string invalidation_reason;
   string evidence_json;          // semicolon-separated for JSON
   string warnings_json;
   double nearest_opposing_liquidity;
   string nearest_opposing_label;
   double invalidation_level;
   string recommendation;
   string technical_narrative;
   string action_guidance;
   int    setup_age_bars;
   int    confirmation_countdown;
   string last_alert;
   datetime last_alert_time;
   bool   chart_objects_active;
   datetime eval_bar_m5;
   int    engine_phase;
  };

string LgStatusToString(const ENUM_LG_STATUS s)
  {
   if(s == LG_STATUS_APPROACH) return "LIQUIDITY_APPROACH";
   if(s == LG_STATUS_TEST) return "LIQUIDITY_TEST";
   if(s == LG_STATUS_SWEEP_UNCONFIRMED) return "LIQUIDITY_SWEEP_UNCONFIRMED";
   if(s == LG_STATUS_GRAB_CONFIRMED) return "LIQUIDITY_GRAB_CONFIRMED";
   if(s == LG_STATUS_HIGH_CONFIDENCE) return "HIGH_CONFIDENCE_LIQUIDITY_GRAB";
   if(s == LG_STATUS_GENUINE_BREAKOUT) return "GENUINE_BREAKOUT";
   if(s == LG_STATUS_FAILED_SWEEP) return "FAILED_SWEEP";
   return "NO_VALID_SETUP";
  }

string LgStateToString(const ENUM_LG_STATE s)
  {
   if(s == LG_STATE_APPROACHING) return "APPROACHING";
   if(s == LG_STATE_SWEPT) return "SWEPT";
   if(s == LG_STATE_REJECTED) return "REJECTED";
   if(s == LG_STATE_DISPLACEMENT) return "DISPLACEMENT_CONFIRMED";
   if(s == LG_STATE_MSS) return "MSS_CONFIRMED";
   if(s == LG_STATE_CONFIRMED) return "CONFIRMED";
   if(s == LG_STATE_BREAKOUT) return "GENUINE_BREAKOUT";
   if(s == LG_STATE_FAILED) return "FAILED_OR_EXPIRED";
   return "IDLE";
  }

string LgDirectionToString(const ENUM_LG_DIRECTION d)
  {
   if(d == LG_DIR_BUY_SIDE_GRAB_BEARISH) return "BUY_SIDE_GRAB_BEARISH_REVERSAL";
   if(d == LG_DIR_SELL_SIDE_GRAB_BULLISH) return "SELL_SIDE_GRAB_BULLISH_REVERSAL";
   return "NONE";
  }

string LgLevelTypeToString(const ENUM_LG_LEVEL_TYPE t)
  {
   if(t == LG_LVL_ASIAN_HIGH) return "ASIAN_HIGH";
   if(t == LG_LVL_ASIAN_LOW) return "ASIAN_LOW";
   if(t == LG_LVL_LONDON_HIGH) return "LONDON_HIGH";
   if(t == LG_LVL_LONDON_LOW) return "LONDON_LOW";
   if(t == LG_LVL_NY_HIGH) return "NEW_YORK_HIGH";
   if(t == LG_LVL_NY_LOW) return "NEW_YORK_LOW";
   if(t == LG_LVL_PDH) return "PDH";
   if(t == LG_LVL_PDL) return "PDL";
   if(t == LG_LVL_PWH) return "PWH";
   if(t == LG_LVL_PWL) return "PWL";
   if(t == LG_LVL_CDH) return "CDH";
   if(t == LG_LVL_CDL) return "CDL";
   if(t == LG_LVL_SWING_HIGH) return "SWING_HIGH";
   if(t == LG_LVL_SWING_LOW) return "SWING_LOW";
   if(t == LG_LVL_EQUAL_HIGH) return "EQUAL_HIGHS";
   if(t == LG_LVL_EQUAL_LOW) return "EQUAL_LOWS";
   if(t == LG_LVL_RANGE_HIGH) return "RANGE_HIGH";
   if(t == LG_LVL_RANGE_LOW) return "RANGE_LOW";
   if(t == LG_LVL_EMA20) return "EMA20";
   if(t == LG_LVL_EMA50) return "EMA50";
   if(t == LG_LVL_EMA200) return "EMA200";
   return "UNKNOWN";
  }

string LgHtfBiasToString(const ENUM_LG_HTF_BIAS b)
  {
   if(b == LG_HTF_STRONGLY_BULLISH) return "STRONGLY_BULLISH";
   if(b == LG_HTF_BULLISH) return "BULLISH";
   if(b == LG_HTF_BEARISH) return "BEARISH";
   if(b == LG_HTF_STRONGLY_BEARISH) return "STRONGLY_BEARISH";
   if(b == LG_HTF_CONFLICTING) return "CONFLICTING";
   return "NEUTRAL";
  }

#endif
//+------------------------------------------------------------------+
