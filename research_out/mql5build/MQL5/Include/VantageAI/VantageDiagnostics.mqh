//+------------------------------------------------------------------+
//| VantageDiagnostics.mqh                                           |
//| Built-in diagnostic mode checks (no live trading)                |
//+------------------------------------------------------------------+
#ifndef VANTAGE_DIAGNOSTICS_MQH
#define VANTAGE_DIAGNOSTICS_MQH

#include "VantageTypes.mqh"
#include "VantageSymbol.mqh"
#include "VantageRisk.mqh"
#include "VantagePositions.mqh"
#include "VantageBackend.mqh"

void VantageRunDiagnostics(const string chart_symbol,
                           const VantageSymbolSpec &spec,
                           const VantageAccountInfo &acct,
                           CVantageBackend &backend,
                           const double max_spread_points)
  {
   Print("========== Vantage AI Diagnostics ==========");
   Print("1) Chart symbol: ", chart_symbol, " (never auto-switched)");
   VantageLogXauusdReferenceProfile(chart_symbol, spec);

   string candidates = "";
   string first = VantageDiscoverGoldCandidates(candidates);
   Print("2) Gold-like symbols found: ", (candidates == "" ? "(none)" : candidates));
   Print("   First candidate (info only): ", first);

   Print("3) Digits=", spec.digits, " | Point=", DoubleToString(spec.point, 8),
         " | Contract=", DoubleToString(spec.contract_size, 2));
   Print("4) Volume min=", DoubleToString(spec.volume_min, 4),
         " step=", DoubleToString(spec.volume_step, 4),
         " max=", DoubleToString(spec.volume_max, 4),
         " | StopsLevel=", spec.stops_level);

   double nv = 0.0;
   string verr = "";
   bool vok = VantageNormalizeVolume(spec, spec.volume_min, nv, verr);
   Print("5) Volume step validation @ min lot: ", vok ? "PASS" : ("FAIL " + verr));

   Print("6) Account mode: ", VantageMarginModeName(acct.margin_mode),
         acct.is_hedging ? " (hedging)" : " (netting/other)");

   VantagePositionSummary pos;
   VantageLoadPositions(chart_symbol, pos);
   Print("7) Open positions on symbol: ", pos.count,
         pos.count == 0 ? " (none)" : " (multi-position aggregation supported)");

   VantagePriceSnap px;
   VantageCapturePrices(chart_symbol, max_spread_points, px);
   Print("8) Spread points=", px.spread_points, px.high_spread ? " HIGH_SPREAD" : " OK");

   long trade_mode = SymbolInfoInteger(chart_symbol, SYMBOL_TRADE_MODE);
   Print("9) Trade mode=", trade_mode,
         (trade_mode == SYMBOL_TRADE_MODE_DISABLED) ? " CLOSED/DISABLED" : " tradable-flags-ok (advisory still never trades)");

   string health = "";
   bool hok = backend.Health(health);
   Print("10) Backend health: ", hok ? "OK" : "OFFLINE/ERR", " | ", health);

   // Risk calc smoke test using min volume, synthetic 1% distance if possible
   if(spec.valid && px.bid > 0.0)
     {
      double entry = px.bid;
      double sl = entry - 50.0 * spec.point;
      double tp = entry + 75.0 * spec.point;
      VantageRiskEstimate risk;
      bool rok = VantageCalcRiskFromLevels(chart_symbol, spec, ORDER_TYPE_BUY, spec.volume_min, entry, sl, tp, risk);
      Print("11) OrderCalcProfit risk path: ", rok ? "PASS" : ("FAIL status=" + risk.status + " err=" + IntegerToString(risk.last_error)));
     }

   // Advisory enforcement note
   Print("12) Advisory enforcement: CTrade/OrderSend must not appear in this EA build.");
   Print("13) Incomplete history check: Bars=", Bars(chart_symbol, PERIOD_M30));
   if(Bars(chart_symbol, PERIOD_M30) < 220)
      Print("    INCOMPLETE_CANDLE_HISTORY — need more M30 bars for EMA200.");
   if(spec.tick_value <= 0.0)
      Print("14) INVALID_TICK_VALUE detected");
   else
      Print("14) Tick value OK: ", DoubleToString(spec.tick_value, 6));
   Print("========== End Diagnostics ==========");
  }

#endif
//+------------------------------------------------------------------+
