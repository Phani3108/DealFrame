"""OpenTelemetry setup — import get_tracer() in every module to instrument spans."""

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

_tracer: trace.Tracer | None = None


def setup_telemetry(
    service_name: str = "temporalos",
    otlp_endpoint: str = "",
    enabled: bool = True,
) -> None:
    """
    Initialize the global TracerProvider.
    Call once at application startup (FastAPI lifespan).
    """
    global _tracer

    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    if enabled:
        if otlp_endpoint:
            # Only import if actually needed to keep startup fast when OTLP is off
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        else:
            # Fall back to console export in dev — shows spans in stdout
            provider.add_span_processor(
                BatchSpanProcessor(ConsoleSpanExporter())
            )

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(service_name)


def get_tracer() -> trace.Tracer:
    """Return the global tracer, initialising with defaults if not yet set up."""
    global _tracer
    if _tracer is None:
        setup_telemetry()
    return _tracer  # type: ignore[return-value]
