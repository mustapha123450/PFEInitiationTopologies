📡 IoT Topology Monitoring — README
Projet de supervision et de migrations automatiques de topologie pour une infrastructure IoT déployée sur Kubernetes avec Istio.

🗂️ Structure du projet
.
├── server.js                  # Serveur central IoT
├── gateway.js                 # Logique des gateways (inter et finales)
├── device.js                  # Simulation des devices IoT
├── application.js             # Application cliente qui consomme les données
├── mon1erapproche.py          # Script de monitoring v1 (mesure toutes les 90s)
├── monitoring_iot.py          # Script de monitoring v2 (temps réel, 1s, cooldown 3min)
├── 01-server.yaml             # Déploiement Kubernetes du serveur
├── 02-gateway-inter.yaml      # Déploiement gateway intermédiaire 1
├── 02-gateway-inter-2.yaml    # Déploiement gateway intermédiaire 2
└── 03-gateway-final.yaml      # Déploiement gateway finale

🏗️ Architecture
L'infrastructure IoT est déployée dans le namespace iot-topology sur Kubernetes. Elle est composée de :
[Devices] → [Gateways Finales (GF1/GF2/GF3)] → [Gateways Intermédiaires (Inter-1/Inter-2)] → [Serveur Central]
                                                                    ↑
                                                           [Application Cliente]

Devices : envoient des données capteurs toutes les 3 secondes vers la gateway finale assignée.
Gateways Finales : reçoivent les données des devices et les transfèrent vers une gateway intermédiaire.
Gateways Intermédiaires : agrègent le trafic et le transmettent au serveur central.
Serveur Central : stocke les données et les expose via une API REST.
Application : interroge le serveur pour récupérer les dernières données des devices.


📦 Composants Node.js
server.js
Serveur central Express.js qui expose une API REST pour :

Enregistrer des devices et des gateways (POST /devices/register, POST /gateways/register)
Recevoir des données capteurs (POST /device/:dev/data)
Consulter les données stockées (GET /device/:dev/latest, GET /device/:dev/data)
Health check (GET /health)

gateway.js
Gateway générique (utilisée pour les gateways finales et intermédiaires) qui :

Transfère les enregistrements de devices vers le niveau supérieur
Propage les données capteurs en ajoutant un timestamp de réception
S'enregistre automatiquement auprès de son nœud parent au démarrage

device.js
Simule un device IoT qui :

S'enregistre auprès de sa gateway finale au démarrage
Envoie un incrément de données toutes les 3 secondes

application.js
Client IoT qui interroge le serveur toutes les 5 secondes pour récupérer les dernières données d'un device cible.

🚀 Déploiement Kubernetes
Prérequis

Kubernetes avec Istio installé
Image Docker iot-topology:latest construite localement
Namespace iot-topology créé

bashkubectl create namespace iot-topology
kubectl label namespace iot-topology istio-injection=enabled
Déploiement
bashkubectl apply -f 01-server.yaml
kubectl apply -f 02-gateway-inter.yaml
kubectl apply -f 02-gateway-inter-2.yaml
kubectl apply -f 03-gateway-final.yaml

📊 Monitoring & Migration automatique
Deux approches implémentées
Approche 1 — mon1erapproche.py (mesure toutes les 90s)

Collecte CPU/RAM via l'API Kubernetes Metrics Server
Collecte QPS, latence p95, bande passante via Prometheus/Istio
Déclenche la migration si QPS > 10 req/s, latence > 50 ms, ou CPU > 30 millicores
Retour automatique à la topologie nominale si toutes les métriques repassent sous les seuils normaux
Cooldown de 5 minutes entre deux migrations (recommandation de Mme Imène)

Approche 2 — monitoring_iot.py (temps réel, 1 seconde)

Mesure uniquement le QPS de GF1 via Prometheus (fenêtre 30s)
Migration instantanée dès que le seuil est dépassé ET le cooldown terminé
Cooldown de 3 minutes après chaque changement de topologie
Utilise le threading pour ne pas bloquer la boucle de monitoring pendant la migration

Seuils de migration
MétriqueSeuil critique (→ Topologie 2)Seuil normal (→ Topologie 1)QPS GF1> 10 req/s< 5 req/sLatence p95 GF1> 50 ms< 25 msCPU GF1> 30 millicores< 15 millicores
Lancer le monitoring
bash# Approche 1
python3 mon1erapproche.py

# Approche 2
python3 monitoring_iot.py
Simuler une surcharge (Terminal 2)
bashwhile true; do
  kubectl exec -n iot-topology deployment/device-gf1-1 -- \
    wget -qO- http://iot-gateway-final-1:8281/health > /dev/null 2>&1
  sleep 0.1
done

🔄 Topologies
TopologieDescriptionNominaleTrafic GF1 → Gateway Inter-1 → ServeurModifiéeTrafic GF1 redirigé → Gateway Inter-2 (délestage)
La bascule entre les deux topologies est assurée par le script redirect_gf1_to_inter2.py via les fonctions architecture_modifiee() et architecture_nominale().

🔧 Dépendances Python
bashpip install requests urllib3
Prometheus doit être accessible via port-forward :
bashkubectl port-forward -n istio-system svc/prometheus 9090:9090
