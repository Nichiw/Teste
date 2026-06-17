#!/bin/bash
# deploy.sh — build e deploy completo no minikube (modo teste local)
set -e

echo "Iniciando minikube..."
minikube start --driver=docker --memory=4096 --cpus=2

echo "Apontando docker para o daemon do minikube..."
eval $(minikube docker-env)

echo "Build das imagens..."
docker build -t auth-service:latest ./auth_service
docker build -t recovery-service:latest ./recovery_service
docker build -t doctors-service:latest ./doctor_service
docker build -t scheduling-service:latest ./schedule_service
docker build -t gateway:latest ./gateway

echo "Aplicando secrets..."
kubectl apply -f k8s/secrets.yaml

echo "Aplicando ConfigMaps (SQL)..."
kubectl apply -f k8s/db-configmaps.yaml

echo "Subindo bancos..."
kubectl apply -f k8s/databases.yaml

echo "Aguardando bancos ficarem prontos..."
kubectl wait --for=condition=ready pod -l app=credentials-db --timeout=120s
kubectl wait --for=condition=ready pod -l app=doctors-db --timeout=120s
kubectl wait --for=condition=ready pod -l app=scheduling-db --timeout=120s

echo "Aguardando MySQL aceitar conexoes (30s)..."
sleep 30

echo "Subindo microsservicos..."
kubectl apply -f k8s/auth-service.yaml
kubectl apply -f k8s/recovery-service.yaml
kubectl apply -f k8s/doctors-service.yaml
kubectl apply -f k8s/scheduling-service.yaml
kubectl apply -f k8s/gateway.yaml

echo "Aguardando microsservicos ficarem prontos..."
kubectl wait --for=condition=ready pod -l app=auth-service --timeout=60s
kubectl wait --for=condition=ready pod -l app=recovery-service --timeout=60s
kubectl wait --for=condition=ready pod -l app=doctors-service --timeout=60s
kubectl wait --for=condition=ready pod -l app=scheduling-service --timeout=60s
kubectl wait --for=condition=ready pod -l app=gateway --timeout=60s

echo ""
echo "Deploy completo!"
echo ""
echo "Expondo gateway via port-forward em background..."
kubectl port-forward service/gateway 8080:8080 &
echo "Gateway disponivel em http://localhost:8080"
echo ""
echo "Para subir o frontend:"
echo "  cd frontend && npm install && npm run dev"
echo ""
echo "Para parar o port-forward: kill %1"
