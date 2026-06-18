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

echo "Aguardando MySQL aceitar conexoes..."

wait_mysql() {
  local POD=$1
  local DB=$2
  echo "Verificando MySQL em $POD..."
  for i in $(seq 1 20); do
    if kubectl exec -i $POD -- mysql -u medmatch -pmedmatch123 $DB -e "SELECT 1;" > /dev/null 2>&1; then
      echo "MySQL pronto em $POD!"
      return 0
    fi
    echo "  Tentativa $i/20 - aguardando 5s..."
    sleep 5
  done
  echo "ERRO: MySQL nao ficou pronto em $POD"
  exit 1
}

CREDENTIALS_POD=$(kubectl get pod -l app=credentials-db -o jsonpath="{.items[0].metadata.name}")
DOCTORS_POD=$(kubectl get pod -l app=doctors-db -o jsonpath="{.items[0].metadata.name}")
SCHEDULING_POD=$(kubectl get pod -l app=scheduling-db -o jsonpath="{.items[0].metadata.name}")

wait_mysql $CREDENTIALS_POD medmatch_credentials
wait_mysql $DOCTORS_POD medmatch_doctors
wait_mysql $SCHEDULING_POD medmatch_scheduling

echo "Gerando hash da senha padrao..."
HASH=$(docker run --rm auth-service:latest python3 -c "
from passlib.context import CryptContext
ctx = CryptContext(schemes=['bcrypt'], deprecated='auto')
print(ctx.hash('medmatch123'))
")
echo "Hash gerado."

echo "Populando dados iniciais..."

# Apenas admin e paciente de teste — medicos se registram pelo proprio sistema
kubectl exec -i $CREDENTIALS_POD -- mysql -u medmatch -pmedmatch123 medmatch_credentials << SQL
INSERT IGNORE INTO usuarios (id, nome, email, senha_hash, perfil, criado_em) VALUES
(1, 'Admin Padrao',   'admin@medmatch.com',    '$HASH', 'administrador', NOW()),
(2, 'Paciente Teste', 'paciente@medmatch.com', '$HASH', 'paciente',      NOW());
SQL

echo "Dados iniciais inseridos!"

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
echo "=========================================="
echo "Deploy completo!"
echo "=========================================="
echo ""
echo "Expondo gateway via port-forward..."
kubectl port-forward service/gateway 8080:8080 &
echo ""
echo "Usuarios pre-cadastrados (senha: medmatch123):"
echo "  admin@medmatch.com     -> Administrador"
echo "  paciente@medmatch.com  -> Paciente"
echo ""
echo "Para cadastrar medicos: use a tela de registro do frontend com perfil Medico."
echo ""
echo "Para subir o frontend:"
echo "  cd frontend && npm install && npm run dev"