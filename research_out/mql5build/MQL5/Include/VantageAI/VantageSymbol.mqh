//+------------------------------------------------------------------+
//| VantageSymbol.mqh                                                |
//| Broker symbol discovery + dynamic specification                  |
//+------------------------------------------------------------------+
#ifndef VANTAGE_SYMBOL_MQH
#define VANTAGE_SYMBOL_MQH

#include "VantageTypes.mqh"

bool VantageSymbolVisible(const string sym)
  {
   return(SymbolSelect(sym, true));
  }

bool VantageNameLooksLikeGold(const string name)
  {
   string u = name;
   StringToUpper(u);
   if(u == "XAUUSD" || u == "GOLD")
      return true;
   if(StringFind(u, "XAU") >= 0)
      return true;
   if(StringFind(u, "GOLD") >= 0)
      return true;
   return false;
  }

// Optional discovery — does NOT change the chart symbol.
// Prefer exact chart symbol; discovery only helps diagnostics / suggestions.
string VantageDiscoverGoldCandidates(string &out_list)
  {
   out_list = "";
   string first = "";
   int total = SymbolsTotal(false);
   for(int i = 0; i < total; i++)
     {
      string name = SymbolName(i, false);
      if(!VantageNameLooksLikeGold(name))
         continue;
      if(out_list != "")
         out_list += ", ";
      out_list += name;
      if(first == "")
         first = name;
     }
   return first;
  }

bool VantageLoadSymbolSpec(const string symbol, VantageSymbolSpec &spec)
  {
   ZeroMemory(spec);
   spec.symbol = symbol;
   if(symbol == "" || !SymbolInfoInteger(symbol, SYMBOL_EXIST))
     {
      spec.valid = false;
      spec.error = "Symbol does not exist in Market Watch / terminal: " + symbol;
      return false;
     }
   if(!VantageSymbolVisible(symbol))
     {
      spec.valid = false;
      spec.error = "Unable to select symbol into Market Watch: " + symbol;
      return false;
     }

   spec.digits            = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   spec.point             = SymbolInfoDouble(symbol, SYMBOL_POINT);
   spec.tick_size         = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   spec.tick_value        = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   spec.tick_value_profit = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE_PROFIT);
   spec.tick_value_loss   = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   spec.contract_size     = SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   spec.volume_min        = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   spec.volume_max        = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   spec.volume_step       = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   spec.stops_level       = (int)SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);
   spec.freeze_level      = (int)SymbolInfoInteger(symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   spec.spread_points     = (int)SymbolInfoInteger(symbol, SYMBOL_SPREAD);
   spec.spread_float      = (SymbolInfoInteger(symbol, SYMBOL_SPREAD_FLOAT) != 0);
   spec.trade_mode        = (int)SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE);
   // MQL5 property is SYMBOL_TRADE_EXEMODE (not SYMBOL_TRADE_EXECUTION)
   spec.trade_execution   = (int)SymbolInfoInteger(symbol, SYMBOL_TRADE_EXEMODE);
   spec.filling_mode      = (int)SymbolInfoInteger(symbol, SYMBOL_FILLING_MODE);
   spec.expiration_mode   = (int)SymbolInfoInteger(symbol, SYMBOL_EXPIRATION_MODE);
   spec.valid = true;
   spec.error = "";

   if(spec.point <= 0.0 || spec.tick_size <= 0.0)
     {
      spec.valid = false;
      spec.error = "Invalid point/tick_size from broker for " + symbol;
      return false;
     }
   return true;
  }

void VantageLogSymbolSpec(const VantageSymbolSpec &spec)
  {
   PrintFormat("[VantageAI] Symbol=%s Digits=%d Point=%s TickSize=%s TickValue=%s Contract=%s",
               spec.symbol, spec.digits,
               DoubleToString(spec.point, spec.digits + 2),
               DoubleToString(spec.tick_size, spec.digits + 2),
               DoubleToString(spec.tick_value, 4),
               DoubleToString(spec.contract_size, 2));
   PrintFormat("[VantageAI] VolMin=%s VolMax=%s VolStep=%s StopsLevel=%d Freeze=%d Spread=%d Float=%s",
               DoubleToString(spec.volume_min, 2),
               DoubleToString(spec.volume_max, 2),
               DoubleToString(spec.volume_step, 2),
               spec.stops_level, spec.freeze_level, spec.spread_points,
               spec.spread_float ? "Y" : "N");
   PrintFormat("[VantageAI] TradeMode=%d Exec=%d Filling=%d Expiration=%d",
               spec.trade_mode, spec.trade_execution, spec.filling_mode, spec.expiration_mode);
  }

// Reference profile from a verified Vantage XAUUSD specification screen
// (Digits 2, Contract 100, Stops 20, Vol 0.01/0.01/100, Floating spread).
// Used for diagnostics ONLY — runtime always uses live SymbolInfo* values.
void VantageLogXauusdReferenceProfile(const string chart_symbol, const VantageSymbolSpec &spec)
  {
   Print("[VantageAI] --- Vantage XAUUSD reference (from broker Specification) ---");
   Print("[VantageAI] Expected chart symbol example: XAUUSD");
   Print("[VantageAI] Reference: Digits=2 | Contract=100 | StopsLevel=20 | VolMin=0.01 | VolStep=0.01 | VolMax=100 | Spread=Floating | Filling=IOC | Calc=CFD Leverage");
   Print("[VantageAI] Live chart symbol in use: ", chart_symbol);
   PrintFormat("[VantageAI] Live: Digits=%d Contract=%s Stops=%d VolMin=%s VolStep=%s VolMax=%s SpreadFloat=%s",
               spec.digits,
               DoubleToString(spec.contract_size, 2),
               spec.stops_level,
               DoubleToString(spec.volume_min, 2),
               DoubleToString(spec.volume_step, 2),
               DoubleToString(spec.volume_max, 2),
               spec.spread_float ? "Y" : "N");

   // Soft checks — warn only, never hard-code or reject other Vantage variants
   if(chart_symbol != "XAUUSD" && StringFind(chart_symbol, "XAU") < 0 && StringFind(chart_symbol, "GOLD") < 0)
      Print("[VantageAI] Note: chart symbol is not a typical gold name. Attach EA to your XAUUSD M30 chart.");
   if(spec.digits == 2)
      Print("[VantageAI] Digits=2 confirmed (price format like 4095.12). Point=", DoubleToString(spec.point, 8));
   else
      Print("[VantageAI] Digits=", spec.digits, " (differs from common Vantage XAUUSD=2 — OK, using live value).");
   if(MathAbs(spec.contract_size - 100.0) < 1e-6)
      Print("[VantageAI] Contract size 100 confirmed (1.00 lot = 100 oz notional on this CFD).");
   else
      Print("[VantageAI] Contract size ", DoubleToString(spec.contract_size, 2), " (differs from common Vantage XAUUSD=100 — using live value for risk).");
   if(spec.stops_level == 20)
      Print("[VantageAI] Stops level 20 confirmed (min SL/TP distance = 20 points = ",
            DoubleToString(20.0 * spec.point, spec.digits), " price).");
   else
      Print("[VantageAI] Stops level=", spec.stops_level, " (live broker value).");
   if(MathAbs(spec.volume_min - 0.01) < 1e-9 && MathAbs(spec.volume_step - 0.01) < 1e-9)
      Print("[VantageAI] Lot min/step 0.01 confirmed.");
   Print("[VantageAI] --- end XAUUSD reference ---");
  }

bool VantageNormalizeVolume(const VantageSymbolSpec &spec, const double volume, double &out_vol, string &err)
  {
   out_vol = volume;
   err = "";
   if(!spec.valid)
     {
      err = "Symbol spec invalid";
      return false;
     }
   if(spec.volume_step <= 0.0)
     {
      err = "Invalid volume step";
      return false;
     }
   double steps = MathRound(volume / spec.volume_step);
   out_vol = steps * spec.volume_step;
   // Fix floating residue
   out_vol = NormalizeDouble(out_vol, 8);
   if(out_vol < spec.volume_min - 1e-12)
     {
      err = "Volume below broker minimum";
      return false;
     }
   if(out_vol > spec.volume_max + 1e-12)
     {
      err = "Volume above broker maximum";
      return false;
     }
   return true;
  }

bool VantageCapturePrices(const string symbol, const double max_spread_points, VantagePriceSnap &px)
  {
   ZeroMemory(px);
   MqlTick tick;
   if(!SymbolInfoTick(symbol, tick))
     {
      ResetLastError();
      return false;
     }
   px.bid = tick.bid;
   px.ask = tick.ask;
   px.last = tick.last;
   px.mid = (px.bid > 0.0 && px.ask > 0.0) ? (px.bid + px.ask) * 0.5 : px.bid;
   px.spread_price = px.ask - px.bid;
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   px.spread_points = (point > 0.0) ? (int)MathRound(px.spread_price / point) : (int)SymbolInfoInteger(symbol, SYMBOL_SPREAD);
   px.server_time = (datetime)TimeCurrent();
   px.local_time  = (datetime)TimeLocal();
   px.utc_time    = (datetime)TimeGMT();
   px.high_spread = (max_spread_points > 0.0 && px.spread_points > max_spread_points);
   return true;
  }

#endif
//+------------------------------------------------------------------+
