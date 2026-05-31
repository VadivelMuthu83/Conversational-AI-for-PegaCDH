"""
CDH-Aware File Parser
=====================
Extends the base FileParser with CDH-specific intelligence:

1. Auto-detects which of the 5 CDH data sources a file is
2. Pre-aggregates Interaction History before chunking
   (raw IH has millions of rows — aggregate to Action×Channel×Week)
3. Attaches CDH source metadata to every chunk (for filtered retrieval)
4. Generates domain-aware text summaries for ADM/Value Finder data
"""
import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.cdh.sources import CDHDataSource, detect_source
from app.parsers.file_parser import FileParser, ParsedFile

logger = logging.getLogger(__name__)


class CDHFileParser(FileParser):
    """
    Drop-in replacement for FileParser that applies CDH-specific
    parsing logic when a file is recognised as a CDH data source.
    """

    def parse_bytes(self, content: bytes, filename: str) -> List[ParsedFile]:
        """
        Override: detect CDH source first, apply domain-specific parsing,
        fall back to base parser for unknown files.
        """
        source = detect_source(filename)

        if source is None:
            logger.debug(f"No CDH source detected for {filename} — using base parser")
            return super().parse_bytes(content, filename)

        logger.info(f"CDH source detected: {source.display_name} → {filename}")

        try:
            return self._parse_cdh(content, filename, source)
        except Exception as e:
            logger.warning(f"CDH parse failed for {filename} ({e}) — falling back to base parser")
            return super().parse_bytes(content, filename)

    def _parse_cdh(self, content: bytes, filename: str,
                   source: CDHDataSource) -> List[ParsedFile]:
        ext = Path(filename).suffix.lower()

        # Load into DataFrame
        df = self._load_dataframe(content, filename, ext)
        if df is None:
            return super().parse_bytes(content, filename)

        # Normalize column names (lowercase + strip)
        df.columns = [c.strip().lower() for c in df.columns]

        # Source-specific processing
        dispatch = {
            "interaction_history": self._process_ih,
            "adm_snapshot":        self._process_adm,
            "explainability_extract": self._process_explainability,
            "actuals_dataset":     self._process_actuals,
            "value_finder":        self._process_value_finder,
        }

        processor = dispatch.get(source.source_id, self._process_generic)
        return processor(df, filename, source)

    # ─── Source processors ────────────────────────────────────────────────────

    def _process_ih(self, df, filename: str, source: CDHDataSource) -> List[ParsedFile]:
        """
        Interaction History: aggregate to Action × Channel × Week.
        Raw IH can have millions of rows — we summarize before indexing.
        """
        import pandas as pd
        import numpy as np

        col = df.columns.tolist()
        logger.info(f"IH raw shape: {df.shape}")

        # Detect key columns (case-insensitive)
        action_col   = self._find_col(col, ["actionname", "action", "name"])
        channel_col  = self._find_col(col, ["channel", "direction"])
        outcome_col  = self._find_col(col, ["outcome", "pyoutcome", "label"])
        prop_col     = self._find_col(col, ["propensity", "finalpropensity"])
        priority_col = self._find_col(col, ["priority", "arbitrationpriority"])
        time_col     = self._find_col(col, ["decisiontime", "pxdecisiontime", "outcometime"])

        # Parse datetime and extract week
        if time_col:
            try:
                df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
                df["_week"] = df[time_col].dt.to_period("W").astype(str)
            except Exception:
                df["_week"] = "unknown"
        else:
            df["_week"] = "unknown"

        # Build aggregation
        group_cols = [c for c in [action_col, channel_col, "_week"] if c]
        if not group_cols:
            return self._process_generic(df, filename, source)

        agg: Dict[str, Any] = {}
        agg["_impressions"] = (df.index, "count")

        if outcome_col:
            outcome_lower = df[outcome_col].str.lower().fillna("")
            df["_accepted"] = outcome_lower.isin(
                ["accepted", "clicked", "positive", "accept", "click", "1", "converted"]
            ).astype(int)
            df["_rejected"] = outcome_lower.isin(
                ["rejected", "ignored", "negative", "reject", "0"]
            ).astype(int)

        numeric_agg = {}
        if prop_col:
            numeric_agg[prop_col] = "mean"
        if priority_col:
            numeric_agg[priority_col] = "mean"
        if "_accepted" in df.columns:
            numeric_agg["_accepted"] = "sum"
        if "_rejected" in df.columns:
            numeric_agg["_rejected"] = "sum"

        try:
            grouped = df.groupby(group_cols).agg(
                impressions=("_week" if "_week" in group_cols else group_cols[0], "count"),
                **{k: (k, v) for k, v in numeric_agg.items()}
            ).reset_index()

            if "_accepted" in grouped.columns and "impressions" in grouped.columns:
                grouped["accept_rate"] = (
                    grouped["_accepted"] / grouped["impressions"].replace(0, np.nan)
                ).round(4)

            grouped.rename(columns={
                action_col: "ActionName",
                channel_col: "Channel",
                "_week": "Week",
                prop_col: "AvgPropensity" if prop_col else prop_col,
                priority_col: "AvgPriority" if priority_col else priority_col,
                "_accepted": "Accepts",
                "_rejected": "Rejects",
            }, inplace=True)

        except Exception as e:
            logger.warning(f"IH aggregation failed ({e}) — using raw sample")
            grouped = df.head(500)

        logger.info(f"IH aggregated: {len(grouped)} rows (from {len(df)} raw)")
        return [self._df_to_cdh_parsed(grouped, filename, source, extra_meta={
            "raw_row_count": len(df),
            "aggregated_row_count": len(grouped),
            "aggregation": "Action × Channel × Week",
        })]

    def _process_adm(self, df, filename: str, source: CDHDataSource) -> List[ParsedFile]:
        """ADM Snapshot: sort by AUC, flag underperformers."""
        auc_col = self._find_col(df.columns, ["auc", "performance"])
        action_col = self._find_col(df.columns, ["actionname", "modelname", "name"])

        text_parts = [
            f"ADM Model Snapshot — {filename}",
            f"Total models: {len(df)}",
        ]

        if auc_col:
            try:
                df[auc_col] = df[auc_col].astype(float)
                mean_auc = df[auc_col].mean()
                low_perf = df[df[auc_col] < 0.6]
                text_parts.append(f"Average AUC: {mean_auc:.3f}")
                text_parts.append(f"Models with AUC < 0.6 (underperforming): {len(low_perf)}")
                if action_col and len(low_perf) > 0:
                    names = low_perf[action_col].tolist()[:10]
                    text_parts.append(f"Underperforming model names: {', '.join(str(n) for n in names)}")
                top = df.nlargest(10, auc_col)
                text_parts.append(f"\nTop 10 models by AUC:\n{top.to_string(index=False)}")
            except Exception as e:
                logger.debug(f"ADM AUC processing: {e}")

        text_parts.append(f"\nFull snapshot sample:\n{df.head(50).to_string(index=False)}")
        return [self._df_to_cdh_parsed(df, filename, source, text_override="\n\n".join(text_parts))]

    def _process_explainability(self, df, filename: str, source: CDHDataSource) -> List[ParsedFile]:
        """Explainability: aggregate predictor importance across customers."""
        pred_col   = self._find_col(df.columns, ["predictorname", "predictor", "feature"])
        weight_col = self._find_col(df.columns, ["predictorweight", "weight", "importance"])
        action_col = self._find_col(df.columns, ["actionname", "action"])

        text_parts = [f"Explainability Extract — {filename}", f"Records: {len(df)}"]

        if pred_col and weight_col:
            try:
                df[weight_col] = df[weight_col].astype(float)
                group_cols = [c for c in [action_col, pred_col] if c]
                importance = (
                    df.groupby(group_cols)[weight_col]
                    .agg(["mean", "count"])
                    .reset_index()
                    .sort_values("mean", ascending=False)
                )
                text_parts.append(f"\nTop predictor importance:\n{importance.head(20).to_string(index=False)}")
            except Exception as e:
                logger.debug(f"Explainability aggregation: {e}")

        text_parts.append(f"\nSample rows:\n{df.head(30).to_string(index=False)}")
        return [self._df_to_cdh_parsed(df, filename, source, text_override="\n\n".join(text_parts))]

    def _process_actuals(self, df, filename: str, source: CDHDataSource) -> List[ParsedFile]:
        """Actuals: compute lift and accuracy metrics."""
        prop_col    = self._find_col(df.columns, ["modelpropensity", "propensity"])
        actual_col  = self._find_col(df.columns, ["actuallabel", "actual", "outcome"])
        action_col  = self._find_col(df.columns, ["actionname", "action"])
        channel_col = self._find_col(df.columns, ["channel"])

        text_parts = [f"Actuals Dataset — {filename}", f"Records: {len(df)}"]

        if actual_col:
            try:
                df[actual_col] = df[actual_col].astype(float)
                overall_rate = df[actual_col].mean()
                text_parts.append(f"Overall positive rate: {overall_rate:.2%}")

                group_cols = [c for c in [action_col, channel_col] if c]
                if group_cols:
                    lift = df.groupby(group_cols)[actual_col].agg(
                        actual_rate="mean", count="count"
                    ).reset_index()
                    lift["lift"] = (lift["actual_rate"] / overall_rate).round(3)
                    lift = lift.sort_values("lift", ascending=False)
                    text_parts.append(f"\nLift by Action × Channel:\n{lift.head(20).to_string(index=False)}")
            except Exception as e:
                logger.debug(f"Actuals lift calculation: {e}")

        text_parts.append(f"\nSample rows:\n{df.head(30).to_string(index=False)}")
        return [self._df_to_cdh_parsed(df, filename, source, text_override="\n\n".join(text_parts))]

    def _process_value_finder(self, df, filename: str, source: CDHDataSource) -> List[ParsedFile]:
        """Value Finder: identify underserved segments and total opportunity."""
        value_col   = self._find_col(df.columns, ["valuescore", "value", "businessvalue"])
        engage_col  = self._find_col(df.columns, ["engagementscore", "engagement"])
        opp_col     = self._find_col(df.columns, ["opportunityvalue", "opportunity"])
        segment_col = self._find_col(df.columns, ["segmentname", "segment", "name"])
        quadrant_col = self._find_col(df.columns, ["quadrant", "category"])

        text_parts = [f"Value Finder Output — {filename}", f"Segments: {len(df)}"]

        if value_col and engage_col:
            try:
                df[value_col]  = df[value_col].astype(float)
                df[engage_col] = df[engage_col].astype(float)
                df["_gap"] = df[value_col] - df[engage_col]
                underserved = df[df["_gap"] > 10].sort_values("_gap", ascending=False)
                text_parts.append(f"Underserved segments (value > engagement by >10pts): {len(underserved)}")
                if opp_col:
                    total_opp = df[df["_gap"] > 0][opp_col].sum()
                    text_parts.append(f"Total revenue opportunity: ${total_opp:,.0f}")
                if len(underserved) > 0:
                    text_parts.append(f"\nTop underserved segments:\n{underserved.head(10).to_string(index=False)}")
            except Exception as e:
                logger.debug(f"Value Finder processing: {e}")

        text_parts.append(f"\nAll segments:\n{df.to_string(index=False)}")
        return [self._df_to_cdh_parsed(df, filename, source, text_override="\n\n".join(text_parts))]

    def _process_generic(self, df, filename: str, source: CDHDataSource) -> List[ParsedFile]:
        """Fallback: standard DataFrame → ParsedFile conversion with CDH metadata."""
        return [self._df_to_cdh_parsed(df, filename, source)]

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _load_dataframe(self, content: bytes, filename: str, ext: str):
        try:
            import pandas as pd
            if ext in (".csv", ".tsv"):
                sep = "\t" if ext == ".tsv" else ","
                return pd.read_csv(io.BytesIO(content), sep=sep, low_memory=False)
            elif ext in (".xlsx", ".xls"):
                return pd.read_excel(io.BytesIO(content))
            elif ext == ".parquet":
                return pd.read_parquet(io.BytesIO(content))
            elif ext == ".json":
                import json
                data = json.loads(content)
                if isinstance(data, list):
                    return pd.DataFrame(data)
                return pd.DataFrame([data])
        except Exception as e:
            logger.warning(f"DataFrame load failed for {filename}: {e}")
        return None

    def _find_col(self, columns, candidates: List[str]) -> Optional[str]:
        """Find the first matching column name (case-insensitive)."""
        col_lower = {c.lower(): c for c in columns}
        for candidate in candidates:
            if candidate.lower() in col_lower:
                return col_lower[candidate.lower()]
        return None

    def _df_to_cdh_parsed(
        self, df, filename: str, source: CDHDataSource,
        extra_meta: Dict = None, text_override: str = None
    ) -> ParsedFile:
        """Convert DataFrame to ParsedFile with CDH source metadata attached."""
        row_count = len(df)
        columns   = list(df.columns)

        if text_override:
            full_text = text_override
        else:
            summary = source.schema_description()
            sample  = df.head(100).to_string(index=False)
            full_text = f"{summary}\n\nData ({row_count} rows):\n{sample}"

        text_chunks = self._chunk_text(full_text)

        meta = {
            "cdh_source_id":   source.source_id,
            "cdh_source_name": source.display_name,
            "cdh_tags":        source.tags,
        }
        if extra_meta:
            meta.update(extra_meta)

        pf = ParsedFile(
            name=filename,
            file_type=source.source_id,
            text_chunks=text_chunks,
            structured_data=df.head(100).to_dict(orient="records"),
            row_count=row_count,
            columns=columns,
            summary=f"{source.display_name} | {row_count} rows × {len(columns)} cols",
        )
        # Attach CDH metadata as an attribute
        pf.cdh_metadata = meta
        return pf
