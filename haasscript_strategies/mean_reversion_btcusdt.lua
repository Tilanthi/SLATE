-- ============================================================================
-- SLATE Mean Reversion Strategy - BTCUSDT Binance Futures
-- ============================================================================
-- Strategy: Mean reversion using Bollinger Bands and RSI
-- Market: BTCUSDT Perpetual Futures on Binance
-- Timeframe: 1 Hour (recommended)
-- Risk: Paper trading only - NEVER execute live trades without testing
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Input Parameters
-- ----------------------------------------------------------------------------

local bbPeriod = Input("Bollinger Bands Period", 20)
local bbStdDev = Input("BB Standard Deviation", 2.0)
local rsiPeriod = Input("RSI Period", 14)
local rsiOversold = Input("RSI Oversold Level", 30)
local rsiOverbought = Input("RSI Overbought Level", 70)

local riskPerTrade = Input("Risk Per Trade (%)", 2.0)
local stopLossPct = Input("Stop Loss (%)", 3.0)
local takeProfitPct = Input("Take Profit (%)", 6.0)

-- ----------------------------------------------------------------------------
-- Get Price Data
-- ----------------------------------------------------------------------------

-- HaasScript uses 1-based indexing
-- ClosePrices() returns array from newest (index 1) to oldest
local closePrices = ClosePrices()
local highPrices = HighPrices()
local lowPrices = LowPrices()

-- Get current price (most recent = index 1 in HaasScript)
local currentPrice = IndexArray(closePrices, 1)

-- ----------------------------------------------------------------------------
-- Calculate Indicators
-- ----------------------------------------------------------------------------

-- Bollinger Bands
local bb = BB(closePrices, bbPeriod, bbStdDev)
local bbMiddle = bb.Middle   -- Middle band (SMA)
local bbUpper = bb.Upper     -- Upper band
local bbLower = bb.Lower     -- Lower band

-- Get current BB values (index 1 = most recent)
local currentBBMiddle = IndexArray(bbMiddle.Values, 1)
local currentBBUpper = IndexArray(bbUpper.Values, 1)
local currentBBLower = IndexArray(bbLower.Values, 1)

-- RSI
local rsi = RSI(closePrices, rsiPeriod)
local currentRSI = IndexArray(rsi.Values, 1)

-- ----------------------------------------------------------------------------
-- Calculate Position Size (Paper Trading)
-- ----------------------------------------------------------------------------

-- Calculate position size based on risk
local accountBalance = BalanceAmount()
local riskAmount = accountBalance * (riskPerTrade / 100)
local positionSize = riskAmount / (currentPrice * (stopLossPct / 100))

-- ----------------------------------------------------------------------------
-- Trading Logic - Mean Reversion
-- ----------------------------------------------------------------------------

-- Entry Conditions

-- LONG Entry: Price below lower BB AND RSI oversold
local longCondition = (currentPrice < currentBBLower) and (currentRSI < rsiOversold)

-- SHORT Entry: Price above upper BB AND RSI overbought
local shortCondition = (currentPrice > currentBBUpper) and (currentRSI > rsiOverbought)

-- Exit Conditions

-- Exit Long: Price crosses back above middle band OR RSI becomes overbought
local exitLongCondition = (currentPrice > currentBBMiddle) or (currentRSI > rsiOverbought)

-- Exit Short: Price crosses back below middle band OR RSI becomes oversold
local exitShortCondition = (currentPrice < currentBBMiddle) or (currentRSI < rsiOversold)

-- ----------------------------------------------------------------------------
-- Position State Check
-- ----------------------------------------------------------------------------

-- Get current position state
local currentPosition = GetPositionDirection()

-- HaasScript position values:
-- PositionLong() = 1 (long position)
-- PositionShort() = 2 (short position)
-- NoPosition() = 0 (no position)

-- ----------------------------------------------------------------------------
-- Execute Trades (Paper Trading Only)
-- ----------------------------------------------------------------------------

-- Enter Long
if longCondition and currentPosition == NoPosition() then
    DoLong("Mean Reversion: Price below BB Lower, RSI oversold")
    Log("LONG SIGNAL: Price=" .. currentPrice .. " BB_Lower=" .. currentBBLower .. " RSI=" .. currentRSI, "Green")

    -- Set stop loss and take profit
    StopLoss(stopLossPct)
    TakeProfit(takeProfitPct)
end

-- Enter Short
if shortCondition and currentPosition == NoPosition() then
    DoShort("Mean Reversion: Price above BB Upper, RSI overbought")
    Log("SHORT SIGNAL: Price=" .. currentPrice .. " BB_Upper=" .. currentBBUpper .. " RSI=" .. currentRSI, "Red")

    -- Set stop loss and take profit
    StopLoss(stopLossPct)
    TakeProfit(takeProfitPct)
end

-- Exit Long Position
if exitLongCondition and currentPosition == PositionLong() then
    DoExitPosition("Exit Long: Price reverted to mean or RSI overbought")
    Log("EXIT LONG: Price=" .. currentPrice .. " RSI=" .. currentRSI, "Yellow")
end

-- Exit Short Position
if exitShortCondition and currentPosition == PositionShort() then
    DoExitPosition("Exit Short: Price reverted to mean or RSI oversold")
    Log("EXIT SHORT: Price=" .. currentPrice .. " RSI=" .. currentRSI, "Yellow")
end

-- ----------------------------------------------------------------------------
-- Logging and Monitoring
-- ----------------------------------------------------------------------------

-- Log current state every tick
Log("BTCUSDT | Price: " .. currentPrice .. " | BB: " .. currentBBLower .. " - " .. currentBBMiddle .. " - " .. currentBBUpper .. " | RSI: " .. currentRSI .. " | Position: " .. tostring(currentPosition))

-- Custom report values
CustomReport("Price", currentPrice)
CustomReport("BB_Upper", currentBBUpper)
CustomReport("BB_Lower", currentBBLower)
CustomReport("RSI", currentRSI)
CustomReport("Position", currentPosition)
