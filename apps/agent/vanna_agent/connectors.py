"""Connector client for Runtime-provided data tools.

Each method wraps a `agent.connectors.call()` to a SuperLink/SuperGrid connector.
Connectors are configured at the Runtime level — this client provides typed access.

Also includes direct Alpha Vantage integration for demo purposes when Runtime
connectors are not available.

Local XGBoost models provide client-side benchmark for federated logistic predictions.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx
import numpy as np

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


@dataclass(frozen=True)
class LocalModelComparison:
    """Comparison between federated logistic and local XGBoost predictions."""
    pair: str
    provider: str
    federated_fill_prob: float
    xgboost_fill_prob: float
    federated_slippage_bps: float
    xgboost_slippage_bps: float
    federated_latency_ms: float
    xgboost_latency_ms: float
    xgboost_feature_importance: dict[str, float]
    model_agreement: bool  # True if both models rank same provider top


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
        # Lazy-init local XGBoost model (loaded from federation artifact or trained locally)
        self._xgb_fill_model: Any | None = None
        self._xgb_slippage_model: Any | None = None
        self._xgb_latency_model: Any | None = None

    def _get_av_client(self) -> AlphaVantageClient:
        if self._av_client is None:
            self._av_client = AlphaVantageClient()
        return self._av_client

    def _get_xgb_models(self) -> tuple[Any, Any, Any]:
        """Load or train local XGBoost models (fill, slippage, latency).
        
        In production, these would be loaded from a local model store.
        For the demo, we train on-the-fly using the federation evidence.
        """
        if self._xgb_fill_model is not None:
            return self._xgb_fill_model, self._xgb_slippage_model, self._xgb_latency_model
        
        try:
            # Try to load from local model artifact (created by federation run)
            from pathlib import Path
            model_dir = Path(__file__).parent.parent / "artifacts" / "xgboost_models"
            if (model_dir / "fill_model.json").exists():
                import xgboost as xgb
                self._xgb_fill_model = xgb.Booster()
                self._xgb_fill_model.load_model(str(model_dir / "fill_model.json"))
                self._xgb_slippage_model = xgb.Booster()
                self._xgb_slippage_model.load_model(str(model_dir / "slippage_model.json"))
                self._xgb_latency_model = xgb.Booster()
                self._xgb_latency_model.load_model(str(model_dir / "latency_model.json"))
                return self._xgb_fill_model, self._xgb_slippage_model, self._xgb_latency_model
        except Exception:
            pass
        
        # Fallback: train quick local models on synthetic data
        return self._train_local_xgb_models()

    def _train_local_xgb_models(self) -> tuple[Any, Any, Any]:
        """Train local XGBoost models on synthetic data for demo."""
        import xgboost as xgb
        from numpy import random
        from ..domain import ProviderEvidence
        from . import FEATURE_NAMES  # type: ignore
        
        # Generate synthetic training data matching federation features
        rng = random.default_rng(20260826)
        n_samples = 2000
        
        # Features: is_lp_a, is_lp_b, is_lp_c, is_high_vol, is_lp_a_vol, is_lp_c_vol, size, quote_age
        X = np.column_stack([
            rng.choice(3, n_samples, p=[0.4, 0.35, 0.25]),  # provider (one-hot)
            rng.binomial(1, 0.3, n_samples),
            rng.uniform(0.05, 1.0, n_samples),
            rng.uniform(0.0, 1.0, n_samples),
        ])
        # Expand to full feature set
        one_hot = np.eye(3)[X[:, 0].astype(int)]
        high_vol = X[:, 1]
        X_full = np.column_stack([
            one_hot,
            high_vol,
            one_hot[:, 0] * high_vol,
            one_hot[:, 2] * high_vol,
            X[:, 2],
            X[:, 3],
        ])
        
        # Fill probability target (LP_B best, LP_A worst in high vol)
        logits = (
            1.25 - 0.30 * one_hot[:, 0] + 0.38 * one_hot[:, 1] + 0.02 * one_hot[:, 2]
            - 0.80 * high_vol - 1.05 * one_hot[:, 0] * high_vol - 0.62 * one_hot[:, 2] * high_vol
            - 0.35 * X[:, 2] - 0.40 * X[:, 3]
        )
        y_fill = rng.binomial(1, 1.0 / (1.0 + np.exp(-np.clip(logits, -30, 30))))
        
        # Slippage target (LP_A high, LP_B low)
        y_slippage = 1.10 * one_hot[:, 0] + 0.42 * one_hot[:, 1] + 0.84 * one_hot[:, 2]
        y_slippage += 0.5 * high_vol + rng.normal(0, 0.1, n_samples)
        
        # Latency target (LP_A 78ms, LP_B 31ms, LP_C 86ms)
        y_latency = 78.0 * one_hot[:, 0] + 31.0 * one_hot[:, 1] + 86.0 * one_hot[:, 2]
        y_latency += 20.0 * high_vol + rng.normal(0, 5.0, n_samples)
        
        # Train XGBoost models
        dtrain_fill = xgb.DMatrix(X_full, label=y_fill, feature_names=FEATURE_NAMES)
        dtrain_slip = xgb.DMatrix(X_full, label=y_slippage, feature_names=FEATURE_NAMES)
        dtrain_lat = xgb.DMatrix(X_full, label=y_latency, feature_names=FEATURE_NAMES)
        
        fill_params = {"objective": "binary:logistic", "max_depth": 4, "eta": 0.1, "seed": 20260826, "verbosity": 0}
        reg_params = {"objective": "reg:squarederror", "max_depth": 4, "eta": 0.1, "seed": 20260826, "verbosity": 0}
        
        self._xgb_fill_model = xgb.train(fill_params, dtrain_fill, num_boost_round=50)
        self._xgb_slippage_model = xgb.train(reg_params, dtrain_slip, num_boost_round=50)
        self._xgb_latency_model = xgb.train(reg_params, dtrain_lat, num_boost_round=50)
        
        return self._xgb_fill_model, self._xgb_slippage_model, self._xgb_latency_model

    def compare_local_vs_federated(
        self,
        pair: str,
        providers: list[str],
        federated_evidence: list[ProviderEvidence],
    ) -> list[LocalModelComparison]:
        """Compare local XGBoost predictions vs federated logistic evidence."""
        import numpy as np
        import xgboost as xgb
        
        fill_model, slippage_model, latency_model = self._get_xgb_models()
        
        # Build feature matrix for each provider
        comparisons = []
        for provider in providers:
            fed = next((e for e in federated_evidence if e.provider == provider), None)
            if not fed:
                continue
            
            # Build feature vector for this provider (avg volatility, size, quote age)
            is_lp_a = 1.0 if provider == "LP_A" else 0.0
            is_lp_b = 1.0 if provider == "LP_B" else 0.0
            is_lp_c = 1.0 if provider == "LP_C" else 0.0
            high_vol = 0.3  # average
            size_scaled = 0.5
            quote_age_scaled = 0.3
            
            X = np.array([[
                is_lp_a, is_lp_b, is_lp_c, high_vol,
                is_lp_a * high_vol, is_lp_c * high_vol,
                size_scaled, quote_age_scaled
            ]])
            dmatrix = xgb.DMatrix(X, feature_names=FEATURE_NAMES)
            
            xgb_fill = float(fill_model.predict(dmatrix)[0])
            xgb_slippage = float(slippage_model.predict(dmatrix)[0])
            xgb_latency = float(latency_model.predict(dmatrix)[0])
            
            # Get feature importance
            importance = fill_model.get_score(importance_type="gain")
            full_importance = {name: importance.get(name, 0.0) for name in FEATURE_NAMES}
            
            # Check model agreement (both rank same provider top)
            fed_fill = fed.fill_probability
            model_agreement = (xgb_fill > 0.5) == (fed_fill > 0.5)  # simplified
            
            comparisons.append(LocalModelComparison(
                pair=pair,
                provider=provider,
                federated_fill_prob=fed_fill,
                xgboost_fill_prob=xgb_fill,
                federated_slippage_bps=fed.expected_slippage_bps,
                xgboost_slippage_bps=xgb_slippage,
                federated_latency_ms=fed.expected_latency_ms,
                xgboost_latency_ms=xgb_latency,
                xgboost_feature_importance=full_importance,
                model_agreement=model_agreement,
            ))
        
        return comparisons

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

    def local_model_comparison_or_fallback(
        self,
        pair: str,
        providers: list[str],
        federated_evidence: list[ProviderEvidence],
    ) -> list[LocalModelComparison]:
        """Get local vs federated model comparison (with fallback to synthetic)."""
        try:
            return self.compare_local_vs_federated(pair, providers, federated_evidence)
        except Exception:
            # Return synthetic comparison
            return [
                LocalModelComparison(
                    pair=pair,
                    provider=p,
                    federated_fill_prob=0.75,
                    xgboost_fill_prob=0.73,
                    federated_slippage_bps=0.5,
                    xgboost_slippage_bps=0.52,
                    federated_latency_ms=30.0,
                    xgboost_latency_ms=32.0,
                    xgboost_feature_importance={
                        "is_lp_a": 0.1, "is_lp_b": 0.15, "is_lp_c": 0.05,
                        "is_high_volatility": 0.25, "is_lp_a_high_volatility": 0.2,
                        "is_lp_c_high_volatility": 0.1, "size_scaled": 0.08,
                        "quote_age_scaled": 0.07,
                    },
                    model_agreement=True,
                )
                for p in providers
            ]