//+------------------------------------------------------------------+
//| IbsSwing.mq5                                                      |
//| Swing trading con IBS (Internal Bar Strength) en NAS100 y oro.    |
//|                                                                   |
//| - Cada día, unos minutos antes del cierre de la bolsa de EE. UU., |
//|   calcula dónde está el precio dentro del rango de la sesión      |
//|   9:30-16:00 de Nueva York: IBS = (precio - mínimo) / (máx - mín).|
//| - IBS < 0.2 (cerca del mínimo del día): compra.                   |
//| - IBS > 0.8 (cerca del máximo del día): cierra la compra.         |
//| - Solo compras. Las operaciones duran unos 3-4 días.              |
//| - Funciona en un solo gráfico y opera los dos símbolos.           |
//| - Por defecto solo opera en cuentas DEMO.                         |
//+------------------------------------------------------------------+
#property copyright "git_test"
#property version   "1.00"
#property description "IBS swing trading en NAS100 y XAUUSD (cierre de la sesión de Nueva York)"

#include <Trade/Trade.mqh>

input group "Símbolos (nombres exactos del bróker)"
input string InpSymbol1 = "NAS100";   // Símbolo 1 ("" = no usar)
input string InpSymbol2 = "XAUUSD";   // Símbolo 2 ("" = no usar)

input group "Horario"
input int    InpServerMinusNY = 7;    // Horas que el servidor va por delante de Nueva York (Pepperstone: 7)
input int    InpDecisionHour  = 15;   // Hora de decisión (Nueva York)
input int    InpDecisionMin   = 55;   // Minuto de decisión (Nueva York)
input int    InpSessionStartHour = 9;  // Inicio de la sesión para el rango (Nueva York). Londres: 3
input int    InpSessionStartMin  = 30; // Minuto de inicio de la sesión (Nueva York). Londres: 0

input group "Señal"
input double InpEntryIbs = 0.20;      // Comprar si IBS < este valor
input double InpExitIbs  = 0.80;      // Cerrar si IBS > este valor

input group "Tamaño y riesgo"
input double InpAllocationPct    = 50.0; // % del equity por símbolo
input double InpExposure         = 1.0;  // Exposición (1.0 = 1x; usar 0.5 para cuentas con 6% de DD máx)
input double InpMaxDailyLossPct  = 3.5;  // Pérdida diaria máxima: cierra todo y no opera más ese día (0 = no)
input bool   InpDemoOnly         = true; // Solo operar en cuentas demo
input long   InpMagic            = 240601; // Número mágico

CTrade   trade;
string   symbols[2];
datetime lastDecisionDay[2];
datetime equityDay = 0;
double   dayStartEquity = 0;
bool     dailyLossHit = false;

//--- hora de Nueva York a partir de la hora del servidor
datetime ToNY(datetime server) { return server - InpServerMinusNY * 3600; }
datetime ToServer(datetime ny) { return ny + InpServerMinusNY * 3600; }

//--- medianoche del día de una fecha
datetime DayOf(datetime t)
  {
   MqlDateTime dt;
   TimeToStruct(t, dt);
   dt.hour = 0;
   dt.min  = 0;
   dt.sec  = 0;
   return StructToTime(dt);
  }

//--- ticket de la posición de este EA en el símbolo (0 si no hay)
ulong OwnPosition(string symbol)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 &&
         PositionGetString(POSITION_SYMBOL) == symbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagic)
         return ticket;
     }
   return 0;
  }

//--- IBS de la sesión de hoy (9:30 NY hasta ahora) con velas M1
bool SessionIbs(string symbol, double &ibs, double &high, double &low, double &price)
  {
   datetime nyNow   = ToNY(TimeCurrent());
   datetime nyOpen  = DayOf(nyNow) + InpSessionStartHour * 3600 + InpSessionStartMin * 60;
   int expected = (int)((DayOf(nyNow) + InpDecisionHour * 3600 + InpDecisionMin * 60 - nyOpen) / 60);
   MqlRates rates[];
   int n = CopyRates(symbol, PERIOD_M1, ToServer(nyOpen), TimeCurrent(), rates);
   if(n < expected * 0.75)   // sesión incompleta (festivo, cierre anticipado o sin datos)
      return false;

   high = rates[0].high;
   low  = rates[0].low;
   for(int i = 1; i < n; i++)
     {
      high = MathMax(high, rates[i].high);
      low  = MathMin(low, rates[i].low);
     }
   price = SymbolInfoDouble(symbol, SYMBOL_BID);
   if(high <= low || price <= 0)
      return false;
   ibs = (price - low) / (high - low);
   return true;
  }

//--- lotes para una exposición de InpAllocationPct * InpExposure del equity
double LotsFor(string symbol)
  {
   double price     = SymbolInfoDouble(symbol, SYMBOL_ASK);
   double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   if(price <= 0 || tickValue <= 0 || tickSize <= 0)
      return 0;

   double notionalPerLot = price * tickValue / tickSize;   // valor de 1 lote en la moneda de la cuenta
   double target = AccountInfoDouble(ACCOUNT_EQUITY) * InpAllocationPct / 100.0 * InpExposure;
   double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   double minV = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double maxV = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double lots = MathFloor(target / notionalPerLot / step) * step;
   if(lots < minV)
     {
      PrintFormat("IbsSwing: %s necesita %.4f lotes, por debajo del mínimo %.2f; no se opera.",
                  symbol, target / notionalPerLot, minV);
      return 0;
     }
   return MathMin(lots, maxV);
  }

//--- pérdida diaria: equity frente al inicio del día del servidor
void CheckDailyLoss()
  {
   datetime today = DayOf(TimeCurrent());
   if(today != equityDay)
     {
      equityDay      = today;
      dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      dailyLossHit   = false;
     }
   if(InpMaxDailyLossPct <= 0 || dailyLossHit)
      return;
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity <= dayStartEquity * (1 - InpMaxDailyLossPct / 100.0))
     {
      dailyLossHit = true;
      for(int k = 0; k < 2; k++)
        {
         ulong ticket = symbols[k] == "" ? (ulong)0 : OwnPosition(symbols[k]);
         if(ticket > 0)
            trade.PositionClose(ticket);
        }
      Alert("IbsSwing: pérdida diaria de ", DoubleToString(InpMaxDailyLossPct, 1),
            "% alcanzada. Posiciones cerradas; no se opera más hoy.");
     }
  }

void Decide(int k)
  {
   string symbol = symbols[k];
   double ibs, high, low, price;
   if(!SessionIbs(symbol, ibs, high, low, price))
     {
      PrintFormat("IbsSwing: %s sin sesión completa hoy; no se decide.", symbol);
      return;
     }
   ulong ticket = OwnPosition(symbol);
   PrintFormat("IbsSwing: %s IBS %.2f (precio %s, rango %s - %s), posición: %s",
               symbol, ibs, DoubleToString(price, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS)),
               DoubleToString(low, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS)),
               DoubleToString(high, (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS)),
               ticket > 0 ? "abierta" : "ninguna");

   if(ticket > 0 && ibs > InpExitIbs)
      trade.PositionClose(ticket);
   else if(ticket == 0 && ibs < InpEntryIbs && !dailyLossHit)
     {
      double lots = LotsFor(symbol);
      if(lots > 0)
         trade.Buy(lots, symbol, 0, 0, 0, "IBS entrada");
     }
  }

int OnInit()
  {
   bool tester = (bool)MQLInfoInteger(MQL_TESTER);
   if(InpDemoOnly && !tester && AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
     {
      Alert("IbsSwing: la cuenta no es DEMO y InpDemoOnly está activo. EA detenido.");
      return INIT_FAILED;
     }
   symbols[0] = InpSymbol1;
   symbols[1] = InpSymbol2;
   for(int k = 0; k < 2; k++)
     {
      lastDecisionDay[k] = 0;
      if(symbols[k] != "" && !SymbolSelect(symbols[k], true))
        {
         Alert("IbsSwing: el símbolo ", symbols[k], " no existe en este bróker. Revisa el nombre.");
         return INIT_FAILED;
        }
     }
   trade.SetExpertMagicNumber(InpMagic);
   EventSetTimer(tester ? 60 : 20);   // en el probador, cada minuto basta y va más rápido
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   Comment("");
  }

void OnTimer()
  {
   CheckDailyLoss();

   datetime nyNow = ToNY(TimeCurrent());
   datetime nyDay = DayOf(nyNow);
   datetime decision = nyDay + InpDecisionHour * 3600 + InpDecisionMin * 60;
   bool window = nyNow >= decision && nyNow < decision + 4 * 60;

   string status = StringFormat("IbsSwing   Hora NY: %s   Decisión: %02d:%02d NY\n",
                                TimeToString(nyNow, TIME_MINUTES), InpDecisionHour, InpDecisionMin);
   for(int k = 0; k < 2; k++)
     {
      if(symbols[k] == "")
         continue;
      if(window && lastDecisionDay[k] != nyDay)
        {
         lastDecisionDay[k] = nyDay;
         Decide(k);
        }
      double ibs, high, low, price;
      string ibsText = SessionIbs(symbols[k], ibs, high, low, price) ? DoubleToString(ibs, 2) : "-";
      status += StringFormat("%s: IBS ahora %s, posición %s\n", symbols[k], ibsText,
                             OwnPosition(symbols[k]) > 0 ? "abierta" : "ninguna");
     }
   if(dailyLossHit)
      status += "** LÍMITE DE PÉRDIDA DIARIA ALCANZADO **\n";
   if(!MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_VISUAL_MODE))
      Comment(status);
  }
//+------------------------------------------------------------------+
