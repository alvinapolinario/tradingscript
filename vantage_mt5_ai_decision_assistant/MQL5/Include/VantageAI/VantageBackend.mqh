//+------------------------------------------------------------------+
//| VantageBackend.mqh                                               |
//| Local FastAPI client via WebRequest (no cloud API keys in EA)    |
//+------------------------------------------------------------------+
#ifndef VANTAGE_BACKEND_MQH
#define VANTAGE_BACKEND_MQH

#include "VantageTypes.mqh"

class CVantageBackend
  {
private:
   string m_base_url;
   string m_token;
   int    m_timeout_ms;
   string m_last_error;
   int    m_last_http;

   string TrimRightSlash(string u)
     {
      while(StringLen(u) > 0 && StringGetCharacter(u, StringLen(u) - 1) == '/')
         u = StringSubstr(u, 0, StringLen(u) - 1);
      return u;
     }

   bool ExtractJsonString(const string json, const string key, string &out_v)
     {
      string pat = "\"" + key + "\"";
      int p = StringFind(json, pat);
      if(p < 0) return false;
      int colon = StringFind(json, ":", p);
      if(colon < 0) return false;
      int q1 = StringFind(json, "\"", colon + 1);
      if(q1 < 0) return false;
      int q2 = q1 + 1;
      while(q2 < StringLen(json))
        {
         ushort ch = StringGetCharacter(json, q2);
         if(ch == '"' && StringGetCharacter(json, q2 - 1) != '\\')
            break;
         q2++;
        }
      out_v = StringSubstr(json, q1 + 1, q2 - q1 - 1);
      return true;
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

public:
   CVantageBackend(void) : m_timeout_ms(8000), m_last_http(0) {}

   void Configure(const string base_url, const string bearer_token, const int timeout_ms)
     {
      m_base_url = TrimRightSlash(base_url);
      m_token = bearer_token;
      m_timeout_ms = timeout_ms;
     }

   string LastError(void) const { return m_last_error; }
   int    LastHttp(void) const { return m_last_http; }

   bool Health(string &detail)
     {
      detail = "";
      m_last_error = "";
      string url = m_base_url + "/health";
      char data[];
      char result[];
      string headers = "Content-Type: application/json\r\n";
      ResetLastError();
      m_last_http = WebRequest("GET", url, headers, m_timeout_ms, data, result, headers);
      int err = GetLastError();
      if(m_last_http == -1)
        {
         if(err == 4014 || err == 4060)
            m_last_error = "WebRequest URL not permitted. Add " + m_base_url + " in Tools → Options → Expert Advisors → Allow WebRequest.";
         else if(err == 5203 || err == 5200)
            m_last_error = "Connection failure / invalid URL talking to " + url;
         else
            m_last_error = "WebRequest failed err=" + IntegerToString(err) + " url=" + url;
         detail = m_last_error;
         return false;
        }
      string body = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
      detail = body;
      if(m_last_http != 200)
        {
         m_last_error = "Health HTTP " + IntegerToString(m_last_http);
         return false;
        }
      return (StringFind(body, "ok") >= 0 || StringFind(body, "\"status\"") >= 0);
     }

   // Returns true on HTTP OK. Optionally fills requested calendar year/month from response.
   bool Heartbeat(const string json_payload, int &out_cal_year, int &out_cal_month)
     {
      m_last_error = "";
      out_cal_year = 0;
      out_cal_month = 0;
      string url = m_base_url + "/api/v1/heartbeat";
      char data[];
      int dlen = StringToCharArray(json_payload, data, 0, WHOLE_ARRAY, CP_UTF8);
      if(dlen > 0)
         ArrayResize(data, dlen - 1);

      char result[];
      string headers = "Content-Type: application/json\r\n";
      headers += "Authorization: Bearer " + m_token + "\r\n";

      ResetLastError();
      m_last_http = WebRequest("POST", url, headers, m_timeout_ms, data, result, headers);
      int err = GetLastError();
      if(m_last_http == -1)
        {
         if(err == 4014 || err == 4060)
            m_last_error = "WebRequest URL not permitted for heartbeat.";
         else
            m_last_error = "Heartbeat WebRequest failed err=" + IntegerToString(err);
         return false;
        }
      if(m_last_http < 200 || m_last_http >= 300)
        {
         m_last_error = "Heartbeat HTTP " + IntegerToString(m_last_http);
         return false;
        }
      string body = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
      int y = 0, m = 0;
      if(ExtractJsonInt(body, "calendar_year", y) && ExtractJsonInt(body, "calendar_month", m))
        {
         if(y >= 2000 && m >= 1 && m <= 12)
           {
            out_cal_year = y;
            out_cal_month = m;
           }
        }
      return true;
     }

   bool Heartbeat(const string json_payload)
     {
      int y = 0, m = 0;
      return Heartbeat(json_payload, y, m);
     }

   bool Analyze(const string json_payload, VantageBackendReply &reply, const int max_age_sec)
     {
      ZeroMemory(reply);
      reply.ok = false;
      m_last_error = "";
      string url = m_base_url + "/api/v1/analyze";

      char data[];
      int dlen = StringToCharArray(json_payload, data, 0, WHOLE_ARRAY, CP_UTF8);
      if(dlen > 0)
         ArrayResize(data, dlen - 1); // drop null terminator

      char result[];
      string headers = "Content-Type: application/json\r\n";
      headers += "Authorization: Bearer " + m_token + "\r\n";

      ResetLastError();
      m_last_http = WebRequest("POST", url, headers, m_timeout_ms, data, result, headers);
      int err = GetLastError();
      reply.http_code = m_last_http;
      reply.received_local = TimeLocal();

      if(m_last_http == -1)
        {
         if(err == 4014 || err == 4060)
            m_last_error = "WebRequest URL not permitted. Add http://127.0.0.1:8000 to Tools → Options → Expert Advisors → Allow WebRequest for listed URL.";
         else if(err == 5203)
            m_last_error = "Backend connection failure / timeout.";
         else
            m_last_error = "WebRequest failed err=" + IntegerToString(err);
         reply.error = m_last_error;
         reply.action = "BACKEND_OFFLINE";
         return false;
        }

      string body = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
      if(m_last_http == 401 || m_last_http == 403)
        {
         m_last_error = "Unauthorized — check local bearer token.";
         reply.error = m_last_error;
         reply.action = "BACKEND_OFFLINE";
         return false;
        }
      if(m_last_http < 200 || m_last_http >= 300)
        {
         m_last_error = "Backend HTTP " + IntegerToString(m_last_http) + " body=" + StringSubstr(body, 0, 180);
         reply.error = m_last_error;
         reply.action = "BACKEND_OFFLINE";
         return false;
        }

      if(StringFind(body, "{") < 0)
        {
         m_last_error = "Malformed JSON response";
         reply.error = m_last_error;
         reply.action = "DATA_UNAVAILABLE";
         return false;
        }

      string action = "", rationale = "", trend = "", env = "", ns = "", nr = "", ts = "";
      string market_state = "", new_entry = "", existing = "", risk_status = "";
      string imm_sup = "", rec1 = "", rec2 = "", bull_conf = "", tech_inv = "", risk_warn = "";
      if(!ExtractJsonString(body, "action", action))
        {
         m_last_error = "Malformed JSON: missing action";
         reply.error = m_last_error;
         reply.action = "DATA_UNAVAILABLE";
         return false;
        }
      ExtractJsonString(body, "rationale", rationale);
      ExtractJsonString(body, "trend", trend);
      ExtractJsonString(body, "environment", env);
      ExtractJsonString(body, "market_state", market_state);
      ExtractJsonString(body, "new_entry_decision", new_entry);
      ExtractJsonString(body, "existing_position_decision", existing);
      ExtractJsonString(body, "risk_status", risk_status);
      ExtractJsonString(body, "immediate_support", imm_sup);
      ExtractJsonString(body, "recovery_level_1", rec1);
      ExtractJsonString(body, "recovery_level_2", rec2);
      ExtractJsonString(body, "bullish_confirmation", bull_conf);
      ExtractJsonString(body, "technical_invalidation", tech_inv);
      ExtractJsonString(body, "risk_warning", risk_warn);
      ExtractJsonString(body, "nearest_support", ns);
      ExtractJsonString(body, "nearest_resistance", nr);
      ExtractJsonString(body, "timestamp_utc", ts);

      reply.action = action;
      reply.rationale = rationale;
      reply.trend = trend;
      reply.environment = env;
      reply.market_state = market_state;
      reply.new_entry_decision = new_entry;
      reply.existing_position_decision = existing;
      reply.risk_status = risk_status;
      reply.immediate_support = imm_sup;
      reply.recovery_level_1 = rec1;
      reply.recovery_level_2 = rec2;
      reply.bullish_confirmation = bull_conf;
      reply.technical_invalidation = tech_inv;
      reply.risk_warning = risk_warn;
      reply.nearest_support = ns;
      reply.nearest_resistance = nr;
      reply.timestamp_utc = ts;
      reply.new_position_allowed = (StringFind(body, "\"new_position_allowed\":true") >= 0);
      reply.add_position_allowed = (StringFind(body, "\"add_position_allowed\":true") >= 0);
      reply.exceeds_max_position_risk = (StringFind(body, "\"exceeds_max_position_risk\":true") >= 0);
      reply.ok = true;
      reply.error = "";

      // Stale response detection (backend age header field if present)
      string age_s = "";
      if(ExtractJsonString(body, "generated_at_utc", age_s) || ts != "")
        {
         // Soft age: if backend sends age_seconds numeric as string field
         string age_field = "";
         if(ExtractJsonString(body, "age_seconds", age_field))
           {
            reply.age_seconds = (int)StringToInteger(age_field);
            reply.stale = (max_age_sec > 0 && reply.age_seconds > max_age_sec);
           }
        }
      if(reply.stale)
        {
         reply.ok = false;
         reply.error = "Stale AI result";
         reply.action = "DATA_UNAVAILABLE";
         m_last_error = reply.error;
         return false;
        }
      return true;
     }
  };

#endif
//+------------------------------------------------------------------+
