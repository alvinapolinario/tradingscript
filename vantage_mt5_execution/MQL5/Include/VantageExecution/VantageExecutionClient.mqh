//+------------------------------------------------------------------+
//| VantageExecutionClient.mqh                                       |
//| WebRequest client for /api/v1/execution/*                        |
//+------------------------------------------------------------------+
#ifndef VANTAGE_EXECUTION_CLIENT_MQH
#define VANTAGE_EXECUTION_CLIENT_MQH

#include "VantageExecutionTypes.mqh"

class CVantageExecutionClient
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

   bool ExtractJsonDouble(const string json, const string key, double &out_v)
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
      bool has_dot = false;
      while(j < StringLen(json))
        {
         ushort ch = StringGetCharacter(json, j);
         if(ch == '.')
           {
            if(has_dot) break;
            has_dot = true;
            j++;
            continue;
           }
         if(ch < '0' || ch > '9')
            break;
         j++;
        }
      if(j <= i)
         return false;
      out_v = StringToDouble(StringSubstr(json, i, j - i));
      return true;
     }

   bool ExtractJsonLong(const string json, const string key, long &out_v)
     {
      double d = 0;
      if(!ExtractJsonDouble(json, key, d))
         return false;
      out_v = (long)d;
      return true;
     }

   bool ExtractJsonInt(const string json, const string key, int &out_v)
     {
      double d = 0;
      if(!ExtractJsonDouble(json, key, d))
         return false;
      out_v = (int)d;
      return true;
     }

   bool ExtractJsonBool(const string json, const string key, bool &out_v)
     {
      string pat = "\"" + key + "\"";
      int p = StringFind(json, pat);
      if(p < 0) return false;
      int colon = StringFind(json, ":", p);
      if(colon < 0) return false;
      string tail = StringSubstr(json, colon + 1, 12);
      if(StringFind(tail, "true") == 0)
        { out_v = true; return true; }
      if(StringFind(tail, "false") == 0)
        { out_v = false; return true; }
      return false;
     }

   bool WebGet(const string path, string &body)
     {
      m_last_error = "";
      body = "";
      string url = m_base_url + path;
      char data[];
      char result[];
      string headers = "Content-Type: application/json\r\n";
      headers += "Authorization: Bearer " + m_token + "\r\n";
      ResetLastError();
      m_last_http = WebRequest("GET", url, headers, m_timeout_ms, data, result, headers);
      int err = GetLastError();
      if(m_last_http == -1)
        {
         if(err == 4014 || err == 4060)
            m_last_error = "WebRequest URL not permitted. Add " + m_base_url + " in Tools → Options → Expert Advisors → Allow WebRequest.";
         else
            m_last_error = "WebRequest GET failed err=" + IntegerToString(err);
         return false;
        }
      body = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
      if(m_last_http == 401 || m_last_http == 403)
        {
         m_last_error = "Unauthorized — check bearer token.";
         return false;
        }
      if(m_last_http < 200 || m_last_http >= 300)
        {
         m_last_error = "HTTP " + IntegerToString(m_last_http);
         return false;
        }
      return true;
     }

   bool WebPostJson(const string path, const string json_payload, string &body)
     {
      m_last_error = "";
      body = "";
      string url = m_base_url + path;
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
            m_last_error = "WebRequest URL not permitted.";
         else
            m_last_error = "WebRequest POST failed err=" + IntegerToString(err);
         return false;
        }
      body = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
      if(m_last_http == 401 || m_last_http == 403)
        {
         m_last_error = "Unauthorized — check bearer token.";
         return false;
        }
      if(m_last_http < 200 || m_last_http >= 300)
        {
         m_last_error = "HTTP " + IntegerToString(m_last_http);
         return false;
        }
      return true;
     }

public:
   CVantageExecutionClient(void) : m_timeout_ms(8000), m_last_http(0) {}

   void Configure(const string base_url, const string bearer_token, const int timeout_ms)
     {
      m_base_url = TrimRightSlash(base_url);
      m_token = bearer_token;
      m_timeout_ms = timeout_ms;
     }

   string LastError(void) const { return m_last_error; }
   int    LastHttp(void) const { return m_last_http; }

   bool PollNext(const string symbol, const double min_confidence, VantageExecOrderSpec &spec)
     {
      ZeroMemory(spec);
      spec.valid = false;
      string path = "/api/v1/execution/next?symbol=" + symbol;
      if(min_confidence > 0)
         path += "&min_confidence=" + DoubleToString(min_confidence, 0);
      string body = "";
      if(!WebGet(path, body))
         return false;

      bool has_signal = false;
      if(!ExtractJsonBool(body, "has_signal", has_signal) || !has_signal)
         return true;

      string order_json = body;
      int ord_key = StringFind(body, "\"order\"");
      if(ord_key >= 0)
        {
         int ob = StringFind(body, "{", ord_key);
         if(ob >= 0)
           {
            int depth = 0;
            int oe = ob;
            for(int i = ob; i < StringLen(body); i++)
              {
               ushort c = StringGetCharacter(body, i);
               if(c == '{') depth++;
               if(c == '}')
                {
                 depth--;
                 if(depth == 0)
                   {
                    oe = i;
                    break;
                   }
                }
              }
            order_json = StringSubstr(body, ob, oe - ob + 1);
           }
        }

      ExtractJsonString(order_json, "signal_id", spec.signal_id);
      ExtractJsonString(order_json, "symbol", spec.symbol);
      ExtractJsonString(order_json, "side", spec.side);
      ExtractJsonString(order_json, "order_type", spec.order_type);
      ExtractJsonDouble(order_json, "stop_loss", spec.stop_loss);
      ExtractJsonDouble(order_json, "take_profit", spec.take_profit);
      ExtractJsonDouble(order_json, "confidence", spec.confidence);
      ExtractJsonLong(order_json, "eval_bar_m5", spec.eval_bar_m5);
      ExtractJsonInt(order_json, "expires_in_sec", spec.expires_in_sec);

      spec.valid = (spec.signal_id != "" && spec.side != "" && spec.stop_loss > 0 && spec.take_profit > 0);
      return true;
     }

   bool SendAck(const VantageExecAckResult &ack, VantageExecAckResult &reply)
     {
      ZeroMemory(reply);
      reply.ok = false;
      string payload = "{";
      payload += "\"signal_id\":\"" + ack.signal_id + "\",";
      payload += "\"status\":\"" + ack.status + "\",";
      payload += "\"ticket\":" + IntegerToString((long)ack.ticket) + ",";
      payload += "\"reason\":\"" + ack.reason + "\"";
      payload += "}";
      string body = "";
      if(!WebPostJson("/api/v1/execution/ack", payload, body))
        {
         reply.error = m_last_error;
         reply.http_code = m_last_http;
         return false;
        }
      reply.ok = true;
      reply.http_code = m_last_http;
      ExtractJsonString(body, "signal_id", reply.signal_id);
      ExtractJsonString(body, "status", reply.status);
      return true;
     }
  };

#endif
