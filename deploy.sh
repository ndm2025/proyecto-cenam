#!/bin/bash
# Script de despliegue para AWS EC2
# Ejecutar en la instancia EC2 después de conectarse por SSH

set -e

echo "=== Actualizando sistema ==="
sudo apt update && sudo apt upgrade -y

echo "=== Instalando Docker ==="
sudo apt install -y docker.io docker-compose
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER

echo "=== Clonando repositorio ==="
cd /home/ubuntu
git clone https://github.com/ndm2025/proyecto-cenam.git
cd proyecto-cenam

echo "=== Construyendo y ejecutando contenedor ==="
sudo docker-compose up -d --build

echo "=== Configurando firewall ==="
sudo ufw allow 8501/tcp
sudo ufw allow 22/tcp
sudo ufw --force enable

echo "=== Despliegue completado ==="
echo "Accede a: http://$(curl -s http://checkip.amazonaws.com):8501"
