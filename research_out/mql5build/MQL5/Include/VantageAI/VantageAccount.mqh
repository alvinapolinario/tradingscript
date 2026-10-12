//+------------------------------------------------------------------+
//| VantageAccount.mqh                                               |
//| Vantage-aware account / environment detection                    |
//+------------------------------------------------------------------+
#ifndef VANTAGE_ACCOUNT_MQH
#define VANTAGE_ACCOUNT_MQH

#include "VantageTypes.mqh"

bool VantageLooksLikeBrokerName(const string company, const string server)
  {
   string c = company;
   string s = server;
   StringToLower(c);
   StringToLower(s);
   // Soft match only — never hard-reject non-exact names
   if(StringFind(c, "vantage") >= 0) return true;
   if(StringFind(s, "vantage") >= 0) return true;
   if(StringFind(c, "van") >= 0 && StringFind(c, "tage") >= 0) return true;
   return false;
  }

bool VantageLoadAccountInfo(VantageAccountInfo &info)
  {
   ZeroMemory(info);
   info.company  = AccountInfoString(ACCOUNT_COMPANY);
   info.server   = AccountInfoString(ACCOUNT_SERVER);
   info.currency = AccountInfoString(ACCOUNT_CURRENCY);
   info.login    = AccountInfoInteger(ACCOUNT_LOGIN);
   info.login_masked = MaskAccountLogin(info.login);
   info.margin_mode = AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   info.trade_allowed_acct = (AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) != 0);
   info.terminal_connected = (TerminalInfoInteger(TERMINAL_CONNECTED) != 0);
   info.terminal_trade_allowed = (TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) != 0);
   info.mql_trade_allowed = (MQLInfoInteger(MQL_TRADE_ALLOWED) != 0);
   info.is_hedging = (info.margin_mode == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING);
   info.balance = AccountInfoDouble(ACCOUNT_BALANCE);
   info.equity = AccountInfoDouble(ACCOUNT_EQUITY);
   info.margin = AccountInfoDouble(ACCOUNT_MARGIN);
   info.free_margin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   info.looks_like_vantage = VantageLooksLikeBrokerName(info.company, info.server);
   if(!info.looks_like_vantage)
      info.vantage_warning = "Warning: company/server do not contain a recognizable Vantage reference. EA still runs — verify you are on the intended broker.";
   else
      info.vantage_warning = "";
   return true;
  }

string VantageMarginModeName(const long mode)
  {
   if(mode == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) return "Hedging";
   if(mode == ACCOUNT_MARGIN_MODE_RETAIL_NETTING) return "Netting";
   if(mode == ACCOUNT_MARGIN_MODE_EXCHANGE) return "Exchange";
   return "Unknown";
  }

void VantageLogAccountDiagnostics(const VantageAccountInfo &info)
  {
   PrintFormat("[VantageAI] Company=%s | Server=%s | Currency=%s | Login=%s | Mode=%s",
               info.company, info.server, info.currency, info.login_masked,
               VantageMarginModeName(info.margin_mode));
   PrintFormat("[VantageAI] AcctTradeAllowed=%s TermConnected=%s TermTradeAllowed=%s MqlTradeAllowed=%s",
               info.trade_allowed_acct ? "Y" : "N",
               info.terminal_connected ? "Y" : "N",
               info.terminal_trade_allowed ? "Y" : "N",
               info.mql_trade_allowed ? "Y" : "N");
   // Explicit: full login must never leave the terminal via HTTP payloads
   Print("[VantageAI] Privacy: full account login is LOCAL-ONLY and never sent to the AI backend.");
   if(info.vantage_warning != "")
      Print("[VantageAI] ", info.vantage_warning);
  }

#endif
//+------------------------------------------------------------------+
