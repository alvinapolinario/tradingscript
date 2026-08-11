//+------------------------------------------------------------------+
//| VantageMacroBridge.mqh                                           |
//| Query MT5 economic calendar and POST to /api/v1/market-news/     |
//+------------------------------------------------------------------+
#ifndef VANTAGE_MACRO_BRIDGE_MQH
#define VANTAGE_MACRO_BRIDGE_MQH

#include "VantageMacroBridgeTypes.mqh"
#include "VantageTypes.mqh"

class CVantageMacroBridge
  {
private:
   VantageMacroBridgeConfig m_cfg;
   string m_last_error;
   int    m_last_http;
   datetime m_last_post;

   string TrimRightSlash(string u)
     {
      while(StringLen(u) > 0 && StringGetCharacter(u, StringLen(u) - 1) == '/')
         u = StringSubstr(u, 0, StringLen(u) - 1);
      return u;
     }

   bool CalendarValueIsSet(const long v) const
     {
      return (v != LONG_MIN);
     }

   double CalendarValueToDouble(const long v) const
     {
      if(!CalendarValueIsSet(v))
         return 0.0;
      return (double)v / 1000000.0;
     }

   string ImportanceToString(const ENUM_CALENDAR_EVENT_IMPORTANCE imp) const
     {
      if(imp >= CALENDAR_IMPORTANCE_HIGH)
         return "HIGH";
      if(imp >= CALENDAR_IMPORTANCE_MODERATE)
         return "MEDIUM";
      return "LOW";
     }

   int ImportanceRank(const ENUM_CALENDAR_EVENT_IMPORTANCE imp) const
     {
      if(imp >= CALENDAR_IMPORTANCE_HIGH)
         return 3;
      if(imp >= CALENDAR_IMPORTANCE_MODERATE)
         return 2;
      if(imp >= CALENDAR_IMPORTANCE_LOW)
         return 1;
      return 0;
     }

   string CategoryFromEventName(const string name) const
     {
      string u = name;
      StringToUpper(u);
      if(StringFind(u, "CPI") >= 0 || StringFind(u, "INFLATION") >= 0 || StringFind(u, "PCE") >= 0)
         return "CPI_INFLATION";
      if(StringFind(u, "INTEREST RATE") >= 0 || StringFind(u, "RATE DECISION") >= 0)
         return "INTEREST_RATE";
      if(StringFind(u, "NFP") >= 0 || StringFind(u, "NONFARM") >= 0 || StringFind(u, "EMPLOYMENT") >= 0 || StringFind(u, "JOBLESS") >= 0)
         return "EMPLOYMENT";
      if(StringFind(u, "GDP") >= 0)
         return "GDP";
      if(StringFind(u, "PMI") >= 0)
         return "PMI";
      if(StringFind(u, "RETAIL") >= 0)
         return "RETAIL_SALES";
      if(StringFind(u, "TRADE BALANCE") >= 0)
         return "TRADE_BALANCE";
      if(StringFind(u, "FOMC") >= 0 || StringFind(u, "ECB") >= 0 || StringFind(u, "BOJ") >= 0 ||
         StringFind(u, "BOE") >= 0 || StringFind(u, "CENTRAL BANK") >= 0 || StringFind(u, "POLICY") >= 0)
         return "CENTRAL_BANK";
      return "OTHER";
     }

   string UtcIso8601(const datetime t) const
     {
      MqlDateTime dt;
      TimeToStruct(t, dt);
      return StringFormat("%04d-%02d-%02dT%02d:%02d:%02dZ", dt.year, dt.mon, dt.day, dt.hour, dt.min, dt.sec);
     }

   bool ExtractJsonInt(const string json, const string key, int &out_v)
     {
      string pat = "\"" + key + "\"";
      int p = StringFind(json, pat);
      if(p < 0) return false;
      int colon = StringFind(json, ":", p);
      if(colon < 0) return false;
      int i = colon + 1;
      while(i < StringLen(json))
        {
         ushort ch = StringGetCharacter(json, i);
         if(ch == ' ' || ch == '\t' || ch == '\r' || ch == '\n')
           { i++; continue; }
         break;
        }
      int j = i;
      if(j < StringLen(json) && StringGetCharacter(json, j) == '-')
         j++;
      while(j < StringLen(json))
        {
         ushort ch = StringGetCharacter(json, j);
         if(ch < '0' || ch > '9')
            break;
         j++;
        }
      if(j <= i)
         return false;
      out_v = (int)StringToInteger(StringSubstr(json, i, j - i));
      return true;
     }

   int SplitCsv(const string csv, string &out[])
     {
      ArrayResize(out, 0);
      string parts[];
      int n = StringSplit(csv, ',', parts);
      int count = 0;
      for(int i = 0; i < n; i++)
        {
         string c = parts[i];
         StringTrimLeft(c);
         StringTrimRight(c);
         StringToUpper(c);
         if(StringLen(c) != 3)
            continue;
         ArrayResize(out, count + 1);
         out[count++] = c;
        }
      return count;
     }

   bool EventKeyExists(const string key, string &keys[], const int key_count) const
     {
      for(int i = 0; i < key_count; i++)
         if(keys[i] == key)
            return true;
      return false;
     }

   bool FetchCurrencyEvents(const string currency, const datetime from_t, const datetime to_t,
                            VantageMacroCalendarEvent &events[], int &event_count,
                            string &keys[], int &key_count)
     {
      MqlCalendarValue values[];
      ResetLastError();
      int n = CalendarValueHistory(values, from_t, to_t, NULL, currency);
      if(n < 0)
        {
         int err = GetLastError();
         if(m_cfg.debug_log)
            Print("[MacroBridge] CalendarValueHistory failed for ", currency, " err=", err);
         return false;
        }

      for(int i = 0; i < n && event_count < VANTAGE_MACRO_MAX_EVENTS; i++)
        {
         MqlCalendarEvent ev;
         if(!CalendarEventById(values[i].event_id, ev))
            continue;
         if(ImportanceRank(ev.importance) < m_cfg.min_importance)
            continue;

         string key = IntegerToString((long)values[i].event_id) + "|" + IntegerToString((long)values[i].time);
         if(EventKeyExists(key, keys, key_count))
            continue;

         VantageMacroCalendarEvent row;
         row.external_event_id = IntegerToString((long)values[i].event_id);
         row.currency = currency;
         row.event_name = ev.name;
         row.importance = ImportanceToString(ev.importance);
         row.category = CategoryFromEventName(ev.name);
         row.event_time = values[i].time;
         row.scheduled_at = UtcIso8601(values[i].time);
         row.country = "";
         MqlCalendarCountry ctry;
         if(CalendarCountryById(ev.country_id, ctry))
            row.country = ctry.code;

         row.has_previous = CalendarValueIsSet(values[i].previous_value);
         row.has_forecast = CalendarValueIsSet(values[i].forecast_value);
         row.has_actual = CalendarValueIsSet(values[i].actual_value);
         row.previous = CalendarValueToDouble(values[i].previous_value);
         row.forecast = CalendarValueToDouble(values[i].forecast_value);
         row.actual = CalendarValueToDouble(values[i].actual_value);

         if(row.has_actual)
            row.status = "RELEASED";
         else if(values[i].revision > 0)
            row.status = "REVISED";
         else
            row.status = "SCHEDULED";

         events[event_count++] = row;
         ArrayResize(keys, key_count + 1);
         keys[key_count++] = key;
        }
      return true;
     }

   string JsonNumberOrNull(const bool has_value, const double v) const
     {
      if(!has_value)
         return "null";
      return DoubleToJson(v, 6);
     }

   string BuildPayloadJson(const VantageMacroCalendarEvent &events[], const int count) const
     {
      string broker = AccountInfoString(ACCOUNT_COMPANY);
      if(broker == "")
         broker = AccountInfoString(ACCOUNT_SERVER);
      string terminal = TerminalInfoString(TERMINAL_NAME);
      string j = "{";
      j += "\"source\":\"MT5_CALENDAR\",";
      j += "\"server_time_utc\":\"" + UtcIso8601(TimeGMT()) + "\",";
      j += "\"terminal\":\"" + JsonEscape(terminal) + "\",";
      j += "\"broker\":\"" + JsonEscape(broker) + "\",";
      j += "\"events\":[";
      for(int i = 0; i < count; i++)
        {
         if(i > 0) j += ",";
         j += "{";
         j += "\"event_id\":\"" + JsonEscape(events[i].external_event_id) + "\",";
         j += "\"external_event_id\":\"" + JsonEscape(events[i].external_event_id) + "\",";
         j += "\"currency\":\"" + JsonEscape(events[i].currency) + "\",";
         j += "\"country\":\"" + JsonEscape(events[i].country) + "\",";
         j += "\"event\":\"" + JsonEscape(events[i].event_name) + "\",";
         j += "\"category\":\"" + JsonEscape(events[i].category) + "\",";
         j += "\"importance\":\"" + JsonEscape(events[i].importance) + "\",";
         j += "\"scheduled_at\":\"" + JsonEscape(events[i].scheduled_at) + "\",";
         j += "\"previous\":" + JsonNumberOrNull(events[i].has_previous, events[i].previous) + ",";
         j += "\"forecast\":" + JsonNumberOrNull(events[i].has_forecast, events[i].forecast) + ",";
         j += "\"actual\":" + JsonNumberOrNull(events[i].has_actual, events[i].actual) + ",";
         j += "\"status\":\"" + JsonEscape(events[i].status) + "\"";
         j += "}";
        }
      j += "]}";
      return j;
     }

   bool PostJson(const string path, const string json_payload, string &body)
     {
      m_last_error = "";
      body = "";
      string url = TrimRightSlash(m_cfg.backend_url) + path;
      char data[];
      int dlen = StringToCharArray(json_payload, data, 0, WHOLE_ARRAY, CP_UTF8);
      if(dlen > 0)
         ArrayResize(data, dlen - 1);
      char result[];
      string headers = "Content-Type: application/json\r\n";
      headers += "Authorization: Bearer " + m_cfg.bearer_token + "\r\n";
      ResetLastError();
      m_last_http = WebRequest("POST", url, headers, m_cfg.timeout_ms, data, result, headers);
      int err = GetLastError();
      if(m_last_http == -1)
        {
         if(err == 4014 || err == 4060)
            m_last_error = "WebRequest URL not permitted. Add " + TrimRightSlash(m_cfg.backend_url) +
                           " in Tools → Options → Expert Advisors → Allow WebRequest.";
         else
            m_last_error = "WebRequest POST failed err=" + IntegerToString(err);
         return false;
        }
      body = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
      if(m_last_http == 401 || m_last_http == 403)
        {
         m_last_error = "Unauthorized — check LOCAL_API_TOKEN / InpApiToken.";
         return false;
        }
      if(m_last_http < 200 || m_last_http >= 300)
        {
         m_last_error = "HTTP " + IntegerToString(m_last_http) + " " + StringSubstr(body, 0, 180);
         return false;
        }
      return true;
     }

public:
   CVantageMacroBridge(void) : m_last_http(0), m_last_post(0) {}

   void Configure(const VantageMacroBridgeConfig &cfg)
     {
      m_cfg = cfg;
      m_cfg.backend_url = TrimRightSlash(m_cfg.backend_url);
     }

   string LastError(void) const { return m_last_error; }
   int    LastHttp(void) const { return m_last_http; }

   bool CalendarAvailable(void) const
     {
      datetime now = TimeTradeServer();
      if(now <= 0) now = TimeCurrent();
      MqlCalendarValue values[];
      ResetLastError();
      int n = CalendarValueHistory(values, now - 3600, now + 3600, NULL, "USD");
      return (n >= 0);
     }

   int CollectEvents(VantageMacroCalendarEvent &events[])
     {
      ArrayResize(events, VANTAGE_MACRO_MAX_EVENTS);
      int event_count = 0;
      string keys[];
      int key_count = 0;

      datetime now = TimeTradeServer();
      if(now <= 0) now = TimeCurrent();
      datetime from_t = now - (datetime)(MathMax(1, m_cfg.lookback_hours) * 3600);
      datetime to_t = now + (datetime)(MathMax(1, m_cfg.lookahead_days) * 86400);

      string currencies[];
      int cc = SplitCsv(m_cfg.currencies_csv, currencies);
      if(cc <= 0)
        {
         ArrayResize(currencies, 1);
         currencies[0] = "USD";
         cc = 1;
        }

      for(int i = 0; i < cc; i++)
         FetchCurrencyEvents(currencies[i], from_t, to_t, events, event_count, keys, key_count);

      ArrayResize(events, event_count);
      return event_count;
     }

   bool SendCalendar(VantageMacroBridgeResult &result)
     {
      ZeroMemory(result);
      result.ok = false;

      VantageMacroCalendarEvent events[];
      int count = CollectEvents(events);
      result.event_count = count;

      if(count <= 0)
        {
         result.ok = true;
         result.error = "No calendar events in window (or calendar unavailable).";
         return true;
        }

      string payload = BuildPayloadJson(events, count);
      string body = "";
      if(!PostJson("/api/v1/market-news/mt5-calendar", payload, body))
        {
         result.error = m_last_error;
         result.http_code = m_last_http;
         return false;
        }

      result.response_body = body;
      result.http_code = m_last_http;
      ExtractJsonInt(body, "inserted", result.inserted);
      ExtractJsonInt(body, "updated", result.updated);
      ExtractJsonInt(body, "unchanged", result.unchanged);
      result.ok = (StringFind(body, "\"ok\":true") >= 0 || StringFind(body, "\"ok\": true") >= 0);
      if(!result.ok && result.error == "")
         result.error = "Backend returned ok=false";
      m_last_post = TimeCurrent();
      return result.ok;
     }
  };

#endif
//+------------------------------------------------------------------+
