"""
MQL5 diagnostic checklist (run via EA InpRunDiagnostics=true).

Covered in VantageDiagnostics.mqh / Experts log:
- [ ] Vantage symbol with suffix (discovery list)
- [ ] Two-digit gold pricing (Digits dynamic)
- [ ] Three-digit gold pricing (Digits dynamic)
- [ ] Minimum lot 0.01 + volume step validation
- [ ] Hedging account mode
- [ ] Netting account mode
- [ ] Multiple open positions aggregation
- [ ] No open position
- [ ] High spread classification
- [ ] Closed market trade mode
- [ ] WebRequest URL not permitted (backend health error text)
- [ ] Backend offline
- [ ] Malformed response (backend client)
- [ ] Stale AI result (max age)
- [ ] Incomplete candle history
- [ ] Invalid tick value
- [ ] OrderCalcProfit failure path
- [ ] Advisory-mode enforcement (InpAdvisoryOnly)
"""
