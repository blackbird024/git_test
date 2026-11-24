//+------------------------------------------------------------------+
//|                                      GannHiLo_XAUUSD_EA.mq5       |
//|  EA para XAUUSD H1: entradas buy stop sobre el máximo de N velas |
//|  anteriores, filtradas por el Gann HiLo Activator.                |
//+------------------------------------------------------------------+
#property copyright "GannHiLo_XAUUSD_EA"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== Señal: Gann HiLo Activator ==="
input int      InpHiLoPeriod       = 5;     // Periodo del Gann HiLo Activator
input int      InpHiLoLookback     = 300;   // Velas usadas para reconstruir la tendencia del HiLo

input group "=== Entrada ==="
input int      InpHighestLookback  = 51;    // Nº de velas anteriores para el máximo de entrada
input int      InpSignalExpiryBars = 10;    // Velas de validez de la orden pendiente

input group "=== Stop Loss / Salida ==="
input int      InpATRPeriod        = 95;    // Periodo del ATR
input double   InpATRMultiplier    = 1.0;   // Multiplicador de ATR para el stop loss
input int      InpExitBars         = 5;     // Velas tras la entrada para cerrar la operación

input group "=== Gestión de riesgo ==="
input double   InpRiskPercent      = 0.3;   // % del balance a arriesgar por operación

input group "=== General ==="
input ulong    InpMagicNumber      = 20261124;         // Número mágico
input string   InpTradeComment     = "GannHiLo_XAUUSD"; // Comentario de las operaciones

CTrade   trade;
int      g_atrHandle   = INVALID_HANDLE;
datetime g_lastBarTime = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   if(_Symbol != "XAUUSD")
      Print("Aviso: este EA está diseñado para XAUUSD. Símbolo actual: ", _Symbol);

   if(_Period != PERIOD_H1)
      Print("Aviso: este EA está diseñado para el timeframe H1. Timeframe actual: ", EnumToString(_Period));

   g_atrHandle = iATR(_Symbol, _Period, InpATRPeriod);
   if(g_atrHandle == INVALID_HANDLE)
     {
      Print("Error al crear el indicador ATR(", InpATRPeriod, ")");
      return(INIT_FAILED);
     }

   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetTypeFillingBySymbol(_Symbol);

   g_lastBarTime = 0;

   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_atrHandle != INVALID_HANDLE)
      IndicatorRelease(g_atrHandle);
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   if(!IsNewBar())
      return;

   ManageOpenPosition();

   if(!HasOpenPosition())
      CheckForSignalAndTrade();
  }

//+------------------------------------------------------------------+
//| Devuelve true solo en el primer tick de cada vela nueva           |
//+------------------------------------------------------------------+
bool IsNewBar()
  {
   datetime currentBarTime = iTime(_Symbol, _Period, 0);
   if(currentBarTime != g_lastBarTime)
     {
      g_lastBarTime = currentBarTime;
      return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
bool HasOpenPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == (long)InpMagicNumber)
         return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
//| Cierra la posición abierta InpExitBars velas después de entrar    |
//+------------------------------------------------------------------+
void ManageOpenPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagicNumber)
         continue;

      datetime openTime     = (datetime)PositionGetInteger(POSITION_TIME);
      int      openBarShift = iBarShift(_Symbol, _Period, openTime, false);

      if(openBarShift >= InpExitBars)
        {
         if(!trade.PositionClose(ticket))
            Print("Error al cerrar la posición #", ticket, ": ", trade.ResultRetcodeDescription());
        }
     }
  }

//+------------------------------------------------------------------+
//| Elimina las órdenes pendientes buy stop propias de este EA        |
//+------------------------------------------------------------------+
void DeletePendingOrders()
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0)
         continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol)
         continue;
      if(OrderGetInteger(ORDER_MAGIC) != (long)InpMagicNumber)
         continue;

      ENUM_ORDER_TYPE type = (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
      if(type == ORDER_TYPE_BUY_STOP)
         trade.OrderDelete(ticket);
     }
  }

//+------------------------------------------------------------------+
//| Evalúa la señal (mínimo de la vela anterior toca/perfora el       |
//| Gann HiLo Activator) y, si procede, coloca la orden buy stop       |
//+------------------------------------------------------------------+
void CheckForSignalAndTrade()
  {
   double hiloValue = CalculateGannHiLo(1);
   if(hiloValue <= 0.0)
      return; // histórico insuficiente todavía

   double prevLow[];
   if(CopyLow(_Symbol, _Period, 1, 1, prevLow) != 1)
      return;

   bool signal = (prevLow[0] <= hiloValue);
   if(!signal)
      return;

   double entryPrice = HighestHigh(1, InpHighestLookback);
   if(entryPrice <= 0.0)
      return;

   double atr[];
   if(CopyBuffer(g_atrHandle, 0, 1, 1, atr) != 1)
      return;

   double slDistance = atr[0] * InpATRMultiplier;
   if(slDistance <= 0.0)
      return;

   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   entryPrice = NormalizeDouble(entryPrice, digits);
   double slPrice = NormalizeDouble(entryPrice - slDistance, digits);

   double ask            = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double stopLevelPoints = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   if(entryPrice <= ask + stopLevelPoints)
     {
      Print("Señal detectada pero el nivel de entrada (", entryPrice,
            ") no es válido para una orden Buy Stop (Ask=", ask, "). Señal descartada.");
      return;
     }

   double lot = CalculateLotSize(entryPrice - slPrice);
   if(lot <= 0.0)
     {
      Print("No se pudo calcular un volumen válido para la operación.");
      return;
     }

   DeletePendingOrders();

   datetime expiration = iTime(_Symbol, _Period, 0) + (datetime)(InpSignalExpiryBars * PeriodSeconds(_Period));

   if(!trade.BuyStop(lot, entryPrice, _Symbol, slPrice, 0.0, ORDER_TIME_SPECIFIED, expiration, InpTradeComment))
      Print("Error al colocar la orden Buy Stop: ", trade.ResultRetcodeDescription());
   else
      Print("Nueva orden Buy Stop: precio=", entryPrice, " SL=", slPrice,
            " lote=", lot, " expira=", TimeToString(expiration));
  }

//+------------------------------------------------------------------+
//| Máximo de 'count' velas empezando 'startShift' velas atrás         |
//+------------------------------------------------------------------+
double HighestHigh(int startShift, int count)
  {
   double highArr[];
   int copied = CopyHigh(_Symbol, _Period, startShift, count, highArr);
   if(copied <= 0)
      return 0.0;

   int idx = ArrayMaximum(highArr, 0, copied);
   return highArr[idx];
  }

//+------------------------------------------------------------------+
//| Calcula el tamaño de lote según el % de riesgo y la distancia al  |
//| stop loss                                                          |
//+------------------------------------------------------------------+
double CalculateLotSize(double slDistance)
  {
   if(slDistance <= 0.0)
      return 0.0;

   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * (InpRiskPercent / 100.0);

   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue <= 0.0 || tickSize <= 0.0)
      return 0.0;

   double lossPerLot = (slDistance / tickSize) * tickValue;
   if(lossPerLot <= 0.0)
      return 0.0;

   double lot = riskMoney / lossPerLot;

   double volMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double volMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double volStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   if(volStep > 0.0)
      lot = MathFloor(lot / volStep) * volStep;

   lot = MathMax(volMin, MathMin(volMax, lot));

   int lotDigits = (volStep > 0.0) ? (int)MathRound(-MathLog10(volStep)) : 2;
   if(lotDigits < 0)
      lotDigits = 0;
   lot = NormalizeDouble(lot, lotDigits);

   if(lot < volMin)
      return 0.0;

   return lot;
  }

//+------------------------------------------------------------------+
//| Calcula el valor del Gann HiLo Activator en el 'shiftTarget'       |
//| indicado (1 = última vela cerrada). Devuelve 0 si no hay           |
//| histórico suficiente.                                              |
//+------------------------------------------------------------------+
double CalculateGannHiLo(int shiftTarget)
  {
   int size = InpHiLoLookback;
   int available = iBars(_Symbol, _Period) - 1; // excluye la vela en formación
   if(available < size)
      size = available;
   if(size < InpHiLoPeriod + 2)
      return 0.0;

   double high[], low[], close[];
   int copiedH = CopyHigh(_Symbol, _Period, 1, size, high);
   int copiedL = CopyLow(_Symbol, _Period, 1, size, low);
   int copiedC = CopyClose(_Symbol, _Period, 1, size, close);

   if(copiedH != size || copiedL != size || copiedC != size)
      return 0.0;

   double hiMA[], loMA[], hilo[];
   int    trend[];
   ArrayResize(hiMA, size);
   ArrayResize(loMA, size);
   ArrayResize(hilo, size);
   ArrayResize(trend, size);

   // Medias móviles simples de máximos y mínimos (orden cronológico: 0=más antigua)
   for(int i = 0; i < size; i++)
     {
      if(i < InpHiLoPeriod - 1)
        {
         hiMA[i] = 0.0;
         loMA[i] = 0.0;
         continue;
        }
      double sumH = 0.0, sumL = 0.0;
      for(int k = 0; k < InpHiLoPeriod; k++)
        {
         sumH += high[i - k];
         sumL += low[i - k];
        }
      hiMA[i] = sumH / InpHiLoPeriod;
      loMA[i] = sumL / InpHiLoPeriod;
     }

   // Tendencia y línea del Gann HiLo Activator
   for(int i = 0; i < size; i++)
     {
      if(i < InpHiLoPeriod)
        {
         trend[i] = 0;
         hilo[i]  = 0.0;
         continue;
        }

      if(close[i] > hiMA[i - 1])
         trend[i] = 1;
      else if(close[i] < loMA[i - 1])
         trend[i] = -1;
      else
         trend[i] = (trend[i - 1] != 0) ? trend[i - 1] : 1;

      hilo[i] = (trend[i] == 1) ? loMA[i] : hiMA[i];
     }

   int targetIndex = size - shiftTarget;
   if(targetIndex < InpHiLoPeriod || targetIndex >= size)
      return 0.0;

   return hilo[targetIndex];
  }
//+------------------------------------------------------------------+
