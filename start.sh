#!/bin/bash

# Build and start the containers
docker-compose up --build -d

# Show the logs
docker-compose logs -f 