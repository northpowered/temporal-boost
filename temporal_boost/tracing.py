from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter


def create_tracer(service_name: str, otlp_endpoint: str, tracer_name: str = __name__) -> trace.Tracer:

    trace.set_tracer_provider(
        TracerProvider(
            resource=Resource.create({SERVICE_NAME: service_name}),
        )
    )

    tempo_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)

    tempo_span_processor = BatchSpanProcessor(tempo_exporter)

    tracer = trace.get_tracer_provider()

    tracer.add_span_processor(tempo_span_processor)

    tracer = trace.get_tracer(tracer_name)

    return tracer
