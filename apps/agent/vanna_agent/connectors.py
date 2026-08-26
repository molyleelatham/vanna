"""Connector client for Runtime-provided data tools.

Each method wraps a `agent.connectors.call()` to a SuperLink/SuperGrid connector.
Connectors are configured at the Runtime level — this client provides typed access.

Also includes direct Alpha Vantage integration for demo purposes when Runtime
connectors are not available.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

from flwr.agentapp import AgentSession


@dataclass(frozen=True)
class MarketData:
    pair: str
    bid: float
    ask: float
    spread_bps: float
    volume_1h: float
    volatility_regime: str  # "calm" | "normal" | "high"
    timestamp: str


@dataclass(frozen=True)
class OrderFlowStats:
    provider: str
    quote_to_trade_ratio: float
    cancellation_rate: float
    avg_quote_age_ms: float
    rejection_asymmetry: float
    window: str


@dataclass(frozen=True)
class ExecutionHistory:
    provider: str
    pair: str
    size_bucket: str
    fill_probability: float
    avg_slippage_bps: float
    avg_latency_ms: float
    rejection_probability: float
    sample_count: int
    window: str


@dataclass(frozen=True)
class RiskMetrics:
    pair: str
    margin_utilization: float
    leverage_ratio: float
    correlated_exposure: float
    settlement_pressure: float
    timestamp: str


@dataclass(frozen=True)
class SurveillanceSignal:
    provider: str
    anomaly_score: float
    quote_to_trade_ratio: float
    cancellation_rate: float
    synchronized_quote_score: float
    cross_pair_anomaly_score: float
    pre_movement_activity_score: float
    sample_count: int
    window: str


@dataclass(frozen=True)
class FederationMetrics:
    cohort_size: int
    model_version: str
    model_age_seconds: int
    synchronized_routing_ratio: float
    anomalous_update_detected: bool


class ConnectorError(Exception):
    """Raised when a connector call fails."""
    def __init__(self, connector: str, message: str, fallback: str | None = None):
        self.connector = connector
        self.message = message
        self.fallback = fallback
        super().__init__(f"{connector}: {message}")


class AlphaVantageClient:
    """Direct Alpha Vantage API client for market data (demo fallback)."""

    BASE_URL = "https://www.alphavantage.co/query"
    FX_PAIRS = {
        "EUR/USD": ("EUR", "USD"),
        "GBP/USD": ("GBP", "USD"),
        "USD/JPY": ("USD", "JPY"),
        "USD/CHF": ("USD", "CHF"),
        "AUD/USD": ("AUD", "USD"),
        "USD/CAD": ("USD", "CAD"),
    }

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("ALPHAVANTAGE_API_KEY")
        if not self.api_key:
            raise ValueError("ALPHAVANTAGE_API_KEY not set")
        self._client = httpx.Client(timeout=10.0)

    def _pair_to_symbol(self, pair: str) -> tuple[str, str]:
        if pair not in self.FX_PAIRS:
            raise ValueError(f"Unsupported pair: {pair}")
        return self.FX_PAIRS[pair]

    def get_fx_rate(self, pair: str) -> dict[str, Any]:
        """Get real-time FX rate from Alpha Vantage."""
        from_curr, to_curr = self._pair_to_symbol(pair)
        params = {
            "function": "CURRENCY_EXCHANGE_RATE",
            "from_currency": from_curr,
            "to_currency": to_curr,
            "apikey": self.api_key,
        }
        resp = self._client.get(self.BASE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        if "Error Message" in data:
            raise ValueError(data["Error Message"])
        if "Note" in data:
            raise ValueError(f"API limit: {data['Note']}")
        rate_info = data.get("Realtime Currency Exchange Rate", {})
        return {
            "from_currency": rate_info.get("1. From_Currency Code"),
            "to_currency": rate_info.get("3. To_Currency Code"),
            "bid": float(rate_info.get("8. Bid Price", 0)),
            "ask": float(rate_info.get("9. Ask Price", 0)),
            "rate": float(rate_info.get("5. Exchange Rate", 0)),
            "timestamp": rate_info.get("6. Last Refreshed", ""),
        }


class ConnectorClient:
    """Typed wrapper around `agent.connectors.call()` for Vanna agents."""

    def __init__(self, agent: AgentSession) -> None:
        self.agent = agent
        self._call_count = 0
        self._max_calls = 10  # hard limit per run
        # Lazy-init Alpha Vantage for direct market data fallback
        self._av_client: AlphaVantageClient | None = None

    def _get_av_client(self) -> AlphaVantageClient:
        if self._av_client is None:
            self._av_client = AlphaVantageClient()
        return self._av_client

    def _call(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        if self._call_count >= self._max_calls:
            raise ConnectorError("rate_limit", f"Max connector calls ({self._max_calls}) exceeded")
        self._call_count += 1
        try:
            result = self.agent.connectors.call(tool, args)
            if isinstance(result, dict) and result.get("error"):
                raise ConnectorError(tool, result.get("message", "unknown"), result.get("fallback"))
            return result
        except Exception as e:
            raise ConnectorError(tool, str(e))

    # --- Market Data ---
    def market_data(self, pair: str, window: str = "1h") -> MarketData:
        """Real-time quotes, spread, volume, volatility regime.
        Tries Runtime connector first, falls back to Alpha Vantage direct.
        """
        try:
            raw = self._call("market_data", {"pair": pair, "window": window})
            return MarketData(
                pair=raw["pair"],
                bid=raw["bid"],
                ask=raw["ask"],
                spread_bps=raw["spread_bps"],
                volume_1h=raw["volume_1h"],
                volatility_regime=raw["volatility_regime"],
                timestamp=raw["timestamp"],
            )
        except ConnectorError:
            # Fallback: direct Alpha Vantage
            return self._market_data_alphavantage(pair)

    def _market_data_alphavantage(self, pair: str) -> MarketData:
        """Fetch market data directly from Alpha Vantage."""
        av = self._get_av_client()
        fx = av.get_fx_rate(pair)
        bid = fx["bid"]
        ask = fx["ask"]
        spread_bps = ((ask - bid) / bid) * 10000 if bid > 0 else 2.0
        # Alpha Vantage free tier doesn't give volume/volatility regime; synthesize
        return MarketData(
            pair=pair,
            bid=bid,
            ask=ask,
            spread_bps=spread_bps,
            volume_1h=1_000_000,  # placeholder
            volatility_regime="normal",  # placeholder
            timestamp=fx["timestamp"],
        )

    # --- Order Flow ---
    def order_flow(self, provider: str, window: str = "24h") -> OrderFlowStats:
        """Quote-to-trade, cancellation rate, quote age, rejection asymmetry."""
        raw = self._call("order_flow", {"provider": provider, "window": window})
        return OrderFlowStats(
            provider=raw["provider"],
            quote_to_trade_ratio=raw["quote_to_trade_ratio"],
            cancellation_rate=raw["cancellation_rate"],
            avg_quote_age_ms=raw["avg_quote_age_ms"],
            rejection_asymmetry=raw["rejection_asymmetry"],
            window=raw["window"],
        )

    # --- Execution History ---
    def execution_history(
        self,
        provider: str,
        pair: str,
        size_bucket: str,
        window: str = "7d",
    ) -> ExecutionHistory:
        """Bucketed fill prob, slippage, latency, rejection prob."""
        raw = self._call(
            "execution_history",
            {"provider": provider, "pair": pair, "size_bucket": size_bucket, "window": window},
        )
        return ExecutionHistory(
            provider=raw["provider"],
            pair=raw["pair"],
            size_bucket=raw["size_bucket"],
            fill_probability=raw["fill_probability"],
            avg_slippage_bps=raw["avg_slippage_bps"],
            avg_latency_ms=raw["avg_latency_ms"],
            rejection_probability=raw["rejection_probability"],
            sample_count=raw["sample_count"],
            window=raw["window"],
        )

    # --- Risk System ---
    def risk_metrics(self, pair: str) -> RiskMetrics:
        """Live margin, leverage, correlated exposure, settlement pressure."""
        raw = self._call("risk_system", {"pair": pair})
        return RiskMetrics(
            pair=raw["pair"],
            margin_utilization=raw["margin_utilization"],
            leverage_ratio=raw["leverage_ratio"],
            correlated_exposure=raw["correlated_exposure"],
            settlement_pressure=raw["settlement_pressure"],
            timestamp=raw["timestamp"],
        )

    # --- Surveillance ---
    def surveillance_signal(self, provider: str, window: str = "24h") -> SurveillanceSignal:
        """ManipulationWatch anomaly components."""
        raw = self._call("surveillance_feed", {"provider": provider, "window": window})
        return SurveillanceSignal(
            provider=raw["provider"],
            anomaly_score=raw["anomaly_score"],
            quote_to_trade_ratio=raw["quote_to_trade_ratio"],
            cancellation_rate=raw["cancellation_rate"],
            synchronized_quote_score=raw["synchronized_quote_score"],
            cross_pair_anomaly_score=raw["cross_pair_anomaly_score"],
            pre_movement_activity_score=raw["pre_movement_activity_score"],
            sample_count=raw["sample_count"],
            window=raw["window"],
        )

    # --- Federation ---
    def federation_metrics(self) -> FederationMetrics:
        """Cohort size, model version, freshness, sync routing ratio."""
        raw = self._call("federation_metrics", {})
        return FederationMetrics(
            cohort_size=raw["cohort_size"],
            model_version=raw["model_version"],
            model_age_seconds=raw["model_age_seconds"],
            synchronized_routing_ratio=raw["synchronized_routing_ratio"],
            anomalous_update_detected=raw["anomalous_update_detected"],
        )

    # --- Fallback Helpers ---
    def market_data_or_fallback(self, pair: str, window: str = "1h") -> MarketData:
        try:
            return self.market_data(pair, window)
        except ConnectorError as e:
            # Return synthetic calm market
            return MarketData(
                pair=pair, bid=1.0800, ask=1.0802, spread_bps=2.0,
                volume_1h=1_000_000, volatility_regime="normal", timestamp=""
            )

    def order_flow_or_fallback(self, provider: str, window: str = "24h") -> OrderFlowStats:
        try:
            return self.order_flow(provider, window)
        except ConnectorError:
            return OrderFlowStats(
                provider=provider, quote_to_trade_ratio=10.0, cancellation_rate=0.1,
                avg_quote_age_ms=50.0, rejection_asymmetry=0.02, window=window
            )

    def execution_history_or_fallback(
        self, provider: str, pair: str, size_bucket: str, window: str = "7d"
    ) -> ExecutionHistory:
        try:
            return self.execution_history(provider, pair, size_bucket, window)
        except ConnectorError:
            # Use static evidence as fallback
            return ExecutionHistory(
                provider=provider, pair=pair, size_bucket=size_bucket,
                fill_probability=0.75, avg_slippage_bps=0.5, avg_latency_ms=30.0,
                rejection_probability=0.25, sample_count=450, window=window
            )

    def risk_metrics_or_fallback(self, pair: str) -> RiskMetrics:
        try:
            return self.risk_metrics(pair)
        except ConnectorError:
            return RiskMetrics(
                pair=pair, margin_utilization=0.3, leverage_ratio=5.0,
                correlated_exposure=0.2, settlement_pressure=0.1, timestamp=""
            )

    def surveillance_signal_or_fallback(self, provider: str, window: str = "24h") -> SurveillanceSignal:
        try:
            return self.surveillance_signal(provider, window)
        except ConnectorError:
            return SurveillanceSignal(
                provider=provider, anomaly_score=0.1, quote_to_trade_ratio=5.0,
                cancellation_rate=0.05, synchronized_quote_score=0.05,
                cross_pair_anomaly_score=0.05, pre_movement_activity_score=0.05,
                sample_count=100, window=window
            )

    def federation_metrics_or_fallback(self) -> FederationMetrics:
        try:
            return self.federation_metrics()
        except ConnectorError:
            return FederationMetrics(
                cohort_size=5, model_version="fed-fallback", model_age_seconds=0,
                synchronized_routing_ratio=0.0, anomalous_update_detected=False
            )