//+------------------------------------------------------------------+
//| VwapReversion.mq5                                                 |
//| Reversión a la media sobre la VWAP de la sesión (intradía).       |
//|                                                                   |
//| - Calcula la VWAP y su desviación estándar desde la apertura de   |
//|   la sesión, con velas de 1 minuto y volumen de ticks.            |
//| - Compra cuando el precio cierra InpEntryBands desviaciones por   |
//|   debajo de la VWAP; vende en corto cuando cierra por encima.     |
//| - Sale cuando el precio vuelve a la VWAP, por stop-loss o a la    |
//|   hora de cierre forzoso. Nunca deja posiciones de un día a otro. |
//| - Por defecto solo opera en cuentas DEMO.                         |
//+------------------------------------------------------------------+
#property copyright "git_test"
#property version   "1.00"
#property description "Reversión a la VWAP intradía con gestión de riesgo conservadora"

#include <Trade/Trade.mqh>

input group "Sesión (hora del SERVIDOR del bróker)"
input int    InpSessionStartHour = 16;   // Hora de apertura de la sesión
input int    InpSessionStartMin  = 30;   // Minuto de apertura de la sesión
input int    InpWarmupMinutes    = 30;   // Minutos sin operar tras la apertura
input int    InpLastEntryHour    = 22;   // Última hora para abrir operaciones
input int    InpLastEntryMin     = 0;    // Último minuto para abrir operaciones
input int    InpCloseAllHour     = 22;   // Hora de cierre forzoso
input int    InpCloseAllMin      = 50;   // Minuto de cierre forzoso

input group "Señal"
input double InpEntryBands  = 2.0;       // Entrada: desviaciones desde la VWAP
input double InpStopBands   = 1.5;       // Stop-loss: desviaciones más allá de la entrada
input bool   InpAllowShorts = true;      // Permitir ventas en corto

input group "Riesgo"
input double InpRiskPercent         = 0.5;  // Riesgo por operación (% del equity)
input int    InpMaxTradesPerDay     = 3;    // Máximo de operaciones por día
input double InpMaxDailyLossPercent = 2.0;  // Pérdida diaria máxima (% del balance)
input bool   InpDemoOnly            = true; // Solo operar en cuentas demo
input long   InpMagic               = 240501; // Número mágico del EA

CTrade trade;

//--- fecha de hoy (hora del servidor) a la hora y minuto indicados
datetime TimeAt(int hour, int minute)
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   dt.hour = hour;
   dt.min  = minute;
   dt.sec  = 0;
   return StructToTime(dt);
  }

//--- VWAP y desviación estándar de la sesión con las velas M1 ya cerradas
bool CalcVwap(double &vwap, double &sd, double &lastClose)
  {
   datetime start    = TimeAt(InpSessionStartHour, InpSessionStartMin);
   datetime lastBar  = iTime(_Symbol, PERIOD_M1, 1);
   if(lastBar < start)
      return false;

   MqlRates rates[];
   int n = CopyRates(_Symbol, PERIOD_M1, start, lastBar, rates);
   if(n < 2)
      return false;

   double pv = 0, pv2 = 0, v = 0;
   for(int i = 0; i < n; i++)
     {
      double tp  = (rates[i].high + rates[i].low + rates[i].close) / 3.0;
      double vol = (double)MathMax(rates[i].tick_volume, 1);
      pv  += tp * vol;
      pv2 += tp * tp * vol;
      v   += vol;
     }
   vwap = pv / v;
   double variance = pv2 / v - vwap * vwap;
   sd = variance > 0 ? MathSqrt(variance) : 0;
   lastClose = rates[n - 1].close;
   return sd > 0;
  }

//--- ticket de la posición abierta por este EA en este símbolo (0 si no hay)
ulong OwnPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 &&
         PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagic)
         return ticket;
     }
   return 0;
  }

//--- operaciones abiertas hoy y resultado del día (cerrado + flotante)
void DailyStats(int &tradesToday, double &pnlToday)
  {
   tradesToday = 0;
   pnlToday    = 0;
   if(!HistorySelect(TimeAt(0, 0), TimeCurrent()))
      return;
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
     {
      ulong deal = HistoryDealGetTicket(i);
      if(HistoryDealGetString(deal, DEAL_SYMBOL) != _Symbol ||
         HistoryDealGetInteger(deal, DEAL_MAGIC) != InpMagic)
         continue;
      if(HistoryDealGetInteger(deal, DEAL_ENTRY) == DEAL_ENTRY_IN)
         tradesToday++;
      pnlToday += HistoryDealGetDouble(deal, DEAL_PROFIT)
                + HistoryDealGetDouble(deal, DEAL_COMMISSION)
                + HistoryDealGetDouble(deal, DEAL_SWAP);
     }
   ulong ticket = OwnPosition();
   if(ticket > 0 && PositionSelectByTicket(ticket))
      pnlToday += PositionGetDouble(POSITION_PROFIT);
  }

//--- lotes para arriesgar InpRiskPercent con un stop a slDistance (0 si no es posible)
double LotsForRisk(double slDistance)
  {
   double riskMoney = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPercent / 100.0;
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue <= 0 || tickSize <= 0 || slDistance <= 0)
      return 0;

   double lots = riskMoney / (slDistance / tickSize * tickValue);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minV = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxV = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   lots = MathFloor(lots / step) * step;
   if(lots < minV)
      return 0; // ni el lote mínimo cabe en el riesgo permitido
   return MathMin(lots, maxV);
  }

int OnInit()
  {
   if(InpDemoOnly && AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
     {
      Alert("VwapReversion: la cuenta no es DEMO y InpDemoOnly está activo. EA detenido.");
      return INIT_FAILED;
     }
   trade.SetExpertMagicNumber(InpMagic);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   Comment("");
  }

void OnTick()
  {
   //--- trabajar solo una vez por vela de 1 minuto
   static datetime lastProcessed = 0;
   datetime currentBar = iTime(_Symbol, PERIOD_M1, 0);
   if(currentBar == lastProcessed)
      return;
   lastProcessed = currentBar;

   datetime now = TimeCurrent();
   ulong ticket = OwnPosition();

   //--- cierre forzoso: nada queda abierto al final del día
   if(now >= TimeAt(InpCloseAllHour, InpCloseAllMin))
     {
      if(ticket > 0)
         trade.PositionClose(ticket);
      Comment("VwapReversion: fuera de horario");
      return;
     }

   double vwap, sd, close;
   if(!CalcVwap(vwap, sd, close))
     {
      Comment("VwapReversion: esperando la sesión");
      return;
     }

   int tradesToday;
   double pnlToday;
   DailyStats(tradesToday, pnlToday);
   double maxLoss = AccountInfoDouble(ACCOUNT_BALANCE) * InpMaxDailyLossPercent / 100.0;
   bool lossLimitHit = pnlToday <= -maxLoss;

   Comment(StringFormat("VwapReversion\nVWAP: %s   desv.: %s\nBandas: %s / %s\n"
                        "Operaciones hoy: %d/%d   Resultado hoy: %.2f%s",
                        DoubleToString(vwap, _Digits), DoubleToString(sd, _Digits),
                        DoubleToString(vwap - InpEntryBands * sd, _Digits),
                        DoubleToString(vwap + InpEntryBands * sd, _Digits),
                        tradesToday, InpMaxTradesPerDay, pnlToday,
                        lossLimitHit ? "\n** LÍMITE DE PÉRDIDA DIARIA ALCANZADO **" : ""));

   //--- gestionar la posición abierta: salir al volver a la VWAP
   if(ticket > 0 && PositionSelectByTicket(ticket))
     {
      long type = PositionGetInteger(POSITION_TYPE);
      if((type == POSITION_TYPE_BUY && close >= vwap) ||
         (type == POSITION_TYPE_SELL && close <= vwap) ||
         lossLimitHit)
         trade.PositionClose(ticket);
      return;
     }

   //--- condiciones para abrir una operación nueva
   if(lossLimitHit || tradesToday >= InpMaxTradesPerDay)
      return;
   datetime warmupEnd = TimeAt(InpSessionStartHour, InpSessionStartMin) + InpWarmupMinutes * 60;
   if(now < warmupEnd || now >= TimeAt(InpLastEntryHour, InpLastEntryMin))
      return;

   double slDistance = InpStopBands * sd;
   double minStop = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   if(slDistance <= minStop)
      return;
   double lots = LotsForRisk(slDistance);
   if(lots <= 0)
      return;

   if(close < vwap - InpEntryBands * sd)
     {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      trade.Buy(lots, _Symbol, ask, NormalizeDouble(ask - slDistance, _Digits), 0, "VWAP long");
     }
   else if(InpAllowShorts && close > vwap + InpEntryBands * sd)
     {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      trade.Sell(lots, _Symbol, bid, NormalizeDouble(bid + slDistance, _Digits), 0, "VWAP short");
     }
  }
//+------------------------------------------------------------------+
