# XAUUSD M30 Market Structure and Alert System (MetaTrader 5)

**Platform: MetaTrader 5 (MQL5)** — not TradingView Pine Script.

The earlier `.pine` file is TradingView-only. MetaEditor cannot compile Pine Script. Use the `.mq5` indicator below.

## Files


| File                                            | Purpose                                   |
| ----------------------------------------------- | ----------------------------------------- |
| `XAUUSD_M30_Alert_System.mq5`                   | Main MT5 indicator (recommended)          |
| `m30gold.mq5`                                   | Same code (alternate filename)            |
| `xauusd_m30_market_structure_alert_system.pine` | TradingView version only (ignore for MT5) |


---

## Install in MT5

1. Open **MetaEditor** (F4 from MT5).
2. In Navigator: **Indicators** → right-click → **Open Folder** (or go to `MQL5\Indicators\`).
3. Copy `XAUUSD_M30_Alert_System.mq5` into that folder.
4. In MetaEditor: open the file → press **Compile** (F7).
5. Confirm **0 errors** in the Toolbox.
6. In MT5: open **XAUUSD** chart, timeframe **M30**.
7. Navigator → **Indicators** → drag **XAUUSD_M30_Alert_System** onto the chart.
8. Set **Important Price Levels** for the current session → OK.

---



## Enable alerts (MT5)

In indicator inputs (**A. General Settings**):

- **Enable popup / push / email alerts** = true  
- Optional: **Send push notification** (enable push in MT5: Tools → Options → Notifications)  
- Optional: **Send email** (configure Tools → Options → Email)  
- **Confirm signals only at candle close** = true (recommended, non-repainting)  
- **Allow multiple alerts per bar** = false (highest priority only)

Alerts use `Alert()`, optional `SendNotification()`, `SendMail()`, and `PlaySound()`.

---



## What you get

- MA + Bollinger Bands plots  
- Editable support/resistance levels + zone shading  
- On-chart signal arrows/labels  
- Top-left dashboard (`Comment`)  
- All 15 alert logics from the original design  
- Pivot retest state machine  
- Cooldown + alert priority  
- Session / day-of-week / ATR / oversized-candle filters

---



## Recommended defaults (XAUUSD M30)


| Setting                 | Value                |
| ----------------------- | -------------------- |
| Confirm at candle close | true                 |
| Intrabar mode           | false                |
| MA                      | EMA 20               |
| Bollinger               | 20, 2.0              |
| RSI                     | 14                   |
| Volume confirm          | true, mult 1.20      |
| Cooldown                | 3 bars               |
| Suppress oversized      | true, 2× ATR         |
| Levels                  | Update every session |


---



## Disclaimer

Decision-support only. No signal guarantees profit. Always manage risk.