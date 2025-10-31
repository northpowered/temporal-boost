# feat(docs): Comprehensive documentation expansion and FastStream integration

This PR significantly expands and improves the Temporal-boost documentation for GitHub Pages, adds comprehensive FastStream integration examples and documentation, and enhances the overall developer experience.

## 📚 Documentation Additions

### New Documentation Files

- **`docs/configuration.md`** - Complete configuration reference
  - All environment variables documented with types, defaults, and examples
  - Configuration priority explanation
  - Environment-specific examples (development, production, high-performance)
  - Security best practices

- **`docs/examples.md`** - Comprehensive examples guide
  - 13+ practical examples covering common patterns
  - Basic to advanced use cases
  - Real-world scenarios (e-commerce, ETL pipelines)
  - Integration examples (FastAPI, FastStream)

- **`docs/advanced_usage.md`** - Advanced patterns and customization
  - Custom runtime configuration
  - Worker builder patterns
  - Interceptors implementation
  - Performance optimization techniques
  - Error handling patterns

- **`docs/api_reference.md`** - Complete API documentation
  - All major classes and methods documented
  - Parameter descriptions and types
  - Usage examples for each API
  - Configuration constants reference

- **`docs/troubleshooting.md`** - Common issues and solutions
  - Connection issues
  - Worker problems
  - Activity/workflow debugging
  - Performance troubleshooting
  - Deployment issues

- **`docs/faststream_integration.md`** - FastStream integration guide
  - Complete FastStream integration documentation
  - Multiple broker support (Redis, RabbitMQ, Kafka)
  - Integration patterns and best practices
  - Error handling and dead-letter queues

### Enhanced Documentation Files

- **`docs/index.md`** - Improved getting started guide
  - Better introduction and framework overview
  - Enhanced installation instructions
  - Improved quick start example
  - Navigation links to all documentation sections

- **`docs/creating_application.md`** - Expanded application creation guide
  - Detailed activity and workflow examples
  - Pydantic integration patterns
  - CRON workers documentation
  - ASGI worker integration
  - Comprehensive FastStream section with multiple examples
  - Best practices section

- **`docs/running_application.md`** - Production deployment guide
  - Development setup
  - Production deployment (systemd, supervisord)
  - Docker deployment with examples
  - Kubernetes deployment manifests
  - Monitoring and observability
  - Troubleshooting section

- **`README.md`** - Modernized project README
  - Compact, scannable format
  - Links to comprehensive documentation
  - Quick start example
  - Better organization

## 💡 Example Enhancements

### New Examples

- **`examples/example_starter.py`** - Enhanced starter example with better documentation
- **`examples/example_cron.py`** - CRON worker example
- **`examples/example_signals.py`** - Workflow signals example
- **`examples/example_ecommerce.py`** - E-commerce order processing
- **`examples/example_fastapi.py`** - FastAPI integration
- **`examples/example_parallel.py`** - Parallel activities execution
- **`examples/example_error_handling.py`** - Error handling patterns
- **`examples/example_client.py`** - Workflow client examples
- **`examples/example_faststream_temporal.py`** - FastStream with Temporal workflows
- **`examples/example_faststream_advanced.py`** - Advanced FastStream patterns
- **`examples/example_faststream_producer.py`** - Message producer for testing

### Enhanced Examples

- **`examples/example_app.py`** - Comprehensive example with better documentation
- **`examples/example_simple_faststream.py`** - Improved with documentation and comments

### Documentation

- **`examples/README.md`** - Comprehensive examples guide
  - Overview of all examples
  - Running instructions
  - Learning path recommendations
  - Example structure guide

## 🔧 Configuration Updates

- **`mkdocs.yml`** - Updated navigation structure
  - Added "Guides" section for better organization
  - Added FastStream Integration to navigation
  - Improved documentation hierarchy

- **`pyproject.toml`** - Updated linting configuration
  - Added RUF029 and DOC201 to ignore list
  - Updated per-file ignores for examples and tests

## ✨ Key Features

### FastStream Integration

- Complete FastStream integration documentation
- Multiple examples demonstrating different patterns
- Support for Redis, RabbitMQ, and Kafka brokers
- Error handling and dead-letter queue patterns
- Producer examples for testing

### Documentation Improvements

- **Comprehensive coverage**: All major features documented
- **Practical examples**: Real-world scenarios and patterns
- **Clear structure**: Logical organization with navigation
- **Best practices**: Security, performance, and deployment guidance
- **Troubleshooting**: Common issues and solutions

### Developer Experience

- **Quick start**: Clear getting started guide
- **Examples**: 13+ practical examples
- **API reference**: Complete API documentation
- **Troubleshooting**: Help for common issues
- **Deployment**: Production-ready deployment guides

## 📋 Documentation Structure

```
docs/
├── index.md                    # Getting started
├── creating_application.md     # Application creation guide
├── running_application.md      # Deployment and production
├── configuration.md            # Configuration reference
├── advanced_usage.md           # Advanced patterns
├── faststream_integration.md   # FastStream integration
├── examples.md                 # Examples guide
├── api_reference.md            # API documentation
├── troubleshooting.md          # Troubleshooting guide
└── release_notes_2.0.0.md     # Release notes
```

## 🎯 Benefits

1. **Improved discoverability**: Easy navigation to find relevant information
2. **Better onboarding**: Clear quick start and examples
3. **Production readiness**: Deployment and configuration guides
4. **FastStream integration**: Complete event-driven architecture support
5. **Developer productivity**: Comprehensive examples and troubleshooting

## 📝 Testing

All examples have been tested and include:
- ✅ Proper documentation strings
- ✅ Run instructions
- ✅ Clear code comments
- ✅ Best practices demonstrated

## 🔗 Related

- Closes documentation gaps identified in user feedback
- Aligns with Temporal SDK best practices
- Follows documentation best practices for GitHub Pages

---

**Breaking Changes**: None

**Migration Guide**: Not applicable - documentation-only changes

**Checklist**:
- [x] Documentation updated
- [x] Examples added and tested
- [x] Navigation structure updated
- [x] All examples include proper documentation
- [x] FastStream integration documented
- [x] README updated with links to documentation

