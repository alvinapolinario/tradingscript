//+------------------------------------------------------------------+
//| VantageMacroBridge.mq5                                           |
//| Standalone EA — syncs MT5 economic calendar to FastAPI market news |
//| POST /api/v1/market-news/mt5-calendar (Bearer LOCAL_API_TOKEN)   |
//| No trading — advisory data feed only.                            |
//+------------------------------------------------------------------+
#property copyright "Vantage Macro Bridge"
#property version   "1.00"
#property description "MT5 economic calendar → FastAPI market news ingest"
#property strict

#include <VantageAI/VantageMacroBridge.mqh>

//--- A. Connection
input group "A. Connection"
input string InpBackendUrl        = "http://187.77.142.118:8000";
input string InpApiToken          = "";
input int    InpPollSeconds       = 300;
input int    InpRequestTimeoutMs  = 12000;

//--- B. Calendar window
input group "B. Calendar window"
input int    InpLookbackHours     = 6;
input int    InpLookaheadDays     = 7;
input int    InpMinImportance     = 2;   // 1=LOW, 2=MEDIUM, 3=HIGH only
input string InpCurrencies        = "USD,EUR,GBP,JPY,AUD,NZD,CAD,CHF";

//--- C. Logging
input group "C. Logging"
input bool   InpDebugLog          = true;
input bool   InpPostOnInit        = true;

CVantageMacroBridge g_bridge;
int                 g_timer_sec = 0;
string              g_last_status = "Starting…";

void UpdateChartComment(const string line2 = "")
  {
   string txt = "Vantage Macro Bridge v" + VANTAGE_MACRO_BRIDGE_VERSION + "\n";
   txt += g_last_status;
   if(line2 != "")
      txt += "\n" + line2;
   Comment(txt);
  }

bool PushCalendar(const bool force_log)
  {
   VantageMacroBridgeResult res;
   if(!g_bridge.SendCalendar(res))
     {
      g_last_status = "FAIL: " + g_bridge.LastError();
      if(force_log || InpDebugLog)
         Print("[MacroBridge] ", g_last_status, " http=", g_bridge.LastHttp());
      UpdateChartComment("Check WebRequest allowlist + LOCAL_API_TOKEN");
      return false;
     }

   if(res.event_count <= 0)
      g_last_status = "OK — no events in window";
   else
      g_last_status = StringFormat("OK — %d events | +%d ~%d =%d",
                                   res.event_count, res.inserted, res.updated, res.unchanged);

   if(force_log || InpDebugLog)
      Print("[MacroBridge] ", g_last_status);

   UpdateChartComment(TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS));
   return true;
  }

int OnInit()
  {
   if(StringLen(InpApiToken) < 8)
     {
      Print("[MacroBridge] Set InpApiToken to backend LOCAL_API_TOKEN.");
      return INIT_PARAMETERS_INCORRECT;
     }

   VantageMacroBridgeConfig cfg;
   cfg.backend_url = InpBackendUrl;
   cfg.bearer_token = InpApiToken;
   cfg.timeout_ms = MathMax(3000, InpRequestTimeoutMs);
   cfg.poll_seconds = MathMax(60, InpPollSeconds);
   cfg.lookback_hours = MathMax(1, InpLookbackHours);
   cfg.lookahead_days = MathMax(1, InpLookaheadDays);
   cfg.min_importance = MathMax(1, MathMin(3, InpMinImportance));
   cfg.currencies_csv = InpCurrencies;
   cfg.debug_log = InpDebugLog;
   g_bridge.Configure(cfg);

   if(!g_bridge.CalendarAvailable())
     {
      Print("[MacroBridge] MT5 economic calendar unavailable on this terminal/broker.");
      g_last_status = "Calendar unavailable — check broker calendar subscription";
      UpdateChartComment();
     }
   else if(InpPostOnInit)
      PushCalendar(true);

   g_timer_sec = cfg.poll_seconds;
   EventSetTimer(g_timer_sec);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   Comment("");
  }

void OnTimer()
  {
   PushCalendar(false);
  }

void OnTick()
  {
   // Timer-driven only — no per-tick work.
  }

//+------------------------------------------------------------------+
