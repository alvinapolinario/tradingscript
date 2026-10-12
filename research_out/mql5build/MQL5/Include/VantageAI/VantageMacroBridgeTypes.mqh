//+------------------------------------------------------------------+
//| VantageMacroBridgeTypes.mqh                                      |
//| Economic calendar bridge types — MT5 → FastAPI market news        |
//+------------------------------------------------------------------+
#ifndef VANTAGE_MACRO_BRIDGE_TYPES_MQH
#define VANTAGE_MACRO_BRIDGE_TYPES_MQH

#define VANTAGE_MACRO_BRIDGE_VERSION "1.0.0"
#define VANTAGE_MACRO_MAX_EVENTS     256

struct VantageMacroBridgeConfig
  {
   string backend_url;
   string bearer_token;
   int    timeout_ms;
   int    poll_seconds;
   int    lookback_hours;
   int    lookahead_days;
   int    min_importance;      // 1=LOW, 2=MEDIUM, 3=HIGH
   string currencies_csv;
   bool   debug_log;
  };

struct VantageMacroCalendarEvent
  {
   string   external_event_id;
   string   currency;
   string   country;
   string   event_name;
   string   importance;
   string   category;
   string   scheduled_at;
   double   previous;
   double   forecast;
   double   actual;
   bool     has_previous;
   bool     has_forecast;
   bool     has_actual;
   string   status;
   datetime event_time;
  };

struct VantageMacroBridgeResult
  {
   bool   ok;
   int    http_code;
   string error;
   int    event_count;
   int    inserted;
   int    updated;
   int    unchanged;
   string response_body;
  };

#endif
//+------------------------------------------------------------------+
