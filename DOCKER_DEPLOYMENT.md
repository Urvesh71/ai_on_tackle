# Kyra Tackle Box - Docker Deployment Guide

## Prerequisites

- Docker installed: https://docs.docker.com/get-docker/
- Docker Compose installed: https://docs.docker.com/compose/install/
- (Optional) NVIDIA GPU drivers for Ollama acceleration

## Quick Start

### 1. Clone/Copy Your Project

```bash
cd your-project-folder
```

### 2. Start All Services

```bash
# Build and start all containers
docker-compose up -d --build
```

### 3. Pull Ollama Model (First Time Only)

```bash
# Pull the Llama 3.1:8b model
docker exec -it kyra-ollama ollama pull llama3.1:8b
```

### 4. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8001
- **MongoDB**: localhost:27017
- **Ollama**: http://localhost:11434

## Commands

### Start Services
```bash
docker-compose up -d
```

### Stop Services
```bash
docker-compose down
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f ollama
```

### Rebuild After Code Changes
```bash
docker-compose up -d --build
```

### Check Running Containers
```bash
docker-compose ps
```

## GPU Support (NVIDIA)

To enable GPU acceleration for Ollama:

1. Install NVIDIA Container Toolkit:
```bash
# Ubuntu/Debian
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

2. Uncomment GPU section in `docker-compose.yml`:
```yaml
ollama:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

3. Restart services:
```bash
docker-compose down
docker-compose up -d
```

## Production Deployment

For production, use the Nginx reverse proxy:

```bash
docker-compose --profile production up -d
```

Then access via:
- **Application**: http://localhost (port 80)
- **API**: http://localhost/api

## Environment Variables

### Backend (.env)
```
MONGO_URL=mongodb://mongodb:27017
DB_NAME=kyra_db
CORS_ORIGINS=*
OLLAMA_HOST=http://ollama:11434
```

### Frontend
Set `REACT_APP_BACKEND_URL` in docker-compose.yml build args.

## Troubleshooting

### Ollama not responding
```bash
# Check if model is downloaded
docker exec -it kyra-ollama ollama list

# Pull model if missing
docker exec -it kyra-ollama ollama pull llama3.1:8b
```

### Backend connection issues
```bash
# Check backend logs
docker-compose logs backend

# Restart backend
docker-compose restart backend
```

### MongoDB connection issues
```bash
# Check if MongoDB is running
docker-compose ps mongodb

# Check MongoDB logs
docker-compose logs mongodb
```

## File Structure

```
your-project/
├── docker-compose.yml      # Main orchestration file
├── backend/
│   ├── Dockerfile          # Backend container config
│   ├── .dockerignore
│   ├── server.py
│   ├── rag_retriever.py
│   ├── commands.json
│   └── requirements.txt
├── frontend/
│   ├── Dockerfile          # Frontend container config
│   ├── .dockerignore
│   ├── nginx.conf          # Frontend Nginx config
│   └── src/
└── nginx/
    └── nginx.conf          # Reverse proxy config (production)
```
