# Configuración de GitHub para CI/CD (Opcional)

Este archivo contiene configuración para automatizar build y push a Docker Hub.

## Archivos necesarios

1. Crear archivo: `.github/workflows/docker-build.yml`

```yaml
name: Build and Push Docker Image

on:
  push:
    branches:
      - main
    tags:
      - 'v*'
  pull_request:
    branches:
      - main

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2
      
      - name: Login to Docker Hub
        uses: docker/login-action@v2
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}
      
      - name: Build and push
        uses: docker/build-push-action@v4
        with:
          context: .
          push: true
          tags: |
            ${{ secrets.DOCKER_USERNAME }}/autobixpe:latest
            ${{ secrets.DOCKER_USERNAME }}/autobixpe:${{ github.ref_name }}
          cache-from: type=registry,ref=${{ secrets.DOCKER_USERNAME }}/autobixpe:buildcache
          cache-to: type=registry,ref=${{ secrets.DOCKER_USERNAME }}/autobixpe:buildcache,mode=max
```

## Setup en GitHub

### 1. Agregar Secrets
- Ir a: `Settings` → `Secrets and variables` → `Actions`
- Click `New repository secret`

Agregar:
- **Name**: `DOCKER_USERNAME` → Tu usuario de Docker Hub
- **Name**: `DOCKER_PASSWORD` → Tu token de Docker Hub

### 2. Docker Hub Setup (si no tienes cuenta)
- Registrate en https://hub.docker.com
- Crea un token en `Account Settings` → `Security`

### Resultado
Cada push a `main` automáticamente:
1. Construye la imagen Docker
2. La sube a Docker Hub
3. Disponible como: `tu-usuario/autobixpe:latest`

---

Luego en Portainer puedes usar `tu-usuario/autobixpe:latest`
