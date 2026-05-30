"""
PySpark Structured Streaming — Market Feature Pipeline

Reads from Kafka topics "trades" and "orders", computes four
market microstructure features every 10 seconds, and writes
them to the PostgreSQL "market_features" table.

Features per window:
  • trade_volume    — total quantity traded
  • vwap            — volume-weighted average price
  • order_imbalance — aggressive buy count − aggressive sell count
  • trade_velocity  — trades per second (count / 10)

Run inside the spark container:
    spark-submit \
      --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,\
                 org.postgresql:postgresql:42.7.1 \
      spark/feature_pipeline.py
"""

import os
import logging

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, sum as _sum, count, when, lit, coalesce,
    to_timestamp, window,
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType,
)

logging.basicConfig(level=logging.WARN)
logger = logging.getLogger("feature_pipeline")

# ── Config ─────────────────────────────────────────────────────────────────

KAFKA_BOOTSTRAP  = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
POSTGRES_HOST    = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT    = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB      = os.getenv("POSTGRES_DB", "flashledger")
POSTGRES_USER    = os.getenv("POSTGRES_USER", "flashledger")
POSTGRES_PASS    = os.getenv("POSTGRES_PASSWORD", "flashledger")
POSTGRES_JDBC    = f"jdbc:postgresql://{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
WINDOW_DURATION  = "10 seconds"
WATERMARK        = "30 seconds"
CHECKPOINT_BASE  = "/tmp/flashledger-checkpoints"

# ── Spark Session ──────────────────────────────────────────────────────────

spark = (
    SparkSession.builder
    .appName("FlashLedger-FeaturePipeline")
    .config("spark.sql.shuffle.partitions", "4")
    .config("spark.streaming.stopGracefullyOnShutdown", "true")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("WARN")

# ── Schemas ────────────────────────────────────────────────────────────────

TRADE_SCHEMA = StructType([
    StructField("trade_id",       StringType(), True),
    StructField("buy_order_id",   StringType(), True),
    StructField("sell_order_id",  StringType(), True),
    StructField("buyer_id",       StringType(), True),
    StructField("seller_id",      StringType(), True),
    StructField("price",          DoubleType(), True),
    StructField("quantity",       DoubleType(), True),
    StructField("aggressor_side", StringType(), True),
    StructField("timestamp",      StringType(), True),
])

ORDER_SCHEMA = StructType([
    StructField("order_id",  StringType(), True),
    StructField("user_id",   StringType(), True),
    StructField("side",      StringType(), True),
    StructField("price",     DoubleType(), True),
    StructField("quantity",  DoubleType(), True),
    StructField("timestamp", StringType(), True),
])

# ── Kafka Readers ──────────────────────────────────────────────────────────

def _kafka_stream(topic: str):
    return (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
        .option("subscribe", topic)
        .option("startingOffsets", "latest")
        .option("failOnDataLoss", "false")
        .load()
    )

raw_trades = _kafka_stream("trades")
raw_orders = _kafka_stream("orders")

# ── Parse ──────────────────────────────────────────────────────────────────

trades = (
    raw_trades
    .select(from_json(col("value").cast("string"), TRADE_SCHEMA).alias("t"))
    .select("t.*")
    .withColumn("event_time", to_timestamp("timestamp"))
    .filter(col("event_time").isNotNull())
)

orders = (
    raw_orders
    .select(from_json(col("value").cast("string"), ORDER_SCHEMA).alias("o"))
    .select("o.*")
    .withColumn("event_time", to_timestamp("timestamp"))
    .filter(col("event_time").isNotNull())
)

# ── Feature Aggregations ───────────────────────────────────────────────────

# trade_volume, vwap, trade_velocity from trades stream
trade_features = (
    trades
    .withWatermark("event_time", WATERMARK)
    .groupBy(window("event_time", WINDOW_DURATION).alias("w"))
    .agg(
        _sum("quantity").alias("trade_volume"),
        (_sum(col("price") * col("quantity")) / _sum("quantity")).alias("vwap"),
        count("trade_id").alias("trade_count"),
        # order_imbalance from aggressor_side in trade events
        (
            _sum(when(col("aggressor_side") == "buy",  lit(1.0)).otherwise(lit(0.0))) -
            _sum(when(col("aggressor_side") == "sell", lit(1.0)).otherwise(lit(0.0)))
        ).alias("order_imbalance"),
    )
    .withColumn("trade_velocity", col("trade_count") / lit(10.0))
    .select(
        col("w.start").alias("window_start"),
        col("w.end").alias("window_end"),
        coalesce(col("trade_volume"),    lit(0.0)).alias("trade_volume"),
        coalesce(col("vwap"),            lit(0.0)).alias("vwap"),
        coalesce(col("order_imbalance"), lit(0.0)).alias("order_imbalance"),
        coalesce(col("trade_velocity"),  lit(0.0)).alias("trade_velocity"),
    )
)

# ── Write to PostgreSQL ────────────────────────────────────────────────────

JDBC_PROPS = {
    "user":     POSTGRES_USER,
    "password": POSTGRES_PASS,
    "driver":   "org.postgresql.Driver",
}


def _write_batch(batch_df, epoch_id: int) -> None:
    """Write one micro-batch of features to PostgreSQL via JDBC."""
    rows = batch_df.count()
    if rows == 0:
        return
    logger.warning("epoch=%d  writing %d feature row(s) to market_features", epoch_id, rows)
    (
        batch_df.write
        .format("jdbc")
        .option("url",      POSTGRES_JDBC)
        .option("dbtable",  "market_features")
        .option("user",     POSTGRES_USER)
        .option("password", POSTGRES_PASS)
        .option("driver",   "org.postgresql.Driver")
        .mode("append")
        .save()
    )


query = (
    trade_features.writeStream
    .outputMode("update")
    .trigger(processingTime=WINDOW_DURATION)
    .foreachBatch(_write_batch)
    .option("checkpointLocation", f"{CHECKPOINT_BASE}/features")
    .start()
)

logger.warning("Feature pipeline running — consuming from Kafka [%s] …", KAFKA_BOOTSTRAP)
query.awaitTermination()
