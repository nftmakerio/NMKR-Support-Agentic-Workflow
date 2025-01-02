# NMKR Support AI Agent

An intelligent AI-powered support system for [NMKR](https://www.nmkr.io/), designed to provide automated, accurate responses to user queries about NMKR's products and services. This system uses CrewAI to orchestrate multiple AI agents that work together to provide comprehensive support responses.

## Overview

This project implements an AI support system that:
- Processes support requests through REST API and webhooks
- Automatically crawls and analyzes NMKR documentation
- Provides detailed, context-aware responses about NMKR services
- Handles asynchronous processing with Redis queue
- Integrates with Plain for customer support workflows

## Prerequisites

- Docker and Docker Compose
- Python 3.10 or higher
- OpenAI API key
- Plain webhook secret (for webhook integration)

## Quick Start

1. Clone the repository:
```bash
git clone <repository-url>
cd nmkr_support_v4
```

2. Create a `.env` file with your credentials:
```env
MODEL=gpt-4o
OPENAI_API_KEY=your_openai_api_key_here
WEBHOOK_SECRET=your_webhook_secret_here
ANTHROPIC_API_KEY=your_anthropic_key_here  # Optional
SPIDER_API_KEY=your_spider_key_here        # Optional
FIRECRAWL_API_KEY=your_firecrawl_key_here # Optional
```

3. Start using the convenience script:
```bash
chmod +x start.sh
./start.sh
```

Or manually with Docker Compose:
```bash
# Build and start services
docker-compose up --build -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## API Endpoints

### Submit Support Request
```bash
curl -X POST "http://localhost:8000/api/support" \
     -H "Content-Type: application/json" \
     -d '{"query": "How much does it cost to do an Airdrop with NMKR?"}'
```

Response:
```json
{
    "job_id": "123-456-789",
    "status": "queued"
}
```

### Check Request Status
```bash
curl "http://localhost:8000/api/support/status/123-456-789"
```

### Plain Webhook Integration
```bash
curl -X POST "http://localhost:8000/api/webhook" \
     -H "Content-Type: application/json" \
     -H "Plain-Workspace-Id: ws_123" \
     -H "Plain-Event-Type: thread.created" \
     -H "Plain-Event-Id: evt_123" \
     -H "Plain-Signature: your-webhook-signature" \
     -d '{
       "id": "evt_123",
       "type": "thread.created",
       "payload": {
         "message": {
           "content": "How much does it cost to do an Airdrop with NMKR?"
         }
       }
     }'
```

## Project Structure
```
nmkr_support_v4/
├── src/
│   └── nmkr_support_v4/
│       ├── api.py                         # FastAPI application
│       ├── crew.py                        # CrewAI configuration
│       ├── queue_manager.py               # Redis queue management
│       ├── tools/
│       │   └── custom_tool.py            # Web crawling tools
│       ├── links_with_descriptions.json   # NMKR links data
│       └── docs_links_with_descriptions.json
├── docker-compose.yml                     # Docker services configuration
├── Dockerfile                            # Container build instructions
├── requirements.txt                      # Python dependencies
├── setup.py                             # Package configuration
└── start.sh                             # Convenience startup script
```

## Development

1. Install in development mode:
```bash
pip install -e .
```

2. Run locally without Docker:
```bash
# Start Redis
redis-server

# Start RQ worker
rq worker nmkr_support

# Start API
uvicorn nmkr_support_v4.api:app --reload
```

## Configuration

### Environment Variables
- `MODEL`: OpenAI model to use (default: gpt-4o)
- `OPENAI_API_KEY`: Your OpenAI API key
- `WEBHOOK_SECRET`: Secret for Plain webhook verification
- `REDIS_URL`: Redis connection URL (default: redis://localhost:6379)

### Docker Services
- **API**: FastAPI application serving endpoints
- **Worker**: RQ worker processing support requests
- **Redis**: Queue and cache management

## Useful Links

- [NMKR Website](https://www.nmkr.io/)
- [NMKR Documentation](https://docs.nmkr.io/)
- [NMKR Developer Portal](https://developer.nmkr.io/)
- [CrewAI Documentation](https://docs.crewai.com/)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Your chosen license]
